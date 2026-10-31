"""
yard_overview.py — what the yard overview measures (V3.20: the planting area).

Design principle P9 — see docs/DESIGN_PHILOSOPHY.md.

The homeowner plan's overview (docs/homeowner/06-yard-overview.md, OV-1) grows
here. V3.20 (OV-3) brings its first measure forward because five places needed
it already: the Report card's cost, the planting plan export, and three pages
of the PDF each summed the area of **every** drawn shape and costed mulch for
it, lawn, path, patio and pond included (OVF-3). Drawing a path made the mulch
dearer.

V3.27 (OV-1, OV-9, PY-12) adds what the overview measures on it: how much
the plants cover once grown (:func:`cover`), the ground they leave bare
(:func:`bare_ground`) and the yard either side of the house
(:func:`yard_parts`). The six items themselves are ``yard_overview_items``.

The planting area, as part 06 §5.1 defines it:

  * the union of the bed-like shapes, when any is drawn (Garden Bed, Mulch
    Area, and the conversion zones: Lawn — to convert, Restoration — Year 1
    and Year 3, Established native);
  * otherwise the property boundary, less Lawn Area, Pathway, Patio / Deck,
    Water Feature, an existing remnant and building footprints;
  * nothing, with neither.

Qt-free. Geometry through shapely (a hard requirement) in local metres from
``src.projection.Projector``; without shapely, the same rule by the shapes'
stored areas, which is what the map labels them with, overlaps counted twice.
"""

from __future__ import annotations

from typing import Optional

#: Shapes a person plants in: their union is the planting area when any exists.
#: Plan My Yard plants exactly here (V3.28, PY-2; ``exclusion`` reads these).
#: *Lawn — to convert* is one since V3.28: a person who draws it and asks for a
#: plan means "turn this into garden" (part 07 §2); V3.20 had counted it as lawn.
BED_SHAPES = ("Garden Bed", "Mulch Area", "Lawn — to convert",
              "Restoration — Year 1", "Restoration — Year 3",
              "Established native")

#: Shapes nobody plants in, taken off the boundary when no bed is drawn, and
#: kept out of a plan (the remnant is left undisturbed).
NOT_PLANTED = ("Lawn Area", "Pathway", "Patio / Deck", "Water Feature",
               "Existing remnant")


def _ring(feature) -> Optional[list]:
    geom = (feature or {}).get("geometry") or {}
    if geom.get("type") != "Polygon" or not geom.get("coordinates"):
        return None
    ring = geom["coordinates"][0]
    return ring if ring and len(ring) >= 3 else None


def _parts(project: dict) -> tuple:
    """``(boundaries, beds, holes)``: the rings (``[lng, lat]``) of each."""
    bounds, beds, holes = [], [], []
    for f in (project or {}).get("features", []) or []:
        props = f.get("properties", {}) or {}
        ring = _ring(f)
        if ring is None:
            continue
        et, kind = props.get("element_type"), props.get("shape_type") or ""
        if et == "property_boundary":
            bounds.append(ring)
        elif et == "custom_shape" and kind in BED_SHAPES:
            beds.append(ring)
        elif et == "custom_shape" and kind in NOT_PLANTED:
            holes.append(ring)
        elif et == "canopy_footprint" and kind.startswith("Building"):
            holes.append(ring)
    return bounds, beds, holes


def local_area(project: dict) -> tuple:
    """``(projector, planting area)``: the area as a shapely geometry in local
    metres (east, north of the rings' centroid) and the projector that put it
    there, or ``(None, None)`` with nothing to plant in. Needs shapely."""
    from shapely.ops import unary_union
    from src.projection import Projector
    bounds, beds, holes = _parts(project)
    rings = beds or bounds
    if not rings:
        return None, None
    proj = Projector.for_positions(
        [(p[1], p[0]) for r in rings for p in r])
    area = unary_union([_poly(proj, r) for r in rings])
    if not beds and holes:
        area = area.difference(unary_union([_poly(proj, r) for r in holes]))
    return (None, None) if area.is_empty else (proj, area)


def _poly(proj, ring):
    from shapely.geometry import Polygon
    shape = Polygon([proj.to_xy(p[1], p[0]) for p in ring])
    return shape if shape.is_valid else shape.buffer(0)


def planting_area(project: dict):
    """The planting area as a shapely geometry in local metres, or ``None``
    with nothing to plant in. Needs shapely."""
    return local_area(project)[1]


def where_areas(project: dict) -> dict:
    """What Plan My Yard's *Where* question offers (V3.28, PY-1): ``{"beds":
    how many beds, "beds_m2": their area, "yard_m2": the outline less what
    is not for planting}``; an area is ``0.0`` when there is none. Needs
    shapely for an area; without it every area is ``0.0``."""
    bounds, beds, holes = _parts(project)
    out = {"beds": len(beds), "beds_m2": 0.0, "yard_m2": 0.0}
    try:
        from shapely.ops import unary_union
        from src.projection import Projector
    except ImportError:
        return out
    rings = beds + bounds
    if not rings:
        return out
    proj = Projector.for_positions([(p[1], p[0]) for r in rings for p in r])
    if beds:
        out["beds_m2"] = float(unary_union(
            [_poly(proj, r) for r in beds]).area)
    if bounds:
        yard = unary_union([_poly(proj, r) for r in bounds])
        if holes:
            yard = yard.difference(unary_union([_poly(proj, r) for r in holes]))
        out["yard_m2"] = float(yard.area)
    return out


