#!/usr/bin/env python3
"""
scripts/fetch_flora_nativity.py — is this plant actually native to AB or SK?

**Run this on a machine with internet.** This container's egress policy answers
403 to CONNECT for ``data.canadensys.net``, same as it does for ``api.gbif.org``
(see ``scripts/fetch_fauna_nativity.py``, which is this script's model), so the
fetch is the half that has to happen on your side.

    python3 scripts/fetch_flora_nativity.py --probe    # 3 requests, seconds
    python3 scripts/fetch_flora_nativity.py            # the real run, ~430

Why this exists
---------------
An outside botanical review of the published catalogue said, of the plant data:

    "Many species said to be native to 'AB, SK' are only native in one or the
     other... A lot of species are listed using out-of-date names."

Both are true, and the second is the reason the first could not be fixed by
hand. Where the claim comes from today:

* ``native_to_alberta`` is a **hand-authored boolean** in the seed file, with
  no source field anywhere on a plant record.
* ``native_provinces`` is **generated from that flag plus the plant's
  ecoregion tags** by ``scripts/tag_prairie_provenance.py``, whose own
  docstring says Saskatchewan status is *"inferred from ecoregion continuity,
  not a per-species range map"*.
* ``native_region`` is free prose. 204 distinct strings, 125 of them the words
  "Western Canada".

So one editorial judgement wears four coats, and every downstream gate reads a
coat. 355 of 431 rows said exactly ``"AB,SK"``. Worse, the generator had gone
stale: V2.72 replaced the ecoregion vocabulary under it and a re-run at V2.75
would have moved 237 species, so the published field was the output of a
routine that would no longer produce it.

Why VASCAN, and why it answers two questions at once
----------------------------------------------------
VASCAN — the Database of Vascular Plants of Canada — was the authority the
review named first, and it is the right one for a Canadian catalogue:

* it records ``establishmentMeans`` **per province**, which is exactly the
  AB-versus-SK distinction nothing here can currently make;
* it is a **taxonomic backbone**, so the same request that settles nativity
  also returns the accepted name and flags a synonym. This catalogue has no
  authority field, no synonym list and no taxon key of any kind: a scientific
  name is a free string checked by one regex, which is how *Solidago rigida*
  and *Oligoneuron rigidum* both ship as separate species.

One request per species. ~430 requests settles both questions for the whole
catalogue.

**This script does not decide anything.** It writes what VASCAN said to
``data/fetched/flora_nativity.json``. ``scripts/ingest_flora_nativity.py``
reads that and *proposes*; a human applies. That split is not ceremony — it is
V2.59 (23 false Monarch hosts), V2.60 (62 good bird edges binned) and V2.64
(20 animals written connected to nothing), each of which was caught because
the apply step was separate and reviewed.

**The response shape here is a GUESS until --probe says otherwise, and that is
deliberate.** V2.59's worst hour went into a fetch that failed on all 55 plants
because the code guessed a field name and *the test fixture encoded the same
guess*, so the suite stayed green while both were wrong. So: the parser accepts
several plausible spellings of each field, ``--probe`` prints the raw JSON and
**what percentage of records populate each field**, and no test in this repo
asserts that VASCAN returns any particular key. Run the probe first. Read it.
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import date
from pathlib import Path
from urllib.parse import urlencode

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

VASCAN_SEARCH = "https://data.canadensys.net/vascan/api/0.1/search.json"

OUTPUT_PATH = PROJECT_ROOT / "data" / "fetched" / "flora_nativity.json"
FILE_VERSION = 1

#: The provinces this catalogue claims. Manitoba is asked for anyway: it costs
#: nothing in the same response, and "should MB be in scope" is an open
#: question the review raised. Knowing the answer before deciding is cheap.
PROVINCES = ("AB", "SK", "MB")

#: Field names this parser will accept for each thing it needs. VASCAN's
#: documented spelling is listed first; the alternates exist because a fetch
#: that returns nothing and says "no data" is indistinguishable from a species
#: with no record, and that ambiguity has cost this repo two increments.
_MATCH_KEYS = ("matches", "results", "taxa")
_DIST_KEYS = ("distribution", "distributions")
_MEANS_KEYS = ("establishmentMeans", "occurrenceStatus", "status")
_LOCATION_KEYS = ("locationID", "locationId", "location", "locality")
_ACCEPTED_KEYS = ("acceptedNameUsage", "acceptedName", "scientificName")
_STATUS_KEYS = ("taxonomicStatus", "status")

#: An origin word that disqualifies a native claim. Matched as a substring,
#: lowercased, because VASCAN writes "introduced" and GRIIS-style sources write
#: things like "introduced: adventive".
DISQUALIFYING = ("introduced", "ephemeral", "excluded", "extirpated",
                 "doubtful")


def _first(record: dict, keys, default=None):
    """The first of ``keys`` present and non-empty, or ``default``."""
    for key in keys:
        value = record.get(key)
        if value not in (None, "", [], {}):
            return value
    return default


def _seeder():
    """The GBIF seeder, reused for its throttle, retries and FetchFailed.

    Imported rather than copied: it already knows how to be a polite client
    that distinguishes "the server refused" from "there is no record", and
    conflating those is what made an earlier run report 208 species as growing
    nowhere.
    """
    import scripts.seed_ecoregion_ranges as seeder             # noqa: PLC0415
    return seeder


def catalogue_species() -> list[str]:
    from scripts.seed_ecoregion_ranges import catalogue_species as names
    return names()


# ── One species ─────────────────────────────────────────────────────────────

def lookup(name: str, *, throttle=None, get_json=None) -> dict:
    """VASCAN's answer for one scientific name, parsed but not judged.

    Returns ``{"matched", "accepted_name", "is_synonym", "taxonomic_status",
    "provinces": {code: means}, "raw_matches": n}``. Raises the seeder's
    ``FetchFailed`` if the server refused, which the caller must keep separate
    from "VASCAN has no record" — those are opposite facts.
    """
    mod = _seeder()
    get_json = get_json or mod._get_json
    throttle = throttle or mod._Throttle()
    query = urlencode({"q": name})
    data = get_json(f"{VASCAN_SEARCH}?{query}", 30.0, throttle)

    results = data.get("results") or []
    matches = []
    for result in results:
        matches = _first(result, _MATCH_KEYS, []) or []
        if matches:
            break

    out = {"matched": False, "accepted_name": "", "is_synonym": False,
           "taxonomic_status": "", "provinces": {}, "raw_matches": len(matches)}
    if not matches:
        return out

    # The first match. VASCAN returns synonyms alongside the accepted taxon;
    # picking by position is a simplification and `raw_matches` is reported so
    # a reviewer can see when there was more than one.
    match = matches[0]
    out["matched"] = True
    accepted = _first(match, _ACCEPTED_KEYS, "") or ""
    out["accepted_name"] = str(accepted)
    status = str(_first(match, _STATUS_KEYS, "") or "")
    out["taxonomic_status"] = status
    out["is_synonym"] = "synonym" in status.lower()

    for row in _first(match, _DIST_KEYS, []) or []:
        if not isinstance(row, dict):
            continue
        where = str(_first(row, _LOCATION_KEYS, "") or "").upper()
        code = where.split("-")[-1].strip()
        if code not in PROVINCES:
            continue
        means = str(_first(row, _MEANS_KEYS, "") or "").strip().lower()
        # A province present with no establishment word is `""`, not "native".
        # Absent is not estimated (src/confidence.py): VASCAN saying nothing
        # about origin is the absence of a claim, never a claim of nativeness.
        out["provinces"][code] = means
    return out


def assess(result: dict) -> dict:
    """What the catalogue should say, given what VASCAN said.

    Three separate fields, deliberately not collapsed:

    ``native_provinces``  the codes VASCAN calls native. Measured.
    ``origin``            ``native`` / ``introduced`` / ``unstated`` /
                          ``absent``. **``unstated`` is a real and expected
                          answer** and must never be rounded to a verdict.
    ``verdict``           what a reviewer should look at: ``confirm``,
                          ``narrow`` (fewer provinces than we claim),
                          ``not_here`` (VASCAN records it from neither), or
                          ``review``.
    """
    if not result.get("matched"):
        return {"native_provinces": "", "origin": "unmatched",
                "verdict": "review",
                "why": "VASCAN returned no match for this name at all, which "
                       "is usually a superseded or misspelled binomial."}

    provinces = result.get("provinces") or {}
    native, introduced, unstated = [], [], []
    for code in PROVINCES:
        if code not in provinces:
            continue
        means = provinces[code]
        if not means:
            unstated.append(code)
        elif any(word in means for word in DISQUALIFYING):
            introduced.append(code)
        else:
            native.append(code)

    here = [c for c in native if c in ("AB", "SK")]
    if here:
        origin, verdict = "native", "confirm"
        why = f"VASCAN records it native in {', '.join(here)}."
    elif [c for c in introduced if c in ("AB", "SK")]:
        origin, verdict = "introduced", "not_here"
        why = ("VASCAN records it as introduced in "
               f"{', '.join(c for c in introduced if c in ('AB', 'SK'))}.")
    elif [c for c in unstated if c in ("AB", "SK")]:
        origin, verdict = "unstated", "review"
        why = ("VASCAN lists it for the province but states no "
               "establishment means. Present, origin unrecorded.")
    else:
        origin, verdict = "absent", "not_here"
        why = "VASCAN records no Alberta or Saskatchewan distribution."

    return {"native_provinces": ",".join(here), "origin": origin,
            "verdict": verdict, "why": why}


# ── The run ─────────────────────────────────────────────────────────────────

def fetch_all(names, *, verbose=True, throttle=None, get_json=None) -> dict:
    """``{name: {...}}`` for every species, plus the failures kept separate."""
    mod = _seeder()
    throttle = throttle or mod._Throttle()
    out: dict = {}
    failed: list = []
    for i, name in enumerate(names, 1):
        try:
            result = lookup(name, throttle=throttle, get_json=get_json)
        except mod.FetchFailed as exc:
            # NOT recorded as "no record". A refusal is not an absence, and
            # writing it as one is the exact bug that made an earlier run
            # report 208 species as growing nowhere.
            failed.append((name, str(exc)))
            if verbose:
                print(f"[{i}/{len(names)}] {name}: COULD NOT FETCH ({exc}) "
                      f"- needs a re-run, NOT recorded")
            throttle.wait()
            continue
        row = dict(result)
        row.update(assess(result))
        row.pop("raw_matches", None)
        row["vascan_matches"] = result.get("raw_matches", 0)
        out[name] = row
        if verbose:
            print(f"[{i}/{len(names)}] {name}: {row['verdict']} "
                  f"({row['origin']}) {row['native_provinces'] or '-'}")
        throttle.wait()
    return {"results": out, "failed": failed}


def write(results: dict, failed: list, *, path=OUTPUT_PATH) -> dict:
    blob = {
        "version": FILE_VERSION,
        "generated": date.today().isoformat(),
        "source": f"VASCAN (Database of Vascular Plants of Canada), "
                  f"retrieved {date.today().isoformat()}",
        "comment": (
            "Per-province establishment means and accepted names for the "
            "plant catalogue. Read by scripts/ingest_flora_nativity.py, which "
            "PROPOSES changes and does not apply them. `origin: unstated` is "
            "a real answer and must not be rounded to a verdict."),
        "provinces_asked": list(PROVINCES),
        "failed": [{"name": n, "why": w} for n, w in failed],
        "results": results,
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(blob, f, indent=1, ensure_ascii=False)
        f.write("\n")
    return blob


def probe(names: list[str]) -> int:
    """Three species, raw, with a populated-field census.

    The single most useful thing in ``fetch_fauna_edges.py`` and the reason
    V2.59's second attempt worked: it reports **what percentage of records
    populate each field**, so a wrong guess about the response shape shows up
    in one run instead of after a four-hundred-request harvest.
    """
    mod = _seeder()
    throttle = mod._Throttle()
    print(f"Probing VASCAN with {len(names)} species.\n")
    census: dict = {}
    for name in names:
        query = urlencode({"q": name})
        try:
            data = mod._get_json(f"{VASCAN_SEARCH}?{query}", 30.0, throttle)
        except mod.FetchFailed as exc:
            print(f"{name}: FETCH FAILED: {exc}")
            print("\nIf this is a 403 from a CONNECT tunnel, you are running "
                  "it in the container. Run it on your own machine.")
            return 1
        print(f"--- {name} ---")
        print(json.dumps(data, indent=1)[:2500])
        for result in data.get("results") or []:
            for key in result:
                census[f"result.{key}"] = census.get(f"result.{key}", 0) + 1
            for match in _first(result, _MATCH_KEYS, []) or []:
                for key in match:
                    census[f"match.{key}"] = census.get(f"match.{key}", 0) + 1
                for row in _first(match, _DIST_KEYS, []) or []:
                    if isinstance(row, dict):
                        for key in row:
                            census[f"dist.{key}"] = census.get(f"dist.{key}", 0) + 1
        print()
        print("parsed ->", json.dumps(lookup(name, throttle=throttle), indent=1))
        print()
        throttle.wait()

    print("=== fields seen, and how often ===")
    for key, n in sorted(census.items(), key=lambda kv: (-kv[1], kv[0])):
        print(f"  {n:4d}  {key}")
    print("\nCheck that the keys this parser reads are in that list:")
    for label, keys in (("matches", _MATCH_KEYS), ("distribution", _DIST_KEYS),
                        ("establishment", _MEANS_KEYS),
                        ("location", _LOCATION_KEYS)):
        print(f"  {label:14s} {keys}")
    print("\nIf none of a group appears, the parser is reading a field that "
          "does not exist and would return 'no distribution' for every "
          "species. Fix _*_KEYS before the real run.")
    return 0


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--probe", action="store_true",
                   help="Three species, raw JSON and a field census. "
                        "RUN THIS FIRST.")
    p.add_argument("--species", action="append", default=None,
                   help="Only this scientific name (repeatable).")
    p.add_argument("--limit", type=int, default=None)
    p.add_argument("--quiet", action="store_true")
    args = p.parse_args(argv)

    names = args.species or catalogue_species()
    if args.limit:
        names = names[:args.limit]

    if args.probe:
        return probe(names[:3] if not args.species else names)

    print(f"Asking VASCAN about {len(names)} species. One request each.\n")
    got = fetch_all(names, verbose=not args.quiet)
    blob = write(got["results"], got["failed"])

    verdicts: dict = {}
    for row in got["results"].values():
        verdicts[row["verdict"]] = verdicts.get(row["verdict"], 0) + 1
    print()
    for verdict, n in sorted(verdicts.items(), key=lambda kv: -kv[1]):
        print(f"  {n:4d}  {verdict}")
    if got["failed"]:
        print(f"\n  {len(got['failed'])} species COULD NOT BE FETCHED. These "
              f"are NOT recorded as absent; re-run for them.")
    print(f"\nWrote {OUTPUT_PATH.relative_to(PROJECT_ROOT)} "
          f"({len(blob['results'])} species).")
    print("Next: python scripts/ingest_flora_nativity.py   (reports; "
          "applies nothing)")
    return 2 if got["failed"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
