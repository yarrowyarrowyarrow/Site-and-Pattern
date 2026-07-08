---
name: codebase-map
description: Orientation map of the Site & Pattern codebase. Use when starting a session, exploring the repo, finding where something lives, or deciding where new code goes (Qt-free core vs _flow glue vs widget vs controller vs db layer). Covers every subsystem — app shell, controllers, SQLite DB layer, Leaflet map JS, panels, generation/scoring, terrain/climate/soil/wind, 3D scene, import pipelines, agent API — plus a docs index, onboarding reading order, and a router to the other skills.
---

# Codebase Map

## Purpose

Site & Pattern is a PyQt6 desktop app for designing native-plant landscapes
(lawn-to-habitat conversion, Alberta/prairies focus). This skill is the router:
read it to know where things live and where your change belongs, then jump to
the specialist skill (see "Deeper dives" at the bottom). Full per-module
inventory: [reference.md](reference.md).

## The app in 30 seconds

- Entry: `main.py` → `src/app.py` `MainWindow`. Left: Leaflet map in
  QWebEngineView (`src/map_widget.py` + `html/map.html` + `html/map/`). Right:
  five side tabs (Site / Plants / Structures / Analysis / Planning).
- Reference data (plant catalogue, fauna, communities) lives in a per-user
  SQLite DB seeded from `data/*.json` — never in the repo tree
  (`src/user_paths.py` is the single source of truth for the directory).
- A design is a single GeoJSON file (`*.perma.geojson`) — a FeatureCollection
  with `element_type`-tagged features (`src/project.py`,
  `docs/PROJECT_FILE_FORMAT.md`).
- Everything headless is deliberately Qt-free and testable under bare `python`
  with stdlib `unittest` (no pytest). The GUI is a thin shell over those cores.
- The product was named **PermaDesign** pre-V1.69; internal identifiers
  (DB filename `permadesign.db`, `src/permadesign_api.py`, the QSettings org)
  keep the legacy name on purpose. User-facing strings come from
  `src/branding.py`.

## Subsystem map

### App shell & controllers

| Path | What |
|---|---|
| `main.py` | Entry point: SSL bootstrap, Qt warning filter, constructs `MainWindow`. |
| `src/app.py` | `MainWindow`: layout, menu, signal wiring, one-line shims. **At its 135-method guard ceiling** — behaviour goes in controllers/modules, wired via lambdas. |
| `src/controllers/map_events.py` | MapBridge → project-state event router (~50 `_on_*` handlers, `@undoable`). **2 lines under its 1950-line ceiling** — new handlers must delegate to flow modules. |
| `src/controllers/persistence.py` | Save/autosave, the whole undo/redo engine (`checkpoint`, `_HANDLERS`), `render_project_to_map`. |
| `src/controllers/mode.py` | Drawing-mode enter/cancel + mode label. |
| `src/controllers/generation.py` | One-click "Generate Design" orchestration. |
| `src/controllers/area_fill_controller.py` | Polygon-fill placement (draw-then-fill). |
| `src/controllers/update_flow.py` | Help menu, About, Check-for-Updates (git + GitHub Releases). |
| `src/controllers/undo_support.py` | The `@undoable` decorator (Qt-free). |
| `src/toolbar.py`, `src/ui_style.py`, `src/collapsible_panel.py`, `src/fill_tab_widget.py`, `src/filter_widgets.py` | Toolbar rows, shared stylesheet, reusable widgets. |
| `src/branding.py`, `src/settings.py`, `src/preferences_dialog.py`, `src/user_paths.py`, `src/resources.py` | App identity, QSettings, map-token dialog, per-user data dir, bundled-file locator. |

### Project state (the part everyone touches)

| Path | What |
|---|---|
| `src/project.py` | Project dict format, save/load, `project_to_map_data`, `new_placement_group_id`. |
| `src/project_store.py` | **The single write path for placed plants** — see the `placed-plants` skill before touching anything here. |
| `src/errors.py` | Typed `PermaDesignError` hierarchy for headless callers. |

### DB layer (`src/db/`)

