"""
features_scan_flow.py — Site › Features › Scan this area (F207, V3.10).

Design principle P8 — see docs/DESIGN_PHILOSOPHY.md.

The owner: "a scan of both the map layer and the satellite layer to work in
synchronicity to provide an accurate placement of existing buildings and trees
… that can then be useful in the 3D view as well as the birds eye designers
view."

Everything a scan needs already existed, behind two buttons with two status
lines and two undo steps: buildings from OpenStreetMap (or the offline building
pack), and trees from the free 1 m canopy-height map, with the satellite photo
read instead when the height map cannot be reached, corrected by the satellite
alignment (``tree_detect_flow``, V2.26). *Scan this area* runs both at once,
adds what they find as **one undo step**, and opens a **review**: each building
and tree found, ticked, so what is not really there (a felled tree, a
demolished garage, a shrub read as a tree) comes out in one go. A row frames
its find on the map.

Not yet: buildings read off the satellite pixels, open building footprints, or
the satellite lined up by itself (the V3.09 plan's T6–T8).
"""

from __future__ import annotations

from contextlib import nullcontext

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import (
    QDialog, QDialogButtonBox, QLabel, QListWidget, QListWidgetItem,
    QVBoxLayout,
)

#: What a scan adds, and so what the review lists.
FOUND_TYPES = ("existing_tree", "existing_building", "canopy_footprint")


def describe(feature: dict) -> str:
    """A review row: "Tree (canopy height) · crown 6 m · 11 m tall"."""
    props = feature.get("properties") or {}
    kind = props.get("element_type")
    label = props.get("label") or ("Tree" if kind == "existing_tree"
                                   else "Building")
    height = float(props.get("height_m") or 0)
    bits = [label]
    if kind == "existing_tree":
        bits.append(f"crown {2 * float(props.get('canopy_radius_m') or 0):.0f} m")
    if height:
        bits.append(f"{height:.0f} m tall")
    return " · ".join(bits)


def centre(feature: dict):
    """``(lat, lng)`` of a find, or ``None``."""
    geom = feature.get("geometry") or {}
    coords = geom.get("coordinates") or []
    if geom.get("type") == "Point" and len(coords) >= 2:
        return float(coords[1]), float(coords[0])
    if geom.get("type") == "Polygon" and coords and coords[0]:
        from src.osm_features import ring_centroid
        c = ring_centroid(coords[0])
        if c is not None:
            return c
    return None


def summary(found: list, osm: dict, trees: dict) -> str:
    """The status line: what the scan found, or, when it added nothing, what
    each source said (offline, nothing nearby, all already marked)."""
    if not found:
        said = [m for m in ((osm or {}).get("message"),
                            (trees or {}).get("message")) if m]
        return "The scan added nothing new. " + " ".join(said)
    n_trees = sum(1 for f in found
                  if (f.get("properties") or {}).get("element_type")
                  == "existing_tree")
    n_bldg = len(found) - n_trees
    return (f"The scan found {n_bldg} building{'s' if n_bldg != 1 else ''} "
            f"and {n_trees} tree{'s' if n_trees != 1 else ''}: untick in the "
            f"list any that are not there.")


def found_since(project: dict, before: set) -> list:
    """The buildings and trees in ``project`` that were not in it before (by
    identity: a scan only appends)."""
    return [f for f in project.get("features", [])
            if id(f) not in before
            and (f.get("properties") or {}).get("element_type") in FOUND_TYPES]


def scan_area(main) -> None:
    """Buildings and trees for the boundary (or 60 m round the pin), both at
    once, off the UI thread; added together; then reviewed."""
    from PyQt6.QtCore import QThread
    from src.osm_features import OSMWorker, bbox_with_area_note
    from src import tree_detect_flow

    sc = dict(main._project.get("properties", {}).get("site_config", {}) or {})
    boundary = main._map_events._project_boundary_latlng()
    margin = main.site_panel.osm_neighbour_margin()
    bbox, area_note = bbox_with_area_note(boundary, sc, pad_m=max(30.0, margin))
    if bbox is None:
        main.site_panel.set_osm_status("Drop a pin or draw a boundary first.")
        return
    main.site_panel.set_osm_status(
        "Scanning: buildings from OpenStreetMap, trees from the canopy-height "
        "map… (~10–30 s)")
    try:
        min_h = float(main.site_panel.tree_min_height())
    except Exception:                                      # noqa: BLE001
        min_h = None
    results: dict = {}
    jobs = {
        "buildings": OSMWorker(bbox),
        "trees": tree_detect_flow._TreeDetectWorker(
            bbox, tree_detect_flow._building_anchors(main._project), min_h),
    }
    threads = []
    main._scan_jobs = (jobs, threads)            # kept alive while they run

    def _arrived(name, payload):
        results[name] = payload
        if len(results) == len(jobs):
            main._scan_jobs = None
            _apply(main, results, boundary=boundary, margin=margin,
                   area_note=area_note, bbox=bbox)

    for name, worker in jobs.items():
        thread = QThread(main)
        worker.moveToThread(thread)
        thread.started.connect(worker.run)
        signal = worker.ready if name == "buildings" else worker.done
        signal.connect(lambda payload, n=name: _arrived(n, payload))
        signal.connect(thread.quit)
        thread.finished.connect(thread.deleteLater)
        threads.append(thread)
        thread.start()


