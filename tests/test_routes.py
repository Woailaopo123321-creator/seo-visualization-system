import pytest

PAGES = [
    "/",
    "/dashboard",
    "/mobile",
    "/backlink-competitor",
    "/backlink-score-model",
    "/backlink-anchors",
    "/backlink-tools",
    "/knowledge",
    "/workflow",
]

LINKS = [
    "/dashboard",
    "/backlink-competitor",
    "/backlink-score-model",
    "/backlink-anchors",
    "/backlink-tools",
    "/knowledge",
    "/workflow",
    "/mobile",
]


@pytest.mark.parametrize("path", PAGES)
def test_pages_render_chinese_shell(client, path):
    response = client.get(path)
    assert response.status_code == 200
    html = response.get_data(as_text=True)
    assert "SEO 学习可视化" in html
    assert "<style" not in html.lower()
    assert "style=" not in html.lower()
    assert "/static/css/app.css" in html


def test_dashboard_and_mobile_link_every_page(client):
    dashboard = client.get("/dashboard").get_data(as_text=True)
    mobile = client.get("/mobile").get_data(as_text=True)
    for href in LINKS:
        assert f'href="{href}"' in dashboard
        if href == "/mobile":
            continue
        assert f'href="{href}"' in mobile
    assert "竞品结构" in mobile
    assert "评分模型" in mobile
    assert "四工具流程" in mobile


def test_root_matches_dashboard(client):
    assert "系统概览" in client.get("/").get_data(as_text=True)


def test_dashboard_chinese_content_sections(client):
    html = client.get("/dashboard").get_data(as_text=True)
    assert "多智能体协作" in html
    assert "心理学洞察" in html
    assert "研究智能体" in html
    assert "先意图，后技巧" in html
    assert "人工确认防冒进" in html


def test_knowledge_page_covers_promised_topics(client):
    html = client.get("/knowledge").get_data(as_text=True)
    assert "2026 算法学习笔记" in html
    assert "AI Overviews" in html
    assert "E-E-A-T" in html
    assert "Ahrefs" in html
    assert "示例数据" in html
    assert "站点级质量比单页技巧更重要" in html


def test_health(client):
    response = client.get("/health")
    assert response.status_code == 200
    assert response.get_json() == {"status": "ok"}


def test_static_assets(client):
    css = client.get("/static/css/app.css")
    script = client.get("/static/js/common.js")
    assert css.status_code == 200
    assert ".sidebar" in css.get_data(as_text=True)
    assert script.status_code == 200


def test_missing_page_and_api(client):
    page = client.get("/missing")
    assert page.status_code == 404
    assert "页面不存在" in page.get_data(as_text=True)
    api = client.get("/api/missing")
    assert api.status_code == 404
    assert api.get_json()["error"] == "未找到接口"


def test_method_not_allowed(client):
    page = client.post("/dashboard")
    assert page.status_code == 405
    assert "方法不被允许" in page.get_data(as_text=True)
    api = client.post("/api/dashboard")
    assert api.status_code == 405
    assert api.get_json()["error"] == "请求方法不被允许"


def test_api_keeps_chinese_characters(client):
    response = client.get("/api/workflow")
    body = response.get_data(as_text=True)
    assert response.status_code == 200
    assert "\\u" not in body
    assert "人工确认" in body


def test_entrypoint_app_serves_health():
    import app as entry

    assert entry.app.json.ensure_ascii is False
    response = entry.app.test_client().get("/health")
    assert response.get_json() == {"status": "ok"}
