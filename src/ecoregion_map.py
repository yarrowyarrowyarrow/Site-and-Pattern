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

    Aspen Parkland is two boxes (one Alberta, one Saskatchewan) under one key,
    and a caller asking "draw aspen parkland" means both.
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
            link_for=None) -> str:
    """The ecoregion map as inline SVG.

    ``highlight`` is ``{ecoregion key: confidence band}``; regions absent from
    it are drawn in the "not recorded here" grey rather than omitted, because
    the shape of where a plant *is not* is half of what a range map says.

    ``link_for`` is an optional ``key -> href`` callable; when given, each
    region becomes a link. Used by the standalone map page and deliberately not
    by the per-species maps, where the region is a fact rather than a control.
    """
    highlight = highlight or {}
    regions = region_geometry()
    if not regions:
        return ""
    project = _projector(width, height)
    order = sorted(regions.items(), key=lambda kv: kv[0] in highlight)

    from src.ecoregion import ecoregion_display              # noqa: PLC0415

    parts = [
        f'<svg class="ecomap" viewBox="0 0 {width} {height}" '
        f'width="100%" height="auto" role="img" '
        f'xmlns="http://www.w3.org/2000/svg" '
        f'aria-label="{html.escape(title or "Ecoregion map")}">'
    ]
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
            shape = (f'<polygon points="{points}" fill="{fill}" '
                     f'fill-opacity="{opacity}" stroke="#7d7a70" '
                     f'stroke-width="0.8" stroke-opacity="0.7">'
                     f'<title>{html.escape(tip)}</title></polygon>')
            href = link_for(key) if link_for else ""
            if href:
                shape = f'<a href="{html.escape(href)}">{shape}</a>'
            parts.append(shape)

    if labels:
        for key, rings in regions.items():
            if not rings:
                continue
            ring = max(rings, key=len)
            xs = [float(c[0]) for c in ring]
            ys = [float(c[1]) for c in ring]
            cx, cy = project(sum(xs) / len(xs), sum(ys) / len(ys))
            name, _ = ecoregion_display(key)
            strong = key in highlight
            parts.append(
                f'<text x="{cx:.1f}" y="{cy:.1f}" text-anchor="middle" '
                f'class="ecomap-label{" on" if strong else ""}">'
                f'{html.escape(_short(name))}</text>')

    parts.append("</svg>")
    return "".join(parts)


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
