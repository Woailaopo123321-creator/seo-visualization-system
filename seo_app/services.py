"""把评分模型、工作流和示例数据组装成页面用的 JSON。"""

from __future__ import annotations

import copy
from functools import lru_cache
from typing import Any

from agents.scoring import (
    EXAMPLE_FEATURES,
    THRESHOLD,
    ScoringError,
    dimension_rows,
    score_backlink,
)
from agents.seo_workflow import SEOWorkflowReAct

from .sample_data import (
    anchor_guidance,
    anchor_items,
    candidates,
    competitor_rows,
    gap_rows,
    kanban_columns,
    knowledge_content,
)

PASS_COLOR = "#047857"
FAIL_COLOR = "#be123c"
THRESHOLD_COLOR = "#b45309"
PALETTE = ["#0f766e", "#0e7490", "#b45309", "#047857", "#0369a1", "#be123c", "#64748b"]


@lru_cache(maxsize=1)
def _cached_sample_run() -> dict[str, Any]:
    """示例工作流是确定性的，缓存后避免每个 API 重复跑一遍。"""

    return SEOWorkflowReAct().run()


def _sample_run() -> dict[str, Any]:
    return copy.deepcopy(_cached_sample_run())

FIELD_LABELS = {
    "discovered_targets": "发现目标",
    "resource_pages": "资源页",
    "unlinked_mentions": "未链接提及",
    "high_relevance": "高相关",
    "human_gate": "人工闸门",
    "competitors_analyzed": "已分析竞品",
    "gap_domains_total": "差距域名",
    "overlap_2_plus": "至少 2 家重叠",
    "overlap_3_plus": "至少 3 家重叠",
    "high_quality_gap": "高质量差距",
    "patterns": "常见模式",
    "recommendation": "建议",
    "task": "任务",
    "task_label": "任务",
    "recommended": "推荐工具",
    "reason": "理由",
    "matched": "已匹配任务",
    "quality_score": "质量分",
    "threshold": "阈值",
    "passed": "达到阈值",
    "requires_hitl": "需要人工确认",
    "priority": "优先级",
    "feature_source": "特征来源",
    "monitored_links": "监测链接",
    "alive": "存活",
    "lost_or_nofollow": "丢失或 nofollow",
    "error": "错误",
    "summary": "摘要",
    "scoring_error": "评分错误",
}

TOOL_LABELS = {
    "backlink_research": "外链研究",
    "backlink_competitor_gap": "竞品差距",
    "backlink_quality_score": "质量评分",
    "backlink_validate": "链接验证",
    "tool_select": "工具选择",
}

TYPE_LABELS = {"thought": "思考", "action": "行动", "observation": "观察"}

SKIP_KEYS = {"ok", "breakdown", "features"}

ANSWER_FIELDS = (
    ("summary", "摘要"),
    ("quality_score", "质量分"),
    ("threshold", "阈值"),
    ("passed", "达到阈值"),
    ("requires_hitl", "需要人工确认"),
    ("discovered_targets", "发现目标"),
    ("high_quality_gap", "高质量差距"),
    ("alive", "存活链接"),
    ("scoring_error", "评分错误"),
    ("human_gate", "人工闸门"),
)


