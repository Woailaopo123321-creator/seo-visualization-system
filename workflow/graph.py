"""
LangGraph StateGraph：确定性 SEO 流水线 + 并行审计分支 + interrupt() 人工闸门。

拓扑（→ 顺序，⇉ 并行，◆ 闸门）：
  benchmark → prioritize_keywords → ◆keywords → map_topical_clusters → entity_signals
  → create_brief → ◆brief(可打回重写) → citation_score → aeo_geo_optimize → qa_optimize
  ⇉ {passage_audit, citation_monitor, fanout_analyze} → audit_join → ◇fanout → ◆publish
  → backlink_research → backlink_competitor_gap → tool_select → ◇tool_select → backlink_quality_score
  → ◆outreach → backlink_validate → memory_extract → finalize

闸门节点与阶段节点分离：恢复时 LangGraph 会从头重跑被中断的节点，
因此闸门节点在 interrupt() 之前不做任何副作用（保持幂等）。
◇ = 可选闸门：节点始终在图里，运行时按 state["enabled_gates"] 决定暂停还是直接放行。
"""

import operator
import time
from datetime import datetime, timezone
from typing import Annotated, Any, Callable, Dict, List, Optional, TypedDict

from langgraph.graph import END, START, StateGraph
from langgraph.types import Command, interrupt

from .spec import (BACKLINK_TOOLS, GATES, MAX_BRIEF_REVISIONS, PARALLEL_AUDITS, REQUIRED_GATES, STAGE_IDS,
                   STAGE_TITLES)
from .tools import get_tool


def merge_dicts(a: Optional[dict], b: Optional[dict]) -> dict:
    """状态合并器：并行节点各写一部分 artifacts / scores，按键合并"""
    out = dict(a or {})
    out.update(b or {})
    return out


class WorkflowState(TypedDict, total=False):
    """图的共享状态；Annotated 字段带合并器，其余字段后写覆盖"""

    site: str
    topic: str
    status: str                 # running | completed | rejected
    current_stage: str          # 并行节点不写此字段，避免同一步多次写入
    brief_revision: int
    artifacts: Annotated[Dict[str, Any], merge_dicts]
    scores: Annotated[Dict[str, Any], merge_dicts]
    trajectory: Annotated[List[Dict[str, Any]], operator.add]
    approvals: Annotated[List[Dict[str, Any]], operator.add]
    errors: Annotated[List[str], operator.add]
    summary: Dict[str, Any]
    enabled_gates: List[str]    # 本次运行启用的闸门（必选 + 选中的可选闸门）


def _now() -> str:
    """UTC ISO 时间（数据库与状态里统一存 UTC，界面再转成本地时间显示）"""
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


# ---------------- 阶段节点 ----------------
def make_stage(stage_id: str) -> Callable[[WorkflowState], Dict[str, Any]]:
    """把 workflow.tools 里的工具包装成图节点：记录轨迹、耗时、评分；工具异常不中断流水线"""
    def node(state: WorkflowState):
        t0 = time.perf_counter()
        errors = []
        try:
            out = get_tool(stage_id).run(state)
        except Exception as e:  # noqa: BLE001 - 工具失败记录到状态，流水线继续
            out = {"error": str(e)}
            errors.append(f"{stage_id}: {e}")
        ms = round((time.perf_counter() - t0) * 1000, 2)
        update: Dict[str, Any] = {
            "artifacts": {stage_id: out},
            "trajectory": [
                {"type": "action", "stage": stage_id, "tool": stage_id, "title": STAGE_TITLES[stage_id],
                 "input": {"site": state.get("site"), "topic": state.get("topic")}, "at": _now()},
                {"type": "observation", "stage": stage_id, "content": out, "elapsed_ms": ms},
            ],
            "errors": errors,
        }
        if stage_id not in PARALLEL_AUDITS:
            update["current_stage"] = stage_id
        if stage_id == "citation_score" and "citation_probability" in out:
            update["scores"] = {"citation_probability": out["citation_probability"], "citation_grade": out.get("grade")}
        if stage_id == "backlink_quality_score" and "quality_score" in out:
            update["scores"] = {"backlink_quality": out["quality_score"]}
        return update
    node.__name__ = stage_id
    return node


def audit_join(state: WorkflowState) -> Dict[str, Any]:
    """并行审计汇合：三个审计都完成后才会执行到这里"""
    art = state.get("artifacts", {})
    summary = {
        "passage": art.get("passage_audit", {}).get("recommendation"),
        "citation_rate": art.get("citation_monitor", {}).get("citation_rate"),
        "fanout_subquestions": art.get("fanout_analyze", {}).get("core_subquestions", []),
    }
    return {"current_stage": "audit_join", "artifacts": {"audit_join": summary},
            "trajectory": [{"type": "thought", "stage": "audit_join",
                            "content": "并行审计（段落 / 引用 / 扇出）已全部完成，汇总后提交发布闸门。"}]}


