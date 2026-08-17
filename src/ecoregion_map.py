"""
ecoregion_map.py — the ecoregions, drawn.

Design principle P5 — see docs/DESIGN_PHILOSOPHY.md.

The catalogue has known since V2.38 which ecoregions a species has actually been
recorded in, with an occurrence count and a confidence band per region
(``plant_ecoregions``, from GBIF). Until now the only way to read that was as a
list of region names, which asks the reader to hold a map of Alberta and
Saskatchewan in their head. A range is a *shape*; drawing it costs one SVG.

**These outlines are hand-authored, and the map says so.** They were ten
five-vertex rectangles until V2.49 traced them against real geography
(``scripts/draw_ecoregions.py``), and they are still a diagram: the real CEC
Level III polygons are a download that has never run in a session with open
egress. An outline drawn without a caption is a claim about a boundary; the
caption (``CAVEAT``) is what keeps it honest (P9). Replace the file and every
map here sharpens with no code change.

**What a colour asserts lives next door**, in :mod:`src.ecoregion_palette`, and
is re-exported here so a caller keeps one import for "the ecoregions, drawn".
The short version: hue is region identity, lightness is confidence (V2.51).

Output is a self-contained ``<svg>`` string: no script, no external reference,
no dependency. Callers embed it directly. ``legend_html`` is the colour key,
which is markup rather than SVG so it can wrap on a phone.
"""

from __future__ import annotations

import html
import json
import math
from functools import lru_cache
from typing import Optional

from src.ecoregion_basemap import (SUBJECT_CLIP_ID, cities_svg, land_svg,
                                   provinces_svg, subject_clip_defs,
                                   water_svg)
from src.ecoregion_palette import (ABSENT_FILL, DRAW_ORDER, HATCHED,
                                   REGION_COLOUR, hatch_defs, hatch_url,
                                   legend_html, region_fill)
from src.resources import resource_path

#: Re-exported so callers keep one import for "the ecoregions, drawn".
__all__ = ["CAVEAT", "HATCHED", "REGION_COLOUR", "frame_height", "legend_html",
           "map_svg", "region_fill", "region_geometry"]

#: Lon/lat window the map draws. Slightly wider than the polygons' own bounds so
#: nothing sits flush against the frame.
_BOUNDS = (-121.0, 48.4, -100.4, 60.6)          # west, south, east, north


#: Albers Equal Area Conic: standard parallels 50 and 58 north, central meridian
#: 110.5 west — the middle of this window.
#:
#: **Why a real projection replaced the cosine factor in V2.66.** The old
#: projector was plate carree with longitude scaled by cos(mean latitude) — one
#: number for the whole map. Across twelve degrees of latitude that number is
#: wrong at both ends: it over-widens the 49th parallel and pinches the 60th, so
#: the grassland looked bigger than it is and the boreal smaller. On a map whose
#: entire job is "how much ground does each ecoregion cover", areas that are not
#: comparable is the one defect that cannot be styled around. Albers is
#: equal-area by construction.
#:
#: **Why not ESRI:102001 verbatim**, which is what the GeoPackage
#: ``tools/ecoregions`` exports is written in. Canada Albers puts its central
#: meridian at 96 west, to keep the whole country upright. Fourteen degrees west
#: of that, the cone has turned far enough that Alberta and Saskatchewan arrive
#: visibly rotated — the first render of this projector came out tilted about
#: twelve degrees clockwise, with the 60th parallel running downhill across the
#: frame. Re-centring the same projection on this window is the standard fix and
#: costs nothing: it is still Albers, still equal-area, and areas still compare.
#: The exported data keeps ESRI:102001 because that is the number other tools
#: expect; only the *drawing* is re-centred.
_ALBERS = (50.0, 58.0, 54.0, -110.5)    # lat1, lat2, lat0, lon0


def _albers(lon: float, lat: float) -> tuple:
    """Albers forward. Returns unscaled (x, y) on the unit sphere, y northward."""
    lat1, lat2, lat0, lon0 = _ALBERS
    p1, p2 = math.radians(lat1), math.radians(lat2)
    n = (math.sin(p1) + math.sin(p2)) / 2.0
    c = math.cos(p1) ** 2 + 2.0 * n * math.sin(p1)
    rho0 = math.sqrt(c - 2.0 * n * math.sin(math.radians(lat0))) / n
    rho = math.sqrt(max(0.0, c - 2.0 * n * math.sin(math.radians(lat)))) / n
    theta = n * math.radians(lon - lon0)
    return rho * math.sin(theta), rho0 - rho * math.cos(theta)


