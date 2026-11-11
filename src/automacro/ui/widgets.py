"""Widgets e funções de formatação reutilizáveis."""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtGui import QKeySequence
from PySide6.QtWidgets import (
    QFrame,
    QScrollArea,
    QHBoxLayout,
    QKeySequenceEdit,
    QLabel,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from automacro.hotkeys.parser import HotkeyError, normalize_hotkey


def fmt_duration(ms: float) -> str:
    if ms < 1000:
        return f"{ms:.0f} ms"
    seconds = ms / 1000.0
    if seconds < 60:
        return f"{seconds:.1f} s"
    minutes, sec = divmod(int(seconds), 60)
    if minutes < 60:
        return f"{minutes} min {sec:02d} s"
    hours, minutes = divmod(minutes, 60)
    return f"{hours} h {minutes:02d} min"


def muted_label(text: str = "") -> QLabel:
    label = QLabel(text)
    label.setProperty("muted", True)
    label.setWordWrap(True)
    return label


def heading(text: str) -> QLabel:
    label = QLabel(text)
    label.setObjectName("heading")
    return label


class Card(QFrame):
    """Caixa com borda arredondada e layout vertical."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("card")
        self.body = QVBoxLayout(self)
        self.body.setContentsMargins(16, 14, 16, 14)
        self.body.setSpacing(10)


class StatusPill(QLabel):
    """Etiqueta colorida que mostra o estado atual."""

    def __init__(self) -> None:
        super().__init__("Ocioso")
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.setMinimumWidth(110)
        self.setSizePolicy(QSizePolicy.Policy.Maximum, QSizePolicy.Policy.Fixed)
        self.set_color("#4b5263", "Ocioso")

    def set_color(self, color: str, text: str) -> None:
        self.setText(text)
        self.setStyleSheet(
            f"background: {color}; color: white; border-radius: 14px; padding: 6px 14px;"
            "font-weight: 600; font-size: 13px;")


class HotkeyEdit(QWidget):
    """Campo para escolher um atalho digitando a combinação (sem precisar escrever texto)."""

    def __init__(self, value: str = "") -> None:
        super().__init__()
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        self._edit = QKeySequenceEdit()
        self._edit.setMinimumHeight(34)
        self._edit.setMaximumSequenceLength(1)
        self._edit.editingFinished.connect(self._on_finished)
        self._error = QLabel("")
        self._error.setStyleSheet("color: #e5484d;")
        layout.addWidget(self._edit, 1)
        layout.addWidget(self._error)
        self._value = ""
        self.set_value(value)

    def value(self) -> str:
        return self._value

    def set_value(self, text: str) -> None:
        try:
            self._value = normalize_hotkey(text)
        except HotkeyError:
            self._value = ""
        self._edit.setKeySequence(QKeySequence.fromString(self._value, QKeySequence.SequenceFormat.PortableText))
        self._error.setText("")

    def _on_finished(self) -> None:
        seq = self._edit.keySequence().toString(QKeySequence.SequenceFormat.PortableText)
        if not seq:
            self._error.setText("")
            return
        try:
            self._value = normalize_hotkey(seq)
            self._error.setText("")
        except HotkeyError as exc:
            self._error.setText(f"inválido: {exc}")
            return
        self._edit.setKeySequence(QKeySequence.fromString(self._value, QKeySequence.SequenceFormat.PortableText))
        self._edit.clearFocus()


def scrolled(widget: QWidget) -> QWidget:
    """Página rolável: em janela baixa ela rola, em vez de o Qt espremer os campos.

    O cartão de ação da página (``run_card``: Iniciar/Parar, Gravar, Reproduzir), se houver, sai
    da rolagem e fica fixo embaixo: a ação principal nunca some atrás da barra de rolagem."""
    area = QScrollArea()
    area.setWidgetResizable(True)
    area.setFrameShape(QFrame.Shape.NoFrame)
    area.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
    area.setWidget(widget)
    pinned = getattr(widget, "run_card", None)
    if pinned is None:
        return area
    widget.layout().removeWidget(pinned)
    container = QWidget()
    box = QVBoxLayout(container)
    box.setContentsMargins(0, 0, 0, 0)
    box.setSpacing(0)
    box.addWidget(area, 1)
    holder = QVBoxLayout()
    holder.setContentsMargins(0, 8, 0, 0)
    holder.addWidget(pinned)
    box.addLayout(holder)
    return container
