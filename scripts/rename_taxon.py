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
**Nativity, when the new name is a judgement.** It would be easy to write the
province list in at the same time, transcribed from a ``--suggest`` printout.
That is a hand-copied fact wearing the costume of a sourced one, and this
catalogue's whole argument against its old nativity data was exactly that.
Rename first, then re-run ``fetch_flora_nativity.py --from-archive`` and
``ingest_flora_nativity.py --apply``: under the corrected name the lookup now
finds the taxon and writes the provinces **and**
``native_provinces_source='flora'`` from the archive itself.

**But not when the new name is the archive's own answer (V2.82).** If
``flora_nativity.json`` recorded ``accepted_name`` for the old name and the new
name IS that name, the province list was never a claim about the old name --
VASCAN was asked about a synonym and replied about the accepted taxon, saying
so in the record. Re-keying that record and keeping the source is therefore not
a transcription, and clearing it would publish *Not established* for a species
the checklist has already settled. V2.80 renamed eight species and accepted
exactly that limbo for all eight; this is the case where there is nothing to
wait for.

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
#:
#: **``fetched/plant_occurrences.json`` is the important one and was missing
#: until V2.81.** The other three are *derived* from it, so re-keying them and
#: not it leaves a raw point cache holding the old name. Nothing breaks and
#: nothing warns; the species simply is not in the cache any more, so the next
#: ``--from-cache`` re-derivation silently drops it. Found the way it would be:
#: the V2.81 re-derivation produced 407 species where the file had 415, and
#: seven of the eight missing ones were still in the catalogue.
#:
#: The cache is a dev artefact and is not shipped, which is exactly why it is
#: easy to forget and expensive to forget -- a re-fetch of ~500,000 GBIF
#: records is the only other way back.
BY_SCIENTIFIC = ("plant_ecoregions.json", "plant_ranges.json",
                 "plant_occurrence_points.json",
                 "fetched/plant_occurrences.json")
PLANT_FILES = ("plants_master.json", "garden_plants.json")

#: The VASCAN extract, keyed by the name that was **asked about** rather than by
#: the name the checklist answered with (V2.82).
NATIVITY = "fetched/flora_nativity.json"


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


def _rekey(mapping: dict, old: str, new: str) -> dict:
    """``mapping`` with ``old``'s value moved to ``new``, **in sorted order**.

    ``pop`` then assign appends, and every one of these files is written in
    name order, so a rename used to drop the species at the bottom of a 400-key
    file -- a two-line change rendered as a 200-line diff, and the next rename
    of the same row rendered as another one. Sorted in, sorted out; a file that
    was not sorted to begin with is left in its own order.
    """
    was_sorted = list(mapping) == sorted(mapping)
    value = mapping.pop(old)
    mapping[new] = value
    return dict(sorted(mapping.items())) if was_sorted else mapping


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


from src.taxon_names import binomial                          # noqa: E402


def _nativity_record(old: str) -> dict:
    """The VASCAN extract's entry for ``old``, or ``{}``."""
    try:
        blob = _load(NATIVITY)
    except (FileNotFoundError, json.JSONDecodeError):
        return {}
    got = ((blob or {}).get("results") or {}).get(old)
    return got if isinstance(got, dict) else {}


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

    # Is the new name the one the archive itself resolved the old one to? If so
    # the recorded province list is about the taxon we are renaming TO, and
    # clearing its source would throw away a sourced fact to avoid a
    # transcription that is not happening.
    nativity = _nativity_record(old)
    carries = bool(nativity.get("accepted_name")
                   and binomial(nativity["accepted_name"]) == new)

    from scripts.derive_local_flora import rulings_for       # noqa: PLC0415
    return {"old": old, "new": new, "plant_file": plant_file, "row": row,
            "common": common, "data_files": hits, "clash": clash,
            "shares_common": shares_common,
            "nativity": nativity, "carries_nativity": carries,
            "local_rulings": rulings_for(old)}


