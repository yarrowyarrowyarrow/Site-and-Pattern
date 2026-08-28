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


REVIEW_PATH = PROJECT_ROOT / "data" / "fetched" / "flower_colour_review.tsv"
MISSES_PATH = PROJECT_ROOT / "data" / "fetched" / "flower_colour_misses.tsv"


def budds_review(text_path: Path) -> int:
    """Turn a flora's prose into a spreadsheet somebody can check in an evening.

    The review file is the whole point. Nothing here is trusted enough to write
    unseen -- it is OCR of a 1979 scan, read by a parser guessing at English --
    but **every row carries the book's own sentence**, so checking one costs
    reading a quote rather than looking a species up. Uncertain rows sort to
    the top, because those are the ones that need a person.
    """
    from src.budds_colour import blocks, read
    from src.flower_colour import COLOUR_SWATCHES

    need = catalogue_needing_colour()
    common = catalogue_common_names()
    findings = read(text_path.read_text(encoding="utf-8", errors="replace"),
                    list(need), common)
    REVIEW_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(REVIEW_PATH, "w", encoding="utf-8", newline="") as fh:
        out = csv.writer(fh, delimiter="\t")
        out.writerow(["scientific_name", "colour", "check", "matched_on",
                      "was", "what the flora says"])
        for f in sorted(findings, key=lambda x: (x.found_as == "name",
                                                 x.scientific_name)):
            out.writerow([f.scientific_name, ",".join(f.buckets),
                          "" if f.found_as == "name" else "CHECK",
                          f.found_as,
                          need.get(f.scientific_name, ""), f.quote])

    # "Not found" was hiding two different problems, and which one dominates
    # decides what is worth fixing. A species the book does not carry is a
    # nomenclature or coverage problem; a species whose description carries no
    # colour word is the genus problem, where a flora states the obvious once
    # at the genus and then notes only departures from it.
    located = blocks(text_path.read_text(encoding="utf-8", errors="replace"),
                     list(need), common)
    got = {f.scientific_name for f in findings}
    silent = sorted(set(located) - got)
    absent = sorted(set(need) - set(located))

    with open(MISSES_PATH, "w", encoding="utf-8", newline="") as fh:
        out = csv.writer(fh, delimiter="\t")
        out.writerow(["scientific_name", "why", "common_name"])
        for name in silent:
            out.writerow([name, "described, but no flower colour stated",
                          common.get(name, "")])
        for name in absent:
            out.writerow([name, "not in this book under either name",
                          common.get(name, "")])

    unsure = [f for f in findings if f.found_as != "name"]
    print(f"{len(need)} species carry a guessed colour")
    print(f"  {len(findings):4d} found with a colour")
    multi = [f for f in findings if len(f.buckets) > 1]
    print(f"  {len(multi):4d} of those bloom in more than one colour, "
          f"kept as a range")
    print(f"  {len(unsure):4d} need a look (matched on common name, not "
          f"binomial)")
    print(f"  {len(silent):4d} described in the book, but it states no flower "
          f"colour for them")
    print(f"  {len(absent):4d} not in this book under either name\n")
    print(f"Written to {REVIEW_PATH}")
    print(f"        and {MISSES_PATH}")
    print("\nOpen it in a spreadsheet. One column to edit -- 'colour' -- and\n"
          "the flora's sentence is on the same row, so a CHECK row is decided\n"
          "by reading it. Valid values:\n  "
          + ", ".join(sorted(COLOUR_SWATCHES)))
    print(f"\nThen: python {Path(__file__).name} --from-review "
          f"{REVIEW_PATH.name} --apply")
    return 0


