import threading
import time

import pytest

from automacro.core.errors import BusyError, ConfirmationRequired, FeatureUnavailableError
from automacro.core.event_bus import (
    ActivityFinished,
    ClickCount,
    Notice,
    Progress,
    RecordingFinished,
)
from automacro.input_handlers.capabilities import (
    BackendCapabilities,
    Feature,
    FeatureStatus,
    Level,
)
from automacro.input_handlers.fake_backend import FakeBackend
from automacro.models.events import EventType, MacroEvent
from automacro.models.macro import Macro
from automacro.models.settings import AutoClickConfig, PlayerSettings
from automacro.models.state import AppState

from conftest import wait_until


def idle(session):
    return wait_until(lambda: session.state is AppState.IDLE)


# ---------------------------------------------------------------- Auto Clicker
def test_autoclick_fixed_count(session, backend):
    cfg = AutoClickConfig(button="right", interval_ms=5, count=10, use_fixed_position=True, x=50, y=60)
    session.start_autoclick(cfg)
    assert idle(session)
    names = backend.names()
    assert names.count("mouse_down") == 10 and names.count("mouse_up") == 10
    assert all(a.args == ("right",) for a in backend.actions if a.name == "mouse_down")
    assert ("move" in names) and backend.position == (50, 60)


def test_autoclick_interval_is_accurate(session, backend):
    session.start_autoclick(AutoClickConfig(interval_ms=20, count=15))
    assert idle(session)
    t = [a.t_ns for a in backend.actions if a.name == "mouse_down"]
    gaps = [(b - a) / 1e6 for a, b in zip(t, t[1:])]
    avg = sum(gaps) / len(gaps)
    assert 18.5 < avg < 21.5, avg


def test_autoclick_infinite_stops_promptly(session, backend, events):
    ev = events(session.bus)
    session.start_autoclick(AutoClickConfig(interval_ms=10, count=0))
    assert wait_until(lambda: session.state is AppState.AUTOCLICKING)
    time.sleep(0.1)
    started = time.perf_counter()
    assert session.stop(wait=True)
    assert time.perf_counter() - started < 0.5
    assert session.state is AppState.IDLE
    assert ev.of(ActivityFinished)[-1].cancelled is True
    assert backend.names().count("mouse_down") == backend.names().count("mouse_up")


def test_autoclick_max_runtime(session, backend):
    session.start_autoclick(AutoClickConfig(interval_ms=10, count=0, max_runtime_s=0.15))
    assert idle(session)
    assert 5 <= backend.names().count("mouse_down") <= 20


def test_autoclick_huge_interval_still_cancels_instantly(session):
    session.start_autoclick(AutoClickConfig(interval_ms=60_000 * 60, count=0))
    assert wait_until(lambda: session.state is AppState.AUTOCLICKING)
    time.sleep(0.05)
    started = time.perf_counter()
    session.stop(wait=True)
    assert time.perf_counter() - started < 0.5


def test_autoclick_toggle(session):
    session.toggle_autoclick()
    assert wait_until(lambda: session.state is AppState.AUTOCLICKING)
    session.toggle_autoclick()
    assert idle(session)


# ---------------------------------------------------------------- Exclusão mútua
def test_no_concurrent_activities(session):
    session.start_autoclick(AutoClickConfig(interval_ms=50, count=0))
    assert wait_until(lambda: session.state is AppState.AUTOCLICKING)
    macro = Macro("m", [MacroEvent.key_down("a"), MacroEvent.key_up("a", 10)])
    with pytest.raises(BusyError):
        session.play(macro)
    with pytest.raises(BusyError):
        session.start_recording()
    with pytest.raises(BusyError):
        session.start_autoclick()
    session.stop(wait=True)
    assert idle(session)


def test_no_playback_during_recording(session):
    session.start_recording()
    assert wait_until(lambda: session.state is AppState.RECORDING)
    with pytest.raises(BusyError, match="gravação"):
        session.play(Macro("m", [MacroEvent.key_down("a")]))
    session.stop(wait=True)


