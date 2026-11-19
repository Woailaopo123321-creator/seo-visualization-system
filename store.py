"""
学习任务存储：线程安全 + 原子写入 + 字段校验。
数据文件路径可用环境变量 SEO_DATA_FILE 覆盖，默认 data/learning_data.json。
"""

import json
import logging
import os
import tempfile
import threading
import copy
from typing import Any, Dict, List, Optional

logger = logging.getLogger("seo.store")

STATUSES = {
    "todo": "待规划",
    "in_progress": "进行中",
    "review": "待优化",
    "done": "已完成",
}
PRIORITIES = {"high": "高", "medium": "中", "low": "低"}
TITLE_MAX = 80
SUBTITLE_MAX = 200

DEFAULT_DATA = {
    "tasks": [
        {"id": 1, "title": "市场调研与选题规划", "subtitle": "确定目标受众与核心主题", "status": "todo", "progress": 0, "priority": "high"},
        {"id": 2, "title": "用户需求分析", "subtitle": "搜索意图分类", "status": "todo", "progress": 0, "priority": "medium"},
        {"id": 3, "title": "竞品内容分析", "subtitle": "AI Overviews 覆盖情况", "status": "todo", "progress": 0, "priority": "medium"},
        {"id": 4, "title": "SEO 关键词研究", "subtitle": "主题集群关键词", "status": "in_progress", "progress": 70, "priority": "high"},
        {"id": 5, "title": "内容大纲设计", "subtitle": "答案优先结构", "status": "in_progress", "progress": 50, "priority": "medium"},
        {"id": 6, "title": "初稿撰写", "subtitle": "加入第一手经验", "status": "in_progress", "progress": 30, "priority": "medium"},
        {"id": 7, "title": "内链结构优化", "subtitle": "支柱页 ↔ 集群页", "status": "review", "progress": 80, "priority": "medium"},
        {"id": 8, "title": "E-E-A-T 信号补强", "subtitle": "作者署名 + sameAs", "status": "review", "progress": 75, "priority": "high"},
        {"id": 9, "title": "标题与描述优化", "subtitle": "Title / Meta Description", "status": "done", "progress": 100, "priority": "medium"},
        {"id": 10, "title": "关键词布局优化", "subtitle": "首段与小标题覆盖", "status": "done", "progress": 100, "priority": "low"},
    ],
    "next_id": 11,
}


class ValidationError(ValueError):
    """字段校验失败；API 层统一转换为 400 + 中文错误信息"""


def validate_task_fields(payload: Any, partial: bool = False) -> Dict[str, Any]:
    """校验并清洗任务字段，返回可写入的 dict；不合法时抛 ValidationError。"""
    if not isinstance(payload, dict):
        raise ValidationError("请求体必须是 JSON 对象")
    clean = {}
    if "title" in payload or not partial:
        title = payload.get("title")
        if not isinstance(title, str) or not title.strip():
            raise ValidationError("title 不能为空")
        if len(title.strip()) > TITLE_MAX:
            raise ValidationError(f"title 不能超过 {TITLE_MAX} 个字符")
        clean["title"] = title.strip()
    if "subtitle" in payload:
        sub = payload.get("subtitle") or ""
        if not isinstance(sub, str) or len(sub) > SUBTITLE_MAX:
            raise ValidationError(f"subtitle 必须是不超过 {SUBTITLE_MAX} 字符的文本")
        clean["subtitle"] = sub.strip()
    if "status" in payload:
        if payload["status"] not in STATUSES:
            raise ValidationError(f"status 必须是 {list(STATUSES)} 之一")
        clean["status"] = payload["status"]
    if "priority" in payload:
        if payload["priority"] not in PRIORITIES:
            raise ValidationError(f"priority 必须是 {list(PRIORITIES)} 之一")
        clean["priority"] = payload["priority"]
    if "progress" in payload:
        p = payload["progress"]
        if isinstance(p, bool) or not isinstance(p, (int, float)) or not 0 <= p <= 100:
            raise ValidationError("progress 必须是 0-100 之间的数字")
        clean["progress"] = int(round(p))
    return clean


