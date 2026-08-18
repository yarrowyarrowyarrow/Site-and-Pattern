"""Stage 3 — one framework as geometry, the other as an attribute.

    python -m tools.ecoregions.harmonize

Reads the ELC ecoregions and ecozones plus the Alberta subregions, clips to
Alberta and Saskatchewan, attaches the Alberta subregion to each ELC polygon by
*spatial* overlap, and writes ``out/ecoregions.gpkg`` plus a crosswalk table.

WHY ELC IS THE GEOMETRY AND ALBERTA IS AN ATTRIBUTE
-------------------------------------------------------------------------------
Because harmonisation is picking one vocabulary and publishing a crosswalk for
the other, and the previous attempts did neither. Their legends mixed Alberta's
Natural Regions vocabulary with Saskatchewan's national ELC vocabulary and added
invented terms on top, which is not a harmonised map, it is three maps printed
over each other.

ELC wins the geometry because it is national: it already spans both provinces
with one classification, so the Alberta/Saskatchewan border stops being a seam
in the legend. Alberta's subregions are real and finer, so they ride along as an
attribute — which is what lets the render carry more detail inside Alberta than
either attempt managed, without two frameworks fighting over the same polygon.

THE JOIN IS SPATIAL, NEVER BY NAME
-------------------------------------------------------------------------------
This is the single most dangerous shortcut available here, so it is worth being
blunt about. **"Athabasca Plain" is a unit in both frameworks and they are not
the same place.** In ELC it is the sand plain south of Lake Athabasca on the
Canadian Shield; in Alberta's classification the similar name attaches to
different ground. Joining on the string would silently corrupt the northeast —
silently, because the output would still be a valid file full of plausible
names, and the error would only surface as bad plant recommendations for
somebody in Fort Chipewyan.

So the join is by area of overlap, and ``validate`` refuses a build where any
polygon's subregion was assigned from anything other than geometry.
"""

from __future__ import annotations

import argparse
import json
import sys

from tools.ecoregions.common import (CRS_PROJECTED, CRS_WGS84, DATA, OUT,
                                     SUBJECT_PROVINCES, ensure_dirs, require)

_RAW = DATA / "raw"
GPKG = OUT / "ecoregions.gpkg"
CROSSWALK = OUT / "crosswalk.csv"

#: The real column names, **verified against the actual downloads** by stage 2
#: on 2026-08-17, not guessed. A key left as "" makes this stage stop and tell
#: you to run stage 2 rather than quietly picking a column that looks about
#: right.
#:
#: What stage 2 found, and what it says about guessing:
#:
#:   * The AAFC ecoregion/ecozone names carry an ``_EN`` suffix, because the
#:     files are bilingual and ship a ``_FR`` column beside each one. Every
#:     guess that reached for ``ECOREGION_NAME`` missed by exactly that suffix.
#:   * Alberta's ``NSRNAME`` and ``NRNAME`` were guessed **correctly** in the
#:     rebuild brief. Worth recording: the rule is not that guesses are always
#:     wrong, it is that you cannot tell which ones are without looking.
#:   * ``ECOREGION_ID`` is 194 distinct across 218 polygons, so it is a
#:     classification id and not a row id. ``OBJECTID`` is the row id.
FIELDS = {
    "elc_ecoregion_name": "ECOREGION_NAME_EN",
    "elc_ecoregion_id": "ECOREGION_ID",
    "elc_ecozone_name": "ECOZONE_NAME_EN",
    "elc_ecozone_id": "ECOZONE_ID",
    # Alberta: subregion (21 values) and its parent natural region (6).
    "ab_subregion": "NSRNAME",
    "ab_region": "NRNAME",
}


def _resolve(gdf, wanted: str, source_label: str) -> str:
    """The real column for ``wanted``, or a hard stop naming what is there.

    Case-insensitive, because portals are inconsistent about it and a case
    mismatch is not the kind of error worth failing a whole run over.
    """
    if not wanted:
        raise SystemExit(
            f"No column configured for {source_label}.\n"
            f"  Run:  python -m tools.ecoregions.inspect_schema\n"
            f"  then fill in FIELDS in tools/ecoregions/harmonize.py.\n"
            f"  Columns available: {sorted(c for c in gdf.columns if c != 'geometry')}")
    lookup = {c.lower(): c for c in gdf.columns}
    if wanted.lower() in lookup:
        return lookup[wanted.lower()]
    raise SystemExit(
        f"{source_label}: no column {wanted!r}.\n"
        f"  Columns available: {sorted(c for c in gdf.columns if c != 'geometry')}\n"
        f"  Nothing was guessed. Run stage 2 and correct FIELDS.")


