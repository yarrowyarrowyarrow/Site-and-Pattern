"""
community_regions.py — the ecoregions a plant community belongs in (V3.14).

Design principle P9 — see docs/DESIGN_PHILOSOPHY.md.

The owner, V3.14: "For plant communities there are none for aspen parkland or
most of the ecoregions." The library's habitat facet read ``plants.ecoregion``,
the column the occurrence derivation superseded at schema v59. On the shipped
catalogue that column names an ecoregion on 125 of 424 plants (Mixed Grassland
on 123) and Aspen Parkland on none, while ``plant_ecoregions`` records 336
species there. So 52 communities read Mixed Grassland and none Aspen Parkland,
and the Site tab's "Browse reference communities for this ecoregion" had
nothing to browse.

**The rule.** A community belongs in an ecoregion when *every* member whose range
is known has been recorded there. Every member, not most, for the reason the
Edmonton switch (F220) asks every member: a community is planted whole, and
"Aspen Parkland" on one whose Maximilian Sunflower has never been recorded there
would invite that plant in as a stranger. A member whose range is unknown
counts neither way, because absent is not "not there". Strongest first, by the
members' records in the region.

A member's range is what ``search_plants`` reads: its ``plant_ecoregions`` rows
when it has any, else the ecoregion-level tags in its column, so the plant
filter and the community filter cannot disagree about one plant.

Where the members share no ecoregion (17 of 68 seeded communities at V3.14,
nearly always by one plant), the community reads **Mixed regions**; with no
member's range known, **Not recorded**. Both read "Generalist" before, which
claims the opposite: that it would grow anywhere.

Riparian and wet meadow are conditions, not places: no coordinate records them.
They come from the members' column tags, any member, as before V3.14.
"""

from __future__ import annotations

import collections

#: The two answers that are not a place. Keys sit beside the ecoregion keys in a
#: community's ``regions``; the labels are what the facet and its folders read.
MIXED = "mixed_regions"
UNRECORDED = "not_recorded"
FALLBACK_LABELS = {MIXED: "Mixed regions", UNRECORDED: "Not recorded"}
#: Their second line in the habitat dropdown, which every row there has.
FALLBACK_NOTES = {MIXED: "its plants are recorded in no one region",
                  UNRECORDED: "no plant in it has a recorded range"}


def ranges_by_plant(conn) -> dict:
    """``{plant_id: {ecoregion: records}}`` from ``plant_ecoregions``, in one
    query. Empty before the table exists (a mid-migration database)."""
    import sqlite3                                          # noqa: PLC0415
    out: dict = collections.defaultdict(dict)
    try:
        rows = conn.execute("SELECT plant_id, ecoregion, occurrences "
                            "FROM plant_ecoregions").fetchall()
    except sqlite3.Error:
        return {}
    for row in rows:
        out[row[0]][row[1]] = int(row[2] or 0)
    return dict(out)


def _tokens(raw) -> list:
    return [t.strip() for t in (raw or "").split(",") if t.strip()]


def member_range(member: dict, ranges: dict) -> dict:
    """``{ecoregion: records}`` for one member row (``plant_id``, ``eco``):
    the derived rows, else the column's ecoregion-level tags at 0 records."""
    derived = ranges.get(member.get("plant_id"))
    if derived:
        return derived
    from src.ecoregion import geographic_keys               # noqa: PLC0415
    places = set(geographic_keys())
    return {t: 0 for t in _tokens(member.get("eco")) if t in places}


def community_regions(members, ranges: dict) -> list:
    """The keys a community is filed under: the ecoregions every member with a
    known range shares (strongest first), else :data:`MIXED` or
    :data:`UNRECORDED`; then the moisture niches any member carries, commonest
    first."""
    from src.ecoregion import is_moisture_niche              # noqa: PLC0415
    known = [r for r in (member_range(m, ranges) for m in members) if r]
    shared = set.intersection(*(set(r) for r in known)) if known else set()
    keys = sorted(shared, key=lambda k: (-sum(r[k] for r in known), k))
    if not keys:
        keys = [MIXED if known else UNRECORDED]
    niches = collections.Counter(
        t for m in members for t in _tokens(m.get("eco")) if is_moisture_niche(t))
    return keys + [t for t, _n in niches.most_common()]


def matches(regions, chosen) -> bool:
    """Whether a community filed under ``regions`` answers a filter on the keys
    ``chosen``: an ecozone, an ecoregion, an Alberta subregion, a niche or a
    fallback. Expanded along the lineage as the plant filter expands it, so a
    ticked ecozone finds every community in its ecoregions, and a subregion
    finds those in the ecoregions it lies in."""
    from src.ecoregion_tree import expand_for_filter         # noqa: PLC0415
    return bool(set(regions or ()) & set(expand_for_filter(chosen)))