def apply_review(path: Path, write: bool) -> int:
    """Write the colours back, after a person has been over them."""
    from src.flower_colour import COLOUR_SWATCHES

    rows = list(csv.DictReader(path.read_text(encoding="utf-8").splitlines(),
                               delimiter="\t"))
    # A row may name a range -- "white,pink" -- because a flora describes one.
    # The first is the primary hex; the whole list is what the filter reads.
    wanted, bad = {}, []
    for row in rows:
        name = (row.get("scientific_name") or "").strip()
        listed = [c.strip().lower()
                  for c in (row.get("colour") or "").split(",") if c.strip()]
        if not name or not listed:
            continue
        unknown = [c for c in listed if c not in COLOUR_SWATCHES]
        if unknown:
            bad.append(f"{name}: {', '.join(repr(u) for u in unknown)}")
            continue
        seen, keys = set(), []
        for key in listed:
            if key not in seen:
                seen.add(key)
                keys.append(key)
        wanted[name] = keys

    if bad:
        print(f"{len(bad)} row(s) name a colour this catalogue does not have. "
              f"Nothing written.\n", file=sys.stderr)
        for b in bad[:15]:
            print(f"      {b}", file=sys.stderr)
        print(f"\nValid: {', '.join(sorted(COLOUR_SWATCHES))}", file=sys.stderr)
        return 1

    still_check = sum(1 for r in rows if (r.get("check") or "").strip())
    print(f"{len(wanted)} colours ready to write")
    if still_check:
        print(f"  {still_check} row(s) still marked CHECK -- they will be "
              f"written as they stand")
    if not write:
        print("\n(report only. Add --apply to write.)")
        return 0

    changed = 0
    for name in ("plants_master.json", "garden_plants.json"):
        path_j = PROJECT_ROOT / "data" / name
        try:
            data = json.loads(path_j.read_text(encoding="utf-8"))
        except (FileNotFoundError, json.JSONDecodeError):
            continue
        for row in data:
            if not isinstance(row, dict):
                continue
            keys = wanted.get(row.get("scientific_name", ""))
            if not keys:
                continue
            # The primary hex stays a single colour, because the 3D viewer and
            # every swatch draw one. The list is the whole answer.
            row["flower_color"] = COLOUR_SWATCHES[keys[0]]
            row["flower_colours"] = ",".join(keys)
            # "flora" -- the mark src.confidence already defines as "read
            # from a published flora", inferred=False. NOT "budds": an
            # unknown mark comes back recorded=False and labelled "not
            # recorded", which would have printed the opposite of the truth on
            # every page whose colour had just been sourced.
            row["flower_colour_source"] = "flora"
            changed += 1
        path_j.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n",
                          encoding="utf-8")
    ranges = sum(1 for k in wanted.values() if len(k) > 1)
    print(f"\nWrote {changed} colours as flower_colour_source='flora', "
          f"{ranges} of them a range.")
    print("Now: bump _SCHEMA_VERSION, then validate-data, then the suite.")
    return 0


def _canonical(name: str) -> str:
    """A USDA scientific name reduced to the binomial this catalogue keys on.

    USDA ships the authority (``Abies amabilis (Douglas ex Loudon) Douglas ex
    Forbes``) and marks hybrids (``Abelia xgrandiflora``). Taking the first two
    tokens is enough and is what ``vascan_archive`` does for the same reason:
    an authority is not part of the name for matching purposes, and matching on
    the full string would miss nearly everything.
    """
    text = (name or "").replace("×", "x").strip()
    parts = [p for p in text.split() if p]
    if len(parts) < 2:
        return text.lower()
    return f"{parts[0]} {parts[1]}".lower()


def read_colour_sets(folder: Path) -> dict:
    """``{binomial: [colour_key, ...]}`` from one CSV per colour.

    Each file is named for the colour it holds -- ``blue.csv``, ``yellow.csv``
    -- because USDA's export carries no characteristics column, so the *filter*
    is the only thing that knows the answer. One download per colour turns that
    filter into a label the file itself carries.
    """
    from src.flower_colour import COLOUR_KEYS

    out: dict = {}
    files = sorted(p for p in folder.iterdir()
                   if p.suffix.lower() in (".csv", ".tsv", ".txt"))
    if not files:
        raise SystemExit(f"No csv files in {folder}.")
    for path in files:
        colour = path.stem.strip().lower()
        if colour not in COLOUR_KEYS:
            raise SystemExit(
                f"{path.name}: '{colour}' is not one of this catalogue's "
                f"colours ({', '.join(COLOUR_KEYS)}). Name each file for the "
                f"colour it holds.")
        header, rows, _d = _rows(path)
        col = next((i for i, c in enumerate(header)
                    if "scientificname" in c.lower().replace(" ", "")), None)
        if col is None:
            raise SystemExit(f"{path.name} has no scientificName column.")
        seen = set()
        for row in rows:
            if col >= len(row):
                continue
            key = _canonical(row[col])
            if key and key not in seen:
                seen.add(key)
                out.setdefault(key, []).append(colour)
        print(f"  {path.name:14s} {len(seen):5d} species -> {colour}")
    return out


