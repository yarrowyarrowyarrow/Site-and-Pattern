"""
src/scene_site.py — what the ground is, in the 3D scene (V3.45, F262).

Design principle P2 (the best designs disappear into their context), P5
(perception is constructed) and P9 (uncertainty is a feature: never false
precision) — see docs/DESIGN_PHILOSOPHY.md.

The V3.43 review, findings 2 and 3: nothing drawn on the ground reached the 3D
preview. A bed, mulch, a lawn, a path, a patio and a pond were all one meadow
texture running to the horizon, a hedge or a fence was not in the scene at all,
there was no street though the app has known the street side since V3.29, and a
house was a tan box. The plants had years of care and the yard round them none.

This module decides, once, what the viewer then only draws (the V2.88 lesson),
as additive fields of the scene (:func:`src.scene_contract.build_scene`):

* ``ground``: ``"pale"`` for a yard, ``"meadow"`` for a walk through a wild
  community (:data:`GROUND_PALE`, :data:`GROUND_MEADOW`).
* ``surfaces``: the outline's inside as lawn, then every drawn area by kind.
* ``lines``: hedges, fences, living fences and windbreaks.
* ``street``: a sidewalk and a road, only where the street side is known.
* a ``roof`` hint on each building.

**The owner's D3** (13 November 2026): where nothing is recorded, lawn inside
the outline and pale neutral ground outside it; houses as plain massing, no
invented windows or colours.

**Nothing here is measured that the design does not hold.** A line's height,
a road's width, a sidewalk's place and a roof's pitch are not recorded
anywhere, so each is one stated estimate below, drawn pale and plain. Where
even the *side* of the street is only assumed, no street is drawn.

Qt-free, DB-free, network-free: plain arithmetic in scene metres (+x east,
+y north).
"""

from __future__ import annotations

import math
from typing import Optional

GROUND_PALE = "pale"
GROUND_MEADOW = "meadow"

# ── surfaces ────────────────────────────────────────────────────────────────

#: A drawn area's ``shape_type`` → the kind the viewer has a look for
#: (``html/scene3d/02c-site.js``: ``SURFACE_LOOK``, held equal by a test).
#: One vocabulary with ``yard_overview.BED_SHAPES`` / ``NOT_PLANTED``,
#: ``shape_tool.AREA_PRESETS`` and ``lawn_zones.ZONE_TYPES``: a test fails on a
#: type any of them offers that is not here.
SURFACE_KINDS = {
    "Garden Bed": "bed",
    "Mulch Area": "mulch",
    "Lawn Area": "lawn",
    "Lawn — to convert": "lawn",          # it is lawn today
    "Pathway": "path",
    "Patio / Deck": "patio",
    "Water Feature": "water",
    "Restoration — Year 1": "seeded",     # prepared ground, newly seeded
    "Restoration — Year 3": "young_meadow",
    "Established native": "meadow",
    "Existing remnant": "meadow",
    "Custom": "custom",
}

#: What a type the table does not know is drawn as: the person's own colour.
CUSTOM = "custom"

#: Every kind a surface can have. ``lawn`` is also the outline's inside (D3).
KINDS = tuple(sorted(set(SURFACE_KINDS.values())))

# ── lines ───────────────────────────────────────────────────────────────────

#: ``style`` → metres tall. **Estimates by form**: nothing in a design records
#: how tall a hedge or a fence is (the tool asks its width, spacing and a
#: species in free text). A rail fence a person can see over; a clipped hedge;
#: a taller living fence; a windbreak of shrubs.
LINE_HEIGHT_M = {"fence": 1.2, "hedge": 1.2, "living_fence": 1.6,
                 "windbreak": 3.0}
#: The width a line is drawn when the design holds none.
LINE_WIDTH_M = 1.5
#: A fence is boards, not a planting: it is drawn this thick whatever the
#: width the line carries (which the map tool fills in for every line).
FENCE_WIDTH_M = 0.1

