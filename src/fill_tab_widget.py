"""
fill_tab_widget.py — a QTabWidget whose tabs stretch to fill the full strip.

Qt ignores ``QTabBar.setExpanding(True)`` once a ``QTabBar::tab`` stylesheet is
applied, so styled tabs size to their content and leave an empty gap to the
right of the last tab. Sizing the tabs here (via ``tabSizeHint``) makes them
share the full available width instead — and it re-evaluates on resize because
``QTabBar`` re-queries ``tabSizeHint`` whenever it is laid out.

By default the bar only ever *widens* tabs to fill the strip (never below a
label's natural width). A panel with many wide tabs that genuinely overflow a
narrow strip (e.g. the Planning panel's six sub-tabs) can opt into *shrink-to-fit*
with ``FillTabWidget(allow_shrink=True)`` — pair that with
``setElideMode(ElideRight)`` so crowded labels elide cleanly. Shrink is opt-in
because nested/short strips (e.g. the 3-tab "On This Design" strip nested several
FillTabWidgets deep) can be handed a tiny transient width during layout, and
shrinking then would squash their labels below readability.
"""

from __future__ import annotations

from PyQt6.QtWidgets import QTabWidget, QTabBar


class _FillTabBar(QTabBar):
    """Tab bar that spreads its tabs across the whole bar width. With
    ``allow_shrink=True`` it also shrinks tabs to an equal share when their
    natural widths would overflow, so none hide behind a scroll chevron."""

    def __init__(self, parent=None, *, allow_shrink: bool = False):
        super().__init__(parent)
        self._allow_shrink = allow_shrink

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
        elif self._allow_shrink:         # crowded + opted in: shrink to share
            hint.setWidth(want)
        # else: crowded but shrink not allowed → keep natural width (widen-only),
        # which is the safe default for short/nested strips.
        return hint


class FillTabWidget(QTabWidget):
    """Drop-in QTabWidget whose tabs fill the full tab-strip width.

    ``allow_shrink=True`` lets the tabs shrink-to-fit when they'd overflow
    (for panels with many wide tabs); the default is widen-only."""

    def __init__(self, parent=None, *, allow_shrink: bool = False):
        super().__init__(parent)
        self.setTabBar(_FillTabBar(self, allow_shrink=allow_shrink))
