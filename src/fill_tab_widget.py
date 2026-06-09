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
    """Tab bar that spreads its tabs across the whole bar width — and, when the
    tabs' natural widths would overflow, shrinks them to an equal share so every
    tab stays visible instead of disappearing behind a scroll chevron. Pair with
    ``setElideMode(ElideRight)`` so crowded labels elide cleanly rather than clip.
    """

    def tabSizeHint(self, index):
        sup = super()
        hint = sup.tabSizeHint(index)
        n = self.count()
        bar_w = self.width()
        if n <= 0 or bar_w <= 0:
            return hint
        base = bar_w // n
        # Give the remainder to the last tab so the row fills exactly.
        want = (bar_w - base * (n - 1)) if index == n - 1 else base
        nat_sum = sum(sup.tabSizeHint(i).width() for i in range(n))
        if nat_sum <= bar_w:
            if want > hint.width():      # room to spare: widen to fill the strip
                hint.setWidth(want)
        else:                            # crowded: shrink to share so none hide
            hint.setWidth(want)
        return hint


class FillTabWidget(QTabWidget):
    """Drop-in QTabWidget whose tabs fill the full tab-strip width."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setTabBar(_FillTabBar(self))