def build_dashboard() -> dict[str, Any]:
    """概览：规则数字、示例候选和工作流示例运行。"""

    scoring = build_scoring()
    workflow = build_workflow()
    passed = sum(1 for item in scoring["candidates"] if item["result"]["passed"])
    total = len(scoring["candidates"])
    finished = "已完成" if workflow["finished"] else "未完成"
    return {
        "hitl_note": "达到 0.70 的目标进入外展候选，发出前仍要人工确认。",
        "stats": [
            {
                "label": "质量阈值",
                "value": f"{THRESHOLD:.2f}",
                "hint": "达到后进入候选，发出前仍要人工确认",
                "badge": "评分规则",
                "sample": False,
            },
            {
                "label": "工作流阶段",
                "value": str(len(SEOWorkflowReAct.STAGES)),
                "hint": "研究 → 差距 → 评分 → 验证",
                "badge": "流程",
                "sample": False,
            },
            {
                "label": "示例候选达标",
                "value": f"{passed}/{total}",
                "hint": "示例特征经过评分模型计算",
                "badge": "示例数据",
                "sample": True,
            },
            {
                "label": "示例运行",
                "value": finished,
                "hint": "研究、差距、评分、验证都已走完" if workflow["finished"] else "示例运行未完成",
                "badge": "示例运行",
                "sample": True,
            },
        ],
        "weights_chart": _weights_chart(),
        "candidates_chart": _candidates_chart(scoring["candidates"]),
        "kanban": kanban_columns(),
    }


def build_competitors() -> dict[str, Any]:
    """竞品页：结构图是示例数据，汇总数字来自工作流工具的示例观察。"""

    agent = SEOWorkflowReAct()
    research = agent.tools["backlink_research"]({}, {})
    gap = agent.tools["backlink_competitor_gap"]({}, {})
    rows = competitor_rows()
    return {
        "caption": "结构图和差距域名是示例数据。上方汇总来自工作流工具的内置示例观察。",
        "stats": [
            _stat("发现目标", research["discovered_targets"]),
            _stat("差距域名", gap["gap_domains_total"]),
            _stat("至少 3 家重叠", gap["overlap_3_plus"]),
            _stat("高质量差距", gap["high_quality_gap"]),
        ],
        "recommendation": gap["recommendation"],
        "patterns": list(gap["patterns"]),
        "gap_rows": gap_rows(),
        "research_chart": _chart(
            caption="示例观察里的研究构成。",
            sample=True,
            badge="示例数据",
            chart_type="bar",
            labels=["发现目标", "资源页", "未链接提及", "高相关"],
            datasets=[
                {
                    "label": "数量",
                    "data": [
                        research["discovered_targets"],
                        research["resource_pages"],
                        research["unlinked_mentions"],
                        research["high_relevance"],
                    ],
                    "backgroundColor": PALETTE[:4],
                }
            ],
        ),
        "domains_chart": _chart(
            caption="示例数据，用来演示引用域规模怎么读。",
            sample=True,
            badge="示例数据",
            chart_type="bar",
            labels=[str(row["name"]) for row in rows],
            datasets=[
                {
                    "label": "引用域",
                    "data": [row["referring_domains"] for row in rows],
                    "backgroundColor": PALETTE[: len(rows)],
                }
            ],
        ),
        "types_chart": _chart(
            caption="示例数据。同一站点的外链拆成可跟随、nofollow 和赞助。",
            sample=True,
            badge="示例数据",
            chart_type="bar",
            labels=[str(row["name"]) for row in rows],
            datasets=[
                {"label": "可跟随", "data": [row["dofollow"] for row in rows], "backgroundColor": "#4f46e5", "stack": "links"},
                {"label": "nofollow", "data": [row["nofollow"] for row in rows], "backgroundColor": "#94a3b8", "stack": "links"},
                {"label": "赞助", "data": [row["sponsored"] for row in rows], "backgroundColor": "#f59e0b", "stack": "links"},
            ],
            stacked=True,
        ),
    }


def build_scoring() -> dict[str, Any]:
    """评分页：权重来自模型，候选特征是示例数据，分数由模型计算。"""

    rows = dimension_rows()
    scored = []
    for candidate in candidates():
        features = candidate["features"]
        if not isinstance(features, dict):
            raise ScoringError("示例候选的特征必须是字典")
        scored.append(
            {
                "name": candidate["name"],
                "sample": True,
                "features": features,
                "result": score_backlink(features).to_dict(),
            }
        )
    default_result = score_backlink(EXAMPLE_FEATURES).to_dict()
    return {
        "threshold": THRESHOLD,
        "hitl_note": "所有外展都要人工确认。达到 0.70 只表示进入候选。",
        "priority": default_result["priority"],
        "weights": rows,
        "default_features": dict(EXAMPLE_FEATURES),
        "default_result": default_result,
        "candidates": scored,
        "weights_chart": _weights_chart(),
        "candidates_chart": _candidates_chart(scored),
    }