def finalize(state: WorkflowState) -> Dict[str, Any]:
    """全部闸门通过后的收尾：写入运行摘要，状态置为 completed"""
    art = state.get("artifacts", {})
    summary = {
        "site": state.get("site"), "topic": state.get("topic"),
        "stages_completed": len([s for s in STAGE_IDS if s in art]),
        "approvals": len(state.get("approvals", [])),
        "citation_probability": state.get("scores", {}).get("citation_probability"),
        "backlink_quality": state.get("scores", {}).get("backlink_quality"),
        "outreach_targets": art.get("outreach_approved", []),
        "brief_title": art.get("create_brief", {}).get("title"),
    }
    return {"status": "completed", "current_stage": "finalize", "summary": summary,
            "trajectory": [{"type": "thought", "stage": "finalize", "content": "工作流完成：全部闸门已人工审批。"}]}


# ---------------- 闸门 ----------------
def gate_payload(gate_id: str, state: WorkflowState) -> Dict[str, Any]:
    """interrupt() 交给界面的内容：建议值、可编辑字段与上下文"""
    g = GATES[gate_id]
    art = state.get("artifacts", {})
    payload = {"gate": gate_id, "title": g["title"], "description": g["description"], "priority": g["priority"],
               "actions": ["approve", "edit", "reject"], "editable": [], "proposal": {}, "context": {}}
    if gate_id == "keywords":
        payload["proposal"] = {"priority_keywords": art.get("prioritize_keywords", {}).get("priority_keywords", [])}
        payload["editable"] = ["priority_keywords"]
        payload["context"] = {"benchmark": art.get("benchmark", {})}
    elif gate_id == "brief":
        brief = art.get("create_brief", {})
        payload["proposal"] = {k: brief.get(k) for k in ("title", "target_keywords", "outline", "answer_first", "version")}
        payload["editable"] = ["title", "outline"]
        payload["revisions_left"] = MAX_BRIEF_REVISIONS - state.get("brief_revision", 0)
        payload["reject_label"] = "打回重写" if payload["revisions_left"] > 0 else "拒绝并结束"
    elif gate_id == "publish":
        qa = art.get("qa_optimize", {})
        payload["proposal"] = {
            "citation_probability": state.get("scores", {}).get("citation_probability"),
            "citation_grade": state.get("scores", {}).get("citation_grade"),
            "qa_issues": qa.get("issues", []),
            "audits": art.get("audit_join", {}),
            "brief_title": art.get("create_brief", {}).get("title"),
        }
    elif gate_id == "fanout":
        fo = art.get("fanout_analyze", {})
        payload["proposal"] = {"subquestions": fo.get("core_subquestions", []),
                               "coverage_strategy": fo.get("coverage_strategy"),
                               "recommendation": fo.get("recommendation")}
        payload["editable"] = ["subquestions"]
    elif gate_id == "tool_select":
        ts = art.get("tool_select", {})
        payload["proposal"] = {"tool": ts.get("recommended"), "alternative": ts.get("alternative"),
                               "reason": ts.get("reason"), "options": BACKLINK_TOOLS}
        payload["editable"] = ["tool"]
    elif gate_id == "outreach":
        q = art.get("backlink_quality_score", {})
        payload["proposal"] = {"targets": q.get("targets", []), "threshold": q.get("threshold"),
                               "approved_targets": q.get("proposed_targets", [])}
        payload["editable"] = ["approved_targets"]
    return payload


def apply_edits(gate_id: str, state: WorkflowState, edits: Dict[str, Any]) -> Dict[str, Any]:
    """把审批时的人工修改写回 artifacts（批准但未修改时只处理外展的默认目标）"""
    art = state.get("artifacts", {})
    if gate_id == "keywords" and edits.get("priority_keywords"):
        return {"prioritize_keywords": {**art.get("prioritize_keywords", {}),
                                        "priority_keywords": edits["priority_keywords"], "edited_by_human": True}}
    if gate_id == "brief" and edits:
        brief = {**art.get("create_brief", {}), "edited_by_human": True}
        for k in ("title", "outline"):
            if edits.get(k):
                brief[k] = edits[k]
        return {"create_brief": brief}
    if gate_id == "fanout" and edits.get("subquestions"):
        return {"fanout_analyze": {**art.get("fanout_analyze", {}), "core_subquestions": edits["subquestions"],
                                   "edited_by_human": True}}
    if gate_id == "tool_select" and edits.get("tool"):
        return {"tool_select": {**art.get("tool_select", {}), "recommended": edits["tool"], "edited_by_human": True}}
    if gate_id == "outreach":
        proposed = art.get("backlink_quality_score", {}).get("proposed_targets", [])
        targets = edits.get("approved_targets", proposed) if edits else proposed
        return {"outreach_approved": targets}
    return {}


