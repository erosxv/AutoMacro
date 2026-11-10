"""Estados da aplicação e transições permitidas."""

from __future__ import annotations

from enum import Enum


class AppState(str, Enum):
    IDLE = "idle"
    COUNTDOWN = "countdown"
    RECORDING = "recording"
    PLAYING = "playing"
    PAUSED = "paused"
    AUTOCLICKING = "autoclicking"
    STOPPING = "stopping"


STATE_LABELS: dict[AppState, str] = {
    AppState.IDLE: "Ocioso",
    AppState.COUNTDOWN: "Iniciando…",
    AppState.RECORDING: "Gravando",
    AppState.PLAYING: "Reproduzindo",
    AppState.PAUSED: "Pausado",
    AppState.AUTOCLICKING: "Auto Clicker ativo",
    AppState.STOPPING: "Parando…",
}

ALLOWED_TRANSITIONS: dict[AppState, frozenset[AppState]] = {
    AppState.IDLE: frozenset({AppState.COUNTDOWN, AppState.RECORDING, AppState.PLAYING,
                              AppState.AUTOCLICKING}),
    AppState.COUNTDOWN: frozenset({AppState.RECORDING, AppState.PLAYING, AppState.AUTOCLICKING,
                                   AppState.STOPPING, AppState.IDLE}),
    AppState.RECORDING: frozenset({AppState.STOPPING, AppState.IDLE}),
    AppState.PLAYING: frozenset({AppState.PAUSED, AppState.STOPPING, AppState.IDLE}),
    AppState.PAUSED: frozenset({AppState.PLAYING, AppState.STOPPING, AppState.IDLE}),
    AppState.AUTOCLICKING: frozenset({AppState.STOPPING, AppState.IDLE}),
    AppState.STOPPING: frozenset({AppState.IDLE}),
}


def can_transition(old: AppState, new: AppState) -> bool:
    return new in ALLOWED_TRANSITIONS[old]


# Atividade em andamento (para mensagens como "não é possível reproduzir durante a gravação").
ACTIVITY_LABELS: dict[str, str] = {
    "autoclick": "o Auto Clicker",
    "record": "a gravação",
    "play": "a reprodução",
}
