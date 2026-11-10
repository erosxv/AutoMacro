"""Aba Biblioteca de macros."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QAbstractItemView,
    QFileDialog,
    QHBoxLayout,
    QHeaderView,
    QInputDialog,
    QMessageBox,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
)

from automacro.models.events import MacroFormatError
from automacro.storage.repository import MacroNotFoundError
from automacro.ui.event_editor import EventEditorDialog
from automacro.ui.tabs.base import BaseTab
from automacro.ui.widgets import fmt_duration, muted_label


class LibraryTab(BaseTab):
    use_in_player = Signal(str)        # id da macro
    changed = Signal()                 # biblioteca mudou (para atualizar o Reprodutor)

    def __init__(self, ctx, on_error) -> None:
        super().__init__(ctx)
        self._on_error = on_error

        root = QVBoxLayout(self)
        root.setContentsMargins(18, 18, 18, 18)
        root.setSpacing(12)

        self.table = QTableWidget(0, 5)
        self.table.setHorizontalHeaderLabels(["Nome", "Eventos", "Duração", "Atualizada em", "Origem"])
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.setAlternatingRowColors(True)
        self.table.verticalHeader().setVisible(False)
        header = self.table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        for col in (1, 2, 3, 4):
            header.setSectionResizeMode(col, QHeaderView.ResizeMode.ResizeToContents)
        self.table.itemSelectionChanged.connect(self._update_buttons)
        self.table.itemDoubleClicked.connect(lambda *_: self._use())
        root.addWidget(self.table, 1)

        self.empty = muted_label("A biblioteca está vazia. Grave uma macro ou importe um arquivo .json.")
        root.addWidget(self.empty)

        row = QHBoxLayout()
        self.use_btn = QPushButton("Usar no Reprodutor")
        self.use_btn.setObjectName("primary")
        self.use_btn.clicked.connect(self._use)
        self.edit_btn = QPushButton("Editar eventos…")
        self.edit_btn.clicked.connect(self._edit)
        self.rename_btn = QPushButton("Renomear")
        self.rename_btn.clicked.connect(self._rename)
        self.dup_btn = QPushButton("Duplicar")
        self.dup_btn.clicked.connect(self._duplicate)
        self.delete_btn = QPushButton("Excluir")
        self.delete_btn.clicked.connect(self._delete)
        for b in (self.use_btn, self.edit_btn, self.rename_btn, self.dup_btn, self.delete_btn):
            row.addWidget(b)
        row.addStretch(1)
        self.import_btn = QPushButton("Importar…")
        self.import_btn.clicked.connect(self._import)
        self.export_btn = QPushButton("Exportar…")
        self.export_btn.clicked.connect(self._export)
        row.addWidget(self.import_btn)
        row.addWidget(self.export_btn)
        root.addLayout(row)

        self.refresh()

    # ---- dados ------------------------------------------------------------------------
    def refresh(self, select_id: str | None = None) -> None:
        keep = select_id or self.selected_id()
        infos = self.ctx.repo.list()
        self.table.setRowCount(len(infos))
        for row, info in enumerate(infos):
            cells = [info.name, str(info.event_count), fmt_duration(info.duration_ms),
                     info.updated_at.replace("T", " ")[:16], "importada" if info.imported else "gravada"]
            for col, text in enumerate(cells):
                item = QTableWidgetItem(text)
                if col == 0:
                    item.setData(Qt.ItemDataRole.UserRole, info.id)
                self.table.setItem(row, col, item)
            if info.id == keep:
                self.table.selectRow(row)
        self.empty.setVisible(not infos)
        self._update_buttons()

    def selected_id(self) -> str | None:
        rows = self.table.selectionModel().selectedRows() if self.table.selectionModel() else []
        if not rows:
            return None
        item = self.table.item(rows[0].row(), 0)
        return item.data(Qt.ItemDataRole.UserRole) if item else None

    def _update_buttons(self) -> None:
        has = self.selected_id() is not None
        for b in (self.use_btn, self.edit_btn, self.rename_btn, self.dup_btn, self.delete_btn,
                  self.export_btn):
            b.setEnabled(has)

    # ---- ações ------------------------------------------------------------------------
    def _use(self) -> None:
        macro_id = self.selected_id()
        if macro_id:
            self.use_in_player.emit(macro_id)

    def _edit(self) -> None:
        macro_id = self.selected_id()
        if not macro_id:
            return
        try:
            macro = self.ctx.repo.load(macro_id)
        except (MacroNotFoundError, MacroFormatError) as exc:
            self._on_error(f"Não foi possível abrir a macro: {exc}")
            return
        dialog = EventEditorDialog(macro, self)
        if dialog.exec() and dialog.result_events is not None:
            macro.events = dialog.result_events
            self.ctx.repo.save(macro, ensure_unique_name=False)
            self.refresh(macro_id)
            self.changed.emit()

    def _rename(self) -> None:
        macro_id = self.selected_id()
        if not macro_id:
            return
        macro = self.ctx.repo.load(macro_id)
        name, ok = QInputDialog.getText(self, "Renomear macro", "Novo nome:", text=macro.name)
        if ok and name.strip():
            try:
                self.ctx.repo.rename(macro_id, name)
            except MacroFormatError as exc:
                self._on_error(str(exc))
                return
            self.refresh(macro_id)
            self.changed.emit()

    def _duplicate(self) -> None:
        macro_id = self.selected_id()
        if not macro_id:
            return
        copy = self.ctx.repo.duplicate(macro_id)
        self.refresh(copy.id)
        self.changed.emit()

    def _delete(self) -> None:
        macro_id = self.selected_id()
        if not macro_id:
            return
        macro = self.ctx.repo.load(macro_id)
        answer = QMessageBox.question(
            self, "Excluir macro", f"Excluir a macro \"{macro.name}\"? Isso não pode ser desfeito.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.Cancel,
            QMessageBox.StandardButton.Cancel)
        if answer == QMessageBox.StandardButton.Yes:
            self.ctx.repo.delete(macro_id)
            self.refresh()
            self.changed.emit()

    def _import(self) -> None:
        paths, _ = QFileDialog.getOpenFileNames(self, "Importar macros", "", "Macros (*.json)")
        last = None
        for path in paths:
            try:
                last = self.ctx.repo.import_file(Path(path)).id
            except MacroFormatError as exc:
                self._on_error(f"{Path(path).name}: {exc}")
        if paths:
            self.refresh(last)
            self.changed.emit()
            if last:
                QMessageBox.information(
                    self, "Importação concluída",
                    "Macros importadas ficam marcadas como \"importada\". O AutoMacro pedirá "
                    "confirmação antes de reproduzir cada uma pela primeira vez.")

    def _export(self) -> None:
        macro_id = self.selected_id()
        if not macro_id:
            return
        macro = self.ctx.repo.load(macro_id)
        safe = "".join(c if c.isalnum() or c in " -_" else "_" for c in macro.name).strip() or "macro"
        path, _ = QFileDialog.getSaveFileName(self, "Exportar macro", f"{safe}.json", "Macros (*.json)")
        if path:
            try:
                self.ctx.repo.export_file(macro_id, Path(path))
            except OSError as exc:
                self._on_error(f"Não foi possível exportar: {exc}")
