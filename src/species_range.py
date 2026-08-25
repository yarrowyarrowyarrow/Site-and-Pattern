"""
species_range.py — where a plant has actually been found, at a stated resolution.

Design principle P9 — see docs/DESIGN_PHILOSOPHY.md.

Why this exists, and why it replaces the picture rather than improving it
------------------------------------------------------------------------
Since V2.38 this catalogue has drawn a species' range by **shading ecoregions**.
Everything since V2.75 has improved how that shading is derived -- containment
instead of a 5 km buffer, the sliver region that was absorbing the mountains,
the harvest cap that was hiding the north -- and every one of those fixes left
the assumption underneath untouched.

The assumption is that a range is a set of ecological units coloured in. It is
not. A range is where the plant has been found; ecoregions are a classification
laid *over* that. Shading a 100,000 km² region because three records fall in it
overstates in exactly the way the outside review objected to, one level above
the bug it named:

    "Listing # of observations in an ecoregion doesn't explain where they are
    in the ecoregion."

The author put it more plainly after seeing the corrected maps: *"this range
does not neatly conform to ecoregions."* It does not, because it is not made of
them.

What this draws instead
-----------------------
The occupied cells of a **0.25 degree grid**. One cell asserts exactly one
thing: *at least one usable record falls inside this square*. Measured on the
shipped cache that is 206-541 cells for a well-recorded species, about 4 KB.

**A grid and not a hull, deliberately.** An alpha shape or concave hull draws a
boundary through ground where nothing was recorded -- it interpolates, and the
interpolation is invisible once it is filled in. That is the review's complaint
wearing a smoother shape. A cell is a fact with a stated resolution, which is
the same bargain the occurrence counts already make.

It also needs no new dependency. `shapely` is in `requirements.txt` but every
`src/` use of it is guarded (`shadow_geometry`, `footprint_ndsm`) because the
app is expected to run without it, and putting the *website build* behind a
hull library the desktop deliberately survives without would be a poor trade
for a smoother edge.

What a cell is not
------------------
**Not a claim that the plant grows throughout the cell.** At this latitude a
0.25 degree cell is roughly 28 km north-south and 16-19 km east-west. Somewhere
in that square, at least once, somebody recorded this plant.

**Not absence anywhere else.** An empty cell is unsurveyed or unrecorded, which
is the same distinction `establishment.py` draws between *unlikely* and
*unknown*. The renderer must never style empty cells as "not here".

**Not an abundance, once it is shaded by count (V2.80).** The first build drew
every occupied cell in one colour and it could not be read: a well-recorded
species lands 10-30 marks in each of its cells, so the marks buried the wash and
all three palettes rendered identically. Shading the cell by how many records it
holds draws that information once instead of thirty times -- but the number is
recording effort as much as it is the plant, so `density_band` says so and the
caption repeats it wherever the ramp appears.

**Not a substitute for the ecoregion rows.** Those still carry counts and
confidence bands, still drive the filters and the region hub pages, and still
answer a different question: not *where is it* but *which of the classified
communities is it recorded from*.
"""

from __future__ import annotations

#: Grid resolution in degrees. 0.25 is the coarsest step that still shows
#: structure inside Alberta (a species confined to the Cypress Hills reads as
#: distinct from one across the whole southeast) and the finest that does not
#: dissolve a sparse species into confetti -- at 0.125 a 1,200-record grass
#: averages two records per cell, which is a scatter plot with square dots.
#: Stated on the page, because a resolution nobody can see is false precision.
CELL_DEG = 0.25

#: About how big a cell is on the ground here, for the caption. Latitude is
#: ~111 km/degree everywhere; longitude shrinks with the cosine, from ~18.5 km
#: at the 49th parallel to ~13.9 km at the 60th.
CELL_KM_NS = 27.8


def cell_of(lat: float, lng: float, *, step: float = CELL_DEG) -> tuple:
    """The grid cell a coordinate falls in, as its south-west corner.

    Floor rather than round, so a cell covers ``[corner, corner + step)`` and
    every coordinate lands in exactly one. Rounding would make cells straddle
    their own labels and put a point on a boundary into whichever neighbour won
    a floating-point comparison.
    """
    import math
    return (math.floor(lat / step) * step, math.floor(lng / step) * step)


def cell_counts(points, *, step: float = CELL_DEG, subject_only: bool = True
                ) -> dict:
    """``{(lat, lng): records}`` -- how many records fall in each cell.

    ``points`` are ``(lat, lng)`` pairs or :class:`Occurrence` tuples -- the
    same duck type `ranges_for_species` takes, so the cache drops straight in.

    ``subject_only`` drops records outside Alberta and Saskatchewan, because a
    range map of ground this catalogue does not speak for is the F142 bug again
    (31.7% of the harvest sits outside the two provinces).

    The count is kept because the *presence* alone could not be drawn (V2.80).
    A well-recorded species puts 10-30 marks in every cell it occupies, so the
    marks bury the wash and every palette renders identically. Shading the cell
    by its count draws the same information once instead of thirty times. What
    the count is **not** is in :func:`density_band`.
    """
    keep = None
    if subject_only:
        from src.subject_area import in_subject_provinces
        keep = in_subject_provinces
    counts: dict = {}
    for point in points:
        lat, lng = float(point[0]), float(point[1])
        if keep is not None and not keep(lat, lng):
            continue
        cell = cell_of(lat, lng, step=step)
        counts[cell] = counts.get(cell, 0) + 1
    return counts


