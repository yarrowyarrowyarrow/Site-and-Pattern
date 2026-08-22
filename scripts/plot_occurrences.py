#!/usr/bin/env python3
"""
scripts/plot_occurrences.py — where the records actually are.

**A dev tool, not an app panel, and nothing it draws is published.** See
"Publishing these is a separate decision" below, which is not a formality.

Why this exists
---------------
An outside botanical review of grownativeplants.ca asked the question the
catalogue could not answer:

    "Listing # of observations in an ecoregion doesn't explain where they are
    in the ecoregion — are they scattered throughout a broad ecozone? In
    isolated outliers? Or is it, for another example, a mountain species that
    shows up in Aspen Parkland?"

Every published range on the site is a *whole-polygon shade* derived from a
count. Three records in a 100,000 km² ecoregion fill the same shape as three
hundred, one lightness step apart. The count travels with the claim (P9) and
the count is not the same information as the distribution: a species clustered
in ten kilometres at the mountain front and a species spread across the region
produce identical maps.

Until V2.75 this script could not have existed, because the pipeline kept only
the derived counts. ``scripts/seed_ecoregion_ranges.py`` now caches the raw
points to ``data/fetched/plant_occurrences.json``, and this reads that.

The mountain species in Aspen Parkland was real, and it was ours
---------------------------------------------------------------
``--buffer-artefacts`` exists because the review's hypothetical turned out to
be a live bug with a bigger number behind it than the one it named. V2.67
introduced ``ecoregion._NEAR_BOUNDARY_M``, a 5 km proximity buffer written to
answer *which ecoregion is this yard in*; ``ranges_for_species`` inherited it
and credited every record to every region within five kilometres. Over 4,000
random points inside the layer, 16.4% land in two or more.

That is fixed in the derivation. This mode is how it stays fixed and how the
cost of the old behaviour is measured rather than asserted: it counts records
whose region assignment no point actually falls inside.

Running it
----------
    python scripts/plot_occurrences.py --species "Aster alpinus" --out aa.svg
    python scripts/plot_occurrences.py --buffer-artefacts
    python scripts/plot_occurrences.py --sheet worst-first.html --limit 40
    python scripts/plot_occurrences.py --sheet specimens.html --specimens --publishable

The cache is a dev artefact and may be absent on a fresh clone; every mode
says so plainly rather than drawing an empty map, because an empty map of a
species with 400 records is the failure that looks most like a finding.

Publishing these is a separate decision, and specimens are the near half
------------------------------------------------------------------------
Two constraints stood in the way, and V2.77 found that ``--specimens
--publishable`` clears both rather than arguing with them:

1. **Licence.** ``scripts/fetch_dataset_licences.py`` asked GBIF per dataset.
   **90.1% of specimen records are CC0 or CC-BY** — and for a herbarium the
   dataset licence IS the record's licence, because a collection is published
   under one. For ``HUMAN_OBSERVATION`` it is only the publisher's default:
   iNaturalist observers each choose their own, so that number sizes the layer
   and does not authorise plotting an individual point.
2. **Sensitive species.** iNaturalist obscures coordinates for rare, threatened
   and collectible taxa precisely so that publishing them does not lead a
   collector to the plant. Orchids and cacti in this catalogue are that
   category. Specimen records do not carry that problem: the plant is already
   a pressed sheet in a cabinet with a locality on its label, and this is why
   the printed regional floras plot specimens.

Note the irony, because it bears on the review's other point: the rare species
the three-record floor under-serves are the same ones whose *observation*
coordinates must stay coarse.

**What is still not decided here.** Nothing this draws is published. Whether
the dots reach grownativeplants.ca, and whether the CC-BY-NC observation layer
joins them, is a call made after looking at these — which is what this mode is
for.
"""

from __future__ import annotations

import argparse
import html
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

#: Dot colours by what kind of record it is. Deliberately not the region
#: palette: these sit ON the regions, and reusing a region hue would make a
#: record look like a claim about the ground under it.
BASIS_COLOUR = {
    "PRESERVED_SPECIMEN": "#1b3a6b",     # a sheet in a cabinet
    "HUMAN_OBSERVATION": "#c2410c",      # someone saw it
    "OCCURRENCE": "#6b7280",
    "MACHINE_OBSERVATION": "#7c3aed",
    "": "#6b7280",
}

#: A record's stated uncertainty, drawn. A 30 m GPS fix and a 5 km "near the
#: lake" are different observations and the old pipeline treated them as one.
_MIN_R, _MAX_R = 1.6, 9.0


def _cache() -> dict:
    from scripts.seed_ecoregion_ranges import read_cache
    return read_cache()


