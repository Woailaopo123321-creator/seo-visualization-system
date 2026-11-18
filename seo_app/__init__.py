"""SEO 学习可视化系统的 Flask 应用工厂。"""

from __future__ import annotations

from pathlib import Path

from flask import Flask, jsonify, render_template, request

from .blueprints import api_bp, pages_bp
from .config import Config
from .navigation import NAV_ITEMS

ROOT = Path(__file__).resolve().parent.parent


def create_app(config: type[Config] | None = None) -> Flask:
    """创建应用。模板和静态文件放在项目根目录。"""

    app = Flask(
        __name__,
        template_folder=str(ROOT / "templates"),
        static_folder=str(ROOT / "static"),
    )
    app.config.from_object(config or Config)
    app.json.ensure_ascii = False

    app.register_blueprint(pages_bp)
    app.register_blueprint(api_bp, url_prefix="/api")

    @app.get("/health")
    def health():
        return jsonify({"status": "ok"})

    @app.errorhandler(404)
    def not_found(_error):
        if request.path.startswith("/api/"):
            return jsonify({"error": "未找到接口"}), 404
        return render_template(
            "error.html",
            title="页面不存在",
            message="没有这个页面。可以从概览进入外链分析、知识笔记和自动化流程。",
        ), 404

    @app.errorhandler(405)
    def method_not_allowed(_error):
        if request.path.startswith("/api/"):
            return jsonify({"error": "请求方法不被允许"}), 405
        return render_template(
            "error.html",
            title="方法不被允许",
            message="这个页面不支持当前请求方法。",
        ), 405

    @app.errorhandler(500)
    def server_error(_error):
        if request.path.startswith("/api/"):
            return jsonify({"error": "服务器内部错误"}), 500
        return render_template(
            "error.html",
            title="服务器内部错误",
            message="页面暂时打不开，请稍后再试。",
        ), 500

    @app.context_processor
    def inject_navigation() -> dict[str, object]:
        return {"nav_items": NAV_ITEMS, "active_path": request.path}

    return app
