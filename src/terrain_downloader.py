"""
terrain_downloader.py — QThread worker that bulk-downloads the full
City of Edmonton LiDAR contour dataset into the local SQLite store.
"""

import urllib.parse

from PyQt6.QtCore import QObject, pyqtSignal

from src.terrain import (
    _EDM_RESOURCE,
    _edm_detect_fields,
    _coerce_float,
    _flatten_geojson_lines,
    _http_get_json,
)
from src.terrain_store import TerrainStore


class EdmontonDownloadWorker(QObject):
    """
    Downloads all pages of the Edmonton contour dataset and writes them to
    TerrainStore.  Move to a QThread before calling run().

    Signals:
      progress(features_stored, page_num, status_text)
      finished(total_stored)
      error(message)
    """

    progress = pyqtSignal(int, int, str)
    finished = pyqtSignal(int)
    error    = pyqtSignal(str)

    def __init__(self):
        super().__init__()
        self._cancel = False

    def cancel(self) -> None:
        self._cancel = True

    def run(self) -> None:
        store = TerrainStore()
        store.clear_edmonton()

        elev_field, geom_field = _edm_detect_fields()
        if not elev_field or not geom_field:
            self.error.emit(
                "Could not detect field names from the Edmonton dataset.\n"
                "Please ensure you have an internet connection and try again."
            )
            return

        total_stored = 0
        page_num     = 0

        while not self._cancel:
            offset = page_num * 1000
            qs = urllib.parse.urlencode({
                "$select": f"{geom_field},{elev_field}",
                "$limit":  1000,
                "$offset": offset,
                "$order":  ":id",
            })
            url = f"{_EDM_RESOURCE}?{qs}"
            page_data = _http_get_json(url, timeout=30)

            if page_data is None:
                # Possibly $order=:id not supported — retry without it
                qs2 = urllib.parse.urlencode({
                    "$select": f"{geom_field},{elev_field}",
                    "$limit":  1000,
                    "$offset": offset,
                })
                page_data = _http_get_json(f"{_EDM_RESOURCE}?{qs2}", timeout=30)

            if not page_data or "features" not in page_data:
                if page_num == 0:
                    self.error.emit(
                        "No data received from the Edmonton Open Data API.\n"
                        "Check your internet connection and try again."
                    )
                    return
                break  # empty last page or network blip after we have data

            feats = page_data.get("features") or []
            if not feats:
                break  # clean end-of-dataset

            converted = _convert_page(feats, elev_field)
            stored = store.store_edmonton_page(converted)
            total_stored += stored
            page_num += 1

            self.progress.emit(
                total_stored,
                page_num,
                f"Page {page_num} downloaded — {total_stored:,} features stored…",
            )

            if len(feats) < 1000:
                break  # last page

        if self._cancel:
            # Leave the store in a partial state (has_edmonton_data() stays False)
            return

        try:
            self.progress.emit(total_stored, page_num, "Merging tiles, please wait…")
            store.mark_edmonton_complete(total_stored)
        except Exception as exc:
            self.error.emit(f"Failed to finalise download: {exc}")
            return

        self.finished.emit(total_stored)


# ── Internal helpers ─────────────────────────────────────────────────────────

def _convert_page(features: list, elev_field: str) -> list:
    """
    Convert a page of Socrata GeoJSON features to the internal format:
      {"coords": [[lat, lng], ...], "elevation_m": float}

    Socrata encodes coordinates as [lng, lat]; we flip to [lat, lng] to
    match the rest of PermaDesign.
    """
    result = []
    for f in features:
        props = f.get("properties") or {}
        geom  = f.get("geometry") or {}
        elev  = _coerce_float(props.get(elev_field))
        if elev is None:
            continue
        for line in _flatten_geojson_lines(geom):
            coords = [[c[1], c[0]] for c in line if len(c) >= 2]
            if len(coords) >= 2:
                result.append({"coords": coords, "elevation_m": elev})
    return result
