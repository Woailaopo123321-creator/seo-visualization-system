"""工作流结构定义（单一数据源）。图构建、API、页面都读取这里。"""

from typing import Any, Dict, List, Optional, Tuple

# 阶段：id, 中文名, 所属阶段组, 未来接入点（None = 确定性代码即可，无需外部服务）
STAGES: List[Tuple[str, str, str, Optional[str]]] = [
    ("benchmark", "竞品基准", "research", "MCP"),
    ("prioritize_keywords", "关键词优先级", "research", "MCP"),
    ("map_topical_clusters", "主题集群", "content", None),
    ("entity_signals", "实体信号", "content", None),
    ("create_brief", "内容简报", "content", "LLM"),
    ("citation_score", "DL 引用评分", "optimize", None),
    ("aeo_geo_optimize", "AEO/GEO 优化", "optimize", None),
    ("qa_optimize", "QA 检查", "optimize", None),
    ("passage_audit", "段落审计", "audit", "MCP"),
    ("citation_monitor", "引用监控", "audit", "MCP"),
    ("fanout_analyze", "查询扇出", "audit", "LLM"),
    ("backlink_research", "外链调研", "backlink", "MCP"),
    ("backlink_competitor_gap", "竞品差距", "backlink", "MCP"),
    ("tool_select", "工具选择", "backlink", None),
    ("backlink_quality_score", "外链质量评分", "backlink", None),
    ("backlink_validate", "外链验证", "finish", "MCP"),
    ("memory_extract", "记忆提取", "finish", "LLM"),
]
STAGE_IDS = [s[0] for s in STAGES]
STAGE_TITLES = {s[0]: s[1] for s in STAGES}
STAGE_TITLES.update({"audit_join": "审计汇合", "finalize": "完成"})

PHASES = [
    ("research", "① 研究"),
    ("content", "② 内容"),
    ("optimize", "③ 优化"),
    ("audit", "④ 并行审计"),
    ("backlink", "⑤ 外链"),
    ("finish", "⑥ 收尾"),
]

# 并行审计分支：三个节点同时执行，汇合后进入发布闸门
PARALLEL_AUDITS = ["passage_audit", "citation_monitor", "fanout_analyze"]

# 人工审批闸门（真正的 interrupt）：after = 位于哪个节点之后；optional = 可选闸门（每次运行可单独开关）
GATES: Dict[str, Dict[str, Any]] = {
    "keywords": {
        "after": "prioritize_keywords", "title": "关键词优先级确认", "short": "关键词", "priority": "高",
        "description": "确认或改写本轮要做的优先关键词。批准后才会进入主题集群与简报。",
        "on_reject": "end", "optional": False,
    },
    "brief": {
        "after": "create_brief", "title": "内容简报审批", "short": "简报", "priority": "高",
        "description": "通过、修改，或打回重写简报（最多重写 2 次）。",
        "on_reject": "rewrite", "optional": False,
    },
    "fanout": {
        "after": "audit_join", "title": "查询扇出子问题确认", "short": "扇出", "priority": "中",
        "description": "确认这篇内容要覆盖哪些扇出子问题（AI 搜索会把主查询拆成这些子问题）。可增删改。",
        "on_reject": "end", "optional": True,
    },
    "publish": {
        "after": "audit_join", "title": "发布前最终确认", "short": "发布", "priority": "高",
        "description": "查看引用评分、QA 问题与并行审计结果，确认是否发布。",
        "on_reject": "end", "optional": False,
    },
    "tool_select": {
        "after": "tool_select", "title": "外链数据工具确认", "short": "工具", "priority": "中",
        "description": "确认外链调研使用哪个数据工具（接入真实工具后会产生 API 费用）。",
        "on_reject": "end", "optional": True,
    },
    "outreach": {
        "after": "backlink_quality_score", "title": "外链外展审批", "short": "外展", "priority": "高",
        "description": "筛选允许外展的目标域名。未批准前不会进行任何外联。",
        "on_reject": "end", "optional": False,
    },
}
GATE_ORDER = ["keywords", "brief", "fanout", "publish", "tool_select", "outreach"]
REQUIRED_GATES = [g for g in GATE_ORDER if not GATES[g]["optional"]]
OPTIONAL_GATES = [g for g in GATE_ORDER if GATES[g]["optional"]]
BACKLINK_TOOLS = ["Ahrefs", "Semrush", "Moz", "Majestic"]
MAX_BRIEF_REVISIONS = 2

PLUG_LABELS: Dict[str, str] = {"MCP": "可接 MCP / 官方 API（只读数据）", "LLM": "需 LLM 密钥（当前为模板生成）"}


def graph_spec() -> Dict[str, Any]:
    """给前端用的结构描述：阶段分组、每组之后的闸门、可选闸门列表"""
    phases = []
    for pid, ptitle in PHASES:
        ids = [s[0] for s in STAGES if s[2] == pid]
        stages = [{"id": s[0], "title": s[1], "plug": s[3]} for s in STAGES if s[2] == pid]
        anchors = set(ids) | ({"audit_join"} if pid == "audit" else set())
        gates_after = [g for g in GATE_ORDER if GATES[g]["after"] in anchors]
        phases.append({"id": pid, "title": ptitle, "parallel": pid == "audit", "stages": stages,
                       "gates_after": gates_after})
    return {
        "phases": phases,
        "gates": [{"id": g, **GATES[g]} for g in GATE_ORDER],
        "stage_count": len(STAGES),
        "gate_count": len(GATES),
        "required_gates": REQUIRED_GATES,
        "optional_gates": OPTIONAL_GATES,
        "parallel": PARALLEL_AUDITS,
        "plug_labels": PLUG_LABELS,
    }
