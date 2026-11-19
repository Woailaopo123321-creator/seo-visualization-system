"""
集中配置：所有环境变量、默认路径与常量都在这里读取，其他模块只从这里取值。

环境变量（都可选）：
  HOST / PORT / FLASK_DEBUG     监听地址、端口、调试模式
  SEO_DATA_FILE                 任务数据 + Agent 统计（默认 data/learning_data.json）
  SEO_WORKFLOW_DB               LangGraph 检查点 + 运行列表（默认 data/workflow.sqlite）
  SEO_ADMIN_TOKEN               管理员令牌；未设置时仅本机可修改数据
  SEO_SECRET_KEY                会话签名密钥；未设置时每次启动随机生成
  SEO_LOGIN_MAX_ATTEMPTS        登录/令牌连续失败多少次后锁定（默认 5）
  SEO_LOGIN_LOCKOUT_SECONDS     锁定时长（秒，默认 900）
  SEO_OPTIONAL_GATES            默认开启的可选闸门，逗号分隔：fanout,tool_select（默认都关闭）
  SEO_LOG_LEVEL                 日志级别（默认 INFO）
"""

from __future__ import annotations

import logging
import os
import secrets
from typing import Any, Dict, List, Optional

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE_DIR, "data")
DEFAULT_DATA_FILE = os.path.join(DATA_DIR, "learning_data.json")
DEFAULT_WORKFLOW_DB = os.path.join(DATA_DIR, "workflow.sqlite")
DASHBOARD_CONFIG = os.path.join(DATA_DIR, "dashboard.json")

APP_NAME = "学习可视化系统"
REPORT_URL = ("https://cursor.com/canvas/store-782b3932-aad0-4e23-aa38-c09e650912ed/"
              "6be012cc-4244-45dd-b295-f8509d775430")
LOCAL_ADDRS = frozenset({"127.0.0.1", "::1"})
LOG_FORMAT = "%(asctime)s %(levelname)s [%(name)s] %(message)s"


def _int_env(name: str, default: int) -> int:
    try:
        return int(os.environ.get(name, default))
    except (TypeError, ValueError):
        return default


def _list_env(name: str) -> List[str]:
    return [x.strip() for x in os.environ.get(name, "").split(",") if x.strip()]


def load_config(overrides: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """读取环境变量得到 Flask 配置；overrides（测试用）优先。"""
    cfg: Dict[str, Any] = {
        "JSON_AS_ASCII": False,
        "DATA_FILE": os.environ.get("SEO_DATA_FILE", DEFAULT_DATA_FILE),
        "WORKFLOW_DB": os.environ.get("SEO_WORKFLOW_DB", DEFAULT_WORKFLOW_DB),
        "SEND_FILE_MAX_AGE_DEFAULT": 3600,  # 静态资源缓存 1 小时（URL 带版本号，更新后自动失效）
        "MAX_CONTENT_LENGTH": 64 * 1024,  # 拒绝超大请求体
        "ADMIN_TOKEN": os.environ.get("SEO_ADMIN_TOKEN") or None,
        "SECRET_KEY": os.environ.get("SEO_SECRET_KEY") or secrets.token_hex(32),
        "SESSION_COOKIE_HTTPONLY": True,
        "SESSION_COOKIE_SAMESITE": "Lax",
        "LOGIN_MAX_ATTEMPTS": _int_env("SEO_LOGIN_MAX_ATTEMPTS", 5),
        "LOGIN_LOCKOUT_SECONDS": _int_env("SEO_LOGIN_LOCKOUT_SECONDS", 900),
        "OPTIONAL_GATES": _list_env("SEO_OPTIONAL_GATES"),
    }
    if overrides:
        cfg.update(overrides)
        if "DATA_FILE" in overrides and "WORKFLOW_DB" not in overrides:
            # 测试等场景改了数据文件时，工作流库跟随放在同一目录，避免写到默认库
            cfg["WORKFLOW_DB"] = os.path.join(os.path.dirname(os.path.abspath(overrides["DATA_FILE"])),
                                              "workflow.sqlite")
    return cfg


def server_options() -> Dict[str, Any]:
    """python app.py 直接运行时的监听参数"""
    return {"host": os.environ.get("HOST", "127.0.0.1"), "port": _int_env("PORT", 5000),
            "debug": os.environ.get("FLASK_DEBUG", "0") == "1"}


def setup_logging() -> None:
    """全站统一日志格式；只配置一次（重复调用无副作用）"""
    root = logging.getLogger()
    if not root.handlers:
        logging.basicConfig(level=os.environ.get("SEO_LOG_LEVEL", "INFO").upper(), format=LOG_FORMAT)
