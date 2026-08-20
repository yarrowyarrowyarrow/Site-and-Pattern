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
    python scripts/seed_ecoregion_ranges.py --resume       # continue a run
    python scripts/seed_ecoregion_ranges.py --limit 20     # a quick look
    python scripts/seed_ecoregion_ranges.py --species "Amelanchier alnifolia"
    python scripts/seed_ecoregion_ranges.py --dry-run      # print, write nothing

Needs the network — GBIF only, no key, no account.

It is safe to re-run and safe to interrupt. The output is sorted and
deterministic given the same records, so a second run's diff is real change in
GBIF rather than churn, and the file is checkpointed every 25 species so a
Ctrl-C is not a lost harvest.

**Being rate-limited (and what the first run got wrong)**
---------------------------------------------------------

The first version of this script asked GBIF at roughly three requests a second
and downloaded every record worldwide for each species. GBIF started answering
**HTTP 429** after 228 species — and the script recorded each throttled species
as having "no georeferenced records", which reads as *this plant grows
nowhere*. That is precisely the kind of unsourced claim this whole pipeline
exists to remove, arriving through the back door.

Three things changed:

* **A failure is not an absence.** ``FetchFailed`` is raised and reported
  separately, the species is left out of the file entirely (so it keeps its
  existing tags), and the run exits non-zero so a bad harvest cannot be
  committed by accident.
* **Ask for less.** The query is now bounded to the shipped polygons' bounding
  box. Everything outside is discarded downstream anyway, so downloading it was
  pure cost — and it was most of the cost. A grass with 3,000 records worldwide
  usually has a few hundred in the prairie provinces: ten pages become one.
* **Slow down and stay slow.** One second between calls to start, backing off
  through 5/15/45/120s on a 429 (honouring ``Retry-After`` when GBIF sends it),
  and the pace stays slower for the rest of the run. A 429 means the *sustained*
  rate was too high; returning to the old pace would just earn another.

If a run still reports failures, re-run it with ``--resume``: species that
already have rows are skipped, and everything else is retried.

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
import urllib.error
import urllib.request
from datetime import date
from pathlib import Path
from urllib.parse import urlencode

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

OUTPUT_PATH = PROJECT_ROOT / "data" / "plant_ecoregions.json"
PLANT_FILES = ("plants_master.json", "garden_plants.json")

GBIF_SEARCH = "https://api.gbif.org/v1/occurrence/search"
PAGE_SIZE = 300
MAX_RECORDS_PER_SPECIES = 6000     # plenty for a range; keeps a run bounded
USER_AGENT = ("SiteAndPattern-ecoregion-seeder/1.0 "
              "(https://github.com/yarrowyarrowyarrow/Site-and-Pattern)")

# Seconds between GBIF calls. The first run of this script asked at ~3 req/s
# and GBIF started answering 429 after 228 species — so this is the floor, not
# the target, and `_Throttle` raises it for the rest of the run the moment a
# 429 arrives. Being slow is free; being rate-limited costs the whole harvest.
POLITE_SLEEP = 1.0
MAX_SLEEP = 8.0                    # ceiling for the adaptive slowdown

# 429 backoff: wait this long, doubling, before giving up on a page. GBIF sends
# Retry-After sometimes; when it does, it wins.
RETRY_WAITS = (5, 15, 45, 120)

# Records from these bases are places a person put the plant, not places it
# grows. Leaving them in is how a botanical garden becomes an ecoregion.
EXCLUDED_BASES = {"LIVING_SPECIMEN", "MATERIAL_SAMPLE", "FOSSIL_SPECIMEN"}


