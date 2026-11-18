"""SEO 外链工作流：研究 → 差距 → 评分 → 验证。"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .react import ReActAgent
from .scoring import EXAMPLE_FEATURES, THRESHOLD, ScoringError, score_backlink


@dataclass(frozen=True)
class Stage:
    """工作流中的一个工具阶段。"""

    id: str
    label: str
    tool: str
    text: str


class SEOWorkflowReAct(ReActAgent):
    """按固定阶段调用外链工具，并在结束后给出人工复核摘要。"""

    STAGES: tuple[Stage, ...] = (
        Stage(
            "research",
            "外链研究",
            "backlink_research",
            "先盘点能争取的外链：资源页、未链接提及，以及主题高度相关的域名。",
        ),
        Stage(
            "gap",
            "竞品差距",
            "backlink_competitor_gap",
            "对照竞品外链，找出多家竞品都有、我方还没有的域名。",
        ),
        Stage(
            "scoring",
            "质量评分",
            "backlink_quality_score",
            "用六维加权模型给候选打分。达到 0.70 只是进入候选，外展前必须人工确认。",
        ),
        Stage(
            "validation",
            "链接验证",
            "backlink_validate",
            "复查链接是否还活着、有没有变成 nofollow。验证结果供人工复核。",
        ),
    )

    def __init__(self) -> None:
        super().__init__("seo_workflow_react", max_steps=15)
        self.register_tool("backlink_research", self._backlink_research)
        self.register_tool("backlink_competitor_gap", self._backlink_competitor_gap)
        self.register_tool("tool_select", self._tool_select)
        self.register_tool("backlink_quality_score", self._backlink_quality_score)
        self.register_tool("backlink_validate", self._backlink_validate)

    def think(self, context: dict[str, Any], trajectory: list[dict[str, Any]]) -> dict[str, Any]:
        """按研究、差距、评分、验证的顺序各执行一次，然后结束。"""

        done = {
            item.get("stage")
            for item in trajectory
            if item.get("type") == "observation" and item.get("stage")
        }
        for stage in self.STAGES:
            if stage.id in done:
                continue
            action_input: dict[str, Any] = {}
            if stage.id == "scoring" and "features" in context:
                action_input = {"features": context["features"]}
            return {
                "decision": "act",
                "stage": stage.id,
                "stage_label": stage.label,
                "text": stage.text,
                "action": stage.tool,
                "action_input": action_input,
            }
        return {
            "decision": "finish",
            "stage": "done",
            "stage_label": "汇总",
            "text": "四个阶段都走完了。汇总给人工复核，不会自动外展。",
            "answer": self._summarize(trajectory),
        }

    def _summarize(self, trajectory: list[dict[str, Any]]) -> dict[str, Any]:
        observations: dict[str, dict[str, Any]] = {}
        for item in trajectory:
            if item.get("type") != "observation" or not item.get("stage"):
                continue
            content = item.get("content")
            if isinstance(content, dict):
                observations[str(item["stage"])] = content

        research = observations.get("research", {})
        gap = observations.get("gap", {})
        scoring = observations.get("scoring", {})
        validation = observations.get("validation", {})
        score_ok = scoring.get("ok") is not False and "quality_score" in scoring
        return {
            "summary": "已完成研究、差距、评分与验证。外展前需要人工确认。",
            "stages_completed": [stage.id for stage in self.STAGES if stage.id in observations],
            "discovered_targets": research.get("discovered_targets"),
            "high_quality_gap": gap.get("high_quality_gap"),
            "quality_score": scoring.get("quality_score") if score_ok else None,
            "threshold": scoring.get("threshold", THRESHOLD),
            "passed": bool(scoring.get("passed")) if score_ok else False,
            "requires_hitl": True,
            "alive": validation.get("alive"),
            "scoring_error": None if score_ok else scoring.get("error"),
            "human_gate": "所有外展需人工确认",
        }

    def _backlink_research(self, action_input: dict[str, Any], context: dict[str, Any]) -> dict[str, Any]:
        """返回内置示例观察，供学习演示。"""

        return {
            "discovered_targets": 15,
            "resource_pages": 8,
            "unlinked_mentions": 6,
            "high_relevance": 9,
            "human_gate": "目标列表需人工筛选",
        }

    def _backlink_competitor_gap(self, action_input: dict[str, Any], context: dict[str, Any]) -> dict[str, Any]:
        """返回内置示例观察，供学习演示。"""

        return {
            "competitors_analyzed": 4,
            "gap_domains_total": 86,
            "overlap_2_plus": 31,
            "overlap_3_plus": 12,
            "high_quality_gap": 9,
            "patterns": ["数据驱动型", "资源页型", "媒体PR型"],
            "recommendation": "优先外展重叠3+且质量分≥0.70的域名",
            "human_gate": "差距列表需人工确认",
        }

    def _tool_select(self, action_input: dict[str, Any], context: dict[str, Any]) -> dict[str, Any]:
        """按任务推荐外部工具。未识别的任务回退到外链研究，并标明未匹配。"""

        labels = {
            "backlink_research": "外链研究",
            "keyword_gap": "关键词差距",
            "own_data": "自有数据",
        }
        mapping = {
            "backlink_research": {"tool": "Ahrefs", "reason": "Link Intersect 与断链报告适合找竞品共有外链。"},
            "keyword_gap": {"tool": "Semrush", "reason": "关键词差距和内容规划更直接。"},
            "own_data": {"tool": "Google Search Console", "reason": "自有点击、展示和查询以官方数据为准。"},
        }
        raw = action_input.get("task", "backlink_research")
        task = str(raw).strip() if raw is not None else ""
        if not task:
            task = "backlink_research"
        matched = task in mapping
        chosen = mapping.get(task, mapping["backlink_research"])
        reason = chosen["reason"]
        if not matched:
            reason = f"未识别的任务，已回退到外链研究建议：{reason}"
        return {
            "task": task,
            "task_label": labels.get(task, task),
            "recommended": chosen["tool"],
            "reason": reason,
            "matched": matched,
            "human_gate": "工具选择需人工确认",
        }

    def _backlink_quality_score(self, action_input: dict[str, Any], context: dict[str, Any]) -> dict[str, Any]:
        """计算质量分。特征来自动作输入、上下文，或内置示例特征。"""

        features, source = self._resolve_features(action_input, context)
        if not isinstance(features, dict):
            return {
                "ok": False,
                "error": "特征必须是字典",
                "feature_source": source,
                "human_gate": "评分输入无效，需人工复核",
            }
        try:
            result = score_backlink(features)
        except ScoringError as exc:
            return {
                "ok": False,
                "error": str(exc),
                "feature_source": source,
                "human_gate": "评分输入无效，需人工复核",
            }
        payload = result.to_dict()
        payload["feature_source"] = source
        return payload

    def _backlink_validate(self, action_input: dict[str, Any], context: dict[str, Any]) -> dict[str, Any]:
        """返回内置示例观察，供学习演示。"""

        return {
            "monitored_links": 24,
            "alive": 21,
            "lost_or_nofollow": 3,
            "human_gate": "验证结果供人工复核",
        }

    @staticmethod
    def _resolve_features(action_input: dict[str, Any], context: dict[str, Any]) -> tuple[Any, str]:
        if isinstance(action_input, dict) and "features" in action_input:
            return action_input["features"], "自定义特征"
        if isinstance(context, dict) and "features" in context:
            return context["features"], "自定义特征"
        return dict(EXAMPLE_FEATURES), "示例特征"
