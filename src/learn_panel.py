"""
learn_panel.py — Side-panel tab for the learning & sharing tools (V2.25).

Groups the three teaching surfaces that used to crowd the Analysis tab:
  F48: Field Study — retrieval-practice quiz (photo ID, specialist links,
       spot-the-gap in your own design)
  F53: Lessons — the guided lesson track
  F52: Present — docent/presentation mode narrating the live design

Analysis answers "what is this site/design doing?"; these tabs teach it and
help you tell its story. All three are design-aware: they read the live
placed-plant/structure lists pushed by app.py's ``_sync_planning_panel``.

Design principle P5 — see docs/DESIGN_PHILOSOPHY.md (perception is
constructed; retrieval practice and narration build the mental model the
tool is trying to teach).
"""

from __future__ import annotations

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QFrame, QScrollArea, QVBoxLayout, QWidget


class LearnPanel(QWidget):
    """Panel housing the Field Study quiz, the guided lesson track, and the
    docent/presentation mode."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._placed_plants: list[dict] = []
        self._structures: list[dict] = []
        self._build_ui()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.setSpacing(0)

        from src.ui_style import inner_tab_stylesheet
        from src.fill_tab_widget import FillTabWidget
        self._tabs = FillTabWidget(allow_shrink=True)
        self._tabs.setDocumentMode(True)
        self._tabs.tabBar().setUsesScrollButtons(False)
        self._tabs.tabBar().setExpanding(True)
        self._tabs.tabBar().setElideMode(Qt.TextElideMode.ElideRight)
        self._tabs.setStyleSheet(inner_tab_stylesheet())

        self._build_field_study_tab()
        self._build_lesson_tab()
        self._build_present_tab()

        layout.addWidget(self._tabs)

    def _scroll_page(self, widget) -> QScrollArea:
        page = QScrollArea()
        page.setWidgetResizable(True)
        page.setFrameShape(QFrame.Shape.NoFrame)
        page.setWidget(widget)
        return page

    # ── F48 — Field Study quiz layer ─────────────────────────────────────────

    def _build_field_study_tab(self):
        from src.field_study_widget import FieldStudyWidget
        # The quiz is design-aware: it reads the live placed-plant list so the
        # "spot the food-web gap" question is about the user's own design.
        self._field_study = FieldStudyWidget(
            plants_provider=lambda: self._placed_plants)
        self._tabs.addTab(self._scroll_page(self._field_study), "Field Study")

    # ── F53 — Guided lesson track ────────────────────────────────────────────

    def _build_lesson_tab(self):
        from src.lesson_track_widget import LessonTrackWidget
        # Design-aware: each step's "your design" readout is the live project.
        self._lesson_track = LessonTrackWidget(
            plants_provider=lambda: self._placed_plants,
            structures_provider=lambda: self._structures)
        self._tabs.addTab(self._scroll_page(self._lesson_track), "Lessons")

    # ── F52 — Docent / presentation mode ─────────────────────────────────────

    def _build_present_tab(self):
        from src.docent_widget import DocentWidget
        # Design-aware: the narration is generated from the live project's facts.
        self._docent = DocentWidget(
            plants_provider=lambda: self._placed_plants,
            structures_provider=lambda: self._structures)
        self._tabs.addTab(self._scroll_page(self._docent), "Present")

    # ── Live-design sync (pushed from app.py's _sync_planning_panel) ─────────

    def set_placed_plants(self, plants: list[dict]):
        """Update the list of placed plants (from app.py)."""
        self._placed_plants = plants
        # Guided lesson track reads the live design.
        if hasattr(self, "_lesson_track"):
            self._lesson_track.refresh()
        # Docent presentation script is regenerated from the live design.
        if hasattr(self, "_docent"):
            self._docent.refresh()

    def set_structures(self, structures: list[dict]):
        """Update the list of placed structures (from app.py)."""
        self._structures = structures
