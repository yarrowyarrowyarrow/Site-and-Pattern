# CLAUDE.md — Working Notes for Claude Code Sessions

This file is read automatically at the start of every Claude Code session
in this repository. It documents conventions and context that are easy to
miss otherwise.

## Project at a glance

**Site & Pattern** is a PyQt6 desktop app (Python 3.10+) for designing
landscapes with native plants — focused on lawn-to-habitat conversion,
pollinator gardens, and ecological restoration in Alberta and the
Canadian prairies. Local SQLite storage; Leaflet inside QWebEngineView
for the map; PyInstaller + NSIS for the Windows installer.

Entry point: `python main.py` → `src.app.MainWindow`.

The product was named **PermaDesign** before the V1.69 rebrand; user-facing surfaces
now read **Site & Pattern** (`src/branding.py`), while several internal identifiers keep
the legacy name on purpose (see the Database-path note below). The design philosophy that
drives the app lives in `docs/DESIGN_PHILOSOPHY.md` — strongly-aligned modules carry a
one-line `Design principle P#` anchor pointing back to it, guarded by
`tests/test_philosophy.py`.

## Design philosophy (read this first — weave it through your work)

This project is not a generic plant-placement tool; it is built on a coherent philosophy, and
work that ignores it tends to be technically fine but spiritually off. Before designing a
feature, skim where it sits in that philosophy. The sources of truth:

- [`docs/DESIGN_PHILOSOPHY.md`](docs/DESIGN_PHILOSOPHY.md) — the thirteen principles, each with a
  "Where this lives in the code" note and an honest **State** marker (*strong / partial / gap*).
- [`docs/PHILOSOPHY_ROADMAP.md`](docs/PHILOSOPHY_ROADMAP.md) — features (F1–F82) organized by the
  principle they serve, with a "Shipped" section at the top.
- [`docs/REFERENCES.md`](docs/REFERENCES.md) — the full bibliography.

**The thirteen principles, in one line each:**

1. Living systems self-organize from the bottom up — encode generative rules, not fixed layouts.
2. The best designs disappear into their context — aim for "grown, not designed".
3. Relationships matter more than components — the edge between species is the unit of value.
4. Time is the most undervalued design variable — design the trajectory, not the install day.
5. Perception is constructed, not received — make invisible ecology *visible*.
6. Conventional value metrics miss ecological value — make ecological value legible.
7. Generalist knowledge produces the most original insights — cross domains deliberately.
8. Repair is more sophisticated than creation — restoration/conversion is first-class.
9. Uncertainty is a feature, not a bug — ship ranges and confidence, never false precision.
10. Design for relationships, not objects — plants are nodes in a network.
11. The body and the site know things the screen does not — drive the user outside.
12. Indigenous knowledge is honoured through relationship, not extraction.
13. A native planting has to be loved to survive — beauty is the mechanism the ecology
    survives contact with people by, not decoration on top of it (adopted V2.33).

**HARD RULE (P12):** Do **not** incorporate Indigenous ecological knowledge, land-management
practices, plant-use traditions, or design frameworks into the data model, recommendations, seed
data, or UI without explicit **free, prior, and informed consent** from the relevant communities.
Until that consent exists, treat any reference as *directional only* — point toward the knowledge,
never encode or operationalize it. If a task seems to push in that direction, stop and raise it
with the user rather than proceeding.

**Keep the weave intact.** When you build something strongly aligned with a principle, add the
`Design principle P# — see docs/DESIGN_PHILOSOPHY.md` anchor at the top of the file, and keep the
doc's State markers and the roadmap's Shipped section honest. `tests/test_philosophy.py` guards
that the doc documents all thirteen themes and that every anchor names a real principle (1–13).

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

