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
from typing import NamedTuple
from urllib.parse import urlencode

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

OUTPUT_PATH = PROJECT_ROOT / "data" / "plant_ecoregions.json"
PLANT_FILES = ("plants_master.json", "garden_plants.json")

GBIF_SEARCH = "https://api.gbif.org/v1/occurrence/search"
PAGE_SIZE = 300
#: Records fetched per species before the harvest stops asking.
#:
#: **It is not a neutral bound, and V2.77 measured what it costs.** GBIF's
#: default result order is newest-first, so for a plant with tens of thousands
#: of records this window is the last few years and nothing else. Sixteen
#: species in this catalogue sit at the cap; between them they hold 89,964
#: records dated 2021-2026 and **thirty-one** herbarium specimens. Saskatoon
#: Berry has 6,000 records, two of them specimens, none older than 2024.
#:
#: Raising it is the wrong fix -- it would multiply the harvest for every
#: species to rescue sixteen. `--specimen-pass` asks for the specimens as their
#: own query instead, which costs one request for most species, and
#: `fetch_occurrences(truncated=...)` makes hitting the cap visible so this
#: cannot go unnoticed again.
MAX_RECORDS_PER_SPECIES = 6000
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

# NOT filtered: identification quality. GBIF's
# `identificationVerificationStatus` is populated by a minority of publishers
# and is absent on most herbarium records, so requiring it would discard the
# best-determined material in the harvest to exclude nothing in particular.
# The decision is deliberate and is disclosed on the website's Method page
# rather than left for a reader to discover. `basisOfRecord` IS cached per
# record (below), so a future pass can weigh a determined specimen against a
# phone photograph without re-fetching.

#: Where the raw points go, so a re-derivation never needs the network again.
CACHE_PATH = PROJECT_ROOT / "data" / "fetched" / "plant_occurrences.json"
CACHE_VERSION = 1

#: A record whose own stated uncertainty is larger than this cannot place a
#: plant in a *region*, so it is not counted as evidence for one.
#:
#: 10 km is chosen against the geography rather than picked round: the
#: narrowest of the 24 ELC ecoregions is a few tens of kilometres across, so a
#: record uncertain to 10 km can still say which one it is in near the middle
#: and is refused near the edges by nothing at all — which is why this is a
#: floor and not the whole answer. Records with NO stated uncertainty are
#: KEPT: absent is not estimated (src/confidence.py), most herbarium sheets
#: state none, and dropping them would silently prefer phone photographs to
#: museum specimens.
MAX_COORD_UNCERTAINTY_M = 10_000.0