def score_features(features: dict[str, Any]) -> dict[str, Any]:
    """给交互表单用的单次评分。"""

    result = score_backlink(features).to_dict()
    result["feature_source"] = "自定义特征"
    return result


def build_anchors() -> dict[str, Any]:
    """锚文本分布。份额由示例条数计算。"""

    items = anchor_items()
    total = sum(int(item["count"]) for item in items)
    shaped = []
    for item in items:
        count = int(item["count"])
        share = count / total if total else 0
        shaped.append(
            {
                "type": item["type"],
                "count": count,
                "share": share,
                "share_label": f"{share * 100:.1f}%",
                "example": item["example"],
                "natural": item["natural"],
            }
        )
    labels = [str(item["type"]) for item in shaped]
    counts = [int(item["count"]) for item in shaped]
    return {
        "badge": "示例数据",
        "caption": "示例数据，用来演示锚文本分布应该怎么读。",
        "total": total,
        "guidance": anchor_guidance(),
        "items": shaped,
        "share_chart": _chart(
            caption="示例数据。扇区大小按条数，不按手填百分比。",
            sample=True,
            badge="示例数据",
            chart_type="doughnut",
            labels=labels,
            datasets=[{"label": "条数", "data": counts, "backgroundColor": PALETTE[: len(labels)]}],
            legend=True,
        ),
        "count_chart": _chart(
            caption="示例数据里的各类型条数。",
            sample=True,
            badge="示例数据",
            chart_type="bar",
            labels=labels,
            datasets=[{"label": "条数", "data": counts, "backgroundColor": PALETTE[: len(labels)]}],
        ),
    }


def build_tools() -> dict[str, Any]:
    """四工具流程，外加任务对应的外部工具建议。"""

    run = _sample_run()
    observations = _observations(run)
    return {
        "caption": "四个阶段来自示例运行。观察数字是工具内置的示例数据，顺序是 ReAct 循环跑出来的。",
        "hitl_note": "流程走完也不会自动发信。外展前要人工确认。",
        "stages": _stage_cards(observations),
        "external_tools": _external_tools(),
        "funnel_chart": _funnel_chart(observations.get("gap", {})),
    }


def build_knowledge() -> dict[str, Any]:
    """知识笔记。工具矩阵是示例标注，任务建议来自工具选择逻辑。"""

    content = knowledge_content()
    tools = content["tools"]
    if not isinstance(tools, dict):
        raise ScoringError("知识笔记的工具对比缺少内容")
    rows = tools["rows"]
    if not isinstance(rows, list):
        raise ScoringError("知识笔记的工具对比缺少内容")
    counts = []
    labels = []
    for row in rows:
        ratings = row["ratings"]
        labels.append(row["tool"])
        counts.append(sum(1 for rating in ratings if rating == "强"))
    content["comparison_chart"] = _chart(
        caption="把笔记矩阵里标成「强」的场景数画出来，方便对照，不是市场排名。",
        sample=True,
        badge="示例数据",
        chart_type="bar",
        labels=labels,
        datasets=[{"label": "标为“强”的场景数", "data": counts, "backgroundColor": PALETTE[: len(labels)]}],
        horizontal=True,
    )
    content["agent_recommendations"] = _external_tools()
    return content


