import pytest

from agents.react import ReActAgent
from agents.scoring import DIMENSIONS, EXAMPLE_FEATURES
from agents.seo_workflow import SEOWorkflowReAct


def test_default_agent_finishes_without_tools():
    result = ReActAgent("base").run()
    assert result["finished"] is True
    assert result["answer"]["summary"] == "done"
    assert [item["type"] for item in result["trajectory"]] == ["thought"]


def test_rejects_bad_construction():
    with pytest.raises(ValueError):
        ReActAgent("  ")
    with pytest.raises(ValueError):
        ReActAgent("named", 0)
    agent = ReActAgent("named")
    with pytest.raises(TypeError):
        agent.register_tool("tool", "not-callable")
    with pytest.raises(TypeError):
        agent.run(["nope"])


def test_unknown_tool_and_tool_errors_stay_in_the_trajectory():
    class Probe(ReActAgent):
        def __init__(self):
            super().__init__("probe", max_steps=4)
            self.register_tool("boom", self._boom)
            self.register_tool("weird", self._weird)

        def _boom(self, action_input, context):
            raise RuntimeError("坏了")

        def _weird(self, action_input, context):
            return ["不是字典"]

        def think(self, context, trajectory):
            seen = [item["content"].get("tool") for item in trajectory if item["type"] == "action"]
            if "missing" not in seen:
                return {"decision": "act", "text": "调用不存在的工具", "action": "missing", "action_input": {}}
            if "boom" not in seen:
                return {"decision": "act", "text": "调用会失败的工具", "action": "boom", "action_input": []}
            if "weird" not in seen:
                return {"decision": "act", "text": "调用返回值不合法的工具", "action": "weird", "action_input": {}}
            return {"decision": "finish", "text": "收尾", "answer": {"summary": "已记录失败"}}

    result = Probe().run()
    observations = [item["content"] for item in result["trajectory"] if item["type"] == "observation"]
    assert result["finished"] is True
    assert observations[0]["ok"] is False
    assert "未知工具" in observations[0]["error"]
    assert "坏了" in observations[1]["error"]
    assert observations[2]["error"] == "工具必须返回字典"


def test_invalid_thought_stops_cleanly():
    class Bad(ReActAgent):
        def think(self, context, trajectory):
            return ["nope"]

    result = Bad("bad", max_steps=3).run()
    assert result["finished"] is False
    assert result["answer"]["summary"] == "思考结果无效"

    class Boom(ReActAgent):
        def think(self, context, trajectory):
            raise RuntimeError("想不出来")

    result = Boom("bad", max_steps=3).run()
    assert result["finished"] is False
    assert "想不出来" in result["answer"]["error"]


def test_workflow_order_and_sample_score():
    result = SEOWorkflowReAct().run()
    actions = [item["content"]["tool"] for item in result["trajectory"] if item["type"] == "action"]
    assert actions == [
        "backlink_research",
        "backlink_competitor_gap",
        "backlink_quality_score",
        "backlink_validate",
    ]
    grouped = {}
    for item in result["trajectory"]:
        grouped.setdefault(item["step"], []).append(item["type"])
    assert grouped[1] == ["thought", "action", "observation"]
    assert grouped[5] == ["thought"]
    scoring = next(
        item["content"]
        for item in result["trajectory"]
        if item["type"] == "observation" and item["stage"] == "scoring"
    )
    assert scoring["feature_source"] == "示例特征"
    assert scoring["quality_score"] == 0.78
    assert result["finished"] is True
    assert result["answer"]["quality_score"] == 0.78
    assert result["answer"]["requires_hitl"] is True
    assert result["answer"]["stages_completed"] == ["research", "gap", "scoring", "validation"]


def test_custom_features_do_not_stop_the_workflow():
    features = {item.key: 1 for item in DIMENSIONS}
    result = SEOWorkflowReAct().run({"features": features})
    assert features == {item.key: 1 for item in DIMENSIONS}
    assert result["answer"]["quality_score"] == 1.0
    scoring = next(
        item["content"]
        for item in result["trajectory"]
        if item["type"] == "observation" and item["stage"] == "scoring"
    )
    assert scoring["feature_source"] == "自定义特征"

    broken = SEOWorkflowReAct().run({"features": {"topical_relevance": 2}})
    assert broken["finished"] is True
    assert broken["answer"]["quality_score"] is None
    assert broken["answer"]["scoring_error"]


def test_max_steps_stops_before_the_summary():
    agent = SEOWorkflowReAct()
    agent.max_steps = 2
    result = agent.run()
    assert result["finished"] is False
    assert result["answer"]["summary"] == "已达到最大步数"
    actions = [item["content"]["tool"] for item in result["trajectory"] if item["type"] == "action"]
    assert actions == ["backlink_research", "backlink_competitor_gap"]


def test_tool_select_fallback():
    agent = SEOWorkflowReAct()
    known = agent.tools["tool_select"]({"task": "keyword_gap"}, {})
    unknown = agent.tools["tool_select"]({"task": "不存在"}, {})
    blank = agent.tools["tool_select"]({}, {})
    assert known["recommended"] == "Semrush"
    assert known["matched"] is True
    assert unknown["matched"] is False
    assert unknown["recommended"] == "Ahrefs"
    assert "未识别" in unknown["reason"]
    assert blank["task"] == "backlink_research"
    assert blank["matched"] is True


def test_workflow_and_competitor_apis(client):
    workflow = client.get("/api/workflow").get_json()
    assert workflow["finished"] is True
    assert workflow["badge"] == "示例运行"
    assert workflow["answer"]["quality_score"] == 0.78
    assert [step["stage"] for step in workflow["steps"][:4]] == [
        "research",
        "gap",
        "scoring",
        "validation",
    ]
    assert [event["type"] for event in workflow["steps"][0]["events"]] == [
        "thought",
        "action",
        "observation",
    ]
    fields = {item["label"]: item["value"] for item in workflow["answer_fields"]}
    assert fields["质量分"] == "0.78"
    assert fields["需要人工确认"] == "是"
    assert workflow["score_chart"]["badge"] == "示例数据"

    tools = client.get("/api/backlinks/tools").get_json()
    assert [stage["id"] for stage in tools["stages"]] == [
        "research",
        "gap",
        "scoring",
        "validation",
    ]
    assert {item["recommended"] for item in tools["external_tools"]} == {
        "Ahrefs",
        "Semrush",
        "Google Search Console",
    }
    assert tools["funnel_chart"]["sample"] is True

    competitors = client.get("/api/backlinks/competitors").get_json()
    assert competitors["stats"][0]["value"] == "15"
    assert competitors["stats"][0]["badge"] == "示例数据"
    assert "0.70" in competitors["recommendation"]
    assert competitors["domains_chart"]["sample"] is True
    assert EXAMPLE_FEATURES["topical_relevance"] == 0.85
