"""
scroll_column.py — a side-panel column that scrolls instead of squeezing (V2.98).

The side panel is one column of fixed height. When its sections need more than
that, a plain QVBoxLayout does not refuse: it hands each child less than its
minimum, and the children overlap. That is how the Plant Communities tab showed
its pattern buttons 11 px tall (0 px on a 1366 × 768 laptop) until V2.98, and
how, with the buttons moved to the placement bar, a full community mix still
laid its rows over its own Place mix button: 670 px of column for 806 px of
minimums.

A column built here scrolls as a whole in that case. When everything fits,
nothing changes: the content is stretched to the viewport exactly as before, so
a list that stretches still fills the space.
"""

from __future__ import annotations

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QFrame, QScrollArea, QVBoxLayout, QWidget


class _Column(QVBoxLayout):
    """Reports no height-for-width, so the scroll area sizes the column by
    its children's *minimums*. One word-wrapping label anywhere in a column
    makes a plain layout report height-for-width, and QScrollArea then treats
    the column's *preferred* height as its minimum: the Communities column
    scrolled at 1366 × 768 with nothing squeezed at all (779 px preferred,
    671 px minimum, 656 px of viewport). The children still wrap: the box
    layout asks each one for its height at the width it gets."""

    def hasHeightForWidth(self) -> bool:
        return False


def scroll_column(owner: QWidget) -> QVBoxLayout:
    """Give ``owner`` a column that scrolls when its content cannot fit, and
    return the column's layout to build into.

    Horizontal scrolling is only as needed: a splitter dragged narrower than
    the content gets a scroll bar rather than clipped controls.
    """
    outer = QVBoxLayout(owner)
    outer.setContentsMargins(0, 0, 0, 0)
    outer.setSpacing(0)
    scroll = QScrollArea(owner)
    scroll.setWidgetResizable(True)
    scroll.setFrameShape(QFrame.Shape.NoFrame)
    scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
    content = QWidget()
    scroll.setWidget(content)
    outer.addWidget(scroll)
    owner._column_scroll = scroll
    return _Column(content)
