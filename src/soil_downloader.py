"""
soil_downloader.py — one-time download of the offline soil pack (V1.67).

Fetches the **Gridded Soil Landscapes of Canada** GeoTIFFs into
``soil_grid.soil_pack_dir()`` so soil can be sampled offline afterwards
(``src/soil_grid.sample_soil``). Mirrors ``building_downloader`` /
``terrain_downloader``: a pure :func:`download_soil_pack` loop (the network
opener is injectable for tests) wrapped by a Qt ``SoilDownloadWorker`` with
progress / finished / error / cancel.

The default source is the national 90 m archive; it's a large one-time download
(like the Edmonton contour pack). Swapping ``SOIL_PACK_SOURCES`` for the
per-attribute topsoil GeoTIFFs shrinks it — ``sample_soil`` finds the rasters by
attribute keyword either way.
"""

from __future__ import annotations

import io
import os
import zipfile
from typing import Callable, Optional

from src.soil_grid import soil_pack_dir

# Natural Resources Canada / AAFC open data (free, OGL-Canada).
SOIL_PACK_SOURCES = [
    "https://agriculture.canada.ca/atlas/data_donnees/"
    "soilLandscapesOfCanada90mGrid/data_donnees/tif/gridded_slc_90m.zip",
]

_USER_AGENT = "PermaDesign/1.0 (+https://github.com/yarrowyarrowyarrow/permadesign)"


def _default_opener(url: str) -> bytes:
    import urllib.request
    req = urllib.request.Request(url, headers={"User-Agent": _USER_AGENT})
    with urllib.request.urlopen(req, timeout=120) as resp:
        return resp.read()


def _write_tifs_from_zip(blob: bytes, dest_dir: str) -> int:
    n = 0
    with zipfile.ZipFile(io.BytesIO(blob)) as zf:
        for member in zf.namelist():
            if member.lower().endswith((".tif", ".tiff")):
                target = os.path.join(dest_dir, os.path.basename(member))
                with zf.open(member) as src, open(target, "wb") as out:
                    out.write(src.read())
                n += 1
    return n


def download_soil_pack(dest_dir: str, sources: Optional[list] = None, *,
                       opener: Optional[Callable] = None,
                       on_progress: Optional[Callable] = None,
                       should_cancel: Optional[Callable] = None) -> int:
    """Download each URL in ``sources`` into ``dest_dir`` (extracting .tif from
    any .zip). Returns the number of GeoTIFFs written. ``opener(url)->bytes`` is
    injectable for tests; ``on_progress(done, total, text)`` and
    ``should_cancel()`` are optional."""
    sources = sources or SOIL_PACK_SOURCES
    opener = opener or _default_opener
    os.makedirs(dest_dir, exist_ok=True)
    written = 0
    total = len(sources)
    for i, url in enumerate(sources):
        if should_cancel and should_cancel():
            return written
        if on_progress:
            on_progress(i, total, f"Downloading soil data {i + 1}/{total}…")
        try:
            blob = opener(url)
        except Exception:  # noqa: BLE001 — one bad source shouldn't kill the run
            continue
        if url.lower().endswith(".zip"):
            written += _write_tifs_from_zip(blob, dest_dir)
        elif url.lower().endswith((".tif", ".tiff")):
            target = os.path.join(dest_dir, os.path.basename(url))
            with open(target, "wb") as out:
                out.write(blob)
            written += 1
    if on_progress:
        on_progress(total, total, f"Soil pack ready — {written} layer(s).")
    return written


try:
    from PyQt6.QtCore import QObject, pyqtSignal
    _HAVE_QT = True
except ImportError:  # pragma: no cover
    _HAVE_QT = False

if _HAVE_QT:
    class SoilDownloadWorker(QObject):
        """Download the soil pack off the UI thread (mirrors
        EdmontonDownloadWorker / BuildingDownloadWorker)."""

        progress = pyqtSignal(int, int, str)
        finished = pyqtSignal(int)
        error = pyqtSignal(str)

        def __init__(self):
            super().__init__()
            self._cancel = False

        def cancel(self) -> None:
            self._cancel = True

        def run(self) -> None:
            try:
                n = download_soil_pack(
                    soil_pack_dir(),
                    on_progress=lambda d, t, msg: self.progress.emit(d, t, msg),
                    should_cancel=lambda: self._cancel)
            except Exception as exc:  # noqa: BLE001
                self.error.emit(f"Soil download failed: {exc}")
                return
            if self._cancel:
                return
            if n == 0:
                self.error.emit(
                    "No soil layers downloaded (check your connection).")
                return
            self.finished.emit(n)
