#!/usr/bin/env python3
"""
scripts/derive_animals_here.py — each region pack's animal records (V3.37,
F190; docs/plans/V3.37-animals-that-belong-here.md).

**Dev-time, needs no network.** Joins the two GBIF counts the repository keeps
for every catalogue animal: its records within each pack's circle
(``data/fetched/animals_near.json``, from ``scripts/fetch_animals_near.py`` on
the owner's PC) and across the pack's province
(``data/fetched/fauna_nativity.json``, from ``scripts/fetch_fauna_nativity.py``).
It writes ``data/regions/<key>/animal_records.json``, which ships and which
``src/fauna_fit.py`` reads. Neither input ships: ``data/fetched/`` stays out
of the installer.

    python scripts/derive_animals_here.py            # report, write nothing
    python scripts/derive_animals_here.py --write    # write each pack's file
    python scripts/derive_animals_here.py --check    # exit 1 if a file is stale

When to run it: after either count is fetched again, and after an animal is
added to, renamed in or removed from ``data/fauna_master.json``. ``--check`` is
what the test suite does.

A pack whose circle has moved since its count was fetched is not written: the
counts would be for another place. An animal GBIF did not answer for is left
out of the file and reads *unrecorded*, never zero.
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

DATA = PROJECT_ROOT / "data"
NEAR_PATH = DATA / "fetched" / "animals_near.json"
PROVINCE_PATH = DATA / "fetched" / "fauna_nativity.json"
CATALOGUE_PATH = DATA / "fauna_master.json"

from src import fauna_fit, region  # noqa: E402

#: The province count's field in ``fauna_nativity.json``, by pack province.
_PROVINCE_FIELD = {"AB": "ab_records", "SK": "sk_records"}


def _load(path: Path):
    with open(path, encoding="utf-8") as fh:
        return json.load(fh)


def build(pack, near_pack: dict, province: dict, catalogue: list) -> dict:
    """The pack's file contents from the two counts and the catalogue."""
    counts = near_pack.get("animals") or {}
    fld = _PROVINCE_FIELD[pack.province]
    animals = {}
    for row in catalogue:
        name = (row.get("scientific_name") or "").strip()
        if not name or name not in counts:
            continue
        animals[name] = {"group": row.get("taxon") or "",
                         "near": int(counts[name]),
                         "province": int((province.get(name) or {}).get(fld)
                                         or 0)}
    return {"version": fauna_fit.VERSION, "key": pack.key,
            "province": pack.province, "radius_km": float(pack.radius_km),
            "centre": list(pack.centre),
            "fetched": near_pack.get("fetched") or "",
            "source": ("GBIF occurrence counts: within the pack's circle "
                       "(scripts/fetch_animals_near.py) and across its "
                       "province (scripts/fetch_fauna_nativity.py); living "
                       "specimens and fossils left out of both"),
            "animals": animals}


def moved(pack, near_pack: dict) -> bool:
    """Whether the pack's circle is not the one its count was fetched for."""
    centre = [round(float(v), 6) for v in near_pack.get("centre") or ()]
    return (centre != [round(float(v), 6) for v in pack.centre]
            or float(near_pack.get("radius_km") or 0) != float(pack.radius_km))


def summary(doc: dict) -> str:
    recs = fauna_fit.from_doc(doc)
    bands = Counter(recs.band(n) for n in recs.animals)
    lines = [f"{doc['key']}: {len(recs.animals)} animals counted, fetched "
             f"{doc['fetched'] or '?'}, {doc['radius_km']:g} km"]
    lines += [f"  {b:10s} {bands.get(b, 0):5d}" for b in fauna_fit.BANDS]
    lines.append("  near share by group: " + ", ".join(
        f"{g} {s:.1%}" for g, s in sorted(recs.shares.items())))
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(
        description=__doc__.split("\n\n")[0],
        formatter_class=argparse.RawDescriptionHelpFormatter)
    mode = p.add_mutually_exclusive_group()
    mode.add_argument("--write", action="store_true",
                      help="write each pack's animal_records.json")
    mode.add_argument("--check", action="store_true",
                      help="exit 1 if a pack's file is not what a fresh "
                           "derivation writes")
    args = p.parse_args(argv)
    near = (_load(NEAR_PATH) if NEAR_PATH.exists() else {}).get("packs") or {}
    province, catalogue = _load(PROVINCE_PATH), _load(CATALOGUE_PATH)
    stale = 0
    for key, pack in sorted(region.regions().items()):
        out = Path(region.animal_records_path(key))
        if key not in near:
            print(f"{key}: no count yet; run scripts/fetch_animals_near.py")
            if args.check and out.exists():
                print(f"  {out.name} has no count behind it")
                stale += 1
            continue
        if moved(pack, near[key]):
            print(f"{key}: the pack's circle has moved since its count was "
                  "fetched; run scripts/fetch_animals_near.py again")
            stale += 1
            continue
        text = fauna_fit.dumps(build(pack, near[key], province, catalogue))
        print(summary(json.loads(text)))
        current = out.read_text(encoding="utf-8") if out.exists() else ""
        if args.write and text != current:
            out.write_text(text, encoding="utf-8")
            print(f"  wrote {out.relative_to(PROJECT_ROOT)}")
        elif args.check and text != current:
            print(f"  {out.relative_to(PROJECT_ROOT)} is stale: run "
                  "python scripts/derive_animals_here.py --write")
            stale += 1
    return 1 if stale else 0


if __name__ == "__main__":
    sys.exit(main())