def _apply(main, results: dict, *, boundary, margin, area_note, bbox) -> None:
    """Both answered: add buildings and trees as one undo step, then review."""
    from src import building_flow, tree_detect_flow
    from src.osm_features import import_osm_result
    before = {id(f) for f in main._project.get("features", [])}
    persistence = getattr(main, "_persistence", None)
    cm = (persistence.checkpoint("scan this area") if persistence is not None
          else nullcontext())
    with cm:
        # The offline pack first, when it covers the area, as the building
        # import does; else what OpenStreetMap sent.
        if building_flow.import_buildings_offline(main, bbox, boundary=boundary,
                                                  margin_m=margin):
            osm = {"message": "Buildings from the offline pack."}
        else:
            osm = import_osm_result(results.get("buildings"), main._project,
                                    boundary=boundary, margin_m=margin,
                                    area_note=area_note)
        trees = tree_detect_flow.import_tree_result(
            main, results.get("trees"), boundary=boundary, margin=margin,
            area_note=area_note)
    found = found_since(main._project, before)
    if found:
        main._mark_modified()
        main._map_events._reload_existing_features()
    main.site_panel.set_osm_status(summary(found, osm, trees))
    if found:
        from PyQt6.QtWidgets import QWidget
        review = ScanReview(found, main if isinstance(main, QWidget)
                            else None)
        review.frame_requested.connect(
            lambda lat, lng: main.map_widget.fit_bounds(
                lat - 0.0004, lng - 0.0006, lat + 0.0004, lng + 0.0006))
        review.accepted.connect(lambda: remove(main, review.unticked()))
        main._scan_review = review
        review.show()


def remove(main, features: list) -> int:
    """Take the unticked finds out of the design, as one undo step."""
    if not features:
        return 0
    drop = {id(f) for f in features}
    persistence = getattr(main, "_persistence", None)
    cm = (persistence.checkpoint("remove scanned features")
          if persistence is not None else nullcontext())
    with cm:
        main._project["features"] = [f for f in main._project["features"]
                                     if id(f) not in drop]
    main._mark_modified()
    if persistence is not None:
        persistence.render_project_to_map()
    main._sync_planning_panel()
    main.site_panel.set_osm_status(
        f"Took out the {len(drop)} you unticked.")
    return len(drop)



class ScanReview(QDialog):
    """Every find, ticked; *Keep the ticked* removes the rest. Not modal, so
    the map can be panned and the satellite switched on while reviewing."""

    frame_requested = pyqtSignal(float, float)

    def __init__(self, found: list, parent=None):
        super().__init__(parent)
        self.setWindowTitle("What the scan found")
        self.setModal(False)
        self._found = list(found)
        lay = QVBoxLayout(self)
        intro = QLabel(
            "Untick what is not really there (a felled tree, a shrub read as a "
            "tree, a building since taken down). Click a row to see it on the "
            "map; switch on 🛰 Satellite to check it against the photo.")
        intro.setWordWrap(True)
        lay.addWidget(intro)
        self.list = QListWidget()
        self.list.setAccessibleName("Buildings and trees the scan found")
        for i, f in enumerate(self._found):
            item = QListWidgetItem(describe(f))
            item.setFlags(item.flags() | Qt.ItemFlag.ItemIsUserCheckable)
            item.setCheckState(Qt.CheckState.Checked)
            item.setData(Qt.ItemDataRole.UserRole, i)
            self.list.addItem(item)
        self.list.currentItemChanged.connect(self._frame)
        lay.addWidget(self.list, 1)
        buttons = QDialogButtonBox()
        keep = buttons.addButton("Keep the ticked",
                                 QDialogButtonBox.ButtonRole.AcceptRole)
        keep.setDefault(True)
        buttons.addButton("Keep all", QDialogButtonBox.ButtonRole.RejectRole)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        lay.addWidget(buttons)
        self.resize(420, 420)

    def unticked(self) -> list:
        return [self._found[self.list.item(i).data(Qt.ItemDataRole.UserRole)]
                for i in range(self.list.count())
                if self.list.item(i).checkState() != Qt.CheckState.Checked]

    def _frame(self, item, _previous=None):
        if item is None:
            return
        where = centre(self._found[item.data(Qt.ItemDataRole.UserRole)])
        if where is not None:
            self.frame_requested.emit(*where)