class Occurrence(NamedTuple):
    """One georeferenced record, with the provenance a re-run would need.

    **A NamedTuple, and lat/lng first, on purpose.** ``ranges_for_species``
    reads ``point[0]`` and ``point[1]``, so these drop straight into the
    existing derivation and into every test double that yields plain
    ``(lat, lng)`` pairs. The extra fields ride along for the cache.

    Why the cache exists at all (V2.75): until now the pipeline kept only the
    derived *counts*. That made every question about the derivation — a
    changed threshold, a corrected polygon, a boundary rule, or simply "where
    in the region are those records?" — cost a fresh harvest of ~400,000 GBIF
    records. It is why the 5 km buffer bug could be found here and not fixed
    here, and why the site could report a count and never a map.
    """

    lat: float
    lng: float
    uncertainty_m: float | None = None
    year: int | None = None
    basis: str = ""
    dataset_key: str = ""


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
                      bbox: tuple[float, float, float, float] | None = None,
                      basis_of_record: str = "",
                      truncated: list | None = None
                      ) -> list[tuple[float, float]]:
    """Georeferenced occurrence coordinates for one species, inside the bbox.

    Filters GBIF-side to records that have coordinates, no recorded geospatial
    issue, and a position within the shipped polygons' bounding box; filters
    here to wild occurrences (see EXCLUDED_BASES).

    ``basis_of_record`` narrows the query to one kind of record GBIF-side --
    ``"PRESERVED_SPECIMEN"`` for the herbarium sheets. This is not a
    convenience: see :data:`MAX_RECORDS_PER_SPECIES`. A harvest bounded at six
    thousand records, ordered newest-first, is four years of phone photographs
    for a common plant, and the century of specimens behind it never arrives.
    Asking for the specimens *as their own query* is the only way they can be
    reached at all.

    ``truncated`` is an optional list this appends to when the cap was hit
    before GBIF said ``endOfRecords`` -- so a caller can tell "GBIF had no more"
    apart from "we stopped asking", which is the distinction the cap had been
    silently erasing.

    Raises :class:`FetchFailed` rather than returning ``[]`` when GBIF could
    not be read. An empty list means "GBIF has no records here", which is a
    real finding; a failure is not, and conflating them is what made the first
    run report 208 species as growing nowhere.
    """
    throttle = throttle or _Throttle()
    lat_min, lat_max, lng_min, lng_max = bbox or polygon_bbox()

    points: list[Occurrence] = []
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
            **({"basisOfRecord": basis_of_record} if basis_of_record else {}),
        })
        data = _get_json(f"{GBIF_SEARCH}?{query}", 60.0, throttle)
        results = data.get("results") or []
        for rec in results:
            if (rec.get("basisOfRecord") or "") in EXCLUDED_BASES:
                continue
            lat, lng = rec.get("decimalLatitude"), rec.get("decimalLongitude")
            if lat is None or lng is None:
                continue
            unc = rec.get("coordinateUncertaintyInMeters")
            year = rec.get("year")
            points.append(Occurrence(
                # 4 dp is ~11 m, matching the shipped polygons' own rounding.
                # Storing more would be precision the join cannot use.
                lat=round(float(lat), 4),
                lng=round(float(lng), 4),
                uncertainty_m=float(unc) if unc is not None else None,
                year=int(year) if year else None,
                basis=(rec.get("basisOfRecord") or ""),
                dataset_key=(rec.get("datasetKey") or ""),
            ))
        if data.get("endOfRecords") or not results:
            break
        offset += PAGE_SIZE
        throttle.wait()
    else:
        # The `while` ran to its bound rather than breaking: GBIF still had
        # records and we stopped asking. Recorded, not assumed.
        if truncated is not None:
            truncated.append(scientific_name)
    return points


# ── The point cache, and what a point has to be worth ───────────────────────

def usable_points(points, *, max_uncertainty_m: float = MAX_COORD_UNCERTAINTY_M
                  ) -> tuple[list, int]:
    """``(points that can place a plant in a region, how many were refused)``.

    A record that states its own coordinate uncertainty is telling you what it
    can and cannot support, and the pipeline had never read it. A specimen
    georeferenced to "the county" carries an uncertainty in the tens of
    kilometres, and counting it toward one ecoregion asserts something its own
    metadata denies.

    This is the honest instrument for the objection a botanical review raised
    about boundaries — better than any threshold on *counts*, because it acts
    per record and for a stated reason rather than hoping errors average out.

    Records with no stated uncertainty are kept; see
    :data:`MAX_COORD_UNCERTAINTY_M`.
    """
    kept, refused = [], 0
    for point in points:
        unc = getattr(point, "uncertainty_m", None)
        if unc is not None and unc > max_uncertainty_m:
            refused += 1
            continue
        kept.append(point)
    return kept, refused


