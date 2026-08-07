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

import threading
from datetime import datetime

from PyQt6.QtCore import Qt, QObject, QThread, QSettings, pyqtSignal
from PyQt6.QtWidgets import (
    QComboBox, QHBoxLayout, QLabel, QPushButton, QSlider, QVBoxLayout, QWidget,
)

from src.map3d_widget import Map3DWidget
from src.scene_contract import build_scene
from src.branding import APP_NAME

# V2.44: these three now live in src/scene3d_toolbar.py, which is the module
# the *reference* window builds its controls from. Two windows drive one viewer
# and the author asked for their controls to match — so the numbers and labels
# have exactly one home, and `tests/test_scene3d_toolbar.py` fails the build if
# the two windows stop offering the same viewer controls.
#
# This window keeps its own hand-built bar rather than embedding the widget:
# `self._year` / `self._month` / `self._hour` / `self._detail` are read from a
# dozen places here (`_when`, `_push_scene`, `_update_labels`, the flyover's
# month stepping), and swapping them for the widget is a mechanical but wide
# change to a working 868-line file that this increment does not need to make.
# The guard test is what stops the two drifting; the extraction is available
# when this file next needs splitting anyway.
from src.scene3d_toolbar import (
    MAX_YEAR as _MAX_YEAR,
    DETAIL_KEY as _DETAIL_KEY,
    DETAIL_LABELS as _DETAIL_LABELS,
    CREATURE_SCALES as _CREATURE_SCALES,
    CREATURE_SCALE_KEY as _CREATURE_SCALE_KEY,
    Scene3DToolBar,
)
# V2.46: plant / remove / net in the design itself. The buttons, the mode and
# the bridge slots all live there, so this window gains one layout call.
from src import scene3d_edit_flow as edit_flow

