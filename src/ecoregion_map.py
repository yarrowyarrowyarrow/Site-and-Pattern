"""
ecoregion_map.py — the ecoregions, drawn.

Design principle P5 — see docs/DESIGN_PHILOSOPHY.md.

The catalogue has known since V2.38 which ecoregions a species has actually been
recorded in, with an occurrence count and a confidence band per region
(``plant_ecoregions``, from GBIF). Until now the only way to read that was as a
list of region names, which asks the reader to hold a map of Alberta and
Saskatchewan in their head. A range is a *shape*; drawing it costs one SVG.

**These outlines are surveyed, since V2.67.** They were ten five-vertex
rectangles, then six shapes traced against the geography by hand
(``scripts/draw_ecoregions.py``, now dead weight kept only for its history),
and they are now the National Ecological Framework for Canada v2.2 clipped to
Alberta and Saskatchewan — twenty-four ecoregions in six ecozones, built by
``tools/ecoregions/`` and adopted with no change to this file, because since
V2.38 the polygon file *is* the vocabulary.

An outline drawn without a caption is still a claim about a boundary, so
``CAVEAT`` stays (P9) — but what it has to say changed with the data, and
saying the old thing about the new file is its own failure. See the note on
the constant.

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
           "map_svg", "projector", "region_fill", "region_geometry"]

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


def projector(width: float, height: float):
    """``(lon, lat) -> (x, y)`` for a map drawn at this size.

    Public since V2.75 so an overlay can be placed in the *same* projection the
    shading uses. Anything drawing on top of :func:`map_svg` — occurrence
    points, a site pin — must go through this rather than reimplementing the
    conic, because a second projector that is 2% off produces dots that sit
    just outside their own region and look like a data error.
    """
    return _projector(width, height)


def region_geometry(level: str = "", within: str = "") -> dict:
    """``{key: [ring, ...]}`` merged across the file's duplicate entries.

    A region may be drawn as more than one polygon, and a caller asking to draw
    it means all of them.

    ``level`` picks which of the three the keys come from — ecozone, ecoregion
    (the default) or Alberta natural subregion. The polygon file has carried
    all three on every feature since adoption; nothing had ever grouped by
    anything but the ecoregion, so two thirds of the classification were
    undrawable.

    ``within`` restricts to one branch: ``region_geometry(SUBREGION,
    within="mixed_grassland")`` is the three subregions of that ecoregion and
    nothing else. That is what makes a drill-down possible without slicing
    geometry — the pieces are already cut this finely on disk.
    """
    from src.ecoregion_tree import ECOZONE, SUBREGION        # noqa: PLC0415
    from src.ecoregion_tree import lineage_keys, subregion_key, zone_key

    branch = set(lineage_keys(within)) if within else set()
    out: dict = {}
    for feature in _load():
        props = feature.get("properties") or {}
        region = (props.get("key") or "").strip()
        if not region:
            continue
        if level == ECOZONE:
            key = zone_key((props.get("ecozone") or "").strip())
        elif level == SUBREGION:
            key = subregion_key((props.get("ab_subregion") or "").strip())
        else:
            key = region
        # Membership is tested on the GROUPING key alone. Testing the ecoregion
        # too looked like belt and braces and quietly widened every subregion
        # focus map to thirteen subregions: a piece of Alpine belongs to
        # Eastern Continental Ranges, which is on Montane's lineage, so asking
        # for Montane drew every subregion that shares any parent with it.
        # `lineage_keys` already walks both directions, so the key test is
        # sufficient at every level, and an unlabelled sliver is dropped by the
        # emptiness check rather than needing a second rule.
        if not key or (branch and key not in branch):
            continue
        out.setdefault(key, []).extend(_rings(feature.get("geometry") or {}))
    return out



def _ring_points(ring, project, min_px: float = 0.0) -> str:
    """One projected ring as an SVG ``points`` string, optionally decimated.

    ``min_px`` drops a vertex that lands within that distance of the last one
    kept. The polygons are simplified to about 900 m for display, which is
    right for the 900 px map on a region page and roughly three times finer
    than a pixel on the 420 px map a species page carries: 846 KB of vertices
    per page, repeated on 430 pages, that nobody can see.

    A rendering decision, not a data one -- the same argument as
    `occurrence_points.MARK_DEG`. The first and last vertices are always kept
    so a ring still closes, and `min_px=0` (the default) changes nothing, so
    every existing map is byte-identical.
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