def _subject_boundary():
    """Alberta and Saskatchewan as one polygon, from Natural Earth.

    Used to clip the national datasets. Natural Earth rather than the ELC file's
    own extent because the ELC polygons cross provincial borders (ecoregions do
    not stop at survey lines) and this layer only claims two provinces.
    """
    import geopandas as gpd

    gdf = gpd.read_file(_RAW / "ne_10m_admin_1_states_provinces.shp")
    lookup = {c.lower(): c for c in gdf.columns}
    name = lookup["name"]
    subject = gdf[gdf[name].isin(SUBJECT_PROVINCES)]
    if len(subject) != len(SUBJECT_PROVINCES):
        raise SystemExit(
            f"Expected {len(SUBJECT_PROVINCES)} subject provinces in Natural "
            f"Earth, found {len(subject)}: {sorted(subject[name])}")
    return subject.to_crs(CRS_WGS84).geometry.union_all()


def _load_elc():
    import geopandas as gpd

    path = _RAW / "nef_ca_ter_ecoregion_v2_2.geojson"
    if not path.exists():
        raise SystemExit(
            f"{path.name} is not downloaded.\n"
            "  Run:  python -m tools.ecoregions.fetch")
    gdf = gpd.read_file(path)
    if gdf.crs is None:
        raise SystemExit(f"{path.name} has no CRS. Refusing to assume one.")
    return gdf.to_crs(CRS_WGS84)


def _attach_ecozone(regions):
    """Ecozone name onto each ecoregion, by largest-overlap spatial join.

    The ecozone is what separates Boreal Shield from Boreal Plains and Taiga
    Shield, which is the largest single error in the second attempt: northern
    Saskatchewan and Alberta's northeast corner were drawn as undifferentiated
    boreal plain when they are Precambrian bedrock with thin soils, jack pine
    and lichen. Carrying the ecozone lets the render say so.
    """
    import geopandas as gpd

    path = _RAW / "nef_ca_ter_ecozone_v2_2.geojson"
    if not path.exists():
        print("  ecozone file absent; ecozone column will be blank")
        regions["ecozone"] = ""
        return regions
    zones = gpd.read_file(path).to_crs(CRS_WGS84)
    zone_name = _resolve(zones, FIELDS["elc_ecozone_name"], "ELC ecozone")
    zones = zones[[zone_name, "geometry"]].rename(
        columns={zone_name: "ecozone"})
    return _largest_overlap_join(regions, zones, "ecozone")


def _largest_overlap_join(left, right, column: str):
    """Give each ``left`` polygon the ``right`` value it overlaps most.

    Not ``sjoin(predicate="intersects")``, which duplicates a row per match and
    then keeps whichever happened to sort first. Not a centroid join either: a
    crescent's centroid can fall outside it, and the parkland is a crescent.
    Area of intersection is the only version of this that is defensible.
    """
    import geopandas as gpd
    import pandas as pd

    left_m = left.to_crs(CRS_PROJECTED).copy()
    left_m["_row"] = range(len(left_m))
    pieces = gpd.overlay(left_m[["_row", "geometry"]],
                         right.to_crs(CRS_PROJECTED),
                         how="intersection", keep_geom_type=True)
    if pieces.empty:
        left[column] = ""
        return left
    pieces["_area"] = pieces.geometry.area
    winner = (pieces.sort_values("_area", ascending=False)
                    .drop_duplicates("_row")[["_row", column]])
    merged = pd.DataFrame({"_row": range(len(left))}).merge(
        winner, on="_row", how="left")
    left[column] = merged[column].fillna("").values
    return left


