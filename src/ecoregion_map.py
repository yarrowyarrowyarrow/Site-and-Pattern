"""
ecoregion_map.py — the ecoregions, drawn.

Design principle P5 — see docs/DESIGN_PHILOSOPHY.md.

The catalogue has known since V2.38 which ecoregions a species has actually been
recorded in, with an occurrence count and a confidence band per region
(``plant_ecoregions``, from GBIF). Until now the only way to read that was as a
list of region names, which asks the reader to hold a map of Alberta and
Saskatchewan in their head. A range is a *shape*; drawing it costs one SVG.

**These polygons are rectangles, and the map says so.** ``ecoregions_canada.
geojson`` holds ten hand-drawn five-vertex boxes, documented as such in
``docs/plans/V2.38-ecoregion-runbook.md``: the real CEC Level III polygons are a
download that has never run in a session with open egress. A box drawn without a
caption is a claim about a boundary; the caption is what keeps it an honest
diagram (P9). Replace the file and every map here sharpens with no code change.

Output is a self-contained ``<svg>`` string: no script, no external reference,
no dependency. Callers embed it directly.
"""

from __future__ import annotations

import html
import json
import math
from typing import Optional

from src.resources import resource_path

#: Lon/lat window the map draws. Slightly wider than the polygons' own bounds so
#: nothing sits flush against the frame.
_BOUNDS = (-121.0, 48.4, -100.4, 60.6)          # west, south, east, north

#: Fills for a region the species is recorded in, by confidence band. A region
#: derived from three records must not look like one derived from three hundred.
_CONFIDENCE_FILL = {
    "high":   ("#4a6b3a", 0.92),
    "medium": ("#6f8f52", 0.72),
    "low":    ("#9db97e", 0.52),
    "":       ("#9db97e", 0.45),
}
_ABSENT_FILL = ("#d9d6cc", 0.55)


def _load() -> list[dict]:
    try:
        with open(resource_path("data", "ecoregions_canada.geojson"),
                  encoding="utf-8") as fh:
            return (json.load(fh) or {}).get("features", []) or []
    except Exception:                                        # noqa: BLE001
        return []


def _load_provinces() -> list[dict]:
    """Provincial outlines, for drawing only.

    Never read by ``src.ecoregion``'s lookup. Borders are most of what made the
    reference map legible: without them a reader has no idea which part of the
    country they are looking at, which was the single biggest thing wrong with
    the first version of this drawing.
    """
    try:
        with open(resource_path("data", "provinces_prairie.geojson"),
                  encoding="utf-8") as fh:
            return (json.load(fh) or {}).get("features", []) or []
    except Exception:                                        # noqa: BLE001
        return []


#: Drawn as a dot and a label when the map is big enough to carry them.
#: Orientation is most of what a reader needs from a small map.
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
                   ("BC", 55.0, -121.3), ("MB", 55.0, -100.0))


def _rings(geometry: dict) -> list:
    kind = geometry.get("type")
    coords = geometry.get("coordinates") or []
    if kind == "Polygon":
        return [coords[0]] if coords else []
    if kind == "MultiPolygon":
        return [poly[0] for poly in coords if poly]
    return []


