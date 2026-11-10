"""Conversão Macro <-> JSON, com limites de tamanho para importações."""

from __future__ import annotations

import json

from automacro.models.events import MacroFormatError
from automacro.models.macro import Macro
from automacro.storage.migrations import migrate

MAX_FILE_BYTES = 64 * 1024 * 1024


def dumps(macro: Macro) -> str:
    macro.validate()
    return json.dumps(macro.to_dict(), ensure_ascii=False, indent=1)


def loads(text: str | bytes) -> Macro:
    size = len(text)
    if size > MAX_FILE_BYTES:
        raise MacroFormatError("arquivo grande demais para ser uma macro")
    try:
        data = json.loads(text)
    except (json.JSONDecodeError, UnicodeDecodeError, RecursionError) as exc:
        raise MacroFormatError(f"JSON inválido: {exc}") from exc
    macro = Macro.from_dict(migrate(data))
    macro.validate()
    return macro
