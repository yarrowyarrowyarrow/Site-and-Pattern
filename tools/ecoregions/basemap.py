"""Stage B — cut the shipped basemap out of Natural Earth 1:10m.

    python -m tools.ecoregions.basemap

Reads the Natural Earth downloads under ``data/raw`` and writes ONE small file,
``data/basemap_prairie.geojson`` in the repository, which the website's
ecoregion map draws underneath the ecoregion fills.

WHY THIS IS A SEPARATE STAGE FROM THE ECOREGION PIPELINE
-------------------------------------------------------------------------------
It does not depend on the ecoregion classification at all, and it fixes errors
that are real today. The file it replaces, ``data/provinces_prairie.geojson``,
draws Saskatchewan and Manitoba as **five-vertex rectangles** and the
Alberta/British Columbia border as a straight line. South of about 54 degrees
north that border is the continental divide, which is ragged; a straight line
there is not a simplification of the boundary, it is a different boundary. The
map also had no water at all, so two of Alberta's largest rivers — the Peace and
the Athabasca — were simply absent.

None of that is a classification question, so none of it has to wait for the
ELC download. Natural Earth is reachable from anywhere GitHub is.

WHAT IT DELIBERATELY DOES NOT DO
-------------------------------------------------------------------------------
It does not touch ``data/ecoregions_canada.geojson``. Those polygons feed
``src/ecoregion.py:lookup_ecoregions``, which decides which plants get
recommended for a real site; replacing them is the reviewed follow-up, not a
side effect of a basemap change.

SIZE
-------------------------------------------------------------------------------
The output is read at site-build time and shipped inside the installer, so it is
kept under a few hundred KB by clipping to the map window, dropping small
waterbodies, and simplifying to a tolerance well below what a 700px-wide map can
resolve. ``--report`` prints the budget.
"""

from __future__ import annotations

import argparse
import json
import sys

from tools.ecoregions.common import (CRS_PROJECTED, CRS_WGS84, DATA, REPO,
                                     SUBJECT_PROVINCES, WINDOW, require)

#: Written into the repo's ``data/`` and tracked in git — this is a shipped file.
OUTPUT = REPO / "data" / "basemap_prairie.geojson"

#: Simplification tolerance in degrees. The wide map is 700px across ~29 degrees
#: of longitude, so one pixel is ~0.04 degrees; 0.008 keeps roughly five vertices
#: per pixel of the finest detail, which is more than the eye can use and still
#: small on disk.
_TOLERANCE = 0.008

#: Lakes smaller than this (square kilometres, measured on the equal-area conic
#: rather than in square degrees) are dropped. Lake Athabasca, Great Slave,
#: Lesser Slave, Reindeer, Wollaston, Winnipeg, Cold and Utikuma all clear it;
#: the thousands of boreal ponds that would turn the north into grey noise at
#: 700px do not.
_MIN_LAKE_AREA_KM2 = 900.0

#: Coordinates are rounded to this many decimal places. Three is about 110 m of
#: latitude — roughly one fortieth of a pixel on the wide map — and it is worth
#: about half the file size, because full float repr spends seventeen characters
#: saying something the renderer cannot draw.
_COORD_DP = 3

#: Natural Earth ranks rivers 1 (largest) to 10. Through the prairies, 6 keeps
#: the Peace, Athabasca, both Saskatchewans, the Churchill, the Bow and the
#: Milk, and drops the creek network.
_MAX_RIVER_RANK = 6

#: Rivers that must survive whatever the rank filter does, checked by name after
#: the fact. The Peace and the Athabasca going missing is the specific defect
#: this stage exists to fix, so it is asserted rather than hoped for.
_REQUIRED_RIVERS = ("Peace", "Athabasca", "North Saskatchewan",
                    "South Saskatchewan")


def _clip(gdf, window):
    """Intersect with the map window and drop whatever falls outside."""
    import geopandas as gpd
    from shapely.geometry import box

    frame = gpd.GeoDataFrame(geometry=[box(*window)], crs=CRS_WGS84)
    out = gpd.overlay(gdf, frame, how="intersection", keep_geom_type=True)
    return out[~out.geometry.is_empty & out.geometry.notna()]


