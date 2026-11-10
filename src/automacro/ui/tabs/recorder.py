"""Aba Gravador."""

from __future__ import annotations

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QCheckBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
)

from automacro.core.errors import AutoMacroError
from automacro.core.event_bus import RecordingCount, RecordingFinished
from automacro.core.session import ACTIVITY_RECORD
from automacro.input_handlers.capabilities import Feature
from automacro.models.macro import Macro
from automacro.models.settings import AppSettings
from automacro.models.state import AppState
from automacro.ui.tabs.base import BaseTab
from automacro.ui.widgets import Card, fmt_duration, heading, muted_label


class RecorderTab(BaseTab):
    macro_saved = Signal(str)          # id da macro salva

    def __init__(self, ctx, on_error) -> None:
        super().__init__(ctx)
        self._on_error = on_error
        self._pending: Macro | None = None

        root = QVBoxLayout(self)
        root.setContentsMargins(18, 18, 18, 18)
        root.setSpacing(14)

        opts = Card()
        opts.body.addWidget(heading("Opções de gravação"))
        self.moves = QCheckBox("Gravar movimentos do mouse (gera macros maiores)")
        self.scroll = QCheckBox("Gravar rolagem do mouse")
        opts.body.addWidget(self.moves)
        opts.body.addWidget(self.scroll)
        opts.body.addWidget(muted_label(
            "Cliques e teclas são sempre gravados, junto com o tempo entre cada ação. "
            "As teclas de atalho do AutoMacro não entram na gravação."))
        root.addWidget(opts)

        run = Card()
        row = QHBoxLayout()
        self.start_btn = QPushButton("● Iniciar gravação")
        self.start_btn.setObjectName("primary")
        self.start_btn.clicked.connect(self._start)
        self.stop_btn = QPushButton("■ Finalizar gravação")
        self.stop_btn.setObjectName("stop")
        self.stop_btn.clicked.connect(lambda: self.ctx.session.stop_recording())
        row.addWidget(self.start_btn)
        row.addWidget(self.stop_btn)
        row.addStretch(1)
        self.count = QLabel("0")
        self.count.setObjectName("bigNumber")
        row.addWidget(self.count)
        row.addWidget(muted_label("eventos"))
        run.body.addLayout(row)
        self.hint = muted_label()
        run.body.addWidget(self.hint)
        root.addWidget(run)

        self.result = Card()
        self.result.body.addWidget(heading("Gravação concluída"))
        self.summary = muted_label()
        self.result.body.addWidget(self.summary)
        name_row = QHBoxLayout()
        self.name = QLineEdit()
        self.name.setPlaceholderText("Nome da macro")
        self.save_btn = QPushButton("Salvar na biblioteca")
        self.save_btn.setObjectName("primary")
        self.save_btn.clicked.connect(self._save)
        self.discard_btn = QPushButton("Descartar")
        self.discard_btn.clicked.connect(self._discard)
        name_row.addWidget(self.name, 1)
        name_row.addWidget(self.save_btn)
        name_row.addWidget(self.discard_btn)
        self.result.body.addLayout(name_row)
        self.result.hide()
        root.addWidget(self.result)
        root.addStretch(1)

        self.load_settings(ctx.settings)
        self.refresh_hotkeys()
        self.set_state(AppState.IDLE, None)
        status = ctx.session.capabilities().status(Feature.CAPTURE)
        if not ctx.session.capabilities().available(Feature.CAPTURE):
            self.start_btn.setToolTip(status.reason)

    # ---- API para a janela ----------------------------------------------------------
    @property
    def has_unsaved(self) -> bool:
        return self._pending is not None

    def confirm_discard_pending(self) -> bool:
        """Pergunta antes de perder uma gravação não salva. True = pode seguir."""
        if self._pending is None:
            return True
        answer = QMessageBox.question(
            self, "Gravação não salva",
            "Há uma gravação que ainda não foi salva. Descartá-la?",
            QMessageBox.StandardButton.Discard | QMessageBox.StandardButton.Cancel,
            QMessageBox.StandardButton.Cancel)
        if answer == QMessageBox.StandardButton.Discard:
            self._discard()
            return True
        return False

    # ---- ações ----------------------------------------------------------------------
    def _start(self) -> None:
        if not self.confirm_discard_pending():
            return
        self.collect_settings(self.ctx.settings)
        self.count.setText("0")
        try:
            self.ctx.session.start_recording()
        except AutoMacroError as exc:
            self._on_error(str(exc))

    def _save(self) -> None:
        if self._pending is None:
            return
        name = self.name.text().strip()
        if not name:
            self._on_error("Dê um nome à macro antes de salvar.")
            return
        macro = self._pending
        macro.name = name
        try:
            saved = self.ctx.repo.save(macro)
        except Exception as exc:
            self._on_error(f"Não foi possível salvar a macro: {exc}")
            return
        self._pending = None
        self.result.hide()
        self.macro_saved.emit(saved.id)

    def _discard(self) -> None:
        self._pending = None
        self.result.hide()

    def collect_settings(self, settings: AppSettings) -> None:
        settings.recorder.record_mouse_moves = self.moves.isChecked()
        settings.recorder.record_scroll = self.scroll.isChecked()

    def load_settings(self, settings: AppSettings) -> None:
        self.moves.setChecked(settings.recorder.record_mouse_moves)
        self.scroll.setChecked(settings.recorder.record_scroll)

    def set_state(self, state: AppState, activity: str | None) -> None:
        idle = state is AppState.IDLE
        self.start_btn.setEnabled(idle)
        self.stop_btn.setEnabled(activity == ACTIVITY_RECORD and not idle)
        self.moves.setEnabled(idle)
        self.scroll.setEnabled(idle)

    def handle_event(self, event: object) -> None:
        if isinstance(event, RecordingCount):
            self.count.setText(str(event.count))
        elif isinstance(event, RecordingFinished):
            macro: Macro = event.macro
            self.count.setText(str(len(macro.events)))
            if not macro.events:
                self._pending = None
                self.result.hide()
                self._on_error("Nada foi gravado: nenhuma ação de mouse ou teclado foi detectada.")
                return
            self._pending = macro
            s = macro.summary()
            self.summary.setText(
                f"{s.events} eventos • duração {fmt_duration(s.duration_ms)} • "
                f"{s.clicks} cliques • {s.moves} movimentos • {s.scrolls} rolagens • "
                f"{s.key_events} eventos de teclado")
            self.name.setText(macro.name)
            self.result.show()
            self.name.setFocus()
            self.name.selectAll()

    def refresh_hotkeys(self) -> None:
        self.hint.setText(f"Atalhos: {self.hotkey('record_start')} inicia  •  "
                          f"{self.hotkey('record_stop')} finaliza")
