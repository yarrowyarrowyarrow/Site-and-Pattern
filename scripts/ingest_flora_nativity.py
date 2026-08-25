#!/usr/bin/env python3
"""
scripts/ingest_flora_nativity.py — what VASCAN says, against what we claim.

**Reports by default. Applies nothing.** That is not caution for its own sake;
it is the shape three increments in this repo arrived at the hard way. V2.59's
first apply put 23 Monarch caterpillars on goldenrod. V2.60's first fix binned
62 good bird edges. V2.64's first apply wrote 20 animals connected to nothing.
Each was caught because a human read a report before anything was written.

Reads ``data/fetched/flora_nativity.json`` (written by
``scripts/fetch_flora_nativity.py`` on a machine with egress) and prints four
buckets:

``confirm``   VASCAN agrees with what the catalogue already says.
``narrow``    VASCAN records fewer provinces than we claim. **Expected to be
              the largest bucket**, because 355 of 431 rows say "AB,SK" and
              that string was generated, not read from a flora.
``not_here``  VASCAN records it introduced, or from neither province. The
              *Rudbeckia hirta* / *Helianthus giganteus* shape.
``name``      the binomial is a synonym, or VASCAN could not match it at all.

What it will not do
-------------------
**No automatic deletion.** Every removal goes through
``data/excluded_taxa.json`` with an authority string, per V2.74, so the
reasoning survives and the next sourcing pass meets it instead of re-deriving
the call.

**No automatic rename.** A superseded name is a *report* here. Renaming moves
plant ids, the ``plant_fauna_master.json`` keys that name a plant by common
name, and a public URL that people may have linked to. Merging *Solidago
rigida* with *Oligoneuron rigidum* is a decision about which name survives, and
it is its own increment.

**No verdict from silence.** ``origin: unstated`` means VASCAN lists the
province and records no establishment means. It is a real and common answer,
and it is reported as itself. Absent is not estimated.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

FETCHED = PROJECT_ROOT / "data" / "fetched" / "flora_nativity.json"
PLANT_FILES = ("plants_master.json", "garden_plants.json")


def _short(path) -> str:
    """A repo-relative path when it is inside the repo, the full path when not.

    `Path.relative_to` raises for anything outside, and it was being called in
    the "the file is missing" error message -- so redirecting the constant to a
    temp path crashed the one code path whose whole job is to fail politely.
    """
    try:
        return str(Path(path).relative_to(PROJECT_ROOT))
    except ValueError:
        return str(path)


def load_fetched(path=FETCHED) -> dict:
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError, OSError):
        return {}


def catalogue() -> dict:
    """``{scientific_name: record}`` over the shipped plant files."""
    out: dict = {}
    for name in PLANT_FILES:
        try:
            with open(PROJECT_ROOT / "data" / name, encoding="utf-8") as f:
                rows = json.load(f)
        except (FileNotFoundError, json.JSONDecodeError, OSError):
            continue
        for row in rows if isinstance(rows, list) else []:
            if isinstance(row, dict) and row.get("scientific_name"):
                out[row["scientific_name"]] = row
    return out


def compare(fetched: dict, rows: dict) -> dict:
    """``{bucket: [proposal]}``, where a proposal explains itself.

    The comparison the fetcher deliberately does not make: VASCAN answers
    "where is this native", and only the catalogue knows "and what did we
    say?". Keeping those apart means a re-fetch never has to know about our
    seed files.
    """
    buckets: dict = {"confirm": [], "narrow": [], "not_here": [],
                     "undetermined": [], "name": []}
    for name, said in sorted((fetched.get("results") or {}).items()):
        record = rows.get(name)
        if record is None:
            continue
        claimed = {c.strip().upper()
                   for c in (record.get("native_provinces") or "").split(",")
                   if c.strip()}
        found = {c.strip().upper()
                 for c in (said.get("native_provinces") or "").split(",")
                 if c.strip()}
        common = (record.get("common_name") or "").strip()
        proposal = {
            "scientific_name": name,
            "common_name": common,
            "claimed": ",".join(sorted(claimed)) or "-",
            "vascan": ",".join(sorted(found)) or "-",
            "origin": said.get("origin", ""),
            "why": said.get("why", ""),
            "accepted_name": said.get("accepted_name", ""),
        }

        if said.get("is_synonym") or said.get("origin") == "unmatched":
            buckets["name"].append(proposal)
            continue
        # Its own bucket, never folded into `not_here`. VASCAN publishes
        # distribution on the lowest accepted taxon, so a species with accepted
        # varieties has none of its own, and reading that as "not here" put
        # Saskatoon Berry outside the parkland (V2.79).
        if said.get("origin") == "undetermined":
            buckets["undetermined"].append(proposal)
            continue
        if said.get("verdict") == "not_here":
            buckets["not_here"].append(proposal)
            continue
        if found and claimed - found:
            # The AB,SK -> AB case. Not an error in VASCAN's favour
            # automatically: a province VASCAN has no row for is a province it
            # says nothing about, which is why this is a proposal and not a fix.
            proposal["removes"] = ",".join(sorted(claimed - found))
            buckets["narrow"].append(proposal)
            continue
        buckets["confirm"].append(proposal)
    return buckets


def report(buckets: dict, fetched: dict, *, limit: int = 40) -> None:
    order = ("not_here", "name", "undetermined", "narrow", "confirm")
    blurb = {
        "not_here": "VASCAN records these introduced here, or from neither "
                    "province. Each needs a data/excluded_taxa.json entry "
                    "with its authority before the row comes out.",
        "name": "Superseded or unmatched names. REPORT ONLY: renaming moves "
                "plant ids, edge keys and a public URL.",
        "narrow": "We claim more provinces than VASCAN records. This is the "
                  "review's actual complaint, and the field it disagrees with "
                  "was generated rather than read from a flora.",
        "undetermined": "VASCAN matched the name and publishes no "
                        "distribution for it. STILL NOT A FINDING ABOUT THE "
                        "PLANT. Against the API this bucket held 173 species "
                        "and meant 'distribution lives on the lowest accepted "
                        "taxon'; the archive roll-up answers those. Whatever "
                        "is left is a lineage the roll-up could not follow, "
                        "and the way to see which is:\n"
                        "    python scripts/fetch_flora_nativity.py "
                        "--from-archive <path> --explain \"<species>\"\n"
                        "  which prints the taxa the name matched, what hangs "
                        "under the one it chose, and the rows each carries. "
                        "Decide nothing from this bucket until it is empty or "
                        "explained.",
        "confirm": "VASCAN agrees with the catalogue.",
    }
    for bucket in order:
        rows = buckets[bucket]
        print(f"\n=== {bucket}: {len(rows)} ===")
        print(f"{blurb[bucket]}\n")
        for row in rows[:limit]:
            extra = (f"  removes {row['removes']}" if row.get("removes")
                     else "")
            print(f"  {row['scientific_name']:34s} "
                  f"claimed {row['claimed']:6s} -> VASCAN {row['vascan']:6s}"
                  f"{extra}")
            if bucket in ("not_here", "name"):
                print(f"      {row['why']}")
                if row.get("accepted_name"):
                    print(f"      accepted name: {row['accepted_name']}")
        if len(rows) > limit:
            print(f"  ... and {len(rows) - limit} more")

    failed = fetched.get("failed") or []
    if failed:
        print(f"\n{len(failed)} species were NOT fetched (the server refused). "
              f"They are absent from every bucket above and are not evidence "
              f"of anything. Re-run the fetch for them.")


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--limit", type=int, default=40,
                   help="Rows printed per bucket (default 40).")
    p.add_argument("--json", help="Also write the buckets here, for review.")
    args = p.parse_args(argv)

    # `FETCHED` read here rather than taken from `load_fetched`'s default,
    # which binds at import and so cannot be redirected -- a wart the V2.79
    # tests found when the real fetch file landed and the "refuses a missing
    # file" test turned out to have been asserting a fact about the working
    # tree instead of about the guard.
    fetched = load_fetched(FETCHED)
    if not fetched:
        print(
            f"No {_short(FETCHED)}.\n\n"
            "Write it first, on a machine with internet:\n"
            "    python3 scripts/fetch_flora_nativity.py --probe\n"
            "    python3 scripts/fetch_flora_nativity.py\n\n"
            "This container's proxy answers 403 to data.canadensys.net.",
            file=sys.stderr)
        return 1

    buckets = compare(fetched, catalogue())
    print(f"VASCAN data: {fetched.get('source', 'source unrecorded')}")
    report(buckets, fetched, limit=args.limit)

    if args.json:
        Path(args.json).write_text(json.dumps(buckets, indent=1),
                                   encoding="utf-8")
        print(f"\nWrote {args.json}")

    print("\nNOTHING HAS BEEN CHANGED. Removals go through "
          "data/excluded_taxa.json with an authority; province narrowing is a "
          "seed-file edit; renames are their own increment.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
