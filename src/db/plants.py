"""
plants.py — SQLite database access layer for the plant catalogue.

The database file is created automatically on first use at data/permadesign.db
(relative to the project root).  If the plants table is empty the seed data
is loaded automatically.
"""

import os
import sqlite3
from typing import Optional

# ── Paths ─────────────────────────────────────────────────────────────────────

_HERE        = os.path.dirname(os.path.abspath(__file__))
_PROJECT_ROOT = os.path.dirname(os.path.dirname(_HERE))
_DATA_DIR    = os.path.join(_PROJECT_ROOT, "data")
_DB_PATH     = os.path.join(_DATA_DIR, "permadesign.db")
_SCHEMA_PATH = os.path.join(_HERE, "schema.sql")


def _ensure_data_dir():
    os.makedirs(_DATA_DIR, exist_ok=True)


# ── Connection (per-call; SQLite is fast for local files) ─────────────────────

def get_connection() -> sqlite3.Connection:
    _ensure_data_dir()
    conn = sqlite3.connect(_DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


# ── Schema + seed bootstrap ───────────────────────────────────────────────────

def init_db() -> None:
    """
    Create tables (if absent) and seed the plant catalogue (if empty).
    Safe to call multiple times.
    """
    _ensure_data_dir()
    conn = get_connection()
    try:
        with open(_SCHEMA_PATH, "r", encoding="utf-8") as f:
            conn.executescript(f.read())
        conn.commit()

        # Auto-seed if empty
        if conn.execute("SELECT COUNT(*) FROM plants").fetchone()[0] == 0:
            from src.db.seed_data import SEED_PLANTS
            _insert_plants(conn, SEED_PLANTS)
    finally:
        conn.close()


def _insert_plants(conn: sqlite3.Connection, plants: list[tuple]) -> None:
    conn.executemany(
        """INSERT INTO plants
           (common_name, scientific_name, plant_type,
            hardiness_zone_min, hardiness_zone_max,
            sun_requirement, water_needs,
            native_region, permaculture_uses,
            spacing_meters, mature_height_meters, notes)
           VALUES (?,?,?,?,?,?,?,?,?,?,?,?)""",
        plants
    )
    conn.commit()


# ── Queries ───────────────────────────────────────────────────────────────────

def _row_to_dict(row: sqlite3.Row) -> dict:
    return dict(row)


def get_all_plants() -> list[dict]:
    conn = get_connection()
    try:
        rows = conn.execute(
            "SELECT * FROM plants ORDER BY plant_type, common_name"
        ).fetchall()
        return [_row_to_dict(r) for r in rows]
    finally:
        conn.close()


def get_plant(plant_id: int) -> Optional[dict]:
    conn = get_connection()
    try:
        row = conn.execute(
            "SELECT * FROM plants WHERE id = ?", (plant_id,)
        ).fetchone()
        return _row_to_dict(row) if row else None
    finally:
        conn.close()


def search_plants(
    query: str = "",
    plant_type: str = "",
    sun_req: str = "",
    water_needs: str = "",
    perm_use: str = "",
    zone: Optional[int] = None,
) -> list[dict]:
    """
    Return plants matching all supplied filters.
    Empty string / None values for a filter means "no restriction".
    """
    sql    = "SELECT * FROM plants WHERE 1=1"
    params: list = []

    if query:
        sql += " AND (LOWER(common_name) LIKE ? OR LOWER(scientific_name) LIKE ?)"
        q = f"%{query.lower()}%"
        params += [q, q]

    if plant_type:
        sql += " AND plant_type = ?"
        params.append(plant_type)

    if sun_req:
        sql += " AND sun_requirement = ?"
        params.append(sun_req)

    if water_needs:
        sql += " AND water_needs = ?"
        params.append(water_needs)

    if perm_use:
        sql += " AND (',' || permaculture_uses || ',') LIKE ?"
        params.append(f"%,{perm_use},%")

    if zone is not None:
        sql += " AND hardiness_zone_min <= ? AND hardiness_zone_max >= ?"
        params += [zone, zone]

    sql += " ORDER BY plant_type, common_name"

    conn = get_connection()
    try:
        rows = conn.execute(sql, params).fetchall()
        return [_row_to_dict(r) for r in rows]
    finally:
        conn.close()


def get_distinct_types() -> list[str]:
    conn = get_connection()
    try:
        rows = conn.execute(
            "SELECT DISTINCT plant_type FROM plants ORDER BY plant_type"
        ).fetchall()
        return [r[0] for r in rows]
    finally:
        conn.close()


def get_distinct_permaculture_uses() -> list[str]:
    """Return a sorted list of every unique permaculture use tag."""
    conn = get_connection()
    try:
        rows = conn.execute(
            "SELECT permaculture_uses FROM plants WHERE permaculture_uses IS NOT NULL"
        ).fetchall()
    finally:
        conn.close()

    uses: set[str] = set()
    for row in rows:
        for tag in row[0].split(","):
            tag = tag.strip()
            if tag:
                uses.add(tag)
    return sorted(uses)
