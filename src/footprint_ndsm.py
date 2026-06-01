"""
footprint_ndsm.py — nDSM height-raster → footprint polygons + heights.

A concrete :class:`~src.footprint_extract.FootprintExtractor` backend that turns
a **normalized DSM** (nDSM = DSM − DEM, i.e. height-above-ground in metres) into
shade-casting footprints: it thresholds the raster to find raised objects
(buildings, tree canopies), traces each connected blob's outline, simplifies it,
projects the pixel ring to WGS-84 lng/lat, and reports a representative height.

This is the whiteboxtools-style path from ``footprint_extract``'s docstring —
whiteboxtools (or any DSM−DEM pipeline) produces the nDSM; this module does the
vectorize-with-heights step. It is the *ideal* extraction source because shadow
length needs a height, which an nDSM carries directly.

Dependency policy (cf. ``shadow_geometry`` / ``projection``):
  * The **algorithmic core** — :func:`vectorize_ndsm` — needs only ``numpy`` +
    ``shapely`` (already optional deps) and is fully unit-testable offline.
  * The **GeoTIFF reader** — :func:`read_ndsm_geotiff` — uses ``rasterio`` when
    installed and raises a clear error otherwise. No torch / GDAL ships here.

The SAM (RGB-segmentation) path stays future work: it produces footprints
*without* heights, which the user then fills in by hand — a strictly weaker
input than an nDSM, so we ship the height-bearing backend first.
"""

from __future__ import annotations

import math
from typing import Optional

try:
    import numpy as np
    _HAVE_NUMPY = True
except ImportError:  # pragma: no cover
    _HAVE_NUMPY = False

try:
    from shapely.geometry import Polygon
    from shapely.ops import unary_union
    _HAVE_SHAPELY = True
except ImportError:  # pragma: no cover
    _HAVE_SHAPELY = False


# An affine geo-transform in the GDAL/rasterio convention:
#   x = c + a*col + b*row ;  y = f + d*col + e*row
# For a north-up raster b == d == 0, a == +px_w, e == -px_h. We keep the full
# 6-tuple so rotated transforms still project correctly.
GeoTransform = tuple  # (c, a, b, f, d, e)


def _pixel_to_xy(col: float, row: float, gt: "GeoTransform") -> tuple:
    c, a, b, f, d, e = gt
    return (c + a * col + b * row, f + d * col + e * row)


def _trace_blob_rings(mask, min_pixels: int):
    """Yield, for each 4-connected True blob in ``mask`` (a 2D bool ndarray) of
    at least ``min_pixels`` cells, a closed pixel-space ring (list of
    ``(col, row)`` corner points) tracing the blob's outer boundary.

    Pure numpy flood-fill + boundary march — no scikit-image. The ring is the
    union of unit cell squares for the blob, so it is exact (axis-aligned,
    staircased); the caller simplifies it."""
    rows, cols = mask.shape
    seen = np.zeros_like(mask, dtype=bool)
    for r0 in range(rows):
        for c0 in range(cols):
            if not mask[r0, c0] or seen[r0, c0]:
                continue
            # Flood-fill this blob (4-connected) collecting its cells.
            stack = [(r0, c0)]
            seen[r0, c0] = True
            cells = []
            while stack:
                r, c = stack.pop()
                cells.append((r, c))
                for dr, dc in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                    nr, nc = r + dr, c + dc
                    if (0 <= nr < rows and 0 <= nc < cols
                            and mask[nr, nc] and not seen[nr, nc]):
                        seen[nr, nc] = True
                        stack.append((nr, nc))
            if len(cells) < min_pixels:
                continue
            yield cells


def _cells_to_polygon(cells):
    """Union the unit squares of a blob's ``(row, col)`` cells into one shapely
    polygon in pixel space (x=col, y=row). Returns the largest polygon if the
    union somehow splits."""
    squares = [Polygon([(c, r), (c + 1, r), (c + 1, r + 1), (c, r + 1)])
               for (r, c) in cells]
    geom = unary_union(squares)
    if geom.is_empty:
        return None
    if geom.geom_type == "MultiPolygon":
        geom = max(geom.geoms, key=lambda g: g.area)
    return geom


