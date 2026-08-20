#!/usr/bin/env python3
"""
scripts/reconcile_use_tags.py — give the score the data the app already holds
(F120).

    python3 scripts/reconcile_use_tags.py            # report only
    python3 scripts/reconcile_use_tags.py --apply    # write the seed files

The Habitat Value Score's host and bird-food components read **use tags**.
The relationship data is in **edges**. Nothing kept the two in agreement, so
the app has been holding a sourced `larval_host` record for Chokecherry while
`design_critic` told the user their chokecherry planting has *"no
butterfly/moth host plants — without host plants there are no caterpillars."*

V2.53 measured that contradiction (48 species) and deliberately did not fix
it, because correcting the tags moves every affected design's Habitat Value
Score and the stability rule makes that a decision rather than a side effect.
This is that decision, taken. By V2.65 the count is 117.

**Additive only, and that is a rule rather than a shortcut.** A missing tag
next to a cited edge is a contradiction: the app holds a record it is not
counting. A tag with no edge behind it is *not* the mirror image of that —
absence of an edge is absence of evidence, not evidence of absence, and the
catalogue's edges cover a fraction of what is real. Removing `bird_food` from
a species because GloBI has no record for it would delete a human's judgement
on the strength of a gap. Same reasoning that makes an establishment band come
back `unknown` rather than `unlikely` below the occurrence floor (P9).

So this only ever adds, every addition is backed by a sourced edge, and the
report says which edge did it.
"""

from __future__ import annotations

import argparse
import json
import os
import sys

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, _ROOT)
_DATA = os.path.join(_ROOT, "data")
_CATALOGUES = ("plants_master.json", "garden_plants.json")


def _rows(path: str) -> list:
    with open(path, "r", encoding="utf-8") as fh:
        return json.load(fh)


def _indent_of(path: str) -> int:
    """How deeply this file indents, so rewriting it does not reformat it.

    The seed files disagree: `plant_fauna_master.json` is written at 1 and the
    two catalogues at 2. Writing the catalogues back at 1 turns an 80-line
    correction into a 27,495-line diff that no one can review — which is
    exactly what the first run of this script did.
    """
    with open(path, "r", encoding="utf-8") as fh:
        for line in fh:
            stripped = line.lstrip(" ")
            if stripped and stripped != line and stripped.startswith(("{", "\"")):
                return len(line) - len(stripped)
    return 1


def _tag_map() -> dict:
    """``{use tag: (relationships, required animal taxon)}`` — imported, not
    restated.

    `data_quality` owns this table because it owns the warning. If the fixer
    kept its own copy the two would drift, and the gate would go quiet while
    the thing it measures went unfixed — or, worse, keep warning about species
    the fixer has decided not to touch, which is a warning that can never
    reach zero and therefore stops being read.
    """
    from src.data_quality import _TAG_BACKED_BY_EDGE
    return dict(_TAG_BACKED_BY_EDGE)


