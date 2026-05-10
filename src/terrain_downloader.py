"""
terrain_downloader.py — QThread worker that bulk-downloads the full
City of Edmonton LiDAR contour dataset into the local SQLite store.

If the live Socrata API can't be reached or its schema can't be
sniffed (the historical "Could not detect field names" error), the
worker falls back to importing a locally-bundled seed file at
``data/edmonton_contours.geojson`` (gzipped variants ``.geojson.gz``
and ``.json.gz`` also accepted). That seed is optional — when absent,
the worker reports the network error with an actionable hint.
"""

import gzip
import json
import os
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


_HERE = os.path.dirname(os.path.abspath(__file__))
_PROJECT_ROOT = os.path.dirname(_HERE)
_SEED_CANDIDATES = (
    os.path.join(_PROJECT_ROOT, "data", "edmonton_contours.geojson"),
    os.path.join(_PROJECT_ROOT, "data", "edmonton_contours.geojson.gz"),
    os.path.join(_PROJECT_ROOT, "data", "edmonton_contours.json"),
    os.path.join(_PROJECT_ROOT, "data", "edmonton_contours.json.gz"),
)


def _find_local_seed() -> "str | None":
    for path in _SEED_CANDIDATES:
        if os.path.exists(path):
            return path
    return None


def _load_seed(path: str) -> "dict | None":
    """Load a GeoJSON FeatureCollection from a (gzipped) local file."""
    try:
        if path.endswith(".gz"):
            with gzip.open(path, "rb") as f:
                return json.loads(f.read().decode("utf-8"))
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return None


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
            # Live API unavailable — fall back to a bundled seed file
            # if the project ships one. This is the offline-first path
            # the README points to when the user can't hit Socrata.
            seed_path = _find_local_seed()
            if seed_path is not None:
                self.progress.emit(
                    0, 0,
                    f"Importing bundled seed: {os.path.basename(seed_path)}…"
                )
                if self._import_local_seed(store, seed_path):
                    return
                # Fall through to the error if the seed didn't parse.
            self.error.emit(
                "Could not detect field names from the Edmonton dataset.\n"
                "\n"
                "Tried:\n"
                "  • Socrata views metadata\n"
                "  • Sample-row sniffing on the GeoJSON endpoint\n"
                "  • Local seed at data/edmonton_contours.geojson(.gz)\n"
                "\n"
                "Check your internet connection, or drop a downloaded\n"
                "GeoJSON of the Edmonton contour dataset at\n"
                "data/edmonton_contours.geojson and retry."
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

    def _import_local_seed(self, store: TerrainStore, path: str) -> bool:
        """Import a locally-bundled GeoJSON contour file in chunks.

        Returns True if anything was stored (and emits ``finished``);
        False if the file couldn't be parsed (caller falls back to the
        regular network error). The seed is expected to be a GeoJSON
        FeatureCollection with the same shape as the live Socrata API
        response — properties carrying an elevation, geometry as
        (Multi)LineString in [lng, lat] order.
        """
        data = _load_seed(path)
        if not isinstance(data, dict):
            return False
        feats = data.get("features") or []
        if not isinstance(feats, list) or not feats:
            return False

        # Sniff the elevation field from the first feature with a numeric
        # property — same hint list as the API path.
        from src.terrain import _EDM_ELEV_HINTS  # local import to avoid cycle
        elev_field: "str | None" = None
        for f in feats[:50]:
            props = (f.get("properties") or {})
            for k, v in props.items():
                if any(h in k.lower() for h in _EDM_ELEV_HINTS):
                    if _coerce_float(v) is not None:
                        elev_field = k
                        break
            if elev_field:
                break
        if elev_field is None:
            for f in feats[:50]:
                for k, v in (f.get("properties") or {}).items():
                    if _coerce_float(v) is not None:
                        elev_field = k
                        break
                if elev_field:
                    break
        if elev_field is None:
            return False

        total_stored = 0
        page_num = 0
        page_size = 1000
        for i in range(0, len(feats), page_size):
            if self._cancel:
                return False
            chunk = feats[i:i + page_size]
            converted = _convert_page(chunk, elev_field)
            stored = store.store_edmonton_page(converted)
            total_stored += stored
            page_num += 1
            self.progress.emit(
                total_stored,
                page_num,
                f"Local seed: page {page_num} — {total_stored:,} features stored…",
            )

        if total_stored == 0:
            return False
        try:
            self.progress.emit(
                total_stored, page_num, "Merging tiles, please wait…"
            )
            store.mark_edmonton_complete(total_stored)
        except Exception as exc:
            self.error.emit(f"Failed to finalise local-seed import: {exc}")
            return True   # we did emit error; tell caller not to re-error
        self.finished.emit(total_stored)
        return True


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
