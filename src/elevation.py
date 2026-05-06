"""
elevation.py — Elevation data fetching and offline caching.

Two data sources, chosen automatically by location:

  1. City of Edmonton Open Data  (primary, Edmonton area only)
     LiDAR-derived 2m contour lines, ~0.3 m vertical accuracy.
     Returns ready-to-draw GeoJSON LineString features.
     Socrata API — no authentication required.

  2. OpenTopoData SRTM 30m  (global fallback)
     Returns an elevation grid; contour generation is done
     client-side in JavaScript via d3-contour.

All network calls run in ElevationFetchWorker (QThread) so the UI never
blocks.  Data is cached as compact JSON files so subsequent opens of
the same design area are instant and fully offline.

Edmonton dataset:
  Locate the dataset ID at https://data.edmonton.ca — search for
  "contour" or "2m topographic".  Copy the 4×4 Socrata ID (e.g.
  "abcd-1234") and set EDMONTON_CONTOUR_DATASET_ID below.  If the ID
  is wrong the fetch raises a RuntimeError and the code falls back to
  SRTM automatically.
"""

from __future__ import annotations

import hashlib
import json
import os
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime
from pathlib import Path
from typing import Optional

from PyQt6.QtCore import QObject, pyqtSignal

# ── Edmonton dataset constants ─────────────────────────────────────────────────
#
# Dataset: City of Edmonton — 2m Topographic Contour Lines (LiDAR-derived)
# Portal:  https://data.edmonton.ca  (search "contour elevation")
# Update EDMONTON_CONTOUR_DATASET_ID with the Socrata 4×4 ID once verified.
#
EDMONTON_CONTOUR_DATASET_ID = "s2r5-bzr9"   # placeholder — verify on portal
EDMONTON_ELEV_FIELD         = "ELEVATION"    # property field; auto-probed if wrong
EDMONTON_BBOX               = (53.30, 53.75, -113.85, -113.15)  # lat_min/max, lng_min/max

# ── Cache helpers ──────────────────────────────────────────────────────────────

def _get_cache_dir() -> Path:
    if sys.platform == "win32":
        base = Path(os.environ.get("LOCALAPPDATA", "")) or (Path.home() / "AppData" / "Local")
    else:
        xdg = os.environ.get("XDG_DATA_HOME", "")
        base = Path(xdg) if xdg else (Path.home() / ".local" / "share")
    cache_dir = base / "PermaDesign" / "elevation"
    cache_dir.mkdir(parents=True, exist_ok=True)
    return cache_dir


def _cache_key(bbox: tuple, source: str) -> str:
    # Round to 4 decimal places (~11 m) to avoid misses from float jitter
    rounded = tuple(round(v, 4) for v in bbox)
    return hashlib.md5(f"{source}:{rounded}".encode()).hexdigest()


def _cache_path(bbox: tuple, source: str) -> Path:
    return _get_cache_dir() / f"elev_{_cache_key(bbox, source)}.json"


def get_cached(bbox: tuple, source: str) -> Optional[dict]:
    path = _cache_path(bbox, source)
    if not path.exists():
        return None
    try:
        with path.open("r", encoding="utf-8") as f:
            data = json.load(f)
        data["_from_cache"] = True
        return data
    except (json.JSONDecodeError, OSError):
        path.unlink(missing_ok=True)
        return None


def save_cache(bbox: tuple, source: str, data: dict) -> None:
    try:
        path = _cache_path(bbox, source)
        with path.open("w", encoding="utf-8") as f:
            json.dump(data, f, separators=(",", ":"))
    except OSError:
        pass   # non-fatal; next run will just re-fetch


def delete_cache(bbox: tuple, source: str) -> None:
    _cache_path(bbox, source).unlink(missing_ok=True)


# ── HTTP helper ────────────────────────────────────────────────────────────────

def _http_get(url: str, timeout: int = 20) -> bytes:
    req = urllib.request.Request(url, headers={
        "User-Agent": "PermaDesign/1.0",
        "Accept":     "application/json",
    })
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return resp.read()
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"HTTP {exc.code}: {body[:200]}") from exc
    except urllib.error.URLError as exc:
        raise RuntimeError(f"Network error: {exc.reason}") from exc