_MONTH_NAMES = ["Jan", "Feb", "Mar", "Apr", "May", "Jun",
                "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
_MONTH_FULL = ["January", "February", "March", "April", "May", "June",
               "July", "August", "September", "October", "November", "December"]


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


class _PhotoWarmWorker(QObject):
    """Fill the species-photo cache off the UI thread (src/photo_warm.py).

    Emits ``batch`` every so often rather than per photo: the only thing the
    window does with it is re-push the dossier so newly-cached photos appear, and
    doing that ~380 times would rebuild the whole dossier for each one.
    """
    batch = pyqtSignal()
    done = pyqtSignal()
    _BATCH = 12

    def __init__(self):
        super().__init__()
        # Owned here, not by the warmer: closeEvent can fire before run() has
        # built one (the catalogue query happens first), and a cancel that landed
        # in that window would be lost.
        self._cancel = threading.Event()

    def run(self):
        try:
            from src.photo_warm import PhotoWarmer, catalogue_photo_rows
            rows = catalogue_photo_rows()
            PhotoWarmer(rows, on_progress=self._progress,
                        cancel_event=self._cancel).run()
        except Exception:      # noqa: BLE001 — photos are a nicety, never a dep
            pass
        self.done.emit()

    def _progress(self, done, _total, newly_cached):
        if newly_cached and done % self._BATCH == 0:
            self.batch.emit()

    def cancel(self):
        self._cancel.set()


_MONTHS = ("January", "February", "March", "April", "May", "June", "July",
           "August", "September", "October", "November", "December")


def _save_data_url(url: str, path: str) -> bool:
    """Write a ``data:image/...;base64,`` URL to disk. False if there isn't one."""
    import base64
    if not url or "," not in url:
        return False
    try:
        with open(path, "wb") as fh:
            fh.write(base64.b64decode(url.split(",", 1)[1]))
        return True
    except (OSError, ValueError):
        return False


class Scene3DWindow(QWidget):
    """3D preview of the current design (growth year + sun controls)."""

    def __init__(self, main):
        super().__init__(None)   # top-level window
        self._main = main
        self._elevation = None
        self._thread = None
        self._worker = None
        self._photo_thread = None
        self._photo_worker = None
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
        # Full 24 h so you can drag into night — a moonlit scene with moths & bats
        # instead of the day's bees & butterflies (V2.12).
        self._hour.setRange(0, 23)
        self._hour.setValue(13)
        self._sun_lbl = QLabel()
        self._month.valueChanged.connect(self._on_controls_changed)
        self._hour.valueChanged.connect(self._on_controls_changed)

        self._year.setToolTip("Watch the design grow — drag to a future year")
        self._month.setToolTip("Season — shifts foliage colour and the sun")
        self._hour.setToolTip(
            "Time of day — drives the sun; drag past dusk for a moonlit night "
            "(moths, bats and glowing blooms)")

        # Detail / quality — lower it if the 3D view is sluggish on this machine
        # (drives window.permaSetQuality in the viewer). Shared with the gallery.
        self._detail = QComboBox()
        self._detail.addItems(_DETAIL_LABELS)
        self._detail.setToolTip(
            "Stylised — faceted low-poly plants: a clear diagram of the "
            "planting, and by far the fastest\n"
            "Balanced — the built-in geometry\n"
            "Lifelike — the full modelled library: real leaves, bark grain "
            "and species silhouettes")
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

        # A render you can put in a proposal (F69). The docent's beats have
        # carried a camera, a year and a season since V2.13 and nothing read
        # them; this places the camera at the beat's own preset, renders the
        # real viewer offscreen at print resolution, and saves a PNG.
        self._still_btn = QPushButton("🖼 Presentation still…")
        self._still_btn.setToolTip(
            "Render this design at print resolution — pick the moment and the "
            "viewpoint, and save an image for a proposal or a printout")
        self._still_btn.clicked.connect(self._on_presentation_still)

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

        # "Flyover" — a hands-free cinematic tour that grows the design, cycles
        # the seasons, and dips into night, while the camera slowly orbits: the
        # lawn-to-habitat pitch in ~60 s (V2.13).
        self._fly_btn = QPushButton("🎬 Flyover")
        self._fly_btn.setCheckable(True)
        self._fly_btn.setToolTip(
            "Play a cinematic tour: watch the design grow year by year, the "
            "seasons turn, and night fall — with the camera orbiting. Toggle "
            "off to take back the controls.")
        self._fly_btn.toggled.connect(self._on_flyover)
        self._fly_timer = None
        self._fly_frames: list = []
        self._fly_idx = 0

        # "Identify" — the "who lives here" roster + always-on name labels over
        # the ambient wildlife, so you can read the scene without hovering (V2.13).
        self._id_btn = QPushButton("🔎 Identify")
        self._id_btn.setCheckable(True)
        self._id_btn.setToolTip(
            "Label every creature and list who lives here — the wildlife your "
            "plants support, without having to hover.")
        self._id_btn.toggled.connect(
            lambda on: self.viewer.set_wildlife_labels(on))

        # How big the creatures are drawn (V2.46). Life size is the default and
        # the truth — every animal is scaled from its real measurement now — so
        # this exists to get a *look* at an 11 mm bee without the app quietly
        # lying about its size. Same list as the shared toolbar's, imported
        # rather than restated so the two windows cannot offer different
        # magnifications.
        self._creature_scale = QComboBox()
        for _label, _mult in _CREATURE_SCALES:
            self._creature_scale.addItem(_label)
        self._creature_scale.setToolTip(
            "How big the creatures are drawn.\n"
            "Life size is the truth — scaled from real measured body length "
            "or wingspan, so a leafcutter bee really is 11 mm beside a 1.75 m "
            "person.\nThe magnifications are for getting a look at one; the "
            "number says how much it is being exaggerated by.")
        self._creature_scale.setCurrentIndex(
            Scene3DToolBar.stored_creature_scale_index())
        self._creature_scale.currentIndexChanged.connect(
            self._on_creature_scale)

        self._last_origin = None

        # Row 1 — the "when / how it looks" scene controls.
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
        bar.addWidget(self._still_btn)

        # Row 2 — how you move through the scene first, then whose eyes you
        # borrow. The old order led with "Creature: [combo]", so the strip
        # opened by asking you to pick a bee before anything had said why you
        # would want one; walking your own garden is the thing most people came
        # for and it needs no setup (V2.37 user feedback: "walk the garden
        # should be the first option, fly as creature should be second and
        # choosing the creature should be 3rd").
        #
        # The grouping follows the real dependency: Walk / Flyover / Identify
        # stand alone, while Fly / Tour / Show its plants all read the creature
        # combo, so the combo sits with them rather than ahead of everything.
        bar2 = QHBoxLayout()
        bar2.addWidget(QLabel("View:"))
        bar2.addWidget(self._walk_btn)
        bar2.addWidget(self._fly_btn)
        bar2.addWidget(self._id_btn)
        bar2.addWidget(QLabel("Creatures:"))
        bar2.addWidget(self._creature_scale)
        bar2.addSpacing(16)
        bar2.addWidget(self._bee_btn)
        bar2.addWidget(self._bee_combo)
        bar2.addWidget(self._tour_btn)
        bar2.addWidget(self._spot_btn)
        bar2.addStretch(1)

        # Row 3 — the trowel, the same three verbs the reference sandbox has
        # had since V2.43/V2.44 (V2.46). *"I want the 3D view and the tour a
        # reference ecosystem to have the same functionality."* The viewer was
        # already capable of all of it — 16-editing.js does not know which
        # window it is in — so this is the missing Python side, and it lives in
        # src/scene3d_edit_flow.py because a design edit is not a sandbox edit:
        # it goes on the undo stack, redraws the map, and counts toward the
        # score.
        bar3 = edit_flow.build_tools(self)

        root = QVBoxLayout(self)
        root.setContentsMargins(6, 6, 6, 6)
        root.addLayout(bar)
        root.addLayout(bar2)
        root.addLayout(bar3)
        root.addWidget(self.viewer, 1)

        self._update_labels()
        self._editable = edit_flow.connect_bridge(self)

    def _current_plant_pick(self) -> dict | None:
        """What the Plants panel has selected, as ``{plant_id, common_name}``.

        Deliberately the *same* selection the map's "Place" button uses rather
        than a second species combo in this window: picking a plant in one
        place and planting it in another is one decision, and two pickers that
        can disagree is how a user ends up planting something they did not
        choose.
        """
        try:
            sel = self._main.plant_panel.selected_plant()
        except Exception:      # noqa: BLE001
            return None
        if not sel or not sel.get("id"):
            return None
        return {"plant_id": int(sel["id"]),
                "common_name": sel.get("common_name") or "plant"}

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
            from src.scene_wildlife import wildlife_for_scene, support_by_taxon
            pids = [p["plant_id"] for p in scene.get("plants", [])
                    if p.get("plant_id")]
            self.viewer.set_wildlife(wildlife_for_scene(scene),
                                     support_by_taxon(pids))
        except Exception:      # noqa: BLE001
            self.viewer.set_wildlife([])
        # The magnification lives in the viewer and resets to life size on a
        # fresh page, so a remembered choice has to be re-pushed rather than
        # assumed (V2.46).
        self.viewer.set_creature_scale(
            _CREATURE_SCALES[self._creature_scale.currentIndex()][1])
        # Click-to-inspect content (V2.29): the sourced ecology behind every
        # species on screen, pushed with the scene so a click opens a card with
        # no round trip. Re-pushed each time because the growth/season sliders
        # change what the card says ("size over time" marks the current year).
        try:
            from src.scene_dossier import build_dossier
            self.viewer.set_dossier(build_dossier(scene))
        except Exception:      # noqa: BLE001 — the card is a read nicety
            self.viewer.set_dossier({})
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

    # ── the presentation still (F69) ────────────────────────────────────────

    def _on_presentation_still(self):
        """Render the design at print resolution and save it.

        The stills come from the docent script, so the choices on offer are the
        ones the app already knows how to narrate — "the design at year 12, in
        August, from the sidewalk" — rather than a bare year/month/camera form.
        """
        from PyQt6.QtWidgets import QFileDialog, QInputDialog
        from src import presentation_still as ps

        stills = ps.presentation_stills(self._main._project)
        cover = ps.cover_still(self._main._project)
        options, specs = [], []
        for st in ([cover] if cover else []) + stills:
            label = (f"{st['title']} — year {st['year']}, "
                     f"{_MONTHS[st['month'] - 1]}, {st['camera']}")
            if label in options:
                continue
            options.append(label)
            specs.append(st)
        if not options:
            return
        choice, ok = QInputDialog.getItem(
            self, "Presentation still", "Moment and viewpoint:",
            options, 0, False)
        if not ok:
            return
        spec = specs[options.index(choice)]
        path, _ = QFileDialog.getSaveFileName(
            self, "Save presentation still",
            f"design-year{spec['year']}.png", "PNG image (*.png)")
        if not path:
            return
        self._render_still(spec, path)

    def _render_still(self, spec, path):
        """Set the scene to the still's moment, then capture it.

        Two QTimer hops rather than one call: the sliders have to re-push the
        scene and the camera preset has to land in the viewer before the
        renderer is asked for a frame, and the bridge is one-directional so
        there is nothing to await. The sprite gallery's contact sheet chains
        the same way.
        """
        from PyQt6.QtCore import QTimer
        from src import presentation_still as ps
        req = ps.render_request(spec)
        for widget, value in ((self._year, spec["year"]),
                              (self._month, spec["month"])):
            widget.blockSignals(True)
            widget.setValue(value)
            widget.blockSignals(False)
        self._update_labels()
        self._push_scene()
        self.viewer.set_camera_preset(req["camera"])

        def _capture():
            def _done(url):
                if _save_data_url(url, path):
                    self._main.statusBar().showMessage(
                        f"Presentation still saved to {path}", 6000)
                else:
                    self._main.statusBar().showMessage(
                        "Could not render the still — let the 3D view finish "
                        "loading and try again.", 6000)
            self.viewer.snapshot(_done, px=req["width"], height=req["height"],
                                 pixel_ratio=req["pixel_ratio"],
                                 mime="image/png", quality=1.0)

        QTimer.singleShot(450, _capture)

    def _on_controls_changed(self, *_):
        self._update_labels()
        self._push_scene()

    def _on_creature_scale(self, idx: int):
        idx = max(0, min(len(_CREATURE_SCALES) - 1, int(idx)))
        QSettings().setValue(_CREATURE_SCALE_KEY, idx)
        self.viewer.set_creature_scale(_CREATURE_SCALES[idx][1])

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
            for b in (self._walk_btn, self._fly_btn):   # fly view is exclusive
                if b.isChecked():
                    b.setChecked(False)
            self._push_targets()
        else:
            # Leaving fly mode also ends any running tour.
            if self._tour_btn.isChecked():
                self._tour_btn.setChecked(False)
        self.viewer.set_bee_mode(on)

    def _on_walk(self, on: bool):
        """Toggle the third-person walk-through. Exclusive with fly + flyover."""
        if on:
            for b in (self._bee_btn, self._fly_btn):
                if b.isChecked():
                    b.setChecked(False)
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
            for b in (self._bee_btn, self._fly_btn):
                if b.isChecked():
                    b.setChecked(False)
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

    # ── Cinematic "Flyover" (V2.13) ───────────────────────────────────────

    @staticmethod
    def _flyover_storyboard() -> list:
        """A ~60 s, three-act storyboard as (year, month, hour, big, sub)
        keyframes. Act 1 grows the design at peak-summer midday; act 2 turns the
        seasons at maturity; act 3 falls into a moonlit night."""
        frames = []
        # Act 1 — growth (year 0 → mature), July midday.
        for y in (0, 1, 2, 3, 5, 7, 9, 12, 15, 18, 22, 25):
            sub = ("the lawn, today" if y == 0 else
                   "seedlings in" if y <= 2 else
                   "filling in" if y <= 9 else
                   "a young habitat" if y <= 18 else "grown, not designed")
            frames.append((y, 7, 13, f"Year {y}", sub))
        # Act 2 — the seasons turn, at maturity.
        season = {3: "spring green", 5: "first blooms", 7: "high summer",
                  9: "autumn seed & fruit", 11: "bare stems, standing seed"}
        for m in (3, 5, 7, 9, 11):
            frames.append((25, m, 13, _MONTH_FULL[m - 1], season[m]))
        # Act 3 — into the night (moths, bats, glowing blooms).
        frames.append((25, 7, 18, "Evening", "the day shift clocks off"))
        frames.append((25, 7, 21, "Dusk", "hawkmoths on the wing"))
        frames.append((25, 7, 23, "Night", "moths, bats & moonlit blooms"))
        return frames

    def _on_flyover(self, on: bool):
        """Start/stop the cinematic flyover. Turns off the interactive modes,
        enables the viewer's auto-orbit, and steps the storyboard on a timer."""
        from PyQt6.QtCore import QTimer
        if on:
            for b in (self._bee_btn, self._walk_btn, self._spot_btn):
                if b.isChecked():
                    b.setChecked(False)
            self.viewer.set_cinematic(True)
            self._fly_frames = self._flyover_storyboard()
            self._fly_idx = 0
            if self._fly_timer is None:
                self._fly_timer = QTimer(self)
                self._fly_timer.timeout.connect(self._advance_flyover)
            self._advance_flyover()               # show the first beat at once
            self._fly_timer.start(2200)
        else:
            if self._fly_timer is not None:
                self._fly_timer.stop()
            self.viewer.set_cinematic(False)

    def _advance_flyover(self):
        """Apply the next storyboard keyframe (looping), pushing the scene once
        and updating the caption."""
        if not self._fly_frames:
            return
        year, month, hour, big, sub = self._fly_frames[self._fly_idx]
        self._fly_idx = (self._fly_idx + 1) % len(self._fly_frames)
        # Set all three sliders without three separate scene pushes.
        for w, v in ((self._year, year), (self._month, month), (self._hour, hour)):
            w.blockSignals(True); w.setValue(v); w.blockSignals(False)
        self._update_labels()
        self.viewer.set_cinematic_caption(big, sub)
        self._push_scene()

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
        self._start_photo_warm()

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

    # ── species photos (cache warm, off-thread) ───────────────────────────────

    def _start_photo_warm(self):
        """Warm the whole catalogue's photos in the background.

        The dossier only ever sends photos that are already cached (it must not
        block a push), so without this the first click on a species shows no
        photo and the second one does. Runs once per window; failures are silent.
        """
        if self._photo_thread is not None:
            return
        self._photo_thread = QThread(self)
        self._photo_worker = _PhotoWarmWorker()
        self._photo_worker.moveToThread(self._photo_thread)
        self._photo_thread.started.connect(self._photo_worker.run)
        self._photo_worker.batch.connect(self._on_photos_warmed)
        self._photo_worker.done.connect(self._photo_thread.quit)
        self._photo_thread.finished.connect(self._cleanup_photo_thread)
        self._photo_thread.start()

    def _on_photos_warmed(self):
        """Re-push the dossier so photos that just landed show on the next click."""
        try:
            from src.scene_dossier import build_dossier
            scene = getattr(self, "_scene", None)
            if scene:
                self.viewer.set_dossier(build_dossier(scene))
        except Exception:      # noqa: BLE001 — the card is a read nicety
            pass

    def _cleanup_photo_thread(self):
        if self._photo_thread is not None:
            self._photo_thread.deleteLater()
        self._photo_thread = None
        self._photo_worker = None

    def _cleanup_thread(self):
        if self._thread is not None:
            self._thread.deleteLater()
        self._thread = None
        self._worker = None

    def closeEvent(self, event):
        if self._tour_timer is not None:
            self._tour_timer.stop()
        if self._fly_timer is not None:
            self._fly_timer.stop()
        t = self._thread
        if t is not None and t.isRunning():
            t.quit()
            t.wait(2000)
        # The warmer sleeps between requests on a cancellable wait, so this
        # returns promptly rather than blocking on an in-flight download.
        if self._photo_worker is not None:
            self._photo_worker.cancel()
        pt = self._photo_thread
        if pt is not None and pt.isRunning():
            pt.quit()
            pt.wait(3000)
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
