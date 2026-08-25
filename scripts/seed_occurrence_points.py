#!/usr/bin/env python3
"""
scripts/seed_occurrence_points.py — the publishable records, as a shipped file.

**Dev-time, run-once, commit the result. Needs no network.** Reads the point
cache `scripts/seed_ecoregion_ranges.py` wrote
(`data/fetched/plant_occurrences.json`, a dev artefact that is never shipped)
plus the licence table `scripts/fetch_dataset_licences.py` wrote, and produces
`data/plant_occurrence_points.json`, which does ship.

    python scripts/seed_occurrence_points.py                 # everything
    python scripts/seed_occurrence_points.py --dry-run       # print, write nothing
    python scripts/seed_occurrence_points.py --species "Gaillardia aristata"

Three filters, in this order, and the order is deliberate
---------------------------------------------------------
1. **Precision.** Anything coarser than 10 km is refused (`usable_points`): a
   dot drawn from a county centroid is a claim the record does not make.
2. **Subject area.** Alberta and Saskatchewan only (F142). A record in British
   Columbia is not a licence question -- it is a record about somewhere else.
3. **Licence.** `PUBLISHABLE_COORDINATES`, which permits `CC_BY_NC` because a
   coordinate is a fact about a place rather than a work being redistributed.
   Absent from the table is dropped: absent is not permissive.

Reporting the drops is half the job. "We publish 34,000 of 365,000 records"
would be the finding, and a quiet map would hide it.
"""

from __future__ import annotations

import argparse
import collections
import json
import sys
from datetime import date
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

OUTPUT_PATH = PROJECT_ROOT / "data" / "plant_occurrence_points.json"


def derive(cache: dict, table: dict, *, step: float, verbose: bool = True
           ) -> tuple:
    """``({species: {"s": [...], "o": [...]}}, drop counts)``."""
    from scripts.fetch_dataset_licences import PUBLISHABLE_COORDINATES
    from src.occurrence_points import marks
    from src.subject_area import in_subject_provinces

    out: dict = {}
    dropped: collections.Counter = collections.Counter()
    for i, (name, points) in enumerate(sorted(cache.items()), 1):
        keep, refused = points_that_are_precise_enough(points)
        dropped["too coarsely georeferenced (over 10 km)"] += refused
        inside = [p for p in keep if in_subject_provinces(p[0], p[1])]
        dropped["outside Alberta and Saskatchewan"] += len(keep) - len(inside)
        allowed = [p for p in inside
                   if table.get(getattr(p, "dataset_key", ""))
                   in PUBLISHABLE_COORDINATES]
        dropped["licence does not permit redrawing the coordinate"] += (
            len(inside) - len(allowed))
        got = marks(allowed, step=step)
        dropped["duplicate at this resolution"] += (
            len(allowed) - sum(len(v) for v in got.values()))
        if any(got.values()):
            out[name] = got
        if verbose and i % 100 == 0:
            print(f"  [{i}/{len(cache)}] ...")
    return out, dropped


def points_that_are_precise_enough(points):
    """`usable_points`, named for what it does here rather than re-implemented."""
    from scripts.seed_ecoregion_ranges import usable_points
    return usable_points(points)


def main(argv: list[str] | None = None) -> int:
    from src.occurrence_points import (KEY_OBSERVATION, KEY_SPECIMEN,
                                       MARK_DEG, build_document)

    p = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--species", action="append", default=None,
                   help="Only this scientific name (repeatable).")
    p.add_argument("--mark", type=float, default=MARK_DEG,
                   help=f"Dedupe resolution in degrees (default {MARK_DEG}).")
    p.add_argument("--dry-run", action="store_true",
                   help="Print the result; write nothing.")
    p.add_argument("--quiet", action="store_true")
    args = p.parse_args(argv)

    from scripts.plot_occurrences import licences
    from scripts.seed_ecoregion_ranges import CACHE_PATH, read_cache
    cache = read_cache()
    if not cache:
        print(f"No point cache at {CACHE_PATH.relative_to(PROJECT_ROOT)}. Run "
              f"scripts/seed_ecoregion_ranges.py on a machine with egress "
              f"first.", file=sys.stderr)
        return 1
    table = licences()                        # raises with its own hint if absent
    if args.species:
        missing = [n for n in args.species if n not in cache]
        if missing:
            print(f"Not in the cache: {', '.join(missing)}", file=sys.stderr)
            return 1
        cache = {n: cache[n] for n in args.species}

    total = sum(map(len, cache.values()))
    print(f"Reading {total:,} cached records for {len(cache)} species. "
          f"No network.")

    got, dropped = derive(cache, table, step=args.mark, verbose=not args.quiet)

    spec = sum(len(v.get(KEY_SPECIMEN) or []) for v in got.values())
    obs = sum(len(v.get(KEY_OBSERVATION) or []) for v in got.values())
    print(f"\n  {len(got)} species with a publishable record")
    print(f"  {spec:,} specimen marks")
    print(f"  {obs:,} observation marks")
    print("\n  dropped:")
    for why, n in dropped.most_common():
        print(f"      {n:8,d}  {why}")

    empty = sorted(set(cache) - set(got))
    if empty:
        # Named, never silently absent: "no publishable record" and "no record"
        # look identical in the output and are different findings.
        print(f"\n  {len(empty)} species have NO publishable record and draw "
              f"no dots:")
        for name in empty[:15]:
            print(f"      {name}")
        if len(empty) > 15:
            print(f"      ... and {len(empty) - 15} more")

    if args.dry_run:
        print("\n--dry-run: nothing written.")
        return 0

    doc = build_document(
        got, step=args.mark,
        source=f"derived from data/fetched/plant_occurrences.json on "
               f"{date.today().isoformat()}")
    OUTPUT_PATH.write_text(
        json.dumps(doc, ensure_ascii=False, separators=(",", ":")) + "\n",
        encoding="utf-8")
    mb = OUTPUT_PATH.stat().st_size / 1_000_000
    print(f"\nWrote {OUTPUT_PATH.relative_to(PROJECT_ROOT)} "
          f"({len(got)} species, {spec + obs:,} marks, {mb:.2f} MB)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
