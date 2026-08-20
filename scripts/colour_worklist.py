#!/usr/bin/env python3
"""The flower-colour backlog, in the order worth working through (V2.51).

    python scripts/colour_worklist.py                 # ranked list, to read
    python scripts/colour_worklist.py --sheet out.html  # contact sheet, to check
    python scripts/colour_worklist.py --genus Solidago   # one genus
    python scripts/colour_worklist.py --paste            # ready for the seeder

WHY THIS EXISTS
-------------------------------------------------------------------------------
The author, after reading ``docs/DATA_GAPS.md``:

    "Colour data, how can I move this along. I read the data_gaps doc and
     wasn't sure what next steps to take."

Fair. The doc says 357 species still carry ``flower_colour_source='estimated'``
and stops there, which states a number and hands over no work. A backlog you
cannot start is the same as a backlog nobody started.

WHAT THIS ADDS
-------------------------------------------------------------------------------
Two things the number does not carry.

**An order.** Not all 357 are equally wrong. 81 are grasses, sedges and rushes,
which have no bloom colour to get wrong (see ``src/flower_colour.py``). Of the
276 that remain, the ones most likely to be wrong are the ones that inherited a
genus default *shared with siblings* — that is exactly the shape of the bug the
author found, where four columbines were all filed red because one of them is.
A genus where nine species carry one identical hex is nine chances to be wrong;
a species holding a hex alone was at least looked at once. So the ranking is
by how many siblings share the value.

**A way to check without being a botanist.** 199 of the 276 already have an
openly-licensed photograph in the catalogue. ``--sheet`` writes those out as a
contact sheet: the photo, the colour the catalogue currently claims, and the
bucket that claim lands in. Wrong ones are visible at a glance, in a way that
reading 276 hex codes is not. Mark them, and the fix is one line each in
``scripts/seed_flower_colour.py``.

WHAT IT DELIBERATELY DOES NOT DO
-------------------------------------------------------------------------------
Guess harder. Nothing here invents a colour, re-derives one from a name, or
promotes ``estimated`` to anything. It selects and it displays. A value only
stops being estimated when a person looks at it and says so, and that judgement
is recorded in the seeder where the reasoning lives beside it (P9).
"""

from __future__ import annotations

import argparse
import collections
import html
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))

from src.db import plants as plants_db                        # noqa: E402
from src.flower_colour import (COLOUR_LABELS,                  # noqa: E402
                               WIND_POLLINATED_TYPES, classify)


def _estimated() -> list[dict]:
    """Species whose flower colour is still a genus-level guess.

    Wind-pollinated families are excluded rather than listed as "to do": a
    grass has no showy flower, ``classify`` files it under straw whatever its
    hex says, and putting 81 of them at the top of a worklist would bury the
    276 rows where the answer can actually be wrong.
    """
    return [r for r in plants_db.get_all_plants()
            if (r.get("flower_colour_source") or "").strip() == "estimated"
            and (r.get("plant_type") or "") not in WIND_POLLINATED_TYPES]


def ranked(rows: list[dict]) -> list[tuple]:
    """``[(siblings, genus, hex, [row, ...]), ...]``, most-shared first.

    ``siblings`` is how many species in the same genus carry that identical
    hex. It is the risk score: one shared value is one decision that was made
    once and applied many times.
    """
    groups: dict = collections.defaultdict(list)
    for row in rows:
        genus = ((row.get("scientific_name") or "").split() or [""])[0]
        groups[(genus, (row.get("flower_color") or "").strip().lower())].append(row)
    out = [(len(v), g, h, sorted(v, key=lambda r: r.get("common_name") or ""))
           for (g, h), v in groups.items()]
    out.sort(key=lambda t: (-t[0], t[1]))
    return out


def _photo(row: dict) -> dict:
    from src.db import photos                                  # noqa: PLC0415
    try:
        return photos.best_photo(row.get("scientific_name") or "") or {}
    except Exception:                                          # noqa: BLE001
        return {}


def print_list(groups: list[tuple], limit: int = 0) -> None:
    shown = groups[:limit] if limit else groups
    for n, genus, hexval, rows in shown:
        bucket = classify(rows[0])
        label = COLOUR_LABELS.get(bucket, bucket or "unclassified")
        flag = "  <-- shared" if n >= 3 else ""
        print(f"\n{n:3d}  {genus:18s} {hexval:9s} {label}{flag}")
        for row in rows:
            mark = "photo" if _photo(row) else "  .  "
            print(f"       {mark}  {row.get('common_name', ''):38s} "
                  f"{row.get('scientific_name', '')}")


def print_paste(groups: list[tuple]) -> None:
    """Lines ready for ``seed_flower_colour.CORRECTIONS``, colour left blank.

    Deliberately unfilled. The whole failure this backlog exists to undo was a
    colour applied to a species nobody had looked at, and a script that
    pre-fills its own answer would repeat it one abstraction higher.
    """
    print("# paste into scripts/seed_flower_colour.py CORRECTIONS, then fill in")
    print("# the hex and the reason. Leave out any row you did not actually check.")
    for _n, _genus, _hexval, rows in groups:
        for row in rows:
            print(f'    "{row.get("scientific_name")}": '
                  f'("", "photo", "{row.get("common_name")}"),')


