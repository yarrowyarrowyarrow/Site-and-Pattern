"""
plan_about.py — *About this plan*, the window (PY-8, V3.29; docs/homeowner/07
§4.5).

Non-modal, opened from the plan bar: the plan's lines and what it could not do
(:mod:`src.plan_notes`), in the Overview's voice. With the Advanced tools on it
also lists the Design notes, the generator's English for every note, which a
modal box showed after every plan until V3.29.
"""

from __future__ import annotations

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QDialog, QDialogButtonBox, QLabel, QScrollArea, QVBoxLayout, QWidget,
)

TITLE = "About this plan"


class AboutPlan(QDialog):
    """The summary, and in the advanced app the Design notes under it."""

    def __init__(self, summary: dict, design_notes: list = (),
                 parent: QWidget | None = None):
        super().__init__(parent)
        self.setWindowTitle(TITLE)
        self.setModal(False)
        self.setMinimumWidth(460)
        outer = QVBoxLayout(self)
        body = QWidget()
        col = QVBoxLayout(body)
        col.setContentsMargins(0, 0, 6, 0)
        self.labels = []

        def add(text: str, bold: bool = False) -> None:
            lab = QLabel(f"<b>{text}</b>" if bold else text)
            lab.setTextFormat(Qt.TextFormat.RichText if bold
                              else Qt.TextFormat.PlainText)
            lab.setWordWrap(True)
            lab.setTextInteractionFlags(
                Qt.TextInteractionFlag.TextSelectableByMouse)
            col.addWidget(lab)
            self.labels.append(lab)

        add(summary.get("heading", TITLE), bold=True)
        for line in summary.get("lines", []):
            add(line)
        if summary.get("could_not"):
            add("What I could not do", bold=True)
            for line in summary["could_not"]:
                add("• " + line)
        if design_notes:
            add("Design notes", bold=True)
            for line in design_notes:
                add("• " + line)
        col.addStretch(1)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QScrollArea.Shape.NoFrame)
        scroll.setHorizontalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setWidget(body)
        outer.addWidget(scroll, 1)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        buttons.rejected.connect(self.close)
        outer.addWidget(buttons)
        from src.generate_design_dialog import fitted_height
        self.resize(self.width(), fitted_height(
            body.sizeHint().height() + buttons.sizeHint().height() + 40, self))

    def text(self) -> str:
        return "\n".join(lab.text() for lab in self.labels)
