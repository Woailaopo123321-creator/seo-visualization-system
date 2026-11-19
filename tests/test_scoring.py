import pytest

from agents.scoring import (
    DIMENSIONS,
    EXAMPLE_FEATURES,
    THRESHOLD,
    WEIGHTS,
    ScoringError,
    score_backlink,
)


def test_weights_match_the_model():
    assert [(item.label, item.weight) for item in DIMENSIONS] == [
        ("相关性", 0.30),
        ("编辑性", 0.20),
        ("流量", 0.15),
        ("锚文本", 0.15),
        ("权威", 0.10),
        ("邻里", 0.10),
    ]
    assert THRESHOLD == 0.70
    assert abs(sum(WEIGHTS.values()) - 1) < 1e-9


def test_example_features_score_is_stable():
    result = score_backlink(EXAMPLE_FEATURES)
    assert result.quality_score == 0.78
    assert result.passed is True
    assert result.requires_hitl is True
    assert result.threshold == 0.70
    assert "人工确认" in result.human_gate
    assert [item["label"] for item in result.breakdown] == [item.label for item in DIMENSIONS]


def test_threshold_edges():
    zeros = score_backlink({key: 0 for key in WEIGHTS})
    ones = score_backlink({key: 1 for key in WEIGHTS})
    below_one = score_backlink(EXAMPLE_FEATURES, threshold=1)
    assert zeros.quality_score == 0.0
    assert zeros.passed is False
    assert zeros.requires_hitl is True
    assert ones.quality_score == 1.0
    assert ones.passed is True
    assert ones.requires_hitl is True
    assert below_one.passed is False


@pytest.mark.parametrize(
    "mutate",
    [
        lambda features: features.pop("topical_relevance"),
        lambda features: features.__setitem__("topical_relevance", 1.2),
        lambda features: features.__setitem__("topical_relevance", -0.01),
        lambda features: features.__setitem__("topical_relevance", True),
        lambda features: features.__setitem__("topical_relevance", "0.8"),
        lambda features: features.__setitem__("extra", 0.2),
    ],
)
def test_invalid_features(mutate):
    features = dict(EXAMPLE_FEATURES)
    mutate(features)
    with pytest.raises(ScoringError):
        score_backlink(features)


def test_invalid_threshold_and_payload_type():
    with pytest.raises(ScoringError):
        score_backlink(EXAMPLE_FEATURES, threshold=0)
    with pytest.raises(ScoringError):
        score_backlink(EXAMPLE_FEATURES, threshold=1.5)
    with pytest.raises(ScoringError):
        score_backlink(["nope"])


def test_scoring_api_and_candidates(client):
    payload = client.get("/api/backlinks/scoring").get_json()
    assert [item["label"] for item in payload["weights"]] == [item.label for item in DIMENSIONS]
    assert abs(sum(item["weight"] for item in payload["weights"]) - 1) < 1e-9
    assert payload["default_result"]["quality_score"] == 0.78
    assert any(item["result"]["passed"] for item in payload["candidates"])
    assert any(not item["result"]["passed"] for item in payload["candidates"])
    for item in payload["candidates"]:
        assert item["sample"] is True
        expected = score_backlink(item["features"])
        assert item["result"]["quality_score"] == expected.quality_score
        assert item["result"]["requires_hitl"] is True

    ok = client.post("/api/backlinks/score", json={"features": EXAMPLE_FEATURES})
    assert ok.status_code == 200
    assert ok.get_json()["quality_score"] == 0.78
    assert ok.get_json()["feature_source"] == "自定义特征"

    missing = client.post("/api/backlinks/score", json={})
    assert missing.status_code == 400
    assert "缺少维度" in missing.get_json()["error"]

    bad = client.post("/api/backlinks/score", data="nope", content_type="text/plain")
    assert bad.status_code == 400
    assert bad.get_json()["error"] == "请提交 JSON 对象"


def test_anchor_shares_and_sample_badge(client):
    payload = client.get("/api/backlinks/anchors").get_json()
    assert payload["badge"] == "示例数据"
    assert abs(sum(item["share"] for item in payload["items"]) - 1) < 1e-9
    assert payload["share_chart"]["sample"] is True
    assert "示例数据" in payload["share_chart"]["badge"]
