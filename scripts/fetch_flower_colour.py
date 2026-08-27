#!/usr/bin/env python3
"""
scripts/fetch_flower_colour.py — a source for the colour we are guessing.

    python scripts/fetch_flower_colour.py --columns <file>     # what is in it?
    python scripts/fetch_flower_colour.py --from-file <file>   # read it
    python scripts/fetch_flower_colour.py                      # what to download

The problem, in one number
--------------------------
**350 of 430 flower colours in this catalogue are a genus default.** They carry
``flower_colour_source = "estimated"`` and every page says *not verified*, which
is honest and is not the same as being right. The author found it the way
anybody would:

    "I am looking at the plains prickly pear cactus which says it has a yellow
     flower whereas the picture on the page clearly shows a pink flower."

*Opuntia polyacantha* is ``#f2c11e``, inherited from the genus. The photograph
above it is magenta.

Why this script will not download anything
------------------------------------------
The same rule ``vascan_archive.py`` and ``tools/ecoregions/fetch.py`` follow,
and it has already been earned twice this month: **a URL asserted from memory
that fetches the wrong dataset and parses successfully is the failure hardest
to notice.** This project's sessions cannot reach the candidate sources to
check one, so the download is yours and the parsing is this script's.

``--columns`` exists because of the other half of that lesson. V2.79's archive
reader was verified against a fixture that shared the reader's assumption about
a column name, so nine tests passed against code that could not open the real
file. **Run ``--columns`` first, on the real download, and read what it says
before anything parses it.**

Candidate sources, best first, none of them verified from here
--------------------------------------------------------------
1. **USDA PLANTS** publishes a per-species characteristics export that includes
   a *Flower Color* field. Structured, public domain, no OCR. Most of this
   catalogue's species range south of the border, so coverage should be good
   but is unmeasured. Start here: if it covers 250 of the 350, the remainder is
   an evening rather than a winter.
2. **Budd's Flora of the Canadian Prairie Provinces** (Agriculture Canada
   publication 1662) is the right authority for exactly this ground, and it is
   a scanned book. Reading colour out of it means OCR or a person.
3. **The photographs already in the catalogue** (319 species with a credited
   image). Sampling the dominant non-foliage hue is tempting and is a different
   claim: it would say *this photograph is pink*, not *this species has pink
   flowers*, and one photograph of one plant in one light is not a flora.

Whatever the source, it lands in ``flower_colour_source`` as a new value beside
``name``/``epithet``/``estimated``, so a page can say where the colour came
from. Nothing is overwritten silently.
"""

from __future__ import annotations

import argparse
import csv
import io
import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

OUTPUT_PATH = PROJECT_ROOT / "data" / "fetched" / "flower_colour.json"

HINT = """No file given, and this script will not guess a download URL.

Candidates, best first:

  1. USDA PLANTS  https://plants.usda.gov/
     Look for the characteristics or "Advanced Search" export. You want a file
     with a scientific name column and a Flower Color column. Save it anywhere.

  2. Budd's Flora of the Canadian Prairie Provinces (Agriculture Canada 1662),
     if you would rather use the regional authority. It is a scanned book, so
     this route needs OCR or a person reading it.

Then:

    python scripts/fetch_flower_colour.py --columns <the file>

which prints its header and three sample rows and PARSES NOTHING. Read that,
send it back, and the reader gets written for the shape the file actually has
rather than the shape somebody assumed."""


def _header_index(rows: list) -> int:
    """Which row is the real header.

    USDA PLANTS puts a preamble line above it -- a real export opened with
    ``--columns`` began ``Search Type: Characteristic`` and the column names
    were on line 2. Taking row 0 on faith reported *1 column* for a four-column
    file, which is the same species of mistake ``--columns`` exists to catch, so
    it should not be the probe making it.

    The header is the first row that is as wide as the file generally is. Width
    is taken as the **mode** rather than the maximum, because one ragged row
    with a stray delimiter should not redefine the shape of the file.
    """
    widths = {}
    for row in rows[:200]:
        widths[len(row)] = widths.get(len(row), 0) + 1
    if not widths:
        return 0
    modal = max(widths, key=lambda w: (widths[w], w))
    for i, row in enumerate(rows[:200]):
        if len(row) == modal:
            return i
    return 0