def polygon_bbox(pad: float = 0.5) -> tuple[float, float, float, float]:
    """``(lat_min, lat_max, lng_min, lng_max)`` around the shipped polygons.

    The single biggest thing that makes this run finish. A prairie grass can
    have thousands of GBIF records worldwide and we only ever count the ones
    inside an ecoregion polygon — so asking GBIF for the rest is pure cost, and
    it is the cost that got the first run throttled. Filtering server-side is
    exactly equivalent to filtering here (``ranges_for_species`` discards
    everything outside a polygon anyway) and turns ten pages into one.

    Padded slightly so a record sitting on a boundary is not lost to rounding.
    """
    with open(PROJECT_ROOT / "data" / "ecoregions_canada.geojson",
              encoding="utf-8") as f:
        data = json.load(f)
    lats, lngs = [], []

    def collect(node):
        """Walk any GeoJSON coordinate nesting down to its positions.

        **Handles MultiPolygon, which V2.67 made necessary.** This used to
        assume ``coordinates`` was a list of rings, which is true of a Polygon
        and one level too shallow for a MultiPolygon: the surveyed ecoregion
        layer is full of them, and the old loop reached a *ring* where it
        expected a *point* and raised ``float() argument must be a string or a
        real number, not 'list'``.

        Loud rather than silent, which is the one mercy in it — the same
        assumption in ``src/ecoregion.py`` skipped quietly and answered "you
        are in no ecoregion" instead. Recursing costs nothing and cannot be
        wrong at the next nesting depth either.
        """
        if (isinstance(node, (list, tuple)) and len(node) >= 2
                and all(isinstance(v, (int, float)) for v in node[:2])):
            lngs.append(float(node[0]))
            lats.append(float(node[1]))
            return
        if isinstance(node, (list, tuple)):
            for child in node:
                collect(child)

    for feature in data.get("features") or []:
        collect((feature.get("geometry") or {}).get("coordinates") or [])
    if not lats:
        return (-90.0, 90.0, -180.0, 180.0)
    return (max(-90.0, min(lats) - pad), min(90.0, max(lats) + pad),
            max(-180.0, min(lngs) - pad), min(180.0, max(lngs) + pad))


class _Throttle:
    """How fast we are currently willing to ask, and why.

    GBIF publishes no hard rate limit; it just starts answering 429. So the
    only honest strategy is to start slow, and get slower whenever it says no.
    The slowdown is permanent for the run — a 429 means the *sustained* rate
    was too high, and dropping back to the old pace would just earn another.
    """

    def __init__(self, base: float = POLITE_SLEEP):
        self.sleep = base
        self.limited = 0            # how many 429s this run has seen

    def wait(self):
        time.sleep(self.sleep)

    def rate_limited(self):
        self.limited += 1
        self.sleep = min(MAX_SLEEP, self.sleep * 1.5)


class FetchFailed(Exception):
    """GBIF could not be read for this species — NOT the same as 'no records'.

    The distinction is the whole point. The first run recorded a rate-limited
    species as having no georeferenced records, which reads as 'this plant
    grows nowhere' — the exact class of unsourced claim this pipeline exists to
    remove. A failure has to be visible and re-runnable instead.
    """


