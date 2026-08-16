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
A European Starling has 267,995 Alberta records and is introduced. That is not
a hypothetical — it is the probe result that killed the first design.

So the two questions have two sources:

* **present?** — occurrence counts inside each province box. Solid: the probe
  gave a monarch 370/596 and a Sonoran desert quail 0/0.
* **introduced?** — GBIF's *checklist distributions*, not its occurrence
  records. ``facet=establishmentMeans`` on occurrences returns **nothing at
  all**, on any species tried, so it can never separate the two however many
  records there are. ``/species/match`` → ``/species/{key}/distributions``
  reads the per-country rows contributed by checklist datasets, **GRIIS** among
  them, and there the starling and the honeybee both come back ``INTRODUCED``.

The dead facet is still requested and still reported, purely so a future GBIF
change becomes visible rather than silently ignored.

Where the checklists say nothing — which will be most species, since they
cover vertebrates and known invasives far better than solitary bees — the
output is ``origin: unstated``: occurs here, origin unrecorded. The ingest gate
accepts those above the record floor, and that is an **inference, not a
measurement**; ``scripts/ingest_fauna_edges.py:nativity_verdict`` carries the
reasoning.

What the requests buy
---------------------
``limit=0`` returns the match count without any records, so presence is two
requests per species rather than a paged harvest. The checklist lookup is two
more and runs **only** where there are AB/SK records to justify it — a species
with none is refused on the count alone. The ecoregion seeder pages through
every record and took far longer; counting does not need the records.

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


GBIF_MATCH = "https://api.gbif.org/v1/species/match"
GBIF_SPECIES = "https://api.gbif.org/v1/species"


def establishment_from_checklists(mod, name: str, throttle) -> list:
    """``establishmentMeans`` for Canada, from GBIF's species checklists.

    **The occurrence facet does not work and this replaces it.** The V2.61
    probe asked GBIF for `facet=establishmentMeans` on three species and got
    *no facet at all* on any of them — including *Sturnus vulgaris*, which has
    267,995 Alberta records and is the textbook introduced bird. Occurrence
    records simply do not carry the field in practice, so faceting them can
    never separate introduced from native, however many records there are.

    Checklists do carry it. ``/species/match`` resolves a name to a backbone
    key and ``/species/{key}/distributions`` returns per-country rows
    contributed by checklist datasets — GRIIS, the Global Register of
    Introduced and Invasive Species, among them. That is the register built
    for this exact question.

    Two extra requests, so it runs **only for species that already have AB or
    SK records**: one with none is rejected on the occurrence count alone and
    asking further would be spending the author's evening on an answer that
    changes nothing.
    """
    try:
        m = mod._get_json(f"{GBIF_MATCH}?{urlencode({'name': name})}",
                          30.0, throttle)
    except mod.FetchFailed:
        return []
    key = m.get("usageKey") or m.get("speciesKey")
    if not key:
        return []
    throttle.wait()
    try:
        d = mod._get_json(f"{GBIF_SPECIES}/{key}/distributions?limit=200",
                          30.0, throttle)
    except mod.FetchFailed:
        return []
    out = set()
    seen_countries = set()
    for row in d.get("results") or []:
        val = (row.get("establishmentMeans") or "").strip()
        if not val:
            continue
        country = (row.get("country") or row.get("countryCode") or "").strip()
        if country:
            seen_countries.add(country)
        # **Canada only, strictly.** The first version skipped a row only when
        # it named a country that was not Canada — so every row with no country
        # field passed, and most of them have none. The result was "introduced
        # SOMEWHERE IN THE WORLD" read as "introduced to Canada", and the 2026
        # run duly flagged the Snow Goose (native to arctic Canada, feral in
        # Europe) and the Summer Tanager (introduced nowhere) as introduced,
        # while Ruffed Grouse, Alder Flycatcher and Red-eyed Vireo all came
        # back "conflicted".
        #
        # A row that does not say Canada is not evidence about Canada. Dropping
        # it may leave a species `unstated`, and unstated is the honest answer
        # when no checklist has judged it here.
        if "CANADA" not in country.upper() and country.upper() != "CA":
            continue
        out.add(val)
    # Deduplicated: distributions come from many checklist datasets and the
    # probe returned `['NATIVE'] * 9` for one monarch. Nine copies of a word
    # is not nine pieces of evidence, and 3,065 species of it would bloat the
    # file for nothing.
    return sorted(out), sorted(seen_countries)


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
    says_native = any("native" in m.lower() for m in means)
    if disqualified and says_native:
        # A checklist calls it native to Canada and another calls it
        # introduced. That is a real disagreement between sources, not a
        # value to resolve by picking the one that fires first — which is
        # what the first cut did, silently. It goes to a human.
        origin, verdict = "conflicted", "review"
    elif disqualified:
        origin, verdict = "introduced", "reject"
    elif not provinces:
        origin, verdict = "unstated", "reject"
    elif says_native:
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


