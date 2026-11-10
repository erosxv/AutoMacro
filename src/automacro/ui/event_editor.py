"""Editor de eventos de uma macro (alterar eventos e delays, remover, ajustar tempos)."""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QAbstractItemView,
    QDialog,
    QDialogButtonBox,
    QDoubleSpinBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QMessageBox,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
)

from automacro.input_handlers.keymap import display_key
from automacro.models.events import (
    EVENT_LABELS,
    KEY_EVENTS,
    MOUSE_BUTTON_EVENTS,
    EventType,
    MacroEvent,
    MacroFormatError,
)
from automacro.models.macro import Macro
from automacro.ui.widgets import fmt_duration

COLUMNS = ["#", "Evento", "Delay (ms)", "X", "Y", "Botão / Tecla / Rolagem"]
_DETAIL_COL = 5


class EventEditorDialog(QDialog):
    """Edita os eventos de uma ``Macro`` em uma tabela. ``result_events`` traz o resultado."""

    def __init__(self, macro: Macro, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle(f"Editar eventos — {macro.name}")
        self.resize(820, 560)
        self._events = [e.copy() for e in macro.events]
        self.result_events: list[MacroEvent] | None = None
        self._loading = False

        layout = QVBoxLayout(self)
        self.table = QTableWidget(0, len(COLUMNS))
        self.table.setHorizontalHeaderLabels(COLUMNS)
        self.table.setAlternatingRowColors(True)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.verticalHeader().setVisible(False)
        header = self.table.horizontalHeader()
        header.setSectionResizeMode(QHeaderView.ResizeMode.Interactive)
        header.setStretchLastSection(True)
        self.table.setColumnWidth(0, 50)
        self.table.setColumnWidth(1, 160)
        self.table.setColumnWidth(2, 110)
        self.table.setColumnWidth(3, 70)
        self.table.setColumnWidth(4, 70)
        self.table.itemChanged.connect(self._item_changed)
        layout.addWidget(self.table, 1)

        tools = QHBoxLayout()
        delete = QPushButton("Remover selecionados")
        delete.clicked.connect(self._delete_selected)
        self.factor = QDoubleSpinBox()
        self.factor.setRange(0.01, 100.0); self.factor.setValue(1.0)
        self.factor.setDecimals(2); self.factor.setPrefix("× ")
        scale = QPushButton("Multiplicar todos os delays")
        scale.clicked.connect(self._scale_delays)
        set_all = QPushButton("Delays dos selecionados = …")
        self.fixed = QDoubleSpinBox()
        self.fixed.setRange(0, 3_600_000); self.fixed.setValue(50); self.fixed.setSuffix(" ms")
        set_all.clicked.connect(self._set_selected_delay)
        tools.addWidget(delete)
        tools.addStretch(1)
        tools.addWidget(self.factor); tools.addWidget(scale)
        tools.addWidget(self.fixed); tools.addWidget(set_all)
        layout.addLayout(tools)

        self.footer = QLabel()
        self.footer.setProperty("muted", True)
        layout.addWidget(self.footer)

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Save |
                                   QDialogButtonBox.StandardButton.Cancel)
        buttons.button(QDialogButtonBox.StandardButton.Save).setText("Salvar alterações")
        buttons.button(QDialogButtonBox.StandardButton.Cancel).setText("Cancelar")
        buttons.accepted.connect(self._accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)
        self._reload()

    # ---- tabela -----------------------------------------------------------------------
    @staticmethod
    def _detail(ev: MacroEvent) -> str:
        if ev.type in MOUSE_BUTTON_EVENTS:
            return {"left": "esquerdo", "right": "direito", "middle": "meio"}.get(ev.button, ev.button or "")
        if ev.type in KEY_EVENTS:
            return ev.key or ""
        if ev.type is EventType.MOUSE_SCROLL:
            return f"{ev.dx},{ev.dy}"
        return ""

    def _reload(self) -> None:
        self._loading = True
        self.table.setRowCount(len(self._events))
        for row, ev in enumerate(self._events):
            self._set_cell(row, 0, str(row + 1), editable=False)
            self._set_cell(row, 1, EVENT_LABELS[ev.type], editable=False)
            self._set_cell(row, 2, f"{ev.delay_ms:g}")
            self._set_cell(row, 3, "" if ev.x is None else str(ev.x))
            self._set_cell(row, 4, "" if ev.y is None else str(ev.y))
            tip = f"tecla: {display_key(ev.key)}" if ev.type in KEY_EVENTS and ev.key else ""
            self._set_cell(row, _DETAIL_COL, self._detail(ev), tip=tip)
        self._loading = False
        self._update_footer()

    def _set_cell(self, row: int, col: int, text: str, editable: bool = True, tip: str = "") -> None:
        item = QTableWidgetItem(text)
        if not editable:
            item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsEditable)
        if tip:
            item.setToolTip(tip)
        self.table.setItem(row, col, item)

    def _update_footer(self) -> None:
        total = sum(e.delay_ms for e in self._events)
        self.footer.setText(f"{len(self._events)} eventos • duração total {fmt_duration(total)}")

    def _item_changed(self, item: QTableWidgetItem) -> None:
        if self._loading:
            return
        row, col, text = item.row(), item.column(), item.text().strip()
        ev = self._events[row]
        old = event_snapshot(ev)
        try:
            if col == 2:
                ev.delay_ms = float(text.replace(",", "."))
            elif col in (3, 4):
                value = int(text) if text else None
                setattr(ev, "x" if col == 3 else "y", value)
            elif col == _DETAIL_COL:
                self._apply_detail(ev, text)
            ev.validate()
        except (ValueError, MacroFormatError) as exc:
            restore_event(ev, old)
            QMessageBox.warning(self, "Valor inválido", f"Linha {row + 1}: {exc}")
        self._reload_row(row)
        self._update_footer()

    @staticmethod
    def _apply_detail(ev: MacroEvent, text: str) -> None:
        if ev.type in MOUSE_BUTTON_EVENTS:
            names = {"esquerdo": "left", "direito": "right", "meio": "middle",
                     "left": "left", "right": "right", "middle": "middle"}
            if text.lower() not in names:
                raise ValueError("use: esquerdo, direito ou meio")
            ev.button = names[text.lower()]
        elif ev.type in KEY_EVENTS:
            ev.key = text
        elif ev.type is EventType.MOUSE_SCROLL:
            try:
                dx, dy = (int(p) for p in text.split(","))
            except ValueError:
                raise ValueError("use o formato dx,dy (ex.: 0,-1)") from None
            ev.dx, ev.dy = dx, dy

    def _reload_row(self, row: int) -> None:
        ev = self._events[row]
        self._loading = True
        self.table.item(row, 2).setText(f"{ev.delay_ms:g}")
        self.table.item(row, 3).setText("" if ev.x is None else str(ev.x))
        self.table.item(row, 4).setText("" if ev.y is None else str(ev.y))
        self.table.item(row, _DETAIL_COL).setText(self._detail(ev))
        self._loading = False

    # ---- ferramentas ------------------------------------------------------------------
    def _selected_rows(self) -> list[int]:
        return sorted({i.row() for i in self.table.selectedIndexes()})

    def _delete_selected(self) -> None:
        rows = self._selected_rows()
        if not rows:
            return
        # O tempo dos eventos removidos passa para o seguinte, preservando a duração total.
        for row in reversed(rows):
            removed = self._events.pop(row)
            if row < len(self._events):
                self._events[row].delay_ms += removed.delay_ms
        self._reload()

    def _scale_delays(self) -> None:
        factor = self.factor.value()
        for ev in self._events:
            ev.delay_ms = min(ev.delay_ms * factor, 24 * 3600 * 1000.0)
        self._reload()

    def _set_selected_delay(self) -> None:
        for row in self._selected_rows():
            self._events[row].delay_ms = self.fixed.value()
        self._reload()

    def _accept(self) -> None:
        try:
            for ev in self._events:
                ev.validate()
        except MacroFormatError as exc:
            QMessageBox.warning(self, "Macro inválida", str(exc))
            return
        self.result_events = self._events
        self.accept()


def event_snapshot(ev: MacroEvent) -> tuple:
    return (ev.type, ev.delay_ms, ev.x, ev.y, ev.button, ev.dx, ev.dy, ev.key)


def restore_event(ev: MacroEvent, snap: tuple) -> None:
    ev.type, ev.delay_ms, ev.x, ev.y, ev.button, ev.dx, ev.dy, ev.key = snap
