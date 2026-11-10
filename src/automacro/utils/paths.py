"""Pastas de dados, configurações e logs (por usuário, específicas de cada SO)."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from platformdirs import PlatformDirs

HOME_ENV = "AUTOMACRO_HOME"   # sobrescreve tudo: útil para modo portátil e para testes


@dataclass(frozen=True)
class AppPaths:
    data_dir: Path
    macros_dir: Path
    logs_dir: Path
    config_file: Path
    lock_file: Path

    @classmethod
    def default(cls) -> "AppPaths":
        override = os.environ.get(HOME_ENV)
        if override:
            return cls.under(Path(override))
        dirs = PlatformDirs("AutoMacro", appauthor=False, roaming=True)
        return cls(
            data_dir=Path(dirs.user_data_dir),
            macros_dir=Path(dirs.user_data_dir) / "macros",
            logs_dir=Path(dirs.user_log_dir) if os.name != "nt" else Path(dirs.user_data_dir) / "logs",
            config_file=Path(dirs.user_config_dir) / "settings.json",
            lock_file=Path(dirs.user_data_dir) / "automacro.lock",
        )

    @classmethod
    def under(cls, root: Path) -> "AppPaths":
        return cls(
            data_dir=root,
            macros_dir=root / "macros",
            logs_dir=root / "logs",
            config_file=root / "settings.json",
            lock_file=root / "automacro.lock",
        )

    def ensure(self) -> "AppPaths":
        for folder in (self.data_dir, self.macros_dir, self.logs_dir, self.config_file.parent):
            folder.mkdir(parents=True, exist_ok=True)
        return self
