#!/usr/bin/env python3
"""
scripts/rename_taxon.py — file a species under the name its flora uses.

**Reports by default. Applies nothing without --apply.**

    python scripts/rename_taxon.py "Urtica dioica" "Urtica gracilis subsp. gracilis"
    python scripts/rename_taxon.py "Urtica dioica" "Urtica gracilis subsp. gracilis" --apply --authority "VASCAN v37.17"

Why this is not a find-and-replace
----------------------------------
A rename here is not one string. The scientific name is the key of three data
files that were built separately -- the ecoregion counts, the occupancy grid and
the occurrence marks -- and a row renamed in ``plants_master.json`` alone keeps
its page and silently loses its maps, which is a failure that looks like missing
data rather than a broken join.

What a rename does NOT touch, and why that is the good news
-----------------------------------------------------------
* **Public URLs.** ``static_site._unique_slugs`` keys on ``common_name``; the
  scientific name only breaks a tie between two species sharing one. So
  ``/plants/stinging-nettle/`` survives the rename. (A species *in* such a tie
  is reported below, because there the slug can move.)
* **Plant-fauna edges.** ``plant_fauna_master.json`` keys on the common name
  too, so all of them follow the row automatically.

What it deliberately leaves alone
---------------------------------
**Nativity.** It would be easy to write the province list in at the same time,
transcribed from a ``--suggest`` printout. That is a hand-copied fact wearing
the costume of a sourced one, and this catalogue's whole argument against its
old nativity data was exactly that. Rename first, then re-run
``fetch_flora_nativity.py --from-archive`` and ``ingest_flora_nativity.py
--apply``: under the corrected name the lookup now finds the taxon and writes
the provinces **and** ``native_provinces_source='flora'`` from the archive
itself.

The old name is kept on the row as ``renamed_from``, so nobody has to read a
commit log to find out that the records filed here arrived under another name.
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import date
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

#: Data files whose top-level ``species`` map is keyed by scientific name.
BY_SCIENTIFIC = ("plant_ecoregions.json", "plant_ranges.json",
                 "plant_occurrence_points.json")
PLANT_FILES = ("plants_master.json", "garden_plants.json")


def _load(name: str):
    with open(PROJECT_ROOT / "data" / name, encoding="utf-8") as fh:
        return json.load(fh)


def _save(name: str, data) -> None:
    """Write a data file back **in the format it already had**.

    ``plant_occurrence_points.json`` and ``plant_ranges.json`` ship compact
    (``separators=(",", ":")``, one line) because they are 2.7 MB and 1 MB of
    machine-written coordinates. Re-saving them with ``indent=2`` inflated them
    to 9.5 MB and 3.3 MB across 960,000 lines, which is a 3.4x repository cost
    and a diff nobody can read, for a change of one dictionary key.

    So the existing file decides: one line in, one line out.
    """
    path = PROJECT_ROOT / "data" / name
    text = json.dumps(data, indent=_indent_of(path), ensure_ascii=False) \
        if _indent_of(path) else \
        json.dumps(data, ensure_ascii=False, separators=(",", ":"))
    path.write_text(text + "\n", encoding="utf-8")


def _indent_of(path: Path) -> int:
    """The file's own indent width, or ``0`` meaning compact.

    Sniffed rather than assumed, twice over. ``plant_fauna_master.json`` is
    written with **indent=1**, so re-saving it at the obvious ``indent=2``
    reindented all 53,000 lines and turned a 600-edge change into a whole-file
    diff.
    """
    try:
        with open(path, encoding="utf-8") as fh:
            fh.readline()
            second = fh.readline()
    except OSError:
        return 2
    if not second.strip():
        return 0
    return len(second) - len(second.lstrip(" ")) or 2


def survey(old: str, new: str) -> dict:
    """Everything the rename would touch. Counts only, writes nothing."""
    plant_file = row = None
    for name in PLANT_FILES:
        for candidate in _load(name):
            if (isinstance(candidate, dict)
                    and candidate.get("scientific_name") == old):
                plant_file, row = name, candidate
                break
        if row is not None:
            break
    if row is None:
        raise SystemExit(f"{old} is not in the catalogue.")

    clash = None
    for name in PLANT_FILES:
        for candidate in _load(name):
            if (isinstance(candidate, dict)
                    and candidate.get("scientific_name") == new):
                clash = name
    common = row.get("common_name") or ""

    # A slug is the common name unless two species share one, and there the
    # scientific name is the tiebreak -- so those are the only renames that can
    # move a public URL.
    shares_common = sum(
        1 for name in PLANT_FILES for c in _load(name)
        if isinstance(c, dict) and (c.get("common_name") or "") == common) > 1

    hits = {}
    for name in BY_SCIENTIFIC:
        try:
            blob = _load(name)
        except (FileNotFoundError, json.JSONDecodeError):
            continue
        species = (blob or {}).get("species") or {}
        if old in species:
            hits[name] = species[old]

    return {"old": old, "new": new, "plant_file": plant_file, "row": row,
            "common": common, "data_files": hits, "clash": clash,
            "shares_common": shares_common}


def report(s: dict) -> None:
    print(f"\n=== RENAME: {s['old']}  ->  {s['new']} ===")
    print(f"  {s['common']}, in {s['plant_file']}")
    for name in s["data_files"]:
        print(f"  re-key 1 entry in data/{name}")
    if not s["data_files"]:
        print("  no keyed data entries (this species has no maps yet)")
    print("  plant-fauna edges follow the common name, so none need touching")
    if s["shares_common"]:
        print(f"  WARNING: another species shares the common name "
              f"'{s['common']}', so the slug is tie-broken by scientific name "
              f"and this URL CAN move")
    else:
        print(f"  URL /plants/{s['common'].lower().replace(' ', '-')}/ is "
              f"unaffected")
    if s["clash"]:
        print(f"  REFUSING: {s['new']} is already in data/{s['clash']}")


def apply(s: dict, authority: str) -> None:
    if not authority:
        raise SystemExit("--apply needs --authority: a rename with no source "
                         "recorded is one the next data pass will undo.")
    if s["clash"]:
        raise SystemExit(f"{s['new']} already exists; merge, do not rename.")

    rows = _load(s["plant_file"])
    for row in rows:
        if isinstance(row, dict) and row.get("scientific_name") == s["old"]:
            row["scientific_name"] = s["new"]
            row["renamed_from"] = s["old"]
            row["renamed_authority"] = authority
            row["renamed_on"] = date.today().isoformat()
            # The old nativity was filed against the old name and is exactly
            # what the re-run is for. Clearing it is the honest state in
            # between: unknown, rather than a claim about a different taxon.
            row["native_provinces_source"] = ""
    _save(s["plant_file"], rows)

    for name, value in s["data_files"].items():
        blob = _load(name)
        blob["species"].pop(s["old"], None)
        blob["species"][s["new"]] = value
        _save(name, blob)

    print(f"\nRenamed. {len(s['data_files'])} data file(s) re-keyed.")


def main(argv=None) -> int:
    p = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("old_name")
    p.add_argument("new_name")
    p.add_argument("--authority", default="",
                   help="the flora that says so. Required with --apply.")
    p.add_argument("--apply", action="store_true",
                   help="write the change. Report only without it.")
    args = p.parse_args(argv)

    s = survey(args.old_name, args.new_name)
    report(s)
    if not args.apply:
        print("\n(report only, nothing written.)")
        return 0
    apply(s, args.authority)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
