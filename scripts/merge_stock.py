#!/usr/bin/env python3
"""
scripts/merge_stock.py — bring a nursery's stock into a region pack (V3.25).

The availability levels come from ``data/regions/<key>/stock.json``
(``src/local_stock.py``). Two ways in, both checked before anything is written:

**A list a nursery published**, saved as text (copied from its website, its
availability PDF, a flyer):

    python scripts/merge_stock.py --list arnica_2026.txt \\
        --supplier "Arnica Wildflowers" --seen 2026-05
    python scripts/merge_stock.py --list ... --write    # the same, saved

Without ``--write`` it only reports: the plants it found on Edmonton's list,
the ones it found that are not (kept in the list, never ranked), and every
line it could not read, which is where a misspelling or an unfamiliar name
shows up. ``--form seed`` for a seed list. ``--source`` says where the list
came from ("website, 12 May 2026"); it defaults to the file's name.

**The review page's answers** (``tools/stock_review``): its export file, or a
directory of its database rows (collections ``lists`` and ``rulings``):

    python scripts/merge_stock.py --merge <file or directory> [--write]

A ``lists`` row carries the pasted text, which is read here again by
``src/stock_lists.match`` (the page's own matching is only a preview). A
``rulings`` row is ``{"scientific_name", "tier", "on"}``; an empty tier takes
an answer back. Only a tier and a date are kept, never a reason.

Run from the project root. Read from file, not seeded: no schema bump.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_ROOT))

CATALOGUE = _ROOT / "data" / "plants_master.json"


def _load(path: Path):
    with open(path, encoding="utf-8") as fh:
        return json.load(fh)


def _catalogue() -> list:
    return _load(CATALOGUE)


def read_list(text: str, supplier: str, seen: str, form: str = "plants",
              source: str = "") -> tuple:
    """``(list row, unread lines)`` from a nursery's text."""
    from src import stock_lists
    found, unread = stock_lists.match(text, stock_lists.name_table(_catalogue()))
    row = {"supplier": supplier, "seen": seen, "form": form,
           "source": source, "species": found}
    return row, unread


def read_review(path: Path) -> dict:
    """``{"lists": [...], "rulings": {name: {"tier", "on"}}}`` from the review
    page's export file, or a directory of its rows (``lists/`` and
    ``rulings/`` folders, or rows of both kinds in one folder)."""
    path = Path(path)
    if not path.is_dir():
        doc = _load(path)
        return {"lists": list(doc.get("lists") or []),
                "rulings": dict(doc.get("rulings") or {})}
    out = {"lists": [], "rulings": {}}
    for f in sorted(path.rglob("*.json")):
        row = _load(f)
        if not isinstance(row, dict):
            raise ValueError(f"{f.name}: not a row")
        if "text" in row or "species" in row:
            out["lists"].append(row)
        elif row.get("scientific_name"):
            out["rulings"][row["scientific_name"]] = {
                k: row[k] for k in ("tier", "on") if k in row}
        else:
            raise ValueError(f"{f.name}: neither a list nor a ruling")
    return out


def merge(doc: dict, review: dict) -> tuple:
    """``(new doc, report lines)``. Lists are added (a list already on file,
    the same supplier, date and form, is replaced); rulings replace a
    species' answer, and an empty tier removes it."""
    new = json.loads(json.dumps(doc))
    lists = new.setdefault("lists", [])
    rulings = new.setdefault("rulings", {})
    report = []
    for row in review.get("lists") or []:
        if row.get("removed"):
            gone = (row.get("supplier"), row.get("seen"), row.get("form", "plants"))
            lists[:] = [l for l in lists if (l.get("supplier"), l.get("seen"),
                                             l.get("form", "plants")) != gone]
            report.append(f"list removed: {gone[0]} {gone[1]} ({gone[2]})")
            continue
        if "text" in row:
            row, unread = read_list(row.get("text") or "", row.get("supplier", ""),
                                    row.get("seen", ""), row.get("form", "plants"),
                                    row.get("source", "") or "review page")
            report += [f"  could not read: {u}" for u in unread]
        row = {k: row[k] for k in ("supplier", "seen", "form", "source",
                                   "species") if k in row}
        same = (row.get("supplier"), row.get("seen"), row.get("form", "plants"))
        lists[:] = [l for l in lists if (l.get("supplier"), l.get("seen"),
                                         l.get("form", "plants")) != same]
        lists.append(row)
        report.append(f"list: {row.get('supplier')} {row.get('seen')} "
                      f"({row.get('form', 'plants')}): "
                      f"{len(row.get('species') or [])} plants")
    for name, r in sorted((review.get("rulings") or {}).items()):
        tier = (r or {}).get("tier") or ""
        if not tier:
            if rulings.pop(name, None) is not None:
                report.append(f"answer taken back: {name}")
            continue
        rulings[name] = {"tier": tier, "on": (r or {}).get("on", "")}
        report.append(f"answer: {name} -> {tier}")
    lists.sort(key=lambda l: (l.get("supplier") or "", l.get("seen") or ""))
    new["rulings"] = dict(sorted(rulings.items()))
    return new, report


def check(doc: dict, key: str) -> list:
    from src import local_stock, region
    names = {r["scientific_name"] for r in _catalogue()}
    return local_stock.validate(doc, region.regions()[key].nurseries, names)


def _write(path: str, doc: dict) -> None:
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(doc, fh, ensure_ascii=False, indent=2)
        fh.write("\n")


def main(argv=None) -> int:
    from src import local_stock, native_here, region
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    way = ap.add_mutually_exclusive_group(required=True)
    way.add_argument("--list", metavar="FILE", help="a nursery's list, as text")
    way.add_argument("--merge", metavar="PATH", help="the review page's answers")
    ap.add_argument("--supplier", help="one of the pack's nurseries")
    ap.add_argument("--seen", help="when the list was current, e.g. 2026-05")
    ap.add_argument("--form", default="plants", choices=local_stock.FORMS)
    ap.add_argument("--source", default="")
    ap.add_argument("--region", default="", help="the pack (default: the edition's)")
    ap.add_argument("--write", action="store_true", help="save the result")
    args = ap.parse_args(argv)

    key = args.region or region.default().key
    path = local_stock.path(key)
    doc = _load(Path(path))
    if args.list:
        if not (args.supplier and args.seen):
            ap.error("--list needs --supplier and --seen")
        text = Path(args.list).read_text(encoding="utf-8")
        row, unread = read_list(text, args.supplier, args.seen, args.form,
                                args.source or os.path.basename(args.list))
        local = native_here.native_names(key)
        here = [n for n in row["species"] if n in local]
        away = [n for n in row["species"] if n not in local]
        print(f"{len(row['species'])} plants found: {len(here)} on the "
              f"{region.regions()[key].short} list, {len(away)} not (kept, "
              "never ranked).")
        for n in away:
            print(f"  not on the list: {n}")
        for u in unread:
            print(f"  could not read: {u}")
        review = {"lists": [row]}
    else:
        review = read_review(Path(args.merge))
    new, report = merge(doc, review)
    print("\n".join(report))
    errs = check(new, key)
    if errs:
        print("Nothing written:\n  " + "\n  ".join(errs))
        return 1
    if not args.write:
        print("(a dry run: add --write to save)")
        return 0
    _write(path, new)
    local_stock.set_document(None)
    print(f"Wrote {os.path.relpath(path, _ROOT)}. Tiers now: "
          f"{local_stock.counts(key)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
