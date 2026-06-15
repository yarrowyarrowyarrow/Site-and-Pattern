"""
src/scene3d_window.py — the "3D Preview" window (V1.62).

Hosts a :class:`src.map3d_widget.Map3DWidget` with the controls that make
the 3D view useful for lawn-to-habitat persuasion:

  * a growth-timeline year slider ("watch your yard at year 1 / 5 / 15"),
  * month + hour sliders driving the shadow-casting sun (same
    ``src/solar`` path as the 2D shade engine, so the two always agree),
  * a Refresh button that re-reads the live project.

The scene itself comes from :func:`src.scene_contract.build_scene` — the
window owns no geometry. Terrain is fetched cache-first on a worker
QThread (``zoning.site_elevation_grid``) and the scene is re-pushed when
it lands, so opening the window never blocks the UI on the network.

``open_3d_view(main)`` is the entry point the View menu uses; it keeps a
singleton window on ``main._scene3d_window`` (no new MainWindow method —
the architecture guard's method ceiling stays meaningful).
"""

from __future__ import annotations

from datetime import datetime

from PyQt6.QtCore import Qt, QObject, QThread, pyqtSignal
from PyQt6.QtWidgets import (
    QHBoxLayout, QLabel, QPushButton, QSlider, QVBoxLayout, QWidget,
)

from src.map3d_widget import Map3DWidget
from src.scene_contract import build_scene
from src.branding import APP_NAME

