"""
species_page.py — one species, as a page you can read, select and hear
(F192, V3.00).

Design principle P5 — see docs/DESIGN_PHILOSOPHY.md.

The Plant Directory's page, moved out of its window so that two places show it:
the Directory, beside its list, and the Browse tab, beside the side panel over
the map (``src/species_flyout.py``). Until V3.00 Browse had a card painted into
the list row instead, drawn with QPainter at a height estimated in advance:
Saskatoon Berry's 26 animals stopped at the seventh with a trailing comma and
the next line drew over them, nothing on it could be selected or copied, and a
screen reader was given nothing at all. Every line here is a label.

What the card had and the page lacked, it has now: the plant's roles in words
(the tags the Role filter matches), how many are in this design, and when it
flowers and fruits, drawn as a twelve-month bar whose accessible name is the
sentence. The card's planting-calendar strip is not carried over as a strip:
98% of its cells said "growing" or "harvest", which restate the bloom and fruit
windows. The months that say something else are a line of text.

**P12:** this shows only what the data model holds — horticultural and use
tags, edible parts, documented ecological relationships. Nothing
ethnobotanical is added and no field is relabelled to imply any.
"""

from __future__ import annotations

import html
from typing import Callable, Optional

from PyQt6.QtCore import QSize, Qt, pyqtSignal
from PyQt6.QtGui import QColor, QFont, QPainter, QPen
from PyQt6.QtWidgets import (
    QFrame, QHBoxLayout, QLabel, QPushButton, QScrollArea, QToolButton,
    QVBoxLayout, QWidget,
)

_HEAD = "color: #e8f5e9; font-size: 18px; font-weight: bold;"
_SCI = "color: #8fb98f; font-size: 13px; font-style: italic;"
_LABEL = "color: #7f9c82; font-size: 12px; font-weight: bold;"
_BODY = "color: #c8e6c9; font-size: 13px;"
_DIM = "color: #90a4ae; font-size: 12px;"
_LINK = "color: #ffe082;"

#: Wildlife names shown per group before "and N more". Boreal Yarrow has 296
#: documented animals; a page that lists them all opens on a wall of names.
_FIRST = 8

#: Calendar tasks worth a line. "growing" and "harvest" restate the bloom and
#: fruit windows above them, so only harvest of something edible is said.
_TASKS = (("start_indoors", "Start indoors"), ("direct_sow", "Sow outdoors"),
          ("transplant", "Plant out"), ("pruning", "Prune"))

_MONTHS = ("January", "February", "March", "April", "May", "June", "July",
           "August", "September", "October", "November", "December")


