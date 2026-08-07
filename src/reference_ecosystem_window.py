"""
src/reference_ecosystem_window.py — the walkable reference-ecosystem window (F50),
editable since V2.43.

Hosts a :class:`src.map3d_widget.Map3DWidget` showing the curated *reference
community* for an ecoregion — the natural community a design is reaching toward —
and drops the user straight into third-person walk mode: "walk your design, then
walk the reference." An ecoregion selector rebuilds the scene from the curated
communities in ``src.reference_ecosystem``; the initial choice follows the
current project's location.

**V2.43: it is a sandbox now, not a diorama.** Pick a species from the palette
and click the ground to plant it; switch to Pull and click a plant to take it
out and be told what that cost the food web. The edits are saved per community
(``src/reference_edit.py``), so your fen is still your fen next launch, and
they are what Learn mode's lessons read — which is why this window is worth
the wiring: it is the *project* Learn mode carries.

The scene is still built by the Qt-free core (`reference_ecosystem` →
`reference_edit` → `scene_contract.build_scene`); this window owns no geometry
and no placement logic. Every mutation goes through ``reference_edit``, which
goes through ``ProjectStore`` — the single write path.

It reads a *synthetic* reference project, never the user's own, so it still
cannot disturb the design.

``open_reference_ecosystem(main)`` is the entry point the View menu and the
Learn menu use; it keeps a singleton on ``main._reference_window`` (no new
MainWindow method — the architecture guard's method ceiling stays meaningful).

Design principle P2 (show the "grown, not designed" endpoint), P6 (the value
target, made walkable), P3/P5 (pulling a plant makes its edges visible) and P8
(repair is first-class — you are mending a community, not decorating a lawn)
— see docs/DESIGN_PHILOSOPHY.md.
"""

from __future__ import annotations

from typing import Optional

from PyQt6.QtWidgets import (
    QComboBox, QHBoxLayout, QLabel, QPushButton, QVBoxLayout, QWidget,
)

from src.map3d_widget import Map3DWidget
from src import reference_edit_flow as edit_flow
from src import scene3d_edit_flow
from src.scene3d_toolbar import Scene3DToolBar
from src.branding import APP_NAME

#: Which toolbar sections the sandbox shows. Everything the 3D preview has
#: *about the viewer* — time, detail, camera, walk, identify — and nothing it
#: has about a design, because there is no design here to act on.
_TOOLBAR_GROUPS = ("time", "detail", "view")

# (label, ecoregion key) for the curated communities, in a natural west→north
# order. Labels mirror plant_panel._AB_ECOREGION_CHOICES.
_CHOICES = [
    ("Aspen Parkland (central AB)", "aspen_parkland"),
    ("Mixedgrass Prairie (south AB)", "mixedgrass_prairie"),
    ("Fescue / Foothills (SW AB)", "fescue_foothills"),
    ("Boreal Mixedwood (north AB)", "boreal_mixedwood"),
    ("Riparian (streamside)", "riparian"),
    ("Wet Meadow / Marsh", "wet_meadow"),
    ("Subalpine / Montane (mountains)", "subalpine_montane"),
]

_HINT = ("Pick a species and click the ground to plant it. "
         "Switch to Pull to take one out.")

#: The timeline year a sandbox opens at. F50 picked 12 so the curated
#: communities read as grown in; V2.44 gives it a second job, as the date
#: stamped on anything you plant.
_DEFAULT_YEAR = 12


