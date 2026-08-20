"""Stage 2 — read the sources and report what is actually in them.

    python -m tools.ecoregions.inspect_schema
    python -m tools.ecoregions.inspect_schema --source elc_ecoregion

Prints, for every classification source: the layers it contains, the real column
names, the dtype and fill rate of each, and the full sorted list of unique values
in every column that looks like a classification field.

WHY THIS IS ITS OWN STAGE
-------------------------------------------------------------------------------
Because you cannot tell which guesses are right without looking. The first real
run settled this: of the rebuild brief's four guesses, ``NSRNAME`` and
``NRNAME`` were **correct**, while ``ECOREGION_NAME`` and ``ECOZONE_NAME``
missed — the AAFC files are bilingual and the columns carry an ``_EN`` suffix
beside a ``_FR`` twin. Fifty per cent, with no way to know which half in
advance. An earlier attempt in this repository guessed ``NA_L3NAME`` and
``L3_KEY`` for the CEC shapefile and shipped a key map built on them without
anyone ever running it against a file.

A field name that does not exist fails loudly. The dangerous case is a field
that exists and means something else — and that is only caught by looking at the
values, which is why this prints them rather than just the headers.

WHAT TO DO WITH THE OUTPUT
-------------------------------------------------------------------------------
Copy the real field names into ``tools/ecoregions/harmonize.py``'s ``FIELDS``
table. Nothing downstream guesses; ``harmonize`` refuses to run against a column
it was not told about.

This lists the layers of whatever it is given, so a ``.gdb`` directory or the
GeoJSON that ``tools.ecoregions.arcgis`` writes are handled the same way as a
``.shp``. Alberta turned out to be the last of those: the province publishes the
subregions as a live ArcGIS service, not as a file in any format.
"""

from __future__ import annotations

import argparse
import sys

from tools.ecoregions.common import DATA, WINDOW, require
from tools.ecoregions.sources import ALL, CLASSIFICATION, Source

_RAW = DATA / "raw"

#: A column is worth dumping values for when its name contains one of these.
#: Deliberately broad: a false positive costs a few printed lines, a false
#: negative costs the whole point of the stage.
_INTERESTING = ("name", "nom", "eco", "zone", "region", "subregion", "prov",
                "nsr", "nr_", "class", "type", "desc", "label", "code")

#: Above this many distinct values a column is an identifier, not a class.
#:
#: Raised from 80 in V2.66 after the first real run: the national ecoregion
#: layer has **194** names, so the cap suppressed the single list this stage
#: exists to produce, printing "looks like an identifier" about the one column
#: everything downstream is keyed on. A cap that hides the answer is worse than
#: no cap. Use ``--window`` to see only the names inside the map window, which
#: is the list you actually want to read.
_MAX_VALUES = 260


def _layers(path):
    import pyogrio

    try:
        info = pyogrio.list_layers(path)
    except Exception:                                         # noqa: BLE001
        return [None]
    return [row[0] for row in info] if len(info) else [None]


def _report_frame(gdf, label: str) -> None:
    print(f"    layer {label}: {len(gdf)} features, CRS {gdf.crs}")
    print(f"    geometry types: {sorted(set(gdf.geom_type))}")
    print()
    print(f"    {'column':28} {'dtype':12} {'non-null':>9}  {'distinct':>8}")
    print(f"    {'-' * 28} {'-' * 12} {'-' * 9}  {'-' * 8}")
    for column in gdf.columns:
        if column == "geometry":
            continue
        series = gdf[column]
        print(f"    {column[:28]:28} {str(series.dtype)[:12]:12} "
              f"{series.notna().sum():9}  {series.nunique():8}")
    print()

    for column in gdf.columns:
        if column == "geometry":
            continue
        lowered = column.lower()
        if not any(token in lowered for token in _INTERESTING):
            continue
        values = sorted({str(v) for v in gdf[column].dropna().unique()})
        if not values or len(values) > _MAX_VALUES:
            print(f"    {column}: {len(values)} distinct "
                  f"(too many to list; looks like an identifier)")
            continue
        print(f"    {column}  ({len(values)} distinct):")
        for value in values:
            print(f"        {value}")
        print()


def _clip_to_window(gdf):
    """Only the features inside the Alberta/Saskatchewan map window.

    A national layer reports 194 ecoregions, of which about twenty are in the
    two provinces this pipeline classifies. Reading the twenty is a job; reading
    the 194 to find them is a chore that gets skipped.
    """
    import geopandas as gpd
    from shapely.geometry import box

    if gdf.crs is None:
        return gdf
    frame = gpd.GeoDataFrame(geometry=[box(*WINDOW)], crs="EPSG:4326")
    return gdf[gdf.to_crs("EPSG:4326").intersects(frame.geometry.iloc[0])]


def inspect_one(source: Source, *, window: bool = False) -> bool:
    import geopandas as gpd

    path = _RAW / source.filename
    if not path.exists():
        print(f"  {source.key}: NOT PRESENT ({source.filename})")
        print(f"      run:  python -m tools.ecoregions.fetch")
        return False
    print(f"  {source.key}  <- {source.filename}")
    print(f"      {source.what}")
    print(f"      {source.publisher}, {source.edition}")
    print()
    for layer in _layers(path):
        try:
            gdf = (gpd.read_file(path, layer=layer) if layer
                   else gpd.read_file(path))
        except Exception as exc:                              # noqa: BLE001
            print(f"    layer {layer}: could not read - {exc}")
            continue
        if window:
            before = len(gdf)
            gdf = _clip_to_window(gdf)
            print(f"    (clipped to the map window: {before} -> {len(gdf)} "
                  f"features)")
        _report_frame(gdf, str(layer))
    return True


def run(only: str = "", *, window: bool = False) -> int:
    require("geopandas", "pyogrio", "shapely")
    targets = [s for s in ALL if s.key == only] if only else list(CLASSIFICATION)
    if only and not targets:
        raise SystemExit(f"No source named {only!r}. "
                         f"Known: {', '.join(s.key for s in ALL)}")
    print("=" * 74)
    print("  SCHEMA REPORT - the real field names, not the expected ones")
    print("=" * 74)
    print()
    missing = 0
    for source in targets:
        if not inspect_one(source, window=window):
            missing += 1
        print("-" * 74)
        print()
    if missing:
        print(f"{missing} source(s) not downloaded yet; nothing was guessed "
              f"about them.")
        return 1
    print("Copy the real classification field names into the FIELDS table in")
    print("tools/ecoregions/harmonize.py, then run the harmonize stage.")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--source", default="",
                        help="inspect one source by key instead of all")
    parser.add_argument("--window", action="store_true",
                        help="report only features inside the Alberta / "
                             "Saskatchewan map window")
    args = parser.parse_args(argv)
    return run(args.source, window=args.window)


if __name__ == "__main__":
    sys.exit(main())