def apply_colour_sets(folder: Path, write: bool) -> int:
    """Match the downloaded colours against the species we are guessing at."""
    from src.flower_colour import COLOUR_SWATCHES

    usda = read_colour_sets(folder)
    need = catalogue_needing_colour()
    common = catalogue_common_names()
    by_canon = {_canonical(sci): sci for sci in need}

    hits, multi, missing = {}, {}, []
    for canon, sci in by_canon.items():
        colours = usda.get(canon)
        if not colours:
            missing.append(sci)
        elif len(colours) > 1:
            multi[sci] = colours
        else:
            hits[sci] = colours[0]

    print(f"\n{len(need)} species carry a guessed colour")
    print(f"  {len(hits):4d} matched to exactly one USDA colour")
    print(f"  {len(multi):4d} matched to more than one (not written)")
    print(f"  {len(missing):4d} not in the USDA set at all")

    if multi:
        print("\nMore than one colour recorded -- these need a person, because "
              "the\ncatalogue stores one hex and USDA is recording real "
              "variation:")
        for sci, colours in sorted(multi.items())[:12]:
            print(f"      {sci:38s} {', '.join(colours)}")
        if len(multi) > 12:
            print(f"      ... and {len(multi) - 12} more")

    if not write:
        print("\n(report only. Add --apply to write these into the seed data.)")
        return 0

    changed = 0
    for name in ("plants_master.json", "garden_plants.json"):
        path = PROJECT_ROOT / "data" / name
        try:
            rows = json.loads(path.read_text(encoding="utf-8"))
        except (FileNotFoundError, json.JSONDecodeError):
            continue
        for row in rows:
            if not isinstance(row, dict):
                continue
            colour = hits.get(row.get("scientific_name", ""))
            if not colour:
                continue
            row["flower_color"] = COLOUR_SWATCHES[colour]
            # A new provenance value beside name/epithet/estimated, so a page
            # can say a flora recorded this rather than a genus implied it.
            row["flower_colour_source"] = "usda"
            changed += 1
        path.write_text(json.dumps(rows, indent=2, ensure_ascii=False) + "\n",
                        encoding="utf-8")
    print(f"\nWrote {changed} colours as flower_colour_source='usda'.")
    print("Now: bump _SCHEMA_VERSION, then validate-data, then the suite.")
    return 0


