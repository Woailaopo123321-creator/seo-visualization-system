from .base import BaseAgent
from typing import Dict, Any

class ProgressAnalyzerAgent(BaseAgent):
    """进度分析 Agent：分析学习任务并给出建议"""
    def __init__(self):
        super().__init__("progress_analyzer")

    def execute(self, task: Dict[str, Any]) -> Dict[str, Any]:
        tasks = task.get("tasks", [])
        if not tasks:
            return {"analysis": "暂无学习任务，建议先添加目标。", "suggestions": ["创建第一个学习计划"]}

        total = len(tasks)
        done = sum(1 for t in tasks if t.get("status") == "done")
        in_progress = sum(1 for t in tasks if t.get("status") == "in_progress")
        avg_progress = sum(t.get("progress", 0) for t in tasks) / max(total, 1)

        analysis = (
            f"当前共有 {total} 个学习任务。"
            f"已掌握 {done} 个，学习中 {in_progress} 个，"
            f"平均进度 {avg_progress:.0f}%。"
        )

        suggestions = []
        if done / max(total, 1) < 0.3:
            suggestions.append("建议优先完成高优先级的待学习任务，建立成就感。")
        if in_progress > 3:
            suggestions.append("学习中任务过多，建议聚焦 1-2 个核心任务。")
        suggestions.append("结合思维导图梳理已掌握知识点，加深记忆。")
        suggestions.append("定期使用进度看板回顾，调整学习节奏。")

        return {
            "analysis": analysis,
            "suggestions": suggestions,
            "metrics": {"total": total, "done": done, "avg_progress": round(avg_progress, 1)}
        }


class MindMapAgent(BaseAgent):
    """思维导图生成 Agent"""
    def __init__(self):
        super().__init__("mindmap_generator")

    def execute(self, task: Dict[str, Any]) -> Dict[str, Any]:
        topic = task.get("topic", "学习主题")
        # 模拟 AI 生成思维导图结构（可替换为真实 LLM 调用）
        structure = {
            "center": topic,
            "branches": [
                {"name": "核心概念", "children": ["定义", "关键特征", "应用场景"]},
                {"name": "学习路径", "children": ["基础知识", "进阶技巧", "实战练习"]},
                {"name": "常见问题", "children": ["易错点", "解决方案"]},
                {"name": "资源推荐", "children": ["书籍", "课程", "工具"]}
            ]
        }
        return {
            "topic": topic,
            "mindmap": structure,
            "description": f"已为「{topic}」生成思维导图结构，建议用手绘或工具进一步细化。"
        }


class RecommendationAgent(BaseAgent):
    """推荐 Agent：推荐可视化方案与学习策略"""
    def __init__(self):
        super().__init__("recommender")

    def execute(self, task: Dict[str, Any]) -> Dict[str, Any]:
        context = task.get("context", "general")
        schemes = {
            "general": ["思维导图（入门首选）", "进度看板（日常管理）", "概念图（知识体系）"],
            "complex": ["概念图", "知识图谱", "流程图"],
            "planning": ["时间线", "进度看板", "流程图"]
        }
        recommended = schemes.get(context, schemes["general"])
        return {
            "recommended_schemes": recommended,
            "reason": "根据当前学习场景智能匹配最适合的可视化方案。",
            "next_action": "选择一个方案开始实践，并在看板中跟踪进度。"
        }