| Path | What |
|---|---|
| `src/db/plants.py` | Connection, `_SCHEMA_VERSION` (currently 45), migration/reseed logic, `search_plants`, climate/wind caches. |
| `src/db/schema.sql` | Authoritative DDL, loaded on every `init_db`. |
| `src/db/seed_data.py` | Seeds the catalogue from `data/*.json`. |
| `src/db/polycultures.py`, `src/db/recipes.py` | Spatial plant communities + ratio-only recipes. |
| `src/db/fauna.py`, `src/db/nurseries.py`, `src/db/calendar_data.py`, `src/db/shade_zones.py`, `src/db/structures.py`, `src/db/import_usda.py` | Fauna registry, nursery directory, planting calendar, shade-tag cache, hard-coded structures, USDA import. |

### Map frontend (Leaflet in QWebEngineView)

| Path | What |
|---|---|
| `src/map_widget.py` | Qt wrapper + `MapBridge` (QWebChannel signals JS → Python). |
| `src/map_js.py` | Typed Python→JS builders for every JS entry point (never hand-format JS strings). |
| `html/map.html` | Thin shell; loads the six split scripts **in order**. |
| `html/map/01-core.js` … `html/map/06-overlays.js` | Shared-global classic scripts, NOT ES modules: core/bridge, boundary, plants, tools, features, overlays. Each has a guard line ceiling. |
| `src/member_colors.py` | Qt-free marker colour tables. |

### Side panels & Qt widgets

`src/plant_panel.py` (+ `src/plant_list_view.py`, `src/on_this_design_panel.py`,
`src/placement_controls.py`), `src/polyculture_panel.py`,
`src/structure_panel.py`, `src/site_panel.py`, `src/analysis_panel.py`,
`src/planning_panel.py`, plus small QPainter widgets
(`src/wind_rose_widget.py`, `src/forage_calendar_widget.py`,
`src/phenology_widget.py`, `src/docent_widget.py`, `src/field_study_widget.py`,
`src/lesson_track_widget.py`). Widgets draw; they never compute — the maths
lives in a Qt-free sibling module.

### Generation & placement scoring (Qt-free)

`src/design_api.py` (programmatic `DesignGenerator` — also the backbone of the
agent API), `src/llm_design.py` (prompt → LLM spec → deterministic placement),
`src/design_critic.py` (evaluate→revise→repair), `src/placement_score.py`
(per-cell scoring), `src/layout.py`, `src/exclusion.py` (keep-out),
`src/area_fill.py`, `src/zoning.py`, `src/design_goals.py`,
`src/planting_spacing.py`, `src/sourcing.py`, `src/polyculture.py`,
`src/pattern_language.py`, `src/succession.py`, `src/lawn_zones.py`,
`src/conversion_plan.py`. Qt-side: `src/generate_design_dialog.py`,
`src/generate_worker.py`.

### Ecology & analysis cores (Qt-free)

`src/habitat_score.py` (the 0–100 Habitat Value Score),
`src/ecological_role.py`, `src/plant_impact.py`, `src/chickadee_scenario.py`,
`src/phenology.py`, `src/forage_calendar.py`, `src/lesson_track.py`,
`src/field_study.py`, `src/docent.py`, `src/bee_habitat.py`,
`src/lep_habitat.py`, `src/creature_community.py`,
`src/reference_ecosystem.py` (+ `src/reference_ecosystem_window.py`),
`src/snapshot_timeline.py` (+ `src/snapshot_window.py`),
`src/planting_plan.py`, `src/field_notes.py`, `src/data_quality.py`,
`src/plant_conditions.py`. Most carry a `Design principle P#` anchor.

### Site data: terrain / climate / soil / wind / water

| Domain | Modules |
|---|---|
| Terrain | `src/terrain.py`, `src/hrdem.py`, `src/terrain_shade.py`, `src/terrain_store.py`, `src/terrain_downloader.py` |
| Sun & shade | `src/solar.py`, `src/shade.py`, `src/shadow_geometry.py` |
| Water | `src/hydrology.py` (D8 flow), `src/water_flow.py` (map glue), `src/precip_split.py` |
| Wind | `src/wind.py` + `src/wind_flow.py` + `src/wind_rose_widget.py`; `src/wind_shadow.py` + `src/wind_shadow_flow.py` |
| Snow | `src/snow.py`, `src/snow_microsite.py` + `src/snow_microsite_flow.py` |
| Soil | `src/soil_grid.py` + `src/soil_downloader.py` + `src/soil_flow.py` |
| Climate/region | `src/climate.py`, `src/ecoregion.py`, `src/property_data.py` (pin auto-fill) |
| Buildings/OSM | `src/osm_features.py`, `src/building_store.py` + `src/building_downloader.py` + `src/building_flow.py` |
| Shared plumbing | `src/tile_store.py`, `src/http_utils.py`, `src/ssl_bootstrap.py`, `src/image_cache.py`, `src/geometry.py`, `src/projection.py` |