def build_workflow() -> dict[str, Any]:
    """跑一次示例工作流，整理成步骤和得分构成。"""

    run = _sample_run()
    observations = _observations(run)
    scoring = observations.get("scoring", {})
    return {
        "badge": "示例运行",
        "caption": "工具观察是内置示例数据。思考、行动、观察的顺序由 ReAct 循环生成。",
        "finished": run["finished"],
        "finished_label": "已完成" if run["finished"] else "未完成",
        "agent": run["agent"],
        "answer": run["answer"],
        "answer_fields": _answer_fields(run["answer"]),
        "steps": _group_steps(run["trajectory"]),
        "score_chart": _score_chart(scoring),
    }


def _stat(label: str, value: object) -> dict[str, Any]:
    return {
        "label": label,
        "value": format_value(value),
        "badge": "示例数据",
        "sample": True,
    }


def _weights_chart() -> dict[str, Any]:
    rows = dimension_rows()
    return _chart(
        caption="六个维度的固定权重，合计 100%。",
        sample=False,
        badge="评分规则",
        chart_type="doughnut",
        labels=[f"{row['label']} {row['weight_label']}" for row in rows],
        datasets=[
            {
                "label": "权重",
                "data": [row["weight"] for row in rows],
                "backgroundColor": PALETTE[: len(rows)],
            }
        ],
    )


def _candidates_chart(scored: list[dict[str, Any]]) -> dict[str, Any]:
    passed = []
    failed = []
    for item in scored:
        score = item["result"]["quality_score"]
        if item["result"]["passed"]:
            passed.append(score)
            failed.append(None)
        else:
            passed.append(None)
            failed.append(score)
    return _chart(
        caption="示例特征经过评分模型计算。绿色达到 0.70，红色未达到，折线是阈值。",
        sample=True,
        badge="示例数据",
        chart_type="bar",
        labels=[str(item["name"]) for item in scored],
        datasets=[
            {"label": "达到阈值", "data": passed, "backgroundColor": PASS_COLOR},
            {"label": "未达阈值", "data": failed, "backgroundColor": FAIL_COLOR},
            {
                "type": "line",
                "label": "阈值 0.70",
                "data": [THRESHOLD for _ in scored],
                "borderColor": THRESHOLD_COLOR,
                "backgroundColor": "transparent",
                "dashed": True,
            },
        ],
        y_max=1,
    )


def _funnel_chart(gap: dict[str, Any]) -> dict[str, Any]:
    labels = ["差距域名", "至少 2 家重叠", "至少 3 家重叠", "高质量差距"]
    keys = ["gap_domains_total", "overlap_2_plus", "overlap_3_plus", "high_quality_gap"]
    return _chart(
        caption="示例运行里的差距收窄。数字来自竞品差距工具的内置观察。",
        sample=True,
        badge="示例数据",
        chart_type="bar",
        labels=labels,
        datasets=[
            {
                "label": "域名数",
                "data": [gap.get(key, 0) for key in keys],
                "backgroundColor": PALETTE[:4],
            }
        ],
        horizontal=True,
    )


def _score_chart(scoring: dict[str, Any]) -> dict[str, Any]:
    breakdown = scoring.get("breakdown") if isinstance(scoring.get("breakdown"), list) else []
    if not breakdown or scoring.get("ok") is False:
        return _chart(
            caption="这次示例运行没有算出得分构成。",
            sample=True,
            badge="示例数据",
            chart_type="bar",
            labels=[],
            datasets=[{"label": "贡献", "data": []}],
        )
    return _chart(
        caption="特征是示例数据，柱高是评分模型算出的贡献。",
        sample=True,
        badge="示例数据",
        chart_type="bar",
        labels=[str(item["label"]) for item in breakdown],
        datasets=[
            {
                "label": "贡献",
                "data": [item["contribution"] for item in breakdown],
                "backgroundColor": PALETTE[: len(breakdown)],
            }
        ],
        y_max=0.4,
    )


def _stage_cards(observations: dict[str, dict[str, Any]]):
    def _one(stage_id: str):
        stage = next(item for item in SEOWorkflowReAct.STAGES if item.id == stage_id)
        content = observations.get(stage.id, {})
        return {
            "id": stage.id,
            "label": stage.label,
            "tool": stage.tool,
            "text": stage.text,
            "observation_fields": labeled_fields(content),
        }

    return [_one(stage.id) for stage in SEOWorkflowReAct.STAGES]


