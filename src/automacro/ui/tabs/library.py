"""Aba Biblioteca de macros."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QSize, Qt, Signal
from PySide6.QtWidgets import (
    QFileDialog,
    QFrame,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QMenu,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from automacro.models.events import MacroFormatError
from automacro.storage.repository import MacroNotFoundError
from automacro.ui.event_editor import EventEditorDialog
from automacro.ui.tabs.base import BaseTab
from automacro.ui.widgets import fmt_duration, muted_label


class LibraryTab(BaseTab):
    """Lista de macros em linhas: nome, resumo, botão de reproduzir e menu de ações."""

    use_in_player = Signal(str)        # id da macro (reproduzir)
    changed = Signal()                 # biblioteca mudou (para atualizar o Reprodutor)

    def __init__(self, ctx, on_error) -> None:
        super().__init__(ctx)
        self._on_error = on_error
        self._target: str | None = None
        self._idle = True

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(8)

        self.empty = QLabel("Nenhuma macro ainda.\nToque em Nova gravação para criar a primeira.")
        self.empty.setObjectName("empty")
        self.empty.setAlignment(Qt.AlignmentFlag.AlignCenter)
        root.addWidget(self.empty, 1)

        self.rows_area = QScrollArea()
        self.rows_area.setWidgetResizable(True)
        self.rows_area.setFrameShape(QFrame.Shape.NoFrame)
        self.rows_area.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        holder = QFrame()
        holder.setObjectName("rowlist")
        self.rows_layout = QVBoxLayout(holder)
        self.rows_layout.setContentsMargins(6, 4, 6, 4)
        self.rows_layout.setSpacing(0)
        self.rows_area.setWidget(holder)
        root.addWidget(self.rows_area, 1)

        self.refresh()

    # ---- dados ------------------------------------------------------------------------
    def refresh(self, select_id: str | None = None) -> None:
        from automacro.ui import icons
        from automacro.ui.theme import palette

        c = palette(self.ctx.settings.ui.theme)
        while self.rows_layout.count():
            item = self.rows_layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.hide()
                widget.setParent(None)      # some já; deleteLater sozinho deixaria a linha pintada
                widget.deleteLater()
        infos = self.ctx.repo.list()
        for index, info in enumerate(infos):
            if index:
                line = QFrame()
                line.setObjectName("rowline")
                line.setFixedHeight(1)
                self.rows_layout.addWidget(line)
            self.rows_layout.addWidget(self._make_row(info, icons, c))
        self.rows_layout.addStretch(1)
        self.empty.setVisible(not infos)
        self.rows_area.setVisible(bool(infos))

    def _make_row(self, info, icons, c) -> QWidget:
        row = QFrame()
        row.setObjectName("macrorow")
        lay = QHBoxLayout(row)
        lay.setContentsMargins(12, 10, 8, 10)
        lay.setSpacing(8)
        text = QVBoxLayout()
        text.setSpacing(2)
        name = QLabel(info.name)
        name.setObjectName("rowname")
        name.setToolTip(info.name)
        summary = f"{info.event_count} ações · {fmt_duration(info.duration_ms)}"
        if info.imported:
            summary += " · importada"
        sub = muted_label(summary)
        sub.setWordWrap(False)
        text.addWidget(name)
        text.addWidget(sub)
        lay.addLayout(text, 1)

        play_btn = QPushButton()
        play_btn.setObjectName("play")
        play_btn.setIcon(icons.play(c["accent"]))
        play_btn.setIconSize(QSize(16, 16))
        play_btn.setFixedSize(44, 44)
        play_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        play_btn.setToolTip(f"Reproduzir {info.name}")
        play_btn.setAccessibleName(f"Reproduzir {info.name}")
        play_btn.clicked.connect(lambda _=False, i=info.id: self._act(i, self._use))
        play_btn.setEnabled(self._idle)
        lay.addWidget(play_btn)

        more_btn = QPushButton()
        more_btn.setObjectName("iconbtn")
        more_btn.setIcon(icons.more(c["muted"]))
        more_btn.setIconSize(QSize(20, 20))
        more_btn.setFixedSize(44, 44)
        more_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        more_btn.setAccessibleName(f"Mais opções para {info.name}")
        menu = QMenu(more_btn)
        menu.addAction("Editar eventos…", lambda i=info.id: self._act(i, self._edit))
        menu.addAction("Renomear", lambda i=info.id: self._act(i, self._rename))
        menu.addAction("Duplicar", lambda i=info.id: self._act(i, self._duplicate))
        menu.addAction("Exportar…", lambda i=info.id: self._act(i, self._export))
        menu.addSeparator()
        menu.addAction("Excluir", lambda i=info.id: self._act(i, self._delete))
        more_btn.setMenu(menu)
        lay.addWidget(more_btn)
        return row

    def set_state(self, state, activity) -> None:
        self._idle = state.value == "idle"
        for button in self.findChildren(QPushButton, "play"):
            button.setEnabled(self._idle)

    def _act(self, macro_id: str, action) -> None:
        self._target = macro_id
        try:
            action()
        finally:
            self._target = None

    def selected_id(self) -> str | None:
        return self._target

    def import_macro(self) -> None:
        self._import()

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
