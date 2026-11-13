"""
scene3d_named_groups.py — the 3D toolbar's two plain groups (V3.44, F261).

Design principle P5 (perception is constructed: a control with no words on it
is not one a newcomer can use) — see docs/DESIGN_PHILOSOPHY.md.

``WHEN`` is the moment as three short lists (*When*, *Season*, *Time of day*)
and ``VIEWS`` is where to look from (*From the street*, *From the house*,
*From above*, *Walk*, *Reset view*). The V3.43 review's finding 13 was sixteen
controls in three rows with three unlabelled sliders among them; these are the
five a homeowner needs, each with its name on it.

A mixin for :class:`src.scene3d_toolbar.Scene3DToolBar`, which holds the
moment (``_at``), :meth:`set_time` and the signals; split out because that
file has a line ceiling and these are a seam of their own (named stops beside
the sliders, never instead of the state). The words and values are
``src/scene3d_stops.py``.
"""

from __future__ import annotations

from PyQt6.QtWidgets import QComboBox, QPushButton

from src import scene3d_stops as stops

#: The group names, as ``scene3d_toolbar`` exports them.
WHEN = "when"
VIEWS = "views"


class NamedGroups:
    """``_build_when`` / ``_build_views`` and what keeps them true."""

    def _build_when(self, row):
        """The moment as three lists of named stops (V3.44)."""
        self._lists = {}
        for key, words, entries, tip in (
                ("year", "When", stops.when_entries,
                 "How long after planting: from the first summer to every "
                 "plant fully grown"),
                ("month", "Season", stops.season_entries,
                 "The time of year: what is green, in flower, or under snow"),
                ("hour", "Time of day", stops.day_entries,
                 "Where the sun is, and where the shade falls")):
            box = QComboBox()
            box.setAccessibleName(words)
            box.setToolTip(tip)
            box.setMinimumHeight(24)
            # Wide enough for anything it can come to say: an entry off the
            # stops ("Twenty-fourth summer") arrives after the list is sized.
            widest = max(box.fontMetrics().horizontalAdvance(w)
                         for w in stops.every_word(key))
            box.setMinimumWidth(widest + 44)
            box.activated.connect(lambda _i, k=key: self._on_list(k))
            label = self._label(f"{words}:")
            label.setBuddy(box)
            row.addWidget(label)
            row.addWidget(box)
            self._lists[key] = (box, entries)
        self._fill_lists()

    def _fill_lists(self):
        """Each list: its stops, plus where the picture is when that is not a
        stop, chosen. Only when what it would show has changed."""
        if WHEN not in self._groups:
            return
        for key, (box, entries) in self._lists.items():
            rows = entries(self._at[key])
            if (box.count() == len(rows)
                    and all(box.itemData(i) == v and box.itemText(i) == w
                            for i, (v, w) in enumerate(rows))):
                index = [v for v, _w in rows].index(self._at[key])
                if box.currentIndex() != index:
                    box.setCurrentIndex(index)
                continue
            blocked = box.blockSignals(True)
            box.clear()
            for value, words in rows:
                box.addItem(words, value)
            box.setCurrentIndex([v for v, _w in rows].index(self._at[key]))
            box.blockSignals(blocked)

    def _on_list(self, key: str):
        box, _entries = self._lists[key]
        value = box.currentData()
        if value is not None:
            self.set_time(**{key: int(value)})

    def _build_views(self, row):
        """Where to look from (V3.44): three named viewpoints, Walk, Reset."""
        if row.count():
            row.addSpacing(10)
        row.addWidget(self._label("View:"))
        self.view_buttons = {}
        self._view_tips = {}
        for key, words, tip in stops.VIEWS:
            btn = QPushButton(words)
            btn.setToolTip(tip)
            btn.clicked.connect(lambda _c=False, k=key:
                                self.view_requested.emit(k))
            row.addWidget(btn)
            self.view_buttons[key] = btn
            self._view_tips[key] = tip
        self._walk_btn = QPushButton("Walk")
        self._walk_btn.setCheckable(True)
        self._walk_btn.setToolTip(
            "Walk through the yard: arrow keys or W A S D to walk, drag with "
            "the right button to look around, click a plant to read about "
            "it. Press again to stop.")
        self._walk_btn.toggled.connect(self.walk_toggled.emit)
        row.addWidget(self._walk_btn)
        self._reset_btn = QPushButton("Reset view")
        self._reset_btn.setToolTip("Show the whole yard again")
        self._reset_btn.clicked.connect(self.reset_view.emit)
        row.addWidget(self._reset_btn)

    def set_view_available(self, key: str, on: bool, why: str = "") -> None:
        """Offer a viewpoint or not; when not, its tooltip says what it needs
        (the V3.19 rule for a switch with nothing to change)."""
        btn = getattr(self, "view_buttons", {}).get(key)
        if btn is None:
            return
        btn.setEnabled(bool(on))
        btn.setToolTip(self._view_tips[key] if on else (why or ""))
