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
    python scripts/derive_local_flora.py --merge PATH   # fold in a review, then write

When to run it: after a ruling is added, after the cache is re-fetched, after a
species is added, renamed or removed. `--check` is what the test suite does, so
a stale file fails the build rather than quietly disagreeing with its inputs.

`--merge` takes the owner's review (V3.12): the review page's export (a file in
the rulings format), or its database rows saved one JSON file per ruling (a
directory, which is what `ArtifactData list` with `out_dir` writes). A yes
(`native`) or a no (`not_native`) replaces a species' ruling, and `unsettled`,
which the page writes when an answer is taken back, removes one. Every ruling is
checked before anything is written. Rulings carry no reason.

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


def _shown(path: Path) -> str:
    """``path`` relative to the repository when it is inside it."""
    try:
        return str(path.relative_to(PROJECT_ROOT))
    except ValueError:
        return str(path)


def _load(path: Path):
    with open(path, encoding="utf-8") as fh:
        return json.load(fh)


def build(cache_path: Path = CACHE_PATH, catalogue_path: Path = CATALOGUE_PATH,
          rulings_path: Path | None = None) -> dict:
    """The document a fresh derivation would ship."""
    from src.local_flora import derive, parse_rulings
    # Read at call time, not bound as a default: a test that points the module
    # at a temporary file must not have the real one read (or written) instead.
    rulings_path = rulings_path or RULINGS_PATH
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


def read_review(path: Path, place: str = "edmonton") -> dict:
    """A review's rulings, as ``{"places": {place: {name: ruling}}}``.

    ``path`` is the review page's export (a file already in that shape), or a
    directory of its database rows, one JSON file each carrying
    ``scientific_name``, ``ruling`` and ``on`` (the directory itself, or one
    holding a ``rulings`` folder), which belong to ``place``.
    """
    path = Path(path)
    if not path.is_dir():
        return _load(path)
    folder = path / "rulings" if (path / "rulings").is_dir() else path
    rows = {}
    for f in sorted(folder.glob("*.json")):
        row = _load(f)
        name = row.get("scientific_name") if isinstance(row, dict) else None
        if not name:
            raise ValueError(f"{f.name}: a ruling row without a scientific_name")
        rows[name] = {k: row[k] for k in ("ruling", "on") if k in row}
    return {"places": {place: rows}}


def merge_rulings(review: dict, path: Path | None = None,
                  catalogue_path: Path = CATALOGUE_PATH) -> list:
    """Fold a review into the rulings file; returns ``[(place, name, what)]``.

    ``native`` and ``not_native`` replace whatever ruling a species had;
    ``unsettled`` (an answer taken back on the page) removes an earlier one.
    Only the ruling and its date are kept. The merged file is checked whole by
    :func:`src.local_flora.parse_rulings` before it is written, so one bad row
    (a name the catalogue lacks, a ruling that is neither yes nor no, a
    "native" across the VASCAN gate) raises ``ValueError`` and writes nothing.
    """
    from src.local_flora import parse_rulings
    path = path or RULINGS_PATH
    species = {r["scientific_name"]: r for r in _load(catalogue_path)
               if r.get("scientific_name")}
    doc = _load(path) if path.exists() else {"version": 1, "places": {}}
    places = doc.setdefault("places", {})
    changes = []
    for place, rows in ((review or {}).get("places") or {}).items():
        current = dict(places.get(place) or {})
        for name, row in sorted((rows or {}).items()):
            row = row or {}
            before = (current.get(name) or {}).get("ruling")
            if row.get("ruling") == "unsettled":
                if name in current:
                    del current[name]
                    changes.append((place, name, f"{before} removed"))
                continue
            entry = {k: str(row[k]).strip() for k in ("ruling", "on")
                     if str(row.get(k) or "").strip()}
            if current.get(name) == entry:
                continue
            current[name] = entry
            changes.append((place, name, entry.get("ruling", "") if before is None
                            else f"{before} -> {entry.get('ruling', '')}"))
        places[place] = dict(sorted(current.items()))
    parse_rulings(doc, species)
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
    mode.add_argument("--merge", metavar="PATH",
                      help="fold a review into data/local_flora_rulings.json "
                           "(the page's export, or a directory of its rows), "
                           "then write data/local_flora.json")
    p.add_argument("--place", default="edmonton",
                   help="the place a directory of rows belongs to "
                        "(default: edmonton)")
    args = p.parse_args(argv)

    if args.merge:
        try:
            changes = merge_rulings(read_review(Path(args.merge), args.place))
        except (OSError, ValueError) as exc:
            print(f"Nothing merged: {exc}")
            return 1
        for place, name, what in changes:
            print(f"  {place}: {name}: {what}")
        print(f"{len(changes)} ruling(s) changed in "
              f"{_shown(RULINGS_PATH)}.\n")
        args.write = True

    text = dumps(build())
    current = (OUTPUT_PATH.read_text(encoding="utf-8")
               if OUTPUT_PATH.exists() else "")
    print(summary(json.loads(text)))
    if args.check:
        if text != current:
            print(f"\n{_shown(OUTPUT_PATH)} is stale: run "
                  "python scripts/derive_local_flora.py --write")
            return 1
        print("\nUp to date.")
        return 0
    if args.write:
        OUTPUT_PATH.write_text(text, encoding="utf-8")
        print(f"\nWrote {_shown(OUTPUT_PATH)}.")
    elif text != current:
        print("\nWould change data/local_flora.json; --write to write it.")
    else:
        print("\nUp to date.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
