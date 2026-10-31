#!/usr/bin/env python3
"""
scripts/rename_common_name.py — correct the name a species is published under.

**Reports by default. Applies nothing without --apply.**

    python scripts/rename_common_name.py "Penstemon lyallii" "Lyall's Penstemon"
    python scripts/rename_common_name.py "Penstemon lyallii" "Lyall's Penstemon" \
        --apply --reason "missing apostrophe"

Why a script and not an edit
----------------------------
**The common name is a foreign key in this repository, and the scientific name
is not.** That is the opposite of what anybody expects, and it is why
``rename_taxon.py`` can promise that a rename leaves the edges alone:

* ``data/plant_fauna_master.json`` names its plant by common name -- 7,200
  edges, and ``_seed_fauna`` used to drop an unresolvable one with a bare
  ``continue``, so a typo here deletes ecology silently. ``validate-data``
  fails on it now, but only after the fact.
* ``static_site._unique_slugs`` slugifies the common name, so **a rename moves
  a public URL** and there is no redirect anywhere in the build.
* The seeded communities in ``src/db/polycultures.py``, the worked example in
  ``src/onboarding.py`` and the bench scenes in ``src/sprite_gallery.py`` name
  their plants as literal Python strings.

The last of those is not rewritten here, deliberately, on the rule
``merge_duplicate_species.py`` wrote after a merge broke three seeded
communities: *a script rewriting source it does not understand is worse than a
checklist.* So the references are printed, with file and line, and
``tests/test_polycultures.py:test_all_member_names_resolve`` is the backstop.

What gets written
-----------------
The row's ``common_name``, every matching edge's ``plant``, and three
provenance fields on the row -- ``common_renamed_from``, ``common_renamed_on``
and ``common_renamed_why`` -- so the retired name stays findable by somebody
who only knows the plant by it, and the reason travels with the row rather
than living in a commit message.

Nothing reads those fields yet. The obvious next use is the website's search
index: a reader who knows the plant as *Yellow Pucoon* now finds nothing at
all, and the retired name is sitting right there on the row.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from datetime import date
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

PLANT_FILES = ("plants_master.json", "garden_plants.json")
EDGE_FILE = "plant_fauna_master.json"


def _load(name: str):
    with open(PROJECT_ROOT / "data" / name, encoding="utf-8") as fh:
        return json.load(fh)


def _save(name: str, data) -> None:
    """Write back at the file's own indent — ``plant_fauna_master.json`` is
    ``indent=1``, and re-saving it at the obvious 2 reindents 53,000 lines."""
    from scripts.rename_taxon import _indent_of          # noqa: PLC0415
    path = PROJECT_ROOT / "data" / name
    width = _indent_of(path)
    text = (json.dumps(data, indent=width, ensure_ascii=False) if width
            else json.dumps(data, ensure_ascii=False, separators=(",", ":")))
    path.write_text(text + "\n", encoding="utf-8")


def _slug(name: str) -> str:
    from src.static_site import slugify                  # noqa: PLC0415
    return slugify(name)


def _source_refs(common: str) -> list:
    """``file:line`` for every mention in Python source. A checklist, not a fix."""
    if not common:
        return []
    try:
        out = subprocess.run(
            ["grep", "-rn", "--include=*.py", f'"{common}"', "src", "scripts"],
            cwd=str(PROJECT_ROOT), capture_output=True, text=True,
            encoding="utf-8", check=False)
        alt = subprocess.run(
            ["grep", "-rn", "--include=*.py", f"'{common}'", "src", "scripts"],
            cwd=str(PROJECT_ROOT), capture_output=True, text=True,
            encoding="utf-8", check=False)
    except OSError:
        return []
    lines = out.stdout.splitlines() + alt.stdout.splitlines()
    return sorted({":".join(ln.split(":", 2)[:2]) for ln in lines if ln.strip()})


def survey(scientific: str, new: str) -> dict:
    plant_file = row = None
    for name in PLANT_FILES:
        for candidate in _load(name):
            if (isinstance(candidate, dict)
                    and candidate.get("scientific_name") == scientific):
                plant_file, row = name, candidate
    if row is None:
        raise SystemExit(f"{scientific} is not in the catalogue.")
    old = row.get("common_name") or ""

    clash = [c.get("scientific_name") for name in PLANT_FILES
             for c in _load(name)
             if isinstance(c, dict) and (c.get("common_name") or "") == new
             and c.get("scientific_name") != scientific]

    edges = [e for e in _load(EDGE_FILE)
             if isinstance(e, dict) and e.get("plant") == old]
    return {"scientific": scientific, "plant_file": plant_file, "row": row,
            "old": old, "new": new, "clash": clash, "edges": edges,
            "refs": _source_refs(old)}


def report(s: dict) -> None:
    print(f"\n=== RENAME: {s['old']!r}  ->  {s['new']!r} ===")
    print(f"  {s['scientific']}, in data/{s['plant_file']}")
    print(f"  {len(s['edges'])} plant-fauna edges re-pointed")
    before, after = _slug(s["old"]), _slug(s["new"])
    if before == after:
        print(f"  URL /plants/{before}/ is unaffected")
    else:
        print(f"  URL MOVES: /plants/{before}/  ->  /plants/{after}/ "
              f"(no redirect exists; the old address stops resolving)")
    if s["refs"]:
        print(f"  {len(s['refs'])} mentions in Python source, "
              f"EDIT THESE BY HAND:")
        for ref in s["refs"]:
            print(f"      {ref}")
    if s["clash"]:
        print(f"  REFUSING: {s['new']!r} is already the common name of "
              f"{', '.join(s['clash'])}")


def apply(s: dict, reason: str) -> None:
    if not reason:
        raise SystemExit("--apply needs --reason: a published name changed "
                         "without one recorded is one the next pass will "
                         "change back.")
    if s["clash"]:
        raise SystemExit(f"{s['new']!r} is already in use; two rows sharing a "
                         f"common name is the problem, not the fix.")

    rows = _load(s["plant_file"])
    for row in rows:
        if isinstance(row, dict) and row.get("scientific_name") == s["scientific"]:
            row["common_name"] = s["new"]
            row["common_renamed_from"] = s["old"]
            row["common_renamed_on"] = date.today().isoformat()
            row["common_renamed_why"] = reason
    _save(s["plant_file"], rows)

    edges = _load(EDGE_FILE)
    moved = 0
    for edge in edges:
        if isinstance(edge, dict) and edge.get("plant") == s["old"]:
            edge["plant"] = s["new"]
            moved += 1
    _save(EDGE_FILE, edges)

    print(f"\nRenamed. {moved} edges re-pointed.")
    print("Now, in order:")
    print("  1. edit the Python references listed above by hand")
    print("  2. bump _SCHEMA_VERSION in src/db/plants.py")
    print("  3. python -m src.cli validate-data")
    print("  4. python -m unittest discover -s tests -t .")


def main(argv=None) -> int:
    p = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("scientific_name",
                   help="the row to rename, keyed by its scientific name")
    p.add_argument("new_common_name")
    p.add_argument("--reason", default="",
                   help="why the published name was wrong. Required with "
                        "--apply.")
    p.add_argument("--apply", action="store_true",
                   help="write the change. Report only without it.")
    args = p.parse_args(argv)

    s = survey(args.scientific_name, args.new_common_name)
    report(s)
    if not args.apply:
        print("\n(report only, nothing written.)")
        return 0
    apply(s, args.reason)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
