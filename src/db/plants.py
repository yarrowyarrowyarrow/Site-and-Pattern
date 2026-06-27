"""
plants.py -- SQLite database access layer for the plant catalogue.

The database file is stored in a user-writable location:
  Windows : %APPDATA%/Site & Pattern/permadesign.db
  macOS   : ~/Library/Application Support/Site & Pattern/permadesign.db
  Linux   : $XDG_DATA_HOME/Site & Pattern/permadesign.db  (default ~/.local/share/)

On first run the DB is created, schema applied, and seed data loaded.
If an old DB exists next to the executable it is migrated automatically. The
per-user folder was named ``PermaDesign`` before the V1.69 rebrand; it is renamed
to ``Site & Pattern`` once, in place, by ``src/user_paths.py`` (the DB *filename*
stays ``permadesign.db`` — internal, never shown to the user).
"""

import os
import pathlib
import shutil
import sqlite3
import sys
from typing import Optional

from src.resources import resource_path

# ── Paths ─────────────────────────────────────────────────────────────────────

_HERE        = os.path.dirname(os.path.abspath(__file__))
# Resolve through resource_path so the schema is found inside a PyInstaller
# bundle (where a module's __file__ is unreliable), not just in a source tree.
_SCHEMA_PATH = resource_path("src", "db", "schema.sql")


def _user_data_dir() -> pathlib.Path:
    """Return a writable per-user data directory regardless of install location.

    Pure (no side effects) so the module-level path constants below can be built
    at import time without creating or migrating anything. Delegates to
    ``user_paths.data_dir_path`` — the single source of truth for the folder name
    (kept here as a named function so tests can monkeypatch this exact symbol)."""
    from src.user_paths import data_dir_path
    return data_dir_path()


_DATA_DIR = str(_user_data_dir())
_DB_PATH  = str(_user_data_dir() / "permadesign.db")

# Legacy path (DB next to exe / project root) — used only for one-time migration
_PROJECT_ROOT    = os.path.dirname(os.path.dirname(_HERE))
_LEGACY_DB_PATH  = os.path.join(_PROJECT_ROOT, "data", "permadesign.db")

# Master plant data (shipped with the application — resolved via resource_path
# so the seed JSON is found both in a source tree and inside a frozen bundle).
_MASTER_JSON_PATH       = resource_path("data", "plants_master.json")
_GARDEN_JSON_PATH       = resource_path("data", "garden_plants.json")
_FAUNA_JSON_PATH        = resource_path("data", "fauna_master.json")
_PLANT_FAUNA_JSON_PATH  = resource_path("data", "plant_fauna_master.json")

# Current schema version — bump when adding columns/tables, or when the
# bundled seed data changes meaningfully (forces a reseed on next start).
#
# v13 (V1.31): normalized `permaculture_uses` blob into a `plant_uses`
# junction table backed by a `uses` lookup, and added a `fauna` registry
# plus `plant_fauna` relationship table for larval-host / nectar /
# fruit-food / nesting links. See Step 1 and Step 2 in the V1.31 plan.
# v14 (V1.35): added `climate_cache` table for growing-degree-day +
# frost-window stats fetched from Open-Meteo Historical Weather. The
# cache is wiped on reseed like the other dependent tables, so users
# upgrading from v13 get an empty cache on next launch and fetch
# fresh on their next property pin set.
# v15 (V1.37): plant-uses vocabulary refresh. Dropped permaculture-
# flavored tags from `_USE_DEFINITIONS` (biomass, pest_deterrent,
# food_forest, edible_landscape); renamed some labels for clarity
# (host_plant → "Larval Host", pollinator → "Pollinator Support",
# water_purification → "Riparian Filter"); promoted "overstory" →
# "canopy_layer" so it's a canonical tag rather than an informal one.
# v16 (V1.37, second pass): two reverts after user feedback.
# (a) "Pioneer Species" / `pioneer_species` reverted to
# "Early Successional" / `early_successional` — the "pioneer" framing
# carries colonizer connotations that don't belong in this app's
# vocabulary. (b) The "First Nations Medicine Wheel" polyculture
# variation was renamed to "Native Prairie Aromatics" and its parent
# was renamed from "Medicinal Herb Circle" to "Aromatic Herb Circle";
# both descriptions stripped of the Indigenous-knowledge claims that
# weren't ours to redistribute. The plant lists are unchanged — the
# species are real Alberta natives — but the framing is now strictly
# horticultural.
# v17 (V1.37, third pass): "Red Indian Paintbrush" (Castilleja
# miniata) renamed to "Common Paintbrush" — the historical horticultural
# common name carried "Indian" as a colonial descriptor. The
# scientific name is the lookup key in the seed pipeline, so existing
# polyculture / recipe references continue to resolve correctly on
# reseed; only the user-visible display name changes.
# v21 (V1.53): added `shade_zone_cache` — a derived per-zone shade-tag index
# (full_sun / partial_shade / full_shade) keyed by project + zone. Footprint
# geometry stays in the project GeoJSON per CLAUDE.md; this is an OUTPUT cache,
# wiped on reseed like climate_cache. The new table is created by the
# executescript(schema.sql) in init_db, so no ALTER migration is needed.
# v22 (V1.55): terrain self-shadowing (src/terrain_shade.py) now folds DEM
# horizon shadows into the shade grid, so a zone previously tagged full_sun may
# now be (partial) shade. No DDL change — this bump is a deliberate cache-buster
# that re-wipes the derived `shade_zone_cache` (already in the reseed block) so
# stale tags can't outlive the model change.
# v23 (V1.60): added the lawn-to-habitat starter communities (Boulevard
# Pollinator Strip, Backyard Meadow Patch, Hedgerow Shelterbelt) to the seeded
# polycultures (P1). No DDL change — the bump re-runs the polyculture seed
# (polycultures / polyculture_members are already wiped in the reseed block) so
# existing installs pick the new communities up.
# v24 (V1.60): imagery columns (image_url / image_attribution / image_license)
# on plants + fauna (I1). _migrate_to_v24 ALTERs existing tables; the reseed
# fills any values present in the seed JSON.
# v25 (V1.61): no DDL — image data populated from iNaturalist (323 plants /
# 58 fauna, CC0/CC-BY/CC-BY-SA only, with attribution). The bump reseeds so
# existing installs pick the photo URLs up.
# v26 (V1.67): added `wind_cache` table for the seasonal wind rose. Per-location
# user cache (not seeded); wiped on reseed like climate_cache so it recomputes.
# v27 (V1.79, F4): added problem/context/forces/solution columns to `polycultures`
# for the Alexander pattern-language framing. The bump reseeds so existing installs
# pick up the authored pattern text seeded in src/db/polycultures.py.
# v28 (V1.79): no DDL — reseed so the de-dashed authored pattern text replaces the
# v27 text on installs that already seeded it.
# v29 (V1.84): no DDL — reseed to pick up the curated availability_class tiers and
# the multi-value (comma-delimited) sun_requirement / water_needs values.
_SCHEMA_VERSION = 29


