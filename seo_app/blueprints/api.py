"""图表和交互使用的 JSON 接口。"""

from __future__ import annotations

from flask import Blueprint, jsonify, request

from agents.scoring import ScoringError

from ..services import (
    build_anchors,
    build_competitors,
    build_dashboard,
    build_knowledge,
    build_scoring,
    build_tools,
    build_workflow,
    score_features,
)

api_bp = Blueprint("api", __name__)


@api_bp.get("/dashboard")
def dashboard():
    return jsonify(build_dashboard())


@api_bp.get("/backlinks/competitors")
def competitors():
    return jsonify(build_competitors())


@api_bp.get("/backlinks/scoring")
def scoring():
    return jsonify(build_scoring())


@api_bp.post("/backlinks/score")
def score():
    payload = request.get_json(silent=True)
    if not isinstance(payload, dict):
        return jsonify({"error": "请提交 JSON 对象"}), 400
    features = payload.get("features", payload)
    if not isinstance(features, dict):
        return jsonify({"error": "特征必须是字典"}), 400
    try:
        return jsonify(score_features(features))
    except ScoringError as exc:
        return jsonify({"error": str(exc)}), 400


@api_bp.get("/backlinks/anchors")
def anchors():
    return jsonify(build_anchors())


@api_bp.get("/backlinks/tools")
def tools():
    return jsonify(build_tools())


@api_bp.get("/knowledge")
def knowledge():
    return jsonify(build_knowledge())


@api_bp.get("/workflow")
def workflow():
    return jsonify(build_workflow())
