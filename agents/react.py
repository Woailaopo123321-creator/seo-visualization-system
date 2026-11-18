from typing import Dict, Any, List, Callable

class ReActAgent:
    """ReAct 基类：Thought-Action-Observation 循环"""
    def __init__(self, name: str, max_steps: int = 10):
        self.name = name
        self.max_steps = max_steps
        self.tools = {}

    def register_tool(self, name: str, func: Callable):
        self.tools[name] = func

    def think(self, context: Dict, trajectory: List) -> Dict:
        return {"decision": "finish", "answer": {"summary": "done"}}

    def run(self, context: Dict = None) -> Dict:
        context = context or {}
        trajectory = []
        for _ in range(self.max_steps):
            thought = self.think(context, trajectory)
            trajectory.append({"type": "thought", "content": thought})
            if thought.get("decision") == "finish":
                return thought.get("answer", {})
            action = thought.get("action")
            if action and action in self.tools:
                obs = self.tools[action](thought.get("action_input", {}), context)
                trajectory.append({"type": "observation", "content": obs})
        return {"summary": "max steps reached"}
