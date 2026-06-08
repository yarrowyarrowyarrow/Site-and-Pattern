"""
fill_tab_widget.py — a QTabWidget whose tabs stretch to fill the full strip.

Qt ignores ``QTabBar.setExpanding(True)`` once a ``QTabBar::tab`` stylesheet is
applied, so styled tabs size to their content and leave an empty gap to the
right of the last tab. Sizing the tabs here (via ``tabSizeHint``) makes them
share the full available width instead — and it re-evaluates on resize because
``QTabBar`` re-queries ``tabSizeHint`` whenever it is laid out.
"""

from __future__ import annotations

from PyQt6.QtWidgets import QTabWidget, QTabBar


class _FillTabBar(QTabBar):
    """Tab bar that spreads its tabs across the whole bar width."""

    def tabSizeHint(self, index):
        hint = super().tabSizeHint(index)
        n = self.count()
        bar_w = self.width()
        if n <= 0 or bar_w <= 0:
            return hint
        base = bar_w // n
        # Give the remainder to the last tab so the row fills exactly.
        want = (bar_w - base * (n - 1)) if index == n - 1 else base
        if want > hint.width():          # only ever widen, never clip a label
            hint.setWidth(want)
        return hint


class FillTabWidget(QTabWidget):
    """Drop-in QTabWidget whose tabs fill the full tab-strip width."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setTabBar(_FillTabBar(self))