# ── Canonical permaculture uses (schema v13) ──────────────────────────────────
# Source of truth for the `uses` lookup table. Each row becomes a row in
# `uses` at seed time; the comma-delimited tokens in plants.permaculture_uses
# are then split out into `plant_uses` rows. Keys here must match the tokens
# that live in data/plants_master.json (and the keys in plant_panel._USE_LABELS).
_USE_DEFINITIONS: list[tuple[str, str, str, int]] = [
    # (key, label, category, sort_order)
    # V1.37 refresh: vocabulary refocused on native habitat + functional
    # landscape design. Dropped permaculture-flavored tags
    # (biomass/chop-drop, pest_deterrent, food_forest, edible_landscape).
    # Renamed labels for audience clarity. Promoted "overstory" (informal
    # data tag) to canonical "canopy_layer".
    ("keystone_species",   "Keystone Species",     "wildlife", 10),
    ("host_plant",         "Larval Host",          "wildlife", 20),
    ("bird_food",          "Bird Food",            "wildlife", 30),
    ("nesting_material",   "Nesting Material",     "wildlife", 40),
    ("pollinator",         "Pollinator Support",   "wildlife", 50),
    ("wildlife_habitat",   "Wildlife Habitat",     "wildlife", 60),
    ("nitrogen_fixer",     "Nitrogen Fixer",       "function", 110),
    ("soil_builder",       "Soil Builder",         "function", 120),
    ("early_successional", "Early Successional",   "function", 130),
    ("canopy_layer",       "Canopy Layer",         "landscape", 205),
    ("windbreak",          "Windbreak",            "landscape", 210),
    ("hedge",              "Hedge",                "landscape", 220),
    ("groundcover",        "Groundcover",          "landscape", 230),
    ("erosion_control",    "Erosion Control",      "landscape", 240),
    ("riparian_filter",    "Riparian Filter",      "landscape", 250),
    ("ornamental",         "Ornamental",           "landscape", 260),
    ("aquatic",            "Aquatic",              "landscape", 270),
    ("medicinal",          "Medicinal",            "utility",  310),
]


def _ensure_data_dir():
    # Rename a pre-rebrand "PermaDesign" folder to the new "Site & Pattern" name
    # *before* creating the (possibly new) data dir — otherwise an empty new
    # folder would make the migration's "already exists" guard skip and strand the
    # old database. Driving the migration off _DATA_DIR keeps a test-overridden
    # tempdir (which already exists) a correct no-op.
    from src import user_paths
    user_paths.migrate_legacy_into(_DATA_DIR)
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


def _migrate_to_v11(conn: sqlite3.Connection):
    """Add ab_ecoregion column (Reference Ecosystem picker, N1)."""
    try:
        conn.execute("ALTER TABLE plants ADD COLUMN ab_ecoregion TEXT")
    except sqlite3.OperationalError:
        pass  # column already present
    conn.commit()


