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

from src.log import get_logger
from src.resources import resource_path

_log = get_logger(__name__)

# ── Paths ─────────────────────────────────────────────────────────────────────

_HERE        = os.path.dirname(os.path.abspath(__file__))
# Resolve through resource_path so the schema is found inside a PyInstaller
# bundle (where a module's __file__ is unreliable), not just in a source tree.
_SCHEMA_PATH = resource_path("src", "db", "schema.sql")

# The photo slots (schema v55, F70), in the order `_attach_photos` prefers them
# when it synthesizes `image_url`. `habit` leads deliberately: the whole plant
# with something for scale is what someone deciding whether they want it — or
# trying to find it in their own yard in May — actually needs, and it is the
# frame iNaturalist's leading photo almost never is.
PHOTO_SLOTS = ("habit", "flower", "leaf", "fruit", "bark_stem", "winter",
               "seedling")
_PLANT_PHOTOS_JSON_PATH = resource_path("data", "plant_photos.json")


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
_BEE_ATTR_JSON_PATH     = resource_path("data", "bee_attributes_master.json")
_LEP_ATTR_JSON_PATH     = resource_path("data", "lepidoptera_attributes_master.json")
_NURSERIES_JSON_PATH    = resource_path("data", "nurseries_master.json")

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
# v30 (V1.87): no DDL — reseed for the type re-tag (herb split into
# wildflower / herb-foliage; graminoids/aquatics fixed by genus).
# v31 (V1.90): add flower_color + flower_form columns (3D flowers) and reseed
# to fill them from the curated seed JSON.
# v32 (V1.91): no DDL — reseed for the expanded flower forms (rays / plume /
# globe / trumpet) and straw seed-head plumes on grasses.
# v33 (V1.92): no DDL — reseed for curated marsh aquatics (cattail brown spike,
# bulrush, yellow pond-lily) feeding the new 3D aquatic/cattail geometry.
# v34 (V1.94): no DDL — reseed for the legume "pea" + bee-balm "whorl" flower
# forms (lupines / vetches / milkvetches / Monarda) feeding the expanded 3D
# flower sprite library + the genus-specific tree/shrub geometry.
# v35 (V2.0): no DDL — reseed for curated fruit_color on fleshy-fruited species
# (saskatoon, chokecherry, currants, viburnum, rose hips…) feeding the new 3D
# berry layer shown in each plant's fruit season.
# v36 (V2.1): no DDL — reseed for the new star / cross / lily flower forms
# (flax, geranium, phlox, draba, blue-eyed grass, wood lily, camas…).
# v37 (V2.2): dropped the denormalized plants.permaculture_uses column; the
# plant_uses junction is now the single source of truth and the legacy
# comma-blob field is synthesized on read. Reseed rebuilds plant_uses.
# v38 (V2.3): no DDL — reseed to expand EXAMPLE_POLYCULTURES to full retail-native
# coverage (every native sold at native nurseries / garden centres / big-box) and
# to add the multi-valued "By Function" Group-By facet (derived from plant uses).
# v39 (V2.07): added the `bee_attributes` table (F37 "see what a bee sees") — per
# bee-species nesting habit, tongue length, flight season, and floral-host genera,
# seeded from data/bee_attributes_master.json + an expanded Alberta Apidae roster
# in data/fauna_master.json. Reseed wipes/repopulates bee_attributes with fauna.
# v40 (V2.12): added the `lepidoptera_attributes` table (F37 "fly as a butterfly")
# — per-species flight season, adult-nectar genera, overwintering stage and
# activity for Alberta's butterflies & moths, seeded from
# data/lepidoptera_attributes_master.json. Powers the fly-through's butterfly/moth
# targets, bloom-accurate nectar beacons, and the seasonal nectar tour. Reseed
# wipes/repopulates lepidoptera_attributes with fauna.
# v41 (V2.12): no DDL — reseed to pick up ~50 curated documented `nectar`
# plant↔lepidoptera edges (data/plant_fauna_master.json) for the flagship
# butterflies & day-flying moths, so ambient wildlife (scene_wildlife) can place
# nectaring butterflies from real edges and the habitat builder shows documented
# (not just genus-inferred) nectar sources.
# v42 (V2.15): province-neutral data model — `ab_ecoregion` renamed to
# `ecoregion` (+ native_province) for the Saskatchewan integration; the old
# name survives as a read-side alias for the frozen agent-API contract.
# v43 (V2.16): no DDL — reseed for the Saskatchewan grassland flora + fauna.
# v44 (V2.18): added the `nurseries` table (native-plant supplier directory),
# seeded from data/nurseries_master.json; wiped + reseeded on every bump.
# v45 (V2.19): no DDL — reseed for the native-only supplier list (NPSS) and
# the Lumsden soil-pH plant-matching fixes.
# v46 (V2.22): added polycultures.origin ('seed' | 'user'). The reseed now
# wipes ONLY origin='seed' rows, so communities users author in the builder
# finally survive schema bumps (they were silently destroyed on every bump
# since the builder shipped). _migrate_to_v46 adds the column to old DBs and
# stamps the shipped examples by name so the first v46 reseed doesn't
# duplicate them.
# v50 (V2.30): no DDL — reseed for the morphology of data/garden_plants.json.
# Those five rows (both apples, Evans and Nanking cherry, bee balm) were the
# ONLY species in the catalogue with no leaf_shape / leaf_size_cm / bark_color:
# the two morphology scripts both target plants_master.json and nothing covered
# the garden file. Since V2.29 a plant's recorded leaf characters select its
# baked archetype variant and put its blade outline into a tree crown's
# silhouette, so those five fell back to neutral defaults — and three of them
# are trees sitting next to each other, which a user picked out of the sprite
# contact sheet as "three near-identical green blobs".
# See scripts/seed_garden_morphology.py for the values and their sourcing.
# v51 (V2.31, F7): the `relationship_edges` VIEW — one queryable edges layer over
# plant_fauna + companion_friends + companion_enemies + shared polyculture
# membership, read by src/db/relationships.py. A VIEW, not a table: the
# per-relationship tables stay the source of truth, so no seeder changes, no new
# reseed wipe entry, and no second copy to drift. schema.sql DROPs and recreates
# it on every init_db, so the definition can evolve without a migration; the
# version bump is here because schema.sql changed, per CLAUDE.md.
# v56 (V2.36): `plants.flower_data_citation` — WHICH source a flower number came
# from, beside v55's `flower_data_source` which records only what KIND of source
# it was. "Read in a flora" that does not name the flora is not a citation, and
# the catalogue is about to start carrying values read out of published
# descriptions. Free text, per species; same shape as `safety_source`.
# v57 (V2.36): `plants.leaf_data_source` + `plants.leaf_data_citation` — the same
# pair for the leaf and habit characters, which the bench can now edit. Those
# columns were seeded by genus-level estimate for all 434 species and are about
# to start being corrected out of a flora; without provenance the catalogue
# cannot tell a read value from a guessed one, which is the whole point of v55
# and v56. Kept separate from the flower pair because the two get verified in
# different sittings from different sources.
# v58 (V2.36): fauna morphology on `bee_attributes` + `lepidoptera_attributes`.
# The animals were where the plants were before V2.33 — every creature's look
# was derived in src/scene_wildlife.py from substrings of its COMMON NAME, so 69
# bees shared 12 appearances (29 bumblebees identical) and 31 lepidoptera shared
# 16. Bees gain body length, build, two colours, metallic, scopa, wing tint and
# the per-tergite `band_pattern`; leps gain a wingspan RANGE (the fauna data's
# first real measurement), three wing colours, shape, pattern, eyespots, resting
# posture and flight_style. Both gain a morph_data_source/citation pair.
# v59 (V2.38): the `plant_ecoregions` table — per-species ecoregion range WITH
# the evidence behind it. `plants.ecoregion` holds tags that were generated
# heuristically and never sourced; a user caught it (Saskatoon Berry, a
# defining Aspen Parkland shrub, tagged only mixedgrass + moist mixedgrass).
# Each row carries the georeferenced record count and a confidence band, so
# three records and three hundred stop being the same claim (P9). Derived by
# scripts/seed_ecoregion_ranges.py from GBIF into data/plant_ecoregions.json.
# The column stays: it is the fallback for species the derivation has not run
# for, and the only home for riparian / wet_meadow, which are site-scale
# moisture niches no coordinate can assert.
# v60 (V2.38): no DDL — reseed to pick up data/plant_ecoregions.json, the
# GBIF-derived per-species ecoregion ranges. 427 species now carry a sourced
# range with an occurrence count behind it.
# v62 (V2.43): +discovered_species, +learn_state — the Learn-mode species
# ledger. Both are USER-AUTHORED and are deliberately absent from the reseed
# wipe block below; see their comment in schema.sql. The bump exists only so
# the CREATE TABLEs reach existing installs.
_SCHEMA_VERSION = 62

# Tolerance (pH units) added at each end of a plant's soil-pH bracket when
# matching against a site's (often coarse, regional) pH estimate. See the
# soil_ph filter in search_plants (P9 — uncertainty, not false precision).
_SOIL_PH_TOLERANCE = 0.5


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