class ReferenceEcosystemWindow(QWidget):
    """A walkable — and plantable — 3D view of an ecoregion's reference
    community."""

    def __init__(self, ecoregion: Optional[str] = None,
                 center: Optional[tuple] = None,
                 toolbar_groups=_TOOLBAR_GROUPS):
        super().__init__(None)   # top-level window
        self.setWindowTitle(f"{APP_NAME}: Reference Ecosystem")
        self.resize(960, 700)
        self._center = center or (51.05, -114.07)
        self._project: dict = {}
        self._community = ""
        self._palette: list = []
        # The timeline year the sandbox is showing. 12 is old enough that every
        # curated community reads as grown in (F50 chose it for that), and it
        # is also what a plant you add is dated to — so a new sapling is young
        # against a mature backdrop rather than instantly matching it.
        self._year = _DEFAULT_YEAR

        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(0)

        bar = QHBoxLayout()
        bar.setContentsMargins(8, 6, 8, 6)
        bar.addWidget(self._label("Reference community:"))
        self._combo = QComboBox()
        for label, key in _CHOICES:
            self._combo.addItem(label, key)
        start = 0
        for i, (_, key) in enumerate(_CHOICES):
            if key == ecoregion:
                start = i
                break
        self._combo.setCurrentIndex(start)
        self._combo.currentIndexChanged.connect(self._on_pick)
        bar.addWidget(self._combo)
        bar.addStretch()
        lay.addLayout(bar)

        self._desc = QLabel("")
        self._desc.setWordWrap(True)
        self._desc.setStyleSheet(
            "color: #b7c9bd; font-size: 11px; padding: 0 10px 6px 10px;")
        lay.addWidget(self._desc)

        self.viewer = Map3DWidget(self)
        lay.addWidget(self.viewer, 1)

        # The same controls the 3D preview has (V2.44). Not a copy of them —
        # the same widget, told which sections to show, so the two windows
        # cannot drift apart again. The design-specific half (refresh, bake a
        # yard photo, presentation still, bee mode) is deliberately absent: a
        # wild community has no design to refresh from.
        self.toolbar = Scene3DToolBar(self, groups=toolbar_groups,
                                      year=self._year, month=6, hour=13)
        self.toolbar.time_changed.connect(self._on_time_changed)
        self.toolbar.detail_changed.connect(self.viewer.set_quality)
        self.toolbar.reset_view.connect(
            lambda: self.viewer.run_js(
                "window.permaResetView && window.permaResetView();"))
        self.toolbar.walk_toggled.connect(self.viewer.set_walk_mode)
        self.toolbar.identify_toggled.connect(self.viewer.set_wildlife_labels)
        lay.addWidget(self.toolbar)

        lay.addLayout(self._build_tools())

        # The consequence line. It is the reason the editing exists, so it gets
        # its own row rather than a status-bar flash that scrolls away while
        # the user is still reading it.
        self._say = QLabel(_HINT)
        self._say.setWordWrap(True)
        self._say.setStyleSheet(
            "color: #cfe8d2; font-size: 12px; padding: 4px 10px 8px 10px;")
        lay.addWidget(self._say)

        # Still opens on your feet inside the community — that is the whole
        # point of F50 — but now the button says so and can be turned off.
        self.toolbar.set_walking(True)

        self._connect_bridge()
        self._push(self._combo.currentData())

    # ── Construction ────────────────────────────────────────────────────────

    def _label(self, text: str) -> QLabel:
        lab = QLabel(text)
        lab.setStyleSheet("color: #90a4ae; font-size: 11px;")
        return lab

    def _build_tools(self) -> QHBoxLayout:
        """The palette bar: what to plant, and the two verbs."""
        bar = QHBoxLayout()
        bar.setContentsMargins(8, 0, 8, 4)
        bar.addWidget(self._label("Plant:"))

        self._species = QComboBox()
        self._species.setMinimumWidth(220)
        self._species.setToolTip(
            "The species of this community. Deliberately not the whole "
            "catalogue — a wild community is a set of plants that belong "
            "together.")
        bar.addWidget(self._species)

        self._plant_btn = QPushButton("🌱 Plant")
        self._plant_btn.setCheckable(True)
        self._plant_btn.setToolTip("Click the ground to place the species above.")
        self._plant_btn.clicked.connect(lambda: self._set_mode("plant"))
        bar.addWidget(self._plant_btn)

        self._pull_btn = QPushButton("✖ Pull")
        self._pull_btn.setCheckable(True)
        self._pull_btn.setToolTip(
            "Click a plant to remove it — and see what loses support.")
        self._pull_btn.clicked.connect(lambda: self._set_mode("pull"))
        bar.addWidget(self._pull_btn)

        # The net (V2.44). Catch, look at, release — the creature is put back
        # when the animation finishes, which is both real field practice and
        # the only version of this that does not teach a child to take
        # pollinators out of a habitat (P11).
        self._net_btn = QPushButton("🥅 Net")
        self._net_btn.setCheckable(True)
        self._net_btn.setToolTip(
            "Walk up to a creature until a ring appears round it, then "
            "click anywhere to swing. Recorded in your field guide, then "
            "released — caught counts for more than seen.")
        self._net_btn.clicked.connect(lambda: self._set_mode("net"))
        bar.addWidget(self._net_btn)

        reset = QPushButton("↺ Reset")
        reset.setToolTip("Throw away your changes and restore the wild "
                         "community as it ships.")
        reset.clicked.connect(lambda: edit_flow.on_reset(self))
        bar.addWidget(reset)
        bar.addStretch()
        return bar

    def _connect_bridge(self) -> None:
        """Wire the viewer's JS→Python channel, when there is one.

        There is none in the ``web3d/dist`` fork build, and none if the page
        failed to load. Editing then simply does nothing, which is the right
        failure: the window still walks the community, which is what it did
        before V2.43.
        """
        bridge = getattr(self.viewer, "bridge", None)
        if bridge is None:
            self._editable = False
            return
        self._editable = True
        # → src/reference_edit_flow.py. Lambdas rather than methods, the same
        # reason app.py uses them: the handlers are a flow module's job and the
        # window stays a layout.
        bridge.plant_requested.connect(
            lambda x, y, pid, nm: edit_flow.on_plant_requested(self, x, y, pid, nm))
        bridge.pull_requested.connect(
            lambda x, y: edit_flow.on_pull_requested(self, x, y))
        bridge.species_inspected.connect(
            lambda kind, key: edit_flow.on_inspected(self, kind, key))
        bridge.species_caught.connect(
            lambda name: edit_flow.on_caught(self, name))
        # V2.46: the net is held now, and a held net has a reach — a miss has
        # to say so or the click looks broken.
        bridge.out_of_reach.connect(
            lambda name: self._say.setText(
                f"{name} is out of reach — walk closer and swing again."
                if name else scene3d_edit_flow.MISS_HINT))

    # ── Community switching ─────────────────────────────────────────────────

    def _on_pick(self, _idx: int):
        self._push(self._combo.currentData())

    def _push(self, ecoregion: str):
        """Load (or build) this community's sandbox and render it."""
        from src.reference_ecosystem import reference_community
        from src.reference_edit import open_sandbox, palette

        self._community = ecoregion or ""
        self._desc.setText(reference_community(ecoregion).get("description", ""))
        try:
            self._project = open_sandbox(ecoregion, center=self._center)
        except Exception:      # noqa: BLE001
            self._desc.setText("Reference community unavailable — plant data "
                               "could not be read.")
            self._project = {}
            return

        try:
            self._palette = palette(ecoregion)
        except Exception:      # noqa: BLE001
            self._palette = []
        self._species.clear()
        for item in self._palette:
            self._species.addItem(
                f"{item['common_name']}  ·  {item['layer']}", item)

        try:
            from src.db import progress
            progress.set_state(progress.LAST_COMMUNITY, self._community)
        except Exception:      # noqa: BLE001
            pass

        self._render()

    def _render(self):
        """Rebuild the Scene JSON from the current project and push it.

        A full rebuild per edit. At ~35 plants that is a brief hitch and it is
        bought deliberately: the alternative is an incremental scene patch,
        which would be a second definition of how a project becomes geometry
        and would drift from ``scene_contract.build_scene`` within a release.
        """
        from datetime import datetime
        from src.scene_contract import build_scene
        # Season and time of day reach the scene through `when`, the same way
        # Scene3DWindow does it — the 21st is the solstice/equinox-ish midpoint
        # of the month, which is what makes the sun angle honest.
        try:
            scene = build_scene(
                self._project, year=self._year,
                when=datetime(2025, self.toolbar.month(), 21,
                              self.toolbar.hour(), 0))
        except Exception:      # noqa: BLE001
            return
        self.viewer.apply_scene(scene)
        try:
            from src.scene_wildlife import wildlife_for_scene, support_by_taxon
            pids = [p["plant_id"] for p in scene.get("plants", [])
                    if p.get("plant_id")]
            self.viewer.set_wildlife(wildlife_for_scene(scene),
                                     support_by_taxon(pids))
        except Exception:      # noqa: BLE001
            self.viewer.set_wildlife([])
        # The magnification lives in the viewer and resets to life size on a
        # fresh page, so a remembered choice has to be re-pushed (V2.46).
        # Follow the toolbar rather than forcing walk mode on. Before V2.44
        # this line was an unconditional ``set_walk_mode(True)``, re-run on
        # every rebuild — so the user was put back on their feet after every
        # single plant, and had no control that could say otherwise.
        self.viewer.set_walk_mode(self.toolbar.is_walking())
        self._reassert_mode()

    def _on_time_changed(self):
        """A time slider moved: re-date the sandbox and rebuild.

        The year is also what a newly planted plant is stamped with, so moving
        this slider forward and planting is how you watch a sapling you put in
        at year 12 catch up with the community around it.
        """
        self._year = self.toolbar.year()
        self._render()

    # ── The trowel ──────────────────────────────────────────────────────────

    #: The three verbs, and what the status line says while each is held.
    _VERBS = (
        ("plant", "_plant_btn", "Click the ground to plant."),
        ("pull", "_pull_btn", "Click a plant to pull it."),
        ("net", "_net_btn",
         "Walk up to a creature until a ring appears, then swing."),
    )

    def _mode(self) -> str:
        for name, attr, _hint in self._VERBS:
            if getattr(self, attr).isChecked():
                return name
        return ""

    def _set_mode(self, which: str):
        """Checkable buttons acting as one exclusive choice, because clicking
        the active one has to turn it *off* — a QButtonGroup would make the
        trowel impossible to put down."""
        for name, attr, _hint in self._VERBS:
            if name != which:
                getattr(self, attr).setChecked(False)
        self._reassert_mode()
        mode = self._mode()
        hint = next((h for n, _a, h in self._VERBS if n == mode), _HINT)
        self._say.setText(hint)

    def _reassert_mode(self):
        """Re-push the mode after a scene rebuild — the viewer keeps it in a
        module global that survives a scene swap, but the walk-mode re-entry
        above is a good place for it to have been lost, and a trowel that
        silently stops working is worse than one that is re-armed twice."""
        if not getattr(self, "_editable", False):
            return
        self.viewer.set_edit_mode(self._mode(), self._current_pick())

    def _current_pick(self) -> Optional[dict]:
        data = self._species.currentData()
        return data if isinstance(data, dict) else None

    # ── Edits ───────────────────────────────────────────────────────────────


