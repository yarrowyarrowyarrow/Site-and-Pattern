"""
flow_layout.py — a layout that wraps, like words in a paragraph (V2.98).

The placement bar floats over the map, and the map is as wide as whatever the
side panel leaves it: about 900 px on a 1366 px laptop, far more on a desktop.
A row of controls that fits one can be clipped on the other, and Qt's box
layouts clip by squeezing widgets below their size hints, which is how the
Placement section's buttons ended up 11 px tall in V2.97. This lays each item
out at its size hint and starts a new line when the next one would not fit, so
a narrow map costs height, never legibility.

Qt ships no such layout (it is an example in the docs); this is that example,
with each line's items centred vertically so a checkbox sits level with the
spin box beside it. Hidden widgets take no room (``QLayoutItem.isEmpty``).
"""

from __future__ import annotations

from PyQt6.QtCore import QPoint, QRect, QSize, Qt
from PyQt6.QtWidgets import QLayout


class FlowLayout(QLayout):
    """Left-to-right, wrapping. Reports ``heightForWidth`` so a parent that
    sizes itself by hand (the placement bar) can ask how tall it must be."""

    def __init__(self, parent=None, *, h_spacing: int = 8, v_spacing: int = 6):
        super().__init__(parent)
        self._items = []
        self._h_spacing = h_spacing
        self._v_spacing = v_spacing

    # ── QLayout protocol ─────────────────────────────────────────────────────

    def addItem(self, item):
        self._items.append(item)

    def count(self) -> int:
        return len(self._items)

    def itemAt(self, index):
        return self._items[index] if 0 <= index < len(self._items) else None

    def takeAt(self, index):
        return self._items.pop(index) if 0 <= index < len(self._items) else None

    def expandingDirections(self):
        return Qt.Orientation(0)

    def hasHeightForWidth(self) -> bool:
        return True

    def heightForWidth(self, width: int) -> int:
        return self._arrange(QRect(0, 0, width, 0), apply=False)

    def setGeometry(self, rect):
        super().setGeometry(rect)
        self._arrange(rect, apply=True)

    def sizeHint(self) -> QSize:
        return self.minimumSize()

    def minimumSize(self) -> QSize:
        size = QSize()
        for item in self._items:
            if not item.isEmpty():
                size = size.expandedTo(item.minimumSize())
        m = self.contentsMargins()
        return size + QSize(m.left() + m.right(), m.top() + m.bottom())

    # ── Layout ───────────────────────────────────────────────────────────────

    def _lines(self, width: int) -> list:
        """Split the visible items into lines that fit ``width``."""
        lines, line, used = [], [], 0
        for item in self._items:
            if item.isEmpty():
                continue
            w = item.sizeHint().width()
            if line and used + self._h_spacing + w > width:
                lines.append(line)
                line, used = [], 0
            used += (self._h_spacing if line else 0) + w
            line.append(item)
        if line:
            lines.append(line)
        return lines

    def _arrange(self, rect: QRect, *, apply: bool) -> int:
        m = self.contentsMargins()
        inner = rect.adjusted(m.left(), m.top(), -m.right(), -m.bottom())
        y = inner.y()
        lines = self._lines(max(1, inner.width()))
        for i, line in enumerate(lines):
            line_h = max(item.sizeHint().height() for item in line)
            x = inner.x()
            for item in line:
                hint = item.sizeHint()
                if apply:
                    top = y + (line_h - hint.height()) // 2
                    item.setGeometry(QRect(QPoint(x, top), hint))
                x += hint.width() + self._h_spacing
            y += line_h + (self._v_spacing if i < len(lines) - 1 else 0)
        return y - rect.y() + m.bottom()
