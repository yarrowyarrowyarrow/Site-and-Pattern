"""
tree_detect_flow.py — orchestration for tree detection (V2.26).

Free functions taking ``main`` (kept off MainWindow/controller, like
``wind_flow``/``building_flow``). Runs detection off the UI thread, then applies
the result on the main thread: boundary/margin clipping, dedupe against
OSM/hand-marked trees, one undo checkpoint, map refresh, honest status line.

**Two detection paths, height first.** The primary method reads the free Meta/WRI
1 m canopy-height map (``src/tree_detect_chm.py``) and runs the industry-standard
variable-window local-maxima on real heights — robust and location-independent.
When that's unavailable (no ``rasterio``, offline, or no coverage) it falls back
to the RGB-from-basemap heuristic (``src/tree_detect.py``), which needs the
satellite-alignment correction and building anchors the height path doesn't.

The JPEG tile decoder lives here (not in the Qt-free core) because decoding
needs a codec: ``QImage`` ships with the app and is documented thread-safe off
the GUI thread (unlike ``QPixmap``), so the RGB worker decodes as it fetches.
"""

from __future__ import annotations

from contextlib import nullcontext

from src import tree_detect
from src import tree_detect_chm

try:
    from PyQt6.QtCore import QObject, pyqtSignal
    _HAVE_QT = True
except ImportError:  # pragma: no cover
    _HAVE_QT = False


def _qimage_decode(data: bytes):
    """Decode an imagery tile (JPEG/PNG bytes) to ``(w, h, rgb888_bytes)`` via
    QImage, or ``None`` when it doesn't parse. Rows are repacked when QImage
    pads scanlines (bytesPerLine > w*3)."""
    from PyQt6.QtGui import QImage
    img = QImage.fromData(data)
    if img.isNull():
        return None
    img = img.convertToFormat(QImage.Format.Format_RGB888)
    w, h = img.width(), img.height()
    if w <= 0 or h <= 0:
        return None
    bpl = img.bytesPerLine()
    ptr = img.constBits()
    ptr.setsize(bpl * h)
    raw = bytes(ptr)
    if bpl == w * 3:
        return (w, h, raw)
    packed = bytearray(w * h * 3)
    for y in range(h):
        packed[y * w * 3:(y + 1) * w * 3] = raw[y * bpl:y * bpl + w * 3]
    return (w, h, bytes(packed))


def _building_anchors(project: dict) -> list:
    """Already-known buildings (imported/drawn/marked) with heights — the
    photogrammetric scale references for shadow→height calibration. Drawn
    tree canopies (caster_kind == 'tree') are excluded: a tree can't anchor
    the sun for other trees."""
    out = []
    for f in (project.get("features") or []):
        p = f.get("properties") or {}
        geom = f.get("geometry") or {}
        et = p.get("element_type")
        if et == "existing_building" and p.get("height_m"):
            c = geom.get("coordinates") or []
            if len(c) >= 2:
                out.append({"lat": c[1], "lng": c[0],
                            "height_m": p["height_m"],
                            "radius_m": p.get("canopy_radius_m")})
        elif (et == "canopy_footprint" and p.get("caster_kind") != "tree"
                and p.get("height_m")):
            ring = (geom.get("coordinates") or [None])[0]
            lat, lng = p.get("lat"), p.get("lng")
            if (lat is None or lng is None) and ring:
                from src.osm_features import ring_centroid
                cc = ring_centroid(ring)
                if cc:
                    lat, lng = cc
            if lat is not None and lng is not None:
                out.append({"lat": lat, "lng": lng,
                            "height_m": p["height_m"],
                            "radius_m": p.get("canopy_radius_m"),
                            "ring": ring})
    return out


