"""
plant_list_view.py — the plant list every picker shows: one model, one row
delegate (Chunk 4; one list for three pickers since V3.00).

Split out of ``src/plant_panel.py`` in Chunk 4 of the strengthening plan. Since
F192 (V3.00) the Browse tab, the Plant Directory and the community builder all
show this list through ``src/plant_picker.py``.

**The card is gone.** Until V3.00 a ▶ at the right of a row expanded it into a
detail block painted underneath, at a height estimated before painting: on
Saskatoon Berry the wildlife line stopped at the seventh of 26 animals with a
trailing comma and the next line drew over it, nothing could be selected, and a
screen reader was given nothing. A plant's page now opens beside the list as
widgets (``src/species_page.py``).

**Each badge says what it is** (finding 5 of the V2.98 review): the dot names
the type, the zone chip the hardiness range, the AB chip the nativity, and
"[2×]" that two are in this design. Until V3.00 every part of a row showed one
tooltip, the plant's name. A row's accessible text carries the same facts, so a
screen reader is not left with the common name alone.

The leading-underscore names are kept for parity with the pre-split history;
they are imported by name from the panels.
"""

from __future__ import annotations

from PyQt6.QtCore import (
    Qt, QAbstractListModel, QModelIndex, QRect, QSize, QEvent,
    QRunnable, QThreadPool, pyqtSignal, QMimeData, QByteArray,
)
from PyQt6.QtGui import (
    QColor, QIcon, QPixmap, QPainter, QFont, QBrush, QPen, QFontMetrics,
)
from PyQt6.QtWidgets import (
    QStyledItemDelegate, QStyle, QStyleOptionViewItem, QToolTip,
)


# ── Type colours ──────────────────────────────────────────────────────────────
# Canonical table lives in src/member_colors (Qt-free); re-exported under
# the historical name for PlantPanel and friends.
from src.member_colors import TYPE_COLORS as _TYPE_COLORS

# ── Vocabulary labels ────────────────────────────────────────────────────────
# One vocabulary since V3.00 (src/plant_filters.py); these names are the ones
# the panels and the species page have always imported from here.
from src.plant_facets import _TYPE_LABELS
from src.plant_filters import (  # noqa: F401  (re-exported)
    AVAILABILITY_LABELS as _AVAILABILITY_LABELS,
    ROLE_LABELS as _USE_LABELS,
    SUN_LABELS as _SUN_LABELS,
    WATER_LABELS as _WATER_LABELS,
)


def labels_csv(value, label_map: dict[str, str]) -> str:
    """Render a (possibly comma-delimited) condition field as human labels.

    "full_sun,partial_shade" → "Full Sun, Partial Shade". Unknown tokens fall
    back to a title-cased form so the row never shows a raw snake_case key.
    Empty/None → "—". (V1.84)
    """
    from src.plant_conditions import condition_tokens
    parts = [label_map.get(t, t.replace("_", " ").title())
             for t in condition_tokens(value)]
    return ", ".join(parts) or "—"


# ── Shared QListWidget stylesheet ─────────────────────────────────────────────
# Used by both the placed-plants list in OnThisDesignPanel and the plant
# pickers. Kept here next to the other plant-list visual constants so a colour
# or border tweak stays in one place.
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


def _swatch_icon(color_hex: str, outline: bool = False) -> QIcon:
    """A small filled circle. ``outline`` draws a hairline ring, which the pale
    flower colours need or a white swatch is invisible on a light menu."""
    pix = QPixmap(14, 14)
    pix.fill(Qt.GlobalColor.transparent)
    p = QPainter(pix)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    p.setBrush(QBrush(QColor(color_hex)))
    p.setPen(QColor(120, 120, 120) if outline else Qt.PenStyle.NoPen)
    p.drawEllipse(1, 1, 12, 12)
    p.end()
    return QIcon(pix)


def _type_icon(plant_type: str) -> QIcon:
    """Return a small coloured circle icon for the given plant type."""
    return _swatch_icon(_TYPE_COLORS.get(plant_type, "#78909c"))


