"""
fauna.py — Query API for the fauna registry and plant ↔ fauna junction.

Introduced in schema v13 (V1.31). Replaces the generic ``host_plant`` tag with
real species-level relationships between plants and the lepidoptera, birds,
and native bees they support.

Design principle P3 (relationships matter more than components) and P10 (design
for relationships, not objects) — see docs/DESIGN_PHILOSOPHY.md.
"""

from __future__ import annotations

import sqlite3
from typing import Optional

from src.db.plants import get_connection


def _row_to_dict(row: sqlite3.Row) -> dict:
    return dict(row) if row is not None else {}


# ── Lookups ───────────────────────────────────────────────────────────────────

def get_fauna(fauna_id: int) -> Optional[dict]:
    conn = get_connection()
    try:
        row = conn.execute(
            "SELECT * FROM fauna WHERE id = ?", (fauna_id,)
        ).fetchone()
        return _row_to_dict(row) if row else None
    finally:
        conn.close()


def list_fauna(taxon: str = "") -> list[dict]:
    """Return all fauna rows, optionally filtered to a single taxon."""
    conn = get_connection()
    try:
        if taxon:
            rows = conn.execute(
                "SELECT * FROM fauna WHERE taxon = ? ORDER BY common_name",
                (taxon,),
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT * FROM fauna ORDER BY taxon, common_name"
            ).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


# ── Plant → fauna ─────────────────────────────────────────────────────────────

def fauna_for_plant(plant_id: int) -> list[dict]:
    """
    Return every fauna species that uses ``plant_id`` for any biological
    relationship, with the relationship + specificity attached. Sorted by
    taxon then common_name.
    """
    conn = get_connection()
    try:
        rows = conn.execute(
            """SELECT f.*, pf.relationship, pf.specificity, pf.source, pf.notes
               FROM plant_fauna pf
               JOIN fauna f ON f.id = pf.fauna_id
               WHERE pf.plant_id = ?
               ORDER BY f.taxon, f.common_name""",
            (plant_id,),
        ).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


def fauna_for_plants(plant_ids: list[int]) -> list[dict]:
    """Return fauna rows for every plant in ``plant_ids`` (with relationship
    columns). Result rows include ``plant_id`` so callers can group.

    Empty ``plant_ids`` → ``[]``.
    """
    if not plant_ids:
        return []
    conn = get_connection()
    try:
        qmarks = ",".join("?" * len(plant_ids))
        rows = conn.execute(
            f"""SELECT pf.plant_id, f.*, pf.relationship, pf.specificity
                FROM plant_fauna pf
                JOIN fauna f ON f.id = pf.fauna_id
                WHERE pf.plant_id IN ({qmarks})""",
            list(plant_ids),
        ).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


# ── Fauna → plant ─────────────────────────────────────────────────────────────

def plants_for_fauna(fauna_id: int, relationship: str = "") -> list[dict]:
    """
    Plants that support ``fauna_id``. If ``relationship`` is given (e.g.
    ``'larval_host'``), filter to that relationship.
    """
    conn = get_connection()
    try:
        if relationship:
            rows = conn.execute(
                """SELECT p.*, pf.relationship, pf.specificity
                   FROM plant_fauna pf
                   JOIN plants p ON p.id = pf.plant_id
                   WHERE pf.fauna_id = ? AND pf.relationship = ?
                   ORDER BY p.common_name""",
                (fauna_id, relationship),
            ).fetchall()
        else:
            rows = conn.execute(
                """SELECT p.*, pf.relationship, pf.specificity
                   FROM plant_fauna pf
                   JOIN plants p ON p.id = pf.plant_id
                   WHERE pf.fauna_id = ?
                   ORDER BY p.common_name""",
                (fauna_id,),
            ).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


# ── Aggregates for the Habitat Value Score ────────────────────────────────────

def lepidoptera_supported_by_plants(plant_ids: list[int]) -> set[int]:
    """
    Return the set of distinct lepidoptera fauna_ids that are larval-hosted
    by at least one plant in ``plant_ids``. This is the ecological-network
    metric for the Habitat Value Score's wildlife component.

    Empty input → empty set.
    """
    if not plant_ids:
        return set()
    conn = get_connection()
    try:
        qmarks = ",".join("?" * len(plant_ids))
        rows = conn.execute(
            f"""SELECT DISTINCT pf.fauna_id
                FROM plant_fauna pf
                JOIN fauna f ON f.id = pf.fauna_id
                WHERE pf.relationship = 'larval_host'
                  AND f.taxon = 'lepidoptera'
                  AND pf.plant_id IN ({qmarks})""",
            list(plant_ids),
        ).fetchall()
        return {r[0] for r in rows}
    finally:
        conn.close()


def fauna_supported_by_plants(
    plant_ids: list[int],
    taxon: str = "",
    relationship: str = "",
) -> set[int]:
    """
    Generalised version of ``lepidoptera_supported_by_plants``. Returns the
    set of distinct fauna_ids supported by ``plant_ids`` under the supplied
    filters (both optional). Used by the analysis panel's per-taxon summaries.
    """
    if not plant_ids:
        return set()
    conn = get_connection()
    try:
        qmarks = ",".join("?" * len(plant_ids))
        sql = (
            "SELECT DISTINCT pf.fauna_id FROM plant_fauna pf "
            "JOIN fauna f ON f.id = pf.fauna_id "
            f"WHERE pf.plant_id IN ({qmarks})"
        )
        params: list = list(plant_ids)
        if taxon:
            sql += " AND f.taxon = ?"
            params.append(taxon)
        if relationship:
            sql += " AND pf.relationship = ?"
            params.append(relationship)
        rows = conn.execute(sql, params).fetchall()
        return {r[0] for r in rows}
    finally:
        conn.close()


def keystone_rank_lepidoptera(plant_id: int) -> int:
    """
    Number of distinct lepidoptera species for which this plant is a
    documented larval host. Tallamy-style "keystone" metric.
    """
    conn = get_connection()
    try:
        row = conn.execute(
            """SELECT COUNT(DISTINCT pf.fauna_id) AS n
               FROM plant_fauna pf
               JOIN fauna f ON f.id = pf.fauna_id
               WHERE pf.plant_id = ?
                 AND pf.relationship = 'larval_host'
                 AND f.taxon = 'lepidoptera'""",
            (plant_id,),
        ).fetchone()
        return int(row[0]) if row else 0
    finally:
        conn.close()
