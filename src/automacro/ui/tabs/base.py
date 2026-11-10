"""Base comum das abas."""

from __future__ import annotations

from PySide6.QtWidgets import QWidget

from automacro.models.settings import AppSettings
from automacro.models.state import AppState
from automacro.ui.context import AppContext


class BaseTab(QWidget):
    def __init__(self, ctx: AppContext) -> None:
        super().__init__()
        self.ctx = ctx

    def hotkey(self, name: str) -> str:
        return self.ctx.settings.hotkeys.as_dict()[name]

    # ---- ganchos (as abas sobrescrevem o que precisarem) ---------------------------
    def set_state(self, state: AppState, activity: str | None) -> None:
        """Chamado a cada mudança de estado do núcleo."""

    def handle_event(self, event: object) -> None:
        """Chamado para cada evento do núcleo (sempre na thread da interface)."""

    def refresh_hotkeys(self) -> None:
        """Chamado quando os atalhos mudam."""

    def collect_settings(self, settings: AppSettings) -> None:
        """Copia os valores dos widgets para ``settings``."""

    def load_settings(self, settings: AppSettings) -> None:
        """Preenche os widgets a partir de ``settings``."""
