"""登录 / 令牌防暴力破解：按客户端地址计数，连续失败达到上限后锁定一段时间。"""

from __future__ import annotations

import logging
import threading
import time
from typing import Dict, Tuple

logger = logging.getLogger("seo.security")


class LoginLimiter:
    """线程安全的失败计数器（内存级，单进程有效；重启后清零）。

    - 在 ``window`` 秒内失败 ``max_attempts`` 次 → 锁定 ``lockout`` 秒
    - 成功一次即清零
    """

    def __init__(self, max_attempts: int = 5, lockout: int = 900, window: int = 900):
        self.max_attempts = max(1, max_attempts)
        self.lockout = max(1, lockout)
        self.window = max(1, window)
        self._lock = threading.Lock()
        self._state: Dict[str, Tuple[int, float, float]] = {}  # key -> (失败次数, 首次失败时间, 锁定到)

    def retry_after(self, key: str) -> int:
        """仍处于锁定状态时返回剩余秒数，否则 0"""
        with self._lock:
            _, _, until = self._state.get(key, (0, 0.0, 0.0))
            left = until - time.time()
            return int(left) + 1 if left > 0 else 0

    def remaining(self, key: str) -> int:
        """锁定前还可以失败几次"""
        with self._lock:
            count, first, _ = self._state.get(key, (0, 0.0, 0.0))
            if time.time() - first > self.window:
                count = 0
            return max(self.max_attempts - count, 0)

    def fail(self, key: str) -> int:
        """记录一次失败；若因此被锁定，返回锁定秒数，否则 0"""
        now = time.time()
        with self._lock:
            count, first, until = self._state.get(key, (0, now, 0.0))
            if now - first > self.window:
                count, first = 0, now
            count += 1
            if count >= self.max_attempts:
                self._state[key] = (0, now, now + self.lockout)
                logger.warning("客户端 %s 连续 %d 次认证失败，锁定 %d 秒", key, count, self.lockout)
                return self.lockout
            self._state[key] = (count, first, until)
            logger.info("客户端 %s 认证失败（第 %d 次）", key, count)
            return 0

    def success(self, key: str) -> None:
        """认证成功：清除该客户端的失败记录"""
        with self._lock:
            self._state.pop(key, None)
