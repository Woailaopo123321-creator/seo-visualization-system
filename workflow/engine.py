"""
工作流运行管理：每次运行一个 thread_id，状态由 SqliteSaver 持久化（重启后可继续审批）。
"""

import contextlib
import logging
import os
import sqlite3
import threading
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, Iterator, List, Optional

from langgraph.checkpoint.sqlite import SqliteSaver
from langgraph.types import Command

from .graph import build_graph
from .spec import BACKLINK_TOOLS, GATE_ORDER, GATES, OPTIONAL_GATES, REQUIRED_GATES, STAGE_IDS, STAGE_TITLES, graph_spec

ACTIONS = {"approve", "edit", "reject"}
logger = logging.getLogger("seo.workflow")


class WorkflowError(ValueError):
    """业务错误：带 HTTP 状态码（400 参数错误 / 404 不存在 / 409 状态冲突）"""

    def __init__(self, message: str, status_code: int = 400):
        super().__init__(message)
        self.status_code = status_code


def _now() -> str:
    """UTC ISO 时间；界面统一转换为本地时间显示"""
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _str_list(value: Any, name: str, max_items: int, max_len: int) -> List[str]:
    """校验“非空文本列表”，返回去掉首尾空白的新列表"""
    if not isinstance(value, list) or not value or len(value) > max_items:
        raise WorkflowError(f"{name} 必须是 1-{max_items} 项的列表")
    out = []
    for v in value:
        if not isinstance(v, str) or not v.strip() or len(v.strip()) > max_len:
            raise WorkflowError(f"{name} 每项必须是不超过 {max_len} 字的非空文本")
        out.append(v.strip())
    return out