Offline packs (terrain/buildings/soil) follow one pattern: SQLite/GeoTIFF store
+ bulk downloader + `*_flow` orchestration. **All geo math goes through
`src/projection.py`** — the map only stores `(lat, lng)`.

### 3D & scene

`src/scene_contract.py` (versioned Scene JSON — the project→3D contract),
`src/scene3d.py`, `src/scene3d_window.py`, `src/map3d_widget.py`,
`src/map3d_js.py`, `src/scene_wildlife.py`, `src/sprite_gallery.py` +
`src/sprite_gallery_window.py`, `src/splat_backdrop.py` + `src/splat_flow.py`
(Gaussian-splat backdrop), `src/web_assets.py` (localhost server for the
viewer). HTML: `html/scene3d.html`, `html/sprite_gallery.html`; vendored
three.js/Spark in `html/vendor/`; optional map3d fork build in `web3d/`.

### Import pipelines

`src/scan_import.py` + `src/scan_import_dialog.py` (phone scan → nDSM →
footprints), `src/footprint_extract.py`, `src/footprint_ndsm.py`,
`src/site_photo.py` + `src/site_photo_flow.py` (photo underlay),
`src/pdf_export.py` (GUI-only export).

### Agent / scripting surface (frozen contract)

`src/permadesign_api.py` (Qt-free facade), `src/cli.py`, `src/mcp_server.py`,
`examples/agent_session.py`, `docs/AGENT_API.md`. The surface is snapshotted by
`tests/test_architecture_guard.py` — see the `agent-api` skill.

### Release & updates

`src/version_branch.py` (V-branch convention), `src/github_releases.py`,
`src/app_version.py`, `scripts/packaging/` (PyInstaller spec, NSIS, build
scripts), `.github/workflows/release-macos.yml` and
`.github/workflows/release-windows.yml`.

## Where does my new code go? (decision tree)

1. **Pure computation, data shaping, geometry, scoring, HTTP fetch?**
   → New Qt-free module `src/<feature>.py`. No PyQt6 import, ever. Inject
   fetchers/clients for tests (see `src/wind.py`).
2. **Orchestration that touches MainWindow, threads, or several widgets?**
   → `src/<feature>_flow.py`: free functions taking `main`, wired from
   `src/app.py` `_connect_signals` (see `src/wind_flow.py`,
   `src/wind_shadow_flow.py`). Do NOT add MainWindow methods — it is at its
   method ceiling (135).
3. **New visual element?** → A widget module (`src/<feature>_widget.py`) that
   only paints, or a new tab inside an existing panel. Self-managing windows
   get their own `src/<feature>_window.py` opened via a lambda from the menu.
4. **Reacting to a map gesture / new MapBridge signal?** → Handler belongs
   conceptually to `src/controllers/map_events.py`, but that file has ~2 lines
   of guard headroom: write a 2–4 line handler that delegates to a flow
   module, or wire the signal straight to the flow via lambda in `app.py`.
5. **New reference data / query?** → `src/db/schema.sql` + `src/db/<domain>.py`
   + seed JSON in `data/` + `_SCHEMA_VERSION` bump (see the `schema-change`
   and `seed-data` skills).
6. **New map visual?** → JS in the right `html/map/0*.js` file (overlays →
   `html/map/06-overlays.js`) + a typed builder in `src/map_js.py` + a method
   on `src/map_widget.py`. Mind the per-file line ceilings.
7. **Mutating placed plants?** → Only through `src/project_store.py`
   (`placed-plants` skill). Mutating any feature? Decorate with `@undoable`.
8. **Headless/agent access?** → Extend `src/permadesign_api.py` AND the
   contract snapshots (`agent-api` skill).

## Docs index (`docs/`)

