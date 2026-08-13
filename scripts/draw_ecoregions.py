#!/usr/bin/env python3
"""Author the ecoregion and province outlines used by the maps and by
``src/ecoregion.py``'s point lookup (V2.49).

    python scripts/draw_ecoregions.py [--check]

WHY THIS EXISTS
-------------------------------------------------------------------------------
The shipped ``data/ecoregions_canada.geojson`` was **ten five-vertex
rectangles**, drawn by hand as a placeholder in V2.14. V2.48 started drawing
them and the author's verdict was immediate:

    "The map is atrocious and needs to actually look like the ecoregion map
     which I also include, including the political/provincial boundaries."

Correct. A grid of boxes is not a map of anywhere. This script replaces the
boxes with outlines that follow the real geography: the continental divide up
the Alberta/British Columbia border, the parkland's arc from Calgary through
Edmonton and east past North Battleford, the grassland triangle in the south,
and the boreal filling the north. It also writes ``data/provinces_prairie.
geojson`` so the drawing can carry provincial borders, which is most of what
made the reference map legible.

**These are still hand-authored, and the caveat still ships with every
drawing.** The real CEC Level III polygons are a download
(``scripts/prepare_ecoregions.py``, see the V2.38 runbook) that has never run in
a session with open egress. What changed is the honesty of the *shape*: an
approximate outline of the right thing beats an exact rectangle around the wrong
thing, and nobody looking at this mistakes it for a survey.

WHY IT SELF-CHECKS
-------------------------------------------------------------------------------
These polygons are not decoration. ``src/ecoregion.py:lookup_ecoregions`` reads
them to decide which ecoregion a user's property is in, which decides which
plants get recommended. Redrawing them silently changes recommendations for
real sites, so the script asserts every city lookup the test suite pins
**before** it writes anything: Edmonton is parkland, Banff is montane,
Saskatoon is moist mixed grassland, Vancouver is nowhere. If a shape drifts, the
script fails rather than the app.

WHY THE REGIONS OVERLAP ON PURPOSE
-------------------------------------------------------------------------------
Real ecoregions tile; these deliberately overlap by a fraction of a degree at
their shared edges. A property near a boundary genuinely belongs to both, and
the second answer is exactly the species list that was going missing before
``lookup_ecoregions`` learned to return more than one (P9).
"""

from __future__ import annotations

import argparse
import json
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))

_DATA = pathlib.Path(__file__).resolve().parent.parent / "data"
_ECO = _DATA / "ecoregions_canada.geojson"
_PROV = _DATA / "provinces_prairie.geojson"

# ── The continental divide, which is the Alberta/BC border ──────────────────
# Sampled every half degree of latitude from the 49th parallel to where the
# border leaves the divide and runs straight up the 120th meridian.
DIVIDE = [
    (-114.07, 49.0), (-114.55, 49.5), (-115.00, 50.0), (-115.45, 50.5),
    (-115.95, 51.0), (-116.45, 51.5), (-117.00, 52.0), (-117.65, 52.5),
    (-118.50, 53.0), (-119.20, 53.6), (-120.00, 54.0),
]

#: How far east of the divide the mountains give way to foothills, by latitude.
#: Narrow in the south (the border cuts diagonally across the ranges) and wider
#: through the Jasper/Willmore section.
_MONTANE_WIDTH = {49.0: 0.55, 49.5: 0.70, 50.0: 0.80, 50.5: 0.85, 51.0: 0.90,
                  51.5: 0.95, 52.0: 1.00, 52.5: 1.05, 53.0: 1.10, 53.6: 1.10,
                  54.0: 1.05}
#: And how far east the foothills run before the parkland or grassland starts.
_FOOTHILL_WIDTH = {49.0: 1.40, 49.5: 1.65, 50.0: 1.85, 50.5: 2.00, 51.0: 2.10,
                   51.5: 2.15, 52.0: 2.15, 52.5: 2.10, 53.0: 2.00, 53.6: 1.90,
                   54.0: 1.80}


def _offset(width: dict) -> list:
    """The divide, shifted east by a per-latitude width."""
    return [(lon + width[lat], lat) for lon, lat in DIVIDE]


def _strip(inner: list, outer: list) -> list:
    """A band between two south-to-north lines, closed."""
    ring = list(inner) + list(reversed(outer))
    return ring + [ring[0]]


# ── The regions ─────────────────────────────────────────────────────────────
# Order matters: `lookup_ecoregion` returns the FIRST polygon containing a
# point, so the narrower, more specific regions are listed before the broad
# ones. Calgary sits in both the foothills and the parkland arc, and foothills
# is the more useful answer.

