"""Aba Configurações."""

from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDoubleSpinBox,
    QFormLayout,
    QFrame,
    QHBoxLayout,
    QLabel,
    QPlainTextEdit,
    QPushButton,
    QScrollArea,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from automacro import __version__
from automacro.hotkeys.parser import HotkeyError, find_conflicts
from automacro.models.settings import HOTKEY_LABELS, AppSettings, HotkeySettings
from automacro.ui.tabs.base import BaseTab
from automacro.ui.widgets import Card, HotkeyEdit, heading, muted_label


class SettingsTab(BaseTab):
    applied = Signal()                 # configurações aplicadas (atalhos, tema…)
    check_requested = Signal()         # usuário clicou em "Verificar agora"

    def __init__(self, ctx, on_error) -> None:
        super().__init__(ctx)
        self._on_error = on_error
        self._edits: dict[str, HotkeyEdit] = {}

        # Conteúdo dentro de uma área rolável: em janelas menores que o conteúdo a aba rola,
        # em vez de o Qt comprimir as linhas até o texto ficar cortado.
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        content = QWidget()
        scroll.setWidget(content)
        outer.addWidget(scroll)

        root = QVBoxLayout(content)
        root.setContentsMargins(18, 18, 18, 18)
        root.setSpacing(14)

        keys = Card()
        keys.body.addWidget(heading("Atalhos globais"))
        form = QFormLayout()
        form.setRowWrapPolicy(QFormLayout.RowWrapPolicy.WrapLongRows)
        form.setHorizontalSpacing(18)
        for name, label in HOTKEY_LABELS.items():
            edit = HotkeyEdit()
            self._edits[name] = edit
            form.addRow(label, edit)
        keys.body.addLayout(form)
        keys.body.addWidget(muted_label(
            "Clique no campo e pressione a combinação desejada. Funcionam mesmo com a janela "
            "minimizada (respeitando as limitações do seu sistema, abaixo)."))
        root.addWidget(keys)

        safety = Card()
        safety.body.addWidget(heading("Segurança"))
        sform = QFormLayout()
        sform.setRowWrapPolicy(QFormLayout.RowWrapPolicy.WrapLongRows)
        sform.setHorizontalSpacing(18)
        self.countdown = QDoubleSpinBox(); self.countdown.setRange(0, 30); self.countdown.setSuffix(" s")
        self.hk_countdown = QDoubleSpinBox(); self.hk_countdown.setRange(0, 30); self.hk_countdown.setSuffix(" s")
        self.max_play = QSpinBox(); self.max_play.setRange(0, 10_000); self.max_play.setSuffix(" min  (0 = sem limite)")
        self.failsafe = QCheckBox("Parar se o mouse for ao canto")
        self.confirm_imported = QCheckBox("Confirmar macros importadas")
        sform.addRow("Contagem regressiva (botões)", self.countdown)
        sform.addRow("Contagem regressiva (atalhos)", self.hk_countdown)
        sform.addRow("Duração máxima da reprodução", self.max_play)
        safety.body.addLayout(sform)
        self.failsafe.setToolTip("Para tudo ao levar o mouse ao canto superior esquerdo da tela")
        self.confirm_imported.setToolTip("Pede confirmação antes de reproduzir macros que vieram de um arquivo importado")
        safety.body.addWidget(self.failsafe)
        safety.body.addWidget(self.confirm_imported)
        root.addWidget(safety)

        look = Card()
        look.body.addWidget(heading("Aparência"))
        row = QHBoxLayout()
        self.theme = QComboBox()
        self.theme.addItem("Escuro", "dark")
        self.theme.addItem("Claro", "light")
        row.addWidget(QLabel("Tema"))
        row.addWidget(self.theme)
        row.addStretch(1)
        look.body.addLayout(row)
        root.addWidget(look)

        upd = Card()
        upd.body.addWidget(heading("Atualizações"))
        self.auto_update = QCheckBox("Procurar atualização ao abrir")
        upd.body.addWidget(self.auto_update)
        urow = QHBoxLayout()
        self.check_btn = QPushButton("Verificar agora")
        self.check_btn.clicked.connect(self.check_requested.emit)
        self.update_status = muted_label(f"Versão instalada: {__version__}")
        self.update_status.setWordWrap(True)
        urow.addWidget(self.check_btn)
        urow.addWidget(self.update_status, 1)
        upd.body.addLayout(urow)
        upd.body.addWidget(muted_label(
            "O programa só avisa; nada é instalado sem você clicar em \"Atualizar agora\"."))
        root.addWidget(upd)

        env = Card()
        env.body.addWidget(heading("Compatibilidade deste sistema"))
        self.env_text = QPlainTextEdit()
        self.env_text.setReadOnly(True)
        self.env_text.setMaximumHeight(120)
        env.body.addWidget(self.env_text)
        root.addWidget(env)

        buttons = QHBoxLayout()
        self.apply_btn = QPushButton("Aplicar e salvar")
        self.apply_btn.setObjectName("primary")
        self.apply_btn.clicked.connect(self.apply)
        reset = QPushButton("Restaurar atalhos padrão")
        reset.clicked.connect(self._reset_hotkeys)
        buttons.addWidget(self.apply_btn)
        buttons.addWidget(reset)
        buttons.addStretch(1)
        root.addLayout(buttons)
        root.addStretch(1)

        self.load_settings(ctx.settings)
        self._fill_env()

    # ---- compatibilidade --------------------------------------------------------------
    def _fill_env(self) -> None:
        session = self.ctx.session
        lines = [f"Sistema: {session.platform.describe()}"]
        caps = session.capabilities()
        problems = caps.problem_lines()
        if problems:
            lines.append("Limitações:")
            lines += [f"• {p}" for p in problems]
        else:
            lines.append("Todos os recursos (captura, envio de cliques e teclas, atalhos globais) estão disponíveis.")
        self.env_text.setPlainText("\n".join(lines))

    # ---- configuração <-> widgets -----------------------------------------------------
    def load_settings(self, settings: AppSettings) -> None:
        for name, edit in self._edits.items():
            edit.set_value(getattr(settings.hotkeys, name))
        s = settings.safety
        self.countdown.setValue(s.countdown_s)
        self.hk_countdown.setValue(s.hotkey_countdown_s)
        self.max_play.setValue(s.max_playback_minutes)
        self.failsafe.setChecked(s.failsafe_corner)
        self.confirm_imported.setChecked(s.confirm_imported)
        self.theme.setCurrentIndex(max(0, self.theme.findData(settings.ui.theme)))
        self.auto_update.setChecked(settings.updates.auto_check)

    def collect_settings(self, settings: AppSettings) -> None:
        defaults = HotkeySettings()
        for name, edit in self._edits.items():
            setattr(settings.hotkeys, name, edit.value() or getattr(defaults, name))
        s = settings.safety
        s.countdown_s = self.countdown.value()
        s.hotkey_countdown_s = self.hk_countdown.value()
        s.max_playback_minutes = self.max_play.value()
        s.failsafe_corner = self.failsafe.isChecked()
        s.confirm_imported = self.confirm_imported.isChecked()
        settings.ui.theme = self.theme.currentData()
        settings.updates.auto_check = self.auto_update.isChecked()

    def set_update_status(self, text: str, busy: bool = False) -> None:
        self.update_status.setText(text)
        self.check_btn.setEnabled(not busy)

    def _reset_hotkeys(self) -> None:
        defaults = HotkeySettings()
        for name, edit in self._edits.items():
            edit.set_value(getattr(defaults, name))

    def validate_hotkeys(self) -> str | None:
        bindings = {name: (edit.value() or getattr(HotkeySettings(), name))
                    for name, edit in self._edits.items()}
        try:
            conflicts = find_conflicts(bindings)
        except HotkeyError as exc:
            return str(exc)
        if conflicts:
            a, b = conflicts[0]
            return (f"O mesmo atalho foi escolhido para \"{HOTKEY_LABELS[a]}\" e "
                    f"\"{HOTKEY_LABELS[b]}\". Escolha atalhos diferentes.")
        return None

    def apply(self) -> bool:
        problem = self.validate_hotkeys()
        if problem:
            self._on_error(problem)
            return False
        self.applied.emit()
        return True