_SHEET_CSS = """
body { font: 15px/1.5 ui-sans-serif, system-ui, sans-serif; margin: 2rem auto;
       max-width: 76rem; padding: 0 1rem; background: #fbfaf7; color: #22241c; }
h1 { font-size: 1.6rem; } h2 { margin: 2.2rem 0 .6rem; font-size: 1.1rem; }
.note { color: #6f7264; max-width: 44rem; }
.grid { display: grid; gap: .9rem;
        grid-template-columns: repeat(auto-fill, minmax(11rem, 1fr)); }
.card { border: 1px solid #e2dfd4; border-radius: 10px; overflow: hidden;
        background: #fff; }
.card img { width: 100%; height: 8.5rem; object-fit: cover; display: block;
            background: #eeece4; }
.card .b { padding: .5rem .6rem .6rem; }
.nm { font-weight: 600; font-size: .88rem; }
.sci { color: #6f7264; font-size: .78rem; font-style: italic; }
.sw { display: inline-block; width: .8rem; height: .8rem; border-radius: 3px;
      vertical-align: -.1rem; margin-right: .3rem;
      box-shadow: inset 0 0 0 1px rgba(0,0,0,.2); }
.cl { font-size: .8rem; margin-top: .35rem; }
.nophoto { color: #8d9080; font-size: .8rem; padding: 2.6rem .6rem; }
"""


def write_sheet(groups: list[tuple], path: pathlib.Path) -> int:
    """A page of photographs with the claimed colour under each.

    Only species that already have a credited photograph in the catalogue: the
    point is to check a claim against an image, and a card with no image is a
    row to read, not a thing to check. Photos keep their credit, same rule as
    the website.
    """
    blocks, cards = [], 0
    for n, genus, hexval, rows in groups:
        with_photo = [(r, _photo(r)) for r in rows]
        with_photo = [(r, p) for r, p in with_photo if p.get("url")]
        if not with_photo:
            continue
        bucket = classify(rows[0])
        label = COLOUR_LABELS.get(bucket, bucket or "unclassified")
        items = []
        for row, photo in with_photo:
            cards += 1
            credit = html.escape(photo.get("credit") or photo.get("license") or "")
            items.append(
                f'<div class="card">'
                f'<img loading="lazy" src="{html.escape(photo["url"])}" '
                f'alt="{html.escape(row.get("common_name") or "")}">'
                f'<div class="b"><div class="nm">'
                f'{html.escape(row.get("common_name") or "")}</div>'
                f'<div class="sci">{html.escape(row.get("scientific_name") or "")}</div>'
                f'<div class="cl"><span class="sw" style="background:'
                f'{html.escape(hexval)}"></span>{html.escape(label)}</div>'
                f'<div class="sci">{credit}</div></div></div>')
        blocks.append(f'<h2>{html.escape(genus)} &mdash; {n} species share '
                      f'<code>{html.escape(hexval)}</code> ({html.escape(label)})'
                      f'</h2><div class="grid">{"".join(items)}</div>')

    path.write_text(
        f"<!doctype html><meta charset=utf-8><title>Flower colour to check</title>"
        f"<style>{_SHEET_CSS}</style>"
        f"<h1>Flower colour: {cards} claims to check</h1>"
        f'<p class="note">Every colour on this page is a <strong>genus-level '
        f'guess</strong>, not an observation. Grouped by how many species in '
        f'the genus share the same value, worst first, because that is the '
        f'shape of the bug that started this: four columbines were all filed '
        f'red because one of them is. Look at the photograph, look at the '
        f'swatch under it, and note the ones that disagree. Images are hotlinked '
        f'from their sources and each keeps its credit.</p>'
        f'{"".join(blocks)}', encoding="utf-8")
    return cards


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--sheet", metavar="PATH",
                    help="write a contact sheet of the photographed ones")
    ap.add_argument("--genus", help="restrict to one genus")
    ap.add_argument("--paste", action="store_true",
                    help="print blank CORRECTIONS lines for the seeder")
    ap.add_argument("--limit", type=int, default=0, help="show only the top N groups")
    args = ap.parse_args()

    rows = _estimated()
    groups = ranked(rows)
    if args.genus:
        want = args.genus.strip().lower()
        groups = [g for g in groups if g[1].lower() == want]
        if not groups:
            print(f"no estimated colours left in {args.genus}")
            return 0

    shared = sum(n for n, _g, _h, _r in groups if n >= 3)
    print(f"{len(rows)} species still carry a guessed flower colour "
          f"(grasses, sedges and rushes excluded: they have no bloom colour).")
    print(f"{shared} of them sit in a genus where 3 or more share one value, "
          f"across {sum(1 for n, *_ in groups if n >= 3)} such groups.")

    if args.paste:
        print()
        print_paste(groups)
        return 0
    if args.sheet:
        out = pathlib.Path(args.sheet)
        cards = write_sheet(groups, out)
        print(f"\nwrote {out} — {cards} species with a photograph to check "
              f"against.\nOpen it, note the ones where the swatch and the "
              f"flower disagree, and add each to CORRECTIONS in "
              f"scripts/seed_flower_colour.py.")
        return 0

    print_list(groups, args.limit)
    print(f"\n--sheet out.html turns the photographed ones into a page you can "
          f"check by eye.\n--genus Solidago narrows to one. --paste emits blank "
          f"seeder lines.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
