"""Ponte thread-safe entre o EventBus do núcleo e a thread da interface.

O núcleo publica eventos em threads de trabalho; ``Signal.emit`` chamado de outra thread
entrega ao receptor (que vive na thread da UI) por conexão **enfileirada**. Assim nenhum
widget é tocado fora da thread da interface.
"""

from __future__ import annotations

from PySide6.QtCore import QObject, Signal

from automacro.core.event_bus import EventBus


class SessionBridge(QObject):
    event = Signal(object)

    def __init__(self, bus: EventBus) -> None:
        super().__init__()
        self._unsubscribe = bus.subscribe(self.event.emit)

    def close(self) -> None:
        self._unsubscribe()
