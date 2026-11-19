"""第四轮细节优化：登录限流、SQLite 并发、可选闸门、删除 / 重置、压缩与缓存、界面无障碍细节"""
import gzip
import re
import sqlite3
import threading

import pytest

import config
from agents.router import route_request
from app import create_app
from security import LoginLimiter
from workflow.spec import OPTIONAL_GATES, REQUIRED_GATES

REMOTE = {"REMOTE_ADDR": "10.0.0.8"}


@pytest.fixture()
def token_app(tmp_path):
    return create_app({"TESTING": True, "DATA_FILE": str(tmp_path / "t.json"), "ADMIN_TOKEN": "s3cret",
                       "LOGIN_MAX_ATTEMPTS": 3, "LOGIN_LOCKOUT_SECONDS": 600})


def start(client, **kw):
    resp = client.post("/api/workflow/runs", json={"site": "demo.com", "topic": "主题权威", **kw})
    assert resp.status_code == 201, resp.get_json()
    return resp.get_json()


def resume(client, tid, **body):
    resp = client.post(f"/api/workflow/runs/{tid}/resume", json=body)
    assert resp.status_code == 200, resp.get_json()
    return resp.get_json()


# ---------------- 登录 / 令牌限流 ----------------
def test_login_lockout_after_max_attempts(token_app):
    c = token_app.test_client()
    r1 = c.post("/login", data={"token": "bad"})
    assert r1.status_code == 401 and "还可尝试 2 次" in r1.get_data(as_text=True)
    assert c.post("/login", data={"token": "bad"}).status_code == 401
    r3 = c.post("/login", data={"token": "bad"})
    assert r3.status_code == 429 and "锁定" in r3.get_data(as_text=True)
    # 锁定期间即使令牌正确也拒绝
    r4 = c.post("/login", data={"token": "s3cret"})
    assert r4.status_code == 429 and int(r4.headers["Retry-After"]) > 0
    # 其他客户端不受影响
    assert c.post("/login", data={"token": "s3cret"}, environ_base=REMOTE).status_code == 302


def test_login_success_resets_counter(token_app):
    c = token_app.test_client()
    c.post("/login", data={"token": "bad"})
    c.post("/login", data={"token": "bad"})
    assert c.post("/login", data={"token": "s3cret"}).status_code == 302
    assert token_app.extensions["login_limiter"].remaining("127.0.0.1") == 3


def test_bearer_token_bruteforce_locks(token_app):
    c = token_app.test_client()
    for _ in range(3):
        assert c.post("/api/cache/clear", headers={"Authorization": "Bearer nope"}).status_code == 401
    r = c.post("/api/cache/clear", headers={"Authorization": "Bearer s3cret"})
    assert r.status_code == 429 and r.get_json()["retry_after"] > 0 and "Retry-After" in r.headers


def test_limiter_window_and_lockout_expire(monkeypatch):
    now = [1000.0]
    monkeypatch.setattr("security.time.time", lambda: now[0])
    lim = LoginLimiter(max_attempts=2, lockout=60, window=30)
    lim.fail("a")
    now[0] += 31  # 超出统计窗口，计数重置
    assert lim.fail("a") == 0 and lim.remaining("a") == 1
    assert lim.fail("a") == 60 and lim.retry_after("a") > 0
    now[0] += 61
    assert lim.retry_after("a") == 0


def test_login_page_explains_lockout(client):
    html = client.get("/login").get_data(as_text=True)
    assert "连续输错 5 次会锁定 15 分钟" in html


# ---------------- 可选闸门 ----------------
def test_optional_gates_full_run(client):
    v = start(client, optional_gates=["fanout", "tool_select"])
    assert v["enabled_gates"] == ["keywords", "brief", "fanout", "publish", "tool_select", "outreach"]
    tid = v["thread_id"]
    resume(client, tid, action="approve")
    v = resume(client, tid, action="approve")
    assert v["pending_approval"]["gate"] == "fanout"
    assert v["stages"]["passage_audit"] == "done"  # 并行审计已完成
    v = resume(client, tid, action="edit", edits={"subquestions": ["定义", "价格对比"]})
    assert v["artifacts"]["fanout_analyze"]["core_subquestions"] == ["定义", "价格对比"]
    assert v["pending_approval"]["gate"] == "publish"
    v = resume(client, tid, action="approve")
    assert v["pending_approval"]["gate"] == "tool_select"
    assert v["pending_approval"]["proposal"]["options"] == ["Ahrefs", "Semrush", "Moz", "Majestic"]
    v = resume(client, tid, action="edit", edits={"tool": "Semrush"})
    assert v["artifacts"]["tool_select"]["recommended"] == "Semrush"
    v = resume(client, tid, action="approve")
    assert v["status"] == "completed"
    assert [a["gate"] for a in v["approvals"]] == ["keywords", "brief", "fanout", "publish", "tool_select", "outreach"]


