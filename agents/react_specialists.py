from typing import Dict, Any, List
from .react import ReActAgent

class ProgressAnalyzerReAct(ReActAgent):
    """使用 ReAct 模式的进度分析 Agent"""
    def __init__(self):
        super().__init__("progress_analyzer_react", max_steps=5)
        self.register_tool("query_tasks", self._query_tasks)
        self.register_tool("calculate_metrics", self._calculate_metrics)

    def _query_tasks(self, action_input: Dict, context: Dict) -> Dict:
        tasks = context["task"].get("tasks", [])
        return {"count": len(tasks), "sample": tasks[:3], "raw_count": len(tasks)}

    def _calculate_metrics(self, action_input: Dict, context: Dict) -> Dict:
        tasks = context["task"].get("tasks", [])
        if not tasks:
            return {"total": 0, "done": 0, "avg_progress": 0}
        total = len(tasks)
        done = sum(1 for t in tasks if t.get("status") == "done")
        in_progress = sum(1 for t in tasks if t.get("status") == "in_progress")
        avg = sum(t.get("progress", 0) for t in tasks) / total
        return {
            "total": total,
            "done": done,
            "in_progress": in_progress,
            "avg_progress": round(avg, 1)
        }

    def think(self, context: Dict[str, Any], trajectory: List[Dict]) -> Dict[str, Any]:
        observations = context.get("observations", [])
        step = len([t for t in trajectory if t["type"] == "thought"]) + 1

        if step == 1:
            return {
                "thought": "我需要先了解当前有多少学习任务，以及它们的状态分布。",
                "action": "query_tasks",
                "action_input": {},
                "decision": "continue"
            }
        elif step == 2:
            return {
                "thought": "已获取任务列表，现在计算关键指标（完成数、平均进度）。",
                "action": "calculate_metrics",
                "action_input": {},
                "decision": "continue"
            }
        else:
            metrics = observations[-1] if observations else {}
            analysis = (
                f"共 {metrics.get('total', 0)} 个任务，"
                f"已掌握 {metrics.get('done', 0)} 个，"
                f"平均进度 {metrics.get('avg_progress', 0)}%。"
            )
            suggestions = ["优先完成待学习任务建立成就感", "使用思维导图巩固已掌握内容"]
            return {
                "thought": "指标已计算完毕，可以给出分析结论和建议。",
                "decision": "finish",
                "answer": {
                    "analysis": analysis,
                    "suggestions": suggestions,
                    "metrics": metrics
                }
            }
