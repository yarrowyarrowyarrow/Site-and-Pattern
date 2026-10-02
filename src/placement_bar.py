"""
placement_bar.py — the bar over the map while you place (F193, V2.98).

While the map is armed to place a plant, a mix or a community, this bar floats
over the map's top edge. Its first line says what the next click will do, in
words ("Placing Wild Bergamot in a row. Click the start point, then the end
point."), with a Done button; its second holds the settings of that pattern,
which lived in a collapsible "Placement" section of the side panel until V2.98.
That section shared a column that does not scroll with the list you browse, so
opening it took the list's height and, on a 1366 × 768 laptop, squeezed the
pattern buttons to nothing. Here they have the map's width and only exist while
they mean something.

**Over the map, not above it.** A strip in the column (where the getting-started
bar lives) would push the map down whenever placing starts, and Leaflet
re-centres on a resize, so the drawing would jump at the moment you aim a click.
Floating costs a strip of map instead, inset past the zoom buttons.

**A sibling of the map, not its child.** Qt's accessible interface for
``QWebEngineView`` reports the web page as its only child, so a widget parented
to the map view is absent from the accessibility tree: measured, 0 of 440 lines
of an AT-SPI dump, where the same label parented to the map's column appears by
name. So the bar is a child of the map's column and follows the map widget's
geometry, which also keeps it over the map in split view.

Presentation only: what to say comes from :func:`src.placement_arming.describe`,
and when to show it from :mod:`src.placement_bar_flow`.
"""

from __future__ import annotations

import html

from PyQt6.QtCore import QEvent, QPoint, Qt, QTimer, pyqtSignal
from PyQt6.QtWidgets import (
    QFrame, QHBoxLayout, QLabel, QPushButton, QVBoxLayout, QWidget,
)

# Where the bar sits on the map: clear of Leaflet's zoom buttons on the left,
# a little off the top edge, and no wider than a comfortable reading line.
_INSET_LEFT = 56
_INSET_RIGHT = 12
_INSET_TOP = 8
_MAX_WIDTH = 980

# Amber edge: an armed map is a *state*, not an action (the V2.37 chip's
# reasoning), and green is this app's "do the thing" colour. Text is 13 px and
# every pair clears 4.5:1 against its background; every control shows keyboard
# focus, and targets are at least 24 px tall — the review's baseline, applied to
# the one surface this increment builds.
_STYLE = """
#placementBar {
    background-color: #13241a;
    border: 1px solid #ffb300;
    border-radius: 6px;
}
#placementBar QWidget { background-color: transparent; }
#placementBar QLabel { color: #e8f5e9; font-size: 13px; border: none; }
#placementBar QLabel#placementStatus { color: #fff3c4; }
#placementBar QLabel#placementNote { color: #ffe0b2; font-size: 13px; }
#placementBar QFrame#placementDot {
    background-color: #ffb300; border: none; border-radius: 5px;
}
#placementBar QPushButton {
    background-color: #1e2e1e; color: #e8f5e9;
    border: 1px solid #4a6a4a; border-radius: 4px;
    padding: 2px 10px; font-size: 13px; min-height: 24px;
}
#placementBar QPushButton:hover { background-color: #26402a; border-color: #81c784; }
#placementBar QPushButton:checked {
    background-color: #1b5e20; color: #ffffff; border-color: #81c784;
    font-weight: bold;
}
#placementBar QPushButton:focus { border: 2px solid #ffe082; }
#placementBar QPushButton#placementDone {
    background-color: #37474f; color: #eceff1; border-color: #90a4ae;
}
#placementBar QPushButton#placementDone:hover { background-color: #455a64; }
#placementBar QPushButton#placementDone:focus { border: 2px solid #ffe082; }
#placementBar QCheckBox {
    color: #e8f5e9; font-size: 13px; min-height: 24px;
    padding: 0 3px; border: 1px solid transparent; border-radius: 3px;
}
#placementBar QCheckBox:focus { border: 1px solid #ffe082; }
#placementBar QCheckBox::indicator {
    width: 16px; height: 16px; border: 1px solid #81c784; border-radius: 3px;
    background-color: #0e1a11;
}
#placementBar QCheckBox::indicator:hover { border-color: #c8e6c9; }
#placementBar QCheckBox::indicator:checked {
    background-color: #81c784; image: url(@CHECK@);
}
#placementBar QSpinBox, #placementBar QDoubleSpinBox {
    background-color: #0e1a11; color: #e8f5e9;
    border: 1px solid #4a6a4a; border-radius: 3px;
    padding: 1px 22px 1px 5px; font-size: 13px; min-height: 24px;
}
#placementBar QSpinBox:focus, #placementBar QDoubleSpinBox:focus {
    border: 2px solid #ffe082;
}
#placementBar QSpinBox::up-button, #placementBar QDoubleSpinBox::up-button {
    subcontrol-origin: border; subcontrol-position: top right;
    width: 20px; border-left: 1px solid #4a6a4a; background-color: #243824;
}
#placementBar QSpinBox::down-button, #placementBar QDoubleSpinBox::down-button {
    subcontrol-origin: border; subcontrol-position: bottom right;
    width: 20px; border-left: 1px solid #4a6a4a; background-color: #243824;
}
#placementBar QSpinBox::up-button:hover, #placementBar QDoubleSpinBox::up-button:hover,
#placementBar QSpinBox::down-button:hover, #placementBar QDoubleSpinBox::down-button:hover {
    background-color: #2e5a2e;
}
#placementBar QSpinBox::up-arrow, #placementBar QDoubleSpinBox::up-arrow {
    image: url(@UP@); width: 10px; height: 6px;
}
#placementBar QSpinBox::down-arrow, #placementBar QDoubleSpinBox::down-arrow {
    image: url(@DOWN@); width: 10px; height: 6px;
}
"""


