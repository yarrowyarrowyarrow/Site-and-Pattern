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

#: A subregion piece smaller than this share of *both* the ecoregion it sits in
#: and the subregion it belongs to loses its subregion label.
#:
#: Two independently digitised layers do not agree along their edges, so
#: intersecting them produces slivers that are artefacts of the mismatch rather
#: than facts about the ground. The first adoption carried 44 pieces under
#: 500 km2 out of 115, including **Aspen Parkland x Subalpine at 17.6 km2** —
#: the parkland does not contain subalpine, that is two boundaries missing each
#: other by a few hundred metres over a long shared edge.
#:
#: The geometry is kept and only the *label* is dropped, so the piece merges
#: back into its ecoregion. Deleting the sliver instead would punch a hole in
#: the layer and fail the coverage check for a good reason: the ground is still
#: there, it is the claim about it that was never real.
_MIN_SUBREGION_SHARE = 0.01


def slug(name: str) -> str:
    """``"Mid-Boreal Uplands"`` -> ``"mid_boreal_uplands"``.

    The app's keys are snake_case identifiers that end up in a database column,
    a filter value and a URL path on the website, so they cannot carry spaces,
    hyphens or case.
    """
    return re.sub(r"[^a-z0-9]+", "_", (name or "").lower()).strip("_")


def _where(geometry, province_hint: str) -> str:
    """A short place hint for the dropdown's second line.

    Derived from the geometry rather than written by hand, so twenty-four of
    them cannot quietly disagree with the map. Coarse on purpose: this is the
    line under a name in a filter list, not a locality.

    **Computed for the whole region, never one piece of it.** Each ecoregion is
    exported as several polygons (one per Alberta subregion), the app
    de-duplicates the vocabulary by key and keeps the *first* piece's label, and
    the first piece is whichever happened to sort first. Aspen Parkland — which
    arcs from Calgary through Edmonton and east past North Battleford — came out
    labelled "south AB / SK" because a southern fragment led the list.
    """
    lat = geometry.centroid.y
    band = "north" if lat >= 55.5 else "central" if lat >= 51.5 else "south"
    return f"{band} {province_hint}" if province_hint else band


def _provinces_for(geom, provinces) -> str:
    """Which of the two provinces a region actually reaches, as "AB" / "SK" /
    "AB / SK". Measured, not assumed: several ELC regions cross the border and
    several stop well short of it."""
    hit = [code for code, shape in provinces.items()
           if geom.intersects(shape) and geom.intersection(shape).area > 1e-4]
    return " / ".join(sorted(hit))


