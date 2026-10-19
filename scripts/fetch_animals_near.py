#!/usr/bin/env python3
"""
fetch_animals_near.py — how often each animal is recorded near each region
pack's centre (V3.36, F190 and F249; docs/plans/V3.36-animals-that-belong-here.md).

Run on a computer with an internet connection (this project's cloud sessions
cannot reach GBIF):

    python scripts/fetch_animals_near.py --probe
    python scripts/fetch_animals_near.py

``data/fetched/fauna_nativity.json`` already says how many times each of the
1,144 animals has been recorded in Alberta and in Saskatchewan. That cannot
tell a mountain bird from a backyard one: the White-tailed Ptarmigan has 1,955
Alberta records, all in the Rockies, and it was drawn in Edmonton yards
(F190: the three ptarmigans appear in 28% of simulated designs). The missing
number is the records **near the yard**: within a region pack's own circle
(``data/regions/<key>/region.json``, 50 km of downtown Edmonton), the same
circle the Edmonton plant list uses.

The same number answers F249, *the animals an Edmonton homeowner knows*: how
often people record an animal near Edmonton is a fair first measure of how
often people notice it there. A session drafts the ~30 from it, and the owner
corrects the draft.

1. ``--probe`` asks about four animals, two ways, and prints the counts: the
   Black-capped Chickadee (thousands expected), the White-tailed Ptarmigan
   (none or nearly), the Monarch and the Tri-coloured Bumble Bee. It asks by
   GBIF's circle filter (``geoDistance``) and by the circle's box, so a filter
   GBIF ignores shows up as two counts that disagree wildly or a refusal.
2. With no options it asks once per animal per pack: about twenty minutes for
   Edmonton at GBIF's pace. It caches to ``data/fetched/animals_near.json``;
   stop it any time (Ctrl+C) and the next run carries on. Send that file to a
   session.

Living specimens (zoos) and fossils are left out, as the province counts did.
**A failure is not an absence**: an animal GBIF would not answer for is left
uncounted and asked again next run, never written down as zero.
"""

from __future__ import annotations

import argparse
import datetime as dt
import functools
import json
import math
import os
import sys
from urllib.parse import urlencode

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, _ROOT)
sys.path.insert(0, os.path.join(_ROOT, "scripts"))

import fetch_fauna_nativity as nativity  # noqa: E402

OUT = os.path.join(_ROOT, "data", "fetched", "animals_near.json")
#: Every basis of record GBIF has except the ones a person put there (zoos,
#: samples) and fossils, which ``fetch_fauna_nativity.EXCLUDED_BASES`` names.
BASES = ("HUMAN_OBSERVATION", "OBSERVATION", "MACHINE_OBSERVATION",
         "PRESERVED_SPECIMEN", "OCCURRENCE", "MATERIAL_CITATION")
PROBE = (("Poecile atricapillus", "thousands: the chickadee at every feeder"),
         ("Lagopus leucura", "none or nearly: a bird of the Rockies"),
         ("Danaus plexippus", "a few: a summer stray this far north"),
         ("Bombus ternarius", "some: a common bumble bee here"))


@functools.lru_cache(maxsize=1)
def gbif():
    """The ecoregion seeder's GBIF machinery (its throttle, its 429 backoff,
    ``FetchFailed``), loaded once: one rate-limit policy for the repo."""
    return nativity._seeder()


def packs() -> list:
    """``[(key, (lat, lng), radius_km), ...]`` for every region pack."""
    from src.region import regions                            # noqa: PLC0415
    return [(key, tuple(r.centre), float(r.radius_km))
            for key, r in sorted(regions().items())]


def box(centre: tuple, radius_km: float) -> tuple:
    """The circle's bounding box, ``(lat_min, lat_max, lng_min, lng_max)``."""
    lat, lng = centre
    dlat = radius_km / 111.32
    dlng = radius_km / (111.32 * math.cos(math.radians(lat)))
    return (lat - dlat, lat + dlat, lng - dlng, lng + dlng)


def query(name: str, centre: tuple, radius_km: float, *,
          by_box: bool = False) -> str:
    """The GBIF occurrence search that counts ``name`` near ``centre``."""
    params = [("scientificName", name), ("hasCoordinate", "true"),
              ("hasGeospatialIssue", "false"), ("limit", "0")]
    params += [("basisOfRecord", b) for b in BASES]
    if by_box:
        lat_min, lat_max, lng_min, lng_max = box(centre, radius_km)
        params += [("decimalLatitude", f"{lat_min:.4f},{lat_max:.4f}"),
                   ("decimalLongitude", f"{lng_min:.4f},{lng_max:.4f}")]
    else:
        params.append(("geoDistance",
                       f"{centre[0]},{centre[1]},{radius_km:g}km"))
    return f"{gbif().GBIF_SEARCH}?{urlencode(params)}"


