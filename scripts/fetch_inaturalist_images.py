#!/usr/bin/env python3
"""
scripts/fetch_inaturalist_images.py — populate the image fields (schema v24,
V1.60) on plants + fauna from iNaturalist, keeping ONLY openly-licensed photos
that are safe to redistribute in a shipped installer.

For each record's ``scientific_name`` it queries the iNaturalist taxa endpoint
(no API key needed for read), takes the matched taxon's ``default_photo``, and —
when the photo's licence is in the redistributable whitelist (CC0 / CC BY /
CC BY-SA; NC / ND / all-rights-reserved are SKIPPED) — writes:

    image_url           the photo URL (iNaturalist static CDN, medium size)
    image_attribution   the photographer + licence credit string
    image_license       the CC licence code (e.g. cc-by-sa)

into ``data/plants_master.json`` and ``data/fauna_master.json``. Re-runnable and
idempotent: records that already have an ``image_url`` are skipped unless
``--force``. Throttled to be polite to the API (≈1 req/s; iNat asks for ≤60/min
and a descriptive User-Agent).

After a run, bump ``src/db/plants.py:_SCHEMA_VERSION`` (24 → 25) so existing
installs reseed and pick up the new images.

This script needs outbound network to api.inaturalist.org. Run it on a machine
with internet (the build sandbox blocks general egress).

macOS / Linux (bash):
    python scripts/fetch_inaturalist_images.py            # plants + fauna
    python scripts/fetch_inaturalist_images.py --plants   # plants only
    python scripts/fetch_inaturalist_images.py --limit 20 # try the first 20
    python scripts/fetch_inaturalist_images.py --force    # re-fetch all

Windows (PowerShell) — from the repo root:
    python .\scripts\fetch_inaturalist_images.py            # plants + fauna
    python .\scripts\fetch_inaturalist_images.py --limit 20 # try the first 20
    python .\scripts\fetch_inaturalist_images.py --plants   # plants only
    python .\scripts\fetch_inaturalist_images.py --force    # re-fetch all
(If `python` isn't found, try `py` instead — e.g. `py .\scripts\...`.)
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
import urllib.parse
import urllib.request

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_PLANTS_JSON = os.path.join(_ROOT, "data", "plants_master.json")
_FAUNA_JSON = os.path.join(_ROOT, "data", "fauna_master.json")

_API = "https://api.inaturalist.org/v1/taxa"
_USER_AGENT = ("PermaDesign image sourcing "
               "(native-habitat design app; openly-licensed photos only)")

# Redistributable licences only — safe to ship in an installer. Everything else
# (cc-by-nc*, cc-by-nd, c / all-rights-reserved, null) is skipped.
ACCEPT_LICENSES = {"cc0", "cc-by", "cc-by-sa"}


# ── Pure helpers (unit-tested, no network) ───────────────────────────────────

def license_ok(code) -> bool:
    """True only for licences we may redistribute."""
    return (code or "").strip().lower() in ACCEPT_LICENSES


def best_taxon(results, scientific_name):
    """Pick the taxon whose name exactly matches ``scientific_name`` (case-
    insensitive). Require an exact match so we never attach a photo of the wrong
    species; returns None otherwise."""
    sn = (scientific_name or "").strip().lower()
    for t in results or []:
        if (t.get("name") or "").strip().lower() == sn:
            return t
    return None


def photo_from_taxon(taxon) -> "tuple | None":
    """``(url, attribution, license_code)`` from a taxon's ``default_photo`` when
    its licence is redistributable, else None."""
    dp = (taxon or {}).get("default_photo") or {}
    code = (dp.get("license_code") or "").strip().lower()
    if not license_ok(code):
        return None
    url = dp.get("medium_url") or dp.get("url") or dp.get("square_url")
    if not url:
        return None
    attribution = (dp.get("attribution") or "").strip()
    return (url, attribution, code)


# ── Network ───────────────────────────────────────────────────────────────--

def _query_taxon(scientific_name: str, timeout: float = 20.0):
    """Query iNaturalist for a species by scientific name; return the matched
    taxon dict or None. Raises on network error (caller handles)."""
    qs = urllib.parse.urlencode({"q": scientific_name, "rank": "species",
                                 "per_page": 5})
    req = urllib.request.Request(
        f"{_API}?{qs}",
        headers={"User-Agent": _USER_AGENT, "Accept": "application/json"})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        data = json.loads(resp.read().decode("utf-8"))
    return best_taxon(data.get("results"), scientific_name)


def _process(path: str, label: str, *, force: bool, limit, sleep: float) -> None:
    if not os.path.exists(path):
        print(f"  (skip {label}: {path} not found)")
        return
    with open(path, "r", encoding="utf-8") as f:
        records = json.load(f)

    todo = [r for r in records
            if r.get("scientific_name")
            and (force or not (r.get("image_url") or "").strip())]
    if limit:
        todo = todo[:limit]
    print(f"{label}: {len(todo)} record(s) to fetch "
          f"(of {len(records)} total).")

    found = skipped = errors = 0
    for i, rec in enumerate(todo, 1):
        sci = rec["scientific_name"]
        try:
            taxon = _query_taxon(sci)
        except Exception as exc:  # noqa: BLE001
            errors += 1
            print(f"  [{i}/{len(todo)}] {sci}: ERROR {exc}")
            time.sleep(sleep)
            continue
        photo = photo_from_taxon(taxon) if taxon else None
        if photo:
            url, attribution, code = photo
            rec["image_url"] = url
            rec["image_attribution"] = attribution
            rec["image_license"] = code
            found += 1
            print(f"  [{i}/{len(todo)}] {sci}: ✓ {code}")
        else:
            skipped += 1
            print(f"  [{i}/{len(todo)}] {sci}: — no redistributable photo")
        time.sleep(sleep)   # be polite to the API

    with open(path, "w", encoding="utf-8") as f:
        json.dump(records, f, indent=2, ensure_ascii=False)
    print(f"{label}: wrote {found} image(s); {skipped} without a usable "
          f"licence; {errors} error(s). Saved {path}.")


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--plants", action="store_true", help="plants only")
    ap.add_argument("--fauna", action="store_true", help="fauna only")
    ap.add_argument("--force", action="store_true",
                    help="re-fetch even records that already have an image")
    ap.add_argument("--limit", type=int, default=0,
                    help="only the first N records (0 = all)")
    ap.add_argument("--sleep", type=float, default=1.0,
                    help="seconds between requests (default 1.0)")
    args = ap.parse_args(argv)

    do_plants = args.plants or not args.fauna
    do_fauna = args.fauna or not args.plants
    limit = args.limit or None

    if do_plants:
        _process(_PLANTS_JSON, "Plants", force=args.force, limit=limit,
                 sleep=args.sleep)
    if do_fauna:
        _process(_FAUNA_JSON, "Fauna", force=args.force, limit=limit,
                 sleep=args.sleep)

    print("\nDone. Now bump src/db/plants.py:_SCHEMA_VERSION (24 → 25) so "
          "existing installs reseed and surface the new photos.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
