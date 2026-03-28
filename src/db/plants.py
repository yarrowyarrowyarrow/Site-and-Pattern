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

# Current schema version — bump when adding columns/tables
_SCHEMA_VERSION = 2


def _ensure_data_dir():
    os.makedirs(_DATA_DIR, exist_ok=True)


# ── Connection (per-call; SQLite is fast for local files) ─────────────────────

def get_connection() -> sqlite3.Connection:
    _ensure_data_dir()
    conn = sqlite3.connect(_DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


# ── Schema + seed bootstrap ───────────────────────────────────────────────────

def _get_schema_version(conn: sqlite3.Connection) -> int:
    try:
        row = conn.execute("SELECT version FROM _schema_version").fetchone()
        return row[0] if row else 0
    except sqlite3.OperationalError:
        return 0


def _set_schema_version(conn: sqlite3.Connection, version: int):
    conn.execute(
        "CREATE TABLE IF NOT EXISTS _schema_version (version INTEGER NOT NULL)"
    )
    conn.execute("DELETE FROM _schema_version")
    conn.execute("INSERT INTO _schema_version VALUES (?)", (version,))
    conn.commit()


def _migrate_to_v2(conn: sqlite3.Connection):
    """Add columns introduced in schema v2 to an existing plants table."""
    new_columns = [
        ("bloom_period",       "TEXT"),
        ("fruit_period",       "TEXT"),
        ("native_to_alberta",  "INTEGER DEFAULT 0"),
        ("edible_parts",       "TEXT"),
        ("deciduous_evergreen","TEXT"),
        ("soil_ph_min",        "REAL"),
        ("soil_ph_max",        "REAL"),
        ("perennial_or_annual","TEXT"),
    ]
    for col_name, col_def in new_columns:
        try:
            conn.execute(f"ALTER TABLE plants ADD COLUMN {col_name} {col_def}")
        except sqlite3.OperationalError:
            pass  # column already present

    # Create companion tables (idempotent via schema.sql CREATE IF NOT EXISTS)
    conn.commit()


def init_db() -> None:
    """
    Create tables (if absent), run migrations, and seed the plant catalogue
    if it is empty or outdated.  Safe to call multiple times.
    """
    _ensure_data_dir()
    conn = get_connection()
    try:
        # Apply full schema (creates any missing tables)
        with open(_SCHEMA_PATH, "r", encoding="utf-8") as f:
            conn.executescript(f.read())
        conn.commit()

        current_version = _get_schema_version(conn)

        if current_version < 2:
            _migrate_to_v2(conn)

        # Reseed if empty, count is low, or schema was just upgraded
        count = conn.execute("SELECT COUNT(*) FROM plants").fetchone()[0]
        needs_reseed = (count < 52) or (current_version < 2 and count > 0)

        if needs_reseed:
            conn.execute("DELETE FROM plants")
            conn.execute("DELETE FROM companion_friends")
            conn.execute("DELETE FROM companion_enemies")
            conn.commit()
            from src.db.seed_data import SEED_PLANTS
            _insert_plants(conn, SEED_PLANTS)
            from src.db.seed_data import SEED_COMPANIONS
            _insert_companions(conn, SEED_COMPANIONS)

        _set_schema_version(conn, _SCHEMA_VERSION)
    finally:
        conn.close()


def _insert_plants(conn: sqlite3.Connection, plants: list[tuple]) -> None:
    conn.executemany(
        """INSERT INTO plants
           (common_name, scientific_name, plant_type,
            hardiness_zone_min, hardiness_zone_max,
            sun_requirement, water_needs,
            native_region, permaculture_uses,
            spacing_meters, mature_height_meters, notes,
            bloom_period, fruit_period, native_to_alberta,
            edible_parts, deciduous_evergreen,
            soil_ph_min, soil_ph_max, perennial_or_annual)
           VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
        plants
    )
    conn.commit()


def _insert_companions(conn: sqlite3.Connection,
                       companions: list[tuple]) -> None:
    """
    companions: list of (common_name_a, common_name_b, relationship)
    relationship: 'friend' | 'enemy'
    Resolved to IDs at insert time; silently skips unknown names.
    """
    name_to_id: dict[str, int] = {}
    for row in conn.execute("SELECT id, common_name FROM plants"):
        name_to_id[row["common_name"]] = row["id"]

    friends: list[tuple] = []
    enemies: list[tuple] = []
    for name_a, name_b, rel in companions:
        id_a = name_to_id.get(name_a)
        id_b = name_to_id.get(name_b)
        if id_a is None or id_b is None:
            continue
        lo, hi = min(id_a, id_b), max(id_a, id_b)
        if rel == "friend":
            friends.append((lo, hi))
        elif rel == "enemy":
            enemies.append((lo, hi))

    if friends:
        conn.executemany(
            "INSERT OR IGNORE INTO companion_friends VALUES (?,?)", friends
        )
    if enemies:
        conn.executemany(
            "INSERT OR IGNORE INTO companion_enemies VALUES (?,?)", enemies
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
    native_only: bool = False,
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

    if native_only:
        sql += " AND native_to_alberta = 1"

    sql += " ORDER BY plant_type, common_name"

    conn = get_connection()
    try:
        rows = conn.execute(sql, params).fetchall()
        return [_row_to_dict(r) for r in rows]
    finally:
        conn.close()


def get_companions(plant_id: int) -> dict[str, list[dict]]:
    """
    Return {'friends': [...plant dicts...], 'enemies': [...plant dicts...]}
    for the given plant_id.  Companion relationships are bidirectional.
    """
    conn = get_connection()
    try:
        def _fetch(table: str) -> list[dict]:
            rows = conn.execute(
                f"""SELECT p.* FROM plants p
                    JOIN {table} c ON (
                        (c.plant_id_a = ? AND c.plant_id_b = p.id) OR
                        (c.plant_id_b = ? AND c.plant_id_a = p.id)
                    )
                    ORDER BY p.common_name""",
                (plant_id, plant_id)
            ).fetchall()
            return [_row_to_dict(r) for r in rows]

        return {
            "friends": _fetch("companion_friends"),
            "enemies": _fetch("companion_enemies"),
        }
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