def _colour_icon(colour_key: str) -> QIcon:
    """The swatch beside a flower-colour choice (V2.48).

    A colour filter whose menu is a list of words is a colour filter you have
    to read instead of look at, which defeats the point of filtering by colour.
    Outlined, because white and cream are otherwise invisible.
    """
    from src.flower_colour import COLOUR_SWATCHES          # noqa: PLC0415
    return _swatch_icon(COLOUR_SWATCHES.get(colour_key, "#78909c"), outline=True)


# ── Plant list item roles ─────────────────────────────────────────────────────

_PLANT_ID_ROLE  = Qt.ItemDataRole.UserRole
_PLANT_OBJ_ROLE = Qt.ItemDataRole.UserRole + 1
_PLANT_PLACED_COUNT_ROLE = Qt.ItemDataRole.UserRole + 2

# MIME type carrying a dragged plant's id (drag from the results list → drop on
# the Plant Community mix, V1.87).
_PLANT_MIME = "application/x-sap-plant-id"


# ── What a row says ───────────────────────────────────────────────────────────

def type_words(plant: dict) -> str:
    """"Shrub", the word the type dot stands for."""
    ptype = plant.get("plant_type") or ""
    return _TYPE_LABELS.get(ptype, ptype.replace("_", " ").title())


def zone_words(plant: dict) -> str:
    """"Hardy in zones 2 to 7", from the same fields as the zone chip."""
    zmin = plant.get("hardiness_zone_min")
    zmax = plant.get("hardiness_zone_max")
    if zmin and zmax and str(zmin) != str(zmax):
        return f"Hardy in zones {zmin} to {zmax}"
    if zmin:
        return f"Hardy from zone {zmin}"
    return ""


def native_words(plant: dict) -> str:
    return ("Native to Alberta" if plant.get("native_to_alberta")
            else "Not native to Alberta")


def placed_words(placed: int) -> str:
    return f"{placed} in this design" if placed else ""


def row_description(plant: dict, placed: int = 0) -> str:
    """What a screen reader is given for a row: "Saskatoon Berry, Amelanchier
    alnifolia. Shrub. Native to Alberta. Hardy in zones 2 to 7. 2 in this
    design." Until V3.00 it was given the common name alone."""
    head = plant.get("common_name") or ""
    if plant.get("scientific_name"):
        head += f", {plant['scientific_name']}"
    parts = [head, type_words(plant), native_words(plant), zone_words(plant),
             placed_words(placed)]
    return ". ".join(p for p in parts if p) + "."


def _zone_badge_text(plant: dict) -> str:
    zmin = plant.get("hardiness_zone_min")
    zmax = plant.get("hardiness_zone_max")
    if zmin and zmax:
        return f"Z{zmin}–{zmax}"
    if zmin:
        return f"Z{zmin}+"
    return ""


# ── Model ─────────────────────────────────────────────────────────────────────

