"""
plant_directory_window.py — the plant directory as a room you can stand in
(F90, V2.41).

Design principle P5 — see docs/DESIGN_PHILOSOPHY.md.

A top-level window, opened from the start screen before any design exists and
from ``View →`` once one does. It follows the singleton shape
``scene3d_window.open_3d_view`` and ``snapshot_window.open_snapshot_view``
already use, with one difference: ``main`` is **optional**, because the whole
point is that you can read the catalogue without owning a design.

Two halves:

  * **Left — the list.** ``PlantListModel`` + ``PlantRowDelegate``, borrowed
    whole from the design-side browser. Virtualized, lazily photo-loading, and
    already able to draw a species row better than anything written fresh here
    would. Nothing in ``plant_panel.py`` is touched — it sits at exactly its
    1600-line ceiling, and the browser's job (get a plant onto the ground) is
    not this window's job anyway.
  * **Right — the species page.** A widget tree, not painted text: the
    delegate's expand-in-place block is drawn with QPainter, so its text cannot
    be selected and its relationships cannot be clicked. Fine for a picker,
    wrong for a reference work.

The facet strip is built by looping :data:`src.plant_directory.FACETS` and
:data:`TOGGLES`, which is how the sixteen ``search_plants`` filters that no UI
ever exposed — keystone, specialist support, pet safety, price, commonness —
arrive without a line of bespoke wiring each.
"""

from __future__ import annotations

from typing import Optional

from PyQt6.QtCore import Qt, QSize
from PyQt6.QtWidgets import (
    QHBoxLayout, QLabel, QLineEdit, QListView, QPushButton, QScrollArea,
    QSplitter, QVBoxLayout, QWidget,
)

from src import plant_directory as pd
from src.filter_widgets import TOGGLE_STYLE, make_multi_combo
from src.plant_list_view import (_RESULTS_LIST_STYLE, PlantListModel,
                                 PlantRowDelegate)
from src.ui_style import BASE_SURFACE, BTN_SECONDARY

_HEAD = "color: #e8f5e9; font-size: 17px; font-weight: bold;"
_SCI = "color: #8fb98f; font-size: 12px; font-style: italic;"
_LABEL = "color: #7f9c82; font-size: 10px; text-transform: uppercase;"
_BODY = "color: #c8e6c9; font-size: 12px;"
_DIM = "color: #90a4ae; font-size: 11px;"


