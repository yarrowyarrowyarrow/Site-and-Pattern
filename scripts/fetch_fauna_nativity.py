#!/usr/bin/env python3
"""
scripts/fetch_fauna_nativity.py — is this animal actually found in AB or SK?

**Run this on a machine with internet.** The container's egress policy answers
403 to CONNECT for ``api.gbif.org``, same as the ecoregion seeder, so this is
the half that has to happen on your side.

    python3 scripts/fetch_fauna_nativity.py --probe     # 3 requests, seconds
    python3 scripts/fetch_fauna_nativity.py             # the real run
    python3 scripts/fetch_fauna_nativity.py --held      # only the 2,898 held

Why this exists
---------------
The catalogue asserts nativity as **a boolean nobody sourced**. 142 of its 167
``fauna`` rows carry ``ab_native = 1`` and no province data at all; only the 25
birds added in V2.60 have ``native_provinces``. Meanwhile F125 left 2,898
animals held precisely *because* nobody could say whether they belong here, and
that question cannot be answered 2,898 times by hand.

GBIF can answer it mechanically. One occurrence query per species per province
gives a count of georeferenced records, and the count travels with the claim so
"three records" and "three thousand" stay visibly different statements (P9).

**OCCURRENCE IS NOT NATIVITY, and this file must never pretend otherwise.**
A European Starling has tens of thousands of Alberta records and is introduced.
A Drone Fly is abundant here and came from Europe. So the run also asks GBIF
for its ``establishmentMeans`` facet, and the ingest gate treats
*introduced* / *invasive* / *managed* as disqualifying however many records
back them. Where GBIF says nothing — which is most of the time — the honest
output is "occurs here, origin unstated", and the ingester requires a human
verdict for anything it cannot rule in.

What one request buys
---------------------
``limit=0`` returns the match count without any records, and
``facet=establishmentMeans`` rides along free. So this is **one request per
species per province**, not a paged harvest: ~6,100 requests at a polite
1/second, a little under two hours. The ecoregion seeder pages through every
record and took far longer; counting does not need the records.

The province boxes, and where they lie
--------------------------------------
Alberta and Saskatchewan are surveyed rectangles, which is a rare gift: 49°N to
60°N, and meridians at 110°W (their shared border) and 101.36°W (SK's east
edge). So a bounding box is very nearly the province.

The one real exception: **Alberta's western border follows the continental
divide south of 54°N**, not the 120°W meridian, so the box overshoots into
British Columbia by up to ~1.5° of longitude at the southern end. Records in
that sliver are in the Rockies within kilometres of the border, which is why
it is accepted rather than corrected — but it is an overshoot, it inflates
Alberta counts for montane species, and it is written down here rather than
discovered later.
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import os
import sys
import time
from urllib.parse import urlencode

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, _ROOT)
_DATA = os.path.join(_ROOT, "data")
_OUT_DIR = os.path.join(_DATA, "fetched")
_OUT = os.path.join(_OUT_DIR, "fauna_nativity.json")


def _seeder():
    """The ecoregion seeder's GBIF machinery, imported rather than retyped.

    Its throttle, its 429 backoff and its `FetchFailed`-is-not-zero rule were
    all paid for by a run that got rate-limited after 228 species and recorded
    every throttled one as "grows nowhere". One rate-limit policy for the whole
    repo is the point; a second copy would drift from it.
    """
    path = os.path.join(_ROOT, "scripts", "seed_ecoregion_ranges.py")
    spec = importlib.util.spec_from_file_location("seed_ecoregion_ranges", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


#: ``code → (lat_min, lat_max, lng_min, lng_max)``. See the module docstring
#: for the Alberta overshoot.
PROVINCE_BOXES = {
    "AB": (49.0, 60.0, -120.0, -110.0),
    "SK": (49.0, 60.0, -110.0, -101.36),
}

#: GBIF ``establishmentMeans`` values that disqualify a species however many
#: records it has. Matched case-insensitively on a substring, because GBIF
#: carries both the Darwin Core vocabulary and free text from publishers.
DISQUALIFYING = ("introduc", "invasiv", "managed", "cultivat", "captiv")

#: Bases of record that are places a person put the animal, not places it
#: lives. Same reasoning as the ecoregion seeder's list.
EXCLUDED_BASES = {"LIVING_SPECIMEN", "MATERIAL_SAMPLE", "FOSSIL_SPECIMEN"}


def _rows(path: str) -> list:
    with open(path, "r", encoding="utf-8") as fh:
        blob = json.load(fh)
    return blob if isinstance(blob, list) else next(
        v for v in blob.values() if isinstance(v, list))


def targets(held_only: bool = False) -> list:
    """Every animal worth asking about: the catalogue's, and the held ones.

    ``held_only`` still *reads* the catalogue — it just does not emit those
    rows. Skipping the read entirely would re-ask about the 25 birds already
    curated in V2.60, which is the opposite of what "only the held ones" means.
    """
    out, seen = [], set()
    for r in _rows(os.path.join(_DATA, "fauna_master.json")):
        if isinstance(r, dict) and r.get("scientific_name"):
            seen.add(r["scientific_name"])
            if not held_only:
                out.append({"scientific_name": r["scientific_name"],
                            "taxon": r.get("taxon", ""), "in_catalogue": True})
    path = os.path.join(_OUT_DIR, "fauna_new_species.json")
    if os.path.exists(path):
        for r in _rows(path):
            if r.get("scientific_name") and r["scientific_name"] not in seen:
                out.append({"scientific_name": r["scientific_name"],
                            "taxon": r.get("taxon", ""), "in_catalogue": False})
                seen.add(r["scientific_name"])
    return out


def count_in_box(mod, name: str, box: tuple, throttle) -> tuple:
    """``(count, establishment_values)`` for one species in one box.

    ``limit=0`` asks GBIF for the match count and no records, so this is one
    request rather than a paged harvest, and the ``establishmentMeans`` facet
    rides along at no extra cost.

    Raises the seeder's ``FetchFailed`` rather than returning 0. **A failure is
    not an absence** — recording a rate-limited species as "not found in
    Alberta" would be exactly the unsourced claim this pipeline exists to
    remove, arriving through the back door.
    """
    lat_min, lat_max, lng_min, lng_max = box
    query = urlencode({
        "scientificName": name,
        "hasCoordinate": "true",
        "hasGeospatialIssue": "false",
        "decimalLatitude": f"{lat_min},{lat_max}",
        "decimalLongitude": f"{lng_min},{lng_max}",
        "facet": "establishmentMeans",
        "facetLimit": 10,
        "limit": 0,
    })
    data = mod._get_json(f"{mod.GBIF_SEARCH}?{query}", 60.0, throttle)
    count = int(data.get("count") or 0)
    means = []
    for facet in data.get("facets") or []:
        if facet.get("field") == "ESTABLISHMENT_MEANS":
            means = [c.get("name", "") for c in facet.get("counts") or []]
    return count, means


def assess(ab: int, sk: int, means: list) -> dict:
    """Turn counts into a verdict, saying which parts are measured.

    Three separate things, deliberately not collapsed into one boolean:

    ``provinces``  where GBIF actually holds records. Measured.
    ``origin``     native / introduced / unstated. Mostly **unstated**, because
                   GBIF's ``establishmentMeans`` is empty far more often than
                   not, and an empty field is the absence of a claim rather
                   than a claim of nativeness (P9 — absent is not estimated).
    ``verdict``    what the ingest gate should do: ``accept`` needs records
                   here AND nothing disqualifying; ``reject`` is a positive
                   statement that it is introduced; ``review`` is everything
                   else, including "present but origin unstated".
    """
    provinces = ",".join(p for p, n in (("AB", ab), ("SK", sk)) if n > 0)
    blob = " ".join(means).lower()
    disqualified = any(w in blob for w in DISQUALIFYING)
    if disqualified:
        origin, verdict = "introduced", "reject"
    elif not provinces:
        origin, verdict = "unstated", "reject"
    elif any("native" in m.lower() for m in means):
        origin, verdict = "native", "accept"
    else:
        origin, verdict = "unstated", "review"
    return {"provinces": provinces, "ab_records": ab, "sk_records": sk,
            "origin": origin, "establishment_means": means,
            "verdict": verdict}


def _save(blob) -> None:
    os.makedirs(_OUT_DIR, exist_ok=True)
    tmp = _OUT + ".tmp"
    with open(tmp, "w", encoding="utf-8") as fh:
        json.dump(blob, fh, indent=1, ensure_ascii=False, sort_keys=True)
    os.replace(tmp, _OUT)          # atomic: a Ctrl-C never leaves half a file


def main() -> int:
    ap = argparse.ArgumentParser(description="AB/SK occurrence per animal.")
    ap.add_argument("--probe", action="store_true",
                    help="three species, to prove the query shape works")
    ap.add_argument("--held", action="store_true",
                    help="only the held animals, not the catalogue's own")
    ap.add_argument("--limit", type=int, default=0)
    args = ap.parse_args()

    mod = _seeder()
    throttle = mod._Throttle()

    if args.probe:
        # One that must be here, one that must not, one that is here and
        # introduced. If the third does not come back disqualified, the
        # establishmentMeans facet is not usable and the gate needs rethinking
        # BEFORE two hours are spent on a full run.
        for name, expect in (("Danaus plexippus", "present in AB"),
                             ("Callipepla gambelii", "absent — desert quail"),
                             ("Sturnus vulgaris", "present but INTRODUCED")):
            try:
                ab, means = count_in_box(mod, name, PROVINCE_BOXES["AB"],
                                         throttle)
                sk, _ = count_in_box(mod, name, PROVINCE_BOXES["SK"], throttle)
            except Exception as exc:                       # noqa: BLE001
                print(f"  {name:24s} FAILED — {exc}")
                continue
            a = assess(ab, sk, means)
            print(f"  {name:24s} AB={ab:<7d} SK={sk:<7d} "
                  f"{a['verdict']:7s} {a['origin']:11s} {means or '(no facet)'}")
            print(f"  {'':24s} expected: {expect}")
            throttle.wait()
        print("\nIf Sturnus vulgaris does not come back 'reject/introduced', "
              "GBIF is not populating establishmentMeans for these taxa — say "
              "so before starting the real run.")
        return 0

    todo = targets(held_only=args.held)
    if args.limit:
        todo = todo[:args.limit]
    have = {}
    if os.path.exists(_OUT):
        with open(_OUT, "r", encoding="utf-8") as fh:
            have = json.load(fh)
    todo = [t for t in todo if t["scientific_name"] not in have]
    print(f"{len(todo)} animals to check "
          f"({len(have)} already done) — 2 requests each, ~1/second")

    failed = []
    for i, t in enumerate(todo, 1):
        name = t["scientific_name"]
        try:
            ab, means = count_in_box(mod, name, PROVINCE_BOXES["AB"], throttle)
            throttle.wait()
            sk, means_sk = count_in_box(mod, name, PROVINCE_BOXES["SK"],
                                        throttle)
        except mod.FetchFailed as exc:
            # NOT recorded as absent. It is left out of the file entirely so a
            # re-run picks it up, and the run says so at the end.
            failed.append((name, str(exc)))
            print(f"[{i}/{len(todo)}] {name}: FAILED ({exc}) — will retry")
            continue
        row = assess(ab, sk, sorted(set(means) | set(means_sk)))
        row["taxon"] = t["taxon"]
        row["in_catalogue"] = t["in_catalogue"]
        have[name] = row
        if i % 25 == 0 or i == len(todo):
            _save(have)
        print(f"[{i}/{len(todo)}] {name}: AB={ab} SK={sk} → "
              f"{row['verdict']} ({row['origin']})")
        throttle.wait()

    _save(have)

    import collections
    verdicts = collections.Counter(r["verdict"] for r in have.values())
    print("\n" + "=" * 62)
    for v in ("accept", "review", "reject"):
        print(f"  {v:8s} {verdicts.get(v, 0):5d}")
    print(f"  written to {os.path.relpath(_OUT, _ROOT)}")
    if failed:
        print(f"\n  {len(failed)} FAILED and are absent from the file rather "
              f"than recorded as zero. Re-run to pick them up.")
    print("=" * 62)
    print("\nCommit that file; the ingest side takes it from there.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
