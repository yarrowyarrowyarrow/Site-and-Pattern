"""
guide_window.py — Help › How to Plan Your Yard, inside the app (F253, V3.38).

Design principle P13 — see docs/DESIGN_PHILOSOPHY.md.

Shows :mod:`src.guide`'s Markdown in a ``QTextBrowser``: offline, in the app's
own colours, with the controls named in the words on screen. Not modal: a
person reads a step and does it on the map behind.

Parented to the main window, so it closes with it. A window with no parent
would keep the app running on its own after the main window closed, because
Qt quits when the last top-level window does.
"""

from __future__ import annotations

from PyQt6.QtGui import QColor, QPalette, QTextCursor
from PyQt6.QtWidgets import (
    QDialog, QHBoxLayout, QPushButton, QTextBrowser, QVBoxLayout, QWidget,
)

from src import guide
from src.branding import APP_NAME
from src.ui_style import WINDOW_STYLE

#: The app's pale green, for links: Qt's default blue is about 2:1 on the
#: page's dark ground.
_LINK = "#a5d6a7"

_PAGE = ("QTextBrowser { background: #16241a; color: #dcedc8; "
         "border: 1px solid #2e4a2e; border-radius: 6px; "
         "padding: 10px 14px; font-size: 14px; }")


class GuideWindow(QDialog):
    """The guide, one scrolling page and a Close button."""

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self.setWindowTitle(f"{APP_NAME}: How to Plan Your Yard")
        self.setModal(False)
        self.setStyleSheet(WINDOW_STYLE + _PAGE)
        self.resize(620, 640)

        lay = QVBoxLayout(self)
        lay.setContentsMargins(12, 12, 12, 10)
        lay.setSpacing(8)

        self.page = QTextBrowser(self)
        self.page.setOpenExternalLinks(True)
        palette = self.page.palette()
        palette.setColor(QPalette.ColorRole.Link, QColor(_LINK))
        self.page.setPalette(palette)
        self.page.setMarkdown(guide.guide_text())
        _space_headings(self.page.document())
        self.page.setAccessibleName("How to plan your yard")
        lay.addWidget(self.page, 1)

        row = QHBoxLayout()
        row.addStretch()
        close = QPushButton("Close", self)
        close.setAccessibleName("Close the guide")
        close.clicked.connect(self.close)
        row.addWidget(close)
        lay.addLayout(row)


def _space_headings(document) -> None:
    """Room above each section heading. Markdown import leaves a heading
    tight against the paragraph before it, and a document's default style
    sheet does not reach text set as Markdown."""
    block = document.begin()
    while block.isValid():
        fmt = block.blockFormat()
        if fmt.headingLevel() > 1:
            fmt.setTopMargin(16)
            fmt.setBottomMargin(4)
            QTextCursor(block).setBlockFormat(fmt)
        block = block.next()


def open_guide(main) -> GuideWindow:
    """Show (or raise) the guide over ``main``. One window per main window."""
    win = getattr(main, "_guide_window", None)
    if win is None:
        win = GuideWindow(main)
        main._guide_window = win
    win.show()
    win.raise_()
    win.activateWindow()
    return win
