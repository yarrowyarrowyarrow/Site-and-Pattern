"""
src/controllers/generation.py — one-click "Generate Design" controller.

Owns the Generate-Design flow, extracted from MainWindow per this package's
controller pattern: show the goal dialog, run generation on a background
``QThread`` (:mod:`src.generate_worker`), and render the resulting plants onto
the map and into the live project. Living here (not as fat methods on
MainWindow) keeps ``src/app.py`` under the architecture-guard ceiling.
"""

from __future__ import annotations

from typing import Optional

from PyQt6.QtCore import QThread
from PyQt6.QtWidgets import QDialog, QMessageBox

import src.project as project_io


class GenerationController:
    """Drives the Generate-Design dialog, worker thread, and result rendering.

    Holds a MainWindow reference so it can read ``_project`` / ``map_widget`` /
    ``plant_panel`` and reuse the same placement bookkeeping the manual
    placement path uses (``_placed_plants`` + ``_project['features']``)."""

    def __init__(self, main_window):
        self._main = main_window
        self._thread: Optional[QThread] = None
        self._worker = None

    # ── Entry point (shim target on MainWindow) ──────────────────────────────

    def open_dialog(self):
        from src.generate_design_dialog import GenerateDesignDialog
        main = self._main

        boundary = self._current_boundary()
        site_config = dict(
            main._project.get("properties", {}).get("site_config", {}) or {})
        has_pin = (site_config.get("latitude") is not None
                   and site_config.get("longitude") is not None)

        dlg = GenerateDesignDialog(
            has_boundary=bool(boundary), has_pin=has_pin,
            preselected=site_config.get("priorities", []), parent=main)
        if dlg.exec() != QDialog.DialogCode.Accepted:
            return

        goals = dlg.selected_goals()
        # Persist the chosen goals into the project's site_config priorities —
        # the field's intended home (and what pre-checks the dialog next time).
        main._project.setdefault("properties", {}).setdefault(
            "site_config", {})["priorities"] = goals
        main._mark_modified()

        self._start(prompt=dlg.brief(), site_config=site_config or None,
                    boundary=boundary, goals=goals, offline=dlg.offline())

    # ── Worker lifecycle (mirrors src/site_panel.py) ─────────────────────────

    def _start(self, *, prompt, site_config, boundary, goals, offline):
        from src.generate_worker import GenerateWorker
        main = self._main
        if hasattr(main, "_act_generate"):
            main._act_generate.setEnabled(False)
        main.statusBar().showMessage("Generating design…")

        thread = QThread(main)
        worker = GenerateWorker(prompt, site_config=site_config,
                                boundary=boundary, goals=goals, offline=offline)
        worker.moveToThread(thread)

        thread.started.connect(worker.run)
        worker.progress.connect(self._on_progress)
        worker.finished.connect(self._on_finished)
        worker.failed.connect(self._on_failed)

        # Auto-teardown: quit the loop on a terminal signal, then schedule both
        # objects for deletion once the thread has actually stopped.
        worker.finished.connect(thread.quit)
        worker.failed.connect(thread.quit)
        worker.finished.connect(worker.deleteLater)
        worker.failed.connect(worker.deleteLater)
        thread.finished.connect(thread.deleteLater)

        self._thread = thread
        self._worker = worker
        thread.start()

    def _on_progress(self, msg: str):
        self._main.statusBar().showMessage(msg)

    def _on_finished(self, project):
        try:
            self._render(project)
        finally:
            self._finish_ui()

    def _on_failed(self, message: str):
        self._finish_ui()
        QMessageBox.warning(self._main, "Generate Design",
                            f"Couldn't generate a design:\n\n{message}")

    def _finish_ui(self):
        main = self._main
        if hasattr(main, "_act_generate"):
            main._act_generate.setEnabled(True)
        self._thread = None
        self._worker = None

    # ── Helpers ──────────────────────────────────────────────────────────────

    def _current_boundary(self):
        """Return the first drawn boundary as a list of ``(lat, lng)``, else
        ``None``. Used to anchor + (later) clip placement."""
        try:
            data = project_io.project_to_map_data(self._main._project)
        except Exception:  # noqa: BLE001
            return None
        for b in data.get("boundaries", []):
            pts = b.get("points") or []
            if len(pts) >= 3:
                return [(float(p[0]), float(p[1])) for p in pts]
        return None

    def _render(self, project):
        """Place every plant from the generated project onto the map and into
        the live project, under one shared placement group so the whole design
        deletes as a unit. Reuses the dual-store bookkeeping (``_placed_plants``
        + ``_project['features']``) from MainWindow's manual placement path."""
        main = self._main
        plants = list(_iter_generated_plants(project))
        if not plants:
            QMessageBox.information(
                main, "Generate Design",
                "The generator didn't place any plants. Try different goals, "
                "or draw a boundary / drop a property pin first.")
            return

        group_id = project_io.new_placement_group_id()
        batch: list[tuple[int, str]] = []
        for props, lat, lng in plants:
            pid = props.get("plant_id")
            if pid is None or lat is None or lng is None:
                continue
            name = props.get("common_name", "")
            poly_name = props.get("polyculture_name", "") or ""
            qty = props.get("quantity", 1) or 1
            spacing_m, plant_type, _ = main._plant_info(pid)
            community_id = project_io.community_id_for(lat, lng)

            main.map_widget.place_plant_marker(
                pid, name, lat, lng, spacing_m=spacing_m, plant_type=plant_type,
                color=None, group_id=group_id, community_id=community_id)
            main._placed_plants.append({
                "plant_id": pid, "common_name": name, "lat": lat, "lng": lng,
                "polyculture_name": poly_name,
                "placement_group_id": group_id,
            })
            main._project["features"].append({
                "type": "Feature",
                "geometry": {"type": "Point", "coordinates": [lng, lat]},
                "properties": {
                    "element_type": "plant",
                    "plant_id": pid,
                    "common_name": name,
                    "polyculture_name": poly_name,
                    "placement_group_id": group_id,
                    "pattern_kind": "generated",
                    "quantity": qty,
                },
            })
            batch.append((pid, name))

        main.plant_panel.on_plants_placed_batch(batch)
        main._mark_modified()
        main._sync_planning_panel()
        main.statusBar().showMessage(
            f"Generated design — placed {len(batch)} plants. Fine-tune by "
            "dragging or deleting.", 5000)

        warnings = (project.as_dict().get("properties", {})
                    .get("generation_warnings", []))
        if warnings:
            QMessageBox.information(main, "Design notes", "\n\n".join(warnings))


def _iter_generated_plants(project):
    """Yield ``(properties, lat, lng)`` for each plant feature in ``project``."""
    for f in project.as_dict().get("features", []):
        props = f.get("properties", {})
        if props.get("element_type") != "plant":
            continue
        coords = (f.get("geometry", {}) or {}).get("coordinates") or []
        if len(coords) >= 2:
            yield props, coords[1], coords[0]
