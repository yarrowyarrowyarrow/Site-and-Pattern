# CLAUDE.md — Working Notes for Claude Code Sessions

This file is read automatically at the start of every Claude Code session
in this repository. It documents conventions and context that are easy to
miss otherwise.

## Project at a glance

**PermaDesign** is a PyQt6 desktop app (Python 3.10+) for designing
landscapes with native plants — focused on lawn-to-habitat conversion,
pollinator gardens, and ecological restoration in Alberta and the
Canadian prairies. Local SQLite storage; Leaflet inside QWebEngineView
for the map; PyInstaller + NSIS for the Windows installer.

Entry point: `python main.py` → `src.app.MainWindow`.

## Branch naming convention (READ FIRST)

**Release branches are named `V<major>.<minor>`** — for example `V1.31`,
`V1.32`, `V1.33`. Each release branch contains a single increment of work.

When starting a new piece of work:
- Inspect the existing branches (local + `origin/`) to find the highest
  numbered `V<major>.<minor>`.
- Create the next branch by **incrementing the minor version by 1**
  (e.g. if `V1.32` is the latest, start `V1.33`).
- Push the new branch to `origin` when work is committed.

**Do not** create branches with the FleetView-style codename pattern
(`claude/wizardly-goldberg-Ntd5l`, etc.), and do not push to such a
branch even if the harness suggests one as the default. If the system
default branch is a codename, override it and use the next `V*.*`.

The "Check for Updates" button in the app (`src/app.py` → `MainWindow._run_update_flow`)
relies on this convention to detect new versions on the server. Breaking
the convention silently breaks that feature.

## Schema versioning

The SQLite schema version is at `src/db/plants.py:_SCHEMA_VERSION`. The
current value is the one shipped with the latest `V*.*` branch.

**Always bump `_SCHEMA_VERSION` when you change `src/db/schema.sql` or
when the seeded data (`data/plants_master.json`, `data/garden_plants.json`,
`data/fauna_master.json`, `data/plant_fauna_master.json`) changes
meaningfully.** A bump triggers a one-time reseed on the user's next
launch — without it, existing installs will not pick up new tables or
new rows.

The reseed path (`src/db/plants.py:init_db` → "needs_reseed" block)
wipes `plants`, `planting_calendar`, `companion_friends`,
`companion_enemies`, `polyculture_members`, `polycultures`, `uses`,
`plant_uses`, `fauna`, `plant_fauna` and re-seeds them from the
shipped JSON. **Add any new dependent tables to that wipe list** or
they will accumulate stale rows across reseeds.

## Running tests

```bash
python -m unittest discover -s tests
```

There is no `pytest` configuration; the suite uses stdlib `unittest`.
Each test module redirects the DB to a `tempfile.mkdtemp` directory so
tests never touch the real user DB at `~/.local/share/PermaDesign/`.

Some tests create temporary git repos via subprocess and disable
`commit.gpgsign` locally in those repos — this is test infrastructure
only, doesn't affect real commits.

## Key directories

| Path | What's there |
|------|--------------|
| `main.py` | Entry point. Installs Qt warning filter, constructs `MainWindow`. |
| `src/app.py` | `MainWindow` — the top-level window, menu bar, "Check for Updates" logic. |
| `src/db/schema.sql` | Authoritative DDL. Loaded on every `init_db`. |
| `src/db/plants.py` | Database access layer + migration logic + seed helpers. |
| `src/db/fauna.py` | Query API for the fauna registry and plant↔fauna junction (V1.31+). |
| `src/db/polycultures.py` | Polyculture CRUD + seeded example communities. |
| `src/db/recipes.py` | Ratio-only polyculture recipes (separate from spatial polycultures). |
| `src/db/structures.py` | Hard-coded list of habitat structures (bee hotels, brush piles, etc.). |
| `src/version_branch.py` | Helpers for the V-branch convention (V1.32+). |
| `src/plant_panel.py` | Right-side plant browser + custom delegate. |
| `src/polyculture_panel.py` | Polyculture/community builder UI. |
| `src/analysis_panel.py` | Site analysis + Habitat Value Score breakdown. |
| `src/map_widget.py` + `html/map.html` | Leaflet map embedded via QWebEngineView. |
| `src/terrain.py` etc. | DEM fetch + slope grid + contour rendering. |
| `data/*.json` | Shipped seed data (plants, fauna, plant↔fauna links). |

## Architectural conventions worth knowing

- **Database path:** `~/.local/share/PermaDesign/permadesign.db` (Linux),
  `%APPDATA%/PermaDesign/` (Windows), `~/Library/Application Support/PermaDesign/` (macOS).
  Never put the DB inside the source tree — `tests/test_polycultures.py`
  has an assertion that enforces this.
- **FK constraints are ON at runtime** (`plants.py:get_connection`) but
  disabled temporarily during the bulk reseed (Python 3.14 enforces FKs
  at statement time rather than transaction-commit time).
- **`permaculture_uses` is in transition:** the comma-delimited blob on
  `plants` is kept populated for one release cycle while filter queries
  migrate to the `plant_uses` junction (V1.31). When safe, the column
  can be dropped — but only after every read site is checked.
- **The map only stores `(lat, lon)`.** All distance/area math currently
  uses an ad-hoc cosLat projection (~1% error at <2 km). Migrating to
  proper UTM via `pyproj` is a planned future step.

## When making schema/data changes

1. Edit `src/db/schema.sql`.
2. Bump `_SCHEMA_VERSION` in `src/db/plants.py`.
3. If you added a dependent table, also add a `DELETE FROM <table>` to
   the reseed block in `init_db`.
4. Update or add a seeding helper following the
   `_seed_uses_lookup` / `_seed_fauna` pattern.
5. Add tests under `tests/` using the temp-DB pattern from
   `test_polycultures.py` / `test_uses_junction.py`.
6. Run `python -m unittest discover -s tests`.

## Do not

- Push to `claude/*-Ntd5l` style branches. Use `V*.*` instead.
- Skip the schema version bump when changing schema or seed data.
- Hand-edit user data files outside of the seed JSON (they get
  overwritten on reseed anyway).
- Use `git commit --no-verify` or `--no-gpg-sign` on real commits
  unless explicitly asked.

## graphify

This project has a knowledge graph at graphify-out/ with god nodes, community structure, and cross-file relationships.

Rules:
- For codebase questions, first run `graphify query "<question>"` when graphify-out/graph.json exists. Use `graphify path "<A>" "<B>"` for relationships and `graphify explain "<concept>"` for focused concepts. These return a scoped subgraph, usually much smaller than GRAPH_REPORT.md or raw grep output.
- If graphify-out/wiki/index.md exists, use it for broad navigation instead of raw source browsing.
- Read graphify-out/GRAPH_REPORT.md only for broad architecture review or when query/path/explain do not surface enough context.
- After modifying code, run `graphify update .` to keep the graph current (AST-only, no API cost).
