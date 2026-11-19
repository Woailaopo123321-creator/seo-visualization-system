from typing import Dict, Any, List
from .react import ReActAgent

class EEATAuditReAct(ReActAgent):
    """深度 E-E-A-T 信任信号审计 ReAct Agent"""
    def __init__(self):
        super().__init__("eeat_audit_react", max_steps=7)
        self.register_tool("check_author_signals", self._check_author)
        self.register_tool("check_experience_evidence", self._check_experience)
        self.register_tool("check_trust_foundations", self._check_trust)
        self.register_tool("generate_audit_report", self._generate_report)

    def _check_author(self, action_input: Dict, context: Dict) -> Dict:
        return {
            "has_real_bylines": False,
            "verifiable_profiles": False,
            "fake_risk": "高（需检查是否存在 AI 生成头像或虚构资质）",
            "score": 35
        }

    def _check_experience(self, action_input: Dict, context: Dict) -> Dict:
        return {
            "first_hand_evidence": "弱",
            "original_photos_or_data": False,
            "specific_process_described": False,
            "score": 28
        }

    def _check_trust(self, action_input: Dict, context: Dict) -> Dict:
        return {
            "about_page": True,
            "contact_info": True,
            "policies": False,
            "error_correction": False,
            "https": True,
            "score": 55
        }

    def _generate_report(self, action_input: Dict, context: Dict) -> Dict:
        scores = action_input.get("scores", {})
        return {
            "overall_trust_score": round(sum(scores.values()) / len(scores), 1) if scores else 0,
            "priority_actions": [
                "立即添加真实作者署名 + 可验证背景",
                "补充第一手证据（原创图、测试过程）",
                "完善隐私政策与纠错机制",
                "禁止任何伪造作者资料"
            ]
        }

    def think(self, context: Dict[str, Any], trajectory: List[Dict]) -> Dict[str, Any]:
        observations = context.get("observations", [])
        step = len([t for t in trajectory if t["type"] == "thought"]) + 1

        if step == 1:
            return {"thought": "先审计作者信任信号（真实署名与可验证性）。", "action": "check_author_signals", "action_input": {}, "decision": "continue"}
        elif step == 2:
            return {"thought": "检查第一手经验证据是否充分。", "action": "check_experience_evidence", "action_input": {}, "decision": "continue"}
        elif step == 3:
            return {"thought": "评估基础信任设施（政策、联系、HTTPS 等）。", "action": "check_trust_foundations", "action_input": {}, "decision": "continue"}
        elif step == 4:
            # 修复：原实现用 set 收集分数，分数相同的维度会被去重导致均分失真
            scores = {f"dim_{i}": obs.get("score", 0) for i, obs in enumerate(observations) if "score" in obs}
            return {"thought": "综合各维度分数，生成完整审计报告与优先行动。", "action": "generate_audit_report", "action_input": {"scores": scores}, "decision": "continue"}
        else:
            report = observations[-1] if observations else {}
            return {
                "thought": "E-E-A-T 深度审计完成。",
                "decision": "finish",
                "answer": {
                    "trust_is_central": True,
                    "overall_score": report.get("overall_trust_score", 0),
                    "priority_actions": report.get("priority_actions", []),
                    "recommendation": "优先修复作者真实性与第一手证据，Trust 是最大杠杆。"
                }
            }
