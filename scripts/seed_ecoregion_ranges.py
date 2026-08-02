"""
seed_ecoregion_ranges.py — derive each species' ecoregion range from GBIF.

**Dev-time, run-once, commit-the-result.** Users never run this; it writes
``data/plant_ecoregions.json``, which ships. Same shape as
``scripts/prepare_ecoregions.py`` and the ``seed_*_morphology.py`` seeders.

Why this exists
---------------
The catalogue's ``ecoregion`` tags were generated heuristically and never
sourced. ``moist_mixedgrass`` is on 246 of 434 plants and ``aspen_parkland`` on
136, in an Alberta-first app centred on Edmonton, and 39 native trees and
shrubs carry no parkland tag at all — Saskatoon Berry among them, which a user
noticed because it is a defining parkland shrub.

This replaces the guess with georeferenced occurrence records, and keeps the
count and a confidence band beside every claim so "three records" and "three
hundred records" stay visibly different statements (P9).

Running it
----------
::

    python scripts/seed_ecoregion_ranges.py                # everything
    python scripts/seed_ecoregion_ranges.py --limit 20     # a quick look
    python scripts/seed_ecoregion_ranges.py --species "Amelanchier alnifolia"
    python scripts/seed_ecoregion_ranges.py --dry-run      # print, write nothing

Needs the network — GBIF only, no key, no account. Expect roughly one to two
seconds per species (it pages 300 records at a time and sleeps between calls to
stay polite), so a full run over ~430 species is a coffee, not an afternoon.

It is safe to re-run. The output is sorted and deterministic given the same
records, so a second run's diff is real change in GBIF, not churn.

**This step cannot run in the project's cloud sessions** — the egress proxy
answers 403 to CONNECT for ``api.gbif.org``. That is why the pipeline is split:
the derivation logic and its tests live in ``src/ecoregion_ranges.py`` and run
anywhere; only the download has to happen on a machine with open egress.

What it does NOT do
-------------------
It never derives ``riparian`` or ``wet_meadow``. Those are site-scale moisture
niches — a coordinate cannot tell you a species grows in wet ground — so the
existing per-species assertions for them are left exactly as they are.

It also never *deletes* a tag on its own authority. Regions that had records
but fewer than ``--min-records`` are printed at the end, so a species sitting
at two records somewhere is a thing a human sees rather than a thing that
silently vanishes.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from datetime import date
from pathlib import Path
from urllib.parse import urlencode

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

OUTPUT_PATH = PROJECT_ROOT / "data" / "plant_ecoregions.json"
PLANT_FILES = ("plants_master.json", "garden_plants.json")

GBIF_SEARCH = "https://api.gbif.org/v1/occurrence/search"
PAGE_SIZE = 300
MAX_RECORDS_PER_SPECIES = 3000     # plenty for a range; keeps a run bounded
POLITE_SLEEP = 0.35                # seconds between GBIF calls

# Records from these bases are places a person put the plant, not places it
# grows. Leaving them in is how a botanical garden becomes an ecoregion.
EXCLUDED_BASES = {"LIVING_SPECIMEN", "MATERIAL_SAMPLE", "FOSSIL_SPECIMEN"}


# ── Reading the catalogue ───────────────────────────────────────────────────

def _load_records(path: Path) -> list[dict]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError, OSError):
        return []
    if isinstance(data, dict):
        for key in ("plants", "records", "data"):
            if isinstance(data.get(key), list):
                return data[key]
        return []
    return data if isinstance(data, list) else []


def catalogue_species() -> list[str]:
    """Every distinct scientific name in the shipped seed files, sorted."""
    names: set[str] = set()
    for filename in PLANT_FILES:
        for rec in _load_records(PROJECT_ROOT / "data" / filename):
            name = (rec.get("scientific_name") or "").strip()
            if name:
                names.add(name)
    return sorted(names)


# ── Talking to GBIF ─────────────────────────────────────────────────────────

def fetch_occurrences(scientific_name: str, *, verbose: bool = False
                      ) -> list[tuple[float, float]]:
    """Georeferenced occurrence coordinates for one species.

    Filters GBIF-side to records that have coordinates and no recorded
    geospatial issue; filters here to wild occurrences (see EXCLUDED_BASES).
    Returns ``[]`` on any failure — a species we could not fetch keeps whatever
    tags it already had, which is the safe direction to fail in.
    """
    from src.http_utils import http_get_json

    points: list[tuple[float, float]] = []
    offset = 0
    while offset < MAX_RECORDS_PER_SPECIES:
        query = urlencode({
            "scientificName": scientific_name,
            "hasCoordinate": "true",
            "hasGeospatialIssue": "false",
            "limit": PAGE_SIZE,
            "offset": offset,
        })
        data = http_get_json(f"{GBIF_SEARCH}?{query}", timeout=30.0)
        if not isinstance(data, dict):
            if verbose:
                print(f"    ! no response at offset {offset}")
            break
        results = data.get("results") or []
        for rec in results:
            if (rec.get("basisOfRecord") or "") in EXCLUDED_BASES:
                continue
            lat, lng = rec.get("decimalLatitude"), rec.get("decimalLongitude")
            if lat is None or lng is None:
                continue
            points.append((float(lat), float(lng)))
        if data.get("endOfRecords") or not results:
            break
        offset += PAGE_SIZE
        time.sleep(POLITE_SLEEP)
    return points


# ── The run ─────────────────────────────────────────────────────────────────

def derive(names: list[str], *, min_records: int, verbose: bool,
           fetch=fetch_occurrences) -> tuple[dict, dict, dict]:
    """``(species_ranges, dropped, no_records)`` for a list of species.

    ``fetch`` is injectable so the tests can drive this without a network —
    which is the only way the threshold behaviour (2 records versus 3) is
    testable at all.
    """
    from src.ecoregion_ranges import ranges_for_species, dropped_regions

    species_ranges: dict[str, list[dict]] = {}
    dropped: dict[str, dict[str, int]] = {}
    no_records: list[str] = []

    for i, name in enumerate(names, 1):
        points = fetch(name, verbose=verbose)
        if not points:
            no_records.append(name)
            if verbose:
                print(f"[{i}/{len(names)}] {name}: no georeferenced records")
            continue
        rows = ranges_for_species(points, min_records=min_records)
        thin = dropped_regions(points, min_records=min_records)
        if rows:
            species_ranges[name] = rows
        if thin:
            dropped[name] = thin
        if verbose:
            summary = ", ".join(f"{r['ecoregion']}={r['occurrences']}"
                                f"({r['confidence']})" for r in rows) or "none"
            print(f"[{i}/{len(names)}] {name}: {len(points)} records → {summary}")
        time.sleep(POLITE_SLEEP)

    return species_ranges, dropped, no_records


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--species", action="append", default=None,
                   help="Derive only this scientific name (repeatable).")
    p.add_argument("--limit", type=int, default=None,
                   help="Only the first N species — for a quick smoke run.")
    p.add_argument("--min-records", type=int, default=None,
                   help="Records inside a region before we claim it "
                        "(default: ecoregion_ranges.MIN_RECORDS).")
    p.add_argument("--dry-run", action="store_true",
                   help="Print the result; write nothing.")
    p.add_argument("--quiet", action="store_true")
    args = p.parse_args(argv)

    from src.ecoregion_ranges import MIN_RECORDS, build_document
    min_records = args.min_records or MIN_RECORDS
    verbose = not args.quiet

    names = args.species or catalogue_species()
    if args.limit:
        names = names[:args.limit]
    if not names:
        print("No species found — is data/plants_master.json present?")
        return 1

    print(f"Deriving ecoregion ranges for {len(names)} species from GBIF "
          f"(min {min_records} records per region)…")
    ranges, dropped, no_records = derive(
        names, min_records=min_records, verbose=verbose)

    doc = build_document(
        ranges,
        source=f"GBIF occurrence search, retrieved {date.today().isoformat()}",
        generated=date.today().isoformat(),
        min_records=min_records)

    print()
    print(f"  {len(ranges)} species with at least one region")
    print(f"  {len(no_records)} species with no georeferenced records")
    if dropped:
        print(f"  {len(dropped)} species had regions under the threshold:")
        for name, thin in sorted(dropped.items())[:40]:
            bits = ", ".join(f"{k}={n}" for k, n in thin.items())
            print(f"      {name}: {bits}")
        if len(dropped) > 40:
            print(f"      … and {len(dropped) - 40} more")

    if args.dry_run:
        print("\n--dry-run: nothing written.")
        return 0

    OUTPUT_PATH.write_text(json.dumps(doc, indent=2, ensure_ascii=False) + "\n",
                           encoding="utf-8")
    print(f"\nWrote {OUTPUT_PATH.relative_to(PROJECT_ROOT)}")
    print("Next: bump _SCHEMA_VERSION in src/db/plants.py so existing installs "
          "reseed, then commit both.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