def write_cache(by_species: dict, *, path=CACHE_PATH, generated: str = "",
                source: str = "") -> dict:
    """Write the raw points, so no future question needs the network.

    Compact on purpose: a run is ~400,000 records, and one JSON object per
    record with six keys is several times the size of one array per record
    with two interned lookup tables. Both `basis` and `dataset_key` repeat
    across tens of thousands of rows, so they are stored once and referenced by
    index. The shape is documented in the file's own ``columns`` field, so it
    reads without this docstring.
    """
    bases: list[str] = []
    datasets: list[str] = []
    base_ix: dict[str, int] = {}
    ds_ix: dict[str, int] = {}

    def intern(value, table, index):
        if value not in index:
            index[value] = len(table)
            table.append(value)
        return index[value]

    species: dict[str, list] = {}
    for name in sorted(by_species):
        rows = []
        for pt in by_species[name]:
            unc = getattr(pt, "uncertainty_m", None)
            rows.append([
                round(float(pt[0]), 4), round(float(pt[1]), 4),
                None if unc is None else round(float(unc)),
                getattr(pt, "year", None),
                intern(getattr(pt, "basis", ""), bases, base_ix),
                intern(getattr(pt, "dataset_key", ""), datasets, ds_ix),
            ])
        species[name] = rows

    blob = {
        "version": CACHE_VERSION,
        "generated": generated or date.today().isoformat(),
        "source": source or "GBIF occurrence search",
        "comment": (
            "Raw georeferenced points behind data/plant_ecoregions.json, kept "
            "so a re-derivation costs nothing. Before V2.75 only the derived "
            "counts survived a run, so changing the threshold, correcting a "
            "polygon or drawing the records on a map all required re-fetching "
            "~400,000 records. Dev cache: the app never reads this."),
        "columns": ["lat", "lng", "uncertainty_m", "year",
                    "basis_index", "dataset_index"],
        "basis": bases,
        "datasets": datasets,
        "species": species,
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(blob, f, separators=(",", ":"))
        f.write("\n")
    return blob


def read_cache(path=CACHE_PATH) -> dict:
    """``{scientific_name: [Occurrence, ...]}`` from the cache, or ``{}``.

    The inverse of :func:`write_cache`, and the entry point for every offline
    consumer — ``scripts/plot_occurrences.py`` and any future re-derivation.
    """
    try:
        with open(path, encoding="utf-8") as f:
            blob = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError, OSError):
        return {}
    bases = blob.get("basis") or []
    datasets = blob.get("datasets") or []

    def name_at(table, i):
        return table[i] if isinstance(i, int) and 0 <= i < len(table) else ""

    out: dict[str, list] = {}
    for name, rows in (blob.get("species") or {}).items():
        points = []
        for row in rows or []:
            if not isinstance(row, list) or len(row) < 2:
                continue
            row = list(row) + [None] * (6 - len(row))
            points.append(Occurrence(
                lat=float(row[0]), lng=float(row[1]),
                uncertainty_m=None if row[2] is None else float(row[2]),
                year=row[3] if isinstance(row[3], int) else None,
                basis=name_at(bases, row[4]),
                dataset_key=name_at(datasets, row[5]),
            ))
        out[name] = points
    return out


# ── The run ─────────────────────────────────────────────────────────────────