def _migrate_to_v18(conn: sqlite3.Connection):
    """Add the safety + spread columns (V1.44 chunk 2). Existing installs get
    the columns added; the reseed that the version bump triggers then fills the
    classified values from the seed JSON."""
    new_columns = [
        ("toxicity_pets",   "TEXT DEFAULT ''"),
        ("toxicity_humans", "TEXT DEFAULT ''"),
        ("has_thorns",      "INTEGER DEFAULT 0"),
        ("spread_habit",    "TEXT DEFAULT ''"),
        ("safety_source",   "TEXT DEFAULT ''"),
    ]
    for col_name, col_def in new_columns:
        try:
            conn.execute(f"ALTER TABLE plants ADD COLUMN {col_name} {col_def}")
        except sqlite3.OperationalError:
            pass  # column already present
    conn.commit()


def _migrate_to_v19(conn: sqlite3.Connection):
    """Add the sourcing + cost columns (V1.45). The version bump triggers a
    reseed that fills the values from the seed JSON."""
    new_columns = [
        ("price_low_cad",      "REAL"),
        ("price_high_cad",     "REAL"),
        ("availability_class", "TEXT DEFAULT ''"),
        ("sourcing_notes",     "TEXT DEFAULT ''"),
    ]
    for col_name, col_def in new_columns:
        try:
            conn.execute(f"ALTER TABLE plants ADD COLUMN {col_name} {col_def}")
        except sqlite3.OperationalError:
            pass  # column already present
    conn.commit()


def _migrate_to_v24(conn: sqlite3.Connection):
    """Add the imagery columns (V1.60) to plants and fauna. The version bump
    triggers a reseed that fills any values present in the seed JSON; existing
    installs keep their rows and just gain the (empty) columns here."""
    for table in ("plants", "fauna"):
        for col_name in ("image_url", "image_attribution", "image_license"):
            try:
                conn.execute(
                    f"ALTER TABLE {table} ADD COLUMN {col_name} TEXT DEFAULT ''")
            except sqlite3.OperationalError:
                pass  # column already present
    conn.commit()


# Vegetation layers and ecological functions used to split the legacy
# single `role` field on polyculture_members. Mirrored in
# src/polyculture_panel.py so the UI and the migration use one source of
# truth; if these lists change, update both places.
_LAYER_VALUES = {"overstory", "understory", "shrub_layer", "groundcover",
                 "herbaceous", "vine", "root"}
_FUNCTION_VALUES = {"nitrogen_fixer", "soil_builder", "pest_deterrent",
                    "pollinator", "windbreak"}
_LEGACY_ROLE_TO_LAYER_FUNC = {
    "canopy":              ("overstory", None),
    "dynamic_accumulator": (None, "soil_builder"),
    "pest_repellent":      (None, "pest_deterrent"),
}


def _role_to_layer_functions(role):
    """Map a legacy single-value role to (layer, functions_list)."""
    role = (role or "").strip()
    if role in _LAYER_VALUES:
        return role, []
    if role in _FUNCTION_VALUES:
        return None, [role]
    if role in _LEGACY_ROLE_TO_LAYER_FUNC:
        layer, fn = _LEGACY_ROLE_TO_LAYER_FUNC[role]
        return layer, ([fn] if fn else [])
    return None, []


def _migrate_polyculture_member_layer_functions(conn: sqlite3.Connection):
    """Add `layer` and `functions` columns to polyculture_members and
    backfill them from the existing `role`. Idempotent: re-running is a
    no-op once every row has either a layer or a non-empty functions
    list."""
    import json as _json

    for col_def in ("layer TEXT", "functions TEXT"):
        try:
            conn.execute(f"ALTER TABLE polyculture_members ADD COLUMN {col_def}")
        except sqlite3.OperationalError:
            pass  # column already present

    # Backfill only rows that haven't been migrated yet — i.e. layer is
    # NULL AND functions is NULL/empty. Already-migrated rows are left
    # alone so user edits aren't clobbered.
    rows = conn.execute(
        "SELECT id, role FROM polyculture_members "
        "WHERE layer IS NULL AND (functions IS NULL OR functions = '' OR functions = '[]')"
    ).fetchall()
    for r in rows:
        layer, functions = _role_to_layer_functions(r["role"])
        if layer is None and not functions:
            # Nothing useful to backfill; still write '[]' so the row is
            # marked as "considered" and we don't keep iterating it.
            conn.execute(
                "UPDATE polyculture_members SET functions = '[]' WHERE id = ?",
                (r["id"],)
            )
        else:
            conn.execute(
                "UPDATE polyculture_members SET layer = ?, functions = ? WHERE id = ?",
                (layer, _json.dumps(functions), r["id"])
            )
    conn.commit()


def _migrate_polyculture_pattern_columns(conn: sqlite3.Connection):
    """Add the Alexander pattern-language columns (problem/context/forces/
    solution) to `polycultures` for existing installs (schema v27, F4).

    Idempotent: each ALTER is wrapped so re-running once the column exists is a
    no-op. No backfill is needed — the v27 version bump triggers a reseed that
    repopulates the seeded communities (and their authored text) wholesale; the
    columns just have to exist before that reseed writes into them."""
    for col_def in ("problem TEXT", "context TEXT",
                    "forces TEXT", "solution TEXT"):
        try:
            conn.execute(f"ALTER TABLE polycultures ADD COLUMN {col_def}")
        except sqlite3.OperationalError:
            pass  # column already present
    conn.commit()


