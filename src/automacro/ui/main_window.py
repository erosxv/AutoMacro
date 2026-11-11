"""Janela principal: cabeçalho com estado + emergência, abas e barra de status."""

from __future__ import annotations

import logging

from PySide6.QtCore import QSize, Qt, QTimer, QUrl
from PySide6.QtGui import QCloseEvent, QDesktopServices, QIcon
from PySide6.QtWidgets import (
    QApplication,
    QFrame,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QMessageBox,
    QBoxLayout,
    QButtonGroup,
    QPushButton,
    QScrollArea,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from automacro import APP_NAME, __version__, updater
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
from automacro.ui.updates import UpdateController
from automacro.ui import icons
from automacro.ui.macros_page import LIST, OPTIONS, RECORD, MacrosPage
from automacro.ui.nowbar import NowBar
from automacro.ui.widgets import StatusPill, scrolled

log = logging.getLogger(__name__)

NOTICE_TIMEOUT_MS = 9000
COMPACT_WIDTH = 640          # abaixo disso a navegação vai para baixo, como num celular


def _nav_button(text: str, name: str) -> QPushButton:
    button = QPushButton(text)
    button.setObjectName(name)
    button.setCheckable(True)
    button.setCursor(Qt.CursorShape.PointingHandCursor)
    return button


class MainWindow(QMainWindow):
    def __init__(self, ctx: AppContext) -> None:
        super().__init__()
        self.ctx = ctx
        self.setWindowTitle(APP_NAME)
        self.resize(900, 680)
        self.setMinimumSize(420, 560)

        root = QWidget()
        root.setObjectName("root")
        self.setCentralWidget(root)
        # Disposição responsiva: [navegação | conteúdo] em janela larga, [conteúdo / navegação]
        # em janela estreita. Os mesmos widgets mudam de lugar, nada é duplicado.
        self._shell = QBoxLayout(QBoxLayout.Direction.LeftToRight, root)
        self._shell.setContentsMargins(0, 0, 0, 0)
        self._shell.setSpacing(0)
        self._compact: bool | None = None

        content = QWidget()
        self._content = content
        layout = QVBoxLayout(content)
        layout.setContentsMargins(20, 16, 20, 10)
        layout.setSpacing(12)

        # ---- cabeçalho -------------------------------------------------------------
        header = QHBoxLayout()
        self.page_title = QLabel("Macros")
        self.page_title.setObjectName("title")
        header.addWidget(self.page_title)
        header.addStretch(1)
        self.pill = StatusPill()
        header.addWidget(self.pill)
        # Sempre à vista, mas neutro: parar é uma ação normal, não um alarme.
        self.emergency = QPushButton("Parar tudo")
        self.emergency.setObjectName("stopall")
        self.emergency.setToolTip("Interrompe imediatamente qualquer gravação, reprodução ou auto clicker "
                                  "(atalho de emergência: Ctrl+Shift+F9 por padrão)")
        self.emergency.clicked.connect(ctx.session.emergency_stop)
        header.addWidget(self.emergency)
        layout.addLayout(header)

        # ---- aviso de limitações do sistema -------------------------------------------
        self.banner = QFrame()
        self.banner.setObjectName("banner")
        banner_layout = QHBoxLayout(self.banner)
        banner_layout.setContentsMargins(12, 8, 6, 8)
        self.banner_text = QLabel()
        self.banner_text.setWordWrap(True)
        self.banner_text.setProperty("muted", True)
        self.banner_text.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        banner_layout.addWidget(self.banner_text, 1)
        self.banner_close = QPushButton("Ocultar")
        self.banner_close.setObjectName("flat")
        self.banner_close.clicked.connect(lambda: self.banner.setVisible(False))
        banner_layout.addWidget(self.banner_close, 0, Qt.AlignmentFlag.AlignTop)
        layout.addWidget(self.banner)
        self._fill_banner()

        # ---- aviso de versão nova (só aparece quando há atualização) ----------------------
        self._update_info = None
        self.update_bar = QFrame()
        self.update_bar.setObjectName("updatebar")
        ub = QHBoxLayout(self.update_bar)
        ub.setContentsMargins(12, 8, 12, 8)
        self.update_label = QLabel()
        self.update_label.setWordWrap(True)
        self.update_now = QPushButton("Atualizar agora")
        self.update_now.setObjectName("primary")
        self.update_later = QPushButton("Depois")
        ub.addWidget(self.update_label, 1)
        ub.addWidget(self.update_now)
        ub.addWidget(self.update_later)
        self.update_bar.setVisible(False)
        layout.addWidget(self.update_bar)

        self.updates = UpdateController(self)
        self.updates.checked.connect(self._on_update_checked)
        self.updates.check_failed.connect(self._on_update_check_failed)
        self.updates.progress.connect(self._on_update_progress)
        self.updates.ready.connect(self._on_update_ready)
        self.updates.download_failed.connect(self._on_update_download_failed)
        self.update_now.clicked.connect(self._start_update)
        self.update_later.clicked.connect(lambda: self.update_bar.setVisible(False))

        # ---- páginas -------------------------------------------------------------
        self.autoclicker = AutoClickerTab(ctx, self.show_error)
        self.recorder = RecorderTab(ctx, self.show_error)
        self.player = PlayerTab(ctx, self.show_error)
        self.library = LibraryTab(ctx, self.show_error)
        self.settings_tab = SettingsTab(ctx, self.show_error)
        self._tab_list = [self.autoclicker, self.recorder, self.player, self.library, self.settings_tab]

        self.macros_page = MacrosPage(ctx, self.library, self.recorder, self.player)

        self.pages = QStackedWidget()
        self.pages.addWidget(scrolled(self.autoclicker))
        self.pages.addWidget(self.macros_page)
        self.pages.addWidget(self.settings_tab)
        layout.addWidget(self.pages, 1)
        self.nowbar = NowBar(ctx)
        layout.addWidget(self.nowbar)

        # ---- navegação (barra lateral ou inferior, conforme a largura) ---------------------
        self.nav = QFrame()
        self.nav.setObjectName("nav")
        self._nav_layout = QBoxLayout(QBoxLayout.Direction.TopToBottom, self.nav)
        self._nav_layout.setContentsMargins(12, 16, 12, 12)
        self._nav_layout.setSpacing(4)
        self._brand = QLabel(APP_NAME)
        self._brand.setObjectName("brand")
        self._nav_layout.addWidget(self._brand)
        self._nav_group = QButtonGroup(self)
        self._nav_group.setExclusive(True)
        self._nav_buttons: list[QPushButton] = []
        self._page_names = ["Auto Clicker", "Macros", "Ajustes"]
        for index, name in enumerate(self._page_names):
            button = _nav_button(name, "nav")
            self._nav_group.addButton(button, index)
            self._nav_buttons.append(button)
            self._nav_layout.addWidget(button)
        self._nav_stretch = self._nav_layout.addStretch(1)
        self._nav_group.idClicked.connect(self.show_page)
        self._nav_buttons[1].setChecked(True)
        self.pages.setCurrentIndex(1)
        self._apply_layout_mode(self.width() < COMPACT_WIDTH)

        # ---- ligações entre abas -------------------------------------------------------
        self.recorder.macro_saved.connect(self._macro_saved)
        self.library.use_in_player.connect(self._use_in_player)
        self.library.changed.connect(lambda: self.player.refresh_macros())
        self.settings_tab.applied.connect(self.apply_settings)
        self.settings_tab.check_requested.connect(self._manual_update_check)
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
            self.banner_text.setText("\n".join(lines))

    def apply_theme(self) -> None:
        theme = self.ctx.settings.ui.theme
        app = QApplication.instance()
        if app is not None:
            app.setStyleSheet(build_qss(theme))
        self._theme_palette = palette(theme)
        self._apply_nav_icons()
        self.nowbar.apply_theme()
        self.macros_page.apply_theme()
        self.library.refresh()
        self._set_state(self.ctx.session.state, self.ctx.session.activity)

    # ======================================================================================
    # Estado
    # ======================================================================================
    def _set_state(self, state: AppState, activity: str | None, text: str | None = None) -> None:
        color = self._theme_palette[STATE_COLORS[state.value]]
        self.pill.set_color(color, text or STATE_LABELS[state])
        for tab in self._tab_list:
            tab.set_state(state, activity)
        if self.player._macro is not None:
            self.nowbar.set_macro_name(self.player._macro.name)
        self.nowbar.set_state(state, activity)
        self.macros_page.set_state(state)
        if state is AppState.RECORDING:           # gravação iniciada por atalho: mostra o painel
            self.show_page(1)
            self.macros_page.show_view(RECORD)

    def _on_event(self, event: object) -> None:
        if isinstance(event, StateChanged):
            self._set_state(event.new, event.activity)
        elif isinstance(event, Countdown):
            self.pill.set_color(self._theme_palette["warning"], f"Começando em {event.remaining}…")
        elif isinstance(event, Notice):
            self.show_notice(event.text, event.level)
        elif isinstance(event, ActivityFinished) and event.error:
            self.show_notice(event.error, "error")
        self.nowbar.handle_event(event)
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
        self.show_macro_page(self.library)
        self.show_notice("Macro salva.", "info")

    def _use_in_player(self, macro_id: str) -> None:
        """Botão de play de uma linha: seleciona a macro e já reproduz."""
        self.player.select_macro(macro_id)
        self.player._play()

    def show_page(self, index: int) -> None:
        self.pages.setCurrentIndex(index)
        self._nav_buttons[index].setChecked(True)
        self.page_title.setText(self._page_names[index])

    def show_macro_page(self, page: QWidget) -> None:
        self.show_page(1)
        self.macros_page.show_view({self.library: LIST, self.recorder: RECORD, self.player: OPTIONS}[page])

    # ---- layout responsivo -----------------------------------------------------------------
    def _apply_layout_mode(self, compact: bool) -> None:
        if compact == self._compact:
            return
        self._compact = compact
        shell = self._shell
        shell.removeWidget(self.nav)
        shell.removeWidget(self._content)
        if compact:
            shell.setDirection(QBoxLayout.Direction.TopToBottom)
            shell.addWidget(self._content, 1)
            shell.addWidget(self.nav)
            self._nav_layout.setDirection(QBoxLayout.Direction.LeftToRight)
            self._nav_layout.setContentsMargins(8, 6, 8, 8)
            self._brand.hide()
            self._nav_stretch_visible(False)
            self.nav.setFixedWidth(16777215)
            self.nav.setMaximumHeight(16777215)
        else:
            shell.setDirection(QBoxLayout.Direction.LeftToRight)
            shell.addWidget(self.nav)
            shell.addWidget(self._content, 1)
            self._nav_layout.setDirection(QBoxLayout.Direction.TopToBottom)
            self._nav_layout.setContentsMargins(12, 18, 12, 12)
            self._brand.show()
            self._nav_stretch_visible(True)
            self.nav.setFixedWidth(190)
        for tab in self._tab_list:
            tab.set_compact(compact)
        self.nav.setProperty("compact", compact)
        for button in self._nav_buttons:
            button.setProperty("compact", compact)
            button.style().unpolish(button)
            button.style().polish(button)
        self.nav.style().unpolish(self.nav)
        self.nav.style().polish(self.nav)

    def _apply_nav_icons(self) -> None:
        c = self._theme_palette
        for button, make in zip(self._nav_buttons, (icons.cursor, icons.list_, icons.sliders)):
            icon = QIcon()
            icon.addPixmap(make(c["muted"]).pixmap(22, 22), QIcon.Mode.Normal, QIcon.State.Off)
            icon.addPixmap(make(c["text"]).pixmap(22, 22), QIcon.Mode.Normal, QIcon.State.On)
            button.setIcon(icon)
            button.setIconSize(QSize(22, 22))

    def _nav_stretch_visible(self, visible: bool) -> None:
        # Em modo lateral o espaço sobra embaixo; em modo inferior os botões dividem a largura.
        index = self._nav_layout.count() - 1
        self._nav_layout.setStretch(index, 1 if visible else 0)
        for i in range(1, index):
            self._nav_layout.setStretch(i, 0 if visible else 1)

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        self._apply_layout_mode(self.width() < COMPACT_WIDTH)

    def _refresh_hotkey_hints(self) -> None:
        for tab in self._tab_list:
            tab.refresh_hotkeys()

    # ======================================================================================
    # Atualização automática
    # ======================================================================================
    def start_update_check(self) -> None:
        """Verificação silenciosa ao abrir o programa (se habilitada nas configurações)."""
        if self.ctx.settings.updates.auto_check:
            QTimer.singleShot(4000, lambda: self.updates.check(manual=False))

    def _manual_update_check(self) -> None:
        if self.updates.check(manual=True):
            self.settings_tab.set_update_status("Verificando…", busy=True)

    def _on_update_checked(self, info, manual: bool) -> None:
        self.settings_tab.set_update_status(
            f"Nova versão disponível: {info.version}" if info
            else f"Você já está na versão mais recente ({__version__}).")
        if info is None:
            if manual:
                self.show_notice("Você já está na versão mais recente.", "info")
            return
        self._update_info = info
        self.update_label.setText(f"Nova versão disponível: {info.version} (você está na {__version__}).")
        self.update_now.setEnabled(True)
        self.update_now.setText("Atualizar agora")
        self.update_bar.setVisible(True)

    def _on_update_check_failed(self, message: str, manual: bool) -> None:
        self.settings_tab.set_update_status(message)
        if manual:
            self.show_notice(message, "warning")

    def _start_update(self) -> None:
        info = self._update_info
        if info is None:
            return
        if self.ctx.session.state is not AppState.IDLE:
            self.show_error("Pare a gravação, a reprodução ou o Auto Clicker antes de atualizar.")
            return
        if not updater.can_self_update():
            # Linux ou execução a partir do código-fonte: abre a página de download.
            QDesktopServices.openUrl(QUrl(info.page_url))
            return
        if self.updates.download(info):
            self.update_now.setEnabled(False)
            self.update_label.setText("Baixando a atualização…")

    def _on_update_progress(self, done: int, total: int) -> None:
        if total > 0:
            self.update_label.setText(f"Baixando a atualização… {done * 100 // total}%")

    def _on_update_download_failed(self, message: str) -> None:
        self.update_now.setEnabled(True)
        if self._update_info is not None:
            self.update_label.setText(f"Nova versão disponível: {self._update_info.version}.")
        self.show_error(f"Não foi possível atualizar: {message}")

    def _on_update_ready(self, path) -> None:
        if self.ctx.session.state is not AppState.IDLE:
            self.update_now.setEnabled(True)
            self.show_error("Pare a atividade em andamento e clique em Atualizar agora de novo.")
            return
        if not self.recorder.confirm_discard_pending():
            self.update_now.setEnabled(True)
            return
        try:
            self.collect_settings()
            self.ctx.store.save(self.ctx.settings)
        except Exception:
            log.exception("Falha ao salvar configurações antes de atualizar")
        try:
            updater.launch_installer(path)
        except updater.UpdateError as exc:
            self.update_now.setEnabled(True)
            self.show_error(str(exc))
            return
        self.update_label.setText("Instalando… o programa vai fechar e abrir de novo.")
        QTimer.singleShot(300, QApplication.quit)

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