# ---------------------------------------------------------------- Gravação
def test_recording_captures_events_and_delays(session, backend, events):
    ev = events(session.bus)
    session.settings.recorder.record_mouse_moves = True
    session.settings.recorder.move_min_distance_px = 0
    session.settings.recorder.move_min_interval_ms = 1
    session.start_recording()
    assert wait_until(lambda: session.state is AppState.RECORDING)
    backend.simulate_move(10, 10)
    time.sleep(0.05)
    backend.simulate_click(10, 10, "left", True)
    time.sleep(0.03)
    backend.simulate_click(10, 10, "left", False)
    backend.simulate_scroll(10, 10, 0, -2)
    backend.simulate_key("a", True)
    time.sleep(0.02)
    backend.simulate_key("a", False)
    session.stop_recording()
    assert wait_until(lambda: ev.of(RecordingFinished))
    macro = ev.of(RecordingFinished)[0].macro
    kinds = [e.type for e in macro.events]
    assert kinds == [EventType.MOUSE_MOVE, EventType.MOUSE_PRESS, EventType.MOUSE_RELEASE,
                     EventType.MOUSE_SCROLL, EventType.KEY_DOWN, EventType.KEY_UP]
    assert macro.events[0].delay_ms == 0
    assert 35 < macro.events[1].delay_ms < 120
    assert 20 < macro.events[2].delay_ms < 90
    assert macro.events[1].button == "left" and (macro.events[1].x, macro.events[1].y) == (10, 10)
    assert backend.active_listeners == 0


def test_recording_ignores_app_hotkeys_and_their_modifiers(session, backend, events):
    ev = events(session.bus)
    session.start_recording()
    assert wait_until(lambda: session.state is AppState.RECORDING)
    backend.simulate_key("x", True)
    backend.simulate_key("x", False)
    # usuário aperta Ctrl+Shift+F9 e depois F7 (finalizar)
    for k in ("<ctrl>", "<shift>", "<f9>"):
        backend.simulate_key(k, True)
    for k in ("<f9>", "<shift>", "<ctrl>"):
        backend.simulate_key(k, False)
    backend.simulate_key("<f7>", True)
    backend.simulate_key("<f7>", False)
    session.stop_recording()
    assert wait_until(lambda: ev.of(RecordingFinished))
    keys = [(e.type.value, e.key) for e in ev.of(RecordingFinished)[0].macro.events]
    assert keys == [("key_down", "x"), ("key_up", "x")]


def test_recording_closes_open_keys_and_buttons(session, backend, events):
    ev = events(session.bus)
    session.start_recording()
    assert wait_until(lambda: session.state is AppState.RECORDING)
    backend.simulate_key("<shift>", True)
    backend.simulate_click(5, 6, "left", True)
    session.stop(wait=True)
    macro = ev.of(RecordingFinished)[0].macro
    assert [e.type for e in macro.events][-2:] == [EventType.KEY_UP, EventType.MOUSE_RELEASE] \
        or {e.type for e in macro.events[-2:]} == {EventType.KEY_UP, EventType.MOUSE_RELEASE}


def test_recording_filters_mouse_moves_by_default(session, backend, events):
    ev = events(session.bus)
    session.start_recording()
    assert wait_until(lambda: session.state is AppState.RECORDING)
    for i in range(50):
        backend.simulate_move(i, i)
    session.stop(wait=True)
    assert ev.of(RecordingFinished)[0].macro.events == []


# ---------------------------------------------------------------- Reprodução
def make_macro():
    return Macro("m", [
        MacroEvent.move(5, 5, 0),
        MacroEvent.press("left", 5, 5, 30),
        MacroEvent.release("left", 5, 5, 30),
        MacroEvent.key_down("a", 30),
        MacroEvent.key_up("a", 30),
    ])


def test_playback_preserves_original_timing(session, backend):
    session.play(make_macro())
    assert idle(session)
    acts = backend.actions
    start = acts[0].t_ns
    assert backend.names() == ["move", "move", "mouse_down", "move", "mouse_up", "key_down", "key_up"]
    offsets = [(a.t_ns - start) / 1e6 for a in acts if a.name in ("move", "mouse_down", "mouse_up", "key_down", "key_up")]
    down = next((a.t_ns - start) / 1e6 for a in acts if a.name == "mouse_down")
    key_up = next((a.t_ns - start) / 1e6 for a in acts if a.name == "key_up")
    assert 27 < down < 36
    assert 117 < key_up < 130


def test_playback_speed(session, backend):
    session.play(make_macro(), PlayerSettings(speed=4.0))
    assert idle(session)
    acts = backend.actions
    assert (acts[-1].t_ns - acts[0].t_ns) / 1e6 < 60      # 120 ms / 4 = 30 ms (+folga)


def test_playback_repeat_and_progress(session, backend, events):
    ev = events(session.bus)
    session.play(make_macro(), PlayerSettings(speed=10, repeat=3))
    assert idle(session)
    assert backend.names().count("key_down") == 3
    last = ev.of(Progress)[-1]
    assert (last.done, last.total, last.loop, last.loops) == (5, 5, 3, 3)


def test_playback_infinite_then_stop(session, backend):
    session.play(make_macro(), PlayerSettings(speed=10, repeat=0))
    assert wait_until(lambda: backend.names().count("key_down") >= 3)
    session.stop(wait=True)
    assert session.state is AppState.IDLE
    n = len(backend.actions)
    time.sleep(0.1)
    assert len(backend.actions) == n                       # nada acontece depois de parar


