"""
species_flyout.py — a plant's page beside the side panel, over the map's right
edge (F192, V3.00).

Design principle P5 — see docs/DESIGN_PHILOSOPHY.md.

Where the page goes was the one real choice in this step. Under the list, it
shares a 437 px column with the search box, the filters and the list, which is
how the painted card it replaces ended up filling the list on its own. In place
of the list, it is roomy, and the list is gone while you read, so comparing two
plants means going back and forth. **Beside the list** the list stays where it
is, the arrow keys step through it and the page follows, and the map it covers
is not in use while you are reading: placing closes the page (the panel's
``_announce_armed``), and no page opens while the map is placing.

It is the map's sibling in the map's column, positioned over the map's right
edge, like the placement bar over its top: ``QWebEngineView``'s accessible
interface reports only the web page, so a child of the view would be invisible
to a screen reader (measured in V2.98).

``install`` is a free function, as ``placement_bar_flow.install`` is, so the
page costs MainWindow no methods (their number is guarded).
"""

from __future__ import annotations

from PyQt6.QtCore import QEvent, QPoint, Qt, QTimer
from PyQt6.QtWidgets import QFrame, QVBoxLayout, QWidget

from src.species_page import SpeciesPage

_INSET = 8
_MIN_WIDTH = 300
_MAX_WIDTH = 420
#: Of the map's width, at most: the yard should still show beside the page.
_SHARE = 0.45

_WATCHED = (QEvent.Type.Resize, QEvent.Type.Move, QEvent.Type.Show,
            QEvent.Type.LayoutRequest)


class SpeciesFlyout(QFrame):
    """A :class:`SpeciesPage` in a frame over the right edge of ``anchor``."""

    def __init__(self, parent: QWidget, anchor: QWidget, *,
                 photo_warmer=None):
        super().__init__(parent)
        self.setObjectName("speciesFlyout")
        self.setAccessibleName("Plant page")
        self.setStyleSheet(
            "QFrame#speciesFlyout { background-color: #1a2a1a; "
            "border: 1px solid #3a5a3a; border-radius: 6px; }"
            "QFrame#speciesFlyout QWidget { background-color: #1a2a1a; "
            "color: #c8e6c9; }")
        self._anchor = anchor
        col = QVBoxLayout(self)
        col.setContentsMargins(1, 1, 1, 1)
        self.page = SpeciesPage(self, actions=True, closable=True,
                                photo_warmer=photo_warmer)
        col.addWidget(self.page)
        self.hide()
        anchor.installEventFilter(self)
        parent.installEventFilter(self)

    def show_plant(self, row: dict, *, placed: int = 0, in_mix: bool = False,
                   focus: bool = False):
        self.page.show_plant(row, placed=placed, in_mix=in_mix)
        self.show()
        self.refit()
        if focus:
            # The first thing to do on the page, which is also where Tab
            # continues from.
            target = self.page.findChild(QWidget, "placeButton") or self.page
            target.setFocus(Qt.FocusReason.OtherFocusReason)

    def refit(self) -> None:
        """Sit against the map's right edge, as tall as the map, at most
        :data:`_SHARE` of its width."""
        if not self.isVisible():
            return
        anchor, parent = self._anchor, self.parentWidget()
        try:
            origin = anchor.mapTo(parent, QPoint(0, 0))
        except (RuntimeError, TypeError):
            return                   # the map left this column (app teardown)
        width = max(_MIN_WIDTH, min(_MAX_WIDTH, int(anchor.width() * _SHARE)))
        width = max(120, min(width, anchor.width() - 2 * _INSET))
        height = max(160, anchor.height() - 2 * _INSET)
        self.setGeometry(origin.x() + anchor.width() - width - _INSET,
                         origin.y() + _INSET, width, height)
        self.raise_()

    def eventFilter(self, obj, event):
        if event.type() in _WATCHED and self.isVisible():
            QTimer.singleShot(0, self.refit)
        return False


def install(main) -> None:
    """Build the page over the map and wire it to the Browse tab."""
    holder = main.map_widget.parentWidget()
    panel = main.plant_panel
    fly = SpeciesFlyout(holder, anchor=main.map_widget,
                        photo_warmer=panel.picker.model.warm_photo)
    main.species_flyout = fly
    panel.page_requested.connect(lambda info: _on_page_requested(main, info))
    panel.page_closed.connect(fly.hide)
    fly.page.close_requested.connect(lambda: _on_close(main))
    fly.page.place_requested.connect(panel.place_from_elsewhere)
    fly.page.mix_requested.connect(panel.add_to_mix)
    # The list fetches photos on a worker thread; the page asked for this one.
    panel.picker.model.imageReady.connect(fly.page.refresh_photo)


def _on_page_requested(main, info: dict) -> None:
    fly = getattr(main, "species_flyout", None)
    if fly is None:
        return
    fly.show_plant(info.get("plant") or {}, placed=int(info.get("placed") or 0),
                   in_mix=bool(info.get("in_mix")),
                   focus=bool(info.get("focus")))


def _on_close(main) -> None:
    """The ✕ or Esc on the page: put it away, and the keyboard back in the
    list it was opened from."""
    from PyQt6.QtWidgets import QApplication
    fly = getattr(main, "species_flyout", None)
    focused = QApplication.focusWidget()
    had_focus = (fly is not None and focused is not None
                 and fly.isAncestorOf(focused))
    main.plant_panel.close_page()
    if fly is not None:
        fly.hide()
    if had_focus:
        main.plant_panel.focus_list()