def occupied_cells(points, *, step: float = CELL_DEG, subject_only: bool = True
                   ) -> list:
    """Sorted ``[(lat, lng), ...]`` south-west corners with at least one record.

    Presence only. :func:`cell_counts` is the same pass with the count kept.
    """
    return sorted(cell_counts(points, step=step, subject_only=subject_only))


#: Lower bounds of density bands 1..4; band 0 is a single record. Log-ish
#: rather than even, because record counts per cell are heavy-tailed -- a cell
#: holding a city runs to thousands while the median cell holds one or two, and
#: even breaks would paint the whole province the lightest colour but Calgary.
DENSITY_BREAKS = (2, 5, 20, 100)

#: What each band says, for the legend. Plain hyphens on purpose: the site
#: normalises em dashes and a range label is not the place to test that.
BAND_LABELS = ("1", "2-4", "5-19", "20-99", "100+")


def density_band(count: int) -> int:
    """Which of the five bands a cell's record count falls in, ``0``-``4``.

    **This is recording effort as much as it is the plant.** A cell containing
    a city is dark for nearly every species in the catalogue, because that is
    where the people with cameras are -- the same collection bias
    `ecoregion_ranges` already discloses in its counts. The band says *how many
    times this was written down here*, never *how much of it grows here*, and
    :func:`caption` has to say so wherever the ramp is drawn.
    """
    n = int(count or 0)
    band = 0
    for i, edge in enumerate(DENSITY_BREAKS, start=1):
        if n >= edge:
            band = i
    return band


def build_document(by_species: dict, *, generated: str = "", source: str = "",
                   step: float = CELL_DEG) -> dict:
    """The shipped file: ``{species: [[lat, lng, records], ...]}`` + provenance.

    ``by_species`` values may be a ``{(lat, lng): count}`` mapping from
    :func:`cell_counts` or a bare sequence of cells, which counts as one record
    each -- a caller that only has presence should not have to invent a number.

    Cells are stored as bare arrays rather than objects. There are hundreds of
    thousands of them across the catalogue and a three-element array is a
    third the size of ``{"lat": .., "lng": .., "n": ..}``; the shape is
    documented in the file's own ``columns`` field so it reads without this
    docstring.
    """
    from datetime import date
    return {
        "version": 2,
        "generated": generated or date.today().isoformat(),
        "source": source or "derived from the GBIF occurrence cache",
        "cell_degrees": step,
        "columns": ["cell_lat_sw", "cell_lng_sw", "records"],
        "comment": (
            "Occupied cells of a {step} degree grid. A cell means at least one "
            "georeferenced record falls inside it. It does NOT mean the plant "
            "grows throughout the cell, and an empty cell is unrecorded rather "
            "than absent. The record count is how often the plant was written "
            "down in that square, which follows roads and towns as much as it "
            "follows the plant; it is not an abundance."
            .format(step=step)),
        "species": {name: _rows(cells)
                    for name, cells in sorted(by_species.items()) if cells},
    }


def _rows(cells) -> list:
    """``[[lat, lng, count], ...]`` from either accepted input shape."""
    items = (sorted(cells.items()) if isinstance(cells, dict)
             else [(c, 1) for c in sorted(cells)])
    return [[round(a, 4), round(b, 4), int(n)] for (a, b), n in items]


def parse_document(blob: dict) -> dict:
    """``{species: [(lat, lng, records), ...]}`` from the shipped file, or ``{}``.

    A version 1 row carried no count. It reads as one record rather than as
    zero, because the file only ever held cells that had at least one -- and
    reading a missing field as an absence is the mistake this repo has now made
    three times (see `docs/DATA_GAPS.md`).
    """
    out = {}
    for name, cells in ((blob or {}).get("species") or {}).items():
        rows = [(float(c[0]), float(c[1]),
                 int(c[2]) if len(c) >= 3 else 1)
                for c in cells or []
                if isinstance(c, (list, tuple)) and len(c) >= 2]
        if rows:
            out[name] = rows
    return out


def caption(cells, *, step: float = CELL_DEG) -> str:
    """What the shaded squares claim, for the page. ``""`` when there are none.

    Nothing recorded draws nothing and says nothing -- the same rule
    `phenology_bar` follows, for the same reason: an empty grid would assert
    that we checked everywhere and found it nowhere.
    """
    rows = list(cells or [])
    n = len(rows)
    if not n:
        return ""
    text = (f"{n:,} squares of about {CELL_KM_NS:.0f} km, each holding at least "
            f"one record. A square is not a claim that the plant grows "
            f"throughout it, and an unshaded square is unrecorded rather than "
            f"empty.")
    if any(len(row) >= 3 for row in rows):
        # Only said when the darkness is actually on the page. A caption that
        # explains a ramp the reader cannot see is noise, and one that leaves
        # an unexplained ramp on the page invites "dark means lots of it".
        text += (" Darker squares hold more records, which follows roads and "
                 "towns as much as it follows the plant.")
    return text
