#!/usr/bin/env python3
"""
count_open_photos.py — how many photographs of each plant the app and the
website may show (V3.34; docs/plans/V3.34-colours-in-photos-next.md, part 2).

Run on a computer with an internet connection (this project's cloud sessions
cannot reach iNaturalist):

    python scripts/count_open_photos.py --seen
    python scripts/count_open_photos.py --probe "Ratibida columnifera"
    python scripts/count_open_photos.py

A plant photograph may ship if it is CC0, CC BY or CC BY-SA
(``src.data_quality._PLANT_IMAGE_LICENSES``). iNaturalist's default licence is
CC BY-NC, so most of what the colour review showed cannot. Before a page is
built to pick photographs from, this measures what there is to pick.

1. ``--seen`` counts the licences of the photographs the colour review showed
   (``data/fetched/colour_evidence.json``, the cache that run left). No network.
2. ``--probe NAME`` asks about one plant with and without the licence filter
   and prints the licence of each photograph the filtered answer holds: the
   check that the filter does what it says. Run it before the full count.
3. With no options it asks, for every plant in the catalogue, how many
   research-grade observations carry an openly licensed photograph, in Alberta
   and Saskatchewan and anywhere, and how many carry any photograph at all.
   Three or four requests a plant, one a second: about twenty-five minutes.
   It caches to ``data/fetched/open_photo_counts.json`` (Ctrl+C, then run it
   again to carry on) and ends with a summary. Send that file to a session.
"""

from __future__ import annotations

import argparse
import collections
import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

from src import colour_checks  # noqa: E402

import fetch_colour_evidence as inat  # noqa: E402

#: The licences a plant photograph may ship under; a test keeps this equal to
#: the data gate's set.
OPEN = ("cc0", "cc-by", "cc-by-sa")
COUNTS = ROOT / "data" / "fetched" / "open_photo_counts.json"
#: How many openly licensed observations, in bands, for the summary.
BANDS = ((0, 0, "none"), (1, 5, "1 to 5"), (6, 20, "6 to 20"),
         (21, None, "more than 20"))


def is_open(licence) -> bool:
    return (licence or "").strip().lower() in OPEN


# ── What the colour review showed (no network) ──────────────────────────────

def seen_report(evidence: dict) -> list:
    """Lines saying how many of the photographs shown could ship."""
    photos = [p for e in evidence.values() for p in e.get("photos") or []]
    if not photos:
        return [f"No photographs in {inat.EVIDENCE}: run the colour fetch "
                "first, or skip --seen."]
    mix = collections.Counter((p.get("license") or "none").lower()
                              for p in photos)
    usable = sum(n for code, n in mix.items() if is_open(code))
    plants = [e for e in evidence.values() if e.get("photos")]
    with_one = sum(1 for e in plants
                   if any(is_open(p.get("license")) for p in e["photos"]))
    lines = [f"{len(photos)} photographs shown, of {len(plants)} plants. "
             f"By licence:"]
    for code, n in mix.most_common():
        lines.append(f"  {code:12} {n:5}  {'may ship' if is_open(code) else ''}")
    lines.append(f"May ship: {usable} of {len(photos)} "
                 f"({100 * usable / len(photos):.0f}%). Plants with at least "
                 f"one that may ship: {with_one} of {len(plants)}.")
    return lines


# ── Counting what iNaturalist holds ─────────────────────────────────────────

def _params(taxon_id, *, region: bool, open_only: bool) -> dict:
    params = {"taxon_id": taxon_id, "quality_grade": "research",
              "photos": "true", "per_page": 1}
    if open_only:
        params["photo_license"] = ",".join(OPEN)
    if region:
        south, west, north, east = inat.PRAIRIES
        params.update(swlat=south, swlng=west, nelat=north, nelng=east)
    return params


def count_one(scientific: str, taxon_id, *, delay: float) -> dict:
    """``{taxon, open_here, open_anywhere, any_anywhere}`` for one plant.
    ``taxon_id`` comes from the colour cache where it can; else it is asked."""
    if not taxon_id:
        found = inat.get("/taxa", {"q": inat.query_name(scientific),
                                   "is_active": "true", "per_page": 10})
        time.sleep(delay)
        taxon_id = inat.pick_taxon(found.get("results"), scientific).get("id")
        if not taxon_id:
            return {"taxon": None, "note": "iNaturalist has no taxon by "
                                           "this name", "fetched": inat._now()}
    out = {"taxon": taxon_id, "fetched": inat._now()}
    for key, region, open_only in (("open_here", True, True),
                                   ("open_anywhere", False, True),
                                   ("any_anywhere", False, False)):
        answer = inat.get("/observations", _params(
            taxon_id, region=region, open_only=open_only))
        out[key] = int(answer.get("total_results") or 0)
        time.sleep(delay)
    return out


def band(n: int) -> str:
    for low, high, words in BANDS:
        if n >= low and (high is None or n <= high):
            return words
    return BANDS[-1][2]


