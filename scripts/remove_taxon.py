#!/usr/bin/env python3
"""
scripts/remove_taxon.py — take a species out, or merge it into another.

**Reports by default. Applies nothing without --apply.**

    python scripts/remove_taxon.py "Helianthus annuus"
    python scripts/remove_taxon.py "Achillea millefolium" --merge-into "Achillea borealis"
    python scripts/remove_taxon.py "Helianthus annuus" --apply --authority "VASCAN records it as introduced in AB and SK."

Why a script and not an edit
----------------------------
A removal here is never one row. *Rudbeckia hirta* (V2.74) took **150
documented edges, an ecoregion entry, two polyculture memberships and a worked
example** with it, and the record of that removal notes the part that went
wrong: it **orphaned six animals**, leaving them in the catalogue with no plant
relationship and therefore no page worth having. V2.75's removal checked for
that and said so.

So this does the counting first, every time, and names what a removal would
strip before anything is written.

Remove, or merge?
-----------------
``--merge-into`` re-points the edges at another species instead of deleting
them, which is the right move when the plant is not absent but **misnamed**:
the animals recorded on *Achillea millefolium* in Alberta were feeding on the
native race, which this catalogue already carries as *Achillea borealis*.

That is a judgement and the script refuses to hide it. A merged edge keeps its
original source and gains a ``renamed_from`` field naming the taxon the record
actually said, so a reader of the data can see that we re-pointed it and on
what basis. An edge whose provenance quietly changes species is the kind of
thing this catalogue exists to not do.

What it does NOT touch
----------------------
Seeded polycultures and the worked example live in **Python** (
``src/db/polycultures.py``, ``src/onboarding.py``), keyed by common name. Those
are printed as a list of file:line for you to edit, because a script rewriting
source it does not understand is worse than a checklist.
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

#: Data files keyed by SCIENTIFIC name.
BY_SCIENTIFIC = ("plant_ecoregions.json", "plant_ranges.json",
                 "plant_occurrence_points.json")
#: The plant catalogues themselves.
PLANT_FILES = ("plants_master.json", "garden_plants.json")
#: Edges key on COMMON name, which is why both are needed throughout.
EDGE_FILE = "plant_fauna_master.json"
EXCLUDED = "excluded_taxa.json"


def _load(name: str):
    with open(PROJECT_ROOT / "data" / name, encoding="utf-8") as fh:
        return json.load(fh)


def _save(name: str, data) -> None:
    (PROJECT_ROOT / "data" / name).write_text(
        json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def find(scientific: str) -> tuple:
    """``(file, row)`` for a species, or ``(None, None)``."""
    for name in PLANT_FILES:
        for row in _load(name):
            if isinstance(row, dict) and row.get("scientific_name") == scientific:
                return name, row
    return None, None


def survey(scientific: str, merge_into: str = "") -> dict:
    """Everything this removal would touch. Counts only, writes nothing."""
    plant_file, row = find(scientific)
    if row is None:
        raise SystemExit(f"{scientific} is not in the catalogue.")
    common = row.get("common_name") or ""

    into_common = ""
    if merge_into:
        _f, into = find(merge_into)
        if into is None:
            raise SystemExit(f"--merge-into {merge_into} is not in the "
                             f"catalogue either.")
        into_common = into.get("common_name") or ""

    edges = _load(EDGE_FILE)
    mine = [e for e in edges if isinstance(e, dict) and e.get("plant") == common]

    # The V2.74 mistake, checked before it can happen again: which animals
    # would be left in the catalogue with no plant relationship at all.
    others: dict = {}
    for e in edges:
        if isinstance(e, dict) and e.get("plant") and e.get("plant") != common:
            others[e.get("fauna")] = others.get(e.get("fauna"), 0) + 1
    orphaned = sorted({e.get("fauna") for e in mine} - set(others))

    data_hits = {}
    for name in BY_SCIENTIFIC:
        try:
            blob = _load(name)
        except (FileNotFoundError, json.JSONDecodeError):
            continue
        if scientific in ((blob or {}).get("species") or {}):
            data_hits[name] = 1

    return {
        "scientific": scientific, "common": common, "plant_file": plant_file,
        "merge_into": merge_into, "into_common": into_common,
        "edges": mine, "orphaned": orphaned, "data_files": data_hits,
        "source_refs": _source_refs(common),
    }


def _source_refs(common: str) -> list:
    """`file:line` for every mention in Python source. A checklist, not a fix."""
    if not common:
        return []
    try:
        out = subprocess.run(
            ["grep", "-rn", "--include=*.py", f'"{common}"', "src", "scripts"],
            cwd=str(PROJECT_ROOT), capture_output=True, text=True,
            encoding="utf-8", check=False)
    except OSError:
        return []
    return [ln.split(":", 2)[0] + ":" + ln.split(":", 2)[1]
            for ln in out.stdout.splitlines() if ln.strip()]


def report(s: dict) -> None:
    verb = (f"MERGE into {s['merge_into']} ({s['into_common']})"
            if s["merge_into"] else "REMOVE")
    print(f"\n=== {verb}: {s['scientific']} ({s['common']}) ===")
    print(f"  in {s['plant_file']}")
    print(f"  {len(s['edges'])} documented plant-fauna edges")
    if s["merge_into"]:
        print(f"      -> re-pointed to {s['into_common']}, each keeping its "
              f"source and gaining renamed_from")
    else:
        print("      -> deleted")
        if s["orphaned"]:
            print(f"  {len(s['orphaned'])} animals would be left with NO plant "
                  f"relationship at all (V2.74 orphaned six this way):")
            for name in s["orphaned"][:12]:
                print(f"      {name}")
            if len(s["orphaned"]) > 12:
                print(f"      ... and {len(s['orphaned']) - 12} more")
        else:
            print("  no animal is left without an edge")
    for name in s["data_files"]:
        print(f"  1 entry in data/{name}")
    if s["source_refs"]:
        print(f"  {len(set(s['source_refs']))} mentions in Python source, "
              f"EDIT THESE BY HAND:")
        for ref in sorted(set(s["source_refs"])):
            print(f"      {ref}")


def apply(s: dict, authority: str) -> None:
    """Write the change. Requires an authority string, per V2.74."""
    if not authority:
        raise SystemExit("--apply needs --authority: a removal with no reason "
                         "recorded is one the next data pass will undo.")

    edges = _load(EDGE_FILE)
    kept = []
    for e in edges:
        if not (isinstance(e, dict) and e.get("plant") == s["common"]):
            kept.append(e)
            continue
        if s["merge_into"]:
            moved = dict(e)
            moved["plant"] = s["into_common"]
            # The provenance of the re-pointing, on the row. The source said
            # one name and we filed it under another; that is a judgement and
            # it travels with the record rather than being lost in a commit.
            moved["renamed_from"] = s["scientific"]
            kept.append(moved)
    _save(EDGE_FILE, kept)

    for name in PLANT_FILES:
        rows = _load(name)
        out = [r for r in rows
               if not (isinstance(r, dict)
                       and r.get("scientific_name") == s["scientific"])]
        if len(out) != len(rows):
            _save(name, out)

    for name in s["data_files"]:
        blob = _load(name)
        blob.get("species", {}).pop(s["scientific"], None)
        _save(name, blob)

    excluded = _load(EXCLUDED)
    excluded.setdefault("taxa", []).append({
        "scientific_name": s["scientific"],
        "common_names": [s["common"]],
        "reason": ("merged_into_" + s["merge_into"].replace(" ", "_").lower()
                   if s["merge_into"] else "introduced_to_alberta"),
        "authority": authority,
        "removed_in": "V2.80",
        "removed_on": date.today().isoformat(),
        "took_with_it": (
            f"{len(s['edges'])} documented plant-fauna edges "
            + (f"re-pointed to {s['into_common']}"
               if s["merge_into"] else "deleted")
            + (f", {len(s['orphaned'])} animals left with no edge"
               if s["orphaned"] and not s["merge_into"] else "")
            + "".join(f", 1 entry in data/{n}" for n in s["data_files"])),
        **({"substitute": f"{s['merge_into']} ({s['into_common']})"}
           if s["merge_into"] else {}),
    })
    _save(EXCLUDED, excluded)
    print("\nWritten. Now, in order:")
    print("  1. edit the Python references listed above by hand")
    print("  2. bump _SCHEMA_VERSION in src/db/plants.py")
    print("  3. python -m src.cli validate-data")
    print("  4. python -m unittest discover -s tests -t .")


def main(argv=None) -> int:
    p = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("scientific_name")
    p.add_argument("--merge-into", default="", metavar="SPECIES",
                   help="re-point this species' edges at SPECIES instead of "
                        "deleting them")
    p.add_argument("--authority", default="",
                   help="why, and on whose say-so. Required with --apply.")
    p.add_argument("--apply", action="store_true",
                   help="write the change. Report only without it.")
    args = p.parse_args(argv)

    s = survey(args.scientific_name, args.merge_into)
    report(s)
    if not args.apply:
        print("\n(report only, nothing written. Add --apply --authority "
              "\"...\" to write.)")
        return 0
    apply(s, args.authority)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
