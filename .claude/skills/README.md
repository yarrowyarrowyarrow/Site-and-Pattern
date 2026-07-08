# Site & Pattern — Skill Library

This library is the project's institutional memory. Each skill is a
procedural playbook, grounded in the actual code, written so that a
mid-level engineer or a smaller model can do the work at the standard the
project holds — without a senior engineer in the room.

Start every non-trivial session by reading `CLAUDE.md` (loaded
automatically), then pull the skill that matches your task. If you don't
know where to start, read **codebase-map** first.

`tests/test_skill_library.py` guards this library: every skill needs a
well-formed `SKILL.md`, every backticked repo path in a skill must exist,
and this index must mention every skill. If you move or delete a source
file, the guard will point you at the skills that need updating — update
them; they are part of the change, not an afterthought.

## Routing table

| If you are… | Use |
|---|---|
| New to the codebase, or unsure where code should live | `codebase-map` |
| Starting or finishing a unit of work (branches, commits, definition of done) | `start-work` |
| Designing or reviewing a feature against the twelve principles / P12 hard rule | `philosophy-check` |
| Adding a feature (controllers, core+flow+widget triad, ceilings, anchors) | `add-feature` |
| Changing `src/db/schema.sql` or anything needing a `_SCHEMA_VERSION` bump | `schema-change` |
| Editing seed JSON in `data/` (plants, fauna, junctions, nurseries) | `seed-data` |
| Touching placed-plant state, undo/redo, or the project dict | `placed-plants` |
| Editing the Leaflet map, `html/map/*.js`, overlays, or the JS bridge | `map-frontend` |
| Doing distance/area math, coordinates, shadow/shelter geometry | `geo-projection` |
| Working on the 3D preview, Scene JSON, sprites, splats, scan import | `scene-3d` |
| Adding/altering an offline data pack (terrain, buildings, soil) | `offline-packs` |
| Adding/altering a networked data source (fetch, cache, fallback) | `external-data` |
| Extending the scripting API, CLI, or MCP tools (frozen contract) | `agent-api` |
| Running or writing tests; a guard test tripped | `testing` |
| Chasing a bug (empty panels, blank map, stale data, network dead) | `debugging` |
| Proving a change actually works before committing | `verify` |
| Launching the app, CLI, MCP server, or scripts (incl. headless) | `run` |
| Building installers or shipping a release (DMG/NSIS/updater chain) | `release-packaging` |

## The shelves

**Process** — `start-work`, `philosophy-check`, `release-packaging`
**Architecture** — `codebase-map`, `add-feature`, `placed-plants`, `agent-api`
**Data layer** — `schema-change`, `seed-data`, `offline-packs`, `external-data`
**Frontend / geo / 3D** — `map-frontend`, `geo-projection`, `scene-3d`
**Quality** — `testing`, `debugging`, `verify`, `run`

## House rules the skills assume

- Release branches are `V<major>.<minor>`; never push to `claude/*`
  codename branches (`.claude/hooks/branch_policy.py` enforces this).
- Schema or seed-data changes require a `_SCHEMA_VERSION` bump in
  `src/db/plants.py` — see `schema-change` before touching either.
- Placed-plant state has one write path: `src/project_store.py`.
- The P12 hard rule (no operationalizing Indigenous knowledge without
  free, prior, informed consent) applies to data, recommendations, and UI
  content — `philosophy-check` has the full statement.
- The suite is stdlib `unittest`: `python -m unittest discover -s tests`.
