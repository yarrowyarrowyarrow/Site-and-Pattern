---
name: agent-api
description: Use when extending or calling the headless scripting API, the CLI, or the MCP server — adding a facade function, a CLI subcommand, or an MCP tool; scripting the app without Qt; or using the API as a headless test harness. Covers the Qt-free facade (src/permadesign_api.py), why symbols keep the legacy PermaDesign name, and the contract-is-a-test discipline that freezes the public surface in tests/test_architecture_guard.py.
---

# Agent / scripting API and its frozen contract

## What this is

`src/permadesign_api.py` is the single advertised, **Qt-free** entry point
for driving the app without the GUI. AI agents, automation scripts, the CLI
(`src/cli.py`), and the MCP server (`src/mcp_server.py`) all build on it.
Nothing in the facade imports PyQt6, so everything runs under a bare
`python` interpreter — no `QApplication`. The plant DB is initialised
lazily on first use (`_ensure_db()` → `src.db.plants.init_db`, idempotent),
so a fresh checkout works without ever launching the GUI.

Three layers, each a thin shell over the one below:

```
src/mcp_server.py   (MCP tools)      ─┐
src/cli.py          (argparse CLI)   ─┼─► src/permadesign_api.py (facade) ─► domain modules
your script / agent (import facade)  ─┘
```

The CLI and MCP tools **never duplicate domain logic** — each subcommand /
tool is a few lines around a facade call. Keep it that way.

## Verified minimal example

Runs headlessly (no Qt). This exact sequence was run in-session:

```bash
python3 -c "
from src.permadesign_api import Project, query_plants, run_analysis
proj = Project.create('Demo', boundary=[(53.55,-113.50),(53.55,-113.49),(53.54,-113.49),(53.54,-113.50)])
p = query_plants(query='yarrow')[0]
proj.place_plant(p['id'], 53.545, -113.495)
print('name:', proj.name, '| plants:', len(proj.placed_plants))
print('score:', run_analysis(proj)['habitat_score']['total'])
"
```

`examples/agent_session.py` is the fuller worked example (create → query →
place → analyze → save round-trip); run it end-to-end to sanity-check the
facade after a change.

## The public surface (facade)

Module-level functions (`src/permadesign_api.py`):
`query_plants(**filters)`, `list_polycultures(top_level_only=True)`,
`list_structures()`, `run_analysis(project)`,
`pull_plant_impact(project, plant_id)`, `chickadee_provision(project)`,
`phenology(project, month)`, `lesson_track(project)`,
`reference_community(ecoregion)`, `docent_script(project)`,
`export_plant_catalogue_docx(out_path)`.

The `Project` class: `create` / `load` (construction), `save`,
`set_boundary`, `place_plant`, `place_polyculture`, `place_structure`
(mutation), `as_dict` / `validate` / `analyze` / `name` / `placed_plants` /
`structures` (inspection). The wrapped dict is the exact GeoJSON format the
GUI reads and writes, so a project built here opens in the app unchanged.

Failures raise **typed** exceptions from `src/errors.py`
(`ProjectError`, `PlantNotFoundError`, `PolycultureNotFoundError`,
`AnalysisError`, `ExportError`, base `PermaDesignError`) — never a Qt
pop-up. Callers get structured, branchable errors.

### Why the legacy `PermaDesign` name

The module is `permadesign_api`, the CLI `prog` is `permadesign`, the MCP
server name is `"permadesign"`. This is **deliberate** (see CLAUDE.md → the
Database-path note): the frozen scripting/MCP API keeps the pre-V1.69
`PermaDesign` name so existing agents/scripts don't break. User-facing
strings read "Site & Pattern" (`src/branding.py`); these API symbols do not.
Don't "fix" them.

## The contract is a test — read this before extending

`tests/test_architecture_guard.py` (class `TestAgentApiContract`) snapshots
the entire public surface in three maps:

- `EXPECTED_API_FUNCTIONS` — function name → exact parameter-name list. It
  also asserts `api.__all__ == set(EXPECTED_API_FUNCTIONS) | {"Project"}`.
- `EXPECTED_PROJECT_METHODS` — the set of `Project` public members.
- `EXPECTED_MCP_TOOLS` — the set of MCP tool names (from
  `mcp_server.TOOL_SPECS`).

A change to any of these is a **breaking change** for agents/scripts/CLI,
so it must be a deliberate, reviewed edit to the snapshot — never an
accident. The test fails loudly with "update the contract snapshot
deliberately if intended." That message is the signal to make the matching
edit, not to route around it.