def catalogue_common_names() -> dict:
    """``{scientific_name: common_name}``, the fallback key for a 1979 flora
    that does not use 2026 nomenclature."""
    out = {}
    for name in ("plants_master.json", "garden_plants.json"):
        try:
            rows = json.loads(
                (PROJECT_ROOT / "data" / name).read_text(encoding="utf-8"))
        except (FileNotFoundError, json.JSONDecodeError):
            continue
        for row in rows:
            if isinstance(row, dict) and row.get("scientific_name"):
                out[row["scientific_name"]] = row.get("common_name") or ""
    return out


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
    p.add_argument("--colour-sets", metavar="FOLDER", dest="colour_sets",
                   help="folder of one CSV per colour, each named for the "
                        "colour it holds (blue.csv, yellow.csv, ...). Reports "
                        "coverage; writes nothing without --apply")
    p.add_argument("--peek", metavar="FILE",
                   help="look at extracted flora text before parsing it: "
                        "counts, a sample, and a warning if a PDF came out "
                        "empty because it is a scan with no text layer")
    p.add_argument("--peek-species", nargs="+", metavar="FILE|NAME",
                   dest="peek_species",
                   help="FILE then optional species names: print the raw block "
                        "found for each, to see OCR quality on real text and "
                        "whether species headings survived as lines")
    p.add_argument("--peek-genus", nargs="+", metavar="FILE|GENUS",
                   dest="peek_genus",
                   help="FILE then optional genus names: show how the book "
                        "writes a GENUS heading, which is what reading the "
                        "genus colour needs")
    p.add_argument("--from-budds", metavar="FILE", dest="from_budds",
                   help="read Budd's Flora (as plain text) and write a review "
                        "spreadsheet: one proposed colour per species, with "
                        "the sentence it came from beside it")
    p.add_argument("--from-review", metavar="FILE", dest="from_review",
                   help="apply the review spreadsheet after you have been "
                        "over it. Reports without --apply")
    p.add_argument("--apply", action="store_true",
                   help="with --colour-sets or --from-review, write the "
                        "colours into the seed data")
    args = p.parse_args(argv)

    if args.peek:
        from src.budds_colour import peek
        path = Path(args.peek)
        if not path.exists():
            print(f"No file at {path}.", file=sys.stderr)
            return 1
        print(peek(path.read_text(encoding="utf-8", errors="replace")))
        return 0

    if args.peek_species:
        from src.budds_colour import blocks, colour_in
        path = Path(args.peek_species[0])
        if not path.exists():
            print(f"No file at {path}.", file=sys.stderr)
            return 1
        names = args.peek_species[1:]
        if not names:
            # Species whose colour is not in dispute, so a wrong answer here is
            # the parser or the OCR rather than a hard plant.
            names = ["Achillea millefolium", "Agastache foeniculum",
                     "Solidago rigida", "Cornus sericea",
                     "Opuntia polyacantha"]
        text = path.read_text(encoding="utf-8", errors="replace")
        found = blocks(text, names, catalogue_common_names())
        for name in names:
            print(f"\n=== {name} ===")
            hit = found.get(name)
            if not hit:
                print("  NOT FOUND in this text (not under this binomial, "
                      "and no common-name match)")
                continue
            block, how = hit
            print(f"  block is {len(block)} characters, matched on {how}:")
            print("  " + block[:600].replace("\n", "\n  "))
            buckets, quote = colour_in(block)
            print(f"\n  -> colour: {'/'.join(buckets) if buckets else 'NONE'}")
            print(f"  -> from:   {quote[:160]!r}")
        print("\nWhat to look at: is the block ONE species (good) or does it "
              "run into\nthe next one (the headings did not survive as "
              "lines)? And is the prose\nreadable, or is the OCR too broken "
              "to parse?")
        return 0

    if args.peek_genus:
        from src.budds_colour import _is_heading, normalise
        path = Path(args.peek_genus[0])
        if not path.exists():
            print(f"No file at {path}.", file=sys.stderr)
            return 1
        genera = args.peek_genus[1:] or ["Solidago", "Viola", "Astragalus"]
        lines = normalise(
            path.read_text(encoding="utf-8", errors="replace")).split("\n")
        for genus in genera:
            print(f"\n=== {genus} ===")
            low = genus.lower()
            shown = 0
            for i, line in enumerate(lines):
                text = line.strip()
                if low not in text.lower() or len(text) > 160:
                    continue
                # A species heading is Genus + lowercase epithet. Anything else
                # carrying the genus name in a short line is a candidate for
                # the genus heading, which is what we need the shape of.
                import re as _re
                if _re.match(rf"{_re.escape(genus)}\s+[a-z]{{3,}}", text):
                    continue
                print(f"  [line {i}] {'HEADING' if _is_heading(text) else '       '} "
                      f"{text[:130]}")
                for nxt in lines[i + 1:i + 3]:
                    print(f"             ... {nxt.strip()[:120]}")
                shown += 1
                if shown >= 4:
                    break
            if not shown:
                print("  no genus-level line found (only species headings)")
        print("\nWhat this is for: a flora states a colour once at the genus "
              "and then\nnotes only departures from it, so 140 species here "
              "have no colour of\ntheir own. Reading the genus needs the shape "
              "of a genus heading, and\nguessing that shape is how the last "
              "three parser bugs happened.")
        return 0

    if args.from_budds:
        path = Path(args.from_budds)
        if not path.exists():
            print(f"No file at {path}.", file=sys.stderr)
            return 1
        return budds_review(path)

    if args.from_review:
        path = Path(args.from_review)
        if not path.exists():
            print(f"No file at {path}.", file=sys.stderr)
            return 1
        return apply_review(path, args.apply)

    if args.colour_sets:
        folder = Path(args.colour_sets)
        if not folder.is_dir():
            print(f"{folder} is not a folder.", file=sys.stderr)
            return 1
        return apply_colour_sets(folder, args.apply)

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