def test_pause_resume_and_stop_while_paused(session, backend):
    slow = Macro("m", [MacroEvent.key_down("a", 0), MacroEvent.key_up("a", 150)])
    session.play(slow)
    assert wait_until(lambda: backend.names().count("key_down") == 1)
    assert session.pause_playback()
    assert session.state is AppState.PAUSED
    time.sleep(0.3)
    assert backend.names().count("key_up") == 0            # pausado: nada executa
    assert session.resume_playback()
    assert wait_until(lambda: backend.names().count("key_up") == 1)
    assert idle(session)

    session.play(slow)
    assert wait_until(lambda: session.state is AppState.PLAYING)
    session.pause_playback()
    session.stop(wait=True)
    assert session.state is AppState.IDLE


def test_stop_during_playback_releases_held_keys(session, backend):
    macro = Macro("m", [MacroEvent.key_down("<shift>", 0), MacroEvent.press("left", 1, 1, 0),
                        MacroEvent.key_up("<shift>", 5000)])
    session.play(macro)
    assert wait_until(lambda: "mouse_down" in backend.names())
    session.stop(wait=True)
    names = backend.names()
    assert names.count("key_up") == 1 and names.count("mouse_up") == 1   # nada ficou preso


def test_backend_failure_stops_safely_and_reports(session, events):
    fake = FakeBackend(fail_after=3)
    session.backend = fake
    ev = events(session.bus)
    macro = Macro("m", [MacroEvent.key_down("a", 0), MacroEvent.key_down("b", 1),
                        MacroEvent.key_down("c", 1), MacroEvent.key_down("d", 1)])
    session.play(macro)
    assert idle(session)
    assert any(n.level == "error" for n in ev.of(Notice))
    assert ev.of(ActivityFinished)[-1].error
    session.play(Macro("ok", [MacroEvent.move(1, 1)]))    # a sessão continua utilizável


def test_empty_macro_rejected(session):
    from automacro.core.errors import AutoMacroError
    with pytest.raises(AutoMacroError, match="vazia"):
        session.play(Macro("vazia", []))


def test_imported_macro_requires_confirmation(session, backend):
    m = make_macro()
    m.imported = True
    with pytest.raises(ConfirmationRequired):
        session.play(m)
    assert backend.actions == []
    session.play(m, confirmed=True)
    assert idle(session)
    assert backend.names().count("key_down") == 1


def test_max_playback_time(session, backend, settings):
    settings.safety.max_playback_minutes = 1
    session.play(make_macro(), PlayerSettings(speed=10, repeat=0))
    assert wait_until(lambda: backend.names().count("key_down") >= 2)
    session.stop(wait=True)


# ---------------------------------------------------------------- Emergência / contagem
def test_emergency_stop_cancels_everything_fast(session, backend, events):
    ev = events(session.bus)
    session.play(Macro("m", [MacroEvent.key_down("a", 0), MacroEvent.key_up("a", 60_000)]))
    assert wait_until(lambda: backend.names().count("key_down") == 1)
    started = time.perf_counter()
    session.emergency_stop()
    assert idle(session)
    assert time.perf_counter() - started < 0.5
    assert backend.names().count("key_up") == 1            # tecla solta
    assert any("emergência" in n.text for n in ev.of(Notice))


def test_emergency_hotkey_end_to_end(session, backend):
    session.settings.hotkeys.emergency = "Ctrl+Shift+F9"
    assert session.start_hotkeys()
    session.start_autoclick(AutoClickConfig(interval_ms=10, count=0))
    assert wait_until(lambda: session.state is AppState.AUTOCLICKING)
    for k in ("<ctrl>", "<shift>", "<f9>"):
        backend.simulate_key(k, True)
    assert idle(session)


def test_all_hotkeys_drive_session(session, backend):
    macro = make_macro()
    session.set_current_macro(macro)
    assert session.start_hotkeys()
    backend.simulate_key("<f8>", True); backend.simulate_key("<f8>", False)
    assert wait_until(lambda: "key_down" in backend.names())
    assert idle(session)
    backend.simulate_key("<f6>", True); backend.simulate_key("<f6>", False)
    assert wait_until(lambda: session.state is AppState.RECORDING)
    backend.simulate_key("<f7>", True); backend.simulate_key("<f7>", False)
    assert idle(session)
    assert session.last_recording is not None


