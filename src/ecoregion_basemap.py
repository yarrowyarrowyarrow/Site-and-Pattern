"""ecoregion_basemap.py — the ground the ecoregions are drawn on.

Design principle P5 — see docs/DESIGN_PHILOSOPHY.md.

Split out of :mod:`src.ecoregion_map` in V2.66. That module is about *projecting
the thematic layer*; this one is about everything underneath it — the
neighbouring provinces, the water, the frame. The seam is the same one every
atlas has between its basemap and its subject.

WHAT CHANGED, AND WHY IT MATTERS
-------------------------------------------------------------------------------
Until V2.66 the map drew four hand-typed province outlines from
``data/provinces_prairie.geojson``: Saskatchewan and Manitoba were five-vertex
rectangles, and the Alberta/British Columbia border was a straight line. South
of about 54 degrees north that border **is the continental divide**, which is
ragged — a straight line there is not a simplified boundary, it is a different
one, and it put the mountains in the wrong place relative to the foothills.
There was also no water at all, so the Peace and the Athabasca — two of the
largest rivers in Alberta — were simply missing, along with Lake Athabasca and
the whole northern Saskatchewan lake country.

``data/basemap_prairie.geojson`` replaces it with Natural Earth 1:10m, clipped
and simplified by ``tools/ecoregions/basemap.py``. Alberta went from 15 vertices
to 187. Nothing here is hand-authored.

This module is drawing only. ``src.ecoregion``'s point lookup has never read a
basemap and still does not: which ecoregion a property falls in is a question
about ecoregion polygons, and putting a river in the file cannot change it.
"""

from __future__ import annotations

import html
import json
from functools import lru_cache

from src.resources import resource_path

__all__ = ["cities_svg", "layer", "water_svg", "provinces_svg"]

#: Drawn as a dot and a label when the map is big enough to carry them. These
#: double as the point probes the ecoregion tests assert against, which is why
#: they are places with unambiguous ecoregion membership rather than simply the
#: largest towns.
CITIES = (
    ("Edmonton", 53.5461, -113.4938),
    ("Calgary", 51.0447, -114.0719),
    ("Fort McMurray", 56.7264, -111.3803),
    ("Grande Prairie", 55.1707, -118.7947),
    ("Lethbridge", 49.6956, -112.8451),
    ("Saskatoon", 52.1332, -106.6700),
    ("Regina", 50.4452, -104.6189),
    ("Prince Albert", 53.2033, -105.7531),
)

#: Where each province's two-letter code sits. Placed by hand rather than at a
#: centroid: Alberta's centroid lands in the middle of the boreal fill, where
#: the label fights the shading.
PROVINCE_LABELS = (("AB", 57.6, -115.0), ("SK", 57.6, -106.0),
                   ("BC", 55.0, -120.5), ("MB", 55.0, -100.9))


@lru_cache(maxsize=1)
def _features() -> list[dict]:
    """The shipped basemap, or an empty list.

    Returns empty rather than raising, for the same reason the ecoregion loader
    does: a missing basemap should cost the reader a plain map, not a traceback
    in the middle of a species page.
    """
    try:
        with open(resource_path("data", "basemap_prairie.geojson"),
                  encoding="utf-8") as fh:
            return (json.load(fh) or {}).get("features", []) or []
    except Exception:                                        # noqa: BLE001
        return []


def layer(name: str) -> list[dict]:
    """Every feature tagged with ``properties.layer == name``."""
    return [f for f in _features()
            if ((f.get("properties") or {}).get("layer") or "") == name]


def _rings(geometry: dict) -> list:
    """Outer rings only. Holes are dropped deliberately: at this scale the one
    polygon with a hole is a lake inside an island, and carrying holes through
    the projector costs more than the two pixels it would repaint.
    """
    kind = geometry.get("type")
    coords = geometry.get("coordinates") or []
    if kind == "Polygon":
        return [coords[0]] if coords else []
    if kind == "MultiPolygon":
        return [poly[0] for poly in coords if poly]
    return []


def _lines(geometry: dict) -> list:
    kind = geometry.get("type")
    coords = geometry.get("coordinates") or []
    if kind == "LineString":
        return [coords] if coords else []
    if kind == "MultiLineString":
        return [line for line in coords if line]
    return []


def _points(ring, project, min_px: float = 0.0) -> str:
    """One projected ring as an SVG ``points`` string, optionally decimated.

    ``min_px`` drops a vertex landing within that distance of the last one
    kept. The polygons are simplified to about 900 m for display, which is
    right for a 900 px region map and about three times finer than a pixel on
    the 420 px map a species page carries.

    A rendering decision, not a data one -- the same argument as
    `occurrence_points.MARK_DEG`. First and last vertices are always kept so a
    ring still closes, and ``min_px=0`` (the default) changes nothing, so every
    existing map stays byte-identical.
    """
    pts = [project(float(lon), float(lat)) for lon, lat in ring]
    if min_px > 0 and len(pts) > 3:
        kept = [pts[0]]
        for x, y in pts[1:-1]:
            lx, ly = kept[-1]
            if abs(x - lx) >= min_px or abs(y - ly) >= min_px:
                kept.append((x, y))
        kept.append(pts[-1])
        pts = kept
    return " ".join(f"{x:.1f},{y:.1f}" for x, y in pts)


