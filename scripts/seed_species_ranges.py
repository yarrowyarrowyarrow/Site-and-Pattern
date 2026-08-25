#!/usr/bin/env python3
"""
scripts/seed_species_ranges.py — derive the grid range for every species.

**Dev-time, run-once, commit the result. Needs no network.** It reads the point
cache `scripts/seed_ecoregion_ranges.py` already wrote
(`data/fetched/plant_occurrences.json`) and writes `data/plant_ranges.json`,
which ships.

    python scripts/seed_species_ranges.py                 # everything
    python scripts/seed_species_ranges.py --species "Gaillardia aristata"
    python scripts/seed_species_ranges.py --dry-run       # print, write nothing
    python scripts/seed_species_ranges.py --cell 0.5      # a coarser grid

Why it is separate from the ecoregion seeder
--------------------------------------------
Same input, different question, and the ecoregion seeder is already the largest
script here. That one asks *which classified communities is this recorded from*
and needs GBIF; this asks *where has it been found* and needs nothing but the
cache. Keeping them apart means a change to the grid resolution costs a
ten-second offline run rather than a fetch.

See `src/species_range.py` for what a cell does and does not claim.
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import date
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

OUTPUT_PATH = PROJECT_ROOT / "data" / "plant_ranges.json"


def derive(cache: dict, *, step: float, verbose: bool = True) -> tuple:
    """``({species: {cell: records}}, {species: (kept, refused, outside)})``."""
    from scripts.seed_ecoregion_ranges import usable_points
    from src.species_range import cell_counts
    from src.subject_area import in_subject_provinces

    ranges, stats = {}, {}
    for i, (name, points) in enumerate(sorted(cache.items()), 1):
        keep, refused = usable_points(points)
        inside = [p for p in keep if in_subject_provinces(p[0], p[1])]
        cells = cell_counts(inside, step=step, subject_only=False)
        if cells:
            ranges[name] = cells
        stats[name] = (len(inside), refused, len(keep) - len(inside))
        if verbose and i % 50 == 0:
            print(f"  [{i}/{len(cache)}] ...")
    return ranges, stats


def main(argv: list[str] | None = None) -> int:
    from src.species_range import CELL_DEG, build_document

    p = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--species", action="append", default=None,
                   help="Only this scientific name (repeatable).")
    p.add_argument("--cell", type=float, default=CELL_DEG,
                   help=f"Grid resolution in degrees (default {CELL_DEG}).")
    p.add_argument("--dry-run", action="store_true",
                   help="Print the result; write nothing.")
    p.add_argument("--quiet", action="store_true")
    args = p.parse_args(argv)

    from scripts.seed_ecoregion_ranges import CACHE_PATH, read_cache
    cache = read_cache()
    if not cache:
        print(f"No point cache at {CACHE_PATH.relative_to(PROJECT_ROOT)}. Run "
              f"scripts/seed_ecoregion_ranges.py on a machine with egress "
              f"first.", file=sys.stderr)
        return 1
    if args.species:
        missing = [n for n in args.species if n not in cache]
        if missing:
            print(f"Not in the cache: {', '.join(missing)}", file=sys.stderr)
            return 1
        cache = {n: cache[n] for n in args.species}

    verbose = not args.quiet
    print(f"Deriving a {args.cell} degree range grid for {len(cache)} species "
          f"from {sum(map(len, cache.values())):,} cached records. No network.")

    ranges, stats = derive(cache, step=args.cell, verbose=verbose)

    total_cells = sum(len(v) for v in ranges.values())
    kept = sum(s[0] for s in stats.values())
    refused = sum(s[1] for s in stats.values())
    outside = sum(s[2] for s in stats.values())
    print(f"\n  {len(ranges)} species with a range, {total_cells:,} cells")
    print(f"  {kept:,} records used")
    print(f"  {refused:,} refused as too coarsely georeferenced "
          f"(over the 10 km uncertainty limit)")
    print(f"  {outside:,} outside Alberta and Saskatchewan")

    empty = sorted(set(cache) - set(ranges))
    if empty:
        # Named, not silently absent: "no range" and "no records we can use"
        # look identical in the output file and are different findings.
        print(f"\n  {len(empty)} species have NO usable record in the two "
              f"provinces and get no range drawn:")
        for name in empty[:20]:
            print(f"      {name}")
        if len(empty) > 20:
            print(f"      ... and {len(empty) - 20} more")

    biggest = sorted(ranges.items(), key=lambda kv: -len(kv[1]))[:5]
    if biggest and verbose:
        print("\n  widest ranges:")
        for name, cells in biggest:
            print(f"      {len(cells):4d} cells  {name}")

    if verbose:
        # The distribution the ramp has to survive. If nearly every cell landed
        # in one band the shading would be doing no work, which is the failure
        # the single-colour wash already made once.
        from src.species_range import BAND_LABELS, density_band
        bands = [0] * len(BAND_LABELS)
        for counts in ranges.values():
            for n in counts.values():
                bands[density_band(n)] += 1
        print("\n  cells per density band (records in the cell):")
        for label, n in zip(BAND_LABELS, bands):
            share = 100.0 * n / total_cells if total_cells else 0.0
            print(f"      {label:>6s}  {n:7,d}  {share:5.1f}%")

    if args.dry_run:
        print("\n--dry-run: nothing written.")
        return 0

    doc = build_document(
        ranges, step=args.cell,
        source=f"derived from data/fetched/plant_occurrences.json on "
               f"{date.today().isoformat()}")
    OUTPUT_PATH.write_text(
        json.dumps(doc, ensure_ascii=False, separators=(",", ":")) + "\n",
        encoding="utf-8")
    size_mb = OUTPUT_PATH.stat().st_size / 1_000_000
    print(f"\nWrote {OUTPUT_PATH.relative_to(PROJECT_ROOT)} "
          f"({len(ranges)} species, {total_cells:,} cells, {size_mb:.2f} MB)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