def summary(counts: dict, names: dict) -> list:
    """Lines for the end of a run: plants by how many openly licensed
    observations there are, here and anywhere, and the plants with none."""
    done = {s: c for s, c in counts.items() if c.get("taxon")}
    lines = [f"{len(done)} plants counted"
             + (f"; {len(counts) - len(done)} not found on iNaturalist"
                if len(counts) > len(done) else "") + "."]
    for key, words in (("open_here", "in Alberta and Saskatchewan"),
                       ("open_anywhere", "anywhere")):
        by = collections.Counter(band(c.get(key, 0)) for c in done.values())
        lines.append(f"Observations with a photo that may ship, {words}: "
                     + ", ".join(f"{w}: {by.get(w, 0)}"
                                 for _l, _h, w in BANDS))
    shippable = sum(c.get("open_anywhere", 0) for c in done.values())
    total = sum(c.get("any_anywhere", 0) for c in done.values())
    if total:
        lines.append(f"All plants together: {shippable} of {total} "
                     f"observations ({100 * shippable / total:.0f}%) have a "
                     "photo that may ship.")
    none = sorted(names.get(s, s) for s, c in done.items()
                  if not c.get("open_anywhere"))
    if none:
        lines.append(f"No photo that may ship, anywhere ({len(none)}): "
                     + ", ".join(none))
    return lines


def probe(scientific: str) -> int:
    print(f"Asking iNaturalist about {scientific!r}\n")
    found = inat.get("/taxa", {"q": inat.query_name(scientific),
                               "is_active": "true", "per_page": 10})
    taxon = inat.pick_taxon(found.get("results"), scientific)
    if not taxon:
        print("No taxon matches the name exactly.")
        return 1
    print(f"Taxon {taxon.get('id')} {taxon.get('name')}")
    for open_only in (False, True):
        params = dict(_params(taxon["id"], region=False, open_only=open_only),
                      per_page=5)
        answer = inat.get("/observations", params)
        print(f"\n{'Openly licensed only' if open_only else 'Any licence'}: "
              f"total_results={answer.get('total_results')!r}")
        for obs in answer.get("results") or []:
            codes = [p.get("license_code") for p in obs.get("photos") or []]
            print(f"  observation {obs.get('id')}: photo licences {codes}")
        if open_only:
            codes = [p.get("license_code") for o in answer.get("results") or []
                     for p in o.get("photos") or []]
            if codes and not any(is_open(c) for c in codes):
                print("The filter returned no openly licensed photograph: "
                      "it is not doing what this script assumes. Send this "
                      "output to a session.")
                return 1
    return 0


def load_counts() -> dict:
    try:
        with open(COUNTS, encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        return {}


def save_counts(counts: dict) -> None:
    COUNTS.parent.mkdir(parents=True, exist_ok=True)
    tmp = COUNTS.with_suffix(".tmp")
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(counts, f, indent=1, ensure_ascii=False)
    tmp.replace(COUNTS)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--seen", action="store_true",
                    help="count the licences of the photographs the colour "
                         "review showed; ask nothing")
    ap.add_argument("--probe", metavar="NAME",
                    help="ask about one plant and print the answer")
    ap.add_argument("--delay", type=float, default=1.0,
                    help="seconds between requests (default 1)")
    args = ap.parse_args(argv)

    if args.seen:
        print("\n".join(seen_report(inat.load_evidence())))
        return 0
    try:
        if args.probe:
            return probe(args.probe)
    except inat.Refused as exc:
        print(f"iNaturalist refused: {exc}")
        return 1
    rows = colour_checks.load_master()
    names = {r["scientific_name"]: r.get("common_name") or r["scientific_name"]
             for r in rows}
    evidence = inat.load_evidence()
    counts = load_counts()
    todo = [s for s in names if s not in counts]
    print(f"{len(names)} plants; counting {len(todo)} "
          f"(about {len(todo) * 3.3 * args.delay / 60:.0f} minutes).")
    try:
        for n, sci in enumerate(todo, 1):
            taxon = ((evidence.get(sci) or {}).get("taxon") or {}).get("id")
            counts[sci] = count_one(sci, taxon, delay=args.delay)
            c = counts[sci]
            print(f"  {n:3d}/{len(todo)} {names[sci]}: "
                  + (f"{c['open_anywhere']} of {c['any_anywhere']} may ship "
                     f"({c['open_here']} in AB/SK)" if c.get("taxon")
                     else c["note"]))
            if n % 10 == 0:
                save_counts(counts)
    except KeyboardInterrupt:
        print("\nStopped. What was counted is kept; run again to carry on.")
    except inat.Refused as exc:
        print(f"\niNaturalist kept refusing ({exc}). What was counted is "
              "kept; try again later.")
    finally:
        save_counts(counts)
    print("\n" + "\n".join(summary(counts, names)))
    print(f"\nSaved {COUNTS}. Send that file to a session.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
