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


# ── Bee attributes (F37 "see what a bee sees") ────────────────────────────────

def bee_attributes_for(fauna_id: int) -> dict:
    """Return the ``bee_attributes`` row for ``fauna_id`` (or ``{}`` if the
    fauna row is not a bee / has no attributes seeded)."""
    conn = get_connection()
    try:
        row = conn.execute(
            "SELECT * FROM bee_attributes WHERE fauna_id = ?", (fauna_id,)
        ).fetchone()
        return _row_to_dict(row) if row else {}
    finally:
        conn.close()


def list_bees_with_attributes() -> list[dict]:
    """Return every bee in the fauna registry LEFT JOIN its bee_attributes,
    so callers get name/image fields alongside nesting/tongue/season. Bees
    with no seeded attributes still appear (attribute columns are NULL).
    Sorted by genus then common_name so the UI can group by genus."""
    conn = get_connection()
    try:
        rows = conn.execute(
            """SELECT f.*,
                      ba.genus              AS bee_genus,
                      ba.nesting_habit      AS nesting_habit,
                      ba.host_genus         AS host_genus,
                      ba.tongue_length      AS tongue_length,
                      ba.flight_season      AS flight_season,
                      ba.floral_host_genera AS floral_host_genera,
                      ba.pollen_specialist  AS pollen_specialist,
                      ba.conservation_status AS conservation_status
               FROM fauna f
               LEFT JOIN bee_attributes ba ON ba.fauna_id = f.id
               WHERE f.taxon = 'bee'
               ORDER BY COALESCE(ba.genus, f.scientific_name), f.common_name""",
        ).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


# ── Lepidoptera attributes (F37 "fly as a butterfly") ─────────────────────────

def lep_attributes_for(fauna_id: int) -> dict:
    """Return the ``lepidoptera_attributes`` row for ``fauna_id`` (or ``{}`` if
    the fauna row is not a butterfly/moth / has no attributes seeded)."""
    conn = get_connection()
    try:
        row = conn.execute(
            "SELECT * FROM lepidoptera_attributes WHERE fauna_id = ?", (fauna_id,)
        ).fetchone()
        return _row_to_dict(row) if row else {}
    finally:
        conn.close()


def list_lepidoptera_with_attributes() -> list[dict]:
    """Return every lepidopteran in the fauna registry LEFT JOIN its
    ``lepidoptera_attributes``, so callers get name/image fields alongside
    flight season, kind, activity and overwintering stage. Species with no
    seeded attributes still appear (attribute columns are NULL). Sorted so
    butterflies group ahead of moths, then by common name."""
    conn = get_connection()
    try:
        rows = conn.execute(
            """SELECT f.*,
                      la.kind                AS lep_kind,
                      la.activity            AS activity,
                      la.flight_season       AS flight_season,
                      la.overwintering_stage AS overwintering_stage,
                      la.voltinism           AS voltinism,
                      la.nectar_flower_genera AS nectar_flower_genera,
                      la.larval_host_note    AS larval_host_note,
                      la.conservation_status AS conservation_status
               FROM fauna f
               LEFT JOIN lepidoptera_attributes la ON la.fauna_id = f.id
               WHERE f.taxon = 'lepidoptera'
               ORDER BY CASE la.kind WHEN 'butterfly' THEN 0 WHEN 'skipper' THEN 1
                                     WHEN 'moth' THEN 2 ELSE 3 END,
                        f.common_name""",
        ).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


def plants_in_genera(genera: list[str]) -> list[dict]:
    """Return plant rows whose scientific-name genus (the first token) is one of
    ``genera`` (case-insensitive). Used by the bee habitat builder's genus-level
    floral-host fallback when there is no curated plant↔bee edge.

    Empty ``genera`` → ``[]``.
    """
    if not genera:
        return []
    conn = get_connection()
    try:
        qmarks = ",".join("?" * len(genera))
        # Genus = characters up to the first space (INSTR on 'name ' guarantees a
        # match even for a single-token scientific_name). Compared upper-cased.
        rows = conn.execute(
            f"""SELECT * FROM plants
                WHERE UPPER(SUBSTR(scientific_name, 1,
                                   INSTR(scientific_name || ' ', ' ') - 1))
                      IN ({qmarks})
                ORDER BY common_name""",
            [g.upper() for g in genera],
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
