from __future__ import annotations

from functools import cache

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QIcon, QPainter, QPixmap

COLORS = {
    "idle": "#666666",
    "starting": "#4C9AFF",
    "running": "#4C9AFF",
    "waiting_input": "#F5C542",
    "waiting_approval": "#D91AFF",
    "completed": "#3FB950",
    "error": "#F85149",
    "stale": "#9A5B2E",
    "disconnected": "#9A5B2E",
    "unknown": "#777777",
}


@cache
def render_icon(state: str, bright: bool = True, size: int = 22) -> QIcon:
    # Cached: a new QIcon per call gets a new QPixmapCache key every time the tray
    # backend asks for its pixmap, so Qt's cache fills with entries that are never reused.
    pixmap = QPixmap(size, size)
    pixmap.fill(Qt.GlobalColor.transparent)
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    color = QColor(COLORS.get(state, COLORS["unknown"]))
    if not bright:
        color.setAlpha(105)
    painter.setPen(Qt.PenStyle.NoPen)
    painter.setBrush(color)
    margin = max(3, size // 6)
    painter.drawEllipse(margin, margin, size - margin * 2, size - margin * 2)
    painter.end()
    return QIcon(pixmap)
