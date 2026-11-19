"""
ReAct 推理模式实现（2026 优化版）
Thought → Action → Observation 循环，完整轨迹记录。
增强：重复动作检测、错误反馈、步数预算、可观测性。
"""

import uuid
from typing import Dict, Any, List, Callable
from .base import BaseAgent

class ReActAgent(BaseAgent):
    """支持 ReAct 循环的 Agent 基类"""
    def __init__(self, name: str, max_steps: int = 8):
        super().__init__(name)
        self.max_steps = max_steps
        self.tools: Dict[str, Callable] = {}

    def register_tool(self, name: str, func: Callable) -> None:
        """注册 ReAct 工具（action 名 → 函数）"""
        self.tools[name] = func

    def think(self, context: Dict[str, Any], trajectory: List[Dict]) -> Dict[str, Any]:
        """模拟思考：根据上下文决定下一步。子类可重写。"""
        raise NotImplementedError

    def _detect_repeat(self, trajectory: List[Dict], action_name: str) -> bool:
        recent = [t for t in trajectory if t.get("type") == "action"][-2:]
        return len(recent) >= 2 and all(t.get("tool") == action_name for t in recent)

    def execute(self, task: Dict[str, Any]) -> Dict[str, Any]:
        """Thought → Action → Observation 循环，直到给出答案或达到最大步数；返回答案与完整轨迹"""
        trajectory = []
        context = {"task": task, "observations": [], "errors": []}
        final_answer = None
        repeated = 0

        for step in range(1, self.max_steps + 1):
            # 1. Thought
            thought = self.think(context, trajectory)
            trajectory.append({
                "step": step,
                "type": "thought",
                "content": thought.get("thought", ""),
                "decision": thought.get("decision", "continue")
            })

            if thought.get("decision") == "finish":
                final_answer = thought.get("answer")
                break

            # 2. Action
            action_name = thought.get("action")
            action_input = thought.get("action_input", {})

            if self._detect_repeat(trajectory, action_name):
                repeated += 1
                observation = {"warning": "检测到重复动作，已跳过", "action": action_name}
                trajectory.append({
                    "step": step,
                    "type": "observation",
                    "content": observation
                })
                context["observations"].append(observation)
                if repeated >= 2:
                    final_answer = {"message": "重复动作过多，提前终止", "observations": context["observations"]}
                    break
                continue

            trajectory.append({
                "step": step,
                "type": "action",
                "tool": action_name,
                "input": action_input
            })

            # 3. Observation
            if action_name in self.tools:
                try:
                    observation = self.tools[action_name](action_input, context)
                except Exception as e:
                    observation = {"error": str(e), "recoverable": True}
                    context["errors"].append(str(e))
            else:
                observation = {"error": f"工具 {action_name} 不存在", "recoverable": False}

            trajectory.append({
                "step": step,
                "type": "observation",
                "content": observation
            })
            context["observations"].append(observation)

        if final_answer is None:
            final_answer = {
                "message": "达到最大步数，基于已有观察给出结果",
                "observations": context["observations"],
                "errors": context["errors"]
            }

        return {
            "result": final_answer,
            "trajectory": trajectory,
            "steps_used": len([t for t in trajectory if t["type"] == "thought"]),
            "errors_count": len(context["errors"]),
            "run_id": f"run_{uuid.uuid4().hex[:8]}",
            "mode": "ReAct-2026"
        }
