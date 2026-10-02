"""
src/design_inputs.py — what the design already knows, for the pages that ask
(V3.05).

Planning › Water asked for the garden's area (200 m²), its rain barrels (2),
swales (0) and ponds (0), with those defaults whatever the design held: the
worked example's 88 m² yard was budgeted as 200 m², and a design with a pond
placed still started from "0 ponds". The V3.05 surface audit found it. These
read the answers off the project, so the page starts from the yard on the map;
the inputs stay editable for what-ifs.

Qt-free; ``planning_panel`` and ``app._sync_planning_panel`` are the callers.
"""

from __future__ import annotations

#: Structure ids (``src/db/structures.py``) that hold or slow water, by the
#: Water page's input they answer.
WATER_STRUCTURES: dict = {
    "rain_barrel": "rain_barrels",
    "pond": "ponds",
    "swale": "swales",
}


def boundary_area_m2(project: dict) -> float:
    """The area inside the drawn property boundaries, in m², by the same
    planar measure the map labels them with. ``0.0`` with no boundary."""
    from src.project import _ring_area_m2
    total = 0.0
    for f in (project or {}).get("features", []) or []:
        props = f.get("properties", {}) or {}
        geom = f.get("geometry", {}) or {}
        if props.get("element_type") != "property_boundary":
            continue
        if geom.get("type") != "Polygon" or not geom.get("coordinates"):
            continue
        total += _ring_area_m2(geom["coordinates"][0])
    return total


def water_features(structures) -> dict:
    """``{"rain_barrels": n, "ponds": n, "swales": n}`` for the placed
    structures (each a ``struct_def`` dict, as the panels are handed them)."""
    counts = {key: 0 for key in WATER_STRUCTURES.values()}
    for s in structures or []:
        key = WATER_STRUCTURES.get((s or {}).get("id"))
        if key:
            counts[key] += 1
    return counts