def _seed_uses_lookup(conn: sqlite3.Connection) -> None:
    """
    Populate the ``uses`` lookup table from ``_USE_DEFINITIONS``. Idempotent:
    rows whose ``key`` already exists are left alone (so other code that
    references their id is stable across runs).
    """
    conn.executemany(
        "INSERT OR IGNORE INTO uses (key, label, category, sort_order) "
        "VALUES (?, ?, ?, ?)",
        _USE_DEFINITIONS,
    )
    conn.commit()


def _populate_plant_uses(conn: sqlite3.Connection, entries: list[dict]) -> int:
    """
    For each plant entry just inserted, split its ``permaculture_uses``
    comma-delimited string into rows in ``plant_uses``. Unknown tokens
    (tags not present in ``uses``) are silently skipped. Returns the number
    of (plant_id, use_id) rows inserted.
    """
    # Build canonical key → use_id map and common_name → plant_id map.
    use_key_to_id = {
        row["key"]: row["id"]
        for row in conn.execute("SELECT id, key FROM uses").fetchall()
    }
    name_to_id = {
        row["common_name"]: row["id"]
        for row in conn.execute("SELECT id, common_name FROM plants").fetchall()
    }

    rows: list[tuple[int, int]] = []
    for p in entries:
        plant_id = name_to_id.get(p.get("common_name", ""))
        if plant_id is None:
            continue
        uses_raw = p.get("permaculture_uses", "")
        if isinstance(uses_raw, list):
            tokens = [str(t).strip() for t in uses_raw]
        else:
            tokens = [t.strip() for t in str(uses_raw).split(",")]
        for tok in tokens:
            if not tok:
                continue
            use_id = use_key_to_id.get(tok)
            if use_id is None:
                continue
            rows.append((plant_id, use_id))

    if rows:
        conn.executemany(
            "INSERT OR IGNORE INTO plant_uses (plant_id, use_id) VALUES (?, ?)",
            rows,
        )
        conn.commit()
    return len(rows)


