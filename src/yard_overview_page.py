"""
yard_overview_page.py — Design › Overview, the six cards (OV-2, V3.27;
docs/homeowner/06-yard-overview.md §4, §6).

Design principle P6 — see docs/DESIGN_PHILOSOPHY.md.

Draws :func:`src.yard_overview_items.overview`: a heading, then one card per
item with its title, its status in words (never a colour alone), its lines and
one button. A card's *More detail* link (MD-4) opens the advanced page that
explains it. Every line is a label a reader can select and hear; the page
scrolls down, never sideways. What the buttons do is
``src/yard_overview_flow.py``'s.
"""

from __future__ import annotations

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import (
    QFrame, QHBoxLayout, QLabel, QPushButton, QScrollArea, QVBoxLayout,
    QWidget,
)

_HEAD = "color: #e8f5e9; font-size: 16px; font-weight: bold;"
_SUB = "color: #a5bfa8; font-size: 12px;"
_TITLE = "color: #e8f5e9; font-size: 14px; font-weight: bold;"
_BODY = "color: #c8e6c9; font-size: 13px;"
_STRIP = "color: #c8e6c9; font-size: 12px;"
#: Status colours, each with its word beside it (4.5:1 on the card).
_STATUS = {"good": "#a5d6a7", "look": "#ffcc80", "plan": "#b0bec5"}
_CARD = ("QFrame#overviewCard { background: #1e2e1e; border: 1px solid "
         "#2e4a2e; border-radius: 6px; }")
_BUTTON = ("QPushButton { background: #2e4a2e; color: #e8f5e9; border: 1px "
           "solid #3d6b3d; border-radius: 4px; padding: 4px 12px; "
           "font-size: 13px; min-height: 24px; }"
           "QPushButton:hover { border-color: #66bb6a; }"
           "QPushButton:focus { border: 2px solid #ffe082; }")
_LINK = ("QPushButton { color: #ffe082; background: transparent; border: "
         "none; font-size: 13px; min-height: 24px; padding: 0 4px; }"
         "QPushButton:focus { border: 2px solid #ffe082; }")


def _label(text: str, style: str) -> QLabel:
    label = QLabel(text)
    label.setStyleSheet(style)
    label.setWordWrap(True)
    label.setTextFormat(Qt.TextFormat.PlainText)
    label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
    return label


class OverviewPage(QScrollArea):
    """The Overview page. ``action_requested(target)`` when a card's button
    or link is pressed."""

    action_requested = pyqtSignal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("overviewPage")
        self.setAccessibleName("How your yard is doing")
        self.setWidgetResizable(True)
        self.setFrameShape(QFrame.Shape.NoFrame)
        self.setHorizontalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        body = QWidget()
        body.setAccessibleName("Overview")
        self._col = QVBoxLayout(body)
        self._col.setContentsMargins(8, 8, 8, 8)
        self._col.setSpacing(8)
        self.setWidget(body)
        self.cards: dict = {}
        self.buttons: dict = {}
        self.show_items("", [])

    def _clear(self):
        while self._col.count():
            item = self._col.takeAt(0)
            w = item.widget()
            if w is not None:
                w.setParent(None)
                w.deleteLater()
        self.cards, self.buttons = {}, {}

    def show_items(self, heading: str, items: list) -> None:
        from src.yard_overview_items import TITLE
        keep = self.verticalScrollBar().value()
        self._clear()
        self._col.addWidget(_label(TITLE, _HEAD))
        if heading:
            self._col.addWidget(_label(heading, _SUB))
        for item in items:
            card = self._card(item)
            self.cards[item.key] = card
            self._col.addWidget(card)
        self._col.addStretch()
        self.verticalScrollBar().setValue(keep)

    def _card(self, item) -> QFrame:
        card = QFrame()
        card.setObjectName("overviewCard")
        card.setStyleSheet(_CARD)
        card.setAccessibleName(f"{item.title}, {item.status_word}"
                               if item.key != "empty" else item.title)
        col = QVBoxLayout(card)
        col.setContentsMargins(10, 8, 10, 8)
        col.setSpacing(4)
        if item.key != "empty":
            top = QHBoxLayout()
            top.addWidget(_label(item.title, _TITLE), 1)
            status = _label(item.status_word, f"color: "
                            f"{_STATUS.get(item.status, '#c8e6c9')}; "
                            "font-size: 13px; font-weight: bold;")
            status.setWordWrap(False)
            top.addWidget(status, 0, Qt.AlignmentFlag.AlignTop)
            col.addLayout(top)
        for line in item.lines:
            col.addWidget(_label(line, _BODY))
        if item.strip:
            strip = _label("   ".join(f"{m} {n}" for m, n in item.strip),
                           _STRIP)
            strip.setAccessibleName("Kinds in flower each month: " + ", ".join(
                f"{m} {n}" for m, n in item.strip))
            col.addWidget(strip)
        row = QHBoxLayout()
        row.addStretch()
        if item.more:
            words, target = item.more
            link = QPushButton(f"{words} ▸")
            link.setObjectName("overviewMore")
            link.setStyleSheet(_LINK)
            link.setCursor(Qt.CursorShape.PointingHandCursor)
            link.setAccessibleName(f"{words}: more detail")
            link.clicked.connect(lambda _c=False, t=target:
                                 self.action_requested.emit(t))
            row.addWidget(link)
        if item.action:
            button = QPushButton(item.action)
            button.setObjectName("overviewAction")
            button.setStyleSheet(_BUTTON)
            button.setAccessibleName(item.action)
            button.clicked.connect(lambda _c=False, t=item.target:
                                   self.action_requested.emit(t))
            row.addWidget(button)
            self.buttons[item.key] = button
        if item.more or item.action:
            col.addLayout(row)
        return card
