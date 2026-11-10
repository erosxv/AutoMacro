"""Leitura/gravação das configurações do aplicativo."""

from __future__ import annotations

import json
import logging
import os
from pathlib import Path

from automacro.models.settings import AppSettings
from automacro.storage.atomic import atomic_write_text

log = logging.getLogger(__name__)


class SettingsStore:
    def __init__(self, path: Path) -> None:
        self._path = Path(path)

    @property
    def path(self) -> Path:
        return self._path

    def load(self) -> AppSettings:
        if not self._path.exists():
            return AppSettings().sanitize()
        try:
            data = json.loads(self._path.read_text(encoding="utf-8"))
        except (OSError, ValueError) as exc:
            log.warning("Configurações ilegíveis (%s); usando padrões.", exc)
            self._backup_corrupt()
            return AppSettings().sanitize()
        return AppSettings.from_dict(data)

    def save(self, settings: AppSettings) -> None:
        text = json.dumps(settings.sanitize().to_dict(), ensure_ascii=False, indent=2)
        atomic_write_text(self._path, text)

    def _backup_corrupt(self) -> None:
        try:
            os.replace(self._path, self._path.with_suffix(".json.bak"))
        except OSError:
            pass
