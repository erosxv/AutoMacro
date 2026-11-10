import pytest

from automacro.hotkeys.manager import HotkeyManager
from automacro.hotkeys.parser import HotkeyError, find_conflicts, normalize_hotkey, parse_hotkey
from automacro.input_handlers.fake_backend import FakeBackend

from conftest import wait_until


@pytest.mark.parametrize("text,expected", [
    ("f6", "F6"), ("ctrl+shift+f9", "Ctrl+Shift+F9"), ("Shift + Ctrl + F9", "Ctrl+Shift+F9"),
    ("Win+E", "Win+E"), ("control+alt+delete", "Ctrl+Alt+Delete"), ("Ctrl++", "Ctrl++"),
    ("esc", "Esc"), ("Ctrl+Page Up", "Ctrl+Page Up"),
])
def test_normalize(text, expected):
    assert normalize_hotkey(text) == expected


@pytest.mark.parametrize("bad", ["", "   ", "Ctrl", "Ctrl+Shift", "A+B", "F99", "Ctrl+Foo", "+ +"])
def test_invalid(bad):
    with pytest.raises(HotkeyError):
        parse_hotkey(bad)


def test_conflicts():
    assert find_conflicts({"a": "F6", "b": "f6", "c": "F7"}) == [("a", "b")]


def make(backend: FakeBackend, bindings):
    manager = HotkeyManager(backend.create_listener())
    hits = []
    for action in bindings:
        manager.register_action(action, lambda a=action: hits.append(a))
    manager.set_bindings(bindings)
    manager.start()
    return manager, hits


def press(backend, *keys):
    for k in keys:
        backend.simulate_key(k, True)
    for k in reversed(keys):
        backend.simulate_key(k, False)


def test_fires_only_on_exact_modifiers(backend):
    manager, hits = make(backend, {"stop": "F9", "emergency": "Ctrl+Shift+F9"})
    try:
        press(backend, "<f9>")
        assert wait_until(lambda: hits == ["stop"])
        press(backend, "<ctrl_l>", "<shift>", "<f9>")
        assert wait_until(lambda: hits == ["stop", "emergency"])
        press(backend, "<ctrl>", "<f9>")           # Ctrl+F9 não está registrado
        press(backend, "<f8>")
        assert hits == ["stop", "emergency"]
    finally:
        manager.stop()


def test_autorepeat_ignored(backend):
    manager, hits = make(backend, {"stop": "F9"})
    try:
        for _ in range(5):
            backend.simulate_key("<f9>", True)       # tecla segurada
        backend.simulate_key("<f9>", False)
        assert wait_until(lambda: hits == ["stop"])
        assert hits == ["stop"]
    finally:
        manager.stop()


def test_injected_keys_never_trigger_hotkeys(backend):
    manager, hits = make(backend, {"stop": "F9"})
    try:
        injector = backend.create_injector()
        backend.loopback = True
        injector.key_down("<f9>")
        injector.key_up("<f9>")
        backend.loopback = False
        press(backend, "<f9>")                         # este sim é do usuário
        assert wait_until(lambda: hits == ["stop"])
        assert hits == ["stop"]
    finally:
        manager.stop()


def test_capture_next_combination(backend):
    manager, hits = make(backend, {"stop": "F9"})
    got = []
    try:
        manager.capture(got.append)
        press(backend, "<ctrl>", "<alt>", "k")
        assert wait_until(lambda: len(got) == 1)
        assert str(got[0]) == "Ctrl+Alt+K"
        assert hits == []                               # a captura não dispara ações

        manager.capture(got.append)
        press(backend, "<esc>")
        assert wait_until(lambda: len(got) == 2)
        assert got[1] is None                           # Esc cancela
    finally:
        manager.stop()


def test_duplicate_bindings_rejected(backend):
    manager = HotkeyManager(backend.create_listener())
    with pytest.raises(HotkeyError):
        manager.set_bindings({"a": "F6", "b": "f6"})


def test_single_listener_and_clean_stop(backend):
    manager, _ = make(backend, {"stop": "F9"})
    assert backend.active_listeners == 1
    manager.stop()
    manager.stop()                                      # idempotente
    assert backend.active_listeners == 0


def test_failing_callback_does_not_break_manager(backend):
    manager = HotkeyManager(backend.create_listener())
    hits = []
    manager.register_action("boom", lambda: 1 / 0)
    manager.register_action("ok", lambda: hits.append("ok"))
    manager.set_bindings({"boom": "F1", "ok": "F2"})
    manager.start()
    try:
        press(backend, "<f1>")
        press(backend, "<f2>")
        assert wait_until(lambda: hits == ["ok"])
    finally:
        manager.stop()