@lru_cache(maxsize=1)
def _extent() -> tuple:
    """The projected bounding box of the map window.

    Sampled around the window's edge rather than taken from its four corners: a
    conic curves, so the northern edge bows and its midpoint is the highest
    point on the map, not either corner.
    """
    west, south, east, north = _BOUNDS
    steps = 60
    xs, ys = [], []
    for i in range(steps + 1):
        f = i / steps
        lon = west + (east - west) * f
        lat = south + (north - south) * f
        for point in ((lon, south), (lon, north), (west, lat), (east, lat)):
            x, y = _albers(*point)
            xs.append(x)
            ys.append(y)
    return min(xs), min(ys), max(xs), max(ys)


def frame_height(width: int) -> int:
    """The height that makes ``width`` fill the frame with no letterbox.

    The projector letterboxes rather than distort, so a caller that picks its
    own height gets blank bands and a map half the size of its own figure.
    Callers ask for a width and take the height they get.
    """
    x0, y0, x1, y1 = _extent()
    return round(width * (y1 - y0) / (x1 - x0))


def _load() -> list[dict]:
    try:
        with open(resource_path("data", "ecoregions_canada.geojson"),
                  encoding="utf-8") as fh:
            return (json.load(fh) or {}).get("features", []) or []
    except Exception:                                        # noqa: BLE001
        return []


def _rings(geometry: dict) -> list:
    kind = geometry.get("type")
    coords = geometry.get("coordinates") or []
    if kind == "Polygon":
        return [coords[0]] if coords else []
    if kind == "MultiPolygon":
        return [poly[0] for poly in coords if poly]
    return []


def _projector(width: float, height: float):
    """lon/lat -> SVG user units, equal-area conic, centred and letterboxed."""
    x0, y0, x1, y1 = _extent()
    span_x, span_y = x1 - x0, y1 - y0
    scale = min(width / span_x, height / span_y)
    pad_x = (width - span_x * scale) / 2.0
    pad_y = (height - span_y * scale) / 2.0

    def project(lon: float, lat: float) -> tuple:
        x, y = _albers(lon, lat)
        # SVG y grows downward; the projection's grows north.
        return pad_x + (x - x0) * scale, pad_y + (y1 - y) * scale

    return project


def region_geometry() -> dict:
    """``{key: [ring, ...]}`` merged across the file's duplicate entries.

    A region may be drawn as more than one polygon, and a caller asking to draw
    it means all of them.
    """
    out: dict = {}
    for feature in _load():
        key = ((feature.get("properties") or {}).get("key") or "").strip()
        if not key:
            continue
        out.setdefault(key, []).extend(_rings(feature.get("geometry") or {}))
    return out