def _recheck_origin(mod, throttle, have: dict) -> int:
    """Re-run only the checklist half, only where the answer can change."""
    todo = sorted(k for k, v in have.items()
                  if v.get("origin") != "unstated")
    print(f"re-checking {len(todo)} species whose origin is not already "
          f"`unstated` (of {len(have)}) — 2 requests each\n")
    changed = []
    for i, name in enumerate(todo, 1):
        row = have[name]
        try:
            means, countries = establishment_from_checklists(mod, name,
                                                             throttle)
        except mod.FetchFailed as exc:
            print(f"[{i}/{len(todo)}] {name}: FAILED ({exc}) — left as-is")
            continue
        new = assess(int(row.get("ab_records") or 0),
                     int(row.get("sk_records") or 0), means)
        if new["origin"] != row.get("origin"):
            changed.append((name, row.get("origin"), new["origin"]))
            print(f"[{i}/{len(todo)}] {name}: {row.get('origin')} → "
                  f"{new['origin']}  {means or '(no Canada row)'}")
        new["checklist_countries"] = countries
        new["taxon"] = row.get("taxon", "")
        new["in_catalogue"] = row.get("in_catalogue", False)
        have[name] = new
        if i % 25 == 0:
            _save(have)
        throttle.wait()
    _save(have)

    import collections
    print("\n" + "=" * 62)
    print(f"  {len(changed)} origins changed")
    for v in ("accept", "review", "reject"):
        print(f"  {v:8s} {sum(1 for r in have.values() if r['verdict'] == v):5d}")
    print(f"  still introduced: "
          f"{sum(1 for r in have.values() if r['origin'] == 'introduced')}")
    print(f"  still conflicted: "
          f"{sum(1 for r in have.values() if r['origin'] == 'conflicted')}")
    print("=" * 62)
    print("\nCommit the file again; the ingest side takes it from there.")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description="AB/SK occurrence per animal.")
    ap.add_argument("--probe", action="store_true",
                    help="three species, to prove the query shape works")
    ap.add_argument("--held", action="store_true",
                    help="only the held animals, not the catalogue's own")
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--recheck-origin", action="store_true",
                    help="redo only the checklist half, for species whose "
                         "origin is not already `unstated`")
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
                             ("Sturnus vulgaris", "present but INTRODUCED"),
                             ("Apis mellifera", "present but INTRODUCED")):
            try:
                ab, facet = count_in_box(mod, name, PROVINCE_BOXES["AB"],
                                         throttle)
                throttle.wait()
                sk, _ = count_in_box(mod, name, PROVINCE_BOXES["SK"], throttle)
                throttle.wait()
                checklist, countries = (
                    establishment_from_checklists(mod, name, throttle)
                    if ab + sk else ([], []))
            except Exception as exc:                       # noqa: BLE001
                print(f"  {name:24s} FAILED — {exc}")
                continue
            a = assess(ab, sk, facet + checklist)
            print(f"  {name:24s} AB={ab:<7d} SK={sk:<7d} "
                  f"{a['verdict']:7s} {a['origin']:11s}")
            print(f"  {'':24s} occurrence facet: {facet or '(none — expected)'}")
            print(f"  {'':24s} checklists (CA):  {checklist or '(none)'}")
            print(f"  {'':24s} countries seen:   "
                  f"{', '.join(countries[:8]) or '(none named)'}")
            print(f"  {'':24s} expected: {expect}")
            throttle.wait()
        print("\nThe two introduced species are the test. The occurrence "
              "facet is known dead — V2.61's probe got no facet at all, on a "
              "starling with 267,995 Alberta records — so the `checklists` "
              "line is the one that has to work.")
        print("If BOTH starling and honeybee show an empty checklist line, "
              "GBIF cannot tell us what is introduced and the gate needs a "
              "different source. Say so before starting the real run.")
        return 0

    have = {}
    if os.path.exists(_OUT):
        with open(_OUT, "r", encoding="utf-8") as fh:
            have = json.load(fh)

    if args.recheck_origin:
        # The cheap repair. The first run's Canada filter was a no-op, so
        # `origin` read "introduced somewhere on Earth" — Snow Goose and
        # Summer Tanager among the casualties. A stricter filter can only
        # REMOVE checklist values, so a species already `unstated` cannot
        # change and does not need re-asking. That turns a three-hour refetch
        # into a few minutes over the couple of hundred that can move.
        return _recheck_origin(mod, throttle, have)

    todo = targets(held_only=args.held)
    if args.limit:
        todo = todo[:args.limit]
    todo = [t for t in todo if t["scientific_name"] not in have]
    print(f"{len(todo)} animals to check ({len(have)} already done) — two "
          f"occurrence requests each, plus two more for the checklist lookup "
          f"where there are AB/SK records to justify it, at ~1/second")

    failed = []
    for i, t in enumerate(todo, 1):
        name = t["scientific_name"]
        try:
            ab, means = count_in_box(mod, name, PROVINCE_BOXES["AB"], throttle)
            throttle.wait()
            sk, means_sk = count_in_box(mod, name, PROVINCE_BOXES["SK"],
                                        throttle)
            # Only for species that are actually here. One with no AB/SK
            # records is rejected on the count alone, and two more requests
            # would buy an answer that changes nothing — which matters when
            # there are 3,065 of them.
            countries = []
            if ab + sk:
                throttle.wait()
                extra, countries = establishment_from_checklists(
                    mod, name, throttle)
                means_sk = list(means_sk) + extra
        except mod.FetchFailed as exc:
            # NOT recorded as absent. It is left out of the file entirely so a
            # re-run picks it up, and the run says so at the end.
            failed.append((name, str(exc)))
            print(f"[{i}/{len(todo)}] {name}: FAILED ({exc}) — will retry")
            continue
        row = assess(ab, sk, sorted(set(means) | set(means_sk)))
        # Kept for diagnosis, not for the verdict. The first run's Canada
        # filter was a no-op and nobody could tell from the output; with this
        # you can see at a glance whether GBIF named a country at all.
        row["checklist_countries"] = countries
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