def test_optional_gates_off_by_default(client):
    v = start(client)
    assert all(v["gates"][g] == "off" for g in OPTIONAL_GATES)
    assert v["enabled_gates"] == REQUIRED_GATES


def test_optional_gates_default_from_config(tmp_path):
    app = create_app({"TESTING": True, "DATA_FILE": str(tmp_path / "d.json"), "OPTIONAL_GATES": ["tool_select", "bogus"]})
    c = app.test_client()
    v = start(c)
    assert "tool_select" in v["enabled_gates"] and "fanout" not in v["enabled_gates"]
    assert 'value="tool_select" checked' in c.get("/workflow-runs").get_data(as_text=True)


def test_reject_at_optional_gate_ends_run(client):
    tid = start(client, optional_gates=["fanout"])["thread_id"]
    resume(client, tid, action="approve")
    resume(client, tid, action="approve")
    v = resume(client, tid, action="reject", comment="子问题方向不对")
    assert v["status"] == "rejected" and v["gates"]["fanout"] == "rejected"


@pytest.mark.parametrize("body", [{"optional_gates": ["publish"]}, {"optional_gates": "fanout"}])
def test_invalid_optional_gates(client, body):
    assert client.post("/api/workflow/runs", json=body).status_code == 400


def test_invalid_optional_gate_edits(client):
    tid = start(client, optional_gates=["fanout", "tool_select"])["thread_id"]
    resume(client, tid, action="approve")
    resume(client, tid, action="approve")
    r = client.post(f"/api/workflow/runs/{tid}/resume", json={"action": "edit", "edits": {"subquestions": []}})
    assert r.status_code == 400
    resume(client, tid, action="approve")
    resume(client, tid, action="approve")
    r = client.post(f"/api/workflow/runs/{tid}/resume", json={"action": "edit", "edits": {"tool": "Google"}})
    assert r.status_code == 400


# ---------------- 删除 / 重置演示数据 ----------------
def test_delete_run(client):
    tid = start(client)["thread_id"]
    assert client.delete(f"/api/workflow/runs/{tid}").status_code == 200
    assert client.get(f"/api/workflow/runs/{tid}").status_code == 404
    assert client.delete(f"/api/workflow/runs/{tid}").status_code == 404
    assert client.get("/api/workflow/runs").get_json()["counts"]["total"] == 0


def test_reset_requires_confirm_and_admin(client):
    start(client)
    start(client)
    assert client.post("/api/workflow/reset", json={}).status_code == 400
    assert client.post("/api/workflow/reset", json={"confirm": True}, environ_base=REMOTE).status_code == 403
    r = client.post("/api/workflow/reset", json={"confirm": True})
    assert r.status_code == 200 and r.get_json()["deleted"] == 2 and r.get_json()["counts"]["total"] == 0


def test_delete_requires_admin(client):
    tid = start(client)["thread_id"]
    assert client.delete(f"/api/workflow/runs/{tid}", environ_base=REMOTE).status_code == 403


# ---------------- SQLite：WAL + 每线程连接，无全局锁 ----------------
def test_workflow_db_uses_wal(app):
    conn = sqlite3.connect(app.extensions["workflow"].db_path)
    assert conn.execute("PRAGMA journal_mode").fetchone()[0] == "wal"
    conn.close()


