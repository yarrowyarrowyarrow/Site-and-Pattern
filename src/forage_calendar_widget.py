"""
forage_calendar_widget.py — a small QPainter bloom-succession chart (V2.13).

Draws the whole-design forage calendar (``src.forage_calendar``): a 12-month
bar of how many plants are in bloom each month with the growing season shaded
and forage gaps flagged red, then a per-plant succession band underneath so the
spring→fall relay is visible. All geometry is trivial; this widget only draws
(plain QPainter, no new dependency), mirroring ``wind_rose_widget``.

Design principle P6 (make ecological value legible) — see docs/DESIGN_PHILOSOPHY.md.
"""

from __future__ import annotations

from PyQt6.QtCore import Qt, QRectF
from PyQt6.QtGui import QColor, QPainter, QFont
from PyQt6.QtWidgets import QWidget

_GROW_SHADE = QColor(46, 74, 46, 90)      # growing season backdrop
_BAR = QColor(0x66, 0xbb, 0x6a)
_BAR_PEAK = QColor(0xc8, 0xe6, 0xc9)
_GAP = QColor(0xe5, 0x53, 0x35)
_GRID = QColor(255, 255, 255, 28)
_TEXT = QColor(0x9e, 0xb0, 0xa2)
_TEXT_DIM = QColor(0x70, 0x80, 0x74)
_MAX_ROWS = 16                            # succession rows before "+N more"


class ForageCalendarWidget(QWidget):
    """Compact bloom-succession chart. Call :meth:`set_calendar` with a
    ``src.forage_calendar.build_forage_calendar`` result."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._cal: dict | None = None
        self.setMinimumHeight(150)

    def set_calendar(self, cal: dict | None):
        self._cal = cal
        rows = min(len(cal["succession"]), _MAX_ROWS) if cal else 0
        self.setMinimumHeight(96 + rows * 12 + (14 if cal and
                              len(cal["succession"]) > _MAX_ROWS else 0))
        self.updateGeometry()
        self.update()

    def paintEvent(self, _ev):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        w, h = self.width(), self.height()
        if not self._cal or not self._cal["months"]:
            p.setPen(_TEXT_DIM)
            p.drawText(self.rect(), Qt.AlignmentFlag.AlignCenter,
                       "No flowering plants placed yet.")
            return

        cal = self._cal
        months = cal["months"]
        left, right, top = 8, w - 8, 6
        cols = 12
        col_w = (right - left) / cols
        bars_h = 74                           # height of the monthly bar area
        base_y = top + bars_h
        peak = max((m["count"] for m in months), default=0) or 1

        small = QFont(self.font()); small.setPointSizeF(8.0)

        # Monthly bloom-count bars.
        for i, m in enumerate(months):
            x = left + i * col_w
            cell = QRectF(x, top, col_w, bars_h)
            if m["is_growing"]:
                p.fillRect(cell, _GROW_SHADE)
            # bar
            frac = m["count"] / peak
            bh = frac * (bars_h - 10)
            if m["is_gap"]:
                # a hollow red slot flags a growing-season month with no forage
                p.setPen(_GAP)
                p.setBrush(Qt.BrushStyle.NoBrush)
                p.drawRect(QRectF(x + col_w * 0.22, base_y - 12,
                                  col_w * 0.56, 10))
            elif m["count"] > 0:
                is_peak = m["month"] == cal["peak_month"]
                p.setPen(Qt.PenStyle.NoPen)
                p.setBrush(_BAR_PEAK if is_peak else _BAR)
                p.drawRoundedRect(QRectF(x + col_w * 0.2, base_y - bh,
                                         col_w * 0.6, bh), 2, 2)
            # month label
            p.setFont(small)
            p.setPen(_TEXT if m["is_growing"] else _TEXT_DIM)
            p.drawText(QRectF(x, base_y + 2, col_w, 14),
                       Qt.AlignmentFlag.AlignCenter, m["abbr"])
            # count above the bar
            if m["count"] > 0 and not m["is_gap"]:
                p.setPen(_TEXT)
                p.drawText(QRectF(x, base_y - bh - 14, col_w, 12),
                           Qt.AlignmentFlag.AlignCenter, str(m["count"]))

        # Divider.
        row_y = base_y + 20
        p.setPen(_GRID)
        p.drawLine(int(left), int(row_y - 4), int(right), int(row_y - 4))

        # Per-plant succession bands (earliest first), colour = flower colour.
        succ = cal["succession"]
        shown = succ[:_MAX_ROWS]
        for r, s in enumerate(shown):
            y = row_y + r * 12
            col = QColor(s["color"]) if _valid(s["color"]) else _BAR
            for mi in range(12):
                if s["months"][mi]:
                    x = left + mi * col_w
                    p.setPen(Qt.PenStyle.NoPen)
                    p.setBrush(col)
                    p.drawRoundedRect(QRectF(x + col_w * 0.12, y + 1.5,
                                             col_w * 0.76, 7), 2, 2)
            # name in the first blooming cell's row, left-aligned faint
            p.setFont(small)
            p.setPen(_TEXT_DIM)
            name = s["name"]
            if len(name) > 22:
                name = name[:21] + "…"
            p.drawText(QRectF(left + 2, y, right - left - 4, 10),
                       Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
                       name)

        extra = len(succ) - len(shown)
        if extra > 0:
            p.setFont(small)
            p.setPen(_TEXT_DIM)
            p.drawText(QRectF(left, row_y + len(shown) * 12, right - left, 12),
                       Qt.AlignmentFlag.AlignLeft,
                       f"+{extra} more flowering plant{'s' if extra != 1 else ''}")


def _valid(hexstr: str) -> bool:
    return bool(hexstr) and QColor(hexstr).isValid()
