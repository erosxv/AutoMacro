"""Backend baseado em pynput (Windows e Linux/X11; parcial em Wayland via XWayland).

O pynput só pode ser importado quando existe um servidor gráfico acessível (no Linux ele
falha ao importar sem ``DISPLAY``). Por isso o import é **tardio** e qualquer falha vira um
relatório de capacidades "indisponível" com o motivo, em vez de derrubar o aplicativo.
"""

from __future__ import annotations

import logging
import time
from types import SimpleNamespace

from automacro.core.errors import InputError
from automacro.input_handlers.base import (
    InjectionTracker,
    InputBackend,
    InputInjector,
    InputListener,
    ListenerCallbacks,
)
from automacro.input_handlers.capabilities import (
    BackendCapabilities,
    Feature,
    FeatureStatus,
    Level,
)
from automacro.utils.platform_info import PlatformInfo, detect_platform

log = logging.getLogger(__name__)

_BUTTON_NAMES = ("left", "right", "middle")


def _load_pynput() -> SimpleNamespace:
    from pynput import keyboard, mouse   # pode lançar ImportError/Exception sem display

    return SimpleNamespace(keyboard=keyboard, mouse=mouse)


def _env_keys() -> set[str]:
    import os

    return {k for k, v in os.environ.items() if v}


_READY_TIMEOUT_S = 3.0


def _wait_ready(listener, timeout: float = _READY_TIMEOUT_S) -> None:
    """Espera (com limite) o listener do pynput ficar pronto para receber eventos.

    ``Listener.wait()`` do pynput não tem timeout e trava se a thread morrer antes de ficar
    pronta; por isso consultamos o estado em vez de chamá-lo.
    """
    ready = getattr(listener, "_ready", None)
    if not isinstance(ready, bool):          # versão do pynput com outro formato interno
        time.sleep(0.15)
        return
    deadline = time.monotonic() + timeout
    while not getattr(listener, "_ready", False):
        if not listener.is_alive():
            raise InputError("a captura de entrada falhou ao iniciar (veja o arquivo de log)")
        if time.monotonic() >= deadline:
            raise InputError("tempo esgotado ao iniciar a captura de mouse/teclado")
        time.sleep(0.002)


# ---- tradução de teclas ---------------------------------------------------------------

def key_to_str(key, kb, platform_os: str = "") -> str | None:
    """pynput -> chave neutra (ver ``keymap``). Retorna None para teclas desconhecidas."""
    if key is None:
        return None
    if isinstance(key, kb.Key):
        return f"<{key.name}>"
    char = getattr(key, "char", None)
    vk = getattr(key, "vk", None)
    if char and len(char) == 1 and ord(char) >= 32:
        return char.lower()
    if vk is not None:
        # No Windows, com Ctrl pressionado o "char" vem como caractere de controle.
        if platform_os == "windows" and (0x41 <= vk <= 0x5A or 0x30 <= vk <= 0x39):
            return chr(vk).lower()
        return f"<vk:{vk}>"
    return None


def str_to_key(name: str, kb):
    """Chave neutra -> objeto aceito pelo ``Controller`` do pynput."""
    if name.startswith("<vk:") and name.endswith(">"):
        try:
            return kb.KeyCode.from_vk(int(name[4:-1]))
        except ValueError:
            raise InputError(f"tecla inválida: {name}") from None
    if name.startswith("<") and name.endswith(">"):
        key = getattr(kb.Key, name[1:-1], None)
        if key is None:
            raise InputError(f"a tecla {name} não existe neste sistema")
        return key
    if len(name) == 1:
        return name
    raise InputError(f"tecla inválida: {name!r}")


class PynputBackend(InputBackend):
    name = "pynput"

    def __init__(self, platform: PlatformInfo | None = None) -> None:
        self.platform = platform or detect_platform()
        self.tracker = InjectionTracker()
        self._mods: SimpleNamespace | None = None
        self._load_error: str | None = None
        self._loaded = False

    # ---- carregamento tardio -----------------------------------------------------------
    def _load(self) -> SimpleNamespace | None:
        if not self._loaded:
            self._loaded = True
            try:
                self._mods = _load_pynput()
            except Exception as exc:   # ImportError, DisplayConnectionError, etc.
                self._load_error = self._explain_load_error(exc)
                log.warning("pynput indisponível: %s", self._load_error)
        return self._mods

    def _explain_load_error(self, exc: Exception) -> str:
        p = self.platform
        log.debug("Detalhe técnico da falha do pynput: %s", exc)    # texto bruto só no log
        if p.is_linux and p.is_wayland and not (p.has_display and "DISPLAY" in _env_keys()):
            return ("sessão Wayland sem XWayland: o Wayland não permite capturar ou enviar "
                    "entrada globalmente a programas comuns. Entre em uma sessão X11 (Xorg) "
                    "na tela de login, ou habilite o XWayland.")
        if p.is_linux and not p.has_display:
            return ("nenhum servidor gráfico acessível (variável DISPLAY ausente). "
                    "Execute dentro de uma sessão gráfica.")
        first_line = str(exc).strip().splitlines()[0] if str(exc).strip() else type(exc).__name__
        return f"falha ao carregar a biblioteca de entrada ({first_line})"

    # ---- InputBackend ------------------------------------------------------------------
    def capabilities(self) -> BackendCapabilities:
        mods = self._load()
        if mods is None:
            return BackendCapabilities.all_unavailable(self.name, self._load_error or "indisponível")

        caps = BackendCapabilities.all_available(self.name)
        p = self.platform
        if p.is_linux and p.is_wayland:
            why = ("Sessão Wayland: o sistema isola a entrada entre aplicativos, então só "
                   "janelas rodando via XWayland são alcançadas. Para suporte completo, "
                   "entre em uma sessão X11 (Xorg) na tela de login.")
            limited = FeatureStatus(Level.LIMITED, why)
            for feature in Feature:
                caps.features[feature] = limited
        if p.is_windows and not p.is_admin:
            caps.notes.append(
                "Programas executados como administrador (e telas de UAC/bloqueio) ignoram "
                "entrada simulada por um programa comum. Para controlá-los, execute o "
                "AutoMacro como administrador."
            )
        if p.os == "macos":
            caps.notes.append("macOS não é um alvo oficial; exige permissão de Acessibilidade.")
        return caps

    def create_injector(self) -> InputInjector:
        mods = self._load()
        if mods is None:
            raise InputError(self._load_error or "backend de entrada indisponível")
        return PynputInjector(mods, self.tracker, self.platform)

    def create_listener(self) -> InputListener:
        mods = self._load()
        if mods is None:
            raise InputError(self._load_error or "backend de entrada indisponível")
        return PynputListener(mods, self.tracker, self.platform)