# ── Location helpers ──────────────────────────────────────────────────────────

def _is_edmonton(lat_min: float, lat_max: float,
                 lng_min: float, lng_max: float) -> bool:
    centroid_lat = (lat_min + lat_max) / 2
    centroid_lng = (lng_min + lng_max) / 2
    return (EDMONTON_BBOX[0] <= centroid_lat <= EDMONTON_BBOX[1]
            and EDMONTON_BBOX[2] <= centroid_lng <= EDMONTON_BBOX[3])


# ── Edmonton Open Data ────────────────────────────────────────────────────────

def fetch_edmonton_contours(bbox: tuple) -> dict:
    """
    Fetch LiDAR-derived 2m contour lines from City of Edmonton Open Data.

    bbox = (lat_min, lat_max, lng_min, lng_max)
    Returns a cache-format dict with a "features" list of GeoJSON features.
    Raises RuntimeError on any network or data error.
    """
    lat_min, lat_max, lng_min, lng_max = bbox

    base = (f"https://data.edmonton.ca/resource/"
            f"{EDMONTON_CONTOUR_DATASET_ID}.geojson")
    params = urllib.parse.urlencode({
        "$where": f"within_box(the_geom,{lat_min},{lng_min},{lat_max},{lng_max})",
        "$limit": "5000",
    })
    url = f"{base}?{params}"

    raw = _http_get(url)
    geojson = json.loads(raw.decode("utf-8"))
    features = geojson.get("features", [])

    if not features:
        raise RuntimeError(
            f"Edmonton dataset returned 0 features for this area. "
            f"Dataset ID may be incorrect ({EDMONTON_CONTOUR_DATASET_ID}). "
            f"Verify at https://data.edmonton.ca"
        )

    # Auto-probe the elevation field name
    elev_field = EDMONTON_ELEV_FIELD
    if features:
        props = features[0].get("properties", {})
        for candidate in (EDMONTON_ELEV_FIELD, "elevation", "CONTOUR_ELV",
                          "ContourElev", "ELEV_M", "contour", "CONTOUR",
                          "elev", "height"):
            if candidate in props:
                elev_field = candidate
                break

    normalized: list[dict] = []
    for feat in features:
        geom = feat.get("geometry", {})
        if geom.get("type") != "LineString":
            continue
        elev_val = feat.get("properties", {}).get(elev_field)
        if elev_val is None:
            continue
        try:
            elev_float = float(elev_val)
        except (TypeError, ValueError):
            continue
        normalized.append({
            "type": "Feature",
            "geometry": geom,
            "properties": {"ELEVATION": elev_float},
        })

    if not normalized:
        raise RuntimeError(
            f"Edmonton dataset has features but none with usable elevation "
            f"data (tried field '{elev_field}')."
        )

    return {
        "source":     "edmonton_opendata",
        "fetched_at": datetime.utcnow().isoformat(timespec="seconds"),
        "bbox":       list(bbox),
        "elev_field": elev_field,
        "features":   normalized,
    }


# ── OpenTopoData SRTM 30m ─────────────────────────────────────────────────────

_SRTM_URL   = "https://api.opentopodata.org/v1/srtm30m?locations={locs}"
_SRTM_BATCH = 100    # API maximum per request


def _build_grid_points(bbox: tuple, cols: int, rows: int) -> list:
    lat_min, lat_max, lng_min, lng_max = bbox
    pts = []
    for r in range(rows):
        lat = lat_max - r * (lat_max - lat_min) / max(rows - 1, 1)
        for c in range(cols):
            lng = lng_min + c * (lng_max - lng_min) / max(cols - 1, 1)
            pts.append((r, c, lat, lng))
    return pts