def _migrate_to_v31(conn: sqlite3.Connection):
    """Add the flower colour + form columns (V1.90) used by the 3D viewer to
    render real-coloured flowers. The version bump triggers a reseed that fills
    the values from the seed JSON."""
    new_columns = [
        ("flower_color", "TEXT DEFAULT ''"),
        ("flower_form",  "TEXT DEFAULT 'none'"),
    ]
    for col_name, col_def in new_columns:
        try:
            conn.execute(f"ALTER TABLE plants ADD COLUMN {col_name} {col_def}")
        except sqlite3.OperationalError:
            pass  # column already present
    conn.commit()


def _migrate_to_v35(conn: sqlite3.Connection):
    """Add the fruit colour column (V2.0) used by the 3D viewer to render berries
    on fleshy-fruited plants in their fruit season. The bump triggers a reseed
    that fills it from the curated seed JSON."""
    try:
        conn.execute("ALTER TABLE plants ADD COLUMN fruit_color TEXT DEFAULT ''")
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


def _migrate_to_v42(conn: sqlite3.Connection):
    """Province-neutral data model (V2.15, Saskatchewan expansion).

    Renames ``plants.ab_ecoregion`` -> ``plants.ecoregion`` (the ecoregion is
    not province-specific — P1/P2) and adds a ``native_provinces`` column to
    ``plants`` and ``fauna`` (comma-separated province codes, e.g. ``"AB,SK"``).
    All ALTERs are guarded so a fresh install (schema.sql already has the new
    shape) skips them; the version bump triggers a reseed that fills the new
    values from the seed JSON. ``native_to_alberta`` / ``ab_native`` are kept as
    back-compat flags.

    Column resolution handles both entry paths cleanly: on a v41 upgrade the
    table has only ``ab_ecoregion`` (rename it); on a fresh install the DDL
    already created ``ecoregion`` and the historical v11 migration re-added a
    stray empty ``ab_ecoregion`` (drop it)."""
    cols = {r[1] for r in conn.execute("PRAGMA table_info(plants)").fetchall()}
    if "ecoregion" not in cols and "ab_ecoregion" in cols:
        conn.execute("ALTER TABLE plants RENAME COLUMN ab_ecoregion TO ecoregion")
    elif "ecoregion" in cols and "ab_ecoregion" in cols:
        try:
            conn.execute("ALTER TABLE plants DROP COLUMN ab_ecoregion")
        except sqlite3.OperationalError:
            pass  # SQLite < 3.35 — harmless; _row_to_dict aliases authoritatively
    for table in ("plants", "fauna"):
        try:
            conn.execute(f"ALTER TABLE {table} ADD COLUMN native_provinces TEXT")
        except sqlite3.OperationalError:
            pass  # column already present
    conn.commit()


def _migrate_to_v55(conn: sqlite3.Connection):
    """Photo sets with named slots (V2.35, F70).

    Creates the table. The BACK-FILL of existing `plants.image_url` values into
    `flower`-slot rows lives in `_seed_plant_photos`, not here: on a fresh
    install the migration chain runs BEFORE the reseed populates `plants`, so a
    back-fill at this point would silently find nothing and the coverage report
    would say every species has no photo while 328 of them plainly do.
    """
    conn.executescript(_photo_ddl())
    # ...and where each flower number came from (P9). Additive and nullable;
    # empty reads as "unknown provenance", which is honest for a DB that
    # predates the column.
    try:
        conn.execute("ALTER TABLE plants ADD COLUMN flower_data_source TEXT DEFAULT ''")
    except sqlite3.OperationalError:
        pass
    conn.commit()


def _migrate_to_v56(conn: sqlite3.Connection):
    """Which source a flower number came from (V2.36).

    `flower_data_source` records the *kind* of source — estimated, read off a
    photo, read in a flora, measured with a ruler. It does not record *which*,
    and "read in a flora" without naming the flora is not a citation. That was
    tolerable while every value was the seeder's genus default and the honest
    answer was "a general botanical convention"; it stops being tolerable the
    moment somebody starts typing numbers out of published descriptions, because
    then the catalogue is making a specific claim it cannot attribute.

    Free text on purpose, and per species rather than per value: a person tunes
    one species in one sitting out of one book. `apply_safety_tags.py` already
    does exactly this with `safety_source`.
    """
    try:
        conn.execute(
            "ALTER TABLE plants ADD COLUMN flower_data_citation TEXT DEFAULT ''")
    except sqlite3.OperationalError:
        pass
    conn.commit()


def _migrate_to_v57(conn: sqlite3.Connection):
    """The same provenance pair, for the leaf and habit characters (V2.36).

    v55/v56 gave the flower columns a source and a citation because the bench
    was about to start correcting them out of published descriptions. The bench
    now edits `leaf_shape`, `leaf_size_cm`, `leaf_arrangement`, `leaf_surface`,
    `growth_form`, `branching` and `mature_height_m` as well — and those are in
    a worse position than the flower columns ever were, because they are
    populated for ALL 434 species by a genus-level estimate rather than left
    blank. A wrong estimate is indistinguishable from a checked value, and
    every one of them changes what the 3D viewer draws.

    Two columns rather than reusing the flower pair: leaf and flower characters
    get verified in different sittings from different sources. A photograph
    settles petal count; a flora settles leaf length. One shared citation would
    have to be overwritten by whichever was checked last.
    """
    for col in ("leaf_data_source", "leaf_data_citation"):
        try:
            conn.execute(f"ALTER TABLE plants ADD COLUMN {col} TEXT DEFAULT ''")
        except sqlite3.OperationalError:
            pass
    conn.commit()


def _migrate_to_v61(conn: sqlite3.Connection):
    """Sourcing columns on the companion tables (V2.42).

    The new tables in v61 (``plant_fauna_derived``, ``fauna_fauna``) need no
    migration — ``schema.sql`` creates them with ``IF NOT EXISTS`` on every
    ``init_db``. The companion tables DO: ``CREATE TABLE IF NOT EXISTS`` is a
    no-op against an existing table, so an install upgrading from v60 would keep
    two-column ``companion_friends``/``companion_enemies`` while the recreated
    ``relationship_edges`` view selects ``cf.source`` — and every relationship
    query would fail with "no such column" on a DB that had merely been used
    before.

    Deliberately additive and empty. A companion pairing with no source reads
    ``recorded`` rather than ``documented``, which is the honest state for data
    nobody has cited; filling these in is how a pairing earns the stronger word.
    """
    for table in ("companion_friends", "companion_enemies"):
        for col in ("source", "notes"):
            try:
                conn.execute(
                    f"ALTER TABLE {table} ADD COLUMN {col} TEXT DEFAULT ''")
            except sqlite3.OperationalError:
                pass                      # column already present
    conn.commit()


def _migrate_to_v59(conn: sqlite3.Connection):
    """The evidence behind a species' ecoregion range (V2.38).

    Pure additive DDL — ``schema.sql`` creates ``plant_ecoregions`` with
    ``IF NOT EXISTS`` on every ``init_db``, so this exists mainly to be the
    documented home of the reasoning and to be explicit for a DB that upgrades
    without a reseed. Nothing is migrated INTO it: the existing
    ``plants.ecoregion`` tags are unsourced, and copying them here would launder
    a guess into a row that looks derived, which is the exact failure this table
    is meant to end (P9). The table stays empty until
    ``scripts/seed_ecoregion_ranges.py`` has run and its output is seeded.
    """
    conn.execute("""
        CREATE TABLE IF NOT EXISTS plant_ecoregions (
            plant_id    INTEGER NOT NULL REFERENCES plants(id) ON DELETE CASCADE,
            ecoregion   TEXT    NOT NULL,
            occurrences INTEGER NOT NULL DEFAULT 0,
            confidence  TEXT    NOT NULL DEFAULT 'low',
            source      TEXT    NOT NULL DEFAULT '',
            PRIMARY KEY (plant_id, ecoregion)
        )""")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_plant_ecoregions_region "
                 "ON plant_ecoregions(ecoregion)")
    conn.commit()


def _migrate_to_v58(conn: sqlite3.Connection):
    """What the animals look like, as data (V2.36).

    The fauna were in the state the flora were in before V2.33, only worse
    because nothing said so. Every creature's appearance was computed in
    `src/scene_wildlife.py` from substrings of its common name — a twelve-genus
    bee table and seventeen `if "azure" in name` tests — which meant:

      * 69 bees rendered as 12 distinct animals; the 29 Bombus were identical
        to one another, as were all 20 cuckoo bees;
      * 31 lepidoptera rendered as 16; a Polyphemus, a Cecropia and an Isabella
        Tiger Moth were the same moth;
      * no size was a measurement — `size` was a hand-tuned 0.5-1.25 multiplier
        in Python, so a 140 mm Cecropia and a 22 mm azure differed by a fudge
        factor rather than by a fact.

    None of it lived in the database, so none of it could be sourced, checked or
    corrected without editing code. These columns move it into the catalogue
    where `scripts/tune_fauna.py` can edit it and the data-quality gate can
    validate it.

    On the existing attribute tables rather than new ones: they are already 1:1
    with `fauna`, already taxon-specific for exactly this reason (the schema
    comment above says so), and already wiped and re-seeded with fauna, so this
    needs no new reseed-wipe entry.
    """
    bee = ("body_length_mm REAL", "build TEXT", "hair_colour TEXT",
           "integument_colour TEXT", "metallic INTEGER", "scopa_position TEXT",
           "wing_tint TEXT", "band_pattern TEXT",
           "morph_data_source TEXT DEFAULT ''",
           "morph_data_citation TEXT DEFAULT ''")
    lep = ("wingspan_min_mm REAL", "wingspan_max_mm REAL",
           "forewing_colour TEXT", "hindwing_colour TEXT", "margin_colour TEXT",
           "wing_shape TEXT", "wing_pattern TEXT", "eyespot_count INTEGER",
           "resting_posture TEXT", "flight_style TEXT",
           "morph_data_source TEXT DEFAULT ''",
           "morph_data_citation TEXT DEFAULT ''")
    for table, cols in (("bee_attributes", bee), ("lepidoptera_attributes", lep)):
        for col in cols:
            try:
                conn.execute(f"ALTER TABLE {table} ADD COLUMN {col}")
            except sqlite3.OperationalError:
                pass                      # already there
    conn.commit()


