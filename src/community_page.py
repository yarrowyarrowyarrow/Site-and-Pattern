"""
community_page.py — a plant community's page, beside the list (F206, V3.09).

Design principle P10 — see docs/DESIGN_PHILOSOPHY.md.

The owner, keeping Plant Communities: "I quite like the way the 'plants' now
show up in an adjacent 'pop up' and would like the same for plant communities
for ease of scrolling, visibility and use. Selecting a plant community can show
the pictures of the plants in the community in the pop up (not too big as I
want it to be mostly all visible in one go) along with the description of the
community and the ability to drop down into individual descriptions of the
plants."

It shares the plant page's frame over the map's right edge
(``src/species_flyout.py``): the community's name and its facts, Place, its
members as small photographs three across, then its description (the pattern
card the panel writes). A member's photograph opens that plant's page in the
same frame, with the way back above it. The panel's own card is left as it was
until the owner has used this one (the plan's T9).
"""

from __future__ import annotations

from typing import Callable, Optional

from PyQt6.QtCore import QSize, Qt, pyqtSignal
from PyQt6.QtGui import QColor, QIcon, QPixmap
from PyQt6.QtWidgets import (
    QFrame, QGridLayout, QHBoxLayout, QLabel, QPushButton, QScrollArea,
    QToolButton, QVBoxLayout, QWidget,
)

#: A member's photograph: small, so most communities fit on one screen.
TILE = QSize(96, 64)
COLUMNS = 3

_HEAD = "color: #e8f5e9; font-size: 16px; font-weight: bold;"
_DIM = "color: #90a4ae; font-size: 12px;"
_SECTION = ("color: #a5d6a7; font-size: 13px; font-weight: bold; "
            "padding: 6px 0 2px 0;")
_TILE_STYLE = (
    "QToolButton { color: #c8e6c9; background: transparent; font-size: 12px; "
    "border: 1px solid #2e4a2e; border-radius: 4px; padding: 2px; }"
    "QToolButton:hover { border-color: #66bb6a; }"
    "QToolButton:focus { border: 2px solid #ffe082; }")


