"""
src/reference_ecosystem_window.py — the walkable reference-ecosystem window (F50).

Hosts a :class:`src.map3d_widget.Map3DWidget` showing the curated *reference
community* for an ecoregion — the natural community a design is reaching toward —
and drops the user straight into third-person walk mode: "walk your design, then
walk the reference." An ecoregion selector rebuilds the scene from the curated
communities in ``src.reference_ecosystem``; the initial choice follows the
current project's location.

The scene is built by the Qt-free core (`reference_ecosystem.build_reference_scene`
→ `scene_contract.build_scene`); this window owns no geometry. It reads a
*synthetic* reference project, never the user's own, so it can't disturb the
design.

``open_reference_ecosystem(main)`` is the entry point the View menu uses; it
keeps a singleton on ``main._reference_window`` (no new MainWindow method — the
architecture guard's method ceiling stays meaningful).

Design principle P2 (show the "grown, not designed" endpoint) and P6 (the value
target, made walkable) — see docs/DESIGN_PHILOSOPHY.md.
"""

from __future__ import annotations

from typing import Optional

from PyQt6.QtWidgets import (
    QComboBox, QHBoxLayout, QLabel, QVBoxLayout, QWidget,
)

from src.map3d_widget import Map3DWidget
from src.branding import APP_NAME

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


class ReferenceEcosystemWindow(QWidget):
    """A walkable 3D view of an ecoregion's reference community."""

    def __init__(self, ecoregion: Optional[str] = None,
                 center: Optional[tuple] = None):
        super().__init__(None)   # top-level window
        self.setWindowTitle(f"{APP_NAME}: Reference Ecosystem")
        self.resize(960, 700)
        self._center = center or (51.05, -114.07)

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

        self._push(self._combo.currentData())

    def _label(self, text: str) -> QLabel:
        lab = QLabel(text)
        lab.setStyleSheet("color: #90a4ae; font-size: 11px;")
        return lab

    def _on_pick(self, _idx: int):
        self._push(self._combo.currentData())

    def _push(self, ecoregion: str):
        from src.reference_ecosystem import (build_reference_scene,
                                             reference_community)
        lat, lng = self._center
        self._desc.setText(reference_community(ecoregion).get("description", ""))
        try:
            scene = build_reference_scene(ecoregion, center_lat=lat, center_lng=lng)
        except Exception:      # noqa: BLE001
            self._desc.setText("Reference community unavailable — plant data "
                               "could not be read.")
            return
        self.viewer.apply_scene(scene)
        # Populate ambient wildlife the community's plants support (same path as
        # the 3D preview), then drop straight into walk mode.
        try:
            from src.scene_wildlife import wildlife_for_scene, support_by_taxon
            pids = [p["plant_id"] for p in scene.get("plants", [])
                    if p.get("plant_id")]
            self.viewer.set_wildlife(wildlife_for_scene(scene),
                                     support_by_taxon(pids))
        except Exception:      # noqa: BLE001
            self.viewer.set_wildlife([])
        self.viewer.set_walk_mode(True)


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
    location; otherwise it defaults to the parkland community."""
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
    win = getattr(main, "_reference_window", None)
    if win is None:
        win = ReferenceEcosystemWindow(ecoregion=ecoregion, center=center)
        main._reference_window = win
    win.show()
    win.raise_()
    win.activateWindow()
    return win