def map_svg(highlight: Optional[dict] = None, *,
            width: int = 460, height: int = 300,
            title: str = "", labels: bool = True,
            cities: Optional[bool] = None,
            link_for=None, reference: bool = False,
            level: str = "", within: str = "", numbered: bool = False,
            overlay: str = "", chrome: str = "",
            min_px: float = 0.0, present_only: bool = False) -> str:
    """The ecoregion map as inline SVG.

    ``level`` and ``within`` draw one level of the vocabulary, optionally
    restricted to one branch — see :func:`region_geometry`. Together they make
    the map a drill-down instead of a single flat picture of twenty-four
    shapes: the overview colours six ecozones, an ecozone's page colours the
    ecoregions inside it, and an ecoregion's page colours its Alberta natural
    subregions.

    When ``within`` is set the rest of the layer is still drawn, in the
    not-recorded grey, because a branch floating on blank provinces loses the
    one thing a locator map is for. You cannot tell where Mixed Grassland is
    from a picture of Mixed Grassland.

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

    ``overlay`` is raw SVG emitted above every other layer, positioned with
    :func:`projector` at the same ``width``/``height``, and **clipped to the
    subject provinces like everything else thematic**. It is the seam for
    drawing *records* rather than *regions* — see
    ``scripts/plot_occurrences.py``. Deliberately a string this module does not
    interpret: the alternative was a point-plotting API here, and where the
    records are is not this file's concern.

    ``chrome`` is emitted last and **not** clipped: a legend, a scale bar, a
    title block. The distinction is not fussiness. Anything placed by the
    projector is a claim about ground and must stop at the border; a key sits
    in the corner of the *frame*, which on this projection is over British
    Columbia, so putting one through ``overlay`` deletes it.
    """
    highlight = highlight or {}
    regions = region_geometry(level, within)
    if not regions:
        return ""
    # The branch sits on the rest of the layer, drawn flat and grey.
    #
    # Always at the ECOREGION level, whatever level is in focus. Drawing the
    # context at the focus level looked right for ecozones and silently deleted
    # Saskatchewan from every subregion map: the subregion attribute only
    # exists in Alberta, so grouping the backdrop that way drops every piece
    # that has no subregion — which is the entire other province. The ecoregion
    # layer is the one level that covers the whole subject area.
    branch = set()
    if within:
        from src.ecoregion_tree import lineage_keys          # noqa: PLC0415
        branch = set(lineage_keys(within))
    context = ({k: v for k, v in region_geometry().items() if k not in branch}
               if within else {})
    # The focused region itself, drawn UNDER its children.
    #
    # Without this a subregion map has a hole in it exactly on the Alberta /
    # Saskatchewan border, and the hole is a lie. Alberta publishes a natural
    # subregion layer and Saskatchewan does not, so on a page for an ecoregion
    # that crosses the border — Mid-Boreal Uplands, Boreal Transition, Athabasca
    # Plain — the Alberta half is covered by subregion polygons and the
    # Saskatchewan half is covered by nothing: it is inside the branch, so the
    # grey context skips it, and it has no subregion, so the focus layer skips
    # it too. It fell through to the bare province wash and read as *this
    # ecoregion stops at the provincial boundary*, which is false about every
    # one of them.
    #
    # Drawing the parent first says the true thing: the whole region, with the
    # subregions that exist mapped on top of it and the rest plainly unmapped.
    underlay = {}
    if within and within in region_geometry():
        underlay = {within: region_geometry()[within]}
    if cities is None:
        cities = width >= 420
    project = _projector(width, height)
    order = sorted(regions.items(),
                   key=lambda kv: (DRAW_ORDER.get(kv[0], 50),) if reference
                   else (kv[0] in highlight,))
    if present_only:
        # Draw only the regions this species is recorded from, over the bare
        # province outline. On a species page the other twenty-one shapes are
        # 846 KB of polygons per page saying "not here" -- which the caption
        # already says in words, and which the reader cannot act on. Kept as an
        # option rather than the default because a region page's map is ABOUT
        # the layer and needs all of it.
        order = [(k, v) for k, v in order if k in highlight]

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
    for _key, rings in sorted(context.items()):
        for ring in rings:
            points = _ring_points(ring, project, min_px)
            parts.append(f'<polygon class="ecomap-region ecomap-outside" '
                         f'points="{points}" fill="{ABSENT_FILL[0]}" '
                         f'fill-opacity="{ABSENT_FILL[1]}"/>')
    for parent_key, rings in underlay.items():
        parent_fill, _op = region_fill(parent_key, "high")
        parent_name = ecoregion_display(parent_key)[0]
        for ring in rings:
            points = _ring_points(ring, project, min_px)
            parts.append(
                f'<polygon class="ecomap-region ecomap-parent" '
                f'points="{points}" fill="{parent_fill}" fill-opacity="0.45">'
                f'<title>{html.escape(parent_name)}</title></polygon>')
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
            points = _ring_points(ring, project, min_px)
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
            # A label over ground this map no longer shades is a name with
            # nothing under it. When only the recorded regions are drawn, only
            # those get named.
            if present_only and key not in highlight:
                continue
            ring = max(rings, key=len)
            lon, lat, angle = _label_point(key, ring)
            cx, cy = project(lon, lat)
            name, _ = ecoregion_display(key)
            strong = reference or key in highlight
            spin = (f' transform="rotate({angle} {cx:.1f} {cy:.1f})"'
                    if angle else "")
            # The name, whole. V2.68 deleted a table of six abbreviations
            # written when this map had six regions: four named regions the
            # survey retired, and the two still reachable were shortening names
            # into DIFFERENT names — the public map labelled Aspen Parkland
            # "Parkland" and Moist Mixed Grassland "Moist Mixed", while drawing
            # "Northern Continental Divide" in full three regions away.
            #
            # If a label ever has to be abbreviated to fit, drop it instead:
            # the legend carries every name in full, keyed by colour, so an
            # unlabelled region loses nothing and a truncated one loses its
            # name.
            parts.append(
                f'<text x="{cx:.1f}" y="{cy:.1f}" text-anchor="middle"{spin} '
                f'class="ecomap-label{" on" if strong else ""}">'
                f'{html.escape(name)}</text>')

    if numbered:
        # A numbered disc per region, keyed to the legend.
        #
        # **Because the fill cannot carry this and it was measured.** Hue is
        # the ecozone and lightness the ecoregion inside it, which works for
        # two or three siblings and collapses at ten: Boreal Transition and
        # Clear Hills Upland came out ΔE 0.3 apart, the same colour. A search
        # over lightness, chroma and hue-rotation together found the best
        # sibling separation that still clears the cross-ecozone colour-vision
        # floor is ΔE 1.7 — still invisible. Ten regions cannot be told apart
        # inside one hue family, full stop.
        #
        # So identity moves off the fill rather than the family being broken
        # up, which is the trade the author asked for: *"I dont mean to change
        # this too drastically as I really like the appearance however it must
        # be usefully distinguishable."* Numbers are the atlas answer to
        # exactly this and cost the palette nothing.
        for index, key in enumerate(numbered_order(level, within), 1):
            rings = regions.get(key) or []
            if not rings:
                continue
            lon, lat, _angle = _label_point(key, max(rings, key=len))
            cx, cy = project(lon, lat)
            parts.append(
                f'<g class="ecomap-num"><circle cx="{cx:.1f}" cy="{cy:.1f}" '
                f'r="8.5"/><text x="{cx:.1f}" y="{cy:.1f}" '
                f'text-anchor="middle" dominant-baseline="central">'
                f'{index}</text></g>')

    if overlay:
        # Inside the subject clip, like everything else thematic. The overlay
        # used to sit outside it, so `plot_occurrences` drew records from
        # British Columbia and Montana over ground this layer does not speak
        # for (F142, V2.78). The caller drops those records itself and says how
        # many; this is the backstop for the remaining case the caller cannot
        # settle -- a dot a few hundred metres over a simplified border, which
        # should be trimmed by the picture rather than deleted from the data.
        parts.append(f'<g clip-path="url(#{SUBJECT_CLIP_ID})">{overlay}</g>')
    if chrome:
        parts.append(chrome)
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
#: **Empty since V2.67**, and kept as a mechanism rather than deleted.
#:
#: Six entries lived here to compensate for hand-drawn shapes whose centroids
#: landed badly. The surveyed layer has twenty-four regions, and hand-placing
#: twenty-four anchors is maintenance that goes stale the first time a polygon
#: moves. ``_interior_point`` below now finds a point that is actually inside
#: the region instead of trusting a centroid — which a crescent's centroid is
#: not — so nothing needs placing by hand. An override stays available for a
#: computed answer that is correct but ugly.
_LABEL_POINT: dict = {}


