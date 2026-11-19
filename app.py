"""
SEO 学习可视化系统 - Flask 主应用（create_app 工厂）

配置项（环境变量）统一在 config.py 读取与说明。
"""

from __future__ import annotations

import datetime as dt
import functools
import gzip
import hashlib
import hmac
import json
import logging
import os
import re
import time
from typing import Any, Dict, Optional
from urllib.parse import urlparse

from flask import Flask, abort, g, jsonify, redirect, render_template, request, send_from_directory, session
from werkzeug.exceptions import HTTPException

from agents.base import Coordinator
from agents.eeat_react import EEATAuditReAct
from agents.react_specialists import ProgressAnalyzerReAct
from agents.router import route_request
from agents.seo_react import SEOLearningPathReAct
from agents.scoring import ScoringError, dimension_rows, score_backlink
from agents.seo_workflow import SEOWorkflowReAct
from agents.specialists import MindMapAgent, ProgressAnalyzerAgent, RecommendationAgent
from config import APP_NAME, BASE_DIR, DASHBOARD_CONFIG, LOCAL_ADDRS, REPORT_URL, load_config, server_options, setup_logging
from pages import PAGES, endpoint_name, grouped_pages
from security import LoginLimiter
from store import PRIORITIES, STATUSES, TaskStore, ValidationError, task_metrics
from workflow import WorkflowEngine, WorkflowError
from workflow.spec import graph_spec
from workflow.tools import tool_kinds

# 旧中文页面路径 → 本系统对应页面（相结合时的兼容入口）
LEGACY_ALIASES = {
    "/knowledge": "/seo",
    "/workflow": "/workflow-runs",
    "/backlink-anchors": "/anchor-text",
}

setup_logging()
logger = logging.getLogger("seo.app")

THREAD_ID_RE = re.compile(r"^run-[0-9a-f]{10}$")
RECOMMEND_CONTEXTS = {"general", "complex", "planning"}
PSYCH_COLORS = ["#15803d", "#b45309", "#0f766e", "#1d4ed8"]  # 浅色主题：白底对比度 ≥ 4.5:1
PSYCH_COLORS_DARK = {"#15803d": "#4ade80", "#b45309": "#fbbf24", "#0f766e": "#5eead4", "#1d4ed8": "#93c5fd"}  # 深色主题
STATUS_COLORS = {"todo": "#2563eb", "in_progress": "#15803d", "review": "#0f766e", "done": "#475569"}  # 白字对比度 ≥ 4.5:1
PAGE_BY_PATH = {p[0]: p for p in PAGES}


def build_coordinator(store: Optional[TaskStore] = None) -> Coordinator:
    """分布式 AI 管理架构：注册全部 Agent；统计数据持久化到任务数据文件"""
    if store is not None:
        coordinator = Coordinator(initial_stats=store.get_meta("agent_stats"),
                                  on_stats_change=lambda stats: store.set_meta("agent_stats", stats))
    else:
        coordinator = Coordinator()
    for agent in (ProgressAnalyzerAgent(), MindMapAgent(), RecommendationAgent(), ProgressAnalyzerReAct(),
                  SEOLearningPathReAct(), EEATAuditReAct(), SEOWorkflowReAct()):
        coordinator.register(agent)
    return coordinator


def _asset_version() -> str:
    """静态资源版本号（文件修改时间），模板里拼到 URL 上，更新 CSS/JS 后浏览器不会用旧缓存"""
    mtimes = [os.path.getmtime(os.path.join(BASE_DIR, "static", f)) for f in ("app.css", "common.js")]
    return str(int(max(mtimes)))


_COMPRESSIBLE = ("text/", "application/json", "application/javascript", "image/svg+xml")


def _maybe_gzip(response):
    """文本类响应 gzip 压缩（≥ 1 KB 且浏览器支持时），无需额外依赖"""
    if (response.status_code != 200 or response.is_streamed and not response.direct_passthrough
            or "Content-Encoding" in response.headers
            or "gzip" not in request.headers.get("Accept-Encoding", "").lower()
            or not response.mimetype or not response.mimetype.startswith(_COMPRESSIBLE)):
        return response
    response.direct_passthrough = False
    data = response.get_data()
    if len(data) < 1024:
        return response
    response.set_data(gzip.compress(data, compresslevel=6))
    response.headers["Content-Encoding"] = "gzip"
    response.headers["Content-Length"] = str(len(response.get_data()))
    vary = response.headers.get("Vary")
    response.headers["Vary"] = f"{vary}, Accept-Encoding" if vary else "Accept-Encoding"
    return response


