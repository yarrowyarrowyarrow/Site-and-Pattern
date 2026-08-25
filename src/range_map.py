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

The marks are off by default, and that is arithmetic (V2.80)
------------------------------------------------------------
The author's verdict on the three palettes was *"all look identical"*, and the
reason was not taste. Measured on the shipped cache:

===========================  ===========  ===========  ==============
species                      range cells  marks drawn  marks per cell
===========================  ===========  ===========  ==============
*Gaillardia aristata*                361        4,046            11.2
*Opuntia polyacantha*                183        5,401            29.5
*Cornus canadensis*                  455        4,707            10.3
===========================  ===========  ===========  ==============

The palettes differ almost entirely in the range wash, and at 460 px the wash
sits under tens of overlapping marks per square. None of the colour was
visible, so a fourth palette would have changed nothing.

So the cell carries the information instead: each square is shaded by **how many
records it holds**, five bands from `species_range.density_band`, and
``marks="none"`` is the default. Four thousand overlapping dots become 361
legible squares, which is what a modern distribution atlas does. The marks are
still drawable — ``marks="all"`` is what the F147 specimen/observation toggle
will switch on over the top of the wash, where the reader has asked for them and
the wash has already done its job.

A ramp needs a legend or it is decoration, so one is drawn in the corner, and it
is titled *records* rather than anything that sounds like abundance: a cell
holding a city is dark for nearly every species in the catalogue.
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
        "ramp": ["#eaece0", "#d5d8c4", "#c0c4a6", "#a5aa88", "#868c6a"],
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
        "ramp": ["#e7efdf", "#d2e0c4", "#b8cda4", "#98b382", "#73955f"],
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
        "ramp": ["#f7edd8", "#eeddb8", "#e2c795", "#cfab6f", "#b58c4c"],
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


def _legend_svg(pal: dict, width: int, height: int) -> list:
    """The ramp, keyed, in the bottom-left corner.

    Drawn whenever the ramp is, because a five-step wash with nothing to read
    it against is decoration. The title is *records* and not a word that could
    be heard as abundance -- see `species_range.density_band`.
    """
    from src.species_range import BAND_LABELS

    # 26 px a swatch, because "100+" at 7.5 px needs about 22 and the labels
    # ran into each other at 15 -- the first render of this legend was
    # unreadable for exactly that reason.
    sw, gap, ramp = 26.0, 2.0, pal["ramp"]
    box_w = len(ramp) * (sw + gap) - gap
    out = [f'<g class="key" transform="translate(14,{height - 30:.0f})">',
           f'<rect class="keybg" x="-6" y="-14" width="{box_w + 12:.0f}" '
           f'height="34" rx="2"/>',
           '<text class="keyt" x="0" y="-5">records per square</text>']
    for i, colour in enumerate(ramp):
        x = i * (sw + gap)
        out.append(f'<rect x="{x:.0f}" y="0" width="{sw:.0f}" height="8" '
                   f'fill="{colour}"/>')
        out.append(f'<text class="keyl" x="{x + sw / 2:.1f}" y="17">'
                   f'{html.escape(BAND_LABELS[i])}</text>')
    out.append("</g>")
    return out


