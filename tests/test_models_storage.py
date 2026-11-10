import json

import pytest

from automacro.models.events import EventType, MacroEvent, MacroFormatError
from automacro.models.macro import Macro
from automacro.models.settings import AppSettings
from automacro.storage import serializer
from automacro.storage.repository import MacroNotFoundError, MacroRepository
from automacro.storage.settings_store import SettingsStore


def sample() -> Macro:
    return Macro("Teste", [
        MacroEvent.move(10, 20),
        MacroEvent.press("left", 10, 20, 100),
        MacroEvent.release("left", 10, 20, 50),
        MacroEvent.scroll(0, -1, 10, 20, 10),
        MacroEvent.key_down("a", 30),
        MacroEvent.key_up("a", 40),
    ])


def test_roundtrip_preserves_events():
    m = sample()
    back = serializer.loads(serializer.dumps(m))
    assert [e.to_dict() for e in back.events] == [e.to_dict() for e in m.events]
    assert back.id == m.id and back.duration_ms == pytest.approx(230)


@pytest.mark.parametrize("bad", [
    {"type": "nope", "delay_ms": 0},
    {"type": "mouse_press", "delay_ms": 0, "button": "x"},
    {"type": "mouse_move", "delay_ms": 0},
    {"type": "key_down", "delay_ms": 0, "key": ""},
    {"type": "key_down", "delay_ms": -1, "key": "a"},
    {"type": "key_down", "delay_ms": float("inf"), "key": "a"},
    {"type": "mouse_move", "delay_ms": 0, "x": True, "y": 1},
    {"type": "mouse_move", "delay_ms": 0, "x": 1.5, "y": 1},
    "texto",
])
def test_invalid_events_rejected(bad):
    with pytest.raises(MacroFormatError):
        MacroEvent.from_dict(bad)


@pytest.mark.parametrize("text", ["", "{", "[]", '{"events": 3, "name": "x"}',
                                  '{"schema_version": 99, "name": "x", "events": []}',
                                  '{"name": "  ", "events": []}'])
def test_invalid_macros_rejected(text):
    with pytest.raises(MacroFormatError):
        serializer.loads(text)


def test_float_coordinates_from_json_accepted():
    ev = MacroEvent.from_dict({"type": "mouse_move", "delay_ms": 1, "x": 400.0, "y": 300.0})
    assert (ev.x, ev.y) == (400, 300) and isinstance(ev.x, int)


def test_repository_crud(tmp_path):
    repo = MacroRepository(tmp_path)
    saved = repo.save(sample())
    assert [i.name for i in repo.list()] == ["Teste"]
    assert repo.load(saved.id).events[1].button == "left"

    renamed = repo.rename(saved.id, "Outro nome")
    assert renamed.name == "Outro nome"

    copy = repo.duplicate(saved.id)
    assert copy.id != saved.id and copy.name != renamed.name
    assert len(repo.list()) == 2

    repo.delete(saved.id)
    with pytest.raises(MacroNotFoundError):
        repo.load(saved.id)


def test_repository_unique_names(tmp_path):
    repo = MacroRepository(tmp_path)
    a = repo.save(Macro("Igual", []))
    b = repo.save(Macro("igual", []))
    assert a.name == "Igual" and b.name == "igual (2)"


def test_repository_rejects_path_traversal(tmp_path):
    repo = MacroRepository(tmp_path)
    for bad in ("../x", "..\\x", "a/b", ""):
        with pytest.raises(MacroNotFoundError):
            repo.load(bad)


def test_repository_skips_corrupt_files(tmp_path):
    repo = MacroRepository(tmp_path)
    repo.save(sample())
    (tmp_path / "quebrado.json").write_text("{ não é json", encoding="utf-8")
    assert len(repo.list()) == 1


def test_import_export_marks_imported_and_new_id(tmp_path):
    repo = MacroRepository(tmp_path / "lib")
    original = repo.save(sample())
    out = repo.export_file(original.id, tmp_path / "saida.json")
    imported = repo.import_file(out)
    assert imported.imported is True
    assert imported.id != original.id
    assert imported.name != original.name      # nome único
    assert len(imported.events) == len(original.events)


def test_import_rejects_garbage(tmp_path):
    repo = MacroRepository(tmp_path / "lib")
    bad = tmp_path / "ruim.json"
    bad.write_text(json.dumps({"hello": "world"}), encoding="utf-8")
    with pytest.raises(MacroFormatError):
        repo.import_file(bad)
    with pytest.raises(MacroFormatError):
        repo.import_file(tmp_path / "nao_existe.json")


def test_settings_tolerate_corruption_and_bad_values(tmp_path):
    path = tmp_path / "settings.json"
    path.write_text(json.dumps({
        "autoclick": {"interval_ms": "rápido", "button": "left", "count": -5},
        "hotkeys": {"stop": "Ctrl+Nada", "record_start": "f10"},
        "player": {"speed": 9999},
    }), encoding="utf-8")
    s = SettingsStore(path).load()
    assert s.autoclick.interval_ms == 100.0           # valor inválido volta ao padrão
    assert s.autoclick.count == 0
    assert s.hotkeys.stop == "F9"                     # atalho inválido volta ao padrão
    assert s.hotkeys.record_start == "F10"            # normalizado
    assert s.player.speed == 20.0                     # limitado

    path.write_text("{lixo", encoding="utf-8")
    assert SettingsStore(path).load().autoclick.interval_ms == 100.0
    assert (tmp_path / "settings.json.bak").exists()


def test_settings_roundtrip(tmp_path):
    store = SettingsStore(tmp_path / "s.json")
    s = AppSettings()
    s.autoclick.interval_ms = 250.0
    s.hotkeys.play_start = "Ctrl+Alt+P"
    store.save(s)
    back = store.load()
    assert back.autoclick.interval_ms == 250.0
    assert back.hotkeys.play_start == "Ctrl+Alt+P"
