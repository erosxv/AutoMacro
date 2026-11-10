"""Testes com o backend REAL (pynput) em um servidor X de verdade.

Rodam apenas se houver DISPLAY (ex.: ``xvfb-run -a pytest``); caso contrário são pulados.
"""

import os
import sys

import pytest

from automacro.core.event_bus import EventBus, RecordingFinished
from automacro.core.session import Session
from automacro.input_handlers.pynput_backend import PynputBackend
from automacro.models.events import EventType
from automacro.models.settings import AppSettings, AutoClickConfig
from automacro.models.state import AppState
from automacro.utils.platform_info import detect_platform

from conftest import wait_until

pytestmark = [
    pytest.mark.x11,
    pytest.mark.skipif(not sys.platform.startswith("linux") or not os.environ.get("DISPLAY"),
                       reason="requer Linux com servidor X (use xvfb-run)"),
]


def start_ready(listener, timeout=3.0):
    """Inicia um listener do pynput e espera ele estar de fato capturando."""
    import time
    listener.start()
    end = time.monotonic() + timeout
    while not listener._ready and time.monotonic() < end:
        time.sleep(0.002)
    assert listener._ready
    return listener


@pytest.fixture
def real_session():
    settings = AppSettings()
    settings.safety.countdown_s = 0
    settings.safety.failsafe_corner = False
    backend = PynputBackend(detect_platform())
    session = Session(backend, settings, EventBus())
    yield session, backend
    session.shutdown()


def test_capabilities_available_on_x11(real_session):
    _, backend = real_session
    caps = backend.capabilities()
    assert caps.backend_name == "pynput"
    assert not caps.problems()


def test_real_click_roundtrip_record_and_play(real_session):
    session, backend = real_session
    events = []
    session.bus.subscribe(events.append)

    session.start_recording()
    assert wait_until(lambda: session.state is AppState.RECORDING)

    # "Usuário" simulado: Controllers crus do pynput, independentes do app. (O injetor do
    # app NÃO serve aqui: o filtro anti-eco descarta, de propósito, o que o próprio app envia.)
    from pynput import keyboard, mouse as pmouse
    ptr, kbd = pmouse.Controller(), keyboard.Controller()
    ptr.position = (120, 90)
    ptr.click(pmouse.Button.left)
    kbd.press("a"); kbd.release("a")
    wait_until(lambda: any(e.type is EventType.KEY_UP for e in session.last_recording.events)
               if session.last_recording else False, timeout=0.3)
    session.stop(wait=True)

    macro = next(e.macro for e in events if isinstance(e, RecordingFinished))
    kinds = [e.type for e in macro.events]
    assert EventType.MOUSE_PRESS in kinds and EventType.MOUSE_RELEASE in kinds
    assert EventType.KEY_DOWN in kinds
    press = next(e for e in macro.events if e.type is EventType.MOUSE_PRESS)
    assert (press.x, press.y) == (120, 90)

    # reproduz de volta e confere que o servidor recebeu os cliques
    seen = []
    from pynput import mouse
    listener = start_ready(mouse.Listener(on_click=lambda x, y, b, p: seen.append((x, y, p))))
    try:
        session.play(macro)
        assert wait_until(lambda: session.state is AppState.IDLE, timeout=5)
        assert wait_until(lambda: (120, 90, True) in seen), f"capturados: {seen}"
    finally:
        listener.stop()


def test_real_autoclick(real_session):
    session, backend = real_session
    from pynput import mouse
    seen = []
    def on_click(x, y, button, pressed):
        # Atenção: o pynput PARA o listener se o callback devolver False.
        if pressed:
            seen.append((x, y, button.name))

    listener = start_ready(mouse.Listener(on_click=on_click))
    try:
        session.start_autoclick(AutoClickConfig(button="middle", interval_ms=10, count=5,
                                                use_fixed_position=True, x=200, y=150))
        assert wait_until(lambda: session.state is AppState.IDLE, timeout=5)
        assert wait_until(lambda: len(seen) == 5), f"capturados: {seen}"
        assert all(s == (200, 150, "middle") for s in seen)
    finally:
        listener.stop()


def test_real_hotkey_and_no_self_trigger(real_session):
    session, backend = real_session
    assert session.start_hotkeys()
    from pynput import keyboard
    kbd = keyboard.Controller()                             # "usuário" real, não o injetor do app
    session.start_autoclick(AutoClickConfig(interval_ms=20, count=0))
    assert wait_until(lambda: session.state is AppState.AUTOCLICKING)
    kbd.press(keyboard.Key.f9); kbd.release(keyboard.Key.f9)   # F9 = interromper
    assert wait_until(lambda: session.state is AppState.IDLE, timeout=3)
