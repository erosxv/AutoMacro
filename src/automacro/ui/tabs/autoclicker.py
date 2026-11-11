"""Aba Auto Clicker."""

from __future__ import annotations

from PySide6.QtCore import QTimer
from PySide6.QtWidgets import (
    QButtonGroup,
    QComboBox,
    QCheckBox,
    QDoubleSpinBox,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QRadioButton,
    QSpinBox,
    QVBoxLayout,
)

from automacro.core.errors import AutoMacroError
from automacro.core.event_bus import ClickCount
from automacro.core.session import ACTIVITY_AUTOCLICK
from automacro.input_handlers.capabilities import Feature
from automacro.models.settings import AppSettings, AutoClickConfig
from automacro.models.state import AppState
from automacro.ui.tabs.base import BaseTab
from automacro.ui.widgets import Card, heading, muted_label

BUTTONS = [("Botão esquerdo", "left"), ("Botão direito", "right"), ("Botão do meio", "middle")]


class AutoClickerTab(BaseTab):
    def __init__(self, ctx, on_error) -> None:
        super().__init__(ctx)
        self._on_error = on_error
        self._unit_is_seconds = False

        root = QVBoxLayout(self)
        root.setContentsMargins(18, 18, 18, 18)
        root.setSpacing(14)

        card = Card()
        card.body.addWidget(heading("Configuração dos cliques"))
        form = QFormLayout()
        form.setRowWrapPolicy(QFormLayout.RowWrapPolicy.WrapLongRows)
        form.setHorizontalSpacing(18)
        form.setVerticalSpacing(10)

        self.button = QComboBox()
        for label, value in BUTTONS:
            self.button.addItem(label, value)
        form.addRow("Botão do mouse", self.button)

        interval_row = QHBoxLayout()
        self.interval = QDoubleSpinBox()
        self.interval.setDecimals(0)
        self.interval.setRange(1, 86_400_000)
        self.interval.setValue(100)
        self.unit = QComboBox()
        self.unit.addItems(["milissegundos", "segundos"])
        self.unit.currentIndexChanged.connect(self._unit_changed)
        interval_row.addWidget(self.interval, 1)
        interval_row.addWidget(self.unit, 1)
        form.addRow("Intervalo entre cliques", interval_row)

        count_row = QHBoxLayout()
        self.count = QSpinBox()
        self.count.setRange(1, 100_000_000)
        self.count.setValue(100)
        self.infinite = QCheckBox("Infinito")
        self.infinite.setChecked(True)
        self.infinite.toggled.connect(lambda on: self.count.setEnabled(not on))
        self.count.setEnabled(False)
        count_row.addWidget(self.count, 1)
        count_row.addWidget(self.infinite)
        form.addRow("Quantidade de cliques", count_row)

        self.max_runtime = QSpinBox()
        self.max_runtime.setRange(0, 86_400)
        self.max_runtime.setSuffix(" s  (0 = sem limite)")
        form.addRow("Tempo máximo", self.max_runtime)
        card.body.addLayout(form)
        root.addWidget(card)

        pos = Card()
        pos.body.addWidget(heading("Onde clicar"))
        self.pos_current = QRadioButton("Na posição atual do cursor")
        self.pos_fixed = QRadioButton("Em uma coordenada específica")
        self.pos_current.setChecked(True)
        group = QButtonGroup(self)
        group.addButton(self.pos_current)
        group.addButton(self.pos_fixed)
        pos.body.addWidget(self.pos_current)
        pos.body.addWidget(self.pos_fixed)
        coords = QHBoxLayout()
        self.x = QSpinBox(); self.x.setRange(-100_000, 100_000); self.x.setPrefix("X  ")
        self.y = QSpinBox(); self.y.setRange(-100_000, 100_000); self.y.setPrefix("Y  ")
        self.capture_btn = QPushButton("Capturar posição (em 3 s)")
        self.capture_btn.clicked.connect(self._capture_position)
        coords.addWidget(self.x, 1); coords.addWidget(self.y, 1)
        pos.body.addLayout(coords)
        pos.body.addWidget(self.capture_btn)
        self.pos_fixed.toggled.connect(self._pos_mode_changed)
        self._pos_mode_changed()
        root.addWidget(pos)

        run = Card()
        self.run_card = run     # fica fixo embaixo da janela (fora da rolagem)
        row = QHBoxLayout()
        self.start_btn = QPushButton("Iniciar")
        self.start_btn.setObjectName("primary")
        self.start_btn.clicked.connect(self._start)
        self.stop_btn = QPushButton("Parar")
        self.stop_btn.setObjectName("stop")
        self.stop_btn.clicked.connect(lambda: self.ctx.session.stop())
        row.addWidget(self.start_btn)
        row.addWidget(self.stop_btn)
        row.addStretch(1)
        self.counter = QLabel("0")
        self.counter.setObjectName("bigNumber")
        self.counter_caption = muted_label("cliques")
        row.addWidget(self.counter)
        row.addWidget(self.counter_caption)
        run.body.addLayout(row)
        self.hint = muted_label()
        run.body.addWidget(self.hint)
        root.addWidget(run)
        root.addStretch(1)

        caps = ctx.session.capabilities()
        if not caps.available(Feature.CURSOR_POSITION):
            self.capture_btn.setEnabled(False)
            self.capture_btn.setToolTip(caps.status(Feature.CURSOR_POSITION).reason)
        self.load_settings(ctx.settings)
        self.refresh_hotkeys()
        self.set_state(AppState.IDLE, None)

    # ---- configuração <-> widgets ---------------------------------------------------
    def _unit_changed(self) -> None:
        to_seconds = self.unit.currentIndex() == 1
        if to_seconds == self._unit_is_seconds:
            return
        value = self.interval.value()
        if to_seconds:
            self.interval.setDecimals(3)
            self.interval.setRange(0.001, 86_400)
            self.interval.setValue(value / 1000.0)
        else:
            self.interval.setRange(1, 86_400_000)
            self.interval.setDecimals(0)
            self.interval.setValue(value * 1000.0)
        self._unit_is_seconds = to_seconds

    def interval_ms(self) -> float:
        value = self.interval.value()
        return value * 1000.0 if self._unit_is_seconds else value

    def _pos_mode_changed(self) -> None:
        fixed = self.pos_fixed.isChecked()
        for w in (self.x, self.y):
            w.setEnabled(fixed)

    def _capture_position(self) -> None:
        self.capture_btn.setEnabled(False)
        remaining = {"n": 3}

        def tick() -> None:
            if remaining["n"] > 0:
                self.capture_btn.setText(f"Posicione o cursor… {remaining['n']}")
                remaining["n"] -= 1
                QTimer.singleShot(1000, tick)
                return
            pos = self.ctx.session.cursor_position()
            self.capture_btn.setText("Capturar posição (em 3 s)")
            self.capture_btn.setEnabled(True)
            if pos is None:
                self._on_error("Não foi possível ler a posição do cursor neste sistema.")
                return
            self.x.setValue(pos[0]); self.y.setValue(pos[1])
            self.pos_fixed.setChecked(True)

        tick()

    def collect_settings(self, settings: AppSettings) -> None:
        cfg = settings.autoclick
        cfg.button = self.button.currentData()
        cfg.interval_ms = self.interval_ms()
        cfg.count = 0 if self.infinite.isChecked() else self.count.value()
        cfg.use_fixed_position = self.pos_fixed.isChecked()
        cfg.x, cfg.y = self.x.value(), self.y.value()
        cfg.max_runtime_s = float(self.max_runtime.value())

    def load_settings(self, settings: AppSettings) -> None:
        cfg = settings.autoclick
        self.button.setCurrentIndex(max(0, self.button.findData(cfg.button)))
        use_seconds = cfg.interval_ms >= 1000 and cfg.interval_ms % 1000 == 0
        self.unit.setCurrentIndex(1 if use_seconds else 0)
        self._unit_changed()
        self.interval.setValue(cfg.interval_ms / 1000.0 if use_seconds else cfg.interval_ms)
        self.infinite.setChecked(cfg.count == 0)
        self.count.setValue(cfg.count or 100)
        (self.pos_fixed if cfg.use_fixed_position else self.pos_current).setChecked(True)
        self.x.setValue(cfg.x); self.y.setValue(cfg.y)
        self.max_runtime.setValue(int(cfg.max_runtime_s))

    # ---- ações ----------------------------------------------------------------------
    def _start(self) -> None:
        self.collect_settings(self.ctx.settings)
        self.counter.setText("0")
        try:
            self.ctx.session.start_autoclick()
        except AutoMacroError as exc:
            self._on_error(str(exc))

    def set_state(self, state: AppState, activity: str | None) -> None:
        idle = state is AppState.IDLE
        running = activity == ACTIVITY_AUTOCLICK and not idle
        self.start_btn.setEnabled(idle)
        self.stop_btn.setEnabled(running)
        for w in (self.button, self.interval, self.unit, self.count, self.infinite,
                  self.max_runtime, self.pos_current, self.pos_fixed):
            w.setEnabled(idle)
        if idle:
            self.count.setEnabled(not self.infinite.isChecked())
            self._pos_mode_changed()
        else:
            self.x.setEnabled(False); self.y.setEnabled(False)

    def handle_event(self, event: object) -> None:
        if isinstance(event, ClickCount):
            target = f" / {event.target}" if event.target else ""
            self.counter.setText(f"{event.count}{target}")
            self.counter_caption.setText("clique" if event.count == 1 else "cliques")

    def refresh_hotkeys(self) -> None:
        self.hint.setText(f"Atalho para iniciar/parar: {self.hotkey('autoclick_toggle')}  •  "
                          f"Parada de emergência: {self.hotkey('emergency')}")