def provinces_svg(project, *, subject_only: bool = False,
                  css: str = "ecomap-prov") -> list[str]:
    """Filled province/state polygons.

    ``subject_only`` draws Alberta and Saskatchewan alone; otherwise the
    neighbours are drawn too, which is what stops the two provinces reading as a
    shape floating in space. The caller styles the two cases differently — the
    neighbours are context and belong in grey.
    """
    out = []
    for feature in layer("province"):
        props = feature.get("properties") or {}
        if subject_only != bool(props.get("subject")):
            continue
        for ring in _rings(feature.get("geometry") or {}):
            out.append(f'<polygon class="{css}" points="{_points(ring, project)}"/>')
    return out


def land_svg(project, *, css: str = "ecomap-land") -> list[str]:
    """The union of every province and state in the window, drawn first.

    Underneath everything so that the hairline gaps between independently
    simplified neighbours fall through to land rather than to the page.
    """
    return [f'<polygon class="{css}" points="{_points(ring, project)}"/>'
            for feature in layer("land")
            for ring in _rings(feature.get("geometry") or {})]


#: id of the clip path that confines the thematic layer to the subject provinces.
SUBJECT_CLIP_ID = "ecomap-subject-clip"


def in_subject_provinces(lat: float, lng: float) -> bool:
    """Back-compat shim. The implementation lives in :mod:`src.subject_area`,
    extracted in V2.78 when it put this file over its line ceiling -- and the
    split is the right one anyway: this module draws the ground, that one
    decides whether a piece of evidence is on it.
    """
    from src.subject_area import in_subject_provinces as impl  # noqa: PLC0415
    return impl(lat, lng)


def subject_clip_defs(project) -> str:
    """A ``<clipPath>`` covering Alberta and Saskatchewan.

    The ecoregion layer classifies two provinces and nothing else, but a
    polygon does not know where its own authority stops. The hand-traced
    placeholders ran south past the 49th parallel into Montana and east past
    the Saskatchewan/Manitoba border, because they were drawn to cover the
    provinces rather than to stop at them. The surveyed layer that replaced
    them in V2.67 is clipped to the two provinces at source, so this matters
    less than it did — but it is still doing work at the edges, where
    simplification pushes a boundary a few hundred metres the wrong side of a
    border it is supposed to follow. Clipping in SVG says the true thing —
    *this* is the area the layer speaks for — without needing a
    polygon-clipping library in a module that has always been dependency-free.

    It stays useful after the real polygons land: a national dataset clipped to
    a provincial window still leaves ragged edges a pixel or two over the line.
    """
    rings = []
    for feature in layer("province"):
        if not (feature.get("properties") or {}).get("subject"):
            continue
        for ring in _rings(feature.get("geometry") or {}):
            rings.append(f'<polygon points="{_points(ring, project)}"/>')
    if not rings:
        return ""
    return (f'<clipPath id="{SUBJECT_CLIP_ID}">' + "".join(rings) + "</clipPath>")


def water_svg(project, *, lakes: bool = True, rivers: bool = True) -> list[str]:
    """Lakes as filled polygons, rivers as polylines.

    Water is what makes a prairie map locatable. The North Saskatchewan through
    Edmonton and the South Saskatchewan through Saskatoon are how most readers
    place themselves before they have read a single label.
    """
    out = []
    if lakes:
        for feature in layer("lake"):
            for ring in _rings(feature.get("geometry") or {}):
                out.append('<polygon class="ecomap-lake" '
                           f'points="{_points(ring, project)}"/>')
    if rivers:
        for feature in layer("river"):
            for line in _lines(feature.get("geometry") or {}):
                out.append('<polyline class="ecomap-river" fill="none" '
                           f'points="{_points(line, project)}"/>')
    return out


def cities_svg(project, *, places: bool = True, provinces: bool = True) -> list[str]:
    """City dots with labels, and the two-letter province codes."""
    out = []
    if places:
        for name, lat, lon in CITIES:
            x, y = project(lon, lat)
            out.append(f'<circle class="ecomap-city" cx="{x:.1f}" '
                       f'cy="{y:.1f}" r="2.2"/>')
            out.append(f'<text class="ecomap-place" x="{x + 4:.1f}" '
                       f'y="{y + 3:.1f}">{html.escape(name)}</text>')
    if provinces:
        for code, lat, lon in PROVINCE_LABELS:
            x, y = project(lon, lat)
            out.append(f'<text class="ecomap-prov-label" x="{x:.1f}" '
                       f'y="{y:.1f}" text-anchor="middle">{code}</text>')
    return out
