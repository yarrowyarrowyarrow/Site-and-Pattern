#!/usr/bin/env python3
"""Move the ``ab_ecoregion`` tags onto the surveyed vocabulary — by measurement.

    python scripts/migrate_ecoregion_tags.py --report     # print, change nothing
    python scripts/migrate_ecoregion_tags.py

V2.67 replaced six hand-traced regions with twenty-four surveyed ones. The
heuristic ``ab_ecoregion`` tags in ``data/plants_master.json`` name the old six,
of which exactly one key survives, so every other tag points at a region that no
longer exists.

WHY THIS IS MEASURED AND NOT DECIDED
-------------------------------------------------------------------------------
The obvious approach is to sit down with the two name lists and write a mapping.
It would even be mostly right — ``mixedgrass_prairie`` is clearly Mixed
Grassland. But "mostly right" is how ``fescue_foothills`` gets mapped, and that
key was a *conflation*: its polygon covered both fescue grassland and forested
foothills, which the survey separates into different ecoregions in different
ecozones. A name-based mapping cannot see that, and would quietly assert
whichever half the author happened to think of.

So the mapping comes from the polygons. The old file is still in git; this
reads it, intersects each old region with the new layer, and asks how the old
claim actually distributes. That is the same discipline the pipeline used to
join Alberta's subregions to ELC — spatial overlap, never name matching — and
for the same reason.

WHAT THE MEASUREMENT ACTUALLY FOUND
-------------------------------------------------------------------------------
Not what was expected. The old regions were assumed to be *coarser* than the
survey — one old key covering several new ones — in which case each tag could
rise to the level that matched its precision, and the three-level vocabulary
would carry all of it losslessly.

Three of the six turned out to be **misplaced** rather than coarse:

    subalpine_montane   best overlap 19% (Western Alberta Upland). The old
                        montane strip barely touches the actual mountains.
    aspen_parkland      40% Aspen Parkland, 33% Boreal Transition — the arc
                        was drawn too far north.
    moist_mixedgrass    39% Moist Mixed Grassland, 36% Aspen Parkland.

For those, rising to the ecozone does not rescue the tag, it disguises the
error: `subalpine_montane` would become Boreal Plains, which is not a coarse
description of an alpine plant but a wrong one.

So the rule is: take the ecoregion when one accounts for two thirds of the old
area, else the ecozone on the same test, else **clear the tag**. Three migrate,
three are dropped.

Dropping costs little and is the honest option. `scripts/seed_ecoregion_ranges.py`
derives ranges for 427 of 432 species straight from occurrence records against
the correct polygons — evidence, where these were inference — and the heuristic
tag was always the weaker fallback that derived rows override. Keeping a wrong
tag because it is the only one available is how false precision gets into a
database, and this repository has the scar to prove it.

The ecozone level is still what makes the two partial cases survivable, and it
only exists because the author asked for the three-level filter. Before that the
choices were fan out (false) or drop (lossy) with nothing in between.
"""

from __future__ import annotations

import argparse
import json
import pathlib
import subprocess
import sys

PROJECT_ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

MASTER = PROJECT_ROOT / "data" / "plants_master.json"
#: The commit whose ``data/ecoregions_canada.geojson`` holds the six hand-traced
#: regions. V2.66 is the last release before adoption.
OLD_REF = "V2.66"

#: A surveyed unit taking at least this share of an old region's area is taken
#: to *be* that region renamed. Tried at the ecoregion level first, then at the
#: ecozone; if neither commands it, the old tag is not migratable and is cleared.
#:
#: Two thirds rather than a half: at a half, a region split 51/49 would be
#: recorded as one of them, which is a coin toss wearing a measurement's
#: clothes.
_DOMINANT = 0.66

#: **Why clearing is a real outcome and not a failure to try harder.**
#:
#: The measurement showed the old polygons were not merely coarser than the
#: survey — three of the six were substantially *misplaced*:
#:
#:     subalpine_montane   19% Western Alberta Upland, 16% Eastern Continental
#:                         Ranges. The old montane strip barely overlaps the
#:                         actual mountains; it was drawn east of the relief.
#:     aspen_parkland      40% Aspen Parkland but 33% Boreal Transition — the
#:                         arc was drawn too far north.
#:     moist_mixedgrass    39% Moist Mixed Grassland and 36% Aspen Parkland.
#:
#: Falling back to the ecozone does not rescue those. It makes them worse in a
#: way that is harder to see: `subalpine_montane` would become Boreal Plains,
#: which is not a coarse description of an alpine plant, it is a wrong one, and
#: `aspen_parkland` would become Boreal Plains at 54% against 46% Prairies —
#: a coin toss reported as a fact.
#:
#: So a tag that no unit at any level can account for is dropped. That costs
#: little and is honest: `scripts/seed_ecoregion_ranges.py` derives ranges for
#: 427 of the 432 species directly from occurrence records against the correct
#: polygons, and those are evidence rather than inference. The heuristic tag was
#: always the weaker fallback; keeping a wrong one because it is all we have is
#: how false precision gets into a database.


def _old_polygons():
    """The pre-adoption polygon file, read out of git history."""
    try:
        blob = subprocess.run(
            ["git", "show", f"{OLD_REF}:data/ecoregions_canada.geojson"],
            cwd=PROJECT_ROOT, capture_output=True, text=True, check=True, encoding="utf-8").stdout
    except (subprocess.CalledProcessError, FileNotFoundError) as exc:
        raise SystemExit(
            f"Could not read the old polygons from {OLD_REF}.\n"
            f"  git show {OLD_REF}:data/ecoregions_canada.geojson\n"
            f"  {exc}\n"
            "Without them this would have to guess the mapping from names, "
            "which is the thing it exists not to do.") from exc
    return json.loads(blob)


