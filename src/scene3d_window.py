"""
src/scene3d_window.py — the "3D Preview" window (V1.62).

Hosts a :class:`src.map3d_widget.Map3DWidget` with the controls that make
the 3D view useful for lawn-to-habitat persuasion:

  * **two short rows a homeowner can read (V3.44, F261):** *When*, *Season*
    and *Time of day* as lists of named stops, and *View* (From the street,
    From the house, From above, Walk, Reset view). It opens on the fifth
    summer, in July, mid-afternoon, from the street
    (``src/scene3d_stops.py``);
  * with **Advanced tools** on, the rows it always had: a growth-timeline
    year slider, month + hour sliders driving the shadow-casting sun (same
    ``src/solar`` path as the 2D shade engine, so the two always agree),
    Detail, the Flyover, Identify, the pollinator tools, Plant and Remove,
    and the two outputs. The sliders are the one record of the moment; the
    lists set them and follow them;
  * since V3.08 no Refresh button: the window follows the design, rebuilding
    once edits pause (``src/follow_design.py``, F89).

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

from PyQt6.QtCore import Qt, QThread, QSettings, QTimer
from PyQt6.QtWidgets import (
    QComboBox, QHBoxLayout, QLabel, QPushButton, QSlider, QVBoxLayout, QWidget,
)

from src.map3d_widget import Map3DWidget
from src.scene3d_workers import (PhotoWarmWorker as _PhotoWarmWorker,
                                 TerrainWorker as _TerrainWorker)
from src.scene_contract import build_scene
from src.branding import APP_NAME

# V2.44: these three live in src/scene3d_toolbar.py, which both 3D windows
# build controls from, so the numbers and labels have one home
# (tests/test_viewer_controls.py). V3.44: the two rows a homeowner reads are
# that toolbar's WHEN and VIEWS groups. The fine sliders are still built
# here, because a dozen places read `self._year` / `_month` / `_hour`
# (`_when`, `_push_scene`, the Flyover, the stills, before_after_flow) and
# they are the one record of the moment; the named lists set and follow them.
from src.scene3d_toolbar import (
    MAX_YEAR as _MAX_YEAR,
    DETAIL_KEY as _DETAIL_KEY,
    DETAIL_LABELS as _DETAIL_LABELS,
    Scene3DToolBar, WHEN as _WHEN, VIEWS as _VIEWS,
)
from src import scene3d_creatures as creatures
from src import scene3d_stops as stops
# V2.46: plant / remove / net in the design itself. The buttons, the mode and
# the bridge slots all live there, so this window gains one layout call.
from src import scene3d_edit_flow as edit_flow

#: While a slider moves, at most one scene push in this many milliseconds;
#: the last value always lands (V3.44: a drag of Year was up to 25 pushes).
PUSH_EVERY_MS = 80

_MONTH_FULL = ["January", "February", "March", "April", "May", "June",
               "July", "August", "September", "October", "November", "December"]


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


def keep_still(main, path: str, spec: dict) -> bool:
    """Hold the last presentation still on the main window, as ``(pixmap,
    caption)``, for the PDF export (F123). False when the file will not load."""
    from PyQt6.QtGui import QPixmap
    pixmap = QPixmap(path)
    if pixmap.isNull():
        return False
    caption = (spec.get("caption") or spec.get("title") or "").strip()
    main._presentation_still = (pixmap, caption)
    return True


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
        #: The shade simulation, kept between pushes (build_scene's ``memo``).
        self._memo: dict = {}
        #: The design the opening view was last shown for (its scene origin).
        self._shown_origin = None
        self._creature_chosen = False     # the person picked one themselves
        self._push_waiting = False
        self._push_timer = QTimer(self)
        self._push_timer.setSingleShot(True)
        self._push_timer.setInterval(PUSH_EVERY_MS)
        self._push_timer.timeout.connect(self._on_push_interval)
        self.setWindowTitle(f"{APP_NAME}: 3D Preview")
        self.resize(960, 700)
        # The app's dark surface (F209, V3.08): a top-level window inherits
        # nothing from the main window's stylesheet.
        from src.ui_style import WINDOW_STYLE
        self.setStyleSheet(WINDOW_STYLE)

        self.viewer = Map3DWidget(self)

        self._year = QSlider(Qt.Orientation.Horizontal)
        self._year.setRange(0, _MAX_YEAR)
        self._year.setValue(stops.OPENING["year"])
        self._year_lbl = QLabel()
        self._year.valueChanged.connect(self._on_controls_changed)

        self._month = QSlider(Qt.Orientation.Horizontal)
        self._month.setRange(1, 12)
        self._month.setValue(stops.OPENING["month"])
        self._month_lbl = QLabel()          # shows the current month name
        self._hour = QSlider(Qt.Orientation.Horizontal)
        # Full 24 h so you can drag into night — a moonlit scene with moths & bats
        # instead of the day's bees & butterflies (V2.12).
        self._hour.setRange(0, 23)
        self._hour.setValue(stops.OPENING["hour"])
        self._sun_lbl = QLabel()
        self._month.valueChanged.connect(self._on_controls_changed)
        self._hour.valueChanged.connect(self._on_controls_changed)

        self._year.setToolTip("Watch the design grow — drag to a future year")
        self._month.setToolTip("Season — shifts foliage colour and the sun")
        self._hour.setToolTip(
            "Time of day — drives the sun; drag past dusk for a moonlit night "
            "(moths, bats and glowing blooms)")
        for slider, name in ((self._year, "Year"),
                             (self._month, "Time of year"),
                             (self._hour, "Time of day")):
            slider.setAccessibleName(name)

        # The two rows a homeowner reads (V3.44): the moment as named stops,
        # and where to look from. The sliders above stay the record of the
        # moment (a dozen places read them); these set them and follow them.
        self.when_bar = Scene3DToolBar(
            self, groups=(_WHEN,), year=self._year.value(),
            month=self._month.value(), hour=self._hour.value())
        self.when_bar.year_changed.connect(self._year.setValue)
        self.when_bar.month_changed.connect(self._month.setValue)
        self.when_bar.hour_changed.connect(self._hour.setValue)
        self.view_bar = Scene3DToolBar(self, groups=(_VIEWS,))
        self.view_bar.view_requested.connect(self._show_view)
        self.view_bar.reset_view.connect(
            lambda: self.viewer.run_js(
                "window.permaResetView && window.permaResetView();"))

        # Detail / quality — lower it if the 3D view is sluggish on this machine
        # (drives window.permaSetQuality in the viewer). Shared with the gallery.
        self._detail = QComboBox()
        self._detail.addItems(_DETAIL_LABELS)
        self._detail.setToolTip(
            "Stylised — faceted low-poly plants: a clear diagram of the "
            "planting, and by far the fastest\n"
            "Balanced — the built-in geometry\n"
            "Lifelike — the full modelled library: real leaves, bark grain "
            "and each plant's own shape")
        self._detail.setCurrentIndex(
            max(0, min(2, int(QSettings().value(_DETAIL_KEY, 1)))))
        self._detail.currentIndexChanged.connect(self._on_detail)

        # A render you can put in a proposal (F69). The docent's beats have
        # carried a camera, a year and a season since V2.13 and nothing read
        # them; this places the camera at the beat's own preset, renders the
        # real viewer offscreen at print resolution, and saves a PNG.
        self._still_btn = QPushButton("🖼 Presentation still…")
        self._still_btn.setToolTip(
            "Render this design at print resolution — pick the moment and the "
            "viewpoint, and save an image for a proposal or a printout")
        self._still_btn.clicked.connect(self._on_presentation_still)

        # Before / after / in five years (F76) — the argument a single still
        # cannot make, because a planting is judged on what it becomes.
        self._ba_btn = QPushButton("⏳ Before / after…")
        self._ba_btn.setToolTip(
            "Render your yard now, at year 1 and at year 5 as one page — "
            "included in the next PDF you export")
        self._ba_btn.clicked.connect(self._on_before_after)

        # "Fly as a pollinator" — first-person fly-through (F37 increment 2; V2.12
        # adds butterflies & moths). Pick a native bee, butterfly or moth, then
        # drop into a low fly camera: its adult nectar plants are glowing beacons
        # (bloom-gated), a butterfly/moth also shows its caterpillar-host plants.
        self._bee_combo = QComboBox()
        self._bee_combo.setToolTip(
            "Choose a native pollinator — a bee, butterfly or moth. Its nectar "
            "plants get marked in the fly view (butterflies/moths also show "
            "their caterpillar host plants).")
        self._bee_combo.setAccessibleName("Pollinator")
        self._populate_creature_combo()
        self._bee_combo.currentIndexChanged.connect(self._on_bee_target_changed)
        self._bee_combo.activated.connect(
            lambda _i: setattr(self, "_creature_chosen", True))
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

        # Walk: a third-person stroll among the ambient wildlife (V2.12),
        # mutually exclusive with the first-person fly view. The button is the
        # View row's since V3.44; the handlers below still switch it off.
        self._walk_btn = self.view_bar._walk_btn
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

        self._last_origin = None

        # The rows below are the Advanced tools' (set_advanced_tools).
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
        # V3.05: this row is *when*, and only that. It also held Reset view,
        # Refresh and the three outputs, and at the 1148 px the window opens at
        # on a 1366 x 768 screen those squeezed Year, Time of year and Time of
        # day to 15 px each: a handle that looked like a checkbox, on the
        # controls that watch the design grow (the surface audit measured it).
        for slider in (self._year, self._month, self._hour):
            slider.setMinimumWidth(110)

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
        bar2.addWidget(QLabel("Tour:"))
        bar2.addWidget(self._fly_btn)
        bar2.addSpacing(16)
        bar2.addWidget(QLabel("Wildlife:"))
        bar2.addWidget(self._id_btn)
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
        for btn in (self._still_btn, self._ba_btn):
            bar3.addWidget(btn)

        # One container for everything the Advanced tools add, so nothing else
        # that shows or hides a control inside it is overruled (the Net button
        # follows the walker, for one).
        self.advanced_rows = QWidget(self)
        self.advanced_rows.setAccessibleName("Advanced tools")
        rows = QVBoxLayout(self.advanced_rows)
        rows.setContentsMargins(8, 0, 8, 0)     # in line with the rows above
        for layout in (bar, bar2, bar3):
            rows.addLayout(layout)

        root = QVBoxLayout(self)
        root.setContentsMargins(6, 6, 6, 6)
        root.addWidget(self.when_bar)
        root.addWidget(self.view_bar)
        root.addWidget(self.advanced_rows)
        root.addWidget(self.viewer, 1)

        self._update_labels()
        self._editable = edit_flow.connect_bridge(self)
        from src import advanced_tools
        self.set_advanced_tools(advanced_tools.is_on())

    # ── simple by default (V3.44) ─────────────────────────────────────────

    def set_advanced_tools(self, on: bool) -> None:
        """Show the fine sliders, Detail, the Flyover, Identify, the
        pollinator tools, Plant and Remove and the outputs, or only the two
        short rows. A tool about to be hidden is stopped first, as the switch
        cancels Measure on the map: nothing is left running with no button."""
        if not on:
            for btn in (self._fly_btn, self._tour_btn, self._bee_btn,
                        self._spot_btn, self._id_btn):
                if btn.isChecked():
                    btn.setChecked(False)
            edit_flow.clear_mode(self)
        self.advanced_rows.setVisible(bool(on))

    def _show_view(self, key: str) -> None:
        """Look from a named viewpoint (``scene3d_stops.VIEWS``). Walking, a
        flight and the Flyover own the camera, so each is left first."""
        for btn in (self._walk_btn, self._bee_btn, self._fly_btn):
            if btn.isChecked():
                btn.setChecked(False)
        self.viewer.show_view(key)

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
        self._year_lbl.setText("fully grown" if y == 0 else f"year {y}")
        self._month_lbl.setText(_MONTH_FULL[self._month.value() - 1])
        self._sun_lbl.setText(f"{self._hour.value()}:00")
        # The named stops say what the sliders say, whoever moved them.
        self.when_bar.set_time(year=y, month=self._month.value(),
                               hour=self._hour.value(), quiet=True)
        edit_flow.refresh_hint(self)

    def _push_scene(self):
        self._push_waiting = False
        scene = build_scene(
            self._main._project,
            year=self._year.value(),
            elevation=self._elevation,
            when=self._when(),
            memo=self._memo,
        )
        # Keep the origin and the built scene for the "show its plants"
        # spotlight.
        self._last_origin = scene.get("origin")
        self._scene = scene
        self.viewer.apply_scene(scene)
        self.view_bar.set_view_available(
            "house", "house" in (scene.get("views") or {}), stops.NO_HOUSE)
        if scene.get("origin") != self._shown_origin:
            self._shown_origin = scene.get("origin")
            self._on_new_design(scene)
        # Ambient wildlife: the animals the design's plants support, placed on
        # the plants they use (V2.12). Recomputed each push so it tracks the
        # year/season. Never let a data hiccup break the scene.
        try:
            from src.scene_wildlife import wildlife_for_scene, support_by_taxon
            from src.scene_contract import standing_plants
            pids = [p["plant_id"] for p in standing_plants(scene)
                    if p.get("plant_id")]
            self.viewer.set_wildlife(wildlife_for_scene(scene),
                                     support_by_taxon(pids))
        except Exception:      # noqa: BLE001
            self.viewer.set_wildlife([])
        # Click-to-inspect content (V2.29): the sourced ecology behind every
        # species on screen, pushed with the scene so a click opens a card with
        # no round trip. Re-pushed each time because the growth/season sliders
        # change what the card says ("size over time" marks the current year).
        try:
            from src import walk_cards       # one card for both windows (V3.39)
            self.viewer.set_dossier(walk_cards.build(scene))
        except Exception:      # noqa: BLE001 — the card is a read nicety
            self.viewer.set_dossier({})
        # Keep an active "show its plants" spotlight in sync with the new scene.
        if getattr(self, "_spot_btn", None) is not None and self._spot_btn.isChecked():
            self._push_spotlight()

    def _on_new_design(self, scene: dict) -> None:
        """The first scene of a design (the window just opened, or another
        design was): the opening view (D5: from the street, or from the house
        when the house hides the planting from the street), unless a walk, a
        flight or the Flyover owns the camera, and the pollinator the tools
        start on, unless the person has picked one."""
        if not any(b.isChecked() for b in
                   (self._walk_btn, self._bee_btn, self._fly_btn)):
            from src.scene_views import opening_view
            self.viewer.show_view(opening_view(scene.get("views")))
        if self._creature_chosen:
            return
        from src.scene_contract import standing_plants
        index = creatures.default_row(
            self._creature_rows,
            [p.get("plant_id") for p in standing_plants(scene)])
        if index is not None and index != self._bee_combo.currentIndex():
            self._bee_combo.setCurrentIndex(index)

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
                     f"{_MONTH_FULL[st['month'] - 1]}, {st['camera']}")
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

    def _on_before_after(self):
        """Before / after / in five years (F76) — see before_after_flow."""
        from src import before_after_flow
        return before_after_flow.on_before_after(self)

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
                    # Kept for File → Export PDF (F123, V3.05): the PDF has
                    # drawn a still page since F69, and nothing ever handed
                    # it one. Kept the way before_after_flow keeps F76's.
                    keep_still(self._main, path, spec)
                    self._main.statusBar().showMessage(
                        f"Presentation still saved to {path}; Export PDF "
                        "will include it", 6000)
                else:
                    self._main.statusBar().showMessage(
                        "Could not render the still — let the 3D view finish "
                        "loading and try again.", 6000)
            self.viewer.snapshot(_done, px=req["width"], height=req["height"],
                                 pixel_ratio=req["pixel_ratio"],
                                 mime="image/png", quality=1.0)

        QTimer.singleShot(450, _capture)

    def _on_controls_changed(self, *_):
        """A slider moved. The labels follow at once; the scene is pushed at
        once too unless one was pushed in the last ``PUSH_EVERY_MS``, in which
        case that interval's end pushes whatever the sliders say by then."""
        self._update_labels()
        if self._push_timer.isActive():
            self._push_waiting = True
            return
        self._push_scene()
        self._push_timer.start()

    def _on_push_interval(self):
        """From a timer, so nothing may escape (an exception out of a Qt slot
        ends the process: ``follow_design._rebuild``)."""
        if not self._push_waiting:
            return
        try:
            self._push_scene()
            self._push_timer.start()
        except Exception:                                  # noqa: BLE001
            self._push_waiting = False

    def _on_detail(self, level: int):
        """Detail combo → viewer quality. The viewer re-renders the current
        scene at the new density itself (build-time only)."""
        QSettings().setValue(_DETAIL_KEY, int(level))
        self.viewer.set_quality(level)

    # ── "Fly as a pollinator" (F37 increment 2; butterflies/moths V2.12) ──

    def _populate_creature_combo(self):
        """Fill the pollinator list (``scene3d_creatures.rows``): bees genus
        by genus, then butterflies and moths. A heading cannot be chosen;
        each other item's userData is the creature."""
        combo = self._bee_combo
        combo.blockSignals(True)
        combo.clear()
        self._creature_rows = creatures.rows()
        for label, creature in self._creature_rows:
            combo.addItem(label, userData=creature)
            if creature is None:
                item = combo.model().item(combo.count() - 1)
                if item is not None:
                    item.setEnabled(False)
        combo.blockSignals(False)
        index = creatures.default_row(self._creature_rows, [])
        if index is not None:
            combo.setCurrentIndex(index)

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
        # The net is the walker's tool, so its button follows him (V2.46d).
        edit_flow.set_walking(self, on)

    # ── "Show its plants" spotlight (V2.12) ───────────────────────────────

    def _push_spotlight(self):
        """Build the spotlight item list (the design's plants the selected
        creature uses) and push it, with the creature's avatar appearance."""
        creature = self._current_creature()
        scene = getattr(self, "_scene", None)
        if creature is None or not scene:
            self.viewer.set_plant_spotlight([])
            return
        used = set(creatures.plant_ids_for(creature))
        from src.scene_contract import standing_plants
        items = [{"plant_id": p["plant_id"], "name": p.get("common_name", ""),
                  "x": p["x"], "y": p["y"], "h": p.get("height_m", 1.0)}
                 for p in standing_plants(scene)
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

    def _on_flyover(self, on: bool):
        """Start/stop the cinematic flyover. Turns off the interactive modes,
        enables the viewer's auto-orbit, and steps the storyboard on a timer."""
        from PyQt6.QtCore import QTimer
        if on:
            for b in (self._bee_btn, self._walk_btn, self._spot_btn):
                if b.isChecked():
                    b.setChecked(False)
            self.viewer.set_cinematic(True)
            self._fly_frames = stops.flyover_storyboard()
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

    def follow_design(self):
        """The design changed (``src/follow_design.py``): rebuild the scene,
        as the retired Refresh button did, without warming the photo cache
        again for every edit."""
        self._push_scene()
        if self._elevation is None and self._thread is None:
            self._start_terrain_fetch()

    def refresh(self):
        """Re-read the live project (and kick a terrain fetch if we don't
        have a grid yet)."""
        # Apply the saved detail level before the first scene push so the
        # initial build honours it (queued until the viewer's JS is ready).
        self.viewer.set_quality(self._detail.currentIndex())
        self._push_scene()
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
            from src import walk_cards
            scene = getattr(self, "_scene", None)
            if scene:
                self.viewer.set_dossier(walk_cards.build(scene))
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
        self._push_timer.stop()
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


def open_3d_view(main, view: str = "") -> Scene3DWindow:
    """Show (or raise) the singleton 3D preview for ``main``'s design.

    ``view`` is a named viewpoint to show (``scene3d_stops.VIEWS``): the
    Overview's street item asks for the street. Without one a window already
    open keeps the camera where the person left it."""
    win = getattr(main, "_scene3d_window", None)
    if win is None:
        win = Scene3DWindow(main)
        main._scene3d_window = win
    win.show()
    win.raise_()
    win.activateWindow()
    win.refresh()
    if view:
        win._show_view(view)
    return win


class _ToolsHook:
    """What ``advanced_tools.ADVANCED_HOOKS`` tells the switch's state.

    The main window holds one from the start: the 3D window does not exist
    until it is opened, and the registry's test wants every entry present.
    A window opened later reads the switch itself."""

    def __init__(self, main):
        self._main = main

    def set_advanced_tools(self, on: bool) -> None:
        win = getattr(self._main, "_scene3d_window", None)
        if win is None:
            return
        try:
            win.set_advanced_tools(on)
        except RuntimeError:                 # the window was deleted
            pass


def tools_hook(main) -> _ToolsHook:
    return _ToolsHook(main)