def _photo_ddl() -> str:
    """The plant_photos DDL, lifted out of schema.sql so the v55 migration can
    run it on a DB that predates the table. schema.sql stays authoritative — this
    reads it rather than restating it, so the two can never drift."""
    with open(_SCHEMA_PATH, "r", encoding="utf-8") as fh:
        sql = fh.read()
    # Between the markers, not by regex: a `;` inside a `--` comment in the
    # table body truncated the first attempt mid-statement, and SQLite's error
    # for that ("near CREATE") points nowhere near the cause.
    start = sql.find(">>> plant_photos")
    end = sql.find("<<< plant_photos")
    if start < 0 or end < 0:
        raise RuntimeError("schema.sql lost its plant_photos markers")
    return sql[sql.index("\n", start) + 1:sql.rfind("\n", start, end)]


def _migrate_to_v54(conn: sqlite3.Connection):
    """How many inflorescences a mature plant carries (V2.35).

    Additive and nullable. Empty falls back to a count derived from
    stem_branching and stature in the viewer, so an unmigrated or unseeded
    install draws a sensible plant rather than a bare one.
    """
    try:
        conn.execute("ALTER TABLE plants ADD COLUMN flowering_stems INTEGER")
    except sqlite3.OperationalError:
        pass              # already present -> fresh install / already migrated
    conn.commit()


def _migrate_to_v53(conn: sqlite3.Connection):
    """The bloom as something to build (V2.34).

    Ten columns describing a flower as characters rather than as one of fifteen
    64x64 pictures. Additive and nullable, filled by the reseed that follows the
    version bump; where a species records nothing the viewer draws exactly the
    billboard it drew before, so partial coverage degrades to today rather than
    to a hole. See scripts/seed_flower_morphology.py.
    """
    for ddl in (
        "ALTER TABLE plants ADD COLUMN flower_arch TEXT DEFAULT ''",
        "ALTER TABLE plants ADD COLUMN flower_symmetry TEXT DEFAULT ''",
        "ALTER TABLE plants ADD COLUMN petal_shape TEXT DEFAULT ''",
        "ALTER TABLE plants ADD COLUMN petal_count INTEGER",
        "ALTER TABLE plants ADD COLUMN florets_per_head INTEGER",
        "ALTER TABLE plants ADD COLUMN flower_diameter_cm REAL",
        "ALTER TABLE plants ADD COLUMN flower_center_color TEXT DEFAULT ''",
        "ALTER TABLE plants ADD COLUMN flower_height_frac REAL",
        "ALTER TABLE plants ADD COLUMN stem_branching TEXT DEFAULT ''",
        "ALTER TABLE plants ADD COLUMN basal_rosette INTEGER DEFAULT 0",
    ):
        try:
            conn.execute(ddl)
        except sqlite3.OperationalError:
            pass          # already present -> fresh install / already migrated
    conn.commit()


def _migrate_to_v52(conn: sqlite3.Connection):
    """Surface character + the graminoid inflorescence (V2.33).

    Additive and nullable, filled by the reseed that follows the version bump.
    Every consumer falls back to its previous behaviour where they are empty —
    a per-genus bark grain, a matte leaf, the generic plume — so an upgraded DB
    is never in a broken intermediate state. See
    scripts/seed_surface_morphology.py and
    scripts/seed_inflorescence_morphology.py for the fields and their sourcing.
    """
    for ddl in (
        "ALTER TABLE plants ADD COLUMN bark_texture TEXT DEFAULT ''",
        "ALTER TABLE plants ADD COLUMN leaf_surface TEXT DEFAULT ''",
        "ALTER TABLE plants ADD COLUMN inflorescence_form TEXT DEFAULT ''",
    ):
        try:
            conn.execute(ddl)
        except sqlite3.OperationalError:
            pass          # already present → fresh install / already migrated
    conn.commit()


def _migrate_to_v49(conn: sqlite3.Connection):
    """Fruit SHAPE column (V2.29). Additive and nullable, filled by the reseed
    that follows the version bump; empty on dry-fruited species, which draw no
    fruit at all. The viewer falls back to the round `berry` sprite where it is
    empty, so an upgraded DB is never in a broken intermediate state."""
    try:
        conn.execute("ALTER TABLE plants ADD COLUMN fruit_form TEXT DEFAULT ''")
    except sqlite3.OperationalError:
        pass          # already present → fresh install / already migrated
    conn.commit()


def _migrate_to_v48(conn: sqlite3.Connection):
    """Herbaceous growth-form column (V2.29). Additive and nullable, filled by
    the reseed that follows the version bump; empty for woody plants."""
    try:
        conn.execute("ALTER TABLE plants ADD COLUMN growth_form TEXT DEFAULT ''")
    except sqlite3.OperationalError:
        pass          # already present → fresh install / already migrated
    conn.commit()


def _migrate_to_v47(conn: sqlite3.Connection):
    """Botanical morphology columns (V2.29) — what a species looks like.

    Additive and nullable: the reseed that follows the version bump fills them
    for the woody species, and every consumer falls back to its previous
    behaviour where they are empty, so an upgraded DB is never in a broken
    intermediate state. See scripts/seed_woody_morphology.py for the fields and
    where their values come from.
    """
    for ddl in (
        "ALTER TABLE plants ADD COLUMN leaf_shape TEXT DEFAULT ''",
        "ALTER TABLE plants ADD COLUMN leaf_size_cm REAL",
        "ALTER TABLE plants ADD COLUMN leaf_arrangement TEXT DEFAULT ''",
        "ALTER TABLE plants ADD COLUMN bark_color TEXT DEFAULT ''",
        "ALTER TABLE plants ADD COLUMN fall_color TEXT DEFAULT ''",
        "ALTER TABLE plants ADD COLUMN branching TEXT DEFAULT ''",
    ):
        try:
            conn.execute(ddl)
        except sqlite3.OperationalError:
            pass          # already present → fresh install / already migrated
    conn.commit()


def _migrate_to_v46(conn: sqlite3.Connection):
    """Polyculture provenance (V2.22) — the end of reseed data loss.

    Adds ``polycultures.origin`` ('seed' | 'user') so the reseed can wipe
    shipped examples without touching communities the user authored in the
    builder. On an upgraded DB every existing row lands as 'user' (the safe
    default); the shipped examples are then re-stamped 'seed' **by name**
    so the reseed that immediately follows this migration replaces them
    instead of duplicating them. A user community that happens to share an
    example's name is treated as the example (replaced) — the pre-v46
    behaviour for every community, now confined to that one collision.
    """
    try:
        conn.execute("ALTER TABLE polycultures "
                     "ADD COLUMN origin TEXT NOT NULL DEFAULT 'user'")
    except sqlite3.OperationalError:
        return  # column already present → fresh install / already migrated
    from src.db.polycultures import EXAMPLE_POLYCULTURES  # lazy: avoid cycle

    def _names(defs):
        for d in defs:
            yield d["name"]
            yield from _names(d.get("variations", []))

    names = list(_names(EXAMPLE_POLYCULTURES))
    qmarks = ",".join("?" for _ in names)
    conn.execute(
        f"UPDATE polycultures SET origin = 'seed' WHERE name IN ({qmarks})",
        names)
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