def _montane() -> list:
    return [_strip(DIVIDE, _offset(_MONTANE_WIDTH))]


def _foothills() -> list:
    return [_strip(_offset(_MONTANE_WIDTH), _offset(_FOOTHILL_WIDTH))]


# Adjacent regions are cut from SHARED boundary lines rather than traced
# separately, because tracing them separately left holes: the first cut had a
# band east of Calgary, 0.8 degrees tall, that belonged to no region at all and
# would have returned "we do not cover your site" to anyone in Strathmore. Each
# line below is sampled at the same longitudes, the region above a line starts
# `_OVERLAP` degrees south of it, and the script refuses to write if any point
# inside Alberta or Saskatchewan comes back uncovered.

#: Longitudes every plains boundary is sampled at, west to east.
_LONS = (-115.40, -114.20, -113.00, -111.50, -110.00, -108.70, -107.00,
         -105.50, -104.00, -102.50, -101.40)

#: Top of the grassland, which is also the bottom of the parkland arc.
_GRASS_TOP = (51.00, 51.05, 51.25, 51.40, 51.50, 51.95, 52.55, 52.45, 52.00,
              51.45, 51.10)
#: Top of the parkland, which is also the bottom of the boreal.
_PARK_TOP = (53.35, 53.90, 54.30, 54.40, 54.30, 54.00, 53.55, 53.05, 52.55,
             52.05, 51.75)
#: How far regions reach past their shared line. A property near a boundary
#: belongs to both, and saying so is the whole point of `lookup_ecoregions`.
_OVERLAP = 0.18

#: The dry/moist grassland split, as (lon, lat) going north from the border.
_DRY_MOIST = ((-106.40, 49.00), (-106.60, 50.30), (-107.10, 50.90),
              (-108.20, 51.70), (-108.70, 52.40))


def _line(lats: tuple) -> list:
    return list(zip(_LONS, lats))


def _below(lats: tuple, floor: float = 49.0, west=None, east=None) -> list:
    """The band under a boundary line, closed against a southern parallel."""
    top = _line(lats)
    if west is not None:
        top = [(lon, lat) for lon, lat in top if lon >= west]
    if east is not None:
        top = [(lon, lat) for lon, lat in top if lon <= east]
    ring = top + [(top[-1][0], floor), (top[0][0], floor)]
    return ring + [ring[0]]


def _parkland() -> list:
    """The aspen parkland arc: Calgary, Red Deer, Edmonton, Lloydminster,
    North Battleford, then north of Saskatoon and down toward Yorkton.

    Its whole character is that it is a crescent rather than a band, which is
    why the rectangle version read as nothing in particular.
    """
    north = _line(_PARK_TOP)
    south = [(lon, lat - _OVERLAP) for lon, lat in _line(_GRASS_TOP)]
    ring = north + list(reversed(south))
    return [ring + [ring[0]]]


def _mixedgrass() -> list:
    """The dry grassland: south-east Alberta and south-west Saskatchewan, cut
    off on the east by the dry/moist split."""
    top = [(lon, lat + _OVERLAP) for lon, lat in _line(_GRASS_TOP)
           if lon <= -107.00]
    east = [(lon, lat) for lon, lat in reversed(_DRY_MOIST)]
    ring = [(-114.60, 49.00)] + top + east
    return [ring + [ring[0]]]


def _moist_mixedgrass() -> list:
    """The moist mixed grassland belt: Regina and Saskatoon, wrapping the dry
    grassland on its north and east."""
    top = [(lon, lat + _OVERLAP) for lon, lat in _line(_GRASS_TOP)
           if lon >= -108.70]
    ring = list(_DRY_MOIST) + top + [(-101.40, 49.00)]
    return [ring + [ring[0]]]


def _boreal() -> list:
    """Everything north of the parkland in both provinces, plus the boreal
    foothills wedge that runs west to the BC border above Grande Prairie."""
    south = [(lon, lat - _OVERLAP) for lon, lat in _line(_PARK_TOP)]
    ring = ([(-120.00, 60.00), (-101.40, 60.00)]
            + [(lon, lat) for lon, lat in reversed(south)]
            + [(-115.60, 52.20), (-116.60, 52.50), (-117.60, 52.95),
               (-118.80, 53.45), (-120.00, 53.90)])
    return [ring + [ring[0]]]


