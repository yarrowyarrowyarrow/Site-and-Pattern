"""
ecoregion_palette.py — what each ecoregion looks like, and what the look means.

Design principle P5 (make the invisible visible) and P9 (ship confidence, never
false precision) — see docs/DESIGN_PHILOSOPHY.md.

Split out of :mod:`src.ecoregion_map` in V2.51, when the architecture guard
fired at 401 lines against 340. The seam is real rather than arithmetic: that
module is about *projecting geometry into an SVG*, and this one is about *what
a colour asserts*. The species page imports this and never touches the map.

**The one rule this file exists to hold.** Hue means region identity; lightness
means how well attested the record is. Before V2.51 the fill carried confidence
alone and every region was the same green, so the author asked for
*"the different ecoregions to be represented by different colours"*. Confidence
was the encoding standing in the way, and dropping it to make room would have
traded one honest map for a prettier dishonest one. Hue took identity, lightness
took confidence, and neither claim lost its channel.
"""

from __future__ import annotations

import html

#: One hue per ecoregion, after the convention every published natural-regions
#: map of the prairies uses: mountains violet, foothills olive, boreal
#: green-teal, parkland yellow-green, grassland gold warming to amber as it
#: gets wetter.
#:
#: **Lightness carries woody cover** (V2.66). The V2.51 set varied in hue alone
#: and three of its six colours were greens sitting within OKLab ΔE 8 of each
#: other — indistinguishable under deuteranopia, and only barely distinguishable
#: with full colour vision. Spreading them across OKLCH lightness 0.47 to 0.90
#: fixes that and says something true while doing it: the dark end is closed
#: forest, the middle is savanna, the pale end is open grassland. A reader who
#: cannot separate the hues still reads the north-south gradient.
REGION_COLOUR: dict = {
    "subalpine_montane":  "#7c5ea6",   # violet, the Rockies
    "fescue_foothills":   "#8a8b3c",   # olive, the fescue foothills
    "boreal_mixedwood":   "#2f6b52",   # dark green, the boreal
    "aspen_parkland":     "#a9c26a",   # yellow-green, the parkland arc
    "moist_mixedgrass":   "#d99a4e",   # amber, the moist grassland
    "mixedgrass_prairie": "#eeddab",   # pale gold, the dry grassland
}
_FALLBACK_COLOUR = "#7f8f6a"

#: Regions drawn with a diagonal hatch **as well as** their colour.
#:
#: Hue and lightness cannot separate every pair that shares a border. Aspen
#: Parkland is yellow-green and the Moist Mixed Grassland it borders for eight
#: hundred kilometres is amber; green against orange is the red-green confusion
#: axis, and under deuteranopia the two collapse to ΔE 4.3 no matter how the
#: lightness is arranged. Every attempt to fix it with colour alone either broke
#: the convention (a cyan boreal, a magenta Rockies) or pushed the parkland into
#: the foothills olive instead — the conflict moved, it did not go away.
#:
#: So the pair that colour cannot carry gets a second channel. The rule, which
#: ``tests/test_ecoregion.py`` enforces against whatever polygons are shipped:
#: **every pair of ecoregions that shares a border must reach CVD ΔE 8, or one
#: of the two must be hatched.** That generalises — when the ELC polygons land
#: with their dozen-odd regions, the test says which ones need a hatch rather
#: than leaving it to somebody's eye.
HATCHED: frozenset = frozenset({"moist_mixedgrass"})

#: How far toward white each confidence band is mixed. A region derived from
#: three records must not look like one derived from three hundred; it must
#: still be recognisably its own colour, which is why ``low`` stops well short
#: of fading out.
#:
#: The mix is gentler than it was before V2.66 and opacity does more of the
#: work, because the palette now runs up to OKLCH lightness 0.90 at the dry
#: grassland. Mixing *that* 55% toward white left a fill one step off the paper,
#: which reads as "not recorded" — the opposite of what it means.
#: ``tests/test_ecoregion.py`` pins the floor: every band of every region stays
#: a measurable distance from ``ABSENT_FILL``.
_BAND_MIX = {"high": 0.0, "medium": 0.22, "low": 0.30, "": 0.26}
_BAND_OPACITY = {"high": 0.95, "medium": 0.84, "low": 0.68, "": 0.72}

#: Not recorded here. Deliberately a near-neutral grey, so "coloured means
#: recorded" reads without hovering.
#:
#: Re-stepped cooler and darker in V2.66. The old ``#cfd0ca`` was a light warm
#: grey chosen against a palette whose palest member was a mid gold; once the
#: dry grassland moved to a pale gold at OKLCH lightness 0.90, the two came
#: within OKLab deltaE 7.4 of each other and a region with three occurrence
#: records looked like a region with none. Both channels now separate them: this
#: is three and a half times less chromatic than the least chromatic fill, and
#: ``tests/test_ecoregion.py`` holds both the distance and the chroma ratio.
ABSENT_FILL = ("#babac4", 0.5)