# ── the street ──────────────────────────────────────────────────────────────

#: Where the sidewalk's middle is, out from the yard's street edge: where
#: :func:`src.scene_views.street_view` stands the neighbour.
SIDEWALK_OUT_M = 4.0
SIDEWALK_WIDTH_M = 1.5
#: A road drawn from the person's answer alone (no road line is recorded):
#: its near edge and its width. A residential street, drawn pale.
ROAD_NEAR_M = 6.0
ROAD_WIDTH_M = 8.0
#: How far a schematic sidewalk and road run past the frontage's ends.
STREET_RUN_M = 150.0
#: A recorded road line is drawn this wide, by OpenStreetMap's class.
ROAD_CLASS_WIDTH_M = {
    "motorway": 14.0, "trunk": 14.0, "primary": 12.0, "secondary": 10.0,
    "tertiary": 9.0, "unclassified": 8.0, "residential": 8.0,
    "living_street": 6.0, "service": 4.0,
}
#: Road lines further than this from the scene's origin are not drawn.
ROAD_REACH_M = 250.0

# ── roofs ───────────────────────────────────────────────────────────────────

#: A gable goes on a clean four-corner footprint of house size only.
GABLE_MAX_SHORT_SIDE_M = 14.0
GABLE_MIN_SIDE_M = 3.0
_SQUARE_WITHIN_DEG = 12.0
#: Rise over half the short side: about a 5-in-12 roof. Nothing records a
#: pitch; this is a common one, and the ridge stays at the recorded height.
GABLE_PITCH = 0.42
#: The walls under a gable are never lower than this, nor the gable more than
#: this share of the building's height.
GABLE_MIN_WALL_M = 2.2
GABLE_MAX_SHARE = 0.45


def is_walk(project: dict) -> bool:
    """A walk through a wild community, not a yard (it records the version of
    the community it was laid out from)."""
    return "reference_version" in ((project or {}).get("properties") or {})


def ground_kind(project: dict) -> str:
    return GROUND_MEADOW if is_walk(project) else GROUND_PALE


def surface_kind(shape_type: str) -> str:
    return SURFACE_KINDS.get(shape_type or "", CUSTOM)


def _open_ring(coords, proj) -> list:
    ring = []
    for pt in coords or []:
        x, y = proj.to_xy(pt[1], pt[0])
        ring.append([round(x, 2), round(y, 2)])
    if len(ring) > 1 and ring[0] == ring[-1]:
        ring = ring[:-1]
    return ring


def surfaces(project: dict, proj, boundary_xy: Optional[list]) -> list:
    """The ground's surfaces, bottom first: ``[{kind, ring, color?, label?,
    base?}]``.

    The outline's inside comes first, as lawn (``base``: where nothing else is
    drawn, D3). Then every drawn area that lies flat (a shape with a height is
    a building or a tree's crown and is in ``buildings``), in the order it was
    drawn. A shape the table does not know keeps the person's colour."""
    out = []
    if boundary_xy and len(boundary_xy) >= 3 and not is_walk(project):
        out.append({"kind": "lawn", "ring": [list(p) for p in boundary_xy],
                    "base": True})
    for f in (project or {}).get("features", []) or []:
        props = f.get("properties") or {}
        geom = f.get("geometry") or {}
        if (props.get("element_type") != "custom_shape"
                or geom.get("type") != "Polygon"
                or float(props.get("height_m") or 0.0) > 0.0):
            continue
        ring = _open_ring((geom.get("coordinates") or [[]])[0], proj)
        if len(ring) < 3:
            continue
        kind = surface_kind(props.get("shape_type"))
        row = {"kind": kind, "ring": ring}
        if kind == CUSTOM:
            row["color"] = props.get("fill_color") or "#9e9e9e"
        if props.get("label"):
            row["label"] = str(props["label"])
        out.append(row)
    return out


