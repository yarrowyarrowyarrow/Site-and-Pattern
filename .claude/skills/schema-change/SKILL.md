---
name: schema-change
description: Use when changing src/db/schema.sql, adding a table/column, bumping _SCHEMA_VERSION in src/db/plants.py, editing the reseed wipe list, writing a _migrate_to_vNN helper, or changing seeded data that must reach existing installs. Covers the migration-vs-reseed distinction, FK-off-during-reseed, the junction-backed permaculture_uses read synthesis, updating docs/DATABASE_SCHEMA.md, and the temp-DB test pattern.
---

# Changing the SQLite schema (Site & Pattern)

## Purpose / when to use

The plant catalogue and communities live in a per-user SQLite DB
(`permadesign.db`) created and reseeded by `src/db/plants.py:init_db`. It is a
**shipped, seeded reference DB**, not project data. Any change to its shape
(`src/db/schema.sql`) or to the seed data it loads from `data/*.json` must be
propagated to existing installs, or those users silently keep the old DB.

Use this skill when you:
- add/remove/rename a table or column in `src/db/schema.sql`;
- change seeded rows meaningfully (see the companion `seed-data` skill);
- need a value change to reach users who already have a DB;
- are writing a `_migrate_to_vNN` helper or editing the reseed block.

**Current facts (verify before quoting):** branch `V2.19`,
`_SCHEMA_VERSION = 46` (in `src/db/plants.py`). CLAUDE.md and
`docs/DATABASE_SCHEMA.md` lag the code — the code wins. `docs/DATABASE_SCHEMA.md`
still says version 17; the inline changelog comments in `plants.py` stop at v41
even though the constant is 45. Treat those docs as stale and fix them as part
of your change (see step 6).

## The mental model: two independent mechanisms

`init_db` does **two different things** to bring a DB up to date. Know which one
your change needs — mixing them up loses user data or fails to ship your change.

1. **ALTER migrations (`_migrate_to_vNN`)** — *additive, data-preserving.* Run
   once, guarded by `if current_version < NN:`. They `ALTER TABLE ... ADD
   COLUMN` (each wrapped in `try/except sqlite3.OperationalError` so a
   fresh install where `schema.sql` already created the column is a no-op).
   They **keep every existing row.** Use for new columns and for any table that
   holds *user-created* data (e.g. `polyculture_members` — the layer/functions
   backfill is a migration, deliberately outside the reseed path so user
   communities survive).

2. **The reseed block** — *destructive wipe + repopulate from shipped JSON.*
   Triggered when `count < 100 OR current_version < _SCHEMA_VERSION`. It
   `DELETE`s the seeded tables and re-inserts them from `data/*.json`. Use to
   ship new/changed **seed data** and new **derived/cache** tables. It
   **destroys anything in the wiped tables** — never put user-authored data in a
   wiped table.

A single change often needs both: a `_migrate_to_vNN` to add the column to old
DBs, **and** the `_SCHEMA_VERSION` bump so the reseed fills that column from the
JSON. `_migrate_to_v24` / `_migrate_to_v31` / `_migrate_to_v35` /
`_migrate_to_v42` in `plants.py` are the canonical examples.

## When a bump is needed vs not

Bump `_SCHEMA_VERSION` (in `src/db/plants.py`) when **any** of these is true:
- you changed `src/db/schema.sql` (new/changed table or column);
- you changed seeded data (`data/plants_master.json`, `garden_plants.json`,
  `fauna_master.json`, `plant_fauna_master.json`, `bee_attributes_master.json`,
  `lepidoptera_attributes_master.json`, `nurseries_master.json`) meaningfully;
- you changed the seeded polycultures/companions/uses vocabulary in
  `src/db/polycultures.py` / `src/db/seed_data.py` / `_USE_DEFINITIONS`.

You do **not** need a bump for pure query-layer or read-side changes that don't
alter stored bytes. Note the historical pattern: many bumps are "no DDL — reseed
to pick up new seed values" (v25, v28–v30, v32–v36, v38, v41). A bump with no
DDL is legitimate and common — it exists purely to *re-run the reseed* on
existing installs.

## The procedure (checklist)

1. **Edit `src/db/schema.sql`** (if the shape changes). It is the authoritative
   DDL, applied via `conn.executescript` on **every** `init_db`, so it must stay
   idempotent — always `CREATE TABLE IF NOT EXISTS` / `CREATE INDEX IF NOT
   EXISTS`. A fresh install gets the whole shape from here; migrations only fix
   *old* DBs. Document new columns with an inline `-- schema vNN` comment as the
   existing columns do.

