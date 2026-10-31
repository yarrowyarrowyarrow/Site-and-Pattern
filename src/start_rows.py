"""
start_rows.py — what the start screen is built from (V3.42): its rows, its
links and its Learn card, in its colours.

Design principle P13 — see docs/DESIGN_PHILOSOPHY.md.
UI conventions: docs/UI_PRINCIPLES.md (Krug).

Split from ``start_screen.py`` when the two-column rebuild (F259) took that
module past its ceiling: the screen decides what is on it and in which state;
this decides what a row, a link and the card look like.

**One row is filled, and it is the default button**: Enter presses it. The
owner's H3 adds a second weight below it, *outlined* (a green border on a
slightly lighter ground), for the other two of the screen's three doors: the
last design and the Learn card. Everything else is plain.
"""

from __future__ import annotations

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QFrame, QHBoxLayout, QLabel, QPushButton, QVBoxLayout, QWidget,
)

from src.elided_label import ElidedLabel

#: A row's colours. Every pair clears 4.5 : 1 on the row and on its hover
#: (``tests/test_front_door.py``).
PLAIN = dict(bg="#1c2c1c", border="#39543a", hover="#2b4526",
             head="#e8f5e9", note="#a5c4a7")
#: The default: white on the primary green (5.13 : 1).
FILLED = dict(bg="#2e7d32", border="#66bb6a", hover="#276b2b",
              head="#ffffff", note="#ffffff")
#: H3's second weight: one of the three doors, not the default.
OUTLINED = dict(bg="#1f3a21", border="#66bb6a", hover="#2b4526",
                head="#e8f5e9", note="#c8e6c9")
#: Unsaved work to restore: amber, because it is the one with a deadline.
AMBER = dict(bg="#7a4f00", border="#ffb74d", hover="#8d5c00",
             head="#ffffff", note="#ffffff")
#: A row inside the Learn card: the card draws the edge.
IN_CARD = dict(PLAIN, bg="transparent", border="transparent",
               edge="transparent")

#: What is not a row: headings, quiet lines, and the hairlines between.
HEAD, QUIET, RULE = "#e8f5e9", "#a5c4a7", "#2f4a30"

#: How tall a row is: two lines of words, or the Rename and Delete under it.
ROW_HEIGHT = 52
#: The column beside each design that holds its Rename and Delete.
LINK_COLUMN = 72

_ROW = ("QPushButton {{ text-align: left; background: {bg}; "
        "border: 1px solid {border}; border-radius: 7px; }}"
        "QPushButton:hover {{ background: {hover}; border-color: {edge}; }}"
        "QPushButton:focus {{ border: 2px solid #e8f5e9; }}")

#: Secondary actions look like links, because they are ones.
LINK = (
    "QPushButton { background: transparent; border: none; color: #8fc98f; "
    "font-size: 13px; text-align: left; padding: 0 2px; "
    "text-decoration: underline; }"
    "QPushButton:hover { color: #d7f0d7; }"
)
#: Delete turns coral under the pointer, and only then.
DELETE_LINK = LINK.replace("QPushButton:hover { color: #d7f0d7; }",
                           "QPushButton:hover { color: #ef9a9a; }")


def _words(text: str, size: int, colour: str, *, bold: bool = False,
           fits: bool = False) -> QLabel:
    """A label in the screen's type; with ``fits`` it is cut with "…" to the
    width it is given (the whole text kept for its tooltip)."""
    label = ElidedLabel(text) if fits else QLabel(text)
    label.setStyleSheet(f"color: {colour}; font-size: {size}px; "
                        f"font-weight: {'bold' if bold else 'normal'}; "
                        "background: transparent;")
    return label


def heading(text: str) -> QLabel:
    return _words(text, 16, HEAD, bold=True)


def quiet(text: str) -> QLabel:
    label = _words(text, 13, QUIET)
    label.setWordWrap(True)
    return label


def link(parent: QWidget, text: str, tooltip: str = "", *,
         deleting: bool = False) -> QPushButton:
    """A link-like button. It is never the dialog's default."""
    btn = QPushButton(text, parent)
    btn.setCursor(Qt.CursorShape.PointingHandCursor)
    btn.setFlat(True)
    btn.setAutoDefault(False)
    btn.setStyleSheet(DELETE_LINK if deleting else LINK)
    if tooltip:
        btn.setToolTip(tooltip)
    return btn


def rule() -> QFrame:
    """A hairline that draws: ``QFrame.HLine`` ignores a stylesheet
    ``color:``, so a 1 px frame with a background does what is meant."""
    line = QFrame()
    line.setFixedHeight(1)
    line.setStyleSheet(f"background-color: {RULE}; border: none;")
    return line


