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
#: The raw GBIF point cache the three above are DERIVED from. Not shipped, and
#: the only one a merge can union honestly: the derived files hold counts and
#: bands per cell, so combining two of them means re-deriving, not adding.
CACHE = "fetched/plant_occurrences.json"
#: The plant catalogues themselves.
PLANT_FILES = ("plants_master.json", "garden_plants.json")
#: Edges key on COMMON name, which is why both are needed throughout.
EDGE_FILE = "plant_fauna_master.json"
EXCLUDED = "excluded_taxa.json"


def _load(name: str):
    with open(PROJECT_ROOT / "data" / name, encoding="utf-8") as fh:
        return json.load(fh)


def _save(name: str, data) -> None:
    """Write a data file back **in the format it already had** — see the same
    function in ``rename_taxon.py``. The occurrence and range files ship
    compact; re-indenting them costs 3.4x the repository size for a one-key
    change."""
    path = PROJECT_ROOT / "data" / name
    width = _indent_of(path)
    text = (json.dumps(data, indent=width, ensure_ascii=False) if width
            else json.dumps(data, ensure_ascii=False, separators=(",", ":")))
    path.write_text(text + "\n", encoding="utf-8")


def _indent_of(path: Path) -> int:
    """The file's own indent width, or ``0`` meaning compact. See the twin in
    ``rename_taxon.py``: the occurrence and range files ship on one line, and
    ``plant_fauna_master.json`` is written at **indent=1**, so both obvious
    defaults are wrong for some file here."""
    try:
        with open(path, encoding="utf-8") as fh:
            fh.readline()
            second = fh.readline()
    except OSError:
        return 2
    if not second.strip():
        return 0
    return len(second) - len(second.lstrip(" ")) or 2


def _current_branch() -> str:
    """The checked-out branch, which under this repo's convention is the
    release. ``unknown`` rather than a guess if git cannot say."""
    try:
        out = subprocess.run(["git", "rev-parse", "--abbrev-ref", "HEAD"],
                             cwd=str(PROJECT_ROOT), capture_output=True,
                             text=True, encoding="utf-8", check=False)
        return out.stdout.strip() or "unknown"
    except OSError:
        return "unknown"


def _claim(edge: dict) -> tuple:
    """What an edge asserts, independent of who reported it.

    ``plant_fauna_master.json`` holds **one row per claim**, with a
    comma-separated source list where more than one work reports it — the form
    ``validate_plant_fauna`` already accepts and ``tests/test_fauna_sourcing``
    already enforces, on the grounds that *"a globi duplicate shadowing a real
    citation is the kind of rot that is only ever found by counting"*.
    """
    return ((edge.get("plant") or "").strip().lower(),
            (edge.get("fauna") or "").strip().lower(),
            edge.get("relationship") or "")


def absorb(existing: dict, incoming: dict) -> dict:
    """``existing``, having taken on everything ``incoming`` adds.

    Sources union, because two works reporting one relationship is strictly
    more evidence than one and dropping either loses a citation. Notes are kept
    when they differ, since each says what its own source actually reported.
    """
    sources = [s.strip() for s in
               f"{existing.get('source', '')},{incoming.get('source', '')}"
               .split(",") if s.strip()]
    existing["source"] = ",".join(dict.fromkeys(sources))
    mine, theirs = (existing.get("notes") or ""), (incoming.get("notes") or "")
    if theirs and theirs not in mine:
        existing["notes"] = f"{mine} {theirs}".strip()
    if incoming.get("renamed_from"):
        existing["renamed_from"] = incoming["renamed_from"]
    if (incoming.get("specificity") == "specialist"
            and not existing.get("specificity")):
        existing["specificity"] = "specialist"
    return existing


def dedupe_claims(edges: list) -> tuple:
    """``(edges, absorbed)`` with one row per claim.

    A merge re-points edges onto a name that may already carry the same claim
    from the other row: V2.80's yarrow merge left 135 of these behind, each
    counted twice by every relationship tally the site publishes.
    """
    out: list = []
    index: dict = {}
    absorbed = 0
    for edge in edges:
        if not (isinstance(edge, dict) and edge.get("plant")):
            out.append(edge)                       # the metadata header
            continue
        key = _claim(edge)
        if key in index:
            absorb(index[key], edge)
            absorbed += 1
            continue
        index[key] = edge
        out.append(edge)
    return out, absorbed


