"""相结合：上传完整系统 + 青绿主题 / 交互评分 / 旧路径兼容。"""


def test_legacy_aliases_redirect(client):
    mapping = {
        "/knowledge": "/seo",
        "/workflow": "/workflow-runs",
        "/backlink-anchors": "/anchor-text",
    }
    for old, new in mapping.items():
        response = client.get(old, follow_redirects=False)
        assert response.status_code == 302
        assert response.headers["Location"].endswith(new)


def test_score_model_has_interactive_calc(client):
    html = client.get("/backlink-score-model").get_data(as_text=True)
    assert "交互试算" in html
    assert "score-form" in html
    assert "topical_relevance" in html
    assert "0.70" in html


def test_backlink_score_api(client):
    response = client.post(
        "/api/backlinks/score",
        json={
            "features": {
                "topical_relevance": 0.85,
                "editorial_placement": 0.78,
                "real_traffic": 0.62,
                "anchor_naturalness": 0.88,
                "authority_score": 0.70,
                "link_neighborhood": 0.75,
            }
        },
    )
    assert response.status_code == 200
    data = response.get_json()
    assert data["quality_score"] == 0.78
    assert data["passed"] is True
    assert data["requires_hitl"] is True
    assert "人工确认" in data["human_gate"]


def test_teal_theme_and_fonts(client):
    css = client.get("/static/app.css").get_data(as_text=True)
    assert "--accent: #0f766e" in css
    assert "Noto Sans SC" in css
    html = client.get("/dashboard").get_data(as_text=True)
    assert "Noto+Serif+SC" in html
    assert "研究智能体" in html
