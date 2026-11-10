"""Motor do Auto Clicker (executa na thread da atividade criada pela ``Session``)."""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass
from typing import Callable

from automacro.core.event_bus import ClickCount
from automacro.core.timing import RunToken
from automacro.input_handlers.base import InputInjector
from automacro.models.settings import AutoClickConfig
from automacro.utils.throttle import Throttle

log = logging.getLogger(__name__)

# Se o sistema atrasar mais que isto, o motor re-sincroniza em vez de disparar uma rajada
# de cliques atrasados.
_RESYNC_LAG_NS = 50_000_000


@dataclass
class AutoClickStats:
    clicks: int = 0
    cancelled: bool = False
    reason: str = ""


class AutoClickEngine:
    def __init__(self, injector: InputInjector,
                 publish: Callable[[object], None] = lambda e: None) -> None:
        self._injector = injector
        self._publish = publish

    def run(self, config: AutoClickConfig, token: RunToken) -> AutoClickStats:
        cfg = config.sanitize()
        stats = AutoClickStats()
        interval_ns = int(cfg.interval_ms * 1e6)
        throttle = Throttle(0.05)
        start = time.perf_counter_ns()
        runtime_limit_ns = int(cfg.max_runtime_s * 1e9)
        deadline = start
        x = cfg.x if cfg.use_fixed_position else None
        y = cfg.y if cfg.use_fixed_position else None
        try:
            while cfg.count == 0 or stats.clicks < cfg.count:
                effective = token.sleep_until(deadline)
                if effective is None:
                    stats.cancelled, stats.reason = True, "interrompido"
                    break
                if runtime_limit_ns and effective - start >= runtime_limit_ns:
                    stats.reason = "tempo máximo atingido"
                    break
                self._injector.click(cfg.button, x, y)
                stats.clicks += 1
                if throttle.ready():
                    self._publish(ClickCount(stats.clicks, cfg.count))
                deadline = effective + interval_ns
                if time.perf_counter_ns() - deadline > _RESYNC_LAG_NS:
                    deadline = time.perf_counter_ns()
            else:
                stats.reason = "quantidade concluída"
        finally:
            self._injector.release_all()
            self._publish(ClickCount(stats.clicks, cfg.count))
        return stats