def _seed_plant_photos(conn: sqlite3.Connection) -> int:
    """Load ``data/plant_photos.json`` into ``plant_photos`` as origin='seed'
    (V2.35, F70). Returns the number of rows inserted.

    Runs on EVERY reseed and inserts only shipped rows, because the wipe above
    removed only shipped rows — a person's own photographs (origin='user') are
    still sitting in the table and must not be duplicated or disturbed.

    A species the file doesn't mention keeps whatever ``plants.image_url`` the
    fetch script gave it: ``_attach_photos`` prefers this table and falls back to
    the column, so partial coverage degrades to the previous release rather than
    to a blank (P9).
    """
    import json as _json                                 # noqa: PLC0415

    if not os.path.exists(_PLANT_PHOTOS_JSON_PATH):
        return 0
    with open(_PLANT_PHOTOS_JSON_PATH, "r", encoding="utf-8") as fh:
        entries = _json.load(fh)
    rows = []
    for e in entries:
        sci = (e.get("scientific_name") or "").strip()
        slot = (e.get("slot") or "").strip()
        url = (e.get("url") or "").strip()
        if not sci or slot not in PHOTO_SLOTS or not url:
            continue
        rows.append((sci, slot, url, e.get("attribution") or "",
                     e.get("license") or "", e.get("source") or "",
                     "seed", e.get("taken_on") or "",
                     int(e.get("rank") or 0), e.get("notes") or ""))
    if rows:
        conn.executemany(
            "INSERT INTO plant_photos (scientific_name, slot, url, attribution,"
            " license, source, origin, taken_on, rank, notes)"
            " VALUES (?,?,?,?,?,?,?,?,?,?)", rows)

    # Back-fill: every species that still has NO row in this table but does have
    # the legacy single `plants.image_url` gets it as a `flower` row. That is
    # honest about what those photos are — iNaturalist's leading photo is nearly
    # always a flower macro, which is exactly the diagnosis behind F70 — and it
    # makes this table the single place `coverage()` has to look. Nothing is
    # lost by the upgrade, and the 111 species with no photo at all become a
    # counted, visible gap instead of an invisible one.
    cur = conn.execute(
        "INSERT INTO plant_photos "
        "  (scientific_name, slot, url, attribution, license, source, origin)"
        " SELECT p.scientific_name, 'flower', p.image_url,"
        "        COALESCE(p.image_attribution, ''), COALESCE(p.image_license, ''),"
        "        'inaturalist', 'seed'"
        "   FROM plants p"
        "  WHERE p.scientific_name IS NOT NULL AND p.scientific_name <> ''"
        "    AND p.image_url IS NOT NULL AND p.image_url <> ''"
        # Dedupe on the PHOTO, not on the species. Scoping it to the species
        # meant that adding one photograph of your own permanently suppressed
        # the shipped one for that plant on the next reseed — the row was gone
        # (wiped as origin='seed') and the back-fill then skipped the species
        # because it "already had" a photo.
        "    AND NOT EXISTS (SELECT 1 FROM plant_photos ph"
        "                     WHERE ph.scientific_name = p.scientific_name"
        "                       AND ph.url = p.image_url)")
    conn.commit()
    return len(rows) + (cur.rowcount or 0)


_ECOREGION_RANGES_PATH = resource_path("data", "plant_ecoregions.json")