def _drop_sliver_subregions(regions):
    """Blank ``ab_subregion`` on pieces too small to be a real claim.

    Reported rather than silent: how many labels a boundary mismatch invented
    is worth knowing, and it is the number that would change if either source
    were re-digitised.
    """
    from tools.ecoregions.common import CRS_PROJECTED             # noqa: PLC0415

    regions = regions.copy()
    regions["_km2"] = regions.to_crs(CRS_PROJECTED).area / 1e6
    by_region = regions.groupby("ecoregion")["_km2"].sum()
    labelled = regions["ab_subregion"].fillna("").astype(bool)
    by_sub = regions[labelled].groupby("ab_subregion")["_km2"].sum()

    dropped = []
    for idx, row in regions.iterrows():
        sub = str(row.get("ab_subregion") or "")
        if not sub:
            continue
        region_share = row["_km2"] / max(by_region.get(row["ecoregion"], 1.0), 1e-9)
        sub_share = row["_km2"] / max(by_sub.get(sub, 1.0), 1e-9)
        if region_share < _MIN_SUBREGION_SHARE and sub_share < _MIN_SUBREGION_SHARE:
            dropped.append((row["ecoregion"], sub, row["_km2"]))
            regions.at[idx, "ab_subregion"] = ""
    if dropped:
        print(f"  {len(dropped)} sliver subregion label(s) dropped as edge "
              f"artefacts (geometry kept):")
        for name, sub, km2 in sorted(dropped, key=lambda d: d[2])[:6]:
            print(f"      {km2:8.1f} km2  {name} x {sub}")
        if len(dropped) > 6:
            print(f"      ... and {len(dropped) - 6} more")
    return regions.drop(columns=["_km2"])


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

    regions = _drop_sliver_subregions(regions)

    # One feature per (ecoregion, subregion) piece, as exported. The app
    # de-duplicates by key, so several pieces of one region is fine and is how
    # the old file already worked.
    features, seen, where_for = [], {}, {}
    merged = regions.dissolve(by="ecoregion", as_index=False)
    for _, row in merged.iterrows():
        name = str(row["ecoregion"])
        seen[name] = str(row.get("ecozone") or "")
        # One label per region, from the region's whole geometry.
        where_for[name] = _where(row.geometry,
                                 _provinces_for(row.geometry, provinces))
    # How much of each Alberta subregion this piece accounts for.
    #
    # **The subregions are not a third tier of the ELC tree and the app must
    # not assume they are.** Measured here: 12 of 21 sit ≥90% inside one
    # ecoregion, but Montane is 42% Northern Continental Divide, Central
    # Mixedwood is 31% Mid-Boreal Uplands across NINE ecoregions, and Athabasca
    # Plain is 47% of its namesake. The Alberta framework and ELC are two
    # classifications of the same ground that agree in most places and cross
    # each other in the mountains and the mid-boreal.
    #
    # Shipping the share means the website can say "this subregion is 42% of
    # that ecoregion" instead of picking a parent and being wrong four times in
    # twenty-one. It is computed here because the area maths needs an equal-area
    # projection and geopandas, and neither ships with the app.
    from tools.ecoregions.common import CRS_PROJECTED         # noqa: PLC0415

    areas = regions.assign(_a=regions.to_crs(CRS_PROJECTED).geometry.area)
    sub_total = (areas[areas["ab_subregion"].astype(str) != ""]
                 .groupby("ab_subregion")["_a"].sum().to_dict())
    for (_, row), area in zip(regions.iterrows(), areas["_a"]):
        name = str(row["ecoregion"])
        zone = str(row.get("ecozone") or "")
        sub = str(row.get("ab_subregion") or "")
        try:
            order = _ZONE_ORDER.index(zone)
        except ValueError:
            order = len(_ZONE_ORDER)
        features.append({
            "type": "Feature",
            "properties": {
                "key": slug(name),
                "name": name,
                "where": where_for.get(name, ""),
                "sort": order * 100 + sorted(seen).index(name),
                "ecozone": zone,
                "ab_subregion": sub,
                "sub_share": (round(area / sub_total[sub], 4)
                              if sub and sub_total.get(sub) else None),
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
        "  2. Move the ab_ecoregion tags in data/plants_master.json onto the",
        "     new vocabulary - BY MEASUREMENT, never by matching the names:",
        "         python scripts/migrate_ecoregion_tags.py --report",
        "         python scripts/migrate_ecoregion_tags.py",
        "     --report prints the mapping and writes nothing; run it first.",
        "     It intersects each old polygon with the new layer and keeps the",
        "     claim at the level that actually accounts for it - the ecoregion,",
        "     else the ecozone, else nothing. Do not skip to writing the",
        "     mapping out by hand: V2.67's plan did exactly that and got one of",
        "     its four 'obvious renames' right. Three of the six old regions",
        "     were MISPLACED rather than merely coarse.",
        "",
        "  3. Bump _SCHEMA_VERSION in src/db/plants.py, or no existing install",
        "     ever reseeds and none of this reaches a user.",
        "",
        "  4. Run the suite. The city lookups in tests/test_ecoregion.py are",
        "     calibrated against the old rectangles and will need updating to",
        "     the real answers - which stage 4 has already verified.",
        "",
        "  5. Check what the drawings SAY about themselves. src.ecoregion_map",
        "     .CAVEAT travels with every map on the website, and it spent all",
        "     of V2.67 calling this surveyed layer hand-traced. Its test now",
        "     compares it against this file's own provenance line, so a future",
        "     source change fails loudly instead of publishing a stale claim.",
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
