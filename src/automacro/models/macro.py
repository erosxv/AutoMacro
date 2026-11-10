"""Macro: sequência nomeada de eventos com metadados."""

from __future__ import annotations

import re
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from automacro.models.events import (
    KEY_EVENTS,
    EventType,
    MacroEvent,
    MacroFormatError,
)

SCHEMA_VERSION = 1
MAX_EVENTS = 500_000
MAX_NAME_LENGTH = 120

_CONTROL_CHARS = re.compile(r"[\x00-\x1f\x7f]")
_SPACES = re.compile(r"\s+")


def clean_name(name: Any) -> str:
    """Normaliza o nome de uma macro (sem caracteres de controle, espaços colapsados)."""
    if not isinstance(name, str):
        raise MacroFormatError("o nome da macro deve ser texto")
    name = _SPACES.sub(" ", _CONTROL_CHARS.sub(" ", name)).strip()
    if not name:
        raise MacroFormatError("o nome da macro não pode ficar vazio")
    return name[:MAX_NAME_LENGTH]


def now_iso() -> str:
    return datetime.now().astimezone().isoformat(timespec="seconds")


@dataclass(frozen=True)
class MacroSummary:
    events: int
    duration_ms: float
    key_events: int
    clicks: int
    moves: int
    scrolls: int
    keys: tuple[str, ...]


@dataclass
class Macro:
    name: str
    events: list[MacroEvent] = field(default_factory=list)
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    created_at: str = field(default_factory=now_iso)
    updated_at: str = field(default_factory=now_iso)
    recorded_on: dict[str, Any] = field(default_factory=dict)
    imported: bool = False
    schema_version: int = SCHEMA_VERSION

    @property
    def duration_ms(self) -> float:
        return sum(e.delay_ms for e in self.events)

    def summary(self) -> MacroSummary:
        keys: list[str] = []
        clicks = moves = scrolls = key_events = 0
        for e in self.events:
            if e.type is EventType.MOUSE_PRESS:
                clicks += 1
            elif e.type is EventType.MOUSE_MOVE:
                moves += 1
            elif e.type is EventType.MOUSE_SCROLL:
                scrolls += 1
            elif e.type in KEY_EVENTS:
                key_events += 1
                if e.type is EventType.KEY_DOWN and e.key and e.key not in keys:
                    keys.append(e.key)
        return MacroSummary(len(self.events), self.duration_ms, key_events, clicks, moves,
                            scrolls, tuple(keys))

    def validate(self) -> None:
        self.name = clean_name(self.name)
        if len(self.events) > MAX_EVENTS:
            raise MacroFormatError(f"a macro excede o limite de {MAX_EVENTS} eventos")
        for ev in self.events:
            ev.validate()

    def touch(self) -> None:
        self.updated_at = now_iso()

    def duplicate(self, new_name: str) -> "Macro":
        return Macro(
            name=clean_name(new_name),
            events=[e.copy() for e in self.events],
            recorded_on=dict(self.recorded_on),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "id": self.id,
            "name": self.name,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "recorded_on": self.recorded_on,
            "imported": self.imported,
            "events": [e.to_dict() for e in self.events],
        }

    @classmethod
    def from_dict(cls, data: Any) -> "Macro":
        if not isinstance(data, dict):
            raise MacroFormatError("a macro deve ser um objeto JSON")
        raw_events = data.get("events")
        if not isinstance(raw_events, list):
            raise MacroFormatError("campo 'events' ausente ou inválido")
        if len(raw_events) > MAX_EVENTS:
            raise MacroFormatError(f"a macro excede o limite de {MAX_EVENTS} eventos")
        recorded_on = data.get("recorded_on")
        macro = cls(
            name=clean_name(data.get("name", "")),
            events=[MacroEvent.from_dict(e) for e in raw_events],
            recorded_on=recorded_on if isinstance(recorded_on, dict) else {},
            imported=bool(data.get("imported", False)),
        )
        for key in ("id", "created_at", "updated_at"):
            value = data.get(key)
            if isinstance(value, str) and value:
                setattr(macro, key, value[:64])
        return macro
