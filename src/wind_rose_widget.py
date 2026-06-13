"""
wind_rose_widget.py — a small QPainter wind-rose (V1.67).

Paints a rose block (``src.wind.compute_wind_rose`` annual/seasonal block) as
stacked speed-banded petals, N at top, clockwise. The geometry comes from the
pure :func:`src.wind.wind_rose_geometry`; this widget only draws — no maths, no
new dependency (plain QPainter).
"""

from __future__ import annotations

from PyQt6.QtCore import Qt, QRectF
from PyQt6.QtGui import QColor, QPainter
from PyQt6.QtWidgets import QWidget

from src.wind import wind_rose_geometry

# Calm/Light → Very strong (matches src.wind._SPEED_LABELS order).
_BAND_COLORS = ["#bbdefb", "#64b5f6", "#43a047", "#fb8c00", "#e53935"]


class WindRoseWidget(QWidget):
    """Compact wind rose. Call :meth:`set_block` with a rose block dict."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._wedges: list = []
        self.setMinimumSize(190, 190)

    def set_block(self, block: dict | None):
        self._wedges = wind_rose_geometry(block) if block else []
        self.update()

    def paintEvent(self, _ev):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        w, h = self.width(), self.height()
        cx, cy = w / 2.0, h / 2.0
        radius = min(w, h) / 2.0 - 16

        # Guide rings + cardinal labels.
        p.setPen(QColor("#546e7a"))
        for frac in (0.5, 1.0):
            rr = radius * frac
            p.drawEllipse(QRectF(cx - rr, cy - rr, 2 * rr, 2 * rr))
        for label, dx, dy in (("N", 0, -radius - 13), ("S", 0, radius + 1),
                              ("E", radius + 2, -6), ("W", -radius - 12, -6)):
            p.drawText(QRectF(cx + dx, cy + dy, 12, 13),
                       Qt.AlignmentFlag.AlignCenter, label)

        if not self._wedges:
            p.setPen(QColor("#90a4ae"))
            p.drawText(self.rect(), Qt.AlignmentFlag.AlignCenter,
                       "No wind data")
            p.end()
            return

        # Outer bands first so inner bands overpaint the centre → stacked rings.
        p.setPen(Qt.PenStyle.NoPen)
        for wdg in sorted(self._wedges, key=lambda x: -x["r1"]):
            r1 = radius * wdg["r1"]
            rect = QRectF(cx - r1, cy - r1, 2 * r1, 2 * r1)
            # Compass bearing → Qt angle (0°=east, CCW). N(0°)→90°, E(90°)→0°.
            start16 = int(round((90.0 - wdg["end_deg"]) * 16))
            span16 = int(round((wdg["end_deg"] - wdg["start_deg"]) * 16))
            p.setBrush(QColor(_BAND_COLORS[min(wdg["band"],
                                               len(_BAND_COLORS) - 1)]))
            p.drawPie(rect, start16, span16)
        p.end()
