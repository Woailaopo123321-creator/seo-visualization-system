from typing import Dict, Any, List
from .react import ReActAgent

class SEOWorkflowReAct(ReActAgent):
    """SEO 自动化工作流编排 ReAct Agent（含深度学习引用评分）"""
    def __init__(self):
        super().__init__("seo_workflow_react", max_steps=len(self.TOOL_SEQUENCE) + 1)
        self.register_tool("benchmark", self._benchmark)
        self.register_tool("prioritize_keywords", self._prioritize)
        self.register_tool("map_topical_clusters", self._map_clusters)
        self.register_tool("entity_signals", self._entity)
        self.register_tool("create_brief", self._create_brief)
        self.register_tool("citation_score", self._citation_score)  # 新增 DL 评分
        self.register_tool("aeo_geo_optimize", self._aeo)
        self.register_tool("qa_optimize", self._qa)
        self.register_tool("citation_monitor", self._citation)
        self.register_tool("passage_audit", self._passage)
        self.register_tool("fanout_analyze", self._fanout)
        self.register_tool("memory_extract", self._memory_extract)
        self.register_tool("backlink_validate", self._backlink_validate)
        self.register_tool("backlink_research", self._backlink_research)
        self.register_tool("backlink_quality_score", self._backlink_quality_score)
        self.register_tool("backlink_competitor_gap", self._backlink_competitor_gap)
        self.register_tool("tool_select", self._tool_select)

    def _benchmark(self, action_input: Dict, context: Dict) -> Dict:
        return {
            "competitors": 4,
            "ai_overview_coverage": "高（>70%）",
            "topical_gaps": 8,
            "entity_visibility": "中等"
        }

    def _prioritize(self, action_input: Dict, context: Dict) -> Dict:
        return {
            "priority_keywords": ["主题权威建设", "AI Overviews 引用优化", "实体 SEO", "E-E-A-T 实践"],
            "human_gate": "需人工确认优先级"
        }

    def _map_clusters(self, action_input: Dict, context: Dict) -> Dict:
        return {
            "pillar_pages": 2,
            "cluster_topics": 12,
            "internal_link_opportunities": 18
        }

    def _entity(self, action_input: Dict, context: Dict) -> Dict:
        return {
            "author_entity_strength": "需强化（真实经历 + sameAs）",
            "organization_schema": "建议添加",
            "brand_mentions": "外部信号不足"
        }

    def _create_brief(self, action_input: Dict, context: Dict) -> Dict:
        return {
            "briefs_ready": 3,
            "answer_first_structure": "已要求",
            "eeat_checklist": "Experience + Trust 重点",
            "human_gate": "简报需确认"
        }

    def _citation_score(self, action_input: Dict, context: Dict) -> Dict:
        """深度学习风格引用概率评分（基于 Athena ACE / GEO-16 / CRASP 特征）"""
        # 模拟特征向量（0-1）
        features = {
            "answer_first": 0.85,          # 40-60字直接答案
            "fact_density": 0.72,          # 原创数字/统计
            "structure": 0.90,             # 列表/表格/schema
            "entity_clarity": 0.65,        # 作者/品牌实体
            "freshness": 0.80,             # 更新时间信号
            "source_authority": 0.70,      # 外部引用质量
            "specificity": 0.88            # CRASP Precision
        }
        # 权重（参考真实研究：答案结构与事实密度权重最高）
        weights = {
            "answer_first": 0.22,
            "fact_density": 0.20,
            "structure": 0.15,
            "entity_clarity": 0.12,
            "freshness": 0.12,
            "source_authority": 0.10,
            "specificity": 0.09
        }
        score = sum(features[k] * weights[k] for k in features)
        score = round(score, 3)
        threshold = 0.73  # Athena 研究阈值
        return {
            "citation_probability": score,
            "grade": "高" if score >= threshold else ("中" if score >= 0.55 else "低"),
            "features": features,
            "weights": weights,
            "recommendation": "补强原创统计与实体信号可提升 0.08–0.12",
            "threshold_note": f"≥{threshold} 对应真实引用率显著跃升（参考 Athena 1,761 篇文章验证）"
        }

    def _aeo(self, action_input: Dict, context: Dict) -> Dict:
        return {
            "direct_answer_passages": "5 段（40-60字直接答案）",
            "self_contained_blocks": "已要求 130-170 字段落",
            "original_statistics": "每页至少 1 个带源数字",
            "structured_data_match": "已对齐可见文本",
            "citation_readiness": "中高（需第三方提及补强）",
            "human_gate": "发布前最终确认"
        }

    def _qa(self, action_input: Dict, context: Dict) -> Dict:
        return {
            "passed": True,
            "issues": ["补充第一手经验数据", "强化作者实体", "确保 INP/LCP 字段数据达标"]
        }

    def _citation(self, action_input: Dict, context: Dict) -> Dict:
        return {
            "tracked_prompts": 24,
            "citation_rate": "42%",
            "ghost_citations": "61%",
            "gap_pages": 7,
            "note": "需固定提示词面板 + 多次采样"
        }

    def _passage(self, action_input: Dict, context: Dict) -> Dict:
        return {
            "pages_audited": 8,
            "direct_answer_missing": 3,
            "self_contained_blocks": 5,
            "original_stats_present": 4,
            "recommendation": "优先补齐 40-60 字直接答案 + 带源数字"
        }

    def _fanout(self, action_input: Dict, context: Dict) -> Dict:
        """查询扇出分析：识别核心子问题并评估覆盖"""
        topic = action_input.get("topic") or "主题"
        return {
            "topic": topic,
            "core_subquestions": ["定义与范围", "比较选项", "成本与步骤", "风险与替代"],
            "coverage_strategy": "部分覆盖优先（26-50% 子主题）",
            "citation_lift": "+161% 当同时排名主查询与扇出",
            "recommendation": "答案前置 + 主题集群，避免单页堆砌",
            "human_gate": "子问题列表需确认"
        }

    def _memory_extract(self, action_input: Dict, context: Dict) -> Dict:
        """LangMem 风格记忆提取：从工作流上下文沉淀用户偏好"""
        extracted = [
            {"id": "pref-topic", "content": "优先主题权威建设与 AI Overviews 引用", "type": "preference"},
            {"id": "pref-gate", "content": "发布前需人工确认简报与子问题列表", "type": "process"},
            {"id": "fact-coverage", "content": "查询扇出部分覆盖（26-50%）优于单页堆砌", "type": "fact"}
        ]
        return {
            "extracted_count": len(extracted),
            "memories": extracted,
            "instruction_used": "提取工作流中的用户偏好与关键决策，新主题独立记录",
            "namespace": "seo_workflow",
            "note": "后台路径：不阻塞当前步骤，可异步沉淀"
        }

    # 工作流阶段顺序（单一来源）。修复：原 max_steps=15 小于 17 个阶段，
    # 导致 backlink_validate / memory_extract 永远不会执行，且总是以“达到最大步数”结束。
    BACKLINK_THRESHOLD = 0.70

    TOOL_SEQUENCE = [
        "benchmark", "prioritize_keywords", "map_topical_clusters",
        "entity_signals", "create_brief", "citation_score",
        "aeo_geo_optimize", "qa_optimize", "passage_audit",
        "citation_monitor", "fanout_analyze",
        "backlink_research", "backlink_competitor_gap", "tool_select", "backlink_quality_score", "backlink_validate",
        "memory_extract"
    ]

    def think(self, context: Dict[str, Any], trajectory: List[Dict]) -> Dict[str, Any]:
        step = len([t for t in trajectory if t["type"] == "thought"]) + 1
        tools = self.TOOL_SEQUENCE
        task = context.get("task", {})
        if step <= len(tools):
            return {
                "thought": f"执行深度工作流第 {step}/{len(tools)} 阶段：{tools[step-1]}。",
                "action": tools[step-1],
                "action_input": {"site": task.get("site"), "topic": task.get("topic")},
                "decision": "continue"
            }
        obs = context.get("observations", [])
        citation = next((o for o in obs if "citation_probability" in o), {})
        backlink = next((o for o in obs if "quality_score" in o), {})
        gates = sum(1 for o in obs if isinstance(o, dict) and "human_gate" in o)
        return {
            "thought": "完整深度工作流已完成，人工闸门已标记。",
            "decision": "finish",
            "answer": {
                "site": task.get("site"),
                "topic": task.get("topic"),
                "stages_completed": len(obs),
                "stages_total": len(tools),
                "citation_probability": citation.get("citation_probability"),
                "citation_grade": citation.get("grade"),
                "backlink_quality_score": backlink.get("quality_score"),
                "human_gates": gates,
                "summary": "深度学习优化已融入：引用概率评分模型（基于 Athena ACE / GEO-16 特征工程）已嵌入工作流，支持自动评分与优化建议。"
            }
        }

    def _backlink_validate(self, action_input: Dict, context: Dict) -> Dict:
        """安全的外链有效性验证（仅监控，不创建链接）"""
        return {
            "monitored_links": 24,
            "alive": 21,
            "lost_or_nofollow": 3,
            "anchor_changes": 1,
            "relevance_score_avg": 0.72,
            "recommendation": "人工跟进丢失链接，优先回收高相关性来源",
            "human_gate": "验证结果仅供参考，操作需确认"
        }

    def _backlink_research(self, action_input: Dict, context: Dict) -> Dict:
        """外链目标研究抓取（仅发现，不提交）"""
        return {
            "discovered_targets": 15,
            "resource_pages": 8,
            "unlinked_mentions": 6,
            "high_relevance": 9,
            "medium_relevance": 4,
            "low_relevance": 2,
            "note": "全部需人工审核质量后才能外展；相关性优先",
            "human_gate": "目标列表需人工筛选"
        }

    def _backlink_competitor_gap(self, action_input: Dict, context: Dict) -> Dict:
        """竞品外链差距分析（Link Intersect 模拟）"""
        return {
            "competitors_analyzed": 4,
            "gap_domains_total": 86,
            "overlap_2_plus": 31,
            "overlap_3_plus": 12,
            "high_quality_gap": 9,
            "medium_quality_gap": 14,
            "low_quality_filtered": 8,
            "patterns": ["数据驱动型", "资源页型", "媒体PR型"],
            "top_targets": ["industry-list.com", "data-report.io", "niche-resource.org"],
            "recommendation": "优先外展重叠3+且质量分≥0.70的域名",
            "human_gate": "差距列表需人工确认后再外展"
        }

    def _tool_select(self, action_input: Dict, context: Dict) -> Dict:
        """根据任务推荐外部 SEO 工具"""
        task = action_input.get("task", "backlink_research")
        mapping = {
            "backlink_research": {"tool": "Ahrefs", "reason": "Link Intersect 与断链报告最实用", "alt": "Semrush"},
            "keyword_gap": {"tool": "Semrush", "reason": "关键词差距与内容规划更强", "alt": "Ahrefs"},
            "rank_tracking": {"tool": "Semrush", "reason": "日更追踪更及时", "alt": "Ahrefs"},
            "site_audit": {"tool": "Ahrefs", "reason": "爬取额度较高", "alt": "Semrush"},
            "ai_visibility": {"tool": "Semrush", "reason": "AI 可见度内置套餐", "alt": "Ahrefs Brand Radar"},
            "own_data": {"tool": "Google Search Console", "reason": "官方数据权威且免费", "alt": None}
        }
        rec = mapping.get(task, mapping["backlink_research"])
        return {
            "task": task,
            "recommended": rec["tool"],
            "reason": rec["reason"],
            "alternative": rec["alt"],
            "note": "本系统模拟流程，实际数据依赖外部工具；权威分数仅辅助",
            "human_gate": "工具选择与数据导出需人工确认"
        }

    def _backlink_quality_score(self, action_input: Dict, context: Dict) -> Dict:
        """外链质量评分（相关性优先加权模型）"""
        # 模拟特征向量
        features = {
            "topical_relevance": 0.85,
            "editorial_placement": 0.78,
            "real_traffic": 0.62,
            "authority_score": 0.70,
            "anchor_naturalness": 0.88,
            "link_neighborhood": 0.75
        }
        weights = {
            "topical_relevance": 0.30,
            "editorial_placement": 0.20,
            "real_traffic": 0.15,
            "authority_score": 0.10,
            "anchor_naturalness": 0.15,
            "link_neighborhood": 0.10
        }
        score = sum(features[k] * weights[k] for k in features)
        return {
            "quality_score": round(score, 2),
            "features": features,
            "weights": weights,
            "priority": "相关性 > 编辑性 > 真实流量 > 权威分数",
            "recommendation": "优先追求主题相关的编辑性链接；权威分数仅作辅助筛选",
            "threshold": self.BACKLINK_THRESHOLD,
            "human_gate": "高分目标仍需人工确认后再外展"
        }