def bed_area_m2(project: dict) -> float:
    """The planting area in m²: what mulch is bought for and the site-prep
    sheet clears (OV-3). ``0.0`` with no boundary and no bed."""
    try:
        import shapely  # noqa: F401
    except ImportError:
        from src.project import _ring_area_m2
        bounds, beds, holes = _parts(project)
        if beds:                         # overlaps count twice without shapely
            return sum(_ring_area_m2(r) for r in beds)
        return max(0.0, sum(_ring_area_m2(r) for r in bounds)
                   - sum(_ring_area_m2(r) for r in holes) if bounds else 0.0)
    area = planting_area(project)
    return float(area.area) if area is not None else 0.0


# ── Cover once grown (OV-1, §5.1) ───────────────────────────────────────────

#: The share of the planting area that reads as well filled once grown (O3).
WELL_FILLED = 0.70

#: Words for a share, from the top (§5.1): ``(at least, words)``.
SHARE_WORDS = ((0.85, "almost all"), (0.72, "about three quarters"),
               (0.60, "about two thirds"), (0.45, "about half"),
               (0.28, "about a third"), (0.18, "about a quarter"),
               (0.0, "less than a fifth"))

#: Bare patches smaller than this are not worth planting (OV-9).
SLIVER_M2 = 0.5


def share_words(share: float) -> str:
    return next(w for floor, w in SHARE_WORDS if share >= floor)


def canopy_m(row: dict) -> float:
    """A plant's mature spread: ``mature_canopy_m``, else 1.5 × its planting
    spacing, which is how every catalogue value was made."""
    try:
        width = float(row.get("mature_canopy_m") or 0)
    except (TypeError, ValueError):
        width = 0.0
    if width > 0:
        return width
    from src.planting_spacing import spacing_to_plant_m       # noqa: PLC0415
    return 1.5 * float(spacing_to_plant_m(row) or 0.3)


def _discs(proj, project: dict, get_plant):
    from shapely.geometry import Point
    from shapely.ops import unary_union
    from src.project_store import ProjectStore
    if get_plant is None:
        from src.db.plants import get_plant                   # noqa: PLC0415
    rows: dict = {}
    discs = []
    for p in ProjectStore(project).placed_plants:
        pid = p.get("plant_id")
        if pid not in rows:
            rows[pid] = get_plant(pid) or {}
        if p.get("lat") is None or p.get("lng") is None:
            continue
        x, y = proj.to_xy(p["lat"], p["lng"])
        discs.append(Point(x, y).buffer(canopy_m(rows[pid]) / 2.0, 24))
    return unary_union(discs) if discs else None


def cover(project: dict, *, get_plant=None) -> Optional[dict]:
    """``{"area_m2", "covered_m2", "share"}``: the planting area and how much
    of it the placed plants' mature spread covers, or ``None`` with no area.
    An estimate, said as "about" (every spread is a 1.5 × spacing default)."""
    proj, area = local_area(project)
    if area is None or area.area <= 0:
        return None
    discs = _discs(proj, project, get_plant)
    covered = discs.intersection(area).area if discs is not None else 0.0
    return {"area_m2": float(area.area), "covered_m2": float(covered),
            "share": float(covered / area.area)}


def bare_ground(project: dict, *, get_plant=None) -> tuple:
    """``(projector, geometry)``: the planting area the grown plants leave
    bare, patches under :data:`SLIVER_M2` dropped; ``(None, None)`` with no
    area."""
    from shapely.ops import unary_union
    proj, area = local_area(project)
    if area is None:
        return None, None
    discs = _discs(proj, project, get_plant)
    bare = area.difference(discs) if discs is not None else area
    parts = [g for g in getattr(bare, "geoms", [bare])
             if g.area >= SLIVER_M2]
    return proj, (unary_union(parts) if parts else None)


def fill_points(project: dict, spacing_m: float = 0.6, *,
                get_plant=None) -> list:
    """``[(lat, lng)]`` on a staggered grid ``spacing_m`` apart over the bare
    ground: where Fill the gaps plants (OV-9)."""
    from shapely.geometry import Point
    from shapely.prepared import prep
    proj, bare = bare_ground(project, get_plant=get_plant)
    if bare is None or spacing_m <= 0:
        return []
    inside = prep(bare)
    x0, y0, x1, y1 = bare.bounds
    out, row, y = [], 0, y0 + spacing_m / 2
    while y <= y1:
        x = x0 + spacing_m / 2 + (spacing_m / 2 if row % 2 else 0.0)
        while x <= x1:
            if inside.contains(Point(x, y)):
                out.append(proj.to_latlng(x, y))
            x += spacing_m
        row, y = row + 1, y + spacing_m * 0.866
    return out


