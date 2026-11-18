"""外链质量评分。

相关性 30% + 编辑性 20% + 流量 15% + 锚文本 15% + 权威 10% + 邻里 10%。
达到 0.70 只表示可以进入外展候选，发出前仍然需要人工确认。
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping


@dataclass(frozen=True)
class Dimension:
    """评分维度。``weight`` 之和必须为 1。"""

    key: str
    label: str
    weight: float
    description: str


DIMENSIONS: tuple[Dimension, ...] = (
    Dimension("topical_relevance", "相关性", 0.30, "来源页主题和目标页是否一致。"),
    Dimension("editorial_placement", "编辑性", 0.20, "链接是否出现在正文里，而不是页脚、侧栏或批量目录。"),
    Dimension("real_traffic", "流量", 0.15, "来源页是否有真实访问。"),
    Dimension("anchor_naturalness", "锚文本", 0.15, "锚文本是否自然，精确匹配是否过多。"),
    Dimension("authority_score", "权威", 0.10, "站点在这个主题上是否常被引用。"),
    Dimension("link_neighborhood", "邻里", 0.10, "同一页上的其他外链是否健康。"),
)

THRESHOLD = 0.70
PRIORITY = "相关性 > 编辑性 > 流量"
WEIGHTS: dict[str, float] = {item.key: item.weight for item in DIMENSIONS}
LABELS: dict[str, str] = {item.key: item.label for item in DIMENSIONS}

# 工作流没收到特征时使用的演示输入。分数仍由模型计算。
EXAMPLE_FEATURES: dict[str, float] = {
    "topical_relevance": 0.85,
    "editorial_placement": 0.78,
    "real_traffic": 0.62,
    "anchor_naturalness": 0.88,
    "authority_score": 0.70,
    "link_neighborhood": 0.75,
}

_WEIGHT_TOTAL = sum(item.weight for item in DIMENSIONS)
if abs(_WEIGHT_TOTAL - 1.0) > 1e-9:
    raise RuntimeError("评分权重之和必须为 1")


class ScoringError(ValueError):
    """特征或阈值不合法。"""


@dataclass(frozen=True)
class ScoreResult:
    """一次评分的结果。``requires_hitl`` 对所有外展都为真。"""

    quality_score: float
    threshold: float
    passed: bool
    requires_hitl: bool
    priority: str
    human_gate: str
    breakdown: tuple[dict[str, float | str], ...]

    def to_dict(self) -> dict[str, object]:
        return {
            "quality_score": self.quality_score,
            "threshold": self.threshold,
            "passed": self.passed,
            "requires_hitl": self.requires_hitl,
            "priority": self.priority,
            "human_gate": self.human_gate,
            "breakdown": [dict(item) for item in self.breakdown],
        }


def dimension_rows() -> list[dict[str, float | str]]:
    """给页面和接口共用的维度说明。"""

    rows: list[dict[str, float | str]] = []
    for item in DIMENSIONS:
        rows.append(
            {
                "key": item.key,
                "label": item.label,
                "weight": item.weight,
                "weight_label": f"{round(item.weight * 100):.0f}%",
                "description": item.description,
                "default": EXAMPLE_FEATURES[item.key],
            }
        )
    return rows


def score_backlink(
    features: Mapping[str, float],
    *,
    threshold: float = THRESHOLD,
) -> ScoreResult:
    """按固定权重计算质量分。

    每个维度必须是 0 到 1 之间的数字。布尔值不算数字。
    展示用的质量分保留两位小数，是否达标也按这个两位小数判断。
    """

    if not isinstance(features, Mapping):
        raise ScoringError("特征必须是字典")
    if isinstance(threshold, bool) or not isinstance(threshold, (int, float)):
        raise ScoringError("阈值必须是 0 到 1 之间的数字")
    if not 0 < float(threshold) <= 1:
        raise ScoringError("阈值必须在 0 到 1 之间")

    missing = [item.key for item in DIMENSIONS if item.key not in features]
    if missing:
        raise ScoringError("缺少维度：" + "、".join(LABELS[key] for key in missing))
    unknown = [str(key) for key in features if key not in WEIGHTS]
    if unknown:
        raise ScoringError("包含未知维度：" + "、".join(unknown))

    normalized: dict[str, float] = {}
    for item in DIMENSIONS:
        value = features[item.key]
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise ScoringError(f"{item.label}必须是 0 到 1 之间的数字")
        number = float(value)
        if number < 0 or number > 1:
            raise ScoringError(f"{item.label}必须在 0 到 1 之间")
        normalized[item.key] = number

    total = 0.0
    breakdown: list[dict[str, float | str]] = []
    for item in DIMENSIONS:
        raw = normalized[item.key]
        total += raw * item.weight
        breakdown.append(
            {
                "key": item.key,
                "label": item.label,
                "weight": item.weight,
                "value": round(raw, 4),
                "contribution": round(raw * item.weight, 4),
            }
        )

    quality = round(total, 2)
    limit = float(threshold)
    passed = quality >= limit
    if passed:
        gate = "已达阈值，可以进入外展候选，发出前必须人工确认"
    else:
        gate = "未达阈值。若仍要联系，必须人工确认"
    return ScoreResult(
        quality_score=quality,
        threshold=limit,
        passed=passed,
        requires_hitl=True,
        priority=PRIORITY,
        human_gate=gate,
        breakdown=tuple(breakdown),
    )