def reconcile(write: bool = False) -> dict:
    """Add every use tag a sourced edge already justifies."""
    tag_map = _tag_map()
    # (file, index) → row, plus the same name resolution `use_tags_vs_edges`
    # does, so the fixer and the gate cannot disagree about which plant an
    # edge names. First match wins there; first match wins here.
    loaded = {name: _rows(os.path.join(_DATA, name)) for name in _CATALOGUES}
    by_name: dict = {}
    for name, rows in loaded.items():
        for i, r in enumerate(rows):
            if not isinstance(r, dict) or not r.get("scientific_name"):
                continue
            for field in ("common_name", "scientific_name"):
                key = (r.get(field) or "").strip().lower()
                if key:
                    by_name.setdefault(key, (name, i))

    edges = [e for e in _rows(os.path.join(_DATA, "plant_fauna_master.json"))
             if isinstance(e, dict) and e.get("relationship")]
    taxon_of = {r["scientific_name"]: (r.get("taxon") or "")
                for r in _rows(os.path.join(_DATA, "fauna_master.json"))
                if isinstance(r, dict) and r.get("scientific_name")}

    # target → the tags it needs, and one example edge per tag as the receipt
    needed: dict = {}
    unsourced = 0
    wrong_taxon = 0
    unmatched = set()
    for e in edges:
        plant = (e.get("plant") or "").strip()
        target = by_name.get(plant.lower())
        if target is None:
            unmatched.add(plant)
            continue
        if not (e.get("source") or "").strip():
            unsourced += 1          # an uncited edge cannot justify anything
            continue
        row = loaded[target[0]][target[1]]
        tags = {t.strip() for t in
                (row.get("permaculture_uses") or "").split(",") if t.strip()}
        rel = (e.get("relationship") or "").strip()
        taxon = taxon_of.get((e.get("fauna") or "").strip(), "")
        for tag, (rels, want) in tag_map.items():
            if rel not in rels or tag in tags:
                continue
            if taxon != want:
                # A gall midge on a hawthorn is a real larval host and not a
                # caterpillar; a deer mouse eating grama seed is not bird food.
                wrong_taxon += 1
                continue
            needed.setdefault(target, {}).setdefault(
                tag, (e.get("fauna"), rel, e.get("source")))

    per_tag: dict = {}
    for target, tags in needed.items():
        for tag in tags:
            per_tag.setdefault(tag, []).append(
                loaded[target[0]][target[1]].get("common_name") or "?")

    print("=" * 68)
    for tag in sorted(per_tag):
        rels, want = tag_map[tag]
        print(f"  {len(per_tag[tag]):>4}  species carry a sourced "
              f"{' / '.join(rels)} edge to a {want} and no {tag!r} tag")
    print(f"  {len(needed):>4}  species affected in total")
    print("=" * 68)
    for tag in sorted(per_tag):
        print(f"\n{tag} — the first 12 and the edge that justifies each:")
        shown = [t for t in sorted(needed, key=lambda k: loaded[k[0]][k[1]]
                                   .get("common_name") or "") if tag in needed[t]]
        for target in shown[:12]:
            row = loaded[target[0]][target[1]]
            fauna, rel, src = needed[target][tag]
            print(f"    {(row.get('common_name') or '?'):<26} "
                  f"{rel:<11} {fauna}  [{src}]")
        if len(shown) > 12:
            print(f"    … and {len(shown) - 12} more")
    if unsourced:
        print(f"\n{unsourced} edge(s) carry no source and justified nothing.")
    if wrong_taxon:
        print(f"{wrong_taxon} edge(s) had the right relationship but the "
              f"wrong animal for the tag, and justified nothing.")
    if unmatched:
        print(f"{len(unmatched)} edge plant name(s) matched no catalogue row.")

    if not write:
        print("\n(report only — re-run with --apply to write)")
        return {"needed": needed, "per_tag": per_tag}

    touched = set()
    for target, tags in needed.items():
        row = loaded[target[0]][target[1]]
        current = [t.strip() for t in
                   (row.get("permaculture_uses") or "").split(",") if t.strip()]
        merged = current + [t for t in sorted(tags) if t not in current]
        # Keep alphabetical where it already was — 424 of 436 rows are sorted,
        # so appending blindly would break the convention far more often than
        # it preserved it. Where a row is NOT sorted, leave the existing order
        # alone and append: reordering it would be a diff about nothing.
        if current == sorted(current):
            merged = sorted(merged)
        row["permaculture_uses"] = ",".join(merged)
        touched.add(target[0])

    for name in sorted(touched):
        path = os.path.join(_DATA, name)
        # Measured BEFORE the open-for-write, which truncates: reading the
        # file's own format out of the empty file it has just become returns
        # the fallback, and that is how the first fix for this still produced
        # a 27,493-line diff.
        indent = _indent_of(path)
        with open(path, "w", encoding="utf-8") as fh:
            json.dump(loaded[name], fh, indent=indent, ensure_ascii=False)
            fh.write("\n")
        print(f"\nwrote {os.path.relpath(path, _ROOT)}")
    print("\nNEXT: bump _SCHEMA_VERSION in src/db/plants.py so existing "
          "installs reseed, then run the suite.")
    return {"needed": needed, "per_tag": per_tag}


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--apply", action="store_true",
                    help="write the corrected tags into the seed catalogues")
    args = ap.parse_args()
    reconcile(write=args.apply)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
