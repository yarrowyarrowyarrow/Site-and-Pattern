#!/usr/bin/env python3
"""
scripts/ingest_fauna_edges.py — review and merge fetched edges (F125).

The other half of ``fetch_fauna_edges.py``. That one runs where there is
internet; this one runs in the repo, offline, over the file it produced.

    python3 scripts/ingest_fauna_edges.py            # report only, changes nothing
    python3 scripts/ingest_fauna_edges.py --apply    # write into the seed files

**Report first, apply second, and never the other way round.** An aggregator
returns what it has, not what is true here: a greenhouse observation from
Belgium, a species that does not occur in Alberta, a genus-level record dressed
as a species. Everything below is a gate, and the gates are the point — this
catalogue's confidence work only means anything if a `documented` edge is
genuinely documented.

Every gate reports a count, so a run tells you what was thrown away and why
rather than only what survived.
"""

from __future__ import annotations

import argparse
import json
import os
import sys

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_DATA = os.path.join(_ROOT, "data")
_FETCHED = os.path.join(_DATA, "fetched")

#: The schema's vocabularies. Restated here as a gate rather than imported, so
#: a candidate file that predates a schema change fails loudly instead of
#: writing a value the CHECK constraint will reject at seed time.
_RELATIONSHIPS = {"larval_host", "nectar", "pollen", "seed_food",
                  "fruit_food", "nesting", "cover"}
_TAXA = {"lepidoptera", "bird", "bee", "other_insect", "mammal"}

#: The citation key new edges are filed under. Registered in
#: data/sources_master.json by --apply if it is not already there.
_SOURCE_KEY = "globi"
_SOURCE_TEXT = ("Global Biotic Interactions (GloBI), "
                "https://globalbioticinteractions.org — aggregated interaction "
                "records; the reporting study travels with each edge in notes.")


def _rows(path: str) -> list:
    with open(path, "r", encoding="utf-8") as fh:
        blob = json.load(fh)
    return blob if isinstance(blob, list) else next(
        v for v in blob.values() if isinstance(v, list))


def _load_seed() -> tuple:
    plants = {}
    for name in ("plants_master.json", "garden_plants.json"):
        for r in _rows(os.path.join(_DATA, name)):
            if r.get("common_name"):
                plants[r["common_name"].strip().lower()] = r["common_name"]
    fauna = {}
    for r in _rows(os.path.join(_DATA, "fauna_master.json")):
        if r.get("scientific_name"):
            fauna[r["scientific_name"].strip().lower()] = r
    edge_rows = _rows(os.path.join(_DATA, "plant_fauna_master.json"))
    existing = {(r["plant"].strip().lower(), r["fauna"].strip().lower(),
                 r.get("relationship", ""))
                for r in edge_rows if r.get("plant") and r.get("fauna")}
    return plants, fauna, edge_rows, existing


def review(candidates: list) -> dict:
    """Run every gate. Returns counts plus the edges that survived."""
    plants, fauna, _edge_rows, existing = _load_seed()
    kept, rejected = [], {}

    def drop(reason):
        rejected[reason] = rejected.get(reason, 0) + 1

    seen = set()
    for c in candidates:
        plant = (c.get("plant") or "").strip()
        animal = (c.get("fauna") or "").strip()
        rel = (c.get("relationship") or "").strip()

        if not plant or not animal or not rel:
            drop("incomplete record"); continue
        if rel not in _RELATIONSHIPS:
            drop(f"relationship not in the schema vocabulary ({rel})"); continue
        if (c.get("_taxon") or "") not in _TAXA:
            drop("taxon not in the schema vocabulary"); continue
        if plant.strip().lower() not in plants:
            drop("plant is not in this catalogue"); continue
        if " " not in animal:
            drop("animal is genus-level, not a species"); continue
        key = (plant.lower(), animal.lower(), rel)
        if key in existing:
            drop("already seeded"); continue
        if key in seen:
            drop("duplicate within the candidate file"); continue
        # The gate that matters most: an edge with no reporting study is an
        # assertion, and this table is defined as documented records only.
        if not (c.get("_citation") or "").strip():
            drop("no reporting study — cannot be filed as documented"); continue
        seen.add(key)
        kept.append({
            "plant": plants[plant.strip().lower()],
            "fauna": animal,
            "relationship": rel,
            "source": _SOURCE_KEY,
            "notes": (c.get("notes") or "")[:300],
            "_new_fauna": animal.strip().lower() not in fauna,
            "_taxon": c.get("_taxon"),
        })
    return {"kept": kept, "rejected": rejected,
            "new_fauna": sorted({k["fauna"] for k in kept if k["_new_fauna"]})}


