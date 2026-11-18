"""页面导航。桌面侧栏、概览入口和手机控制台共用这里的文案。"""

from __future__ import annotations

NAV_ITEMS: tuple[dict[str, str], ...] = (
    {
        "path": "/dashboard",
        "label": "概览",
        "description": "阈值、示例运行和全部页面入口",
    },
    {
        "path": "/backlink-competitor",
        "label": "竞品结构",
        "description": "竞品外链规模、类型构成和差距汇总",
    },
    {
        "path": "/backlink-score-model",
        "label": "评分模型",
        "description": "六维加权、0.70 阈值和人工确认",
    },
    {
        "path": "/backlink-anchors",
        "label": "锚文本",
        "description": "锚文本类型分布和自然度",
    },
    {
        "path": "/backlink-tools",
        "label": "四工具流程",
        "description": "研究、差距、评分、验证",
    },
    {
        "path": "/knowledge",
        "label": "SEO 知识",
        "description": "2026 算法笔记、AI Overviews、E-E-A-T 和工具对比",
    },
    {
        "path": "/workflow",
        "label": "自动化",
        "description": "示例运行里的思考、行动和观察",
    },
    {
        "path": "/mobile",
        "label": "手机控制台",
        "description": "移动端入口",
    },
)

MOBILE_SECTIONS: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("核心入口", ("/dashboard",)),
    (
        "外链分析",
        (
            "/backlink-competitor",
            "/backlink-score-model",
            "/backlink-anchors",
            "/backlink-tools",
        ),
    ),
    ("学习与自动化", ("/knowledge", "/workflow")),
)

_BY_PATH = {item["path"]: item for item in NAV_ITEMS}


def mobile_sections() -> list[dict[str, object]]:
    """手机控制台分组，每项都指向一个实际页面。"""

    sections: list[dict[str, object]] = []
    for title, paths in MOBILE_SECTIONS:
        sections.append({"title": title, "items": [_BY_PATH[path] for path in paths]})
    return sections
