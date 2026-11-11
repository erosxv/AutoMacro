"""Aba Reprodutor."""

from __future__ import annotations

from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDoubleSpinBox,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QSpinBox,
    QVBoxLayout,
)

from automacro.core.errors import AutoMacroError, ConfirmationRequired
from automacro.core.event_bus import Countdown, Progress
from automacro.core.session import ACTIVITY_PLAY
from automacro.models.macro import Macro
from automacro.models.settings import AppSettings
from automacro.models.state import AppState
from automacro.storage.repository import MacroNotFoundError
from automacro.ui.tabs.base import BaseTab
from automacro.ui.widgets import Card, fmt_duration, heading, muted_label


class PlayerTab(BaseTab):
    def __init__(self, ctx, on_error) -> None:
        super().__init__(ctx)
        self._on_error = on_error
        self._macro: Macro | None = None
        self._state = AppState.IDLE

        root = QVBoxLayout(self)
        root.setContentsMargins(18, 18, 18, 18)
        root.setSpacing(14)

        pick = Card()
        pick.body.addWidget(heading("Macro"))
        row = QHBoxLayout()
        self.combo = QComboBox()
        self.combo.setMinimumWidth(120)
        self.combo.currentIndexChanged.connect(self._selection_changed)
        refresh = QPushButton("Atualizar")
        refresh.clicked.connect(self.refresh_macros)
        row.addWidget(self.combo, 1)
        row.addWidget(refresh)
        pick.body.addLayout(row)
        self.info = muted_label("Nenhuma macro selecionada. Grave uma ou importe pela Biblioteca.")
        pick.body.addWidget(self.info)
        root.addWidget(pick)

        opts = Card()
        opts.body.addWidget(heading("Reprodução"))
        form = QFormLayout()
        form.setRowWrapPolicy(QFormLayout.RowWrapPolicy.WrapLongRows)
        form.setHorizontalSpacing(18)
        self.speed = QDoubleSpinBox()
        self.speed.setRange(0.05, 20.0); self.speed.setSingleStep(0.25); self.speed.setDecimals(2)
        self.speed.setSuffix(" ×"); self.speed.setValue(1.0)
        form.addRow("Velocidade", self.speed)
        rep = QHBoxLayout()
        self.repeat = QSpinBox(); self.repeat.setRange(1, 10_000_000); self.repeat.setValue(1)
        self.infinite = QCheckBox("Infinito")
        self.infinite.toggled.connect(lambda on: self.repeat.setEnabled(not on))
        rep.addWidget(self.repeat, 1); rep.addWidget(self.infinite)
        form.addRow("Repetições", rep)
        self.loop_delay = QSpinBox()
        self.loop_delay.setRange(0, 3_600_000); self.loop_delay.setSuffix(" ms")
        form.addRow("Pausa entre repetições", self.loop_delay)
        opts.body.addLayout(form)
        root.addWidget(opts)

        run = Card()
        buttons = QHBoxLayout()
        self.play_btn = QPushButton("Reproduzir")
        self.play_btn.setObjectName("primary")
        self.play_btn.clicked.connect(self._play)
        self.pause_btn = QPushButton("Pausar")
        self.pause_btn.clicked.connect(lambda: self.ctx.session.toggle_pause())
        self.stop_btn = QPushButton("Parar")
        self.stop_btn.setObjectName("stop")
        self.stop_btn.clicked.connect(lambda: self.ctx.session.stop())
        for b in (self.play_btn, self.pause_btn, self.stop_btn):
            buttons.addWidget(b)
        buttons.addStretch(1)
        run.body.addLayout(buttons)
        self.progress = QProgressBar()
        self.progress.setRange(0, 100)
        self.progress.setValue(0)
        run.body.addWidget(self.progress)
        self.progress_text = muted_label("Pronto")
        run.body.addWidget(self.progress_text)
        self.hint = muted_label()
        run.body.addWidget(self.hint)
        root.addWidget(run)
        root.addStretch(1)

        self.load_settings(ctx.settings)
        self.refresh_macros()
        self.refresh_hotkeys()
        self.set_state(AppState.IDLE, None)

    # ---- seleção de macro -------------------------------------------------------------
    def refresh_macros(self, select_id: str | None = None) -> None:
        current = select_id or (self._macro.id if self._macro else None)
        self.combo.blockSignals(True)
        self.combo.clear()
        for info in self.ctx.repo.list():
            self.combo.addItem(f"{info.name}  ({info.event_count} eventos)", info.id)
        index = self.combo.findData(current) if current else -1
        self.combo.setCurrentIndex(index if index >= 0 else (0 if self.combo.count() else -1))
        self.combo.blockSignals(False)
        self._selection_changed()

    def select_macro(self, macro_id: str) -> None:
        self.refresh_macros(select_id=macro_id)

    def _selection_changed(self) -> None:
        macro_id = self.combo.currentData()
        self._macro = None
        if macro_id:
            try:
                self._macro = self.ctx.repo.load(macro_id)
            except (MacroNotFoundError, Exception) as exc:
                self.info.setText(f"Não foi possível carregar a macro: {exc}")
        self.ctx.session.set_current_macro(self._macro)
        if self._macro is None:
            self.info.setText("Nenhuma macro selecionada. Grave uma ou importe pela Biblioteca.")
        else:
            s = self._macro.summary()
            imported = "  •  importada" if self._macro.imported else ""
            self.info.setText(f"{s.events} eventos • duração {fmt_duration(s.duration_ms)} • "
                              f"{s.clicks} cliques • {s.key_events} eventos de teclado{imported}")
        self.progress.setValue(0)
        self.progress_text.setText("Pronto")
        self.set_state(self._state, self.ctx.session.activity)

    # ---- ações ------------------------------------------------------------------------
    def _play(self) -> None:
        if self._macro is None:
            self._on_error("Selecione uma macro para reproduzir.")
            return
        self.collect_settings(self.ctx.settings)
        self.progress.setValue(0)
        confirmed = False
        while True:
            try:
                self.ctx.session.play(self._macro, confirmed=confirmed)
                return
            except ConfirmationRequired:
                answer = QMessageBox.warning(
                    self, "Macro importada",
                    f"A macro \"{self._macro.name}\" foi importada e pode executar qualquer "
                    "ação de mouse e teclado neste computador.\n\n"
                    "Só continue se você confiou na origem do arquivo.",
                    QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.Cancel,
                    QMessageBox.StandardButton.Cancel)
                if answer != QMessageBox.StandardButton.Yes:
                    return
                self._macro.imported = False            # confiada: não pergunta de novo
                try:
                    self.ctx.repo.save(self._macro, ensure_unique_name=False)
                except Exception:
                    pass
                confirmed = True
            except AutoMacroError as exc:
                self._on_error(str(exc))
                return

    def collect_settings(self, settings: AppSettings) -> None:
        settings.player.speed = self.speed.value()
        settings.player.repeat = 0 if self.infinite.isChecked() else self.repeat.value()
        settings.player.loop_delay_ms = float(self.loop_delay.value())

    def load_settings(self, settings: AppSettings) -> None:
        p = settings.player
        self.speed.setValue(p.speed)
        self.infinite.setChecked(p.repeat == 0)
        self.repeat.setValue(p.repeat or 1)
        self.loop_delay.setValue(int(p.loop_delay_ms))

    def set_state(self, state: AppState, activity: str | None) -> None:
        self._state = state
        idle = state is AppState.IDLE
        playing = activity == ACTIVITY_PLAY and not idle
        self.play_btn.setEnabled(idle and self._macro is not None)
        self.pause_btn.setEnabled(state in (AppState.PLAYING, AppState.PAUSED))
        self.pause_btn.setText("▶ Continuar" if state is AppState.PAUSED else "Pausar")
        self.stop_btn.setEnabled(playing)
        for w in (self.combo, self.speed, self.infinite, self.loop_delay):
            w.setEnabled(idle)
        self.repeat.setEnabled(idle and not self.infinite.isChecked())

    def handle_event(self, event: object) -> None:
        if isinstance(event, Progress):
            self.progress.setValue(int(event.done * 100 / max(event.total, 1)))
            loops = "∞" if event.loops == 0 else str(event.loops)
            self.progress_text.setText(
                f"Evento {event.done}/{event.total}  •  repetição {event.loop}/{loops}")
        elif isinstance(event, Countdown) and event.activity == ACTIVITY_PLAY:
            self.progress_text.setText(f"Começando em {event.remaining}…")

    def refresh_hotkeys(self) -> None:
        self.hint.setText(f"Atalhos: {self.hotkey('play_start')} reproduz  •  "
                          f"{self.hotkey('play_pause')} pausa/continua  •  "
                          f"{self.hotkey('stop')} interrompe")