def _require(cache: dict) -> None:
    if cache:
        return
    from scripts.seed_ecoregion_ranges import CACHE_PATH
    print(
        f"No point cache at {CACHE_PATH.relative_to(PROJECT_ROOT)}.\n\n"
        "It is a dev artefact, written by a run of\n"
        "    python scripts/seed_ecoregion_ranges.py\n"
        "on a machine with egress (this container's proxy answers 403 to\n"
        "api.gbif.org). Nothing here can be drawn without it, and drawing an\n"
        "empty map instead would be the failure that looks most like a\n"
        "finding.",
        file=sys.stderr)
    raise SystemExit(1)


# ── Which records may be drawn ──────────────────────────────────────────────

class NoLicenceTable(RuntimeError):
    """No ``dataset_licences.json``. Refused rather than defaulted.

    Treating an unknown licence as permissive publishes what we may not, and
    treating it as withheld draws an empty map that reads as "the herbaria have
    nothing" — both are worse than saying which command is missing.
    """


def licences(path=None) -> dict:
    """``{dataset_key: licence token}`` from the dataset licence table."""
    import json                                              # noqa: PLC0415
    from scripts.fetch_dataset_licences import OUTPUT_PATH   # noqa: PLC0415
    path = path or OUTPUT_PATH
    try:
        with open(path, encoding="utf-8") as f:
            blob = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError, OSError) as exc:
        raise NoLicenceTable(
            f"No dataset licence table at {path}.\n\n"
            "It is a dev artefact, written on a machine with egress by\n"
            "    python scripts/fetch_dataset_licences.py\n"
            "Without it nothing here can say what may be redrawn, and drawing\n"
            "an empty map instead would be the failure that looks most like a\n"
            "finding.") from exc
    return {k: (r.get("licence") or "UNSPECIFIED")
            for k, r in (blob.get("datasets") or {}).items()}


def specimens(points) -> list:
    """Only the herbarium sheets — the basis the printed floras plot."""
    from scripts.seed_ecoregion_ranges import SPECIMEN_BASIS  # noqa: PLC0415
    return [p for p in points if getattr(p, "basis", "") == SPECIMEN_BASIS]


def publishable(points, table: dict) -> list:
    """Only records whose dataset licence permits redrawing the coordinate.

    Reuses ``fetch_dataset_licences.PUBLISHABLE`` rather than restating it, so
    a change to what this project considers publishable cannot apply in one
    place and not the other. A ``dataset_key`` absent from the table is
    dropped: absent is not permissive, which is the same rule the photo
    pipeline runs on.
    """
    from scripts.fetch_dataset_licences import PUBLISHABLE   # noqa: PLC0415
    return [p for p in points
            if table.get(getattr(p, "dataset_key", "")) in PUBLISHABLE]


def drawable(points, *, only_specimens: bool, only_publishable: bool,
             table: dict | None = None) -> tuple[list, dict]:
    """``(points to draw, {why: how many were dropped})``.

    The counts come back rather than being swallowed, because "we drew four of
    three hundred records" is the finding and a quiet blank map is not.
    """
    kept = list(points)
    why: dict[str, int] = {}
    if only_specimens:
        after = specimens(kept)
        why["not a specimen"] = len(kept) - len(after)
        kept = after
    if only_publishable:
        after = publishable(kept, table or {})
        why["licence does not permit redrawing"] = len(kept) - len(after)
        kept = after
    return kept, {k: v for k, v in why.items() if v}


def _radius(uncertainty_m: float | None, scale: float) -> float:
    """Dot radius: the record's own stated uncertainty, in map units.

    Clamped at both ends. Below ``_MIN_R`` a dot stops being visible; above
    ``_MAX_R`` one county-level record would cover a fifth of the map and
    read as a claim rather than as a caveat. A record stating no uncertainty
    gets the minimum and is drawn hollow, because "not recorded" and
    "recorded as precise" must not look the same (P9).
    """
    if uncertainty_m is None:
        return _MIN_R
    return max(_MIN_R, min(_MAX_R, uncertainty_m * scale))


