"""
plant_panel.py — Right-side panel: plant browser, search, filters, detail view,
place-on-map, and placed-plants list.
"""

from __future__ import annotations

from typing import Optional

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit,
    QComboBox, QListWidget, QListWidgetItem, QFrame,
    QPushButton, QSizePolicy, QScrollArea, QSplitter,
    QFormLayout, QGroupBox,
    QSpinBox, QDoubleSpinBox,
    QColorDialog, QMenu,
)
from PyQt6.QtCore import (
    Qt, QTimer, QThread, pyqtSignal, QSize, QAbstractListModel,
    QModelIndex, QRect, QEvent, QSettings,
)
from PyQt6.QtGui import (
    QColor, QIcon, QPixmap, QPainter, QFont, QBrush, QPen, QPalette,
    QFontMetrics,
)
from PyQt6.QtWidgets import (
    QStyledItemDelegate, QStyle, QStyleOptionViewItem, QListView,
)

# ── Type colours ──────────────────────────────────────────────────────────────
_TYPE_COLORS: dict[str, str] = {
    "tree":        "#2e7d32",
    "shrub":       "#558b2f",
    "herb":        "#7cb342",
    "groundcover": "#c6a817",
    "vine":        "#00838f",
    "root":        "#6d4c41",
}

_TYPE_LABELS: dict[str, str] = {
    "tree":        "Tree",
    "shrub":       "Shrub",
    "herb":        "Herb / Perennial",
    "groundcover": "Groundcover",
    "vine":        "Vine",
    "root":        "Root / Bulb",
}

_SUN_LABELS: dict[str, str] = {
    "full_sun":      "Full Sun",
    "partial_shade": "Partial Shade",
    "full_shade":    "Full Shade",
}

_WATER_LABELS: dict[str, str] = {
    "low":    "Low",
    "medium": "Medium",
    "high":   "High",
}

_DECIDUOUS_LABELS: dict[str, str] = {
    "deciduous":  "Deciduous",
    "evergreen":  "Evergreen",
    "herbaceous": "Herbaceous (dies back)",
}

_LIFECYCLE_LABELS: dict[str, str] = {
    "perennial": "Perennial",
    "annual":    "Annual",
    "biennial":  "Biennial",
}

# V1.37: vocabulary refined toward "native habitat" + "functional
# landscape design" framing. Dropped permaculture-flavored tags
# (biomass = chop-and-drop, pest_deterrent = companion-planting,
# food_forest, edible_landscape). Renamed a few labels for clarity:
# host_plant → "Larval Host" (clearer for the audience),
# pollinator → "Pollinator Support",
# early_successional → "Pioneer Species",
# water_purification → "Riparian Filter".
# Promoted "overstory" (informal tag in data) to canonical
# "canopy_layer" so users can describe vertical structure.
_USE_LABELS: dict[str, str] = {
    # Wildlife / native habitat
    "keystone_species":   "Keystone Species",
    "host_plant":         "Larval Host",
    "pollinator":         "Pollinator Support",
    "bird_food":          "Bird Food",
    "nesting_material":   "Nesting Material",
    "wildlife_habitat":   "Wildlife Habitat",
    # Ecological function
    "nitrogen_fixer":     "Nitrogen Fixer",
    "soil_builder":       "Soil Builder",
    "early_successional": "Early Successional",
    # Functional landscape design
    "canopy_layer":       "Canopy Layer",
    "windbreak":          "Windbreak",
    "hedge":              "Hedge",
    "groundcover":        "Groundcover",
    "erosion_control":    "Erosion Control",
    "riparian_filter":    "Riparian Filter",
    "ornamental":         "Ornamental",
    "aquatic":            "Aquatic",
    "medicinal":          "Medicinal",
}


# ── Alberta ecoregion choices (Reference Ecosystem picker, N1) ────────────────
# Order matches the dropdown; the empty-string id is "any ecoregion" (no
# filter).  Keep the ids in sync with the comma-separated tags stored in
# plants.ab_ecoregion (see data/plants_master.json + src/db/plants.py
# heuristic tagging pass).
_AB_ECOREGION_CHOICES: list[tuple[str, str]] = [
    ("Any ecoregion",          ""),
    ("Aspen Parkland (central AB)", "aspen_parkland"),
    ("Mixedgrass Prairie (south AB)", "mixedgrass_prairie"),
    ("Fescue / Foothills (SW AB)",    "fescue_foothills"),
    ("Boreal Mixedwood (north AB)",   "boreal_mixedwood"),
    ("Riparian (streamside)",         "riparian"),
    ("Wet Meadow / Marsh",            "wet_meadow"),
    ("Subalpine / Montane (mountains)", "subalpine_montane"),
]


# ── Calendar status colours & labels ─────────────────────────────────────────
_CALENDAR_STATUS_COLORS: dict[str, str] = {
    "dormant":       "#37474f",   # dark grey
    "start_indoors": "#7b1fa2",   # purple
    "direct_sow":    "#00838f",   # teal
    "transplant":    "#1565c0",   # blue
    "growing":       "#2e7d32",   # green
    "harvest":       "#e65100",   # orange
    "pruning":       "#6d4c41",   # brown
}

_CALENDAR_STATUS_LABELS: dict[str, str] = {
    "dormant":       "Dormant",
    "start_indoors": "Start Indoors",
    "direct_sow":    "Direct Sow",
    "transplant":    "Transplant",
    "growing":       "Growing",
    "harvest":       "Harvest",
    "pruning":       "Pruning",
}

