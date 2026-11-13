"""Ícones desenhados em código (traço único, mesma espessura), sem arquivos de imagem.

Cada função devolve um QIcon na cor pedida. Os ícones são redesenhados quando o tema muda.
"""

from __future__ import annotations

from collections.abc import Callable

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import QColor, QIcon, QPainter, QPainterPath, QPen, QPixmap

_SIZE = 24          # coordenadas lógicas; o pixmap é desenhado em 2x para ficar nítido


def _make(color: str, draw: Callable[[QPainter, QColor], None], size: int = 22) -> QIcon:
    scale = 2
    pm = QPixmap(size * scale, size * scale)
    pm.fill(Qt.GlobalColor.transparent)
    p = QPainter(pm)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    p.scale(size * scale / _SIZE, size * scale / _SIZE)
    qc = QColor(color)
    pen = QPen(qc, 1.8)
    pen.setCapStyle(Qt.PenCapStyle.RoundCap)
    pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
    p.setPen(pen)
    p.setBrush(Qt.BrushStyle.NoBrush)
    draw(p, qc)
    p.end()
    pm.setDevicePixelRatio(scale)
    return QIcon(pm)


def _poly(points: list[tuple[float, float]]) -> QPainterPath:
    path = QPainterPath(QPointF(*points[0]))
    for x, y in points[1:]:
        path.lineTo(x, y)
    path.closeSubpath()
    return path


def _fill(p: QPainter, c: QColor) -> None:
    p.setBrush(c)


def _qss_image(name: str, color: str, draw) -> str | None:
    """Grava um ícone em PNG numa pasta temporária e devolve o caminho (o QSS só aceita arquivo)."""
    import tempfile
    from pathlib import Path

    try:
        folder = Path(tempfile.gettempdir()) / "automacro-ui"
        folder.mkdir(parents=True, exist_ok=True)
        target = folder / f"{name}_{color.lstrip('#')}.png"
        if not target.exists() and not _make(color, draw, 16).pixmap(32, 32).save(str(target)):
            return None
        return target.as_posix()
    except Exception:
        return None


def checkmark_file(color: str, background: str = "") -> str | None:
    return _qss_image("check", color, lambda p, c: p.drawPolyline(
        [QPointF(6, 12.5), QPointF(10.2, 16.5), QPointF(18, 7.5)]))


def chevron_down_file(color: str) -> str | None:
    return _qss_image("chevdown", color, lambda p, c: p.drawPolyline(
        [QPointF(6.5, 9.5), QPointF(12, 15), QPointF(17.5, 9.5)]))


def play(color: str, size: int = 18) -> QIcon:
    def d(p, c):
        _fill(p, c)
        p.drawPath(_poly([(7, 4.5), (7, 19.5), (19, 12)]))
    return _make(color, d, size)


def pause(color: str, size: int = 18) -> QIcon:
    def d(p, c):
        _fill(p, c)
        p.drawRoundedRect(QRectF(6, 4.5, 4, 15), 1.2, 1.2)
        p.drawRoundedRect(QRectF(14, 4.5, 4, 15), 1.2, 1.2)
    return _make(color, d, size)


def stop(color: str, size: int = 16) -> QIcon:
    def d(p, c):
        _fill(p, c)
        p.drawRoundedRect(QRectF(5.5, 5.5, 13, 13), 2.2, 2.2)
    return _make(color, d, size)


def record(color: str, size: int = 16) -> QIcon:
    def d(p, c):
        _fill(p, c)
        p.drawEllipse(QRectF(5, 5, 14, 14))
    return _make(color, d, size)


def more(color: str, size: int = 20) -> QIcon:
    def d(p, c):
        _fill(p, c)
        p.setPen(Qt.PenStyle.NoPen)
        for x in (5, 12, 19):
            p.drawEllipse(QRectF(x - 1.8, 10.2, 3.6, 3.6))
    return _make(color, d, size)


def chevron_left(color: str, size: int = 18) -> QIcon:
    def d(p, c):
        p.drawPolyline([QPointF(15, 5.5), QPointF(8.5, 12), QPointF(15, 18.5)])
    return _make(color, d, size)


def cursor(color: str, size: int = 22) -> QIcon:
    def d(p, c):
        p.drawPath(_poly([(8, 3.5), (8, 16), (11.2, 13.2), (13.6, 18.2), (15.8, 17.2),
                          (13.4, 12.2), (17.6, 11.8)]))
    return _make(color, d, size)


def list_(color: str, size: int = 22) -> QIcon:
    def d(p, c):
        p.drawLine(QPointF(4, 6), QPointF(20, 6))
        p.drawLine(QPointF(4, 12), QPointF(20, 12))
        p.drawLine(QPointF(4, 18), QPointF(14, 18))
    return _make(color, d, size)


def sliders(color: str, size: int = 22) -> QIcon:
    def d(p, c):
        p.drawLine(QPointF(4, 7), QPointF(14, 7))
        p.drawLine(QPointF(18, 7), QPointF(20, 7))
        p.drawLine(QPointF(4, 17), QPointF(6, 17))
        p.drawLine(QPointF(10, 17), QPointF(20, 17))
        p.drawEllipse(QRectF(14, 5, 4, 4))
        p.drawEllipse(QRectF(6, 15, 4, 4))
    return _make(color, d, size)
