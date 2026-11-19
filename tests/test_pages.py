import re

import pytest

from pages import PAGES


@pytest.mark.parametrize("path", [p[0] for p in PAGES])
def test_every_page_renders_with_site_nav(client, path):
    resp = client.get(path)
    assert resp.status_code == 200
    html = resp.get_data(as_text=True)
    assert 'class="app-sidebar"' in html, "页面未使用统一 base 模板"
    assert 'href="/static/app.css?v=' in html
    assert resp.headers["X-Content-Type-Options"] == "nosniff"


def test_all_templates_registered():
    import os
    tpl_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "templates")
    templates = {f for f in os.listdir(tpl_dir)
                 if f.endswith(".html") and f not in ("error.html", "base.html", "login.html")}
    assert templates == {p[1] for p in PAGES}


def test_paths_unique():
    paths = [p[0] for p in PAGES]
    assert len(paths) == len(set(paths))


def test_internal_links_resolve(client):
    """所有页面内的站内链接都必须指向存在的路由"""
    valid = {p[0] for p in PAGES} | {"/health"}
    broken = set()
    for path, *_ in PAGES:
        html = client.get(path).get_data(as_text=True)
        for href in re.findall(r'href="(/[^"#?]*)', html):
            if href.startswith("/static/") or href == "/favicon.ico":
                continue
            if href not in valid:
                broken.add((path, href))
    assert not broken, broken


def test_sitemap_lists_every_page(client):
    html = client.get("/sitemap").get_data(as_text=True)
    for path, *_ in PAGES:
        assert f'href="{path}"' in html


def test_404_html_page(client):
    resp = client.get("/no-such-page")
    assert resp.status_code == 404
    assert "text/html" in resp.content_type
    assert "页面不存在" in resp.get_data(as_text=True)


def test_404_api_json(client):
    resp = client.get("/api/no-such")
    assert resp.status_code == 404
    assert resp.get_json()["status_code"] == 404


def test_favicon_and_static(client):
    assert client.get("/favicon.ico").status_code == 200
    for f in ("app.css", "common.js", "favicon.svg"):
        assert client.get(f"/static/{f}").status_code == 200


def test_dashboard_uses_live_data(client):
    html = client.get("/dashboard").get_data(as_text=True)
    assert "1,248" not in html  # 旧版硬编码数字已移除
    client.post("/api/tasks", json={"title": "仪表盘联动测试任务", "status": "todo", "priority": "high"})
    html = client.get("/dashboard").get_data(as_text=True)
    assert "仪表盘联动测试任务" in html
    data = client.get("/api/dashboard").get_json()
    assert data["stats"]["tasks_total"] == 11
    assert data["stats"]["pages"] == len(PAGES)
    assert [c["key"] for c in data["columns"]] == ["todo", "in_progress", "review", "done"]