_MONTH_ABBR = ["Jan", "Feb", "Mar", "Apr", "May", "Jun",
               "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]


def _type_icon(plant_type: str) -> QIcon:
    """Return a small coloured circle icon for the given plant type."""
    color_hex = _TYPE_COLORS.get(plant_type, "#78909c")
    pix = QPixmap(14, 14)
    pix.fill(Qt.GlobalColor.transparent)
    p = QPainter(pix)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    p.setBrush(QBrush(QColor(color_hex)))
    p.setPen(Qt.PenStyle.NoPen)
    p.drawEllipse(1, 1, 12, 12)
    p.end()
    return QIcon(pix)


# ── Plant list item ───────────────────────────────────────────────────────────

_PLANT_ID_ROLE  = Qt.ItemDataRole.UserRole
_PLANT_OBJ_ROLE = Qt.ItemDataRole.UserRole + 1
_PLANT_PLACED_COUNT_ROLE = Qt.ItemDataRole.UserRole + 2
_PLANT_EXPANDED_ROLE     = Qt.ItemDataRole.UserRole + 3


# ── Compact results model + delegate ──────────────────────────────────────────
#
# The list is now a virtualized QListView backed by PlantListModel. Each row
# is one line by default (~22 px) so 10+ plants fit at default panel size and
# 20+ when the panel is widened. Clicking a row's chevron expands it inline,
# revealing the full detail block beneath the row without collapsing other
# expanded rows. Multiple rows can be expanded at once for cross-comparison.
#
# Search/filter rebuilds the model from scratch; expansion state is keyed by
# plant_id so expanded plants stay expanded across filter changes when they
# remain in the result set.

# Compact row geometry constants — tuned so 10+ rows fit in the default
# results pane height (~330 px after header + filters).
_ROW_H_COMPACT  = 26
_ROW_H_WRAPPED  = 44    # two-line variant for very long common names
_ROW_H_PADDING  = 4
_ZONE_BADGE_W   = 56
_NATIVE_BADGE_W = 18    # square AB-leaf badge

# Inline calendar strip (expanded rows): month-abbr row + coloured cells
# + legend, with small vertical gaps. Total fits inside the existing
# detail block between the data rows and the wrapped notes.
_CAL_MONTH_ROW_H = 12
_CAL_STRIP_H     = 18
_CAL_LEGEND_H    = 14
_CAL_GAP         = 3
_CAL_BLOCK_H     = (_CAL_MONTH_ROW_H + _CAL_STRIP_H + _CAL_LEGEND_H
                    + _CAL_GAP * 3)


def _zone_badge_text(plant: dict) -> str:
    zmin = plant.get("hardiness_zone_min")
    zmax = plant.get("hardiness_zone_max")
    if zmin and zmax:
        return f"Z{zmin}–{zmax}"
    if zmin:
        return f"Z{zmin}+"
    return ""


class PlantListModel(QAbstractListModel):
    """List model for compact one-line plant rows with expand-in-place state.

    The model owns the per-plant expansion flag (expanded ⇒ delegate paints
    a tall row that includes the detail block). Expansion state survives
    filter changes for any plant whose id is still in the new result set.
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self._plants: list[dict] = []
        self._placed_counts: dict[int, int] = {}
        self._expanded_ids: set[int] = set()
        # Per-plant 12-month planting calendar, lazily fetched the first
        # time a row is expanded. None means "not yet attempted"; an empty
        # list means "no calendar data". Cache lives for the panel's
        # lifetime.
        self._calendar_cache: dict[int, list[dict]] = {}

    # Standard model API -------------------------------------------------

    def rowCount(self, parent=QModelIndex()) -> int:
        return 0 if parent.isValid() else len(self._plants)

    def data(self, index: QModelIndex, role: int = Qt.ItemDataRole.DisplayRole):
        if not index.isValid() or index.row() >= len(self._plants):
            return None
        plant = self._plants[index.row()]
        if role == _PLANT_OBJ_ROLE:
            return plant
        if role == _PLANT_ID_ROLE:
            return plant.get("id")
        if role == _PLANT_PLACED_COUNT_ROLE:
            return self._placed_counts.get(plant.get("id"), 0)
        if role == _PLANT_EXPANDED_ROLE:
            return plant.get("id") in self._expanded_ids
        if role == Qt.ItemDataRole.DisplayRole:
            return plant.get("common_name", "")
        if role == Qt.ItemDataRole.ToolTipRole:
            return f"{plant.get('common_name','')} ({plant.get('scientific_name','—')})"
        return None

    # Public API ---------------------------------------------------------

    def set_plants(self, plants: list[dict]):
        """Swap the result set; preserve expansion for surviving ids."""
        self.beginResetModel()
        self._plants = list(plants)
        valid_ids = {p.get("id") for p in plants}
        self._expanded_ids = {pid for pid in self._expanded_ids if pid in valid_ids}
        self.endResetModel()

    def set_placed_counts(self, counts: dict[int, int]):
        self._placed_counts = dict(counts)
        if self._plants:
            top = self.index(0)
            bot = self.index(len(self._plants) - 1)
            self.dataChanged.emit(top, bot, [_PLANT_PLACED_COUNT_ROLE])

    def toggle_expanded(self, row: int):
        if 0 <= row < len(self._plants):
            pid = self._plants[row].get("id")
            if pid in self._expanded_ids:
                self._expanded_ids.discard(pid)
            else:
                self._expanded_ids.add(pid)
            idx = self.index(row)
            self.dataChanged.emit(idx, idx, [_PLANT_EXPANDED_ROLE])

    def collapse_all(self):
        if self._expanded_ids:
            self._expanded_ids.clear()
            if self._plants:
                self.dataChanged.emit(self.index(0),
                                      self.index(len(self._plants) - 1),
                                      [_PLANT_EXPANDED_ROLE])

    def calendar_for(self, plant_id: Optional[int]) -> list[dict]:
        """Return a 12-entry list of {month,status,notes} for plant_id.

        Empty list when plant_id is missing or DB lookup fails. Results
        are memoised so paint() can call this on every redraw cheaply.
        """
        if not plant_id:
            return []
        cached = self._calendar_cache.get(plant_id)
        if cached is not None:
            return cached
        try:
            from src.db.plants import get_calendar
            cal = get_calendar(plant_id)
        except Exception:
            cal = []
        self._calendar_cache[plant_id] = cal
        return cal


class PlantRowDelegate(QStyledItemDelegate):
    """Paints a compact one-line row with optional inline expansion.

    Compact row layout (left → right):
      · plant-type dot
      · common name (bold)  · scientific name (italic, dim)
      · placed-count chip ([N×]) when ≥1 placed
      · zone badge (Z3–5)
      · native-AB chip (small green leaf when native, neutral square otherwise)
      · expand chevron (▶ collapsed / ▼ expanded)

    Expanded rows extend below the compact row with a wrapped detail block
    showing description, sun/water, spacing/height, bloom/fruit periods,
    edible parts, and companions.
    """

    EXPAND_BTN_W = 18
    DOT_W = 14
    LEFT_PAD = 6

    # Colours for the native-AB badge.
    AB_NATIVE_BG  = "#2e7d32"
    AB_NATIVE_FG  = "#e8f5e9"
    AB_OTHER_BG   = "#37474f"
    AB_OTHER_FG   = "#90a4ae"

    def __init__(self, parent=None):
        super().__init__(parent)
        self._sci_font = QFont()
        self._sci_font.setItalic(True)
        self._small_font = QFont()
        # On some Windows + HiDPI setups the default QFont reports
        # pointSize() == -1 (size carried in pixels) and pointSize()-1
        # would feed a negative value into setPointSize, which Qt
        # rejects with a noisy warning per call. Decrement whichever
        # unit is actually populated; if neither is, leave the default.
        _pt = self._small_font.pointSize()
        _px = self._small_font.pixelSize()
        if _pt > 1:
            self._small_font.setPointSize(_pt - 1)
        elif _px > 1:
            self._small_font.setPixelSize(_px - 1)
        self._bold_font = QFont()
        self._bold_font.setBold(True)

        # Cache of "Hosts: Monarch, Mourning Cloak +N" strings keyed by
        # plant_id. Paint() is called on every scroll, so we avoid hitting
        # the DB more than once per plant. The cache is invalidated by
        # rebuilding the delegate (cheap; only on schema reload).
        self._wildlife_cache: dict[int, str] = {}
        self._companions_cache: dict[int, str] = {}

    def _wildlife_text_for_plant(self, plant_id) -> str:
        """Return a short comma-separated list of fauna supported by this
        plant, suitable for inline display in the detail block. Empty
        plants render '—'. Cached per plant_id."""
        if not plant_id:
            return "—"
        cached = self._wildlife_cache.get(plant_id)
        if cached is not None:
            return cached
        try:
            from src.db.fauna import fauna_for_plant
            rows = fauna_for_plant(int(plant_id))
        except Exception:
            self._wildlife_cache[plant_id] = "—"
            return "—"
        if not rows:
            text = "—"
        else:
            # Prefer larval hosts first (most ecologically meaningful), then
            # nectar/fruit/seed. De-duplicate by fauna common_name so a
            # single species appearing under multiple relationships doesn't
            # pad the list.
            seen: set[str] = set()
            ordered: list[str] = []
            for relation_priority in ("larval_host", "fruit_food", "seed_food",
                                       "nectar", "nesting", "pollen", "cover"):
                for r in rows:
                    if r.get("relationship") != relation_priority:
                        continue
                    name = r.get("common_name") or ""
                    if name in seen or not name:
                        continue
                    seen.add(name)
                    ordered.append(name)
            # V1.37: list every supported species — the row wraps to a
            # second line now, so the old top-3 "+N" cap that left
            # users wondering what was hidden is no longer needed.
            text = ", ".join(ordered)
        self._wildlife_cache[plant_id] = text
        return text

    def _companions_text_for_plant(self, plant_id) -> str:
        """Return a short "friends · avoid: enemies" string for the plant
        detail block. The companion tables (`companion_friends`,
        `companion_enemies`) are seeded at install but were never
        surfaced in the UI before V1.33 — this turns a long-standing
        README claim into an actual visible feature. Cached per
        plant_id; same invalidation pattern as the wildlife cache.
        """
        if not plant_id:
            return "—"
        cached = self._companions_cache.get(plant_id)
        if cached is not None:
            return cached
        try:
            from src.db.plants import get_companions
            data = get_companions(int(plant_id))
        except Exception:
            self._companions_cache[plant_id] = "—"
            return "—"
        friends = [p.get("common_name") or "" for p in data.get("friends") or []]
        enemies = [p.get("common_name") or "" for p in data.get("enemies") or []]
        friends = [n for n in friends if n]
        enemies = [n for n in enemies if n]
        if not friends and not enemies:
            text = "—"
        else:
            # V1.37: show all friends — Bur Oak has 4+ companions, the
            # old top-3 cap left users wondering what the "+N" hid.
            # Uses + companions rows now wrap to a second line if the
            # text doesn't fit on one, so listing everything is fine.
            parts: list[str] = []
            if friends:
                parts.append(", ".join(friends))
            if enemies:
                parts.append("avoid " + ", ".join(enemies))
            text = " · ".join(parts)
        self._companions_cache[plant_id] = text
        return text

    # Geometry helpers ---------------------------------------------------
    # All three return a rect anchored to the right edge of `compact`,
    # vertically centred to the bottom *line* of the compact strip
    # (where `line_h` defaults to the strip height for single-line
    # rows and is half of it for the two-line wrap variant).

    def _expand_btn_rect(self, compact: QRect) -> QRect:
        # Chevron is centred to the FULL compact strip so it stays
        # vertically aligned with the dot whether wrapped or not.
        return QRect(compact.right() - self.EXPAND_BTN_W,
                     compact.top(),
                     self.EXPAND_BTN_W,
                     compact.height())

    def _native_badge_rect(self, compact: QRect, line_h: int) -> QRect:
        x = compact.right() - self.EXPAND_BTN_W - _NATIVE_BADGE_W - 4
        y = compact.bottom() - line_h + (line_h - 14) // 2
        return QRect(x, y, _NATIVE_BADGE_W, 14)

    def _zone_badge_rect(self, compact: QRect, line_h: int) -> QRect:
        x = (compact.right() - self.EXPAND_BTN_W - _NATIVE_BADGE_W - 4
             - _ZONE_BADGE_W - 4)
        y = compact.bottom() - line_h + (line_h - 16) // 2
        return QRect(x, y, _ZONE_BADGE_W, 16)

    # Sizing -------------------------------------------------------------

    def _compact_height_for(self, plant: dict, panel_w: int) -> int:
        """Return how tall the compact strip needs to be: 1 line (26 px)
        or 2 lines (44 px). Long common names (e.g. "White-grained
        Mountain Rice Grass") that can't fit beside the chevron + AB
        badge on one line trigger the wrapped layout, so the user
        always sees the bold common name in full.

        Slack is intentionally generous (32 px) so wrap kicks in before
        Qt clips on Windows DPI scaling — Qt's font metrics on Windows
        often report ~5–15 px less than the rendered ink, and we'd
        rather err toward an extra-tall row than a clipped name.
        """
        common = plant.get("common_name") or ""
        if not common:
            return _ROW_H_COMPACT
        fm_b = QFontMetrics(self._bold_font)
        common_render = max(
            fm_b.horizontalAdvance(common),
            fm_b.boundingRect(common).width(),
        ) + 32
        # 1-line "lean" budget: row width minus left dot/pad and the
        # right-side chevron + AB chip.
        lean_budget = max(40, panel_w
                          - self.LEFT_PAD - self.DOT_W
                          - (self.EXPAND_BTN_W + _NATIVE_BADGE_W + 8))
        return _ROW_H_COMPACT if common_render <= lean_budget else _ROW_H_WRAPPED

    def sizeHint(self, option: QStyleOptionViewItem, index: QModelIndex) -> QSize:
        plant = index.data(_PLANT_OBJ_ROLE) or {}
        expanded = bool(index.data(_PLANT_EXPANDED_ROLE))
        view = self.parent()
        panel_w = (view.viewport().width() if view else option.rect.width()) or 280
        compact_h = self._compact_height_for(plant, panel_w)
        if not expanded:
            return QSize(0, compact_h)
        # Estimate detail height: base + per-line height for description.
        avail_w = max(200, panel_w - 12)
        fm = QFontMetrics(self._small_font)
        notes = plant.get("notes") or ""
        notes_h = 0
        if notes:
            # Reserve space for the FULL wrapped description. The plant
            # data block is one of the app's key features, so we never
            # truncate it — the longest entries in plants_master.json
            # are ~750 chars (~17 lines on a typical 280 px panel); cap
            # at 40 lines purely as a safety bound for any future
            # extra-long entries.
            bound = fm.boundingRect(
                0, 0, avail_w, 100000,
                int(Qt.TextFlag.TextWordWrap),
                notes,
            )
            wrapped_lines = max(1, bound.height() // fm.lineSpacing() + 1)
            notes_h = min(wrapped_lines, 40) * fm.lineSpacing() + 8
        # Calendar strip: month-abbr row (12) + coloured cells (18) +
        # legend row (line height) + small gaps. Only reserved when the
        # plant actually has a calendar in the local DB.
        cal_h = 0
        model = index.model()
        if isinstance(model, PlantListModel):
            cal = model.calendar_for(plant.get("id"))
            if cal:
                cal_h = _CAL_BLOCK_H
        # Detail rows: 5 single-line + 3 double-line (Uses, Wildlife,
        # Companions) = 11 lineSpacing units; round up to 12 for the
        # gap before the calendar block. V1.37 made the three list
        # rows wrap so Bur Oak's full companion + uses lists fit.
        detail_h = 12 * fm.lineSpacing() + cal_h + notes_h + 8
        return QSize(0, compact_h + detail_h)

    # Painting -----------------------------------------------------------

    def paint(self, painter: QPainter, option: QStyleOptionViewItem, index: QModelIndex):
        plant = index.data(_PLANT_OBJ_ROLE) or {}
        placed = index.data(_PLANT_PLACED_COUNT_ROLE) or 0
        expanded = bool(index.data(_PLANT_EXPANDED_ROLE))
        rect = option.rect

        painter.save()
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)

        selected = bool(option.state & QStyle.StateFlag.State_Selected)
        bg = QColor("#2e5a2e") if selected else QColor("#1a2a1a")
        if expanded and not selected:
            bg = QColor("#1f311f")
        painter.fillRect(rect, bg)

        # Row separator.
        painter.setPen(QPen(QColor("#1f341f"), 1))
        painter.drawLine(rect.left(), rect.bottom(), rect.right(), rect.bottom())

        # ── Compact row ─────────────────────────────────────────────
        # Decide the strip's own height up front: ~26 px when the common
        # name fits beside the chevron + AB badge on one line, ~44 px
        # (two lines) when it doesn't. The wrapped variant gives the
        # common name the full row width on line 1 and pushes the sci
        # name + badges down to line 2.
        compact_h = self._compact_height_for(plant, rect.width())
        wrapped = compact_h == _ROW_H_WRAPPED
        compact = QRect(rect.left(), rect.top(), rect.width(), compact_h)
        line_h = compact_h // 2 if wrapped else compact_h

        # Plant-type dot — vertically centred to line 1 (top half if
        # wrapped, otherwise the whole strip).
        dot_x = compact.left() + self.LEFT_PAD
        dot_centre_y = compact.top() + (line_h // 2 if wrapped
                                        else compact_h // 2)
        dot_color = QColor(_TYPE_COLORS.get(plant.get("plant_type", ""), "#78909c"))
        painter.setBrush(dot_color)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawEllipse(dot_x, dot_centre_y - 5, 10, 10)
        x = dot_x + self.DOT_W

        # Right-hand reservations. The zone badge (~56 px) is the
        # heaviest decoration — when the panel is narrow we collapse
        # it so the common name keeps its room. Zones are still
        # listed in the expanded detail block.
        right_pad_full = self.EXPAND_BTN_W + _NATIVE_BADGE_W + _ZONE_BADGE_W + 16
        right_pad_lean = self.EXPAND_BTN_W + _NATIVE_BADGE_W + 8

        common = plant.get("common_name", "")
        sci    = plant.get("scientific_name") or ""
        count_badge = f"  [{placed}×]" if placed > 0 else ""
        common_text = common + count_badge

        painter.setFont(self._bold_font)
        fm_b = QFontMetrics(self._bold_font)
        # Take max(advance, boundingRect) + 24 px slack for the right
        # side bearing — Windows GDI/DirectWrite bold glyphs frequently
        # ink several px past the cursor advance and Qt clips at the
        # rect's right edge. Slack must be ≤ the wrap-decision slack
        # (32 px in `_compact_height_for`) so non-wrapped rows always
        # still have enough room.
        common_advance = fm_b.horizontalAdvance(common_text)
        common_bb      = fm_b.boundingRect(common_text).width()
        common_render  = max(common_advance, common_bb) + 24

        # Single-line layout: try full (with zone) first, fall back to
        # lean (drop zone) so common name keeps fitting.
        # Wrapped layout: common always gets the whole row on line 1,
        # sci + all badges live on line 2 with the full reservation.
        if wrapped:
            # Line 1 — common name takes everything except the chevron
            # column on the right.
            line1_top   = compact.top()
            common_w_max = max(40, compact.right() - x - self.EXPAND_BTN_W - 6)
            if common_render <= common_w_max:
                common_w = common_render
                display_common = common_text
            else:
                # Pathologically long even on a full row → elide.
                common_w = common_w_max
                display_common = fm_b.elidedText(
                    common_text, Qt.TextElideMode.ElideRight, common_w,
                )
            painter.setPen(QColor("#e8f5e9") if selected else QColor("#c8e6c9"))
            painter.drawText(
                QRect(x, line1_top, common_w, line_h),
                int(Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft),
                display_common,
            )

            # Line 2 — sci on the left, all three badges on the right.
            show_zone = True
            line2_top = compact.top() + line_h
            sci_x = x
            sci_w = max(0, compact.right() - right_pad_full - sci_x)
            if sci and sci_w > 12:
                painter.setFont(self._sci_font)
                painter.setPen(QColor("#90a4ae"))
                fm_s = QFontMetrics(self._sci_font)
                sci_text = fm_s.elidedText(sci, Qt.TextElideMode.ElideRight, sci_w)
                painter.drawText(
                    QRect(sci_x, line2_top, sci_w, line_h),
                    int(Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft),
                    sci_text,
                )
        else:
            text_max_full = max(40, compact.right() - x - right_pad_full)
            text_max_lean = max(40, compact.right() - x - right_pad_lean)
            show_zone = common_render <= text_max_full
            text_max  = text_max_full if show_zone else text_max_lean
            right_pad = right_pad_full if show_zone else right_pad_lean

            if common_render <= text_max:
                common_w = common_render
                display_common = common_text
            else:
                common_w = text_max
                display_common = fm_b.elidedText(
                    common_text, Qt.TextElideMode.ElideRight, common_w,
                )
            painter.setPen(QColor("#e8f5e9") if selected else QColor("#c8e6c9"))
            painter.drawText(
                QRect(x, compact.top(), common_w, compact_h),
                int(Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft),
                display_common,
            )
            x_after_common = x + common_w + 6
            sci_w = max(0, compact.right() - right_pad - x_after_common)
            if sci and sci_w > 12:
                painter.setFont(self._sci_font)
                painter.setPen(QColor("#90a4ae"))
                fm_s = QFontMetrics(self._sci_font)
                sci_text = fm_s.elidedText(sci, Qt.TextElideMode.ElideRight, sci_w)
                painter.drawText(
                    QRect(x_after_common, compact.top(), sci_w, compact_h),
                    int(Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft),
                    sci_text,
                )

        # Zone badge — only when there was room for the common name on
        # the chosen layout.
        if show_zone:
            zr = self._zone_badge_rect(compact, line_h)
            zone_text = _zone_badge_text(plant)
            if zone_text:
                painter.setBrush(QColor("#37474f"))
                painter.setPen(QPen(QColor("#546e7a"), 1))
                painter.drawRoundedRect(zr, 3, 3)
                painter.setPen(QColor("#cfd8dc"))
                painter.setFont(self._small_font)
                painter.drawText(zr, int(Qt.AlignmentFlag.AlignCenter), zone_text)

        # Native-AB badge — green leaf glyph if native, neutral hatched dot otherwise.
        nb = self._native_badge_rect(compact, line_h)
        is_native = bool(plant.get("native_to_alberta"))
        bg_col = QColor(self.AB_NATIVE_BG if is_native else self.AB_OTHER_BG)
        fg_col = QColor(self.AB_NATIVE_FG if is_native else self.AB_OTHER_FG)
        painter.setBrush(bg_col)
        painter.setPen(QPen(QColor("#0d160d"), 0.5))
        painter.drawRoundedRect(nb, 3, 3)
        painter.setPen(fg_col)
        painter.setFont(self._small_font)
        # "AB" for native, en-dash for non-native — accessible without colour.
        painter.drawText(nb, int(Qt.AlignmentFlag.AlignCenter),
                         "AB" if is_native else "–")

        # Expand chevron — centred to the full compact strip so it
        # stays vertically aligned with the dot.
        chev = self._expand_btn_rect(compact)
        painter.setPen(QColor("#a5d6a7") if expanded else QColor("#78909c"))
        painter.setFont(self._small_font)
        painter.drawText(chev, int(Qt.AlignmentFlag.AlignCenter),
                         "▼" if expanded else "▶")

        # ── Expanded detail block ─────────────────────────────────
        if expanded:
            detail = QRect(rect.left() + 8, compact.bottom() + 4,
                           rect.width() - 16, rect.height() - compact_h - 8)
            painter.setPen(QColor("#90a4ae"))
            painter.setFont(self._small_font)
            fm_s = QFontMetrics(self._small_font)
            line_h = fm_s.lineSpacing()

            def _row(label: str, value: str, dy: int, *, max_lines: int = 1):
                """Paint one detail row. ``max_lines`` controls how much
                vertical space the value text gets — 1 (default) clips
                at the right edge, 2 wraps onto a second line for the
                long lists (Uses, Companions) introduced in V1.33.
                Bumps the value rect's height by ``max_lines * line_h``
                so Qt's TextWordWrap has room to break."""
                lbl_w = 80
                painter.setPen(QColor("#78909c"))
                painter.drawText(QRect(detail.left(), detail.top() + dy, lbl_w, line_h),
                                 int(Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft),
                                 label)
                painter.setPen(QColor("#cfd8dc"))
                flags = int(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft)
                if max_lines > 1:
                    flags |= int(Qt.TextFlag.TextWordWrap)
                painter.drawText(
                    QRect(detail.left() + lbl_w, detail.top() + dy,
                          detail.width() - lbl_w, line_h * max_lines),
                    flags, value,
                )

            spacing = plant.get("spacing_meters")
            height  = plant.get("mature_height_meters")
            sun     = _SUN_LABELS.get(plant.get("sun_requirement", ""), "—")
            water   = _WATER_LABELS.get(plant.get("water_needs", ""), "—")
            bloom   = plant.get("bloom_period") or "—"
            fruit   = plant.get("fruit_period") or "—"
            edible  = plant.get("edible_parts") or "—"
            uses_raw = plant.get("permaculture_uses") or ""
            # V1.37: unknown tags (not in _USE_LABELS) used to render as
            # the raw snake_case key — "food_forest" alongside
            # "Pollinator Plant" looked inconsistent. Now we title-case
            # them with spaces so the row reads uniformly regardless of
            # whether each tag has a canonical entry yet.
            def _format_use_tag(key: str) -> str:
                label = _USE_LABELS.get(key)
                if label:
                    return label
                return key.replace("_", " ").title()
            uses = ", ".join(_format_use_tag(u.strip())
                             for u in uses_raw.split(",") if u.strip()) or "—"

            zmin = plant.get("hardiness_zone_min")
            zmax = plant.get("hardiness_zone_max")
            if zmin and zmax:
                zones_str = f"Z{zmin}–{zmax}"
            elif zmin:
                zones_str = f"Z{zmin}+"
            else:
                zones_str = "—"

            # Schema v13: surface wildlife supported (lepidoptera larval
            # hosts + bird/bee links) inline in the detail block. Fetched
            # lazily so the delegate stays cheap when the database is
            # not available.
            hosts_text = self._wildlife_text_for_plant(plant.get("id"))
            companions_text = self._companions_text_for_plant(plant.get("id"))

            # Layout: short single-line rows stack at 1 * line_h each,
            # then Uses + Wildlife + Companions get 2 * line_h each so
            # their long comma-separated lists wrap instead of clipping
            # at the right edge. Total detail rows below: 5 single +
            # 3 double = 5 + 6 = 11 line_h.
            _row("Zones:",         zones_str, 0)
            _row("Sun · Water:",   f"{sun}  ·  {water}", line_h)
            _row("Spacing:",       (f"{spacing} m" if spacing else "—"), 2 * line_h)
            _row("Height:",        (f"{height} m" if height else "—"), 3 * line_h)
            _row("Bloom · Fruit:", f"{bloom}  ·  {fruit}", 4 * line_h)
            _row("Edible:",        edible, 5 * line_h)
            _row("Uses:",          uses, 6 * line_h, max_lines=2)
            _row("Wildlife:",      hosts_text, 8 * line_h, max_lines=2)
            _row("Companions:",    companions_text, 10 * line_h, max_lines=2)

            # ── Colour-coded planting calendar strip ──────────────
            # 12 cells across the detail width, one per month, coloured by
            # life-stage status from the planting_calendar table. Restores
            # the at-a-glance "what is this plant doing in July?" visual
            # that lived in the legacy detail panel before the compact
            # list landed.
            cal_block_top = detail.top() + 12 * line_h
            model = index.model()
            cal: list[dict] = []
            if isinstance(model, PlantListModel):
                cal = model.calendar_for(plant.get("id"))
            if cal:
                self._paint_calendar(painter, detail, cal_block_top, cal)
                notes_top_offset = 12 * line_h + _CAL_BLOCK_H
            else:
                notes_top_offset = 12 * line_h + 4

            notes = plant.get("notes") or ""
            if notes:
                ntop = detail.top() + notes_top_offset
                painter.setPen(QColor("#b0bec5"))
                painter.setFont(self._small_font)
                painter.drawText(
                    QRect(detail.left(), ntop, detail.width(),
                          detail.bottom() - ntop),
                    int(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft
                        | Qt.TextFlag.TextWordWrap),
                    notes,
                )
        painter.restore()

    # ── Calendar strip painter ──────────────────────────────────────────

    def _paint_calendar(self, painter: QPainter, detail: QRect, top: int,
                        cal: list[dict]):
        """Paint the 12-month coloured stage strip inside `detail`.

        Layout (top → bottom):
          row 0: 12 month-abbreviation labels (Jan, Feb, …)
          row 1: 12 coloured cells, one per month, status-coloured;
                 the current month gets a yellow ring
          row 2: legend dots for non-dormant statuses
        """
        from datetime import datetime
        current_month = datetime.now().month

        avail_w = detail.width()
        cell_count = 12

        # Row 0 — month labels.
        label_top = top
        painter.setFont(self._small_font)
        painter.setPen(QColor("#90a4ae"))
        for i in range(cell_count):
            x0 = detail.left() + (i * avail_w) // cell_count
            x1 = detail.left() + ((i + 1) * avail_w) // cell_count
            painter.drawText(
                QRect(x0, label_top, x1 - x0, _CAL_MONTH_ROW_H),
                int(Qt.AlignmentFlag.AlignCenter),
                _MONTH_ABBR[i],
            )

        # Row 1 — coloured stage cells.
        cell_top = label_top + _CAL_MONTH_ROW_H + _CAL_GAP
        for i in range(cell_count):
            x0 = detail.left() + (i * avail_w) // cell_count
            x1 = detail.left() + ((i + 1) * avail_w) // cell_count
            cell_rect = QRect(x0 + 1, cell_top, max(1, x1 - x0 - 2),
                              _CAL_STRIP_H)
            status = (cal[i].get("status") if i < len(cal) else None) or "dormant"
            color = QColor(_CALENDAR_STATUS_COLORS.get(status, "#37474f"))
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(color)
            painter.drawRoundedRect(cell_rect, 2, 2)
            if (i + 1) == current_month:
                painter.setPen(QPen(QColor("#fdd835"), 1.5))
                painter.setBrush(Qt.BrushStyle.NoBrush)
                painter.drawRoundedRect(cell_rect, 2, 2)

        # Row 2 — legend. V1.37: legend wraps to a second line when it
        # doesn't fit horizontally, so a Pruning cell (brown) is never
        # shown without its matching legend entry. The old behaviour
        # `break`-ed on overflow, which silently dropped Pruning on
        # narrow panels and left users wondering what the brown cell
        # in March meant.
        legend_top = cell_top + _CAL_STRIP_H + _CAL_GAP
        legend_x = detail.left()
        fm = QFontMetrics(self._small_font)
        for status, color in _CALENDAR_STATUS_COLORS.items():
            if status == "dormant":
                continue   # ubiquitous; skipping it keeps the legend compact
            label = _CALENDAR_STATUS_LABELS[status]
            tw = fm.horizontalAdvance(label)
            if legend_x + 9 + tw + 8 > detail.right():
                legend_x = detail.left()
                legend_top += _CAL_LEGEND_H + 2
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(QColor(color))
            painter.drawEllipse(legend_x, legend_top + 4, 6, 6)
            painter.setPen(QColor("#90a4ae"))
            painter.drawText(
                QRect(legend_x + 9, legend_top, tw + 2, _CAL_LEGEND_H),
                int(Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft),
                label,
            )
            legend_x += 9 + tw + 8

    # Editor / interaction --------------------------------------------------

    def editorEvent(self, event: QEvent, model, option: QStyleOptionViewItem,
                    index: QModelIndex) -> bool:
        # Click on the chevron toggles expansion. After an expand, also
        # scroll the row to the top of the viewport so the user can see
        # the full detail block (data rows + colour-coded month strip
        # + notes) without having to scroll inside the list manually.
        if event.type() == QEvent.Type.MouseButtonRelease:
            # Constrain the chevron hit area to the compact strip — when
            # the row is expanded, option.rect spans the full row height
            # and a naive click test would treat the whole right column
            # of the detail block as a chevron hit.
            plant = index.data(_PLANT_OBJ_ROLE) or {}
            compact_h = self._compact_height_for(plant, option.rect.width())
            compact = QRect(option.rect.left(), option.rect.top(),
                             option.rect.width(), compact_h)
            chev = self._expand_btn_rect(compact)
            if chev.contains(event.pos()) and isinstance(model, PlantListModel):
                was_expanded = bool(index.data(_PLANT_EXPANDED_ROLE))
                model.toggle_expanded(index.row())
                view = self.parent()
                if view is not None and not was_expanded:
                    # Newly expanded — pin to top so the calendar strip
                    # and notes are visible.
                    try:
                        view.scrollTo(
                            index, view.ScrollHint.PositionAtTop
                        )
                    except Exception:
                        pass
                return True
        return super().editorEvent(event, model, option, index)


# ── On-this-design summary panel ──────────────────────────────────────────────

class OnThisDesignPanel(QWidget):
    """Third inner tab (sibling of Plants and Plant Communities) reviewing
    what's currently placed. Three sub-tabs:

    - **Plants**: species → count.
    - **Communities**: community name → number of instances on the map.
    - **Stats**: species count, native %, layer breakdown, ecological-
      function tags.

    App.py owns the instance and drives both inputs:
    ``set_plants_counts(plant_panel._placed_counts)`` whenever the Plants
    tab signals ``placed_counts_changed``; ``set_design_data(enriched)``
    inside ``_sync_planning_panel`` for Communities + Stats."""

    def __init__(self, parent=None):
        super().__init__(parent)
        from PyQt6.QtWidgets import QTabWidget, QTextBrowser
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(2)
        self._tabs = QTabWidget()
        self._tabs.setStyleSheet(
            "QTabWidget::pane { border: 1px solid #2e4a2e; background: #1a2a1a; }"
            "QTabBar::tab { background: #1e2e1e; color: #a5d6a7; "
            "padding: 3px 10px; border: 1px solid #2e4a2e; "
            "border-bottom: none; font-size: 11px; }"
            "QTabBar::tab:selected { background: #2e4a2e; color: #e8f5e9; }"
        )
        root.addWidget(self._tabs)

        # Plants sub-tab
        plants_widget = QWidget()
        pl = QVBoxLayout(plants_widget)
        pl.setContentsMargins(2, 2, 2, 2)
        pl.setSpacing(2)
        self._plants_count_label = QLabel("None placed yet")
        self._plants_count_label.setStyleSheet("color: #78909c; font-size: 11px;")
        pl.addWidget(self._plants_count_label)
        self._plants_list = QListWidget()
        self._plants_list.setMinimumHeight(60)
        self._plants_list.setStyleSheet(_RESULTS_LIST_STYLE)
        self._plants_list.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self._plants_list.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding
        )
        pl.addWidget(self._plants_list, 1)
        self._tabs.addTab(plants_widget, "Plants")

        # Communities sub-tab
        communities_widget = QWidget()
        cl = QVBoxLayout(communities_widget)
        cl.setContentsMargins(2, 2, 2, 2)
        cl.setSpacing(2)
        self._communities_count_label = QLabel("No communities placed yet")
        self._communities_count_label.setStyleSheet(
            "color: #78909c; font-size: 11px;"
        )
        cl.addWidget(self._communities_count_label)
        self._communities_list = QListWidget()
        self._communities_list.setMinimumHeight(60)
        self._communities_list.setStyleSheet(_RESULTS_LIST_STYLE)
        self._communities_list.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self._communities_list.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding
        )
        cl.addWidget(self._communities_list, 1)
        self._tabs.addTab(communities_widget, "Communities")

        # Stats sub-tab
        stats_widget = QWidget()
        sl = QVBoxLayout(stats_widget)
        sl.setContentsMargins(2, 2, 2, 2)
        sl.setSpacing(2)
        self._stats_text = QTextBrowser()
        self._stats_text.setStyleSheet(
            "QTextBrowser { background: #1a2a1a; color: #c8e6c9; "
            "border: 1px solid #2e4a2e; border-radius: 4px; font-size: 12px; }"
        )
        sl.addWidget(self._stats_text, 1)
        self._tabs.addTab(stats_widget, "Stats")

        # Latest enriched snapshot — stashed so Stats can refresh without
        # the caller re-pushing it.
        self._latest_enriched: list[dict] = []

    # ── Plants sub-tab ────────────────────────────────────────────────

    def set_plants_counts(self, counts: dict):
        self._plants_list.clear()
        if not counts:
            self._plants_count_label.setText("None placed yet")
            return
        try:
            from src.db.plants import get_plant
            total = 0
            for pid, count in sorted(counts.items(), key=lambda kv: (-kv[1], kv[0])):
                p = get_plant(pid)
                name = p["common_name"] if p else f"Plant #{pid}"
                item = QListWidgetItem(f"{name}  ×{count}")
                item.setIcon(_type_icon(p["plant_type"] if p else ""))
                self._plants_list.addItem(item)
                total += count
            self._plants_count_label.setText(
                f"{total} plant{'s' if total != 1 else ''} placed"
                f" ({len(counts)} species)"
            )
        except Exception:
            self._plants_count_label.setText(
                f"{sum(counts.values())} plants placed"
            )

    # ── Communities + Stats sub-tabs ──────────────────────────────────

    def set_design_data(self, enriched: list[dict]):
        """Refresh Communities + Stats sub-tabs from the full enriched
        list of placed-plant features. Each entry should carry at least
        ``plant_id`` and (for community grouping) ``polyculture_name`` +
        ``polyculture_center_lat`` / ``polyculture_center_lng``."""
        self._latest_enriched = list(enriched or [])
        self._refresh_communities(enriched or [])
        self._refresh_stats(enriched or [])

    def _refresh_communities(self, enriched: list[dict]):
        self._communities_list.clear()
        # Group by community name; count distinct (centre lat, centre lng)
        # pairs per name to get instance count, plus total member count.
        from collections import defaultdict
        instances: dict[str, set] = defaultdict(set)
        member_counts: dict[str, int] = defaultdict(int)
        for p in enriched:
            name = (p.get("polyculture_name") or "").strip()
            if not name:
                continue
            clat = p.get("polyculture_center_lat")
            clng = p.get("polyculture_center_lng")
            key = (round(float(clat), 6), round(float(clng), 6)) if (
                clat is not None and clng is not None
            ) else p.get("placement_group_id")
            instances[name].add(key)
            member_counts[name] += 1
        if not instances:
            self._communities_count_label.setText("No communities placed yet")
            return
        for name in sorted(instances.keys(), key=str.lower):
            n_inst = len(instances[name])
            n_mem = member_counts[name]
            item = QListWidgetItem(
                f"{name}  — {n_inst} instance{'s' if n_inst != 1 else ''}"
                f", {n_mem} member{'s' if n_mem != 1 else ''}"
            )
            self._communities_list.addItem(item)
        total_inst = sum(len(v) for v in instances.values())
        self._communities_count_label.setText(
            f"{total_inst} community instance{'s' if total_inst != 1 else ''} "
            f"across {len(instances)} community name"
            f"{'s' if len(instances) != 1 else ''}"
        )

    def _refresh_stats(self, enriched: list[dict]):
        if not enriched:
            self._stats_text.setHtml(
                "<i style='color:#78909c;'>Nothing placed yet.</i>"
            )
            return
        from src.db.plants import get_plant
        total = len(enriched)
        species: set = set()
        native = 0
        layer_counts: dict[str, int] = {}
        function_counts: dict[str, int] = {}
        type_counts: dict[str, int] = {}
        plant_cache: dict[int, dict] = {}
        for p in enriched:
            pid = p.get("plant_id")
            if not pid:
                continue
            species.add(int(pid))
            plant = plant_cache.get(pid)
            if plant is None:
                try:
                    plant = get_plant(pid) or {}
                except Exception:
                    plant = {}
                plant_cache[pid] = plant
            if plant.get("native_to_alberta") or p.get("native_to_alberta"):
                native += 1
            ptype = (plant.get("plant_type") or p.get("plant_type") or "").lower()
            if ptype:
                type_counts[ptype] = type_counts.get(ptype, 0) + 1
            # Layer + function tags only stamp on community members, but
            # try to surface them when present (the bare-plant case
            # simply contributes nothing to layer/function tallies).
            layer = (p.get("layer") or "").lower()
            if layer:
                layer_counts[layer] = layer_counts.get(layer, 0) + 1
            for fn in (p.get("functions") or []):
                key = str(fn).lower()
                function_counts[key] = function_counts.get(key, 0) + 1
        native_pct = (100.0 * native / total) if total else 0.0
        rows: list[str] = []
        rows.append(
            f"<p><b>{total}</b> plants placed · "
            f"<b>{len(species)}</b> species · "
            f"<b>{native_pct:.0f}%</b> Alberta-native</p>"
        )
        if type_counts:
            rows.append("<p><b>Plant types</b><br>")
            rows.append(
                ", ".join(
                    f"{t.replace('_', ' ')}: {n}"
                    for t, n in sorted(type_counts.items(), key=lambda kv: -kv[1])
                )
            )
            rows.append("</p>")
        if layer_counts:
            rows.append("<p><b>Vegetation layers</b><br>")
            rows.append(
                ", ".join(
                    f"{l.replace('_', ' ')}: {n}"
                    for l, n in sorted(layer_counts.items(), key=lambda kv: -kv[1])
                )
            )
            rows.append("</p>")
        if function_counts:
            rows.append("<p><b>Ecological functions</b><br>")
            rows.append(
                ", ".join(
                    f"{f.replace('_', ' ')}: {n}"
                    for f, n in sorted(function_counts.items(), key=lambda kv: -kv[1])
                )
            )
            rows.append("</p>")
        self._stats_text.setHtml("".join(rows))


