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
built to pick photographs from, this measures what there is to pick, and how
much a second tier would add: non-commercial photographs (CC BY-NC, CC BY-NC-SA)
shown only among a plant's extra photographs in the free app and website, the
option the owner is weighing (plan, D1).

1. ``--seen`` counts the licences of the photographs the colour review showed
   (``data/fetched/colour_evidence.json``, the cache that run left). No network.
2. ``--probe NAME`` asks about one plant with each licence filter and prints
   the licence of every photograph each answer holds: the check that the
   filters do what they say. Run it before the full count.
3. With no options it asks, for every plant in the catalogue, how many
   research-grade observations carry a photograph that may ship (in Alberta
   and Saskatchewan, and anywhere), one that is non-commercial, and any
   photograph at all. Four or five requests a plant, one a second: about half
   an hour. It caches to ``data/fetched/open_photo_counts.json`` (Ctrl+C, then
   run it again to carry on; a plant counted by an earlier version is asked
   only what it lacks) and ends with a summary. Send that file to a session.
"""

from __future__ import annotations

import argparse
import collections
import json
import sys
import time
from pathlib import Path
from typing import Optional

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

from src import colour_checks  # noqa: E402

import fetch_colour_evidence as inat  # noqa: E402

#: The licences a plant photograph may ship under; a test keeps this equal to
#: the data gate's set.
OPEN = ("cc0", "cc-by", "cc-by-sa")
#: Non-commercial, the second tier being weighed. NoDerivatives stays out of
#: both: it forbids a crop.
NC = ("cc-by-nc", "cc-by-nc-sa")
COUNTS = ROOT / "data" / "fetched" / "open_photo_counts.json"
#: How many observations, in bands, for the summary.
BANDS = ((0, 0, "none"), (1, 5, "1 to 5"), (6, 20, "6 to 20"),
         (21, None, "more than 20"))
#: Fewer observations than this that may ship and a plant is short of choice:
#: the review page offers about three a group.
SHORT = 3
#: ``(key, in Alberta and Saskatchewan only, licences)``; ``()`` is any.
QUESTIONS = (("open_here", True, OPEN), ("open_anywhere", False, OPEN),
             ("nc_anywhere", False, NC), ("any_anywhere", False, ()))


def is_open(licence) -> bool:
    return (licence or "").strip().lower() in OPEN


def is_nc(licence) -> bool:
    return (licence or "").strip().lower() in NC


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
    nc = sum(n for code, n in mix.items() if is_nc(code))
    lines = [f"{len(photos)} photographs shown, of {len(plants)} plants. "
             f"By licence:"]
    for code, n in mix.most_common():
        lines.append(f"  {code:12} {n:5}  " + (
            "may ship" if is_open(code) else
            "non-commercial" if is_nc(code) else ""))
    lines.append(f"May ship: {usable} of {len(photos)} "
                 f"({100 * usable / len(photos):.0f}%). Plants with at least "
                 f"one that may ship: {with_one} of {len(plants)}.")
    lines.append(f"Non-commercial: {nc} of {len(photos)} "
                 f"({100 * nc / len(photos):.0f}%).")
    return lines


# ── Counting what iNaturalist holds ─────────────────────────────────────────

def _params(taxon_id, *, region: bool, licences: tuple = ()) -> dict:
    params = {"taxon_id": taxon_id, "quality_grade": "research",
              "photos": "true", "per_page": 1}
    if licences:
        params["photo_license"] = ",".join(licences)
    if region:
        south, west, north, east = inat.PRAIRIES
        params.update(swlat=south, swlng=west, nelat=north, nelng=east)
    return params


def count_one(scientific: str, taxon_id, *, delay: float,
              have: Optional[dict] = None) -> dict:
    """``{taxon, open_here, open_anywhere, nc_anywhere, any_anywhere}`` for
    one plant. ``taxon_id`` comes from the colour cache where it can; else it
    is asked. A count already in ``have`` (an earlier run) is not asked again."""
    have = dict(have or {})
    taxon_id = have.get("taxon") or taxon_id
    if not taxon_id:
        found = inat.get("/taxa", {"q": inat.query_name(scientific),
                                   "is_active": "true", "per_page": 10})
        time.sleep(delay)
        taxon_id = inat.pick_taxon(found.get("results"), scientific).get("id")
        if not taxon_id:
            return {"taxon": None, "note": "iNaturalist has no taxon by "
                                           "this name", "fetched": inat._now()}
    out = dict(have, taxon=taxon_id, fetched=inat._now())
    for key, region, licences in QUESTIONS:
        if key in out:
            continue
        answer = inat.get("/observations", _params(
            taxon_id, region=region, licences=licences))
        out[key] = int(answer.get("total_results") or 0)
        time.sleep(delay)
    return out


def lacks(entry: dict) -> bool:
    """A plant found on iNaturalist whose entry is missing a count."""
    return bool(entry.get("taxon")) and any(
        key not in entry for key, _r, _l in QUESTIONS)


def band(n: int) -> str:
    for low, high, words in BANDS:
        if n >= low and (high is None or n <= high):
            return words
    return BANDS[-1][2]


def _bands(done: dict, key: str) -> str:
    by = collections.Counter(band(c.get(key, 0)) for c in done.values())
    return ", ".join(f"{w}: {by.get(w, 0)}" for _l, _h, w in BANDS)


def summary(counts: dict, names: dict) -> list:
    """Lines for the end of a run: plants by how many observations there are
    with a photo that may ship, here and anywhere, and with a non-commercial
    one; how many plants short of choice non-commercial photos would fill;
    and the plants with none."""
    done = {s: c for s, c in counts.items() if c.get("taxon")}
    lines = [f"{len(done)} plants counted"
             + (f"; {len(counts) - len(done)} not found on iNaturalist"
                if len(counts) > len(done) else "") + "."]
    lines.append("Observations with a photo that may ship, in Alberta and "
                 "Saskatchewan: " + _bands(done, "open_here"))
    lines.append("Observations with a photo that may ship, anywhere: "
                 + _bands(done, "open_anywhere"))
    nc = {s: c for s, c in done.items() if "nc_anywhere" in c}
    if nc:
        lines.append("Observations with a non-commercial photo, anywhere: "
                     + _bands(nc, "nc_anywhere"))
    shippable = sum(c.get("open_anywhere", 0) for c in done.values())
    total = sum(c.get("any_anywhere", 0) for c in done.values())
    if total:
        lines.append(
            f"All plants together: {shippable} of {total} observations "
            f"({100 * shippable / total:.0f}%) have a photo that may ship"
            + (f"; {sum(c['nc_anywhere'] for c in nc.values())} "
               f"({100 * sum(c['nc_anywhere'] for c in nc.values()) / total:.0f}%)"
               " a non-commercial one" if nc else "") + ".")
    short = {s: c for s, c in nc.items() if c.get("open_anywhere", 0) < SHORT}
    if nc:
        filled = [s for s, c in short.items()
                  if c.get("open_anywhere", 0) + c["nc_anywhere"] >= SHORT]
        lines.append(f"Short of choice (fewer than {SHORT} that may ship): "
                     f"{len(short)} plants. Non-commercial photos would give "
                     f"{len(filled)} of them {SHORT} or more.")
    none = sorted(names.get(s, s) for s, c in done.items()
                  if not c.get("open_anywhere"))
    if none:
        lines.append(f"No photo that may ship, anywhere ({len(none)}): "
                     + ", ".join(none))
    neither = sorted(names.get(s, s) for s, c in nc.items()
                     if not c.get("open_anywhere") and not c["nc_anywhere"])
    if neither:
        lines.append(f"Neither kind, anywhere ({len(neither)}): "
                     + ", ".join(neither))
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
    for words, licences in (("Any licence", ()),
                            ("May ship only (CC0, CC BY, CC BY-SA)", OPEN),
                            ("Non-commercial only (CC BY-NC, CC BY-NC-SA)",
                             NC)):
        params = dict(_params(taxon["id"], region=False, licences=licences),
                      per_page=5)
        answer = inat.get("/observations", params)
        print(f"\n{words}: total_results={answer.get('total_results')!r}")
        for obs in answer.get("results") or []:
            codes = [p.get("license_code") for p in obs.get("photos") or []]
            print(f"  observation {obs.get('id')}: photo licences {codes}")
        codes = [str(p.get("license_code") or "").lower()
                 for o in answer.get("results") or []
                 for p in o.get("photos") or []]
        if licences and codes and not any(c in licences for c in codes):
            print(f"The filter returned no photograph licensed "
                  f"{', '.join(licences)}: it is not doing what this script "
                  "assumes. Send this output to a session.")
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
    todo = [s for s in names if s not in counts or lacks(counts[s])]
    print(f"{len(names)} plants; counting {len(todo)} "
          f"(about {len(todo) * 4.3 * args.delay / 60:.0f} minutes).")
    try:
        for n, sci in enumerate(todo, 1):
            taxon = ((evidence.get(sci) or {}).get("taxon") or {}).get("id")
            counts[sci] = count_one(sci, taxon, delay=args.delay,
                                    have=counts.get(sci))
            c = counts[sci]
            print(f"  {n:3d}/{len(todo)} {names[sci]}: "
                  + (f"{c['open_anywhere']} may ship and {c['nc_anywhere']} "
                     f"non-commercial, of {c['any_anywhere']} "
                     f"({c['open_here']} may ship in AB/SK)" if c.get("taxon")
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
