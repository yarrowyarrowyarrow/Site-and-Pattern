# PermaDesign Database Schema

PermaDesign stores its plant catalogue and saved plant communities in a
local SQLite database. This is **not** the project file (see
[`PROJECT_FILE_FORMAT.md`](PROJECT_FILE_FORMAT.md)) — it's the shared,
seeded reference data every project draws from.

- **DDL:** [`src/db/schema.sql`](../src/db/schema.sql) (authoritative;
  loaded on every `init_db`)
- **Access layer:** [`src/db/plants.py`](../src/db/plants.py),
  [`polycultures.py`](../src/db/polycultures.py),
  [`recipes.py`](../src/db/recipes.py),
  [`structures.py`](../src/db/structures.py),
  [`fauna.py`](../src/db/fauna.py)
- **Current schema version:** `17` (`src/db/plants.py:_SCHEMA_VERSION`)
- **Location:**
  - Linux: `~/.local/share/PermaDesign/permadesign.db`
  - Windows: `%APPDATA%/PermaDesign/`
  - macOS: `~/Library/Application Support/PermaDesign/`

  The DB is **never** stored inside the source tree — `tests/test_polycultures.py`
  asserts this.

Structure definitions (bee hotels, ponds, …) are **not** in SQLite —
they're a hard-coded list in `src/db/structures.py`.

---

## Tables

### `plants` — the catalogue
One row per species. Key columns (full list in the DDL):

| column | notes |
|---|---|
| `id` | PK, referenced by project `plant_id` |
| `common_name`, `scientific_name` | |
| `plant_type` | tree, shrub, herb, groundcover, vine, root |
| `hardiness_zone_min/max` | |
| `sun_requirement` | full_sun, partial_shade, full_shade |
| `water_needs` | low, medium, high |
| `permaculture_uses` | comma-separated tag blob (legacy; see `plant_uses`) |
| `spacing_meters`, `mature_height_meters`, `mature_canopy_m` | `mature_canopy_m` NULL ⇒ heuristic (1.5× spacing) in `get_plant` |
| `bloom_period`, `fruit_period` | e.g. "May–June" |
| `native_to_alberta` | 1 = native |
| `edible_parts`, `deciduous_evergreen`, `soil_ph_min/max`, `perennial_or_annual` | |
| `marker_color` | custom map-marker hex |
| `growth_rate`, `years_to_maturity`, `growth_curve` | succession/timeline (curve: fast_early \| steady \| slow_start) |
| `ab_ecoregion` | comma-separated AB ecoregion tags |

### `companion_friends` / `companion_enemies`
Symmetric plant↔plant companion relationships (`plant_id_a`, `plant_id_b`).

### `planting_calendar`
12 rows per plant: `(plant_id, month, status, notes)`. `status` ∈
`dormant, start_indoors, direct_sow, transplant, growing, harvest, pruning`.

### `polycultures` / `polyculture_members`
Saved **spatial** plant communities. Members carry `offset_x`/`offset_y`
(metres from the community centre), a `layer`, and a JSON `functions`
array. `parent_id` supports variations.

### `polyculture_recipes` / `polyculture_recipe_members`
**Ratio-only** mixes (no spatial layout): members carry an integer
`weight` instead of offsets. Drive ratio assignment for row/grid/circle
placement.

### `uses` / `plant_uses` (schema v13)
Canonical permaculture-use vocabulary (`uses.key`/`label`/`category`) and
the plant↔use junction that replaced substring matching on the legacy
`plants.permaculture_uses` blob for filter queries.

### `fauna` / `plant_fauna` (schema v13)
Native lepidoptera / bird / bee registry and the plant↔fauna junction,
tagged by `relationship` (`larval_host, nectar, pollen, seed_food,
fruit_food, nesting, cover`) and `specificity` (`specialist`/`generalist`).
Powers the wildlife column in the plant browser and the
lepidoptera-supported count in the habitat score.

### `climate_cache` (schema v14)
One row per ~1 km² (`lat_q`, `lng_q` = lat/lng × 100, rounded) caching
growing-degree-day + frost-window stats from Open-Meteo. Never
auto-expires.

### Indexes
On `plants(plant_type)`, `plants(zone range)`, `plants(native_to_alberta)`,
`planting_calendar(plant_id)`, the two member junctions, and the three
`plant_fauna` columns. See the bottom of the DDL.

---

## Seeding & reseed

`init_db` (in `src/db/plants.py`) creates the tables, then **reseeds**
when the row count is low or the stored schema version is older than
`_SCHEMA_VERSION`. Seed data ships as JSON in `data/`:

- `data/plants_master.json`
- `data/garden_plants.json`
- `data/fauna_master.json`
- `data/plant_fauna_master.json`

The reseed wipes and repopulates: `plants`, `planting_calendar`,
`companion_friends`, `companion_enemies`, `polyculture_members`,
`polycultures`, `uses`, `plant_uses`, `fauna`, `plant_fauna`.

> FK constraints are ON at runtime but disabled during the bulk reseed
> (Python 3.14 enforces FKs at statement time, not commit time).

---

## Changing the schema (checklist)

From `CLAUDE.md` — follow exactly so existing installs pick up changes:

1. Edit `src/db/schema.sql`.
2. **Bump `_SCHEMA_VERSION`** in `src/db/plants.py` (this triggers the
   one-time reseed on the user's next launch).
3. If you added a dependent table, add a `DELETE FROM <table>` to the
   reseed block in `init_db` (or it accumulates stale rows across
   reseeds).
4. Add/extend a seeding helper following the `_seed_uses_lookup` /
   `_seed_fauna` pattern.
5. Add tests under `tests/` using the temp-DB pattern from
   `test_polycultures.py` / `test_uses_junction.py`.
6. Run `python -m unittest discover -s tests`.

Forgetting step 2 means existing installs silently keep the old schema —
no new tables, no new rows.
