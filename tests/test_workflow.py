"""LangGraph 工作流：运行、interrupt / 恢复、持久化、权限、旧接口兼容、新页面"""
import pytest

from app import create_app
from workflow.spec import OPTIONAL_GATES, PARALLEL_AUDITS, REQUIRED_GATES, STAGE_IDS

REMOTE = {"REMOTE_ADDR": "10.0.0.8"}


def start(client, **kw):
    resp = client.post("/api/workflow/runs", json={"site": "demo.com", "topic": "主题权威", **kw})
    assert resp.status_code == 201, resp.get_json()
    return resp.get_json()


def resume(client, tid, **body):
    return client.post(f"/api/workflow/runs/{tid}/resume", json=body)


def test_graph_spec(client):
    data = client.get("/api/workflow/graph").get_json()
    assert data["stage_count"] == 17 and data["gate_count"] == 6 and data["optional_gates"] == ["fanout", "tool_select"]
    assert data["parallel"] == PARALLEL_AUDITS
    assert "gate_keywords" in data["mermaid"]
    assert all(t["kind"] == "sample" for t in data["tools"].values())  # 未接 LLM / 真实 API


def test_run_pauses_at_first_gate(client):
    v = start(client)
    assert v["status"] == "waiting_approval"
    assert v["pending_approval"]["gate"] == "keywords"
    assert v["stages"]["benchmark"] == "done" and v["stages"]["map_topical_clusters"] == "pending"
    assert v["progress"]["done"] == 2
    assert v["pending_approval"]["proposal"]["priority_keywords"][0] == "主题权威 入门"
    # 旧版 human_gate 字符串标记已移除
    assert all("human_gate" not in a for a in v["artifacts"].values())


def test_full_run_with_edits_and_rewrite(client):
    tid = start(client)["thread_id"]
    v = resume(client, tid, action="edit", edits={"priority_keywords": ["长尾词A", "长尾词B"]}, comment="先做长尾").get_json()
    assert v["pending_approval"]["gate"] == "brief"
    assert v["artifacts"]["create_brief"]["target_keywords"] == ["长尾词A", "长尾词B"]
    # 打回重写：create_brief 重新执行，版本 +1
    v = resume(client, tid, action="reject", comment="补充案例").get_json()
    assert v["pending_approval"]["gate"] == "brief" and v["brief_revision"] == 1
    assert v["pending_approval"]["proposal"]["version"] == 2
    v = resume(client, tid, action="edit", edits={"title": "人工改过的标题"}).get_json()
    assert v["pending_approval"]["gate"] == "publish"
    # 并行审计分支三项都完成并已汇合
    assert all(v["stages"][s] == "done" for s in PARALLEL_AUDITS)
    assert v["pending_approval"]["proposal"]["audits"]["citation_rate"]
    v = resume(client, tid, action="approve").get_json()
    assert v["pending_approval"]["gate"] == "outreach"
    proposed = v["pending_approval"]["proposal"]["approved_targets"]
    assert "generic-directory.net" not in proposed  # 低于阈值的不默认外展
    v = resume(client, tid, action="edit", edits={"approved_targets": ["data-report.io"]}).get_json()
    assert v["status"] == "completed" and v["pending_approval"] is None
    assert v["progress"]["done"] == len(STAGE_IDS)
    assert v["summary"]["outreach_targets"] == ["data-report.io"]
    assert v["summary"]["brief_title"] == "人工改过的标题"
    assert [a["gate"] for a in v["approvals"]] == ["keywords", "brief", "brief", "publish", "outreach"]
    mem = v["artifacts"]["memory_extract"]["memories"]
    assert any("先做长尾" in m["content"] for m in mem)
    assert all(v["gates"][g] == "approved" for g in REQUIRED_GATES)
    assert all(v["gates"][g] == "off" for g in OPTIONAL_GATES)


def test_reject_ends_run(client):
    tid = start(client)["thread_id"]
    v = resume(client, tid, action="reject").get_json()
    assert v["status"] == "rejected"
    assert v["stages"]["map_topical_clusters"] == "skipped"
    assert resume(client, tid, action="approve").status_code == 409  # 已结束，无闸门可审


def test_brief_rewrite_limit(client):
    tid = start(client)["thread_id"]
    resume(client, tid, action="approve")
    resume(client, tid, action="reject")
    v = resume(client, tid, action="reject").get_json()
    assert v["brief_revision"] == 2 and v["pending_approval"]["revisions_left"] == 0
    v = resume(client, tid, action="reject").get_json()
    assert v["status"] == "rejected"


@pytest.mark.parametrize("body,code", [
    ({"action": "maybe"}, 400),
    ({"action": "edit", "edits": {"priority_keywords": []}}, 400),
    ({"action": "edit", "edits": {"priority_keywords": ["x" * 51]}}, 400),
    ({"action": "approve", "comment": "x" * 501}, 400),
    ({"action": "approve", "gate": "outreach"}, 409),
])
def test_resume_validation(client, body, code):
    tid = start(client)["thread_id"]
    assert resume(client, tid, **body).status_code == code
    # 校验失败不改变状态
    assert client.get(f"/api/workflow/runs/{tid}").get_json()["pending_approval"]["gate"] == "keywords"