class PynputInjector(InputInjector):
    def __init__(self, mods: SimpleNamespace, tracker: InjectionTracker,
                 platform: PlatformInfo) -> None:
        super().__init__(tracker)
        self._kb = mods.keyboard
        self._ms = mods.mouse
        self._mouse = mods.mouse.Controller()
        self._keyboard = mods.keyboard.Controller()
        self._buttons = {name: getattr(mods.mouse.Button, name) for name in _BUTTON_NAMES}

    def _button(self, name: str):
        try:
            return self._buttons[name]
        except KeyError:
            raise InputError(f"botão do mouse desconhecido: {name!r}") from None

    def _move_to(self, x, y):
        self._mouse.position = (x, y)

    def _mouse_down(self, button):
        self._mouse.press(self._button(button))

    def _mouse_up(self, button):
        self._mouse.release(self._button(button))

    def _scroll(self, dx, dy):
        self._mouse.scroll(dx, dy)

    def _key_down(self, key):
        self._keyboard.press(str_to_key(key, self._kb))

    def _key_up(self, key):
        self._keyboard.release(str_to_key(key, self._kb))

    def _position(self):
        pos = self._mouse.position
        return (int(pos[0]), int(pos[1]))


class PynputListener(InputListener):
    def __init__(self, mods: SimpleNamespace, tracker: InjectionTracker,
                 platform: PlatformInfo) -> None:
        self._kb = mods.keyboard
        self._ms = mods.mouse
        self._tracker = tracker
        self._os = platform.os
        self._mouse_listener = None
        self._key_listener = None
        self._running = False

    @property
    def running(self) -> bool:
        return self._running

    def start(self, callbacks: ListenerCallbacks) -> None:
        if self._running:
            raise InputError("listener já iniciado")
        self._running = True
        try:
            if callbacks.wants_mouse:
                self._mouse_listener = self._ms.Listener(
                    on_move=self._wrap_move(callbacks),
                    on_click=self._wrap_click(callbacks),
                    on_scroll=self._wrap_scroll(callbacks),
                )
                self._mouse_listener.start()
            if callbacks.wants_keyboard:
                self._key_listener = self._kb.Listener(
                    on_press=self._wrap_key(callbacks, True),
                    on_release=self._wrap_key(callbacks, False),
                )
                self._key_listener.start()
            # O pynput devolve o controle de start() antes de a captura estar de fato ativa;
            # só consideramos "iniciado" quando estiver, senão os primeiros cliques se perdem.
            for listener in (self._mouse_listener, self._key_listener):
                if listener is not None:
                    _wait_ready(listener)
        except Exception:
            self.stop()
            raise

    def stop(self) -> None:
        self._running = False
        for attr in ("_mouse_listener", "_key_listener"):
            listener = getattr(self, attr)
            setattr(self, attr, None)
            if listener is not None:
                try:
                    listener.stop()
                    listener.join(timeout=1.0)
                except Exception:
                    log.exception("Erro ao parar listener")

    # Um callback que lança exceção encerra o listener do pynput; por isso tudo é protegido.
    def _wrap_move(self, cb: ListenerCallbacks):
        def handler(x, y, *_):
            if cb.on_move and self._running:
                try:
                    cb.on_move(int(x), int(y))
                except Exception:
                    log.exception("Erro no callback de movimento")
        return handler

    def _wrap_click(self, cb: ListenerCallbacks):
        def handler(x, y, button, pressed, *_):
            name = getattr(button, "name", None)
            if name not in _BUTTON_NAMES or not (cb.on_click and self._running):
                return
            try:
                cb.on_click(int(x), int(y), name, bool(pressed))
            except Exception:
                log.exception("Erro no callback de clique")
        return handler

    def _wrap_scroll(self, cb: ListenerCallbacks):
        def handler(x, y, dx, dy, *_):
            if cb.on_scroll and self._running:
                try:
                    cb.on_scroll(int(x), int(y), int(dx), int(dy))
                except Exception:
                    log.exception("Erro no callback de rolagem")
        return handler

    def _wrap_key(self, cb: ListenerCallbacks, pressed: bool):
        def handler(key, *_):
            if not (cb.on_key and self._running):
                return
            try:
                name = key_to_str(key, self._kb, self._os)
                if name is None or self._tracker.consume(name, pressed):
                    return
                cb.on_key(name, pressed)
            except Exception:
                log.exception("Erro no callback de teclado")
        return handler