def column_gap() -> QWidget:
    """The empty link column beside a row with no Rename, so every row's
    right edge lines up with the designs'."""
    gap = QWidget()
    gap.setFixedWidth(LINK_COLUMN)
    return gap


class Row(QPushButton):
    """One choice: what it is (``title``), a line under it (``note``), a fact
    on the right (``fact``, a design's date), and a ``+`` or a ``›`` when it
    starts something or leads somewhere.

    ``primary`` is true for the filled and the amber rows: the screen has
    exactly one, and it is the default button."""

    def __init__(self, title: str, colours: dict, *, note: str = "",
                 fact: str = "", plus: bool = False, chevron: bool = False,
                 described: str = "", parent: QWidget | None = None):
        super().__init__(parent)
        self.words = (title, note, fact)
        self.primary = colours is FILLED or colours is AMBER
        self.outlined = colours is OUTLINED
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setMinimumHeight(ROW_HEIGHT)
        self.setStyleSheet(_ROW.format(**dict(
            {"edge": "#a5d6a7"}, **colours)))
        row = QHBoxLayout(self)
        row.setContentsMargins(14, 6, 14, 6)
        row.setSpacing(10)
        if plus:
            mark = _words("+", 20, colours["head"], bold=True)
            mark.setFixedWidth(14)
            row.addWidget(mark)
        # The name and the line under it take the room the date leaves and
        # end in "…" where it runs out: in a wide font a long name was cut
        # mid-letter (V3.42, measured in CI's DejaVu Sans).
        lines = QVBoxLayout()
        lines.setSpacing(1)
        lines.addWidget(_words(title, 15, colours["head"], bold=True,
                               fits=True))
        if note:
            lines.addWidget(_words(note, 13, colours["note"], fits=True))
        row.addLayout(lines, 1)
        if fact:
            right = _words(fact, 13, colours["note"])
            right.setAlignment(Qt.AlignmentFlag.AlignRight
                               | Qt.AlignmentFlag.AlignVCenter)
            row.addWidget(right)
        if chevron:
            row.addWidget(_words("›", 18, colours["note"]))
        # The words are child labels, so a screen reader would hear only
        # "button" (V2.98 review, finding 17).
        self.setAccessibleName(title)
        self.setAccessibleDescription(
            described or ", ".join(t for t in (note, fact) if t))


class LearnCard(QFrame):
    """The Learn column: one outlined card of rows, each leading somewhere,
    with a hairline between them (V3.42)."""

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self.setObjectName("learnCard")
        self.setStyleSheet(
            f"QFrame#learnCard {{ background: {PLAIN['bg']}; "
            f"border: 1px solid {OUTLINED['border']}; border-radius: 8px; }}")
        self.rows: list[Row] = []
        self._lay = QVBoxLayout(self)
        self._lay.setContentsMargins(2, 2, 2, 2)
        self._lay.setSpacing(0)

    def add(self, title: str, note: str, tooltip: str = "") -> Row:
        if self.rows:
            self._lay.addWidget(rule())
        row = Row(title, IN_CARD, note=note, chevron=True, parent=self)
        if tooltip:
            row.setToolTip(tooltip)
        self._lay.addWidget(row)
        self.rows.append(row)
        return row


# ── Layout helpers ───────────────────────────────────────────────────────────

def clear_layout(layout) -> None:
    """Empty ``layout``, nested layouts and their widgets included."""
    while layout.count():
        item = layout.takeAt(0)
        w = item.widget()
        if w is not None:
            # Out of the window now, deleted later: hiding a box hides its
            # Rename and Delete only to the eye, and they stayed the screen's
            # children (and a screen reader's) until the deferred delete.
            w.hide()
            w.setParent(None)
            w.deleteLater()
        elif item.layout() is not None:
            clear_layout(item.layout())


def retab(layout) -> None:
    """Tab in the order drawn: a widget made after its window was built
    joins the end of the window's tab chain. A container that takes no focus
    (the Learn column, its card) is walked into."""
    def walk(lay):
        for item in (lay.itemAt(i) for i in range(lay.count())):
            w = item.widget()
            if w is None:
                if item.layout() is not None:
                    yield from walk(item.layout())
            elif w.isHidden():
                continue
            elif w.focusPolicy() & Qt.FocusPolicy.TabFocus:
                yield w
            elif w.layout() is not None:
                yield from walk(w.layout())
    chain = list(walk(layout))
    for a, b in zip(chain, chain[1:]):
        QWidget.setTabOrder(a, b)
