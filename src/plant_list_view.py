"""
plant_list_view.py — Model + delegate for the plant browser's virtualized
results list (right-side panel).

Split out of ``src/plant_panel.py`` in Chunk 4 of the strengthening plan.
Pure structural move: ``PlantListModel`` and ``PlantRowDelegate`` along
with the constants and helpers they need. PlantPanel re-imports the few
constants it shares (``_TYPE_COLORS``, ``_SUN_LABELS``, ``_USE_LABELS``,
``_WATER_LABELS``) and the ``_type_icon`` helper from here, so any value
edits stay in one place.

The leading-underscore names are kept for parity with the pre-split
plant_panel.py history; they're imported by name from PlantPanel and
should be treated as module-private to this file + plant_panel.py.
"""

from __future__ import annotations

from typing import Optional

from PyQt6.QtCore import (
    Qt, QAbstractListModel, QModelIndex, QRect, QSize, QEvent,
    QRunnable, QThreadPool, pyqtSignal,
)
from PyQt6.QtGui import (
    QColor, QIcon, QPixmap, QPainter, QFont, QBrush, QPen, QFontMetrics,
)
from PyQt6.QtWidgets import (
    QStyledItemDelegate, QStyle, QStyleOptionViewItem,
)


# ── Type colours ──────────────────────────────────────────────────────────────
# Canonical table lives in src/member_colors (Qt-free); re-exported under
# the historical name for PlantPanel and friends.
from src.member_colors import TYPE_COLORS as _TYPE_COLORS

# ── Vocabulary labels (also imported by plant_panel.py for filter UI) ─────────
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


# ── Shared QListWidget stylesheet ─────────────────────────────────────────────
# Used by both the placed-plants list in OnThisDesignPanel and the legacy
# secondary lists in PlantPanel. Kept here next to the other plant-list
# visual constants so a colour or border tweak stays in one place.
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


# ── Plant list item roles ─────────────────────────────────────────────────────

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
# Breathing room between the legend's last line and the notes paragraph,
# so even a wrapped legend (macOS's wider font) reads clearly separated.
_CAL_NOTES_GAP   = 6

# Expanded-row photo block (I1): max image height + two attribution lines.
_IMG_MAX_H = 110


def _zone_badge_text(plant: dict) -> str:
    zmin = plant.get("hardiness_zone_min")
    zmax = plant.get("hardiness_zone_max")
    if zmin and zmax:
        return f"Z{zmin}–{zmax}"
    if zmin:
        return f"Z{zmin}+"
    return ""


def _detail_image_path(plant: dict):
    """Local path to this plant's open-licensed photo if it's already cached /
    local, else None (I1). Cache-only — never blocks paint — so the expanded-row
    image is inert until the image dataset / cache is populated."""
    url = (plant or {}).get("image_url")
    if not url:
        return None
    try:
        from src.image_cache import get_cached_image
        return get_cached_image(url)
    except Exception:
        return None


