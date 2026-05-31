"""
footprint_extract.py — Pluggable 2D footprint extraction from raster tiles.

The shade estimator (``src/shade.py`` + ``src/shadow_geometry.py``) casts
shadows from 2D *footprint* polygons of buildings and tree canopies. Today those
footprints are drawn by hand on the map (a canopy/structure perimeter + a height
attribute). This module defines the abstraction by which they could *instead* be
auto-extracted from an imported satellite / aerial TIFF in a future release —
without shipping any heavy dependency now.

Two backends are anticipated and plug in behind ``FootprintExtractor``:
  * **Segment Anything (SAM):** segment building roofs / tree crowns from RGB
    imagery, then vectorize the masks to lng/lat rings.
  * **whiteboxtools:** derive an nDSM (DSM − DEM) and threshold/segment it into
    building and canopy polygons *with* heights — the ideal source since shadow
    length needs a height.

Per the project's optional-dependency policy (cf. ``src/projection.py``'s pyproj
backend and ``src/shadow_geometry.py``'s shapely guard) this module is **pure
Python and imports nothing heavy** — no torch, no GDAL, no rasterio ship today.
``get_extractor()`` returns a stub that raises ``NotImplementedError`` with a
clear message; real backends register themselves here later and the rest of the
app (which only depends on the returned lng/lat rings + heights) stays unchanged.
"""

from __future__ import annotations

from typing import Optional, Protocol, runtime_checkable

# A footprint ring is a list of (lng, lat) vertices (GeoJSON order), matching
# what shade.casters_from_project / shadow_geometry.footprint_to_metric expect.
Ring = list  # list[tuple[float, float]]


@runtime_checkable
class FootprintExtractor(Protocol):
    """Protocol every extraction backend implements.

    Implementations convert a georeferenced raster into ground footprints in
    WGS-84 lng/lat. ``extract_with_heights`` is preferred where the backend can
    estimate height (e.g. an nDSM from whiteboxtools); ``extract_footprints``
    is the geometry-only fallback (e.g. SAM masks over RGB) whose heights the
    user fills in manually afterward."""

    def extract_footprints(self, tiff_path: str) -> list:
        """Return a list of lng/lat rings (``list[Ring]``) for the structures /
        canopies detected in ``tiff_path``."""
        ...

    def extract_with_heights(self, tiff_path: str) -> list:
        """Return a list of ``(ring, height_m)`` tuples where the backend can
        estimate height; otherwise raise ``NotImplementedError``."""
        ...


class NotImplementedExtractor:
    """Default backend: no auto-extraction is available.

    Shipped so callers can program against ``get_extractor()`` today and get a
    clear, actionable error rather than an ImportError. Replace by registering a
    SAM- or whiteboxtools-backed extractor via ``set_extractor`` once those
    optional dependencies are adopted.
    """

    _MSG = (
        "Automated footprint extraction is not available in this build. "
        "Install/enable a SAM or whiteboxtools backend, or draw the "
        "canopy/structure perimeter and height manually on the map."
    )

    def extract_footprints(self, tiff_path: str) -> list:
        raise NotImplementedError(self._MSG)

    def extract_with_heights(self, tiff_path: str) -> list:
        raise NotImplementedError(self._MSG)


# Module-level registry. Future backends call set_extractor() at import time.
_extractor: "Optional[FootprintExtractor]" = None


def set_extractor(extractor: "FootprintExtractor") -> None:
    """Register the active footprint-extraction backend (called by a future
    SAM/whiteboxtools plugin)."""
    global _extractor
    _extractor = extractor


def get_extractor() -> "FootprintExtractor":
    """Return the active extractor, or the NotImplemented stub if none is
    registered. Always returns an object satisfying ``FootprintExtractor``."""
    return _extractor if _extractor is not None else NotImplementedExtractor()


def extraction_available() -> bool:
    """True when a real (non-stub) extraction backend is registered, so the UI
    can show/hide an 'auto-extract from imagery' action accordingly."""
    return _extractor is not None and not isinstance(
        _extractor, NotImplementedExtractor)
