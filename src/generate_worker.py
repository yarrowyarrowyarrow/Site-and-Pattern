"""
generate_worker.py — background worker for one-click design generation.

Runs the generator off the GUI thread, mirroring the ``QThread`` pattern in
:mod:`src.site_panel`. Since V3.22 (RM-3) the app always builds with the
rule-based generator, ``generate_design_offline``: the local language model,
and the brief only it read, left the app, and stay in the command line and the
MCP server. Genuinely fatal problems (e.g. no site location) surface via the
``failed`` signal.
"""

from __future__ import annotations

from typing import Optional

from PyQt6.QtCore import QObject, pyqtSignal, pyqtSlot


class GenerateWorker(QObject):
    """Generates a design on its own thread and emits the resulting Project."""

    progress = pyqtSignal(str)
    finished = pyqtSignal(object)   # src.permadesign_api.Project
    failed = pyqtSignal(str)

    def __init__(self, *, site_config: Optional[dict],
                 boundary: Optional[list], goals: list,
                 budget: Optional[float] = None,
                 fauna_ids: Optional[list] = None,
                 match_site: bool = True,
                 density: str = "balanced",
                 cover: Optional[float] = None,
                 setting: str = "", street_side: str = "", variant: int = 0,
                 existing_features: Optional[list] = None):
        super().__init__()
        self._site_config = site_config
        self._boundary = boundary
        self._goals = goals
        self._budget = budget
        self._fauna_ids = fauna_ids or []
        self._match_site = match_site
        self._density = density
        self._cover = cover
        self._setting, self._street_side = setting, street_side
        self._variant = variant
        self._existing_features = existing_features or []

    @pyqtSlot()
    def run(self):
        from src.llm_design import generate_design_offline
        from src.errors import PermaDesignError
        try:
            self.progress.emit("Planning your yard…")
            project = generate_design_offline(
                site_config=self._site_config, boundary=self._boundary,
                goals=self._goals, budget=self._budget,
                fauna_ids=self._fauna_ids, match_site=self._match_site,
                density=self._density, cover=self._cover,
                setting=self._setting, street_side=self._street_side,
                variant=self._variant,
                existing_features=self._existing_features)
            self.finished.emit(project)
        except PermaDesignError as exc:
            self.failed.emit(str(exc))
        except Exception as exc:  # noqa: BLE001 — never crash the worker thread
            self.failed.emit(f"Unexpected error during generation: {exc}")