class CommunityPage(QWidget):
    """One community. ``show_community(polyculture)`` fills it from
    ``polycultures.get_polyculture_by_id``'s dict."""

    #: The ✕, or Esc while the page has focus.
    close_requested = pyqtSignal()
    #: Place this community (its id).
    place_requested = pyqtSignal(int)
    #: Open a member's page: ``{"id": plant_id}``.
    member_requested = pyqtSignal(dict)
    #: A related community named in the description (its id).
    community_requested = pyqtSignal(int)

    def __init__(self, parent=None, *,
                 photo_warmer: Optional[Callable] = None,
                 plant_fn: Optional[Callable] = None):
        super().__init__(parent)
        self.setObjectName("communityPage")
        self._photo_warmer = photo_warmer
        self._plant_fn = plant_fn
        self._community: dict = {}
        self._tiles: dict = {}          # plant id -> its QToolButton

        outer = QVBoxLayout(self)
        outer.setContentsMargins(14, 10, 10, 8)
        outer.setSpacing(6)

        head = QHBoxLayout()
        names = QVBoxLayout()
        names.setSpacing(2)
        self._name = QLabel("")
        self._name.setStyleSheet(_HEAD)
        self._name.setWordWrap(True)
        self._name.setTextInteractionFlags(
            Qt.TextInteractionFlag.TextSelectableByMouse)
        names.addWidget(self._name)
        self._facts = QLabel("")
        self._facts.setStyleSheet(_DIM)
        self._facts.setWordWrap(True)
        names.addWidget(self._facts)
        head.addLayout(names, 1)
        self._close = QToolButton()
        self._close.setText("✕")
        self._close.setAccessibleName("Close the community page")
        self._close.setToolTip("Close (Esc)")
        self._close.setFixedSize(28, 28)
        self._close.setStyleSheet(
            "QToolButton { color: #c8e6c9; background: transparent; "
            "border: 1px solid #2e4a2e; border-radius: 4px; font-size: 14px; }"
            "QToolButton:hover { border-color: #66bb6a; }"
            "QToolButton:focus { border: 2px solid #ffe082; }")
        self._close.clicked.connect(self.close_requested)
        head.addWidget(self._close, 0, Qt.AlignmentFlag.AlignTop)
        outer.addLayout(head)

        from src.ui_style import BTN_PRIMARY
        self._place = QPushButton("Place this community")
        self._place.setObjectName("placeButton")
        self._place.setStyleSheet(BTN_PRIMARY)
        self._place.clicked.connect(
            lambda: self.shown_id() is not None
            and self.place_requested.emit(self.shown_id()))
        outer.addWidget(self._place)

        self._scroll = QScrollArea()
        self._scroll.setWidgetResizable(True)
        self._scroll.setFrameShape(QFrame.Shape.NoFrame)
        self._scroll.setAccessibleName("Community page")
        body = QWidget()
        self._scroll.setWidget(body)
        col = QVBoxLayout(body)
        col.setContentsMargins(0, 0, 4, 0)
        col.setSpacing(4)
        self._members_head = QLabel("The plants")
        self._members_head.setStyleSheet(_SECTION)
        col.addWidget(self._members_head)
        grid_holder = QWidget()
        self._grid = QGridLayout(grid_holder)
        self._grid.setContentsMargins(0, 0, 0, 0)
        self._grid.setSpacing(4)
        col.addWidget(grid_holder)
        about = QLabel("About this community")
        about.setStyleSheet(_SECTION)
        col.addWidget(about)
        self._about = QLabel("")
        self._about.setWordWrap(True)
        self._about.setTextFormat(Qt.TextFormat.RichText)
        self._about.setStyleSheet("color: #c8e6c9; font-size: 12px;")
        self._about.setTextInteractionFlags(
            Qt.TextInteractionFlag.TextBrowserInteraction)
        self._about.setOpenExternalLinks(False)
        self._about.linkActivated.connect(self._on_link)
        col.addWidget(self._about)
        col.addStretch()
        outer.addWidget(self._scroll, 1)

    # ── Filling it ───────────────────────────────────────────────────────────

    def shown_id(self) -> Optional[int]:
        cid = self._community.get("id")
        return int(cid) if cid is not None else None

    def members(self) -> list:
        return list(self._community.get("members") or [])

    def show_community(self, polyculture: dict, *, facts: str = "") -> None:
        """Fill the page for ``polyculture``; ``facts`` is its one line
        ("8 plants · Full Sun · Mesic"), worked out from it when not given."""
        self._community = dict(polyculture or {})
        name = self._community.get("name") or ""
        self._name.setText(name)
        self.setAccessibleName(f"About {name}")
        self._facts.setText(facts or _facts_for(self._community))
        self._render_tiles()
        self._about.setText(_description_html(self._community))
        self._scroll.verticalScrollBar().setValue(0)

    def refresh_photo(self, plant_id: int) -> None:
        """A photograph finished downloading: draw it if it is a member's."""
        btn = self._tiles.get(int(plant_id))
        if btn is not None:
            btn.setIcon(QIcon(self._tile_pixmap(int(plant_id))))

    def keyPressEvent(self, event):                       # noqa: N802
        if event.key() == Qt.Key.Key_Escape:
            self.close_requested.emit()
            event.accept()
            return
        super().keyPressEvent(event)

    def _render_tiles(self) -> None:
        while self._grid.count():
            item = self._grid.takeAt(0)
            w = item.widget()
            if w is not None:
                w.setParent(None)
                w.deleteLater()
        self._tiles = {}
        seen = []
        for m in self.members():
            pid = m.get("plant_id")
            if pid is None or int(pid) in self._tiles:
                continue        # a community lists a species once per spot
            pid = int(pid)
            btn = QToolButton()
            btn.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextUnderIcon)
            btn.setIconSize(TILE)
            btn.setIcon(QIcon(self._tile_pixmap(pid, m)))
            name = m.get("common_name") or f"Plant #{pid}"
            btn.setText(btn.fontMetrics().elidedText(
                name, Qt.TextElideMode.ElideRight, TILE.width()))
            btn.setAccessibleName(name)
            btn.setToolTip(f"{name}: open its page")
            btn.setStyleSheet(_TILE_STYLE)
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.clicked.connect(
                lambda _c=False, p=pid: self.member_requested.emit({"id": p}))
            self._grid.addWidget(btn, len(seen) // COLUMNS, len(seen) % COLUMNS)
            self._tiles[pid] = btn
            seen.append(pid)
        n = len(seen)
        self._members_head.setText(
            f"The plants ({n} species)" if n else "No plants in it yet")

    def _plant(self, plant_id: int) -> dict:
        fn = self._plant_fn
        if fn is None:
            from src.db.plants import get_plant as fn
        try:
            return fn(plant_id) or {}
        except Exception:                                  # noqa: BLE001
            return {}

    def _tile_pixmap(self, plant_id: int, member: Optional[dict] = None
                     ) -> QPixmap:
        """The plant's photograph cropped to a tile, or, until one is cached,
        its type's colour (and the photograph asked for)."""
        plant = self._plant(plant_id)
        url = plant.get("image_url") or ""
        path = None
        if url:
            try:
                from src.image_cache import get_cached_image
                path = get_cached_image(url)
            except Exception:                              # noqa: BLE001
                path = None
        pix = QPixmap(path) if path else QPixmap()
        if not pix.isNull():
            scaled = pix.scaled(TILE, Qt.AspectRatioMode.KeepAspectRatioByExpanding,
                                Qt.TransformationMode.SmoothTransformation)
            x = max(0, (scaled.width() - TILE.width()) // 2)
            y = max(0, (scaled.height() - TILE.height()) // 2)
            return scaled.copy(x, y, TILE.width(), TILE.height())
        if url and self._photo_warmer is not None:
            try:
                self._photo_warmer(plant)
            except Exception:                              # noqa: BLE001
                pass
        from src.member_colors import plant_color
        swatch = QPixmap(TILE)
        swatch.fill(QColor(plant_color({**(member or {}), **plant})))
        return swatch

    def _on_link(self, href: str) -> None:
        if href.startswith("community:"):
            try:
                self.community_requested.emit(int(href.split(":", 1)[1]))
            except ValueError:
                pass


def _facts_for(polyculture: dict) -> str:
    """The list row's line for this community (F196), from the library index
    that row is drawn from; the plant count alone when that cannot be read."""
    from src.polyculture_panel import community_facts
    try:
        from src.db import polycultures
        entry = polycultures.get_library_index().get(polyculture.get("id"))
    except Exception:                                      # noqa: BLE001
        entry = None
    if entry is None:
        entry = {"member_count": len(polyculture.get("members") or [])}
    return community_facts(entry)


def _description_html(polyculture: dict) -> str:
    """The pattern card the panel writes (F4), or the bare description."""
    try:
        from src import pattern_language
        from src.db import polycultures
        pattern = pattern_language.build_pattern(
            polyculture,
            all_communities=polycultures.get_all_polycultures(
                top_level_only=False))
        return pattern_language.pattern_card_html(pattern, include_header=False)
    except Exception:                                      # noqa: BLE001
        return polyculture.get("description") or ""
