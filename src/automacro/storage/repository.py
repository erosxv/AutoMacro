"""Biblioteca de macros em disco: um arquivo ``<uuid>.json`` por macro."""

from __future__ import annotations

import logging
import re
import threading
from dataclasses import dataclass
from pathlib import Path

from automacro.models.events import MacroFormatError
from automacro.models.macro import Macro, clean_name
from automacro.storage import serializer
from automacro.storage.atomic import atomic_write_text

log = logging.getLogger(__name__)

_ID_PATTERN = re.compile(r"^[0-9A-Za-z-]{8,64}$")


class MacroNotFoundError(KeyError):
    pass


@dataclass(frozen=True)
class MacroInfo:
    id: str
    name: str
    event_count: int
    duration_ms: float
    updated_at: str
    imported: bool
    path: Path


class MacroRepository:
    def __init__(self, directory: Path) -> None:
        self._dir = Path(directory)
        self._dir.mkdir(parents=True, exist_ok=True)
        self._lock = threading.RLock()

    @property
    def directory(self) -> Path:
        return self._dir

    # ---- helpers ---------------------------------------------------------------------
    def _path(self, macro_id: str) -> Path:
        if not isinstance(macro_id, str) or not _ID_PATTERN.match(macro_id):
            raise MacroNotFoundError(macro_id)
        return self._dir / f"{macro_id}.json"

    def _names(self, exclude_id: str | None = None) -> set[str]:
        return {i.name.casefold() for i in self.list() if i.id != exclude_id}

    def unique_name(self, name: str, exclude_id: str | None = None) -> str:
        base = clean_name(name)
        taken = self._names(exclude_id)
        if base.casefold() not in taken:
            return base
        n = 2
        while True:
            suffix = f" ({n})"
            candidate = base[: 120 - len(suffix)] + suffix
            if candidate.casefold() not in taken:
                return candidate
            n += 1

    # ---- API -------------------------------------------------------------------------
    def list(self) -> list[MacroInfo]:
        infos: list[MacroInfo] = []
        with self._lock:
            for path in sorted(self._dir.glob("*.json")):
                try:
                    macro = serializer.loads(path.read_text(encoding="utf-8"))
                except (MacroFormatError, OSError, UnicodeDecodeError) as exc:
                    log.warning("Ignorando arquivo de macro ilegível %s: %s", path.name, exc)
                    continue
                infos.append(MacroInfo(
                    id=macro.id, name=macro.name, event_count=len(macro.events),
                    duration_ms=macro.duration_ms, updated_at=macro.updated_at,
                    imported=macro.imported, path=path,
                ))
        infos.sort(key=lambda i: i.name.casefold())
        return infos

    def load(self, macro_id: str) -> Macro:
        path = self._path(macro_id)
        with self._lock:
            if not path.exists():
                raise MacroNotFoundError(macro_id)
            return serializer.loads(path.read_text(encoding="utf-8"))

    def save(self, macro: Macro, ensure_unique_name: bool = True) -> Macro:
        macro.validate()
        path = self._path(macro.id)
        with self._lock:
            if ensure_unique_name:
                macro.name = self.unique_name(macro.name, exclude_id=macro.id)
            macro.touch()
            atomic_write_text(path, serializer.dumps(macro))
        return macro

    def delete(self, macro_id: str) -> None:
        path = self._path(macro_id)
        with self._lock:
            if not path.exists():
                raise MacroNotFoundError(macro_id)
            path.unlink()

    def rename(self, macro_id: str, new_name: str) -> Macro:
        with self._lock:
            macro = self.load(macro_id)
            macro.name = clean_name(new_name)
            return self.save(macro)

    def duplicate(self, macro_id: str, new_name: str | None = None) -> Macro:
        with self._lock:
            original = self.load(macro_id)
            copy = original.duplicate(new_name or f"{original.name} (cópia)")
            return self.save(copy)

    def import_file(self, path: Path) -> Macro:
        """Importa um arquivo de macro. Sempre gera um novo id e marca como importada."""
        path = Path(path)
        try:
            text = path.read_bytes()
        except OSError as exc:
            raise MacroFormatError(f"não foi possível ler o arquivo: {exc}") from exc
        macro = serializer.loads(text)
        fresh = Macro(name=macro.name, events=macro.events, recorded_on=macro.recorded_on,
                      imported=True)
        return self.save(fresh)

    def export_file(self, macro_id: str, destination: Path) -> Path:
        macro = self.load(macro_id)
        destination = Path(destination)
        atomic_write_text(destination, serializer.dumps(macro))
        return destination
