"""Teste de fumaça da interface: janela real (Qt offscreen) + backend falso.

Verifica que a UI monta, reage aos estados do núcleo (via ponte de sinais) e que o fluxo
gravar -> salvar -> reproduzir funciona de ponta a ponta sem tocar no mouse real.
"""

import os
import time

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
pytest.importorskip("PySide6")

from PySide6.QtWidgets import QApplication  # noqa: E402

from automacro.core.event_bus import EventBus  # noqa: E402
from automacro.core.session import Session  # noqa: E402
from automacro.input_handlers.fake_backend import FakeBackend  # noqa: E402
from automacro.models.settings import AppSettings  # noqa: E402
from automacro.models.state import AppState  # noqa: E402
from automacro.storage.repository import MacroRepository  # noqa: E402
from automacro.storage.settings_store import SettingsStore  # noqa: E402
from automacro.ui.bridge import SessionBridge  # noqa: E402
from automacro.ui.context import AppContext  # noqa: E402
from automacro.ui.main_window import MainWindow  # noqa: E402
from automacro.utils.paths import AppPaths  # noqa: E402
from automacro.utils.platform_info import detect_platform  # noqa: E402

SHOTS = os.environ.get("AUTOMACRO_SHOTS")   # pasta opcional para salvar capturas


@pytest.fixture(scope="module")
def qapp():
    return QApplication.instance() or QApplication([])


def pump(app, predicate, timeout=3.0):
    end = time.monotonic() + timeout
    while time.monotonic() < end:
        app.processEvents()
        if predicate():
            return True
        time.sleep(0.01)
    app.processEvents()
    return predicate()


@pytest.fixture
def ui(qapp, tmp_path):
    paths = AppPaths.under(tmp_path).ensure()
    settings = AppSettings()
    settings.safety.countdown_s = 0.0
    settings.safety.failsafe_corner = False
    backend = FakeBackend()
    bus = EventBus()
    session = Session(backend, settings, bus, detect_platform({}, "linux"))
    ctx = AppContext(session, MacroRepository(paths.macros_dir),
                     SettingsStore(paths.config_file), paths, SessionBridge(bus))
    window = MainWindow(ctx)
    window.show()
    qapp.processEvents()
    yield qapp, window, ctx, backend
    ctx.bridge.close()
    session.shutdown()
    window.close()


def shot(window, name):
    if SHOTS:
        os.makedirs(SHOTS, exist_ok=True)
        window.grab().save(os.path.join(SHOTS, f"{name}.png"))


def test_window_builds_with_all_tabs(ui):
    app, window, ctx, _ = ui
    assert window.tabs.count() == 5
    assert [window.tabs.tabText(i) for i in range(5)] == [
        "Auto Clicker", "Gravador", "Reprodutor", "Biblioteca", "Configurações"]
    for i in range(window.tabs.count()):
        window.tabs.setCurrentIndex(i)
        app.processEvents()
        assert not window.grab().isNull()
        shot(window, f"aba{i}_{window.tabs.tabText(i).replace(' ', '_')}")
    assert window.emergency.isEnabled()


def test_autoclick_reflected_in_ui_and_emergency_button_stops(ui):
    app, window, ctx, backend = ui
    ctx.settings.autoclick.interval_ms = 5
    ctx.settings.autoclick.count = 0           # infinito
    ctx.session.start_autoclick()
    assert pump(app, lambda: ctx.session.state is AppState.AUTOCLICKING)
    assert pump(app, lambda: backend.names().count("mouse_up") > 3)
    shot(window, "autoclick_ativo")
    window.emergency.click()                   # botão de emergência da janela
    assert pump(app, lambda: ctx.session.state is AppState.IDLE)
    before = len(backend.actions)
    time.sleep(0.1)
    assert len(backend.actions) == before      # nada continua clicando


def test_record_save_play_flow_through_ui(ui):
    app, window, ctx, backend = ui
    ctx.session.start_recording()
    assert pump(app, lambda: ctx.session.state is AppState.RECORDING)
    backend.simulate_click(120, 80, "left", True)
    time.sleep(0.03)
    backend.simulate_click(120, 80, "left", False)
    backend.simulate_key("a", True)
    backend.simulate_key("a", False)
    assert pump(app, lambda: window.recorder.count.text() == "4")
    window.recorder.stop_btn.click()
    assert pump(app, lambda: window.recorder._pending is not None)
    shot(window, "gravacao_concluida")

    window.recorder.name.setText("Teste UI")
    window.recorder.save_btn.click()
    app.processEvents()
    infos = ctx.repo.list()
    assert [i.name for i in infos] == ["Teste UI"]
    assert infos[0].event_count == 4

    window.tabs.setCurrentIndex(3)
    app.processEvents()
    shot(window, "biblioteca")

    macro = ctx.repo.load(infos[0].id)
    backend.clear_actions()
    ctx.session.play(macro)
    assert pump(app, lambda: backend.names().count("key_up") == 1)
    assert pump(app, lambda: ctx.session.state is AppState.IDLE)
    # Cada clique gravado com coordenadas move o cursor até elas antes de pressionar/soltar.
    assert backend.names() == ["move", "mouse_down", "move", "mouse_up", "key_down", "key_up"]
    assert [a.args for a in backend.actions if a.name == "move"] == [(120, 80), (120, 80)]


def test_environment_banner_reports_unavailable_features(qapp, tmp_path):
    from automacro.input_handlers.capabilities import BackendCapabilities

    paths = AppPaths.under(tmp_path).ensure()
    caps = BackendCapabilities.all_unavailable("fake", "Wayland: o sistema bloqueia a entrada global")
    bus = EventBus()
    session = Session(FakeBackend(caps), AppSettings(), bus, detect_platform({}, "linux"))
    ctx = AppContext(session, MacroRepository(paths.macros_dir),
                     SettingsStore(paths.config_file), paths, SessionBridge(bus))
    window = MainWindow(ctx)
    window.show()
    qapp.processEvents()
    assert "Wayland" in window.banner_text.text()
    shot(window, "limitacao_sistema")
    ctx.bridge.close()
    session.shutdown()
    window.close()
