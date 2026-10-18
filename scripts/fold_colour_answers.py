#!/usr/bin/env python3
"""
fold_colour_answers.py — bring the owner's flower colour answers into the
catalogue (V3.33; docs/plans/V3.33-flower-colours-from-photographs.md).

    python scripts/fold_colour_answers.py colour_answers.json          # check
    python scripts/fold_colour_answers.py colour_answers.json --write  # fold in

``colour_answers.json`` is what the review page's *Save my answers* writes
(``scripts/fetch_colour_evidence.py``). Every answer is checked first, against
``src.colour_checks``: a plant on the list, colours from the buckets, colours
or a verdict but not both. **Nothing is written if any answer fails**, and the
problems are listed.

``--write`` then lays the answers over ``data/flower_colour_checks.json`` (the
record: each plant's colours or verdict, what it was before, the observations
the page showed) and writes the matching rows of ``data/plants_master.json``:
the bucket's hex, the colour list, and ``photo`` as the source. Run it again
with the same file and nothing changes.

After writing: bump ``_SCHEMA_VERSION`` in ``src/db/plants.py`` so installed
copies reseed and pick the colours up, and run the tests.
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from src import colour_checks  # noqa: E402


def read_answers(path: Path) -> dict:
    with open(path, encoding="utf-8") as f:
        payload = json.load(f)
    if not isinstance(payload, dict) or not isinstance(
            payload.get("answers"), dict):
        raise SystemExit(f"{path}: not a saved answers file (no 'answers').")
    return payload


def fold(payload: dict, *, write: bool, master: Path = colour_checks.MASTER,
         checks_path: Path = colour_checks.CHECKS) -> int:
    rows = colour_checks.load_master(master)
    existing = colour_checks.load_checks(checks_path)
    answers = payload["answers"]
    # A plant answered before is still answerable: the review page lists
    # what is not yet answered, and a second answer replaces the first.
    listed = {i["scientific_name"]
              for i in colour_checks.worklist(rows, {})} | set(existing)
    problems = colour_checks.validate(answers, listed)
    if problems:
        print(f"{len(problems)} answers cannot be folded in; nothing written:")
        for p in problems:
            print("  " + p)
        return 1
    made = str(payload.get("made") or "")[:10] or dt.date.today().isoformat()
    checks = colour_checks.record(answers, made=made, existing=existing,
                                  rows=rows)
    done = colour_checks.apply(rows, checks)
    left = colour_checks.agrees(rows, checks)
    print(f"{len(answers)} answers: " + ", ".join(
        f"{n} {what}" for what, n in sorted(done.items())))
    if left:
        print("These would not agree afterwards; nothing written:")
        for line in left:
            print("  " + line)
        return 1
    if not write:
        print("Checked only. Run again with --write to fold them in.")
        return 0
    with open(master, "w", encoding="utf-8") as f:
        f.write(json.dumps(rows, indent=2, ensure_ascii=False) + "\n")
    with open(checks_path, "w", encoding="utf-8") as f:
        json.dump({"about": "Flower colours checked against photographs "
                            "(V3.33, src/colour_checks.py).",
                   "checks": dict(sorted(checks.items()))},
                  f, indent=1, ensure_ascii=False)
        f.write("\n")
    print(f"Wrote {master.name} and {checks_path.name}. Now bump "
          "_SCHEMA_VERSION in src/db/plants.py and run the tests.")
    return 0


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("answers", type=Path, help="the saved colour_answers.json")
    ap.add_argument("--write", action="store_true",
                    help="fold the answers in (default: check only)")
    args = ap.parse_args(argv)
    return fold(read_answers(args.answers), write=args.write)


if __name__ == "__main__":
    sys.exit(main())