class PlantListModel(QAbstractListModel):
    """The rows a picker shows, how many of each are in the design, and their
    photos, fetched off the UI thread on request."""

    # Emitted (from a worker thread) when a plant's photo finishes caching, so
    # an open species page can redraw with it. Carries the plant id.
    imageReady = pyqtSignal(int)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._plants: list[dict] = []
        self._placed_counts: dict[int, int] = {}
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
        if role == Qt.ItemDataRole.DisplayRole:
            return plant.get("common_name", "")
        if role == Qt.ItemDataRole.AccessibleTextRole:
            return row_description(
                plant, self._placed_counts.get(plant.get("id"), 0))
        if role == Qt.ItemDataRole.ToolTipRole:
            return f"{plant.get('common_name','')} ({plant.get('scientific_name','—')})"
        return None

    # Drag support (drag a plant onto the mix, V1.87) --------------------

    def flags(self, index: QModelIndex):
        base = super().flags(index)
        if index.isValid():
            return base | Qt.ItemFlag.ItemIsDragEnabled
        return base

    def mimeTypes(self) -> list[str]:
        return [_PLANT_MIME]

    def supportedDragActions(self):
        return Qt.DropAction.CopyAction

    def mimeData(self, indexes):
        md = QMimeData()
        for idx in indexes:
            if idx.isValid():
                pid = self._plants[idx.row()].get("id")
                if pid is not None:
                    md.setData(_PLANT_MIME, QByteArray(str(int(pid)).encode()))
                    break
        return md

    # Public API ---------------------------------------------------------

    def set_plants(self, plants: list[dict]):
        """Swap the result set."""
        self.beginResetModel()
        self._plants = list(plants)
        self.endResetModel()

    def plants(self) -> list[dict]:
        return list(self._plants)

    def placed_count(self, plant_id) -> int:
        return int(self._placed_counts.get(plant_id, 0))

    def set_placed_counts(self, counts: dict[int, int]):
        self._placed_counts = dict(counts)
        if self._plants:
            top = self.index(0)
            bot = self.index(len(self._plants) - 1)
            self.dataChanged.emit(top, bot, [_PLANT_PLACED_COUNT_ROLE])

    def warm_photo(self, plant: dict):
        """Start caching one plant's photo now, for the species page.

        Public since V2.41: the Directory's page is a consumer that never
        expanded a row, which was the only trigger, so its photo said "not
        downloaded yet" for the whole session.
        """
        self._prefetch_image(plant)

    def _prefetch_image(self, plant: dict):
        """Kick a one-time background fetch of a plant's photo into the local
        cache (I1). Off the UI thread; emits ``imageReady`` when done. No-op
        without a URL, when already cached, or if Qt threading is
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
        # Bind the OWNER, not its bound signal. A bound signal keeps no strong
        # claim on the object's C++ lifetime, so a fetch that finishes after the
        # model has gone (close the panel, switch tabs, end a test) emits into
        # freed memory — a hard crash from a nicety. `emit_if_alive` checks the
        # wrapper before touching it.
        owner = self

        class _FetchTask(QRunnable):
            def run(self):
                try:
                    from src.image_cache import resolve_image
                    from src.qt_safety import emit_if_alive
                    if resolve_image(url, attribution, license_str):
                        emit_if_alive(owner, "imageReady", pid)
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


# ── Delegate ──────────────────────────────────────────────────────────────────
#
# One row per plant: ~26 px, or two lines (~44 px) when a long common name
# cannot fit beside its badges, so the bold name is always whole.

_ROW_H_COMPACT  = 26
_ROW_H_WRAPPED  = 44    # two-line variant for very long common names
_ZONE_BADGE_W   = 56
_NATIVE_BADGE_W = 18    # square AB-leaf badge


class PlantRowDelegate(QStyledItemDelegate):
    """Paints one row (left → right):

      · plant-type dot
      · common name (bold) and the placed count ([N×]) · scientific name
      · zone badge (Z3–5), dropped when the name needs the room
      · native-AB chip ("AB" when native, "–" otherwise)

    Every part has its own tooltip (:meth:`helpEvent`).
    """

    DOT_W = 14
    LEFT_PAD = 6
    RIGHT_PAD = 6

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

    # Geometry -----------------------------------------------------------

    def _compact_height_for(self, plant: dict, panel_w: int) -> int:
        """1 line (26 px) or 2 (44 px). A long common name ("White-grained
        Mountain Rice Grass") that cannot fit beside the AB badge on one line
        takes the wrapped layout, so the user always sees it in full.

        Slack is generous (32 px) so the wrap kicks in before Qt clips on
        Windows DPI scaling, whose font metrics often report 5–15 px less than
        the rendered ink.
        """
        common = plant.get("common_name") or ""
        if not common:
            return _ROW_H_COMPACT
        fm_b = QFontMetrics(self._bold_font)
        common_render = max(
            fm_b.horizontalAdvance(common),
            fm_b.boundingRect(common).width(),
        ) + 32
        lean_budget = max(40, panel_w - self.LEFT_PAD - self.DOT_W
                          - (_NATIVE_BADGE_W + self.RIGHT_PAD + 8))
        return _ROW_H_COMPACT if common_render <= lean_budget else _ROW_H_WRAPPED

    def _layout(self, plant: dict, rect: QRect, placed: int) -> dict:
        """Where each part of the row goes. Painting and the tooltips both read
        this, so they cannot disagree about where a badge is."""
        compact_h = self._compact_height_for(plant, rect.width())
        wrapped = compact_h == _ROW_H_WRAPPED
        compact = QRect(rect.left(), rect.top(), rect.width(), compact_h)
        line_h = compact_h // 2 if wrapped else compact_h

        dot_x = compact.left() + self.LEFT_PAD
        dot_centre_y = compact.top() + (line_h // 2 if wrapped
                                        else compact_h // 2)
        dot = QRect(dot_x, dot_centre_y - 5, 10, 10)
        x = dot_x + self.DOT_W

        native = QRect(compact.right() - self.RIGHT_PAD - _NATIVE_BADGE_W,
                       compact.bottom() - line_h + (line_h - 14) // 2,
                       _NATIVE_BADGE_W, 14)
        zone_rect = QRect(native.left() - 4 - _ZONE_BADGE_W,
                          compact.bottom() - line_h + (line_h - 16) // 2,
                          _ZONE_BADGE_W, 16)
        right_full = compact.right() - zone_rect.left() + 6
        right_lean = compact.right() - native.left() + 6

        common = plant.get("common_name", "")
        count_badge = f"  [{placed}×]" if placed > 0 else ""
        common_text = common + count_badge
        fm_b = QFontMetrics(self._bold_font)
        # max(advance, boundingRect) + 24 px slack for the right side bearing:
        # Windows bold glyphs often ink past the advance and Qt clips at the
        # rect's edge. Must be ≤ the wrap decision's 32 px slack.
        common_render = max(fm_b.horizontalAdvance(common_text),
                            fm_b.boundingRect(common_text).width()) + 24

        if wrapped:
            name_w_max = max(40, compact.right() - x - self.RIGHT_PAD)
            name_w = min(common_render, name_w_max)
            name = QRect(x, compact.top(), name_w, line_h)
            show_zone = True
            sci = QRect(x, compact.top() + line_h,
                        max(0, compact.right() - right_full - x), line_h)
        else:
            max_full = max(40, compact.right() - x - right_full)
            max_lean = max(40, compact.right() - x - right_lean)
            show_zone = common_render <= max_full
            text_max = max_full if show_zone else max_lean
            name_w = min(common_render, text_max)
            name = QRect(x, compact.top(), name_w, compact_h)
            after = x + name_w + 6
            right = right_full if show_zone else right_lean
            sci = QRect(after, compact.top(),
                        max(0, compact.right() - right - after), compact_h)
        return {
            "compact": compact, "wrapped": wrapped, "line_h": line_h,
            "dot": dot, "name": name, "name_text": common_text,
            "elide": common_render > name.width(), "sci": sci,
            "zone": zone_rect if (show_zone and _zone_badge_text(plant))
            else None,
            "native": native,
        }

    def sizeHint(self, option: QStyleOptionViewItem, index: QModelIndex) -> QSize:
        plant = index.data(_PLANT_OBJ_ROLE) or {}
        view = self.parent()
        panel_w = (view.viewport().width() if view else option.rect.width()) or 280
        return QSize(0, self._compact_height_for(plant, panel_w))

    # Painting -----------------------------------------------------------

    def paint(self, painter: QPainter, option: QStyleOptionViewItem, index: QModelIndex):
        plant = index.data(_PLANT_OBJ_ROLE) or {}
        placed = index.data(_PLANT_PLACED_COUNT_ROLE) or 0
        rect = option.rect
        lay = self._layout(plant, rect, placed)

        painter.save()
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)

        selected = bool(option.state & QStyle.StateFlag.State_Selected)
        painter.fillRect(rect, QColor("#2e5a2e") if selected else QColor("#1a2a1a"))
        painter.setPen(QPen(QColor("#1f341f"), 1))
        painter.drawLine(rect.left(), rect.bottom(), rect.right(), rect.bottom())

        # Plant-type dot.
        painter.setBrush(QColor(_TYPE_COLORS.get(plant.get("plant_type", ""), "#78909c")))
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawEllipse(lay["dot"])

        # Common name (+ placed count).
        painter.setFont(self._bold_font)
        fm_b = QFontMetrics(self._bold_font)
        name = lay["name"]
        text = lay["name_text"]
        if lay["elide"]:
            text = fm_b.elidedText(text, Qt.TextElideMode.ElideRight, name.width())
        painter.setPen(QColor("#e8f5e9") if selected else QColor("#c8e6c9"))
        painter.drawText(name, int(Qt.AlignmentFlag.AlignVCenter
                                   | Qt.AlignmentFlag.AlignLeft), text)

        # Scientific name.
        sci = plant.get("scientific_name") or ""
        if sci and lay["sci"].width() > 12:
            painter.setFont(self._sci_font)
            painter.setPen(QColor("#90a4ae"))
            fm_s = QFontMetrics(self._sci_font)
            painter.drawText(
                lay["sci"], int(Qt.AlignmentFlag.AlignVCenter
                                | Qt.AlignmentFlag.AlignLeft),
                fm_s.elidedText(sci, Qt.TextElideMode.ElideRight,
                                lay["sci"].width()))

        # Zone badge — only when there was room for the name beside it.
        if lay["zone"] is not None:
            painter.setBrush(QColor("#37474f"))
            painter.setPen(QPen(QColor("#546e7a"), 1))
            painter.drawRoundedRect(lay["zone"], 3, 3)
            painter.setPen(QColor("#cfd8dc"))
            painter.setFont(self._small_font)
            painter.drawText(lay["zone"], int(Qt.AlignmentFlag.AlignCenter),
                             _zone_badge_text(plant))

        # Native-AB badge: "AB" if native, an en dash otherwise, so it reads
        # without the colour.
        is_native = bool(plant.get("native_to_alberta"))
        painter.setBrush(QColor(self.AB_NATIVE_BG if is_native else self.AB_OTHER_BG))
        painter.setPen(QPen(QColor("#0d160d"), 0.5))
        painter.drawRoundedRect(lay["native"], 3, 3)
        painter.setPen(QColor(self.AB_NATIVE_FG if is_native else self.AB_OTHER_FG))
        painter.setFont(self._small_font)
        painter.drawText(lay["native"], int(Qt.AlignmentFlag.AlignCenter),
                         "AB" if is_native else "–")
        painter.restore()

    # Tooltips -----------------------------------------------------------

    def tooltip_at(self, plant: dict, rect: QRect, placed: int, pos) -> str:
        """The tooltip for whatever part of the row is under ``pos``."""
        lay = self._layout(plant, rect, placed)
        if lay["dot"].adjusted(-3, -3, 3, 3).contains(pos):
            return type_words(plant)
        if lay["zone"] is not None and lay["zone"].contains(pos):
            return zone_words(plant)
        if lay["native"].contains(pos):
            return native_words(plant)
        text = (f"{plant.get('common_name', '')} "
                f"({plant.get('scientific_name') or '—'})")
        if placed:
            text += f". {placed_words(placed)}"
        return text

    def helpEvent(self, event, view, option, index):
        if event is None or event.type() != QEvent.Type.ToolTip:
            return super().helpEvent(event, view, option, index)
        plant = index.data(_PLANT_OBJ_ROLE) or {}
        placed = index.data(_PLANT_PLACED_COUNT_ROLE) or 0
        QToolTip.showText(event.globalPos(),
                          self.tooltip_at(plant, option.rect, placed, event.pos()),
                          view)
        return True
