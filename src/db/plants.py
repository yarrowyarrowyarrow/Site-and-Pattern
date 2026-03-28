import sqlite3
import os

DB_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "plants.db")
SCHEMA_PATH = os.path.join(os.path.dirname(__file__), "schema.sql")


def get_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db():
    conn = get_connection()
    with open(SCHEMA_PATH) as f:
        conn.executescript(f.read())
    conn.commit()
    conn.close()


def get_all_plants():
    conn = get_connection()
    rows = conn.execute("SELECT * FROM plants ORDER BY common_name").fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_plant_by_id(plant_id):
    conn = get_connection()
    row = conn.execute("SELECT * FROM plants WHERE id = ?", (plant_id,)).fetchone()
    conn.close()
    return dict(row) if row else None


def search_plants(query="", plant_type=None, sun=None, water=None, perm_use=None, zone=None):
    conn = get_connection()
    sql = "SELECT * FROM plants WHERE 1=1"
    params = []

    if query:
        sql += " AND (common_name LIKE ? OR scientific_name LIKE ?)"
        params += [f"%{query}%", f"%{query}%"]
    if plant_type:
        sql += " AND plant_type = ?"
        params.append(plant_type)
    if sun:
        sql += " AND sun_requirement = ?"
        params.append(sun)
    if water:
        sql += " AND water_needs = ?"
        params.append(water)
    if perm_use:
        sql += " AND permaculture_uses LIKE ?"
        params.append(f"%{perm_use}%")
    if zone is not None:
        sql += " AND hardiness_zone_min <= ? AND hardiness_zone_max >= ?"
        params += [zone, zone]

    sql += " ORDER BY common_name"
    rows = conn.execute(sql, params).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_plant_types():
    conn = get_connection()
    rows = conn.execute("SELECT DISTINCT plant_type FROM plants ORDER BY plant_type").fetchall()
    conn.close()
    return [r["plant_type"] for r in rows]


def get_plant_by_name(common_name):
    conn = get_connection()
    row = conn.execute(
        "SELECT * FROM plants WHERE common_name = ?", (common_name,)
    ).fetchone()
    conn.close()
    return dict(row) if row else None