def map_svg(highlight: Optional[dict] = None, *,
            width: int = 460, height: int = 300,
            title: str = "", labels: bool = True,
            cities: Optional[bool] = None,
            link_for=None, reference: bool = False) -> str:
    """The ecoregion map as inline SVG.

    ``highlight`` is ``{ecoregion key: confidence band}``; regions absent from
    it are drawn in the "not recorded here" grey rather than omitted, because
    the shape of where a plant *is not* is half of what a range map says.

    ``reference=True`` draws every region in its own colour at full strength
    and claims no confidence at all. That is the mode for a navigation or key
    map, which is about *where the regions are*, not about a species. It exists
    because those callers used to pass a fabricated ``"medium"`` for every
    region and got a tooltip reading "medium confidence" about nothing.

    ``cities`` defaults to on above 420px wide. Below that the dots collide and
    a map you cannot read is worse than one without labels.

    ``link_for`` is an optional ``key -> href`` callable; when given, each
    region becomes a link. Used by the standalone map page and deliberately not
    by the per-species maps, where the region is a fact rather than a control.
    """
    highlight = highlight or {}
    regions = region_geometry()
    if not regions:
        return ""
    if cities is None:
        cities = width >= 420
    project = _projector(width, height)
    order = sorted(regions.items(),
                   key=lambda kv: (DRAW_ORDER.get(kv[0], 50),) if reference
                   else (kv[0] in highlight,))

    from src.ecoregion import ecoregion_display              # noqa: PLC0415

    parts = [
        f'<svg class="ecomap" viewBox="0 0 {width} {height}" '
        f'width="100%" height="auto" role="img" '
        f'xmlns="http://www.w3.org/2000/svg" '
        f'aria-label="{html.escape(title or "Ecoregion map")}">',
        hatch_defs(),
        subject_clip_defs(project),
    ]
    # Neighbours first and in grey — they are context, and without them the two
    # provinces read as a shape floating in space rather than part of a
    # continent. Then Alberta and Saskatchewan as the wash the fills sit on.
    parts += land_svg(project)
    parts += provinces_svg(project, subject_only=False, css="ecomap-context")
    parts += provinces_svg(project, subject_only=True, css="ecomap-prov")
    # Everything thematic is clipped to the two provinces the layer speaks for.
    parts.append(f'<g clip-path="url(#{SUBJECT_CLIP_ID})">')
    for key, rings in order:
        band = highlight.get(key)
        present = reference or key in highlight
        name, where = ecoregion_display(key)
        tip = name + (f" ({where})" if where else "")
        if reference:
            fill, opacity = region_fill(key, "high")
        elif present:
            fill, opacity = region_fill(key, band or "")
            tip += f", {band} confidence" if band else ", recorded"
        else:
            fill, opacity = ABSENT_FILL
            tip += ", not recorded"
        hatch = hatch_url(key) if (reference or present) else ""
        for ring in rings:
            points = " ".join(
                f"{x:.1f},{y:.1f}" for x, y in
                (project(float(lon), float(lat)) for lon, lat in ring))
            shape = (f'<polygon class="ecomap-region" points="{points}" '
                     f'fill="{fill}" fill-opacity="{opacity}">'
                     f'<title>{html.escape(tip)}</title></polygon>')
            if hatch:
                # A second polygon over the first rather than a pattern *as* the
                # fill: the flat colour has to stay underneath so the region
                # keeps its identity for a reader who sees colour fine and is
                # only helped, not replaced, by the texture.
                shape += (f'<polygon class="ecomap-hatch" points="{points}" '
                          f'fill="{hatch}"/>')
            href = link_for(key) if link_for else ""
            if href:
                shape = f'<a href="{html.escape(href)}">{shape}</a>'
            parts.append(shape)

    parts.append("</g>")
    # Water over the fills — a river that vanishes under a polygon is worse than
    # no river — then borders on top so a boundary reads through everything.
    parts += water_svg(project)
    parts += provinces_svg(project, subject_only=True, css="ecomap-border")

    if cities:
        parts += cities_svg(project)

    if labels:
        for key, rings in regions.items():
            if not rings:
                continue
            ring = max(rings, key=len)
            lon, lat, angle = _label_point(key, ring)
            cx, cy = project(lon, lat)
            name, _ = ecoregion_display(key)
            strong = reference or key in highlight
            spin = (f' transform="rotate({angle} {cx:.1f} {cy:.1f})"'
                    if angle else "")
            parts.append(
                f'<text x="{cx:.1f}" y="{cy:.1f}" text-anchor="middle"{spin} '
                f'class="ecomap-label{" on" if strong else ""}">'
                f'{html.escape(_short(name))}</text>')

    parts.append("</svg>")
    return "".join(parts)


#: Where each region's name sits, and at what angle. A centroid is the obvious
#: choice and the wrong one for these shapes: the parkland is a crescent whose
#: centroid falls outside it, and the montane strip's centroid lands in British
#: Columbia.
#:
#: The two western strips are about 25px wide on the reference map and the word
#: "Foothills" is twice that, so they are set ALONG the strip instead of across
#: it — 55 degrees, which is the bearing of the continental divide through this
#: window. Every point here is asserted to fall inside its own polygon by
#: ``tests/test_ecoregion.py``, because the first version of this table had
#: "Montane" printed in British Columbia.
_LABEL_POINT = {
    "boreal_mixedwood": (-110.5, 57.2, 0),
    "aspen_parkland": (-111.5, 53.3, 0),
    "moist_mixedgrass": (-104.6, 50.6, 0),
    "mixedgrass_prairie": (-111.0, 50.1, 0),
    "fescue_foothills": (-116.08, 52.40, 55),
    "subalpine_montane": (-115.69, 51.20, 55),
}


def _label_point(key: str, ring: list) -> tuple:
    if key in _LABEL_POINT:
        return _LABEL_POINT[key]
    xs = [float(c[0]) for c in ring]
    ys = [float(c[1]) for c in ring]
    return sum(xs) / len(xs), sum(ys) / len(ys), 0


def _short(name: str) -> str:
    """Region names are long and the boxes are small."""
    return {
        "Boreal Mixedwood / Plain": "Boreal",
        "Moist Mixed Grassland": "Moist Mixed",
        "Mixedgrass Prairie": "Mixedgrass",
        "Fescue / Foothills": "Foothills",
        "Subalpine / Montane": "Montane",
        "Aspen Parkland": "Parkland",
    }.get(name, name)


#: The one sentence that has to travel with every drawing of this file.
CAVEAT = ("Approximate extents, not surveyed boundaries: the regions are "
          "hand-traced against the geography, not digitised from a survey. "
          "Occurrence counts are real; the outlines are a diagram.")