| Doc | One line |
|---|---|
| `docs/DESIGN_PHILOSOPHY.md` | The twelve principles + "where this lives in the code" + honest State markers. Read before designing features. |
| `docs/PHILOSOPHY_ROADMAP.md` | Features F1–F53 ranked by principle/impact; "Shipped" section is the historical record — keep it honest. |
| `docs/ROADMAP.md` | The effort/impact feature ledger (complementary to the philosophy roadmap). |
| `docs/REFERENCES.md` | Full bibliography behind the philosophy. Directional only — see the P12 hard rule in `CLAUDE.md`. |
| `docs/AGENT_API.md` | Scripting/CLI/MCP reference (lags the code slightly — the contract test is the truth). |
| `docs/PROJECT_FILE_FORMAT.md` | The `*.perma.geojson` format, feature `element_type`s, schema history. |
| `docs/DATABASE_SCHEMA.md` | SQLite catalogue schema narrative. |
| `docs/BUILD.md` | Run locally + build the 1-click installers. |
| `docs/USER_GUIDE.md` | 5-minute tour of the controls. |
| `docs/3D_SPRITES.md` | Catalogue of 3D plant sprites/geometry archetypes. |
| `docs/review.md` | Priorities/history primer for deep-dive code reviews. |
| `docs/data_gaps_v1.44.md` | Known seed-data gaps for the Generate Design goals. |
| `docs/archive/` | Historical brainstorms/handoffs — context only. |

## Data, scripts, tests

- `data/` — shipped seed JSON (`plants_master.json`, `garden_plants.json`,
  `fauna_master.json`, `plant_fauna_master.json`, nurseries, bee/lep
  attributes, ecoregions GeoJSON, hardiness zones, prairie fallbacks for
  rainfall/soil/wind). Changing these meaningfully ⇒ `_SCHEMA_VERSION` bump.
- `scripts/` — offline data tooling (catalogue checks `check_plant_data.py`,
  flora/fauna expanders, sprite renderers, DOCX export) + `scripts/packaging/`.
- `tests/` — stdlib `unittest` only. Run everything:
  `python -m unittest discover -s tests`. Qt-dependent tests self-skip
  headless. Every DB test redirects `src.db.plants._DATA_DIR`/`_DB_PATH` to a
  tempdir BEFORE importing consumers. The suite doubles as the architecture's
  enforcement: guard tests fail builds on ceiling/contract/path violations.

## Onboarding reading order

1. `CLAUDE.md`, then skim `docs/DESIGN_PHILOSOPHY.md` (the twelve principles).
2. `src/project.py` + `docs/PROJECT_FILE_FORMAT.md` — the data model.
3. `src/project_store.py` — the placed-plant invariant.
4. `src/app.py` down through `_connect_signals` — how everything is wired.
5. `tests/test_architecture_guard.py` — the ceilings and frozen contracts.
6. One exemplar triad end-to-end: `src/wind.py` → `src/wind_flow.py` →
   `src/wind_rose_widget.py` → its wiring in `src/app.py`.
7. `src/permadesign_api.py` + `examples/agent_session.py` — the headless view.

## Deeper dives (skills in .claude/skills/)

- **add-feature** — end-to-end feature playbook (triad pattern, ceilings, wiring, docs).
- **generate-design** — the LLM spec → deterministic placement → critic pipeline + Habitat Score.
- **placed-plants** — the ProjectStore single-write-path rule.
- **agent-api** — scripting facade / CLI / MCP and the frozen contract.
- **schema-change**, **seed-data** — DB schema and shipped JSON changes.
- **offline-packs** — terrain/building/soil pack pattern.
- **external-data** — Open-Meteo/OSM/SoilGrids fetchers + caching + fallbacks.
- **map-frontend** — Leaflet JS split, MapBridge, `src/map_js.py` builders.
- **geo-projection** — lat/lng math via `src/projection.py`.
- **scene-3d** — Scene JSON contract and the three.js viewer.
- **testing**, **debugging**, **verify**, **run** — proving and driving the app.
- **start-work** — branch convention (`V<major>.<minor>`) and session setup.
- **philosophy-check** — principle fit, anchors, State markers, the P12 rule.
- **release-packaging** — installers, GitHub Releases, in-app updater.
- **legacy-lessons** — the incident ledger: why each guard/convention exists.