def detect_trees_for_site(main) -> None:
    """Detect existing trees over the drawn boundary (or ≈60 m around the pin)
    off-thread and import them as ``existing_tree`` shade casters. Tries the
    canopy-height map first, falls back to the satellite photo. Status lands in
    the same line the OSM import uses; the whole import is one undo step."""
    from src.osm_features import bbox_with_area_note

    sc = dict(main._project.get("properties", {}).get("site_config", {}) or {})
    boundary = main._map_events._project_boundary_latlng()
    margin = main.site_panel.osm_neighbour_margin()
    bbox, area_note = bbox_with_area_note(boundary, sc,
                                          pad_m=max(30.0, margin))
    if bbox is None:
        main.site_panel.set_osm_status("Drop a pin or draw a boundary first.")
        return
    main.site_panel.set_osm_status(
        "Detecting trees from the canopy-height map… (~10–30 s)")

    from PyQt6.QtCore import QThread
    thread = QThread(main)
    worker = _TreeDetectWorker(bbox, _building_anchors(main._project))
    worker.moveToThread(thread)
    main._tree_detect_thread = thread
    main._tree_detect_worker = worker

    def _apply(payload):
        mode = (payload or {}).get("mode")
        res = (payload or {}).get("res")
        persistence = getattr(main, "_persistence", None)
        cm = (persistence.checkpoint("detect trees") if persistence is not None
              else nullcontext())
        with cm:
            if mode == "chm":
                out = tree_detect_chm.import_chm_result(
                    res, main._project, boundary=boundary, margin_m=margin,
                    area_note=area_note)
            else:
                # RGB fallback: needs the satellite-alignment correction (its
                # positions are read off the displayed basemap, not true coords).
                east, north = main.site_panel.satellite_offset()
                out = tree_detect.import_detected_trees(
                    res, main._project, boundary=boundary, margin_m=margin,
                    offset_east_m=east, offset_north_m=north,
                    area_note=area_note)
                if res is None:
                    out["message"] = (
                        "Couldn't get tree data — the canopy-height map and "
                        "the satellite imagery were both unreachable (offline, "
                        "or this build lacks the 'rasterio' package for height "
                        "data). Nothing was imported; mark trees by hand below.")
                else:
                    out["message"] = ("Couldn't reach the canopy-height map, "
                                      "so read the satellite photo instead "
                                      "(less reliable). " + out["message"])
        if out["added"]:
            main._mark_modified()
            main._map_events._reload_existing_features()
        main.site_panel.set_osm_status(out["message"])

    def _done():
        worker.deleteLater()
        thread.deleteLater()
        main._tree_detect_worker = None
        main._tree_detect_thread = None

    thread.started.connect(worker.run)
    worker.done.connect(_apply)
    worker.done.connect(thread.quit)
    thread.finished.connect(_done)
    thread.start()


if _HAVE_QT:
    class _TreeDetectWorker(QObject):
        # {"mode": "chm"|"rgb", "res": detector result | None}
        done = pyqtSignal(object)

        def __init__(self, bbox, buildings=None):
            super().__init__()
            self._bbox = bbox
            self._buildings = buildings or []

        def run(self):
            # Height first: measured, location-independent, no per-photo tuning.
            try:
                res = tree_detect_chm.detect_trees_chm(self._bbox)
            except Exception:  # noqa: BLE001 — never crash the worker thread
                res = None
            if res is not None:
                # The height map has no colour, so tag conifer/broadleaf from
                # the satellite photo at each tree (best-effort; leaves foliage
                # unknown on any failure). Crosses height ⊗ colour (P7).
                try:
                    tree_detect.classify_foliage_at_points(
                        res.get("trees") or [], self._bbox,
                        _decode=_qimage_decode)
                except Exception:  # noqa: BLE001
                    pass
                self.done.emit({"mode": "chm", "res": res})
                return
            # Fallback: the RGB-from-basemap heuristic (no rasterio / offline /
            # no canopy-height coverage here).
            try:
                res = tree_detect.detect_trees(self._bbox,
                                               buildings=self._buildings,
                                               _decode=_qimage_decode)
            except Exception:  # noqa: BLE001
                res = None
            self.done.emit({"mode": "rgb", "res": res})
