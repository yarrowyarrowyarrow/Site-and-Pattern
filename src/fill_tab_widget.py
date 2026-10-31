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
        nat = [sup.tabSizeHint(i).width() for i in range(n)]
        nat_sum = sum(nat)
        if nat_sum <= bar_w:
            # Room to spare: every tab keeps its label's width and takes an
            # equal part of what is left, the last tab the remainder, so the
            # row fills exactly. Until V3.05 each tab was widened to an equal
            # share of the whole bar, which took from a tab wider than its
            # share the room its label needed: Analysis' "Sun & Shade" and
            # Planning's "Timeline" were cut off on a 1366-wide screen with
            # 100 px of strip to spare (the surface audit found them).
            extra = bar_w - nat_sum
            share = extra // n
            last = extra - share * n if index == n - 1 else 0
            hint.setWidth(nat[index] + share + last)
        elif self._allow_shrink:
            # Crowded + opted in: shrink in proportion to the labels, so a
            # short one gives up as much as a long one rather than keeping an
            # equal share it does not need.
            widths = [w * bar_w // nat_sum for w in nat]
            last = bar_w - sum(widths) if index == n - 1 else 0
            hint.setWidth(widths[index] + last)
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
        # Document mode is a *prerequisite* for filling: without it Qt sizes the
        # tab bar to its own size hint (the sum of natural tab widths), so
        # ``tabSizeHint`` never sees the full strip width and the widen logic
        # has nothing to widen into. Most call sites set this; the ones that
        # forgot got natural-width tabs with a gap — so own it here.
        self.setDocumentMode(True)
        self.tabBar().setUsesScrollButtons(False)
