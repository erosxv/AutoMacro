import sys
import time

import pytest

from automacro.core.event_bus import EventBus
from automacro.core.session import Session
from automacro.core.timing import set_wait_margin_ns, wait_margin_ns
from automacro.input_handlers.fake_backend import FakeBackend
from automacro.models.settings import AppSettings
from automacro.utils.platform_info import detect_platform, enable_high_resolution_timer


@pytest.fixture(autouse=True)
def _timing_setup():
    """Reproduz o que o app faz ao iniciar.

    Linux: margem fixa (testes determinísticos). Windows: o app pede ao sistema timer de 1 ms
    e calibra a margem medindo o próprio sistema; os testes fazem o mesmo, senão mediriam um
    Windows sem o ajuste (esperas em passos de ~15 ms) que o usuário nunca terá.
    """
    if sys.platform.startswith("win"):
        undo = enable_high_resolution_timer()
        set_wait_margin_ns(None)
        wait_margin_ns()          # calibra agora (o app faz isso ao iniciar), não na 1ª espera
        yield
        undo()
    else:
        set_wait_margin_ns(2_000_000)
        yield
    set_wait_margin_ns(None)


@pytest.fixture
def backend():
    return FakeBackend()


@pytest.fixture
def settings():
    s = AppSettings()
    s.safety.countdown_s = 0.0
    s.safety.failsafe_corner = False
    s.safety.confirm_imported = True
    return s


@pytest.fixture
def events():
    class Collector:
        def __init__(self, bus: EventBus):
            self.items = []
            bus.subscribe(self.items.append)

        def of(self, cls):
            return [e for e in self.items if isinstance(e, cls)]

    return Collector


@pytest.fixture
def session(backend, settings):
    s = Session(backend, settings, EventBus(), platform=detect_platform({}, "linux"))
    yield s
    s.shutdown()


def wait_until(predicate, timeout=3.0, step=0.005):
    end = time.monotonic() + timeout
    while time.monotonic() < end:
        if predicate():
            return True
        time.sleep(step)
    return predicate()
