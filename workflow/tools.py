"""
阶段工具：可替换的接口层。

每个阶段对应一个 StageTool：输入是当前工作流状态（只读），输出是该阶段的产出 dict。
当前实现全部是「示例数据」（kind="sample"），复用 agents/seo_workflow.py 中的模拟工具；
接入真实能力时，只需实现同样的 run(state) 并调用 register_tool() 替换，图与 UI 不用改：

  - plug="MCP"：读取型数据（Google Search Console、页面抓取、Ahrefs/Semrush 等），
                 可用 MCP 客户端或官方 API 实现，一般不需要 LLM 密钥。
  - plug="LLM"：需要判断/写作的节点（简报撰写、扇出子问题、记忆提取），
                 需要模型 API 密钥。⚠️ 当前版本刻意未接入 LLM。
  - plug=None ：评分公式、阈值判断等确定性代码，不需要外部服务。
"""

from typing import Any, Callable, Dict, Optional, Protocol

from agents.seo_workflow import SEOWorkflowReAct

from .spec import STAGES


class StageTool(Protocol):
    """阶段工具接口：接入真实 MCP / LLM 工具时实现这个协议并 register_tool 即可"""

    name: str
    kind: str          # "sample" | "mcp" | "llm" | "rule"
    plug: Optional[str]

    def run(self, state: Dict[str, Any]) -> Dict[str, Any]: ...


