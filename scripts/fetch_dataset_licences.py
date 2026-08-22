#!/usr/bin/env python3
"""
scripts/fetch_dataset_licences.py — may we redraw these records?

**Run this on a machine with internet.** This container's egress policy answers
403 to CONNECT for ``api.gbif.org``.

    python3 scripts/fetch_dataset_licences.py --probe   # 3 requests, seconds
    python3 scripts/fetch_dataset_licences.py           # the real run

Why this exists
---------------
`scripts/plot_occurrences.py` can draw the occurrence records; nothing publishes
them, and the blocker is licensing. `docs/DATA_SOURCES.md` currently rests the
GBIF position on storing *"only the derived counts, never GBIF's records
themselves"*. Drawing coordinates on a public page changes that sentence, and
the records carry per-publisher licences that have to be honoured.

**Why per dataset and not per record.** The obvious move is to re-fetch every
occurrence with its ``license`` field, which is ~555,000 records and a couple of
hours. It is also the wrong granularity for the case that matters: a herbarium
publishes its whole collection under one licence, and specimens are the records
the printed floras plot. One request per *dataset* answers that exactly, and
there are a few hundred datasets rather than half a million records.

**Where this approximates, and it must be said rather than discovered.**
iNaturalist publishes with the *observer's* chosen licence per observation
(CC0 / CC-BY / CC-BY-NC all occur inside one dataset), so for
``HUMAN_OBSERVATION`` the dataset licence is the publisher's default and not a
per-record fact. That is fine for deciding **whether a layer is publishable at
all** and not fine for publishing individual iNaturalist points. The report
below therefore splits by ``basisOfRecord`` and says which half is exact.

What it writes
--------------
``data/fetched/dataset_licences.json`` — ``{datasetKey: {title, licence,
publisher}}``, plus a summary the report reads back. A dev artefact; the app
never reads it.
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

GBIF_DATASET = "https://api.gbif.org/v1/dataset"
OUTPUT_PATH = PROJECT_ROOT / "data" / "fetched" / "dataset_licences.json"
FILE_VERSION = 1

#: Licences that permit redrawing the coordinate on a public page with credit.
#: NonCommercial is deliberately NOT here: this project is PolyForm
#: Noncommercial, but the *website* is a public reference work and an NC licence
#: on a published map is a claim about downstream use we cannot make for
#: readers. Same bar the photographs are held to (`ACCEPT_LICENSES` in
#: scripts/fetch_inaturalist_images.py), for the same reason.
PUBLISHABLE = ("CC0", "CC_BY")

#: Counted and reported rather than silently dropped, because "we could not
#: publish 40% of the records" is the finding, not a footnote.
WITHHELD = ("CC_BY_NC", "UNSPECIFIED", "UNSUPPORTED")


def _seeder():
    import scripts.seed_ecoregion_ranges as seeder            # noqa: PLC0415
    return seeder


def dataset_keys() -> collections.Counter:
    """``{datasetKey: how many cached records came from it}``."""
    from scripts.seed_ecoregion_ranges import read_cache      # noqa: PLC0415
    counts: collections.Counter = collections.Counter()
    for points in read_cache().values():
        for p in points:
            counts[getattr(p, "dataset_key", "") or "(none)"] += 1
    return counts


def lookup(key: str, *, throttle=None, get_json=None) -> dict:
    """One dataset's licence and title, or ``{}`` if GBIF has no such key."""
    mod = _seeder()
    get_json = get_json or mod._get_json
    throttle = throttle or mod._Throttle()
    data = get_json(f"{GBIF_DATASET}/{key}", 30.0, throttle)
    if not isinstance(data, dict) or not data:
        return {}
    lic = (data.get("license") or "").rstrip("/").rsplit("/", 1)[-1]
    return {
        "title": data.get("title") or "",
        "licence": _normalise(data.get("license") or ""),
        "licence_raw": data.get("license") or "",
        "publisher": data.get("publishingOrganizationKey") or "",
        "type": data.get("type") or "",
        "_slug": lic,
    }


def _normalise(url: str) -> str:
    """GBIF returns a licence URL; reduce it to the token we reason about.

    Unrecognised is ``UNSPECIFIED`` rather than a guess: a licence we cannot
    name is one we cannot honour, which is the same rule the photo pipeline
    applies (absent is not permissive).
    """
    u = (url or "").lower()
    if "publicdomain/zero" in u or "cc0" in u:
        return "CC0"
    if "by-nc-sa" in u:
        return "CC_BY_NC_SA"
    if "by-nc" in u:
        return "CC_BY_NC"
    if "by-sa" in u:
        return "CC_BY_SA"
    if "/by/" in u or u.endswith("/by") or "licenses/by" in u:
        return "CC_BY"
    return "UNSPECIFIED" if u else "UNSPECIFIED"