def _clearance(point: tuple, xs: list, ys: list) -> float:
    """Distance from ``point`` to the nearest vertex — a cheap stand-in for
    distance to the edge, which is all a label placement needs."""
    lon, lat = point
    return min((lon - x) ** 2 + (lat - y) ** 2
               for x, y in zip(xs, ys)) ** 0.5


def _interior_point(ring: list) -> tuple:
    """A point inside ``ring``, as far from its edge as a coarse scan finds.

    A centroid is not good enough. The parkland is a crescent and the Peace
    Lowland wraps a river; both can put their centroid outside themselves, and
    the first coloured draft of this map printed "Montane" in British Columbia
    for exactly that reason. This samples a grid over the bounding box, keeps
    what falls inside, and returns the sample furthest from any vertex — an
    approximation of the pole of inaccessibility, which is where an atlas puts
    a label.
    """
    from src.geometry import point_in_ring                       # noqa: PLC0415

    xs = [float(c[0]) for c in ring]
    ys = [float(c[1]) for c in ring]
    centre = (sum(xs) / len(xs), sum(ys) / len(ys))
    best, best_gap = None, -1.0
    if point_in_ring(centre[1], centre[0], ring):
        best, best_gap = centre, _clearance(centre, xs, ys)
    steps = 12
    for i in range(1, steps):
        for j in range(1, steps):
            lon = min(xs) + (max(xs) - min(xs)) * i / steps
            lat = min(ys) + (max(ys) - min(ys)) * j / steps
            if not point_in_ring(lat, lon, ring):
                continue
            gap = _clearance((lon, lat), xs, ys)
            if gap > best_gap:
                best, best_gap = (lon, lat), gap
    return best or centre


