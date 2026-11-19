"""服务端渲染的页面。图表数据由 /api 提供。"""

from __future__ import annotations

from flask import Blueprint, render_template

from agents.scoring import THRESHOLD, dimension_rows
from agents.seo_workflow import SEOWorkflowReAct

from ..navigation import mobile_sections
from ..sample_data import (
    agent_roles,
    anchor_guidance,
    kanban_columns,
    psychology_insights,
)
from ..services import build_knowledge

pages_bp = Blueprint("pages", __name__)


@pages_bp.get("/")
@pages_bp.get("/dashboard")
def dashboard():
    return render_template(
        "dashboard.html",
        kanban=kanban_columns(),
        agents=agent_roles(),
        psychology=psychology_insights(),
        stages=SEOWorkflowReAct.STAGES,
        threshold=f"{THRESHOLD:.2f}",
    )


@pages_bp.get("/mobile")
def mobile():
    return render_template(
        "mobile_control.html",
        sections=mobile_sections(),
        stage_count=len(SEOWorkflowReAct.STAGES),
        dimension_count=len(dimension_rows()),
        threshold=f"{THRESHOLD:.2f}",
    )


@pages_bp.get("/backlink-competitor")
def backlink_competitor():
    return render_template("backlinks_competitors.html")


@pages_bp.get("/backlink-score-model")
def backlink_score_model():
    return render_template(
        "backlinks_scoring.html",
        dimensions=dimension_rows(),
        threshold=f"{THRESHOLD:.2f}",
    )


@pages_bp.get("/backlink-anchors")
def backlink_anchors():
    return render_template("backlinks_anchors.html", guidance=anchor_guidance())


@pages_bp.get("/backlink-tools")
def backlink_tools():
    return render_template("backlinks_tools.html", stages=SEOWorkflowReAct.STAGES)


@pages_bp.get("/knowledge")
def knowledge():
    return render_template("knowledge.html", knowledge=build_knowledge())


@pages_bp.get("/workflow")
def workflow():
    return render_template("workflow.html", stages=SEOWorkflowReAct.STAGES)