def report(s: dict) -> None:
    print(f"\n=== RENAME: {s['old']}  ->  {s['new']} ===")
    print(f"  {s['common']}, in {s['plant_file']}")
    for name in s["data_files"]:
        print(f"  re-key 1 entry in data/{name}")
    if not s["data_files"]:
        print("  no keyed data entries (this species has no maps yet)")
    print("  plant-fauna edges follow the common name, so none need touching")
    for place in s.get("local_rulings") or {}:
        print(f"  carry the owner's {place} ruling in "
              f"data/local_flora_rulings.json, then re-derive local_flora.json")
    if s["shares_common"]:
        print(f"  WARNING: another species shares the common name "
              f"'{s['common']}', so the slug is tie-broken by scientific name "
              f"and this URL CAN move")
    else:
        print(f"  URL /plants/{s['common'].lower().replace(' ', '-')}/ is "
              f"unaffected")
    if s["carries_nativity"]:
        rec = s["nativity"]
        print(f"  nativity KEPT: the archive resolved {s['old']} to "
              f"{rec['accepted_name']!r} and recorded {rec.get('native_provinces')!r}"
              f" — that record is about the new name, so it is re-keyed in "
              f"data/{NATIVITY} and native_provinces_source stands")
    elif s["nativity"]:
        print(f"  nativity CLEARED: the archive's accepted name for "
              f"{s['old']} is {s['nativity'].get('accepted_name')!r}, not "
              f"{s['new']} — so its province list is about a different taxon. "
              f"Re-run fetch_flora_nativity.py --from-archive, then "
              f"ingest_flora_nativity.py --apply.")
    else:
        print(f"  nativity CLEARED: no entry in data/{NATIVITY} to carry")
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
            # A second rename must not erase the first (V2.82). Two of these
            # rows had already moved once -- Oenothera caespitosa -> O.
            # cespitosa subsp. cespitosa -> O. cespitosa -- and overwriting
            # the field loses the name a reader is most likely to search for,
            # which is the whole reason it exists.
            row["renamed_from"] = ", ".join(
                dict.fromkeys([*(t.strip() for t in
                                 (row.get("renamed_from") or "").split(",")
                                 if t.strip()), s["old"]]))
            row["renamed_authority"] = authority
            row["renamed_on"] = date.today().isoformat()
            # The old nativity was filed against the old name and is exactly
            # what the re-run is for. Clearing it is the honest state in
            # between: unknown, rather than a claim about a different taxon.
            #
            # Unless (V2.82) the new name IS the accepted name the archive
            # resolved the old one to. Then the record was never about the old
            # name -- VASCAN answered for the accepted taxon and said so in
            # `accepted_name` -- and clearing the source would report a sourced
            # fact as unknown.
            if not s["carries_nativity"]:
                row["native_provinces_source"] = ""
    _save(s["plant_file"], rows)

    if s["carries_nativity"]:
        blob = _load(NATIVITY)
        blob["results"] = _rekey(blob["results"], s["old"], s["new"])
        _save(NATIVITY, blob)

    for name, value in s["data_files"].items():
        blob = _load(name)
        blob["species"] = _rekey(blob["species"], s["old"], s["new"])
        _save(name, blob)

    # The local lists (F220): the owner's rulings follow the name, and the
    # derived list is re-derived, because it is keyed by the name too and the
    # suite refuses a stale one.
    from scripts.derive_local_flora import carry_rulings, write  # noqa: PLC0415
    for place, what in carry_rulings(s["old"], s["new"]):
        print(f"  {place} ruling {what}")
    write()

    print(f"\nRenamed. {len(s['data_files']) + (1 if s['carries_nativity'] else 0)}"
          f" data file(s) re-keyed.")
    if s["carries_nativity"]:
        print("  native_provinces_source kept; nothing to re-run.")
    else:
        print("  native_provinces_source cleared; re-run "
              "fetch_flora_nativity.py --from-archive then "
              "ingest_flora_nativity.py --apply.")


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