REGIONS = (
    # key, label, name, where, sort, rings
    ("subalpine_montane", "Subalpine / Montane (mountains)",
     "Subalpine / Montane", "the mountains", 5, _montane()),
    ("fescue_foothills", "Fescue / Foothills (SW AB)",
     "Fescue / Foothills", "SW Alberta", 3, _foothills()),
    ("aspen_parkland", "Aspen Parkland (central AB / SK)",
     "Aspen Parkland", "central AB / SK", 0, _parkland()),
    ("moist_mixedgrass", "Moist Mixed Grassland (Regina / Saskatoon)",
     "Moist Mixed Grassland", "Regina / Saskatoon", 2, _moist_mixedgrass()),
    ("mixedgrass_prairie", "Mixedgrass Prairie (south AB / SK)",
     "Mixedgrass Prairie", "south AB / SK", 1, _mixedgrass()),
    ("boreal_mixedwood", "Boreal Mixedwood (north AB / SK)",
     "Boreal Mixedwood / Plain", "north AB / SK", 4, _boreal()),
)


# ── Provincial boundaries, for drawing only ─────────────────────────────────
# Never read by the lookup. Alberta and Saskatchewan are unusually easy to draw
# honestly: three of Alberta's four borders and all four of Saskatchewan's are
# meridians and parallels, and the fourth is the divide above.

def _alberta() -> list:
    ring = ([(-114.07, 49.0)] + DIVIDE[1:] + [(-120.0, 60.0), (-110.0, 60.0),
                                              (-110.0, 49.0)])
    return ring + [ring[0]]


def _saskatchewan() -> list:
    ring = [(-110.0, 49.0), (-101.36, 49.0), (-101.36, 60.0), (-110.0, 60.0)]
    return ring + [ring[0]]


def _british_columbia() -> list:
    """Only the sliver inside the map window, for context east of the coast."""
    ring = [(-121.5, 49.0), (-114.07, 49.0)] + DIVIDE[1:] + [(-121.5, 60.0)]
    return ring + [ring[0]]


def _manitoba() -> list:
    ring = [(-101.36, 49.0), (-99.0, 49.0), (-99.0, 60.0), (-101.36, 60.0)]
    return ring + [ring[0]]


PROVINCES = (
    ("BC", "British Columbia", _british_columbia()),
    ("AB", "Alberta", _alberta()),
    ("SK", "Saskatchewan", _saskatchewan()),
    ("MB", "Manitoba", _manitoba()),
)

#: Drawn as dots with labels. Orientation is most of what a reader needs from a
#: small map, and these are the places the catalogue's own tests name.
CITIES = (
    ("Calgary", 51.0447, -114.0719),
    ("Edmonton", 53.5461, -113.4938),
    ("Fort McMurray", 56.7264, -111.3803),
    ("Grande Prairie", 55.1707, -118.7947),
    ("Lethbridge", 49.6956, -112.8451),
    ("Saskatoon", 52.1332, -106.6700),
    ("Regina", 50.4452, -104.6189),
    ("Prince Albert", 53.2033, -105.7531),
)


# ── The self-check ──────────────────────────────────────────────────────────
#: Every lookup the suite pins. Asserted before anything is written, because
#: these polygons decide which plants a real site is offered.
EXPECT = (
    (53.5461, -113.4938, "aspen_parkland", "Edmonton"),
    (52.2681, -113.8112, "aspen_parkland", "Red Deer"),
    (56.7264, -111.3803, "boreal_mixedwood", "Fort McMurray"),
    (55.1707, -118.7947, "boreal_mixedwood", "Grande Prairie"),
    (49.6956, -112.8451, "mixedgrass_prairie", "Lethbridge"),
    (50.0405, -110.6764, "mixedgrass_prairie", "Medicine Hat"),
    (51.0447, -114.0719, "fescue_foothills", "Calgary"),
    (51.1784, -115.5708, "subalpine_montane", "Banff"),
    (52.8737, -118.0814, "subalpine_montane", "Jasper"),
    (50.4452, -104.6189, "moist_mixedgrass", "Regina"),
    (50.6500, -104.8700, "moist_mixedgrass", "Lumsden"),
    (52.1332, -106.6700, "moist_mixedgrass", "Saskatoon"),
    (52.7575, -108.2861, "aspen_parkland", "North Battleford"),
    (52.7368, -108.2967, "aspen_parkland", "Battleford"),
    (50.2881, -107.7939, "mixedgrass_prairie", "Swift Current"),
)
#: Points that must fall outside every polygon.
EXPECT_NONE = ((49.2827, -123.1207, "Vancouver"),
               (49.8951, -97.1384, "Winnipeg"),
               (75.0, -100.0, "the Arctic"))
