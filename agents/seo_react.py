from typing import Dict, Any, List
from .react import ReActAgent

class SEOLearningPathReAct(ReActAgent):
    """2026 优化版：专门分析 SEO 学习路径的 ReAct Agent（融入 E-E-A-T / Helpful Content / AI Overviews）"""
    def __init__(self):
        super().__init__("seo_learning_path_react", max_steps=6)
        self.register_tool("get_seo_stages", self._get_seo_stages)
        self.register_tool("analyze_stage_progress", self._analyze_stage_progress)
        self.register_tool("suggest_next_steps", self._suggest_next_steps)

    def _get_seo_stages(self, action_input: Dict, context: Dict) -> Dict:
        stages = [
            {"id": 1, "name": "搜索意图与关键词", "description": "匹配查询意图，长尾词挖掘，主题集群"},
            {"id": 2, "name": "Helpful Content + E-E-A-T", "description": "真实经验、原创性、专业性、信任信号（Trust 最重要）"},
            {"id": 3, "name": "页面与内容结构", "description": "主内容质量、标题结构、内部链接、可提取答案"},
            {"id": 4, "name": "技术基础与页面体验", "description": "可抓取/索引、Core Web Vitals (LCP/INP/CLS)、移动优先"},
            {"id": 5, "name": "权威与外链", "description": "自然反向链接、品牌提及、主题权威"},
            {"id": 6, "name": "AI 搜索与测量", "description": "AI Overviews 引用准备、Search Console、持续迭代"}
        ]
        return {"stages": stages, "total_stages": len(stages), "year": 2026}

    def _analyze_stage_progress(self, action_input: Dict, context: Dict) -> Dict:
        progress = {
            "搜索意图与关键词": 45,
            "Helpful Content + E-E-A-T": 20,
            "页面与内容结构": 30,
            "技术基础与页面体验": 15,
            "权威与外链": 10,
            "AI 搜索与测量": 5
        }
        avg = sum(progress.values()) / len(progress)
        weak = [k for k, v in progress.items() if v < 35]
        return {
            "stage_progress": progress,
            "average": round(avg, 1),
            "weak_stages": weak,
            "priority_focus": "Helpful Content 与技术基础是当前最大杠杆"
        }

    def _suggest_next_steps(self, action_input: Dict, context: Dict) -> Dict:
        weak = action_input.get("weak_stages", [])
        suggestions = []
        if any("Helpful" in w or "E-E-A-T" in w for w in weak):
            suggestions.append("补充真实经验与作者信息，避免纯 AI 生成无事实核查内容")
        if any("技术" in w for w in weak):
            suggestions.append("优先修复 Core Web Vitals（LCP≤2.5s, INP≤200ms, CLS≤0.1）与移动端可抓取性")
        if any("AI" in w for w in weak):
            suggestions.append("确保页面可被 snippet 引用，主内容可提取、结构清晰")
        suggestions.append("建立主题集群，强化内部链接与品牌提及")
        return {"suggestions": suggestions[:4], "priority": "先补 Helpful Content 与技术门槛"}

    def think(self, context: Dict[str, Any], trajectory: List[Dict]) -> Dict[str, Any]:
        observations = context.get("observations", [])
        step = len([t for t in trajectory if t["type"] == "thought"]) + 1

        if step == 1:
            return {"thought": "获取 2026 年适配的 SEO 学习阶段定义。", "action": "get_seo_stages", "action_input": {}, "decision": "continue"}
        elif step == 2:
            return {"thought": "分析当前各阶段进度，识别薄弱环节。", "action": "analyze_stage_progress", "action_input": {}, "decision": "continue"}
        elif step == 3:
            prog = observations[-1] if observations else {}
            return {"thought": f"进度平均 {prog.get('average', 0)}%，薄弱：{prog.get('weak_stages', [])}。生成可执行建议。", "action": "suggest_next_steps", "action_input": {"weak_stages": prog.get("weak_stages", [])}, "decision": "continue"}
        else:
            return {
                "thought": "输出完整 2026 SEO 学习路径分析与可执行方案。",
                "decision": "finish",
                "answer": {
                    "summary": "基于 2026 Google 算法：相关性 + Helpful Content/E-E-A-T + 技术可访问性是核心。",
                    "stage_progress": observations[1].get("stage_progress", {}) if len(observations) > 1 else {},
                    "weak_stages": observations[1].get("weak_stages", []) if len(observations) > 1 else [],
                    "next_actions": observations[2].get("suggestions", []) if len(observations) > 2 else [],
                    "executable_plan": [
                        "1. 审计主内容质量（努力、原创、专业、准确）",
                        "2. 修复 Core Web Vitals 与移动索引问题",
                        "3. 建立主题集群 + 真实作者信号",
                        "4. 监控 Search Console 与 AI Overview 引用"
                    ]
                }
            }