def _seed_fauna(conn: sqlite3.Connection) -> int:
    """
    Load ``data/fauna_master.json`` into the ``fauna`` table, then load
    ``data/plant_fauna_master.json`` into ``plant_fauna``. Returns the
    number of plant↔fauna links inserted. Idempotent on the fauna table
    via ``INSERT OR IGNORE`` keyed on ``scientific_name``.
    """
    import json as _json

    # Phase 1: fauna registry
    if os.path.exists(_FAUNA_JSON_PATH):
        with open(_FAUNA_JSON_PATH, "r", encoding="utf-8") as f:
            fauna_entries = _json.load(f)
        fauna_rows = [
            (
                e["scientific_name"],
                e["common_name"],
                e["taxon"],
                int(e.get("ab_native", 1)),
                e.get("range_notes"),
                e.get("icon"),
                e.get("description"),
                e.get("image_url", ""),
                e.get("image_attribution", ""),
                e.get("image_license", ""),
            )
            for e in fauna_entries
            if "scientific_name" in e and "common_name" in e and "taxon" in e
        ]
        if fauna_rows:
            conn.executemany(
                "INSERT OR IGNORE INTO fauna "
                "(scientific_name, common_name, taxon, ab_native, "
                " range_notes, icon, description, "
                " image_url, image_attribution, image_license) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                fauna_rows,
            )
            conn.commit()

    # Phase 2: plant ↔ fauna links
    if not os.path.exists(_PLANT_FAUNA_JSON_PATH):
        return 0

    with open(_PLANT_FAUNA_JSON_PATH, "r", encoding="utf-8") as f:
        link_entries = _json.load(f)

    name_to_pid = {
        row["common_name"]: row["id"]
        for row in conn.execute("SELECT id, common_name FROM plants").fetchall()
    }
    sci_to_fid = {
        row["scientific_name"]: row["id"]
        for row in conn.execute("SELECT id, scientific_name FROM fauna").fetchall()
    }

    link_rows: list[tuple] = []
    for entry in link_entries:
        # Skip metadata records (those without a 'plant' / 'fauna' key).
        if "plant" not in entry or "fauna" not in entry:
            continue
        pid = name_to_pid.get(entry["plant"])
        fid = sci_to_fid.get(entry["fauna"])
        if pid is None or fid is None:
            continue
        link_rows.append((
            pid,
            fid,
            entry.get("relationship", "larval_host"),
            entry.get("specificity"),
            entry.get("source"),
            entry.get("notes"),
        ))

    if link_rows:
        conn.executemany(
            "INSERT OR IGNORE INTO plant_fauna "
            "(plant_id, fauna_id, relationship, specificity, source, notes) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            link_rows,
        )
        conn.commit()
    return len(link_rows)


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
        ecoregion = p.get("ab_ecoregion", "")
        if isinstance(ecoregion, list):
            ecoregion = ",".join(ecoregion)
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
            ecoregion,
            p.get("toxicity_pets", ""),
            p.get("toxicity_humans", ""),
            1 if p.get("has_thorns") else 0,
            p.get("spread_habit", ""),
            p.get("safety_source", ""),
            p.get("price_low_cad"),
            p.get("price_high_cad"),
            p.get("availability_class", ""),
            p.get("sourcing_notes", ""),
            p.get("image_url", ""),
            p.get("image_attribution", ""),
            p.get("image_license", ""),
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
            growth_rate, years_to_maturity, growth_curve,
            ab_ecoregion,
            toxicity_pets, toxicity_humans, has_thorns,
            spread_habit, safety_source,
            price_low_cad, price_high_cad, availability_class,
            sourcing_notes,
            image_url, image_attribution, image_license)
           VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
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

    # Phase 3 (schema v13): populate the plant_uses junction table for
    # the newly-inserted entries. Skips quietly if the `uses` lookup is
    # empty (e.g. very early in the bootstrap sequence).
    try:
        _populate_plant_uses(conn, entries)
    except sqlite3.OperationalError:
        pass

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

        if current_version < 11:
            _migrate_to_v11(conn)

        if current_version < 18:
            _migrate_to_v18(conn)

        if current_version < 19:
            _migrate_to_v19(conn)

        if current_version < 24:
            _migrate_to_v24(conn)

        # Add parent_id to polycultures if missing
        try:
            conn.execute("ALTER TABLE polycultures ADD COLUMN parent_id INTEGER REFERENCES polycultures(id) ON DELETE SET NULL")
            conn.commit()
        except sqlite3.OperationalError:
            pass  # column already present

        # Idempotent additive migration — adds layer/functions columns to
        # polyculture_members and backfills them from the existing role.
        # Kept outside the version-bump reseed path so user-created
        # plant communities are preserved.
        _migrate_polyculture_member_layer_functions(conn)

        # Idempotent additive migration — adds the pattern-language columns to
        # polycultures so the v27 reseed below can write authored problem/
        # context/forces/solution text into them (F4).
        _migrate_polyculture_pattern_columns(conn)

        count = conn.execute("SELECT COUNT(*) FROM plants").fetchone()[0]

        # Reseed if empty, below master dataset size, or upgrading schema version
        needs_reseed = (count < 100) or (current_version < _SCHEMA_VERSION)

        if needs_reseed:
            # Disable FK enforcement for the bulk reseed — Python 3.14 enforces
            # FK constraints at statement time rather than transaction commit,
            # which can cause failures when parent/child rows are inserted in the
            # same transaction.  Data is internally consistent so this is safe.
            conn.execute("PRAGMA foreign_keys = OFF")
            # Wipe child tables before parents so FK chains (even with FK off
            # they still inform the order we'd want when FK is back on).
            conn.execute("DELETE FROM plant_fauna")
            conn.execute("DELETE FROM plant_uses")
            conn.execute("DELETE FROM fauna")
            conn.execute("DELETE FROM uses")
            conn.execute("DELETE FROM companion_friends")
            conn.execute("DELETE FROM companion_enemies")
            conn.execute("DELETE FROM planting_calendar")
            conn.execute("DELETE FROM polyculture_members")
            conn.execute("DELETE FROM polycultures")
            conn.execute("DELETE FROM plants")
            # climate_cache is per-location user data, not seeded — wipe
            # on reseed so the next launch refetches against any updated
            # source defaults rather than serving stale interpretations.
            conn.execute("DELETE FROM climate_cache")
            # wind_cache is per-location user data, not seeded — wipe on reseed
            # like climate_cache so the next launch refetches the wind rose.
            conn.execute("DELETE FROM wind_cache")
            # shade_zone_cache is per-project derived output (not seeded) — wipe
            # on reseed like climate_cache so it recomputes against any updated
            # shade model rather than serving stale tags.
            conn.execute("DELETE FROM shade_zone_cache")
            conn.commit()
            # Seed the uses lookup first so _seed_from_json_file can populate
            # plant_uses for each freshly inserted plant in the same pass.
            _seed_uses_lookup(conn)
            _seed_from_json_file(conn, _MASTER_JSON_PATH)    # 433 native plants
            _seed_from_json_file(conn, _GARDEN_JSON_PATH)    # cultivated garden plants
            from src.db.seed_data import SEED_COMPANIONS
            _insert_companions(conn, SEED_COMPANIONS)
            # Fauna registry + plant↔fauna links — depends on plants being
            # seeded first so we can resolve common_name → plant_id.
            _seed_fauna(conn)
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

    # One-time import of any pre-existing recipes that lived in
    # ~/.permadesign_config.json. Subsequent runs are no-ops thanks to
    # the `polyculture_recipes_migrated` flag.
    try:
        from src.db.recipes import migrate_qsettings_recipes
        migrate_qsettings_recipes()
    except Exception:
        pass  # Non-critical; user can recreate recipes from the new tab


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
    has_image_only: bool = False,
    ab_ecoregion: str = "",
    pet_safe_only: bool = False,
    kid_safe_only: bool = False,
    well_behaved_only: bool = False,
    max_unit_price: Optional[float] = None,
    common_only: bool = False,
    availability_in: Optional[list] = None,
    host_for_fauna_id: Optional[int] = None,
    supports_fauna_id: Optional[int] = None,
    supports_specialist: bool = False,
    soil_ph: Optional[float] = None,
    moisture: str = "",
) -> list[dict]:
    """
    Return plants matching all supplied filters.
    Empty string / None values for a filter means "no restriction".
    """
    sql    = "SELECT * FROM plants WHERE 1=1"
    params: list = []

    # plant_type / sun_req / water_needs / perm_use accept a single string
    # (legacy) or a list of values for multi-select filters (V1.85). Coerce to a
    # clean list so callers passing either shape work unchanged.
    def _as_filter_list(v) -> list:
        if not v:
            return []
        if isinstance(v, str):
            return [v]
        return [str(x) for x in v if x]

    if query:
        sql += " AND (LOWER(common_name) LIKE ? OR LOWER(scientific_name) LIKE ? OR LOWER(permaculture_uses) LIKE ?)"
        q = f"%{query.lower()}%"
        params += [q, q, q]

    # Type is a single column value; a multi-select matches ANY chosen type.
    types = _as_filter_list(plant_type)
    if types:
        sql += " AND plant_type IN (%s)" % ",".join("?" for _ in types)
        params += types

    # sun_requirement / water_needs may hold a comma-delimited list when a plant
    # tolerates a range (V1.84). A multi-select filter matches if ANY chosen
    # value is among the plant's tokens — OR of the membership test used by the
    # ab_ecoregion filter below.
    suns = _as_filter_list(sun_req)
    if suns:
        sql += " AND (" + " OR ".join(
            "(',' || COALESCE(sun_requirement,'') || ',') LIKE ?" for _ in suns) + ")"
        params += [f"%,{s},%" for s in suns]

    waters = _as_filter_list(water_needs)
    if waters:
        sql += " AND (" + " OR ".join(
            "(',' || COALESCE(water_needs,'') || ',') LIKE ?" for _ in waters) + ")"
        params += [f"%,{w},%" for w in waters]

    # Schema v13: tag filters now run through the plant_uses junction table
    # via a single EXISTS sub-select per tag. ``_use_filter`` keeps the SQL
    # readable and lets the caller build up an arbitrary set of tag filters.
    def _use_filter(use_key: str) -> str:
        return (
            " AND EXISTS (SELECT 1 FROM plant_uses pu "
            "             JOIN uses u ON u.id = pu.use_id "
            "             WHERE pu.plant_id = plants.id AND u.key = ?)"
        )

    # Use is AND-of-tags: a multi-select keeps only plants that have EVERY chosen
    # use (one EXISTS sub-select per tag), mirroring the old stacked toggles.
    for use_key in _as_filter_list(perm_use):
        sql += _use_filter(use_key)
        params.append(use_key)

    if zone is not None:
        sql += " AND hardiness_zone_min <= ? AND hardiness_zone_max >= ?"
        params += [zone, zone]

    if native_only:
        sql += " AND native_to_alberta = 1"

    if edible_only:
        sql += " AND edible_parts IS NOT NULL AND edible_parts != ''"

    if medicinal_only:
        sql += _use_filter("medicinal")
        params.append("medicinal")

    if nfixer_only:
        sql += _use_filter("nitrogen_fixer")
        params.append("nitrogen_fixer")

    if pollinator_only:
        sql += _use_filter("pollinator")
        params.append("pollinator")

    if perennial_only:
        sql += " AND LOWER(perennial_or_annual) = 'perennial'"

    if host_plant_only:
        sql += _use_filter("host_plant")
        params.append("host_plant")

    if keystone_only:
        sql += _use_filter("keystone_species")
        params.append("keystone_species")

    if bird_food_only:
        sql += _use_filter("bird_food")
        params.append("bird_food")

    if has_image_only:
        sql += " AND image_url IS NOT NULL AND image_url != ''"

    # ab_ecoregion column is a comma-separated list of region ids. A
    # multi-select "restoring toward" filter matches a plant documented from
    # ANY of the chosen ecoregions (OR of substring-safe patterns). Accepts a
    # single string (legacy) or a list (V1.85).
    ecoregions = _as_filter_list(ab_ecoregion)
    if ecoregions:
        sql += " AND (" + " OR ".join(
            "(',' || COALESCE(ab_ecoregion,'') || ',') LIKE ?" for _ in ecoregions) + ")"
        params += [f"%,{e},%" for e in ecoregions]

    # Safety filters (schema v18) use a DENYLIST: exclude only plants we have
    # classified as toxic. Unassessed ('') and explicit 'none' both pass, so
    # "pet/kid safe" means "no KNOWN toxicity", not a guarantee — surfaced as a
    # caveat in the UI (see src/design_goals.py).
    if pet_safe_only:
        sql += " AND COALESCE(toxicity_pets,'') NOT IN ('low','high')"

    if kid_safe_only:
        sql += (" AND COALESCE(toxicity_humans,'') NOT IN ('low','high')"
                " AND COALESCE(has_thorns,0) = 0")

    if well_behaved_only:
        sql += (" AND COALESCE(spread_habit,'') NOT IN "
                "('aggressive_rhizomatous','self_seeding')")

    # Sourcing/cost filters (schema v19). `max_unit_price` keeps plants whose
    # estimated LOW price is at/under the cap (a cheap-enough option exists);
    # unpriced plants pass (NULL price). `common_only` is a denylist — it drops
    # only plants KNOWN to be hard to source; unassessed availability passes.
    if max_unit_price is not None:
        sql += " AND (price_low_cad IS NULL OR price_low_cad <= ?)"
        params.append(float(max_unit_price))

    if common_only:
        # Denylist: drop only plants that are genuinely hard to buy (seed/plug
        # only or rare). Native specialists are the normal channel for AB
        # natives, so they pass — as does unassessed availability.
        sql += (" AND COALESCE(availability_class,'') NOT IN "
                "('seed_or_plug','rare')")

    # Allowlist (V1.84): keep only the chosen sourcing tiers. Drives the plant
    # browser's multi-select rarity dropdown — empty/None means "no restriction".
    if availability_in:
        placeholders = ",".join("?" for _ in availability_in)
        sql += f" AND COALESCE(availability_class,'') IN ({placeholders})"
        params += [str(v) for v in availability_in]

    # Fauna-support filters (schema v20) via the plant_fauna junction. Reuse the
    # EXISTS-subquery style used by the use-tag filters above.
    if host_for_fauna_id is not None:
        sql += (" AND EXISTS (SELECT 1 FROM plant_fauna pf WHERE "
                "pf.plant_id = plants.id AND pf.fauna_id = ? "
                "AND pf.relationship = 'larval_host')")
        params.append(int(host_for_fauna_id))

    if supports_fauna_id is not None:
        sql += (" AND EXISTS (SELECT 1 FROM plant_fauna pf WHERE "
                "pf.plant_id = plants.id AND pf.fauna_id = ?)")
        params.append(int(supports_fauna_id))

    if supports_specialist:
        sql += (" AND EXISTS (SELECT 1 FROM plant_fauna pf WHERE "
                "pf.plant_id = plants.id AND pf.specificity = 'specialist')")

    # Site-fit filters (V1.48). `soil_ph` keeps plants whose tolerance range
    # brackets the site pH (containment, mirroring `zone`); unassessed bounds
    # (NULL) pass so a missing range never excludes a plant. `moisture` maps a
    # site wetness class to the existing water/habitat columns.
    if soil_ph is not None:
        sql += (" AND (soil_ph_min IS NULL OR soil_ph_min <= ?)"
                " AND (soil_ph_max IS NULL OR soil_ph_max >= ?)")
        params += [float(soil_ph), float(soil_ph)]

    # water_needs may be comma-delimited (V1.84), so test membership with LIKE
    # rather than `=`/`IN` on the whole field.
    def _water_like(*values: str) -> str:
        return "(" + " OR ".join(
            "(',' || COALESCE(water_needs,'') || ',') LIKE '%," + v + ",%'"
            for v in values) + ")"

    if moisture == "wet":
        # Wet/low ground: high- or moderate-water plants, true aquatics, or
        # species tagged to a wet ecoregion (wet_meadow / riparian).
        sql += (" AND (" + _water_like("high", "moderate") +
                " OR plant_type = 'aquatic'"
                " OR (',' || COALESCE(ab_ecoregion,'') || ',') LIKE '%,wet_meadow,%'"
                " OR (',' || COALESCE(ab_ecoregion,'') || ',') LIKE '%,riparian,%')")
    elif moisture == "dry":
        sql += " AND " + _water_like("low")
    elif moisture == "mesic":
        sql += " AND " + _water_like("medium", "moderate")

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