def _attach_alberta(regions):
    """Alberta subregion and natural region, joined spatially.

    Returns ``(regions, crosswalk)``. The crosswalk is derived from the same
    overlap areas rather than from name matching, and carries the overlap
    fraction as its confidence so a reader can see which pairings are a clean
    nesting and which are a sliver.
    """
    import geopandas as gpd
    import pandas as pd

    # Whatever form Alberta arrived in. GeoJSON is what the ArcGIS service
    # yields, .shp is what a portal download would give, and .gdb is what the
    # brief expected; pyogrio reads all three, so the only thing that has to
    # vary is which name we look for.
    path = next((candidate for candidate in (
        _RAW / "alberta_natural_subregions.geojson",
        _RAW / "alberta_natural_subregions.shp",
        _RAW / "alberta_natural_subregions.gdb",
    ) if candidate.exists()), _RAW / "alberta_natural_subregions.geojson")
    if not path.exists():
        print("  Alberta subregions absent; ab_subregion column will be blank")
        regions["ab_subregion"] = ""
        regions["ab_region"] = ""
        return regions, pd.DataFrame(
            columns=["ab_subregion", "elc_ecoregion", "elc_ecozone",
                     "overlap_km2", "fraction_of_subregion", "confidence"])

    alberta = gpd.read_file(path)
    sub_col = _resolve(alberta, FIELDS["ab_subregion"], "Alberta subregions")
    reg_col = _resolve(alberta, FIELDS["ab_region"], "Alberta subregions")
    alberta = alberta[[sub_col, reg_col, "geometry"]].rename(
        columns={sub_col: "ab_subregion", reg_col: "ab_region"})
    alberta = alberta.to_crs(CRS_WGS84)

    regions = _largest_overlap_join(regions, alberta[["ab_subregion", "geometry"]],
                                    "ab_subregion")
    regions = _largest_overlap_join(regions, alberta[["ab_region", "geometry"]],
                                    "ab_region")

    # The crosswalk: every (subregion, ecoregion) pair that shares ground, with
    # how much of the subregion that pairing accounts for.
    pieces = gpd.overlay(
        alberta.to_crs(CRS_PROJECTED),
        regions[["ecoregion", "ecozone", "geometry"]].to_crs(CRS_PROJECTED),
        how="intersection", keep_geom_type=True)
    pieces["overlap_km2"] = pieces.geometry.area / 1e6
    totals = (alberta.to_crs(CRS_PROJECTED).assign(
        _a=lambda d: d.geometry.area / 1e6)
        .groupby("ab_subregion")["_a"].sum())
    walk = (pieces.groupby(["ab_subregion", "ecoregion", "ecozone"])
                  ["overlap_km2"].sum().reset_index())
    walk["fraction_of_subregion"] = walk.apply(
        lambda r: r["overlap_km2"] / totals.get(r["ab_subregion"], float("nan")),
        axis=1)
    walk["confidence"] = walk["fraction_of_subregion"].map(
        lambda f: "high" if f >= 0.75 else "medium" if f >= 0.35 else "low")
    walk = walk.sort_values(["ab_subregion", "overlap_km2"],
                            ascending=[True, False])
    return regions, walk


def run() -> int:
    require("geopandas", "shapely", "pyogrio")
    ensure_dirs()
    import geopandas as gpd

    print("Harmonizing (ELC geometry, Alberta subregions as an attribute)\n")
    elc = _load_elc()
    name_col = _resolve(elc, FIELDS["elc_ecoregion_name"], "ELC ecoregions")
    id_col = _resolve(elc, FIELDS["elc_ecoregion_id"], "ELC ecoregions")
    regions = elc[[name_col, id_col, "geometry"]].rename(
        columns={name_col: "ecoregion", id_col: "ecoregion_id"})
    print(f"  ELC ecoregions, national : {len(regions)}")

    boundary = _subject_boundary()
    regions = gpd.clip(regions, boundary)
    regions = regions[~regions.geometry.is_empty & regions.geometry.notna()]
    regions = regions.explode(index_parts=False).reset_index(drop=True)
    regions = regions.dissolve(by=["ecoregion", "ecoregion_id"],
                               as_index=False)
    print(f"  clipped to AB + SK       : {len(regions)}")

    regions = _attach_ecozone(regions)
    regions, walk = _attach_alberta(regions)

    regions = regions.set_crs(CRS_WGS84, allow_override=True)
    regions.to_file(GPKG, layer="ecoregions", driver="GPKG")
    walk.to_csv(CROSSWALK, index=False)
    print(f"\n  wrote {GPKG.name}   ({len(regions)} polygons)")
    print(f"  wrote {CROSSWALK.name} ({len(walk)} crosswalk rows)")
    print("\n  ecoregions present:")
    for name in sorted(regions["ecoregion"].dropna().unique()):
        zone = regions.loc[regions["ecoregion"] == name, "ecozone"].iloc[0]
        print(f"    {name}  ({zone})")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.parse_args(argv)
    return run()


if __name__ == "__main__":
    sys.exit(main())