def lines(project: dict, proj) -> list:
    """Hedges, fences, living fences and windbreaks: ``[{kind, points,
    width_m, height_m}]``. The height is :data:`LINE_HEIGHT_M`'s estimate."""
    out = []
    for f in (project or {}).get("features", []) or []:
        props = f.get("properties") or {}
        geom = f.get("geometry") or {}
        if (props.get("element_type") != "hedgerow"
                or geom.get("type") != "LineString"):
            continue
        pts = []
        for pt in geom.get("coordinates") or []:
            x, y = proj.to_xy(pt[1], pt[0])
            pts.append([round(x, 2), round(y, 2)])
        if len(pts) < 2:
            continue
        kind = props.get("style") if props.get("style") in LINE_HEIGHT_M \
            else "hedge"
        width = FENCE_WIDTH_M if kind == "fence" else float(
            props.get("width_m") or LINE_WIDTH_M)
        out.append({"kind": kind, "points": pts,
                    "width_m": round(width, 2),
                    "height_m": LINE_HEIGHT_M[kind]})
    return out


# ── the street ──────────────────────────────────────────────────────────────

def _strip(cx, cy, d, n, t0, t1, s0, s1) -> list:
    """A rectangle in the frontage's own axes (``t`` toward the street,
    ``s`` along it), as a ring in scene metres."""
    return [[round(cx + d[0] * t + n[0] * s, 2),
             round(cy + d[1] * t + n[1] * s, 2)]
            for t, s in ((t0, s0), (t0, s1), (t1, s1), (t1, s0))]


def street(project: dict, proj, boundary_xy: Optional[list]) -> Optional[dict]:
    """The street beside the yard, or ``None``.

    ``None`` without an outline (nothing says where the yard ends) and where
    the street's side is only assumed: a road in the picture would state as
    fact what the Overview says in words is "taken to be the south side".

    Told by the person (Plan My Yard's front-yard question): a sidewalk where
    the neighbour of :func:`src.scene_views.street_view` stands, and a road
    beyond it, both schematic. Measured from the road lines kept with the
    design: those lines, as wide as their class, and the sidewalk only where
    it lies clear of them.
    """
    if not boundary_xy or len(boundary_xy) < 3 or is_walk(project):
        return None
    from src.frontage import frontage_for_project, roads_in_project
    try:
        front = frontage_for_project(project)
    except Exception:                                      # noqa: BLE001
        return None
    if not front.known:
        return None

    ring = [(float(p[0]), float(p[1])) for p in boundary_xy]
    cx = sum(p[0] for p in ring) / len(ring)
    cy = sum(p[1] for p in ring) / len(ring)
    b = math.radians(front.bearing)
    d = (math.sin(b), math.cos(b))            # toward the street
    n = (math.cos(b), -math.sin(b))           # along the frontage
    ts = [((x - cx) * d[0] + (y - cy) * d[1],
           (x - cx) * n[0] + (y - cy) * n[1]) for x, y in ring]
    t_edge = max(t for t, _s in ts)
    s_lo = min(s for _t, s in ts) - STREET_RUN_M
    s_hi = max(s for _t, s in ts) + STREET_RUN_M

    out = {"bearing": round(float(front.bearing) % 360.0, 1),
           "how": "told" if front.told else "measured"}

    roads = []
    for road in roads_in_project(project) if front.measured else []:
        pts = []
        for pt in road.get("line") or []:
            x, y = proj.to_xy(pt[1], pt[0])
            if math.hypot(x, y) <= ROAD_REACH_M:
                pts.append([round(x, 2), round(y, 2)])
            elif len(pts) >= 2:
                break
            else:
                pts = []
        if len(pts) >= 2:
            roads.append({"points": pts,
                          "width_m": ROAD_CLASS_WIDTH_M.get(
                              road.get("highway") or "", 8.0),
                          "name": road.get("name") or ""})
    if roads:
        out["roads"] = roads
        # How near the yard's street edge the nearest road's own edge comes.
        edges = [((x - cx) * d[0] + (y - cy) * d[1]) - r["width_m"] / 2.0
                 for r in roads for x, y in r["points"]]
        beyond = [t for t in edges if t > t_edge]
        room = min(beyond) - t_edge if beyond else None
    else:
        out["road"] = _strip(cx, cy, d, n, t_edge + ROAD_NEAR_M,
                             t_edge + ROAD_NEAR_M + ROAD_WIDTH_M, s_lo, s_hi)
        room = ROAD_NEAR_M
    half = SIDEWALK_WIDTH_M / 2.0
    if room is not None and room >= SIDEWALK_OUT_M + half:
        out["sidewalk"] = _strip(cx, cy, d, n, t_edge + SIDEWALK_OUT_M - half,
                                 t_edge + SIDEWALK_OUT_M + half, s_lo, s_hi)
    return out


