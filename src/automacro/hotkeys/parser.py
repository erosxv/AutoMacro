"""Leitura e formatação de atalhos como ``"Ctrl+Shift+F9"``."""

from __future__ import annotations

from dataclasses import dataclass

from automacro.input_handlers.keymap import (
    MODIFIER_ORDER,
    MODIFIERS,
    display_key,
    display_modifier,
    parse_main_key,
    parse_modifier,
)


class HotkeyError(ValueError):
    """Atalho inválido ou em conflito."""


@dataclass(frozen=True)
class Hotkey:
    """Combinação: zero ou mais modificadores + exatamente uma tecla principal."""

    modifiers: frozenset[str]
    key: str

    def __str__(self) -> str:
        return format_hotkey(self)


def parse_hotkey(text: str) -> Hotkey:
    if not isinstance(text, str) or not text.strip():
        raise HotkeyError("atalho vazio")
    raw = text.strip()
    if raw == "+":
        tokens = ["+"]
    elif raw.endswith("++"):
        # "Ctrl++" significa Ctrl e a tecla "+".
        tokens = raw[:-2].split("+") + ["+"]
    else:
        tokens = raw.split("+")
    tokens = [t.strip() for t in tokens]
    if any(not t for t in tokens):
        raise HotkeyError(f"atalho inválido: {text!r}")

    modifiers: set[str] = set()
    main: str | None = None
    for token in tokens:
        mod = parse_modifier(token)
        if mod is not None:
            modifiers.add(mod)
            continue
        key = parse_main_key(token)
        if key is None:
            raise HotkeyError(f"tecla desconhecida: {token!r}")
        if main is not None:
            raise HotkeyError("use apenas uma tecla principal por atalho")
        main = key
    if main is None:
        raise HotkeyError("o atalho precisa de uma tecla além dos modificadores")
    if main in MODIFIERS:
        raise HotkeyError("o atalho precisa de uma tecla além dos modificadores")
    return Hotkey(frozenset(modifiers), main)


def format_hotkey(hotkey: Hotkey) -> str:
    parts = [display_modifier(m) for m in MODIFIER_ORDER if m in hotkey.modifiers]
    parts.append(display_key(hotkey.key))
    return "+".join(parts)


def normalize_hotkey(text: str) -> str:
    """Retorna a forma padrão do texto (levanta HotkeyError se inválido)."""
    return format_hotkey(parse_hotkey(text))


def find_conflicts(bindings: dict[str, str]) -> list[tuple[str, str]]:
    """Pares de ações que usam exatamente o mesmo atalho."""
    seen: dict[Hotkey, str] = {}
    conflicts: list[tuple[str, str]] = []
    for action, text in bindings.items():
        hk = parse_hotkey(text)
        if hk in seen:
            conflicts.append((seen[hk], action))
        else:
            seen[hk] = action
    return conflicts