class SpeciesPage(QWidget):
    """One species: a fixed head (name, and Place when ``actions``) over a
    scrolling body. ``show_plant(row)`` fills it from
    :func:`src.plant_directory.species_entry`."""

    #: The page's Place button: place this plant (the row given to show_plant).
    place_requested = pyqtSignal(dict)
    #: The page's Add to mix button.
    mix_requested = pyqtSignal(dict)
    #: The ✕, or Esc while the page has focus.
    close_requested = pyqtSignal()

    def __init__(self, parent=None, *, actions: bool = False,
                 closable: bool = False,
                 entry_fn: Optional[Callable] = None,
                 photo_warmer: Optional[Callable] = None):
        super().__init__(parent)
        self.setObjectName("speciesPage")
        self._entry_fn = entry_fn
        self._photo_warmer = photo_warmer
        self._row: dict = {}
        self._entry: dict = {}
        self._placed = 0
        self._in_mix = False

        outer = QVBoxLayout(self)
        outer.setContentsMargins(14, 10, 10, 8)
        outer.setSpacing(6)

        head = QHBoxLayout()
        head.setSpacing(6)
        names = QVBoxLayout()
        names.setSpacing(2)
        self._name = QLabel("")
        self._name.setStyleSheet(_HEAD)
        self._name.setWordWrap(True)
        self._name.setTextInteractionFlags(
            Qt.TextInteractionFlag.TextSelectableByMouse)
        names.addWidget(self._name)
        self._sci = QLabel("")
        self._sci.setStyleSheet(_SCI)
        self._sci.setWordWrap(True)
        self._sci.setTextInteractionFlags(
            Qt.TextInteractionFlag.TextSelectableByMouse)
        names.addWidget(self._sci)
        self._placed_line = QLabel("")
        self._placed_line.setStyleSheet(_DIM)
        self._placed_line.setTextInteractionFlags(
            Qt.TextInteractionFlag.TextSelectableByMouse)
        names.addWidget(self._placed_line)
        head.addLayout(names, 1)
        self._close = None
        if closable:
            self._close = QToolButton()
            self._close.setText("✕")
            self._close.setObjectName("speciesPageClose")
            self._close.setAccessibleName("Close the plant page")
            self._close.setToolTip("Close (Esc)")
            self._close.setCursor(Qt.CursorShape.PointingHandCursor)
            self._close.setFixedSize(28, 28)
            self._close.setStyleSheet(
                "QToolButton { color: #c8e6c9; background: transparent; "
                "border: 1px solid #2e4a2e; border-radius: 4px; "
                "font-size: 14px; }"
                "QToolButton:hover { border-color: #66bb6a; }"
                "QToolButton:focus { border: 2px solid #ffe082; }")
            self._close.clicked.connect(self.close_requested)
            head.addWidget(self._close, 0, Qt.AlignmentFlag.AlignTop)
        self._head = QWidget()
        self._head.setLayout(head)
        outer.addWidget(self._head)

        self._place_btn = None
        self._mix_btn = None
        if actions:
            from src.place_action import PlaceButton
            row = QHBoxLayout()
            row.setSpacing(6)
            self._place_btn = PlaceButton("plant")
            self._place_btn.clicked.connect(
                lambda: self._row and self.place_requested.emit(self._row))
            row.addWidget(self._place_btn, 1)
            self._mix_btn = QPushButton("Add to mix")
            self._mix_btn.setObjectName("speciesPageMix")
            self._mix_btn.setToolTip(
                "Add this plant to the mix under the plant list, to place "
                "several species together in a row, grid, circle or area.")
            self._mix_btn.setStyleSheet(
                "QPushButton { background: #1e2e1e; color: #a5d6a7; "
                "border: 1px solid #2e4a2e; border-radius: 4px; "
                "padding: 4px 10px; font-size: 13px; min-height: 24px; }"
                "QPushButton:hover { border-color: #4a7a4a; }"
                "QPushButton:focus { border: 2px solid #ffe082; }"
                "QPushButton:disabled { color: #7f9c82; }")
            self._mix_btn.clicked.connect(
                lambda: self._row and self.mix_requested.emit(self._row))
            row.addWidget(self._mix_btn)
            self._actions = QWidget()
            self._actions.setLayout(row)
            outer.addWidget(self._actions)

        self._body = QWidget()
        self._col = QVBoxLayout(self._body)
        self._col.setContentsMargins(0, 4, 6, 8)
        self._col.setSpacing(6)
        self._scroll = QScrollArea()
        self._scroll.setAccessibleName("Species page")   # a Tab stop (V3.02)
        self._scroll.setWidgetResizable(True)
        self._scroll.setFrameShape(QFrame.Shape.NoFrame)
        self._scroll.setHorizontalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self._scroll.setWidget(self._body)
        outer.addWidget(self._scroll, 1)
        self.show_empty()

    # ── What is shown ───────────────────────────────────────────────────────

    def shown_id(self) -> int:
        """The plant on the page, or 0."""
        return int(self._row.get("id") or 0) if self._entry else 0

    def entry(self) -> dict:
        return self._entry

    def show_empty(self, text: str = "Pick a species to read about it."):
        self._row, self._entry = {}, {}
        self._head.setVisible(self._close is not None)
        self._name.setText("")
        self._sci.setText("")
        self._placed_line.setVisible(False)
        if self._place_btn is not None:
            self._actions.setVisible(False)
        self.setAccessibleName("Plant page")
        self._clear()
        hint = QLabel(text)
        hint.setStyleSheet(_DIM)
        hint.setWordWrap(True)
        hint.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        self._col.addWidget(hint)
        self._col.addStretch()

    def show_plant(self, row: dict, *, placed: int = 0, in_mix: bool = False,
                   why: Optional[list] = None):
        """Fill the page for ``row`` (a catalogue row; only its id is read
        here, and it is what Place and Add to mix hand back). ``why`` is the
        generator's reasons for one placed plant's spot (F19), shown first
        when the page was opened from that plant on the map."""
        self._why = [w for w in (why or []) if w]
        entry_fn = self._entry_fn
        if entry_fn is None:
            from src.plant_directory import species_entry as entry_fn
        entry = entry_fn(int((row or {}).get("id") or 0)) if row else {}
        if not entry:
            self.show_empty()
            return
        same = self.shown_id() == int(row.get("id") or 0)
        self._row, self._entry = dict(row), entry
        self._placed, self._in_mix = int(placed or 0), bool(in_mix)
        if self._photo_warmer is not None:
            # The list warms a photo only when asked. Ask for this one now; the
            # owner calls refresh_photo when it lands.
            self._photo_warmer(row)
        self._render()
        if not same:
            self._scroll.verticalScrollBar().setValue(0)

    def set_placement(self, *, placed: Optional[int] = None,
                      in_mix: Optional[bool] = None):
        """How many are in the design, and whether it is in the mix, changed
        while the page was open."""
        if placed is not None:
            self._placed = int(placed)
        if in_mix is not None:
            self._in_mix = bool(in_mix)
        if self._entry:
            self._render_head()

    def refresh_photo(self, plant_id: int):
        """A photo finished downloading: redraw if it is this plant's."""
        if self._entry and int(plant_id) == self.shown_id():
            keep = self._scroll.verticalScrollBar().value()
            self._render()
            self._scroll.verticalScrollBar().setValue(keep)

    def keyPressEvent(self, event):
        if event.key() == Qt.Key.Key_Escape and self._close is not None:
            self.close_requested.emit()
            event.accept()
            return
        super().keyPressEvent(event)

    # ── Rendering ───────────────────────────────────────────────────────────

    def _render_head(self):
        entry = self._entry
        name = entry.get("name") or ""
        self._head.setVisible(True)
        self._name.setText(name)
        self._sci.setText(entry.get("scientific_name") or "")
        self._placed_line.setText(
            f"{self._placed} in this design" if self._placed else "")
        self._placed_line.setVisible(bool(self._placed))
        self.setAccessibleName(f"About {name}")
        if self._place_btn is not None:
            self._actions.setVisible(True)
            self._place_btn.set_subject(name)
            self._mix_btn.setText("In the mix" if self._in_mix else "Add to mix")
            self._mix_btn.setEnabled(not self._in_mix)
            self._mix_btn.setAccessibleName(
                f"{name} is in the mix" if self._in_mix
                else f"Add {name} to the mix")

    def _render(self):
        entry = self._entry
        self._render_head()
        self._clear()
        add = self._col.addWidget

        add(self._photo_block(entry))
        if getattr(self, "_why", None):
            # F19 (V3.05): why the generator put this one here, read back
            # from the score that chose the spot.
            self._section("Why here", ". ".join(self._why) + ".")
        if entry.get("badges"):
            self._section("Why it matters", " · ".join(entry["badges"]))
        if entry.get("roles"):
            self._section("Roles", " · ".join(entry["roles"]))
        self._section("Conditions", " · ".join(
            p for p in (_conditions(entry), entry.get("soil_ph"),
                        entry.get("zones")) if p))
        self._section("Size", " · ".join(p for p in (
            _metres(entry.get("mature_height_m"), "tall"),
            _metres(entry.get("mature_canopy_m"), "wide"),
            _years(entry.get("years_to_maturity")),
            _metres(entry.get("spacing_m"), "apart")) if p))
        self._season_block(entry)
        if entry.get("morphology"):
            self._section("What it looks like", " · ".join(entry["morphology"]))
        self._native_block(entry)
        self._range_block(entry)
        self._wildlife_block(entry)
        self._companion_block(entry)
        if entry.get("edible_parts"):
            self._section("Edible parts", entry["edible_parts"])
        self._sourcing_block(entry)
        if entry.get("safety"):
            self._section("Safety", " · ".join(entry["safety"]))
        if entry.get("notes"):
            self._section("Notes", entry["notes"])
        if entry.get("provenance"):
            self._section("Where these numbers came from",
                          " · ".join(entry["provenance"]), dim=True)
        self._col.addStretch()

    def _clear(self):
        while self._col.count():
            item = self._col.takeAt(0)
            w = item.widget()
            if w is not None:
                w.setParent(None)
                w.deleteLater()

    def _section(self, heading: str, body: str, *, dim: bool = False,
                 rich: bool = False) -> Optional[QLabel]:
        if not (body or "").strip():
            return None
        if heading:
            head = QLabel(heading)
            head.setStyleSheet(_LABEL)
            head.setWordWrap(True)
            head.setTextInteractionFlags(
                Qt.TextInteractionFlag.TextSelectableByMouse)
            self._col.addWidget(head)
        text = QLabel(body)
        text.setWordWrap(True)
        text.setStyleSheet(_DIM if dim else _BODY)
        flags = Qt.TextInteractionFlag.TextSelectableByMouse
        if rich:
            text.setTextFormat(Qt.TextFormat.RichText)
            flags |= (Qt.TextInteractionFlag.LinksAccessibleByMouse
                      | Qt.TextInteractionFlag.LinksAccessibleByKeyboard)
        else:
            text.setTextFormat(Qt.TextFormat.PlainText)
        text.setTextInteractionFlags(flags)
        self._col.addWidget(text)
        return text

    def _photo_block(self, entry: dict) -> QWidget:
        """The photograph, or an honest line about not having one. Roughly a
        quarter of the catalogue has no picture; saying so beats an empty
        frame, and it is also the work list."""
        from src.image_cache import credit_line, get_cached_image
        box = QLabel()
        photos = entry.get("photos") or []
        url = photos[0].get("url") if photos else ""
        path = get_cached_image(url) if url else None
        if path:
            from PyQt6.QtGui import QPixmap
            pix = QPixmap(path)
            if not pix.isNull():
                # Inside 320 x 240 either way round: a herbarium sheet scaled
                # to the width alone stood 356 px tall and pushed every
                # section below the fold.
                box.setPixmap(pix.scaled(
                    QSize(max(240, min(320, self.width() - 40)), 240),
                    Qt.AspectRatioMode.KeepAspectRatio,
                    Qt.TransformationMode.SmoothTransformation))
                credit = credit_line(photos[0].get("attribution") or "",
                                     photos[0].get("license") or "")
                box.setToolTip(credit or "")
                box.setAccessibleName(
                    f"Photograph of {entry.get('name') or 'this plant'}"
                    + (f". {credit}" if credit else ""))
                if not credit:
                    return box
                holder = QWidget()
                col = QVBoxLayout(holder)
                col.setContentsMargins(0, 0, 0, 0)
                col.setSpacing(2)
                col.addWidget(box)
                line = QLabel(credit)
                line.setStyleSheet(_DIM)
                line.setWordWrap(True)
                line.setTextInteractionFlags(
                    Qt.TextInteractionFlag.TextSelectableByMouse)
                col.addWidget(line)
                return holder
        box.setText("No photograph of this species yet."
                    if not url else "Photograph not downloaded yet.")
        box.setStyleSheet(_DIM)
        box.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        return box

    def _season_block(self, entry: dict):
        """Bloom and fruit as words, the bar under them, and the calendar's
        tasks (sowing, pruning) as a line."""
        text = " · ".join(p for p in (
            f"blooms {entry['bloom']}" if entry.get("bloom") else "",
            _bloom_colour_line(entry),
            f"fruits {entry['fruit']}" if entry.get("fruit") else "",
            _colour_word(entry.get("fruit_color"), "fruit")) if p)
        self._section("Season", text)
        bloom = entry.get("bloom_months") or []
        fruit = entry.get("fruit_months") or []
        if bloom or fruit:
            self._col.addWidget(SeasonBar(bloom, fruit))
        tasks = _calendar_tasks(entry.get("calendar") or [],
                                edible=bool(entry.get("edible_parts")))
        if tasks:
            self._section("", tasks)

    def _native_block(self, entry: dict):
        """Where it is native, before where it has been found (F220, F222,
        V3.12). The website has said "Native to" since V2.47 and this page
        never did, so Eastern Red Columbine, native to Saskatchewan and "Found
        in" an ecoregion that straddles the border, read as Albertan."""
        from src.native_here import province_words
        self._section("Native to", province_words(entry))
        around = entry.get("around") or {}
        if around.get("words"):
            self._section(f"Around {around['short']}", around["words"])

    def _range_block(self, entry: dict):
        """Where it has been recorded, **with the count and the confidence**:
        a region seen 242 times and one seen 5 times are different claims (P9).
        """
        rows = entry.get("ranges") or []
        if not rows:
            return
        bits = []
        for r in rows[:4]:
            if r.get("occurrences"):
                bits.append(f"{r['name']} ({r['occurrences']} records, "
                            f"{r['confidence']} confidence)")
            else:
                bits.append(f"{r['name']} (no occurrence data)")
        self._section("Found in", "\n".join(bits))
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
            self._section("Wildlife", "No documented animal relationships yet, "
                                      "which means unrecorded, not absent.",
                          dim=True)
            return
        animals = int(w.get("animals") or w["total"])
        special = int(w.get("specialist_animals") or w.get("specialists") or 0)
        line = f"Feeds or shelters {animals} documented species"
        if special:
            line += (f", {special} of them "
                     f"{'a specialist' if special == 1 else 'specialists'} "
                     f"with nowhere else to go (⚑)")
        self._section("Wildlife", line + ".")
        for group in w.get("groups") or []:
            label = self._section("", _group_html(group, _FIRST), rich=True)
            if label is not None and len(group.get("items") or []) > _FIRST:
                label.linkActivated.connect(
                    lambda _href, lab=label, g=group:
                    lab.setText(_group_html(g, None)))
        self._citation_block(w)

    def _citation_block(self, wildlife: dict):
        """Where the wildlife relationships came from. Every edge has carried a
        citation; until V2.42 no screen showed one, so a sourced record and an
        invention looked the same."""
        from src.citations import format_citation, is_placeholder
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
            names = ", ".join(i["name"] for i in g["items"] if i.get("name"))
            if names:
                bits.append(f"{g['label']}: {names}")
        self._section("Grows with", "\n".join(bits))

    def _sourcing_block(self, entry: dict):
        # The website's sentence (V3.14): this printed the raw tier, "· rare",
        # "· big box", where the site says "hard to find in the trade".
        from src.sourcing import describe
        text, note = describe(entry.get("sourcing") or {})
        self._section("Where to get it", text)
        if note:
            self._section("", note, dim=True)


