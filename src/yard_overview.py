"""
yard_overview.py — what the yard overview measures (V3.20: the planting area).

Design principle P9 — see docs/DESIGN_PHILOSOPHY.md.

The homeowner plan's overview (docs/homeowner/06-yard-overview.md, OV-1) grows
here. V3.20 (OV-3) brings its first measure forward because five places needed
it already: the Report card's cost, the planting plan export, and three pages
of the PDF each summed the area of **every** drawn shape and costed mulch for
it, lawn, path, patio and pond included (OVF-3). Drawing a path made the mulch
dearer.

The planting area, as part 06 §5.1 defines it:

  * the union of the bed-like shapes, when any is drawn (Garden Bed, Mulch
    Area, and the planted conversion zones: Restoration — Year 1 and Year 3,
    Established native);
  * otherwise the property boundary, less lawn (Lawn Area and the conversion
    zone *Lawn — to convert*), Pathway, Patio / Deck, Water Feature and
    building footprints;
  * nothing, with neither.

Qt-free. Geometry through shapely (a hard requirement) in local metres from
``src.projection.Projector``; without shapely, the same rule by the shapes'
stored areas, which is what the map labels them with, overlaps counted twice.
"""

from __future__ import annotations

from typing import Optional

#: Shapes a person plants in: their union is the planting area when any exists.
BED_SHAPES = ("Garden Bed", "Mulch Area", "Restoration — Year 1",
              "Restoration — Year 3", "Established native")

#: Shapes nobody plants in, taken off the boundary when no bed is drawn.
NOT_PLANTED = ("Lawn Area", "Lawn — to convert", "Pathway", "Patio / Deck",
               "Water Feature")


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


def planting_area(project: dict):
    """The planting area as a shapely geometry in local metres (east, north
    of the rings' centroid), or ``None`` with nothing to plant in. Needs
    shapely."""
    from shapely.geometry import Polygon
    from shapely.ops import unary_union
    from src.projection import Projector
    bounds, beds, holes = _parts(project)
    rings = beds or bounds
    if not rings:
        return None
    proj = Projector.for_positions(
        [(p[1], p[0]) for r in rings for p in r])

    def poly(ring):
        shape = Polygon([proj.to_xy(p[1], p[0]) for p in ring])
        return shape if shape.is_valid else shape.buffer(0)

    area = unary_union([poly(r) for r in rings])
    if not beds and holes:
        area = area.difference(unary_union([poly(r) for r in holes]))
    return None if area.is_empty else area


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