def _projector(width: float, height: float):
    """Equirectangular, with longitude compressed by cos(mean latitude).

    At this scale a plate-carree map of the prairies is visibly stretched
    east-west; one cosine factor is the whole correction and keeps the drawing
    honest about proportions without pulling in a projection library.
    """
    west, south, east, north = _BOUNDS
    k = math.cos(math.radians((south + north) / 2.0))
    span_x = (east - west) * k
    span_y = north - south
    scale = min(width / span_x, height / span_y)
    pad_x = (width - span_x * scale) / 2.0
    pad_y = (height - span_y * scale) / 2.0

    def project(lon: float, lat: float) -> tuple:
        x = pad_x + (lon - west) * k * scale
        y = pad_y + (north - lat) * scale
        return x, y

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
            link_for=None) -> str:
    """The ecoregion map as inline SVG.

    ``highlight`` is ``{ecoregion key: confidence band}``; regions absent from
    it are drawn in the "not recorded here" grey rather than omitted, because
    the shape of where a plant *is not* is half of what a range map says.

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
    order = sorted(regions.items(), key=lambda kv: kv[0] in highlight)

    from src.ecoregion import ecoregion_display              # noqa: PLC0415

    parts = [
        f'<svg class="ecomap" viewBox="0 0 {width} {height}" '
        f'width="100%" height="auto" role="img" '
        f'xmlns="http://www.w3.org/2000/svg" '
        f'aria-label="{html.escape(title or "Ecoregion map")}">'
    ]
    # Provinces first, as a plain wash under the ecoregion fills: they are the
    # frame, not the subject.
    for feature in _load_provinces():
        for ring in _rings(feature.get("geometry") or {}):
            points = " ".join(
                f"{x:.1f},{y:.1f}" for x, y in
                (project(float(lon), float(lat)) for lon, lat in ring))
            parts.append(f'<polygon class="ecomap-prov" points="{points}"/>')
    for key, rings in order:
        band = highlight.get(key)
        present = key in highlight
        fill, opacity = (_CONFIDENCE_FILL.get(band or "", _CONFIDENCE_FILL[""])
                         if present else _ABSENT_FILL)
        name, where = ecoregion_display(key)
        tip = name + (f" ({where})" if where else "")
        if present:
            tip += f", {band} confidence" if band else ", recorded"
        else:
            tip += ", not recorded"
        for ring in rings:
            points = " ".join(
                f"{x:.1f},{y:.1f}" for x, y in
                (project(float(lon), float(lat)) for lon, lat in ring))
            shape = (f'<polygon class="ecomap-region" points="{points}" '
                     f'fill="{fill}" fill-opacity="{opacity}">'
                     f'<title>{html.escape(tip)}</title></polygon>')
            href = link_for(key) if link_for else ""
            if href:
                shape = f'<a href="{html.escape(href)}">{shape}</a>'
            parts.append(shape)

    # Provincial borders again, on top, so a boundary reads through the fills.
    for feature in _load_provinces():
        for ring in _rings(feature.get("geometry") or {}):
            points = " ".join(
                f"{x:.1f},{y:.1f}" for x, y in
                (project(float(lon), float(lat)) for lon, lat in ring))
            parts.append(f'<polygon class="ecomap-border" points="{points}"/>')

    if cities:
        for name, lat, lon in CITIES:
            x, y = project(lon, lat)
            parts.append(f'<circle class="ecomap-city" cx="{x:.1f}" '
                         f'cy="{y:.1f}" r="2.2"/>')
            parts.append(f'<text class="ecomap-place" x="{x + 4:.1f}" '
                         f'y="{y + 3:.1f}">{html.escape(name)}</text>')
        for code, lat, lon in PROVINCE_LABELS:
            x, y = project(lon, lat)
            parts.append(f'<text class="ecomap-prov-label" x="{x:.1f}" '
                         f'y="{y:.1f}" text-anchor="middle">{code}</text>')

    if labels:
        for key, rings in regions.items():
            if not rings:
                continue
            ring = max(rings, key=len)
            cx, cy = project(*_label_point(key, ring))
            name, _ = ecoregion_display(key)
            strong = key in highlight
            parts.append(
                f'<text x="{cx:.1f}" y="{cy:.1f}" text-anchor="middle" '
                f'class="ecomap-label{" on" if strong else ""}">'
                f'{html.escape(_short(name))}</text>')

    parts.append("</svg>")
    return "".join(parts)


#: Where each region's name sits. A centroid is the obvious choice and the
#: wrong one for these shapes: the parkland is a crescent whose centroid falls
#: outside it, and the montane strip's centroid lands in British Columbia.
_LABEL_POINT = {
    "boreal_mixedwood": (-110.5, 57.0),
    "aspen_parkland": (-111.5, 53.3),
    "moist_mixedgrass": (-104.0, 50.4),
    "mixedgrass_prairie": (-111.0, 50.1),
    "fescue_foothills": (-114.6, 52.3),
    "subalpine_montane": (-117.3, 53.4),
}


def _label_point(key: str, ring: list) -> tuple:
    if key in _LABEL_POINT:
        return _LABEL_POINT[key]
    xs = [float(c[0]) for c in ring]
    ys = [float(c[1]) for c in ring]
    return sum(xs) / len(xs), sum(ys) / len(ys)


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
CAVEAT = ("Approximate extents, not surveyed boundaries: the shipped regions "
          "are hand-drawn boxes. Occurrence counts are real; the outlines are "
          "a diagram.")