def _rows(path: Path):
    """Header + rows from a csv/tsv, whichever it turns out to be."""
    text = path.read_text(encoding="utf-8", errors="replace")
    # Sniffed rather than assumed: a "csv" export that is tab-separated is
    # common enough, and getting it wrong yields one enormous column that
    # still parses.
    delim = "\t" if text.count("\t") > text.count(",") else ","
    reader = csv.reader(io.StringIO(text), delimiter=delim)
    rows = [r for r in reader if r]
    if not rows:
        raise SystemExit(f"{path} has no rows.")
    head = _header_index(rows)
    if head:
        print(f"(skipped {head} preamble line(s) above the header: "
              f"{' | '.join(c[:30] for c in rows[0])})\n")
    return rows[head], rows[head + 1:], delim


def columns(path: Path) -> int:
    """Print what is in the file. Parse nothing, decide nothing."""
    header, rows, delim = _rows(path)
    print(f"{path.name}: {len(rows):,} rows, "
          f"{'tab' if delim == chr(9) else 'comma'}-separated, "
          f"{len(header)} columns\n")
    print("columns:")
    for i, name in enumerate(header):
        sample = next((r[i] for r in rows[:200]
                       if i < len(r) and r[i].strip()), "")
        print(f"  {i:3d}  {name[:44]:44s}  e.g. {sample[:36]!r}")
    print("\nfirst three rows:")
    for row in rows[:3]:
        print("  " + " | ".join(c[:24] for c in row[:8]))

    # Say outright whether this file can answer the question, rather than
    # leaving it to be inferred from a column listing. The first real USDA
    # export was a name list with no colour in it, and that is easy to miss.
    name_col = next((c for c in header
                     if "scientificname" in c.lower().replace(" ", "")
                     or c.lower() in ("scientific name", "taxon", "species")), "")
    colour_col = next((c for c in header
                       if "color" in c.lower() or "colour" in c.lower()), "")
    print("\n--- can this file answer the question? ---")
    print(f"  scientific name column: {name_col or 'NOT FOUND'}")
    print(f"  flower colour column:   {colour_col or 'NOT FOUND'}")
    if name_col and colour_col:
        print("\nBoth present. Send this output back and the reader gets "
              "written for it.")
    else:
        print("\nThis export cannot be used as-is. In the USDA PLANTS "
              "advanced search the\ncharacteristics fields are opt-in: tick "
              "Flower Color before exporting, or the\nfile comes back as a "
              "name list. Re-export and run --columns again.")
    return 0


def catalogue_needing_colour() -> dict:
    """``{scientific_name: current hex}`` for every guessed colour."""
    out = {}
    for name in ("plants_master.json", "garden_plants.json"):
        try:
            rows = json.loads(
                (PROJECT_ROOT / "data" / name).read_text(encoding="utf-8"))
        except (FileNotFoundError, json.JSONDecodeError):
            continue
        for row in rows:
            if not isinstance(row, dict):
                continue
            if (row.get("flower_colour_source") or "") == "estimated":
                out[row.get("scientific_name", "")] = row.get("flower_color", "")
    out.pop("", None)
    return out


def main(argv=None) -> int:
    p = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--columns", metavar="FILE",
                   help="print the file's header and samples; parse nothing")
    p.add_argument("--from-file", metavar="FILE", dest="from_file",
                   help="read colours from a downloaded source file")
    p.add_argument("--needing", action="store_true",
                   help="list the species whose colour is a genus default")
    args = p.parse_args(argv)

    if args.needing:
        need = catalogue_needing_colour()
        print(f"{len(need)} species carry an estimated flower colour:\n")
        for sci, hex_ in sorted(need.items()):
            print(f"  {sci:38s} {hex_}")
        return 0

    if args.columns:
        path = Path(args.columns)
        if not path.exists():
            print(f"No file at {path}.\n\n{HINT}", file=sys.stderr)
            return 1
        return columns(path)

    if args.from_file:
        print("The reader is not written yet, on purpose: it needs the real\n"
              "column names. Run --columns on this file first and send the\n"
              "output back.\n", file=sys.stderr)
        return 2

    print(HINT)
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
