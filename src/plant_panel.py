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
    QSpinBox, QDoubleSpinBox, QSlider, QCheckBox,
    QColorDialog, QMenu, QStackedWidget, QButtonGroup,
)
from PyQt6.QtCore import (
    Qt, QTimer, QThread, pyqtSignal, QSize, QAbstractListModel,
    QModelIndex, QRect, QEvent,
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

_USE_LABELS: dict[str, str] = {
    "nitrogen_fixer":    "Nitrogen Fixer",
    "dynamic_accumulator": "Dynamic Accumulator",
    "pollinator":        "Pollinator Plant",
    "windbreak":         "Windbreak",
    "food_forest":       "Food Forest",
    "medicine":          "Medicinal",
    "wildlife_habitat":  "Wildlife Habitat",
    "pioneer":           "Pioneer",
    "biomass":           "Biomass / Chop-Drop",
    "groundcover":       "Groundcover",
    "pest_repellent":    "Pest Repellent",
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
        # list means "no calendar data" (e.g. Permapeople plants without
        # local rows). Cache lives for the panel's lifetime.
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

        Empty list when plant_id is missing or DB lookup fails (e.g. the
        row is a Permapeople preview without a local id). Results are
        memoised so paint() can call this on every redraw cheaply.
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
        self._small_font.setPointSize(self._small_font.pointSize() - 1)
        self._bold_font = QFont()
        self._bold_font.setBold(True)

    # Geometry helpers ---------------------------------------------------

    def _expand_btn_rect(self, opt_rect: QRect) -> QRect:
        return QRect(opt_rect.right() - self.EXPAND_BTN_W,
                     opt_rect.top(),
                     self.EXPAND_BTN_W,
                     _ROW_H_COMPACT)

    def _native_badge_rect(self, opt_rect: QRect) -> QRect:
        x = opt_rect.right() - self.EXPAND_BTN_W - _NATIVE_BADGE_W - 4
        y = opt_rect.top() + (_ROW_H_COMPACT - 14) // 2
        return QRect(x, y, _NATIVE_BADGE_W, 14)

    def _zone_badge_rect(self, opt_rect: QRect) -> QRect:
        x = (opt_rect.right() - self.EXPAND_BTN_W - _NATIVE_BADGE_W - 4
             - _ZONE_BADGE_W - 4)
        y = opt_rect.top() + (_ROW_H_COMPACT - 16) // 2
        return QRect(x, y, _ZONE_BADGE_W, 16)

    # Sizing -------------------------------------------------------------

    def sizeHint(self, option: QStyleOptionViewItem, index: QModelIndex) -> QSize:
        plant = index.data(_PLANT_OBJ_ROLE) or {}
        expanded = bool(index.data(_PLANT_EXPANDED_ROLE))
        if not expanded:
            return QSize(0, _ROW_H_COMPACT)
        # Estimate detail height: base + per-line height for description.
        view = self.parent()
        avail_w = max(200, (view.viewport().width() if view else 280) - 12)
        fm = QFontMetrics(self._small_font)
        notes = plant.get("notes") or ""
        notes_h = 0
        if notes:
            wrapped_lines = max(1, fm.boundingRect(0, 0, avail_w, 1000,
                                                    int(Qt.TextFlag.TextWordWrap),
                                                    notes).height() // fm.lineSpacing())
            notes_h = min(wrapped_lines, 6) * fm.lineSpacing() + 4
        # Calendar strip: month-abbr row (12) + coloured cells (18) +
        # legend row (line height) + small gaps. Only reserved when the
        # plant actually has a calendar in the local DB; Permapeople-only
        # rows just skip it.
        cal_h = 0
        model = index.model()
        if isinstance(model, PlantListModel):
            cal = model.calendar_for(plant.get("id"))
            if cal:
                cal_h = _CAL_BLOCK_H
        detail_h = 6 * fm.lineSpacing() + cal_h + notes_h + 8
        return QSize(0, _ROW_H_COMPACT + detail_h)

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
        compact = QRect(rect.left(), rect.top(), rect.width(), _ROW_H_COMPACT)
        x = compact.left() + self.LEFT_PAD
        y_mid = compact.top() + _ROW_H_COMPACT // 2

        # Plant-type dot.
        dot_color = QColor(_TYPE_COLORS.get(plant.get("plant_type", ""), "#78909c"))
        painter.setBrush(dot_color)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawEllipse(x, y_mid - 5, 10, 10)
        x += self.DOT_W

        # Right-hand reserved area for badges + chevron.
        right_pad = self.EXPAND_BTN_W + _NATIVE_BADGE_W + _ZONE_BADGE_W + 16
        text_max = max(40, compact.right() - x - right_pad)

        # Common + scientific name on a single line. The common name
        # always gets enough room to render in full; the scientific
        # name shrinks (and ellipsises) to fit whatever's left over,
        # because the user can always reach the full sci name from
        # the expanded detail block.
        common = plant.get("common_name", "")
        sci    = plant.get("scientific_name") or ""
        count_badge = f"  [{placed}×]" if placed > 0 else ""
        common_text = common + count_badge

        painter.setPen(QColor("#e8f5e9") if selected else QColor("#c8e6c9"))
        painter.setFont(self._bold_font)
        fm_b = QFontMetrics(self._bold_font)
        common_natural = fm_b.horizontalAdvance(common_text)

        if common_natural <= text_max:
            common_w = common_natural
            painter.drawText(
                QRect(x, compact.top(), common_w, _ROW_H_COMPACT),
                int(Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft),
                common_text,
            )
            x_after_common = x + common_w + 6
            sci_w = max(0, compact.right() - right_pad - x_after_common)
            if sci and sci_w > 12:
                painter.setFont(self._sci_font)
                painter.setPen(QColor("#90a4ae"))
                fm_s = QFontMetrics(self._sci_font)
                sci_text = fm_s.elidedText(sci, Qt.TextElideMode.ElideRight, sci_w)
                painter.drawText(
                    QRect(x_after_common, compact.top(), sci_w, _ROW_H_COMPACT),
                    int(Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft),
                    sci_text,
                )
        else:
            # Pathologically narrow panel — common name doesn't fit.
            # Elide it, drop the scientific name; the chevron still
            # opens the expanded detail block which shows everything.
            common_w = text_max
            elided = fm_b.elidedText(common_text, Qt.TextElideMode.ElideRight,
                                      common_w)
            painter.drawText(
                QRect(x, compact.top(), common_w, _ROW_H_COMPACT),
                int(Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft),
                elided,
            )

        # Zone badge.
        zr = self._zone_badge_rect(compact)
        zone_text = _zone_badge_text(plant)
        if zone_text:
            painter.setBrush(QColor("#37474f"))
            painter.setPen(QPen(QColor("#546e7a"), 1))
            painter.drawRoundedRect(zr, 3, 3)
            painter.setPen(QColor("#cfd8dc"))
            painter.setFont(self._small_font)
            painter.drawText(zr, int(Qt.AlignmentFlag.AlignCenter), zone_text)

        # Native-AB badge — green leaf glyph if native, neutral hatched dot otherwise.
        nb = self._native_badge_rect(compact)
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

        # Expand chevron.
        chev = self._expand_btn_rect(compact)
        painter.setPen(QColor("#a5d6a7") if expanded else QColor("#78909c"))
        painter.setFont(self._small_font)
        painter.drawText(chev, int(Qt.AlignmentFlag.AlignCenter),
                         "▼" if expanded else "▶")

        # ── Expanded detail block ─────────────────────────────────
        if expanded:
            detail = QRect(rect.left() + 8, compact.bottom() + 4,
                           rect.width() - 16, rect.height() - _ROW_H_COMPACT - 8)
            painter.setPen(QColor("#90a4ae"))
            painter.setFont(self._small_font)
            fm_s = QFontMetrics(self._small_font)
            line_h = fm_s.lineSpacing()

            def _row(label: str, value: str, dy: int):
                lbl_w = 80
                painter.setPen(QColor("#78909c"))
                painter.drawText(QRect(detail.left(), detail.top() + dy, lbl_w, line_h),
                                 int(Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft),
                                 label)
                painter.setPen(QColor("#cfd8dc"))
                painter.drawText(QRect(detail.left() + lbl_w, detail.top() + dy,
                                        detail.width() - lbl_w, line_h),
                                 int(Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft),
                                 value)

            spacing = plant.get("spacing_meters")
            height  = plant.get("mature_height_meters")
            sun     = _SUN_LABELS.get(plant.get("sun_requirement", ""), "—")
            water   = _WATER_LABELS.get(plant.get("water_needs", ""), "—")
            bloom   = plant.get("bloom_period") or "—"
            fruit   = plant.get("fruit_period") or "—"
            edible  = plant.get("edible_parts") or "—"
            uses_raw = plant.get("permaculture_uses") or ""
            uses = ", ".join(_USE_LABELS.get(u.strip(), u.strip())
                             for u in uses_raw.split(",") if u.strip()) or "—"

            _row("Sun · Water:", f"{sun}  ·  {water}", 0)
            _row("Spacing:",     (f"{spacing} m" if spacing else "—"), line_h)
            _row("Height:",      (f"{height} m" if height else "—"), 2 * line_h)
            _row("Bloom · Fruit:", f"{bloom}  ·  {fruit}", 3 * line_h)
            _row("Edible:",      edible, 4 * line_h)
            _row("Uses:",        uses, 5 * line_h)

            # ── Colour-coded planting calendar strip ──────────────
            # 12 cells across the detail width, one per month, coloured by
            # life-stage status from the planting_calendar table. Restores
            # the at-a-glance "what is this plant doing in July?" visual
            # that lived in the legacy detail panel before the compact
            # list landed.
            cal_block_top = detail.top() + 6 * line_h
            model = index.model()
            cal: list[dict] = []
            if isinstance(model, PlantListModel):
                cal = model.calendar_for(plant.get("id"))
            if cal:
                self._paint_calendar(painter, detail, cal_block_top, cal)
                notes_top_offset = 6 * line_h + _CAL_BLOCK_H
            else:
                notes_top_offset = 6 * line_h + 4

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

        # Row 2 — legend.
        legend_top = cell_top + _CAL_STRIP_H + _CAL_GAP
        legend_x = detail.left()
        fm = QFontMetrics(self._small_font)
        for status, color in _CALENDAR_STATUS_COLORS.items():
            if status == "dormant":
                continue   # ubiquitous; skipping it keeps the legend on one line
            label = _CALENDAR_STATUS_LABELS[status]
            tw = fm.horizontalAdvance(label)
            if legend_x + 9 + tw + 8 > detail.right():
                break   # don't wrap; truncate gracefully on narrow panels
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
            chev = self._expand_btn_rect(option.rect)
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


# ── Main widget ───────────────────────────────────────────────────────────────

class PlantPanel(QWidget):
    """Right-hand panel for browsing, filtering and placing plants."""

    # Place a plant (or pattern of plants). The third arg is the legacy
    # quantity spinner value (used when pattern["kind"]=="single"); the
    # fourth is the pattern descriptor — see MapWidget.set_mode docstring.
    place_plant_requested = pyqtSignal(int, str, int, dict)   # plant_id, common_name, quantity, pattern
    color_changed = pyqtSignal(int, str)                       # plant_id, hex_color

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
        self._run_search()   # populate on startup

    # ── Build ─────────────────────────────────────────────────────────────────

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # Header
        header = QLabel("  Plant Browser")
        header.setFixedHeight(32)
        header.setStyleSheet(
            "background:#1b3a1b; color:#a5d6a7; font-weight:bold; "
            "font-size:13px; border-bottom:1px solid #2e4a2e;"
        )
        root.addWidget(header)

        # Main split: browser (top) vs placement controls + placed list (bottom)
        splitter = QSplitter(Qt.Orientation.Vertical)
        splitter.setChildrenCollapsible(False)
        root.addWidget(splitter)

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

        splitter.addWidget(local_tab)

        # ── Bottom: placement controls + placed plants ────────────────────
        bottom = QWidget()
        bot_layout = QVBoxLayout(bottom)
        bot_layout.setContentsMargins(8, 4, 8, 8)
        bot_layout.setSpacing(6)

        # The legacy "Selected Plant" detail group + standalone planting
        # calendar QGroupBox were removed when the Permapeople tab was
        # dropped — both are now redundant with the inline-expand chevron
        # in the results list (which shows the full detail block + the
        # 12-cell colour-coded month strip in one place).

        # ── Pattern mode selector ───────────────────────────────────────
        # Single = click-to-place (current behaviour). Row/Grid/Circle take
        # two clicks each and emit a single batch placement with shared
        # group_id. Per-mode parameter widgets live in a QStackedWidget so
        # only relevant inputs are visible at a time.
        self._build_pattern_controls(bot_layout)

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

        # Colour picker button
        self._color_btn = QPushButton("●")
        self._color_btn.setFixedSize(28, 28)
        self._color_btn.setToolTip("Set custom marker colour for this plant")
        self._color_btn.clicked.connect(self._on_color_pick)
        self._color_btn.setStyleSheet(
            "QPushButton { background: #2e4a2e; border: 1px solid #4a7a4a; "
            "border-radius: 14px; font-size: 16px; color: #78909c; }"
            "QPushButton:hover { background: #3a5a3a; }"
        )
        place_row.addWidget(self._color_btn)

        # Place on Map button
        self._place_btn = QPushButton("Place on Map")
        self._place_btn.setEnabled(False)
        self._place_btn.setToolTip("Click to enter plant-placement mode on the map")
        self._place_btn.clicked.connect(self._on_place_clicked)
        self._place_btn.setStyleSheet(_PLACE_BTN_STYLE)
        place_row.addWidget(self._place_btn)

        bot_layout.addLayout(place_row)

        # ── Placed plants section — collapsible (persisted across sessions) ─
        from src.collapsible_panel import CollapsiblePanel
        self._placed_panel = CollapsiblePanel(
            "On This Design", panel_id="plant_panel_on_design", expanded=True
        )
        placed_body = QWidget()
        pb_layout = QVBoxLayout(placed_body)
        pb_layout.setContentsMargins(0, 0, 0, 0)
        pb_layout.setSpacing(2)

        self._placed_count_label = QLabel("None placed yet")
        self._placed_count_label.setStyleSheet("color: #78909c; font-size: 11px;")
        pb_layout.addWidget(self._placed_count_label)

        self._placed_list = QListWidget()
        self._placed_list.setMinimumHeight(60)
        self._placed_list.setStyleSheet(_RESULTS_LIST_STYLE)
        self._placed_list.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self._placed_list.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding
        )
        pb_layout.addWidget(self._placed_list, 1)
        self._placed_panel.set_content(placed_body)
        bot_layout.addWidget(self._placed_panel, 1)

        splitter.addWidget(bottom)
        # Lean the split toward the browser so an expanded row's full
        # detail block (~180 px) is visible without scrolling. The user
        # can still drag the splitter handle to rebalance.
        splitter.setSizes([520, 280])
        splitter.setStretchFactor(0, 3)
        splitter.setStretchFactor(1, 2)

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
        picker preview. The compact-list flow doesn't surface the bottom
        detail group (the inline expand chevron is the discovery path);
        that group is only used for the Permapeople tab.
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

    def _build_pattern_controls(self, parent_layout: QVBoxLayout):
        """Build the placement-mode segmented buttons + per-mode inputs."""
        self._pattern_kind = "single"   # 'single' | 'row' | 'grid' | 'circle'

        wrap = QGroupBox("Placement Mode")
        wrap.setStyleSheet(
            "QGroupBox { color: #a5d6a7; font-size: 11px; "
            "border: 1px solid #2e4a2e; border-radius: 4px; margin-top: 8px; }"
            "QGroupBox::title { subcontrol-origin: margin; left: 8px; "
            "padding: 0 4px; }"
        )
        outer = QVBoxLayout(wrap)
        outer.setContentsMargins(6, 6, 6, 6)
        outer.setSpacing(4)

        # ── Mode segmented buttons ────────────────────────────────────
        seg = QHBoxLayout()
        seg.setSpacing(2)
        self._pattern_btn_group = QButtonGroup(self)
        self._pattern_btn_group.setExclusive(True)
        for key, label, tip in [
            ("single", "Single", "Click to place one plant at a time"),
            ("row",    "Row",    "Click start, then end — fills a line of plants"),
            ("grid",   "Grid",   "Click two opposite corners — fills a rectangle"),
            ("circle", "Circle", "Click centre, then radius — places plants on a circle"),
        ]:
            btn = QPushButton(label)
            btn.setCheckable(True)
            btn.setToolTip(tip)
            btn.setStyleSheet(_PATTERN_SEG_STYLE)
            btn.setProperty("pattern_kind", key)
            self._pattern_btn_group.addButton(btn)
            seg.addWidget(btn)
            if key == "single":
                btn.setChecked(True)
        self._pattern_btn_group.buttonClicked.connect(self._on_pattern_kind_changed)
        outer.addLayout(seg)

        # ── Stacked per-mode parameter panels ──────────────────────────
        self._pattern_stack = QStackedWidget()
        outer.addWidget(self._pattern_stack)

        # Single — no parameters beyond the legacy Qty spinner below.
        single_panel = QWidget()
        sl = QVBoxLayout(single_panel)
        sl.setContentsMargins(0, 0, 0, 0)
        sl.addWidget(QLabel("Use the Qty spinner below for burst placement."))
        sl.itemAt(0).widget().setStyleSheet("color: #78909c; font-size: 11px;")
        self._pattern_stack.addWidget(single_panel)

        # Row — count input.
        row_panel = QWidget()
        rl = QHBoxLayout(row_panel)
        rl.setContentsMargins(0, 0, 0, 0)
        rl.setSpacing(4)
        rl.addWidget(self._small_label("Count:"))
        self._row_count = QSpinBox()
        self._row_count.setRange(0, 200)
        self._row_count.setValue(0)
        self._row_count.setSpecialValueText("auto")
        self._row_count.setToolTip("0 = auto from spacing; otherwise force this many plants")
        self._row_count.setStyleSheet(_QTY_SPIN_STYLE)
        self._row_count.setFixedWidth(80)
        rl.addWidget(self._row_count)
        rl.addStretch()
        self._pattern_stack.addWidget(row_panel)

        # Grid — rows × cols + stagger.
        grid_panel = QWidget()
        gl = QHBoxLayout(grid_panel)
        gl.setContentsMargins(0, 0, 0, 0)
        gl.setSpacing(4)
        gl.addWidget(self._small_label("Rows:"))
        self._grid_rows = QSpinBox()
        self._grid_rows.setRange(0, 200)
        self._grid_rows.setSpecialValueText("auto")
        self._grid_rows.setStyleSheet(_QTY_SPIN_STYLE)
        self._grid_rows.setFixedWidth(70)
        gl.addWidget(self._grid_rows)
        gl.addWidget(self._small_label("Columns:"))
        self._grid_cols = QSpinBox()
        self._grid_cols.setRange(0, 200)
        self._grid_cols.setSpecialValueText("auto")
        self._grid_cols.setStyleSheet(_QTY_SPIN_STYLE)
        self._grid_cols.setFixedWidth(70)
        gl.addWidget(self._grid_cols)
        self._grid_stagger = QCheckBox("Stagger")
        self._grid_stagger.setToolTip("Hex-pack: offset every other row by half a column")
        gl.addWidget(self._grid_stagger)
        gl.addStretch()
        self._pattern_stack.addWidget(grid_panel)

        # Circle — total + fill.
        circle_panel = QWidget()
        cl = QHBoxLayout(circle_panel)
        cl.setContentsMargins(0, 0, 0, 0)
        cl.setSpacing(4)
        cl.addWidget(self._small_label("Total:"))
        self._circle_count = QSpinBox()
        self._circle_count.setRange(0, 2000)
        self._circle_count.setSpecialValueText("auto")
        self._circle_count.setToolTip(
            "Total plants in the placement.\n"
            "0 (auto) = derive from spacing — perimeter mode uses arc length, "
            "fill mode packs the whole disc.\n"
            "Otherwise: that many plants on the perimeter (no fill) or in the "
            "hex-pack disc (fill), closest-to-centre first."
        )
        self._circle_count.setStyleSheet(_QTY_SPIN_STYLE)
        self._circle_count.setFixedWidth(80)
        cl.addWidget(self._circle_count)
        self._circle_fill = QCheckBox("Fill (hex)")
        self._circle_fill.setToolTip(
            "Honeycomb-pack the whole disc so every plant has six "
            "equidistant neighbours. Use the Total spinner to cap the "
            "count for large radii."
        )
        cl.addWidget(self._circle_fill)
        cl.addStretch()
        self._pattern_stack.addWidget(circle_panel)

        # ── Overlap factor slider (applies to all multi modes) ─────────
        ov = QHBoxLayout()
        ov.setSpacing(4)
        ov.addWidget(self._small_label("Overlap:"))
        self._overlap_slider = QSlider(Qt.Orientation.Horizontal)
        self._overlap_slider.setRange(0, 100)
        self._overlap_slider.setValue(0)
        self._overlap_slider.setToolTip(
            "0% = centres exactly mature-width apart (no canopy overlap)\n"
            "100% = centres coincide. Effective spacing = mature_width × (1 − overlap)"
        )
        ov.addWidget(self._overlap_slider, 1)
        self._overlap_label = QLabel("0%")
        self._overlap_label.setStyleSheet("color: #a5d6a7; font-size: 11px; min-width: 32px;")
        ov.addWidget(self._overlap_label)
        self._overlap_slider.valueChanged.connect(
            lambda v: self._overlap_label.setText(f"{v}%")
        )
        outer.addLayout(ov)

        # ── Polyculture mix panel ─────────────────────────────────────
        # When the user adds ≥1 secondary species via right-click → "Add
        # to Polyculture Mix", Row/Grid/Circle placements distribute
        # species across positions. Spacing defaults to the largest
        # mature-width in the mix so canopies don't overlap.
        self._build_polyculture_controls(outer)

        parent_layout.addWidget(wrap)

    def _build_polyculture_controls(self, outer: QVBoxLayout):
        """Build the inline polyculture-mix UI inside the placement group.

        Layout (top → bottom):
          · status label (mode + spacing summary)
          · saved-recipe row: dropdown + Save / Delete
          · always-visible column of per-species rows:
              icon · common name · ratio spinner · × remove
          · Clear mix button

        The species rows are a vertical column (no QListWidget) so all
        ≤8 species are visible simultaneously without scrolling.
        """
        mix_box = QGroupBox("Polyculture Mix")
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

        # ── Saved-recipe row ──────────────────────────────────────────
        recipe_row = QHBoxLayout()
        recipe_row.setSpacing(4)
        self._recipe_combo = QComboBox()
        self._recipe_combo.setToolTip("Load a saved polyculture mix")
        self._recipe_combo.activated.connect(self._on_recipe_selected)
        recipe_row.addWidget(self._recipe_combo, 1)
        self._recipe_save_btn = QPushButton("Save")
        self._recipe_save_btn.setToolTip("Save the current mix under a name you can recall later")
        self._recipe_save_btn.setStyleSheet(_PATTERN_SEG_STYLE)
        self._recipe_save_btn.clicked.connect(self._on_recipe_save)
        recipe_row.addWidget(self._recipe_save_btn)
        self._recipe_delete_btn = QPushButton("✕")
        self._recipe_delete_btn.setToolTip("Delete the currently-selected saved mix")
        self._recipe_delete_btn.setFixedWidth(28)
        self._recipe_delete_btn.setStyleSheet(
            "QPushButton { background: #1e2e1e; color: #ef9a9a; "
            "border: 1px solid #4a2e2e; border-radius: 3px; "
            "padding: 2px 4px; font-size: 11px; }"
            "QPushButton:hover { border-color: #8a4a4a; }"
            "QPushButton:disabled { color: #455a64; border-color: #2e4a2e; }"
        )
        self._recipe_delete_btn.clicked.connect(self._on_recipe_delete)
        recipe_row.addWidget(self._recipe_delete_btn)
        ml.addLayout(recipe_row)
        self._refresh_recipe_combo()

        # ── Species rows (one per mix entry, custom widgets) ─────────
        self._mix_rows_container = QWidget()
        self._mix_rows_layout = QVBoxLayout(self._mix_rows_container)
        self._mix_rows_layout.setContentsMargins(0, 2, 0, 2)
        self._mix_rows_layout.setSpacing(2)
        self._mix_rows_container.setVisible(False)
        ml.addWidget(self._mix_rows_container)

        # ── Clear button ─────────────────────────────────────────────
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
        btn_row.addStretch()
        ml.addLayout(btn_row)

        outer.addWidget(mix_box)

    @staticmethod
    def _small_label(text: str) -> QLabel:
        lbl = QLabel(text)
        lbl.setStyleSheet("color: #90a4ae; font-size: 11px;")
        return lbl

    def _on_pattern_kind_changed(self, btn):
        kind = btn.property("pattern_kind") or "single"
        self._pattern_kind = kind
        idx = {"single": 0, "row": 1, "grid": 2, "circle": 3}.get(kind, 0)
        self._pattern_stack.setCurrentIndex(idx)
        # Burst quantity only applies in Single mode.
        self._qty_spin.setEnabled(kind == "single")

    def _current_pattern(self) -> dict:
        """Build the pattern dict to pass to the map-placement signal.

        When a polyculture mix is active and the mode is multi-cell
        (row/grid/circle), the pattern's params get a `polyculture` key
        carrying the resolved species list, distribution strategy, and
        effective spacing — App._enter_plant_mode uses this to override
        the primary's spacing on the map, and App._on_pattern_placed
        uses it to assign species across positions.
        """
        kind = self._pattern_kind
        overlap = self._overlap_slider.value() / 100.0
        params: dict = {}
        if kind == "row":
            params = {
                "count": self._row_count.value() or None,
                "overlap": overlap,
            }
        elif kind == "grid":
            params = {
                "rows": self._grid_rows.value() or None,
                "cols": self._grid_cols.value() or None,
                "stagger": self._grid_stagger.isChecked(),
                "overlap": overlap,
            }
        elif kind == "circle":
            params = {
                "count": self._circle_count.value() or None,
                "fill": self._circle_fill.isChecked(),
                "overlap": overlap,
            }
        else:
            return {"kind": "single"}

        poly = self.active_polyculture()
        if poly is not None:
            params["polyculture"] = poly
        return {"kind": kind, "params": params}

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
                f"Polyculture: {n} species at {ratios} — spacing "
                f"{eff:.2f} m (max). Click Place Mix on Map."
            )
        self._mix_rows_container.setVisible(True)
        self._mix_clear_btn.setEnabled(True)

        for idx, s in enumerate(self._mix_species):
            row = self._build_mix_row(idx, s)
            self._mix_rows_layout.addWidget(row)

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
            "Click to set this species' marker colour for this polyculture mix"
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
            f"Polyculture: {n} species at {ratios} — spacing "
            f"{eff:.2f} m (max). Click Place Mix on Map."
        )

    # ── Saved recipes ────────────────────────────────────────────────────

    def _refresh_recipe_combo(self):
        from src.settings import get_polyculture_recipes
        try:
            recipes = get_polyculture_recipes()
        except Exception:
            recipes = []
        self._saved_recipes = recipes

        self._recipe_combo.blockSignals(True)
        self._recipe_combo.clear()
        if not recipes:
            self._recipe_combo.addItem("(no saved mixes)")
            self._recipe_combo.setEnabled(False)
            self._recipe_delete_btn.setEnabled(False)
        else:
            self._recipe_combo.addItem("— select a saved mix to load —")
            for r in recipes:
                self._recipe_combo.addItem(r.get("name") or "(unnamed)")
            self._recipe_combo.setEnabled(True)
            self._recipe_delete_btn.setEnabled(True)
        self._recipe_combo.blockSignals(False)

    def _on_recipe_selected(self, idx: int):
        # idx 0 is the placeholder when recipes exist; ignore it.
        if not self._saved_recipes or idx < 1:
            return
        if idx - 1 >= len(self._saved_recipes):
            return
        recipe = self._saved_recipes[idx - 1]
        self._load_recipe_into_mix(recipe)

    def _load_recipe_into_mix(self, recipe: dict):
        """Rehydrate species records from the local DB, then populate mix."""
        from src.db.plants import get_plant
        loaded: list[dict] = []
        for s in recipe.get("species", []):
            pid = s.get("id")
            if not pid:
                continue
            try:
                p = get_plant(int(pid))
            except Exception:
                p = None
            if not p:
                # Plant was deleted from the local DB — fall back to the
                # cached fields stored with the recipe so the row still
                # renders (placement will skip if id is invalid).
                p = {
                    "id": pid,
                    "common_name": s.get("common_name") or "(missing plant)",
                    "spacing_meters": s.get("spacing_m") or 1.0,
                    "plant_type": s.get("plant_type") or "herb",
                    "marker_color": s.get("color") or "",
                }
            entry = dict(p)
            entry["_weight"] = int(s.get("weight") or 1)
            loaded.append(entry)
        if not loaded:
            return
        self._mix_species = loaded[: self._MIX_MAX]
        self._refresh_mix_list()

    def _on_recipe_save(self):
        from PyQt6.QtWidgets import QInputDialog
        if len(self._mix_species) < 1:
            return
        existing_names = [r.get("name") for r in self._saved_recipes]
        # Suggest a default name from the first two species.
        default_name = ""
        if len(self._mix_species) >= 2:
            default_name = (
                f"{self._mix_species[0].get('common_name','')} + "
                f"{self._mix_species[1].get('common_name','')}"
            )
            if len(self._mix_species) > 2:
                default_name += f" +{len(self._mix_species) - 2}"
        name, ok = QInputDialog.getText(
            self, "Save Polyculture Mix",
            "Name for this mix (overwrites if name already exists):",
            text=default_name,
        )
        if not ok or not name.strip():
            return
        name = name.strip()
        recipe = {
            "name": name,
            "species": [
                {
                    "id": int(s["id"]),
                    "common_name": s.get("common_name") or "",
                    "spacing_m": float(s.get("spacing_meters") or 1.0),
                    "plant_type": s.get("plant_type") or "herb",
                    "color": s.get("marker_color") or "",
                    "weight": int(s.get("_weight", 1) or 1),
                }
                for s in self._mix_species if s.get("id")
            ],
        }
        # Replace by name (case-sensitive) so re-saving updates in place.
        recipes = [r for r in self._saved_recipes if r.get("name") != name]
        recipes.append(recipe)

        from src.settings import save_polyculture_recipes
        try:
            save_polyculture_recipes(recipes)
        except Exception as exc:
            self._mix_status.setText(f"Save failed: {exc}")
            return
        self._refresh_recipe_combo()
        # Select the just-saved entry so the user gets confirmation.
        for i in range(self._recipe_combo.count()):
            if self._recipe_combo.itemText(i) == name:
                self._recipe_combo.setCurrentIndex(i)
                break

    def _on_recipe_delete(self):
        idx = self._recipe_combo.currentIndex()
        if not self._saved_recipes or idx < 1:
            return
        if idx - 1 >= len(self._saved_recipes):
            return
        target = self._saved_recipes[idx - 1]
        recipes = [r for r in self._saved_recipes if r is not target]
        from src.settings import save_polyculture_recipes
        try:
            save_polyculture_recipes(recipes)
        except Exception as exc:
            self._mix_status.setText(f"Delete failed: {exc}")
            return
        self._refresh_recipe_combo()

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
            act_mix = menu.addAction("Remove from Polyculture Mix")
            act_mix.triggered.connect(
                lambda: self._remove_from_mix(int(plant["id"]))
            )
        else:
            act_mix = menu.addAction("Add to Polyculture Mix")
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
        """Update the colour picker button to show the current plant's colour."""
        if hex_color:
            self._color_btn.setStyleSheet(
                f"QPushButton {{ background: {hex_color}; border: 1px solid #4a7a4a; "
                f"border-radius: 14px; font-size: 16px; color: {hex_color}; }}"
                f"QPushButton:hover {{ border-color: #8aca8a; }}"
            )
        else:
            self._color_btn.setStyleSheet(
                "QPushButton { background: #2e4a2e; border: 1px solid #4a7a4a; "
                "border-radius: 14px; font-size: 16px; color: #78909c; }"
                "QPushButton:hover { background: #3a5a3a; }"
            )

    # ── Permapeople tab ────────────────────────────────────────────────────────

    # ── Public API ────────────────────────────────────────────────────────────

    def set_api_keys(self, _key_id: str, _key_secret: str):
        """Compatibility no-op — Permapeople integration was removed.

        Kept so existing call-sites (app.py loads keys on startup) don't
        crash; the keys themselves are simply ignored now. The setter
        and the Settings dialog can be deleted entirely in a follow-up.
        """
        return

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
        self._refresh_placed_list()

    def on_plant_placed(self, plant_id: int, common_name: str):
        """Notify the panel that a plant was placed on the map."""
        self._placed_counts[plant_id] = self._placed_counts.get(plant_id, 0) + 1
        self._results_model.set_placed_counts(self._placed_counts)
        self._refresh_placed_list()

    def clear_placed(self):
        """Clear the placed-plants list (e.g. on New project)."""
        self._placed_counts.clear()
        self._results_model.set_placed_counts(self._placed_counts)
        self._refresh_placed_list()

    def load_placed(self, plants: list[dict]):
        """Reload placed-plants list from a loaded project."""
        self._placed_counts.clear()
        for p in plants:
            pid = p.get("plant_id", 0)
            self._placed_counts[pid] = self._placed_counts.get(pid, 0) + 1
        self._results_model.set_placed_counts(self._placed_counts)
        self._refresh_placed_list()

    def _refresh_placed_list(self):
        self._placed_list.clear()
        if not self._placed_counts:
            self._placed_count_label.setText("None placed yet")
            return

        # Look up names
        try:
            from src.db.plants import get_plant
            total = 0
            for pid, count in sorted(self._placed_counts.items()):
                p = get_plant(pid)
                name = p["common_name"] if p else f"Plant #{pid}"
                item = QListWidgetItem(f"{name}  ×{count}")
                item.setIcon(_type_icon(p["plant_type"] if p else ""))
                self._placed_list.addItem(item)
                total += count
            self._placed_count_label.setText(
                f"{total} plant{'s' if total != 1 else ''} placed"
                f" ({len(self._placed_counts)} species)"
            )
        except Exception:
            self._placed_count_label.setText(
                f"{sum(self._placed_counts.values())} plants placed"
            )


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

_PATTERN_SEG_STYLE = """
QPushButton {
    background: #1e2e1e;
    color: #c8e6c9;
    border: 1px solid #2e4a2e;
    border-radius: 3px;
    padding: 4px 6px;
    font-size: 11px;
}
QPushButton:checked {
    background: #2e7d32;
    color: #e8f5e9;
    border-color: #66bb6a;
    font-weight: bold;
}
QPushButton:hover:!checked {
    border-color: #4a7a4a;
    background: #243824;
}
"""