# ── plant_uses junction helpers (schema v13) ──────────────────────────────────

def get_plant_uses(plant_id: int) -> list[str]:
    """Return the set of canonical use keys attached to ``plant_id``."""
    conn = get_connection()
    try:
        rows = conn.execute(
            "SELECT u.key FROM plant_uses pu "
            "JOIN uses u ON u.id = pu.use_id "
            "WHERE pu.plant_id = ? ORDER BY u.sort_order",
            (plant_id,),
        ).fetchall()
        return [r[0] for r in rows]
    finally:
        conn.close()


def plants_with_use(use_key: str) -> set[int]:
    """Return the set of plant ids tagged with ``use_key``."""
    conn = get_connection()
    try:
        rows = conn.execute(
            "SELECT pu.plant_id FROM plant_uses pu "
            "JOIN uses u ON u.id = pu.use_id "
            "WHERE u.key = ?",
            (use_key,),
        ).fetchall()
        return {r[0] for r in rows}
    finally:
        conn.close()


def plant_uses_for_ids(plant_ids: list[int]) -> dict[int, set[str]]:
    """
    Bulk variant: returns ``{plant_id: {use_key, ...}, ...}`` for the
    plants in ``plant_ids``. Empty input → empty dict. Designed for the
    analysis panel, which needs per-plant tag sets for the whole design.
    """
    if not plant_ids:
        return {}
    conn = get_connection()
    try:
        qmarks = ",".join("?" * len(plant_ids))
        rows = conn.execute(
            f"SELECT pu.plant_id, u.key FROM plant_uses pu "
            f"JOIN uses u ON u.id = pu.use_id "
            f"WHERE pu.plant_id IN ({qmarks})",
            list(plant_ids),
        ).fetchall()
        out: dict[int, set[str]] = {}
        for r in rows:
            out.setdefault(r[0], set()).add(r[1])
        return out
    finally:
        conn.close()


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


