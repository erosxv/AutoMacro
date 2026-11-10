"""O que o backend atual consegue (ou não) fazer neste sistema, e por quê.

É a base do requisito "informar claramente quando o sistema operacional impedir uma
funcionalidade": cada recurso indisponível ou limitado carrega o motivo em português.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum, IntEnum


class Feature(str, Enum):
    CAPTURE = "capture"                  # observar mouse/teclado globalmente (gravar)
    INJECT = "inject"                    # enviar cliques/teclas (reproduzir, auto clicker)
    HOTKEYS = "hotkeys"                  # atalhos globais
    CURSOR_POSITION = "cursor_position"  # ler a posição do cursor


FEATURE_LABELS: dict[Feature, str] = {
    Feature.CAPTURE: "Captura global de mouse e teclado",
    Feature.INJECT: "Envio de cliques e teclas",
    Feature.HOTKEYS: "Atalhos globais",
    Feature.CURSOR_POSITION: "Leitura da posição do cursor",
}


class Level(IntEnum):
    AVAILABLE = 0
    LIMITED = 1
    UNAVAILABLE = 2


@dataclass(frozen=True)
class FeatureStatus:
    level: Level = Level.AVAILABLE
    reason: str = ""


@dataclass
class BackendCapabilities:
    backend_name: str
    features: dict[Feature, FeatureStatus] = field(default_factory=dict)
    notes: list[str] = field(default_factory=list)

    def status(self, feature: Feature) -> FeatureStatus:
        return self.features.get(feature, FeatureStatus())

    def available(self, feature: Feature) -> bool:
        """True se o recurso funciona (mesmo que de forma limitada)."""
        return self.status(feature).level != Level.UNAVAILABLE

    def problems(self) -> list[tuple[Feature, FeatureStatus]]:
        return [(f, s) for f, s in self.features.items() if s.level != Level.AVAILABLE]

    def problem_lines(self) -> list[str]:
        lines = []
        for feature, status in self.problems():
            tag = "Indisponível" if status.level == Level.UNAVAILABLE else "Limitado"
            lines.append(f"{FEATURE_LABELS[feature]} — {tag}: {status.reason}")
        lines.extend(self.notes)
        return lines

    @classmethod
    def all_available(cls, name: str) -> "BackendCapabilities":
        return cls(name, {f: FeatureStatus() for f in Feature})

    @classmethod
    def all_unavailable(cls, name: str, reason: str) -> "BackendCapabilities":
        unavailable = FeatureStatus(Level.UNAVAILABLE, reason)
        return cls(name, {f: unavailable for f in Feature})
