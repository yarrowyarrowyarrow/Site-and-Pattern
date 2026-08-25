"""
range_map.py — a species range drawn the way a flora draws one.

Design principle P5 — see docs/DESIGN_PHILOSOPHY.md (make the invisible
visible), and P9 for what the picture refuses to claim.

What changed and why
--------------------
The species map used to be twenty-four ecoregion polygons shaded by confidence.
`src/species_range.py` explains why that was the wrong unit. This draws what
the printed regional floras draw: **a shaded range, the records as marks on top
of it, and enough geography to locate them** — province outlines, the big lakes,
the main rivers.

The range squares come from :mod:`src.species_range`; the ground under them is
the same `ecoregion_basemap` the ecoregion maps use, so the two cannot drift
apart geographically. `ecoregion_map.map_svg` is untouched: the region hub pages
and the desktop still need it, and this is a second renderer for a different
question rather than a replacement.

Two marks, and they differ in **shape** as well as colour
---------------------------------------------------------
A herbarium specimen and a phone observation are different kinds of evidence —
a determined sheet in a cabinet against a photograph somebody uploaded — and the
site publishes both with a toggle. Distinguishing them by hue alone fails in
greyscale, fails when printed, and fails for the ~8% of men with a red-green
deficiency. So specimens are **filled** and observations are **hollow**, which
survives all three.

Palettes live in :data:`PALETTES` rather than in the drawing code, because
choosing one is the author's call and prose descriptions of a palette have
already failed once.
"""

from __future__ import annotations

import html

#: Named palettes. Each is one dict so a variant is a data change, not a diff
#: through the renderer. Keys are deliberately about *role*, not colour, so a
#: reader of the drawing code cannot accidentally hard-code a hue.
PALETTES = {
    # Closest to a printed flora plate: near-white ground, the range as a soft
    # warm wash, records as ink.
    "atlas": {
        "label": "Atlas plate",
        "paper": "#faf8f3", "context": "#efece3", "subject": "#ffffff",
        "coast": "#b8b3a4", "border": "#8f897a",
        "water": "#dbe6ec", "river": "#c3d4de",
        "range": "#c8cbb0", "range_edge": "#b3b795",
        "specimen": "#23261d", "observation": "#23261d",
        "city": "#6b6357",
    },
    # The site's own accent family, so a species page does not look like a
    # different website below the fold.
    "sage": {
        "label": "Site sage",
        "paper": "#fbfaf7", "context": "#f1efe8", "subject": "#ffffff",
        "coast": "#cfcbbc", "border": "#8d907f",
        "water": "#e2ebee", "river": "#cbdae1",
        "range": "#bfd0ad", "range_edge": "#9db98a",
        "specimen": "#2f4622", "observation": "#3f5c31",
        "city": "#737667",
    },
    # Warmer and higher contrast: the range reads as a place rather than as a
    # tint, which suits a species with a small tight range.
    "ochre": {
        "label": "Ochre",
        "paper": "#fdfaf4", "context": "#f2ede2", "subject": "#ffffff",
        "coast": "#cbc3b1", "border": "#8a8271",
        "water": "#e4ebe9", "river": "#cddbd8",
        "range": "#e8cf9e", "range_edge": "#d3b478",
        "specimen": "#3d2a12", "observation": "#7a4a1e",
        "city": "#7a7263",
    },
}

DEFAULT_PALETTE = "atlas"


def _cell_polygon(lat: float, lng: float, step: float, project) -> str:
    """One grid square, projected. Four corners, because the projection is a
    conic — a square in degrees is not a rectangle on the page, and drawing it
    as one would leave hairline gaps between neighbours at the top of the map.
    """
    corners = ((lat, lng), (lat + step, lng),
               (lat + step, lng + step), (lat, lng + step))
    pts = " ".join(f"{x:.1f},{y:.1f}"
                   for x, y in (project(b, a) for a, b in corners))
    return pts


def range_svg(cells, *, specimens=(), observations=(), width: int = 640,
              palette: str = DEFAULT_PALETTE, step: float = 0.25,
              title: str = "", cities: bool = True) -> str:
    """The map, as one self-contained ``<svg>`` string.

    ``cells`` are south-west corners from :func:`species_range.occupied_cells`.
    ``specimens`` and ``observations`` are ``(lat, lng)`` pairs. Any of the
    three may be empty: a species with records but no range is impossible, and
    a range with no marks is what the page shows when the reader turns both
    record layers off.
    """
    from src.ecoregion_basemap import (cities_svg, land_svg, provinces_svg,
                                       water_svg)
    from src.ecoregion_map import frame_height, projector

    pal = PALETTES.get(palette) or PALETTES[DEFAULT_PALETTE]
    height = frame_height(width)
    project = projector(width, height)

    parts = [
        f'<svg class="rangemap" viewBox="0 0 {width} {height}" width="100%" '
        f'height="auto" role="img" xmlns="http://www.w3.org/2000/svg" '
        f'aria-label="{html.escape(title or "Range map")}">',
        f'<rect width="{width}" height="{height}" fill="{pal["paper"]}"/>',
        f'<style>.rangemap .ctx{{fill:{pal["context"]};stroke:{pal["coast"]};'
        f'stroke-width:.5}}.rangemap .subj{{fill:{pal["subject"]};'
        f'stroke:{pal["border"]};stroke-width:1}}'
        f'.rangemap .cell{{fill:{pal["range"]};stroke:{pal["range_edge"]};'
        f'stroke-width:.4;shape-rendering:crispEdges}}'
        f'.rangemap .spec{{fill:{pal["specimen"]};fill-opacity:.85;stroke:none}}'
        f'.rangemap .obs{{fill:none;stroke:{pal["observation"]};'
        f'stroke-width:.9;stroke-opacity:.8}}</style>',
    ]
    # Neighbours in grey first, so the two provinces read as part of a
    # continent rather than a shape floating in space.
    parts += land_svg(project, css="ctx")
    parts += provinces_svg(project, subject_only=False, css="ctx")
    parts += provinces_svg(project, subject_only=True, css="subj")
    parts += water_svg(project)

    for lat, lng in cells or ():
        parts.append(f'<polygon class="cell" '
                     f'points="{_cell_polygon(lat, lng, step, project)}"/>')

    # Borders again, over the range, so a province edge stays legible where the
    # wash sits against it. Cheap, and the alternative is a range that looks
    # like it dissolves the boundary it stops at.
    parts += provinces_svg(project, subject_only=True, css="subj")

    r = max(0.9, width * 0.0028)
    for lat, lng in observations or ():
        x, y = project(lng, lat)
        parts.append(f'<circle class="obs" cx="{x:.1f}" cy="{y:.1f}" '
                     f'r="{r:.1f}"/>')
    for lat, lng in specimens or ():
        x, y = project(lng, lat)
        parts.append(f'<circle class="spec" cx="{x:.1f}" cy="{y:.1f}" '
                     f'r="{r:.1f}"/>')

    if cities and width >= 420:
        parts += cities_svg(project)
    parts.append("</svg>")
    return "".join(parts)
