#!/usr/bin/env python3
"""
scripts/warm_photo_cache.py — download the photographs once, so the site can
carry copies instead of pointing at somebody else's server.

    python scripts/warm_photo_cache.py              # plants and animals
    python scripts/warm_photo_cache.py --plants     # just the plants
    python scripts/warm_photo_cache.py --limit 20   # try a few first

What this is for
----------------
``build-site`` copies a photograph into ``assets/photos/`` when the bytes are
already in the local cache, and otherwise leaves the page pointing at the
original URL. It never fetches, on purpose: a build that reaches the network is
a build that fails differently on a bad day. So the fetching is this script's
job, and it is a separate step you run when you feel like it.

Before a warm run the site publishes about **375 hotlinked photographs**. Those
pages load at somebody else's speed and a photo disappears from the catalogue
the day its author deletes it from iNaturalist.

The cache is not in the repository, and that is the point
---------------------------------------------------------
It lives in the per-user data directory beside the database
(``%APPDATA%/Site & Pattern/image_cache`` on Windows), which is why:

* deleting ``public/`` before a rebuild does **not** cost you the photographs;
* a re-run is nearly free, because ``fetch_and_cache_image`` serves anything
  already cached and never re-downloads it;
* nothing here is committed, so the repository does not grow by 70 MB.

Warm it once and every future ``build-site`` bundles the photographs with no
extra step.

Politeness
----------
One request per second by default. iNaturalist asks for no more than 60 a
minute and a descriptive User-Agent, and ``image_cache`` already sends one. A
full cold run is therefore about six minutes; there is no hurry and being
rude to a free API on behalf of a catalogue that depends on it would be a poor
trade.

Failures are not fatal and not silent
-------------------------------------
A photo that will not download is reported and skipped. The page falls back to
the hotlink it already had, which is exactly the behaviour before the run, so a
partial warm is strictly better than none.
"""

from __future__ import annotations

import argparse
import json
import pathlib
import sys
import time

PROJECT_ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

#: Seed files that carry a photograph, and the label used when reporting.
SOURCES = (
    ("plants_master.json", "plants"),
    ("garden_plants.json", "plants"),
    ("fauna_master.json", "fauna"),
)


def _rows(filename: str) -> list:
    path = PROJECT_ROOT / "data" / filename
    try:
        blob = json.loads(path.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError):
        return []
    return [r for r in blob if isinstance(r, dict)]


def targets(want_plants: bool, want_fauna: bool) -> list:
    """``(name, url, attribution, licence)`` for every remote photograph."""
    out, seen = [], set()
    for filename, kind in SOURCES:
        if kind == "plants" and not want_plants:
            continue
        if kind == "fauna" and not want_fauna:
            continue
        for row in _rows(filename):
            url = (row.get("image_url") or "").strip()
            # A local path is already "cached" in the only sense that matters,
            # and a blank is a species we have no photograph for at all.
            if not url.startswith("http") or url in seen:
                continue
            seen.add(url)
            out.append((
                row.get("scientific_name") or row.get("common_name") or "?",
                url,
                row.get("image_attribution") or "",
                row.get("image_license") or "",
            ))
    return out


def warm(items: list, sleep: float) -> int:
    from src.image_cache import fetch_and_cache_image, get_cached_image

    already = fetched = failed = 0
    failures = []
    total = len(items)
    for i, (name, url, attribution, licence) in enumerate(items, 1):
        if get_cached_image(url):
            already += 1
            continue
        path = fetch_and_cache_image(url, attribution, licence)
        if path:
            fetched += 1
        else:
            failed += 1
            failures.append(name)
        # Only sleep after a real request. Skipping the cached ones at full
        # speed is what makes a re-run cheap.
        if i < total:
            time.sleep(sleep)
        if fetched and fetched % 25 == 0:
            print(f"  ... {fetched} downloaded, {already} already cached")

    print(f"\n{total} photographs referenced")
    print(f"  {already:4d} already in the cache (not re-downloaded)")
    print(f"  {fetched:4d} downloaded now")
    print(f"  {failed:4d} could not be fetched")
    if failures:
        print("\nThese kept their hotlink, which is what they had before:")
        for name in failures[:15]:
            print(f"      {name}")
        if len(failures) > 15:
            print(f"      ... and {len(failures) - 15} more")
    if fetched or already:
        print("\nNow rebuild, and the build line should read "
              f"'{already + fetched} copied from cache'.")
    return 0


def main(argv=None) -> int:
    p = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--plants", action="store_true",
                   help="only the plant photographs")
    p.add_argument("--fauna", action="store_true",
                   help="only the animal photographs")
    p.add_argument("--limit", type=int, default=0, metavar="N",
                   help="stop after N photographs (try a few first)")
    p.add_argument("--sleep", type=float, default=1.0, metavar="SECONDS",
                   help="pause between requests (default 1.0; iNaturalist "
                        "asks for no more than 60 a minute)")
    args = p.parse_args(argv)

    # Neither flag means both, which is the common case.
    want_plants = args.plants or not args.fauna
    want_fauna = args.fauna or not args.plants

    items = targets(want_plants, want_fauna)
    if args.limit:
        items = items[:args.limit]
    if not items:
        print("Nothing to warm.")
        return 0

    from src.image_cache import _cache_dir  # noqa: PLC0415 — reporting only
    print(f"{len(items)} photographs to consider")
    print(f"cache: {_cache_dir()}\n")
    return warm(items, max(0.0, args.sleep))


if __name__ == "__main__":
    raise SystemExit(main())