2. **Write a migration helper if you added a column/table to an existing
   table.** Follow `_migrate_to_v31`:
   ```python
   def _migrate_to_v46(conn):
       for col_name, col_def in (("my_col", "TEXT DEFAULT ''"),):
           try:
               conn.execute(f"ALTER TABLE plants ADD COLUMN {col_name} {col_def}")
           except sqlite3.OperationalError:
               pass  # column already present (fresh install got it from schema.sql)
       conn.commit()
   ```
   Then wire it into `init_db`: `if current_version < 46: _migrate_to_v46(conn)`.
   A brand-new `CREATE TABLE IF NOT EXISTS` needs **no** migration helper — the
   `executescript(schema.sql)` at the top of `init_db` creates it. (That is why
   `shade_zone_cache`/`wind_cache` had "no ALTER migration needed" — see the v21
   / v26 changelog comments.)

3. **Bump `_SCHEMA_VERSION`** in `src/db/plants.py` to the next integer, and add
   a changelog comment above the constant in the established style (`# vNN
   (V2.x): what changed and why`). This one line is what makes existing installs
   reseed — forgetting it means your change never ships.

4. **If you added a NEW dependent (seeded or derived) table, add it to the
   reseed wipe list** in `init_db`'s `needs_reseed` block, or it accumulates
   stale rows across reseeds. The current wipe order (children before parents,
   under `PRAGMA foreign_keys = OFF`) is:
   `bee_attributes` → `lepidoptera_attributes` → `plant_fauna` → `plant_uses` →
   `fauna` → `uses` → `companion_friends` → `companion_enemies` →
   `planting_calendar` → `polyculture_members` → `polycultures` → `plants` →
   `nurseries` → `climate_cache` → `wind_cache` → `shade_zone_cache`.
   Insert a new **child** table's `DELETE` *before* its parent. **Exception —
   never wipe a table holding user-authored data** (that is why the reseed does
   *not* touch `polyculture_recipes` or `polyculture_recipe_members`, and why
   the `polyculture_members` layer/functions backfill is a migration, not a
   reseed step).

5. **Add or extend a seeding helper** following the `_seed_*` pattern (see the
   `seed-data` skill for field-level detail). Wire the call into the reseed
   block **after its dependencies**: `_seed_uses_lookup` must run before
   `_seed_from_json_file` (which populates `plant_uses` per plant);
   `_seed_fauna` before `_seed_bee_attributes` / `_seed_lepidoptera_attributes`
   (they resolve `scientific_name → fauna_id` against the seeded `fauna` table).

6. **Update the docs.** `docs/DATABASE_SCHEMA.md` (the "Current schema version"
   line, the table list, the reseed wipe list) and — if you find them stale —
   the inline changelog block above `_SCHEMA_VERSION`. These are drifting today;
   your change is a good moment to true them up (state the real version, not a
   copied-forward number).

7. **Write a temp-DB test** (next section) and run the suite (Validation).

## Key files

| Path | What it holds |
|---|---|
| `src/db/plants.py` | `init_db`, `_SCHEMA_VERSION`, all `_migrate_to_vNN`, the reseed wipe list, the `_seed_*` helpers, `get_connection` (FK pragma), read-side `_attach_permaculture_uses`. |
| `src/db/schema.sql` | Authoritative DDL, applied every `init_db`. Must stay idempotent. |
| `src/db/seed_data.py` | `SEED_COMPANIONS`, `load_plants_from_master`, `reseed()`. |
| `src/db/polycultures.py` | `EXAMPLE_POLYCULTURES`, `seed_example_polycultures` (seeded after plants). |
| `src/db/fauna.py` | Read-side query API for `fauna` / `bee_attributes` / `lepidoptera_attributes`. |
| `src/db/nurseries.py` | Read-side query API for the `nurseries` table (schema v44). |
| `docs/DATABASE_SCHEMA.md` | Human schema doc (currently STALE — fix as part of your change). |
| `tests/test_uses_junction.py` | Canonical temp-DB test; junction + read-synthesis invariants. |
| `tests/test_polycultures.py` | Temp-DB CRUD test; also asserts the DB never lives in the source tree. |
| `tests/test_climate_cache.py` | Temp-DB cache test; shows the `assertGreaterEqual(_SCHEMA_VERSION, N)` guard style. |

## Pitfalls & gotchas (mined from the code/tests)

- **FK enforcement is ON at runtime, OFF during the bulk reseed.**
  `get_connection` sets `PRAGMA foreign_keys = ON`. The reseed block explicitly
  flips it `OFF` before wiping/inserting and back `ON` after, because **Python
  3.14 enforces FK constraints at statement time rather than at commit**, so
  parent+child rows inserted in the same transaction would otherwise fail. If
  you add seed inserts to the reseed, they run with FK OFF — the data must be
  internally consistent on its own (resolve names→ids yourself, as the helpers
  do). `tests/test_polycultures.py::test_add_member_invalid_plant_id_raises`
  confirms FK violations *do* raise at normal runtime.

