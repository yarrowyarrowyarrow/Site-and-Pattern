"""
ecoregion_ranges.py — which ecoregions a species is actually recorded from.

Design principle P9 — see docs/DESIGN_PHILOSOPHY.md (uncertainty is a feature:
ship ranges and confidence, never false precision).

The catalogue's ecoregion tags were generated heuristically and never sourced.
It shows: ``moist_mixedgrass`` sits on 246 of 434 plants and ``aspen_parkland``
on 136, in an Alberta-first app centred on Edmonton, and 39 native trees and
shrubs carry no parkland tag at all — including Saskatoon Berry, which is a
defining parkland shrub and which a user noticed missing.

The fix is not a better heuristic. It is to stop asserting range from a guess
and start deriving it from georeferenced occurrence records, keeping **the
count and the confidence beside every claim**, so "three records" and "three
hundred records" are visibly different statements.

This module is the derivation, with no network and no Qt in it. Occurrences
arrive as ``(lat, lng)`` pairs from whatever the caller wants — the real fetch
lives in ``scripts/seed_ecoregion_ranges.py`` (GBIF, run once at dev time and
the result committed), and the tests inject fixtures. Splitting it this way is
what makes the threshold rule testable at all: the interesting behaviour is
what happens at 2 records versus 3, and that must not require a download.

**Only geographic ecoregions are derived.** ``riparian`` and ``wet_meadow`` are
site-scale moisture niches, not regions — no occurrence coordinate can put a
species "in wet ground". Those tags stay as they are, asserted per species from
the literature, and this pipeline leaves them alone.
"""

from __future__ import annotations

from typing import Callable, Iterable, Sequence

# How many georeferenced records inside a region's polygons before we are
# willing to say the species grows there.
#
# Two is a coincidence — a misidentified herbarium sheet plus a garden escape
# will do it. Three is the smallest number that is evidence of anything, and it
# is reported as LOW confidence so nothing downstream mistakes it for a range
# map. Raising this would quietly re-create the original problem from the other
# direction: a real but under-collected region dropping off the list.
MIN_RECORDS = 3

# Confidence bands, by record count inside the region.
CONFIDENCE_BANDS: list[tuple[int, str]] = [
    (20, "high"),        # >= 20 records — a documented population
    (8,  "medium"),      # 8-19          — consistent, thinly collected
    (MIN_RECORDS, "low"),   # 3-7        — present, barely
]

CONFIDENCE_ORDER = ("high", "medium", "low")


def confidence_for(occurrences: int) -> str:
    """The confidence band a record count falls in, or ``""`` below the floor."""
    for floor, label in CONFIDENCE_BANDS:
        if occurrences >= floor:
            return label
    return ""


def _containment_lookup(lat: float, lng: float) -> list[str]:
    """The regions a coordinate is *inside*, with no proximity buffer.

    Separated from ``src.ecoregion.lookup_ecoregions`` by one keyword rather
    than duplicated, so the geometry has one implementation and the two
    questions asked of it stay visibly different. See
    :func:`ranges_for_species` for why range derivation must not use the
    buffered answer.
    """
    from src.ecoregion import lookup_ecoregions                 # noqa: PLC0415
    return lookup_ecoregions(lat, lng, near_m=0.0)


def ranges_for_species(
    occurrences: Iterable[Sequence[float]],
    *,
    lookup: Callable[[float, float], list[str]] | None = None,
    min_records: int = MIN_RECORDS,
) -> list[dict]:
    """Derive one species' ecoregion membership from its occurrence points.

    ``occurrences`` is an iterable of ``(lat, lng)``. Returns a list of
    ``{"ecoregion", "occurrences", "confidence"}`` sorted commonest first,
    excluding regions under ``min_records``.

    **A record counts for the region it is IN, and for no other (V2.75).**

    This docstring used to say the opposite — "a point in an overlap counts for
    both regions it falls in" — and it was true when it was written: V2.38's
    hand-traced placeholders deliberately overlapped at their shared edges, so
    a point really could be inside two. The surveyed ELC polygons adopted in
    V2.67 *tile*, and the overlap trick was replaced the same day by
    ``ecoregion._NEAR_BOUNDARY_M``, a 5 km proximity buffer written for a
    different question: *which ecoregion is this yard in*, where the outlines'
    ~1 km accuracy makes a near-boundary answer genuinely plural.

    This function inherited that buffer by defaulting its ``lookup``, and the
    shipped counts in ``data/plant_ecoregions.json`` were derived with it live.
    Measured over 4,000 random points inside the layer: **16.4% are credited to
    two or more ecoregions**. A record is evidence about one place; crediting
    it to every region within 5 km manufactures range, and it manufactures it
    in the direction that looks most like a real finding — a montane species
    acquiring parkland records at the mountain front.

    So the default lookup is now pinned to containment. Callers may still pass
    their own ``lookup``; what they may not do is get the site-detection
    behaviour here by accident.
    """
    if lookup is None:
        lookup = _containment_lookup

    counts: dict[str, int] = {}
    for point in occurrences:
        if point is None or len(point) < 2:
            continue
        lat, lng = point[0], point[1]
        if lat is None or lng is None:
            continue
        try:
            keys = lookup(float(lat), float(lng))
        except (TypeError, ValueError):
            continue
        for key in keys:
            counts[key] = counts.get(key, 0) + 1

    out = []
    for key, n in counts.items():
        if n < min_records:
            continue
        out.append({"ecoregion": key, "occurrences": n,
                    "confidence": confidence_for(n)})
    # Commonest first, then alphabetical so the file is stable between runs and
    # a diff shows real change rather than dict ordering.
    out.sort(key=lambda r: (-r["occurrences"], r["ecoregion"]))
    return out