def _report(result: dict) -> None:
    kept = result["kept"]
    ready = [k for k in kept if not k["_new_fauna"]]
    print("=" * 64)
    print(f"  {len(kept)} edges survived every gate")
    print(f"    {len(ready)} ready now (animal already in fauna_master)")
    print(f"    {len(kept) - len(ready)} blocked on {len(result['new_fauna'])} "
          f"new animals")
    print(f"  {len({k['plant'] for k in ready})} plants would gain an edge")
    print("=" * 64)
    if result["rejected"]:
        print("\nrejected:")
        for reason, n in sorted(result["rejected"].items(),
                                key=lambda kv: -kv[1]):
            print(f"  {n:6d}  {reason}")
    by_rel: dict = {}
    for k in ready:
        by_rel[k["relationship"]] = by_rel.get(k["relationship"], 0) + 1
    if by_rel:
        print("\nready edges by relationship:")
        for rel, n in sorted(by_rel.items(), key=lambda kv: -kv[1]):
            print(f"  {n:6d}  {rel}")


def _apply(result: dict) -> None:
    """Write the ready edges into the seed file, and register the source.

    Only edges whose animal already exists are written. The rest wait for their
    fauna rows, which need a common name, a taxon and a nativity call — none of
    which an interaction record supplies, and all of which show up in the UI.
    """
    ready = [{k: v for k, v in e.items() if not k.startswith("_")}
             for e in result["kept"] if not e["_new_fauna"]]
    if not ready:
        print("nothing ready to write.")
        return

    path = os.path.join(_DATA, "plant_fauna_master.json")
    rows = _rows(path)
    rows.extend(ready)
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(rows, fh, indent=1, ensure_ascii=False)
    print(f"wrote {len(ready)} edges into {os.path.relpath(path, _ROOT)}")

    src_path = os.path.join(_DATA, "sources_master.json")
    if os.path.exists(src_path):
        with open(src_path, "r", encoding="utf-8") as fh:
            sources = json.load(fh)
        listish = sources if isinstance(sources, list) else None
        blob = json.dumps(sources)
        if _SOURCE_KEY not in blob:
            entry = {"key": _SOURCE_KEY, "citation": _SOURCE_TEXT}
            if listish is not None:
                sources.append(entry)
            else:
                sources[_SOURCE_KEY] = _SOURCE_TEXT
            with open(src_path, "w", encoding="utf-8") as fh:
                json.dump(sources, fh, indent=1, ensure_ascii=False)
            print(f"registered '{_SOURCE_KEY}' in sources_master.json")

    print("\nNEXT: bump _SCHEMA_VERSION in src/db/plants.py so existing "
          "installs reseed, then run the suite.")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--apply", action="store_true",
                    help="write the ready edges into the seed files")
    ap.add_argument("--file", default=os.path.join(
        _FETCHED, "fauna_edges_candidates.json"))
    args = ap.parse_args()

    if not os.path.exists(args.file):
        print(f"no candidate file at {args.file}\n"
              f"Run scripts/fetch_fauna_edges.py on a machine with internet "
              f"first.")
        return 1
    with open(args.file, "r", encoding="utf-8") as fh:
        candidates = json.load(fh)
    print(f"reviewing {len(candidates)} candidates from "
          f"{os.path.relpath(args.file, _ROOT)}\n")

    result = review(candidates)
    _report(result)
    if args.apply:
        print()
        _apply(result)
    else:
        print("\n(report only — re-run with --apply to write)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