# ── Climate cache (schema v14, V1.35) ────────────────────────────────────────
#
# Stores derived growing-degree-day + frost-window stats from
# Open-Meteo Historical Weather, keyed by lat/lng quantized to 0.01°
# (~1 km). The fetch costs several seconds against the live API, so
# caching it per location lets the UI stay responsive when the user
# nudges the property pin around.
#
# These helpers are the storage layer only; the orchestration (fetch
# on cache miss, derive stats, persist) lives in src/climate.py.

def _quantize_latlng(lat: float, lng: float) -> tuple[int, int]:
    """Project (lat, lng) to integer keys at 0.01° resolution. ~1 km
    granularity is fine — GDD and frost dates don't change meaningfully
    over that scale outside mountain valleys."""
    return int(round(lat * 100)), int(round(lng * 100))


def get_cached_climate(lat: float, lng: float) -> Optional[dict]:
    """Return the cached climate-summary dict for (lat, lng), or None on
    miss. Caller is responsible for fetching + storing on a miss."""
    lat_q, lng_q = _quantize_latlng(lat, lng)
    conn = get_connection()
    try:
        row = conn.execute(
            "SELECT gdd5_mean, last_spring_frost_doy, first_fall_frost_doy, "
            "frost_free_days, years_used, source, cached_at "
            "FROM climate_cache WHERE lat_q = ? AND lng_q = ?",
            (lat_q, lng_q),
        ).fetchone()
        if row is None:
            return None
        return {
            "gdd5_mean":             row["gdd5_mean"],
            "last_spring_frost_doy": row["last_spring_frost_doy"],
            "first_fall_frost_doy":  row["first_fall_frost_doy"],
            "frost_free_days":       row["frost_free_days"],
            "years_used":            row["years_used"],
            "source":                row["source"],
            "cached_at":             row["cached_at"],
        }
    finally:
        conn.close()