class SeasonBar(QWidget):
    """Twelve months, a row for flowers and a row for fruit, each row named in
    words so the colour is never the only cue. The accessible name is the
    sentence (``phenology_bar.alt_text``), which is what a screen reader reads
    and what the tooltip says."""

    BLOOM = "#d98b3a"
    FRUIT = "#b98aa6"
    EMPTY = "#2c3b2c"
    _LABEL_W = 60
    _ROW_H = 16           # room for its 12 px words (V3.03)
    _HEAD_H = 16

    def __init__(self, bloom, fruit, parent=None):
        super().__init__(parent)
        from src.phenology_bar import alt_text
        self._rows = [(name, set(int(m) for m in months), colour)
                      for name, months, colour in (
                          ("Flowers", bloom, self.BLOOM),
                          ("Fruit", fruit, self.FRUIT)) if months]
        text = alt_text(bloom, fruit)
        self.setAccessibleName(text)
        self.setToolTip(text)
        self.setMinimumWidth(220)
        self.setFixedHeight(self._HEAD_H + 2 + len(self._rows) * (self._ROW_H + 3))

    def paintEvent(self, _event):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        font = QFont(self.font())
        font.setPixelSize(12)
        p.setFont(font)
        left = self._LABEL_W
        cell = (self.width() - left) / 12.0
        p.setPen(QColor("#90a4ae"))
        for i, month in enumerate(_MONTHS):
            p.drawText(int(left + i * cell), 0, int(cell), self._HEAD_H,
                       int(Qt.AlignmentFlag.AlignCenter), month[0])
        for r, (name, months, colour) in enumerate(self._rows):
            top = self._HEAD_H + 2 + r * (self._ROW_H + 3)
            p.setPen(QColor("#c8e6c9"))
            p.drawText(0, top, left - 4, self._ROW_H,
                       int(Qt.AlignmentFlag.AlignVCenter
                           | Qt.AlignmentFlag.AlignLeft), name)
            for i in range(12):
                filled = (i + 1) in months
                p.setPen(QPen(QColor("#3a4d3a"), 1))
                p.setBrush(QColor(colour if filled else self.EMPTY))
                p.drawRoundedRect(int(left + i * cell) + 1, top,
                                  max(2, int(cell) - 2), self._ROW_H, 2, 2)
        p.end()


