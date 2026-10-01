"""
plant_directory_window.py — the plant directory as a room you can stand in
(F90, V2.41; one picker and one page since V3.00).

Design principle P5 — see docs/DESIGN_PHILOSOPHY.md.

A top-level window, opened from the start screen before any design exists and
from ``View →`` once one does. It follows the singleton shape
``scene3d_window.open_3d_view`` and ``snapshot_window.open_snapshot_view``
already use, with one difference: ``main`` is **optional**, because the whole
point is that you can read the catalogue without owning a design.

Since V3.00 (F192) it is built from the two widgets every picker shares: the
filters and list of ``src/plant_picker.py`` across the top and left, and the
page of ``src/species_page.py`` on the right. The Browse tab shows the same page
beside its list, so the directory is no longer the only place a plant can be
read, and it is no longer a place a plant cannot be placed from: with a design
open, the page's Place hands the plant to the Browse tab and brings the map
forward.
"""

from __future__ import annotations

from typing import Optional

from PyQt6.QtCore import Qt, QSize
from PyQt6.QtWidgets import (
    QPushButton, QSplitter, QVBoxLayout, QWidget,
)

from src.plant_list_view import _PLANT_OBJ_ROLE
from src.plant_picker import PlantPicker
from src.species_page import SpeciesPage
from src.ui_style import BASE_SURFACE, BTN_SECONDARY


class PlantDirectoryWindow(QWidget):
    """Browse the catalogue. Constructs with no MainWindow."""

    def __init__(self, main=None):
        super().__init__(None)                      # top-level window
        self._main = main
        self.setWindowTitle("Plant Directory")
        self.setMinimumSize(QSize(1000, 640))
        self.setStyleSheet(BASE_SURFACE)

        outer = QVBoxLayout(self)
        outer.setContentsMargins(12, 12, 12, 12)
        outer.setSpacing(8)

        # A reference work is something you look things up in: name order, and
        # the filters unfolded, because a window has room for them.
        self.picker = PlantPicker(self, wide=True, filters_open=True,
                                  list_apart=True)
        outer.addWidget(self.picker)

        left = QWidget()
        col = QVBoxLayout(left)
        col.setContentsMargins(0, 0, 6, 0)
        col.setSpacing(6)
        col.addWidget(self.picker.view, 1)
        quiz = QPushButton("Quiz me on these")
        quiz.setToolTip(
            "Field Study over the species you have filtered to — identify "
            "them, trace a specialist to its host. Retrieval practice is how "
            "any of this sticks.")
        quiz.setStyleSheet(BTN_SECONDARY)
        quiz.clicked.connect(self._open_quiz)
        col.addWidget(quiz)

        self.page = SpeciesPage(actions=main is not None,
                                photo_warmer=self.picker.model.warm_photo)
        split = QSplitter(Qt.Orientation.Horizontal)
        split.addWidget(left)
        split.addWidget(self.page)
        split.setSizes([420, 580])
        split.setStretchFactor(1, 1)
        outer.addWidget(split, 1)

        # Every way of moving the highlight shows that plant: a click, the
        # arrow keys. Nothing here places, so reading is all a click can mean.
        self.picker.view.selectionModel().currentChanged.connect(
            lambda current, _previous: self._show(current))
        # The photo lands on a worker thread a moment after the page asked.
        self.picker.model.imageReady.connect(self.page.refresh_photo)
        self.picker.results_changed.connect(self._on_results)
        self.page.place_requested.connect(self._place)
        self.page.mix_requested.connect(self._add_to_mix)

        self.picker.refresh()

    def rows(self) -> list:
        return self.picker.rows()

    def refresh(self):
        self.picker.refresh()

    def preset(self, criteria: dict):
        """Open showing exactly this filter — the start screen's in-bloom line
        uses it. Replaces rather than merges (see PlantPicker.set_criteria)."""
        self.picker.set_criteria(criteria)

    # ── The page ────────────────────────────────────────────────────────────

    def _show(self, index):
        row = index.data(_PLANT_OBJ_ROLE) if index.isValid() else None
        if not row:
            return
        panel = getattr(self._main, "plant_panel", None)
        pid = row.get("id")
        self.page.show_plant(
            row,
            placed=panel.placed_count(pid) if panel is not None else 0,
            in_mix=panel.in_mix(pid) if panel is not None else False)

    def _on_results(self):
        shown = self.page.shown_id()
        if not self.rows():
            self.page.show_empty()
        elif shown and not any(r.get("id") == shown for r in self.rows()):
            self.page.show_empty()
        elif shown:
            self.picker.select_plant_id(shown)

    def _place(self, row: dict):
        """Hand the plant to the Browse tab, armed, and bring the map forward:
        the click that places it happens there."""
        panel = getattr(self._main, "plant_panel", None)
        if panel is None:
            return
        panel.place_from_elsewhere(row)
        self._main.raise_()
        self._main.activateWindow()

    def _add_to_mix(self, row: dict):
        panel = getattr(self._main, "plant_panel", None)
        if panel is None:
            return
        panel.add_to_mix(row)
        self.page.set_placement(in_mix=panel.in_mix(row.get("id")))

    # ── Actions ─────────────────────────────────────────────────────────────

    def _open_quiz(self):
        """Field Study over the current result set.

        ``field_study.generate_quiz`` already accepts an arbitrary plant list —
        it was written design-aware but never required a design — so studying a
        filter and then being tested on it costs nothing but this window.
        """
        from src.field_study_widget import FieldStudyWidget
        rows = list(self.rows())
        win = FieldStudyWidget(plants_provider=lambda: rows)
        win.setWindowTitle(f"Field Study — {len(rows)} species")
        win.setStyleSheet(BASE_SURFACE)
        win.setMinimumSize(QSize(560, 520))
        win.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose)
        win.show()
        # Held so Python doesn't collect the window the moment this returns.
        self._quiz_window = win


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