def dropped_regions(
    occurrences: Iterable[Sequence[float]],
    *,
    lookup: Callable[[float, float], list[str]] | None = None,
    min_records: int = MIN_RECORDS,
) -> dict[str, int]:
    """Regions that had records but not enough of them, and how many.

    Reported by the script rather than discarded silently: a species sitting at
    two records in a region is the case a human should look at, and a pipeline
    that only prints what it kept cannot be audited (P9).
    """
    if lookup is None:
        lookup = _containment_lookup
    counts: dict[str, int] = {}
    for point in occurrences:
        if point is None or len(point) < 2:
            continue
        lat, lng = point[0], point[1]
        if lat is None or lng is None:
            continue
        try:
            keys = lookup(float(lat), float(lng))
        except (TypeError, ValueError):
            continue
        for key in keys:
            counts[key] = counts.get(key, 0) + 1
    return {k: n for k, n in sorted(counts.items()) if 0 < n < min_records}


# ── The shipped file ────────────────────────────────────────────────────────

FILE_VERSION = 1


def build_document(species_ranges: dict[str, list[dict]], *,
                   source: str, generated: str,
                   min_records: int = MIN_RECORDS) -> dict:
    """Wrap derived ranges in the shipped-file envelope.

    The envelope carries the *provenance of the whole run* — where the records
    came from, when, and what threshold was applied — because a per-row
    "confidence: high" means nothing without knowing what was being counted.
    """
    return {
        "version": FILE_VERSION,
        "generated": generated,
        "source": source,
        "min_records": min_records,
        "comment": (
            "Per-species ecoregion membership derived from georeferenced "
            "occurrence records by scripts/seed_ecoregion_ranges.py. Keyed by "
            "scientific name because plant ids are not stable across a reseed. "
            "Geographic ecoregions only — riparian and wet_meadow are "
            "site-scale moisture niches and are not derivable from a "
            "coordinate."
        ),
        "species": {name: rows for name, rows in sorted(species_ranges.items())},
    }


def parse_document(data: dict | None) -> dict[str, list[dict]]:
    """``{scientific_name: [{ecoregion, occurrences, confidence}, …]}``.

    Tolerant on purpose: a missing or malformed file means "nothing derived
    yet", and the read side then falls back to the catalogue's existing tags
    rather than showing a user an empty plant list.
    """
    if not isinstance(data, dict):
        return {}
    species = data.get("species")
    if not isinstance(species, dict):
        return {}
    out: dict[str, list[dict]] = {}
    for name, rows in species.items():
        if not isinstance(name, str) or not isinstance(rows, list):
            continue
        clean = []
        for row in rows:
            if not isinstance(row, dict):
                continue
            key = row.get("ecoregion")
            if not key:
                continue
            try:
                n = int(row.get("occurrences") or 0)
            except (TypeError, ValueError):
                n = 0
            conf = row.get("confidence") or confidence_for(n)
            if conf not in CONFIDENCE_ORDER:
                conf = "low"
            clean.append({"ecoregion": key, "occurrences": n,
                          "confidence": conf})
        if clean:
            out[name.strip()] = clean
    return out


def stale_keys(data: dict | None = None) -> set:
    """Derived keys the current polygon vocabulary does not define.

    Empty is the normal state. Non-empty means the polygons have moved since
    the last derivation run and these rows are keyed to regions that no longer
    exist — the window between adopting a new layer and re-running
    ``scripts/seed_ecoregion_ranges.py`` against it.

    **Why this is worth naming rather than leaving to a test.** A derived key
    that no longer exists is *inert*: it matches no filter, so the species
    quietly falls back to its heuristic tag and nothing looks broken. But a key
    that survives the change **by name** while its polygon moves is *wrong*,
    and looks exactly as confident as it did before. V2.67 had exactly one:
    ``aspen_parkland`` kept its key, and the traced polygon behind the old
    derivation overlaps the surveyed Aspen Parkland by only 40%. So during the
    window, 309 species assert a parkland range computed against ground that is
    substantially somewhere else — Scarlet Globemallow, a dry-prairie plant,
    reads "Aspen Parkland, 65 records, high confidence".

    That is not fixable by translation (see ``docs/plans/V2.68``): it needs the
    re-derivation. What is fixable is knowing you are in the window, which is
    what this answers. Pass ``data`` to check a document in hand; omit it to
    check the shipped file.
    """
    from src.ecoregion import geographic_keys                 # noqa: PLC0415

    if data is None:
        import json                                           # noqa: PLC0415

        from src.resources import resource_path               # noqa: PLC0415
        try:
            with open(resource_path("data", "plant_ecoregions.json"),
                      encoding="utf-8") as handle:
                data = json.load(handle)
        except Exception:                                     # noqa: BLE001
            return set()
    valid = set(geographic_keys())
    return {row["ecoregion"] for rows in parse_document(data).values()
            for row in rows if row["ecoregion"] not in valid}
