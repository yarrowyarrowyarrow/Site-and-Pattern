#!/usr/bin/env python3
"""
scripts/pdf_to_text.py — get the words out of a PDF.

    python scripts/pdf_to_text.py budds.pdf

Writes ``budds.txt`` beside it, then tells you whether the file is usable.

Why this is its own step
------------------------
``fetch_flower_colour.py`` reads **plain text**, not PDFs, on purpose: a PDF
library is an install that fails on some machines for reasons that have
nothing to do with flowers, and burying the extraction inside the parser hides
the one question that decides how much work the whole job is.

That question is **does this PDF have a text layer?** A PDF can be either:

* **Text**, where the words are in the file and this takes seconds; or
* **Images**, where each page is a photograph of a page and there are no words
  in the file at all. Then this prints almost nothing, and the job needs OCR
  before anything else can happen.

Both look identical in a PDF viewer, because your eyes do the OCR. The
difference is the difference between an evening and a project, so this reports
it as a number and says which one you have.

Not installed yet?
------------------
    pip install pypdf

One dependency, pure Python, nothing to compile.

If it turns out to be a scan
----------------------------
You need OCR, which is a different tool: Tesseract (free) or Acrobat's
"Recognise Text". Both write a *new* PDF with a text layer, and then this
script works on that. OCR of a 1979 scan will be wrong sometimes -- which is
why the colour reader quotes the book's own sentence beside every proposal
rather than trusting itself.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

#: Below this many characters per page, averaged, a PDF is almost certainly a
#: scan. A typed page of a flora runs to a few thousand; an image-only page
#: yields a page number and stray marks, if anything.
SCAN_THRESHOLD = 100


def extract(pdf: Path, out: Path, quiet: bool = False) -> tuple:
    """``(pages, characters)``. Writes ``out``."""
    try:
        import pypdf
    except ImportError:
        raise SystemExit(
            "pypdf is not installed. Run:\n\n    pip install pypdf\n\n"
            "One dependency, pure Python, nothing to compile.")

    reader = pypdf.PdfReader(str(pdf))
    total = len(reader.pages)
    chunks = []
    for i, page in enumerate(reader.pages, 1):
        try:
            chunks.append(page.extract_text() or "")
        except Exception as exc:                       # noqa: BLE001
            # One unreadable page must not cost the other 900. A flora has
            # plates and fold-outs that are images even in a text PDF.
            chunks.append("")
            if not quiet:
                print(f"  page {i}: unreadable ({type(exc).__name__})")
        if not quiet and total > 50 and i % 100 == 0:
            print(f"  ... {i} of {total} pages")

    text = "\n".join(chunks)
    out.write_text(text, encoding="utf-8")
    return total, len(text)


def main(argv=None) -> int:
    p = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("pdf", help="the PDF to read")
    p.add_argument("--out", help="where to write the text "
                                 "(default: same name, .txt)")
    p.add_argument("--quiet", action="store_true", help="less progress noise")
    args = p.parse_args(argv)

    pdf = Path(args.pdf)
    if not pdf.exists():
        print(f"No file at {pdf}.", file=sys.stderr)
        return 1
    out = Path(args.out) if args.out else pdf.with_suffix(".txt")

    pages, chars = extract(pdf, out, args.quiet)
    per_page = chars / pages if pages else 0

    print(f"\n{pdf.name}: {pages:,} pages, {chars:,} characters "
          f"({per_page:,.0f} per page)")
    print(f"Written to {out}")

    if per_page < SCAN_THRESHOLD:
        print("\nTHIS IS A SCAN, NOT TEXT.")
        print("There are no words in this PDF -- each page is a picture of a "
              "page. It\nlooks readable because your eyes are doing the work "
              "the computer cannot.")
        print("\nIt needs OCR first: Tesseract (free), or Acrobat's "
              "'Recognise Text'. Both\nwrite a new PDF with a text layer, and "
              "this script then works on that one.")
        return 2

    print("\nThis has a real text layer. Next:")
    print(f"    python scripts/fetch_flower_colour.py --peek {out.name}")
    print("which counts what is in it before anything tries to parse it.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