class PlantDirectoryWindow(QWidget):
    """Browse the catalogue. Constructs with no MainWindow."""

    def __init__(self, main=None):
        super().__init__(None)                      # top-level window
        self._main = main
        self._criteria: dict = {}
        self._rows: list[dict] = []
        self._shown: dict = {}
        self.setWindowTitle("Plant Directory")
        self.setMinimumSize(QSize(1000, 640))
        self.setStyleSheet(BASE_SURFACE)

        outer = QVBoxLayout(self)
        outer.setContentsMargins(12, 12, 12, 12)
        outer.setSpacing(8)
        self._build_filters(outer)

        split = QSplitter(Qt.Orientation.Horizontal)
        split.addWidget(self._build_list())
        split.addWidget(self._build_species_pane())
        split.setSizes([420, 580])
        split.setStretchFactor(1, 1)
        outer.addWidget(split, 1)

        self.refresh()

    # ── Filters ─────────────────────────────────────────────────────────────

    def _build_filters(self, outer):
        self._search = QLineEdit()
        self._search.setPlaceholderText(
            "Search 400+ native species by name, or by what they do…")
        self._search.setClearButtonEnabled(True)
        self._search.textChanged.connect(self._on_search)
        self._search.setStyleSheet(
            "QLineEdit { background: #16241a; border: 1px solid #2e4a2e; "
            "border-radius: 4px; padding: 6px 8px; color: #c8e6c9; }")
        outer.addWidget(self._search)

        self._combos: dict = {}
        row = QHBoxLayout()
        row.setSpacing(6)
        for key, label, _param, values in pd.FACETS:
            combo = make_multi_combo(
                label, values, on_change=lambda k=key: self._on_facet(k))
            self._combos[key] = combo
            row.addWidget(combo)
        outer.addLayout(row)

        # The toggles wrap: there are thirteen and most have never had a
        # control before, so they get room rather than a "more filters" drawer
        # that would hide them again.
        self._toggles: dict = {}
        chips = _FlowRow()
        for key, label, _param, tip in pd.TOGGLES:
            btn = QPushButton(label)
            btn.setCheckable(True)
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.setToolTip(tip)
            btn.setStyleSheet(TOGGLE_STYLE)
            btn.toggled.connect(lambda _on, k=key: self._on_toggle(k))
            self._toggles[key] = btn
            chips.add(btn)
        outer.addWidget(chips)

    def _on_search(self, text: str):
        self._criteria["query"] = text
        self.refresh()

    def _on_facet(self, key: str):
        self._criteria[key] = self._combos[key].checked_keys()
        self.refresh()

    def _on_toggle(self, key: str):
        self._criteria[key] = self._toggles[key].isChecked()
        self.refresh()

    # ── The list ────────────────────────────────────────────────────────────

    def _build_list(self) -> QWidget:
        box = QWidget()
        col = QVBoxLayout(box)
        col.setContentsMargins(0, 0, 6, 0)
        col.setSpacing(6)

        self._count = QLabel("")
        self._count.setStyleSheet(_DIM)
        col.addWidget(self._count)

        self._model = PlantListModel(self)
        # The model fetches row photos on a worker thread and announces each
        # one. Without this the species pane would say "not downloaded yet"
        # for the whole session even after the picture landed a second later.
        self._model.imageReady.connect(self._on_image_ready)
        self._list = QListView()
        self._delegate = PlantRowDelegate(self._list)
        self._list.setModel(self._model)
        self._list.setItemDelegate(self._delegate)
        self._list.setSelectionMode(QListView.SelectionMode.SingleSelection)
        self._list.setUniformItemSizes(False)
        self._list.setVerticalScrollMode(QListView.ScrollMode.ScrollPerPixel)
        self._list.setStyleSheet(_RESULTS_LIST_STYLE)
        self._list.clicked.connect(self._on_row)
        col.addWidget(self._list, 1)

        quiz = QPushButton("Quiz me on these")
        quiz.setToolTip(
            "Field Study over the species you have filtered to — identify "
            "them, trace a specialist to its host. Retrieval practice is how "
            "any of this sticks.")
        quiz.setStyleSheet(BTN_SECONDARY)
        quiz.clicked.connect(self._open_quiz)
        col.addWidget(quiz)
        return box

    def _on_row(self, index):
        row = index.row()
        if 0 <= row < len(self._rows):
            self._show_species(self._rows[row])

    def _on_image_ready(self, plant_id: int):
        """Redraw the open species page when *its* photo finishes caching."""
        if self._shown and int(plant_id) == int(self._shown.get("id") or 0):
            self._show_species(self._shown)

    # ── The species page ────────────────────────────────────────────────────

    def _build_species_pane(self) -> QWidget:
        self._pane = QWidget()
        self._pane_col = QVBoxLayout(self._pane)
        self._pane_col.setContentsMargins(14, 4, 8, 8)
        self._pane_col.setSpacing(8)
        self._pane_col.addStretch()

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setWidget(self._pane)
        scroll.setFrameShape(QScrollArea.Shape.NoFrame)
        self._empty_species()
        return scroll

    def _clear_pane(self):
        while self._pane_col.count():
            item = self._pane_col.takeAt(0)
            w = item.widget()
            if w is not None:
                w.setParent(None)

    def _empty_species(self):
        self._shown = {}
        self._clear_pane()
        hint = QLabel("Pick a species to read about it.")
        hint.setStyleSheet(_DIM)
        self._pane_col.addWidget(hint)
        self._pane_col.addStretch()

    def _show_species(self, row: dict):
        entry = pd.species_entry(int(row.get("id") or 0))
        if not entry:
            self._empty_species()
            return
        self._shown = row
        # The list only warms a photo when a row is *expanded*, and nothing
        # here expands anything. Ask for this one now; `imageReady` brings the
        # page back to redraw it.
        self._model.warm_photo(row)
        self._clear_pane()
        add = self._pane_col.addWidget

        name = QLabel(entry["name"])
        name.setStyleSheet(_HEAD)
        name.setWordWrap(True)
        add(name)
        sci = QLabel(entry["scientific_name"])
        sci.setStyleSheet(_SCI)
        sci.setTextInteractionFlags(
            Qt.TextInteractionFlag.TextSelectableByMouse)
        add(sci)

        add(self._photo_block(entry))

        if entry["badges"]:
            self._section("Why it matters", " · ".join(entry["badges"]))
        self._section("Conditions", " · ".join(
            p for p in (_conditions(entry), entry["soil_ph"], entry["zones"])
            if p))
        self._section("Size", " · ".join(p for p in (
            _metres(entry["mature_height_m"], "tall"),
            _metres(entry["mature_canopy_m"], "wide"),
            _years(entry["years_to_maturity"]),
            _metres(entry["spacing_m"], "apart")) if p))
        self._section("Season", " · ".join(p for p in (
            f"blooms {entry['bloom']}" if entry["bloom"] else "",
            _colour_word(entry["bloom_color"], "flowers"),
            f"fruits {entry['fruit']}" if entry["fruit"] else "",
            _colour_word(entry["fruit_color"], "fruit")) if p))
        if entry["morphology"]:
            self._section("What it looks like", " · ".join(entry["morphology"]))
        self._range_block(entry)
        self._wildlife_block(entry)
        self._companion_block(entry)
        if entry["edible_parts"]:
            self._section("Edible parts", entry["edible_parts"])
        self._sourcing_block(entry)
        if entry["safety"]:
            self._section("Safety", " · ".join(entry["safety"]))
        if entry["notes"]:
            self._section("Notes", entry["notes"])
        if entry["provenance"]:
            self._section("Where these numbers came from",
                          " · ".join(entry["provenance"]), dim=True)
        self._pane_col.addStretch()

    def _section(self, heading: str, body: str, *, dim: bool = False):
        if not (body or "").strip():
            return
        if heading:
            head = QLabel(heading)
            head.setStyleSheet(_LABEL)
            self._pane_col.addWidget(head)
        text = QLabel(body)
        text.setWordWrap(True)
        text.setStyleSheet(_DIM if dim else _BODY)
        text.setTextInteractionFlags(
            Qt.TextInteractionFlag.TextSelectableByMouse)
        self._pane_col.addWidget(text)

    def _photo_block(self, entry: dict) -> QWidget:
        """The photograph, or an honest line about not having one.

        323 of 434 species carry a photo and the named-slot table ships empty,
        so roughly a quarter of this catalogue has no picture. Saying so beats
        an empty frame, and it is also the work list.
        """
        from src.image_cache import credit_line, get_cached_image
        box = QLabel()
        photos = entry.get("photos") or []
        url = photos[0].get("url") if photos else ""
        path = get_cached_image(url) if url else None
        if path:
            from PyQt6.QtGui import QPixmap
            pix = QPixmap(path)
            if not pix.isNull():
                box.setPixmap(pix.scaledToWidth(
                    320, Qt.TransformationMode.SmoothTransformation))
                credit = credit_line(photos[0].get("attribution") or "",
                                     photos[0].get("license") or "")
                box.setToolTip(credit or "")
                return box
        box.setText("No photograph of this species yet."
                    if not url else "Photograph not downloaded yet.")
        box.setStyleSheet(_DIM)
        return box

    def _range_block(self, entry: dict):
        """Where it has been recorded — **with the count and the confidence**.

        A region seen 242 times and one seen 5 times are different claims, and
        a directory that prints them identically is inventing certainty (P9).
        """
        rows = entry.get("ranges") or []
        if not rows:
            return
        bits = []
        for r in rows[:4]:
            if r["occurrences"]:
                bits.append(f"{r['name']} ({r['occurrences']} records, "
                            f"{r['confidence']} confidence)")
            else:
                bits.append(f"{r['name']} (no occurrence data)")
        self._section("Found in", "\n".join(bits))
        # `source` has been on these rows since schema v59 and was never shown.
        # An occurrence count without its provenance is a number the reader has
        # no way to weigh.
        origins = []
        for r in rows:
            src = (r.get("source") or "").strip()
            if src and src not in origins:
                origins.append(src)
        if origins:
            self._section("", "Range data: " + "; ".join(origins), dim=True)

    def _wildlife_block(self, entry: dict):
        w = entry.get("wildlife") or {}
        if not w.get("total"):
            self._section("Wildlife", "No documented animal relationships yet "
                                      "— which means unrecorded, not absent.",
                          dim=True)
            return
        lines = []
        for group in w["groups"]:
            names = ", ".join(
                (i["name"] + (" ⚑" if i["specialist"] else ""))
                for i in group["items"][:8])
            more = len(group["items"]) - 8
            lines.append(f"{group['how']}: {names}"
                         + (f" +{more} more" if more > 0 else ""))
        head = f"Feeds or shelters {w['total']} documented species"
        if w["specialists"]:
            head += (f" — {w['specialists']} of them "
                     f"{'is a specialist' if w['specialists'] == 1 else 'are specialists'} "
                     f"with nowhere else to go (⚑)")
        self._section(head, "\n".join(lines))
        self._citation_block(w)

    def _citation_block(self, wildlife: dict):
        """Where the wildlife relationships came from.

        Every one of these edges has always carried a real citation, and until
        V2.42 no screen in the app displayed one — the field reached this view
        model and was dropped here. A user could not tell a sourced record from
        an invention, which makes well-sourced data worth nothing to them.
        """
        from src.citations import (                          # noqa: PLC0415
            format_citation, is_placeholder)
        keys: list = []
        unattributed = 0
        for group in wildlife.get("groups") or []:
            for item in group.get("items") or []:
                for key in (k.strip() for k in
                            (item.get("source") or "").split(",")):
                    if not key:
                        continue
                    if is_placeholder(key):
                        unattributed += 1
                    elif key not in keys:
                        keys.append(key)
        if not keys and not unattributed:
            return
        lines = [f"· {format_citation(k)}" for k in keys]
        if unattributed:
            lines.append(
                f"· {unattributed} of these relationships were seeded without "
                "naming a specific work, and are not yet attributable.")
        self._section("Where these relationships came from",
                      "\n".join(lines), dim=True)

    def _companion_block(self, entry: dict):
        groups = (entry.get("relationships") or {}).get("groups") or []
        bits = []
        for g in groups:
            if g.get("group") != "companion":
                continue
            names = ", ".join(i["name"] for i in g["items"][:8] if i["name"])
            if names:
                bits.append(f"{g['label']}: {names}")
        self._section("Grows with", "\n".join(bits))

    def _sourcing_block(self, entry: dict):
        s = entry.get("sourcing") or {}
        bits = [s.get("price", ""), s.get("availability", "")]
        self._section("Where to get it",
                      " · ".join(b for b in bits if b))
        if s.get("notes"):
            self._section("", s["notes"], dim=True)

    # ── Actions ─────────────────────────────────────────────────────────────

    def _open_quiz(self):
        """Field Study over the current result set.

        ``field_study.generate_quiz`` already accepts an arbitrary plant list —
        it was written design-aware but never required a design — so studying a
        filter and then being tested on it costs nothing but this window.
        """
        from src.field_study_widget import FieldStudyWidget
        rows = list(self._rows)
        win = FieldStudyWidget(plants_provider=lambda: rows)
        win.setWindowTitle(f"Field Study — {len(rows)} species")
        win.setStyleSheet(BASE_SURFACE)
        win.setMinimumSize(QSize(560, 520))
        win.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose)
        win.show()
        # Held so Python doesn't collect the window the moment this returns.
        self._quiz_window = win

    # ── Contents ────────────────────────────────────────────────────────────

    def refresh(self):
        self._rows = pd.search(self._criteria)
        self._model.set_plants(self._rows)
        total = len(self._rows)
        self._count.setText(
            f"{total} species" if total != 1 else "1 species")
        if not total:
            self._empty_species()

    def preset(self, criteria: dict):
        """Open showing exactly this filter — the start screen's in-bloom line
        uses it.

        **Replaces** rather than merges. The window is a singleton, so merging
        would silently AND today's request onto whatever the user had left in
        the box last time and show them a number that matches nothing they
        asked for.
        """
        self._criteria = dict(criteria or {})
        self._search.blockSignals(True)
        self._search.setText(self._criteria.get("query") or "")
        self._search.blockSignals(False)
        for key, combo in self._combos.items():
            combo.set_checked_keys(
                [str(v) for v in (self._criteria.get(key) or [])])
        for key, btn in self._toggles.items():
            btn.blockSignals(True)
            btn.setChecked(bool(self._criteria.get(key)))
            btn.blockSignals(False)
        self.refresh()


