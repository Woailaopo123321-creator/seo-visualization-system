"""
页面注册表（单一数据源）
路由、导航菜单、站点地图、测试都从这里读取，新增页面只需在此登记一行。
"""

from collections import OrderedDict
from typing import Dict, List

# (路径, 模板, 标题, 分组)
PAGES = [
    # 总览
    ("/", "index.html", "学习进度看板", "总览"),
    ("/dashboard", "dashboard.html", "系统概览仪表盘", "总览"),
    ("/overview", "overview.html", "系统总览", "总览"),
    ("/mobile", "mobile_control.html", "手机控制台", "总览"),
    ("/schemes", "schemes.html", "可视化方案", "总览"),
    ("/sitemap", "sitemap.html", "全部页面", "总览"),
    # SEO 知识
    ("/seo", "seo.html", "SEO 可视化", "SEO 知识"),
    ("/seo-2026", "seo_2026.html", "谷歌 SEO 2026", "SEO 知识"),
    ("/seo-deep", "seo_deep.html", "2026 SEO 深度洞察", "SEO 知识"),
    ("/seo-path", "seo_path.html", "SEO 学习路径（ReAct）", "SEO 知识"),
    ("/seo-minimal", "seo_minimal.html", "SEO × 极简心理学", "SEO 知识"),
    ("/seo-tools", "seo_tools.html", "SEO 工具对比", "SEO 知识"),
    ("/keywords", "keywords.html", "关键词", "SEO 知识"),
    ("/eeat", "eeat.html", "E-E-A-T", "SEO 知识"),
    ("/eeat-audit", "eeat_audit.html", "E-E-A-T 深度审计", "SEO 知识"),
    ("/entity", "entity.html", "实体 SEO · sameAs", "SEO 知识"),
    ("/topical", "topical.html", "主题权威 · 支柱-集群", "SEO 知识"),
    ("/passage", "passage.html", "段落架构", "SEO 知识"),
    ("/aeo-geo", "aeo_geo.html", "SEO · AEO · GEO", "SEO 知识"),
    ("/aio-optimize", "aio_optimize.html", "AI Overviews 优化", "SEO 知识"),
    ("/fanout", "fanout.html", "查询扇出", "SEO 知识"),
    ("/citation", "citation.html", "AI 引用追踪", "SEO 知识"),
    ("/decay", "decay_monitoring.html", "引用衰减监控", "SEO 知识"),
    ("/crasp", "crasp.html", "CRASP 框架", "SEO 知识"),
    ("/crasp-vs-cited", "crasp_vs_cited.html", "CRASP vs CITED", "SEO 知识"),
    # 外链
    ("/backlink", "backlink.html", "外链策略 2026", "外链分析"),
    ("/backlink-tools", "backlink_tools.html", "外链四工具", "外链分析"),
    ("/backlink-quality", "backlink_quality.html", "外链质量指标", "外链分析"),
    ("/backlink-score-model", "backlink_score_model.html", "质量评分模型", "外链分析"),
    ("/backlink-competitor", "backlink_competitor.html", "竞品外链结构", "外链分析"),
    ("/backlink-competitor-quality", "backlink_competitor_quality.html", "竞品外链质量", "外链分析"),
    ("/anchor-text", "anchor_text.html", "锚文本分布", "外链分析"),
    ("/backlink-auto", "backlink_auto.html", "外链自动化边界", "外链分析"),
    # AI 与自动化
    ("/workflow-runs", "workflow_runs.html", "工作流审批台（LangGraph）", "AI 与自动化"),
    ("/agent-architecture", "agent_architecture.html", "本系统多 AI 架构与路线图", "AI 与自动化"),
    ("/agent-patterns", "agent_patterns.html", "多智能体模式与框架对比", "AI 与自动化"),
    ("/ai", "ai.html", "AI 管理中心", "AI 与自动化"),
    ("/ai-react", "ai_react.html", "ReAct 轨迹", "AI 与自动化"),
    ("/seo-workflow", "seo_workflow.html", "自动化 SEO 工作流", "AI 与自动化"),
    ("/ai-workflow", "ai_workflow.html", "AI 自动化工作流", "AI 与自动化"),
    ("/dl-seo", "dl_seo.html", "深度学习引用评分", "AI 与自动化"),
    ("/dl-automation", "dl_automation.html", "深度学习自动化", "AI 与自动化"),
    ("/multi-agent", "multi_agent.html", "多智能体架构", "AI 与自动化"),
    ("/agent-security", "agent_security.html", "智能体安全协议", "AI 与自动化"),
    # 架构与记忆
    ("/langgraph", "langgraph.html", "LangGraph 框架", "架构与记忆"),
    ("/langgraph-state", "langgraph_state.html", "LangGraph 状态管理", "架构与记忆"),
    ("/langchain-memory", "langchain_memory.html", "LangChain 记忆", "架构与记忆"),
    ("/langmem-semantic", "langmem_semantic.html", "LangMem 语义提取", "架构与记忆"),
    ("/langmem-dedup", "langmem_dedup.html", "LangMem 去重合并", "架构与记忆"),
    ("/langmem-instructions", "langmem_instructions.html", "LangMem 指令设计", "架构与记忆"),
    ("/microservices", "microservices.html", "微服务架构", "架构与记忆"),
    ("/consistency", "consistency.html", "分布式一致性", "架构与记忆"),
    ("/cache-strategy", "cache_strategy.html", "分布式缓存策略", "架构与记忆"),
    # 心理学
    ("/minimal-psych", "minimal_psych.html", "极简设计心理学", "心理学"),
]


def endpoint_name(template: str) -> str:
    """模板名 → Flask endpoint 名（index.html → page_index）"""
    return "page_" + template.rsplit(".", 1)[0]


def grouped_pages() -> "OrderedDict[str, List[Dict[str, str]]]":
    """按分组整理的页面列表（侧栏导航、站点地图、/api/pages 共用）"""
    groups = OrderedDict()
    for path, _tpl, title, group in PAGES:
        groups.setdefault(group, []).append({"path": path, "title": title})
    return groups
