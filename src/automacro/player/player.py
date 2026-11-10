"""Reprodutor de macros.

Roda na thread da atividade (criada pela ``Session``). Cada evento tem um prazo absoluto
calculado a partir do início da repetição; pausas apenas deslocam os prazos seguintes.
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass
from itertools import accumulate
from typing import Callable

from automacro.core.event_bus import Progress
from automacro.core.timing import RunToken
from automacro.input_handlers.base import InputInjector
from automacro.models.events import EventType, MacroEvent
from automacro.models.macro import Macro
from automacro.models.settings import PlayerSettings
from automacro.utils.throttle import Throttle

log = logging.getLogger(__name__)


@dataclass
class PlaybackStats:
    events_played: int = 0
    loops_completed: int = 0
    max_late_ms: float = 0.0
    cancelled: bool = False


def execute_event(injector: InputInjector, ev: MacroEvent) -> None:
    t = ev.type
    if t is EventType.MOUSE_MOVE:
        injector.move_to(ev.x, ev.y)
    elif t is EventType.MOUSE_PRESS:
        injector.mouse_down(ev.button, ev.x, ev.y)
    elif t is EventType.MOUSE_RELEASE:
        injector.mouse_up(ev.button, ev.x, ev.y)
    elif t is EventType.MOUSE_SCROLL:
        if ev.x is not None and ev.y is not None:
            injector.move_to(ev.x, ev.y)
        injector.scroll(ev.dx, ev.dy)
    elif t is EventType.KEY_DOWN:
        injector.key_down(ev.key)
    elif t is EventType.KEY_UP:
        injector.key_up(ev.key)


class Player:
    def __init__(self, injector: InputInjector, publish: Callable[[object], None] = lambda e: None) -> None:
        self._injector = injector
        self._publish = publish

    def run(self, macro: Macro, settings: PlayerSettings, token: RunToken) -> PlaybackStats:
        stats = PlaybackStats()
        events = macro.events
        total = len(events)
        if total == 0:
            return stats

        speed = max(settings.speed, 0.01)
        offsets_ns = [int(ms * 1e6 / speed) for ms in accumulate(e.delay_ms for e in events)]
        loops = settings.repeat                 # 0 = infinito
        throttle = Throttle(0.05)
        loop = 0
        try:
            while loops == 0 or loop < loops:
                loop += 1
                shift = 0                        # tempo total em pausa nesta repetição
                t0 = time.perf_counter_ns()
                for i, ev in enumerate(events):
                    deadline = t0 + offsets_ns[i] + shift
                    effective = token.sleep_until(deadline)
                    if effective is None:
                        stats.cancelled = True
                        return stats
                    shift += effective - deadline
                    late_ms = (time.perf_counter_ns() - effective) / 1e6
                    if late_ms > stats.max_late_ms:
                        stats.max_late_ms = late_ms
                    execute_event(self._injector, ev)
                    stats.events_played += 1
                    if throttle.ready() or i == total - 1:
                        self._publish(Progress(i + 1, total, loop, loops))
                stats.loops_completed += 1
                if (loops == 0 or loop < loops) and settings.loop_delay_ms > 0:
                    if not token.sleep_for(settings.loop_delay_ms / 1000.0):
                        stats.cancelled = True
                        return stats
                if token.cancelled:
                    stats.cancelled = True
                    return stats
            return stats
        finally:
            # Nunca deixar tecla ou botão preso, termine como terminar.
            self._injector.release_all()
