"""Evento de macro: estrutura mínima, serializável e validada.

Cada evento guarda o ``delay_ms`` **relativo ao evento anterior**. Isso torna a edição
natural (alterar um delay desloca o resto da macro) e o player calcula os instantes
absolutos ao carregar.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from enum import Enum
from typing import Any

VALID_BUTTONS: tuple[str, ...] = ("left", "right", "middle")
MAX_KEY_LENGTH = 40
MAX_DELAY_MS = 24 * 3600 * 1000.0
MAX_COORD = 1_000_000
MAX_SCROLL = 10_000


class MacroFormatError(ValueError):
    """Dados de macro inválidos ou corrompidos."""


class EventType(str, Enum):
    MOUSE_MOVE = "mouse_move"
    MOUSE_PRESS = "mouse_press"
    MOUSE_RELEASE = "mouse_release"
    MOUSE_SCROLL = "mouse_scroll"
    KEY_DOWN = "key_down"
    KEY_UP = "key_up"


MOUSE_BUTTON_EVENTS = frozenset({EventType.MOUSE_PRESS, EventType.MOUSE_RELEASE})
KEY_EVENTS = frozenset({EventType.KEY_DOWN, EventType.KEY_UP})

EVENT_LABELS: dict[EventType, str] = {
    EventType.MOUSE_MOVE: "Mover mouse",
    EventType.MOUSE_PRESS: "Pressionar botão",
    EventType.MOUSE_RELEASE: "Soltar botão",
    EventType.MOUSE_SCROLL: "Rolar",
    EventType.KEY_DOWN: "Pressionar tecla",
    EventType.KEY_UP: "Soltar tecla",
}


def as_int(value: Any, name: str, limit: int) -> int:
    """Converte para int aceitando floats integrais (ex.: 400.0 vindo de JSON)."""
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise MacroFormatError(f"'{name}' deve ser um número inteiro")
    if isinstance(value, float):
        if not math.isfinite(value) or not value.is_integer():
            raise MacroFormatError(f"'{name}' deve ser um número inteiro")
        value = int(value)
    if abs(value) > limit:
        raise MacroFormatError(f"'{name}' fora do intervalo permitido")
    return value


def as_delay(value: Any) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise MacroFormatError("'delay_ms' deve ser numérico")
    value = float(value)
    if not math.isfinite(value) or value < 0 or value > MAX_DELAY_MS:
        raise MacroFormatError("'delay_ms' deve estar entre 0 e 24 horas")
    return value


@dataclass(slots=True)
class MacroEvent:
    type: EventType
    delay_ms: float = 0.0
    x: int | None = None
    y: int | None = None
    button: str | None = None
    dx: int | None = None
    dy: int | None = None
    key: str | None = None

    # ---- construtores de conveniência -------------------------------------------------
    @classmethod
    def move(cls, x: int, y: int, delay_ms: float = 0.0) -> "MacroEvent":
        return cls(EventType.MOUSE_MOVE, delay_ms, x=x, y=y)

    @classmethod
    def press(cls, button: str, x: int | None = None, y: int | None = None,
              delay_ms: float = 0.0) -> "MacroEvent":
        return cls(EventType.MOUSE_PRESS, delay_ms, x=x, y=y, button=button)

    @classmethod
    def release(cls, button: str, x: int | None = None, y: int | None = None,
                delay_ms: float = 0.0) -> "MacroEvent":
        return cls(EventType.MOUSE_RELEASE, delay_ms, x=x, y=y, button=button)

    @classmethod
    def scroll(cls, dx: int, dy: int, x: int | None = None, y: int | None = None,
               delay_ms: float = 0.0) -> "MacroEvent":
        return cls(EventType.MOUSE_SCROLL, delay_ms, x=x, y=y, dx=dx, dy=dy)

    @classmethod
    def key_down(cls, key: str, delay_ms: float = 0.0) -> "MacroEvent":
        return cls(EventType.KEY_DOWN, delay_ms, key=key)

    @classmethod
    def key_up(cls, key: str, delay_ms: float = 0.0) -> "MacroEvent":
        return cls(EventType.KEY_UP, delay_ms, key=key)

    # ---- validação e serialização -----------------------------------------------------
    def validate(self) -> None:
        """Normaliza tipos e levanta MacroFormatError se o evento for inválido."""
        self.type = EventType(self.type)
        self.delay_ms = as_delay(self.delay_ms)

        if self.type is EventType.MOUSE_MOVE:
            if self.x is None or self.y is None:
                raise MacroFormatError("mouse_move exige x e y")
        if self.x is not None:
            self.x = as_int(self.x, "x", MAX_COORD)
        if self.y is not None:
            self.y = as_int(self.y, "y", MAX_COORD)
        if (self.x is None) != (self.y is None):
            raise MacroFormatError("x e y devem vir juntos")

        if self.type in MOUSE_BUTTON_EVENTS:
            if self.button not in VALID_BUTTONS:
                raise MacroFormatError(f"botão inválido: {self.button!r}")
        elif self.type is EventType.MOUSE_SCROLL:
            if self.dx is None or self.dy is None:
                raise MacroFormatError("mouse_scroll exige dx e dy")
            self.dx = as_int(self.dx, "dx", MAX_SCROLL)
            self.dy = as_int(self.dy, "dy", MAX_SCROLL)
        elif self.type in KEY_EVENTS:
            if not isinstance(self.key, str) or not self.key or len(self.key) > MAX_KEY_LENGTH:
                raise MacroFormatError("tecla inválida")

    def to_dict(self) -> dict[str, Any]:
        d: dict[str, Any] = {"type": self.type.value, "delay_ms": round(self.delay_ms, 3)}
        t = self.type
        if t in MOUSE_BUTTON_EVENTS:
            d["button"] = self.button
        if t is EventType.MOUSE_SCROLL:
            d["dx"], d["dy"] = self.dx, self.dy
        if t in KEY_EVENTS:
            d["key"] = self.key
        if self.x is not None and self.y is not None:
            d["x"], d["y"] = self.x, self.y
        return d

    @classmethod
    def from_dict(cls, data: Any) -> "MacroEvent":
        if not isinstance(data, dict):
            raise MacroFormatError("evento deve ser um objeto")
        try:
            etype = EventType(data.get("type"))
        except ValueError:
            raise MacroFormatError(f"tipo de evento desconhecido: {data.get('type')!r}") from None
        ev = cls(
            type=etype,
            delay_ms=data.get("delay_ms", 0.0),
            x=data.get("x"),
            y=data.get("y"),
            button=data.get("button"),
            dx=data.get("dx"),
            dy=data.get("dy"),
            key=data.get("key"),
        )
        ev.validate()
        return ev

    def copy(self) -> "MacroEvent":
        return MacroEvent(self.type, self.delay_ms, self.x, self.y, self.button,
                          self.dx, self.dy, self.key)
