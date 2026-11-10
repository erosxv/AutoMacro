"""Logs em arquivo rotativo + captura de exceções não tratadas (inclusive em threads)."""

from __future__ import annotations

import logging
import sys
import threading
from logging.handlers import RotatingFileHandler
from pathlib import Path

LOG_FORMAT = "%(asctime)s %(levelname)-8s %(threadName)s %(name)s: %(message)s"
_configured = False


def setup_logging(logs_dir: Path, debug: bool = False, console: bool = True) -> Path:
    """Configura o logging global. Idempotente. Retorna o caminho do arquivo de log."""
    global _configured
    log_file = Path(logs_dir) / "automacro.log"
    if _configured:
        return log_file
    Path(logs_dir).mkdir(parents=True, exist_ok=True)

    root = logging.getLogger()
    root.setLevel(logging.DEBUG if debug else logging.INFO)
    formatter = logging.Formatter(LOG_FORMAT)

    file_handler = RotatingFileHandler(log_file, maxBytes=1_000_000, backupCount=3,
                                       encoding="utf-8")
    file_handler.setFormatter(formatter)
    root.addHandler(file_handler)
    if console and sys.stderr is not None:
        stream = logging.StreamHandler(sys.stderr)
        stream.setFormatter(formatter)
        root.addHandler(stream)

    log = logging.getLogger("automacro.crash")

    def _excepthook(exc_type, exc, tb):
        if issubclass(exc_type, KeyboardInterrupt):
            sys.__excepthook__(exc_type, exc, tb)
            return
        log.critical("Exceção não tratada", exc_info=(exc_type, exc, tb))

    def _thread_hook(args: threading.ExceptHookArgs):
        if args.exc_type is SystemExit:
            return
        log.critical("Exceção não tratada na thread %s",
                     args.thread.name if args.thread else "?",
                     exc_info=(args.exc_type, args.exc_value, args.exc_traceback))

    sys.excepthook = _excepthook
    threading.excepthook = _thread_hook
    _configured = True
    return log_file
