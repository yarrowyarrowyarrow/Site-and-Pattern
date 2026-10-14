"""
elided_label.py — a one-line label that never widens its window (V3.19, QF-12).

A QLabel asks its layout for the width of its whole text, and a window's
minimum width is the sum of what its widgets ask for. The status bar's line
of this month's jobs (src/month_tasks.py) is as long as the design's plant
list: with every catalogue plant in October it asked for 1,104 px, and the
window's minimum width went from 1,007 px to 1,564 px, wider than the
1366 px screen the app is checked at. This label takes the width the layout
gives it and cuts its text there with an ellipsis, the whole line a hover
away, as the getting-started strip's detail line does
(``FirstStepBar._elide_detail``).

``text()`` is the whole line, as it was set; only what is painted is cut.
"""

from __future__ import annotations

from PyQt6.QtCore import QEvent, Qt
from PyQt6.QtWidgets import QLabel, QSizePolicy


class ElidedLabel(QLabel):
    """A single-line QLabel that fits its text to its width with "…"."""

    def __init__(self, text: str = "", parent=None):
        super().__init__(parent)
        self._full = ""
        # Ignored: the layout neither grows for the text nor keeps a minimum
        # for it; the label takes the stretch it is given.
        self.setSizePolicy(QSizePolicy.Policy.Ignored,
                           QSizePolicy.Policy.Preferred)
        self.setText(text)

    def setText(self, text: str) -> None:            # noqa: N802 (Qt name)
        self._full = text or ""
        self._fit()

    def text(self) -> str:                           # noqa: D401
        """The whole line, however much of it fits."""
        return self._full

    def resizeEvent(self, event):                    # noqa: N802 (Qt name)
        super().resizeEvent(event)
        self._fit()

    def changeEvent(self, event):                    # noqa: N802 (Qt name)
        # A stylesheet's font arrives at polish, after the text may be set.
        super().changeEvent(event)
        if event.type() == QEvent.Type.FontChange:
            self._fit()

    def _fit(self) -> None:
        shown = self.fontMetrics().elidedText(
            self._full, Qt.TextElideMode.ElideRight, max(0, self.width() - 2))
        if shown == "…" or (self._full and not shown):
            shown = ""                  # no useful room: say nothing, not "…"
        QLabel.setText(self, shown)
        cut = shown != self._full
        self.setToolTip(self._full if cut else "")
        self.setAccessibleDescription(self._full if cut else "")
