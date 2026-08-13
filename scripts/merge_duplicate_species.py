#!/usr/bin/env python3
"""Merge duplicate species rows in data/plants_master.json (V2.50).

    python scripts/merge_duplicate_species.py [--check]

WHY THIS EXISTS
-------------------------------------------------------------------------------
Building the website surfaced three scientific names appearing twice in the
catalogue under different common names. Two of them are in ``plants_master``
itself and are straightforwardly the same plant entered twice:

    Geum triflorum      "Old Man's Whiskers (Prairie Smoke)"  +  "Prairie Smoke"
    Valeriana sitchensis "Sitka Valerian"                     +  "Valerian"

They were not just cosmetic. ``_seed_plant_ecoregions`` keys its GBIF ranges by
scientific name and resolved that to a single id, so one row of each pair
silently lost its occurrence data (fixed in V2.48 by mapping to every matching
id, which is the right fix for genuinely distinct rows and the wrong shape to
rely on for rows that should never have been two).

WHICH NAME SURVIVES
-------------------------------------------------------------------------------
The author's call, and it is a call rather than a lookup: several of these
plants carry three or four common names in circulation and picking one is an
editorial decision about what a reader is most likely to search for.

    Geum triflorum       -> "Three Flowered Avens (Prairie Smoke, Old Man's Whiskers)"
    Valeriana sitchensis -> "Sitka Valerian"

HOW THE TWO ROWS ARE COMBINED
-------------------------------------------------------------------------------
Field by field, keeping whichever row actually recorded something rather than
picking a winner wholesale: the two rows were authored at different times and
each knows things the other does not. Comma-delimited tag columns are **unioned**
(one row had ``medicinal`` and the other did not, and dropping it would lose a
real fact). A conflict between two non-empty scalar values keeps the survivor's
and prints the discarded one, so a genuine disagreement is visible rather than
silently resolved.

THE PART THIS SCRIPT DOES NOT DO
-------------------------------------------------------------------------------
Common names are a foreign key in more places than the catalogue. The seeded
example communities in ``src/db/polycultures.py`` name their members as literal
strings, so retiring a common name here leaves them pointing at nothing. Both
Geum rows and the ``Valerian`` row were named in three communities, and the run
that merged them broke all three.

``tests/test_polycultures.py:test_all_member_names_resolve`` catches it — it is
what caught it — but only after a full-suite run, so **after any rename here,
grep the retired names across ``src/`` and ``data/`` before committing**.
"""

from __future__ import annotations

import argparse
import json
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))

_JSON = pathlib.Path(__file__).resolve().parent.parent / "data" / "plants_master.json"

#: ``scientific_name -> (surviving common name, name of the row to keep as the
#: base)``. The base is the row whose other fields are preferred on a conflict.
MERGES: dict = {
    "Geum triflorum": (
        "Three Flowered Avens (Prairie Smoke, Old Man's Whiskers)",
        "Old Man's Whiskers (Prairie Smoke)"),
    "Valeriana sitchensis": ("Sitka Valerian", "Sitka Valerian"),
}

#: Columns holding a comma-delimited SET rather than a single value. Unioned on
#: merge, then re-sorted so the result does not depend on row order.
#:
#: ``edible_parts`` is deliberately NOT here even though it looks like one. Its
#: values contain commas inside parentheses ("roots (medicinal, not culinary)")
#: and unioning on the comma shredded that into three tokens reading
#: "not culinary)", "root (medicinal)" and "roots (medicinal". It is free text
#: and is treated as free text.
_SET_COLUMNS = ("permaculture_uses", "ecoregion", "native_provinces",
                "sun_requirement", "water_needs")

#: Free-text columns worth keeping BOTH of: the two rows were written at
#: different times and each says something the other does not. The Valerian
#: pair is the case in point, where the discarded row carried the warning that
#: the valerian usually sold is a different, non-native species.
_JOIN_COLUMNS = ("notes",)


def _clean_note(text: str) -> str:
    """Drop the stale "this is a duplicate" sentence a merge makes false."""
    keep = [s for s in (text or "").split(". ")
            if "DUPLICATE ENTRY" not in s.upper()]
    return ". ".join(s.strip() for s in keep if s.strip()).strip()


def _join(a: str, b: str) -> str:
    a, b = _clean_note(a), _clean_note(b)
    if not b or b in a:
        return a
    if not a:
        return b
    return f"{a.rstrip('.')}. {b}"


def _union(a: str, b: str) -> str:
    parts = {t.strip() for t in f"{a or ''},{b or ''}".split(",") if t.strip()}
    return ",".join(sorted(parts))


def merge_rows(base: dict, other: dict, name: str) -> tuple:
    """``(merged row, [notes about discarded values])``."""
    merged = dict(base)
    notes = []
    for key, value in other.items():
        if key == "common_name":
            continue
        if key in _SET_COLUMNS:
            joined = _union(merged.get(key, ""), value)
            if joined != (merged.get(key) or ""):
                notes.append(f"{key}: unioned to {joined!r}")
            merged[key] = joined
            continue
        if key in _JOIN_COLUMNS:
            joined = _join(merged.get(key, ""), value)
            if joined != (merged.get(key) or ""):
                notes.append(f"{key}: kept both, {len(joined)} chars")
            merged[key] = joined
            continue
        mine = merged.get(key)
        if mine in (None, "", []):
            if value not in (None, "", []):
                merged[key] = value
                notes.append(f"{key}: took {value!r} from the other row")
        elif value not in (None, "", []) and value != mine:
            notes.append(f"{key}: kept {mine!r}, discarded {value!r}")
    merged["common_name"] = name
    return merged, notes


def apply(rows: list) -> tuple:
    out, report = [], []
    handled = set()
    by_sci: dict = {}
    for row in rows:
        by_sci.setdefault((row.get("scientific_name") or "").strip(), []).append(row)

    for row in rows:
        sci = (row.get("scientific_name") or "").strip()
        if sci not in MERGES:
            out.append(row)
            continue
        if sci in handled:
            continue                      # the second copy; already merged
        handled.add(sci)
        name, base_name = MERGES[sci]
        group = by_sci[sci]
        if len(group) == 1:
            group[0]["common_name"] = name
            out.append(group[0])
            report.append(f"{sci}: only one row, renamed to {name!r}")
            continue
        base = next((r for r in group
                     if (r.get("common_name") or "") == base_name), group[0])
        merged = base
        notes: list = []
        for other in group:
            if other is base:
                continue
            merged, more = merge_rows(merged, other, name)
            notes.extend(more)
        out.append(merged)
        dropped = [r.get("common_name") for r in group if r is not base]
        report.append(f"{sci}: {len(group)} rows -> 1, named {name!r} "
                      f"(absorbed {dropped})")
        report.extend(f"    {n}" for n in notes)
    return out, report


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--check", action="store_true",
                    help="report what would change; write nothing")
    args = ap.parse_args()

    rows = json.loads(_JSON.read_text(encoding="utf-8"))
    merged, report = apply(rows)
    print(f"{len(rows)} rows -> {len(merged)}")
    for line in report:
        print(f"  {line}")

    names = [r.get("scientific_name") for r in merged]
    dupes = sorted({n for n in names if names.count(n) > 1})
    if dupes:
        print(f"\n  still duplicated: {dupes}")

    if args.check:
        print("\n--check: nothing written")
        return 0
    _JSON.write_text(json.dumps(merged, indent=2, ensure_ascii=False) + "\n",
                     encoding="utf-8")
    print(f"\nwrote {_JSON}")
    print("Remember to bump _SCHEMA_VERSION in src/db/plants.py.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
