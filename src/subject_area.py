"""
subject_area.py — is this coordinate on ground this catalogue speaks for?

Design principle P9 — see docs/DESIGN_PHILOSOPHY.md.

Why this is its own module
--------------------------
``ecoregion_basemap`` draws the ground. This answers a different question about
it, and the two were briefly in one file until the architecture guard said so.
The boundary is worth keeping: everything there is a picture, everything here
is a decision about whether a piece of evidence is in scope.

Why it exists at all (F142, V2.78)
----------------------------------
``scripts/seed_ecoregion_ranges.py`` asks GBIF for records inside the polygon
layer's **bounding box** plus half a degree. That box runs west to -120.5 and
south to 48.5, so it takes in a wedge of British Columbia, a strip of Montana
and North Dakota, the Manitoba edge and a slice of the Northwest Territories.

The derivation ignores every one of them correctly. The *drawing* did not:
``map_svg`` emitted its overlay seam outside the group it clips to the subject
provinces, so **175,876 of 555,477 cached records (31.7%)** were plotted over
ground the layer has no authority over, on maps whose entire argument is about
what a shaded region claims. The author spotted it as "some spillover into BC".

**The province outline alone is not the test, and that is the whole design.**
``data/basemap_prairie.geojson`` is Natural Earth at 1:10m: Alberta and
Saskatchewan come to **193 vertices between them**. That is fine for drawing
and much too coarse for adjudicating a record along the continental divide,
where the border is a wiggle and the mountains are full of collections.
Dropping a real Banff specimen because our basemap cut a corner would be the
same class of error as the 5 km buffer V2.75 removed: a display simplification
reaching into a claim.

So a point is ours if it is inside the coarse outline **or** inside any
surveyed ecoregion polygon. The cheap test settles almost everything and only
the disputed edge pays for the detailed one.

Related but deliberately separate: ``site_facets.SUBJECT_PROVINCES`` is the
same two provinces as a *vocabulary* for the website's filters. One is a list
of codes, the other is geometry, and merging them would put a polygon lookup
behind a filter chip.
"""

from __future__ import annotations

_SUBJECT_RINGS = None


def _subject_rings() -> list:
    """Alberta and Saskatchewan as rings, with a bounding box each.

    Built once. Two rings and 193 vertices between them, which is coarse — see
    :func:`in_subject_provinces` for why that is deliberately not the whole
    test.
    """
    from src.ecoregion_basemap import _rings, layer            # noqa: PLC0415
    global _SUBJECT_RINGS
    if _SUBJECT_RINGS is None:
        rings = []
        for feature in layer("province"):
            if not (feature.get("properties") or {}).get("subject"):
                continue
            for ring in _rings(feature.get("geometry") or {}):
                lons = [float(c[0]) for c in ring]
                lats = [float(c[1]) for c in ring]
                rings.append((min(lats), max(lats), min(lons), max(lons), ring))
        _SUBJECT_RINGS = rings
    return _SUBJECT_RINGS


def in_subject_provinces(lat: float, lng: float) -> bool:
    """Is this coordinate on ground this catalogue speaks for?

    **Why this exists (F142, V2.78).** ``map_svg``'s ``overlay`` seam is
    emitted outside the subject clip group, so ``plot_occurrences`` drew every
    record it was handed — and the GBIF harvest is bounded by the polygon
    *bounding box* plus half a degree, which reaches deep into British
    Columbia, Montana, Manitoba and the Northwest Territories. Those records
    are correctly ignored by the range derivation and were being drawn anyway:
    dots over ground the layer has no authority over, on a map whose whole
    argument is about what a shaded region claims. The author spotted it as
    "some spillover into BC".

    **The province outline alone is not the test.** It is Natural Earth at
    1:10m and 193 vertices, which is fine for drawing and much too coarse for
    deciding a record's fate along the continental divide, where the border is
    a wiggle and the mountains are full of collections. Dropping a real Banff
    specimen because our basemap cut a corner would be the same class of error
    as the 5 km buffer: a display simplification reaching into a claim.

    So a point counts as ours if it is inside the coarse province outline **or**
    inside any surveyed ecoregion polygon. The cheap test runs first and settles
    almost everything; only the disputed edge pays for the detailed one.
    """
    from src.geometry import point_in_ring                    # noqa: PLC0415
    for lat_min, lat_max, lng_min, lng_max, ring in _subject_rings():
        if not (lat_min <= lat <= lat_max and lng_min <= lng <= lng_max):
            continue
        if point_in_ring(lat, lng, ring):
            return True
    from src.ecoregion_ranges import _containment_lookup      # noqa: PLC0415
    return bool(_containment_lookup(lat, lng))