def test_concurrent_runs_and_reads(app):
    engine = app.extensions["workflow"]
    errors, ids = [], []

    def worker(i):
        try:
            v = engine.start(f"site{i}.com", f"主题{i}")
            ids.append(v["thread_id"])
            engine.list_runs()
            engine.counts()
            engine.resume(v["thread_id"], {"action": "approve"})
        except Exception as e:  # noqa: BLE001
            errors.append(e)

    threads = [threading.Thread(target=worker, args=(i,)) for i in range(6)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    assert not errors
    assert engine.counts()["total"] == 6
    assert all(engine.view(t)["pending_approval"]["gate"] == "brief" for t in ids)


def test_double_resume_same_gate_conflicts(client):
    tid = start(client)["thread_id"]
    resume(client, tid, action="approve", gate="keywords")
    r = client.post(f"/api/workflow/runs/{tid}/resume", json={"action": "approve", "gate": "keywords"})
    assert r.status_code == 409


# ---------------- 时间：存 UTC，界面转本地 ----------------
def test_times_stored_as_utc(client):
    v = start(client)
    run = client.get("/api/workflow/runs").get_json()["runs"][0]
    assert run["created_at"].endswith("+00:00")
    tid = v["thread_id"]
    a = resume(client, tid, action="approve")["approvals"][0]
    assert a["at"].endswith("+00:00")


def test_ui_formats_local_time(client):
    js = client.get("/static/common.js").get_data(as_text=True)
    assert "function fmtTime" in js and "UTC" in js
    assert "data-tz-note" in client.get("/dashboard").get_data(as_text=True)


# ---------------- 压缩与缓存 ----------------
def test_gzip_html_and_static(client):
    r = client.get("/dashboard", headers={"Accept-Encoding": "gzip"})
    assert r.headers["Content-Encoding"] == "gzip"
    assert "系统概览" in gzip.decompress(r.data).decode()
    r = client.get("/static/app.css?v=1", headers={"Accept-Encoding": "gzip"})
    assert r.headers["Content-Encoding"] == "gzip"
    assert "immutable" in r.headers["Cache-Control"]
    assert "Content-Encoding" not in client.get("/dashboard").headers  # 不支持 gzip 的客户端


# ---------------- 界面细节 ----------------
def test_base_template_accessibility(client):
    html = client.get("/workflow-runs").get_data(as_text=True)
    assert 'class="skip-link" href="#main"' in html and 'id="main"' in html
    assert 'aria-current="page"' in html
    assert 'aria-expanded="false"' in html and 'aria-controls="app-sidebar"' in html
    assert 'id="toast-stack"' in html and 'aria-live="polite"' in html
    assert re.search(r'<meta name="description" content="[^"]+">', html)
    assert re.search(r'/static/app\.css\?v=\d+', html) and 'id="theme-btn"' in html


def test_every_page_has_specific_title(client):
    from pages import PAGES
    for path, _tpl, title, _group in PAGES:
        html = client.get(path).get_data(as_text=True)
        t = re.search(r"<title>(.*?)</title>", html, re.S).group(1)
        assert t.endswith("· 学习可视化系统") and t != "学习可视化系统 · 学习可视化系统", path


def test_heading_order_no_skips(client):
    from pages import PAGES
    for path, *_ in PAGES:
        html = client.get(path).get_data(as_text=True)
        levels = [int(x) for x in re.findall(r"<h([1-6])\b", html)]
        for a, b in zip(levels, levels[1:]):
            assert b <= a + 1, f"{path} 标题层级跳跃 h{a}→h{b}"


def test_dark_mode_and_print_styles(client):
    css = client.get("/static/app.css").get_data(as_text=True)
    assert "prefers-color-scheme: dark" in css and ':root[data-theme="dark"]' in css
    assert "@media print" in css and "--tap: 44px" in css and "prefers-reduced-motion" in css


def test_templates_use_theme_variables_for_surfaces(client):
    """模板里的白色 / 浅灰底色已改为主题变量（深色模式下不会出现白块）"""
    import glob
    offenders = []
    for f in glob.glob("templates/*.html"):
        for m in re.finditer(r"background(?:-color)?\s*:\s*(#fff\b|#ffffff\b|white\b|#f8fafc\b|#f1f5f9\b)", open(f, encoding="utf-8").read()):
            offenders.append((f, m.group(1)))
    assert not offenders


# ---------------- 配置集中 / 路由模块 ----------------
def test_load_config_from_env(monkeypatch):
    monkeypatch.setenv("SEO_OPTIONAL_GATES", "fanout, tool_select")
    monkeypatch.setenv("SEO_LOGIN_MAX_ATTEMPTS", "abc")
    cfg = config.load_config()
    assert cfg["OPTIONAL_GATES"] == ["fanout", "tool_select"]
    assert cfg["LOGIN_MAX_ATTEMPTS"] == 5  # 非法值回退默认


def test_route_request_module():
    assert route_request("帮我做 EEAT 审计") == ("eeat_audit_react", "eeat")
    assert route_request("随便聊聊") == ("recommender", None)