- **`permaculture_uses` is a junction, synthesized on read (schema v37+).** The
  denormalized `plants.permaculture_uses` column was **dropped**. Do not add it
  back or `SELECT` it. The comma-string still visible to read-side consumers is
  built in `_attach_permaculture_uses` (called from `get_plant`,
  `get_all_plants`, `search_plants`, `get_companions`) from the `plant_uses`
  junction. Tag filters in `search_plants` (`keystone_only`, `host_plant_only`,
  …) go through an `EXISTS`-on-`plant_uses` subquery, not a string LIKE. The
  JSON seed field `permaculture_uses` stays — it feeds both the junction
  (`_populate_plant_uses`) and `data_quality` validation.
  `tests/test_uses_junction.py::test_permaculture_uses_column_dropped` guards the
  drop.

- **Reseed triggers on `count < 100` too, not only a version bump.** Any test or
  path that leaves fewer than 100 plants will silently trigger a full reseed on
  the next `init_db`. Keep that in mind when writing tests that insert a handful
  of dummy rows into a fresh DB.

- **`ecoregion` was `ab_ecoregion` before v42.** `_migrate_to_v42` renames the
  column (province-neutral) and `_row_to_dict` re-exposes `ab_ecoregion` as a
  synthesized alias for the frozen MCP/`permadesign_api` contract. If you touch
  ecoregion, keep both the column (`ecoregion`) and the alias working; the seed
  loader accepts either JSON key.

- **Migrations must be idempotent and order-independent going forward.** They
  run in ascending `if current_version < NN` order every launch until the stored
  version catches up. Never assume a prior migration's *data* state — only its
  *shape*. The `_migrate_to_v42` column-resolution branch (handling both the
  "only `ab_ecoregion` exists" upgrade path and the "both exist" fresh-install
  path) is the reference for writing a robust one.

- **Don't renumber or reuse a version.** `_SCHEMA_VERSION` only ever increases.
  A user's stored version gates which migrations run; reusing a number strands
  installs mid-range.

- **P12 (Indigenous knowledge) — HARD RULE.** Do **not** add columns, tables,
  seed rows, or vocabulary that operationalize Indigenous ecological knowledge,
  plant-use traditions, or land-management frameworks without free, prior, and
  informed consent from the relevant communities. The v16/v17 changelog entries
  show the project has already *removed* such framing (medicine-wheel →
  "Aromatic Herb Circle"; "Red Indian Paintbrush" → "Common Paintbrush"). If a
  schema/seed task pushes that way, stop and raise it with the user.

## Writing the temp-DB test

Every DB test redirects the DB to a `tempfile.mkdtemp` dir **before importing
anything that opens it**, so the real user DB at
`~/.local/share/Site & Pattern/` is never touched. The exact pattern (from
`tests/test_uses_junction.py`):

```python
import os, sys, tempfile, unittest
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

_TMP_DIR = tempfile.mkdtemp(prefix="permadesign_mychange_test_")
import src.db.plants as _plants_mod          # import the MODULE first
_plants_mod._DATA_DIR = _TMP_DIR             # then monkeypatch the paths
_plants_mod._DB_PATH  = os.path.join(_TMP_DIR, "permadesign_test.db")

from src.db.plants import init_db, get_connection  # now safe to import the API

class TestMyChange(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        init_db()                            # builds schema + seeds into the temp DB

    def test_new_column_present(self):
        conn = get_connection()
        try:
            cols = {r[1] for r in conn.execute("PRAGMA table_info(plants)")}
        finally:
            conn.close()
        self.assertIn("my_col", cols)
```

Assert what your change guarantees: column present (`PRAGMA table_info`), new
table populated (`SELECT COUNT(*)`), a seeded value reachable through the read
API, and — for junction/derived tables — that the read-side synthesis matches
the stored rows (see `test_get_plant_synthesizes_uses_from_junction`). Use
`assertGreaterEqual(_SCHEMA_VERSION, NN)` rather than equality if you only care
that the feature exists from vNN onward (see `test_climate_cache`).

The DB is **never** stored in the source tree — `tests/test_polycultures.py`
asserts `_DB_PATH` resolves under the user-data dir. `src/user_paths.py` is the
single source of truth for that directory.

## Validation (run these)

From the repo root:

```bash
# The DB/seed test spine — fastest signal your change is coherent:
python -m unittest tests.test_uses_junction tests.test_data_quality tests.test_polycultures tests.test_climate_cache -v

# Seed-data schema/en/ reference validation (must exit 0):
python scripts/check_plant_data.py --quiet

# Full suite before you call it done (stdlib unittest — there is NO pytest here):
python -m unittest discover -s tests
```

All three were run in this session and pass (the first reports `OK`, the CLI
exits 0 with warnings-only, the full suite is the project gate). If you add a
new seeded data file, also append it to `data_quality.validate_all()` and to the
reseed wipe list per step 4.