def _get_json(url: str, timeout: float, throttle: "_Throttle") -> dict:
    """GET and parse, retrying through 429s. Raises :class:`FetchFailed`.

    Deliberately not ``src.http_utils.http_get_json``: that returns ``None`` on
    every failure, which is right for the app (offline-first, degrade quietly)
    and wrong here, where "the server told us to slow down" and "there is no
    data" must not look alike.
    """
    last = ""
    for attempt, wait in enumerate((0, *RETRY_WAITS)):
        if wait:
            time.sleep(wait)
        try:
            req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                return json.loads(resp.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            last = f"HTTP {exc.code}"
            if exc.code == 429:
                throttle.rate_limited()
                # GBIF sometimes says how long to wait. When it does, obey it
                # rather than guessing.
                retry_after = exc.headers.get("Retry-After") if exc.headers else None
                if retry_after:
                    try:
                        time.sleep(min(300, float(retry_after)))
                    except (TypeError, ValueError):
                        pass
                print(f"    · rate limited (429), backing off "
                      f"{RETRY_WAITS[min(attempt, len(RETRY_WAITS) - 1)]}s "
                      f"— pacing now {throttle.sleep:.1f}s/request")
                continue
            if 500 <= exc.code < 600:
                continue                     # transient server error, retry
            raise FetchFailed(last) from exc
        except (urllib.error.URLError, TimeoutError, OSError) as exc:
            last = str(exc)
            continue
        except ValueError as exc:            # non-JSON body
            raise FetchFailed(f"non-JSON response: {exc}") from exc
    raise FetchFailed(last or "gave up after retries")


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

def fetch_occurrences(scientific_name: str, *, verbose: bool = False,
                      throttle: "_Throttle | None" = None,
                      bbox: tuple[float, float, float, float] | None = None
                      ) -> list[tuple[float, float]]:
    """Georeferenced occurrence coordinates for one species, inside the bbox.

    Filters GBIF-side to records that have coordinates, no recorded geospatial
    issue, and a position within the shipped polygons' bounding box; filters
    here to wild occurrences (see EXCLUDED_BASES).

    Raises :class:`FetchFailed` rather than returning ``[]`` when GBIF could
    not be read. An empty list means "GBIF has no records here", which is a
    real finding; a failure is not, and conflating them is what made the first
    run report 208 species as growing nowhere.
    """
    throttle = throttle or _Throttle()
    lat_min, lat_max, lng_min, lng_max = bbox or polygon_bbox()

    points: list[tuple[float, float]] = []
    offset = 0
    while offset < MAX_RECORDS_PER_SPECIES:
        query = urlencode({
            "scientificName": scientific_name,
            "hasCoordinate": "true",
            "hasGeospatialIssue": "false",
            # Server-side geography: everything outside the polygons is
            # discarded downstream anyway, so fetching it is pure cost — and it
            # is the cost that got the first run throttled.
            "decimalLatitude": f"{lat_min},{lat_max}",
            "decimalLongitude": f"{lng_min},{lng_max}",
            "limit": PAGE_SIZE,
            "offset": offset,
        })
        data = _get_json(f"{GBIF_SEARCH}?{query}", 60.0, throttle)
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
        throttle.wait()
    return points


# ── The run ─────────────────────────────────────────────────────────────────

def derive(names: list[str], *, min_records: int, verbose: bool,
           fetch=fetch_occurrences, throttle: "_Throttle | None" = None,
           on_progress=None) -> tuple[dict, dict, list, list]:
    """``(species_ranges, dropped, no_records, failed)`` for a list of species.

    ``failed`` is separate from ``no_records`` on purpose: a species GBIF
    refused to answer for has NOT been shown to grow nowhere, and the run
    should be re-runnable for exactly those.

    ``fetch`` is injectable so the tests can drive this without a network —
    which is the only way the threshold behaviour (2 records versus 3) is
    testable at all. ``on_progress(species_ranges)`` is called periodically so
    a long run can checkpoint its output to disk.
    """
    from src.ecoregion_ranges import ranges_for_species, dropped_regions

    throttle = throttle or _Throttle()
    species_ranges: dict[str, list[dict]] = {}
    dropped: dict[str, dict[str, int]] = {}
    no_records: list[str] = []
    failed: list[tuple[str, str]] = []

    for i, name in enumerate(names, 1):
        try:
            points = fetch(name, verbose=verbose, throttle=throttle)
        except TypeError:
            # An injected test double with the old signature.
            points = fetch(name, verbose=verbose)
        except FetchFailed as exc:
            failed.append((name, str(exc)))
            print(f"[{i}/{len(names)}] {name}: COULD NOT FETCH ({exc}) "
                  f"— will need a re-run, NOT recorded as absent")
            throttle.wait()
            continue

        if not points:
            no_records.append(name)
            if verbose:
                print(f"[{i}/{len(names)}] {name}: no records in range")
            throttle.wait()
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
        if on_progress is not None and i % 25 == 0:
            on_progress(species_ranges)
        throttle.wait()

    return species_ranges, dropped, no_records, failed


def load_existing() -> dict[str, list[dict]]:
    """Species already derived in a previous run — what ``--resume`` skips.

    Only species with ROWS count as done. A species with no rows might have
    been a genuine absence or might have been a rate-limit casualty, and there
    is no way to tell after the fact, so a resume retries it. That makes a
    throttled run self-healing rather than something to redo from scratch.
    """
    from src.ecoregion_ranges import parse_document
    try:
        with open(OUTPUT_PATH, encoding="utf-8") as f:
            return parse_document(json.load(f))
    except (FileNotFoundError, json.JSONDecodeError, OSError):
        return {}


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
    p.add_argument("--resume", action="store_true",
                   help="Skip species that already have rows in the output "
                        "file. Species with no rows are retried, so a run that "
                        "hit GBIF's rate limit heals itself.")
    p.add_argument("--sleep", type=float, default=POLITE_SLEEP,
                   help=f"Seconds between GBIF calls (default {POLITE_SLEEP}). "
                        "Raised automatically for the rest of the run on a 429.")
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

    existing: dict[str, list[dict]] = {}
    if args.resume:
        existing = load_existing()
        before = len(names)
        names = [n for n in names if n not in existing]
        print(f"--resume: {len(existing)} species already derived, "
              f"{before - len(names)} skipped, {len(names)} to go.")

    if not names:
        print("Nothing to do." if args.resume
              else "No species found — is data/plants_master.json present?")
        return 0 if args.resume else 1

    lat_min, lat_max, lng_min, lng_max = polygon_bbox()
    throttle = _Throttle(args.sleep)

    print(f"Deriving ecoregion ranges for {len(names)} species from GBIF "
          f"(min {min_records} records per region, {throttle.sleep:.1f}s "
          f"between calls).")
    print(f"Querying only lat {lat_min:.1f}..{lat_max:.1f}, "
          f"lng {lng_min:.1f}..{lng_max:.1f} — records outside the polygons "
          f"are never counted, so there is no reason to download them.\n")

    def checkpoint(partial: dict):
        """Write what we have so far, so an interrupt is not a lost harvest."""
        if args.dry_run:
            return
        merged = dict(existing)
        merged.update(partial)
        _write(merged, min_records)

    ranges, dropped, no_records, failed = derive(
        names, min_records=min_records, verbose=verbose,
        throttle=throttle, on_progress=checkpoint)

    merged = dict(existing)
    merged.update(ranges)

    print()
    print(f"  {len(merged)} species with at least one region "
          f"({len(ranges)} from this run)")
    print(f"  {len(no_records)} species with no records inside the polygons")
    if failed:
        print(f"  {len(failed)} species COULD NOT BE FETCHED — these are NOT "
              f"recorded as absent. Re-run with --resume to retry them:")
        for name, why in failed[:20]:
            print(f"      {name}: {why}")
        if len(failed) > 20:
            print(f"      … and {len(failed) - 20} more")
    if throttle.limited:
        print(f"  GBIF rate-limited us {throttle.limited} time(s); pacing "
              f"ended at {throttle.sleep:.1f}s/request. Re-run with --resume "
              f"(and --sleep {throttle.sleep:.1f}) if anything failed.")
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

    _write(merged, min_records)
    print(f"\nWrote {OUTPUT_PATH.relative_to(PROJECT_ROOT)} "
          f"({len(merged)} species)")
    if failed:
        print("Re-run with --resume before committing — some species are "
              "missing because GBIF refused, not because they grow nowhere.")
        return 2
    print("Next: bump _SCHEMA_VERSION in src/db/plants.py so existing installs "
          "reseed, then commit both.")
    return 0


def _write(species_ranges: dict, min_records: int) -> None:
    from src.ecoregion_ranges import build_document
    doc = build_document(
        species_ranges,
        source=f"GBIF occurrence search, retrieved {date.today().isoformat()}",
        generated=date.today().isoformat(),
        min_records=min_records)
    OUTPUT_PATH.write_text(json.dumps(doc, indent=2, ensure_ascii=False) + "\n",
                           encoding="utf-8")


if __name__ == "__main__":
    sys.exit(main())
