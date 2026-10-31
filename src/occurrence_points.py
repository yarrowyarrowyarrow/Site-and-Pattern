"""
occurrence_points.py — the records themselves, as the website may publish them.

Design principle P9 — see docs/DESIGN_PHILOSOPHY.md.

Why the points and not only the grid
------------------------------------
V2.79 replaced the ecoregion shading with a 0.25 degree occupancy grid, which
is a much smaller claim: *at least one usable record falls inside this square*.
It is still a summary. The author's ask is the one a flora answers directly —
show the dots, and let the reader see **which kind of evidence** each one is:

    "The range picture (with the option to toggle the 2 kinds of observation
     data [catalogue vs iNaturalist]) should appear on the site too."

Those two kinds are a real distinction, not a filter convenience. A herbarium
specimen is a pressed sheet in a cabinet with a determination on it, which
somebody can go and re-examine. An iNaturalist observation is a photograph a
person uploaded, identified by community agreement. Both are evidence; they are
not the same evidence, and a map that merges them silently is asserting they
are.

What is in here and what is not
-------------------------------
**Only what a licence permits redrawing.** The rule lives in
`scripts/fetch_dataset_licences.PUBLISHABLE_COORDINATES` and is not restated
here. A dataset absent from the licence table is dropped: absent is not
permissive, the same rule the photograph pipeline runs on.

**Only Alberta and Saskatchewan.** F142's rule — 31.7% of the harvest sits
outside the two provinces this catalogue speaks for.

**Only records precise enough to draw.** `usable_points` refuses anything
coarser than 10 km, because a dot drawn from a county-centroid record is a
claim the record does not make.

One mark per 0.01 degree, and why that is not subsampling
---------------------------------------------------------
Records are deduplicated onto a 0.01 degree grid — about 1.1 km north-south,
and **under half a pixel** on the 640 px map this feeds. Two records 200 m
apart are already one dot; keeping both costs bytes and draws nothing.

That makes it a rendering decision rather than an editorial one, which matters,
because *subsampling* would be an editorial one and would need saying on the
page. Measured over the shipped cache: 365,092 records collapse to 171,881
marks, and the picture is identical. What the reader loses is the ability to
count dots — which was never a valid reading anyway, since dot density tracks
collection effort. :func:`caption` says so.
"""

from __future__ import annotations

#: Degrees to deduplicate marks onto. Sub-pixel at every width the site draws.
MARK_DEG = 0.01

#: The two evidence kinds, and the GBIF `basisOfRecord` that decides.
#: `PRESERVED_SPECIMEN` is the herbarium sheet; everything else that survives
#: the harvest filters is somebody's field observation.
SPECIMEN_BASIS = "PRESERVED_SPECIMEN"

#: Keys in the shipped file. Short because there are 171,881 of them.
KEY_SPECIMEN = "s"
KEY_OBSERVATION = "o"


def kind_of(point) -> str:
    """``"s"`` for a preserved specimen, ``"o"`` for anything else."""
    basis = (getattr(point, "basis", "") or "")
    return KEY_SPECIMEN if basis == SPECIMEN_BASIS else KEY_OBSERVATION


def marks(points, *, step: float = MARK_DEG) -> dict:
    """``{"s": [(lat, lng), ...], "o": [...]}`` — deduplicated, sorted.

    ``points`` are already filtered by the caller: this does not know about
    licences, provinces or coordinate uncertainty, and must not learn, or the
    three rules end up with two implementations each.

    Sorted so a re-run diffs cleanly.
    """
    seen: dict = {KEY_SPECIMEN: set(), KEY_OBSERVATION: set()}
    for point in points:
        lat = round(float(point[0]) / step) * step
        lng = round(float(point[1]) / step) * step
        seen[kind_of(point)].add((round(lat, 4), round(lng, 4)))
    return {k: sorted(v) for k, v in seen.items()}


def build_document(by_species: dict, *, generated: str = "", source: str = "",
                   step: float = MARK_DEG) -> dict:
    """The shipped file plus its provenance."""
    from datetime import date
    return {
        "version": 1,
        "generated": generated or date.today().isoformat(),
        "source": source or "derived from the GBIF occurrence cache",
        "mark_degrees": step,
        "columns": ["lat", "lng"],
        "comment": (
            "Occurrence records this project may redraw, split into 's' "
            "(preserved specimen) and 'o' (field observation). Deduplicated "
            "onto a {step} degree grid, which is under half a pixel on the "
            "map: two records closer than that were already one dot. Records "
            "outside Alberta and Saskatchewan, records coarser than 10 km, and "
            "records whose dataset licence does not permit redrawing the "
            "coordinate are all absent. The number of dots reflects how much "
            "collecting happened, not how much plant there is."
            .format(step=step)),
        "species": {
            name: {k: [[round(a, 4), round(b, 4)] for a, b in rows]
                   for k, rows in kinds.items() if rows}
            for name, kinds in sorted(by_species.items())
            if any(kinds.values())},
    }


def parse_document(blob: dict) -> dict:
    """``{species: {"s": [(lat, lng), ...], "o": [...]}}``, or ``{}``."""
    out: dict = {}
    for name, kinds in ((blob or {}).get("species") or {}).items():
        got = {}
        for key in (KEY_SPECIMEN, KEY_OBSERVATION):
            rows = [(float(c[0]), float(c[1])) for c in (kinds or {}).get(key)
                    or [] if isinstance(c, (list, tuple)) and len(c) >= 2]
            if rows:
                got[key] = rows
        if got:
            out[name] = got
    return out


def caption(kinds: dict) -> str:
    """What the dots claim, for the page. ``""`` when there are none.

    Nothing recorded says nothing — the `phenology_bar` rule (P9). An empty map
    with a confident caption would assert that we looked everywhere.
    """
    spec = len((kinds or {}).get(KEY_SPECIMEN) or [])
    obs = len((kinds or {}).get(KEY_OBSERVATION) or [])
    if not (spec or obs):
        return ""
    parts = []
    if spec:
        parts.append(f"{spec:,} herbarium specimen{'' if spec == 1 else 's'}")
    if obs:
        parts.append(f"{obs:,} field observation{'' if obs == 1 else 's'}")
    return (
        f"{' and '.join(parts)} this project may redraw. A filled dot is a "
        f"pressed sheet somebody can re-examine; a hollow ring is a "
        f"photograph identified by community agreement. Where the dots are "
        f"dense is where people have looked, not where the plant is "
        f"commonest, and empty ground is unsurveyed rather than unoccupied.")
