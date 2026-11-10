"""Ponte entre o atualizador (threads de rede) e a interface (sinais Qt)."""

from __future__ import annotations

import logging
import threading
from pathlib import Path

from PySide6.QtCore import QObject, Signal

from automacro import __version__, updater
from automacro.updater import UpdateError, UpdateInfo

log = logging.getLogger(__name__)


class UpdateController(QObject):
    """Roda a verificação e o download fora da thread da interface.

    Os sinais devem ser ligados a métodos de QObjects (não a lambdas), para que cheguem
    sempre na thread da interface.
    """

    checked = Signal(object, bool)      # UpdateInfo | None, manual
    check_failed = Signal(str, bool)    # mensagem, manual
    progress = Signal(int, int)         # baixado, total
    ready = Signal(object)              # Path do instalador verificado
    download_failed = Signal(str)

    def __init__(self, parent: QObject | None = None, current_version: str = __version__) -> None:
        super().__init__(parent)
        self._current = current_version
        self._busy = threading.Lock()
        self._cancel = threading.Event()

    @property
    def busy(self) -> bool:
        return self._busy.locked()

    def check(self, manual: bool = False) -> bool:
        """Inicia uma verificação. Retorna False se já houver uma em andamento."""
        if not self._busy.acquire(blocking=False):
            return False
        threading.Thread(target=self._check, args=(manual,), name="automacro-update-check",
                         daemon=True).start()
        return True

    def _check(self, manual: bool) -> None:
        try:
            info = updater.check_for_update(self._current)
        except UpdateError as exc:
            log.info("Verificação de atualização falhou: %s", exc)
            self._release()
            self.check_failed.emit(str(exc), manual)
            return
        except Exception:
            log.exception("Erro inesperado ao verificar atualização")
            self._release()
            self.check_failed.emit("Erro inesperado ao verificar atualizações.", manual)
            return
        self._release()
        self.checked.emit(info, manual)

    def download(self, info: UpdateInfo) -> bool:
        if not self._busy.acquire(blocking=False):
            return False
        self._cancel.clear()
        threading.Thread(target=self._download, args=(info,), name="automacro-update-download",
                         daemon=True).start()
        return True

    def cancel_download(self) -> None:
        self._cancel.set()

    def _download(self, info: UpdateInfo) -> None:
        try:
            path: Path = updater.download_installer(
                info, progress=lambda done, total: self.progress.emit(done, total),
                cancelled=self._cancel.is_set)
        except UpdateError as exc:
            self._release()
            self.download_failed.emit(str(exc))
            return
        except Exception:
            log.exception("Erro inesperado ao baixar atualização")
            self._release()
            self.download_failed.emit("Erro inesperado ao baixar a atualização.")
            return
        self._release()
        self.ready.emit(path)

    def _release(self) -> None:
        if self._busy.locked():
            self._busy.release()