def points_svg(points, project, *, scale: float = 0.0) -> str:
    """The occurrence overlay for :func:`src.ecoregion_map.map_svg`."""
    out = []
    for pt in points:
        x, y = project(pt[1], pt[0])
        unc = getattr(pt, "uncertainty_m", None)
        colour = BASIS_COLOUR.get(getattr(pt, "basis", ""), BASIS_COLOUR[""])
        r = _radius(unc, scale)
        year = getattr(pt, "year", None)
        tip = (f"{pt[0]:.4f}, {pt[1]:.4f}"
               f"{f' · {year}' if year else ''}"
               f" · {getattr(pt, 'basis', '') or 'basis unrecorded'}"
               f" · {'±%dm' % unc if unc is not None else 'uncertainty unrecorded'}")
        fill = "none" if unc is None else colour
        out.append(
            f'<circle cx="{x:.1f}" cy="{y:.1f}" r="{r:.1f}" fill="{fill}" '
            f'stroke="{colour}" stroke-width="0.9" fill-opacity="0.55">'
            f'<title>{html.escape(tip)}</title></circle>')
    return f'<g class="occ">{"".join(out)}</g>'


def caption(name: str, shading_n: int, dots_n: int, dropped: dict) -> str:
    """The sentence without which a filtered map is a lie by omission.

    A region shaded from three hundred records and showing four dots reads as
    broken. It is not broken — it is two different statements drawn on one
    picture, and the only way that is honest is to say so on the picture.
    """
    if dots_n == shading_n and not dropped:
        return f"{shading_n:,} records, all drawn."
    bits = [f"{dots_n:,} of {shading_n:,} records drawn"]
    for why, n in sorted(dropped.items(), key=lambda kv: -kv[1]):
        bits.append(f"{n:,} {why}")
    tail = "; ".join(bits)
    if dots_n:
        return (f"{tail}. The shading below is derived from all "
                f"{shading_n:,}, not from the dots.")
    return (f"{tail}. No dot is drawable here — the shading below still comes "
            f"from all {shading_n:,} records, so this is a gap in what may be "
            f"drawn, not in what is known.")


def species_svg(name: str, points, *, width: int = 720, dots=None) -> str:
    """One species: the derived shading, with the records that produced it.

    ``dots`` draws a *subset* while the shading stays derived from every point
    — the published range is a claim about all the evidence, and filtering the
    picture must not quietly filter the claim. Callers that filter are
    responsible for printing :func:`caption` beside it.
    """
    from src.ecoregion_map import frame_height, map_svg, projector
    from src.ecoregion_ranges import ranges_for_species

    height = frame_height(width)
    project = projector(width, height)
    rows = ranges_for_species(points)
    highlight = {r["ecoregion"]: r["confidence"] for r in rows}
    drawn = points if dots is None else dots

    # Metres -> map units, so an uncertainty radius means what it says. Taken
    # off the projection itself rather than assumed: two points a known
    # distance apart, measured on the drawing.
    from src.projection import metres_per_deg
    per_lat, _per_lng = metres_per_deg(54.0)
    one_km_in_degrees = 1000.0 / per_lat
    y0 = project(-110.5, 54.0)[1]
    y1 = project(-110.5, 54.0 + one_km_in_degrees)[1]
    scale = abs(y1 - y0) / 1000.0          # map units per metre

    return map_svg(highlight, width=width, height=height,
                   title=f"Records behind the range of {name}",
                   overlay=points_svg(drawn, project, scale=scale))


def buffer_artefacts(cache: dict) -> tuple[int, int, list]:
    """``(assignments, artefacts, worst)`` — what the 5 km buffer cost.

    An *artefact* is a (species, region) pair the buffered lookup would claim
    and containment does not: no record of that species falls inside that
    region. It is the honest measure of the V2.67 bug, computed from the
    records rather than argued from the geometry.
    """
    from src.ecoregion import lookup_ecoregions
    from src.ecoregion_ranges import MIN_RECORDS

    total = artefacts = 0
    worst: list[tuple[str, str, int]] = []
    for name, points in sorted(cache.items()):
        buffered: dict[str, int] = {}
        inside: dict[str, int] = {}
        for pt in points:
            for key in lookup_ecoregions(pt[0], pt[1]):
                buffered[key] = buffered.get(key, 0) + 1
            for key in lookup_ecoregions(pt[0], pt[1], near_m=0.0):
                inside[key] = inside.get(key, 0) + 1
        for key, n in buffered.items():
            if n < MIN_RECORDS:
                continue
            total += 1
            if inside.get(key, 0) < MIN_RECORDS:
                artefacts += 1
                worst.append((name, key, n))
    worst.sort(key=lambda row: -row[2])
    return total, artefacts, worst