# ── Front and back (PY-12, the owner's L3) ──────────────────────────────────

def _house(project: dict, proj):
    """The largest building footprint, in local metres, or ``None``."""
    best = None
    for f in (project or {}).get("features", []) or []:
        props = f.get("properties", {}) or {}
        if (props.get("element_type") == "canopy_footprint"
                and (props.get("shape_type") or "").startswith("Building")):
            ring = _ring(f)
            if ring is not None:
                shape = _poly(proj, ring)
                if best is None or shape.area > best.area:
                    best = shape
    return best


def yard_parts(project: dict) -> Optional[dict]:
    """The planting area either side of the house: ``{"front", "back"}`` in
    m², split by a line through the house's middle across the way to the
    street (``cues_to_care.frontage_for``: the road when known, else the south
    side, and ``assumed`` says which); ``{"whole"}`` with no building drawn;
    ``None`` with no area."""
    from shapely.geometry import Polygon
    import math
    proj, area = local_area(project)
    if area is None:
        return None
    house = _house(project, proj)
    if house is None:
        return {"whole": float(area.area)}
    from src.cues_to_care import frontage_for                 # noqa: PLC0415
    side = frontage_for(project)
    b = math.radians(side.bearing)
    ux, uy = math.sin(b), math.cos(b)            # towards the street
    cx, cy = house.centroid.x, house.centroid.y
    reach = 4 * max(area.bounds[2] - area.bounds[0],
                    area.bounds[3] - area.bounds[1], 1.0)
    px, py = -uy * reach, ux * reach             # along the line
    street = Polygon([(cx + px, cy + py), (cx - px, cy - py),
                      (cx - px + ux * reach, cy - py + uy * reach),
                      (cx + px + ux * reach, cy + py + uy * reach)])
    front = area.intersection(street).area
    return {"front": float(front), "back": float(area.area - front),
            "assumed": not side.known}


def about_m2(m2: float) -> str:
    """"about 60 m²": to 5 m² under 100, else to 10 (P9)."""
    step = 5 if m2 < 100 else 10
    return f"about {max(step, int(round(m2 / step)) * step):,} m²"


def parts_words(parts: Optional[dict]) -> str:
    """"Front yard about 60 m², back yard about 140 m²." or ``""``."""
    if not parts or "front" not in parts:
        return ""
    return (f"Front yard {about_m2(parts['front'])}, back yard "
            f"{about_m2(parts['back'])}.")


# ── What filling the gaps takes (OV-9) ──────────────────────────────────────

#: Low plants for the gaps: these types, or a wildflower this short.
FILLER_TYPES = ("grass", "sedge", "groundcover")
FILLER_MAX_HEIGHT_M = 0.6
FILL_SPACING_M = 0.6


def _fillers(project: dict, get_plant, place: str) -> list:
    """Up to two low plants to fill with: the design's own, most numerous
    first; else the region's two best-ranked grasses or sedges (PR-1)."""
    from src.project_store import ProjectStore
    counts: dict = {}
    for p in ProjectStore(project).placed_plants:
        counts[p.get("plant_id")] = counts.get(p.get("plant_id"), 0) + 1
    own = []
    for pid, n in sorted(counts.items(), key=lambda kv: -kv[1]):
        row = get_plant(pid) or {}
        try:
            tall = float(row.get("mature_height_meters") or 9)
        except (TypeError, ValueError):
            tall = 9.0
        if (row.get("plant_type") in FILLER_TYPES
                or (row.get("plant_type") == "wildflower"
                    and tall <= FILLER_MAX_HEIGHT_M)):
            own.append(row)
    if own:
        return own[:2]
    from src import native_here, plant_priority, zoning
    from src.db.plants import get_all_plants
    names = native_here.native_names(place)
    pool = [r for r in get_all_plants()
            if r.get("plant_type") in ("grass", "sedge")
            and r.get("scientific_name") in names
            and not zoning.needs_standing_water(r)]
    return plant_priority.rank(pool, place=place)[:2]


def fill_plan(project: dict, *, get_plant=None, place: str = "") -> dict:
    """``{"bare_m2", "points", "fillers", "records", "cost"}``: where Plant
    them would put low plants 60 cm apart, which ones (alternating), and what
    they would cost, before anything is placed."""
    from src import region
    from src.sourcing import estimate_cost
    if get_plant is None:
        from src.db.plants import get_plant                   # noqa: PLC0415
    _proj, bare = bare_ground(project, get_plant=get_plant)
    if not place:
        site = ((project or {}).get("properties") or {}).get(
            "site_config") or {}
        place = region.for_site(site).key
    points = fill_points(project, FILL_SPACING_M, get_plant=get_plant)
    fillers = _fillers(project, get_plant, place) if points else []
    records = ([(int(fillers[i % len(fillers)]["id"]), lat, lng)
                for i, (lat, lng) in enumerate(points)] if fillers else [])
    cost = estimate_cost([(pid, 1) for pid, _la, _ln in records],
                         get_plant=get_plant)
    return {"bare_m2": float(bare.area) if bare is not None else 0.0,
            "points": points, "fillers": fillers, "records": records,
            "cost": cost}