**This is now auto-enforced** by `.claude/hooks/branch_policy.py` (wired in
`.claude/settings.json`), so it no longer depends on remembering:
- On **SessionStart** the hook computes the next V-branch
  (`src/version_branch.py:next_version_branch` = newest `origin/V*.*` + 1 minor,
  or the current branch if it's already a V-branch) and, when the session starts
  on a `claude/*` codename / `main` / detached HEAD, **switches to it**
  (`git checkout -B <V>` from the current commit, no-clobber) and injects a
  directive into context. This **overrides** any harness-supplied "Git
  Development Branch Requirements" that names a codename branch.
- A **PreToolUse** guard **blocks** any `git push`/branch-create to a `claude/*`
  branch (deletes of codename branches are allowed — that's cleanup). Both hooks
  fail open so a hook bug can never block real work.

The "Check for Updates" button in the app
(`src/controllers/update_flow.py:_on_check_for_updates`) relies on this
convention to detect new versions on the server. Breaking the convention
silently breaks that feature. (V2.25: source checkouts update in-app with
one click — a stash-aware `git checkout -B <V> origin/<V>` + restart
prompt; the destructive `reset --hard` path deleted in V2.22 stays dead
and is pinned out by `tests/test_architecture_guard.py`. Frozen builds
update via GitHub Releases.)

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
`companion_enemies`, `uses`, `plant_uses`, `fauna`, `plant_fauna` (and
the attribute/nursery/cache tables) and re-seeds them from the shipped
JSON. **Add any new dependent tables to that wipe list** or they will
accumulate stale rows across reseeds. **Never wipe a table holding
user-authored rows**: `polycultures` / `polyculture_members` and `plant_photos` are wiped
only where `origin='seed'` (schema v46 / v55) so builder-authored communities
survive upgrades — user member `plant_id`s are re-pointed by name after
the plants wipe (`_remap_user_polyculture_plants`), because plant ids
are NOT stable across reseeds.

## Save the plan (READ THIS BEFORE STARTING WORK)

**Every increment leaves a plan behind**, in `docs/plans/`, named
`V<major>.<minor>-<short-slug>.md` — version first, matching the branch
convention above, so plans sort in release order and pair with the branch that
carried them out. Write it before the work, amend it as investigation changes
your mind, and commit it alongside the code.

A plan records the *reasoning*: what was measured, what was decided and why,
what was deliberately left alone, and what could not be verified. The commit log
already says what changed. See [`docs/plans/README.md`](docs/plans/README.md)
for the house style and the index of past plans — and **add a row to that index
table** when you add a plan.

## Running tests

```bash
python -m unittest discover -s tests
```

There is no `pytest` configuration; the suite uses stdlib `unittest`.

**The suite needs PyQt6 *and* the Qt runtime libs**, or ~156 widget tests skip
*silently* — which is how a `NameError` on every PDF export survived four minor
versions behind a green suite. On a bare container:

```bash
pip install PyQt6
apt-get update && apt-get install -y --no-install-recommends libegl1
```

The wheel alone is not enough (`ImportError: libEGL.so.1`), and the apt install
404s without the `update` first. A skipped test proves nothing — check the skip
count, not just the OK.

**And that is still not everything (found V2.38).** Without `PyQt6-WebEngine`
*every* test that drives a real `MainWindow` skips — 47 of them across
`test_undo_redo.py` and `test_app_smoke.py`, including the whole undo/redo
characterisation suite and the only tests that execute `app.py`'s signal
wiring. They skip with a message that reads like an environment limitation
(`No module named 'PyQt6.QtWebEngineWidgets'`) rather than a gap:

```bash
pip install PyQt6-WebEngine        # +47 tests actually run
```

With it installed the process **exits 139 (segfault) at teardown**, after the
summary — `Release of profile requested but WebEnginePage still not deleted`.
It fires even on a run where zero tests execute, so it is WebEngine shutdown,
not test code. **Read the `Ran N tests … OK` line, not the exit code** — and do
not confuse it with the V2.37 segfault, which was a real use-after-free
(worker threads emitting into deleted widgets, fixed in `src/qt_safety.py`) and
appeared *mid*-run.

Each test module redirects the DB to a `tempfile.mkdtemp` directory so
tests never touch the real user DB at `~/.local/share/Site & Pattern/`.

Some tests create temporary git repos via subprocess and disable
`commit.gpgsign` locally in those repos — this is test infrastructure
only, doesn't affect real commits.

## Key directories

| Path | What's there |
|------|--------------|
| `main.py` | Entry point. Installs Qt warning filter, constructs `MainWindow`. |
| `src/app.py` | `MainWindow` — the top-level window, menu bar, "Check for Updates" logic. Behaviour lives in `src/controllers/` (shim pattern; see `tests/test_architecture_guard.py`). |
| `src/project_store.py` | **The single write path for placed-plant state** (V1.62). Never mutate `_placed_plants` / plant features directly — `tests/test_project_store.py` greps the tree for violations. |
| `src/controllers/` | MainWindow's extracted behaviour: map-event router, persistence/undo, mode, generation, area fill, update flow. |
| `src/db/schema.sql` | Authoritative DDL. Loaded on every `init_db`. |
| `src/db/plants.py` | Database access layer + migration logic + seed helpers. |
| `src/db/photos.py` | **Photo sets with named slots (F70, V2.35).** Many photos per species — habit / flower / leaf / fruit / bark_stem / winter / seedling — keyed by `scientific_name` (ids are not stable across a reseed) with `origin='seed'` vs `'user'` deciding what a reseed destroys. `plants.image_url` is synthesized on read from the best slot, so every existing screen improves without a change at the call site. |
| `src/photo_import.py` | Bringing a photograph in (F72, V2.35): downscale, re-encode, and **strip EXIF unconditionally** — a photo of your own yard carries your home's GPS coordinates and these get committed. The stripper is stdlib so it cannot be skipped by Pillow being absent. |
| `src/db/fauna.py` | Query API for the fauna registry and plant↔fauna junction (V1.31+), plus the schema-v58 morphology loaders (`bee_morphology`, `lep_morphology`). |
| `html/botany/diagrams.js` + `html/botany/fauna.js` | **The vocabularies, drawn (V2.36).** Every term a bench asks you to choose — 33 botanical (leaf shape, inflorescence architecture, leaf arrangement) and 31 zoological (wing shape/pattern, resting posture, flight style, bee build, scopa) — as generated inline SVG, plus a glossary line each. A word you cannot picture is not a control. Also the source for `docs/*_FIELD_GUIDE.md` via `scripts/render_botany_diagrams.js`. |
| `scripts/tune_morphology.py` + `scripts/tune_fauna.py` | The catalogue benches (dev tools, not app panels): plants and animals, each with a drawn vocabulary beside every dropdown, provenance that travels with the values, and out-of-vocabulary refusal at the save endpoint. Shared scaffolding in `scripts/_bench_common.py`. |
| `src/scene_wildlife.py` | Which animals appear in a design, where they sit, and what they look like. **Appearance is data since schema v58** — the genus/name tables here are the fallback for a species nobody has described, not the only answer. |
| `src/db/relationships.py` | **The unified edges layer (F7, V2.31).** One query API + one edge vocabulary (`EDGE_KINDS`) over the schema-v51 `relationship_edges` view, which unions `plant_fauna`, both companion tables and shared polyculture membership. Ask "what is connected to this plant?" here, not table by table. Every edge carries `evidence` — `documented` (seeded record + `source`) vs `derived` (computed, e.g. two plants feeding the same animal). |
| `src/relationship_graph.py` | Relationship-web overlay core (F5, V2.31): the design as a drawable graph — species at their planting centroid, wildlife on a ring outside it. All geometry Python-side; `html/map/07-network.js` only renders. |
| `src/site_prep.py` + `src/planting_map.py` + `src/maintenance_calendar.py` | The take-it-outside document (F43/F41/F42, V2.31), assembled in job order by `src/planting_plan_export.py` and drawn as PDF pages by `src/pdf_export.py`: prep the ground → buy it (F40) → dig it in the right places → phase it (F17) → keep it alive. The planting map is a **scale drawing**, not a map screenshot; numbers are per species and key to the F40 buy list. |
| `src/onboarding.py` + `src/onboarding_flow.py` | Cold-start path (F44/F45, V2.31): the three-step progress model (pin → boundary → plants) read from the project, the beginner Generate defaults, and the worked example — authored as species *names* + metre offsets and resolved against the live catalogue at open time (never a shipped `.perma.geojson`, because plant ids aren't stable across reseeds). Surfaced by `src/welcome_dialog.py` + `src/first_step_bar.py`. |
| `src/db/polycultures.py` | Polyculture CRUD + seeded example communities. |
| `src/db/recipes.py` | Ratio-only polyculture recipes (separate from spatial polycultures). |
| `src/db/structures.py` | Hard-coded list of habitat structures (bee hotels, brush piles, etc.). |
| `src/version_branch.py` | Helpers for the V-branch convention (V1.32+). |
| `src/github_releases.py` | Qt-free GitHub Releases lookup + installer download for the frozen-build in-app updater (V1.73). |
| `src/app_version.py` | Reads the build's `version.txt` so a frozen `.dmg`/`.exe` knows its own V-version (V1.73). |
| `.github/workflows/release-macos.yml` | Builds the macOS DMG on a cloud Mac and publishes it to a GitHub Release on every `V*` push, feeding the in-app updater (V1.73). |
| `src/plant_panel.py` | Right-side plant browser + custom delegate. |
| `src/polyculture_panel.py` | Polyculture/community builder UI. |
| `src/analysis_panel.py` | Site analysis + Habitat Value Score breakdown. |
| `src/learn_panel.py` | Learn side tab: Field Study quiz, guided Lessons, Present/docent mode (V2.25). |
| `src/map_widget.py` + `html/map.html` + `html/map/*.js` | Leaflet map embedded via QWebEngineView. The JS is split into seven sequential classic scripts (V1.64, +`07-network.js` in V2.31) — shared-global model, NOT ES modules; load order matters. |
| `html/scene3d/01b-surface.js` | **Plant surfaces + `plantMaterial` (F63, V2.33).** Ten procedural surface classes (bark smooth/furrowed/papery/shaggy/scaly, leaf matte/glossy/pubescent/glaucous, needle) sampled triplanar in object space — no UVs, no textures in the GLBs, both of which are contract. Also owns the wind shader and `applySceneWind`. |
| `html/scene3d/14-layers.js` | The four procedural layer tufts (groundcover / grass / aquatic / vine), split out of `04-quality.js` in V2.34. The permanent fallback for the layer archetypes — Stylised skips the GLBs on purpose, so these run every session and cannot rot. |
| `html/scene3d/15-florets.js` | **The bloom as geometry (F80, V2.34).** A floret built from petal count × petal shape × radial/bilateral symmetry, plus a separate disc in its own colour, placed by one of nine inflorescence architectures (`solitary·raceme·spike·panicle·corymb·umbel·head·cyme·whorl`) — and **lit**, where the old billboard was `MeshBasicMaterial`. Reads the ten schema-v53 columns; an empty `flower_arch` falls back to the 05-flowers.js billboard, and Stylised keeps the billboard on purpose. |
| `html/scene3d/13-stylised.js` | **Stylised bodies (F79, V2.34).** Detail level 0 is a STYLE, not a thinning: no baked models, no surface grain, flat-shaded, forbs as faceted masses. The levels are **Stylised / Balanced / Lifelike**. Own the argument here, not in the quality knob. |
| `src/wind_scene.py` | The site's real seasonal wind + a rasterised shelter grid, as the 3D scene consumes it (F68, V2.33). Joins `wind.py` and `wind_shadow.py` — both years old — to the viewer that never read them. |
| `src/presentation_still.py` | The render you put in a proposal (F69, V2.33; `Design principle P13`). Turns the docent's beats — whose `year`/`season_month`/`camera` nothing had ever read — into still specs the 3D window renders at print resolution and `pdf_export` lays out. |
| `src/llm_design.py` | Generate Design: LLM spec → deterministic placement (scored cells, zones, keep-out, density). |
| `src/design_critic.py` | Evaluate→revise→repair loop for generated designs (V1.62). |
| `src/placement_score.py` | Per-cell ecological scoring + aesthetic composition terms (V1.62). |
| `src/scene_contract.py` | Versioned Scene JSON (`build_scene`) — the project→3D contract (V1.62). |
| `src/scene3d_window.py` + `src/map3d_widget.py` + `html/scene3d.html` | View → 3D Preview: built-in three.js viewer (or the `web3d/dist` map3d fork build when present). |
| `src/scan_import.py` + `src/scan_import_dialog.py` | Phone-scan import: point cloud → control-point georeference → nDSM → shade-casting footprints + 3D point layer (V1.62–63). Detects Gaussian-splat PLYs (V1.65). |
| `src/splat_backdrop.py` + `src/splat_flow.py` | Gaussian-splat photoreal backdrop (V1.65): file→three.js world matrix, lat/lng footprint, `splat_backdrop` feature (Qt-free core) + the map-side "yard photo" overlay glue. Rendered by Spark in `html/scene3d.html`; baked top-down onto the 2D map. |
| `src/building_store.py` + `src/building_downloader.py` + `src/building_flow.py` | Offline building-footprint pack (V1.66): SQLite `buildings.db` tile store + region bulk-downloader (OSM-sourced, mirrors the contour pack) + the import/download orchestration. Feeds the existing `osm_features.add_features_to_project` → `canopy_footprint` → shade + 3D. |
| `src/wind.py` + `src/wind_flow.py` + `src/wind_rose_widget.py` | Wind data (V1.67): Open-Meteo seasonal wind rose (DB-cached in `wind_cache` → offline) + live current reading + windbreak-orientation hint (Qt-free core in `wind.py`); off-thread fetch + QPainter rose in the Analysis → Wind tab. |
| `src/wind_shadow.py` + `src/wind_shadow_flow.py` | Dynamic wind shadow (V1.68): porosity-aware per-plant shelter merged via shapely (Qt-free core, reuses `shadow_geometry`); a 0–360 dial + "Live wind shadow" toggle drive a JS ghost (`06-overlays.js`, redrawn live on dial/drag) with Python computing the authoritative merged bands on commit. Wired from `app.py` (controllers at their ceilings). |
| `src/soil_grid.py` + `src/soil_downloader.py` + `src/soil_flow.py` | Offline soil pack (V1.67): download-once Gridded Soil Landscapes of Canada GeoTIFFs sampled by lat/lng (rasterio+pyproj). `property_data.fetch_soil` order = pack → SoilGrids → regional. `soil_flow.apply_soil_site_fields` wires soil pH into plant matching. |
| `src/permadesign_api.py` + `src/mcp_server.py` | Scripting facade + MCP tools (contract frozen by `test_architecture_guard.py`). |
| `src/terrain.py` etc. | DEM fetch + slope grid + contour rendering. |
| `data/*.json` | Shipped seed data (plants, fauna, plant↔fauna links). |

## Architectural conventions worth knowing

- **Database path:** `~/.local/share/Site & Pattern/permadesign.db` (Linux),
  `%APPDATA%/Site & Pattern/` (Windows), `~/Library/Application Support/Site & Pattern/` (macOS).
  Never put the DB inside the source tree — `tests/test_polycultures.py`
  has an assertion that enforces this.
  - **The data folder was `PermaDesign` before the V1.69 rebrand** and is renamed
    to `Site & Pattern` once, in place, on first launch — `src/user_paths.py` is the
    single source of truth (`user_data_dir` / `data_dir_path` / `migrate_legacy_into`);
    all stores (`plants`, `building_store`, `terrain_store`, `soil_grid`, `image_cache`)
    go through it. The DB *filename* stays `permadesign.db` (internal). The display
    name lives in `src/branding.py` (`APP_NAME`); the QSettings org/app name, the repo,
    and the frozen `permadesign_api`/MCP symbols deliberately keep the legacy name.
- **FK constraints are ON at runtime** (`plants.py:get_connection`) but
  disabled temporarily during the bulk reseed (Python 3.14 enforces FKs
  at statement time rather than transaction-commit time).
- **`permaculture_uses` is junction-backed (schema v37, V2.2):** the
  denormalized comma-blob column was dropped from `plants`; the
  `plant_uses` junction (seeded from the JSON `permaculture_uses` field)
  is the single source of truth. Read-side consumers still see a
  `permaculture_uses` comma-string, but it is *synthesized on read* from
  the junction in `get_plant` / `get_all_plants` / `search_plants` /
  `get_companions` (via `_attach_permaculture_uses`). The keyword filter
  in `search_plants` matches use tags through an EXISTS-on-`plant_uses`
  subquery. The JSON seed field stays — it feeds both the junction and
  `data_quality` validation.
- **The map only stores `(lat, lon)`.** Distance/area math goes through
  `src/projection.py` — default backend is the legacy cosLat metric
  (~1% error at <2 km — centimetres at yard scale, the app's real domain).
  A parallel UTM backend existed until V2.22 but no code path ever enabled
  it; it was deleted. A future accurate backend belongs behind the same
  `Projector` interface.
- **Placed-plant state has ONE write path:** `src/project_store.py`
  (V1.62). The project dict's plant features and the `_placed_plants`
  index are kept in sync by the store; `tests/test_project_store.py`
  fails the build on any new direct mutation in `src/`.

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