def _size(value) -> int:
    """How many records an entry in one of the keyed data files holds.

    The three files have three shapes -- a list of cells, a list of regions, and
    a ``{specimen: [...], observation: [...]}`` split -- and a merge has to know
    which of two entries is the fuller one.
    """
    if isinstance(value, dict):
        return sum(len(v) if hasattr(v, "__len__") else 1
                   for v in value.values())
    return len(value) if hasattr(value, "__len__") else 1


def _union_points(a, b):
    """Both rows' raw points, de-duplicated, order preserved."""
    seen: dict = {}
    for row in list(a or []) + list(b or []):
        seen.setdefault(json.dumps(row, separators=(",", ":")), row)
    return list(seen.values())


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
    #: ``file -> (mine, theirs)`` record counts, so a merge can say which entry
    #: it is about to keep instead of silently keeping the survivor's.
    sizes = {}
    for name in (*BY_SCIENTIFIC, CACHE):
        try:
            blob = _load(name)
        except (FileNotFoundError, json.JSONDecodeError):
            continue
        species = (blob or {}).get("species") or {}
        if scientific in species:
            if name in BY_SCIENTIFIC:
                data_hits[name] = 1
            sizes[name] = (_size(species[scientific]),
                           _size(species.get(merge_into))
                           if merge_into in species else 0)

    fields = []
    if merge_into:
        from scripts.merge_duplicate_species import (        # noqa: PLC0415
            merge_rows)
        _f, into = find(merge_into)
        _merged, fields = merge_rows(dict(into), row,
                                     into.get("common_name") or "")

    from scripts.derive_local_flora import rulings_for       # noqa: PLC0415
    return {
        "scientific": scientific, "common": common, "plant_file": plant_file,
        "merge_into": merge_into, "into_common": into_common,
        "edges": mine, "orphaned": orphaned, "data_files": data_hits,
        "sizes": sizes, "fields": fields,
        "source_refs": _source_refs(common),
        "local_rulings": rulings_for(scientific),
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
    for place in s.get("local_rulings") or {}:
        print(f"  the owner's {place} ruling in data/local_flora_rulings.json "
              + (f"moves to {s['merge_into']} unless it has its own"
                 if s["merge_into"] else "is dropped"))
    if s["merge_into"]:
        for name, (mine, theirs) in s["sizes"].items():
            if name == CACHE:
                print(f"  data/{name}: {mine} + {theirs} raw points UNIONED "
                      f"under {s['merge_into']}")
            elif mine > theirs:
                print(f"  data/{name}: keeping THIS row's {mine} records over "
                      f"the survivor's {theirs} (re-keyed; both record sets "
                      f"arrive on the next re-derivation from the cache)")
            else:
                print(f"  data/{name}: survivor's {theirs} records kept, "
                      f"this row's {mine} dropped")
        if s["fields"]:
            print(f"  {len(s['fields'])} field decisions:")
            for note in s["fields"]:
                print(f"      {note}")
    if s["source_refs"]:
        print(f"  {len(set(s['source_refs']))} mentions in Python source, "
              f"EDIT THESE BY HAND:")
        for ref in sorted(set(s["source_refs"])):
            print(f"      {ref}")


def apply(s: dict, authority: str, release: str) -> None:
    """Write the change. Requires an authority string, per V2.74."""
    if not authority:
        raise SystemExit("--apply needs --authority: a removal with no reason "
                         "recorded is one the next data pass will undo.")

    edges = _load(EDGE_FILE)
    moved_edges = []
    for e in edges:
        if not (isinstance(e, dict) and e.get("plant") == s["common"]):
            moved_edges.append(e)
            continue
        if s["merge_into"]:
            moved = dict(e)
            moved["plant"] = s["into_common"]
            # The provenance of the re-pointing, on the row. The source said
            # one name and we filed it under another; that is a judgement and
            # it travels with the record rather than being lost in a commit.
            moved["renamed_from"] = s["scientific"]
            moved_edges.append(moved)
    # One row per claim, sources unioned (V2.82). Re-pointing lands edges on a
    # name that may already carry the same claim from the other row, and a
    # second row is not a second fact.
    kept, duplicates = dedupe_claims(moved_edges)
    _save(EDGE_FILE, kept)

    # The row's fields, merged rather than discarded (V2.82). The two rows were
    # authored at different times and each knows things the other does not --
    # the nettle pair disagreed on 21 columns and the retired row held the only
    # photograph. Winner-takes-all was throwing all of that away.
    notes: list = []
    if s["merge_into"]:
        from scripts.merge_duplicate_species import (        # noqa: PLC0415
            merge_rows)
        _f, retired = find(s["scientific"])
        for name in PLANT_FILES:
            rows = _load(name)
            touched = False
            for i, row in enumerate(rows):
                if (isinstance(row, dict)
                        and row.get("scientific_name") == s["merge_into"]):
                    merged, notes = merge_rows(
                        dict(row), retired, row.get("common_name") or "")
                    merged["scientific_name"] = s["merge_into"]
                    merged["merged_from"] = s["scientific"]
                    merged["merged_on"] = date.today().isoformat()
                    rows[i] = merged
                    touched = True
            if touched:
                _save(name, rows)

    for name in PLANT_FILES:
        rows = _load(name)
        out = [r for r in rows
               if not (isinstance(r, dict)
                       and r.get("scientific_name") == s["scientific"])]
        if len(out) != len(rows):
            _save(name, out)

    for name in (*BY_SCIENTIFIC, CACHE):
        try:
            blob = _load(name)
        except (FileNotFoundError, json.JSONDecodeError):
            continue
        species = (blob or {}).get("species") or {}
        if s["scientific"] not in species:
            continue
        # Sortedness is read before the mutation, not after: every one of these
        # files is written in name order, and re-inserting a key appends it.
        was_sorted = list(species) == sorted(species)
        mine = species.pop(s["scientific"])
        if s["merge_into"] and name == CACHE:
            species[s["merge_into"]] = _union_points(
                species.get(s["merge_into"]), mine)
        elif s["merge_into"] and _size(mine) > _size(species.get(
                s["merge_into"], [])):
            species[s["merge_into"]] = mine
        blob["species"] = (dict(sorted(species.items())) if was_sorted
                           else species)
        _save(name, blob)

    # The local lists (F220), keyed by scientific name like the files above:
    # the owner's rulings follow a merge or go with a removal, and the derived
    # list is re-derived, because the suite refuses a stale one.
    from scripts.derive_local_flora import carry_rulings, write  # noqa: PLC0415
    for place, what in carry_rulings(s["scientific"], s["merge_into"]):
        print(f"  {place} ruling {what}")
    write()

    # V2.80's lesson, automated: `validate_excluded_taxa` maps every listed
    # common name to the exclusion, so listing one that DELIBERATELY continues
    # on another row reports the survivor as "back in plants_master.json". The
    # catalogue is re-read after the write rather than reasoned about.
    still_published = {r.get("common_name") for name in PLANT_FILES
                       for r in _load(name) if isinstance(r, dict)}
    continues = s["common"] in still_published

    excluded = _load(EXCLUDED)
    excluded.setdefault("taxa", []).append({
        "scientific_name": s["scientific"],
        "common_names": [] if continues else [s["common"]],
        **({"note": f"the common name {s['common']!r} is not listed above "
                    f"because it continues on another row"} if continues else {}),
        "reason": ("merged_into_" + s["merge_into"].replace(" ", "_").lower()
                   if s["merge_into"] else "introduced_to_alberta"),
        "authority": authority,
        "removed_in": release,
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
    if notes:
        print(f"\n{len(notes)} field decisions merged into {s['merge_into']}:")
        for note in notes:
            print(f"  {note}")
    if duplicates:
        print(f"\n{duplicates} re-pointed edge(s) asserted a claim "
              f"{s['into_common']} already carried; each was absorbed into the "
              f"existing row with its source added rather than dropped.")
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
    p.add_argument("--release", default="",
                   help="the V-version recording this, e.g. V2.82. Defaults "
                        "to the current branch, because the branch IS the "
                        "release here; it was hardcoded to V2.80 until V2.82.")
    p.add_argument("--apply", action="store_true",
                   help="write the change. Report only without it.")
    args = p.parse_args(argv)

    s = survey(args.scientific_name, args.merge_into)
    report(s)
    if not args.apply:
        print("\n(report only, nothing written. Add --apply --authority "
              "\"...\" to write.)")
        return 0
    apply(s, args.authority, args.release or _current_branch())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