def report(licences: dict, counts: collections.Counter) -> None:
    """The decision, as numbers. Split by basis, because only one half is exact."""
    from scripts.seed_ecoregion_ranges import read_cache      # noqa: PLC0415

    by_basis: dict = collections.defaultdict(collections.Counter)
    for points in read_cache().values():
        for p in points:
            lic = (licences.get(getattr(p, "dataset_key", ""), {})
                   .get("licence") or "UNSPECIFIED")
            by_basis[getattr(p, "basis", "") or "(none)"][lic] += 1

    print("\n=== records by basis and dataset licence ===")
    for basis in sorted(by_basis, key=lambda b: -sum(by_basis[b].values())):
        total = sum(by_basis[basis].values())
        ok = sum(n for l, n in by_basis[basis].items() if l in PUBLISHABLE)
        print(f"\n{basis}  ({total:,} records)")
        for lic, n in by_basis[basis].most_common():
            mark = "publishable" if lic in PUBLISHABLE else "withheld"
            print(f"   {lic:14s} {n:8,}  {mark}")
        print(f"   -> {ok:,} of {total:,} ({100*ok/total:.1f}%) redrawable")

    spec = by_basis.get("PRESERVED_SPECIMEN", {})
    spec_ok = sum(n for l, n in spec.items() if l in PUBLISHABLE)
    print("\n=== the decision ===")
    print("PRESERVED_SPECIMEN is the half where a dataset licence is exact:")
    print(f"   {spec_ok:,} of {sum(spec.values()):,} specimen records are "
          f"redrawable under CC0/CC-BY.")
    print("HUMAN_OBSERVATION dataset licences are the publisher's default and "
          "NOT a per-record fact (iNaturalist observers choose their own), so "
          "that column sizes the layer and does not authorise plotting an "
          "individual point.")


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--probe", action="store_true",
                   help="Three datasets, raw. RUN THIS FIRST.")
    p.add_argument("--quiet", action="store_true")
    args = p.parse_args(argv)

    mod = _seeder()
    counts = dataset_keys()
    if not counts:
        print("No point cache. Run scripts/seed_ecoregion_ranges.py first.",
              file=sys.stderr)
        return 1
    keys = [k for k in counts if k and k != "(none)"]
    print(f"{len(keys)} distinct datasets behind {sum(counts.values()):,} "
          f"cached records.")

    if args.probe:
        keys = sorted(keys, key=lambda k: -counts[k])[:3]
        print("Probing the three largest.\n")

    throttle = mod._Throttle()
    out: dict = {}
    failed: list = []
    for i, key in enumerate(sorted(keys, key=lambda k: -counts[k]), 1):
        try:
            row = lookup(key, throttle=throttle)
        except mod.FetchFailed as exc:
            # Not recorded as unlicensed. A refusal is not a licence fact, and
            # defaulting it to "withheld" would understate what is publishable
            # just as badly as defaulting it to CC0 would overstate it.
            failed.append((key, str(exc)))
            print(f"[{i}/{len(keys)}] {key}: COULD NOT FETCH ({exc})")
            throttle.wait()
            continue
        out[key] = row
        if not args.quiet:
            print(f"[{i}/{len(keys)}] {row.get('licence','?'):14s} "
                  f"{counts[key]:7,} records  {row.get('title','')[:56]}")
        throttle.wait()

    if args.probe:
        print("\nRaw licence strings, to check the normaliser:")
        for k, r in out.items():
            print(f"   {r['licence']:14s} <- {r['licence_raw']}")
        return 0

    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(OUTPUT_PATH, "w", encoding="utf-8") as f:
        json.dump({"version": FILE_VERSION,
                   "generated": date.today().isoformat(),
                   "source": "GBIF /v1/dataset, retrieved "
                             f"{date.today().isoformat()}",
                   "comment": "Dataset-level licences for the cached "
                              "occurrence points. EXACT for specimen data; for "
                              "iNaturalist this is the publisher default and "
                              "not a per-record licence.",
                   "failed": [{"key": k, "why": w} for k, w in failed],
                   "datasets": out}, f, indent=1, ensure_ascii=False)
        f.write("\n")
    print(f"\nWrote {OUTPUT_PATH.relative_to(PROJECT_ROOT)} "
          f"({len(out)} datasets).")
    if failed:
        print(f"{len(failed)} datasets could not be fetched and are NOT "
              f"recorded as unlicensed. Re-run for them.")
    report(out, counts)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
