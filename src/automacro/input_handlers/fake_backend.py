"""Backend falso, usado nos testes (e útil para depurar a UI sem mexer no mouse real)."""

from __future__ import annotations

import threading
import time
from dataclasses import dataclass

from automacro.input_handlers.base import (
    InjectionTracker,
    InputBackend,
    InputInjector,
    InputListener,
    ListenerCallbacks,
)
from automacro.input_handlers.capabilities import BackendCapabilities


@dataclass(frozen=True)
class FakeAction:
    t_ns: int
    name: str            # move, mouse_down, mouse_up, scroll, key_down, key_up
    args: tuple


class FakeBackend(InputBackend):
    name = "fake"

    def __init__(self, capabilities: BackendCapabilities | None = None,
                 loopback: bool = False, fail_after: int | None = None) -> None:
        self._caps = capabilities or BackendCapabilities.all_available("fake")
        self.tracker = InjectionTracker()
        self.loopback = loopback            # eventos injetados também chegam aos listeners
        self.fail_after = fail_after        # lança erro depois de N ações (testes de falha)
        self.actions: list[FakeAction] = []
        self.position = (0, 0)
        self._lock = threading.Lock()
        self._listeners: list["FakeListener"] = []
        self.listeners_started = 0

    # ---- API do backend -------------------------------------------------------------
    def capabilities(self) -> BackendCapabilities:
        return self._caps

    def create_injector(self) -> InputInjector:
        return FakeInjector(self)

    def create_listener(self) -> InputListener:
        return FakeListener(self)

    # ---- utilidades de teste --------------------------------------------------------
    @property
    def active_listeners(self) -> int:
        with self._lock:
            return sum(1 for l in self._listeners if l.running)

    def names(self) -> list[str]:
        with self._lock:
            return [a.name for a in self.actions]

    def clear_actions(self) -> None:
        with self._lock:
            self.actions.clear()

    def _record(self, name: str, *args) -> None:
        with self._lock:
            if self.fail_after is not None and len(self.actions) >= self.fail_after:
                raise RuntimeError("falha simulada do backend")
            self.actions.append(FakeAction(time.perf_counter_ns(), name, args))

    def _active(self) -> list["FakeListener"]:
        with self._lock:
            return [l for l in self._listeners if l.running]

    # simulam o usuário real
    def simulate_key(self, key: str, pressed: bool) -> None:
        for listener in self._active():
            listener.deliver_key(key, pressed)

    def simulate_move(self, x: int, y: int) -> None:
        self.position = (x, y)
        for listener in self._active():
            listener.deliver_move(x, y)

    def simulate_click(self, x: int, y: int, button: str, pressed: bool) -> None:
        self.position = (x, y)
        for listener in self._active():
            listener.deliver_click(x, y, button, pressed)

    def simulate_scroll(self, x: int, y: int, dx: int, dy: int) -> None:
        for listener in self._active():
            listener.deliver_scroll(x, y, dx, dy)


class FakeInjector(InputInjector):
    def __init__(self, backend: FakeBackend) -> None:
        super().__init__(backend.tracker)
        self._b = backend

    def _move_to(self, x, y):
        self._b._record("move", x, y)
        self._b.position = (x, y)
        if self._b.loopback:
            for l in self._b._active():
                l.deliver_move(x, y)

    def _mouse_down(self, button):
        self._b._record("mouse_down", button)
        if self._b.loopback:
            for l in self._b._active():
                l.deliver_click(*self._b.position, button, True)

    def _mouse_up(self, button):
        self._b._record("mouse_up", button)
        if self._b.loopback:
            for l in self._b._active():
                l.deliver_click(*self._b.position, button, False)

    def _scroll(self, dx, dy):
        self._b._record("scroll", dx, dy)
        if self._b.loopback:
            for l in self._b._active():
                l.deliver_scroll(*self._b.position, dx, dy)

    def _key_down(self, key):
        self._b._record("key_down", key)
        if self._b.loopback:
            for l in self._b._active():
                l.deliver_key(key, True)

    def _key_up(self, key):
        self._b._record("key_up", key)
        if self._b.loopback:
            for l in self._b._active():
                l.deliver_key(key, False)

    def _position(self):
        return self._b.position


class FakeListener(InputListener):
    def __init__(self, backend: FakeBackend) -> None:
        self._b = backend
        self._callbacks: ListenerCallbacks | None = None
        self._running = False

    def start(self, callbacks: ListenerCallbacks) -> None:
        if self._running:
            raise RuntimeError("listener já iniciado")
        self._callbacks = callbacks
        self._running = True
        with self._b._lock:
            self._b._listeners.append(self)
            self._b.listeners_started += 1

    def stop(self) -> None:
        self._running = False

    @property
    def running(self) -> bool:
        return self._running

    def deliver_key(self, key: str, pressed: bool) -> None:
        cb = self._callbacks
        if cb and cb.on_key:
            if self._b.tracker.consume(key, pressed):
                return
            cb.on_key(key, pressed)

    def deliver_move(self, x, y):
        cb = self._callbacks
        if cb and cb.on_move:
            cb.on_move(x, y)

    def deliver_click(self, x, y, button, pressed):
        cb = self._callbacks
        if cb and cb.on_click:
            cb.on_click(x, y, button, pressed)

    def deliver_scroll(self, x, y, dx, dy):
        cb = self._callbacks
        if cb and cb.on_scroll:
            cb.on_scroll(x, y, dx, dy)
