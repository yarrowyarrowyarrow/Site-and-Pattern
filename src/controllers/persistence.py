"""
src/controllers/persistence.py — Save / autosave / undo-stack controller.

Owns the small, low-coupling persistence helpers: marking the project
dirty (and reflecting that in the window title), saving to disk +
choosing a path, the autosave timer, and pushing entries onto the
undo stack.

Extracted from ``src/app.py:MainWindow`` in Chunk 5c of the
strengthening roadmap. The much larger ``_do_undo`` / ``_do_redo``
methods (200+ lines each, action-type branches that mutate project
state and drive the map via typed bridges from Chunk 3) stay on
MainWindow for a separate follow-up — they're high-risk and deserve
their own characterisation tests first.

The controller still talks to Qt via the bound MainWindow: file dialog
parent, status bar messages, the undo/redo QAction widgets created in
``_build_menu``. Making it Qt-free is Chunk 6 (E1).
"""

from __future__ import annotations

import os

from PyQt6.QtCore import QTimer
from PyQt6.QtWidgets import QFileDialog, QMessageBox

import src.project as project_io


class PersistenceController:
    """Save / autosave / push_undo. Holds a MainWindow reference for the
    project state (``_project``, ``_project_path``, ``_modified``), the
    undo stack (``_undo_stack``, ``_redo_stack``, ``_max_undo``), the
    undo/redo QActions (``_act_undo``, ``_act_redo``), the autosave
    timer slot (``_autosave_timer``), and the Qt host (file dialog
    parent, status bar, window title).
    """

    def __init__(self, main_window):
        self._main = main_window

    # ── Modified flag + window title ─────────────────────────────────────────

    def _mark_modified(self):
        self._main._modified = True
        if not self._main.windowTitle().endswith(' *'):
            self._main.setWindowTitle(self._main.windowTitle() + ' *')

    # ── Save / Save As ────────────────────────────────────────────────────────

    def _on_save(self):
        if self._main._project_path:
            self._save_to_path(self._main._project_path)
        else:
            self._on_save_as()

    def _on_save_as(self):
        path, _ = QFileDialog.getSaveFileName(
            self._main, "Save Design", "",
            "PermaDesign Files (*.perma.geojson);;GeoJSON (*.geojson)"
        )
        if path:
            if not path.endswith('.perma.geojson') and not path.endswith('.geojson'):
                path += '.perma.geojson'
            self._save_to_path(path)

    def _save_to_path(self, path: str):
        try:
            project_io.save_project(self._main._project, path)
            self._main._project_path = path
            self._main._modified     = False
            name = self._main._project["properties"].get("project_name", "Design")
            self._main.setWindowTitle(f"PermaDesign — {name}")
            self._main.statusBar().showMessage(f"Saved: {path}", 3000)
        except Exception as exc:
            QMessageBox.critical(self._main, "Save failed", str(exc))

    # ── Autosave timer ────────────────────────────────────────────────────────

    def _start_autosave(self):
        self._main._autosave_timer = QTimer(self._main)
        self._main._autosave_timer.setInterval(self._main.AUTOSAVE_INTERVAL_MS)
        self._main._autosave_timer.timeout.connect(self._autosave)
        self._main._autosave_timer.start()

    def _autosave(self):
        if not self._main._modified:
            return
        tmp = os.path.join(os.path.expanduser("~"), ".permadesign_autosave.perma.geojson")
        try:
            project_io.save_project(self._main._project, tmp)
        except Exception:
            pass

    # ── Undo stack push ───────────────────────────────────────────────────────
    # _do_undo and _do_redo themselves stay on MainWindow for now — they're
    # 200+ lines of action-type-specific branches that mutate project state
    # and drive the map via the typed bridge from Chunk 3. Extracting them
    # safely needs the characterisation tests that Chunk 2 sketched out
    # but didn't fully land for the undo branches.

    def _push_undo(self, entry: dict):
        self._main._undo_stack.append(entry)
        if len(self._main._undo_stack) > self._main._max_undo:
            self._main._undo_stack.pop(0)
        self._main._redo_stack.clear()
        self._main._act_undo.setEnabled(True)
        self._main._act_redo.setEnabled(False)