def _seed_plant_ecoregions(conn: sqlite3.Connection) -> int:
    """Populate ``plant_ecoregions`` from ``data/plant_ecoregions.json``.

    Keyed by scientific name in the file (plant ids are not stable across a
    reseed) and resolved to ids here, the same shape ``_seed_fauna`` uses for
    its links. Returns the number of rows inserted.

    A missing or empty file is not an error and never will be: the derivation
    is a dev-time GBIF run (``scripts/seed_ecoregion_ranges.py``) that has not
    necessarily happened for every species, and a species with no derived rows
    keeps the tags in ``plants.ecoregion``. Failing here would take the whole
    catalogue down over a file whose entire job is to be optional.
    """
    import json as _json                                 # noqa: PLC0415
    try:
        with open(_ECOREGION_RANGES_PATH, "r", encoding="utf-8") as f:
            raw = _json.load(f)
    except (FileNotFoundError, _json.JSONDecodeError, OSError):
        return 0
    if not isinstance(raw, dict):
        return 0

    from src.ecoregion_ranges import parse_document
    from src.ecoregion import geographic_keys

    ranges = parse_document(raw)
    if not ranges:
        return 0
    source = str(raw.get("source") or "")
    # A key that is not in the shipped polygon vocabulary would be invisible in
    # every filter — drop it here rather than storing a row nothing can select.
    valid = set(geographic_keys())
    name_to_id = {
        (row["scientific_name"] or "").strip(): row["id"]
        for row in conn.execute(
            "SELECT id, scientific_name FROM plants").fetchall()
    }
    rows = []
    for name, entries in ranges.items():
        plant_id = name_to_id.get(name)
        if plant_id is None:
            continue
        for entry in entries:
            if entry["ecoregion"] not in valid:
                continue
            rows.append((plant_id, entry["ecoregion"], entry["occurrences"],
                         entry["confidence"], source))
    if not rows:
        return 0
    conn.executemany(
        "INSERT OR REPLACE INTO plant_ecoregions "
        "(plant_id, ecoregion, occurrences, confidence, source) "
        "VALUES (?, ?, ?, ?, ?)", rows)
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
        def _fauna_provinces(e: dict) -> str:
            # Explicit JSON value wins; else derive "AB" from the ab_native flag
            # (province-neutral generalization added in schema v42).
            np = e.get("native_provinces")
            if isinstance(np, list):
                return ",".join(np)
            if np is not None:
                return str(np)
            return "AB" if int(e.get("ab_native", 1)) else ""

        fauna_rows = [
            (
                e["scientific_name"],
                e["common_name"],
                e["taxon"],
                int(e.get("ab_native", 1)),
                _fauna_provinces(e),
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
                " native_provinces, range_notes, icon, description, "
                " image_url, image_attribution, image_license) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
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
    unresolved: list[str] = []
    for entry in link_entries:
        # Skip metadata records (those without a 'plant' / 'fauna' key).
        if "plant" not in entry or "fauna" not in entry:
            continue
        pid = name_to_pid.get(entry["plant"])
        fid = sci_to_fid.get(entry["fauna"])
        if pid is None or fid is None:
            # V2.42: this used to be a bare `continue`. A typo in a plant or
            # fauna name deleted an edge with no error, no count and no way to
            # notice — the data-quality gate never opened this file either, so
            # the loss was invisible from both ends. The gate now resolves these
            # names (validate_plant_fauna), and a survivor here is reported so
            # a reseed cannot quietly shrink the graph.
            missing = "plant" if pid is None else "fauna"
            unresolved.append(f"{entry['plant']} ↔ {entry['fauna']} ({missing})")
            continue
        link_rows.append((
            pid,
            fid,
            entry.get("relationship", "larval_host"),
            entry.get("specificity"),
            entry.get("source"),
            entry.get("notes"),
        ))

    if unresolved:
        print(f"[seed] WARNING: {len(unresolved)} plant↔fauna link(s) dropped — "
              f"name did not resolve: {'; '.join(unresolved[:5])}"
              + (" …" if len(unresolved) > 5 else ""))

    if link_rows:
        conn.executemany(
            "INSERT OR IGNORE INTO plant_fauna "
            "(plant_id, fauna_id, relationship, specificity, source, notes) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            link_rows,
        )
        conn.commit()
    return len(link_rows)


def _opt_int(v):
    """`int(v)` or None. Keeps "not described" (None) distinct from a real 0 —
    `eyespot_count` 0 is a genuine value (most butterflies have none) and
    `metallic` 0 means "checked, and it is not"."""
    if v is None or v == "":
        return None
    try:
        return int(v)
    except (TypeError, ValueError):
        return None


def _seed_bee_attributes(conn: sqlite3.Connection) -> int:
    """
    Load ``data/bee_attributes_master.json`` into the ``bee_attributes`` table
    (schema v39, F37). Each record is keyed by ``scientific_name`` and resolved
    to the matching ``fauna`` row's id (bee rows only); records whose bee is not
    in the fauna registry are skipped. Idempotent via ``INSERT OR IGNORE`` on the
    ``fauna_id`` primary key. Returns the number of rows inserted.

    Mirrors ``_seed_fauna`` phase 2 and must run *after* ``_seed_fauna`` so the
    fauna registry exists to resolve scientific_name → fauna_id.
    """
    import json as _json

    if not os.path.exists(_BEE_ATTR_JSON_PATH):
        return 0

    with open(_BEE_ATTR_JSON_PATH, "r", encoding="utf-8") as f:
        entries = _json.load(f)

    sci_to_fid = {
        row["scientific_name"]: row["id"]
        for row in conn.execute(
            "SELECT id, scientific_name FROM fauna WHERE taxon = 'bee'"
        ).fetchall()
    }

    rows: list[tuple] = []
    for e in entries:
        # Skip metadata records (those without a 'scientific_name' key).
        if "scientific_name" not in e:
            continue
        fid = sci_to_fid.get(e["scientific_name"])
        if fid is None:
            continue
        pollen = e.get("pollen_specialist")
        rows.append((
            fid,
            e.get("genus"),
            e.get("nesting_habit"),
            e.get("host_genus"),
            e.get("tongue_length"),
            e.get("flight_season"),
            e.get("floral_host_genera"),
            int(pollen) if pollen is not None else None,
            e.get("conservation_status"),
            e.get("source"),
            e.get("notes"),
            # Morphology (v58). Absent in a record simply means "not described
            # yet" — the columns are nullable and the viewer keeps its genus
            # fallback, so a partly-filled catalogue degrades rather than breaks.
            e.get("body_length_mm"),
            e.get("build"),
            e.get("hair_colour"),
            e.get("integument_colour"),
            _opt_int(e.get("metallic")),
            e.get("scopa_position"),
            e.get("wing_tint"),
            e.get("band_pattern"),
            e.get("morph_data_source") or "",
            e.get("morph_data_citation") or "",
        ))

    if rows:
        conn.executemany(
            "INSERT OR IGNORE INTO bee_attributes "
            "(fauna_id, genus, nesting_habit, host_genus, tongue_length, "
            " flight_season, floral_host_genera, pollen_specialist, "
            " conservation_status, source, notes, "
            " body_length_mm, build, hair_colour, integument_colour, metallic, "
            " scopa_position, wing_tint, band_pattern, "
            " morph_data_source, morph_data_citation) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, "
            "        ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            rows,
        )
        conn.commit()
    return len(rows)


def _seed_lepidoptera_attributes(conn: sqlite3.Connection) -> int:
    """
    Load ``data/lepidoptera_attributes_master.json`` into the
    ``lepidoptera_attributes`` table (schema v40, F37 "fly as a butterfly").
    Each record is keyed by ``scientific_name`` and resolved to the matching
    ``fauna`` row's id (lepidoptera rows only); records whose species is not in
    the fauna registry are skipped. Idempotent via ``INSERT OR IGNORE`` on the
    ``fauna_id`` primary key. Returns the number of rows inserted.

    Mirrors ``_seed_bee_attributes`` and must run *after* ``_seed_fauna`` so the
    fauna registry exists to resolve scientific_name → fauna_id.
    """
    import json as _json

    if not os.path.exists(_LEP_ATTR_JSON_PATH):
        return 0

    with open(_LEP_ATTR_JSON_PATH, "r", encoding="utf-8") as f:
        entries = _json.load(f)

    sci_to_fid = {
        row["scientific_name"]: row["id"]
        for row in conn.execute(
            "SELECT id, scientific_name FROM fauna WHERE taxon = 'lepidoptera'"
        ).fetchall()
    }

    rows: list[tuple] = []
    for e in entries:
        # Skip metadata records (those without a 'scientific_name' key).
        if "scientific_name" not in e:
            continue
        fid = sci_to_fid.get(e["scientific_name"])
        if fid is None:
            continue
        rows.append((
            fid,
            e.get("kind"),
            e.get("activity"),
            e.get("flight_season"),
            e.get("overwintering_stage"),
            e.get("voltinism"),
            e.get("nectar_flower_genera"),
            e.get("larval_host_note"),
            e.get("conservation_status"),
            e.get("source"),
            e.get("notes"),
            # Morphology (v58) — nullable, so a partly-described catalogue
            # degrades to the viewer's name-table fallback rather than breaking.
            e.get("wingspan_min_mm"),
            e.get("wingspan_max_mm"),
            e.get("forewing_colour"),
            e.get("hindwing_colour"),
            e.get("margin_colour"),
            e.get("wing_shape"),
            e.get("wing_pattern"),
            _opt_int(e.get("eyespot_count")),
            e.get("resting_posture"),
            e.get("flight_style"),
            e.get("morph_data_source") or "",
            e.get("morph_data_citation") or "",
        ))

    if rows:
        conn.executemany(
            "INSERT OR IGNORE INTO lepidoptera_attributes "
            "(fauna_id, kind, activity, flight_season, overwintering_stage, "
            " voltinism, nectar_flower_genera, larval_host_note, "
            " conservation_status, source, notes, "
            " wingspan_min_mm, wingspan_max_mm, forewing_colour, "
            " hindwing_colour, margin_colour, wing_shape, wing_pattern, "
            " eyespot_count, resting_posture, flight_style, "
            " morph_data_source, morph_data_citation) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, "
            "        ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            rows,
        )
        conn.commit()
    return len(rows)


def _seed_derived_edges(conn: sqlite3.Connection) -> tuple[int, int]:
    """
    Materialise the derived relationship edges (schema v61, V2.42).

    Two products, both computed by ``src.db.derived_edges`` from data already
    shipped and already cited:

    * ``plant_fauna_derived`` — genus-level host records (``floral_host_genera``
      on bees, ``nectar_flower_genera`` on lepidoptera) expanded onto the
      catalogue's members of each genus. Takes plant coverage from 22.6% to
      ~46%, which is the difference between the relationship features working
      and not.
    * ``fauna_fauna`` — the cuckoo bees, whose ``host_genus`` is another BEE and
      who are therefore unreachable in a plant↔fauna-only graph.

    Must run AFTER ``_seed_bee_attributes`` / ``_seed_lepidoptera_attributes``
    (it reads the JSON, but the fauna ids it resolves against come from
    ``_seed_fauna``). Returns ``(plant_edges, fauna_edges)``.

    Nothing here invents a relationship: every row carries the citation of the
    record it was expanded from, plus the genus it matched on and a confidence
    band, so a reader can see exactly what was claimed and what this app did
    with it. See docs/DATA_AUDIT.md §6.
    """
    import json as _json
    from src.db.derived_edges import (           # noqa: PLC0415
        bee_genus_host_edges, lepidoptera_genus_host_edges, cleptoparasite_edges,
    )

    def _load(path):
        if not os.path.exists(path):
            return []
        with open(path, "r", encoding="utf-8") as f:
            return [r for r in _json.load(f)
                    if isinstance(r, dict) and "_comment" not in r]

    bees = _load(_BEE_ATTR_JSON_PATH)
    leps = _load(_LEP_ATTR_JSON_PATH)
    if not bees and not leps:
        return (0, 0)

    plants = [dict(r) for r in conn.execute(
        "SELECT common_name, scientific_name FROM plants").fetchall()]
    name_to_pid = {
        row["common_name"]: row["id"]
        for row in conn.execute("SELECT id, common_name FROM plants").fetchall()
    }
    sci_to_fid = {
        row["scientific_name"]: row["id"]
        for row in conn.execute(
            "SELECT id, scientific_name FROM fauna").fetchall()
    }

    edges = (bee_genus_host_edges(plants, bees)[0]
             + lepidoptera_genus_host_edges(plants, leps)[0])
    rows = []
    for e in edges:
        pid = name_to_pid.get(e["plant"])
        fid = sci_to_fid.get(e["fauna"])
        if pid is None or fid is None:
            continue
        rows.append((pid, fid, e["relationship"], e["derivation"],
                     e["basis"], e["confidence"], e["source"]))
    if rows:
        conn.executemany(
            "INSERT OR IGNORE INTO plant_fauna_derived "
            "(plant_id, fauna_id, relationship, derivation, basis, "
            " confidence, source) VALUES (?, ?, ?, ?, ?, ?, ?)", rows)

    ff_rows = []
    for e in cleptoparasite_edges(bees):
        a = sci_to_fid.get(e["fauna_a"])
        b = sci_to_fid.get(e["fauna_b"])
        if a is None or b is None:
            continue
        ff_rows.append((a, b, e["relationship"], e["evidence"],
                        e["confidence"], e["basis"], e["source"], e["notes"]))
    if ff_rows:
        conn.executemany(
            "INSERT OR IGNORE INTO fauna_fauna "
            "(fauna_id_a, fauna_id_b, relationship, evidence, confidence, "
            " basis, source, notes) VALUES (?, ?, ?, ?, ?, ?, ?, ?)", ff_rows)
    conn.commit()
    return (len(rows), len(ff_rows))


def _seed_nurseries(conn: sqlite3.Connection) -> int:
    """Load ``data/nurseries_master.json`` into the ``nurseries`` table (schema
    v44, V2.18). The JSON is an object with a ``nurseries`` list (plus metadata /
    disclaimer keys, which are ignored). Returns the number of rows inserted."""
    import json as _json

    if not os.path.exists(_NURSERIES_JSON_PATH):
        return 0
    with open(_NURSERIES_JSON_PATH, "r", encoding="utf-8") as f:
        payload = _json.load(f)
    entries = payload.get("nurseries", []) if isinstance(payload, dict) else payload

    rows = [
        (
            e.get("name", ""),
            e.get("kind", ""),
            e.get("province", ""),
            e.get("city", ""),
            e.get("lat"),
            e.get("lng"),
            e.get("url", ""),
            e.get("sells", ""),
            1 if e.get("ships") else 0,
            e.get("notes", ""),
        )
        for e in entries
        if isinstance(e, dict) and e.get("name")
    ]
    if rows:
        conn.executemany(
            "INSERT INTO nurseries "
            "(name, kind, province, city, lat, lng, url, sells, ships, notes) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            rows,
        )
        conn.commit()
    return len(rows)


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
        # Accept the new ``ecoregion`` key or the legacy ``ab_ecoregion`` (v42
        # province-neutral rename); either may be a list or comma-string.
        ecoregion = p.get("ecoregion", p.get("ab_ecoregion", ""))
        if isinstance(ecoregion, list):
            ecoregion = ",".join(ecoregion)
        # native_provinces: explicit JSON value wins; otherwise derive from the
        # legacy native_to_alberta flag so existing AB seed data keeps working
        # (native_to_alberta truthy -> "AB", else "").
        native_provinces = p.get("native_provinces")
        if isinstance(native_provinces, list):
            native_provinces = ",".join(native_provinces)
        if native_provinces is None:
            native_provinces = "AB" if str(
                p.get("native_to_alberta", 0)).strip() in ("1", "1?") else ""
        plant_rows.append((
            p.get("common_name", ""),
            p.get("scientific_name", ""),
            p.get("plant_type", "herb"),
            p.get("hardiness_zone_min"),
            p.get("hardiness_zone_max"),
            p.get("sun_requirement", ""),
            p.get("water_needs", ""),
            p.get("native_region", ""),
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
            native_provinces,
            p.get("toxicity_pets", ""),
            p.get("toxicity_humans", ""),
            1 if p.get("has_thorns") else 0,
            p.get("spread_habit", ""),
            p.get("safety_source", ""),
            p.get("price_low_cad"),
            p.get("price_high_cad"),
            p.get("availability_class", ""),
            p.get("sourcing_notes", ""),
            p.get("flower_color", ""),
            p.get("flower_form", "none"),
            p.get("fruit_color", ""),
            p.get("fruit_form", ""),
            p.get("image_url", ""),
            p.get("image_attribution", ""),
            p.get("image_license", ""),
            p.get("leaf_shape", ""),
            p.get("leaf_size_cm"),
            p.get("leaf_arrangement", ""),
            p.get("bark_color", ""),
            p.get("fall_color", ""),
            p.get("branching", ""),
            p.get("growth_form", ""),
            p.get("bark_texture", ""),
            p.get("leaf_surface", ""),
            p.get("inflorescence_form", ""),
            p.get("flower_arch", ""),
            p.get("flower_symmetry", ""),
            p.get("petal_shape", ""),
            p.get("petal_count"),
            p.get("florets_per_head"),
            p.get("flower_diameter_cm"),
            p.get("flower_center_color", ""),
            p.get("flower_height_frac"),
            p.get("stem_branching", ""),
            1 if p.get("basal_rosette") else 0,
            p.get("flowering_stems"),
            p.get("flower_data_source", ""),
            p.get("flower_data_citation", ""),
            p.get("leaf_data_source", ""),
            p.get("leaf_data_citation", ""),
        ))

    conn.executemany(
        """INSERT INTO plants
           (common_name, scientific_name, plant_type,
            hardiness_zone_min, hardiness_zone_max,
            sun_requirement, water_needs,
            native_region,
            spacing_meters, mature_height_meters, notes,
            bloom_period, fruit_period, native_to_alberta,
            edible_parts, deciduous_evergreen,
            soil_ph_min, soil_ph_max, perennial_or_annual,
            growth_rate, years_to_maturity, growth_curve,
            ecoregion, native_provinces,
            toxicity_pets, toxicity_humans, has_thorns,
            spread_habit, safety_source,
            price_low_cad, price_high_cad, availability_class,
            sourcing_notes, flower_color, flower_form, fruit_color, fruit_form,
            image_url, image_attribution, image_license,
            leaf_shape, leaf_size_cm, leaf_arrangement,
            bark_color, fall_color, branching, growth_form,
            bark_texture, leaf_surface, inflorescence_form,
            flower_arch, flower_symmetry, petal_shape, petal_count,
            florets_per_head, flower_diameter_cm, flower_center_color,
            flower_height_frac, stem_branching, basal_rosette,
            flowering_stems, flower_data_source, flower_data_citation,
            leaf_data_source, leaf_data_citation)
           VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,
                   ?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,
                   ?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
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

        if current_version < 31:
            _migrate_to_v31(conn)
        if current_version < 35:
            _migrate_to_v35(conn)
        if current_version < 42:
            _migrate_to_v42(conn)
        if current_version < 46:
            _migrate_to_v46(conn)
        if current_version < 47:
            _migrate_to_v47(conn)
        if current_version < 48:
            _migrate_to_v48(conn)
        if current_version < 49:
            _migrate_to_v49(conn)
        if current_version < 52:
            _migrate_to_v52(conn)

        if current_version < 53:
            _migrate_to_v53(conn)

        if current_version < 54:
            _migrate_to_v54(conn)

        if current_version < 55:
            _migrate_to_v55(conn)

        if current_version < 56:
            _migrate_to_v56(conn)

        if current_version < 57:
            _migrate_to_v57(conn)

        if current_version < 58:
            _migrate_to_v58(conn)

        if current_version < 59:
            _migrate_to_v59(conn)

        # schema.sql has already recreated relationship_edges by this point, and
        # that view selects the columns this migration adds. It works because
        # SQLite binds a view's column references lazily — CREATE VIEW succeeds
        # against columns that do not exist yet, and only a SELECT would fail.
        # This must therefore land before anything queries the view, which it
        # does: nothing reads relationships during init_db. Verified by
        # tests/test_derived_edges.py:TestUpgradeFromV60.
        if current_version < 61:
            _migrate_to_v61(conn)

        # Add parent_id to polycultures if missing
        try:
            conn.execute("ALTER TABLE polycultures ADD COLUMN parent_id INTEGER REFERENCES polycultures(id) ON DELETE SET NULL")
            conn.commit()
        except sqlite3.OperationalError:
            pass  # column already present

        # Idempotent additive migration — adds layer/functions columns to
        # polyculture_members and backfills them from the existing role.
        # (User-created communities are protected from the reseed itself by
        # the origin='seed' scoping below, schema v46.)
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
            conn.execute("DELETE FROM bee_attributes")   # child of fauna — wipe first
            conn.execute("DELETE FROM lepidoptera_attributes")   # child of fauna
            conn.execute("DELETE FROM plant_fauna")
            # schema v61 (V2.42): derived edges are recomputed from the attribute
            # files on every reseed, so they must be wiped like any other seeded
            # table or they accumulate rows pointing at stale plant/fauna ids.
            conn.execute("DELETE FROM plant_fauna_derived")
            conn.execute("DELETE FROM fauna_fauna")
            conn.execute("DELETE FROM plant_uses")
            conn.execute("DELETE FROM plant_ecoregions")   # reseeded from JSON
            conn.execute("DELETE FROM fauna")
            conn.execute("DELETE FROM uses")
            conn.execute("DELETE FROM companion_friends")
            conn.execute("DELETE FROM companion_enemies")
            conn.execute("DELETE FROM planting_calendar")
            # Polycultures hold USER-AUTHORED data alongside the shipped
            # examples (schema v46): wipe only origin='seed' rows. Members
            # are scoped through their parent (FK is OFF here, so the
            # CASCADE won't fire — delete children explicitly, then clear
            # any parent_id that pointed at a wiped seed example so the id
            # can't be re-used by a freshly seeded row.
            conn.execute(
                "DELETE FROM polyculture_members WHERE polyculture_id IN "
                "(SELECT id FROM polycultures WHERE origin = 'seed')")
            conn.execute("DELETE FROM polycultures WHERE origin = 'seed'")
            # Photo sets (schema v55) take the SAME rule, and it is the whole of
            # F72: a shipped photo is re-seeded, a person's own photograph is
            # never touched. Writing a user photo into plants.image_url instead
            # would destroy it here on the next schema bump, which is the trap
            # the table exists to avoid.
            conn.execute("DELETE FROM plant_photos WHERE origin = 'seed'")
            conn.execute(
                "UPDATE polycultures SET parent_id = NULL WHERE parent_id "
                "IS NOT NULL AND parent_id NOT IN (SELECT id FROM polycultures)")
            # Plant ids are NOT stable across a reseed (AUTOINCREMENT, never
            # reset) — snapshot the names behind every plant id the surviving
            # user communities reference, so they can be re-pointed at the
            # reseeded rows afterwards (_remap_user_polyculture_plants).
            user_plant_refs = conn.execute(
                "SELECT id, scientific_name, common_name FROM plants "
                "WHERE id IN (SELECT plant_id FROM polyculture_members) "
                "   OR id IN (SELECT center_plant_id FROM polycultures "
                "             WHERE center_plant_id IS NOT NULL)").fetchall()
            conn.execute("DELETE FROM plants")
            # Nurseries are seeded from data/nurseries_master.json — wipe + reseed
            # so directory edits ship on the next schema bump (V2.18).
            conn.execute("DELETE FROM nurseries")
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
            # Shipped photo sets (F70). Independent of plant ids — the
            # table is keyed by scientific_name on purpose.
            _seed_plant_photos(conn)
            # Derived ecoregion ranges (schema v59) — depends on plants being
            # seeded so scientific_name resolves to a plant id. Absent file =
            # nothing seeded = the read side keeps using plants.ecoregion.
            _seed_plant_ecoregions(conn)
            # Fauna registry + plant↔fauna links — depends on plants being
            # seeded first so we can resolve common_name → plant_id.
            _seed_fauna(conn)
            # Bee attributes (F37) — depends on the fauna registry above so we
            # can resolve each bee's scientific_name → fauna_id.
            _seed_bee_attributes(conn)
            # Lepidoptera attributes (F37 "fly as a butterfly") — same dependency.
            _seed_lepidoptera_attributes(conn)
            # Derived edges (V2.42) — must run after BOTH attribute seeders and
            # after _seed_fauna, since it expands their genus lists against the
            # seeded plants and resolves fauna ids.
            _seed_derived_edges(conn)
            # Native-plant nursery directory (V2.18) — independent of plants/fauna.
            _seed_nurseries(conn)
            # Re-point surviving user communities at the reseeded plant rows
            # (ids shifted) — must run before FK enforcement returns.
            _remap_user_polyculture_plants(conn, user_plant_refs)
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
        # Non-critical; polycultures can be created manually — but a broken
        # seed used to ship silently, so leave the evidence in the log.
        _log.exception("seeding example polycultures failed")

    # One-time import of any pre-existing recipes that lived in
    # ~/.permadesign_config.json. Subsequent runs are no-ops thanks to
    # the `polyculture_recipes_migrated` flag.
    try:
        from src.db.recipes import migrate_qsettings_recipes
        migrate_qsettings_recipes()
    except Exception:
        _log.exception("legacy recipe migration failed")  # user can recreate them

    # Any init may have reseeded/migrated the catalogue — drop the cache.
    invalidate_plant_cache()


def _remap_user_polyculture_plants(conn: sqlite3.Connection,
                                   old_refs) -> None:
    """Re-point user communities at the reseeded plant rows (schema v46).

    ``old_refs`` is the pre-wipe snapshot of ``(id, scientific_name,
    common_name)`` for every plant id referenced by a surviving (user)
    polyculture. Plant ids shift on every reseed, so each old id is
    resolved to the new catalogue row by scientific name (falling back to
    common name). Members whose plant no longer exists in the catalogue
    are dropped — with a log line, not silently."""
    if not old_refs:
        return
    by_sci = {}
    by_common = {}
    for row in conn.execute(
            "SELECT id, scientific_name, common_name FROM plants"):
        if row["scientific_name"]:
            by_sci.setdefault(row["scientific_name"], row["id"])
        if row["common_name"]:
            by_common.setdefault(row["common_name"], row["id"])

    remap: dict[int, int] = {}
    lost: list[str] = []
    for old in old_refs:
        new_id = (by_sci.get(old["scientific_name"])
                  or by_common.get(old["common_name"]))
        if new_id is not None:
            remap[old["id"]] = new_id
        else:
            lost.append(old["common_name"] or old["scientific_name"]
                        or str(old["id"]))

    # Two-phase (via negative temp ids) so an old→new pair can never be
    # re-remapped by a later pair that shares the number. FK is OFF here.
    for old_id, new_id in remap.items():
        conn.execute("UPDATE polyculture_members SET plant_id = ? "
                     "WHERE plant_id = ?", (-new_id, old_id))
        conn.execute("UPDATE polycultures SET center_plant_id = ? "
                     "WHERE center_plant_id = ?", (-new_id, old_id))
    conn.execute("UPDATE polyculture_members SET plant_id = -plant_id "
                 "WHERE plant_id < 0")
    conn.execute("UPDATE polycultures SET center_plant_id = -center_plant_id "
                 "WHERE center_plant_id < 0")

    # Anything still pointing outside the fresh catalogue references a plant
    # that no longer ships — drop/clear it audibly rather than strand an
    # FK-invalid row for the next runtime query to trip on.
    cur = conn.execute(
        "DELETE FROM polyculture_members "
        "WHERE plant_id NOT IN (SELECT id FROM plants)")
    conn.execute(
        "UPDATE polycultures SET center_plant_id = NULL "
        "WHERE center_plant_id IS NOT NULL "
        "AND center_plant_id NOT IN (SELECT id FROM plants)")
    if lost or cur.rowcount:
        _log.warning(
            "reseed: %d member row(s) dropped — plants no longer in the "
            "catalogue%s", cur.rowcount,
            (": " + ", ".join(sorted(lost)[:10])) if lost else "")


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

    # Columns named explicitly (schema v61 added source/notes): a positional
    # INSERT here breaks the moment the table grows, and these pairings are
    # deliberately seeded WITHOUT a source — that is what makes them read
    # `recorded` rather than `documented` in relationship_edges.
    if friends:
        conn.executemany(
            "INSERT OR IGNORE INTO companion_friends (plant_id_a, plant_id_b) "
            "VALUES (?,?)", friends
        )
    if enemies:
        conn.executemany(
            "INSERT OR IGNORE INTO companion_enemies (plant_id_a, plant_id_b) "
            "VALUES (?,?)", enemies
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
    # Back-compat: the ab_ecoregion column was renamed to ecoregion in v42
    # (province-neutral). Expose the legacy key as a synthesized alias so
    # read-side consumers (plant browser, llm_design, polyculture panel, the
    # frozen permadesign_api / MCP surface) keep working unchanged.
    if "ecoregion" in d:
        d["ab_ecoregion"] = d.get("ecoregion") or ""
    return d


def _attach_photos(plants: list[dict]) -> None:
    """Synthesize ``image_url`` / ``image_attribution`` / ``image_license`` from
    the ``plant_photos`` table (schema v55, F70), and hand the whole set over as
    ``photos``.

    The same read-side-synthesis shape ``_attach_permaculture_uses`` uses below,
    and for the same reason: the junction is the source of truth, but every
    existing consumer reads a single field and must keep working. The plant
    browser, the 3D dossier card, the bee and lepidoptera panels and
    ``photo_warm`` all get better photographs here without one line of change at
    the call site.

    Preference order is ``PHOTO_SLOTS`` — **habit first** — and a person's own
    photograph (``origin='user'``) beats a shipped one in the same slot, because
    a picture of the plant in THEIR yard is more use than a stranger's. Where the
    table has nothing, the row keeps whatever ``plants.image_url`` already held,
    so a species the photo set doesn't cover renders exactly as it did before.
    """
    names = [(p.get("scientific_name") or "").strip() for p in plants]
    wanted = {n for n in names if n}
    if not wanted:
        return
    conn = get_connection()
    try:
        # One query for the whole list, not one per plant — get_all_plants is
        # 434 rows and render_project_to_map is called on every File→Open.
        marks = ",".join("?" * len(wanted))
        rows = conn.execute(
            f"SELECT scientific_name, slot, url, attribution, license, source,"
            f"       origin, taken_on, rank"
            f"  FROM plant_photos WHERE scientific_name IN ({marks})"
            f" ORDER BY rank, id", tuple(wanted)).fetchall()
    except sqlite3.OperationalError:
        return          # pre-v55 DB mid-migration; the column keeps working
    finally:
        conn.close()

    by_name: dict[str, list[dict]] = {}
    for r in rows:
        by_name.setdefault(r["scientific_name"], []).append(dict(r))

    order = {slot: i for i, slot in enumerate(PHOTO_SLOTS)}
    for p in plants:
        shots = by_name.get((p.get("scientific_name") or "").strip())
        if not shots:
            p.setdefault("photos", [])
            continue
        p["photos"] = shots
        best = min(shots, key=lambda s: (order.get(s["slot"], 99),
                                         0 if s["origin"] == "user" else 1,
                                         s["rank"]))
        p["image_url"] = best["url"]
        p["image_attribution"] = best["attribution"]
        p["image_license"] = best["license"]


def ecoregion_ranges_for_ids(plant_ids: list[int],
                             conn: Optional[sqlite3.Connection] = None
                             ) -> dict[int, list[dict]]:
    """``{plant_id: [{ecoregion, occurrences, confidence, source}, …]}``.

    The sourced half of a plant's range. Strongest evidence first, so a caller
    showing one line shows the best-attested region.

    Pass ``conn`` when you already have one open — ``get_all_plants`` and
    ``search_plants`` both do, and opening a second connection inside a query
    they are already inside is pure churn on the hottest read path in the app
    (``render_project_to_map`` calls it on every File→Open and every undo).
    """
    if not plant_ids:
        return {}
    own = conn is None
    conn = conn or get_connection()
    try:
        marks = ",".join("?" * len(plant_ids))
        rows = conn.execute(
            f"SELECT plant_id, ecoregion, occurrences, confidence, source "
            f"  FROM plant_ecoregions WHERE plant_id IN ({marks}) "
            f" ORDER BY occurrences DESC, ecoregion", list(plant_ids)).fetchall()
    finally:
        if own:
            conn.close()
    out: dict[int, list[dict]] = {}
    for r in rows:
        out.setdefault(r["plant_id"], []).append({
            "ecoregion":   r["ecoregion"],
            "occurrences": r["occurrences"],
            "confidence":  r["confidence"],
            "source":      r["source"],
        })
    return out


def _attach_ecoregions(plants: list[dict],
                       conn: Optional[sqlite3.Connection] = None) -> None:
    """Overlay derived ecoregion ranges onto each plant dict (schema v59).

    The same read-side-synthesis shape ``_attach_permaculture_uses`` uses, with
    one difference that matters: the junction does **not** replace the column
    wholesale, it replaces the *geographic* half of it.

    ``plants.ecoregion`` mixes two kinds of claim. The geographic tags were
    generated heuristically and never sourced — those are what the GBIF
    derivation supersedes. ``riparian`` and ``wet_meadow`` are site-scale
    moisture niches that no coordinate can assert, so they are carried through
    untouched from the column.

    A species the derivation has not covered keeps its column value entirely,
    so the catalogue never gets *smaller* because a download has not been run.
    Each plant also gains ``ecoregion_evidence`` — the rows with their counts —
    for anything that wants to show how good the claim is (P9).
    """
    ids = [p["id"] for p in plants if p.get("id") is not None]
    if not ids:
        return
    try:
        derived = ecoregion_ranges_for_ids(ids, conn)
    except sqlite3.Error:
        return                      # pre-v59 DB mid-migration: keep the column
    if not derived:
        return
    from src.ecoregion import is_moisture_niche
    for p in plants:
        rows = derived.get(p.get("id"))
        p["ecoregion_evidence"] = rows or []
        if not rows:
            continue
        existing = [t.strip() for t in (p.get("ecoregion") or "").split(",")
                    if t.strip()]
        niches = [t for t in existing if is_moisture_niche(t)]
        geographic = [r["ecoregion"] for r in rows]
        merged = geographic + [n for n in niches if n not in geographic]
        p["ecoregion"] = ",".join(merged)
        p["ab_ecoregion"] = p["ecoregion"]      # frozen agent-API alias (v42)


def _attach_permaculture_uses(plants: list[dict]) -> None:
    """Populate each dict's derived ``permaculture_uses`` (comma-joined, sorted)
    from the plant_uses junction. The denormalized column was dropped in schema
    v37; this keeps the legacy blob-shaped field available to read-side consumers
    (succession, the plant browser, the polyculture panel) while the junction is
    the single source of truth. One batched query for the whole list."""
    ids = [p["id"] for p in plants if p.get("id") is not None]
    if not ids:
        return
    uses_map = plant_uses_for_ids(ids)
    for p in plants:
        p["permaculture_uses"] = ",".join(sorted(uses_map.get(p["id"], ())))


def get_all_plants() -> list[dict]:
    conn = get_connection()
    try:
        rows = conn.execute(
            "SELECT * FROM plants ORDER BY plant_type, common_name"
        ).fetchall()
        result = [_row_to_dict(r) for r in rows]
        _attach_permaculture_uses(result)
        _attach_ecoregions(result, conn)
        _attach_photos(result)
        return result
    finally:
        conn.close()


# ── In-memory catalogue cache (V2.22) ────────────────────────────────────────
# The catalogue is read-only between reseeds, but get_plant() opened a fresh
# connection and ran two queries per call — and render_project_to_map calls
# it once per placed plant on every File→Open and every snapshot undo/redo
# (≈600 queries per Ctrl+Z on a 300-plant design). The first miss loads the
# whole catalogue (a few hundred rows) into a dict; every plants write path
# calls invalidate_plant_cache(). Keyed to _DB_PATH so tests that repoint
# the DB (the temp-DB pattern) can never see another DB's rows.

_plant_cache: Optional[dict] = None
_plant_cache_db: Optional[str] = None


def invalidate_plant_cache() -> None:
    """Drop the in-memory catalogue cache. Call after ANY write to
    ``plants`` (reseed, marker colour, USDA import)."""
    global _plant_cache, _plant_cache_db
    _plant_cache = None
    _plant_cache_db = None


def _cached_plants() -> dict:
    global _plant_cache, _plant_cache_db
    if _plant_cache is None or _plant_cache_db != _DB_PATH:
        _plant_cache = {p["id"]: p for p in get_all_plants()}
        _plant_cache_db = _DB_PATH
    return _plant_cache


def get_plant(plant_id: int) -> Optional[dict]:
    try:
        key = int(plant_id)
    except (TypeError, ValueError):
        return None
    p = _cached_plants().get(key)
    # Shallow copy per call: callers historically got a fresh dict and some
    # annotate it in place — they must not be able to poison the cache.
    return dict(p) if p is not None else None


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
    ecoregion: str = "",
    native_province: str = "",
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
    bloom_months: Optional[list] = None,
    fruit_months: Optional[list] = None,
) -> list[dict]:
    """
    Return plants matching all supplied filters.
    Empty string / None values for a filter means "no restriction".

    ``bloom_months`` / ``fruit_months`` are lists of 1–12 month numbers; a plant
    matches if its recorded window covers ANY of them. See ``_month_filter``
    below for why these are applied in Python rather than SQL.
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
        sql += (" AND (LOWER(common_name) LIKE ? OR LOWER(scientific_name) LIKE ?"
                " OR EXISTS (SELECT 1 FROM plant_uses pu JOIN uses u"
                " ON u.id = pu.use_id WHERE pu.plant_id = plants.id"
                " AND LOWER(u.key) LIKE ?))")
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

    # ecoregion column is a comma-separated list of region ids. A multi-select
    # "restoring toward" filter matches a plant documented from ANY of the chosen
    # ecoregions (OR of substring-safe patterns). Accepts a single string
    # (legacy) or a list (V1.85). The ``ab_ecoregion`` parameter is the
    # pre-v42 name, kept for back-compat (frozen MCP contract); ``ecoregion`` is
    # the province-neutral name — either (or both) may be supplied.
    #
    # Since schema v59 the filter also reads the derived `plant_ecoregions`
    # junction, and it MUST: the read side overlays derived ranges onto the
    # column *after* the query, so a filter that looked only at the column would
    # still hide the species the derivation just corrected. That is the reported
    # bug — Saskatoon Berry, whose column says mixedgrass but whose occurrence
    # records say parkland — surviving its own fix.
    ecoregions = _as_filter_list(ecoregion) + _as_filter_list(ab_ecoregion)
    if ecoregions:
        from src.ecoregion import is_moisture_niche          # noqa: PLC0415
        geographic = [e for e in ecoregions if not is_moisture_niche(e)]
        moisture   = [e for e in ecoregions if is_moisture_niche(e)]
        clauses, geo_params, wet_params = [], [], []

        # Geographic regions: the derived rows SUPERSEDE the column for any
        # species that has them, exactly as `_attach_ecoregions` does on the
        # read side. ORing the two instead was wrong and visibly so — a plant
        # whose stale column said parkland but whose occurrence records say
        # otherwise came back from the parkland filter while its own card
        # (rendered from the derived rows) did not say parkland. The filter and
        # the thing it filters have to agree about what a plant's range is.
        if geographic:
            marks = ",".join("?" * len(geographic))
            clauses.append(
                f"(CASE WHEN EXISTS (SELECT 1 FROM plant_ecoregions pe "
                f"                    WHERE pe.plant_id = plants.id) "
                f"      THEN EXISTS (SELECT 1 FROM plant_ecoregions pe "
                f"                    WHERE pe.plant_id = plants.id "
                f"                      AND pe.ecoregion IN ({marks})) "
                f"      ELSE (" + " OR ".join(
                    "(',' || COALESCE(ecoregion,'') || ',') LIKE ?"
                    for _ in geographic) + ") END)")
            geo_params = list(geographic) + [f"%,{e},%" for e in geographic]

        # Moisture niches are never derived — no coordinate can assert "wet
        # ground" — so they are always read from the column, for every species.
        if moisture:
            clauses.append("(" + " OR ".join(
                "(',' || COALESCE(ecoregion,'') || ',') LIKE ?"
                for _ in moisture) + ")")
            wet_params = [f"%,{e},%" for e in moisture]

        sql += " AND (" + " OR ".join(clauses) + ")"
        params += geo_params + wet_params

    # native_province (v42): keep only plants native to the given province code
    # (e.g. "SK"). The province-aware generalization of the native_only flag,
    # which stays keyed on native_to_alberta for back-compat.
    if native_province:
        sql += " AND (',' || COALESCE(native_provinces,'') || ',') LIKE ?"
        params.append(f"%,{native_province},%")

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
    #
    # A tolerance margin (V2.18.1) widens the bracket by _SOIL_PH_TOLERANCE at
    # each end. Both the site pH (often a coarse regional estimate) and each
    # plant's tolerance bounds are approximate, so a hard cutoff let a 0.1 pH
    # gap wrongly exclude e.g. every tree on Regina's alkaline clay (site 7.6 vs
    # a plant max of 7.5). Respecting that uncertainty (P9) restores the woody
    # species people actually plant there.
    if soil_ph is not None:
        sql += (" AND (soil_ph_min IS NULL OR soil_ph_min <= ?)"
                " AND (soil_ph_max IS NULL OR soil_ph_max >= ?)")
        params += [float(soil_ph) + _SOIL_PH_TOLERANCE,
                   float(soil_ph) - _SOIL_PH_TOLERANCE]

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
                " OR (',' || COALESCE(ecoregion,'') || ',') LIKE '%,wet_meadow,%'"
                " OR (',' || COALESCE(ecoregion,'') || ',') LIKE '%,riparian,%')")
    elif moisture == "dry":
        sql += " AND " + _water_like("low")
    elif moisture == "mesic":
        sql += " AND " + _water_like("medium", "moderate")

    sql += " ORDER BY plant_type, common_name"

    conn = get_connection()
    try:
        rows = conn.execute(sql, params).fetchall()
        result = [_row_to_dict(r) for r in rows]
        _attach_permaculture_uses(result)
        _attach_ecoregions(result, conn)
        _attach_photos(result)
        result = _month_filter(result, "bloom_period", bloom_months)
        result = _month_filter(result, "fruit_period", fruit_months)
        return result
    finally:
        conn.close()


def _month_filter(plants: list[dict], column: str, months) -> list[dict]:
    """Keep plants whose ``column`` window covers any of ``months`` (1–12).

    Applied in Python, not SQL, because ``bloom_period`` / ``fruit_period`` are
    free text ("June–July", "Jun-Jul", "Nov-Feb") rather than integer bounds, so
    a LIKE cannot answer "does May–August include July?" — and the year-wrapping
    ranges would defeat a BETWEEN even if it could. ``parse_month_range`` is the
    parser every other consumer already shares (forage calendar, phenology,
    habitat score), so a filter built on it can never disagree with the gap
    months the analysis panel reports.

    A plant with no recorded window is excluded rather than assumed: "we don't
    know when this blooms" is not the same claim as "it blooms in July" (P9).
    """
    wanted = {int(m) for m in (months or []) if str(m).strip()}
    if not wanted:
        return plants
    from src.habitat_score import parse_month_range
    return [p for p in plants
            if wanted & set(parse_month_range(p.get(column) or ""))]


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
            result = [_row_to_dict(r) for r in rows]
            _attach_permaculture_uses(result)
            _attach_ecoregions(result, conn)
            _attach_photos(result)
            return result

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
    invalidate_plant_cache()


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
