"""Janela principal: cabeçalho com estado + emergência, abas e barra de status."""

from __future__ import annotations

import logging

from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QCloseEvent
from PySide6.QtWidgets import (
    QApplication,
    QFrame,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from automacro import APP_NAME, __version__
from automacro.core.errors import AutoMacroError
from automacro.core.event_bus import ActivityFinished, Countdown, Notice, StateChanged
from automacro.hotkeys.parser import HotkeyError
from automacro.models.state import STATE_LABELS, AppState
from automacro.ui.context import AppContext
from automacro.ui.tabs.autoclicker import AutoClickerTab
from automacro.ui.tabs.library import LibraryTab
from automacro.ui.tabs.player import PlayerTab
from automacro.ui.tabs.recorder import RecorderTab
from automacro.ui.tabs.settings import SettingsTab
from automacro.ui.theme import STATE_COLORS, build_qss, palette
from automacro.ui.widgets import StatusPill, muted_label

log = logging.getLogger(__name__)

NOTICE_TIMEOUT_MS = 9000


class MainWindow(QMainWindow):
    def __init__(self, ctx: AppContext) -> None:
        super().__init__()
        self.ctx = ctx
        self.setWindowTitle(APP_NAME)
        self.resize(900, 760)
        self.setMinimumSize(760, 640)

        root = QWidget()
        root.setObjectName("root")
        self.setCentralWidget(root)
        layout = QVBoxLayout(root)
        layout.setContentsMargins(18, 14, 18, 10)
        layout.setSpacing(12)

        # ---- cabeçalho -------------------------------------------------------------
        header = QHBoxLayout()
        titles = QVBoxLayout()
        title = QLabel(APP_NAME)
        title.setObjectName("title")
        titles.addWidget(title)
        titles.addWidget(muted_label("Auto Clicker e Gravador de Macros"))
        header.addLayout(titles)
        header.addStretch(1)
        self.pill = StatusPill()
        header.addWidget(self.pill)
        self.emergency = QPushButton("PARADA DE EMERGÊNCIA")
        self.emergency.setObjectName("danger")
        self.emergency.setToolTip("Interrompe imediatamente qualquer gravação, reprodução ou auto clicker")
        self.emergency.clicked.connect(ctx.session.emergency_stop)
        header.addWidget(self.emergency)
        layout.addLayout(header)

        # ---- aviso de limitações do sistema -------------------------------------------
        self.banner = QFrame()
        self.banner.setObjectName("banner")
        banner_layout = QVBoxLayout(self.banner)
        banner_layout.setContentsMargins(12, 8, 12, 8)
        self.banner_text = QLabel()
        self.banner_text.setWordWrap(True)
        self.banner_text.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        banner_layout.addWidget(self.banner_text)
        layout.addWidget(self.banner)
        self._fill_banner()

        # ---- abas ----------------------------------------------------------------
        self.tabs = QTabWidget()
        self.autoclicker = AutoClickerTab(ctx, self.show_error)
        self.recorder = RecorderTab(ctx, self.show_error)
        self.player = PlayerTab(ctx, self.show_error)
        self.library = LibraryTab(ctx, self.show_error)
        self.settings_tab = SettingsTab(ctx, self.show_error)
        self._tab_list = [self.autoclicker, self.recorder, self.player, self.library, self.settings_tab]
        for tab, name in zip(self._tab_list, ["Auto Clicker", "Gravador", "Reprodutor",
                                              "Biblioteca", "Configurações"]):
            self.tabs.addTab(tab, name)
        layout.addWidget(self.tabs, 1)

        # ---- ligações entre abas -------------------------------------------------------
        self.recorder.macro_saved.connect(self._macro_saved)
        self.library.use_in_player.connect(self._use_in_player)
        self.library.changed.connect(lambda: self.player.refresh_macros())
        self.settings_tab.applied.connect(self.apply_settings)
        ctx.bridge.event.connect(self._on_event)

        # ---- barra de status -------------------------------------------------------
        self.notice = QLabel("")
        self.statusBar().addWidget(self.notice, 1)
        self.statusBar().addPermanentWidget(QLabel(f"v{__version__}"))
        self._notice_timer = QTimer(self)
        self._notice_timer.setSingleShot(True)
        self._notice_timer.timeout.connect(lambda: self.notice.setText(""))

        self.apply_theme()
        self._set_state(ctx.session.state, ctx.session.activity)
        self._refresh_hotkey_hints()
        self._report_environment()

    # ======================================================================================
    # Ambiente e tema
    # ======================================================================================
    def _report_environment(self) -> None:
        """Informa à sessão o tamanho da tela (para avisar se a macro vier de outra)."""
        screen = QApplication.primaryScreen()
        if screen is not None:
            size = screen.size()
            ratio = screen.devicePixelRatio()
            self.ctx.session.set_environment_info(
                {"screen": [round(size.width() * ratio), round(size.height() * ratio)]})

    def _fill_banner(self) -> None:
        caps = self.ctx.session.capabilities()
        lines = caps.problem_lines()
        self.banner.setVisible(bool(lines))
        if lines:
            self.banner_text.setText("⚠  " + "\n⚠  ".join(lines))

    def apply_theme(self) -> None:
        theme = self.ctx.settings.ui.theme
        app = QApplication.instance()
        if app is not None:
            app.setStyleSheet(build_qss(theme))
        self._theme_palette = palette(theme)
        self._set_state(self.ctx.session.state, self.ctx.session.activity)

    # ======================================================================================
    # Estado
    # ======================================================================================
    def _set_state(self, state: AppState, activity: str | None, text: str | None = None) -> None:
        color = self._theme_palette[STATE_COLORS[state.value]]
        self.pill.set_color(color, text or STATE_LABELS[state])
        for tab in self._tab_list:
            tab.set_state(state, activity)

    def _on_event(self, event: object) -> None:
        if isinstance(event, StateChanged):
            self._set_state(event.new, event.activity)
        elif isinstance(event, Countdown):
            self.pill.set_color(self._theme_palette["warning"], f"Começando em {event.remaining}…")
        elif isinstance(event, Notice):
            self.show_notice(event.text, event.level)
        elif isinstance(event, ActivityFinished) and event.error:
            self.show_notice(event.error, "error")
        for tab in self._tab_list:
            tab.handle_event(event)

    # ======================================================================================
    # Mensagens
    # ======================================================================================
    def show_notice(self, text: str, level: str = "info") -> None:
        """Mensagem não bloqueante (ex.: vinda de um atalho enquanto outro app está em foco)."""
        color = {"error": "danger", "warning": "warning"}.get(level, "muted")
        self.notice.setStyleSheet(f"color: {self._theme_palette[color]}; font-weight: 600;")
        self.notice.setText(text)
        self.notice.setToolTip(text)
        self._notice_timer.start(NOTICE_TIMEOUT_MS)

    def show_error(self, text: str) -> None:
        """Erro de uma ação feita pelo usuário na janela: diálogo + barra de status."""
        self.show_notice(text, "error")
        QMessageBox.warning(self, APP_NAME, text)

    # ======================================================================================
    # Ligações entre abas
    # ======================================================================================
    def _macro_saved(self, macro_id: str) -> None:
        self.library.refresh(macro_id)
        self.player.refresh_macros(select_id=macro_id)
        self.tabs.setCurrentWidget(self.library)
        self.show_notice("Macro salva na biblioteca.", "info")

    def _use_in_player(self, macro_id: str) -> None:
        self.player.select_macro(macro_id)
        self.tabs.setCurrentWidget(self.player)

    def _refresh_hotkey_hints(self) -> None:
        for tab in self._tab_list:
            tab.refresh_hotkeys()

    # ======================================================================================
    # Configurações
    # ======================================================================================
    def collect_settings(self) -> None:
        for tab in self._tab_list:
            tab.collect_settings(self.ctx.settings)

    def apply_settings(self) -> None:
        """Lê as abas, valida, aplica ao núcleo e grava em disco."""
        settings = self.ctx.settings
        self.collect_settings()
        try:
            self.ctx.session.apply_settings(settings)
        except HotkeyError as exc:
            self.show_error(f"Atalhos inválidos: {exc}")
            return
        try:
            self.ctx.store.save(settings)
        except OSError as exc:
            self.show_error(f"Não foi possível salvar as configurações: {exc}")
            return
        self.apply_theme()
        self._refresh_hotkey_hints()
        for tab in self._tab_list:
            tab.load_settings(settings)
        self.show_notice("Configurações aplicadas e salvas.", "info")

    # ======================================================================================
    # Fechamento
    # ======================================================================================
    def closeEvent(self, event: QCloseEvent) -> None:
        if not self.recorder.confirm_discard_pending():
            event.ignore()
            return
        try:
            self.collect_settings()
            self.ctx.store.save(self.ctx.settings)
        except Exception:
            log.exception("Falha ao salvar configurações ao fechar")
        try:
            self.ctx.session.stop(wait=True, timeout=3.0)
        except AutoMacroError:
            pass
        event.accept()
