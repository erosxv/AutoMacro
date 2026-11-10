"""Limitador simples de frequência, para não inundar a UI com eventos."""

from __future__ import annotations

import threading
import time


class Throttle:
    """``ready()`` devolve True no máximo uma vez a cada ``interval_s`` segundos."""

    def __init__(self, interval_s: float) -> None:
        self._interval = interval_s
        self._last = 0.0
        self._lock = threading.Lock()

    def ready(self) -> bool:
        now = time.monotonic()
        with self._lock:
            if now - self._last >= self._interval:
                self._last = now
                return True
            return False

    def reset(self) -> None:
        with self._lock:
            self._last = 0.0
