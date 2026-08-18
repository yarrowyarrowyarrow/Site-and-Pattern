"""Stage 7 — put the harmonized layer into the app.

    python -m tools.ecoregions.adopt --dry-run     # report, write nothing
    python -m tools.ecoregions.adopt

Converts ``out/ecoregions_app.geojson`` into the shape ``src/ecoregion.py``
reads, and writes it to ``data/ecoregions_canada.geojson``.

WHY THIS IS A SEPARATE STAGE FROM export
-------------------------------------------------------------------------------
Because it is the one step with consequences for somebody's actual garden.
Stages 1 to 6 produce files; this one changes which plants the application
recommends for a real site. The rebuild brief scoped it out of the first run for
that reason, and it stays behind its own command so that running the pipeline
can never do it as a side effect.

WHAT REPLACING THE FILE DOES, AND WHY THAT IS THE WHOLE JOB
-------------------------------------------------------------------------------
``src/ecoregion.py`` was built so that **the polygon file is the vocabulary**:

    "adding a region means adding a polygon and nothing else"

So the filter dropdown, the data validator's accepted keys, the site panel's
detection and the per-species range tags all follow from this one file. That
design decision, made in V2.38 for a different reason, is what makes a
six-region-to-twenty-four-region change tractable at all.

WHAT IT DOES NOT DO, AND MUST NOT
-------------------------------------------------------------------------------
It does not touch ``data/plant_ecoregions.json`` or the ``ab_ecoregion`` tags in
``data/plants_master.json``. Both are keyed to the old six-region vocabulary,
and both have to be **re-derived** against the new polygons rather than
translated onto them.

Translating is the tempting shortcut and it manufactures evidence. A species
recorded in the old ``boreal_mixedwood`` rectangle would fan out to all nine
Boreal Plains ecoregions, asserting nine occurrences where the data supports
one region. This project's rule is the opposite (P9): a range comes from
occurrence records or it is not claimed. ``scripts/seed_ecoregion_ranges.py``
re-runs against whatever polygons are shipped, which is exactly the tool for
this — it just needs a few hours and a network.

Until that re-run, species keep no derived ranges under the new keys, and the
filter honestly returns nothing rather than a guess. ``--dry-run`` prints the
size of that gap before you commit to it.
"""

from __future__ import annotations

import argparse
import json
import re
import sys

from tools.ecoregions.common import OUT, REPO, repair, require
from tools.ecoregions.export import GEOJSON_APP

TARGET = REPO / "data" / "ecoregions_canada.geojson"

#: Display order for the dropdown: by system, south to north, mountains last.
#: A reader scanning a 24-item list needs it grouped by something, and the
#: ecozone is the same thing the colours encode.
_ZONE_ORDER = ("Prairies", "Boreal Plains", "Boreal Shield", "Taiga Plains",
               "Taiga Shield", "Montane Cordillera")


def slug(name: str) -> str:
    """``"Mid-Boreal Uplands"`` -> ``"mid_boreal_uplands"``.

    The app's keys are snake_case identifiers that end up in a database column,
    a filter value and a URL path on the website, so they cannot carry spaces,
    hyphens or case.
    """
    return re.sub(r"[^a-z0-9]+", "_", (name or "").lower()).strip("_")


def _where(geometry, province_hint: str) -> str:
    """A short place hint for the dropdown's second line.

    Derived from the polygon's own centroid rather than written by hand, so
    twenty-four of them cannot quietly disagree with the geometry. Coarse on
    purpose: this is the line under the name in a filter list, not a locality.
    """
    lon, lat = geometry.centroid.x, geometry.centroid.y
    north = "north" if lat >= 55.5 else "central" if lat >= 51.5 else "south"
    return f"{north} {province_hint}" if province_hint else north


def _provinces_for(geom, provinces) -> str:
    """Which of the two provinces a region actually reaches, as "AB" / "SK" /
    "AB / SK". Measured, not assumed: several ELC regions cross the border and
    several stop well short of it."""
    hit = [code for code, shape in provinces.items()
           if geom.intersects(shape) and geom.intersection(shape).area > 1e-4]
    return " / ".join(sorted(hit))