def _province_rows(raw, window):
    """Provinces and states in the window, tagged subject or context.

    ``SUBJECT_PROVINCES`` get their real names and are what the ecoregion fills
    sit on; everything else keeps a name for labelling but is drawn as grey
    context. Natural Earth's ``iso_3166_2`` gives the short codes the map prints
    (AB, SK, BC, MB, MT) without a hand-maintained lookup.
    """
    import geopandas as gpd

    gdf = gpd.read_file(raw / "ne_10m_admin_1_states_provinces.shp")
    cols = {c.lower(): c for c in gdf.columns}
    name_col = cols.get("name")
    iso_col = cols.get("iso_3166_2")
    admin_col = cols.get("admin")
    if not (name_col and iso_col and admin_col):
        raise SystemExit(
            "Natural Earth admin_1 is missing an expected column.\n"
            f"  found: {sorted(gdf.columns)}\n"
            "Inspect the download rather than guessing — the whole point of "
            "this pipeline is that field names are checked, not assumed."
        )
    gdf = gdf[[name_col, iso_col, admin_col, "geometry"]].rename(
        columns={name_col: "name", iso_col: "iso", admin_col: "country"})
    gdf = _clip(gdf, window)
    gdf["subject"] = gdf["name"].isin(SUBJECT_PROVINCES)
    # "CA-AB" -> "AB"; US states come through as "US-MT" and read the same way.
    gdf["code"] = gdf["iso"].fillna("").str.split("-").str[-1]
    return gdf.drop(columns=["iso"])


def _lake_rows(raw, window):
    import geopandas as gpd
    import pandas as pd

    frames = []
    for stem in ("ne_10m_lakes", "ne_10m_lakes_north_america"):
        path = raw / f"{stem}.geojson"
        if path.exists():
            frames.append(gpd.read_file(path))
    if not frames:
        raise SystemExit("No Natural Earth lake layer found under data/raw.")
    gdf = gpd.GeoDataFrame(pd.concat(frames, ignore_index=True),
                           crs=frames[0].crs)
    cols = {c.lower(): c for c in gdf.columns}
    gdf = gdf.rename(columns={cols.get("name", "name"): "name"})
    keep = [c for c in ("name", "geometry") if c in gdf.columns]
    gdf = _clip(gdf[keep], window)
    # Measured on the equal-area conic, so "900 km2" means 900 km2 at 60 degrees
    # north as well as at 49. Doing this in square degrees would have quietly
    # applied a stricter threshold in the north, dropping boreal lakes that are
    # bigger than southern ones it kept.
    km2 = gdf.geometry.to_crs(CRS_PROJECTED).area / 1e6
    return gdf[km2 >= _MIN_LAKE_AREA_KM2]


def _river_rows(raw, window):
    import geopandas as gpd

    gdf = gpd.read_file(raw / "ne_10m_rivers_lake_centerlines.shp")
    cols = {c.lower(): c for c in gdf.columns}
    name_col = cols.get("name")
    rank_col = cols.get("scalerank")
    if not (name_col and rank_col):
        raise SystemExit(
            "Natural Earth rivers layer is missing name/scalerank.\n"
            f"  found: {sorted(gdf.columns)}")
    gdf = gdf[[name_col, rank_col, "geometry"]].rename(
        columns={name_col: "name", rank_col: "rank"})
    gdf = gdf[gdf["rank"] <= _MAX_RIVER_RANK]
    gdf = _clip(gdf, window)
    return gdf


def _text(value) -> str:
    """A GeoJSON-safe string for a field that may be absent or NaN.

    Natural Earth leaves ``name`` empty on unnamed waterbodies, and pandas reads
    that column as float NaN once any row is missing — which sorts as a float
    and serialises as the literal ``NaN``, which is not valid JSON.
    """
    if value is None or value != value:                       # NaN != NaN
        return ""
    return str(value)


def _round(obj):
    """Round every coordinate in a nested GeoJSON coordinate list."""
    if isinstance(obj, (int, float)):
        return round(float(obj), _COORD_DP)
    return [_round(item) for item in obj]