class PlantListModel(QAbstractListModel):
    """List model for compact one-line plant rows with expand-in-place state.

    The model owns the per-plant expansion flag (expanded ⇒ delegate paints
    a tall row that includes the detail block). Expansion state survives
    filter changes for any plant whose id is still in the new result set.
    """

    # Emitted (from a worker thread) when a plant's photo finishes caching, so
    # the row can repaint with the image. Carries the plant id.
    imageReady = pyqtSignal(int)

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
        # Plant ids whose photo we've already kicked a background fetch for.
        self._img_prefetched: set[int] = set()
        self.imageReady.connect(self._on_image_ready)

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
            plant = self._plants[row]
            pid = plant.get("id")
            if pid in self._expanded_ids:
                self._expanded_ids.discard(pid)
            else:
                self._expanded_ids.add(pid)
                self._prefetch_image(plant)   # warm the photo for this row
            idx = self.index(row)
            self.dataChanged.emit(idx, idx, [_PLANT_EXPANDED_ROLE])

    def _prefetch_image(self, plant: dict):
        """Kick a one-time background fetch of a plant's photo into the local
        cache (I1). Off the UI thread; emits ``imageReady`` when done so the row
        repaints. No-op without a URL, when already cached, or if Qt threading is
        unavailable."""
        url = (plant or {}).get("image_url")
        pid = plant.get("id")
        if not url or pid is None or pid in self._img_prefetched:
            return
        self._img_prefetched.add(pid)
        try:
            from src.image_cache import get_cached_image
            if get_cached_image(url):
                return  # already available — nothing to fetch
        except Exception:
            return
        attribution = plant.get("image_attribution", "")
        license_str = plant.get("image_license", "")
        signal = self.imageReady

        class _FetchTask(QRunnable):
            def run(self):
                try:
                    from src.image_cache import resolve_image
                    if resolve_image(url, attribution, license_str):
                        signal.emit(pid)
                except Exception:
                    pass

        try:
            QThreadPool.globalInstance().start(_FetchTask())
        except Exception:
            pass

    def _on_image_ready(self, plant_id: int):
        for row, p in enumerate(self._plants):
            if p.get("id") == plant_id:
                idx = self.index(row)
                self.dataChanged.emit(idx, idx, [_PLANT_OBJ_ROLE])
                break

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
        # 16 matches the painted detail rect (rect.width() - 16) so the
        # wrap estimate and the painted wrap agree.
        avail_w = max(200, panel_w - 16)
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
                # Reserve the extra lines the legend wraps onto (wider
                # macOS fonts), mirroring the offset used in paint().
                extra_rows = self._legend_rows_for_width(avail_w) - 1
                cal_h = (_CAL_BLOCK_H + extra_rows * (_CAL_LEGEND_H + 2)
                         + _CAL_NOTES_GAP)
        # Open-licensed photo (I1): reserved only when one is cached, so the
        # row height is unchanged until images exist.
        image_h = 0
        if _detail_image_path(plant):
            image_h = _IMG_MAX_H + 2 * fm.lineSpacing() + 6
        # Detail rows: 5 single-line + 3 double-line (Uses, Wildlife,
        # Companions) = 11 lineSpacing units; round up to 12 for the
        # gap before the calendar block. V1.37 made the three list
        # rows wrap so Bur Oak's full companion + uses lists fit.
        detail_h = 12 * fm.lineSpacing() + cal_h + notes_h + image_h + 8
        return QSize(0, compact_h + detail_h)

    # Painting -----------------------------------------------------------

    def _paint_detail_image(self, painter: QPainter, detail: QRect,
                            plant: dict, img_path: str) -> QRect:
        """Draw the plant's cached photo + its attribution at the top of the
        detail block. Returns a detail rect shifted below them so the existing
        detail rows reflow down. Falls back to the original rect if the pixmap
        can't load."""
        pm = QPixmap(img_path)
        if pm.isNull():
            return detail
        scaled = pm.scaled(detail.width(), _IMG_MAX_H,
                           Qt.AspectRatioMode.KeepAspectRatio,
                           Qt.TransformationMode.SmoothTransformation)
        painter.drawPixmap(detail.left(), detail.top(), scaled)
        y = detail.top() + scaled.height() + 2
        fm_s = QFontMetrics(self._small_font)
        attr = (plant.get("image_attribution") or "").strip()
        if attr:
            painter.setPen(QColor("#78909c"))
            painter.setFont(self._small_font)
            painter.drawText(
                QRect(detail.left(), y, detail.width(), 2 * fm_s.lineSpacing()),
                int(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft
                    | Qt.TextFlag.TextWordWrap),
                attr)
            y += 2 * fm_s.lineSpacing()
        y += 4
        return QRect(detail.left(), y, detail.width(),
                     max(0, detail.bottom() - y))

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
            # Open-licensed photo (I1) at the top of the detail block — only when
            # cached, so this whole branch is inert until images exist. Returns a
            # detail rect shifted below the image so the rows reflow down.
            img_path = _detail_image_path(plant)
            if img_path:
                detail = self._paint_detail_image(painter, detail, plant, img_path)
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
                # _CAL_BLOCK_H covers a single legend line; add the lines
                # the legend actually wrapped onto so the notes start
                # below it instead of underneath it.
                extra_rows = self._legend_rows_for_width(detail.width()) - 1
                notes_top_offset = (12 * line_h + _CAL_BLOCK_H
                                    + extra_rows * (_CAL_LEGEND_H + 2)
                                    + _CAL_NOTES_GAP)
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

    def _legend_rows_for_width(self, detail_w: int) -> int:
        """How many lines the calendar legend wraps onto at this width.

        Mirrors the wrap loop in ``_paint_calendar`` exactly, so the
        painted legend and the heights reserved in sizeHint/paint can
        never disagree — macOS's wider font wraps "Pruning" onto a second
        legend line that used to be painted straight over the notes text
        below (the _CAL_BLOCK_H constant only covers one legend line).
        """
        fm = QFontMetrics(self._small_font)
        rows = 1
        x = 0
        for status in _CALENDAR_STATUS_COLORS:
            if status == "dormant":
                continue   # skipped by the painter too
            tw = fm.horizontalAdvance(_CALENDAR_STATUS_LABELS[status])
            if x + 9 + tw + 8 > detail_w - 1:   # detail.right() == left+w-1
                rows += 1
                x = 0
            x += 9 + tw + 8
        return rows

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