def test_unknown_outreach_target_rejected(client):
    tid = start(client)["thread_id"]
    for _ in range(3):
        resume(client, tid, action="approve")
    assert resume(client, tid, action="edit", edits={"approved_targets": ["evil.com"]}).status_code == 400


def test_unknown_run(client):
    assert client.get("/api/workflow/runs/run-0000000000").status_code == 404
    assert client.get("/api/workflow/runs/../../etc").status_code == 404
    assert resume(client, "run-0000000000", action="approve").status_code == 404


def test_persistence_across_restart(tmp_path):
    cfg = {"TESTING": True, "DATA_FILE": str(tmp_path / "d.json")}
    c1 = create_app(cfg).test_client()
    tid = start(c1)["thread_id"]
    resume(c1, tid, action="approve")
    c2 = create_app(cfg).test_client()  # 模拟重启：新进程、新连接
    v = c2.get(f"/api/workflow/runs/{tid}").get_json()
    assert v["pending_approval"]["gate"] == "brief"
    runs = c2.get("/api/workflow/runs").get_json()
    assert runs["runs"][0]["thread_id"] == tid and runs["counts"]["waiting_approval"] == 1
    v = resume(c2, tid, action="approve").get_json()  # 重启后继续审批
    assert v["pending_approval"]["gate"] == "publish"


def test_runs_list_and_counts(client):
    a = start(client)["thread_id"]
    b = start(client, topic="第二个")["thread_id"]
    resume(client, a, action="reject")
    data = client.get("/api/workflow/runs").get_json()
    assert {r["thread_id"] for r in data["runs"]} == {a, b}
    assert data["counts"] == {"total": 2, "waiting_approval": 1, "completed": 0, "rejected": 1}
    assert data["runs"][0]["pending_gate_title"] in (None, "关键词优先级确认")


# ---- 权限 ----
def test_remote_cannot_start_or_approve(client):
    assert client.post("/api/workflow/runs", json={}, environ_base=REMOTE).status_code == 403
    tid = start(client)["thread_id"]
    assert client.post(f"/api/workflow/runs/{tid}/resume", json={"action": "approve"},
                       environ_base=REMOTE).status_code == 403
    assert client.get(f"/api/workflow/runs/{tid}", environ_base=REMOTE).status_code == 200  # 可只读查看


def test_token_protects_workflow(tmp_path):
    app = create_app({"TESTING": True, "DATA_FILE": str(tmp_path / "t.json"), "ADMIN_TOKEN": "tok"})
    c = app.test_client()
    assert c.post("/api/workflow/runs", json={}).status_code == 401
    h = {"Authorization": "Bearer tok"}
    tid = c.post("/api/workflow/runs", json={}, headers=h).get_json()["thread_id"]
    assert c.post(f"/api/workflow/runs/{tid}/resume", json={"action": "approve"}).status_code == 401
    assert c.post(f"/api/workflow/runs/{tid}/resume", json={"action": "approve"}, headers=h).status_code == 200


def test_cross_site_approve_blocked(client):
    tid = start(client)["thread_id"]
    resp = client.post(f"/api/workflow/runs/{tid}/resume", json={"action": "approve"},
                       headers={"Origin": "https://evil.example"})
    assert resp.status_code == 403


# ---- 兼容与新页面 ----
def test_legacy_endpoint_still_works(client):
    data = client.post("/api/ai/seo-workflow", json={"site": "a.com"}).get_json()
    assert data["status"] == "success" and data["mode"] == "legacy"
    assert "/workflow-runs" in data["note"]


@pytest.mark.parametrize("text,target", [
    ("帮我做一次 E-E-A-T 信任审计", "eeat_audit_react"),
    ("我的 SEO 学习路径怎么安排", "seo_learning_path_react"),
    ("看看任务进度", "progress_analyzer_react"),
    ("画个思维导图", "mindmap_generator"),
    ("给我推荐可视化方案", "recommender"),
    ("今天天气", "recommender"),
])
def test_supervisor_rule_router(client, text, target):
    data = client.post("/api/ai/route", json={"request": text}).get_json()
    assert data["route"]["target"] == target
    assert data["status"] == "success"


def test_router_workflow_does_not_start_run(client):
    data = client.post("/api/ai/route", json={"request": "启动外链工作流"}).get_json()
    assert data["route"]["target"] == "workflow" and data["result"]["link"] == "/workflow-runs"
    assert client.get("/api/workflow/runs").get_json()["counts"]["total"] == 0


def test_router_validation(client):
    assert client.post("/api/ai/route", json={"request": ""}).status_code == 400


def test_knowledge_pages(client):
    arch = client.get("/agent-architecture").get_data(as_text=True)
    pat = client.get("/agent-patterns").get_data(as_text=True)
    assert "分阶段路线图" in arch and "interrupt" in arch and "cursor.com/canvas" in arch
    assert "LangGraph（采用）" in pat and "Orchestrator-worker" in pat and "CrewAI" in pat
    runs = client.get("/workflow-runs").get_data(as_text=True)
    assert "const SPEC" in runs and "关键词优先级确认" in runs


def test_dashboard_and_sidebar_show_pending(client):
    start(client)
    html = client.get("/dashboard").get_data(as_text=True)
    assert "1 个 SEO 工作流停在人工闸门" in html
    assert 'class="badge-dot"' in html
    assert "1 个待审批" in client.get("/mobile").get_data(as_text=True)