class _FlowRow(QWidget):
    """A row of chips that wraps. Thirteen toggles do not fit on one line at
    any sane window width, and hiding them behind a "more filters" button
    would put them back where they have been all along — present, working and
    invisible."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._col = QVBoxLayout(self)
        self._col.setContentsMargins(0, 0, 0, 0)
        self._col.setSpacing(4)
        self._row = None
        self._n = 0

    def add(self, widget: QWidget, per_row: int = 7):
        if self._row is None or self._n >= per_row:
            self._row = QHBoxLayout()
            self._row.setSpacing(5)
            self._row.addStretch()
            self._col.addLayout(self._row)
            self._n = 0
        self._row.insertWidget(self._n, widget)
        self._n += 1


def _conditions(entry: dict) -> str:
    """Sun and water as words. The raw fields are comma-delimited snake_case
    ("full_sun,partial_shade"), and `labels_csv` is the existing renderer the
    design-side rows already use — so the two surfaces cannot disagree about
    what a condition is called."""
    from src.plant_list_view import _SUN_LABELS, _WATER_LABELS, labels_csv
    sun = labels_csv(entry.get("sun", "").replace(" ", "_"), _SUN_LABELS)
    water = labels_csv(entry.get("water", ""), _WATER_LABELS)
    out = []
    if sun and sun != "—":
        out.append(sun)
    if water and water != "—":
        out.append(f"{water} water")
    return " · ".join(out)


def _colour_word(value: str, what: str) -> str:
    """Colour fields hold either a name or a hex triplet — the hex drives the
    3D bloom and is meaningless on a page. Print names, drop codes."""
    text = (value or "").strip()
    if not text or text.startswith("#"):
        return ""
    return f"{text} {what}"


def _metres(value, word: str) -> str:
    try:
        v = float(value or 0)
    except (TypeError, ValueError):
        return ""
    return f"{v:g} m {word}" if v else ""


def _years(value) -> str:
    try:
        v = int(value or 0)
    except (TypeError, ValueError):
        return ""
    return f"mature in {v} year{'s' if v != 1 else ''}" if v else ""


def open_plant_directory(main=None,
                         criteria: Optional[dict] = None
                         ) -> PlantDirectoryWindow:
    """Show (or raise) the directory. ``main`` is optional — the start screen
    opens this with no MainWindow in existence, which is the point.

    The singleton is kept on ``main`` when there is one (the pattern
    ``open_3d_view`` and ``open_snapshot_view`` use, so no new MainWindow
    method is needed and the architecture guard's method ceiling stays
    meaningful) and in a module global when there is not.
    """
    global _WINDOW
    win = getattr(main, "_plant_directory_window", None) if main else _WINDOW
    if win is None or not _alive(win):
        win = PlantDirectoryWindow(main)
        if main is not None:
            main._plant_directory_window = win
        else:
            _WINDOW = win
    if criteria:
        win.preset(criteria)
    win.show()
    win.raise_()
    win.activateWindow()
    return win


#: Holds the window when it was opened without a MainWindow to hang it on.
_WINDOW: Optional[PlantDirectoryWindow] = None


def _alive(win) -> bool:
    from src.qt_safety import is_alive
    return is_alive(win)