def derive(names: list[str], *, min_records: int, verbose: bool,
           fetch=fetch_occurrences, throttle: "_Throttle | None" = None,
           on_progress=None, collect=None,
           tally: dict | None = None) -> tuple[dict, dict, list, list]:
    """``(species_ranges, dropped, no_records, failed)`` for a list of species.

    ``collect`` is an optional dict that receives ``{name: points}`` as they
    arrive — the raw harvest, before the uncertainty filter, so the cache holds
    what GBIF actually returned and the filter stays a derivation-time decision
    that can be revisited without re-fetching.

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

        if collect is not None:
            collect[name] = list(points)

        if not points:
            no_records.append(name)
            if verbose:
                print(f"[{i}/{len(names)}] {name}: no records in range")
            throttle.wait()
            continue

        points, refused = usable_points(points)
        if refused and verbose:
            print(f"[{i}/{len(names)}] {name}: {refused} record(s) too "
                  f"coarsely georeferenced to place in a region")

        rows = ranges_for_species(points, min_records=min_records,
                                  tally=tally)
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


#: The one basis of record a public dot map can be drawn from. Herbarium
#: sheets carry no rare-taxa coordinate obscuring (the sheet is already in a
#: cabinet with a label on it), and their licence is a fact about the whole
#: collection rather than a per-observer choice -- which is what the printed
#: regional floras plot, for both of those reasons.
SPECIMEN_BASIS = "PRESERVED_SPECIMEN"


def merge_into_cache(harvest: dict, *, path=CACHE_PATH) -> tuple[dict, dict]:
    """``(merged cache, {name: how many records were new})``.

    De-duplicates on ``(lat, lng, year, dataset_key)``. Not on the whole tuple:
    ``uncertainty_m`` and ``basis`` can be re-stated between GBIF exports for a
    record that is the same sheet in the same cabinet, and counting it twice
    would inflate exactly the number a confidence band is computed from.

    Not on ``(lat, lng)`` alone either. Two different collectors at the same
    trailhead in different decades are two records, and a dot map that silently
    collapsed them would under-report the very thing it is drawn to show.
    """
    merged = read_cache(path)
    added: dict[str, int] = {}
    for name, points in harvest.items():
        have = merged.get(name) or []
        seen = {(p[0], p[1], getattr(p, "year", None),
                 getattr(p, "dataset_key", "")) for p in have}
        fresh = []
        for pt in points:
            key = (pt[0], pt[1], getattr(pt, "year", None),
                   getattr(pt, "dataset_key", ""))
            if key in seen:
                continue
            seen.add(key)
            fresh.append(pt)
        if fresh:
            merged[name] = list(have) + fresh
            added[name] = len(fresh)
    return merged, added


def specimen_pass(names: list[str], *, throttle: "_Throttle | None" = None,
                  verbose: bool = True, fetch=fetch_occurrences
                  ) -> tuple[dict, list]:
    """``({name: specimen records}, failed)`` -- the herbarium half, on its own.

    Asked as its own GBIF query rather than filtered out of the general
    harvest, because the general harvest cannot reach it: see
    :data:`MAX_RECORDS_PER_SPECIES`. Most species answer in one request (GBIF
    returns the whole first page when there are fewer than ``PAGE_SIZE``), so
    running this over the entire catalogue costs minutes and needs no guess
    about which species were truncated.
    """
    throttle = throttle or _Throttle()
    harvest: dict[str, list] = {}
    failed: list[tuple[str, str]] = []
    for i, name in enumerate(names, 1):
        try:
            points = fetch(name, verbose=verbose, throttle=throttle,
                           basis_of_record=SPECIMEN_BASIS)
        except FetchFailed as exc:
            failed.append((name, str(exc)))
            print(f"[{i}/{len(names)}] {name}: COULD NOT FETCH ({exc}) "
                  f"-- NOT recorded as having no specimens")
            throttle.wait()
            continue
        harvest[name] = list(points)
        if verbose:
            print(f"[{i}/{len(names)}] {name}: {len(points)} specimen record(s)")
        throttle.wait()
    return harvest, failed


def cache_fetcher(cache: dict):
    """A ``fetch`` for :func:`derive` that reads the cache instead of GBIF.

    The cache was built so that no question about this derivation would ever
    need the network again, and until now nothing used it that way -- a changed
    threshold or a corrected polygon still meant a fresh harvest on a machine
    with egress. It also means the derivation can be re-run, and its diff read,
    in a session that has no egress at all.
    """
    def fetch(name, **_kwargs):
        return list(cache.get(name) or [])
    return fetch


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
    p.add_argument("--specimen-pass", action="store_true",
                   help="Fetch PRESERVED_SPECIMEN records as their own query "
                        "and merge them into the point cache. The general "
                        "harvest is capped and ordered newest-first, so for a "
                        "common plant it never reaches the herbarium sheets.")
    p.add_argument("--from-cache", action="store_true",
                   help="Re-derive from data/fetched/plant_occurrences.json "
                        "with NO network. Use after --specimen-pass, or after "
                        "any change to the polygons or the threshold.")
    p.add_argument("--quiet", action="store_true")
    args = p.parse_args(argv)

    from src.ecoregion_ranges import MIN_RECORDS, build_document
    min_records = args.min_records or MIN_RECORDS
    verbose = not args.quiet

    names = args.species or catalogue_species()
    if args.limit:
        names = names[:args.limit]

    if args.specimen_pass:
        return _run_specimen_pass(names, sleep=args.sleep, verbose=verbose,
                                  dry_run=args.dry_run)

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
    throttle = _Throttle(0.0 if args.from_cache else args.sleep)
    fetch = fetch_occurrences

    if args.from_cache:
        cache = read_cache()
        if not cache:
            print(f"No point cache at "
                  f"{CACHE_PATH.relative_to(PROJECT_ROOT)}. Run this script "
                  f"without --from-cache, on a machine with egress, first.",
                  file=sys.stderr)
            return 1
        fetch = cache_fetcher(cache)
        missing = [n for n in names if n not in cache]
        print(f"Re-deriving {len(names)} species from "
              f"{sum(len(v) for v in cache.values()):,} cached records "
              f"(min {min_records} per region). No network.")
        if missing:
            # Not silently absent: a species the cache never held would come
            # out of this run with no rows, which reads as "grows nowhere".
            one = len(missing) == 1
            print(f"  {len(missing)} of them "
                  f"{'is' if one else 'are'} NOT in the cache and will derive "
                  f"to nothing. {'It keeps its' if one else 'They keep their'} "
                  f"existing rows only if you run with --resume: "
                  f"{', '.join(missing[:6])}"
                  f"{' ...' if len(missing) > 6 else ''}")
        print()
    else:
        print(f"Deriving ecoregion ranges for {len(names)} species from GBIF "
              f"(min {min_records} records per region, {throttle.sleep:.1f}s "
              f"between calls).")
        print(f"Querying only lat {lat_min:.1f}..{lat_max:.1f}, "
              f"lng {lng_min:.1f}..{lng_max:.1f} — records outside the "
              f"polygons are never counted, so there is no reason to download "
              f"them.\n")

    # Bound before `checkpoint` closes over it, not merely before `derive`
    # calls it: the closure would resolve either way and only one of those is
    # a thing the next reader can see is safe.
    harvest: dict[str, list] = {}
    tally: dict = {}

    def checkpoint(partial: dict):
        """Write what we have so far, so an interrupt is not a lost harvest."""
        if args.dry_run:
            return
        merged = dict(existing)
        merged.update(partial)
        _write(merged, min_records, tally,
               from_cache=bool(args.from_cache))

    ranges, dropped, no_records, failed = derive(
        names, min_records=min_records, verbose=verbose, fetch=fetch,
        throttle=throttle, on_progress=checkpoint, tally=tally,
        collect=None if args.from_cache else harvest)

    merged = dict(existing)
    merged.update(ranges)

    print()
    print(f"  {len(merged)} species with at least one region "
          f"({len(ranges)} from this run)")
    print(f"  {len(no_records)} species with no records inside the polygons")
    seen = sum(tally.values())
    if seen:
        from src.ecoregion import SIMPLIFICATION_M
        print(f"  {tally.get('counted', 0):,} of {seen:,} records counted; "
              f"{tally.get('unsettled', 0):,} "
              f"({tally.get('unsettled', 0) / seen:.1%}) fell within "
              f"{SIMPLIFICATION_M:.0f} m of a border and count for no region; "
              f"{tally.get('outside', 0):,} were outside the layer")
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

    _write(merged, min_records, tally,
           from_cache=bool(args.from_cache))
    print(f"\nWrote {OUTPUT_PATH.relative_to(PROJECT_ROOT)} "
          f"({len(merged)} species)")

    # The raw points, so nothing after this needs the network (V2.75). A
    # partial run still writes what it got: the cache is a strict improvement
    # on nothing, and --resume merges the next run into it.
    if harvest:
        previous = read_cache()
        previous.update(harvest)
        write_cache(previous,
                    source=f"GBIF occurrence search, retrieved {date.today()}")
        records = sum(len(v) for v in previous.values())
        size_mb = CACHE_PATH.stat().st_size / 1_000_000
        print(f"Wrote {CACHE_PATH.relative_to(PROJECT_ROOT)} "
              f"({records:,} records over {len(previous)} species, "
              f"{size_mb:.1f} MB). Re-deriving from it needs no network — see "
              f"scripts/plot_occurrences.py.")
    if failed:
        print("Re-run with --resume before committing — some species are "
              "missing because GBIF refused, not because they grow nowhere.")
        return 2
    print("Next: bump _SCHEMA_VERSION in src/db/plants.py so existing installs "
          "reseed, then commit both.")
    return 0


def _run_specimen_pass(names: list[str], *, sleep: float, verbose: bool,
                       dry_run: bool) -> int:
    """``--specimen-pass``: the herbarium half, merged into the cache.

    Deliberately does NOT re-derive the ranges. Fetching and deriving are two
    decisions and the diff between them is the thing worth reading, so this
    ends by naming the command that does the second one.
    """
    if not read_cache():
        print(f"No point cache at {CACHE_PATH.relative_to(PROJECT_ROOT)}. "
              f"Run the full harvest first; a specimen pass merges into an "
              f"existing cache rather than standing in for one.",
              file=sys.stderr)
        return 1

    throttle = _Throttle(sleep)
    print(f"Asking GBIF for {SPECIMEN_BASIS} records for {len(names)} "
          f"species, as their own query.")
    print(f"The general harvest stops at {MAX_RECORDS_PER_SPECIES:,} records "
          f"per species and GBIF orders newest-first, so for a common plant "
          f"it is recent observations all the way down and the specimens "
          f"never arrive. This is how they are reached.\n")

    harvest, failed = specimen_pass(names, throttle=throttle, verbose=verbose)
    merged, added = merge_into_cache(harvest)

    fetched = sum(len(v) for v in harvest.values())
    gained = sum(added.values())
    print(f"\n  {fetched:,} specimen records fetched over {len(harvest)} "
          f"species; {gained:,} of them were not already cached.")
    empty = sorted(n for n, v in harvest.items() if not v)
    if empty:
        print(f"  {len(empty)} species have NO specimen records in range. That "
              f"is a real finding about the herbaria, not a fetch failure:")
        for name in empty[:20]:
            print(f"      {name}")
        if len(empty) > 20:
            print(f"      ... and {len(empty) - 20} more")
    if added:
        print("\n  Biggest gains (these are the species the cap was hiding):")
        for name, n in sorted(added.items(), key=lambda kv: -kv[1])[:15]:
            print(f"      +{n:5d}  {name}")
    if failed:
        print(f"\n  {len(failed)} species COULD NOT BE FETCHED and are NOT "
              f"recorded as specimen-free. Re-run for them:")
        for name, why in failed[:20]:
            print(f"      {name}: {why}")

    if dry_run:
        print("\n--dry-run: nothing written.")
        return 0
    if not gained:
        print("\nNothing new; cache left alone.")
        return 2 if failed else 0

    write_cache(merged,
                source=f"GBIF occurrence search + {SPECIMEN_BASIS} pass, "
                       f"retrieved {date.today().isoformat()}")
    records = sum(len(v) for v in merged.values())
    print(f"\nWrote {CACHE_PATH.relative_to(PROJECT_ROOT)} "
          f"({records:,} records over {len(merged)} species).")
    print("Next: re-derive from it with no network, and read the diff:")
    print("    python scripts/seed_ecoregion_ranges.py --from-cache")
    return 2 if failed else 0


def _retrieved_source(from_cache: bool) -> str:
    """What to write as ``source``, which is a *retrieval* date (V2.81).

    This said ``retrieved {today}`` unconditionally, and a ``--from-cache``
    re-derivation fetches nothing: the V2.81 run would have stamped
    "retrieved 2026-08-31" on a harvest taken on the 24th and published that
    on every species page, under a heading whose whole job is answering *as of
    when*. A derivation date and a retrieval date are two facts and only one of
    them is today's.
    """
    if not from_cache:
        return f"GBIF occurrence search, retrieved {date.today().isoformat()}"
    try:
        with open(CACHE_PATH, encoding="utf-8") as handle:
            cached = json.load(handle)
    except Exception:                                         # noqa: BLE001
        cached = {}
    stated = (cached.get("source") or "").strip()
    if stated:
        return stated
    when = (cached.get("generated") or "").strip()
    return (f"GBIF occurrence search, retrieved {when}" if when
            else "GBIF occurrence search, retrieval date not recorded")


def _write(species_ranges: dict, min_records: int,
           tally: dict | None = None, *, from_cache: bool = False) -> None:
    from src.ecoregion_ranges import build_document
    doc = build_document(
        species_ranges,
        source=_retrieved_source(from_cache),
        generated=date.today().isoformat(),
        min_records=min_records, tally=tally)
    OUTPUT_PATH.write_text(json.dumps(doc, indent=2, ensure_ascii=False) + "\n",
                           encoding="utf-8")


if __name__ == "__main__":
    sys.exit(main())