#: Painter's order for the reference map: broadest first, so the narrow western
#: strips land on top of the boreal wedge instead of under it. Only consulted
#: when every region is drawn in colour; a species map keeps its own order,
#: which puts the regions the plant is recorded in last.
DRAW_ORDER = {"boreal_mixedwood": 0, "aspen_parkland": 1,
              "moist_mixedgrass": 2, "mixedgrass_prairie": 3,
              "fescue_foothills": 4, "subalpine_montane": 5}


def mix_to_white(hexcolour: str, amount: float) -> str:
    """``hexcolour`` lightened toward white by ``amount`` (0..1)."""
    value = (hexcolour or "").lstrip("#")
    if len(value) != 6:
        return hexcolour
    try:
        parts = [int(value[i:i + 2], 16) for i in (0, 2, 4)]
    except ValueError:
        return hexcolour
    return "#" + "".join(
        f"{round(c + (255 - c) * max(0.0, min(1.0, amount))):02x}"
        for c in parts)


def region_fill(key: str, band: str = "high") -> tuple:
    """``(fill, opacity)`` for one region at one confidence band."""
    base = REGION_COLOUR.get(key, _FALLBACK_COLOUR)
    band = band if band in _BAND_MIX else ""
    return mix_to_white(base, _BAND_MIX[band]), _BAND_OPACITY[band]


#: Geometry of the hatch, in user units. Kept here beside the colours because
#: the hatch is part of what a region *looks like*, not part of projecting it.
HATCH_ID = "ecomap-hatch"
HATCH_SIZE = 5


def hatch_defs() -> str:
    """The ``<defs>`` block defining one diagonal-hatch pattern per hatched
    region, or ``""`` when nothing is hatched.

    One pattern per region rather than one shared pattern: the strokes are
    tinted from the region's own colour, so a hatch never introduces a colour
    the legend does not account for.
    """
    if not HATCHED:
        return ""
    patterns = []
    for key in sorted(HATCHED):
        stroke = mix_to_black(REGION_COLOUR.get(key, _FALLBACK_COLOUR), 0.35)
        patterns.append(
            f'<pattern id="{HATCH_ID}-{key}" width="{HATCH_SIZE}" '
            f'height="{HATCH_SIZE}" patternUnits="userSpaceOnUse" '
            f'patternTransform="rotate(45)">'
            f'<line x1="0" y1="0" x2="0" y2="{HATCH_SIZE}" '
            f'stroke="{stroke}" stroke-width="1.1" stroke-opacity="0.55"/>'
            f"</pattern>")
    return "<defs>" + "".join(patterns) + "</defs>"


def hatch_url(key: str) -> str:
    """``url(#…)`` for a hatched region, or ``""`` for every other region."""
    return f"url(#{HATCH_ID}-{key})" if key in HATCHED else ""


def mix_to_black(hexcolour: str, amount: float) -> str:
    """``hexcolour`` darkened toward black by ``amount`` (0..1)."""
    value = (hexcolour or "").lstrip("#")
    if len(value) != 6:
        return hexcolour
    try:
        parts = [int(value[i:i + 2], 16) for i in (0, 2, 4)]
    except ValueError:
        return hexcolour
    keep = 1.0 - max(0.0, min(1.0, amount))
    return "#" + "".join(f"{round(c * keep):02x}" for c in parts)


def legend_html(link_for=None, *, active: str = "") -> str:
    """The colour key, as HTML rather than SVG.

    A key drawn inside the SVG has to survive the map being scaled down to a
    phone-width column, and it loses. As markup it wraps, and each swatch can
    be a link into that region's own page.
    """
    from src.ecoregion import ecoregion_display                # noqa: PLC0415
    from src.ecoregion_map import region_geometry              # noqa: PLC0415

    items = []
    for key in sorted(region_geometry(), key=lambda k: DRAW_ORDER.get(k, 50)):
        fill, _ = region_fill(key, "high")
        name, where = ecoregion_display(key)
        # The swatch is generated from the same REGION_COLOUR entry and the same
        # HATCHED set as the polygon, so a legend that disagrees with the map is
        # not a thing that can happen by editing one of them. The previous
        # rebuild attempt shipped a legend with two of its colours swapped.
        swatch = fill
        if key in HATCHED:
            stroke = mix_to_black(REGION_COLOUR.get(key, _FALLBACK_COLOUR), 0.35)
            swatch = (f"repeating-linear-gradient(45deg,{fill},{fill} 2px,"
                      f"{stroke} 2px,{stroke} 3px)")
        label = (f'<span class="ecokey-sw" style="background:{swatch}"></span>'
                 f'<span class="ecokey-name">{html.escape(name)}</span>'
                 + (f'<span class="ecokey-where">{html.escape(where)}</span>'
                    if where else ""))
        href = link_for(key) if link_for else ""
        on = " on" if key == active else ""
        items.append(
            f'<a class="ecokey-item{on}" href="{html.escape(href)}">{label}</a>'
            if href else f'<span class="ecokey-item{on}">{label}</span>')
    return f'<div class="ecokey">{"".join(items)}</div>' if items else ""
