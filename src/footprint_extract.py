"""
footprint_extract.py — Pluggable 2D footprint extraction from raster tiles.

The shade estimator (``src/shade.py`` + ``src/shadow_geometry.py``) casts
shadows from 2D *footprint* polygons of buildings and tree canopies. Today those
footprints are drawn by hand on the map (a canopy/structure perimeter + a height
attribute). This module defines the abstraction by which they could *instead* be
auto-extracted from an imported satellite / aerial TIFF in a future release —
without shipping any heavy dependency now.

Two backends plug in behind ``FootprintExtractor``:
  * **whiteboxtools / nDSM (SHIPPED, V1.53):** derive an nDSM (DSM − DEM) and
    threshold/vectorize it into building & canopy polygons *with* heights — the
    ideal source since shadow length needs a height. Implemented in
    ``src/footprint_ndsm.py``; its vectorizer core needs only numpy + shapely.
  * **Segment Anything (SAM) (future):** segment roofs / crowns from RGB imagery,
    then vectorize the masks to lng/lat rings. Produces footprints *without*
    heights (filled in by hand), so it's a weaker input than an nDSM.

Per the project's optional-dependency policy (cf. ``src/projection.py``'s pyproj
backend and ``src/shadow_geometry.py``'s shapely guard) this module stays **pure
Python and imports nothing heavy** — no torch, no GDAL. ``get_extractor()``
returns the built-in nDSM backend when numpy + shapely are present, an explicitly
registered backend if one was set, else a stub that raises ``NotImplementedError``
with a clear message. The rest of the app only depends on the returned lng/lat
rings + heights, so swapping backends changes nothing downstream.
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
    """Return the active extractor.

    Preference order: an explicitly registered backend (``set_extractor``), else
    the built-in nDSM backend when its deps (numpy + shapely) are importable,
    else the NotImplemented stub. Always returns a ``FootprintExtractor``."""
    if _extractor is not None:
        return _extractor
    try:
        from src.footprint_ndsm import NdsmExtractor, _HAVE_NUMPY, _HAVE_SHAPELY
        if _HAVE_NUMPY and _HAVE_SHAPELY:
            return NdsmExtractor()
    except Exception:  # noqa: BLE001 — fall through to the stub
        pass
    return NotImplementedExtractor()


def extraction_available() -> bool:
    """True when a real (non-stub) extraction backend is available — either
    explicitly registered or the built-in nDSM backend whose deps are present.
    Lets the UI show/hide the 'import footprints from imagery' action."""
    return not isinstance(get_extractor(), NotImplementedExtractor)


def add_extracted_footprints(rings_heights: list, project_dict: dict,
                             *, source: str = "extract") -> list:
    """Append extracted ``(ring_lnglat, height_m)`` footprints to a project as
    shade-casting ``canopy_footprint`` polygon features (the same element type
    the manual draw flow produces, so shade.casters_from_project picks them up).

    Pure: mutates ``project_dict['features']`` in place and returns the list of
    feature dicts it added. Rings with fewer than 3 vertices are skipped. The
    GUI calls this on the main thread after the (optionally off-thread)
    extraction, then renders the returned features."""
    import time
    from src.osm_features import ring_radius_m   # shared footprint sizing
    feats = project_dict.setdefault("features", [])
    new_feats = []
    for ring, height_m in rings_heights or []:
        if not ring or len(ring) < 3:
            continue
        coords = [[float(p[0]), float(p[1])] for p in ring]
        if coords[0] != coords[-1]:
            coords.append(coords[0])           # close the ring
        new_feats.append({
            "type": "Feature",
            "geometry": {"type": "Polygon", "coordinates": [coords]},
            "properties": {
                "element_type": "canopy_footprint",
                "shape_id": f"shape_extract_{int(time.time()*1000)}_{len(new_feats)}",
                "label": "Footprint (imported)",
                "shape_type": "Imported footprint",
                "fill_color": "#8d6e63",
                "stroke_color": "#5d4037",
                "fill_opacity": 0.3,
                "dash_array": "",
                "height_m": float(height_m) if height_m else 0.0,
                "cast_shade": bool(height_m and height_m > 0),
                # Sized from the ring so the keep-out / circle fallback match the
                # footprint instead of a hard-coded default.
                "canopy_radius_m": max(0.5, ring_radius_m(coords)),
                "source": source,
            },
        })
    feats.extend(new_feats)
    return new_feats
