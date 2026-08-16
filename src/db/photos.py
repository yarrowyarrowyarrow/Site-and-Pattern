"""
src/db/photos.py — the photo-set query API (V2.35, schema v55, F70).

Design principle P5 (perception is constructed, not received) — see
docs/DESIGN_PHILOSOPHY.md.

``plants.image_url`` was ONE slot, and that single fact is most of what was
wrong with this app's photography. The selection criterion was never usefulness:
``scripts/fetch_inaturalist_images.py`` takes *the first photo whose licence is
redistributable*, which is the right rule for a licence filter and the wrong one
for a photograph. iNaturalist's leading photo is nearly always a macro of a
flower — the frame that identifies a plant to a botanist, and the least useful
one for deciding whether you want it in your yard or for finding it there in
May. With one column, improving the photo meant losing the other.

So: many photos per species, each in a named slot.

    habit       the whole plant, in context, with something for scale
    flower      the bloom, close
    leaf        foliage and arrangement — ID in the ten months it isn't flowering
    fruit       fruit or seed head
    bark_stem   bark, cane colour, stem section — winter ID; dogwood's whole case
    winter      the plant in January — what a yard looks like five months a year
    seedling    the first true leaves (F74: this one prevents weeding your own
                milkweed in its first May)

Two things this module is careful about, both with precedent in the codebase:

* **Keyed by ``scientific_name``, never ``plant_id``.** Plant ids are not stable
  across a reseed (``CLAUDE.md``) — a photo table keyed by id would silently
  re-point photos at the wrong species on some future schema bump and nobody
  would notice for months.
* **``origin`` decides what a reseed destroys.** ``'seed'`` rows are wiped and
  re-seeded; ``'user'`` rows never are. That single distinction is the whole of
  F72 — the obvious place to put a person's own photograph is
  ``plants.image_url``, and it is a trap, because the next schema bump deletes
  it.

Qt-free and read-mostly, mirroring :mod:`src.db.fauna`.
"""

from __future__ import annotations

import sqlite3
from typing import Optional

from src.db.plants import PHOTO_SLOTS, get_connection

# Re-exported so callers have one import for the vocabulary.
SLOTS = PHOTO_SLOTS

# What a slot is FOR, in one line — used by the curation bench and by the
# coverage report, so the description lives once.
SLOT_PURPOSE = {
    "habit": "the whole plant, in context, with something for scale",
    "flower": "the bloom, close",
    "leaf": "foliage and how the leaves sit on the stem",
    "fruit": "fruit or seed head",
    "bark_stem": "bark, cane colour, stem section — winter ID",
    "winter": "the plant in January",
    "seedling": "the first true leaves — what NOT to weed in May",
}

_SLOT_ORDER = {slot: i for i, slot in enumerate(PHOTO_SLOTS)}


def _rank(row: dict) -> tuple:
    """Sort key: preferred slot first, a person's own photo before a shipped one
    in the same slot, then the authored rank."""
    return (_SLOT_ORDER.get(row.get("slot"), 99),
            0 if row.get("origin") == "user" else 1,
            row.get("rank") or 0,
            row.get("id") or 0)


def photos_for(scientific_name: str, slot: str = "") -> list[dict]:
    """Every photo recorded for a species, best first. ``slot`` narrows it."""
    sci = (scientific_name or "").strip()
    if not sci:
        return []
    sql = "SELECT * FROM plant_photos WHERE scientific_name = ?"
    params: list = [sci]
    if slot:
        sql += " AND slot = ?"
        params.append(slot)
    conn = get_connection()
    try:
        rows = [dict(r) for r in conn.execute(sql, params).fetchall()]
    except sqlite3.OperationalError:
        return []                       # pre-v55 DB — the caller falls back
    finally:
        conn.close()
    return sorted(rows, key=_rank)


def best_photo(scientific_name: str) -> Optional[dict]:
    """The one photo to show when there is room for one. See the slot order."""
    shots = photos_for(scientific_name)
    return shots[0] if shots else None


def add_photo(scientific_name: str, slot: str, url: str, *,
              attribution: str = "", license: str = "",  # noqa: A002
              source: str = "", origin: str = "user",
              taken_on: str = "", rank: int = 0, notes: str = "") -> int:
    """Record a photo. Returns the new row id, or 0 if it was rejected.

    ``origin`` defaults to ``'user'`` on purpose: the risky mistake is a
    person's own photograph being written as shipped data and destroyed by the
    next reseed, and a default should fail in the safe direction.
    """
    sci = (scientific_name or "").strip()
    url = (url or "").strip()
    if not sci or not url or slot not in PHOTO_SLOTS:
        return 0
    # Collapse whitespace in the credit (V2.62). iNaturalist attribution
    # strings arrive with embedded newlines — one real import produced
    # "(c) \nKENPEI, some rights reserved (CC BY)" — and a credit is a single
    # line wherever it is shown, so a stray break renders as a broken caption
    # under somebody's photograph.
    attribution = " ".join((attribution or "").split())
    notes = " ".join((notes or "").split())
    conn = get_connection()
    try:
        cur = conn.execute(
            "INSERT INTO plant_photos (scientific_name, slot, url, attribution,"
            " license, source, origin, taken_on, rank, notes)"
            " VALUES (?,?,?,?,?,?,?,?,?,?)",
            (sci, slot, url, attribution, license, source,
             "seed" if origin == "seed" else "user", taken_on, int(rank), notes))
        conn.commit()
        return int(cur.lastrowid or 0)
    finally:
        conn.close()


def remove_photo(photo_id: int) -> bool:
    """Delete one photo row. Returns whether anything was removed."""
    conn = get_connection()
    try:
        cur = conn.execute("DELETE FROM plant_photos WHERE id = ?", (int(photo_id),))
        conn.commit()
        return cur.rowcount > 0
    finally:
        conn.close()


def coverage() -> dict:
    """How much of the catalogue actually has photographs, per slot.

    The number this exists to make visible: ``src.data_quality`` has always
    checked that a bee photo is licensed correctly and had NO OPINION about 62
    of 69 bees having no photo at all. A gap nothing counts is a gap nobody
    closes.

    Returns ``{"species": n, "with_any": n, "by_slot": {slot: n}, "missing":
    [scientific_name, …]}`` — ``missing`` is the work list.
    """
    conn = get_connection()
    try:
        names = [r[0] for r in conn.execute(
            "SELECT scientific_name FROM plants"
            " WHERE scientific_name IS NOT NULL AND scientific_name <> ''"
        ).fetchall()]
        try:
            rows = conn.execute(
                "SELECT scientific_name, slot FROM plant_photos").fetchall()
        except sqlite3.OperationalError:
            rows = []
    finally:
        conn.close()

    have: dict[str, set] = {}
    for sci, slot in rows:
        have.setdefault(sci, set()).add(slot)
    by_slot = {slot: sum(1 for s in have.values() if slot in s)
               for slot in PHOTO_SLOTS}
    return {
        "species": len(names),
        "with_any": sum(1 for n in names if have.get(n)),
        "by_slot": by_slot,
        "missing": sorted(n for n in names if not have.get(n)),
    }
