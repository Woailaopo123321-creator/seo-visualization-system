import pytest


def test_health(client):
    data = client.get("/health").get_json()
    assert data["status"] == "ok"
    assert data["agent_count"] == 7


def test_tasks_crud(client):
    tasks = client.get("/api/tasks").get_json()
    assert isinstance(tasks, list) and len(tasks) == 10

    resp = client.post("/api/tasks", json={"title": "  新任务  ", "subtitle": "备注", "priority": "high"})
    assert resp.status_code == 201
    task = resp.get_json()
    assert task["title"] == "新任务" and task["status"] == "todo" and task["priority"] == "high"

    resp = client.put(f"/api/tasks/{task['id']}", json={"status": "done"})
    assert resp.status_code == 200
    assert resp.get_json()["progress"] == 100  # 完成自动 100%

    resp = client.put(f"/api/tasks/{task['id']}", json={"progress": 40, "status": "in_progress"})
    assert resp.get_json()["progress"] == 40

    assert len(client.get("/api/tasks").get_json()) == 11  # 已持久化
    assert client.delete(f"/api/tasks/{task['id']}").status_code == 200
    assert client.delete(f"/api/tasks/{task['id']}").status_code == 404
    assert len(client.get("/api/tasks").get_json()) == 10


def test_task_stats(client):
    stats = client.get("/api/tasks/stats").get_json()
    assert stats["total"] == 10 and stats["done"] == 2


@pytest.mark.parametrize("payload", [
    {},
    {"title": ""},
    {"title": "   "},
    {"title": "x" * 81},
    {"title": "ok", "status": "bogus"},
    {"title": "ok", "progress": 101},
    {"title": "ok", "progress": "50"},
    {"title": "ok", "priority": "urgent"},
])
def test_task_validation(client, payload):
    resp = client.post("/api/tasks", json=payload)
    assert resp.status_code == 400
    assert "error" in resp.get_json()


def test_task_body_must_be_object(client):
    assert client.post("/api/tasks", json=["a"]).status_code == 400


def test_update_missing_and_empty(client):
    assert client.put("/api/tasks/9999", json={"title": "x"}).status_code == 404
    assert client.put("/api/tasks/1", json={}).status_code == 400
    assert client.put("/api/tasks/1", json={"id": 5}).status_code == 400  # 不允许改 id


@pytest.mark.parametrize("url,body", [
    ("/api/ai/analyze", {}),
    ("/api/ai/analyze-react", {}),
    ("/api/ai/react", {}),
    ("/api/ai/seo-path", {}),
    ("/api/ai/eeat-audit", {}),
    ("/api/ai/eeat-audit", {"content_sample": "示例内容"}),
    ("/api/ai/seo-workflow", {"site": "demo.com", "topic": "主题权威"}),
    ("/api/ai/mindmap", {"topic": "SEO 基础"}),
    ("/api/ai/recommend", {"context": "planning"}),
    ("/api/ai/recommend", {"type": "complex"}),  # 兼容旧字段
])
def test_ai_endpoints_success(client, url, body):
    resp = client.post(url, json=body)
    assert resp.status_code == 200, resp.get_json()
    data = resp.get_json()
    assert data["status"] == "success"
    assert "agent" in data


@pytest.mark.parametrize("url,body", [
    ("/api/ai/mindmap", {"topic": ""}),
    ("/api/ai/mindmap", {"topic": "x" * 51}),
    ("/api/ai/recommend", {"context": "nope"}),
    ("/api/ai/seo-workflow", {"site": 123}),
])
def test_ai_validation(client, url, body):
    assert client.post(url, json=body).status_code == 400


def test_seo_workflow_runs_all_stages(client):
    data = client.post("/api/ai/seo-workflow", json={"site": "a.com", "topic": "t"}).get_json()
    from agents.seo_workflow import SEOWorkflowReAct
    tools = [s["tool"] for s in data["trajectory"] if s["type"] == "action"]
    assert tools == SEOWorkflowReAct.TOOL_SEQUENCE
    ans = data["result"]
    assert ans["stages_completed"] == ans["stages_total"] == len(SEOWorkflowReAct.TOOL_SEQUENCE)
    assert ans["site"] == "a.com"
    assert ans["citation_probability"] is not None


def test_eeat_score_is_true_average(client):
    data = client.post("/api/ai/eeat-audit", json={}).get_json()
    assert data["result"]["overall_score"] == round((35 + 28 + 55) / 3, 1)


def test_react_agent_uses_real_tasks(client):
    client.post("/api/tasks", json={"title": "额外任务"})
    data = client.post("/api/ai/react").get_json()
    assert data["result"]["metrics"]["total"] == 11


def test_cache_and_stats(client, app):
    first = client.post("/api/ai/mindmap", json={"topic": "缓存"}).get_json()
    second = client.post("/api/ai/mindmap", json={"topic": "缓存"}).get_json()
    assert first["cached"] is False and second["cached"] is True
    stats = client.get("/health").get_json()["agent_stats"]
    assert stats["success"] == 1 and stats["cache_hits"] == 1
    assert client.post("/api/cache/clear").status_code == 200
    assert client.get("/health").get_json()["cache_size"] == 0


def test_corrupt_data_file_falls_back(app, client):
    with open(app.config["DATA_FILE"], "w", encoding="utf-8") as f:
        f.write("{not json")
    assert len(client.get("/api/tasks").get_json()) == 10