def _project_center(project: dict) -> Optional[tuple]:
    """A representative (lat, lng) for a project — the mean of its feature
    coordinates — or ``None`` when it has none."""
    if not isinstance(project, dict):
        return None
    lats: list[float] = []
    lngs: list[float] = []
    for f in project.get("features", []):
        geom = (f or {}).get("geometry") or {}
        if geom.get("type") == "Point":
            c = geom.get("coordinates") or []
            if len(c) >= 2:
                lngs.append(c[0])
                lats.append(c[1])
    if lats:
        return (sum(lats) / len(lats), sum(lngs) / len(lngs))
    return None


def open_reference_ecosystem(main, ecoregion: Optional[str] = None):
    """Show (or raise) the reference-ecosystem window. The initial community
    follows the project's ecoregion when it can be determined from its
    location; otherwise it follows the sandbox the learner was last in, and
    failing that the parkland community."""
    center = None
    if ecoregion is None:
        project = getattr(main, "_project", None)
        center = _project_center(project) if project else None
        if center is not None:
            try:
                from src.ecoregion import lookup_ecoregion
                ecoregion = lookup_ecoregion(center[0], center[1])
            except Exception:      # noqa: BLE001
                ecoregion = None
    if ecoregion is None:
        # Learn mode has no project to take a location from, so the honest
        # default is "where you left off" rather than always the parkland.
        try:
            from src.db import progress
            ecoregion = progress.get_state(progress.LAST_COMMUNITY, "") or None
        except Exception:          # noqa: BLE001
            ecoregion = None
    win = getattr(main, "_reference_window", None)
    if win is None:
        win = ReferenceEcosystemWindow(ecoregion=ecoregion, center=center)
        main._reference_window = win
    win.show()
    win.raise_()
    win.activateWindow()
    return win