#: Exactly one region, because a mid-region site should not read as a boundary.
EXPECT_ONE = ((53.5461, -113.4938, "Edmonton"), (52.1332, -106.6700, "Saskatoon"))


def _feature(key, label, name, where, sort, ring) -> dict:
    return {"type": "Feature",
            "properties": {"key": key, "label": label, "name": name,
                           "where": where, "sort": sort},
            "geometry": {"type": "Polygon",
                         "coordinates": [[[round(x, 3), round(y, 3)]
                                          for x, y in ring]]}}


def build_ecoregions() -> dict:
    features = []
    for key, label, name, where, sort, rings in REGIONS:
        for ring in rings:
            features.append(_feature(key, label, name, where, sort, ring))
    return {"type": "FeatureCollection", "features": features}


def build_provinces() -> dict:
    return {"type": "FeatureCollection", "features": [
        {"type": "Feature",
         "properties": {"code": code, "name": name},
         "geometry": {"type": "Polygon",
                      "coordinates": [[[round(x, 3), round(y, 3)]
                                       for x, y in ring]]}}
        for code, name, ring in PROVINCES]}


def _coverage_gaps(eco, step: float = 0.2) -> list:
    """Sampled points inside Alberta or Saskatchewan that belong to no region.

    The first cut of these shapes left a band east of Calgary, 0.8 degrees
    tall, that no polygon covered: anyone in Strathmore would have been told
    the catalogue does not reach their site. Tracing adjacent regions
    separately is what caused it, and this is what catches it happening again.
    """
    provinces = [f["geometry"]["coordinates"]
                 for f in build_provinces()["features"]
                 if f["properties"]["code"] in ("AB", "SK")]
    holes = []
    lat = 49.0 + step
    while lat < 60.0:
        lon = -120.0 + step
        while lon < -101.4:
            if (any(eco._point_in_polygon(lat, lon, r) for r in provinces)
                    and not eco.lookup_ecoregions(lat, lon)):
                holes.append((round(lat, 2), round(lon, 2)))
            lon += step
        lat += step
    if not holes:
        return []
    return [f"{len(holes)} sampled points inside AB/SK belong to no region, "
            f"e.g. {holes[:4]}"]


def check(doc: dict) -> list:
    """Run every pinned lookup against ``doc`` without touching the shipped
    file. Returns a list of failure strings."""
    from src import ecoregion as eco
    real_load = eco._load_features
    eco._load_features = lambda: doc["features"]
    eco._FEATURES_CACHE = None
    problems = []
    try:
        for lat, lng, want, place in EXPECT:
            got = eco.lookup_ecoregion(lat, lng)
            if got != want:
                allk = eco.lookup_ecoregions(lat, lng)
                problems.append(f"{place}: got {got!r} (all: {allk}), want {want!r}")
        for lat, lng, place in EXPECT_NONE:
            if eco.lookup_ecoregion(lat, lng) is not None:
                problems.append(f"{place}: should be outside every polygon")
        for lat, lng, place in EXPECT_ONE:
            keys = eco.lookup_ecoregions(lat, lng)
            if len(keys) != 1:
                problems.append(f"{place}: in {len(keys)} regions {keys}, want 1")
        problems.extend(_coverage_gaps(eco))
    finally:
        eco._load_features = real_load
        eco._FEATURES_CACHE = None
    return problems


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--check", action="store_true",
                    help="verify the lookups; write nothing")
    args = ap.parse_args()

    eco = build_ecoregions()
    prov = build_provinces()
    verts = sum(len(f["geometry"]["coordinates"][0]) for f in eco["features"])
    print(f"{len(eco['features'])} ecoregion polygons, {verts} vertices "
          f"(was 10 polygons of 5)")
    print(f"{len(prov['features'])} province outlines")

    problems = check(eco)
    if problems:
        print("\nLOOKUP FAILURES, nothing written:")
        for p in problems:
            print(f"  {p}")
        return 1
    print(f"all {len(EXPECT) + len(EXPECT_NONE) + len(EXPECT_ONE)} "
          f"pinned lookups pass")

    if args.check:
        print("--check: nothing written")
        return 0
    _ECO.write_text(json.dumps(eco, indent=1) + "\n", encoding="utf-8")
    _PROV.write_text(json.dumps(prov, indent=1) + "\n", encoding="utf-8")
    print(f"\nwrote {_ECO}\nwrote {_PROV}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
