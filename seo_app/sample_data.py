"""没有真实采集数据时使用的学习示例。

页面上凡是来自这里的数字，都会标明「示例数据」。
"""

from __future__ import annotations

import copy

from agents.scoring import EXAMPLE_FEATURES

COMPETITORS: tuple[dict[str, int | str], ...] = (
    {"name": "我方站点", "referring_domains": 240, "dofollow": 1680, "nofollow": 980, "sponsored": 140},
    {"name": "竞品 A", "referring_domains": 860, "dofollow": 7420, "nofollow": 3860, "sponsored": 1120},
    {"name": "竞品 B", "referring_domains": 640, "dofollow": 5100, "nofollow": 2940, "sponsored": 860},
    {"name": "竞品 C", "referring_domains": 510, "dofollow": 3600, "nofollow": 2100, "sponsored": 500},
    {"name": "竞品 D", "referring_domains": 430, "dofollow": 2500, "nofollow": 2200, "sponsored": 700},
)

GAP_ROWS: tuple[dict[str, int | str], ...] = (
    {
        "domain": "data-lab.example",
        "overlap": 4,
        "pattern": "数据驱动型",
        "note": "多家竞品引用它的行业数据集",
    },
    {
        "domain": "resources.example",
        "overlap": 3,
        "pattern": "资源页型",
        "note": "资源页集中列出工具和教程",
    },
    {
        "domain": "press-daily.example",
        "overlap": 3,
        "pattern": "媒体PR型",
        "note": "新闻稿转载，编辑性要人工看",
    },
    {
        "domain": "community-wiki.example",
        "overlap": 2,
        "pattern": "资源页型",
        "note": "重叠较低，优先级靠后",
    },
    {
        "domain": "review-hub.example",
        "overlap": 3,
        "pattern": "数据驱动型",
        "note": "评测文里的链接，锚文本要自然",
    },
)

ANCHOR_ITEMS: tuple[dict[str, int | str], ...] = (
    {"type": "品牌词", "count": 42, "example": "示例品牌", "natural": "通常自然"},
    {"type": "部分匹配", "count": 28, "example": "品牌 SEO 指南", "natural": "通常自然"},
    {"type": "裸链", "count": 22, "example": "https://example.com/guide", "natural": "通常自然"},
    {"type": "通用词", "count": 16, "example": "查看这里", "natural": "常见，指向性弱"},
    {"type": "精确匹配", "count": 10, "example": "最好的 SEO 工具", "natural": "比例升高时要人工看"},
    {"type": "无文本图片", "count": 5, "example": "（图片链接）", "natural": "需要 alt 说明"},
)

ANCHOR_GUIDANCE: tuple[str, ...] = (
    "品牌词、部分匹配和裸链占多数时，锚文本通常更自然。",
    "精确匹配可以出现，比例升高时要人工看是不是过度优化。",
    "评分模型里的「锚文本」看的是自然度，不是某一种锚文本越多越好。",
)

CANDIDATES: tuple[dict[str, object], ...] = (
    {
        "name": "行业周刊资源页",
        "features": {
            "topical_relevance": 0.92,
            "editorial_placement": 0.86,
            "real_traffic": 0.74,
            "anchor_naturalness": 0.84,
            "authority_score": 0.80,
            "link_neighborhood": 0.77,
        },
    },
    {"name": "默认示例目标", "features": dict(EXAMPLE_FEATURES)},
    {
        "name": "近阈值评测文",
        "features": {
            "topical_relevance": 0.74,
            "editorial_placement": 0.66,
            "real_traffic": 0.58,
            "anchor_naturalness": 0.70,
            "authority_score": 0.62,
            "link_neighborhood": 0.60,
        },
    },
    {
        "name": "目录站批量链接",
        "features": {
            "topical_relevance": 0.40,
            "editorial_placement": 0.12,
            "real_traffic": 0.55,
            "anchor_naturalness": 0.20,
            "authority_score": 0.45,
            "link_neighborhood": 0.10,
        },
    },
)

