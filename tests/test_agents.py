import time

from agents.base import BaseAgent, Coordinator


class Slow(BaseAgent):
    def __init__(self):
        super().__init__("slow")

    def execute(self, task):
        time.sleep(0.3)
        return {}


class Boom(BaseAgent):
    def __init__(self):
        super().__init__("boom")

    def execute(self, task):
        raise RuntimeError("bad")


def test_unknown_agent():
    assert Coordinator().dispatch("nope", {})["status"] == "failed"


def test_timeout_and_failure_are_structured():
    c = Coordinator(timeout=0.05)
    c.register(Slow())
    c.register(Boom())
    assert c.dispatch("slow", {})["status"] == "timeout"
    r = c.dispatch("boom", {})
    assert r["status"] == "failed" and "bad" in r["error"]
    s = c.snapshot()
    assert s["timeout"] == 1 and s["failed"] == 1


def test_cached_result_is_isolated():
    from agents.specialists import MindMapAgent
    c = Coordinator()
    c.register(MindMapAgent())
    r1 = c.dispatch("mindmap_generator", {"topic": "a"})
    r1["mindmap"]["center"] = "mutated"
    r2 = c.dispatch("mindmap_generator", {"topic": "a"})
    assert r2["mindmap"]["center"] == "a"


def test_multi_dispatch_order():
    from agents.specialists import MindMapAgent, RecommendationAgent
    c = Coordinator()
    c.register(MindMapAgent())
    c.register(RecommendationAgent())
    res = c.multi_dispatch([("recommender", {"context": "general"}), ("mindmap_generator", {"topic": "x"})])
    assert res[0]["agent"] == "recommender" and res[1]["agent"] == "mindmap_generator"
