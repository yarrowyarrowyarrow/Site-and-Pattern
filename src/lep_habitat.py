"""
lep_habitat.py — "Fly as a butterfly": turn the Alberta Lepidoptera data spine
into the two plant selections the 3D fly-through needs for a chosen butterfly or
moth (F37, the "see what a pollinator sees" family).

Two relationships matter, and they are kept distinct on purpose (P3/P10 —
relationships are the product; P8 — habitat is built *for* a life stage):

  1. Nectar plants — what the ADULT drinks from. These become the collectable,
     bloom-gated nectar beacons in the fly-through. Sourced from documented
     ``plant_fauna`` nectar edges plus a genus-level fallback from the species'
     ``lepidoptera_attributes.nectar_flower_genera``. Honest about non-feeders
     (P9): giant silk moths and some sphinxes have vestigial mouthparts, so their
     nectar list is deliberately empty — the fly-through shows no nectar for them,
     only host plants.

  2. Larval host plants — where the CATERPILLAR feeds (and the female lays eggs).
     These become the "caterpillar nursery" markers. Sourced from the rich
     documented ``plant_fauna`` ``larval_host`` edges the app already ships.

Qt-free by design: reads through ``src.db.fauna`` and returns plain data so the
3D window (and, later, an analysis lens) can share one "chosen butterfly →
relevant plants" selection — mirroring ``src.bee_habitat``.

Design principle P3, P10, P8, P5, P9 — see docs/DESIGN_PHILOSOPHY.md.
"""

from __future__ import annotations

from typing import Optional

from src.db import fauna as _fauna
from src.habitat_score import parse_month_range


# ── Selector ──────────────────────────────────────────────────────────────────

def list_target_lepidoptera() -> list[dict]:
    """Return every butterfly/moth the user can target in the fly-through, with
    the display + behavioural fields the viewer needs (kind → avatar, activity →
    day/night hint, flight_season → the seasonal tour). Butterflies sort ahead
    of skippers ahead of moths (see ``list_lepidoptera_with_attributes``)."""
    out: list[dict] = []
    for row in _fauna.list_lepidoptera_with_attributes():
        out.append({
            "id": row["id"],
            "scientific_name": row.get("scientific_name", ""),
            "common_name": row.get("common_name", ""),
            "kind": row.get("lep_kind") or "butterfly",
            "activity": row.get("activity") or "day",
            "flight_season": row.get("flight_season"),
            "overwintering_stage": row.get("overwintering_stage"),
            "nectar_flower_genera": row.get("nectar_flower_genera"),
            "conservation_status": row.get("conservation_status"),
            "image_url": row.get("image_url", ""),
        })
    return out


# ── Plant selections ──────────────────────────────────────────────────────────

def _genera_list(csv: Optional[str]) -> list[str]:
    return [g.strip() for g in (csv or "").split(",") if g.strip()]


def nectar_plant_ids_for_lep(fauna_id: int) -> list[int]:
    """DB plant ids the ADULT nectars at: documented ``plant_fauna`` nectar edges
    unioned with a genus fallback from ``nectar_flower_genera``. Empty for
    non-feeding adults (their ``nectar_flower_genera`` is NULL) — never guessed.
    These drive the fly-through's collectable nectar beacons (bloom-gated in the
    viewer against the scene month)."""
    ids: set[int] = set()
    for p in _fauna.plants_for_fauna(fauna_id, relationship="nectar"):
        ids.add(p["id"])
    attrs = _fauna.lep_attributes_for(fauna_id)
    genera = _genera_list(attrs.get("nectar_flower_genera"))
    if genera:
        for p in _fauna.plants_in_genera(genera):
            ids.add(p["id"])
    return sorted(ids)


def larval_host_ids_for_lep(fauna_id: int) -> list[int]:
    """DB plant ids the CATERPILLAR feeds on (documented ``larval_host`` edges).
    These drive the fly-through's "caterpillar nursery" markers — shown whenever
    the host plant is present in the design, independent of bloom."""
    return sorted({p["id"]
                   for p in _fauna.plants_for_fauna(fauna_id, relationship="larval_host")})


def flight_months_for_lep(fauna_id: int) -> list[int]:
    """The months (1-12) the adult is on the wing, parsed from ``flight_season``.
    Empty when undocumented — the seasonal tour then spans the whole year rather
    than guessing a window (P9)."""
    attrs = _fauna.lep_attributes_for(fauna_id)
    return parse_month_range(attrs.get("flight_season") or "")
