"""
first_step_bar.py — the empty-state hint, as a strip above the map (F44 / F45).

The map is a QWebEngineView, so the honest place for an empty-state overlay is
*beside* it, not inside it: drawing into the web view would mean new JS against
a chunk already near its guard ceiling, for a hint that has nothing to do with
Leaflet. A slim Qt strip between the toolbars and the map costs no JS, cannot
be repainted away by a map redraw, and reads as part of the app chrome.

It shows the three-step path with the current step highlighted, carries the
✨ Generate Design call to action, and **removes itself** once the user has a
pin, a boundary and plants — guidance that outstays its welcome becomes
furniture. A View-menu toggle brings it back.

Presentation only: the steps and their done-ness come from
:func:`src.onboarding.steps_progress`.
"""

from __future__ import annotations

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import (
    QHBoxLayout, QLabel, QPushButton, QSizePolicy, QWidget,
)


class FirstStepBar(QWidget):
    """Three step chips + a Generate button + a dismiss ✕."""

    #: A step chip was clicked — carries the step key ('pin'/'boundary'/'plants').
    step_clicked = pyqtSignal(str)
    generate_requested = pyqtSignal()
    dismissed = pyqtSignal()

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self.setObjectName("firstStepBar")
        self.setStyleSheet(
            "#firstStepBar { background: #16281a; "
            "border-bottom: 1px solid #2e4a2e; }")
        row = QHBoxLayout(self)
        row.setContentsMargins(10, 5, 8, 5)
        row.setSpacing(8)

        lead = QLabel("Getting started:")
        lead.setStyleSheet(
            "color: #8aa88a; font-size: 11px; font-weight: bold;")
        row.addWidget(lead)

        self._chips: list[QPushButton] = []
        for _ in range(3):
            chip = QPushButton()
            chip.setCursor(Qt.CursorShape.PointingHandCursor)
            chip.setFlat(True)
            row.addWidget(chip)
            self._chips.append(chip)

        row.addStretch(1)

        # Lowest-priority element in the strip: it may be cut on a narrow
        # window, which is why the same sentence is on each chip's tooltip.
        self._detail = QLabel("")
        self._detail.setStyleSheet("color: #a5c8a5; font-size: 11px;")
        self._detail.setTextFormat(Qt.TextFormat.PlainText)
        self._detail.setMinimumWidth(0)
        self._detail.setSizePolicy(QSizePolicy.Policy.Ignored,
                                   QSizePolicy.Policy.Preferred)
        row.addWidget(self._detail, 2)

        self._generate = QPushButton("✨ Generate Design")
        self._generate.setCursor(Qt.CursorShape.PointingHandCursor)
        self._generate.setToolTip(
            "Fill your boundary with native plants chosen from your goals "
            "(Ctrl+G).\nEverything it places stays editable — drag, delete or "
            "add to it.")
        self._generate.setStyleSheet(
            "QPushButton { background: #2e7d32; color: #e8f5e9; "
            "border: 1px solid #66bb6a; border-radius: 4px; "
            "padding: 4px 12px; font-weight: bold; font-size: 11px; }"
            "QPushButton:hover { background: #388e3c; }")
        self._generate.clicked.connect(self.generate_requested)
        row.addWidget(self._generate)

        close = QPushButton("✕")
        close.setCursor(Qt.CursorShape.PointingHandCursor)
        close.setFlat(True)
        close.setFixedWidth(22)
        close.setToolTip("Hide this strip (View → Getting-started strip "
                         "brings it back)")
        close.setStyleSheet(
            "QPushButton { color: #7a8f7a; font-size: 12px; border: none; }"
            "QPushButton:hover { color: #e8f5e9; }")
        close.clicked.connect(self.dismissed)
        row.addWidget(close)

    # ── Update ───────────────────────────────────────────────────────────────

    def set_generate_enabled(self, enabled: bool):
        """Grey the strip's Generate button while a run is in flight, in step
        with the File-menu action (GenerationController). This strip is now the
        only Generate button on the main window — the Draw-toolbar one was
        removed — so without this a second run could be started mid-flight."""
        self._generate.setEnabled(bool(enabled))

    def set_progress(self, steps: list, current: dict):
        """Render ``src.onboarding.steps_progress`` output plus the
        ``first_step`` dict that says which one is live."""
        for i, chip in enumerate(self._chips):
            if i >= len(steps):
                chip.setVisible(False)
                continue
            step = steps[i]
            chip.setVisible(True)
            done = bool(step.get("done"))
            live = (not done) and step.get("key") == current.get("key")
            mark = "✓" if done else f"{i + 1}."
            # The chip carries the short label; the sentence lives in the
            # tooltip so a narrow window loses nothing (the detail label
            # beside it is the first thing the layout squeezes).
            chip.setText(f"  {mark} {step.get('short') or step.get('title', '')}  ")
            chip.setToolTip(f"{step.get('title', '')}\n\n{step.get('detail', '')}")
            chip.setSizePolicy(QSizePolicy.Policy.Fixed,
                               QSizePolicy.Policy.Preferred)
            chip.setStyleSheet(self._chip_style(done, live))
            try:
                chip.clicked.disconnect()
            except TypeError:
                pass
            chip.clicked.connect(
                lambda _checked=False, k=step.get("key", ""):
                self.step_clicked.emit(k))
        self._detail_text = "" if current.get("complete") \
            else current.get("detail", "")
        self._detail.setToolTip(self._detail_text)
        self._elide_detail()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._elide_detail()

    def _elide_detail(self):
        """Cut the detail with an ellipsis rather than mid-word.

        A QLabel clipped by the layout looks like a rendering bug; an elided
        one looks like a deliberate summary — and the full sentence is a
        hover away on both the label and the live chip.
        """
        text = getattr(self, "_detail_text", "")
        if not text:
            self._detail.setText("")
            return
        width = max(0, self._detail.width() - 2)
        if width < 40:              # no useful room — the chips say enough
            self._detail.setText("")
            return
        self._detail.setText(
            self._detail.fontMetrics().elidedText(
                text, Qt.TextElideMode.ElideRight, width))

    @staticmethod
    def _chip_style(done: bool, live: bool) -> str:
        if live:
            return ("QPushButton { color: #0d1f0d; background: #a5d6a7; "
                    "border: 1px solid #c5e1a5; border-radius: 10px; "
                    "padding: 2px 4px; font-size: 11px; font-weight: bold; }")
        if done:
            return ("QPushButton { color: #7a9f7a; background: transparent; "
                    "border: 1px solid #2e4a2e; border-radius: 10px; "
                    "padding: 2px 4px; font-size: 11px; }")
        return ("QPushButton { color: #b0bec5; background: transparent; "
                "border: 1px dashed #3e5c3e; border-radius: 10px; "
                "padding: 2px 4px; font-size: 11px; }")
