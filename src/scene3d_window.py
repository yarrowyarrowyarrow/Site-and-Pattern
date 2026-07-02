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

from PyQt6.QtCore import Qt, QObject, QThread, QSettings, pyqtSignal
from PyQt6.QtWidgets import (
    QComboBox, QHBoxLayout, QLabel, QPushButton, QSlider, QVBoxLayout, QWidget,
)

from src.map3d_widget import Map3DWidget
from src.scene_contract import build_scene
from src.branding import APP_NAME

_MAX_YEAR = 25
_MONTH_NAMES = ["Jan", "Feb", "Mar", "Apr", "May", "Jun",
                "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
_MONTH_FULL = ["January", "February", "March", "April", "May", "June",
               "July", "August", "September", "October", "November", "December"]
_DETAIL_KEY = "viewer3d/detail"            # 0 Low · 1 Medium · 2 High (shared w/ gallery)
_DETAIL_LABELS = ["Low", "Medium", "High"]


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
        self.setWindowTitle(f"{APP_NAME}: 3D Preview")
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
        self._month_lbl = QLabel()          # shows the current month name
        self._hour = QSlider(Qt.Orientation.Horizontal)
        self._hour.setRange(5, 21)
        self._hour.setValue(13)
        self._sun_lbl = QLabel()
        self._month.valueChanged.connect(self._on_controls_changed)
        self._hour.valueChanged.connect(self._on_controls_changed)

        self._year.setToolTip("Watch the design grow — drag to a future year")
        self._month.setToolTip("Season — shifts foliage colour and the sun")
        self._hour.setToolTip("Time of day — drives the shadow-casting sun")

        # Detail / quality — lower it if the 3D view is sluggish on this machine
        # (drives window.permaSetQuality in the viewer). Shared with the gallery.
        self._detail = QComboBox()
        self._detail.addItems(_DETAIL_LABELS)
        self._detail.setToolTip(
            "Geometry detail — lower it if the 3D view is sluggish on this machine")
        self._detail.setCurrentIndex(
            max(0, min(2, int(QSettings().value(_DETAIL_KEY, 1)))))
        self._detail.currentIndexChanged.connect(self._on_detail)

        refresh = QPushButton("Refresh from design")
        refresh.setToolTip("Re-read the live project and rebuild the scene")
        refresh.clicked.connect(self.refresh)

        # The camera now stays put while the sliders move; this re-centers it.
        reset_view = QPushButton("Reset view")
        reset_view.setToolTip("Re-center the camera on the design")
        reset_view.clicked.connect(
            lambda: self.viewer.run_js(
                "window.permaResetView && window.permaResetView();"))

        # Bake the loaded Gaussian-splat backdrop to a top-down "yard photo"
        # for the 2D map (V1.65). Enabled only when the project has a splat.
        self._bake_btn = QPushButton("📷 Add yard photo to map")
        self._bake_btn.setToolTip(
            "Render the photoreal scan straight down and add it to the 2D map "
            "as a personal satellite layer")
        self._bake_btn.setEnabled(False)
        self._bake_btn.clicked.connect(self._on_bake_yard_photo)

        # "Fly as a pollinator" — first-person fly-through (F37 increment 2; V2.12
        # adds butterflies & moths). Pick a native bee, butterfly or moth, then
        # drop into a low fly camera: its adult nectar plants are glowing beacons
        # (bloom-gated), a butterfly/moth also shows its caterpillar-host plants.
        self._bee_combo = QComboBox()
        self._bee_combo.setToolTip(
            "Choose a native pollinator — a bee, butterfly or moth. Its nectar "
            "plants get marked in the fly view (butterflies/moths also show "
            "their caterpillar host plants).")
        self._populate_creature_combo()
        self._bee_combo.currentIndexChanged.connect(self._on_bee_target_changed)
        self._bee_btn = QPushButton("🐝 Fly as a bee")
        self._bee_btn.setCheckable(True)
        self._bee_btn.setToolTip(
            "Drop into a first-person nectar run — WASD/arrows to fly, "
            "Q/E up-down, drag to look, F flies you to the nearest flower. "
            "Brush a glowing flower to collect its nectar.")
        self._bee_btn.toggled.connect(self._on_bee_mode)

        # "Tour the year" — auto-hop flower to flower while the season advances
        # under you, so you watch the design's bloom succession (V2.12). Steps
        # the month through the creature's flight season on a timer.
        self._tour_btn = QPushButton("🌸 Tour the year")
        self._tour_btn.setCheckable(True)
        self._tour_btn.setToolTip(
            "Fly a hands-free tour: the flyer visits each flower in turn while "
            "the months roll forward, revealing what blooms when for this "
            "creature. Toggle off to take back the controls.")
        self._tour_btn.toggled.connect(self._on_tour)
        self._tour_months: list = []          # flight months of the current creature
        self._tour_timer = None

        # "Walk the garden" — third-person stroll among the ambient wildlife
        # (V2.12). Mutually exclusive with the first-person fly view.
        self._walk_btn = QPushButton("🚶 Walk the garden")
        self._walk_btn.setCheckable(True)
        self._walk_btn.setToolTip(
            "Stroll through your design in third person — WASD/arrows to walk, "
            "drag to look around — and meet the bees, butterflies, birds and "
            "other creatures your plants support.")
        self._walk_btn.toggled.connect(self._on_walk)

        # "Show its plants" — spotlight (illuminate + a touring creature) the
        # plants in THIS design that the chosen creature benefits from (V2.12).
        self._spot_btn = QPushButton("✨ Show its plants")
        self._spot_btn.setCheckable(True)
        self._spot_btn.setToolTip(
            "Light up the plants in your design that feed or host the selected "
            "creature, and send one of it to visit each — an at-a-glance answer "
            "to 'which of my plants help this bee / butterfly?'")
        self._spot_btn.toggled.connect(self._on_spotlight)

        self._last_origin = None

        bar = QHBoxLayout()
        bar.addWidget(QLabel("Year:"))
        bar.addWidget(self._year, 2)
        bar.addWidget(self._year_lbl)
        bar.addSpacing(16)
        bar.addWidget(QLabel("Time of year:"))
        bar.addWidget(self._month, 1)
        bar.addWidget(self._month_lbl)
        bar.addWidget(QLabel("Time of day:"))
        bar.addWidget(self._hour, 1)
        bar.addWidget(self._sun_lbl)
        bar.addSpacing(16)
        bar.addWidget(QLabel("Detail:"))
        bar.addWidget(self._detail)
        bar.addWidget(reset_view)
        bar.addWidget(refresh)
        bar.addWidget(self._bake_btn)
        bar.addSpacing(16)
        bar.addWidget(self._bee_combo)
        bar.addWidget(self._bee_btn)
        bar.addWidget(self._tour_btn)
        bar.addWidget(self._walk_btn)
        bar.addWidget(self._spot_btn)

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
        self._month_lbl.setText(_MONTH_FULL[self._month.value() - 1])
        self._sun_lbl.setText(f"{self._hour.value()}:00")

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
        # Remember the origin so a yard-photo bake frames the splat correctly,
        # and keep the built scene for the "show its plants" spotlight.
        self._last_origin = scene.get("origin")
        self._scene = scene
        self.viewer.apply_scene(scene)
        # Ambient wildlife: the animals the design's plants support, placed on
        # the plants they use (V2.12). Recomputed each push so it tracks the
        # year/season. Never let a data hiccup break the scene.
        try:
            from src.scene_wildlife import wildlife_for_scene
            self.viewer.set_wildlife(wildlife_for_scene(scene))
        except Exception:      # noqa: BLE001
            self.viewer.set_wildlife([])
        # Keep an active "show its plants" spotlight in sync with the new scene.
        if getattr(self, "_spot_btn", None) is not None and self._spot_btn.isChecked():
            self._push_spotlight()

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

    def _on_detail(self, level: int):
        """Detail combo → viewer quality. The viewer re-renders the current
        scene at the new density itself (build-time only)."""
        QSettings().setValue(_DETAIL_KEY, int(level))
        self.viewer.set_quality(level)

    # ── "Fly as a pollinator" (F37 increment 2; butterflies/moths V2.12) ──

    def _populate_creature_combo(self):
        """Fill the target-creature combo: native bees grouped genus-first (as
        the analysis panel's Bees tab), then a Butterflies & Moths section. Each
        selectable item's userData is a dict describing the creature."""
        combo = self._bee_combo
        combo.blockSignals(True)
        combo.clear()

        def _header(text):
            combo.addItem(text, userData=None)
            item = combo.model().item(combo.count() - 1)
            if item is not None:
                item.setEnabled(False)

        try:
            from src.bee_habitat import list_target_bees
            bees = list_target_bees()
        except Exception:      # noqa: BLE001 — never let a data issue break the window
            bees = []
        current_genus = None
        for b in bees:
            if b["genus"] != current_genus:
                current_genus = b["genus"]
                _header(f"── {current_genus} ──")
            label = (f"    {b['common_name']} (any {b['genus']})" if b["is_group"]
                     else f"    {b['common_name']}")
            combo.addItem(label, userData={"taxon": "bee", "fid": b["id"],
                                           "kind": "bee", "name": b["common_name"]})

        try:
            from src.lep_habitat import list_target_lepidoptera
            leps = list_target_lepidoptera()
        except Exception:      # noqa: BLE001
            leps = []
        if leps:
            _header("── Butterflies & Moths ──")
            for lp in leps:
                # 'skipper' flies like a butterfly for our purposes.
                kind = "moth" if lp["kind"] == "moth" else "butterfly"
                icon = "🦋" if kind == "butterfly" else "🌙"
                combo.addItem(f"    {icon} {lp['common_name']}",
                              userData={"taxon": "lep", "fid": lp["id"],
                                        "kind": kind, "name": lp["common_name"]})

        combo.blockSignals(False)
        for i in range(combo.count()):
            if combo.itemData(i) is not None:
                combo.setCurrentIndex(i)
                break

    def _current_creature(self):
        """The selected creature dict, or None on a disabled header row."""
        return self._bee_combo.itemData(self._bee_combo.currentIndex())

    def _fly_verb(self, creature) -> str:
        kind = (creature or {}).get("kind", "bee")
        return {"bee": "🐝 Fly as a bee", "butterfly": "🦋 Fly as a butterfly",
                "moth": "🌙 Fly as a moth"}.get(kind, "🐝 Fly as a bee")

    def _push_targets(self):
        """Push the selected creature's plant selections + avatar kind to the
        viewer, and remember its flight months for the seasonal tour."""
        creature = self._current_creature()
        self._tour_months = []
        if creature is None:
            self.viewer.set_bee_targets([], "", "bee", [])
            return
        fid, kind, name = creature["fid"], creature["kind"], creature["name"]
        nectar_ids: list = []
        host_ids: list = []
        appearance = None
        try:
            if creature["taxon"] == "bee":
                from src.bee_habitat import (target_plant_ids_for_bee,
                                             flight_months_for_bee)
                nectar_ids = target_plant_ids_for_bee(fid)
                self._tour_months = flight_months_for_bee(fid)
            else:
                from src.lep_habitat import (nectar_plant_ids_for_lep,
                                             larval_host_ids_for_lep,
                                             flight_months_for_lep)
                nectar_ids = nectar_plant_ids_for_lep(fid)
                host_ids = larval_host_ids_for_lep(fid)
                self._tour_months = flight_months_for_lep(fid)
            from src.scene_wildlife import appearance_for_fauna
            appearance = appearance_for_fauna(fid)   # style the avatar to species
        except Exception:      # noqa: BLE001
            nectar_ids, host_ids = [], []
        self.viewer.set_bee_targets(nectar_ids, name, kind, host_ids, appearance)

    def _on_bee_mode(self, on: bool):
        """Toggle the first-person fly view. Pushes the current creature's target
        plants before entering so the beacons are ready."""
        if on:
            if self._walk_btn.isChecked():      # fly and walk are exclusive
                self._walk_btn.setChecked(False)
            self._push_targets()
        else:
            # Leaving fly mode also ends any running tour.
            if self._tour_btn.isChecked():
                self._tour_btn.setChecked(False)
        self.viewer.set_bee_mode(on)

    def _on_walk(self, on: bool):
        """Toggle the third-person walk-through. Exclusive with the fly view."""
        if on and self._bee_btn.isChecked():
            self._bee_btn.setChecked(False)     # leaves fly mode first
        self.viewer.set_walk_mode(on)

    # ── "Show its plants" spotlight (V2.12) ───────────────────────────────

    def _creature_plant_ids(self, creature) -> list:
        """DB plant ids the creature benefits from: a bee's forage, or a
        butterfly/moth's nectar + larval-host plants."""
        fid = creature["fid"]
        try:
            if creature["taxon"] == "bee":
                from src.bee_habitat import target_plant_ids_for_bee
                return target_plant_ids_for_bee(fid)
            from src.lep_habitat import (nectar_plant_ids_for_lep,
                                         larval_host_ids_for_lep)
            return sorted(set(nectar_plant_ids_for_lep(fid))
                          | set(larval_host_ids_for_lep(fid)))
        except Exception:      # noqa: BLE001
            return []

    def _push_spotlight(self):
        """Build the spotlight item list (the design's plants the selected
        creature uses) and push it, with the creature's avatar appearance."""
        creature = self._current_creature()
        scene = getattr(self, "_scene", None)
        if creature is None or not scene:
            self.viewer.set_plant_spotlight([])
            return
        used = set(self._creature_plant_ids(creature))
        items = [{"plant_id": p["plant_id"], "name": p.get("common_name", ""),
                  "x": p["x"], "y": p["y"], "h": p.get("height_m", 1.0)}
                 for p in scene.get("plants", [])
                 if p.get("plant_id") in used]
        appearance = None
        try:
            from src.scene_wildlife import appearance_for_fauna
            appearance = appearance_for_fauna(creature["fid"])
        except Exception:      # noqa: BLE001
            pass
        self.viewer.set_plant_spotlight(items, appearance)

    def _on_spotlight(self, on: bool):
        """Toggle the spotlight. Exclusive with fly mode (it's an orbit/walk
        overlay); pushes an empty list to clear."""
        if on:
            if self._bee_btn.isChecked():
                self._bee_btn.setChecked(False)
            self._push_spotlight()
        else:
            self.viewer.set_plant_spotlight([])

    def _on_bee_target_changed(self, *_):
        self._bee_btn.setText(self._fly_verb(self._current_creature()))
        if self._bee_btn.isChecked():
            self._push_targets()
        if getattr(self, "_spot_btn", None) is not None and self._spot_btn.isChecked():
            self._push_spotlight()

    # ── Seasonal "Tour the year" (V2.12) ──────────────────────────────────

    def _on_tour(self, on: bool):
        """Start/stop the hands-free seasonal tour. Ensures fly mode is on, tells
        the viewer to auto-hop flowers, and steps the month on a timer so the
        blooms change across the creature's flight season."""
        from PyQt6.QtCore import QTimer
        if on:
            if not self._bee_btn.isChecked():
                self._bee_btn.setChecked(True)   # enters fly mode + pushes targets
            self.viewer.set_bee_tour(True)
            if self._tour_timer is None:
                self._tour_timer = QTimer(self)
                self._tour_timer.timeout.connect(self._advance_tour_month)
            self._tour_timer.start(4000)
        else:
            if self._tour_timer is not None:
                self._tour_timer.stop()
            self.viewer.set_bee_tour(False)

    def _advance_tour_month(self):
        """Move the month slider to the creature's next flight month (cycling),
        or through all twelve when the flight season is undocumented. Changing
        the slider re-pushes the scene, which the viewer keeps in step (the
        camera stays put in fly mode)."""
        months = self._tour_months or list(range(1, 13))
        cur = self._month.value()
        later = [m for m in months if m > cur]
        nxt = later[0] if later else months[0]
        self._month.setValue(nxt)            # → _on_controls_changed → _push_scene

    def refresh(self):
        """Re-read the live project (and kick a terrain fetch if we don't
        have a grid yet)."""
        # Apply the saved detail level before the first scene push so the
        # initial build honours it (queued until the viewer's JS is ready).
        self.viewer.set_quality(self._detail.currentIndex())
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
        if self._tour_timer is not None:
            self._tour_timer.stop()
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