def range_svg(cells, *, specimens=(), observations=(), width: int = 640,
              palette: str = DEFAULT_PALETTE, step: float = 0.25,
              title: str = "", cities: bool = True, marks: str = "none",
              legend: bool = True) -> str:
    """The map, as one self-contained ``<svg>`` string.

    ``cells`` are rows from :func:`species_range.cell_counts` or
    :func:`species_range.parse_document` -- ``(lat, lng)`` south-west corners,
    or ``(lat, lng, records)`` to shade each square by how many records it
    holds. A plain mapping of ``{cell: count}`` is accepted too.

    ``marks`` is ``"none"`` (the default), ``"all"``, or ``"few"``, which draws
    marks only for cells holding a single record -- the places the wash makes
    least visible. **The default is off on purpose**: at this scale a
    well-recorded species draws 10-30 marks per square, which buries the wash
    entirely. The module docstring has the measurements.

    ``specimens`` and ``observations`` are ``(lat, lng)`` pairs, and are only
    consulted when ``marks`` asks for them. Any of the three may be empty: a
    range with no marks is the default view, and no cells at all is what a
    species with no usable record draws (which is nothing, per P9).
    """
    from src.ecoregion_basemap import (cities_svg, land_svg, provinces_svg,
                                       water_svg)
    from src.ecoregion_map import frame_height, projector

    from src.species_range import density_band

    pal = PALETTES.get(palette) or PALETTES[DEFAULT_PALETTE]
    height = frame_height(width)
    project = projector(width, height)

    if isinstance(cells, dict):
        rows = [(lat, lng, n) for (lat, lng), n in sorted(cells.items())]
    else:
        rows = [tuple(c) for c in (cells or ())]
    counted = all(len(r) >= 3 for r in rows) and bool(rows)
    ramp = pal.get("ramp") or []
    show_key = bool(legend and counted and ramp and width >= 420)

    parts = [
        f'<svg class="rangemap" viewBox="0 0 {width} {height}" width="100%" '
        f'height="auto" role="img" xmlns="http://www.w3.org/2000/svg" '
        f'aria-label="{html.escape(title or "Range map")}">',
        f'<rect width="{width}" height="{height}" fill="{pal["paper"]}"/>',
        f'<style>.rangemap .ctx{{fill:{pal["context"]};stroke:{pal["coast"]};'
        f'stroke-width:.5}}.rangemap .subj{{fill:{pal["subject"]};'
        f'stroke:{pal["border"]};stroke-width:1}}'
        # The second, over-the-range pass is stroke ONLY. It reused `.subj`,
        # whose fill is opaque white, so every build of this map painted the
        # range out again immediately after drawing it and the wash was never
        # once on the page. That, and not the density of the marks, is why all
        # three palettes rendered identically (found V2.80).
        f'.rangemap .subjline{{fill:none;stroke:{pal["border"]};'
        f'stroke-width:1;stroke-linejoin:round}}'
        f'.rangemap .cell{{fill:{pal["range"]};stroke:{pal["range_edge"]};'
        f'stroke-width:.4;shape-rendering:crispEdges}}'
        # The banded squares carry no stroke. Adjacent cells share corner
        # coordinates exactly, so crispEdges tiles them without seams, and a
        # single edge colour across five fills reads as a grid drawn over the
        # data rather than as the data.
        + "".join(f'.rangemap .c{i}{{fill:{colour};stroke:none;'
                  f'shape-rendering:crispEdges}}'
                  for i, colour in enumerate(ramp))
        + f'.rangemap .spec{{fill:{pal["specimen"]};fill-opacity:.85;'
        f'stroke:none}}'
        f'.rangemap .obs{{fill:none;stroke:{pal["observation"]};'
        f'stroke-width:.9;stroke-opacity:.8}}'
        # The toggle, inside the SVG so it works in a standalone file as well
        # as in a page. A class on the <svg> hides one layer; with neither
        # class set both are shown, so a viewer with no JavaScript sees
        # everything rather than nothing.
        f'.rangemap.only-spec .layer-obs{{display:none}}'
        f'.rangemap.only-obs .layer-spec{{display:none}}'
        # The key sits over the neighbours' grey, not over the paper, so it
        # carries its own ground or the labels fight the coastline.
        f'.rangemap .keybg{{fill:{pal["paper"]};fill-opacity:.82;stroke:none}}'
        f'.rangemap .keyt{{font:600 8.5px/1 ui-sans-serif,system-ui,sans-serif;'
        f'fill:{pal["city"]};letter-spacing:.02em}}'
        f'.rangemap .keyl{{font:500 7.5px/1 ui-sans-serif,system-ui,sans-serif;'
        f'fill:{pal["city"]};text-anchor:middle}}'
        # `water_svg` and `cities_svg` are shared with the ecoregion maps and
        # emit `ecomap-*` classes, which are styled in html/site/site.css. This
        # SVG claims to be self-contained, and was not: opened on its own every
        # lake rendered black (SVG's default fill) and every river vanished
        # (a polyline with fill:none and no stroke). Scoping the rules under
        # `.rangemap` also outranks site.css, so the palette's water, river and
        # city entries are finally the ones on the page rather than decoration
        # in a table nothing read.
        f'.rangemap .ecomap-lake{{fill:{pal["water"]};stroke:{pal["coast"]};'
        f'stroke-width:.4}}'
        f'.rangemap .ecomap-river{{fill:none;stroke:{pal["river"]};'
        f'stroke-width:.9;stroke-linejoin:round;stroke-linecap:round}}'
        f'.rangemap .ecomap-city{{fill:{pal["city"]};stroke:{pal["paper"]};'
        f'stroke-width:.8}}'
        f'.rangemap .ecomap-place{{font:500 8.5px/1 ui-sans-serif,system-ui,'
        f'sans-serif;fill:{pal["city"]};paint-order:stroke;'
        f'stroke:{pal["paper"]};stroke-width:2.2px}}'
        f'.rangemap .ecomap-prov-label{{font:700 13px/1 ui-sans-serif,'
        f'system-ui,sans-serif;fill:{pal["border"]};letter-spacing:.14em;'
        f'opacity:.75;paint-order:stroke;stroke:{pal["paper"]};'
        f'stroke-width:3px}}</style>',
    ]
    # Neighbours in grey first, so the two provinces read as part of a
    # continent rather than a shape floating in space.
    parts += land_svg(project, css="ctx")
    parts += provinces_svg(project, subject_only=False, css="ctx")
    parts += provinces_svg(project, subject_only=True, css="subj")
    parts += water_svg(project)

    for row in rows:
        lat, lng = float(row[0]), float(row[1])
        css = (f"c{density_band(row[2])}" if counted and ramp else "cell")
        parts.append(f'<polygon class="{css}" '
                     f'points="{_cell_polygon(lat, lng, step, project)}"/>')

    # Borders again, over the range, so a province edge stays legible where the
    # wash sits against it. Cheap, and the alternative is a range that looks
    # like it dissolves the boundary it stops at. `subjline` and not `subj`:
    # see the note on that rule in the stylesheet above.
    parts += provinces_svg(project, subject_only=True, css="subjline")

    if marks != "none":
        # "few" keeps the marks whose cell the wash says least about -- the
        # single-record squares, which are the lightest band and the ones a
        # reader is most likely to take for nothing at all.
        thin = None
        if marks == "few" and counted:
            from src.species_range import cell_of
            singles = {(r[0], r[1]) for r in rows if r[2] <= 1}
            thin = lambda a, b: cell_of(a, b, step=step) in singles  # noqa: E731

        r = max(0.9, width * 0.0028)
        # Indexed rather than unpacked, so an `Occurrence` row drops in the way
        # it does everywhere else in this pipeline instead of raising on its
        # third field.
        #
        # Each kind goes in its own `<g>` so the page can hide one with a
        # single CSS rule (V2.80). Splitting the layers at render time and
        # emitting two whole maps would double the bytes to show the reader one
        # picture at a time.
        for css, points in (("obs", observations), ("spec", specimens)):
            drawn = []
            for point in points or ():
                lat, lng = float(point[0]), float(point[1])
                if thin is not None and not thin(lat, lng):
                    continue
                x, y = project(lng, lat)
                drawn.append(f'<circle class="{css}" cx="{x:.1f}" '
                             f'cy="{y:.1f}" r="{r:.1f}"/>')
            if drawn:
                parts.append(f'<g class="layer-{css}">{"".join(drawn)}</g>')

    if cities and width >= 420:
        parts += cities_svg(project)
    if show_key:
        parts += _legend_svg(pal, width, height)
    parts.append("</svg>")
    return "".join(parts)
