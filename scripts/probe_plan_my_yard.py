"""
probe_plan_my_yard.py — what Plan My Yard does with what a person draws
(PY-11, V3.28; docs/homeowner/07-plan-my-yard.md §2).

Runs the offline generator on a 15 x 10 m yard in south Edmonton with the
first-run goals and prints, for each case, how many plants it placed, how many
landed on the drawn shape, and how much of the planting area they cover once
grown, measured by ``yard_overview.cover`` exactly as the Overview measures it.

    python scripts/probe_plan_my_yard.py            # print the table
    python scripts/probe_plan_my_yard.py --assert   # fail on the PY-2/PY-4 rules

It uses a throwaway database, so your own designs and catalogue are never
touched. It takes a minute or two (a few seconds a plan).
"""

from __future__ import annotations

import math
import os
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

LAT0, LNG0 = 53.5232, -113.5263
KX = 111320 * math.cos(math.radians(LAT0))
KY = 111320.0
W, D = 15.0, 10.0
BOUNDARY = [[LAT0 + n / KY, LNG0 + e / KX]
            for e, n in ((0, 0), (W, 0), (W, D), (0, D))]
SITE = {"latitude": LAT0 + 5 / KY, "longitude": LNG0 + 7 / KX}

#: The cases of 07 §2: (label, shape type, x0, y0, x1, y1).
SHAPES = (
    ("Garden Bed, 6 x 3 m", "Garden Bed", 1, 6, 7, 9),
    ("Lawn Area, south 60%", "Lawn Area", 0, 0, 15, 6),
    ("Lawn - to convert, south 60%", "Lawn — to convert", 0, 0, 15, 6),
    ("Patio / Deck, south 60%", "Patio / Deck", 0, 0, 15, 6),
    ("Pathway, 1 x 10 m", "Pathway", 7, 0, 8, 10),
)


def _db():
    import src.db.plants as P
    tmp = tempfile.mkdtemp(prefix="plan_my_yard_probe_")
    P._DATA_DIR = tmp
    P._DB_PATH = os.path.join(tmp, "probe.db")
    P.init_db()


def _shape(kind, x0, y0, x1, y1):
    ring = [[LNG0 + e / KX, LAT0 + n / KY]
            for e, n in ((x0, y0), (x1, y0), (x1, y1), (x0, y1), (x0, y0))]
    return {"type": "Feature",
            "geometry": {"type": "Polygon", "coordinates": [ring]},
            "properties": {"element_type": "custom_shape", "shape_type": kind}}


def run(density: str = "balanced", features=(), cover=None) -> dict:
    """One plan: ``{placed, on_shape, cover, per_m2}``."""
    from src.llm_design import generate_design_offline
    from src.onboarding import FIRST_RUN_GOALS
    from src import yard_overview
    features = list(features)
    project = generate_design_offline(
        site_config=SITE, boundary=BOUNDARY, goals=list(FIRST_RUN_GOALS),
        density=density, existing_features=features, cover=cover).as_dict()
    whole = {"features": project["features"] + features}
    plants = [f for f in project["features"]
              if (f.get("properties") or {}).get("plant_id")]
    kinds = len({f["properties"]["plant_id"] for f in plants})
    on = 0
    if features:
        from src.geometry import point_in_ring
        ring = features[0]["geometry"]["coordinates"][0]
        for f in plants:
            lng, lat = f["geometry"]["coordinates"]
            on += point_in_ring(lat, lng, ring)
    c = yard_overview.cover(whole) or {"share": 0.0, "area_m2": 0.0}
    return {"placed": len(plants), "on_shape": on, "cover": c["share"],
            "kinds": kinds,
            "area": c["area_m2"],
            "per_m2": len(plants) / c["area_m2"] if c["area_m2"] else 0.0}


def measure() -> dict:
    out = {"cover": {}, "shapes": {}}
    for label, cover in (("Fill it now", 0.70),
                         ("Over two or three summers", 0.40)):
        out["cover"][label] = run(cover=cover)
    out["open"] = run()
    for label, kind, *box in SHAPES:
        out["shapes"][label] = run(features=[_shape(kind, *box)])
    return out


def failures(m: dict) -> list:
    """The PY-2 to PY-4 rules (07 §5), as sentences; ``[]`` when all hold."""
    bad = []
    now = m["cover"]["Fill it now"]["cover"]
    later = m["cover"]["Over two or three summers"]["cover"]
    if now < 0.65:
        bad.append(f"Fill it now covers {now:.0%}, under 65%")
    if not 0.35 <= later <= 0.45:
        bad.append(f"Over two or three summers covers {later:.0%}, not 35-45%")
    s = m["shapes"]
    bed = s["Garden Bed, 6 x 3 m"]
    if not bed["placed"] or bed["on_shape"] < 0.9 * bed["placed"]:
        bad.append(f"Garden Bed: {bed['on_shape']} of {bed['placed']} in it")
    if s["Lawn Area, south 60%"]["on_shape"]:
        bad.append(f"Lawn Area: {s['Lawn Area, south 60%']['on_shape']} on it")
    path, open_yard = s["Pathway, 1 x 10 m"], m["open"]
    if path["on_shape"] or path["placed"] < 0.9 * open_yard["placed"] * 0.93:
        bad.append(f"Pathway: {path['placed']} placed, {path['on_shape']} "
                   f"on it, open yard {open_yard['placed']}")
    patio = s["Patio / Deck, south 60%"]
    if patio["on_shape"] or patio["cover"] < 0.35:
        bad.append(f"Patio: {patio['on_shape']} on it, "
                   f"{patio['cover']:.0%} cover")
    # 07 §5 asked for as many plants a m2 as the open yard, written when a
    # zone collapsed a plan to 6 plants at 23% cover. Filling to cover, a
    # tree and three shrubs cover more than thirty violets, so the rule is
    # the zone's cover, by enough kinds to be a planting (V3.28).
    zone = s["Lawn - to convert, south 60%"]
    if zone["cover"] < open_yard["cover"] - 0.05 or zone["kinds"] < 6:
        bad.append(f"Lawn - to convert: {zone['cover']:.0%} cover by "
                   f"{zone['kinds']} kinds, open yard {open_yard['cover']:.0%}")
    return bad


def main(argv=None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    _db()
    m = measure()
    print("How full (no shapes drawn), 150 m2:")
    for label, r in m["cover"].items():
        print(f"  {label:28s} placed {r['placed']:3d}; covers {r['cover']:.0%}")
    print(f"  {'Balanced (advanced)':28s} placed {m['open']['placed']:3d}; "
          f"covers {m['open']['cover']:.0%}")
    print("\nOne shape drawn, balanced:")
    for label, r in m["shapes"].items():
        print(f"  {label:30s} placed {r['placed']:3d} of {r['kinds']:2d} kinds; "
              f"{r['on_shape']:3d} on it; covers {r['cover']:.0%} of "
              f"{r['area']:.0f} m2")
    if "--assert" in argv:
        bad = failures(m)
        for line in bad:
            print("FAIL:", line)
        return 1 if bad else 0
    return 0


if __name__ == "__main__":
    sys.exit(main())