# ── Main widget ───────────────────────────────────────────────────────────────

class PlantPanel(QWidget):
    """Right-hand panel for browsing, filtering and placing plants."""

    # Place a plant (or pattern of plants). The third arg is the legacy
    # quantity spinner value (used when pattern["kind"]=="single"); the
    # fourth is the pattern descriptor — see MapWidget.set_mode docstring.
    place_plant_requested = pyqtSignal(int, str, int, dict)   # plant_id, common_name, quantity, pattern
    color_changed = pyqtSignal(int, str)                       # plant_id, hex_color
    # Emitted when "Save as Plant Community" creates a new community from
    # the stack, so the Communities tab can refresh its library list.
    communityCreated = pyqtSignal()
    # Emitted whenever _placed_counts mutates (place / clear / load / remove)
    # so the sibling On-This-Design inner tab can refresh its Plants sub-tab.
    placed_counts_changed = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._current_zone: Optional[int] = None
        self._selected_plant: Optional[dict] = None
        self._placed_counts: dict[int, int] = {}   # plant_id -> count

        # Polyculture mix — explicit list of species the user has added
        # via right-click → "Add to Polyculture Mix". When ≥2 species
        # are present, Row/Grid/Circle placements distribute species
        # across positions; otherwise the placement is single-species
        # (the currently-selected plant). The mix is intentionally
        # independent of the current selection — the selection only
        # exists to drive the Place button and detail expansion.
        self._mix_species: list[dict] = []
        self._MIX_MAX = 8   # cap so the list stays readable in the panel

        # Most recent recipe stashed at Place-click time so App can
        # consume it when JS fires onPatternPlaced after the user's
        # 2-click gesture (otherwise changing the mix mid-gesture would
        # use the wrong recipe). Cleared after consumption.
        self._pending_polyculture: Optional[dict] = None

        # Debounce timer for local search
        self._search_timer = QTimer(self)
        self._search_timer.setSingleShot(True)
        self._search_timer.setInterval(200)
        self._search_timer.timeout.connect(self._run_search)

        self._build_ui()

        # Restore the user's last "Restoring toward X" ecoregion choice so
        # it survives a restart. _on_ecoregion_changed is wired in
        # _build_ui, so guard against an infinite save-during-load loop by
        # setting via index without triggering an extra save.
        self._restore_ecoregion_preference()

        self._run_search()   # populate on startup
        # Snap the splitter to its auto-fit baseline on launch so the
        # bottom pane (incl. the Place Mix on Map button) is fully
        # visible even before the user touches the Plant Community Mix.
        QTimer.singleShot(0, self._refit_bottom_pane)

    def showEvent(self, event):
        # Belt-and-suspenders: the first show may happen after __init__
        # but before the splitter has real sizes (e.g. when the Plants
        # inner tab isn't the initial selection). Retry on first show so
        # the user lands on the auto-fit layout regardless of tab order.
        super().showEvent(event)
        if not getattr(self, "_did_initial_refit", False):
            self._did_initial_refit = True
            QTimer.singleShot(0, self._refit_bottom_pane)

    _SETTINGS_ECOREGION_KEY      = "plant_panel/ab_ecoregion"
    _SETTINGS_ECOREGION_AUTO_KEY = "plant_panel/ab_ecoregion_auto"

    def _restore_ecoregion_preference(self):
        """Pre-select the ecoregion combo. Priority:

          1. The user's explicit saved choice (set every time they
             touch the combo via ``_on_ecoregion_changed``).
          2. The most recent auto-detected ecoregion (V1.36 — written
             by ``site_panel._on_ecoregion`` after a property pin
             auto-detection).

        Auto-detect never overrides an explicit choice. Users who
        manually picked a region keep their preference forever; users
        who never touched the combo get the right default once they
        drop a property pin."""
        settings = QSettings()
        explicit = settings.value(self._SETTINGS_ECOREGION_KEY, "", type=str)
        autodetect = settings.value(
            self._SETTINGS_ECOREGION_AUTO_KEY, "", type=str
        )
        preferred = explicit or autodetect
        if not preferred:
            return
        for i in range(self._ecoregion_combo.count()):
            if self._ecoregion_combo.itemData(i) == preferred:
                self._ecoregion_combo.blockSignals(True)
                self._ecoregion_combo.setCurrentIndex(i)
                self._ecoregion_combo.blockSignals(False)
                return

    def _on_ecoregion_changed(self, _idx: int):
        QSettings().setValue(
            self._SETTINGS_ECOREGION_KEY,
            self._combo_value(self._ecoregion_combo),
        )
        self._run_search()

    # ── Build ─────────────────────────────────────────────────────────────────

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # Main split: browser (top) vs placement controls + placed list
        # (bottom). The browser pane is prioritised — when a row in the
        # plant list is expanded the splitter gives extra space to the
        # top while the placement controls become scrollable below
        # (Phase 3).
        splitter = QSplitter(Qt.Orientation.Vertical)
        splitter.setChildrenCollapsible(False)
        # Make the splitter handle obvious so the user notices it can
        # be dragged to claim more room for the placement controls.
        splitter.setHandleWidth(6)
        splitter.setStyleSheet(
            "QSplitter::handle:vertical { background: #2e4a2e; "
            "height: 6px; margin: 1px 0; border-radius: 2px; }"
            "QSplitter::handle:vertical:hover { background: #4a7a4a; }"
        )
        root.addWidget(splitter, 1)
        self._main_splitter = splitter

        # ── Top pane: search + filters + results list ─────────────────────
        local_tab = QWidget()
        top_layout = QVBoxLayout(local_tab)
        top_layout.setContentsMargins(8, 8, 8, 4)
        top_layout.setSpacing(4)

        # Search box
        self._search_box = QLineEdit()
        self._search_box.setPlaceholderText("Search plants…")
        self._search_box.setClearButtonEnabled(True)
        self._search_box.textChanged.connect(self._on_search_changed)
        top_layout.addWidget(self._search_box)

        # Filter row 1: Type + Sun
        row1 = QHBoxLayout()
        row1.setSpacing(4)
        self._type_combo = self._make_combo(
            [("All types", "")]
            + [(lbl, key) for key, lbl in _TYPE_LABELS.items()]
        )
        self._sun_combo = self._make_combo(
            [("Any sun", "")]
            + [(lbl, key) for key, lbl in _SUN_LABELS.items()]
        )
        row1.addWidget(self._type_combo)
        row1.addWidget(self._sun_combo)
        top_layout.addLayout(row1)

        # Filter row 2: Water + Use
        row2 = QHBoxLayout()
        row2.setSpacing(4)
        self._water_combo = self._make_combo(
            [("Any water", "")]
            + [(lbl, key) for key, lbl in _WATER_LABELS.items()]
        )
        self._use_combo = self._make_combo(
            [("Any use", "")]
            + [(lbl, key) for key, lbl in _USE_LABELS.items()]
        )
        row2.addWidget(self._water_combo)
        row2.addWidget(self._use_combo)
        top_layout.addLayout(row2)

        # Toggle filter row: Native AB + Edible + Medicinal + N-Fixer +
        # Pollinator + Perennial. The legacy "Filter by zone" / Zone label
        # row was removed (low value, took vertical space). Hardiness-zone
        # detection still runs in the background and tags placements via
        # `_current_zone`; users can read it from the status bar.
        _toggle_style = (
            "QPushButton { background: #1e2e1e; color: #78909c; border: 1px solid #2e4a2e; "
            "border-radius: 3px; padding: 2px 6px; font-size: 11px; }"
            "QPushButton:checked { background: #2e5a2e; color: #a5d6a7; border-color: #66bb6a; }"
            "QPushButton:hover { border-color: #4a7a4a; }"
        )
        extra_row = QHBoxLayout()
        extra_row.setSpacing(3)

        self._native_filter_btn = QPushButton("Native AB")
        self._native_filter_btn.setCheckable(True)
        self._native_filter_btn.setToolTip("Only show plants native to Alberta")
        self._native_filter_btn.setStyleSheet(_toggle_style)
        self._native_filter_btn.toggled.connect(self._run_search)
        extra_row.addWidget(self._native_filter_btn)

        self._edible_btn = QPushButton("Edible")
        self._edible_btn.setCheckable(True)
        self._edible_btn.setToolTip("Only show plants with edible parts")
        self._edible_btn.setStyleSheet(_toggle_style)
        self._edible_btn.toggled.connect(self._run_search)
        extra_row.addWidget(self._edible_btn)

        self._medicinal_btn = QPushButton("Medicinal")
        self._medicinal_btn.setCheckable(True)
        self._medicinal_btn.setToolTip("Only show plants with medicinal uses")
        self._medicinal_btn.setStyleSheet(_toggle_style)
        self._medicinal_btn.toggled.connect(self._run_search)
        extra_row.addWidget(self._medicinal_btn)

        self._nfixer_btn = QPushButton("N-Fixer")
        self._nfixer_btn.setCheckable(True)
        self._nfixer_btn.setToolTip("Only show nitrogen-fixing plants")
        self._nfixer_btn.setStyleSheet(_toggle_style)
        self._nfixer_btn.toggled.connect(self._run_search)
        extra_row.addWidget(self._nfixer_btn)

        self._pollinator_btn = QPushButton("Pollinator")
        self._pollinator_btn.setCheckable(True)
        self._pollinator_btn.setToolTip("Only show pollinator-friendly plants")
        self._pollinator_btn.setStyleSheet(_toggle_style)
        self._pollinator_btn.toggled.connect(self._run_search)
        extra_row.addWidget(self._pollinator_btn)

        self._perennial_btn = QPushButton("Perennial")
        self._perennial_btn.setCheckable(True)
        self._perennial_btn.setToolTip("Only show perennial plants")
        self._perennial_btn.setStyleSheet(_toggle_style)
        self._perennial_btn.toggled.connect(self._run_search)
        extra_row.addWidget(self._perennial_btn)

        top_layout.addLayout(extra_row)

        # Habitat-focused filter row: keystone species, larval host plants,
        # and bird-food producers. These three drive most of the value of
        # the "lawn-to-habitat" reframe — they let users surface the high-
        # impact natives (à la Doug Tallamy) rather than ornamental fluff.
        habitat_row = QHBoxLayout()
        habitat_row.setSpacing(3)

        self._keystone_btn = QPushButton("Keystone")
        self._keystone_btn.setCheckable(True)
        self._keystone_btn.setToolTip(
            "Keystone species — natives that support the most "
            "specialist insects and food webs"
        )
        self._keystone_btn.setStyleSheet(_toggle_style)
        self._keystone_btn.toggled.connect(self._run_search)
        habitat_row.addWidget(self._keystone_btn)

        self._host_btn = QPushButton("Host Plant")
        self._host_btn.setCheckable(True)
        self._host_btn.setToolTip(
            "Larval host plant for native butterflies / moths "
            "(e.g. milkweed for monarchs)"
        )
        self._host_btn.setStyleSheet(_toggle_style)
        self._host_btn.toggled.connect(self._run_search)
        habitat_row.addWidget(self._host_btn)

        self._birdfood_btn = QPushButton("Bird Food")
        self._birdfood_btn.setCheckable(True)
        self._birdfood_btn.setToolTip(
            "Produces seeds or berries eaten by native birds"
        )
        self._birdfood_btn.setStyleSheet(_toggle_style)
        self._birdfood_btn.toggled.connect(self._run_search)
        habitat_row.addWidget(self._birdfood_btn)

        habitat_row.addStretch(1)
        top_layout.addLayout(habitat_row)

        # ── Reference ecosystem picker (N1) ──────────────────────────────
        # Drives a server-side filter on plants.ab_ecoregion.  Each label is
        # an Alberta ecoregion; selecting one narrows the result list to
        # plants documented from that ecoregion.  Persisted across sessions
        # via QSettings so the user's "I'm restoring toward X" choice
        # survives a restart.
        ecoregion_row = QHBoxLayout()
        ecoregion_row.setSpacing(4)
        ecoregion_row.addWidget(QLabel("Restoring toward:"))
        self._ecoregion_combo = self._make_combo(_AB_ECOREGION_CHOICES)
        self._ecoregion_combo.setToolTip(
            "Filter the plant list to species documented from a specific\n"
            "Alberta ecoregion. Use 'Any ecoregion' to see everything."
        )
        self._ecoregion_combo.currentIndexChanged.connect(self._on_ecoregion_changed)
        ecoregion_row.addWidget(self._ecoregion_combo, 1)
        top_layout.addLayout(ecoregion_row)

        # Result count label
        self._result_count = QLabel("Results: —")
        self._result_count.setStyleSheet("color: #78909c; font-size: 11px;")
        top_layout.addWidget(self._result_count)

        # ── Compact results list (QListView + custom delegate) ─────────
        # Built on PlantListModel + PlantRowDelegate so each plant lives on
        # one ~26 px row by default (10+ visible at default panel size). The
        # chevron at the right edge expands a row inline to reveal the full
        # detail block; multiple rows can be expanded at once.
        self._results_model    = PlantListModel(self)
        self._results_list     = QListView()
        self._results_delegate = PlantRowDelegate(self._results_list)
        self._results_list.setModel(self._results_model)
        self._results_list.setItemDelegate(self._results_delegate)
        self._results_list.setSelectionMode(
            self._results_list.SelectionMode.SingleSelection
        )
        self._results_list.setUniformItemSizes(False)
        self._results_list.setStyleSheet(_RESULTS_LIST_STYLE)
        self._results_list.setVerticalScrollMode(
            self._results_list.ScrollMode.ScrollPerPixel
        )
        self._results_list.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self._results_list.selectionModel().currentChanged.connect(
            self._on_view_current_changed
        )
        self._results_list.doubleClicked.connect(self._on_view_double_clicked)
        self._results_list.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self._results_list.customContextMenuRequested.connect(self._on_plant_context_menu)
        top_layout.addWidget(self._results_list)

        from src.collapsible_panel import CollapsiblePanel
        self._browser_panel = CollapsiblePanel(
            "Plant Browser", panel_id="plant_panel_browser", expanded=True
        )
        self._browser_panel.set_content(local_tab)
        splitter.addWidget(self._browser_panel)

        # ── Bottom: placement controls + placed plants ────────────────────
        bottom = QWidget()
        bot_layout = QVBoxLayout(bottom)
        bot_layout.setContentsMargins(8, 4, 8, 8)
        bot_layout.setSpacing(6)

        # The legacy "Selected Plant" detail group + standalone planting
        # calendar QGroupBox were removed — both are now redundant with
        # the inline-expand chevron in the results list (which shows the
        # full detail block + the 12-cell colour-coded month strip in
        # one place).

        # ── Pattern mode selector ───────────────────────────────────────
        # Single = click-to-place (current behaviour). Row/Grid/Circle take
        # two clicks each and emit a single batch placement with shared
        # group_id. The placement-controls widget is shared with the Plant
        # Communities tab so both tabs expose identical placement options.
        from src.placement_controls import PlacementControlsWidget
        self._placement = PlacementControlsWidget(show_canopy_base=True)
        self._placement.patternKindChanged.connect(self._on_pattern_kind_changed)
        bot_layout.addWidget(self._placement)
        self._build_polyculture_controls(bot_layout)

        # ── Placement controls: quantity + colour + place button ───────
        place_row = QHBoxLayout()
        place_row.setSpacing(4)

        # Quantity spinner — only meaningful for Single mode (burst placement).
        qty_label = QLabel("Qty:")
        qty_label.setStyleSheet("color: #90a4ae; font-size: 11px;")
        self._qty_spin = QSpinBox()
        self._qty_spin.setMinimum(1)
        self._qty_spin.setMaximum(50)
        self._qty_spin.setValue(1)
        self._qty_spin.setFixedWidth(65)
        self._qty_spin.setToolTip("Single mode: how many plants to burst at the click point\n"
                                  "Ignored in Row/Grid/Circle modes")
        self._qty_spin.setStyleSheet(_QTY_SPIN_STYLE)
        place_row.addWidget(qty_label)
        place_row.addWidget(self._qty_spin)

        # Colour picker — small caption "Colour" sits directly above a
        # rainbow-tinted circular button so the affordance is obvious
        # both by label and by icon.
        color_col = QVBoxLayout()
        color_col.setContentsMargins(0, 0, 0, 0)
        color_col.setSpacing(2)
        color_caption = QLabel("Colour")
        color_caption.setAlignment(Qt.AlignmentFlag.AlignHCenter)
        color_caption.setStyleSheet("color: #90a4ae; font-size: 10px;")
        color_col.addWidget(color_caption)

        self._color_btn = QPushButton()
        self._color_btn.setFixedSize(28, 28)
        self._color_btn.setToolTip(
            "Set a custom marker colour for this plant.\n"
            "Click to open the colour picker."
        )
        self._color_btn.clicked.connect(self._on_color_pick)
        color_col.addWidget(self._color_btn, alignment=Qt.AlignmentFlag.AlignHCenter)
        place_row.addLayout(color_col)
        # Show the rainbow default until a plant is selected with a custom colour.
        self._update_color_btn("")

        # Place on Map button
        self._place_btn = QPushButton("Place on Map")
        self._place_btn.setEnabled(False)
        self._place_btn.setToolTip("Click to enter plant-placement mode on the map")
        self._place_btn.clicked.connect(self._on_place_clicked)
        self._place_btn.setStyleSheet(_PLACE_BTN_STYLE)
        place_row.addWidget(self._place_btn)

        bot_layout.addLayout(place_row)

        # Bottom pane: just placement controls now. (On This Design lives
        # in a sibling inner tab at the same level as Plants and Plant
        # Communities — see app.py's inner QTabWidget.) The widget+scroll
        # area pair is kept as instance attrs so `_refit_bottom_pane` can
        # auto-size the splitter when the mix grows/shrinks.
        self._bottom_widget = bottom
        bottom.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum
        )
        self._bottom_scroll = QScrollArea()
        self._bottom_scroll.setWidget(bottom)
        self._bottom_scroll.setWidgetResizable(True)
        self._bottom_scroll.setFrameShape(QFrame.Shape.NoFrame)
        self._bottom_scroll.setHorizontalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAlwaysOff
        )
        self._bottom_scroll.setMinimumHeight(140)

        splitter.addWidget(self._bottom_scroll)
        splitter.setSizes([700, 200])
        splitter.setStretchFactor(0, 5)
        splitter.setStretchFactor(1, 0)

    # ── Filter helpers ────────────────────────────────────────────────────────

    @staticmethod
    def _make_combo(items: list[tuple[str, str]]) -> QComboBox:
        cb = QComboBox()
        for label, data in items:
            cb.addItem(label, userData=data)
        cb.currentIndexChanged.connect(lambda _: None)  # placeholder
        return cb

    def _combo_value(self, combo: QComboBox) -> str:
        data = combo.currentData()
        return data if data else ""

    # ── Search / filter ───────────────────────────────────────────────────────

    def _on_search_changed(self, _text: str):
        self._search_timer.start()

    def _run_search(self):
        try:
            from src.db.plants import search_plants
        except Exception:
            return

        # Wire filter combo signals on first run
        if not hasattr(self, "_filters_wired"):
            self._type_combo.currentIndexChanged.connect(lambda _: self._run_search())
            self._sun_combo.currentIndexChanged.connect(lambda _: self._run_search())
            self._water_combo.currentIndexChanged.connect(lambda _: self._run_search())
            self._use_combo.currentIndexChanged.connect(lambda _: self._run_search())
            self._filters_wired = True

        # The dedicated zone-filter toggle was removed; results are
        # never zone-restricted now. `_current_zone` is still tracked
        # for status-bar display elsewhere.
        zone = None

        try:
            plants = search_plants(
                query       = self._search_box.text().strip(),
                plant_type  = self._combo_value(self._type_combo),
                sun_req     = self._combo_value(self._sun_combo),
                water_needs = self._combo_value(self._water_combo),
                perm_use    = self._combo_value(self._use_combo),
                zone        = zone,
                native_only = self._native_filter_btn.isChecked(),
                edible_only = self._edible_btn.isChecked(),
                medicinal_only = self._medicinal_btn.isChecked(),
                nfixer_only = self._nfixer_btn.isChecked(),
                pollinator_only = self._pollinator_btn.isChecked(),
                perennial_only = self._perennial_btn.isChecked(),
                host_plant_only = self._host_btn.isChecked(),
                keystone_only   = self._keystone_btn.isChecked(),
                bird_food_only  = self._birdfood_btn.isChecked(),
                ab_ecoregion    = self._combo_value(self._ecoregion_combo),
            )
        except Exception as exc:
            self._result_count.setText(f"Error: {exc}")
            return

        self._results_model.set_plants(plants)
        self._results_model.set_placed_counts(self._placed_counts)

        n = len(plants)
        self._result_count.setText(f"Results: {n}")

    # ── Selection / detail ────────────────────────────────────────────────────

    def _on_view_current_changed(self, current: QModelIndex, _prev: QModelIndex):
        """QListView equivalent of the old QListWidget currentItemChanged.

        Selecting a row enables the Place button and updates the colour-
        picker preview. The compact-list flow doesn't surface a separate
        bottom detail group — the inline expand chevron is the discovery
        path.
        """
        if not current.isValid():
            self._selected_plant = None
            self._place_btn.setEnabled(False)
            return
        plant = current.data(_PLANT_OBJ_ROLE)
        if not plant:
            self._selected_plant = None
            self._place_btn.setEnabled(False)
            return
        self._selected_plant = plant
        self._update_color_btn(plant.get("marker_color") or "")
        self._place_btn.setEnabled(True)

    def _on_view_double_clicked(self, index: QModelIndex):
        """Double-click: place the plant directly (Single mode)."""
        if not index.isValid():
            return
        plant = index.data(_PLANT_OBJ_ROLE)
        if plant:
            self._selected_plant = plant
            self._on_place_clicked()

    # ── Place on map ──────────────────────────────────────────────────────────

    # ── Pattern mode UI ───────────────────────────────────────────────────────

    def _build_polyculture_controls(self, outer: QVBoxLayout):
        """Build the inline stack-mix UI inside the placement group."""
        mix_box = QGroupBox("Plant current mix")
        mix_box.setStyleSheet(
            "QGroupBox { color: #a5d6a7; font-size: 11px; "
            "border: 1px solid #2e4a2e; border-radius: 4px; margin-top: 8px; }"
            "QGroupBox::title { subcontrol-origin: margin; left: 8px; "
            "padding: 0 4px; }"
        )
        ml = QVBoxLayout(mix_box)
        ml.setContentsMargins(6, 6, 6, 6)
        ml.setSpacing(3)

        self._mix_status = QLabel(
            "Mix off — right-click a plant in the list to add it.\n"
            "With ≥2 species, Row/Grid/Circle will mix them across the placement."
        )
        self._mix_status.setWordWrap(True)
        self._mix_status.setStyleSheet("color: #78909c; font-size: 10px;")
        ml.addWidget(self._mix_status)

        # ── Species rows (one per mix entry, custom widgets) ─────────
        self._mix_rows_container = QWidget()
        self._mix_rows_layout = QVBoxLayout(self._mix_rows_container)
        self._mix_rows_layout.setContentsMargins(0, 2, 0, 2)
        self._mix_rows_layout.setSpacing(2)
        self._mix_rows_container.setVisible(False)
        ml.addWidget(self._mix_rows_container)

        # ── Action buttons (clear, save as community) ────────────────
        btn_row = QHBoxLayout()
        btn_row.setSpacing(4)
        self._mix_clear_btn = QPushButton("Clear mix")
        self._mix_clear_btn.setStyleSheet(
            "QPushButton { background: #1e2e1e; color: #ef9a9a; "
            "border: 1px solid #4a2e2e; border-radius: 3px; "
            "padding: 2px 8px; font-size: 11px; }"
            "QPushButton:hover { border-color: #8a4a4a; }"
            "QPushButton:disabled { color: #455a64; border-color: #2e4a2e; }"
        )
        self._mix_clear_btn.clicked.connect(self._clear_mix)
        self._mix_clear_btn.setEnabled(False)
        btn_row.addWidget(self._mix_clear_btn)

        self._mix_save_btn = QPushButton("Save as Community")
        self._mix_save_btn.setStyleSheet(
            "QPushButton { background: #1e2e1e; color: #a5d6a7; "
            "border: 1px solid #2e4a2e; border-radius: 3px; "
            "padding: 2px 8px; font-size: 11px; }"
            "QPushButton:hover { border-color: #4a7a4a; }"
            "QPushButton:disabled { color: #455a64; border-color: #2e4a2e; }"
        )
        self._mix_save_btn.setToolTip(
            "Hex-pack the current stack into a disc and save it as a "
            "named Plant Community (appears in the Plant Community tab)."
        )
        self._mix_save_btn.clicked.connect(self._on_save_stack_as_community)
        self._mix_save_btn.setEnabled(False)
        btn_row.addWidget(self._mix_save_btn)

        self._mix_open_builder_btn = QPushButton("Open in Builder…")
        self._mix_open_builder_btn.setStyleSheet(
            "QPushButton { background: #1e2e1e; color: #a5d6a7; "
            "border: 1px solid #2e4a2e; border-radius: 3px; "
            "padding: 2px 8px; font-size: 11px; }"
            "QPushButton:hover { border-color: #4a7a4a; }"
            "QPushButton:disabled { color: #455a64; border-color: #2e4a2e; }"
        )
        self._mix_open_builder_btn.setToolTip(
            "Pre-populate the visual builder with this stack so you can "
            "tweak positions before saving it as a Plant Community."
        )
        self._mix_open_builder_btn.clicked.connect(self._on_open_stack_in_builder)
        self._mix_open_builder_btn.setEnabled(False)
        btn_row.addWidget(self._mix_open_builder_btn)
        btn_row.addStretch()
        ml.addLayout(btn_row)

        outer.addWidget(mix_box)

    def _on_pattern_kind_changed(self, kind: str):
        # Burst quantity only applies in Single mode.
        self._qty_spin.setEnabled(kind == "single")

    def _current_pattern(self) -> dict:
        """Build the pattern dict to pass to the map-placement signal.

        When a stack mix is active and the mode is multi-cell
        (row/grid/circle), the pattern's params get a `polyculture` key
        carrying the resolved species list, distribution strategy, and
        effective spacing — App._enter_plant_mode uses this to override
        the primary's spacing on the map, and App._on_pattern_placed
        uses it to assign species across positions.
        """
        pattern = self._placement.current_pattern()
        if pattern["kind"] == "single":
            return {"kind": "single"}
        poly = self.active_polyculture()
        if poly is not None:
            pattern["params"]["polyculture"] = poly
        return pattern

    # ── Polyculture mix ───────────────────────────────────────────────────

    def active_polyculture(self) -> Optional[dict]:
        """Return the current mix recipe, or None if fewer than 2 species.

        Recipe shape (all fields JSON-safe so it can travel through Qt
        signals and into the project file unchanged):
            {
              "species": [{"id", "common_name", "spacing_m",
                           "plant_type", "color", "weight"}, ...],
              "strategy": "even_split",
              "spacing_strategy": "max",
              "effective_spacing_m": float,
            }

        The mix is the explicit `_mix_species` list, populated only via
        the right-click "Add to Polyculture Mix" action. Each entry
        carries `_weight` (an integer ratio set by the row's spinner,
        defaulting to 1); equal weights ⇒ exactly equal split.
        """
        if len(self._mix_species) < 2:
            return None
        species = [
            {
                "id": int(p["id"]),
                "common_name": p.get("common_name") or "",
                "spacing_m": float(p.get("spacing_meters") or 1.0),
                "plant_type": p.get("plant_type") or "herb",
                "color": p.get("marker_color") or "",
                "weight": float(p.get("_weight", 1) or 1),
            }
            for p in self._mix_species if p.get("id")
        ]
        if len(species) < 2:
            return None
        from src.polyculture import resolve_spacing
        eff = resolve_spacing(species, "max")
        return {
            "species": species,
            "strategy": "even_split",
            "spacing_strategy": "max",
            "effective_spacing_m": eff,
        }

    def peek_pending_polyculture(self) -> Optional[dict]:
        """Return the recipe stashed at Place-click time *without* clearing it.

        App calls this from `_on_pattern_placed`. We deliberately do not
        clear the stash here so the user can drop multiple identical
        polyculture patterns back-to-back without re-clicking Place
        Mix. The stash is replaced when Place Mix is clicked again
        (`_on_place_clicked`) and cleared when plant mode exits
        (`clear_pending_polyculture`).
        """
        return self._pending_polyculture

    def clear_pending_polyculture(self):
        """Drop the in-flight recipe — called when plant mode is cancelled."""
        self._pending_polyculture = None

    def _add_to_mix(self, plant: dict):
        """Add a plant to the mix, ignoring duplicates and DB-less rows.

        Stores a shallow copy so we can attach a per-mix `_weight`
        without mutating the canonical plant dict in the search
        results.
        """
        pid = plant.get("id")
        if not pid:
            return
        if any(s.get("id") == pid for s in self._mix_species):
            return
        if len(self._mix_species) >= self._MIX_MAX:
            return
        entry = dict(plant)
        entry["_weight"] = 1
        self._mix_species.append(entry)
        self._refresh_mix_list()

    def _remove_from_mix(self, plant_id: int):
        before = len(self._mix_species)
        self._mix_species = [
            s for s in self._mix_species if s.get("id") != plant_id
        ]
        if len(self._mix_species) != before:
            self._refresh_mix_list()

    def _clear_mix(self):
        if not self._mix_species:
            return
        self._mix_species = []
        self._refresh_mix_list()

    def _refresh_mix_list(self):
        """Rebuild the species rows + status label from `_mix_species`.

        Each row is a custom QFrame: type-icon + common name + ratio
        spinner + × remove button. The whole stack is always visible
        (no scroll) so all ≤8 species fit at once. Also updates the
        Place button's text and the recipe combo's "active" tooltip
        so users see at a glance that a polyculture is queued up.
        """
        # Tear down old rows (stop signal connections from leaking).
        while self._mix_rows_layout.count():
            item = self._mix_rows_layout.takeAt(0)
            w = item.widget()
            if w is not None:
                w.setParent(None)
                w.deleteLater()

        n = len(self._mix_species)

        # Place button label tracks the active mix.
        if hasattr(self, "_place_btn"):
            self._place_btn.setText(
                "Place Mix on Map" if n >= 2 else "Place on Map"
            )

        if n == 0:
            self._mix_status.setText(
                "Mix off — right-click a plant in the list to add it.\n"
                "With ≥2 species, Row/Grid/Circle will mix them in equal "
                "ratios (adjust per-row to skew)."
            )
            self._mix_rows_container.setVisible(False)
            self._mix_clear_btn.setEnabled(False)
            self._mix_save_btn.setEnabled(False)
            self._mix_open_builder_btn.setEnabled(False)
            QTimer.singleShot(0, self._refit_bottom_pane)
            return

        all_sp = [float(s.get("spacing_meters") or 1.0) for s in self._mix_species]
        eff = max(all_sp) if all_sp else 1.0
        if n == 1:
            self._mix_status.setText(
                f"Mix: 1 species (need ≥2 to activate).\n"
                f"Add at least one more, then choose Row/Grid/Circle."
            )
        else:
            ratios = ":".join(str(int(s.get("_weight", 1) or 1))
                              for s in self._mix_species)
            self._mix_status.setText(
                f"Plant community: {n} species at {ratios} — spacing "
                f"{eff:.2f} m (max). Click Place Mix on Map."
            )
        self._mix_rows_container.setVisible(True)
        self._mix_clear_btn.setEnabled(True)
        # Save/Open-Builder are only meaningful with ≥2 species — single
        # species "communities" are just plants.
        can_save = n >= 2
        self._mix_save_btn.setEnabled(can_save)
        self._mix_open_builder_btn.setEnabled(can_save)

        for idx, s in enumerate(self._mix_species):
            row = self._build_mix_row(idx, s)
            self._mix_rows_layout.addWidget(row)
        # Auto-fit the bottom pane: grow it (eating into the plant browser)
        # so all the freshly added mix rows are visible without scrolling.
        # Deferred to the next event-loop tick so the new rows have been
        # laid out and contribute to sizeHint().
        QTimer.singleShot(0, self._refit_bottom_pane)

    def _refit_bottom_pane(self):
        """Resize `_main_splitter` so the bottom pane fits the placement
        controls + Plant Community Mix + Place Mix button without scrolling.
        Eats into the plant browser, but keeps `_MIN_BROWSER_PX` visible
        so the user always has a few result rows. Manual splitter drags
        are overridden on the next mix mutation — that's intentional.
        """
        splitter = getattr(self, "_main_splitter", None)
        scroll = getattr(self, "_bottom_scroll", None)
        bottom = getattr(self, "_bottom_widget", None)
        if splitter is None or scroll is None or bottom is None:
            return
        sizes = splitter.sizes()
        if len(sizes) != 2:
            return
        total = sum(sizes)
        if total <= 0:
            # Splitter hasn't been laid out yet — retry on the next tick.
            QTimer.singleShot(0, self._refit_bottom_pane)
            return
        # `+ 6` is a small fudge so the bottom scroll-area never shows a
        # vertical scrollbar at the snug fit (frame + spacing rounding).
        desired = max(scroll.minimumHeight(), bottom.sizeHint().height() + 6)
        max_bottom = max(total - _MIN_BROWSER_PX, scroll.minimumHeight())
        new_bottom = min(desired, max_bottom)
        splitter.setSizes([total - new_bottom, new_bottom])

    def _build_mix_row(self, idx: int, species: dict) -> QFrame:
        """One species line: clickable colour dot + name + ratio spinner + ×.

        The dot is per-row clickable: it opens a QColorDialog and writes
        the chosen hex into `self._mix_species[idx]["marker_color"]` only.
        The canonical plant row (and any single-species placements that
        use the global picker) are untouched, so each polyculture mix
        can carry its own colour palette without polluting the DB.
        """
        row = QFrame()
        row.setStyleSheet(
            "QFrame { background: #1e2e1e; border: 1px solid #2e4a2e; "
            "border-radius: 3px; }"
        )
        rl = QHBoxLayout(row)
        rl.setContentsMargins(4, 2, 4, 2)
        rl.setSpacing(4)

        # Clickable colour dot — overrides the type colour for this mix only.
        dot = QPushButton()
        dot.setFixedSize(14, 14)
        dot.setCursor(Qt.CursorShape.PointingHandCursor)
        dot.setToolTip(
            "Click to set this species' marker colour for this plant community mix"
        )
        self._style_mix_dot(dot, species)
        dot.clicked.connect(
            lambda _checked=False, i=idx, btn=dot: self._on_mix_dot_clicked(i, btn)
        )
        rl.addWidget(dot)

        name = QLabel(species.get("common_name") or "—")
        name.setStyleSheet("color: #c8e6c9; font-size: 11px;")
        name.setToolTip(species.get("scientific_name") or "")
        rl.addWidget(name, 1)

        spin = QSpinBox()
        spin.setRange(1, 9)
        spin.setValue(int(species.get("_weight", 1) or 1))
        spin.setFixedWidth(46)
        spin.setToolTip(
            "Ratio: how many of this species per cycle.\n"
            "Equal numbers (default 1:1:1…) ⇒ exact even split.\n"
            "Set 2 to get twice as many of this species, etc."
        )
        spin.setStyleSheet(_QTY_SPIN_STYLE)
        # Capture idx by default-arg so each row's signal binds to its own row.
        spin.valueChanged.connect(
            lambda v, i=idx: self._on_mix_weight_changed(i, v)
        )
        rl.addWidget(spin)

        rm = QPushButton("✕")
        rm.setFixedSize(20, 20)
        rm.setToolTip("Remove from mix")
        rm.setStyleSheet(
            "QPushButton { background: transparent; color: #ef9a9a; "
            "border: 1px solid transparent; border-radius: 3px; "
            "font-size: 11px; }"
            "QPushButton:hover { border-color: #8a4a4a; background: #2e1a1a; }"
        )
        pid = species.get("id")
        rm.clicked.connect(lambda: self._remove_from_mix(int(pid)) if pid else None)
        rl.addWidget(rm)

        return row

    @staticmethod
    def _style_mix_dot(btn: QPushButton, species: dict):
        """Repaint a mix-row dot using its per-mix marker_color override
        (falling back to the type colour). Border is a darker tint so the
        dot is clearly clickable."""
        color_hex = (species.get("marker_color")
                     or _TYPE_COLORS.get(species.get("plant_type", ""), "#78909c"))
        btn.setStyleSheet(
            f"QPushButton {{ background: {color_hex}; border: 1px solid #0d160d; "
            f"border-radius: 7px; min-width: 14px; min-height: 14px; }}"
            f"QPushButton:hover {{ border-color: #a5d6a7; }}"
        )

    def _on_mix_dot_clicked(self, idx: int, btn: QPushButton):
        if not (0 <= idx < len(self._mix_species)):
            return
        species = self._mix_species[idx]
        current = (species.get("marker_color")
                   or _TYPE_COLORS.get(species.get("plant_type", ""), "#66bb6a"))
        initial = QColor(current)
        color = QColorDialog.getColor(
            initial, self,
            f"Marker colour for {species.get('common_name', '')} (this mix)"
        )
        if not color.isValid():
            return
        species["marker_color"] = color.name()
        self._style_mix_dot(btn, species)

    def _on_mix_weight_changed(self, idx: int, value: int):
        if 0 <= idx < len(self._mix_species):
            self._mix_species[idx]["_weight"] = max(1, int(value))
            # Update only the status line — rebuilding rows would
            # disturb the spinner the user is interacting with.
            self._refresh_mix_status_only()

    def _refresh_mix_status_only(self):
        n = len(self._mix_species)
        if n < 2:
            return
        all_sp = [float(s.get("spacing_meters") or 1.0) for s in self._mix_species]
        eff = max(all_sp) if all_sp else 1.0
        ratios = ":".join(str(int(s.get("_weight", 1) or 1))
                          for s in self._mix_species)
        self._mix_status.setText(
            f"Plant community: {n} species at {ratios} — spacing "
            f"{eff:.2f} m (max). Click Place Mix on Map."
        )

    # ── Save stack as Plant Community ──────────────────────────────────────

    def _stack_for_export(self) -> list[dict]:
        """Return the current mix in the shape stack_to_community_members
        expects (id, common_name, spacing_m, plant_type, color, _weight)."""
        out: list[dict] = []
        for s in self._mix_species:
            pid = s.get("id")
            if not pid:
                continue
            out.append({
                "id": int(pid),
                "common_name": s.get("common_name") or "",
                "spacing_m": float(s.get("spacing_meters") or 1.0),
                "plant_type": s.get("plant_type") or "herb",
                "color": s.get("marker_color") or "",
                "_weight": int(s.get("_weight") or 1),
            })
        return out

    def _prompt_unique_community_name(self, default: str) -> Optional[str]:
        from PyQt6.QtWidgets import QInputDialog, QMessageBox
        from src.db import polycultures
        name, ok = QInputDialog.getText(
            self, "Save Plant Community",
            "Name for the new plant community:", text=default,
        )
        if not ok:
            return None
        name = name.strip()
        if not name:
            return None
        if polycultures.get_polyculture_by_name(name) is not None:
            base = name
            suffix = 2
            while polycultures.get_polyculture_by_name(f"{base} {suffix}") is not None:
                suffix += 1
            name = f"{base} {suffix}"
            QMessageBox.information(
                self, "Renamed",
                f"A community with that name already exists. "
                f"Saved as '{name}' instead."
            )
        return name

    def _on_save_stack_as_community(self):
        from PyQt6.QtWidgets import QMessageBox
        from src.db import polycultures
        from src.polyculture import stack_to_community_members
        stack = self._stack_for_export()
        if len(stack) < 2:
            return
        default = " + ".join(s["common_name"] for s in stack[:3])
        if len(stack) > 3:
            default += f" +{len(stack)-3}"
        default += " mix"
        name = self._prompt_unique_community_name(default)
        if not name:
            return
        members = stack_to_community_members(stack)
        try:
            new_id = polycultures.create_polyculture(name, "", None)
            polycultures.replace_polyculture_members(new_id, members)
        except Exception as exc:
            QMessageBox.critical(self, "Error",
                                 f"Could not save plant community:\n{exc}")
            return
        self.communityCreated.emit()
        QMessageBox.information(
            self, "Saved",
            f"Plant community '{name}' saved with {len(members)} "
            f"members. Find it under the Plant Community tab."
        )

    def _on_open_stack_in_builder(self):
        from PyQt6.QtWidgets import QDialog, QMessageBox
        from src.db import polycultures
        from src.polyculture import stack_to_community_members
        from src.polyculture_panel import PolycultureBuilderDialog
        stack = self._stack_for_export()
        if len(stack) < 2:
            return
        members = stack_to_community_members(stack)
        dialog = PolycultureBuilderDialog(self, polyculture_id=None)
        try:
            dialog.canvas.set_members(members)
            dialog._refresh_member_list()
        except Exception:
            pass
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        data = dialog.get_data()
        if not data.get("name"):
            return
        try:
            new_id = polycultures.create_polyculture(
                data["name"], data.get("description", ""), None
            )
            polycultures.replace_polyculture_members(new_id, data.get("members") or [])
        except Exception as exc:
            QMessageBox.critical(self, "Error",
                                 f"Could not save plant community:\n{exc}")
            return
        self.communityCreated.emit()
        QMessageBox.information(
            self, "Saved",
            f"Plant community '{data['name']}' saved."
        )

    # ── Place on map ──────────────────────────────────────────────────────────

    def _on_place_clicked(self, _item=None):
        if not self._selected_plant:
            return
        pattern = self._current_pattern()
        # Stash the polyculture recipe in flight so App can read it back
        # in `_on_pattern_placed` after JS finishes the 2-click gesture.
        # Cleared on consumption.
        self._pending_polyculture = (
            (pattern.get("params") or {}).get("polyculture")
            if isinstance(pattern, dict) else None
        )
        self.place_plant_requested.emit(
            self._selected_plant["id"],
            self._selected_plant["common_name"],
            self._qty_spin.value(),
            pattern,
        )

    def _on_plant_context_menu(self, pos):
        """Right-click context menu for plant results list."""
        index = self._results_list.indexAt(pos)
        if not index.isValid():
            return
        plant = index.data(_PLANT_OBJ_ROLE)
        if not plant:
            return

        menu = QMenu(self)
        menu.setStyleSheet(
            "QMenu { background: #1e2e1e; color: #c8e6c9; border: 1px solid #2e4a2e; }"
            "QMenu::item:selected { background: #2e4a2e; }"
        )

        act_place = menu.addAction(f"Place {plant['common_name']} on Map")
        act_place.triggered.connect(lambda: self._quick_place(plant))

        act_place5 = menu.addAction("Place ×5 on Map")
        act_place5.triggered.connect(lambda: self._quick_place(plant, 5))

        menu.addSeparator()

        expanded = bool(index.data(_PLANT_EXPANDED_ROLE))
        act_expand = menu.addAction("Collapse details" if expanded else "Expand details")
        act_expand.triggered.connect(
            lambda: self._results_model.toggle_expanded(index.row())
        )

        menu.addSeparator()

        # Polyculture mix — only meaningful for plants with a real id.
        already_in_mix = any(
            s.get("id") == plant.get("id") for s in self._mix_species
        )
        if already_in_mix:
            act_mix = menu.addAction("Remove from current mix")
            act_mix.triggered.connect(
                lambda: self._remove_from_mix(int(plant["id"]))
            )
        else:
            act_mix = menu.addAction("Add to current mix")
            act_mix.triggered.connect(lambda: self._add_to_mix(plant))
            if not plant.get("id"):
                act_mix.setEnabled(False)
            elif len(self._mix_species) >= self._MIX_MAX:
                act_mix.setEnabled(False)
                act_mix.setText(f"Mix full ({self._MIX_MAX} species max)")

        menu.exec(self._results_list.viewport().mapToGlobal(pos))

    def _quick_place(self, plant, qty=1):
        """Place a plant directly from context menu (always Single mode)."""
        self.place_plant_requested.emit(
            plant["id"], plant["common_name"], qty, {"kind": "single"}
        )

    def _on_color_pick(self):
        """Open a colour picker to set a custom marker colour for the selected plant."""
        if not self._selected_plant or not self._selected_plant.get("id"):
            return
        plant = self._selected_plant
        current = plant.get("marker_color") or ""
        initial = QColor(current) if current else QColor(
            _TYPE_COLORS.get(plant.get("plant_type", ""), "#66bb6a")
        )
        color = QColorDialog.getColor(initial, self, "Choose marker colour")
        if not color.isValid():
            return
        hex_color = color.name()  # e.g. '#ff5722'
        # Save to DB
        try:
            from src.db.plants import update_marker_color
            update_marker_color(plant["id"], hex_color)
            self._selected_plant["marker_color"] = hex_color
        except Exception:
            pass
        # Update the colour button preview
        self._update_color_btn(hex_color)
        # Signal the map to update existing markers
        self.color_changed.emit(plant["id"], hex_color)

    def _update_color_btn(self, hex_color: str):
        """Update the colour picker button to show the current plant's colour.

        With no custom colour set, paint a rainbow conic gradient so the
        button reads obviously as a colour picker without needing the
        caption label.
        """
        if hex_color:
            self._color_btn.setStyleSheet(
                f"QPushButton {{ background: {hex_color}; border: 1px solid #4a7a4a; "
                f"border-radius: 14px; }}"
                f"QPushButton:hover {{ border-color: #8aca8a; }}"
            )
        else:
            self._color_btn.setStyleSheet(
                "QPushButton {"
                " background: qconicalgradient(cx:0.5, cy:0.5, angle:0,"
                " stop:0 #ff5252, stop:0.17 #ffb74d, stop:0.33 #fdd835,"
                " stop:0.5 #66bb6a, stop:0.67 #29b6f6, stop:0.83 #7e57c2,"
                " stop:1 #ff5252);"
                " border: 1px solid #4a7a4a; border-radius: 14px;"
                "}"
                "QPushButton:hover { border-color: #8aca8a; }"
            )

    # ── Public API ────────────────────────────────────────────────────────────

    def set_zone(self, zone: Optional[int]):
        """Called by the main window when the hardiness zone changes.

        The dedicated zone filter UI was removed; we still track the
        current zone for any future zone-aware logic (status bar,
        suggested-plants), and we no longer touch the deleted
        `_zone_filter_btn` / `_zone_label` widgets.
        """
        self._current_zone = zone

    def on_plant_removed(self, plant_id: int):
        """Notify the panel that a plant marker was removed from the map."""
        if plant_id in self._placed_counts:
            self._placed_counts[plant_id] -= 1
            if self._placed_counts[plant_id] <= 0:
                del self._placed_counts[plant_id]
        self._results_model.set_placed_counts(self._placed_counts)
        self.placed_counts_changed.emit()

    def on_plant_placed(self, plant_id: int, common_name: str):
        """Notify the panel that a plant was placed on the map."""
        self._placed_counts[plant_id] = self._placed_counts.get(plant_id, 0) + 1
        self._results_model.set_placed_counts(self._placed_counts)
        self.placed_counts_changed.emit()

    def on_plants_placed_batch(self, placements: list[tuple[int, str]]):
        """Notify the panel that several plants were placed at once.

        Counts are updated for every (plant_id, common_name) pair, but the
        results model and the placed-list QListWidget are only rebuilt once
        at the end. This is the difference between O(N) DB lookups + list
        clears (which blocks the Qt event loop long enough that the embedded
        Leaflet view paints a stale 0x0 frame) and one rebuild — important
        when a polyculture drops 8+ markers in one click.
        """
        if not placements:
            return
        for pid, _name in placements:
            self._placed_counts[pid] = self._placed_counts.get(pid, 0) + 1
        self._results_model.set_placed_counts(self._placed_counts)
        self.placed_counts_changed.emit()

    def clear_placed(self):
        """Clear the placed-plants list (e.g. on New project)."""
        self._placed_counts.clear()
        self._results_model.set_placed_counts(self._placed_counts)
        self.placed_counts_changed.emit()

    def load_placed(self, plants: list[dict]):
        """Reload placed-plants list from a loaded project."""
        self._placed_counts.clear()
        for p in plants:
            pid = p.get("plant_id", 0)
            self._placed_counts[pid] = self._placed_counts.get(pid, 0) + 1
        self._results_model.set_placed_counts(self._placed_counts)
        self.placed_counts_changed.emit()


