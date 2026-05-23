"""
plants.py -- SQLite database access layer for the plant catalogue.

The database file is stored in a user-writable location:
  Windows : %APPDATA%/PermaDesign/permadesign.db
  macOS   : ~/Library/Application Support/PermaDesign/permadesign.db
  Linux   : $XDG_DATA_HOME/PermaDesign/permadesign.db  (default ~/.local/share/)

On first run the DB is created, schema applied, and seed data loaded.
If an old DB exists next to the executable it is migrated automatically.
"""

import os
import pathlib
import shutil
import sqlite3
import sys
from typing import Optional

# ── Paths ─────────────────────────────────────────────────────────────────────

_HERE        = os.path.dirname(os.path.abspath(__file__))
_SCHEMA_PATH = os.path.join(_HERE, "schema.sql")


def _user_data_dir() -> pathlib.Path:
    """Return a writable per-user data directory regardless of install location."""
    if sys.platform == "win32":
        base = os.environ.get("APPDATA") or pathlib.Path.home()
    elif sys.platform == "darwin":
        base = pathlib.Path.home() / "Library" / "Application Support"
    else:
        base = os.environ.get("XDG_DATA_HOME") or (pathlib.Path.home() / ".local" / "share")
    return pathlib.Path(base) / "PermaDesign"


_DATA_DIR = str(_user_data_dir())
_DB_PATH  = str(_user_data_dir() / "permadesign.db")

# Legacy path (DB next to exe / project root) — used only for one-time migration
_PROJECT_ROOT    = os.path.dirname(os.path.dirname(_HERE))
_LEGACY_DB_PATH  = os.path.join(_PROJECT_ROOT, "data", "permadesign.db")

# Master plant data (shipped with the application)
_MASTER_JSON_PATH  = os.path.join(_PROJECT_ROOT, "data", "plants_master.json")
_GARDEN_JSON_PATH  = os.path.join(_PROJECT_ROOT, "data", "garden_plants.json")

# Current schema version — bump when adding columns/tables, or when the
# bundled seed data changes meaningfully (forces a reseed on next start).
_SCHEMA_VERSION = 11


def _ensure_data_dir():
    os.makedirs(_DATA_DIR, exist_ok=True)


def _migrate_legacy_db():
    """One-time copy of the old project-root DB to the new user-data location."""
    if os.path.exists(_LEGACY_DB_PATH) and not os.path.exists(_DB_PATH):
        try:
            shutil.copy2(_LEGACY_DB_PATH, _DB_PATH)
        except OSError:
            pass


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


def _migrate_to_v4(conn: sqlite3.Connection):
    """Add marker_color column introduced in schema v4."""
    try:
        conn.execute("ALTER TABLE plants ADD COLUMN marker_color TEXT")
    except sqlite3.OperationalError:
        pass  # column already present
    conn.commit()


def _migrate_to_v5(conn: sqlite3.Connection):
    """Add growth rate, years to maturity, and growth curve for succession planning."""
    new_columns = [
        ("growth_rate", "TEXT"),            # slow | moderate | fast
        ("years_to_maturity", "INTEGER"),   # estimated years to reach mature size
        ("growth_curve", "TEXT"),           # fast_early | steady | slow_start
    ]
    for col_name, col_def in new_columns:
        try:
            conn.execute(f"ALTER TABLE plants ADD COLUMN {col_name} {col_def}")
        except sqlite3.OperationalError:
            pass  # column already present
    conn.commit()


def _migrate_to_v8(conn: sqlite3.Connection):
    """Add mature_canopy_m (horizontal canopy spread at maturity)."""
    try:
        conn.execute("ALTER TABLE plants ADD COLUMN mature_canopy_m REAL")
    except sqlite3.OperationalError:
        pass  # column already present
    conn.commit()