def _report_filters(args, cache: dict, filtered) -> None:
    """The whole-catalogue arithmetic behind a sheet, printed once.

    Whether a layer is worth publishing is not a question about twenty-four
    thumbnails. It is "how many species does this leave with nothing", and that
    number has to be looked at rather than inferred from the pictures that
    happen to be on the page.
    """
    if not (args.specimens or args.publishable):
        return
    total = sum(len(v) for v in cache.values())
    kept = 0
    empty = 0
    reasons: dict[str, int] = {}
    for points in cache.values():
        dots, why = filtered(points)
        kept += len(dots)
        empty += 0 if dots else 1
        for k, n in why.items():
            reasons[k] = reasons.get(k, 0) + n
    share = (100.0 * kept / total) if total else 0.0
    print(f"\nAcross the whole cache: {kept:,} of {total:,} records "
          f"({share:.1f}%) are drawable under these filters.")
    for why, n in sorted(reasons.items(), key=lambda kv: -kv[1]):
        print(f"      {n:8,}  {why}")
    print(f"  {empty} of {len(cache)} species have no drawable record at all.")


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--species", help="Scientific name to draw.")
    p.add_argument("--out", help="Write the SVG here (default: stdout).")
    p.add_argument("--width", type=int, default=720)
    p.add_argument("--sheet", help="Write a contact sheet of many species.")
    p.add_argument("--limit", type=int, default=24,
                   help="Species on the contact sheet (default 24).")
    p.add_argument("--buffer-artefacts", action="store_true",
                   help="Count region claims no record actually falls inside.")
    p.add_argument("--specimens", action="store_true",
                   help="Draw only PRESERVED_SPECIMEN records — the basis the "
                        "printed regional floras plot, and the one with no "
                        "rare-taxa coordinate obscuring.")
    p.add_argument("--publishable", action="store_true",
                   help="Draw only records whose dataset licence permits "
                        "redrawing the coordinate (CC0 / CC-BY).")
    args = p.parse_args(argv)

    cache = _cache()
    _require(cache)

    table: dict = {}
    if args.publishable:
        try:
            table = licences()
        except NoLicenceTable as exc:
            print(exc, file=sys.stderr)
            return 1

    def filtered(points):
        return drawable(points, only_specimens=args.specimens,
                        only_publishable=args.publishable, table=table)

    if args.buffer_artefacts:
        total, bad, worst = buffer_artefacts(cache)
        share = (100.0 * bad / total) if total else 0.0
        print(f"{total} region claims across {len(cache)} species under the "
              f"buffered lookup.")
        print(f"{bad} of them ({share:.1f}%) have fewer than the floor of "
              f"records actually inside the region — they exist only because "
              f"a record passed within 5 km.")
        print("\nWorst by record count:")
        for name, key, n in worst[:30]:
            print(f"  {n:5d}  {name} -> {key}")
        return 0

    if args.sheet:
        # Ordered by what the sheet is *of*: with a filter on, the species
        # worth looking at are the ones with the most DRAWABLE records, not the
        # most records. Sorting by the latter is how a contact sheet of the
        # specimen layer would have opened on sixteen blank maps.
        ranked = sorted(cache, key=lambda n: -len(filtered(cache[n])[0]))
        names = ranked[:args.limit]
        blocks, blank = [], []
        for name in names:
            pts = cache[name]
            dots, why = filtered(pts)
            if not dots:
                blank.append(name)
            blocks.append(
                f'<figure><figcaption>{html.escape(name)}</figcaption>'
                f'{species_svg(name, pts, width=360, dots=dots)}'
                f'<p>{html.escape(caption(name, len(pts), len(dots), why))}</p>'
                f'</figure>')
        Path(args.sheet).write_text(
            "<meta charset='utf-8'><title>Occurrence contact sheet</title>"
            "<style>body{font:14px system-ui;background:#fff;margin:2rem}"
            "figure{display:inline-block;margin:0 1rem 1.5rem 0;width:360px;"
            "vertical-align:top}"
            "figcaption{font-style:italic;margin-bottom:.3rem}"
            "p{color:#555;font-size:12px;margin:.3rem 0 0}</style>"
            + "".join(blocks), encoding="utf-8")
        print(f"Wrote {args.sheet} ({len(names)} species).")
        _report_filters(args, cache, filtered)
        if blank:
            print(f"  {len(blank)} of them have nothing drawable and render as "
                  f"a shaded map with no dots: {', '.join(blank[:8])}"
                  f"{' ...' if len(blank) > 8 else ''}")
        return 0

    if not args.species:
        p.error("give --species, --sheet or --buffer-artefacts")

    points = cache.get(args.species)
    if points is None:
        print(f"{args.species!r} is not in the cache. It holds "
              f"{len(cache)} species.", file=sys.stderr)
        return 1

    dots, why = filtered(points)
    svg = species_svg(args.species, points, width=args.width, dots=dots)
    if args.out:
        Path(args.out).write_text(svg, encoding="utf-8")
        print(f"Wrote {args.out}. "
              f"{caption(args.species, len(points), len(dots), why)}")
    else:
        print(svg)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
