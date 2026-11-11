"""Barra de atividade: aparece embaixo só quando algo está acontecendo."""

from __future__ import annotations

from PySide6.QtCore import QSize, Qt
from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QProgressBar, QPushButton, QVBoxLayout

from automacro.core.event_bus import ClickCount, Countdown, Progress, RecordingCount
from automacro.models.state import AppState
from automacro.ui import icons
from automacro.ui.context import AppContext
from automacro.ui.theme import palette


class NowBar(QFrame):
    def __init__(self, ctx: AppContext) -> None:
        super().__init__()
        self.ctx = ctx
        self.setObjectName("nowbar")
        self._macro_name = ""
        self._side = ""

        lay = QHBoxLayout(self)
        lay.setContentsMargins(16, 12, 12, 12)
        lay.setSpacing(12)
        col = QVBoxLayout()
        col.setSpacing(8)
        top = QHBoxLayout()
        self.title = QLabel("")
        self.title.setObjectName("nowtitle")
        self.side = QLabel("")
        self.side.setProperty("muted", True)
        top.addWidget(self.title, 1)
        top.addWidget(self.side)
        col.addLayout(top)
        self.bar = QProgressBar()
        self.bar.setObjectName("nowprogress")
        self.bar.setTextVisible(False)
        self.bar.setRange(0, 100)
        self.bar.setFixedHeight(6)
        col.addWidget(self.bar)
        lay.addLayout(col, 1)

        self.pause_btn = QPushButton()
        self.pause_btn.setObjectName("iconbtn")
        self.pause_btn.setFixedSize(44, 44)
        self.pause_btn.setIconSize(QSize(16, 16))
        self.pause_btn.setAccessibleName("Pausar")
        self.pause_btn.clicked.connect(lambda: ctx.session.toggle_pause())
        lay.addWidget(self.pause_btn)
        self.stop_btn = QPushButton("Parar")
        self.stop_btn.setObjectName("stopall")
        self.stop_btn.setIconSize(QSize(12, 12))
        self.stop_btn.setMinimumHeight(44)
        self.stop_btn.clicked.connect(lambda: ctx.session.stop())
        lay.addWidget(self.stop_btn)
        self.setVisible(False)
        self.apply_theme()

    def apply_theme(self) -> None:
        c = palette(self.ctx.settings.ui.theme)
        self._colors = c
        self.pause_btn.setIcon(icons.pause(c["text"]))
        self.stop_btn.setIcon(icons.stop(c["bg"]))

    def set_macro_name(self, name: str) -> None:
        self._macro_name = name

    def set_state(self, state: AppState, activity: str | None) -> None:
        self.setVisible(state is not AppState.IDLE)
        playing = state in (AppState.PLAYING, AppState.PAUSED)
        self.pause_btn.setVisible(playing)
        self.bar.setVisible(state in (AppState.PLAYING, AppState.PAUSED, AppState.COUNTDOWN))
        c = self._colors
        if state is AppState.PAUSED:
            self.pause_btn.setIcon(icons.play(c["text"]))
            self.pause_btn.setAccessibleName("Continuar")
        else:
            self.pause_btn.setIcon(icons.pause(c["text"]))
            self.pause_btn.setAccessibleName("Pausar")
        name = f": {self._macro_name}" if self._macro_name else ""
        self.title.setText({
            AppState.COUNTDOWN: "Começando…",
            AppState.RECORDING: "Gravando",
            AppState.PLAYING: f"Reproduzindo{name}",
            AppState.PAUSED: f"Em pausa{name}",
            AppState.AUTOCLICKING: "Auto Clicker ativo",
            AppState.STOPPING: "Parando…",
        }.get(state, ""))
        if state in (AppState.COUNTDOWN, AppState.RECORDING, AppState.AUTOCLICKING):
            self.side.setText("")
        if state is AppState.COUNTDOWN:
            self.bar.setValue(0)

    def handle_event(self, event: object) -> None:
        if isinstance(event, Progress):
            self.bar.setValue(int(event.done * 100 / max(event.total, 1)))
            self.side.setText(f"Ação {event.done} de {event.total}")
        elif isinstance(event, RecordingCount):
            self.side.setText(f"{event.count} ações")
        elif isinstance(event, ClickCount):
            self.side.setText(f"{event.count} cliques")
        elif isinstance(event, Countdown):
            self.side.setText(f"{event.remaining}…")