class WorkflowEngine:
    """LangGraph 工作流的运行管理器。

    并发设计（不再使用全局锁）：
    - 数据库开启 WAL：读写互不阻塞，多个线程可同时读取运行列表 / 状态
    - 运行列表表（workflow_runs）每个线程一个独立连接（threading.local）
    - LangGraph 的 SqliteSaver 用自己的连接，内部自带锁
    - 只对“同一个运行”的启动 / 审批加锁（防止重复提交同一个闸门），不同运行互不影响
    """

    def __init__(self, db_path: str, default_optional_gates: Optional[List[str]] = None):
        os.makedirs(os.path.dirname(os.path.abspath(db_path)), exist_ok=True)
        self.db_path = db_path
        self.default_optional_gates = [g for g in (default_optional_gates or []) if g in OPTIONAL_GATES]
        self._local = threading.local()
        self._run_locks: Dict[str, threading.Lock] = {}
        self._run_locks_guard = threading.Lock()
        self._all_conns: List[sqlite3.Connection] = []
        self._conns_guard = threading.Lock()
        self._saver_conn = self._connect()
        self.saver = SqliteSaver(self._saver_conn)
        self.saver.setup()
        self.graph = build_graph().compile(checkpointer=self.saver)
        with self._db() as conn:
            conn.execute("""CREATE TABLE IF NOT EXISTS workflow_runs (
                thread_id TEXT PRIMARY KEY, site TEXT, topic TEXT, status TEXT, current_stage TEXT,
                pending_gate TEXT, created_at TEXT, updated_at TEXT)""")
        logger.info("工作流引擎就绪：%s（WAL，默认可选闸门：%s）", db_path,
                    ",".join(self.default_optional_gates) or "无")

    # ---------- 连接管理 ----------
    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path, check_same_thread=False, timeout=10)
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA synchronous=NORMAL")
        conn.execute("PRAGMA busy_timeout=10000")
        with self._conns_guard:
            self._all_conns.append(conn)
        return conn

    @contextlib.contextmanager
    def _db(self) -> Iterator[sqlite3.Connection]:
        """当前线程专用连接；with 块结束自动提交（异常时回滚）"""
        conn = getattr(self._local, "conn", None)
        if conn is None:
            conn = self._local.conn = self._connect()
        with conn:
            yield conn

    def _run_lock(self, thread_id: str) -> threading.Lock:
        with self._run_locks_guard:
            return self._run_locks.setdefault(thread_id, threading.Lock())

    @staticmethod
    def _config(thread_id: str) -> Dict[str, Any]:
        return {"configurable": {"thread_id": thread_id}}

    # ---------- 查询 ----------
    def view(self, thread_id: str) -> Dict[str, Any]:
        """运行的完整视图：状态、各阶段 / 闸门进度、待审批内容、审批记录、轨迹与产出"""
        snap = self.graph.get_state(self._config(thread_id))
        if not snap or not snap.values:
            raise WorkflowError(f"运行 {thread_id} 不存在", 404)
        v = snap.values
        interrupts = [i.value for i in (snap.interrupts or ())]
        pending = interrupts[0] if interrupts else None
        art = v.get("artifacts", {})
        nxt = list(snap.next or ())
        if pending:
            status = "waiting_approval"
        elif not nxt:
            status = v.get("status") if v.get("status") in ("completed", "rejected") else "completed"
        else:
            status = "running"
        stages = {}
        for sid in STAGE_IDS:
            stages[sid] = "done" if sid in art else ("current" if sid in nxt else "pending")
        latest = {}
        for a in v.get("approvals", []):
            latest[a["gate"]] = a["action"]
        enabled = v.get("enabled_gates") or REQUIRED_GATES
        gates = {}
        for gid in GATE_ORDER:
            if GATES[gid]["optional"] and gid not in enabled and gid not in latest:
                gates[gid] = "off"
            elif pending and pending.get("gate") == gid:
                gates[gid] = "waiting"
            elif gid in latest:
                gates[gid] = "rejected" if latest[gid] == "reject" else "approved"
            else:
                gates[gid] = "pending"
        if status == "rejected":
            for sid in STAGE_IDS:
                if stages[sid] == "pending":
                    stages[sid] = "skipped"
        return {
            "thread_id": thread_id, "site": v.get("site"), "topic": v.get("topic"), "status": status,
            "current_stage": v.get("current_stage"), "next": nxt, "pending_approval": pending,
            "stages": stages, "gates": gates, "artifacts": art, "scores": v.get("scores", {}),
            "approvals": v.get("approvals", []), "trajectory": v.get("trajectory", []),
            "errors": v.get("errors", []), "summary": v.get("summary"),
            "progress": {"done": sum(1 for s in stages.values() if s == "done"), "total": len(STAGE_IDS)},
            "brief_revision": v.get("brief_revision", 0),
            "enabled_gates": [g for g in GATE_ORDER if g in enabled or not GATES[g]["optional"]],
        }

    def _sync_row(self, view: Dict[str, Any]) -> None:
        pending = (view.get("pending_approval") or {}).get("gate")
        with self._db() as conn:
            conn.execute("UPDATE workflow_runs SET status=?, current_stage=?, pending_gate=?, updated_at=? "
                              "WHERE thread_id=?",
                         (view["status"], view.get("current_stage"), pending, _now(), view["thread_id"]))

    def list_runs(self, limit: int = 50) -> List[Dict[str, Any]]:
        """最近的运行（新的在前），附带当前阶段 / 待审批闸门的中文名"""
        with self._db() as conn:
            cur = conn.execute("SELECT thread_id, site, topic, status, current_stage, pending_gate, created_at, "
                                    "updated_at FROM workflow_runs ORDER BY created_at DESC, rowid DESC LIMIT ?",
                                    (limit,))
            cols = [c[0] for c in cur.description]
            rows = [dict(zip(cols, r)) for r in cur.fetchall()]
        for r in rows:
            r["current_stage_title"] = STAGE_TITLES.get(r["current_stage"], r["current_stage"])
            r["pending_gate_title"] = GATES.get(r["pending_gate"], {}).get("title") if r["pending_gate"] else None
        return rows

    def counts(self) -> Dict[str, int]:
        """各状态的运行数量（仪表盘、侧栏徽标用）"""
        with self._db() as conn:
            rows = conn.execute("SELECT status, COUNT(*) FROM workflow_runs GROUP BY status").fetchall()
        c = {k: v for k, v in rows}
        return {"total": sum(c.values()), "waiting_approval": c.get("waiting_approval", 0),
                "completed": c.get("completed", 0), "rejected": c.get("rejected", 0)}

    # ---------- 运行 ----------
    def start(self, site: str, topic: str, optional_gates: Optional[List[str]] = None) -> Dict[str, Any]:
        """启动一次运行：执行到第一个闸门暂停后返回视图。optional_gates=None 时用默认配置"""
        chosen = self.default_optional_gates if optional_gates is None else optional_gates
        if not isinstance(chosen, list) or any(g not in OPTIONAL_GATES for g in chosen):
            raise WorkflowError(f"optional_gates 只能包含 {OPTIONAL_GATES}")
        enabled = [g for g in GATE_ORDER if g in REQUIRED_GATES or g in chosen]
        thread_id = "run-" + uuid.uuid4().hex[:10]
        now = _now()
        with self._db() as conn:
            conn.execute("INSERT INTO workflow_runs VALUES (?,?,?,?,?,?,?,?)",
                         (thread_id, site, topic, "running", None, None, now, now))
        with self._run_lock(thread_id):
            self.graph.invoke({"site": site, "topic": topic, "status": "running", "brief_revision": 0,
                               "enabled_gates": enabled, "artifacts": {}, "scores": {}, "trajectory": [],
                               "approvals": [], "errors": []},
                              self._config(thread_id))
            view = self.view(thread_id)
            self._sync_row(view)
        logger.info("启动工作流 %s（%s / %s，闸门：%s）", thread_id, site, topic, ",".join(enabled))
        return view

    def validate_decision(self, gate_id: str, decision: Any) -> Dict[str, Any]:
        """校验审批请求，返回清洗后的 {action, comment, edits, by}；不合法时抛 WorkflowError(400)"""
        if not isinstance(decision, dict):
            raise WorkflowError("请求体必须是 JSON 对象")
        action = decision.get("action")
        if action not in ACTIONS:
            raise WorkflowError(f"action 必须是 {sorted(ACTIONS)} 之一")
        comment = decision.get("comment") or ""
        if not isinstance(comment, str) or len(comment) > 500:
            raise WorkflowError("comment 必须是不超过 500 字的文本")
        edits = decision.get("edits") or {}
        if not isinstance(edits, dict):
            raise WorkflowError("edits 必须是对象")
        clean = {}
        if action == "edit":
            if gate_id == "keywords":
                clean["priority_keywords"] = _str_list(edits.get("priority_keywords"), "priority_keywords", 10, 50)
            elif gate_id == "brief":
                if "title" in edits:
                    t = edits["title"]
                    if not isinstance(t, str) or not t.strip() or len(t) > 100:
                        raise WorkflowError("title 必须是不超过 100 字的非空文本")
                    clean["title"] = t.strip()
                if "outline" in edits:
                    clean["outline"] = _str_list(edits["outline"], "outline", 15, 100)
                if not clean:
                    raise WorkflowError("修改简报时至少提供 title 或 outline")
            elif gate_id == "outreach":
                targets = edits.get("approved_targets")
                if not isinstance(targets, list) or not all(isinstance(t, str) for t in targets):
                    raise WorkflowError("approved_targets 必须是域名列表")
                clean["approved_targets"] = targets
            elif gate_id == "fanout":
                clean["subquestions"] = _str_list(edits.get("subquestions"), "subquestions", 10, 60)
            elif gate_id == "tool_select":
                tool = edits.get("tool")
                if tool not in BACKLINK_TOOLS:
                    raise WorkflowError(f"tool 必须是 {BACKLINK_TOOLS} 之一")
                clean["tool"] = tool
            else:
                raise WorkflowError("该闸门没有可修改的内容，请使用 approve 或 reject")
        return {"action": action, "comment": comment.strip(), "edits": clean, "by": decision.get("by", "admin")}

    def resume(self, thread_id: str, decision: Any) -> Dict[str, Any]:
        """提交当前闸门的审批并继续执行到下一个闸门或结束"""
        with self._run_lock(thread_id):
            view = self.view(thread_id)
            pending = view.get("pending_approval")
            if not pending:
                raise WorkflowError("该运行当前没有待审批的闸门", 409)
            gate_id = pending["gate"]
            expected = decision.get("gate") if isinstance(decision, dict) else None
            if expected and expected != gate_id:
                raise WorkflowError(f"当前待审批的是 {gate_id}，不是 {expected}", 409)
            clean = self.validate_decision(gate_id, decision)
            if gate_id == "outreach" and clean["edits"].get("approved_targets") is not None:
                known = {t["domain"] for t in pending["proposal"].get("targets", [])}
                unknown = [t for t in clean["edits"]["approved_targets"] if t not in known]
                if unknown:
                    raise WorkflowError(f"未知的外链目标：{unknown}")
            self.graph.invoke(Command(resume=clean), self._config(thread_id))
            view = self.view(thread_id)
            self._sync_row(view)
        logger.info("工作流 %s 闸门 %s：%s → %s", thread_id, gate_id, clean["action"], view["status"])
        return view

    # ---------- 删除 / 重置 ----------
    def delete(self, thread_id: str) -> bool:
        """删除一次运行（检查点 + 列表记录）；不存在时返回 False"""
        with self._run_lock(thread_id):
            with self._db() as conn:
                n = conn.execute("DELETE FROM workflow_runs WHERE thread_id=?", (thread_id,)).rowcount
            self.saver.delete_thread(thread_id)
        with self._run_locks_guard:
            self._run_locks.pop(thread_id, None)
        if n:
            logger.info("已删除工作流运行 %s", thread_id)
        return bool(n)

    def reset(self) -> int:
        """清空全部运行（演示数据），返回删除的数量"""
        with self._db() as conn:
            ids = [r[0] for r in conn.execute("SELECT thread_id FROM workflow_runs").fetchall()]
        for tid in ids:
            self.delete(tid)
        logger.info("已清空全部工作流运行（%d 条）", len(ids))
        return len(ids)

    def spec(self) -> Dict[str, Any]:
        """结构描述（同 workflow.spec.graph_spec）"""
        return graph_spec()

    def mermaid(self) -> str:
        """LangGraph 生成的 Mermaid 拓扑图"""
        return self.graph.get_graph().draw_mermaid()

    def close(self) -> None:
        """关闭全部连接（测试 / 退出时调用）"""
        with self._conns_guard:
            for conn in self._all_conns:
                try:
                    conn.close()
                except sqlite3.Error:
                    pass
            self._all_conns.clear()
        self._local = threading.local()
