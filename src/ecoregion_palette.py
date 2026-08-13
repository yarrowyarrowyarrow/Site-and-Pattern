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
REGION_COLOUR: dict = {
    "subalpine_montane":  "#8b79b8",   # violet, the Rockies
    "fescue_foothills":   "#6f8f3f",   # olive, the fescue foothills
    "boreal_mixedwood":   "#3f8f75",   # green-teal, the boreal
    "aspen_parkland":     "#b3cc6b",   # yellow-green, the parkland arc
    "moist_mixedgrass":   "#d9a94e",   # amber, the moist grassland
    "mixedgrass_prairie": "#e3c96a",   # gold, the dry grassland
}
_FALLBACK_COLOUR = "#7f8f6a"

#: How far toward white each confidence band is mixed. A region derived from
#: three records must not look like one derived from three hundred; it must
#: still be recognisably its own colour, which is why ``low`` stops at 0.55
#: rather than fading out.
_BAND_MIX = {"high": 0.0, "medium": 0.3, "low": 0.55, "": 0.42}
_BAND_OPACITY = {"high": 0.95, "medium": 0.88, "low": 0.8, "": 0.8}

#: Not recorded here. Deliberately a neutral grey with almost no chroma, so
#: "coloured means recorded" reads without hovering. The palest fill in the
#: palette is the low-confidence dry grassland at ``#f2e7bc``, which is
#: unmistakably yellow beside this.
ABSENT_FILL = ("#cfd0ca", 0.5)

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
        label = (f'<span class="ecokey-sw" style="background:{fill}"></span>'
                 f'<span class="ecokey-name">{html.escape(name)}</span>'
                 + (f'<span class="ecokey-where">{html.escape(where)}</span>'
                    if where else ""))
        href = link_for(key) if link_for else ""
        on = " on" if key == active else ""
        items.append(
            f'<a class="ecokey-item{on}" href="{html.escape(href)}">{label}</a>'
            if href else f'<span class="ecokey-item{on}">{label}</span>')
    return f'<div class="ecokey">{"".join(items)}</div>' if items else ""
