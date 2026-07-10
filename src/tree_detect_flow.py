"""
tree_detect_flow.py — orchestration for satellite tree detection (V2.26).

Free functions taking ``main`` (kept off MainWindow/controller, like
``wind_flow``/``building_flow``). Fetches + scans the property's imagery tiles
off the UI thread (``src/tree_detect.py``), then applies the result on the main
thread through the shared OSM-import tail: satellite-alignment correction,
boundary/margin clipping, dedupe against OSM/hand-marked trees, one undo
checkpoint, map refresh, honest status line.

The JPEG tile decoder lives here (not in the Qt-free core) because decoding
needs a codec: ``QImage`` ships with the app and is documented thread-safe off
the GUI thread (unlike ``QPixmap``), so the worker decodes as it fetches.
"""

from __future__ import annotations

from contextlib import nullcontext

from src import tree_detect

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


def detect_trees_for_site(main) -> None:
    """Detect existing tree crowns from the satellite imagery over the drawn
    boundary (or ≈60 m around the pin), off-thread, and import them as
    ``existing_tree`` shade casters. Status lands in the same line the OSM
    import uses; the whole import is one undo step."""
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
        "Scanning the satellite photo for tree crowns… (~10–30 s)")

    from PyQt6.QtCore import QThread
    thread = QThread(main)
    worker = _TreeDetectWorker(bbox)
    worker.moveToThread(thread)
    main._tree_detect_thread = thread
    main._tree_detect_worker = worker

    def _apply(res):
        east, north = main.site_panel.satellite_offset()
        persistence = getattr(main, "_persistence", None)
        cm = (persistence.checkpoint("detect trees") if persistence is not None
              else nullcontext())
        with cm:
            out = tree_detect.import_detected_trees(
                res, main._project, boundary=boundary, margin_m=margin,
                offset_east_m=east, offset_north_m=north,
                area_note=area_note)
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
        done = pyqtSignal(object)     # tree_detect.detect_trees result | None

        def __init__(self, bbox):
            super().__init__()
            self._bbox = bbox

        def run(self):
            try:
                res = tree_detect.detect_trees(self._bbox,
                                               _decode=_qimage_decode)
            except Exception:  # noqa: BLE001 — never crash the worker thread
                res = None
            self.done.emit(res)
