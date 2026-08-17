"""Stage 2 — read the sources and report what is actually in them.

    python -m tools.ecoregions.inspect_schema
    python -m tools.ecoregions.inspect_schema --source elc_ecoregion

Prints, for every classification source: the layers it contains, the real column
names, the dtype and fill rate of each, and the full sorted list of unique values
in every column that looks like a classification field.

WHY THIS IS ITS OWN STAGE
-------------------------------------------------------------------------------
Because the guesses are always wrong. The rebuild brief guessed ``NSRNAME``,
``NRNAME``, ``ECOREGION_NAME`` and ``ECOZONE_NAME``, and said so in as many
words: *"Do not assume field names."* An earlier attempt in this repository
guessed ``NA_L3NAME`` and ``L3_KEY`` for the CEC shapefile and shipped a key map
built on them without anyone ever running it against the file.

A field name that does not exist fails loudly. The dangerous case is a field
that exists and means something else — and that is only caught by looking at the
values, which is why this prints them rather than just the headers.

WHAT TO DO WITH THE OUTPUT
-------------------------------------------------------------------------------
Copy the real field names into ``tools/ecoregions/harmonize.py``'s ``FIELDS``
table. Nothing downstream guesses; ``harmonize`` refuses to run against a column
it was not told about.

Alberta's subregions may arrive as a File Geodatabase rather than a shapefile.
This lists the layers of whatever it is given, so ``.gdb`` directories are
handled the same way as ``.shp`` files.
"""

from __future__ import annotations

import argparse
import sys

from tools.ecoregions.common import DATA, require
from tools.ecoregions.sources import ALL, CLASSIFICATION, Source

_RAW = DATA / "raw"

#: A column is worth dumping values for when its name contains one of these.
#: Deliberately broad: a false positive costs a few printed lines, a false
#: negative costs the whole point of the stage.
_INTERESTING = ("name", "nom", "eco", "zone", "region", "subregion", "prov",
                "nsr", "nr_", "class", "type", "desc", "label", "code")

#: Above this many distinct values a column is an identifier, not a class.
_MAX_VALUES = 80


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


def inspect_one(source: Source) -> bool:
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
        _report_frame(gdf, str(layer))
    return True


def run(only: str = "") -> int:
    require("geopandas", "pyogrio")
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
        if not inspect_one(source):
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
    args = parser.parse_args(argv)
    return run(args.source)


if __name__ == "__main__":
    sys.exit(main())
