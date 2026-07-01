#!/usr/bin/env python3
"""
scripts/fetch_inaturalist_images.py — populate the image fields (schema v24,
V1.60) on plants + fauna from iNaturalist, keeping ONLY openly-licensed photos
that are safe to redistribute in a shipped installer.

For each record's ``scientific_name`` it queries the iNaturalist taxa endpoint
(no API key needed for read) and scans the species' photos for the first one
whose licence is in the redistributable whitelist (CC0 / CC BY / CC BY-SA; NC /
ND / all-rights-reserved are SKIPPED). **Bees are held to a stricter,
commercial-safe bar — CC0 / CC-BY only, no ShareAlike** (the F37 A1 decision,
mirrored by ``src/data_quality.py:validate_fauna_images`` so a bee photo this
script writes always passes validation). It checks the curated ``default_photo``
first, then — if that isn't openly licensed — the species' WIDER photo set from
the taxon-detail endpoint (often ~12 photos by different photographers), so a
species isn't skipped just because its single default photo is NonCommercial.
On a match it writes:

    image_url           the photo URL (iNaturalist static CDN, medium size)
    image_attribution   the photographer + licence credit string
    image_license       the CC licence code (e.g. cc-by-sa)

into ``data/plants_master.json`` and ``data/fauna_master.json``. Re-runnable and
idempotent: records that already have an ``image_url`` are skipped unless
``--force`` — so a plain re-run retries only the species still missing a photo
(e.g. to pick up the wider-photo-set scan added after a first pass). Throttled to be polite to the API (≈1 req/s; iNat asks for ≤60/min
and a descriptive User-Agent).

After a run, bump ``src/db/plants.py:_SCHEMA_VERSION`` (by one) so existing
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

# Bee photos are held to a stricter, commercial-safe bar than the rest of the
# fauna: CC0 / CC-BY only — no ShareAlike (the F37 A1 decision, mirrored by
# src/data_quality.py:_BEE_IMAGE_LICENSES which rejects any bee photo outside
# this set). Kept in sync here so a bee image this script writes always passes
# validate_fauna_images().
BEE_ACCEPT_LICENSES = {"cc0", "cc-by"}


def accept_for(taxon) -> set:
    """The licence whitelist to apply to a record of this ``taxon``. Bees use the
    stricter commercial-safe set; every other taxon may also use CC-BY-SA."""
    return BEE_ACCEPT_LICENSES if (taxon or "").strip().lower() == "bee" \
        else ACCEPT_LICENSES


# ── Pure helpers (unit-tested, no network) ───────────────────────────────────

def license_ok(code, accept=ACCEPT_LICENSES) -> bool:
    """True only for licences in ``accept`` — the redistributable set by default,
    or ``BEE_ACCEPT_LICENSES`` for the stricter commercial-safe bee policy."""
    return (code or "").strip().lower() in accept


def best_taxon(results, scientific_name):
    """Pick the taxon whose name exactly matches ``scientific_name`` (case-
    insensitive). Require an exact match so we never attach a photo of the wrong
    species; returns None otherwise."""
    sn = (scientific_name or "").strip().lower()
    for t in results or []:
        if (t.get("name") or "").strip().lower() == sn:
            return t
    return None


def taxon_candidates(taxon) -> list:
    """Ordered candidate photo dicts for a taxon: the curated ``default_photo``
    first, then every ``taxon_photos`` entry (the species' wider photo set). This
    is what lets us rescue a species whose default photo is NC/ND but which has
    other, openly-licensed photos."""
    if not taxon:
        return []
    out = []
    dp = taxon.get("default_photo")
    if dp:
        out.append(dp)
    for tp in taxon.get("taxon_photos") or []:
        ph = tp.get("photo") if isinstance(tp, dict) else None
        if ph:
            out.append(ph)
    return out


def pick_photo(candidates, accept=ACCEPT_LICENSES) -> "tuple | None":
    """First ``(url, attribution, license_code)`` among ``candidates`` whose
    licence is in ``accept`` (defaults to the redistributable set; pass
    ``BEE_ACCEPT_LICENSES`` for bees), else None. De-dupes by photo id so a photo
    that appears as both the default and in taxon_photos isn't checked twice."""
    seen = set()
    for ph in candidates or []:
        if not isinstance(ph, dict):
            continue
        pid = ph.get("id")
        if pid is not None:
            if pid in seen:
                continue
            seen.add(pid)
        code = (ph.get("license_code") or "").strip().lower()
        if not license_ok(code, accept):
            continue
        url = ph.get("medium_url") or ph.get("url") or ph.get("square_url")
        if not url:
            continue
        return (url, (ph.get("attribution") or "").strip(), code)
    return None


def photo_from_taxon(taxon, accept=ACCEPT_LICENSES) -> "tuple | None":
    """``(url, attribution, license_code)`` for the first photo in the taxon's
    photo set (default first, then taxon_photos) whose licence is in ``accept``,
    else None."""
    return pick_photo(taxon_candidates(taxon), accept)


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


def _fetch_taxon_detail(taxon_id, timeout: float = 20.0):
    """Fetch the full taxon record (``/v1/taxa/{id}``) — its ``taxon_photos`` is
    the wider photo set (often ~12) used to find an openly-licensed photo when
    the default isn't one. Returns the taxon dict or None."""
    req = urllib.request.Request(
        f"{_API}/{int(taxon_id)}",
        headers={"User-Agent": _USER_AGENT, "Accept": "application/json"})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        data = json.loads(resp.read().decode("utf-8"))
    results = data.get("results") or []
    return results[0] if results else None


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

    found = skipped = errors = deep = 0
    for i, rec in enumerate(todo, 1):
        sci = rec["scientific_name"]
        # Bees only accept CC0/CC-BY (commercial-safe); other taxa also CC-BY-SA.
        accept = accept_for(rec.get("taxon"))
        try:
            taxon = _query_taxon(sci)
        except Exception as exc:  # noqa: BLE001
            errors += 1
            print(f"  [{i}/{len(todo)}] {sci}: ERROR {exc}")
            time.sleep(sleep)
            continue

        # Try the photos already in the search result first (default + any
        # taxon_photos). If none are openly licensed, pull the full photo set
        # from the taxon-detail endpoint and scan that (one extra request, only
        # for the species that need it).
        photo = pick_photo(taxon_candidates(taxon), accept) if taxon else None
        via = "default/set"
        if not photo and taxon and taxon.get("id"):
            time.sleep(sleep)
            try:
                detail = _fetch_taxon_detail(taxon["id"])
            except Exception as exc:  # noqa: BLE001
                detail = None
                print(f"  [{i}/{len(todo)}] {sci}: detail fetch error {exc}")
            deep += 1
            photo = pick_photo(taxon_candidates(detail), accept) if detail else None
            via = "full set"

        if photo:
            url, attribution, code = photo
            rec["image_url"] = url
            rec["image_attribution"] = attribution
            rec["image_license"] = code
            found += 1
            print(f"  [{i}/{len(todo)}] {sci}: ✓ {code} ({via})")
        else:
            skipped += 1
            print(f"  [{i}/{len(todo)}] {sci}: — no redistributable photo")
        time.sleep(sleep)   # be polite to the API

    with open(path, "w", encoding="utf-8") as f:
        json.dump(records, f, indent=2, ensure_ascii=False)
    print(f"{label}: wrote {found} image(s); {skipped} without a usable "
          f"licence; {errors} error(s); {deep} needed the full photo set. "
          f"Saved {path}.")


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

    print("\nDone. Now bump src/db/plants.py:_SCHEMA_VERSION (by one) so "
          "existing installs reseed and surface the new photos.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
