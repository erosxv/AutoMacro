"""Gravador de macros.

Cria um listener a cada gravação e o encerra ao final (nenhum listener fica ativo fora de
uma gravação). Os atalhos do próprio aplicativo não entram na macro.
"""

from __future__ import annotations

import logging
import math
import threading
import time
from typing import Callable

from automacro.input_handlers.base import InputBackend, InputListener, ListenerCallbacks
from automacro.input_handlers.keymap import MODIFIERS, canonical_key
from automacro.models.events import EventType, MacroEvent
from automacro.models.macro import MAX_EVENTS, Macro
from automacro.models.settings import RecorderSettings

log = logging.getLogger(__name__)


class Recorder:
    def __init__(
        self,
        backend: InputBackend,
        settings: RecorderSettings,
        hotkey_keys: Callable[[], set[str]] = lambda: set(),
        on_count: Callable[[int], None] | None = None,
        on_limit: Callable[[], None] | None = None,
    ) -> None:
        self._backend = backend
        self._settings = settings
        self._hotkey_keys = hotkey_keys
        self._on_count = on_count
        self._on_limit = on_limit

        self._lock = threading.Lock()
        self._listener: InputListener | None = None
        self._recording = False
        self._events: list[MacroEvent] = []
        self._last_ns = 0
        self._last_move_ns = 0
        self._last_move_pos: tuple[int, int] | None = None
        self._held_keys: set[str] = set()
        self._held_buttons: dict[str, tuple[int, int]] = {}
        self._hotkey_modifiers: set[str] = set()      # modificadores "consumidos" por atalhos
        self._modifier_events: dict[str, MacroEvent] = {}
        self._limit_reported = False

    @property
    def count(self) -> int:
        with self._lock:
            return len(self._events)

    @property
    def recording(self) -> bool:
        return self._recording

    # ---- ciclo de vida -----------------------------------------------------------------
    def start(self) -> None:
        with self._lock:
            if self._recording:
                raise RuntimeError("gravação já em andamento")
            self._reset()
            self._recording = True
        listener = self._backend.create_listener()
        callbacks = ListenerCallbacks(
            on_move=self._on_move if self._settings.record_mouse_moves else None,
            on_click=self._on_click,
            on_scroll=self._on_scroll if self._settings.record_scroll else None,
            on_key=self._on_key,
        )
        try:
            listener.start(callbacks)
        except Exception:
            with self._lock:
                self._recording = False
            raise
        self._listener = listener
        self._last_ns = time.perf_counter_ns()

    def stop(self, name: str = "Nova macro", extra_info: dict | None = None) -> Macro:
        """Encerra a captura e devolve a macro. Seguro de chamar mais de uma vez."""
        with self._lock:
            self._recording = False
            listener, self._listener = self._listener, None
        if listener is not None:
            listener.stop()
        with self._lock:
            events = self._finalize_events()
        macro = Macro(name=name, events=events, recorded_on=dict(extra_info or {}))
        return macro

    def _reset(self) -> None:
        self._events = []
        self._last_ns = 0
        self._last_move_ns = 0
        self._last_move_pos = None
        self._held_keys.clear()
        self._held_buttons.clear()
        self._hotkey_modifiers.clear()
        self._modifier_events.clear()
        self._limit_reported = False

    # ---- captura -----------------------------------------------------------------------
    def _add(self, event: MacroEvent) -> bool:
        """Chamar com o lock. Calcula o delay a partir do evento anterior."""
        if len(self._events) >= MAX_EVENTS:
            if not self._limit_reported:
                self._limit_reported = True
                if self._on_limit:
                    threading.Thread(target=self._on_limit, daemon=True).start()
            return False
        now = time.perf_counter_ns()
        event.delay_ms = 0.0 if not self._events else (now - self._last_ns) / 1e6
        self._last_ns = now
        self._events.append(event)
        return True

    def _notify(self) -> None:
        if self._on_count:
            try:
                self._on_count(len(self._events))
            except Exception:
                log.exception("Erro no callback de contagem")

    def _on_move(self, x: int, y: int) -> None:
        s = self._settings
        now = time.perf_counter_ns()
        with self._lock:
            if not self._recording:
                return
            if (now - self._last_move_ns) / 1e6 < s.move_min_interval_ms:
                return
            if self._last_move_pos is not None and s.move_min_distance_px > 0:
                if math.hypot(x - self._last_move_pos[0],
                              y - self._last_move_pos[1]) < s.move_min_distance_px:
                    return
            self._last_move_ns = now
            self._last_move_pos = (x, y)
            added = self._add(MacroEvent.move(x, y))
        if added:
            self._notify()

    def _on_click(self, x: int, y: int, button: str, pressed: bool) -> None:
        with self._lock:
            if not self._recording:
                return
            if pressed:
                self._held_buttons[button] = (x, y)
                added = self._add(MacroEvent.press(button, x, y))
            else:
                self._held_buttons.pop(button, None)
                added = self._add(MacroEvent.release(button, x, y))
        if added:
            self._notify()

    def _on_scroll(self, x: int, y: int, dx: int, dy: int) -> None:
        with self._lock:
            if not self._recording:
                return
            added = self._add(MacroEvent.scroll(dx, dy, x, y))
        if added:
            self._notify()

    def _on_key(self, key: str, pressed: bool) -> None:
        canon = canonical_key(key)
        is_modifier = canon in MODIFIERS
        hotkey_keys = {canonical_key(k) for k in self._hotkey_keys()}
        added = False
        with self._lock:
            if not self._recording:
                return
            # Teclas principais dos atalhos do app (F6..F9 etc.) não entram na macro.
            if not is_modifier and canon in hotkey_keys:
                if pressed:
                    # Os modificadores segurados fazem parte do atalho: retira da gravação.
                    for mod in list(self._held_keys & MODIFIERS):
                        ev = self._modifier_events.pop(mod, None)
                        if ev is not None and ev in self._events:
                            self._remove_event(ev)
                        self._hotkey_modifiers.add(mod)
                return
            if not pressed and is_modifier and canon in self._hotkey_modifiers:
                self._hotkey_modifiers.discard(canon)
                self._held_keys.discard(canon)
                return
            if pressed:
                if canon in self._held_keys:       # auto-repetição: grava só a 1ª pressão
                    return
                self._held_keys.add(canon)
                ev = MacroEvent.key_down(canon)
                added = self._add(ev)
                if added and is_modifier:
                    self._modifier_events[canon] = ev
            else:
                self._held_keys.discard(canon)
                self._modifier_events.pop(canon, None)
                added = self._add(MacroEvent.key_up(canon))
        if added:
            self._notify()

    def _remove_event(self, event: MacroEvent) -> None:
        """Remove um evento preservando o tempo total (o delay passa ao evento seguinte)."""
        idx = next((i for i, e in enumerate(self._events) if e is event), None)
        if idx is None:
            return
        removed = self._events.pop(idx)
        if idx < len(self._events):
            self._events[idx].delay_ms += removed.delay_ms
        if not self._events:
            self._last_ns = time.perf_counter_ns()

    def _finalize_events(self) -> list[MacroEvent]:
        """Fecha pares abertos (tecla/botão sem soltar) para a macro nunca deixar nada preso."""
        events = self._events
        for key in sorted(self._held_keys - self._hotkey_modifiers):
            events.append(MacroEvent.key_up(key, 0.0))
        for button, (x, y) in self._held_buttons.items():
            events.append(MacroEvent.release(button, x, y, 0.0))
        if events:
            events[0].delay_ms = 0.0
        return events
