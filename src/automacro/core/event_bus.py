"""Barramento de eventos do núcleo para quem quiser observar (UI, testes, logs).

Os assinantes são chamados **na thread de quem publica**; eles devem ser rápidos e
não bloquear. A UI converte cada evento em um sinal Qt (entrega enfileirada).
"""

from __future__ import annotations

import logging
import threading
from dataclasses import dataclass
from typing import Any, Callable

from automacro.models.state import AppState

log = logging.getLogger(__name__)


@dataclass(frozen=True)
class StateChanged:
    old: AppState
    new: AppState
    activity: str | None


@dataclass(frozen=True)
class Progress:
    done: int
    total: int
    loop: int
    loops: int              # 0 = infinito


@dataclass(frozen=True)
class RecordingCount:
    count: int


@dataclass(frozen=True)
class ClickCount:
    count: int
    target: int             # 0 = infinito


@dataclass(frozen=True)
class Countdown:
    remaining: int
    activity: str


@dataclass(frozen=True)
class Notice:
    level: str              # "info" | "warning" | "error"
    text: str


@dataclass(frozen=True)
class RecordingFinished:
    macro: Any              # automacro.models.macro.Macro


@dataclass(frozen=True)
class ActivityFinished:
    activity: str
    cancelled: bool
    error: str | None


Subscriber = Callable[[Any], None]


class EventBus:
    def __init__(self) -> None:
        self._subscribers: list[Subscriber] = []
        self._lock = threading.Lock()

    def subscribe(self, callback: Subscriber) -> Callable[[], None]:
        with self._lock:
            self._subscribers.append(callback)

        def unsubscribe() -> None:
            with self._lock:
                if callback in self._subscribers:
                    self._subscribers.remove(callback)

        return unsubscribe

    def publish(self, event: Any) -> None:
        with self._lock:
            subscribers = list(self._subscribers)
        for callback in subscribers:
            try:
                callback(event)
            except Exception:  # um assinante com defeito não pode derrubar o motor
                log.exception("Erro em assinante do barramento de eventos")

    def notice(self, level: str, text: str) -> None:
        log_fn = {"error": log.error, "warning": log.warning}.get(level, log.info)
        log_fn("%s", text)
        self.publish(Notice(level, text))