# ── roofs ───────────────────────────────────────────────────────────────────

def roof_for(ring: list, height_m: float) -> dict:
    """The roof a building is drawn with: ``{"form": "gable", "ridge": [[x, y],
    [x, y]], "rise_m": r}`` or ``{"form": "flat"}``.

    A gable only on a clean four-corner footprint of house size: four corners,
    each within a few degrees of square, neither side short of a shed nor the
    short one wider than a house. Its ridge runs the long way through the
    middle **at the recorded height**; the walls stop ``rise_m`` lower. So the
    building is never taller than the shade map's, only narrower at the top.
    """
    flat = {"form": "flat"}
    pts = [(float(p[0]), float(p[1])) for p in ring or []]
    if len(pts) != 4 or float(height_m or 0) < GABLE_MIN_WALL_M + 0.5:
        return flat
    sides = []
    for i in range(4):
        (x0, y0), (x1, y1) = pts[i], pts[(i + 1) % 4]
        sides.append((x1 - x0, y1 - y0))
    lengths = [math.hypot(dx, dy) for dx, dy in sides]
    if min(lengths) < GABLE_MIN_SIDE_M:
        return flat
    for i in range(4):
        (ax, ay), (bx, by) = sides[i], sides[(i + 1) % 4]
        cos = (ax * bx + ay * by) / (lengths[i] * lengths[(i + 1) % 4])
        if abs(math.degrees(math.asin(max(-1.0, min(1.0, cos))))) \
                > _SQUARE_WITHIN_DEG:
            return flat
    # The two pairs of opposite sides: the ridge joins the short pair's middles.
    a = (lengths[0] + lengths[2]) / 2.0
    b = (lengths[1] + lengths[3]) / 2.0
    short, first = (a, 0) if a <= b else (b, 1)
    if short > GABLE_MAX_SHORT_SIDE_M:
        return flat

    def mid(i):
        (x0, y0), (x1, y1) = pts[i], pts[(i + 1) % 4]
        return [round((x0 + x1) / 2.0, 2), round((y0 + y1) / 2.0, 2)]

    rise = min(short / 2.0 * GABLE_PITCH, float(height_m) * GABLE_MAX_SHARE,
               float(height_m) - GABLE_MIN_WALL_M)
    if rise < 0.3:
        return flat
    return {"form": "gable", "ridge": [mid(first), mid(first + 2)],
            "rise_m": round(rise, 2)}


def add_roofs(buildings: list) -> None:
    """Give each building (not a drawn tree crown) its ``roof`` hint."""
    for bld in buildings or []:
        if bld.get("kind") == "canopy":
            continue
        bld["roof"] = roof_for(bld.get("ring") or [], bld.get("height_m") or 0)


def site_fields(project: dict, proj, boundary_xy: Optional[list],
                buildings: list) -> dict:
    """The scene's ``ground``, ``surfaces``, ``lines`` and ``street``, and a
    ``roof`` on each of ``buildings`` (in place)."""
    add_roofs(buildings)
    return {
        "ground": ground_kind(project),
        "surfaces": surfaces(project, proj, boundary_xy),
        "lines": lines(project, proj),
        "street": street(project, proj, boundary_xy),
    }
