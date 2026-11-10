"""Migração de versões do formato de macro."""

from __future__ import annotations

from typing import Any, Callable

from automacro.models.events import MacroFormatError
from automacro.models.macro import SCHEMA_VERSION

# versão N -> função que converte os dados da versão N para a versão N+1.
MIGRATIONS: dict[int, Callable[[dict[str, Any]], dict[str, Any]]] = {}


def migrate(data: Any) -> dict[str, Any]:
    if not isinstance(data, dict):
        raise MacroFormatError("o arquivo não contém uma macro (esperado um objeto JSON)")
    version = data.get("schema_version", 1)
    if isinstance(version, bool) or not isinstance(version, int) or version < 1:
        raise MacroFormatError("'schema_version' inválido")
    if version > SCHEMA_VERSION:
        raise MacroFormatError(
            f"macro criada por uma versão mais nova do AutoMacro (formato {version}); "
            f"esta versão entende até o formato {SCHEMA_VERSION}"
        )
    while version < SCHEMA_VERSION:
        data = MIGRATIONS[version](data)
        version += 1
        data["schema_version"] = version
    return data