def test_countdown_then_start_and_cancel_during_countdown(session, backend, settings, events):
    from automacro.core.event_bus import Countdown
    ev = events(session.bus)
    settings.safety.countdown_s = 2.0
    session.start_autoclick(AutoClickConfig(interval_ms=10, count=3))
    assert session.state is AppState.COUNTDOWN
    time.sleep(0.2)
    session.stop(wait=True)
    assert idle(session)
    assert backend.actions == []                           # cancelou antes de agir
    assert [c.remaining for c in ev.of(Countdown)][:1] == [2]


@pytest.mark.parametrize("activity", ["autoclick", "play", "record"])
def test_countdown_completes_into_active_state(session, backend, settings, activity):
    """Depois da contagem a atividade precisa chegar ao estado final (nenhuma transição
    inválida pode ser engolida em silêncio)."""
    settings.safety.countdown_s = 0.2
    target = {"autoclick": AppState.AUTOCLICKING, "play": AppState.PLAYING,
              "record": AppState.RECORDING}[activity]
    if activity == "autoclick":
        session.start_autoclick(AutoClickConfig(interval_ms=10, count=0))
    elif activity == "play":
        session.play(Macro("m", [MacroEvent.key_down("a", 0), MacroEvent.key_up("a", 5000)]))
    else:
        session.start_recording()
    assert session.state is AppState.COUNTDOWN
    assert wait_until(lambda: session.state is target, timeout=2)
    session.stop(wait=True)
    assert idle(session)


def test_every_state_transition_used_is_allowed():
    """A tabela de transições deve permitir todo caminho que a sessão percorre."""
    from automacro.models.state import can_transition
    for target in (AppState.AUTOCLICKING, AppState.PLAYING, AppState.RECORDING):
        assert can_transition(AppState.COUNTDOWN, target)
        assert can_transition(target, AppState.STOPPING)
    assert can_transition(AppState.STOPPING, AppState.IDLE)
    assert can_transition(AppState.PLAYING, AppState.PAUSED)
    assert can_transition(AppState.PAUSED, AppState.PLAYING)


def test_failsafe_corner_blocks_start_and_triggers(session, backend, settings):
    from automacro.core.errors import AutoMacroError
    settings.safety.failsafe_corner = True
    backend.position = (0, 0)
    with pytest.raises(AutoMacroError, match="canto"):
        session.start_autoclick(AutoClickConfig(interval_ms=10, count=0))
    with pytest.raises(AutoMacroError, match="canto"):
        session.start_autoclick(AutoClickConfig(use_fixed_position=True, x=0, y=0))

    backend.position = (300, 300)
    session.start_autoclick(AutoClickConfig(interval_ms=10, count=0))
    assert wait_until(lambda: session.state is AppState.AUTOCLICKING)
    backend.position = (0, 0)                               # usuário joga o mouse no canto
    assert wait_until(lambda: session.state is AppState.IDLE, timeout=2)


# ---------------------------------------------------------------- Capacidades / SO
def test_unavailable_feature_reports_reason(settings):
    from automacro.core.session import Session
    caps = BackendCapabilities.all_available("fake")
    caps.features[Feature.INJECT] = FeatureStatus(Level.UNAVAILABLE, "Wayland isola a entrada")
    caps.features[Feature.HOTKEYS] = FeatureStatus(Level.UNAVAILABLE, "sem atalhos no Wayland")
    s = Session(FakeBackend(caps), settings)
    try:
        with pytest.raises(FeatureUnavailableError, match="Wayland isola"):
            s.start_autoclick()
        notices = []
        s.bus.subscribe(notices.append)
        assert s.start_hotkeys() is False
        assert any(isinstance(n, Notice) and "sem atalhos" in n.text for n in notices)
        assert caps.problem_lines()
    finally:
        s.shutdown()


def test_shutdown_stops_everything_and_is_idempotent(backend, settings):
    from automacro.core.session import Session
    s = Session(backend, settings)
    s.start_hotkeys()
    s.start_autoclick(AutoClickConfig(interval_ms=10, count=0))
    assert wait_until(lambda: s.state is AppState.AUTOCLICKING)
    s.shutdown()
    s.shutdown()
    assert s.state is AppState.IDLE
    assert backend.active_listeners == 0
    assert not [t for t in threading.enumerate() if t.name.startswith("automacro-") and t.is_alive()]


def test_many_start_stop_cycles_leave_no_threads_or_listeners(session, backend):
    for _ in range(25):
        session.start_recording()
        assert wait_until(lambda: session.state is AppState.RECORDING)
        session.stop(wait=True)
        assert idle(session)
    assert backend.active_listeners == 0
    assert not [t for t in threading.enumerate() if t.name in ("automacro-record",) and t.is_alive()]


def test_clickcount_events_published(session, events):
    ev = events(session.bus)
    session.start_autoclick(AutoClickConfig(interval_ms=5, count=7))
    assert idle(session)
    assert ev.of(ClickCount)[-1].count == 7