class TaskStore:
    """JSON 文件存储：任务列表 + 元数据（如 Agent 统计）。读写都加锁，写入走临时文件 + 原子替换。"""

    def __init__(self, path: str):
        self.path = path
        self._lock = threading.Lock()

    def _read(self):
        try:
            if os.path.exists(self.path):
                with open(self.path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                if isinstance(data, dict) and isinstance(data.get("tasks"), list):
                    return data
                logger.warning("数据文件格式不正确，使用默认数据: %s", self.path)
        except (OSError, json.JSONDecodeError) as e:
            logger.error("读取数据失败: %s", e)
        return copy.deepcopy(DEFAULT_DATA)

    def _write(self, data):
        directory = os.path.dirname(os.path.abspath(self.path))
        os.makedirs(directory, exist_ok=True)
        fd, tmp = tempfile.mkstemp(dir=directory, prefix=".tasks-", suffix=".json")
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            os.replace(tmp, self.path)  # 原子替换，避免写一半损坏
        except Exception:
            if os.path.exists(tmp):
                os.remove(tmp)
            raise

    def get_meta(self, key: str, default: Any = None) -> Any:
        """读取与任务同文件保存的附加数据（如 agent_stats）"""
        with self._lock:
            return copy.deepcopy(self._read().get(key, default))

    def set_meta(self, key: str, value: Any) -> None:
        """写入一项元数据（与任务保存在同一文件）"""
        with self._lock:
            data = self._read()
            data[key] = value
            self._write(data)

    def list(self) -> List[Dict[str, Any]]:
        """全部任务（副本，调用方可随意修改）"""
        with self._lock:
            return self._read()["tasks"]

    def create(self, payload: Any) -> Dict[str, Any]:
        """校验后新建任务，返回新任务"""
        fields = validate_task_fields(payload)
        with self._lock:
            data = self._read()
            next_id = data.get("next_id") or (max((t.get("id", 0) for t in data["tasks"]), default=0) + 1)
            task = {"id": next_id, "title": fields["title"], "subtitle": "", "status": "todo",
                    "progress": 0, "priority": "medium"}
            task.update(fields)
            if task["status"] == "done":
                task["progress"] = 100
            data["tasks"].append(task)
            data["next_id"] = next_id + 1
            self._write(data)
            return task

    def update(self, task_id: int, payload: Any) -> Optional[Dict[str, Any]]:
        """部分更新任务；任务不存在时返回 None"""
        fields = validate_task_fields(payload, partial=True)
        if not fields:
            raise ValidationError("没有可更新的字段")
        with self._lock:
            data = self._read()
            for task in data["tasks"]:
                if task.get("id") == task_id:
                    task.update(fields)
                    if fields.get("status") == "done" and "progress" not in fields:
                        task["progress"] = 100
                    self._write(data)
                    return task
            return None

    def delete(self, task_id: int) -> bool:
        """删除任务；不存在时返回 False"""
        with self._lock:
            data = self._read()
            before = len(data["tasks"])
            data["tasks"] = [t for t in data["tasks"] if t.get("id") != task_id]
            if len(data["tasks"]) == before:
                return False
            self._write(data)
            return True


def task_metrics(tasks: List[Dict[str, Any]]) -> Dict[str, Any]:
    """任务统计：总数、各状态数量、完成率、平均进度"""
    total = len(tasks)
    by_status = {k: 0 for k in STATUSES}
    for t in tasks:
        by_status[t.get("status", "todo")] = by_status.get(t.get("status", "todo"), 0) + 1
    avg = sum(t.get("progress", 0) for t in tasks) / total if total else 0
    return {
        "total": total,
        "by_status": by_status,
        "done": by_status.get("done", 0),
        "in_progress": by_status.get("in_progress", 0),
        "avg_progress": round(avg, 1),
        "completion_rate": round(by_status.get("done", 0) / total * 100, 1) if total else 0,
    }
