#!/usr/bin/env python3
"""
scripts/derive_local_flora.py — which species are native around each place.

**Dev-time, needs no network.** Reads the point cache
(`data/fetched/plant_occurrences.json`), the catalogue's VASCAN province lists
(`data/plants_master.json`) and the owner's rulings
(`data/local_flora_rulings.json`), and writes `data/local_flora.json`, which
ships and which every surface reads through `src/native_here.py`.

    python scripts/derive_local_flora.py            # report, write nothing
    python scripts/derive_local_flora.py --write    # write data/local_flora.json
    python scripts/derive_local_flora.py --check    # exit 1 if the shipped file is stale

When to run it: after a ruling is added, after the cache is re-fetched, after a
species is added, renamed or removed. `--check` is what the test suite does, so
a stale file fails the build rather than quietly disagreeing with its inputs.

See `src/local_flora.py` for the rule and what each tier claims.
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
CACHE_PATH = DATA / "fetched" / "plant_occurrences.json"
CATALOGUE_PATH = DATA / "plants_master.json"
RULINGS_PATH = DATA / "local_flora_rulings.json"
OUTPUT_PATH = DATA / "local_flora.json"


def _load(path: Path):
    with open(path, encoding="utf-8") as fh:
        return json.load(fh)


def build(cache_path: Path = CACHE_PATH, catalogue_path: Path = CATALOGUE_PATH,
          rulings_path: Path = RULINGS_PATH) -> dict:
    """The document a fresh derivation would ship."""
    from src.local_flora import derive, parse_rulings
    catalogue = _load(catalogue_path)
    species = {r["scientific_name"]: r for r in catalogue
               if r.get("scientific_name")}
    rulings = (parse_rulings(_load(rulings_path), species)
               if rulings_path.exists() else {})
    return derive(catalogue, _load(cache_path), rulings)


def write() -> str:
    """Derive and write ``data/local_flora.json``; returns the summary."""
    from src.local_flora import dumps
    doc = build()
    OUTPUT_PATH.write_text(dumps(doc), encoding="utf-8")
    return summary(doc)


def rulings_for(scientific: str, path: Path = RULINGS_PATH) -> dict:
    """``{place: ruling}`` the owner has made on ``scientific``."""
    if not path.exists():
        return {}
    places = (_load(path).get("places") or {})
    return {k: rows[scientific] for k, rows in places.items()
            if scientific in (rows or {})}


def carry_rulings(old: str, new: str = "", path: Path = RULINGS_PATH) -> list:
    """Move ``old``'s rulings to ``new``, or drop them when ``new`` is empty.

    For ``rename_taxon.py`` and ``remove_taxon.py``, which re-key every other
    file keyed by scientific name: a ruling left on a name the catalogue no
    longer has stops the derivation outright (``parse_rulings`` refuses it).
    On a merge a ruling already on ``new`` stands. Returns ``[(place, what
    happened)]`` and writes only when something changed.
    """
    if not path.exists():
        return []
    doc = _load(path)
    changes = []
    for place, rows in (doc.get("places") or {}).items():
        if old not in (rows or {}):
            continue
        ruling = rows.pop(old)
        if new and new not in rows:
            rows[new] = ruling
            changes.append((place, f"moved to {new}"))
        else:
            changes.append((place, "dropped" + (f"; {new} keeps its own"
                                                if new else "")))
        doc["places"][place] = dict(sorted(rows.items()))
    if changes:
        path.write_text(json.dumps(doc, indent=2, ensure_ascii=False) + "\n",
                        encoding="utf-8")
    return changes


def summary(doc: dict) -> str:
    from src.local_flora import TIERS, is_native
    out = []
    for key, place in doc["places"].items():
        entries = place["species"].values()
        tiers = Counter(e["tier"] for e in entries)
        ruled = Counter(e["ruling"] for e in entries if e.get("ruling"))
        native = sum(1 for e in entries if is_native(e))
        out.append(f"{place['name']} ({place['radius_km']:g} km): "
                   f"{native} native of {len(place['species'])}")
        out += [f"  {t:16s} {tiers.get(t, 0)}" for t in TIERS]
        if ruled:
            out.append("  rulings: " + ", ".join(f"{k} {v}"
                                                  for k, v in sorted(ruled.items())))
    return "\n".join(out)


def main(argv: list[str] | None = None) -> int:
    from src.local_flora import dumps
    p = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter)
    mode = p.add_mutually_exclusive_group()
    mode.add_argument("--write", action="store_true",
                      help="write data/local_flora.json")
    mode.add_argument("--check", action="store_true",
                      help="exit 1 if data/local_flora.json is not what a "
                           "fresh derivation writes")
    args = p.parse_args(argv)

    text = dumps(build())
    current = (OUTPUT_PATH.read_text(encoding="utf-8")
               if OUTPUT_PATH.exists() else "")
    print(summary(json.loads(text)))
    if args.check:
        if text != current:
            print(f"\n{OUTPUT_PATH.relative_to(PROJECT_ROOT)} is stale: run "
                  "python scripts/derive_local_flora.py --write")
            return 1
        print("\nUp to date.")
        return 0
    if args.write:
        OUTPUT_PATH.write_text(text, encoding="utf-8")
        print(f"\nWrote {OUTPUT_PATH.relative_to(PROJECT_ROOT)}.")
    elif text != current:
        print("\nWould change data/local_flora.json; --write to write it.")
    else:
        print("\nUp to date.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