def _bad_request(message: str):
    return jsonify({"error": message, "status": "invalid"}), 400


def _json_body() -> Dict[str, Any]:
    """请求体 JSON 对象；空请求体视为 {}"""
    body = request.get_json(silent=True)
    if body is None:
        return {}
    if not isinstance(body, dict):
        raise ValidationError("请求体必须是 JSON 对象")
    return body


def _text_field(body: Dict[str, Any], key: str, default: str, max_len: int, required: bool = False) -> str:
    """取字符串字段：去首尾空白、长度校验，空值回退为默认值"""
    value = body.get(key, default)
    if value is None:
        value = default
    if not isinstance(value, str):
        raise ValidationError(f"{key} 必须是字符串")
    value = value.strip()
    if required and not value:
        raise ValidationError(f"{key} 不能为空")
    if len(value) > max_len:
        raise ValidationError(f"{key} 不能超过 {max_len} 个字符")
    return value or default


def _psych_level(score: float, inverse: bool = False) -> str:
    s = 100 - score if inverse else score
    if s >= 70:
        return "良好"
    if s >= 60:
        return "较强"
    if s >= 40:
        return "中等"
    return "偏低"


def create_app(config: Optional[Dict[str, Any]] = None) -> Flask:
    """创建应用；config 用于测试覆盖（例如 DATA_FILE / ADMIN_TOKEN）"""
    app = Flask(__name__, static_folder="static", static_url_path="/static")
    app.config.update(load_config(config))
    app.json.ensure_ascii = False

    store = TaskStore(app.config["DATA_FILE"])
    coordinator = build_coordinator(store)
    app.extensions["task_store"] = store
    app.extensions["coordinator"] = coordinator
    workflow = WorkflowEngine(app.config["WORKFLOW_DB"], app.config["OPTIONAL_GATES"])
    app.extensions["workflow"] = workflow
    limiter = LoginLimiter(app.config["LOGIN_MAX_ATTEMPTS"], app.config["LOGIN_LOCKOUT_SECONDS"])
    app.extensions["login_limiter"] = limiter
    asset_version = _asset_version()
    started_at = time.time()

    # ---------- 请求钩子 ----------
    @app.before_request
    def start_timer():
        g.start = time.perf_counter()

    @app.after_request
    def add_headers(response):
        if hasattr(g, "start"):
            response.headers["X-Response-Time"] = f"{(time.perf_counter() - g.start) * 1000:.1f}ms"
        response.headers.setdefault("X-Content-Type-Options", "nosniff")
        response.headers.setdefault("X-Frame-Options", "SAMEORIGIN")
        response.headers.setdefault("Referrer-Policy", "same-origin")
        if request.path.startswith("/static/") and request.args.get("v"):
            # URL 带版本号的静态资源：内容变化 URL 就变，可以放心长期缓存
            response.headers["Cache-Control"] = "public, max-age=31536000, immutable"
        return _maybe_gzip(response)

    # ---------- 权限：保护修改数据的接口 ----------
    def _token_fingerprint(token):
        return hashlib.sha256(("seo-admin:" + token).encode()).hexdigest()[:32]

    def auth_state():
        token = app.config.get("ADMIN_TOKEN")
        logged_in = bool(token) and session.get("admin") == _token_fingerprint(token)
        return {"token_required": bool(token), "logged_in": logged_in,
                "is_local": request.remote_addr in LOCAL_ADDRS}

    def check_write_permission():
        # 1) 拒绝跨站请求（防止恶意网页借用浏览器向本服务发起修改）
        origin = request.headers.get("Origin")
        if origin and urlparse(origin).netloc != request.host:
            abort(403, description="跨站请求被拒绝")
        token = app.config.get("ADMIN_TOKEN")
        if token:
            # 2) 已配置令牌：请求头或登录会话二选一
            provided = request.headers.get("X-Admin-Token", "")
            auth_header = request.headers.get("Authorization", "")
            if auth_header.startswith("Bearer "):
                provided = auth_header[7:]
            if provided:
                # 请求头令牌与登录共用失败计数：防止脚本暴力猜测
                _check_lockout()
                if hmac.compare_digest(provided.encode(), token.encode()):
                    limiter.success(_client_key())
                    return
                limiter.fail(_client_key())
                abort(401, description="管理员令牌不正确")
            if auth_state()["logged_in"]:
                return
            abort(401, description="需要管理员令牌：请登录，或在请求头携带 Authorization: Bearer <SEO_ADMIN_TOKEN>")
        # 3) 未配置令牌：仅允许本机修改
        if request.remote_addr not in LOCAL_ADDRS:
            abort(403, description="未设置 SEO_ADMIN_TOKEN 时只允许本机修改数据")

    def _client_key() -> str:
        return request.remote_addr or "unknown"

    def _check_lockout() -> None:
        wait = limiter.retry_after(_client_key())
        if wait:
            minutes = max(1, round(wait / 60))
            resp = jsonify({"error": "Too Many Requests", "status_code": 429, "retry_after": wait,
                            "detail": f"认证失败次数过多，已锁定，请约 {minutes} 分钟后再试"})
            resp.status_code = 429
            resp.headers["Retry-After"] = str(wait)
            abort(resp)

    def require_admin(view):
        @functools.wraps(view)
        def wrapper(*args, **kwargs):
            check_write_permission()
            return view(*args, **kwargs)
        return wrapper

    @app.context_processor
    def inject_nav():
        page = PAGE_BY_PATH.get(request.path)
        return {"nav_groups": grouped_pages(), "current_path": request.path, "page_count": len(PAGES),
                "current_group": page[3] if page else None, "page_title": page[2] if page else "学习可视化系统",
                "auth": auth_state(), "wf_waiting": workflow.counts()["waiting_approval"],
                "report_url": REPORT_URL, "app_name": APP_NAME, "asset_version": asset_version,
                "max_attempts": app.config["LOGIN_MAX_ATTEMPTS"],
                "lockout_minutes": max(1, round(app.config["LOGIN_LOCKOUT_SECONDS"] / 60)),
                "page_desc": f"{APP_NAME} · {page[3]} · {page[2]}" if page else f"{APP_NAME}：SEO 学习、可视化与多智能体工作流"}

    # ---------- 错误处理：API 返回 JSON，页面返回友好 HTML ----------
    def _wants_json():
        return request.path.startswith("/api/") or request.path == "/health"

    @app.errorhandler(HTTPException)
    def handle_http_error(e):
        if _wants_json():
            return jsonify({"error": e.name, "detail": e.description, "status_code": e.code}), e.code
        return render_template("error.html", code=e.code, name=e.name, description=e.description), e.code

    @app.errorhandler(Exception)
    def handle_unexpected(e):
        logger.exception("Internal error on %s", request.path)
        if _wants_json():
            return jsonify({"error": "internal error", "status_code": 500}), 500
        return render_template("error.html", code=500, name="服务器内部错误",
                               description="页面暂时无法显示，请稍后重试。"), 500

    @app.errorhandler(WorkflowError)
    def handle_workflow_error(e):
        return jsonify({"error": str(e), "detail": str(e), "status_code": e.status_code}), e.status_code

    @app.errorhandler(ValidationError)
    def handle_validation(e):
        return _bad_request(str(e))

    @app.errorhandler(ScoringError)
    def handle_scoring(e):
        return _bad_request(str(e))

    # ---------- 页面路由（由 pages.PAGES 统一注册） ----------
    def make_view(template):
        def view():
            return render_template(template)
        return view

    for path, template, _title, _group in PAGES:
        if template in ("dashboard.html", "mobile_control.html", "workflow_runs.html"):
            continue
        app.add_url_rule(path, endpoint_name(template), make_view(template))

    for old_path, new_path in LEGACY_ALIASES.items():
        def _alias(target=new_path):
            return redirect(target, code=302)

        app.add_url_rule(old_path, f"alias_{old_path.strip('/').replace('-', '_')}", _alias)

    def dashboard_context():
        try:
            with open(DASHBOARD_CONFIG, "r", encoding="utf-8") as f:
                cfg = json.load(f)
        except (OSError, json.JSONDecodeError) as e:
            logger.error("读取仪表盘配置失败: %s", e)
            cfg = {"workflow": {"stages": [], "current_stage": 0}, "agents": [], "psych": [], "tip": ""}

        tasks = store.list()
        metrics = task_metrics(tasks)
        agent_stats = coordinator.snapshot()
        today = dt.date.today()
        week_start = today - dt.timedelta(days=today.weekday())
        columns = []
        for key, label in STATUSES.items():
            items = [t for t in tasks if t.get("status") == key]
            items.sort(key=lambda t: ["high", "medium", "low"].index(t.get("priority", "medium"))
                       if t.get("priority", "medium") in PRIORITIES else 1)
            columns.append({"key": key, "label": label, "color": STATUS_COLORS[key],
                            "count": len(items), "items": items[:3], "more": max(len(items) - 3, 0)})
        psych = []
        for i, p in enumerate(cfg.get("psych", [])):
            color = p.get("color", PSYCH_COLORS[i % len(PSYCH_COLORS)])
            psych.append({**p, "color": color, "color_dark": PSYCH_COLORS_DARK.get(color.lower(), color),
                          "level": _psych_level(p.get("score", 0), p.get("inverse", False))})
        focus = round(sum(p["score"] for p in psych if not p.get("inverse")) /
                      max(len([p for p in psych if not p.get("inverse")]), 1)) if psych else 0
        stages = cfg.get("workflow", {}).get("stages", [])
        current = cfg.get("workflow", {}).get("current_stage", 0)
        return {
            "date_range": f"{week_start:%Y-%m-%d} ~ {week_start + dt.timedelta(days=6):%Y-%m-%d}",
            "stats": {
                "tasks_total": metrics["total"],
                "tasks_done": metrics["done"],
                "completion_rate": metrics["completion_rate"],
                "avg_progress": metrics["avg_progress"],
                "pages": len(PAGES),
                "page_groups": len(grouped_pages()),
                "agent_runs": agent_stats["success"],
                "agent_count": len(coordinator.agents),
                "focus": focus,
            },
            "columns": columns,
            "workflow": {"stages": stages, "current_stage": current,
                         "percent": round(current / len(stages) * 100) if stages else 0},
            "agents": cfg.get("agents", []),
            "wf": workflow.counts(),
            "psych": psych,
            "tip": cfg.get("tip", ""),
        }

    @app.route("/dashboard")
    def page_dashboard():
        return render_template("dashboard.html", d=dashboard_context(), statuses=STATUSES)

    @app.route("/mobile")
    def page_mobile_control():
        tasks = store.list()
        metrics = task_metrics(tasks)
        stats = coordinator.snapshot()
        m = {
            "tasks_total": metrics["total"], "tasks_done": metrics["done"], "in_progress": metrics["in_progress"],
            "avg_progress": metrics["avg_progress"], "agent_runs": stats["success"],
            "agent_count": len(coordinator.agents),
            "workflow_stages": len(SEOWorkflowReAct.TOOL_SEQUENCE),
            "backlink_threshold": SEOWorkflowReAct.BACKLINK_THRESHOLD,
            "wf": workflow.counts(),
        }
        return render_template("mobile_control.html", m=m)

    @app.route("/workflow-runs")
    def page_workflow_runs():
        return render_template("workflow_runs.html", spec=graph_spec(),
                               default_optional=workflow.default_optional_gates)

    # ---------- LangGraph 工作流 API ----------
    def _thread(thread_id):
        if not THREAD_ID_RE.match(thread_id):
            abort(404, description="运行不存在")
        return thread_id

    @app.route("/api/workflow/graph")
    def api_workflow_graph():
        return jsonify({**graph_spec(), "tools": tool_kinds(), "mermaid": workflow.mermaid()})

    @app.route("/api/workflow/runs", methods=["GET"])
    def api_workflow_runs():
        return jsonify({"runs": workflow.list_runs(), "counts": workflow.counts()})

    @app.route("/api/workflow/runs", methods=["POST"])
    @require_admin
    def api_workflow_start():
        body = _json_body()
        site = _text_field(body, "site", "example.com", 200)
        topic = _text_field(body, "topic", "SEO 工作流", 100)
        return jsonify(workflow.start(site, topic, body.get("optional_gates"))), 201

    @app.route("/api/workflow/runs/<thread_id>", methods=["GET"])
    def api_workflow_view(thread_id):
        return jsonify(workflow.view(_thread(thread_id)))

    @app.route("/api/workflow/runs/<thread_id>/resume", methods=["POST"])
    @require_admin
    def api_workflow_resume(thread_id):
        body = request.get_json(silent=True)
        if not isinstance(body, dict):
            raise ValidationError("请求体必须是 JSON 对象，例如 {\"action\": \"approve\"}")
        return jsonify(workflow.resume(_thread(thread_id), body))

    @app.route("/api/workflow/runs/<thread_id>", methods=["DELETE"])
    @require_admin
    def api_workflow_delete(thread_id):
        if not workflow.delete(_thread(thread_id)):
            abort(404, description="运行不存在")
        return jsonify({"status": "deleted", "thread_id": thread_id, "counts": workflow.counts()})

    @app.route("/api/workflow/reset", methods=["POST"])
    @require_admin
    def api_workflow_reset():
        if _json_body().get("confirm") is not True:
            raise ValidationError("清空全部运行需要确认：请求体 {\"confirm\": true}")
        return jsonify({"status": "reset", "deleted": workflow.reset(), "counts": workflow.counts()})

    # ---------- Supervisor 规则路由 ----------
    @app.route("/api/ai/route", methods=["POST"])
    def ai_route():
        body = _json_body()
        text = _text_field(body, "request", "", 300, required=True)
        target, hit = route_request(text)
        route = {"target": target, "matched": hit, "mode": "rule",
                 "note": "规则路由（无需 LLM）；接入模型后可升级为语义路由"}
        if target == "workflow":
            # 启动工作流属于写操作，路由只给出入口，不自动执行
            return jsonify({"route": route, "status": "success",
                            "result": {"message": "该请求属于 SEO 工作流，请在审批台启动一次可暂停审批的运行。",
                                       "link": "/workflow-runs"}})
        task = {"tasks": store.list()} if target == "progress_analyzer_react" else {"topic": text[:50]}
        if target == "eeat_audit_react":
            task = {"content_sample": text}
        if target == "recommender":
            task = {"context": "general"}
        result = coordinator.dispatch(target, task)
        return jsonify({"route": route, **result}), (200 if result.get("status") == "success" else 500)

    # ---------- 登录 / 退出 ----------
    def _safe_next(url):
        return url if isinstance(url, str) and url.startswith("/") and not url.startswith("//") else "/dashboard"

    @app.route("/login", methods=["GET", "POST"])
    def login():
        token = app.config.get("ADMIN_TOKEN")
        next_url = _safe_next(request.values.get("next"))
        key = _client_key()
        if request.method == "POST":
            wait = limiter.retry_after(key)
            if wait:
                error = f"失败次数过多，已锁定，请约 {max(1, round(wait / 60))} 分钟后再试"
                resp = app.make_response((render_template("login.html", error=error, next_url=next_url,
                                                          locked=True), 429))
                resp.headers["Retry-After"] = str(wait)
                return resp
            provided = request.form.get("token", "")
            if token and hmac.compare_digest(provided.encode(), token.encode()):
                limiter.success(key)
                session.clear()
                session["admin"] = _token_fingerprint(token)
                logger.info("管理员登录成功：%s", key)
                return redirect(next_url)
            if not token:
                return render_template("login.html", error="服务器未配置 SEO_ADMIN_TOKEN，无需登录",
                                       next_url=next_url), 400
            locked_for = limiter.fail(key)
            if locked_for:
                error = f"失败次数过多，已锁定 {max(1, round(locked_for / 60))} 分钟"
                return render_template("login.html", error=error, next_url=next_url, locked=True), 429
            error = f"令牌不正确（还可尝试 {limiter.remaining(key)} 次）"
            return render_template("login.html", error=error, next_url=next_url), 401
        return render_template("login.html", error=None, next_url=next_url)

    @app.route("/logout")
    def logout():
        session.clear()
        return redirect("/dashboard")

    @app.route("/favicon.ico")
    def favicon():
        return send_from_directory(app.static_folder, "favicon.svg", mimetype="image/svg+xml")

    # ---------- 系统 API ----------
    @app.route("/health")
    def health():
        return jsonify({
            "status": "ok",
            "agents": list(coordinator.agents.keys()),
            "agent_count": len(coordinator.agents),
            "cache_size": coordinator.cache_size(),
            "agent_stats": coordinator.snapshot(),
            "uptime_seconds": round(time.time() - started_at, 1),
            "pages": len(PAGES),
        })

    @app.route("/api/cache/clear", methods=["POST"])
    @require_admin
    def clear_cache():
        coordinator.clear_cache()
        return jsonify({"status": "cache cleared"})

    @app.route("/api/pages")
    def api_pages():
        return jsonify(grouped_pages())

    @app.route("/api/dashboard")
    def api_dashboard():
        return jsonify(dashboard_context())

    # ---------- 任务 API ----------
    @app.route("/api/tasks", methods=["GET"])
    def get_tasks():
        return jsonify(store.list())

    @app.route("/api/tasks/stats", methods=["GET"])
    def get_task_stats():
        return jsonify(task_metrics(store.list()))

    @app.route("/api/tasks", methods=["POST"])
    @require_admin
    def add_task():
        task = store.create(_json_body())
        return jsonify(task), 201

    @app.route("/api/tasks/<int:task_id>", methods=["PUT", "PATCH"])
    @require_admin
    def update_task(task_id):
        task = store.update(task_id, _json_body())
        if task is None:
            abort(404, description=f"任务 {task_id} 不存在")
        return jsonify(task)

    @app.route("/api/tasks/<int:task_id>", methods=["DELETE"])
    @require_admin
    def delete_task(task_id):
        if not store.delete(task_id):
            abort(404, description=f"任务 {task_id} 不存在")
        return jsonify({"status": "deleted", "id": task_id})

    # ---------- AI API ----------
    def run_agent(agent_name, task):
        result = coordinator.dispatch(agent_name, task)
        status = result.get("status")
        code = 200 if status == "success" else (504 if status == "timeout" else 500)
        return jsonify(result), code

    @app.route("/api/ai/analyze", methods=["POST"])
    def ai_analyze():
        return run_agent("progress_analyzer", {"tasks": store.list()})

    @app.route("/api/ai/analyze-react", methods=["POST"])
    @app.route("/api/ai/react", methods=["POST"])  # ai_react.html 使用的路径（原先缺失，导致 404）
    def ai_analyze_react():
        return run_agent("progress_analyzer_react", {"tasks": store.list()})

    @app.route("/api/ai/seo-path", methods=["POST"])
    def ai_seo_path():
        body = _json_body()
        topic = _text_field(body, "topic", "SEO学习路径", 100)
        return run_agent("seo_learning_path_react", {"topic": topic})

    @app.route("/api/ai/eeat-audit", methods=["POST"])
    def ai_eeat_audit():
        body = _json_body()
        sample = _text_field(body, "content_sample", "待审计内容", 5000)
        return run_agent("eeat_audit_react", {"content_sample": sample})

    @app.route("/api/ai/seo-workflow", methods=["POST"])
    def ai_seo_workflow():
        body = _json_body()
        site = _text_field(body, "site", "example.com", 200)
        topic = _text_field(body, "topic", "SEO 工作流", 100)
        resp, code = run_agent("seo_workflow_react", {"site": site, "topic": topic})
        data = resp.get_json()
        data["mode"] = "legacy"
        data["note"] = "旧版一次跑完模式（闸门只做标记，不暂停）。可暂停审批的 LangGraph 版本：POST /api/workflow/runs，页面 /workflow-runs"
        return jsonify(data), code

    @app.route("/api/ai/mindmap", methods=["POST"])
    def ai_mindmap():
        body = _json_body()
        topic = _text_field(body, "topic", "", 50, required=True)
        return run_agent("mindmap_generator", {"topic": topic})

    @app.route("/api/ai/recommend", methods=["POST"])
    def ai_recommend():
        body = _json_body()
        # 兼容旧前端发送的 {"type": ...}
        context = body.get("context", body.get("type", "general"))
        if context not in RECOMMEND_CONTEXTS:
            raise ValidationError(f"context 必须是 {sorted(RECOMMEND_CONTEXTS)} 之一")
        return run_agent("recommender", {"context": context})

    @app.route("/api/backlinks/scoring", methods=["GET"])
    def api_backlink_scoring():
        return jsonify({
            "threshold": 0.70,
            "priority": "相关性 > 编辑性 > 流量",
            "weights": dimension_rows(),
            "hitl_note": "所有外展都要人工确认。达到 0.70 只表示进入候选。",
        })

    @app.route("/api/backlinks/score", methods=["POST"])
    def api_backlink_score():
        body = _json_body()
        features = body.get("features", body)
        if not isinstance(features, dict):
            raise ValidationError("特征必须是字典")
        result = score_backlink(features).to_dict()
        result["feature_source"] = "自定义特征"
        return jsonify(result)

    return app


app = create_app()

if __name__ == "__main__":
    app.run(**server_options())
