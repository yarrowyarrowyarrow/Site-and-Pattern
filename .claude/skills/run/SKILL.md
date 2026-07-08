---
name: run
description: Use when launching the app or a satellite entry point — the PyQt6 GUI (python main.py), the headless CLI (python -m src.cli), the MCP server, examples/agent_session.py, or the packaging scripts. Covers local GUI launch and its dependencies, what runs vs breaks in a headless/no-PyQt6 container, first-launch DB creation/seeding at the per-OS data dir, and how to reset to a clean state safely.
---

# Running the app and its entry points

## Entry points at a glance

| Command | What it starts | Needs a display? | Needs PyQt6? |
|---|---|---|---|
| `python3 main.py` | The full GUI (`src.app.MainWindow`) | Yes (or offscreen) | Yes |
| `python3 -m src.cli <sub>` | Headless CLI over the facade | No | No |
| `python3 -m src.mcp_server` | MCP stdio server | No | No (needs `mcp` SDK) |
| `python3 examples/agent_session.py` | Worked facade example | No | No |
| `python3 -m src.permadesign_api` (import) | Scripting facade | No | No |

## Local GUI launch

```bash
# not run here — PyQt6 is absent in this container (see below)
python3 main.py
```

`main.py` installs a Qt warning-message filter, then constructs
`MainWindow`. It requires the deps in `requirements.txt` — notably PyQt6 and
PyQt6-WebEngine (the map is Leaflet inside `QWebEngineView`). On first launch
the app creates and seeds the user DB (see "First launch" below).

### `requirements.txt` vs `requirements-optional.txt`

- **`requirements.txt`** — everything needed to run the GUI: PyQt6 +
  WebEngine, `certifi` (HTTPS certs, see `debugging` §6), and the core data
  stack.
- **`requirements-optional.txt`** — heavier, feature-gated deps that the app
  degrades gracefully without: e.g. `shapely` (merged shade/wind-shadow
  geometry), `rasterio` + `pyproj` (soil GeoTIFF sampling, UTM projection).
  These were moved to *optional* deliberately (commit "move rasterio/pyproj
  to optional reqs") because bundling them broke the frozen DMG/EXE build.
  Modules that use them guard the import and skip the feature when absent —
  mirror that pattern if you add one (see `offline-packs` / `geo-projection`).

## Headless / offscreen launch (remote containers)

**Observed in this container:** `python3 main.py` — even with
`QT_QPA_PLATFORM=offscreen` — fails immediately:

```
ModuleNotFoundError: No module named 'PyQt6'
```

So the GUI **cannot run here at all**; PyQt6 (and shapely/numpy/rasterio)
are not installed. On a machine where PyQt6 *is* installed but there is no
display, launch offscreen:

```bash
QT_QPA_PLATFORM=offscreen python3 main.py     # constructs; no visible window
```

Even offscreen, `QWebEngineView` (Chromium) may need a sandbox flag in some
containers; if the map subprocess crashes, run from a terminal to see the
Chromium error and consult `docs/BUILD.md`. **For any domain work in a
headless environment, prefer the CLI / facade** — they need neither a display
nor PyQt6, and they exercise the same domain logic (see `agent-api`).

## The CLI (works headlessly — verified here)

```bash
python3 -m src.cli list-structures            # verified: prints 15 structures
python3 -m src.cli query yarrow --native      # search the catalogue
python3 -m src.cli validate-data --quiet      # data-quality gate (exit 0, warns)
python3 -m src.cli analyze path/to.perma.geojson
python3 -m src.cli export-catalogue out.docx  # needs python-docx
python3 -m src.cli generate "pollinator garden" --no-llm --out design.perma.geojson
```

Subcommands: `query`, `list-communities`, `list-structures`, `analyze`,
`export-catalogue`, `generate`, `validate-data`. Most take `--json` for
machine output; process exit code is non-zero on failure. It's a thin shell
over `src/permadesign_api.py` — no domain logic duplicated.

## The MCP server

```bash
pip install mcp            # SDK not bundled; build_server() imports it lazily
python3 -m src.mcp_server  # runs over stdio; point an MCP client at it
```

The tool *functions* (`tool_*` in `src/mcp_server.py`) are unit-testable
without the SDK; only the running server needs it. See `agent-api`.

## First-launch behaviour

On first GUI launch (and on the first facade/CLI call), `init_db()`
(`src/db/plants.py`):

1. Resolves the per-user data dir via `src/user_paths.py` (creates it;
   migrates a pre-V1.69 `PermaDesign` folder to `Site & Pattern` once).
2. Creates `permadesign.db` there and seeds it from the shipped
   `data/*.json` (plants, fauna, junctions, nurseries, communities).
3. Records the schema version in `PRAGMA user_version`.

Per-OS DB path (from `src/user_paths.py`):

- Linux: `~/.local/share/Site & Pattern/permadesign.db`
- macOS: `~/Library/Application Support/Site & Pattern/permadesign.db`
- Windows: `%APPDATA%\Site & Pattern\permadesign.db`

Seeding is idempotent; a reseed only re-fires when `_SCHEMA_VERSION` bumps
or the DB is near-empty (see `debugging` §2, `schema-change`).

## Reset to a clean state (destructive — warn first)

Deleting the user DB makes the next launch recreate + reseed it. **This
destroys any designs stored in that DB.** Saved `.perma.geojson` files
elsewhere are unaffected.

```bash
# Linux — irreversible for that DB's contents; confirm with the user first
rm "$HOME/.local/share/Site & Pattern/permadesign.db"
```

For a full reset (also clears downloaded terrain/building/soil packs and the
image cache), remove the whole `Site & Pattern` folder. Never delete the
source-tree `data/` — that's the shipped seed, not user data.

## Satellite scripts

`scripts/` holds one-off data tools, runnable with `python3 scripts/<name>.py`:
`check_plant_data.py`, `check_community_coverage.py`, `apply_safety_tags.py`,
`apply_sourcing_data.py`, `export_plant_docx.py`, `expand_fauna.py`,
`expand_prairie_flora.py`, `tag_prairie_provenance.py`, and more. The
packaging scripts live under `scripts/packaging/` — see `release-packaging`.

## Pitfalls

- **Don't assume the GUI runs in a remote container.** Here it can't (no
  PyQt6). Reach for the CLI/facade for anything that doesn't strictly need
  the window.
- **First launch writes to the user data dir, not the repo.** If your edits
  to `data/*.json` don't show up, that's the reseed-trigger issue, not a
  launch problem (see `debugging` §2).
- **`generate --no-llm`** works fully offline; without `--no-llm` it needs a
  reachable local LLM (Ollama by default) and falls back to offline
  generation if unreachable.
- Offscreen ≠ headless-safe for the map subprocess; WebEngine may still need
  flags.

## Key files

| Path | What |
|---|---|
| `main.py` | GUI entry: Qt warning filter → `MainWindow`. |
| `src/cli.py` | Headless CLI (`python -m src.cli`). |
| `src/mcp_server.py` | MCP stdio server (lazy SDK import). |
| `examples/agent_session.py` | Facade worked example / smoke. |
| `requirements.txt` | Core deps (PyQt6, WebEngine, certifi, …). |
| `requirements-optional.txt` | Feature-gated deps (shapely, rasterio, pyproj, …). |
| `src/user_paths.py` | Per-OS data dir + first-launch migration. |
| `scripts/` | One-off data/maintenance scripts. |

## Validation

```bash
python3 -m src.cli list-structures          # headless sanity check (exit 0)
python3 examples/agent_session.py           # facade round-trip
```