def _style() -> str:
    """The style sheet with its images resolved. Qt draws a styled spin box's
    arrows and a styled check box's tick only from an image (the CSS
    border-triangle trick draws a grey block, which is what the side panel's
    spin boxes still show), so three small SVGs ship in html/assets/ui, which
    the installers already bundle. Forward slashes: Qt's url() reads them on
    every platform."""
    from src.resources import resource_path
    def _asset(name):
        return resource_path("html", "assets", "ui", name).replace("\\", "/")
    return (_STYLE.replace("@UP@", _asset("spin-up.svg"))
            .replace("@DOWN@", _asset("spin-down.svg"))
            .replace("@CHECK@", _asset("check.svg")))


_WATCHED = (QEvent.Type.Resize, QEvent.Type.Move, QEvent.Type.Show,
            QEvent.Type.ParentChange)


class PlacementBar(QFrame):
    """Status line + Done, over one page of controls per source."""

    #: Done was pressed. The flow routes it to MainWindow._cancel_draw, the one
    #: cancel path, exactly as Esc does.
    done_requested = pyqtSignal()
    #: Undo beside the note on where the last placement landed (F198).
    undo_requested = pyqtSignal()

    def __init__(self, parent: QWidget, anchor: QWidget):
        super().__init__(parent)
        self.setObjectName("placementBar")
        self.setAccessibleName("Placement")
        self.setStyleSheet(_style())
        self._anchor = anchor
        self._source = ""
        self._pages: dict[str, QWidget] = {}

        outer = QVBoxLayout(self)
        outer.setContentsMargins(12, 8, 10, 8)
        outer.setSpacing(6)

        top = QHBoxLayout()
        top.setSpacing(8)
        dot = QFrame()
        dot.setObjectName("placementDot")
        dot.setFixedSize(10, 10)
        top.addWidget(dot, 0, Qt.AlignmentFlag.AlignVCenter)
        self._status = QLabel("")
        self._status.setObjectName("placementStatus")
        self._status.setTextFormat(Qt.TextFormat.RichText)
        self._status.setWordWrap(True)
        top.addWidget(self._status, 1)
        # Each source may put one control on this line, beside the sentence
        # that names what it applies to (the Plants tab's marker colour).
        self._accessories: dict[str, QWidget] = {}
        self._top = top
        self._done = QPushButton("Done")
        self._done.setObjectName("placementDone")
        self._done.setAccessibleName("Done placing")
        self._done.setToolTip("Stop placing (Esc)")
        self._done.setCursor(Qt.CursorShape.PointingHandCursor)
        self._done.clicked.connect(self.done_requested)
        top.addWidget(self._done, 0, Qt.AlignmentFlag.AlignTop)
        outer.addLayout(top)

        # Where the last placement landed (F198, V3.05): outside the boundary,
        # inside another plant's circle. Says so and offers Undo; never refuses,
        # because a groundcover under a shrub is often the design.
        self._note_row = QWidget()
        note_line = QHBoxLayout(self._note_row)
        note_line.setContentsMargins(18, 0, 0, 0)
        note_line.setSpacing(8)
        self._note = QLabel("")
        self._note.setObjectName("placementNote")
        self._note.setWordWrap(True)
        note_line.addWidget(self._note, 1)
        self._undo = QPushButton("Undo")
        self._undo.setObjectName("placementUndo")
        self._undo.setAccessibleName("Undo that placement")
        self._undo.setToolTip("Take the last placement back (Ctrl+Z)")
        self._undo.setCursor(Qt.CursorShape.PointingHandCursor)
        self._undo.clicked.connect(self.undo_requested)
        note_line.addWidget(self._undo, 0, Qt.AlignmentFlag.AlignTop)
        self._note_row.setVisible(False)
        outer.addWidget(self._note_row)

        self._pages_holder = QWidget()
        self._pages_layout = QVBoxLayout(self._pages_holder)
        self._pages_layout.setContentsMargins(0, 0, 0, 0)
        self._pages_layout.setSpacing(0)
        outer.addWidget(self._pages_holder)

        self.hide()
        anchor.installEventFilter(self)
        parent.installEventFilter(self)

    # ── Content ──────────────────────────────────────────────────────────────

    @property
    def source(self) -> str:
        """Which panel's page is showing ('' when hidden)."""
        return self._source

    def add_page(self, source: str, page: QWidget,
                 accessory: QWidget | None = None) -> None:
        """Adopt ``page`` (a panel's placement controls) as ``source``'s page,
        and ``accessory``, if given, for the first line. The bar shows or hides
        the accessory's holder with the page; the panel still decides whether
        the accessory itself is shown (the colour hides while a mix is placed).
        """
        self._pages[source] = page
        self._pages_layout.addWidget(page)
        page.setVisible(False)
        if accessory is not None:
            holder = QWidget()
            row = QHBoxLayout(holder)
            row.setContentsMargins(0, 0, 0, 0)
            row.addWidget(accessory)
            holder.setVisible(False)
            self._top.insertWidget(self._top.indexOf(self._done), holder)
            self._accessories[source] = holder

    def status_text(self) -> str:
        """The first line as plain text (what a screen reader is given)."""
        return self._status.accessibleName()

    def show_page(self, source: str, headline: str, instruction: str) -> None:
        """Show ``source``'s controls under the sentence, and the bar."""
        for key, page in self._pages.items():
            page.setVisible(key == source)
        for key, holder in self._accessories.items():
            holder.setVisible(key == source)
        self._source = source
        plain = f"{headline}. {instruction}"
        self._status.setText(
            f"<b>{html.escape(headline)}.</b>&nbsp; {html.escape(instruction)}")
        self._status.setAccessibleName(plain)
        self.setAccessibleDescription(plain)
        self.show()
        self.refit()

    def show_note(self, text: str) -> None:
        """Say where the last placement landed, with Undo; ``""`` clears."""
        self._note.setText(text)
        self._note.setAccessibleName(text)
        self._note_row.setVisible(bool(text))
        if text:
            self.setAccessibleDescription(
                f"{self._status.accessibleName()} {text}")
        self.refit()

    def note_text(self) -> str:
        return self._note.text() if self._note_row.isVisibleTo(self) else ""

    def hide_bar(self) -> None:
        self._source = ""
        self.show_note("")
        self.hide()

    # ── Geometry ─────────────────────────────────────────────────────────────

    def refit(self) -> None:
        """Sit over the top of the anchor (the map), inset past its zoom
        buttons, as tall as the content needs at that width."""
        if not self.isVisible():
            return
        anchor, parent = self._anchor, self.parentWidget()
        try:
            origin = anchor.mapTo(parent, QPoint(0, 0))
        except (RuntimeError, TypeError):
            return                   # the map left this column (app teardown)
        left = origin.x() + _INSET_LEFT
        avail = max(240, anchor.width() - _INSET_LEFT - _INSET_RIGHT)
        width = min(avail, _MAX_WIDTH)
        height = self.heightForWidth(width)
        if height <= 0:
            height = self.sizeHint().height()
        self.setGeometry(left + (avail - width) // 2, origin.y() + _INSET_TOP,
                         width, height)
        self.raise_()

    def eventFilter(self, obj, event):
        if event.type() in _WATCHED and self.isVisible():
            QTimer.singleShot(0, self.refit)
        return False

    def event(self, event):
        # A page's content changed (another pattern's settings, a longer
        # sentence): the bar sizes itself by hand, so it has to re-measure.
        if event.type() == QEvent.Type.LayoutRequest and self.isVisible():
            QTimer.singleShot(0, self.refit)
        return super().event(event)