def build_mapping(*, verbose: bool = True) -> dict:
    """``{old_key: [new_key, ...]}``, measured by area of overlap."""
    try:
        import geopandas as gpd
        from shapely.geometry import shape
    except ImportError:
        raise SystemExit(
            "This needs geopandas and shapely (dev-only):\n"
            "    pip install geopandas shapely pyogrio")
    from tools.ecoregions.common import CRS_PROJECTED, CRS_WGS84, repair
    from src.ecoregion_tree import level_of                       # noqa: PLC0415

    old_raw = _old_polygons()
    rows = []
    for feature in old_raw.get("features") or []:
        key = ((feature.get("properties") or {}).get("key") or "").strip()
        if key:
            rows.append({"old": key, "geometry": shape(feature["geometry"])})
    old = repair(gpd.GeoDataFrame(rows, crs=CRS_WGS84), "old polygons")
    old = old.dissolve(by="old", as_index=False).to_crs(CRS_PROJECTED)

    new = gpd.read_file(PROJECT_ROOT / "data" / "ecoregions_canada.geojson")
    new = new[["key", "name", "ecozone", "geometry"]].rename(
        columns={"key": "new"})
    new = repair(new, "new polygons").to_crs(CRS_PROJECTED)

    pieces = gpd.overlay(old, new, how="intersection", keep_geom_type=True)
    pieces["km2"] = pieces.geometry.area / 1e6
    totals = old.assign(km2=old.geometry.area / 1e6).set_index("old")["km2"]

    mapping: dict = {}
    for old_key, group in pieces.groupby("old"):
        by_region = (group.groupby(["new", "ecozone"])["km2"].sum()
                     .sort_values(ascending=False))
        total = float(totals.get(old_key, group["km2"].sum()) or 1.0)
        from src.ecoregion_tree import zone_key                    # noqa: PLC0415

        (top_region, _zone), top_km2 = by_region.index[0], by_region.iloc[0]
        region_share = top_km2 / total
        zones = group.groupby("ecozone")["km2"].sum().sort_values(
            ascending=False)
        zone_share = zones.iloc[0] / total

        if region_share >= _DOMINANT:
            mapping[old_key] = [top_region]
            level = "ecoregion"
            why = f"{region_share:.0%} of it is {top_region}"
        elif zone_share >= _DOMINANT:
            mapping[old_key] = [zone_key(zones.index[0])]
            level = "ecozone"
            why = (f"no single ecoregion dominates (best {top_region} at "
                   f"{region_share:.0%}) but {zone_share:.0%} is "
                   f"{zones.index[0]}")
        else:
            mapping[old_key] = []
            level = "DROPPED"
            why = (f"best ecoregion {top_region} at {region_share:.0%}, best "
                   f"ecozone {zones.index[0]} at {zone_share:.0%} — the old "
                   f"polygon was misplaced, not merely coarse")
        if verbose:
            target = mapping[old_key][0] if mapping[old_key] else "(cleared)"
            print(f"  {old_key:20} -> {target:24} [{level}]")
            print(f"       {why}")
        bad = [k for k in mapping[old_key] if not level_of(k)]
        if bad:
            raise SystemExit(f"{old_key} mapped to {bad}, which is not in the "
                             f"vocabulary. Refusing to write a dead tag.")
    return mapping


def apply_mapping(mapping: dict, *, report: bool = False) -> int:
    data = json.loads(MASTER.read_text(encoding="utf-8"))
    rows = data if isinstance(data, list) else data.get("plants", data)

    changed, unmapped, cleared = 0, {}, 0
    for plant in rows:
        raw = (plant.get("ab_ecoregion") or "").strip()
        if not raw:
            continue
        out: list = []
        for key in [k.strip() for k in raw.split(",") if k.strip()]:
            if key in mapping:
                for new_key in mapping[key]:
                    if new_key not in out:
                        out.append(new_key)
            else:
                # Moisture niches and anything already migrated pass through.
                if key not in out:
                    out.append(key)
                    if key not in ("riparian", "wet_meadow"):
                        unmapped[key] = unmapped.get(key, 0) + 1
        new_value = ",".join(out)
        if new_value != raw:
            changed += 1
            if not report:
                plant["ab_ecoregion"] = new_value
        if not out:
            cleared += 1

    print(f"\n  {changed} plant(s) retagged"
          + (f", {cleared} cleared" if cleared else ""))
    if unmapped:
        print("  keys with no mapping, left as they were:")
        for key, count in sorted(unmapped.items()):
            print(f"      {key} ({count} plants)")
    if report:
        print("\n  --report: nothing written.")
        return 0
    MASTER.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n",
                      encoding="utf-8")
    print(f"  wrote {MASTER.relative_to(PROJECT_ROOT)}")
    print("\n  Bump _SCHEMA_VERSION in src/db/plants.py so installs reseed.")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--report", action="store_true",
                        help="print the mapping and the counts, write nothing")
    args = parser.parse_args(argv)
    print("Measuring the old regions against the surveyed layer\n")
    mapping = build_mapping()
    return apply_mapping(mapping, report=args.report)


if __name__ == "__main__":
    sys.exit(main())
