"""
src/live_refresh.py — a read-out that follows the design (V3.05).

Five pages opened on a button and an empty box: Analysis › Habitat, and Planning
› Effort, Wildlife, Harvest and Water. Each panel was already handed the placed
plants and structures on every edit, so the button only gated work the app
could do by itself, and its result did not follow the design: press it, add six
plants, and the page still described the old design without saying so. The
V3.05 surface audit counted them; ``analysis_panel.set_placed_plants`` had
already named the class ("the V2.42 stale-list bug") and moved three other
read-outs off their buttons one release at a time.

:class:`LiveRefresh` is the rule in one place. A tab widget's pages are paired
with the function that fills each; the current page is refilled when its panel
comes on screen, when the page becomes current, and when :meth:`LiveRefresh.poke`
says an input changed. A page nobody is looking at is not computed (some of
these warm photographs or walk the edge layer), and a burst of edits (a
community of eight placed at once) is one refill, not eight.
"""

from __future__ import annotations

from typing import Callable

from PyQt6.QtCore import QEvent, QObject, QTimer
from PyQt6.QtWidgets import QTabWidget, QWidget

#: Long enough to fold a burst of edits into one refill, short enough that the
#: page has changed by the time the eye gets back to it.
DELAY_MS = 150


class LiveRefresh(QObject):
    """Refill the page on screen when it shows or its inputs change."""

    def __init__(self, owner: QWidget, tabs: QTabWidget,
                 pages: dict, delay_ms: int = DELAY_MS):
        super().__init__(owner)
        self._owner = owner
        self._tabs = tabs
        self._pages: dict = dict(pages)     # page widget → fill function
        self._timer = QTimer(self)
        self._timer.setSingleShot(True)
        self._timer.setInterval(delay_ms)
        self._timer.timeout.connect(self._run)
        tabs.currentChanged.connect(lambda _i: self.poke())
        owner.installEventFilter(self)

    def poke(self) -> None:
        """An input changed, or something may now be on screen."""
        self._timer.start()

    def eventFilter(self, obj, event) -> bool:                 # noqa: N802
        if obj is self._owner and event.type() == QEvent.Type.Show:
            self.poke()
        return False

    def fill_now(self) -> bool:
        """Fill the current page at once, if it is on screen. Returns whether
        anything was filled (tests, and callers that cannot wait)."""
        self._timer.stop()
        return self._run()

    def _run(self) -> bool:
        try:
            if not self._owner.isVisible():
                return False
            fill: Callable | None = self._pages.get(self._tabs.currentWidget())
        except RuntimeError:            # the panel was deleted while queued
            return False
        if fill is None:
            return False
        fill()
        return True