def _group_html(group: dict, first: Optional[int]) -> str:
    """One wildlife group as rich text: its first ``first`` names and a link
    to the rest, or all of them when ``first`` is None."""
    items = group.get("items") or []
    shown = items if first is None else items[:first]
    names = ", ".join(html.escape(i.get("name") or "")
                      + (" ⚑" if i.get("specialist") else "") for i in shown)
    text = f"<b>{html.escape(group.get('how') or '')}</b>: {names}"
    more = len(items) - len(shown)
    if more > 0:
        text += (f' <a href="more" style="{_LINK}">and {more} more</a>')
    return text


def _calendar_tasks(calendar: list, *, edible: bool) -> str:
    """``"Prune in March and April"``: the calendar's months that say something
    the bloom and fruit windows do not. Harvest is said only of a plant with
    edible parts, where it is a task rather than the fruiting season again."""
    by_status: dict = {}
    for row in calendar or []:
        status = row.get("status") or ""
        try:
            month = int(row.get("month") or 0)
        except (TypeError, ValueError):
            continue
        if 1 <= month <= 12:
            by_status.setdefault(status, set()).add(month)
    tasks = list(_TASKS) + ([("harvest", "Harvest")] if edible else [])
    bits = [f"{label} in {_month_runs(sorted(by_status[status]))}"
            for status, label in tasks if by_status.get(status)]
    return " · ".join(bits)