def store_cached_climate(lat: float, lng: float, summary: dict) -> None:
    """Persist a climate summary for (lat, lng). Overwrites any prior
    cached row at the same quantized location."""
    lat_q, lng_q = _quantize_latlng(lat, lng)
    conn = get_connection()
    try:
        conn.execute(
            "INSERT OR REPLACE INTO climate_cache "
            "(lat_q, lng_q, gdd5_mean, last_spring_frost_doy, "
            " first_fall_frost_doy, frost_free_days, years_used, source, "
            " cached_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)",
            (
                lat_q, lng_q,
                summary.get("gdd5_mean"),
                summary.get("last_spring_frost_doy"),
                summary.get("first_fall_frost_doy"),
                summary.get("frost_free_days"),
                summary.get("years_used"),
                summary.get("source"),
            ),
        )
        conn.commit()
    finally:
        conn.close()


def get_cached_wind(lat: float, lng: float) -> Optional[dict]:
    """Return the cached wind-rose dict for (lat, lng), or None on miss.
    The rose is stored as JSON (nested annual/seasonal blocks)."""
    import json as _json
    lat_q, lng_q = _quantize_latlng(lat, lng)
    conn = get_connection()
    try:
        row = conn.execute(
            "SELECT rose_json, cached_at FROM wind_cache "
            "WHERE lat_q = ? AND lng_q = ?",
            (lat_q, lng_q),
        ).fetchone()
        if row is None:
            return None
        try:
            rose = _json.loads(row["rose_json"])
        except (ValueError, TypeError):
            return None
        rose["cached_at"] = row["cached_at"]
        return rose
    finally:
        conn.close()


def store_cached_wind(lat: float, lng: float, rose: dict) -> None:
    """Persist a wind rose for (lat, lng). Overwrites any prior cached row at
    the same quantized location."""
    import json as _json
    lat_q, lng_q = _quantize_latlng(lat, lng)
    conn = get_connection()
    try:
        conn.execute(
            "INSERT OR REPLACE INTO wind_cache "
            "(lat_q, lng_q, rose_json, source, cached_at) "
            "VALUES (?, ?, ?, ?, CURRENT_TIMESTAMP)",
            (lat_q, lng_q, _json.dumps(rose), rose.get("source")),
        )
        conn.commit()
    finally:
        conn.close()