def numbered_order(level: str = "", within: str = "") -> list:
    """The keys of one map, in the order their numbers run.

    **One function, called by the map and the legend**, for the reason
    ``hub_slug`` exists: two lists that have to agree, kept in step by hand,
    do not stay in step. A key numbered 4 on the map and 5 in the legend is
    worse than no numbers, because the reader has no way to notice.

    Alphabetical by display name, which is the order the legend already read
    in and the order somebody scanning for a name expects.
    """
    from src.ecoregion import ecoregion_display              # noqa: PLC0415

    return sorted(region_geometry(level, within),
                  key=lambda k: ecoregion_display(k)[0])


def _label_point(key: str, ring: list) -> tuple:
    """``(lon, lat, angle)`` for a region's printed name."""
    if key in _LABEL_POINT:
        return _LABEL_POINT[key]
    lon, lat = _interior_point(ring)
    return lon, lat, 0


#: The one sentence that has to travel with every drawing of this file.
#:
#: V2.68: this said "Approximate extents, not surveyed boundaries ... the
#: outlines are a diagram" for as long as the outlines *were* a diagram. V2.67
#: replaced them with the surveyed layer and did not come back here, so 432
#: species pages and the map page spent an increment disclaiming data that had
#: become better than the disclaimer. Understating a source is not the safe
#: direction of error it looks like: a reader who is told the outline is a
#: sketch has no reason to trust it where it matters, at the edge.
#:
#: What is still worth saying is the simplification, because that is the one
#: way this drawing differs from the survey it comes from.
CAVEAT = ("Boundaries digitised from the National Ecological Framework for "
          "Canada v2.2 (Ecological Stratification Working Group 1995), "
          "simplified to about 900 m for display: an outline is accurate to "
          "roughly a kilometre, not to the metre.")