KANBAN: tuple[dict[str, object], ...] = (
    {"title": "待规划", "tone": "plan", "items": ["市场调研", "竞品名单确认"]},
    {"title": "进行中", "tone": "doing", "items": ["SEO 关键词研究", "外链差距筛选"]},
    {"title": "待优化", "tone": "review", "items": ["SEO 优化建议", "锚文本自然度"]},
    {"title": "已完成", "tone": "done", "items": ["关键词布局"]},
)

KNOWLEDGE: dict[str, object] = {
    "intro": "这些笔记用来建立判断框架。工具强弱是学习标注，算法部分只整理公开可查的方向。",
    "algorithm": {
        "title": "2026 算法学习笔记",
        "summary": "整理公开可查的方向，用来对照自己的页面，而不是预测下一次更新。",
        "points": [
            "先满足搜索意图，再谈关键词放在哪里。",
            "经验信号变重：过程、原始数据和真实案例，比改写别人的结论更站得住。",
            "垃圾政策重点看规模化滥造、借用高权重站点发无关内容，以及过期域名跳转。",
            "页面体验是入场条件：移动端能用，主要内容稳定出现，插页不挡住阅读。",
            "结构化数据帮助搜索引擎理解页面，空洞内容加上标记仍然站不住。",
        ],
    },
    "aio": {
        "title": "AI Overviews",
        "summary": "复杂问题上面可能先出现一段带来源引用的生成式摘要。",
        "points": [
            "容易被引用的段落通常定义清楚、数字可核对，并且能脱离全文单独读懂。",
            "摘要会分走一部分点击。页面同时要争取被引用，和让人点进来的深度。",
            "用品牌词和产品词搜索，看摘要有没有提到你，引用的是不是你的页面。",
            "正文留下步骤、比较和经验。短答案可以被摘要拿走，深度留在页面上。",
        ],
    },
    "eeat": {
        "title": "E-E-A-T",
        "summary": "信任是底座。经验、专业和权威都要落到读者能核对的页面上。",
        "pillars": [
            {"key": "Experience", "label": "经验", "text": "你真的做过吗？写出过程、限制和结果。"},
            {"key": "Expertise", "label": "专业", "text": "作者有没有能力把这个题目讲清楚。"},
            {"key": "Authoritativeness", "label": "权威", "text": "行业里有没有别人引用你、提到你。"},
            {"key": "Trustworthiness", "label": "信任", "text": "信息准确，身份透明，页面安全，广告和正文分得开。"},
        ],
    },
    "tools": {
        "title": "工具对比",
        "summary": "下面的强弱是学习笔记里的主观标注，方便对照记忆。",
        "badge": "示例数据",
        "scenes": ["外链研究", "竞品差距", "关键词", "自有点击", "技术审计"],
        "rows": [
            {
                "tool": "Ahrefs",
                "ratings": ["强", "强", "一般", "无", "一般"],
                "fit": "外链交集和断链优先从这里看。",
            },
            {
                "tool": "Semrush",
                "ratings": ["一般", "强", "强", "无", "一般"],
                "fit": "关键词差距和内容规划更直接。",
            },
            {
                "tool": "Moz",
                "ratings": ["一般", "一般", "一般", "无", "一般"],
                "fit": "适合作为第二意见，主流程仍以上面两家和官方数据为准。",
            },
            {
                "tool": "Google Search Console",
                "ratings": ["弱", "无", "一般", "强", "强"],
                "fit": "自有点击、展示、查询和覆盖报告以它为准。",
            },
        ],
    },
}


def competitor_rows() -> list[dict[str, int | str]]:
    return copy.deepcopy(list(COMPETITORS))


def gap_rows() -> list[dict[str, int | str]]:
    return copy.deepcopy(list(GAP_ROWS))


def anchor_items() -> list[dict[str, int | str]]:
    return copy.deepcopy(list(ANCHOR_ITEMS))


def anchor_guidance() -> list[str]:
    return list(ANCHOR_GUIDANCE)


def candidates() -> list[dict[str, object]]:
    return copy.deepcopy(list(CANDIDATES))


def kanban_columns() -> list[dict[str, object]]:
    return copy.deepcopy(list(KANBAN))


def knowledge_content() -> dict[str, object]:
    return copy.deepcopy(KNOWLEDGE)