class FunctionTool:
    """把普通函数包装成 StageTool；kind 标明来源（sample 示例数据 / mcp / llm / rule）"""

    def __init__(self, name: str, fn: Callable[[Dict[str, Any]], Dict[str, Any]], kind: str = "sample",
                 plug: Optional[str] = None):
        self.name, self.fn, self.kind, self.plug = name, fn, kind, plug

    def run(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """执行并清理输出（去掉旧版 human_gate 标记，补充 _source 来源说明）"""
        out = dict(self.fn(state))
        # 旧版的 human_gate 字符串标记已由图中真正的 interrupt 闸门取代
        out.pop("human_gate", None)
        out.setdefault("_source", "示例数据（模拟）" if self.kind == "sample" else self.kind)
        return out


_legacy = SEOWorkflowReAct()  # 复用旧版的示例数据工具


def _legacy_tool(method_name):
    method = getattr(_legacy, method_name)

    def fn(state):
        action_input = {"site": state.get("site"), "topic": state.get("topic")}
        return method(action_input, {"task": action_input, "observations": []})
    return fn


# ---------- 需要读取上下文的示例工具 ----------
def _sample_keywords(state):
    out = _legacy_tool("_prioritize")(state)
    topic = state.get("topic") or "SEO"
    out["priority_keywords"] = [f"{topic} 入门"] + out["priority_keywords"][:3]
    return out


def _sample_brief(state):
    """简报撰写员（LLM 接入点）。当前：按模板拼装，不调用模型。"""
    art = state.get("artifacts", {})
    kws = art.get("prioritize_keywords", {}).get("priority_keywords", [])
    revision = state.get("brief_revision", 0)
    topic = state.get("topic") or "SEO"
    outline = [f"什么是{topic}（40-60 字直接答案）", "核心步骤与清单", "常见误区与对比",
               "真实案例 / 第一手数据", "FAQ（覆盖扇出子问题）"]
    if revision:
        outline.insert(3, f"补充：作者经验与可验证来源（第 {revision} 次修订）")
    return {
        "title": f"{topic}：2026 实操指南" + (f"（修订 v{revision + 1}）" if revision else ""),
        "target_keywords": kws,
        "outline": outline,
        "answer_first": "已要求首段 40-60 字直接回答核心问题",
        "eeat_checklist": ["真实作者署名", "第一手经验", "带来源的数据"],
        "version": revision + 1,
        "_source": "模板生成（模拟）· 接入 LLM 后由「简报撰写员」生成",
    }


_TARGETS = [
    ("industry-list.com", 0.86, 0.80, 0.55, 0.72, 0.90, 0.80),
    ("data-report.io", 0.82, 0.78, 0.70, 0.75, 0.85, 0.78),
    ("niche-resource.org", 0.90, 0.70, 0.48, 0.60, 0.88, 0.70),
    ("generic-directory.net", 0.30, 0.20, 0.15, 0.40, 0.60, 0.30),
    ("seo-weekly.blog", 0.78, 0.82, 0.62, 0.66, 0.84, 0.76),
]
_WEIGHTS = {"topical_relevance": 0.30, "editorial_placement": 0.20, "real_traffic": 0.15,
            "authority_score": 0.10, "anchor_naturalness": 0.15, "link_neighborhood": 0.10}


def _sample_quality(state):
    """外链质量评分：确定性加权公式（无需 LLM），特征值为示例数据。"""
    threshold = SEOWorkflowReAct.BACKLINK_THRESHOLD
    scored = []
    for domain, *feats in _TARGETS:
        features = dict(zip(_WEIGHTS, feats))
        score = round(sum(features[k] * w for k, w in _WEIGHTS.items()), 3)
        scored.append({"domain": domain, "score": score, "pass": score >= threshold})
    scored.sort(key=lambda x: -x["score"])
    return {
        "weights": _WEIGHTS, "threshold": threshold, "targets": scored,
        "proposed_targets": [t["domain"] for t in scored if t["pass"]],
        "quality_score": round(sum(t["score"] for t in scored) / len(scored), 3),
    }


def _sample_memory(state):
    """记忆整理员（LLM 接入点）。当前：从已审批记录中按规则提取，不调用模型。"""
    approvals = state.get("approvals", [])
    kws = state.get("artifacts", {}).get("prioritize_keywords", {}).get("priority_keywords", [])
    memories = [{"type": "preference", "content": f"已确认优先关键词：{'、'.join(kws)}"}] if kws else []
    for a in approvals:
        if a.get("comment"):
            memories.append({"type": "feedback", "content": f"[{a['gate']}] {a['comment']}"})
    return {"extracted_count": len(memories), "memories": memories, "namespace": ("site", state.get("site")),
            "_source": "规则提取（模拟）· 接入 LLM / LangMem 后可做语义提取"}


_CUSTOM = {
    "prioritize_keywords": _sample_keywords,
    "create_brief": _sample_brief,
    "backlink_quality_score": _sample_quality,
    "memory_extract": _sample_memory,
}
_LEGACY_METHODS = {
    "benchmark": "_benchmark", "map_topical_clusters": "_map_clusters", "entity_signals": "_entity",
    "citation_score": "_citation_score", "aeo_geo_optimize": "_aeo", "qa_optimize": "_qa",
    "passage_audit": "_passage", "citation_monitor": "_citation", "fanout_analyze": "_fanout",
    "backlink_research": "_backlink_research", "backlink_competitor_gap": "_backlink_competitor_gap",
    "tool_select": "_tool_select", "backlink_validate": "_backlink_validate",
}

_REGISTRY: Dict[str, StageTool] = {}
for _sid, _title, _phase, _plug in STAGES:
    _fn = _CUSTOM.get(_sid) or _legacy_tool(_LEGACY_METHODS[_sid])
    _REGISTRY[_sid] = FunctionTool(_sid, _fn, kind="sample", plug=_plug)


def get_tool(name: str) -> StageTool:
    """按阶段 id 取当前注册的工具"""
    return _REGISTRY[name]


def register_tool(name: str, tool: StageTool) -> None:
    """替换某个阶段的实现（例如接入 MCP 版 Search Console 工具）。"""
    if name not in _REGISTRY:
        raise KeyError(f"未知阶段 {name}")
    _REGISTRY[name] = tool


def tool_kinds() -> Dict[str, Dict[str, Optional[str]]]:
    """各阶段工具的类型与接入点（/api/workflow/graph 展示用）"""
    return {k: {"kind": v.kind, "plug": v.plug} for k, v in _REGISTRY.items()}
