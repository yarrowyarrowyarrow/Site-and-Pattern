#!/usr/bin/env python3
"""Dev tool — report how well the seeded plant communities cover the native
species a user can actually buy, and flag any member name that won't resolve.

Read-only: loads the seed JSON + imports ``EXAMPLE_POLYCULTURES`` directly (no
DB, no Qt). Run from the repo root:

    python3 scripts/check_community_coverage.py

Two checks:
  1. Resolution — every community member name must match a catalogue
     ``common_name`` (case-insensitively), or it is silently dropped at seed
     time.
  2. Coverage — of the retail-available natives (availability_class in
     native_specialist / garden_centre / big_box), how many appear in at least
     one community, and which are still missing (grouped by type + ecoregion).
"""
from __future__ import annotations

import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

RETAIL_CLASSES = {"native_specialist", "garden_centre", "big_box"}
DATA_FILES = ["data/plants_master.json", "data/garden_plants.json"]


def _load_plants() -> list[dict]:
    plants: list[dict] = []
    for rel in DATA_FILES:
        with open(os.path.join(ROOT, rel), encoding="utf-8") as fh:
            plants.extend(json.load(fh))
    return plants


def _member_names() -> list[str]:
    """Every member name across top-level communities AND variations."""
    from src.db.polycultures import EXAMPLE_POLYCULTURES

    names: list[str] = []

    def _walk(defn: dict) -> None:
        for member in defn.get("members", []):
            names.append(member[0])
        for var in defn.get("variations", []):
            _walk(var)

    for community in EXAMPLE_POLYCULTURES:
        _walk(community)
    return names


def main() -> int:
    plants = _load_plants()
    by_name = {p["common_name"].lower(): p for p in plants}

    retail = {
        p["common_name"]
        for p in plants
        if p.get("availability_class") in RETAIL_CLASSES
        and str(p.get("native_to_alberta", 0)) in ("1", "True", "true")
    }

    member_names = _member_names()
    distinct_members = sorted(set(member_names))

    # 1. Resolution check.
    unresolved = sorted({n for n in member_names if n.lower() not in by_name})
    print(f"Member names: {len(distinct_members)} distinct "
          f"({len(member_names)} total references)")
    if unresolved:
        print(f"\n❌ {len(unresolved)} UNRESOLVED member name(s) "
              f"(silently dropped at seed time):")
        for n in unresolved:
            print(f"    - {n!r}")
    else:
        print("✅ All member names resolve to a catalogue plant.")

    # 2. Coverage of retail-available natives.
    covered = {n for n in retail if n in {m for m in distinct_members}}
    # case-insensitive coverage
    member_lower = {m.lower() for m in distinct_members}
    covered = {n for n in retail if n.lower() in member_lower}
    missing = sorted(retail - covered)

    print(f"\nRetail-available natives: {len(retail)}")
    print(f"Covered by a community:   {len(covered)}")
    print(f"Still missing:            {len(missing)}")

    if missing:
        by_type: dict[str, list[str]] = {}
        for name in missing:
            p = by_name.get(name.lower(), {})
            ptype = p.get("plant_type", "?")
            by_type.setdefault(ptype, []).append(name)
        print("\nMissing by plant_type:")
        for ptype in sorted(by_type, key=lambda t: -len(by_type[t])):
            names = by_type[ptype]
            print(f"\n  {ptype} ({len(names)}):")
            for name in names:
                p = by_name.get(name.lower(), {})
                eco = p.get("ab_ecoregion", "")
                print(f"    - {name}  [{eco}]")

    return 1 if unresolved else 0


if __name__ == "__main__":
    raise SystemExit(main())
