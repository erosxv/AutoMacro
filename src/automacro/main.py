"""Ponto de entrada do AutoMacro."""

from __future__ import annotations

import argparse
import logging
import sys

from automacro import APP_NAME, __version__


def _parse_args(argv: list[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(prog="automacro", description="Auto Clicker + Gravador de Macros")
    parser.add_argument("--doctor", action="store_true", help="verifica o ambiente e sai")
    parser.add_argument("--debug", action="store_true", help="log detalhado")
    parser.add_argument("--version", action="version", version=f"{APP_NAME} {__version__}")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv)
    if args.doctor:
        from automacro.doctor import main as doctor_main

        return doctor_main()

    from PySide6.QtCore import QLockFile
    from PySide6.QtWidgets import QApplication, QMessageBox

    from automacro.core.event_bus import EventBus
    from automacro.core.session import Session
    from automacro.core.timing import wait_margin_ns
    from automacro.input_handlers.factory import create_backend
    from automacro.storage.repository import MacroRepository
    from automacro.storage.settings_store import SettingsStore
    from automacro.ui.bridge import SessionBridge
    from automacro.ui.context import AppContext
    from automacro.ui.main_window import MainWindow
    from automacro.utils.logging_setup import setup_logging
    from automacro.utils.paths import AppPaths
    from automacro.utils.platform_info import detect_platform, enable_high_resolution_timer

    paths = AppPaths.default().ensure()
    log_file = setup_logging(paths.logs_dir, debug=args.debug)
    log = logging.getLogger("automacro")
    log.info("Iniciando %s %s (log em %s)", APP_NAME, __version__, log_file)

    app = QApplication(sys.argv)
    app.setApplicationName(APP_NAME)

    # Instância única: dois processos disputariam os mesmos atalhos globais.
    lock = QLockFile(str(paths.lock_file))
    if not lock.tryLock(100):
        QMessageBox.information(None, APP_NAME, "O AutoMacro já está em execução.")
        return 1

    undo_timer = enable_high_resolution_timer()
    margin_ms = wait_margin_ns() / 1e6
    log.info("Margem de espera calibrada: %.1f ms", margin_ms)

    platform = detect_platform()
    store = SettingsStore(paths.config_file)
    bus = EventBus()
    session = Session(create_backend(platform), store.load(), bus, platform)
    ctx = AppContext(session, MacroRepository(paths.macros_dir), store, paths, SessionBridge(bus))

    window = MainWindow(ctx)
    window.show()
    session.start_hotkeys()
    window.start_update_check()

    def cleanup() -> None:
        ctx.bridge.close()
        session.shutdown()
        undo_timer()
        lock.unlock()
        log.info("Encerrado")

    app.aboutToQuit.connect(cleanup)
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