_MAX_YEAR = 25
_MONTH_NAMES = ["Jan", "Feb", "Mar", "Apr", "May", "Jun",
                "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]


class _TerrainWorker(QObject):
    """Cache-first elevation fetch off the UI thread."""
    done = pyqtSignal(object)   # elevation dict or None

    def __init__(self, boundary, site_config):
        super().__init__()
        self._boundary = boundary
        self._site_config = site_config

    def run(self):
        elev = None
        try:
            from src.zoning import site_elevation_grid
            elev = site_elevation_grid(self._boundary, self._site_config)
        except Exception:
            elev = None
        self.done.emit(elev)


class Scene3DWindow(QWidget):
    """3D preview of the current design (growth year + sun controls)."""

    def __init__(self, main):
        super().__init__(None)   # top-level window
        self._main = main
        self._elevation = None
        self._thread = None
        self._worker = None
        self.setWindowTitle(f"{APP_NAME} — 3D Preview")
        self.resize(960, 700)

        self.viewer = Map3DWidget(self)

        self._year = QSlider(Qt.Orientation.Horizontal)
        self._year.setRange(0, _MAX_YEAR)
        self._year.setValue(0)
        self._year_lbl = QLabel()
        self._year.valueChanged.connect(self._on_controls_changed)

        self._month = QSlider(Qt.Orientation.Horizontal)
        self._month.setRange(1, 12)
        self._month.setValue(6)
        self._hour = QSlider(Qt.Orientation.Horizontal)
        self._hour.setRange(5, 21)
        self._hour.setValue(13)
        self._sun_lbl = QLabel()
        self._month.valueChanged.connect(self._on_controls_changed)
        self._hour.valueChanged.connect(self._on_controls_changed)

        refresh = QPushButton("Refresh from design")
        refresh.clicked.connect(self.refresh)

        # Bake the loaded Gaussian-splat backdrop to a top-down "yard photo"
        # for the 2D map (V1.65). Enabled only when the project has a splat.
        self._bake_btn = QPushButton("📷 Bake yard photo")
        self._bake_btn.setToolTip(
            "Render the photoreal scan straight down and add it to the 2D map "
            "as a personal satellite layer")
        self._bake_btn.setEnabled(False)
        self._bake_btn.clicked.connect(self._on_bake_yard_photo)

        self._last_origin = None

        bar = QHBoxLayout()
        bar.addWidget(QLabel("Year:"))
        bar.addWidget(self._year, 2)
        bar.addWidget(self._year_lbl)
        bar.addSpacing(12)
        bar.addWidget(QLabel("Sun:"))
        bar.addWidget(self._month, 1)
        bar.addWidget(self._hour, 1)
        bar.addWidget(self._sun_lbl)
        bar.addSpacing(12)
        bar.addWidget(refresh)
        bar.addWidget(self._bake_btn)

        root = QVBoxLayout(self)
        root.setContentsMargins(6, 6, 6, 6)
        root.addLayout(bar)
        root.addWidget(self.viewer, 1)

        self._update_labels()

    # ── scene plumbing ────────────────────────────────────────────────────

    def _when(self) -> datetime:
        return datetime(2025, self._month.value(), 21, self._hour.value(), 0)

    def _update_labels(self):
        y = self._year.value()
        self._year_lbl.setText("mature" if y == 0 else f"year {y}")
        self._sun_lbl.setText(
            f"{_MONTH_NAMES[self._month.value() - 1]} {self._hour.value()}:00")

    def _push_scene(self):
        scene = build_scene(
            self._main._project,
            year=self._year.value(),
            elevation=self._elevation,
            when=self._when(),
            # Set by the scan-import flow for this session (not persisted —
            # the scan's footprints are; the raw points are a preview aid).
            scan=getattr(self._main, "_scan_scene_sample", None),
        )
        # Remember the origin so a yard-photo bake frames the splat correctly.
        self._last_origin = scene.get("origin")
        self.viewer.apply_scene(scene)

    def _on_bake_yard_photo(self):
        """Render the loaded splat top-down and hand the PNG to the map layer."""
        from src import splat_backdrop, splat_flow
        feat = splat_backdrop.feature_from_project(self._main._project)
        if feat is None or not self._last_origin:
            self._main.statusBar().showMessage(
                "No yard scan to bake — import one via File → Import Yard Scan.",
                5000)
            return
        rect = splat_backdrop.scene_rect(
            feat, self._last_origin["lat"], self._last_origin["lng"])

        def _done(url):
            if splat_flow.apply_baked_ortho(self._main, feat, url):
                self._main.statusBar().showMessage(
                    "Yard photo baked onto the map — toggle it under "
                    "View → Yard photo.", 6000)
            else:
                self._main.statusBar().showMessage(
                    "Bake produced no image — let the splat finish loading in "
                    "3D, then try again.", 6000)

        self.viewer.capture_ortho(rect, _done)

    def _on_controls_changed(self, *_):
        self._update_labels()
        self._push_scene()

    def refresh(self):
        """Re-read the live project (and kick a terrain fetch if we don't
        have a grid yet)."""
        self._push_scene()
        from src.splat_backdrop import feature_from_project
        self._bake_btn.setEnabled(
            feature_from_project(self._main._project) is not None)
        if self._elevation is None and self._thread is None:
            self._start_terrain_fetch()

    # ── terrain (cache-first, off-thread) ─────────────────────────────────

    def _boundary_latlng(self):
        from src.scene_contract import _boundary_ring
        return _boundary_ring(self._main._project)

    def _start_terrain_fetch(self):
        boundary = self._boundary_latlng()
        site_config = (self._main._project.get("properties", {})
                       or {}).get("site_config", {}) or {}
        if not boundary and site_config.get("latitude") is None:
            return    # nowhere to fetch terrain for
        self._thread = QThread(self)
        self._worker = _TerrainWorker(boundary, site_config)
        self._worker.moveToThread(self._thread)
        self._thread.started.connect(self._worker.run)
        self._worker.done.connect(self._on_terrain_done)
        self._worker.done.connect(self._thread.quit)
        self._thread.finished.connect(self._cleanup_thread)
        self._thread.start()

    def _on_terrain_done(self, elevation):
        if elevation:
            self._elevation = elevation
            self._push_scene()

    def _cleanup_thread(self):
        if self._thread is not None:
            self._thread.deleteLater()
        self._thread = None
        self._worker = None

    def closeEvent(self, event):
        t = self._thread
        if t is not None and t.isRunning():
            t.quit()
            t.wait(2000)
        super().closeEvent(event)


def open_3d_view(main) -> Scene3DWindow:
    """Show (or raise) the singleton 3D preview for ``main``'s design."""
    win = getattr(main, "_scene3d_window", None)
    if win is None:
        win = Scene3DWindow(main)
        main._scene3d_window = win
    win.show()
    win.raise_()
    win.activateWindow()
    win.refresh()
    return win
