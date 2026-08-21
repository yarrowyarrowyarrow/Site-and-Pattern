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

The cache is a dev artefact and may be absent on a fresh clone; every mode
says so plainly rather than drawing an empty map, because an empty map of a
species with 400 records is the failure that looks most like a finding.

Publishing these is a separate decision
---------------------------------------
Two constraints, and the second can cause harm:

1. **Licence.** ``docs/DATA_SOURCES.md`` currently rests the GBIF position on
   storing "only the derived counts, never GBIF's records themselves". Drawing
   coordinates on a public page changes that sentence, and GBIF records carry
   per-record licences.
2. **Sensitive species.** iNaturalist obscures coordinates for rare,
   threatened and collectible taxa precisely so that publishing them does not
   lead a collector to the plant. Orchids and cacti in this catalogue are that
   category. A published map must never plot a point at finer precision than
   its source published it.

Note the irony, because it bears on the review's other point: the rare species
the three-record floor under-serves are the same ones whose coordinates must
stay coarse.
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


def species_svg(name: str, points, *, width: int = 720) -> str:
    """One species: the derived shading, with the records that produced it."""
    from src.ecoregion_map import frame_height, map_svg, projector
    from src.ecoregion_ranges import ranges_for_species

    height = frame_height(width)
    project = projector(width, height)
    rows = ranges_for_species(points)
    highlight = {r["ecoregion"]: r["confidence"] for r in rows}

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
                   overlay=points_svg(points, project, scale=scale))


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
    args = p.parse_args(argv)

    cache = _cache()
    _require(cache)

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
        names = sorted(cache, key=lambda n: -len(cache[n]))[:args.limit]
        blocks = []
        for name in names:
            pts = cache[name]
            blocks.append(
                f'<figure><figcaption>{html.escape(name)} '
                f'<small>{len(pts)} records</small></figcaption>'
                f'{species_svg(name, pts, width=360)}</figure>')
        Path(args.sheet).write_text(
            "<meta charset='utf-8'><title>Occurrence contact sheet</title>"
            "<style>body{font:14px system-ui;background:#fff;margin:2rem}"
            "figure{display:inline-block;margin:0 1rem 1.5rem 0;width:360px}"
            "figcaption{font-style:italic;margin-bottom:.3rem}"
            "small{font-style:normal;color:#666}</style>"
            + "".join(blocks), encoding="utf-8")
        print(f"Wrote {args.sheet} ({len(names)} species).")
        return 0

    if not args.species:
        p.error("give --species, --sheet or --buffer-artefacts")

    points = cache.get(args.species)
    if points is None:
        print(f"{args.species!r} is not in the cache. It holds "
              f"{len(cache)} species.", file=sys.stderr)
        return 1

    svg = species_svg(args.species, points, width=args.width)
    if args.out:
        Path(args.out).write_text(svg, encoding="utf-8")
        print(f"Wrote {args.out} ({len(points)} records).")
    else:
        print(svg)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
