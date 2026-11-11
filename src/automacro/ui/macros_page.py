"""Página Macros: lista (padrão), gravação e opções de reprodução, uma de cada vez."""

from __future__ import annotations

from PySide6.QtCore import QSize, Qt
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QPushButton,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from automacro.ui import icons
from automacro.ui.context import AppContext
from automacro.ui.theme import palette
from automacro.ui.widgets import scrolled

LIST, RECORD, OPTIONS = 0, 1, 2


class MacrosPage(QWidget):
    def __init__(self, ctx: AppContext, library, recorder, player) -> None:
        super().__init__()
        self.ctx = ctx
        self.library, self.recorder, self.player = library, recorder, player

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        self.views = QStackedWidget()
        root.addWidget(self.views)

        # ---- visão 1: lista -------------------------------------------------------------
        lst = QWidget()
        lay = QVBoxLayout(lst)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(6)
        top = QHBoxLayout()
        self.record_btn = QPushButton("Nova gravação")
        self.record_btn.setObjectName("primary")
        self.record_btn.setMinimumHeight(48)
        self.record_btn.setIconSize(QSize(14, 14))
        self.record_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.record_btn.clicked.connect(self.new_recording)
        top.addWidget(self.record_btn, 1)
        lay.addLayout(top)
        self.hint = QLabel("")
        self.hint.setProperty("muted", True)
        self.hint.setAlignment(Qt.AlignmentFlag.AlignHCenter)
        lay.addWidget(self.hint)
        lay.addSpacing(8)
        self.list_title = QLabel("Minhas macros")
        self.list_title.setProperty("muted", True)
        lay.addWidget(self.list_title)
        lay.addWidget(library, 1)
        foot = QHBoxLayout()
        self.options_btn = QPushButton("Velocidade e repetições")
        self.options_btn.setObjectName("flat")
        self.options_btn.clicked.connect(lambda: self.show_view(OPTIONS))
        self.import_btn = QPushButton("Importar…")
        self.import_btn.setObjectName("flat")
        self.import_btn.clicked.connect(library.import_macro)
        foot.addWidget(self.options_btn)
        foot.addStretch(1)
        foot.addWidget(self.import_btn)
        lay.addLayout(foot)
        self.views.addWidget(lst)

        # ---- visões 2 e 3: gravação e opções (com botão de voltar) --------------------------
        self.views.addWidget(self._with_back(recorder, "Gravar"))
        self.views.addWidget(self._with_back(player, "Velocidade e repetições"))
        self.apply_theme()
        self.refresh_hotkeys()

    def _with_back(self, tab: QWidget, title: str) -> QWidget:
        box = QWidget()
        lay = QVBoxLayout(box)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(8)
        back = QPushButton(" Macros")
        back.setObjectName("flat")
        back.setCursor(Qt.CursorShape.PointingHandCursor)
        back.clicked.connect(lambda: self.show_view(LIST))
        row = QHBoxLayout()
        row.addWidget(back)
        row.addStretch(1)
        lay.addLayout(row)
        lay.addWidget(scrolled(tab), 1)
        back.setProperty("backbtn", True)
        return box

    def _backs(self) -> list[QPushButton]:
        return [b for b in self.findChildren(QPushButton) if b.property("backbtn")]

    # ---- navegação ------------------------------------------------------------------------
    def show_view(self, index: int) -> None:
        self.views.setCurrentIndex(index)

    def new_recording(self) -> None:
        self.show_view(RECORD)
        self.recorder._start()

    def apply_theme(self) -> None:
        c = palette(self.ctx.settings.ui.theme)
        self.record_btn.setIcon(icons.record(c["accent_text"]))
        for back in self._backs():
            back.setIcon(icons.chevron_left(c["muted"]))
            back.setIconSize(QSize(16, 16))

    def refresh_hotkeys(self) -> None:
        self.hint.setText(f"Atalho para gravar: {self.ctx.settings.hotkeys.record_start}")

    def set_state(self, state) -> None:
        idle = state.value == "idle"
        self.record_btn.setEnabled(idle)
