import os

from app import create_app
from pages import PAGES

TPL_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "templates")


def test_every_template_extends_base():
    for f in os.listdir(TPL_DIR):
        if f.endswith(".html") and f != "base.html":
            with open(os.path.join(TPL_DIR, f), encoding="utf-8") as fh:
                src = fh.read()
            assert src.startswith('{% extends "base.html" %}'), f
            assert "<html" not in src and '<div class="header">' not in src, f


def test_active_nav_item(client):
    html = client.get("/backlink-tools").get_data(as_text=True)
    assert 'href="/backlink-tools" class="active"' in html
    assert "外链分析" in html  # 分组副标题


def test_agent_stats_persist_across_restart(tmp_path):
    cfg = {"TESTING": True, "DATA_FILE": str(tmp_path / "d.json")}
    app1 = create_app(cfg)
    c1 = app1.test_client()
    c1.post("/api/ai/mindmap", json={"topic": "持久化"})
    c1.post("/api/ai/seo-path")
    c1.post("/api/ai/mindmap", json={"topic": "持久化"})  # 缓存命中
    app2 = create_app(cfg)  # 模拟重启
    stats = app2.test_client().get("/health").get_json()["agent_stats"]
    assert stats["success"] == 2 and stats["cache_hits"] == 1
    assert stats["per_agent"]["mindmap_generator"]["runs"] == 1
    assert app2.test_client().get("/api/dashboard").get_json()["stats"]["agent_runs"] == 2


def test_stats_persistence_keeps_tasks(tmp_path):
    cfg = {"TESTING": True, "DATA_FILE": str(tmp_path / "d.json")}
    c = create_app(cfg).test_client()
    c.post("/api/tasks", json={"title": "保留我"})
    c.post("/api/ai/analyze")
    titles = [t["title"] for t in create_app(cfg).test_client().get("/api/tasks").get_json()]
    assert "保留我" in titles


def test_mobile_uses_real_data(client):
    html = client.get("/mobile").get_data(as_text=True)
    assert 'stat-num">HITL' not in html  # 旧版写死的统计已移除
    assert ">10</div>" in html  # 默认 10 个任务
    client.post("/api/tasks", json={"title": "新任务"})
    client.post("/api/ai/mindmap", json={"topic": "m"})
    html = client.get("/mobile").get_data(as_text=True)
    assert ">11</div>" in html
    assert "1 个任务进行中" not in html  # 进行中数量来自数据（默认 3）
    assert "3 个任务进行中" in html


def test_offline_export_is_self_contained(app):
    from scripts.export_offline import export_offline
    html = export_offline(app, "http://example.local:5000")
    assert "/static/" not in html
    assert 'href="http://example.local:5000/dashboard"' in html
    assert "离线快照" in html and "--accent" in html  # CSS 已内联


def test_page_count_consistent(client):
    assert len(client.get("/api/pages").get_json()) == 6
    assert sum(len(v) for v in client.get("/api/pages").get_json().values()) == len(PAGES)
