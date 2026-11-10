"""Objetos compartilhados entre as abas."""

from __future__ import annotations

from dataclasses import dataclass

from automacro.core.session import Session
from automacro.models.settings import AppSettings
from automacro.storage.repository import MacroRepository
from automacro.storage.settings_store import SettingsStore
from automacro.ui.bridge import SessionBridge
from automacro.utils.paths import AppPaths


@dataclass
class AppContext:
    session: Session
    repo: MacroRepository
    store: SettingsStore
    paths: AppPaths
    bridge: SessionBridge

    @property
    def settings(self) -> AppSettings:
        return self.session.settings
