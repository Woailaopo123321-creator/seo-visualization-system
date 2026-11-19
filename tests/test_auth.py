import pytest

from app import create_app

REMOTE = {"REMOTE_ADDR": "10.0.0.8"}


@pytest.fixture()
def token_app(tmp_path):
    return create_app({"TESTING": True, "DATA_FILE": str(tmp_path / "t.json"), "ADMIN_TOKEN": "s3cret"})


WRITE_CALLS = [
    ("post", "/api/tasks", {"title": "x"}),
    ("put", "/api/tasks/1", {"progress": 10}),
    ("delete", "/api/tasks/1", None),
    ("post", "/api/cache/clear", None),
]


# ---- 未设置令牌：本机可写，远程只读 ----
@pytest.mark.parametrize("method,url,body", WRITE_CALLS)
def test_no_token_local_can_write(client, method, url, body):
    resp = getattr(client, method)(url, json=body)
    assert resp.status_code in (200, 201)


@pytest.mark.parametrize("method,url,body", WRITE_CALLS)
def test_no_token_remote_is_forbidden(client, method, url, body):
    resp = getattr(client, method)(url, json=body, environ_base=REMOTE)
    assert resp.status_code == 403
    assert "本机" in resp.get_json()["detail"]


def test_remote_can_still_read(client):
    assert client.get("/api/tasks", environ_base=REMOTE).status_code == 200
    assert client.get("/dashboard", environ_base=REMOTE).status_code == 200
    assert client.post("/api/ai/mindmap", json={"topic": "a"}, environ_base=REMOTE).status_code == 200


def test_cross_origin_write_rejected(client):
    resp = client.post("/api/tasks", json={"title": "x"}, headers={"Origin": "https://evil.example"})
    assert resp.status_code == 403
    ok = client.post("/api/tasks", json={"title": "x"}, headers={"Origin": "http://localhost"})
    assert ok.status_code == 201


# ---- 设置令牌后：本机也需要令牌 ----
@pytest.mark.parametrize("method,url,body", WRITE_CALLS)
def test_token_required(token_app, method, url, body):
    c = token_app.test_client()
    assert getattr(c, method)(url, json=body).status_code == 401
    assert getattr(c, method)(url, json=body, headers={"Authorization": "Bearer wrong"}).status_code == 401


def test_bearer_and_header_token(token_app):
    c = token_app.test_client()
    assert c.post("/api/tasks", json={"title": "a"}, headers={"Authorization": "Bearer s3cret"},
                  environ_base=REMOTE).status_code == 201
    assert c.post("/api/tasks", json={"title": "b"}, headers={"X-Admin-Token": "s3cret"}).status_code == 201


def test_login_session_flow(token_app):
    c = token_app.test_client()
    assert c.get("/login").status_code == 200
    assert "只读模式" in c.get("/dashboard").get_data(as_text=True)
    assert c.post("/login", data={"token": "nope"}).status_code == 401
    resp = c.post("/login", data={"token": "s3cret", "next": "/"})
    assert resp.status_code == 302 and resp.headers["Location"].endswith("/")
    assert "管理员已登录" in c.get("/dashboard").get_data(as_text=True)
    assert c.post("/api/tasks", json={"title": "via session"}).status_code == 201
    c.get("/logout")
    assert c.post("/api/tasks", json={"title": "after logout"}).status_code == 401


def test_login_open_redirect_blocked(token_app):
    c = token_app.test_client()
    resp = c.post("/login", data={"token": "s3cret", "next": "//evil.example"})
    assert resp.headers["Location"].endswith("/dashboard")


def test_login_without_token_configured(client):
    assert "本机模式" in client.get("/dashboard").get_data(as_text=True)
    assert client.post("/login", data={"token": "x"}).status_code == 400
