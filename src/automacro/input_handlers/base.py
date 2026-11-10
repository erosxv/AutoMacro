"""Interfaces que todo backend de entrada implementa.

Contrato importante:

* ``InputInjector`` rastreia tudo que está pressionado (``release_all`` solta tudo, para
  nunca deixar uma tecla "presa" depois de parar ou falhar).
* ``InjectionTracker`` marca as teclas que **nós mesmos** enviamos, para que o listener de
  atalhos não reaja a elas (ex.: uma macro que contém F9 não pode parar a si mesma).
"""

from __future__ import annotations

import logging
import threading
import time
from abc import ABC, abstractmethod
from collections import deque
from dataclasses import dataclass
from typing import Callable

from automacro.input_handlers.capabilities import BackendCapabilities

log = logging.getLogger(__name__)


class InjectionTracker:
    """Lembra, por pouco tempo, das teclas enviadas por nós para ignorá-las ao capturar."""

    TTL_NS = 300_000_000   # 300 ms

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._items: deque[tuple[str, bool, int]] = deque()

    def _prune(self, now: int) -> None:
        while self._items and now - self._items[0][2] > self.TTL_NS:
            self._items.popleft()

    def note(self, key: str, pressed: bool) -> None:
        now = time.perf_counter_ns()
        with self._lock:
            self._prune(now)
            self._items.append((key, pressed, now))

    def consume(self, key: str, pressed: bool) -> bool:
        """True se este evento foi gerado por nós (e o remove da lista)."""
        now = time.perf_counter_ns()
        with self._lock:
            self._prune(now)
            for item in self._items:
                if item[0] == key and item[1] == pressed:
                    self._items.remove(item)
                    return True
        return False


@dataclass
class ListenerCallbacks:
    on_move: Callable[[int, int], None] | None = None
    on_click: Callable[[int, int, str, bool], None] | None = None
    on_scroll: Callable[[int, int, int, int], None] | None = None
    on_key: Callable[[str, bool], None] | None = None

    @property
    def wants_mouse(self) -> bool:
        return any((self.on_move, self.on_click, self.on_scroll))

    @property
    def wants_keyboard(self) -> bool:
        return self.on_key is not None


class InputInjector(ABC):
    """Envia entrada ao sistema. Subclasses implementam os métodos ``_...``."""

    def __init__(self, tracker: InjectionTracker | None = None) -> None:
        self._tracker = tracker or InjectionTracker()
        self._held_keys: set[str] = set()
        self._held_buttons: set[str] = set()
        self._held_lock = threading.Lock()

    # ---- API pública ----------------------------------------------------------------
    def move_to(self, x: int, y: int) -> None:
        self._move_to(int(x), int(y))

    def mouse_down(self, button: str, x: int | None = None, y: int | None = None) -> None:
        if x is not None and y is not None:
            self._move_to(int(x), int(y))
        self._mouse_down(button)
        with self._held_lock:
            self._held_buttons.add(button)

    def mouse_up(self, button: str, x: int | None = None, y: int | None = None) -> None:
        if x is not None and y is not None:
            self._move_to(int(x), int(y))
        self._mouse_up(button)
        with self._held_lock:
            self._held_buttons.discard(button)

    def click(self, button: str, x: int | None = None, y: int | None = None) -> None:
        self.mouse_down(button, x, y)
        self.mouse_up(button)

    def scroll(self, dx: int, dy: int) -> None:
        self._scroll(int(dx), int(dy))

    def key_down(self, key: str) -> None:
        self._tracker.note(key, True)
        self._key_down(key)
        with self._held_lock:
            self._held_keys.add(key)

    def key_up(self, key: str) -> None:
        self._tracker.note(key, False)
        self._key_up(key)
        with self._held_lock:
            self._held_keys.discard(key)

    def position(self) -> tuple[int, int] | None:
        return self._position()

    def release_all(self) -> int:
        """Solta tudo que ainda está pressionado. Retorna quantas entradas foram soltas."""
        with self._held_lock:
            keys, buttons = list(self._held_keys), list(self._held_buttons)
        released = 0
        for key in keys:
            try:
                self.key_up(key)
                released += 1
            except Exception:
                log.exception("Falha ao soltar a tecla %s", key)
        for button in buttons:
            try:
                self.mouse_up(button)
                released += 1
            except Exception:
                log.exception("Falha ao soltar o botão %s", button)
        return released

    @property
    def held(self) -> tuple[frozenset[str], frozenset[str]]:
        with self._held_lock:
            return frozenset(self._held_keys), frozenset(self._held_buttons)

    def close(self) -> None:
        self.release_all()

    # ---- a implementar --------------------------------------------------------------
    @abstractmethod
    def _move_to(self, x: int, y: int) -> None: ...

    @abstractmethod
    def _mouse_down(self, button: str) -> None: ...

    @abstractmethod
    def _mouse_up(self, button: str) -> None: ...

    @abstractmethod
    def _scroll(self, dx: int, dy: int) -> None: ...

    @abstractmethod
    def _key_down(self, key: str) -> None: ...

    @abstractmethod
    def _key_up(self, key: str) -> None: ...

    @abstractmethod
    def _position(self) -> tuple[int, int] | None: ...


class InputListener(ABC):
    """Observa entrada global. Os callbacks chegam em threads do backend (devem ser rápidos)."""

    @abstractmethod
    def start(self, callbacks: ListenerCallbacks) -> None: ...

    @abstractmethod
    def stop(self) -> None: ...

    @property
    @abstractmethod
    def running(self) -> bool: ...


class InputBackend(ABC):
    name: str = "base"

    @abstractmethod
    def capabilities(self) -> BackendCapabilities: ...

    @abstractmethod
    def create_injector(self) -> InputInjector: ...

    @abstractmethod
    def create_listener(self) -> InputListener: ...

    def close(self) -> None:
        """Libera recursos globais do backend (padrão: nada)."""
