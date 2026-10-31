"""
community_flyout.py — a community's page in the plant page's frame (F206, V3.09).

Design principle P10 — see docs/DESIGN_PHILOSOPHY.md.

The frame over the map's right edge (``src/species_flyout.py``) shows a plant's
page; :class:`CommunityFlyout` lets it show a community's
(``src/community_page.py``) too, and a member's plant page opened from it with
the way back above. It opens as a plant's does: a finished click or an arrow
onto a community in Placement › Communities, not while the map is placing (the
list is a palette then, V2.99), and placing closes it.

Its own module because the plant frame sits under a 200-line ceiling, and so
the community's half of the frame can grow (the plan's T9) without touching
the plant's.
"""

from __future__ import annotations

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QApplication, QPushButton

from src.community_page import CommunityPage
from src.species_flyout import SpeciesFlyout


class CommunityFlyout(SpeciesFlyout):
    """The plant frame, able to show a community and drop into its members."""

    def __init__(self, parent, anchor, *, photo_warmer=None):
        super().__init__(parent, anchor, photo_warmer=photo_warmer)
        col = self.layout()
        # The way back to the community a member's page was opened from.
        self._back = QPushButton("◀ Back")
        self._back.setObjectName("communityBack")
        # A link back, at the page's left edge, not a second toolbar (V3.11).
        self._back.setStyleSheet(
            "QPushButton { text-align: left; padding: 6px 14px; "
            "color: #a5d6a7; background: transparent; border: none; "
            "border-bottom: 1px solid #2e4a2e; font-size: 13px; }"
            "QPushButton:hover { color: #e8f5e9; }"
            "QPushButton:focus { border: 2px solid #ffe082; }")
        self._back.setCursor(Qt.CursorShape.PointingHandCursor)
        self._back.clicked.connect(self.back_to_community)
        self._back.hide()
        col.insertWidget(0, self._back)
        self.community = CommunityPage(self, photo_warmer=photo_warmer)
        self.community.hide()
        col.addWidget(self.community)
        self.community.member_requested.connect(self._open_member)
        self.community.community_requested.connect(self._open_related)
        #: How many of a plant are in the design (set by :func:`wire`).
        self.placed_of = lambda _pid: 0

    def show_plant(self, row: dict, *, from_community: bool = False, **kw):
        """A plant's page; ``from_community`` when a member was clicked, which
        puts the way back above it."""
        self.community.hide()
        self.page.show()
        name = self.community._community.get("name") or "the community"
        self._back.setText(f"◀ Back to {name}")
        self._back.setVisible(from_community)
        super().show_plant(row, **kw)

    def show_community(self, polyculture: dict, *, focus: bool = False):
        """A community's page in place of a plant's."""
        self.community.show_community(polyculture)
        self.page.hide()
        self._back.hide()
        self.community.show()
        self.show()
        self.refit()
        if focus:
            self.community.setFocus(Qt.FocusReason.OtherFocusReason)

    def showing_community(self) -> bool:
        """Whether the community's page, or a member's opened from it, is up
        (asked of the frame, so it holds before the window is on screen)."""
        return not self.isHidden() and (not self.community.isHidden()
                                         or not self._back.isHidden())

    def back_to_community(self) -> None:
        self._back.hide()
        self.page.hide()
        self.community.show()

    def _open_member(self, info: dict) -> None:
        pid = int(info.get("id") or 0)
        self.show_plant({"id": pid}, placed=self.placed_of(pid),
                        from_community=True)

    def _open_related(self, polyculture_id: int) -> None:
        from src.db import polycultures
        row = polycultures.get_polyculture_by_id(int(polyculture_id))
        if row:
            self.show_community(row)


def wire(main, fly: CommunityFlyout) -> None:
    """Connect the community list and the page (from ``species_flyout.install``,
    so the page costs MainWindow no methods)."""
    communities = main.polyculture_panel
    communities.set_details_in_page(True)
    communities.page_requested.connect(
        lambda cid: _on_community_requested(main, cid))
    communities.armedChanged.connect(
        lambda info: (info or {}).get("armed") and fly.showing_community()
        and fly.hide())
    fly.community.close_requested.connect(lambda: _on_close(main))
    fly.community.place_requested.connect(communities.place_by_id)
    main.plant_panel.picker.model.imageReady.connect(fly.community.refresh_photo)
    fly.placed_of = lambda pid: sum(
        1 for p in (getattr(main, "_placed_plants", None) or [])
        if p.get("plant_id") == pid)


def _on_community_requested(main, polyculture_id: int) -> None:
    from src.db import polycultures
    from src.placement_bar_flow import PLACING_MODES
    fly = getattr(main, "species_flyout", None)
    if fly is None or getattr(main, "_current_mode", "none") in PLACING_MODES:
        return
    row = polycultures.get_polyculture_by_id(int(polyculture_id))
    if row:
        fly.show_community(row)


def _on_close(main) -> None:
    """The ✕ or Esc: put the page away, and the keyboard back in the list if
    it was on the page."""
    fly = getattr(main, "species_flyout", None)
    if fly is None:
        return
    focused = QApplication.focusWidget()
    had_focus = focused is not None and fly.isAncestorOf(focused)
    fly.hide()
    if had_focus:
        main.polyculture_panel.focus_list()
