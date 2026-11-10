"""Escolha do backend de entrada conforme o sistema e a sessão gráfica."""

from __future__ import annotations

import logging

from automacro.input_handlers.base import InputBackend
from automacro.input_handlers.pynput_backend import PynputBackend
from automacro.utils.platform_info import PlatformInfo, detect_platform

log = logging.getLogger(__name__)


def create_backend(platform: PlatformInfo | None = None) -> InputBackend:
    """Hoje: pynput em todos os sistemas (com limitações declaradas no Wayland).

    Novos backends (``evdev/uinput`` ou portais do Wayland) entram aqui sem mudar o resto.
    """
    platform = platform or detect_platform()
    backend = PynputBackend(platform)
    log.info("Backend de entrada: %s em %s", backend.name, platform.describe())
    return backend