def _month_runs(months: list) -> str:
    """``[3, 4]`` → "March and April"; ``[5, 6, 7]`` → "May to July"."""
    runs, start = [], None
    for i, m in enumerate(months):
        if start is None:
            start = m
        if i + 1 == len(months) or months[i + 1] != m + 1:
            if m == start:
                runs.append(_MONTHS[m - 1])
            elif m == start + 1:
                runs.append(f"{_MONTHS[start - 1]} and {_MONTHS[m - 1]}")
            else:
                runs.append(f"{_MONTHS[start - 1]} to {_MONTHS[m - 1]}")
            start = None
    return ", ".join(runs)


def _conditions(entry: dict) -> str:
    """Sun and water as words. The raw fields are comma-delimited snake_case
    ("full_sun,partial_shade"); `labels_csv` is the renderer the list rows use,
    so the two cannot disagree about what a condition is called."""
    from src.plant_list_view import _SUN_LABELS, _WATER_LABELS, labels_csv
    sun = labels_csv((entry.get("sun") or "").replace(" ", "_"), _SUN_LABELS)
    water = labels_csv(entry.get("water") or "", _WATER_LABELS)
    out = []
    if sun and sun != "—":
        out.append(sun)
    if water and water != "—":
        out.append(f"{water} water")
    return " · ".join(out)


def _bloom_colour_line(entry: dict) -> str:
    """"Purple flowers (not verified, a genus-level estimate)" (V2.48). The
    provenance rides along because the colour was seeded per genus."""
    label = (entry.get("bloom_colour_label") or "").strip()
    if not label:
        return ""
    note = (entry.get("bloom_colour_note") or "").strip()
    # The grasses' label is already a full phrase.
    head = label if entry.get("bloom_colour") == "straw" else f"{label} flowers"
    return head + (f" ({note})" if note else "")


def _colour_word(value, what: str) -> str:
    """Colour fields hold a name or a hex triplet; the hex drives the 3D bloom
    and is meaningless on a page. Print names, drop codes."""
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
