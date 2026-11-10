"""Gerenciador de atalhos globais.

* Usa **um único** listener de teclado para o aplicativo todo (sem listeners duplicados).
* Combinação exata: ``F9`` não dispara quando Ctrl+Shift estão pressionados, então
  ``F9`` (interromper) e ``Ctrl+Shift+F9`` (emergência) convivem sem ambiguidade.
* Ignora auto-repetição de tecla segurada.
* Teclas enviadas pelo próprio AutoMacro (reprodução) já chegam filtradas pelo backend,
  então uma macro que contém F9 não consegue interromper a si mesma.
"""

from __future__ import annotations

import logging
import queue
import threading
from typing import Callable

from automacro.hotkeys.parser import Hotkey, HotkeyError, find_conflicts, parse_hotkey
from automacro.input_handlers.base import InputListener, ListenerCallbacks
from automacro.input_handlers.keymap import MODIFIERS, canonical_key

log = logging.getLogger(__name__)

_STOP = object()


class HotkeyManager:
    def __init__(self, listener: InputListener) -> None:
        self._listener = listener
        self._lock = threading.RLock()
        self._table: dict[tuple[frozenset[str], str], list[str]] = {}
        self._actions: dict[str, tuple[Callable[[], None], bool]] = {}
        self._held_mods: set[str] = set()
        self._held_keys: set[str] = set()
        self._capture: Callable[[Hotkey | None], None] | None = None
        self._queue: "queue.SimpleQueue" = queue.SimpleQueue()
        self._worker: threading.Thread | None = None
        self._started = False

    # ---- configuração ------------------------------------------------------------------
    def register_action(self, action: str, callback: Callable[[], None],
                        immediate: bool = False) -> None:
        """``immediate=True`` executa na própria thread do listener (use só para o que é
        instantâneo, como a parada de emergência). Os demais rodam em uma thread dedicada."""
        with self._lock:
            self._actions[action] = (callback, immediate)

    def set_bindings(self, bindings: dict[str, str]) -> None:
        """Substitui todos os atalhos. Levanta HotkeyError em atalho inválido ou repetido."""
        conflicts = find_conflicts(bindings)
        if conflicts:
            a, b = conflicts[0]
            raise HotkeyError(f"o mesmo atalho está em uso por duas ações ({a} e {b})")
        table: dict[tuple[frozenset[str], str], list[str]] = {}
        for action, text in bindings.items():
            hk = parse_hotkey(text)
            table.setdefault((hk.modifiers, hk.key), []).append(action)
        with self._lock:
            self._table = table

    # ---- ciclo de vida -----------------------------------------------------------------
    @property
    def running(self) -> bool:
        return self._started and self._listener.running

    def start(self) -> None:
        with self._lock:
            if self._started:
                return
            self._started = True
            self._held_mods.clear()
            self._held_keys.clear()
        self._worker = threading.Thread(target=self._dispatch_loop,
                                        name="automacro-hotkeys-dispatch", daemon=True)
        self._worker.start()
        try:
            self._listener.start(ListenerCallbacks(on_key=self._on_key))
        except Exception:
            self.stop()
            raise

    def stop(self) -> None:
        with self._lock:
            was_started, self._started = self._started, False
            self._capture = None
        try:
            self._listener.stop()
        finally:
            if was_started and self._worker is not None:
                self._queue.put(_STOP)
                if self._worker is not threading.current_thread():
                    self._worker.join(timeout=2.0)
                self._worker = None

    # ---- captura de atalho (tela de configurações) -------------------------------------
    def capture(self, callback: Callable[[Hotkey | None], None]) -> None:
        """A próxima combinação digitada vai para ``callback`` (None se cancelada com Esc)."""
        with self._lock:
            self._capture = callback

    def cancel_capture(self) -> None:
        with self._lock:
            self._capture = None

    # ---- tratamento de teclas ----------------------------------------------------------
    def _on_key(self, key: str, pressed: bool) -> None:
        canon = canonical_key(key)
        if canon in MODIFIERS:
            with self._lock:
                (self._held_mods.add if pressed else self._held_mods.discard)(canon)
            return
        if not pressed:
            with self._lock:
                self._held_keys.discard(canon)
            return

        with self._lock:
            if canon in self._held_keys:       # auto-repetição
                return
            self._held_keys.add(canon)
            mods = frozenset(self._held_mods)
            capture, self._capture = self._capture, None
            actions = [] if capture else list(self._table.get((mods, canon), ()))

        if capture is not None:
            result = None if (canon == "<esc>" and not mods) else Hotkey(mods, canon)
            self._safe(capture, result)
            return
        for action in actions:
            entry = self._actions.get(action)
            if entry is None:
                continue
            callback, immediate = entry
            if immediate:
                self._safe(callback)
            else:
                self._queue.put((action, callback))

    def _dispatch_loop(self) -> None:
        while True:
            item = self._queue.get()
            if item is _STOP:
                return
            action, callback = item
            self._safe(callback)

    @staticmethod
    def _safe(callback: Callable, *args) -> None:
        try:
            callback(*args)
        except Exception:
            log.exception("Erro ao executar ação de atalho")
