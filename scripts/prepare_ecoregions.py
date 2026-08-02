"""
prepare_ecoregions.py — Replace the shipped Alberta ecoregion polygons
with simplified polygons derived from the CEC Level III Ecoregions of
North America shapefile.

This is a dev-time / data-prep script, NOT part of the user-facing
runtime. Run it once when you want to upgrade the shipped
``data/ecoregions_canada.geojson`` from the V1.36 rectangular starter
set to real CEC boundaries. The resulting file is committed to the
repo and shipped — users never run this.

Requires (dev-time only — NOT in user requirements.txt):

    pip install fiona shapely pyproj

(``shapely`` is the standard library for vector geometry in Python.
``fiona`` reads the .shp + .shx + .dbf + .prj fileset. ``pyproj``
re-projects from the source CRS, which the CEC ships in Lambert
Azimuthal Equal Area, to WGS84 / GeoJSON-native lat/lng.)

Workflow:

    1. Download the CEC NA Level III ecoregions shapefile from
       http://www.cec.org/north-american-environmental-atlas/ecoregions
       (Level III; "Ecoregions of North America"). Unzip into a
       working directory and pass its path as ``--shapefile``.

    2. Run this script. It clips to the Alberta bounding box,
       reprojects each polygon to WGS84, simplifies with a tolerance
       of ~0.01° (~1 km — fine for plant-filter use), and writes
       a GeoJSON FeatureCollection with one feature per ecoregion.

    3. Map each CEC Level III ecoregion name to a canonical key in
       ``KEY_MAP`` below. Merge several CEC polygons into one key, or
       add keys — **adding a key is now the whole job.** Since V2.38 the
       written file IS the app's geographic ecoregion vocabulary: each
       feature carries ``key`` / ``name`` / ``where`` / ``sort``, and
       ``src/ecoregion.py`` reads them, so a new region appears in the
       filter dropdown, the data validator's accepted keys and the
       range-derivation script at once. There is no second list to edit.

       This is what makes "when I add BC and other areas of turtle island
       we simply add more ecoregions" true rather than aspirational.

    4. Commit the regenerated ``data/ecoregions_canada.geojson`` with a
       schema bump per CLAUDE.md — the key set is the data validator's
       vocabulary, and per-species ecoregion rows are keyed against it.

    5. Re-run ``scripts/seed_ecoregion_ranges.py`` afterwards. Species
       ranges are derived by intersecting occurrence records with THESE
       polygons, so new boundaries mean new counts.

Note that ``riparian`` and ``wet_meadow`` are deliberately NOT in this
file and never will be. They are site-scale moisture niches, not regions
— no polygon can say a species grows in wet ground — and they live in
``src/ecoregion.MOISTURE_NICHES`` instead.

This script intentionally fails fast if its optional deps aren't
installed — they're not in the user-facing requirements.txt, and
making them implicit would defeat the V1.36 "pure-Python ray casting,
zero new shipped deps" decision.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parent.parent
OUTPUT_PATH  = PROJECT_ROOT / "data" / "ecoregions_canada.geojson"

# Alberta bbox (rough envelope, leaves some buffer for boundary polygons).
AB_BBOX = (-120.0, 49.0, -110.0, 60.0)   # (west, south, east, north)


# CEC Level III ecoregion name → the app's canonical key. Names are the
# standard CEC labels for the prairie provinces; confirm against the actual
# shapefile you download, because column names have changed across CEC
# releases. Several CEC regions may share one key (a deliberate merge).
#
# ADD A REGION HERE and it exists everywhere — that is the point.
KEY_MAP = {
    "Boreal Plain":                        "boreal_mixedwood",
    "Aspen Parkland":                      "aspen_parkland",
    "Western Cordillera":                  "subalpine_montane",
    "Montane Cordillera":                  "subalpine_montane",
    "Temperate Prairies":                  "mixedgrass_prairie",
    "South Central Semi-Arid Prairies":    "mixedgrass_prairie",
    "Moist Mixed Grassland":               "moist_mixedgrass",
    "Western Interior Forested Mountains": "fescue_foothills",
}

# How each key is written for a person: (name, where it is). Name and place
# stay APART — see the note in the feature builder below. A key with no entry
# falls back to a title-cased version of itself and no place.
DISPLAY = {
    "aspen_parkland":     ("Aspen Parkland",           "central AB / SK"),
    "mixedgrass_prairie": ("Mixedgrass Prairie",       "south AB / SK"),
    "moist_mixedgrass":   ("Moist Mixed Grassland",    "Regina / Saskatoon"),
    "fescue_foothills":   ("Fescue / Foothills",       "SW Alberta"),
    "boreal_mixedwood":   ("Boreal Mixedwood / Plain", "north AB / SK"),
    "subalpine_montane":  ("Subalpine / Montane",      "the mountains"),
}


def _require_dev_deps():
    missing = []
    try:
        import fiona  # noqa: F401
    except ImportError:
        missing.append("fiona")
    try:
        import shapely  # noqa: F401
    except ImportError:
        missing.append("shapely")
    try:
        import pyproj  # noqa: F401
    except ImportError:
        missing.append("pyproj")
    if missing:
        print(
            "Missing dev-only dependencies: " + ", ".join(missing) + "\n"
            "Install with:\n"
            "    pip install " + " ".join(missing) + "\n\n"
            "These are NOT in requirements.txt — they're only needed when "
            "regenerating ecoregions_canada.geojson from the CEC shapefile."
        )
        return False
    return True


def regenerate(shapefile_path: Path, key_map: dict[str, str]) -> int:
    """Build a fresh GeoJSON FeatureCollection from the CEC shapefile.
    ``key_map`` maps CEC Level III ecoregion names → canonical keys
    in ``_AB_ECOREGION_CHOICES``. Unmapped names are skipped with a
    warning."""
    if not _require_dev_deps():
        return 1

    import fiona
    from shapely.geometry import shape, mapping
    from shapely.ops import transform, unary_union
    from pyproj import Transformer

    if not shapefile_path.exists():
        print(f"Shapefile not found: {shapefile_path}")
        return 1

    # Per-canonical-key list of polygons we'll union at the end.
    by_key: dict[str, list] = {}

    with fiona.open(shapefile_path) as src:
        src_crs = src.crs
        transformer = Transformer.from_crs(src_crs, "EPSG:4326", always_xy=True)
        project = lambda x, y, z=None: transformer.transform(x, y)
        for rec in src:
            name = (rec["properties"].get("NA_L3NAME")
                    or rec["properties"].get("L3_KEY") or "").strip()
            canonical = key_map.get(name)
            if not canonical:
                continue
            geom = shape(rec["geometry"])
            geom_ll = transform(project, geom)
            # Clip to Alberta envelope for file-size sanity.
            from shapely.geometry import box
            clipped = geom_ll.intersection(box(*AB_BBOX))
            if not clipped.is_empty:
                by_key.setdefault(canonical, []).append(clipped)

    features = []
    for sort, (key, polys) in enumerate(by_key.items()):
        merged = unary_union(polys)
        merged = merged.simplify(0.01, preserve_topology=True)
        name, where = DISPLAY.get(key, (key.replace("_", " ").title(), ""))
        features.append({
            "type": "Feature",
            # key/name/where/sort ARE the app's vocabulary (V2.38) — name and
            # where are kept APART on purpose: packed into one label they
            # elided mid-word in the filter dropdown ("Moist Mixed Gras...ina
            # (Saskatoon)"), losing both the ecoregion and the geography.
            "properties": {
                "key": key, "name": name, "where": where, "sort": sort,
                "label": f"{name} ({where})" if where else name,
            },
            "geometry": mapping(merged),
        })

    out = {
        "type": "FeatureCollection",
        "name": "Ecoregions (CEC Level III)",
        "crs":  "WGS84",
        "comment": "Generated by scripts/prepare_ecoregions.py from the "
                   "CEC Level III Ecoregions of North America shapefile. "
                   "Each feature's key/name/where/sort ARE the app's "
                   "geographic ecoregion vocabulary (V2.38) — src/ecoregion.py "
                   "reads them, so adding a region means adding a polygon here "
                   "and nothing else.",
        "features": features,
    }
    OUTPUT_PATH.write_text(json.dumps(out, indent=2) + "\n", encoding="utf-8")
    print(f"Wrote {len(features)} feature(s) to {OUTPUT_PATH.relative_to(PROJECT_ROOT)}")
    return 0


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument(
        "--shapefile", type=Path, required=False,
        help="Path to the CEC Level III ecoregions .shp file. "
             "If omitted, just prints the docs.",
    )
    args = p.parse_args(argv)
    if args.shapefile is None:
        print(__doc__)
        return 0
    return regenerate(args.shapefile, KEY_MAP)


if __name__ == "__main__":
    sys.exit(main())