def _seed_from_json_file(conn: sqlite3.Connection, json_path: str) -> int:
    """
    Insert all plants from a JSON file into the plants table (skipping duplicates
    by common_name).  Also populates planting_calendar from cal_jan..cal_dec fields.
    Returns the number of plants inserted.
    """
    import json as _json

    if not os.path.exists(json_path):
        return 0

    with open(json_path, "r", encoding="utf-8") as f:
        entries = _json.load(f)

    # Skip plants already in the DB (allows calling this for multiple JSON files)
    existing_names = {
        row[0].lower()
        for row in conn.execute("SELECT common_name FROM plants").fetchall()
    }
    entries = [p for p in entries if p.get("common_name", "").lower() not in existing_names]
    if not entries:
        return 0

    plant_rows = []
    for p in entries:
        uses = p.get("permaculture_uses", "")
        if isinstance(uses, list):
            uses = ", ".join(uses)
        plant_rows.append((
            p.get("common_name", ""),
            p.get("scientific_name", ""),
            p.get("plant_type", "herb"),
            p.get("hardiness_zone_min"),
            p.get("hardiness_zone_max"),
            p.get("sun_requirement", ""),
            p.get("water_needs", ""),
            p.get("native_region", ""),
            uses,
            p.get("spacing_m") or p.get("spacing_meters"),
            p.get("mature_height_m") or p.get("mature_height_meters"),
            p.get("notes", ""),
            p.get("bloom_period", ""),
            p.get("fruit_period", ""),
            p.get("native_to_alberta", 0),
            p.get("edible_parts", ""),
            p.get("deciduous_evergreen", ""),
            p.get("soil_ph_min"),
            p.get("soil_ph_max"),
            p.get("perennial_annual") or p.get("perennial_or_annual", ""),
            p.get("growth_rate"),
            p.get("years_to_maturity"),
            p.get("growth_curve"),
        ))

    conn.executemany(
        """INSERT INTO plants
           (common_name, scientific_name, plant_type,
            hardiness_zone_min, hardiness_zone_max,
            sun_requirement, water_needs,
            native_region, permaculture_uses,
            spacing_meters, mature_height_meters, notes,
            bloom_period, fruit_period, native_to_alberta,
            edible_parts, deciduous_evergreen,
            soil_ph_min, soil_ph_max, perennial_or_annual,
            growth_rate, years_to_maturity, growth_curve)
           VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
        plant_rows,
    )
    conn.commit()

    # Phase 2: build name→id map then insert calendar entries
    name_to_id = {
        row[0]: row[1]
        for row in conn.execute("SELECT common_name, id FROM plants").fetchall()
    }

    months = ["cal_jan", "cal_feb", "cal_mar", "cal_apr", "cal_may", "cal_jun",
              "cal_jul", "cal_aug", "cal_sep", "cal_oct", "cal_nov", "cal_dec"]
    cal_rows = []
    for p in entries:
        plant_id = name_to_id.get(p.get("common_name", ""))
        if plant_id is None:
            continue
        for i, key in enumerate(months, 1):
            status = p.get(key)
            if status and status != "dormant":
                cal_rows.append((plant_id, i, status))

    if cal_rows:
        conn.executemany(
            "INSERT OR IGNORE INTO planting_calendar (plant_id, month, status, notes) "
            "VALUES (?, ?, ?, NULL)",
            cal_rows,
        )
        conn.commit()

    return len(entries)


def _seed_from_master_json(conn: sqlite3.Connection) -> int:
    """Backward-compat wrapper — seeds from the master native plant JSON."""
    return _seed_from_json_file(conn, _MASTER_JSON_PATH)


def init_db() -> None:
    """
    Create tables (if absent), run migrations, and seed the plant catalogue
    if it is empty or outdated.  Safe to call multiple times.
    """
    _ensure_data_dir()
    _migrate_legacy_db()
    conn = get_connection()
    try:
        # Apply full schema (creates any missing tables)
        with open(_SCHEMA_PATH, "r", encoding="utf-8") as f:
            conn.executescript(f.read())
        conn.commit()

        current_version = _get_schema_version(conn)

        if current_version < 2:
            _migrate_to_v2(conn)

        if current_version < 4:
            _migrate_to_v4(conn)

        if current_version < 5:
            _migrate_to_v5(conn)

        if current_version < 8:
            _migrate_to_v8(conn)

        # Add parent_id to polycultures if missing
        try:
            conn.execute("ALTER TABLE polycultures ADD COLUMN parent_id INTEGER REFERENCES polycultures(id) ON DELETE SET NULL")
            conn.commit()
        except sqlite3.OperationalError:
            pass  # column already present

        count = conn.execute("SELECT COUNT(*) FROM plants").fetchone()[0]

        # Reseed if empty, below master dataset size, or upgrading schema version
        needs_reseed = (count < 100) or (current_version < _SCHEMA_VERSION)

        if needs_reseed:
            # Disable FK enforcement for the bulk reseed — Python 3.14 enforces
            # FK constraints at statement time rather than transaction commit,
            # which can cause failures when parent/child rows are inserted in the
            # same transaction.  Data is internally consistent so this is safe.
            conn.execute("PRAGMA foreign_keys = OFF")
            conn.execute("DELETE FROM companion_friends")
            conn.execute("DELETE FROM companion_enemies")
            conn.execute("DELETE FROM planting_calendar")
            conn.execute("DELETE FROM polyculture_members")
            conn.execute("DELETE FROM polycultures")
            conn.execute("DELETE FROM plants")
            conn.commit()
            _seed_from_json_file(conn, _MASTER_JSON_PATH)    # 433 native plants
            _seed_from_json_file(conn, _GARDEN_JSON_PATH)    # cultivated garden plants
            from src.db.seed_data import SEED_COMPANIONS
            _insert_companions(conn, SEED_COMPANIONS)
            conn.execute("PRAGMA foreign_keys = ON")
            conn.commit()

        _set_schema_version(conn, _SCHEMA_VERSION)
    finally:
        conn.close()

    # Seed example polycultures (after plants are ready)
    try:
        from src.db.polycultures import seed_example_polycultures
        seed_example_polycultures()
    except Exception:
        pass  # Non-critical; polycultures can be created manually


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
    d = dict(row)
    # mature_canopy_m defaults to 1.5× the planting spacing when no per-species
    # value has been entered, so the preview canopy ring always has something
    # to draw. Accurate species data can override this later.
    if "mature_canopy_m" in d and not d.get("mature_canopy_m"):
        sp = d.get("spacing_meters")
        if sp:
            d["mature_canopy_m"] = float(sp) * 1.5
    return d


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
    edible_only: bool = False,
    medicinal_only: bool = False,
    nfixer_only: bool = False,
    pollinator_only: bool = False,
    perennial_only: bool = False,
    host_plant_only: bool = False,
    keystone_only: bool = False,
    bird_food_only: bool = False,
) -> list[dict]:
    """
    Return plants matching all supplied filters.
    Empty string / None values for a filter means "no restriction".
    """
    sql    = "SELECT * FROM plants WHERE 1=1"
    params: list = []

    if query:
        sql += " AND (LOWER(common_name) LIKE ? OR LOWER(scientific_name) LIKE ? OR LOWER(permaculture_uses) LIKE ?)"
        q = f"%{query.lower()}%"
        params += [q, q, q]

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

    if edible_only:
        sql += " AND edible_parts IS NOT NULL AND edible_parts != ''"

    if medicinal_only:
        sql += " AND LOWER(permaculture_uses) LIKE '%medicinal%'"

    if nfixer_only:
        sql += " AND LOWER(permaculture_uses) LIKE '%nitrogen%'"

    if pollinator_only:
        sql += " AND LOWER(permaculture_uses) LIKE '%pollinator%'"

    if perennial_only:
        sql += " AND LOWER(perennial_or_annual) = 'perennial'"

    if host_plant_only:
        sql += " AND LOWER(permaculture_uses) LIKE '%host_plant%'"

    if keystone_only:
        sql += " AND LOWER(permaculture_uses) LIKE '%keystone_species%'"

    if bird_food_only:
        sql += " AND LOWER(permaculture_uses) LIKE '%bird_food%'"

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


# ── Planting calendar ─────────────────────────────────────────────────────────

def _seed_calendar(conn: sqlite3.Connection):
    """Populate planting_calendar from seed_data if the table is empty."""
    count = conn.execute("SELECT COUNT(*) FROM planting_calendar").fetchone()[0]
    if count > 0:
        return
    from src.db.seed_data import SEED_CALENDAR
    # Resolve common_name -> id
    name_to_id: dict[str, int] = {}
    for row in conn.execute("SELECT id, common_name FROM plants"):
        name_to_id[row["common_name"]] = row["id"]
    rows: list[tuple] = []
    for common_name, month, status, notes in SEED_CALENDAR:
        pid = name_to_id.get(common_name)
        if pid is None:
            continue
        rows.append((pid, month, status, notes))
    conn.executemany(
        "INSERT OR IGNORE INTO planting_calendar (plant_id, month, status, notes) "
        "VALUES (?,?,?,?)", rows
    )
    conn.commit()


def get_calendar(plant_id: int) -> list[dict]:
    """
    Return the 12-month planting calendar for a given plant.
    Returns a list of dicts with keys: month, status, notes.
    Missing months are filled with 'dormant'.
    """
    conn = get_connection()
    try:
        rows = conn.execute(
            "SELECT month, status, notes FROM planting_calendar "
            "WHERE plant_id = ? ORDER BY month", (plant_id,)
        ).fetchall()
    finally:
        conn.close()
    by_month = {r["month"]: {"month": r["month"], "status": r["status"],
                              "notes": r["notes"]} for r in rows}
    return [by_month.get(m, {"month": m, "status": "dormant", "notes": None})
            for m in range(1, 13)]


def get_current_month_tasks() -> list[dict]:
    """
    Return plants with active tasks for the current month.
    Each dict: {plant_id, common_name, plant_type, status, notes}.
    Excludes dormant and growing (those aren't actionable).
    """
    from datetime import datetime
    month = datetime.now().month
    conn = get_connection()
    try:
        rows = conn.execute(
            """SELECT p.id AS plant_id, p.common_name, p.plant_type,
                      c.status, c.notes
               FROM planting_calendar c
               JOIN plants p ON p.id = c.plant_id
               WHERE c.month = ? AND c.status NOT IN ('dormant', 'growing')
               ORDER BY c.status, p.common_name""",
            (month,)
        ).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


# ── Marker customisation ──────────────────────────────────────────────────────

def update_marker_color(plant_id: int, color: Optional[str]) -> None:
    """Set or clear the custom marker colour for a plant."""
    conn = get_connection()
    try:
        conn.execute(
            "UPDATE plants SET marker_color = ? WHERE id = ?",
            (color, plant_id)
        )
        conn.commit()
    finally:
        conn.close()