def count(mod, name: str, centre: tuple, radius_km: float, throttle, *,
          by_box: bool = False) -> int:
    """Records of ``name`` near ``centre``. Raises the seeder's
    ``FetchFailed`` rather than returning 0."""
    url = query(name, centre, radius_km, by_box=by_box)
    data = mod._get_json(url, 60.0, throttle)
    if "count" not in data:
        raise mod.FetchFailed(f"no 'count' in GBIF's answer: {sorted(data)}")
    return int(data["count"])


def animals() -> list:
    """``[(scientific_name, common_name, taxon), ...]`` from the catalogue."""
    with open(os.path.join(_ROOT, "data", "fauna_master.json"),
              encoding="utf-8") as fh:
        rows = json.load(fh)
    return [(r["scientific_name"], r.get("common_name") or "",
             r.get("taxon") or "") for r in rows if r.get("scientific_name")]


def load() -> dict:
    try:
        with open(OUT, encoding="utf-8") as fh:
            return json.load(fh)
    except FileNotFoundError:
        return {"version": 1, "packs": {}}


def save(blob: dict) -> None:
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    tmp = OUT + ".tmp"
    with open(tmp, "w", encoding="utf-8") as fh:
        json.dump(blob, fh, indent=1, ensure_ascii=False, sort_keys=True)
    os.replace(tmp, OUT)


def probe(mod, throttle) -> int:
    key, centre, radius = packs()[0]
    print(f"Counting near {key} ({centre[0]}, {centre[1]}), {radius:g} km\n")
    bad = 0
    for name, expect in PROBE:
        try:
            circle = count(mod, name, centre, radius, throttle)
            throttle.wait()
            square = count(mod, name, centre, radius, throttle, by_box=True)
            throttle.wait()
        except mod.FetchFailed as exc:
            print(f"  {name:22s} FAILED: {exc}")
            bad += 1
            continue
        print(f"  {name:22s} circle {circle:>7d}   box {square:>7d}   "
              f"(expected {expect})")
        if circle > square:
            print("    the circle counted more than the box around it: "
                  "GBIF is not applying the circle filter")
            bad += 1
    print("\nThe box is about a quarter bigger than the circle, so the box "
          "count should be a little higher, never lower.")
    if bad:
        print("Something is not as this script expects. Send this output "
              "to a session before the full run.")
        return 1
    return 0


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--probe", action="store_true",
                    help="four animals, two ways; writes nothing")
    ap.add_argument("--limit", type=int, default=0,
                    help="ask about at most this many animals this run")
    args = ap.parse_args(argv)
    mod = gbif()
    throttle = mod._Throttle()
    if args.probe:
        return probe(mod, throttle)
    blob = load()
    everyone = animals()
    for key, centre, radius in packs():
        pack = blob["packs"].setdefault(key, {})
        pack.update(centre=list(centre), radius_km=radius)
        counts = pack.setdefault("animals", {})
        todo = [a for a in everyone if a[0] not in counts]
        if args.limit:
            todo = todo[:args.limit]
        print(f"{key}: {len(everyone)} animals, asking about {len(todo)} "
              f"(about {len(todo) * throttle.sleep / 60:.0f} minutes)")
        failed = 0
        try:
            for n, (name, common, _taxon) in enumerate(todo, 1):
                try:
                    counts[name] = count(mod, name, centre, radius, throttle)
                except mod.FetchFailed as exc:
                    failed += 1
                    print(f"  {n:4d}/{len(todo)} {common or name}: not "
                          f"answered ({exc}); asked again next run")
                    continue
                finally:
                    throttle.wait()
                if n % 25 == 0 or n == len(todo):
                    print(f"  {n:4d}/{len(todo)} {common or name}: "
                          f"{counts[name]} records")
                    pack["fetched"] = dt.date.today().isoformat()
                    save(blob)
        except KeyboardInterrupt:
            print("\nStopped. What was counted is kept; run again to carry on.")
            save(blob)
            return 0
        pack["fetched"] = dt.date.today().isoformat()
        save(blob)
        if failed:
            print(f"{failed} not answered; run the same command again.")
    print(f"\nSaved {OUT}. Send that file to a session.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