def build(*, dry_run: bool = False) -> int:
    require("geopandas", "shapely")
    import geopandas as gpd

    if not GEOJSON_APP.exists():
        raise SystemExit(
            f"{GEOJSON_APP} does not exist.\n"
            "  Run:  python -m tools.ecoregions.export")
    # Repaired on the way in as well as on the way out: an export written
    # before that check existed is still sitting on somebody's disk.
    regions = repair(gpd.read_file(GEOJSON_APP), "exported layer")

    base = gpd.read_file(REPO / "data" / "basemap_prairie.geojson")
    subject = base[(base["layer"] == "province")
                   & base["subject"].fillna(False).astype(bool)]
    provinces = {row["code"]: row.geometry for _, row in subject.iterrows()}

    # One feature per (ecoregion, subregion) piece, as exported. The app
    # de-duplicates by key, so several pieces of one region is fine and is how
    # the old file already worked.
    features, seen = [], {}
    merged = regions.dissolve(by="ecoregion", as_index=False)
    for _, row in merged.iterrows():
        name = str(row["ecoregion"])
        seen[name] = str(row.get("ecozone") or "")
    for _, row in regions.iterrows():
        name = str(row["ecoregion"])
        zone = str(row.get("ecozone") or "")
        try:
            order = _ZONE_ORDER.index(zone)
        except ValueError:
            order = len(_ZONE_ORDER)
        features.append({
            "type": "Feature",
            "properties": {
                "key": slug(name),
                "name": name,
                "where": _where(row.geometry, _provinces_for(row.geometry,
                                                            provinces)),
                "sort": order * 100 + sorted(seen).index(name),
                "ecozone": zone,
                "ab_subregion": str(row.get("ab_subregion") or ""),
            },
            "geometry": json.loads(gpd.GeoSeries([row.geometry]).to_json(
            ))["features"][0]["geometry"],
        })

    payload = {
        "type": "FeatureCollection",
        "name": "Ecoregions of Alberta and Saskatchewan (ELC v2.2)",
        "comment": (
            "National Ecological Framework for Canada v2.2 terrestrial "
            "ecoregions (Ecological Stratification Working Group 1995; "
            "Agriculture and Agri-Food Canada), clipped to Alberta and "
            "Saskatchewan, with the Alberta natural subregion attached by "
            "spatial overlap (Natural Regions Committee 2006). Generated by "
            "tools/ecoregions; see tools/ecoregions/README.md. These are "
            "digitised boundaries from a published survey, not the "
            "hand-traced approximations this file used to hold."),
        "features": features,
    }

    keys = sorted({f["properties"]["key"] for f in features})
    print(f"  {len(features)} polygons, {len(keys)} distinct regions")
    for zone in _ZONE_ORDER:
        names = sorted({f["properties"]["name"] for f in features
                        if f["properties"]["ecozone"] == zone})
        if names:
            print(f"    {zone}: {', '.join(names)}")

    _report_stale_keys(keys)

    if dry_run:
        print("\n  --dry-run: nothing written.")
        return 0
    TARGET.write_text(json.dumps(payload, separators=(",", ":")) + "\n",
                      encoding="utf-8")
    print(f"\n  wrote {TARGET.relative_to(REPO)}  "
          f"({TARGET.stat().st_size / 1e6:.2f} MB)")
    print(_next_steps())
    return 0


def _report_stale_keys(new_keys: list) -> None:
    """How much range evidence the vocabulary change orphans.

    Printed before anything is written, because it is the number that decides
    whether this is a good idea today or after the seeder has re-run.
    """
    path = REPO / "data" / "plant_ecoregions.json"
    if not path.exists():
        return
    data = json.loads(path.read_text(encoding="utf-8"))
    species = data.get("species") or {}
    old_keys, rows = set(), 0
    for entry in species.values():
        for row in (entry if isinstance(entry, list) else entry.get("regions", [])):
            key = row.get("ecoregion") if isinstance(row, dict) else row
            if key:
                old_keys.add(key)
                rows += 1
    orphaned = sorted(k for k in old_keys if k not in new_keys)
    print(f"\n  data/plant_ecoregions.json: {len(species)} species, "
          f"{rows} derived range rows")
    if orphaned:
        print(f"  {len(orphaned)} of its region keys do not exist in the new "
              f"vocabulary:")
        print(f"    {', '.join(orphaned)}")
        print("  Those rows stop matching. They are NOT translated onto the new "
              "regions:")
        print("  a species recorded in the old boreal_mixedwood rectangle would "
              "become")
        print("  nine claims where the evidence supports one. Re-derive instead:")
        print("    python scripts/seed_ecoregion_ranges.py")


def _next_steps() -> str:
    return "\n".join([
        "",
        "=" * 74,
        "  WHAT STILL HAS TO HAPPEN",
        "=" * 74,
        "",
        "  1. Re-derive the per-species ranges against the new polygons:",
        "         python scripts/seed_ecoregion_ranges.py",
        "     Hours, and it needs a network. Until it finishes, species have no",
        "     derived range under the new keys and the filter says so honestly",
        "     rather than guessing.",
        "",
        "  2. The ab_ecoregion tags in data/plants_master.json still name the",
        "     old six regions. They are the fallback the derived rows override,",
        "     so they go stale rather than wrong - but they should be cleared or",
        "     re-derived once step 1 has run.",
        "",
        "  3. Bump _SCHEMA_VERSION in src/db/plants.py, or no existing install",
        "     ever reseeds and none of this reaches a user.",
        "",
        "  4. Run the suite. The city lookups in tests/test_ecoregion.py are",
        "     calibrated against the old rectangles and will need updating to",
        "     the real answers - which stage 4 has already verified.",
        "=" * 74,
    ])


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--dry-run", action="store_true",
                        help="report what would change, write nothing")
    args = parser.parse_args(argv)
    return build(dry_run=args.dry_run)


if __name__ == "__main__":
    sys.exit(main())