def vectorize_ndsm(ndsm, gt: "GeoTransform", *,
                   min_height_m: float = 2.0,
                   min_area_m2: float = 6.0,
                   simplify_m: float = 1.0,
                   pixel_size_m: Optional[float] = None) -> list:
    """Vectorize an nDSM array into footprints with heights.

    Parameters
    ----------
    ndsm : 2D numpy array
        Height-above-ground in metres (DSM − DEM). NaN / negative cells are
        treated as ground.
    gt : GeoTransform
        Maps pixel (col, row) → projected/world (x, y). When the raster is in a
        projected CRS (metres) the rings come back in those units; when it is
        already lng/lat, pass that transform and the rings are lng/lat. Callers
        feeding metre-CRS rasters should reproject the rings afterwards.
    min_height_m : float
        Cells at or above this height are "raised" (default 2 m — trees /
        buildings, matching shade.casters_from_project's ``>= 2.0`` rule).
    min_area_m2 : float
        Discard blobs smaller than this (noise / chimneys).
    simplify_m : float
        Douglas–Peucker tolerance for the traced ring, in raster units.
    pixel_size_m : float, optional
        Ground size of a pixel in metres, for the area filter. Inferred from
        ``gt`` when omitted.

    Returns
    -------
    list of ``(ring_xy, height_m)`` where ``ring_xy`` is a list of ``(x, y)``
    world coords (closed) and ``height_m`` is the blob's median height. Empty
    list when numpy/shapely are missing or nothing qualifies.
    """
    if not (_HAVE_NUMPY and _HAVE_SHAPELY):
        return []
    arr = np.asarray(ndsm, dtype="float64")
    if arr.ndim != 2 or arr.size == 0:
        return []
    if pixel_size_m is None:
        # |a| and |e| are the px width/height in world units; assume metres.
        pixel_size_m = math.sqrt(abs(gt[1]) * abs(gt[5])) or 1.0
    px_area = pixel_size_m * pixel_size_m
    min_pixels = max(1, int(round(min_area_m2 / px_area)))

    mask = np.isfinite(arr) & (arr >= float(min_height_m))
    out: list = []
    for cells in _trace_blob_rings(mask, min_pixels):
        poly = _cells_to_polygon(cells)
        if poly is None:
            continue
        poly = poly.simplify(simplify_m / max(pixel_size_m, 1e-9),
                             preserve_topology=True)
        if poly.is_empty or poly.area <= 0:
            continue
        # Representative height: median over the blob's cells (robust to spikes).
        heights = [arr[r, c] for (r, c) in cells if math.isfinite(arr[r, c])]
        height_m = float(np.median(heights)) if heights else float(min_height_m)
        ring_xy = [_pixel_to_xy(x, y, gt) for (x, y) in poly.exterior.coords]
        out.append((ring_xy, round(height_m, 1)))
    return out


class NdsmExtractor:
    """A :class:`FootprintExtractor` over an nDSM GeoTIFF (whiteboxtools-style).

    Reads a height-above-ground raster, vectorizes raised blobs, and returns
    lng/lat rings (+ heights). Register it with
    ``footprint_extract.set_extractor(NdsmExtractor())`` to enable the GUI's
    'Import footprints' action."""

    def __init__(self, *, min_height_m: float = 2.0,
                 min_area_m2: float = 6.0, simplify_m: float = 1.0):
        self.min_height_m = min_height_m
        self.min_area_m2 = min_area_m2
        self.simplify_m = simplify_m

    def extract_with_heights(self, tiff_path: str) -> list:
        ndsm, gt, to_lnglat = read_ndsm_geotiff(tiff_path)
        rings = vectorize_ndsm(
            ndsm, gt, min_height_m=self.min_height_m,
            min_area_m2=self.min_area_m2, simplify_m=self.simplify_m)
        out = []
        for ring_xy, height_m in rings:
            ring_ll = [to_lnglat(x, y) for (x, y) in ring_xy]
            out.append((ring_ll, height_m))
        return out

    def extract_footprints(self, tiff_path: str) -> list:
        return [ring for ring, _h in self.extract_with_heights(tiff_path)]


def read_ndsm_geotiff(tiff_path: str):
    """Read an nDSM GeoTIFF → ``(ndsm_array, geotransform, to_lnglat)``.

    ``to_lnglat(x, y) -> (lng, lat)`` converts the raster's world coords to
    WGS-84 (identity when the raster is already EPSG:4326). Uses ``rasterio``
    (+ ``pyproj`` for reprojection) when available; raises a clear
    ``RuntimeError`` otherwise so the caller can tell the user what to install.
    """
    try:
        import rasterio
    except ImportError as exc:  # pragma: no cover - depends on optional dep
        raise RuntimeError(
            "Reading GeoTIFFs needs the optional 'rasterio' package "
            "(pip install rasterio). The nDSM vectorizer itself only needs "
            "numpy + shapely.") from exc

    with rasterio.open(tiff_path) as ds:
        band = ds.read(1).astype("float64")
        if ds.nodata is not None:
            band = band.copy()
            band[band == ds.nodata] = float("nan")
        t = ds.transform                       # affine.Affine
        gt = (t.c, t.a, t.b, t.f, t.d, t.e)
        crs = ds.crs

    if crs is None or crs.to_epsg() == 4326:
        return band, gt, (lambda x, y: (x, y))

    try:
        from pyproj import Transformer
        tr = Transformer.from_crs(crs, 4326, always_xy=True)
        return band, gt, (lambda x, y: tr.transform(x, y))
    except ImportError as exc:  # pragma: no cover
        raise RuntimeError(
            "This GeoTIFF is in a projected CRS; reprojecting to lat/lng needs "
            "the optional 'pyproj' package (pip install pyproj).") from exc


# ── Qt worker thread (optional; mirrors shade.ShadeWorker / osm.OSMWorker) ───
try:
    from PyQt6.QtCore import QObject, pyqtSignal
    _HAVE_QT = True
except ImportError:
    _HAVE_QT = False

if _HAVE_QT:
    class FootprintExtractWorker(QObject):
        """Run footprint extraction from a GeoTIFF off the UI thread (the read +
        vectorize can be slow).

            worker = FootprintExtractWorker(path)
            worker.ready.connect(on_ready)   # emits {rings, error}
        """

        ready = pyqtSignal(object)
        finished = pyqtSignal()

        def __init__(self, tiff_path, parent=None):
            super().__init__(parent)
            self._path = tiff_path

        def run(self):
            from src.footprint_extract import get_extractor
            try:
                rings = get_extractor().extract_with_heights(self._path)
                payload = {"rings": rings, "error": None}
            except Exception as exc:  # noqa: BLE001 — report, never crash
                payload = {"rings": [], "error": str(exc)}
            self.ready.emit(payload)
            self.finished.emit()
