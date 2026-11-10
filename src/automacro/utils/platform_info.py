"""Detecção de sistema operacional, tipo de sessão gráfica e privilégios."""

from __future__ import annotations

import os
import sys
from dataclasses import dataclass


@dataclass(frozen=True)
class PlatformInfo:
    os: str                 # "windows" | "linux" | "macos" | "other"
    session_type: str       # "windows" | "x11" | "wayland" | "none" | "other"
    has_display: bool
    is_admin: bool
    desktop: str | None
    python: str

    @property
    def is_windows(self) -> bool:
        return self.os == "windows"

    @property
    def is_linux(self) -> bool:
        return self.os == "linux"

    @property
    def is_wayland(self) -> bool:
        return self.session_type == "wayland"

    def describe(self) -> str:
        names = {"windows": "Windows", "linux": "Linux", "macos": "macOS", "other": "Outro"}
        text = names.get(self.os, self.os)
        if self.os == "linux":
            text += f" ({self.session_type.upper() if self.session_type != 'none' else 'sem sessão gráfica'}"
            text += f", {self.desktop})" if self.desktop else ")"
        return text


def _is_admin(os_name: str) -> bool:
    try:
        if os_name == "windows":
            import ctypes

            return bool(ctypes.windll.shell32.IsUserAnAdmin())  # type: ignore[attr-defined]
        return os.geteuid() == 0  # type: ignore[attr-defined]
    except Exception:
        return False


def detect_platform(environ: dict[str, str] | None = None,
                    platform: str | None = None) -> PlatformInfo:
    env = os.environ if environ is None else environ
    plat = sys.platform if platform is None else platform
    if plat.startswith("win"):
        os_name, session, display = "windows", "windows", True
    elif plat.startswith("linux"):
        os_name = "linux"
        declared = env.get("XDG_SESSION_TYPE", "").strip().lower()
        if declared in ("x11", "wayland"):
            session = declared
        elif env.get("WAYLAND_DISPLAY"):
            session = "wayland"
        elif env.get("DISPLAY"):
            session = "x11"
        else:
            session = "none"
        display = bool(env.get("DISPLAY") or env.get("WAYLAND_DISPLAY"))
    elif plat == "darwin":
        os_name, session, display = "macos", "other", True
    else:
        os_name, session, display = "other", "other", bool(env.get("DISPLAY"))
    return PlatformInfo(
        os=os_name,
        session_type=session,
        has_display=display,
        is_admin=_is_admin(os_name),
        desktop=env.get("XDG_CURRENT_DESKTOP") or None,
        python=sys.version.split()[0],
    )


def enable_high_resolution_timer():
    """No Windows, pede resolução de timer de 1 ms. Retorna uma função que desfaz o pedido.

    Em outros sistemas não faz nada e retorna uma função vazia.
    """
    if sys.platform.startswith("win"):
        try:
            import ctypes

            winmm = ctypes.windll.winmm  # type: ignore[attr-defined]
            if winmm.timeBeginPeriod(1) == 0:
                return lambda: winmm.timeEndPeriod(1)
        except Exception:
            pass
    return lambda: None
