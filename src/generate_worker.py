"""
generate_worker.py — background worker for one-click design generation.

Runs the (potentially slow, network-bound) LLM generation off the GUI thread,
mirroring the ``QThread`` pattern in :mod:`src.site_panel`. On any
:class:`~src.errors.LLMError` — most commonly an unreachable local model — it
transparently falls back to the deterministic offline path so the user always
gets a design. Genuinely fatal problems (e.g. no site location) surface via the
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

    def __init__(self, prompt: str, *, site_config: Optional[dict],
                 boundary: Optional[list], goals: list, offline: bool,
                 budget: Optional[float] = None,
                 fauna_ids: Optional[list] = None,
                 match_site: bool = True):
        super().__init__()
        self._prompt = prompt
        self._site_config = site_config
        self._boundary = boundary
        self._goals = goals
        self._offline = offline
        self._budget = budget
        self._fauna_ids = fauna_ids or []
        self._match_site = match_site

    @pyqtSlot()
    def run(self):
        from src.llm_design import generate_design, generate_design_offline
        from src.errors import LLMError, PermaDesignError
        try:
            if self._offline:
                self.progress.emit("Building design (offline)…")
                project = generate_design_offline(
                    site_config=self._site_config, boundary=self._boundary,
                    goals=self._goals, budget=self._budget,
                    fauna_ids=self._fauna_ids, match_site=self._match_site)
            else:
                self.progress.emit("Asking the local AI for a design…")
                try:
                    project = generate_design(
                        self._prompt, site_config=self._site_config,
                        boundary=self._boundary, goals=self._goals,
                        budget=self._budget, fauna_ids=self._fauna_ids,
                        match_site=self._match_site)
                except LLMError as exc:
                    self.progress.emit(
                        f"AI unavailable ({exc}); building offline…")
                    project = generate_design_offline(
                        site_config=self._site_config, boundary=self._boundary,
                        goals=self._goals, budget=self._budget,
                        fauna_ids=self._fauna_ids, match_site=self._match_site)
            self.finished.emit(project)
        except PermaDesignError as exc:
            self.failed.emit(str(exc))
        except Exception as exc:  # noqa: BLE001 — never crash the worker thread
            self.failed.emit(f"Unexpected error during generation: {exc}")
