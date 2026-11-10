"""Configurações do aplicativo (tolerantes a arquivos antigos, incompletos ou corrompidos)."""

from __future__ import annotations

import dataclasses
import math
from dataclasses import dataclass, field
from typing import Any

from automacro.models.events import VALID_BUTTONS

MIN_INTERVAL_MS = 1.0
MAX_INTERVAL_MS = 24 * 3600 * 1000.0
MIN_SPEED = 0.05
MAX_SPEED = 20.0


def _coerce(value: Any, default: Any) -> Any:
    kind = type(default)
    if kind is bool:
        return value if isinstance(value, bool) else default
    if isinstance(value, bool):
        return default
    if kind is int:
        if isinstance(value, (int, float)) and math.isfinite(value) and float(value).is_integer():
            return int(value)
        return default
    if kind is float:
        if isinstance(value, (int, float)) and math.isfinite(value):
            return float(value)
        return default
    if kind is str:
        return value if isinstance(value, str) else default
    return default


def _load(cls: type, data: Any):
    inst = cls()
    if isinstance(data, dict):
        for f in dataclasses.fields(cls):
            if f.name in data:
                setattr(inst, f.name, _coerce(data[f.name], getattr(inst, f.name)))
    return inst


def _clamp(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))


@dataclass
class AutoClickConfig:
    button: str = "left"
    interval_ms: float = 100.0
    count: int = 0                      # 0 = infinito
    use_fixed_position: bool = False
    x: int = 0
    y: int = 0
    max_runtime_s: float = 0.0          # 0 = sem limite

    def sanitize(self) -> "AutoClickConfig":
        if self.button not in VALID_BUTTONS:
            self.button = "left"
        self.interval_ms = _clamp(self.interval_ms, MIN_INTERVAL_MS, MAX_INTERVAL_MS)
        self.count = max(0, self.count)
        self.max_runtime_s = max(0.0, self.max_runtime_s)
        return self


@dataclass
class HotkeySettings:
    record_start: str = "F6"
    record_stop: str = "F7"
    play_start: str = "F8"
    stop: str = "F9"
    emergency: str = "Ctrl+Shift+F9"
    autoclick_toggle: str = "F4"
    play_pause: str = "Ctrl+F8"

    def as_dict(self) -> dict[str, str]:
        return {f.name: getattr(self, f.name) for f in dataclasses.fields(self)}

    def sanitize(self) -> "HotkeySettings":
        from automacro.hotkeys.parser import HotkeyError, normalize_hotkey

        defaults = HotkeySettings()
        for f in dataclasses.fields(self):
            try:
                setattr(self, f.name, normalize_hotkey(getattr(self, f.name)))
            except HotkeyError:
                setattr(self, f.name, getattr(defaults, f.name))
        return self


HOTKEY_LABELS: dict[str, str] = {
    "record_start": "Iniciar gravação",
    "record_stop": "Finalizar gravação",
    "play_start": "Iniciar reprodução",
    "stop": "Interromper execução",
    "emergency": "Parada de emergência",
    "autoclick_toggle": "Auto Clicker (iniciar/parar)",
    "play_pause": "Pausar/continuar reprodução",
}


@dataclass
class RecorderSettings:
    record_mouse_moves: bool = False
    record_scroll: bool = True
    move_min_interval_ms: float = 15.0
    move_min_distance_px: int = 4

    def sanitize(self) -> "RecorderSettings":
        self.move_min_interval_ms = _clamp(self.move_min_interval_ms, 1.0, 1000.0)
        self.move_min_distance_px = int(_clamp(self.move_min_distance_px, 0, 500))
        return self


@dataclass
class PlayerSettings:
    speed: float = 1.0
    repeat: int = 1                     # 0 = infinito
    loop_delay_ms: float = 0.0

    def sanitize(self) -> "PlayerSettings":
        self.speed = _clamp(self.speed, MIN_SPEED, MAX_SPEED)
        self.repeat = max(0, self.repeat)
        self.loop_delay_ms = _clamp(self.loop_delay_ms, 0.0, 3_600_000.0)
        return self


@dataclass
class SafetySettings:
    countdown_s: float = 3.0            # contagem regressiva ao iniciar pelos botões
    hotkey_countdown_s: float = 0.0     # contagem regressiva ao iniciar por atalho
    confirm_imported: bool = True
    failsafe_corner: bool = True        # mouse no canto superior esquerdo = parar tudo
    max_playback_minutes: int = 0       # 0 = sem limite

    def sanitize(self) -> "SafetySettings":
        self.countdown_s = _clamp(self.countdown_s, 0.0, 30.0)
        self.hotkey_countdown_s = _clamp(self.hotkey_countdown_s, 0.0, 30.0)
        self.max_playback_minutes = max(0, self.max_playback_minutes)
        return self


@dataclass
class UISettings:
    theme: str = "dark"

    def sanitize(self) -> "UISettings":
        if self.theme not in ("dark", "light"):
            self.theme = "dark"
        return self


@dataclass
class UpdateSettings:
    auto_check: bool = True             # verifica versão nova ao abrir (nunca instala sozinho)

    def sanitize(self) -> "UpdateSettings":
        return self


@dataclass
class AppSettings:
    autoclick: AutoClickConfig = field(default_factory=AutoClickConfig)
    hotkeys: HotkeySettings = field(default_factory=HotkeySettings)
    recorder: RecorderSettings = field(default_factory=RecorderSettings)
    player: PlayerSettings = field(default_factory=PlayerSettings)
    safety: SafetySettings = field(default_factory=SafetySettings)
    ui: UISettings = field(default_factory=UISettings)
    updates: UpdateSettings = field(default_factory=UpdateSettings)

    def sanitize(self) -> "AppSettings":
        for part in (self.autoclick, self.hotkeys, self.recorder, self.player, self.safety,
                     self.ui, self.updates):
            part.sanitize()
        return self

    def to_dict(self) -> dict[str, Any]:
        return dataclasses.asdict(self)

    @classmethod
    def from_dict(cls, data: Any) -> "AppSettings":
        data = data if isinstance(data, dict) else {}
        return cls(
            autoclick=_load(AutoClickConfig, data.get("autoclick")),
            hotkeys=_load(HotkeySettings, data.get("hotkeys")),
            recorder=_load(RecorderSettings, data.get("recorder")),
            player=_load(PlayerSettings, data.get("player")),
            safety=_load(SafetySettings, data.get("safety")),
            ui=_load(UISettings, data.get("ui")),
            updates=_load(UpdateSettings, data.get("updates")),
        ).sanitize()
