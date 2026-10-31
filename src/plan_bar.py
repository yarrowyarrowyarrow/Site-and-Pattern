"""
plan_bar.py — the line above the map after a plan lands (PY-6, PY-8, V3.29;
docs/homeowner/07-plan-my-yard.md §4.4–§4.5).

*Your plan: 95 plants of 14 kinds.* with **Try another**, **About this plan**
and **Undo**. It replaces the modal *Design notes* box that opened after every
plan: the notes are one press away (*About this plan*, which in the advanced
app also lists the Design notes) instead of between the person and their map.

A strip in the map's column, beside the map, never inside it: the web view's
accessible interface reports only the page (the V2.98 rule). It goes when the
plan it names leaves the design (an undo, a replace, a new design), which
:func:`follow` checks on every edit (``follow_design.request_sync``).
"""

from __future__ import annotations

from PyQt6.QtCore import pyqtSignal
from PyQt6.QtWidgets import QFrame, QHBoxLayout, QLabel, QPushButton

_BUTTON = ("QPushButton { background: #2e4a2e; color: #e8f5e9; border: none; "
           "border-radius: 4px; padding: 3px 12px; font-size: 13px; }"
           "QPushButton:disabled { color: #9fb59f; }"
           "QPushButton:focus { border: 2px solid #ffe082; }")


class PlanBar(QFrame):
    """One line: what the plan is, and three things to do with it."""

    try_another = pyqtSignal()
    about = pyqtSignal()
    undo = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("planBar")
        self.setAccessibleName("Your plan")
        self.setStyleSheet(
            "QFrame#planBar { background: #1e2e1e; "
            "border-bottom: 1px solid #2e4a2e; }"
            "QLabel { color: #e8f5e9; font-size: 13px; }")
        row = QHBoxLayout(self)
        row.setContentsMargins(10, 4, 10, 4)
        self.label = QLabel("")
        row.addWidget(self.label, 1)
        self.buttons = []
        for text, signal, tip in (
                ("Try another", self.try_another,
                 "Make a different plan from the same answers. "
                 "It replaces this one; Undo brings this one back."),
                ("About this plan", self.about,
                 "What this plan holds and what it could not do."),
                ("Undo", self.undo, "Take the plan off the map (Ctrl+Z).")):
            b = QPushButton(text)
            b.setStyleSheet(_BUTTON)
            b.setToolTip(tip)
            b.clicked.connect(signal)
            row.addWidget(b)
            self.buttons.append(b)
        close = QPushButton("✕")
        close.setFlat(True)
        close.setFixedWidth(24)
        close.setAccessibleName("Hide this line")
        close.setToolTip("Hide this line. The plan stays.")
        close.setStyleSheet("QPushButton { color: #b0c4b0; border: none; "
                            "font-size: 13px; }"
                            "QPushButton:focus { border: 2px solid #ffe082; }")
        close.clicked.connect(self.hide)
        row.addWidget(close)
        self.run = ""
        self.hide()

    def show_plan(self, plants: int, kinds: int, run: str) -> None:
        self.run = run
        self._text = (f"Your plan: {plants} plant{'s' if plants != 1 else ''} "
                      f"of {kinds} kind{'s' if kinds != 1 else ''}.")
        self.set_busy(False)
        self.show()

    def set_busy(self, busy: bool) -> None:
        """While another plan is made: *Planning…*, and nothing to press."""
        self.label.setText("Planning another…" if busy
                           else getattr(self, "_text", ""))
        for b in self.buttons:
            b.setEnabled(not busy)

    def follow(self, project: dict) -> None:
        """Hide when the plan this line names is no longer in ``project``."""
        if not self.isVisible() or not self.run:
            return
        for f in (project or {}).get("features") or []:
            if (f.get("properties") or {}).get("plan_run") == self.run:
                return
        self.hide()


def make(main) -> PlanBar:
    """The bar, for the map's column; its buttons go to the controller."""
    bar = PlanBar(main)
    main.plan_bar = bar
    gen = main._generation
    bar.try_another.connect(gen.try_another)
    bar.about.connect(gen.show_about)
    bar.undo.connect(lambda: main._do_undo())
    return bar