def _external_tools() -> list[dict[str, Any]]:
    agent = SEOWorkflowReAct()
    recommendations = []
    for task in ("backlink_research", "keyword_gap", "own_data"):
        recommendations.append(agent.tools["tool_select"]({"task": task}, {}))
    return recommendations


def _observations(run: dict[str, Any]) -> dict[str, dict[str, Any]]:
    found: dict[str, dict[str, Any]] = {}
    for item in run["trajectory"]:
        if item.get("type") == "observation" and item.get("stage") and isinstance(item.get("content"), dict):
            found[str(item["stage"])] = item["content"]
    return found


def _group_steps(trajectory: list[dict[str, Any]]) -> list[dict[str, Any]]:
    grouped: dict[int, dict[str, Any]] = {}
    for event in trajectory:
        step = int(event["step"])
        bucket = grouped.setdefault(
            step,
            {
                "step": step,
                "stage": event.get("stage"),
                "stage_label": event.get("stage_label") or "",
                "events": [],
            },
        )
        if event.get("stage_label"):
            bucket["stage_label"] = event["stage_label"]
        bucket["events"].append(
            {
                "type": event["type"],
                "type_label": TYPE_LABELS.get(event["type"], event["type"]),
                "fields": _event_fields(event),
            }
        )
    return [grouped[key] for key in sorted(grouped)]


def _event_fields(event: dict[str, Any]) -> list[dict[str, str]]:
    content = event.get("content") if isinstance(event.get("content"), dict) else {}
    if event.get("type") == "thought":
        fields = [{"label": "内容", "value": str(content.get("text") or "—")}]
        if content.get("error"):
            fields.append({"label": "错误", "value": str(content["error"])})
        return fields
    if event.get("type") == "action":
        tool = content.get("tool")
        label = TOOL_LABELS.get(tool, str(tool))
        return [{"label": "工具", "value": label}]
    return labeled_fields(content)


def _answer_fields(answer: dict[str, Any]) -> list[dict[str, str]]:
    fields = []
    for key, label in ANSWER_FIELDS:
        if key not in answer:
            continue
        if key == "scoring_error" and not answer.get(key):
            continue
        fields.append({"label": label, "value": format_value(answer.get(key))})
    return fields


def labeled_fields(content: dict[str, Any]) -> list[dict[str, str]]:
    fields = []
    for key, value in content.items():
        if key in SKIP_KEYS:
            continue
        formatted = format_value(value)
        if formatted is None:
            continue
        fields.append({"label": FIELD_LABELS.get(key, str(key)), "value": formatted})
    return fields


def format_value(value: Any) -> str | None:
    """把观察值收成页面上的短文本。字典和得分明细留给图表，不塞进表格。"""

    if isinstance(value, dict):
        return None
    if isinstance(value, list) and any(isinstance(item, dict) for item in value):
        return None
    if isinstance(value, list):
        return "、".join(str(item) for item in value)
    if isinstance(value, bool):
        return "是" if value else "否"
    if isinstance(value, float):
        return f"{value:.2f}"
    if value is None:
        return "—"
    return str(value)


def _chart(
    *,
    caption: str,
    sample: bool,
    badge: str,
    chart_type: str,
    labels: list[str],
    datasets: list[dict[str, Any]],
    stacked: bool = False,
    horizontal: bool = False,
    y_max: float | None = None,
    legend: bool = True,
) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "caption": caption,
        "sample": sample,
        "badge": badge,
        "type": chart_type,
        "labels": labels,
        "datasets": datasets,
        "stacked": stacked,
        "horizontal": horizontal,
        "legend": legend,
    }
    if y_max is not None:
        payload["y_max"] = y_max
    return payload
