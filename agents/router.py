"""Supervisor 入口路由（规则版）。

路线图建议早期用关键词规则，可解释、零成本；接入 LLM 后可换成模型语义路由，
只需保持 route_request(text) -> (target, matched) 的签名不变。
"""

from typing import List, Optional, Tuple

# (目标 Agent, 触发关键词)；按顺序匹配，先命中先生效
ROUTER_RULES: List[Tuple[str, Tuple[str, ...]]] = [
    ("eeat_audit_react", ("e-e-a-t", "eeat", "信任", "作者", "审计")),
    ("seo_learning_path_react", ("学习路径", "路径", "怎么学", "阶段")),
    ("progress_analyzer_react", ("进度", "看板", "任务")),
    ("mindmap_generator", ("导图", "思维导图", "脑图")),
    ("recommender", ("推荐", "可视化方案", "方案")),
    ("workflow", ("工作流", "流水线", "外链", "发布", "关键词", "简报")),
]
FALLBACK_TARGET = "recommender"


def route_request(text: str) -> Tuple[str, Optional[str]]:
    """返回 (目标, 命中的关键词)；都不命中时交给推荐 Agent"""
    lowered = text.lower()
    for target, words in ROUTER_RULES:
        hit = next((w for w in words if w in lowered), None)
        if hit:
            return target, hit
    return FALLBACK_TARGET, None
