"""Measure what the offline generator does with a yard's drawn shapes.

Part of the homeowner-path plan, docs/homeowner/07-plan-my-yard.md (§2). Runs
``generate_design_offline`` on a 15 x 10 m yard in south Edmonton with the
first-run goals and prints, for each case, how many plants it placed, how many
landed on the drawn shape, and how much of the yard the plants cover once grown
(one disc per plant, ``mature_canopy_m`` across, as 06-yard-overview.md §5.1
measures it).

Run it from the repository root against a throwaway database, so your own
designs and catalogue are never touched:

    S=$(mktemp -d)
    HOME=$S XDG_DATA_HOME=$S/.local/share PYTHONPATH=. \\
        python3 docs/homeowner/prototypes/plan_my_yard_probe.py

It takes a minute or two (about five seconds a design). Re-run it after each
PY work item: the numbers in 07 §2 are this script's output at V3.17.
"""

from __future__ import annotations

import math

from shapely.geometry import Point, Polygon
from shapely.ops import unary_union

from src.db import plants as P

P.init_db()

from src.exclusion import keepout_circles  # noqa: E402
from src.llm_design import generate_design_offline  # noqa: E402
from src.onboarding import FIRST_RUN_GOALS  # noqa: E402

LAT0, LNG0 = 53.5232, -113.5263
KX = 111320 * math.cos(math.radians(LAT0))
KY = 111320.0
W, D = 15.0, 10.0
YARD = Polygon([(0, 0), (W, 0), (W, D), (0, D)])
BOUNDARY = [[LAT0 + n / KY, LNG0 + e / KX] for e, n in ((0, 0), (W, 0), (W, D), (0, D))]
SITE = {"latitude": LAT0 + 5 / KY, "longitude": LNG0 + 7 / KX}
TARGET = {"sparse": 0.30, "balanced": 0.60, "full": 0.90}   # x 1 plant a m2


def _shape(kind, x0, y0, x1, y1):
    ring = [[LNG0 + e / KX, LAT0 + n / KY]
            for e, n in ((x0, y0), (x1, y0), (x1, y1), (x0, y1), (x0, y0))]
    feature = {"type": "Feature",
               "geometry": {"type": "Polygon", "coordinates": [ring]},
               "properties": {"element_type": "custom_shape", "shape_type": kind}}
    return feature, Polygon([(x0, y0), (x1, y0), (x1, y1), (x0, y1)])


def _run(density, features):
    project = generate_design_offline(
        site_config=SITE, boundary=BOUNDARY, goals=list(FIRST_RUN_GOALS),
        density=density, existing_features=features).as_dict()
    points, discs = [], []
    for f in project["features"]:
        pid = f["properties"].get("plant_id")
        if not pid:
            continue
        lng, lat = f["geometry"]["coordinates"]
        pt = Point((lng - LNG0) * KX, (lat - LAT0) * KY)
        points.append(pt)
        canopy = float(P.get_plant(pid).get("mature_canopy_m") or 1.0)
        discs.append(pt.buffer(canopy / 2))
    cover = unary_union(discs).intersection(YARD).area / YARD.area if discs else 0.0
    return points, cover, project["properties"].get("generation_warnings", [])


def main():
    print("Density alone (no shapes drawn), 150 m2:")
    for density in ("sparse", "balanced", "full"):
        pts, cover, _ = _run(density, [])
        print(f"  {density:9} placed {len(pts):3} of a {int(150 * TARGET[density]):3}-plant "
              f"target; covers {cover:.0%} of the yard once grown")

    cases = [
        ("Garden Bed, 6 x 3 m (12% of the yard)", "Garden Bed", (1, 1, 7, 4)),
        ("Lawn Area, south 60% of the yard", "Lawn Area", (0, 0, 15, 6)),
        ("Lawn - to convert, south 60%", "Lawn — to convert", (0, 0, 15, 6)),
        ("Patio / Deck, south 60%", "Patio / Deck", (0, 0, 15, 6)),
        ("Pathway, 1 x 10 m (7% of the yard)", "Pathway", (7, 0, 8, 10)),
    ]
    print("\nOne shape drawn, balanced density (42 plants with nothing drawn):")
    for label, kind, box in cases:
        feature, poly = _shape(kind, *box)
        pts, cover, _ = _run("balanced", [feature])
        on = sum(1 for p in pts if poly.contains(p))
        print(f"  {label:40} placed {len(pts):3}; {on:3} on the shape; covers {cover:.0%}")
        if kind in ("Pathway", "Patio / Deck"):
            radius = keepout_circles({"features": [feature]})[0][2]
            print(f"  {'':40} kept out by a circle of radius {radius:.1f} m "
                  f"({math.pi * radius * radius:.0f} m2)")

    _, _, notes = _run("balanced", [])
    print("\nThe design notes a balanced plan shows today:")
    for note in notes:
        print("  -", note)


if __name__ == "__main__":
    main()