# Minimum plant-browser height the auto-fit will leave when the Plant
# Community Mix has grown enough to want the whole splitter. Roughly the
# filter dropdowns + ~3 result rows.
_MIN_BROWSER_PX = 180


# ── Stylesheets ───────────────────────────────────────────────────────────────

_RESULTS_LIST_STYLE = """
QListWidget {
    background: #1a2a1a;
    border: 1px solid #2e4a2e;
    border-radius: 4px;
    color: #c8e6c9;
    font-size: 12px;
    outline: none;
}
QListWidget::item {
    padding: 3px 6px;
    border-bottom: 1px solid #1f341f;
}
QListWidget::item:selected {
    background: #2e5a2e;
    color: #e8f5e9;
}
QListWidget::item:hover {
    background: #243824;
}
"""

_PLACE_BTN_STYLE = """
QPushButton {
    background: #2e7d32;
    color: #e8f5e9;
    border: none;
    border-radius: 4px;
    padding: 7px 12px;
    font-weight: bold;
    font-size: 13px;
}
QPushButton:hover  { background: #388e3c; }
QPushButton:pressed { background: #1b5e20; }
QPushButton:disabled { background: #2a3a2a; color: #4a6a4a; }
"""

_QTY_SPIN_STYLE = """
QSpinBox {
    background: #1a2a1a;
    color: #c8e6c9;
    border: 1px solid #2e4a2e;
    border-radius: 3px;
    padding: 2px 4px;
    font-size: 13px;
}
QSpinBox::up-button {
    subcontrol-origin: border;
    subcontrol-position: top right;
    width: 18px;
    border-left: 1px solid #2e4a2e;
    background: #243824;
}
QSpinBox::up-button:hover { background: #2e5a2e; }
QSpinBox::up-arrow {
    image: none;
    border-left: 4px solid transparent;
    border-right: 4px solid transparent;
    border-bottom: 5px solid #a5d6a7;
    width: 0; height: 0;
}
QSpinBox::down-button {
    subcontrol-origin: border;
    subcontrol-position: bottom right;
    width: 18px;
    border-left: 1px solid #2e4a2e;
    background: #243824;
}
QSpinBox::down-button:hover { background: #2e5a2e; }
QSpinBox::down-arrow {
    image: none;
    border-left: 4px solid transparent;
    border-right: 4px solid transparent;
    border-top: 5px solid #a5d6a7;
    width: 0; height: 0;
}
"""

