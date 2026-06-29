"""
building_downloader.py — bulk-download a region's building footprints into the
offline BuildingStore (V1.66), mirroring ``terrain_downloader``.

A region bbox (a few km around the property) is split into ~0.03° sub-bboxes;
each is fetched with the existing ``osm_features.fetch_buildings`` and merged
into ``src/building_store.BuildingStore`` as it arrives, paced between requests
to stay polite to the public Overpass instance. After this runs once, every
later design in that area imports its buildings straight from disk (offline).

The download loop (:func:`download_region`) is a pure function with the network
fetch injectable, so it is unit-testable headlessly. ``BuildingDownloadWorker``
is the thin Qt/QThread wrapper (defined only when PyQt6 is importable), with the
same ``progress``/``finished``/``error`` signals + ``cancel()`` as
``EdmontonDownloadWorker`` so the site-panel download UI wires up identically.
"""

from __future__ import annotations

import math
import time
from typing import Callable, Optional

from src.building_store import BuildingStore

_TILE_DEG = 0.03          # ~3 km lat / ~2 km lng at 53°N — a comfy Overpass page
_PACE_S = 1.0             # delay between Overpass calls (politeness)


def tile_region(bbox: dict, step_deg: float = _TILE_DEG) -> list:
    """Split a region ``bbox`` ({south,north,west,east}) into a grid of
    sub-bboxes of side ``step_deg``. The last row/column is clamped to the
    region edge so the whole area is covered without overshoot."""
    south, north = bbox["south"], bbox["north"]
    west, east = bbox["west"], bbox["east"]
    out = []
    # Subtract a tiny epsilon so float noise (0.02/0.01 → 2.0000000000002)
    # doesn't round up to a spurious extra row/column.
    n_lat = max(1, int(math.ceil((north - south) / step_deg - 1e-9)))
    n_lng = max(1, int(math.ceil((east - west) / step_deg - 1e-9)))
    for r in range(n_lat):
        s = south + r * step_deg
        n = min(north, s + step_deg)
        for c in range(n_lng):
            w = west + c * step_deg
            e = min(east, w + step_deg)
            out.append({"south": s, "north": n, "west": w, "east": e})
    return out


def _region_label(bbox: dict) -> str:
    return (f"{bbox['south']:.3f},{bbox['west']:.3f} – "
            f"{bbox['north']:.3f},{bbox['east']:.3f}")


def download_region(region_bbox: dict, store: BuildingStore, *,
                    fetch_fn: Optional[Callable] = None,
                    on_progress: Optional[Callable] = None,
                    should_cancel: Optional[Callable] = None,
                    pace_s: float = _PACE_S,
                    region_name: str = "") -> int:
    """Fetch every sub-tile of ``region_bbox`` and merge into ``store``.

    ``fetch_fn(subbbox) -> list[building item]`` defaults to
    ``osm_features.fetch_buildings``. ``on_progress(total_new, done, total)``
    and ``should_cancel() -> bool`` are optional. Returns the number of new
    buildings stored; marks the pack complete only if it ran to the end (a
    cancel leaves a partial cache that ``has_data()`` still reports False for).
    """
    if fetch_fn is None:
        from src.osm_features import fetch_buildings as fetch_fn  # noqa: PLW0127
    tiles = tile_region(region_bbox)
    total_new = 0
    for i, sub in enumerate(tiles):
        if should_cancel and should_cancel():
            return total_new                      # partial — not marked complete
        try:
            items = fetch_fn(sub) or []
        except Exception:  # noqa: BLE001 — one flaky tile shouldn't kill the run
            items = []
        total_new += store.add_buildings(items)
        if on_progress:
            on_progress(total_new, i + 1, len(tiles))
        if pace_s and i + 1 < len(tiles):
            time.sleep(pace_s)
    store.mark_complete(region_name or _region_label(region_bbox), total_new)
    return total_new


# ── Qt worker thread (optional; mirrors EdmontonDownloadWorker) ──────────────
try:
    from PyQt6.QtCore import QObject, pyqtSignal
    _HAVE_QT = True
except ImportError:  # pragma: no cover
    _HAVE_QT = False

if _HAVE_QT:
    class BuildingDownloadWorker(QObject):
        """Download a region's buildings into BuildingStore off the UI thread.

        Signals mirror EdmontonDownloadWorker:
          progress(total_new, done_tiles, status_text)
          finished(total_new)
          error(message)
        """

        progress = pyqtSignal(int, int, str)
        finished = pyqtSignal(int)
        error = pyqtSignal(str)

        def __init__(self, region_bbox: dict, region_name: str = ""):
            super().__init__()
            self._bbox = region_bbox
            self._region_name = region_name
            self._cancel = False

        def cancel(self) -> None:
            self._cancel = True

        def run(self) -> None:
            store = BuildingStore()
            store.clear()

            def _progress(total_new, done, total):
                self.progress.emit(
                    total_new, done,
                    f"Tile {done}/{total} — {total_new:,} buildings stored…")

            try:
                total = download_region(
                    self._bbox, store,
                    on_progress=_progress,
                    should_cancel=lambda: self._cancel,
                    region_name=self._region_name)
            except Exception as exc:  # noqa: BLE001 — never crash the thread
                self.error.emit(f"Building download failed: {exc}")
                return
            if self._cancel:
                return                        # partial cache; has_data() stays False
            self.finished.emit(total)
