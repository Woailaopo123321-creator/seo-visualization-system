"""
分布式 AI 管理架构 - 基础 Agent 与协调器
模拟分布式多智能体系统：协调器分配任务给专业 Agent。
增强：线程安全的结果缓存（含过期清理）、超时保护、运行统计（可观测性）。
"""

from abc import ABC, abstractmethod
from typing import Any, Callable, Dict, Optional
import concurrent.futures
import copy
import hashlib
import json
import logging
import threading
import time

logger = logging.getLogger("seo.agents")


class BaseAgent(ABC):
    """所有 Agent 的基类：name 用于协调器注册与分发"""

    def __init__(self, name: str):
        self.name = name

    @abstractmethod
    def execute(self, task: Dict[str, Any]) -> Dict[str, Any]:
        """执行任务并返回结果 dict（由协调器包装 status / 耗时 / 缓存信息）"""


class Coordinator:
    """中央协调器：负责任务分解与分发（分布式管理核心）"""

    def __init__(self, cache_ttl: int = 30, timeout: float = 12, max_cache: int = 256,
                 initial_stats: Optional[Dict[str, Any]] = None,
                 on_stats_change: Optional[Callable[[Dict[str, Any]], None]] = None):
        self.agents: Dict[str, BaseAgent] = {}
        self.executor = concurrent.futures.ThreadPoolExecutor(max_workers=4)
        self._cache: Dict[str, tuple] = {}  # key -> (result, expire_time)
        self._lock = threading.Lock()
        self.cache_ttl = cache_ttl
        self.timeout = timeout
        self.max_cache = max_cache
        self.stats = {"runs": 0, "success": 0, "failed": 0, "timeout": 0, "cache_hits": 0, "per_agent": {}}
        if initial_stats:
            # 从持久化数据恢复统计，重启后不清零
            for k, v in initial_stats.items():
                if k == "per_agent" and isinstance(v, dict):
                    self.stats["per_agent"] = copy.deepcopy(v)
                elif k in self.stats and isinstance(v, (int, float)):
                    self.stats[k] = v
        self._on_stats_change = on_stats_change
        self._persist_lock = threading.Lock()

    def register(self, agent: BaseAgent) -> None:
        """注册 Agent（同名覆盖）"""
        self.agents[agent.name] = agent

    @staticmethod
    def _cache_key(agent_name: str, task: Dict[str, Any]) -> str:
        raw = f"{agent_name}:{json.dumps(task, sort_keys=True, ensure_ascii=False, default=str)}"
        return hashlib.sha256(raw.encode()).hexdigest()

    def _persist(self):
        if not self._on_stats_change:
            return
        # 串行化写入，保证落盘的是最新快照
        with self._persist_lock:
            try:
                self._on_stats_change(self.snapshot())
            except Exception:  # noqa: BLE001 - 持久化失败不影响主流程
                logger.exception("保存 Agent 统计失败")

    def _record(self, agent_name: str, outcome: str, elapsed_ms: float = 0.0):
        self._record_locked(agent_name, outcome, elapsed_ms)
        self._persist()

    def _record_locked(self, agent_name: str, outcome: str, elapsed_ms: float = 0.0):
        with self._lock:
            self.stats["runs"] += 1
            self.stats[outcome] = self.stats.get(outcome, 0) + 1
            per = self.stats["per_agent"].setdefault(agent_name, {"runs": 0, "success": 0, "avg_ms": 0.0})
            per["runs"] += 1
            if outcome == "success":
                per["success"] += 1
                per["avg_ms"] = round(per["avg_ms"] + (elapsed_ms - per["avg_ms"]) / per["success"], 2)

    def _purge_expired(self, now: float):
        expired = [k for k, (_, exp) in self._cache.items() if exp <= now]
        for k in expired:
            del self._cache[k]
        # 超过上限时淘汰最早过期的条目
        if len(self._cache) > self.max_cache:
            for k, _ in sorted(self._cache.items(), key=lambda kv: kv[1][1])[: len(self._cache) - self.max_cache]:
                del self._cache[k]

    def dispatch(self, agent_name: str, task: Dict[str, Any], use_cache: bool = True) -> Dict[str, Any]:
        if agent_name not in self.agents:
            return {"error": f"Agent {agent_name} 未注册", "agent": agent_name, "status": "failed"}

        cache_key = self._cache_key(agent_name, task)
        if use_cache:
            with self._lock:
                hit = self._cache.get(cache_key)
                if hit and time.time() < hit[1]:
                    self.stats["cache_hits"] += 1
                    result = copy.deepcopy(hit[0])
                    result["cached"] = True
                else:
                    result = None
            if result is not None:
                self._persist()
                return result

        start = time.perf_counter()
        future = self.executor.submit(self.agents[agent_name].execute, task)
        try:
            result = future.result(timeout=self.timeout)
        except concurrent.futures.TimeoutError:
            self._record(agent_name, "timeout")
            logger.warning("Agent %s 执行超时", agent_name)
            return {"error": "Agent 执行超时", "agent": agent_name, "status": "timeout"}
        except Exception as e:  # noqa: BLE001 - 将 Agent 异常转为结构化结果
            self._record(agent_name, "failed")
            logger.exception("Agent %s 执行失败", agent_name)
            return {"error": str(e), "agent": agent_name, "status": "failed"}

        elapsed_ms = (time.perf_counter() - start) * 1000
        result = dict(result)
        result.update({"agent": agent_name, "status": "success", "cached": False,
                       "elapsed_ms": round(elapsed_ms, 2)})
        self._record(agent_name, "success", elapsed_ms)
        if use_cache:
            with self._lock:
                now = time.time()
                self._cache[cache_key] = (copy.deepcopy(result), now + self.cache_ttl)
                self._purge_expired(now)
        return result

    def multi_dispatch(self, tasks: list) -> list:
        """并行分发多个任务（真正的分布式模拟），结果顺序与输入一致"""
        futures = [self.executor.submit(self.dispatch, name, task) for name, task in tasks]
        return [f.result() for f in futures]

    def cache_size(self) -> int:
        """当前未过期的缓存条数"""
        with self._lock:
            self._purge_expired(time.time())
            return len(self._cache)

    def snapshot(self) -> Dict[str, Any]:
        """运行统计的副本（成功 / 失败 / 超时 / 缓存命中等）"""
        with self._lock:
            return copy.deepcopy(self.stats)

    def clear_cache(self) -> None:
        """清空结果缓存"""
        with self._lock:
            self._cache.clear()