def _feature(geom, properties: dict) -> dict:
    """One simplified, coordinate-rounded GeoJSON feature."""
    import shapely

    simplified = geom.simplify(_TOLERANCE, preserve_topology=True)
    geometry = json.loads(shapely.to_geojson(simplified))
    geometry["coordinates"] = _round(geometry["coordinates"])
    return {"type": "Feature", "properties": properties, "geometry": geometry}


def build(*, report: bool = False) -> int:
    require("geopandas", "shapely")
    raw = DATA / "raw"
    if not (raw / "ne_10m_admin_1_states_provinces.shp").exists():
        raise SystemExit(
            f"Natural Earth sources not found in {raw}.\n"
            "Run:  python -m tools.ecoregions.fetch")

    provinces = _province_rows(raw, WINDOW)
    lakes = _lake_rows(raw, WINDOW)
    rivers = _river_rows(raw, WINDOW)

    missing = [r for r in _REQUIRED_RIVERS
               if not rivers["name"].fillna("").str.contains(r).any()]
    if missing:
        raise SystemExit(
            "These rivers did not survive the filter: " + ", ".join(missing) +
            f"\nRaise _MAX_RIVER_RANK above {_MAX_RIVER_RANK} or check the "
            "download. The Peace and the Athabasca going missing is the exact "
            "defect this stage exists to fix, so this is a hard failure.")

    features = []
    # One "all the land in the window" polygon, drawn first and underneath
    # everything. Provinces are simplified independently, so a shared boundary
    # — the 60th parallel between Alberta and the Northwest Territories, the
    # 49th along the United States — comes back as two slightly different lines
    # with a hairline of nothing between them. On the first render those showed
    # as white slivers across the top of the map and along the border. Painting
    # the union underneath means a sliver falls through to land colour instead
    # of to the page, which is the standard fix and costs one polygon.
    land = provinces.geometry.union_all().simplify(_TOLERANCE,
                                                   preserve_topology=True)
    features.append(_feature(land, {"layer": "land"}))
    for _, row in provinces.iterrows():
        features.append(_feature(row.geometry, {
            "layer": "province", "code": row["code"], "name": row["name"],
            "country": row["country"], "subject": bool(row["subject"])}))
    for _, row in lakes.iterrows():
        features.append(_feature(row.geometry, {
            "layer": "lake", "name": _text(row.get("name"))}))
    for _, row in rivers.iterrows():
        features.append(_feature(row.geometry, {
            "layer": "river", "name": _text(row.get("name")),
            "rank": int(row["rank"])}))

    payload = {
        "type": "FeatureCollection",
        "name": "Prairie basemap (Natural Earth 10m)",
        "comment": (
            "Provincial/state outlines, major lakes and major rivers for the "
            "Alberta/Saskatchewan map window, clipped from Natural Earth "
            "1:10m and simplified to " + str(_TOLERANCE) + " degrees. "
            "Drawing only: src/ecoregion.py's point lookup never reads this. "
            "Regenerate with `python -m tools.ecoregions.basemap`. "
            "Source: Natural Earth 1:10m (public domain), "
            "github.com/nvkelso/natural-earth-vector."),
        "features": features,
    }
    OUTPUT.write_text(json.dumps(payload, separators=(",", ":")) + "\n",
                      encoding="utf-8")

    size_kb = OUTPUT.stat().st_size / 1024
    print(f"Wrote {len(features)} features to "
          f"{OUTPUT.relative_to(REPO)}  ({size_kb:.0f} KB)")
    if report:
        print(f"  provinces/states : {len(provinces)}")
        print(f"  lakes            : {len(lakes)}")
        print(f"  rivers           : {len(rivers)}  "
              f"(named: {sorted(set(rivers['name'].dropna()))[:12]}...)")
        print(f"  subject fills    : "
              f"{sorted(provinces[provinces['subject']]['name'])}")
    return 0


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    p.add_argument("--report", action="store_true",
                   help="print per-layer counts and the size budget")
    args = p.parse_args(argv)
    return build(report=args.report)


if __name__ == "__main__":
    sys.exit(main())