def gate_enabled(gate_id: str, state: WorkflowState) -> bool:
    """必选闸门始终启用；可选闸门看本次运行的 enabled_gates（旧运行没有该字段 → 只启用必选闸门）"""
    return gate_id in (state.get("enabled_gates") or REQUIRED_GATES) or not GATES[gate_id]["optional"]


def make_gate(gate_id: str, next_node: str) -> Callable[[WorkflowState], Command]:
    """生成闸门节点：interrupt() 暂停 → 按 approve / edit / reject 决定去向"""
    on_reject = GATES[gate_id]["on_reject"]

    def gate(state: WorkflowState) -> Command:
        if not gate_enabled(gate_id, state):
            return Command(goto=next_node)  # 可选闸门未启用：直接放行，不记录审批
        decision = interrupt(gate_payload(gate_id, state))  # ⏸ 在此真正暂停，等待人工
        decision = decision if isinstance(decision, dict) else {"action": "approve"}
        action = decision.get("action", "approve")
        edits = decision.get("edits") or {}
        record = {"gate": gate_id, "title": GATES[gate_id]["title"], "action": action,
                  "comment": decision.get("comment", ""), "edits": edits, "by": decision.get("by", "admin"),
                  "at": _now()}
        update: Dict[str, Any] = {
            "approvals": [record],
            "trajectory": [{"type": "gate", "stage": f"gate_{gate_id}", "content": record}],
        }
        if action in ("approve", "edit"):
            art = apply_edits(gate_id, state, edits if action == "edit" else {})
            if art:
                update["artifacts"] = art
            return Command(update=update, goto=next_node)
        if on_reject == "rewrite" and state.get("brief_revision", 0) < MAX_BRIEF_REVISIONS:
            update["brief_revision"] = state.get("brief_revision", 0) + 1
            return Command(update=update, goto="create_brief")
        update["status"] = "rejected"
        return Command(update=update, goto=END)

    gate.__name__ = f"gate_{gate_id}"
    return gate


def build_graph() -> StateGraph:
    """组装完整拓扑（见模块文档字符串），返回未编译的 StateGraph"""
    g = StateGraph(WorkflowState)
    for sid in STAGE_IDS:
        g.add_node(sid, make_stage(sid))
    g.add_node("audit_join", audit_join)
    g.add_node("finalize", finalize)
    g.add_node("gate_keywords", make_gate("keywords", "map_topical_clusters"),
               destinations=("map_topical_clusters", END))
    g.add_node("gate_brief", make_gate("brief", "citation_score"),
               destinations=("citation_score", "create_brief", END))
    g.add_node("gate_fanout", make_gate("fanout", "gate_publish"), destinations=("gate_publish", END))
    g.add_node("gate_tool_select", make_gate("tool_select", "backlink_quality_score"),
               destinations=("backlink_quality_score", END))
    g.add_node("gate_publish", make_gate("publish", "backlink_research"),
               destinations=("backlink_research", END))
    g.add_node("gate_outreach", make_gate("outreach", "backlink_validate"),
               destinations=("backlink_validate", END))

    chain = [START, "benchmark", "prioritize_keywords", "gate_keywords"]
    for a, b in zip(chain, chain[1:]):
        g.add_edge(a, b)
    for a, b in [("map_topical_clusters", "entity_signals"), ("entity_signals", "create_brief"),
                 ("create_brief", "gate_brief"),
                 ("citation_score", "aeo_geo_optimize"), ("aeo_geo_optimize", "qa_optimize"),
                 ("audit_join", "gate_fanout"),
                 ("backlink_research", "backlink_competitor_gap"), ("backlink_competitor_gap", "tool_select"),
                 ("tool_select", "gate_tool_select"), ("backlink_quality_score", "gate_outreach"),
                 ("backlink_validate", "memory_extract"), ("memory_extract", "finalize"),
                 ("finalize", END)]:
        g.add_edge(a, b)
    # 并行扇出 + 汇合
    for audit in PARALLEL_AUDITS:
        g.add_edge("qa_optimize", audit)
    g.add_edge(PARALLEL_AUDITS, "audit_join")
    return g
