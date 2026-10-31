#!/usr/bin/env python3
"""
fold_photo_picks.py — bring the owner's photo picks into the catalogue (V3.35,
F251; docs/plans/V3.35-several-photos-a-plant.md).

    python scripts/fold_photo_picks.py photo_picks.json          # check
    python scripts/fold_photo_picks.py photo_picks.json --write  # fold in

``photo_picks.json`` is what the picking page's *Save my picks* writes
(``scripts/fetch_photo_candidates.py``). Every pick is checked first, against
``src.photo_picks``: a plant in the catalogue, at most six photographs, each
one of iNaturalist's open photographs with a licence that may ship and a
credit. **Nothing is written if any pick fails**, and the problems are listed.

``--write`` then replaces each picked plant's rows in ``data/plant_photos.json``
with its picks, in the owner's order, and gives its ``plants_master.json`` row
the first pick as its one photograph. *Keep the photo it has* changes nothing.
Run it again with the same file and nothing changes.

After writing: bump ``_SCHEMA_VERSION`` in ``src/db/plants.py`` so installed
copies reseed and pick the photographs up, and run the tests.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from src import colour_checks, photo_picks  # noqa: E402

PHOTOS = ROOT / "data" / "plant_photos.json"


def read_picks(path: Path) -> dict:
    with open(path, encoding="utf-8") as f:
        payload = json.load(f)
    if not isinstance(payload, dict) or not isinstance(
            payload.get("answers"), dict):
        raise SystemExit(f"{path}: not a saved picks file (no 'answers').")
    return payload


def fold(payload: dict, *, write: bool, master: Path = colour_checks.MASTER,
         photos_path: Path = PHOTOS) -> int:
    rows = colour_checks.load_master(master)
    with open(photos_path, encoding="utf-8") as f:
        photos = json.load(f)
    answers = payload["answers"]
    problems = photo_picks.validate(
        answers, (r.get("scientific_name") or "" for r in rows))
    if problems:
        print(f"{len(problems)} problems; nothing written:")
        for p in problems:
            print("  " + p)
        return 1
    done = photo_picks.apply(answers, rows, photos)
    print(f"{len(answers)} plants: {done['picked']} picked "
          f"({done['photographs']} photographs), {done['kept']} kept as they "
          f"were.")
    if not write:
        print("Checked only. Run again with --write to fold them in.")
        return 0
    with open(master, "w", encoding="utf-8") as f:
        f.write(json.dumps(rows, indent=2, ensure_ascii=False) + "\n")
    with open(photos_path, "w", encoding="utf-8") as f:
        f.write(json.dumps(photos, indent=1, ensure_ascii=False) + "\n")
    print(f"Wrote {master.name} and {photos_path.name}. Now bump "
          "_SCHEMA_VERSION in src/db/plants.py and run the tests.")
    return 0


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("picks", type=Path, help="the saved photo_picks.json")
    ap.add_argument("--write", action="store_true",
                    help="fold the picks in (default: check only)")
    args = ap.parse_args(argv)
    return fold(read_picks(args.picks), write=args.write)


if __name__ == "__main__":
    sys.exit(main())
