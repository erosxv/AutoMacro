"""Exceções do núcleo. Todas carregam mensagens prontas para exibir ao usuário."""

from __future__ import annotations


class AutoMacroError(Exception):
    """Base das exceções do AutoMacro."""


class BusyError(AutoMacroError):
    """Já existe uma atividade em andamento (gravar, reproduzir ou clicar)."""


class FeatureUnavailableError(AutoMacroError):
    """O sistema operacional ou o ambiente impede o recurso pedido."""


class InputError(AutoMacroError):
    """Falha ao enviar ou capturar entrada (mouse/teclado)."""


class ConfirmationRequired(AutoMacroError):
    """A ação exige confirmação explícita do usuário (ex.: macro importada)."""
