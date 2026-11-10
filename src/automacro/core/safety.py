"""Mecanismos de segurança: parada de emergência e failsafe do cursor."""

from __future__ import annotations

import logging
import threading
import weakref
from typing import Callable

from automacro.core.timing import RunToken

log = logging.getLogger(__name__)


class EmergencyStop:
    """Registro de execuções ativas; ``trigger`` cancela todas de forma síncrona e barata.

    É seguro chamar ``trigger`` de qualquer thread (inclusive da thread do listener de
    teclado): ele só levanta flags, sem esperar nada terminar.
    """

    def __init__(self) -> None:
        self._tokens: "weakref.WeakSet[RunToken]" = weakref.WeakSet()
        self._lock = threading.Lock()
        self.trigger_count = 0

    def register(self, token: RunToken) -> None:
        with self._lock:
            self._tokens.add(token)

    def unregister(self, token: RunToken) -> None:
        with self._lock:
            self._tokens.discard(token)

    def trigger(self) -> int:
        with self._lock:
            tokens = list(self._tokens)
            self.trigger_count += 1
        for token in tokens:
            token.cancel()
        return len(tokens)


class CursorFailsafe:
    """Observa a posição do cursor e dispara ``on_trigger`` se ele for ao canto superior esquerdo.

    Roda em uma thread própria enquanto houver uma atividade. Se ``position`` não estiver
    disponível (ex.: Wayland), simplesmente não é iniciado.
    """

    def __init__(self, position: Callable[[], tuple[int, int] | None],
                 on_trigger: Callable[[], None], interval_s: float = 0.05,
                 corner_px: int = 1) -> None:
        self._position = position
        self._on_trigger = on_trigger
        self._interval = interval_s
        self._corner = corner_px
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None

    def start(self) -> None:
        if self._thread is not None:
            return
        self._stop.clear()
        self._thread = threading.Thread(target=self._run, name="automacro-failsafe", daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()
        thread, self._thread = self._thread, None
        if thread is not None and thread is not threading.current_thread():
            thread.join(timeout=1.0)

    def _run(self) -> None:
        while not self._stop.wait(self._interval):
            try:
                pos = self._position()
            except Exception:
                log.debug("Falha ao ler posição do cursor no failsafe", exc_info=True)
                continue
            if pos is None:
                continue
            x, y = pos
            if x <= self._corner and y <= self._corner:
                log.warning("Failsafe acionado: cursor no canto superior esquerdo")
                try:
                    self._on_trigger()
                finally:
                    return
