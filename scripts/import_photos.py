#!/usr/bin/env python3
"""import_photos.py — bring a folder of your own photographs into the catalogue.

    python scripts/import_photos.py ~/Pictures/yard              # dry run
    python scripts/import_photos.py ~/Pictures/yard --write
    python scripts/import_photos.py ~/Pictures/yard --write --private

WHY THIS EXISTS
111 of 434 plants ship with no photograph at all, and the ones that do have a
photo mostly have the wrong FRAME: `scripts/fetch_inaturalist_images.py` picks
the first photo with a redistributable licence, and iNaturalist's leading photo
is nearly always a macro of a flower. That is the frame that identifies a plant
to a botanist and the least useful one for deciding whether you want it in your
yard — or for finding it there in May, when it is forty unidentifiable green
rosettes.

Your photographs fix both problems at once, and you hold the copyright, so the
licence question that blocks everything else does not arise.

NAMING
One file per photo, named for its species and slot::

    Ratibida_columnifera_habit.jpg     Genus_species_slot.ext
    ratibida columnifera - flower.jpg  spaces and dashes are fine
    Ratibida_columnifera_habit_2.jpg   a trailing number is ignored

Slots (see src/db/photos.py for what each one is FOR):

    habit  flower  leaf  fruit  bark_stem  winter  seedling

A file whose species does not match the catalogue is reported and skipped — it
is never guessed at, because a photo filed under the wrong plant is worse than
no photo (P9).

WHAT IT WRITES
Two destinations, and the difference is the whole of F72:

* **shipped** (the default) — the file goes to ``data/photos/`` and a row into
  ``data/plant_photos.json``, both committed. Every install gets it.
* ``--private`` — the file goes to the per-user photo folder beside the database
  and the row goes straight into the local DB with ``origin='user'``, which the
  reseed never touches. Nothing is committed.

Every import is **stripped of EXIF first** (:mod:`src.photo_import`). A photo of
your own yard carries your home's coordinates, and the natural next step for a
photo you like is to commit it somewhere public.

P12: this records the botanical and visual record only.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

from src.photo_import import (import_photo, shipped_photo_dir,   # noqa: E402
                              slugify, user_photo_dir)

_MASTER = os.path.join(_ROOT, "data", "plants_master.json")
_PHOTOS_JSON = os.path.join(_ROOT, "data", "plant_photos.json")

SLOTS = ("habit", "flower", "leaf", "fruit", "bark_stem", "winter", "seedling")
_EXT = (".jpg", ".jpeg", ".png")

DEFAULT_LICENSE = "cc-by-sa"


def _catalogue_names() -> dict:
    with open(_MASTER, encoding="utf-8") as fh:
        recs = json.load(fh)
    out = {}
    for r in recs:
        sci = (r.get("scientific_name") or "").strip()
        if sci:
            out[slugify(sci)] = sci
    return out


def parse_filename(name: str, names: dict) -> tuple:
    """``('Ratibida columnifera', 'habit')`` from a filename, or
    ``(None, reason)``.

    Matches the LONGEST species prefix so that a two-word name followed by a
    slot is unambiguous, and so `Ratibida_columnifera_var_pulcherrima_habit`
    works if the catalogue carries that name.
    """
    stem = os.path.splitext(os.path.basename(name))[0]
    slug = slugify(stem)
    # Drop a trailing sequence number: ratibida_columnifera_habit_2
    slug = re.sub(r"_\d+$", "", slug)
    for slot in SLOTS:
        if not slug.endswith("_" + slugify(slot)):
            continue
        sp = slug[: -(len(slugify(slot)) + 1)]
        if sp in names:
            return names[sp], slot
        return None, (f"slot {slot!r} recognised but species {sp!r} is not in "
                      f"the catalogue")
    return None, "filename does not end in a known slot (%s)" % ", ".join(SLOTS)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("folder", help="folder of Genus_species_slot.jpg files")
    ap.add_argument("--write", action="store_true",
                    help="actually import (default is a dry run)")
    ap.add_argument("--private", action="store_true",
                    help="keep them on this machine instead of shipping them")
    ap.add_argument("--credit", default="",
                    help="attribution line, e.g. '© Your Name, CC BY-SA 4.0'")
    ap.add_argument("--license", default=DEFAULT_LICENSE)
    args = ap.parse_args()

    if not os.path.isdir(args.folder):
        print(f"not a folder: {args.folder}")
        return 1
    names = _catalogue_names()
    files = sorted(f for f in os.listdir(args.folder)
                   if f.lower().endswith(_EXT))
    if not files:
        print(f"no .jpg/.png files in {args.folder}")
        return 1

    plan, skipped = [], []
    for f in files:
        sci, slot_or_why = parse_filename(f, names)
        (plan if sci else skipped).append((f, sci, slot_or_why))

    for f, _sci, why in skipped:
        print(f"  skip  {f}\n        {why}")
    print(f"\n{len(plan)} of {len(files)} files resolve to a catalogue species.")
    for f, sci, slot in plan[:12]:
        print(f"  {f}  ->  {sci}  [{slot}]")
    if len(plan) > 12:
        print(f"  … and {len(plan) - 12} more")

    if not args.write:
        print("\nDry run. Re-run with --write to import.")
        return 0

    dest = user_photo_dir() if args.private else shipped_photo_dir()
    credit = args.credit or ("© the project owner, "
                             f"{args.license.upper()} (own photograph)")
    rows, notes = [], set()
    for f, sci, slot in plan:
        try:
            res = import_photo(os.path.join(args.folder, f), sci, slot, dest)
        except (OSError, ValueError) as exc:
            print(f"  FAILED {f}: {exc}")
            continue
        if res["note"]:
            notes.add(res["note"])
        rows.append({"scientific_name": sci, "slot": slot,
                     "url": (res["path"] if args.private
                             else "data/photos/" + res["filename"]),
                     "attribution": credit, "license": args.license,
                     "source": "owner", "taken_on": "", "rank": 0, "notes": ""})
        print(f"  ok    {res['filename']}  {res['bytes'] // 1024} KB"
              + ("  (metadata stripped)" if res["stripped"] else ""))

    if args.private:
        from src.db.photos import add_photo                  # noqa: PLC0415
        for r in rows:
            add_photo(r["scientific_name"], r["slot"], r["url"],
                      attribution=r["attribution"], license=r["license"],
                      source="owner", origin="user")
        print(f"\n{len(rows)} photo(s) added to your local library "
              f"(origin='user' — a reseed will never touch them).")
    else:
        existing = []
        if os.path.exists(_PHOTOS_JSON):
            with open(_PHOTOS_JSON, encoding="utf-8") as fh:
                existing = json.load(fh)
        have = {(e.get("scientific_name"), e.get("url")) for e in existing}
        added = [r for r in rows if (r["scientific_name"], r["url"]) not in have]
        with open(_PHOTOS_JSON, "w", encoding="utf-8") as fh:
            json.dump(existing + added, fh, indent=2, ensure_ascii=False)
            fh.write("\n")
        print(f"\n{len(added)} photo(s) written to data/plant_photos.json and "
              f"data/photos/.")
        print("Bump src/db/plants.py:_SCHEMA_VERSION so existing installs "
              "reseed and pick them up, then commit both.")
    for n in notes:
        print(f"\nNote: {n}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
