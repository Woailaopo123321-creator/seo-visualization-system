"""ReAct 循环：Thought → Action → Observation。"""

from __future__ import annotations

from typing import Any, Callable

ToolFunc = Callable[[dict[str, Any], dict[str, Any]], dict[str, Any]]


class ReActAgent:
    """按思考、行动、观察推进，直到结束或达到步数上限。

    子类覆盖 :meth:`think`。工具缺失、返回值不合法或执行抛错时，
    错误会写进观察，不会直接抛给调用方。
    """

    def __init__(self, name: str, max_steps: int = 10) -> None:
        if not isinstance(name, str) or not name.strip():
            raise ValueError("Agent 名称不能为空")
        if isinstance(max_steps, bool) or not isinstance(max_steps, int) or max_steps < 1:
            raise ValueError("max_steps 至少为 1")
        self.name = name.strip()
        self.max_steps = max_steps
        self.tools: dict[str, ToolFunc] = {}

    def register_tool(self, name: str, func: ToolFunc) -> None:
        """注册一个工具。同名注册会覆盖旧工具。"""

        if not isinstance(name, str) or not name.strip():
            raise ValueError("工具名称不能为空")
        if not callable(func):
            raise TypeError("工具必须可调用")
        self.tools[name.strip()] = func

    def think(self, context: dict[str, Any], trajectory: list[dict[str, Any]]) -> dict[str, Any]:
        """决定下一步。

        返回 ``decision="finish"`` 和 ``answer`` 表示结束。
        否则返回 ``action`` 与 ``action_input``。
        """

        return {
            "decision": "finish",
            "text": "没有更多动作",
            "answer": {"summary": "done"},
        }

    def run(self, context: dict[str, Any] | None = None) -> dict[str, Any]:
        """执行循环，返回是否完成、答案和完整轨迹。"""

        ctx = self._copy_context(context)
        trajectory: list[dict[str, Any]] = []
        answer: dict[str, Any] = {"summary": "已达到最大步数"}
        finished = False

        for step in range(1, self.max_steps + 1):
            thought = self._safe_think(ctx, trajectory)
            failed = bool(thought.get("error"))
            thought_content: dict[str, Any] = {
                "text": str(thought.get("text") or ""),
                "decision": thought.get("decision"),
            }
            if failed:
                thought_content["error"] = thought["error"]
            trajectory.append(self._event(step, "thought", thought, thought_content))

            if thought.get("decision") == "finish":
                raw_answer = thought.get("answer") or {}
                answer = raw_answer if isinstance(raw_answer, dict) else {"summary": str(raw_answer)}
                finished = not failed
                break

            action_input = thought.get("action_input")
            if not isinstance(action_input, dict):
                action_input = {}
            trajectory.append(
                self._event(
                    step,
                    "action",
                    thought,
                    {"tool": thought.get("action"), "input": action_input},
                )
            )
            trajectory.append(
                self._event(
                    step,
                    "observation",
                    thought,
                    self._invoke(thought.get("action"), action_input, ctx),
                )
            )
        else:
            answer = {"summary": "已达到最大步数", "human_gate": "流程未完成，需人工接手"}
            finished = False

        return {
            "agent": self.name,
            "finished": finished,
            "answer": answer,
            "trajectory": trajectory,
        }

    def _copy_context(self, context: dict[str, Any] | None) -> dict[str, Any]:
        if context is None:
            return {}
        if not isinstance(context, dict):
            raise TypeError("context 必须是字典")
        return dict(context)

    def _safe_think(self, context: dict[str, Any], trajectory: list[dict[str, Any]]) -> dict[str, Any]:
        try:
            thought = self.think(context, trajectory)
        except Exception as exc:
            return {
                "decision": "finish",
                "text": "思考阶段出错",
                "error": str(exc),
                "answer": {"summary": "思考失败", "error": str(exc)},
            }
        if not isinstance(thought, dict):
            return {
                "decision": "finish",
                "text": "思考结果无效",
                "error": "think() 必须返回字典",
                "answer": {"summary": "思考结果无效"},
            }
        return thought

    def _invoke(self, action: Any, action_input: dict[str, Any], context: dict[str, Any]) -> dict[str, Any]:
        if not isinstance(action, str) or action not in self.tools:
            return {"ok": False, "error": f"未知工具：{action}"}
        try:
            result = self.tools[action](action_input, context)
        except Exception as exc:
            return {"ok": False, "error": f"工具执行失败：{exc}"}
        if not isinstance(result, dict):
            return {"ok": False, "error": "工具必须返回字典"}
        payload = dict(result)
        payload.setdefault("ok", True)
        return payload

    @staticmethod
    def _event(step: int, kind: str, thought: dict[str, Any], content: dict[str, Any]) -> dict[str, Any]:
        return {
            "step": step,
            "type": kind,
            "stage": thought.get("stage"),
            "stage_label": thought.get("stage_label"),
            "content": content,
        }
