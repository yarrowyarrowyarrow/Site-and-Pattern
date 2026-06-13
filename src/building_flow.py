"""
building_flow.py — orchestration for the offline building pack (V1.66).

Free functions taking ``main``, kept off ``MapEventRouter`` so the controller
stays under its line ceiling (mirrors ``scan_import_dialog.start_scan_import``
and ``splat_flow``). Two entry points:

  * :func:`import_buildings_offline` — the per-design "Import from OpenStreetMap"
    fast path: if this area's pack is downloaded, place its buildings straight
    from disk (no network) through the existing ``osm_features`` pipeline.
  * :func:`start_building_download` — the one-time bulk region download, wiring
    ``BuildingDownloadWorker`` on a QThread exactly like the Edmonton terrain
    download (progress / finished / error / cancel).
"""

from __future__ import annotations

import math


def _pad_bbox(bbox: dict, metres: float) -> dict:
    """Grow a bbox by ``metres`` on every side so a region download pulls in
    the neighbouring blocks (their buildings shade the property too)."""
    clat = (bbox["south"] + bbox["north"]) / 2.0
    dlat = metres / 111320.0
    dlng = metres / (111320.0 * max(1e-9, math.cos(clat * math.pi / 180)))
    return {"south": bbox["south"] - dlat, "north": bbox["north"] + dlat,
            "west": bbox["west"] - dlng, "east": bbox["east"] + dlng}


def import_buildings_offline(main, bbox: dict) -> bool:
    """Place buildings for ``bbox`` from the offline pack if it covers the area.

    Returns ``True`` when it handled the import (so the caller skips the live
    Overpass fetch); ``False`` when there's no pack or no buildings nearby.
    """
    from src.building_store import BuildingStore
    store = BuildingStore()
    if not store.has_data():
        return False
    items = store.buildings_in_bbox(bbox)
    if not items:
        return False
    from src.osm_features import add_features_to_project
    added = add_features_to_project(items, main._project)
    if added:
        main._mark_modified()
        main._map_events._reload_existing_features()
    main.site_panel.set_osm_status(
        f"Imported {added} building(s) from the offline pack "
        f"({len(items)} nearby). Trees need an online import.")
    return True


def start_building_download(main) -> None:
    """Kick off the one-time bulk building-footprint download for the property's
    region into the offline ``BuildingStore`` (mirrors the Edmonton terrain
    download flow). State lives on ``main``: ``_bldg_dl_thread`` / ``_bldg_dl_worker``."""
    from PyQt6.QtCore import QThread
    from src.building_downloader import BuildingDownloadWorker
    from src.osm_features import bbox_from_boundary_or_pin

    sc = dict(main._project.get("properties", {}).get("site_config", {}) or {})
    boundary = main._map_events._project_boundary_latlng()
    base = bbox_from_boundary_or_pin(boundary, sc, radius_m=2500.0)
    if base is None:
        main.site_panel.set_osm_status("Drop a pin or draw a boundary first.")
        main.site_panel.reset_buildings_download()
        return
    region = _pad_bbox(base, 2000.0)

    thread = QThread(main)
    worker = BuildingDownloadWorker(region, (sc.get("pin_label") or "").strip())
    worker.moveToThread(thread)
    main._bldg_dl_thread = thread
    main._bldg_dl_worker = worker

    def _progress(total_new, done, text):
        main.site_panel.set_buildings_download_progress(total_new, done, text)

    def _finished(total):
        main.site_panel.reset_buildings_download()
        main.site_panel.set_osm_status(
            f"Building pack ready — {total:,} footprint(s) cached offline. "
            "Use 'Import from OpenStreetMap' to place them.")
        main.statusBar().showMessage(
            f"Building download complete — {total:,} footprints cached offline.",
            8000)

    def _error(message):
        main.site_panel.reset_buildings_download()
        main.site_panel.set_osm_status(message)

    def _thread_done():
        try:
            main.site_panel._bldg_cancel_btn.clicked.disconnect(worker.cancel)
        except Exception:  # noqa: BLE001 — already disconnected
            pass
        # A cancel never fires finished(), so reset the button state here too.
        main.site_panel.reset_buildings_download()
        worker.deleteLater()
        thread.deleteLater()
        main._bldg_dl_worker = None
        main._bldg_dl_thread = None

    thread.started.connect(worker.run)
    worker.progress.connect(_progress)
    worker.finished.connect(_finished)
    worker.error.connect(_error)
    worker.finished.connect(thread.quit)
    worker.error.connect(thread.quit)
    thread.finished.connect(_thread_done)
    main.site_panel._bldg_cancel_btn.clicked.connect(worker.cancel)
    thread.start()