## Adding a new facade function

1. Write the function in `src/permadesign_api.py`. Call `_ensure_db()` first
   if it reads the DB. Wrap domain errors in a typed `src/errors.py`
   exception. Keep it Qt-free (no PyQt import, even transitively — import
   heavy domain modules lazily inside the function, as the existing
   analysis functions do).
2. Add its name to `__all__`.
3. Add it to `EXPECTED_API_FUNCTIONS` in `tests/test_architecture_guard.py`
   with its exact parameter names.
4. Add unit coverage in `tests/test_permadesign_api.py`.
5. Document it in `docs/AGENT_API.md`.

## Adding a new CLI subcommand

1. Write a `_cmd_<name>(args) -> int` handler in `src/cli.py` — a few lines
   around a facade call. Return a process exit code (0 = success).
2. Register a subparser in `_build_parser()` and `set_defaults(func=...)`.
   Add `--json` if the output is machine-consumed.
3. Add coverage in `tests/test_cli.py`.

## Adding a new MCP tool

1. Write a plain `tool_<name>(...)` function in `src/mcp_server.py` taking
   and returning JSON-friendly values — **no MCP dependency in the function
   body** (that's what keeps it unit-testable without the SDK). Mutation
   tools are stateless/file-based: take a `project_path`, `Project.load` it,
   apply one change, `save` it back.
2. Append `{"name": "<name>", "func": tool_<name>}` to `TOOL_SPECS` (the
   single source of truth — `build_server()` registers each entry; FastMCP
   reads the function signature + docstring to build the schema).
3. Add `"<name>"` to `EXPECTED_MCP_TOOLS` in
   `tests/test_architecture_guard.py`.
4. Add coverage in `tests/test_mcp_server.py`.

The MCP SDK (`mcp` package) is **not** required to run the tool functions or
their tests — `build_server()` imports it lazily and raises a clear install
hint if absent. Only running the actual server (`python -m src.mcp_server`)
needs `pip install mcp`.

## Using the API as a headless test harness

Because the facade is Qt-free and DB-lazy, it's the cheapest way to
exercise domain features without a display. Build a project in-memory,
place plants, call `run_analysis` / `pull_plant_impact` / `phenology` /
etc., and assert on the returned JSON-friendly dicts. This is how you
verify a scoring/analysis change end-to-end without launching Qt (see the
`verify` skill).

## Pitfalls

- **Don't import PyQt into the facade** — not even transitively. PDF design
  export is intentionally absent from the facade because `src/pdf_export.py`
  needs a live `QPrinter` + a rendered map screenshot; only the headless
  DOCX catalogue export is exposed.
- **Editing the surface without updating the snapshot** fails the guard.
  Editing the snapshot *without meaning to* ships a breaking change. Treat
  the `EXPECTED_*` maps as the API's changelog gate.
- **`place_structure` accepts unknown ids** (mirrors `DesignGenerator`) but
  attaches the real `struct_def` when it has one so habitat scoring counts
  it — don't add a "reject unknown id" check expecting tests to like it.
- Coordinates into `Project` are `(lat, lng)` tuples in `set_boundary` and
  `(lat, lng)` positional in `place_plant`; the stored GeoJSON is `[lng,
  lat]`. The facade does the flip for you — pass lat/lng.

## Key files

| Path | What |
|---|---|
| `src/permadesign_api.py` | The Qt-free facade + `Project`. `__all__` is the advertised surface. |
| `src/cli.py` | argparse CLI over the facade (`python -m src.cli`). |
| `src/mcp_server.py` | MCP tools; `TOOL_SPECS` registry; lazy SDK import. |
| `src/errors.py` | Typed exception hierarchy raised by the facade. |
| `docs/AGENT_API.md` | Human-facing API reference — keep in sync. |
| `examples/agent_session.py` | Worked end-to-end example / smoke script. |
| `tests/test_architecture_guard.py` | `TestAgentApiContract` — the frozen `EXPECTED_*` snapshots. |
| `tests/test_permadesign_api.py` | Facade unit tests. |
| `tests/test_cli.py` | CLI unit tests. |
| `tests/test_mcp_server.py` | MCP tool-logic unit tests (no SDK needed). |

## Validation

```bash
python3 -m unittest tests.test_architecture_guard tests.test_permadesign_api tests.test_cli tests.test_mcp_server -v
python3 examples/agent_session.py
```