def fetch_srtm_grid(bbox: tuple, cols: int = 20, rows: int = 20) -> dict:
    """
    Fetch an elevation grid from OpenTopoData SRTM 30m.

    bbox = (lat_min, lat_max, lng_min, lng_max)
    Returns a cache-format dict with a "grid" (rows×cols, row-major N→S).
    Raises RuntimeError on network failure.
    """
    lat_min, lat_max, lng_min, lng_max = bbox
    pts = _build_grid_points(bbox, cols, rows)

    grid: list[list[Optional[float]]] = [[None] * cols for _ in range(rows)]

    for i in range(0, len(pts), _SRTM_BATCH):
        batch = pts[i : i + _SRTM_BATCH]
        locs  = "|".join(f"{lat:.6f},{lng:.6f}" for _, _, lat, lng in batch)
        url   = _SRTM_URL.format(locs=urllib.parse.quote(locs, safe="|,.-"))

        raw  = _http_get(url)
        resp = json.loads(raw.decode("utf-8"))

        for idx, result in enumerate(resp.get("results", [])):
            r, c, _, _ = batch[idx]
            grid[r][c] = result.get("elevation")

        if i + _SRTM_BATCH < len(pts):
            time.sleep(1.1)   # respect 1 req/sec rate limit

    return {
        "source":     "srtm30m",
        "fetched_at": datetime.utcnow().isoformat(timespec="seconds"),
        "bbox":       list(bbox),
        "cols":       cols,
        "rows":       rows,
        "lat_min":    lat_min,
        "lat_max":    lat_max,
        "lng_min":    lng_min,
        "lng_max":    lng_max,
        "grid":       grid,
    }


# ── Top-level orchestrator ────────────────────────────────────────────────────

def get_elevation_data(bbox: tuple, cols: int = 20, rows: int = 20) -> dict:
    """
    Cache-first elevation fetch.

    Picks Edmonton Open Data for Edmonton-area bounding boxes, SRTM 30m
    elsewhere.  On Edmonton fetch failure falls back to SRTM automatically.
    bbox = (lat_min, lat_max, lng_min, lng_max)
    """
    lat_min, lat_max, lng_min, lng_max = bbox
    use_edmonton = _is_edmonton(lat_min, lat_max, lng_min, lng_max)
    source_name  = "edmonton_opendata" if use_edmonton else "srtm30m"

    cached = get_cached(bbox, source_name)
    if cached:
        return cached

    if use_edmonton:
        try:
            data = fetch_edmonton_contours(bbox)
        except Exception as edmonton_err:
            # Graceful fallback — Edmonton API unavailable or dataset ID wrong
            try:
                data = fetch_srtm_grid(bbox, cols, rows)
                data["_fallback_reason"] = str(edmonton_err)
            except Exception as srtm_err:
                raise RuntimeError(
                    f"Edmonton fetch failed ({edmonton_err}); "
                    f"SRTM fallback also failed ({srtm_err})"
                ) from srtm_err
    else:
        data = fetch_srtm_grid(bbox, cols, rows)

    save_cache(bbox, data["source"], data)
    return data


# ── QThread worker ────────────────────────────────────────────────────────────

class ElevationFetchWorker(QObject):
    """
    Runs get_elevation_data() in a background thread.

    Usage:
        worker = ElevationFetchWorker(bbox, cols, rows)
        thread = QThread()
        worker.moveToThread(thread)
        worker.finished.connect(self._on_elevation_ready)
        worker.error.connect(self._on_elevation_error)
        thread.started.connect(worker.run)
        worker.finished.connect(thread.quit)
        worker.error.connect(thread.quit)
        thread.start()
        # Keep references: self._elev_thread = thread; self._elev_worker = worker
    """

    finished = pyqtSignal(dict)   # emits the full cache-format dict
    error    = pyqtSignal(str)    # emits a human-readable error message

    def __init__(self, bbox: tuple, cols: int = 20, rows: int = 20,
                 parent=None):
        super().__init__(parent)
        self._bbox = bbox
        self._cols = cols
        self._rows = rows

    def run(self) -> None:
        try:
            data = get_elevation_data(self._bbox, self._cols, self._rows)
            self.finished.emit(data)
        except Exception as exc:
            self.error.emit(str(exc))
