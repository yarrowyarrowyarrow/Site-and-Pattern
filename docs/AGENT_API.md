# PermaDesign Agent / Scripting API

PermaDesign can be driven entirely without the GUI through a **Qt-free**
Python surface. Nothing here imports PyQt6 or needs a display, a
`QApplication`, or the Leaflet map — so it runs in a plain interpreter,
a CI job, a CLI, or an MCP tool an AI agent calls.

Three layers, all over the same core:

1. **Scripting API** — `src/permadesign_api.py` (import and call directly)
2. **CLI** — `src/cli.py` (`python -m src.cli …` or the `permadesign` script)
3. **MCP server** — `src/mcp_server.py` (tools for Claude Code / MCP clients)

A complete, runnable example is
[`examples/agent_session.py`](../examples/agent_session.py). This doc is
the reference behind it.

---

## 1. Scripting API (`src.permadesign_api`)

```python
from src.permadesign_api import (
    Project, query_plants, list_polycultures, list_structures,
    run_analysis, export_plant_catalogue_docx,
)
```

The plant database is initialised lazily and idempotently on first use,
so a fresh checkout works without launching the GUI first.

### Catalogue queries

```python
query_plants(**filters) -> list[dict]
```
Search the plant catalogue. Filters (all optional) are forwarded to
`src.db.plants.search_plants`:

| filter | type | meaning |
|---|---|---|
| `query` | str | free-text on common/scientific name + uses |
| `plant_type` | str | tree, shrub, herb, groundcover, vine, root |
| `sun_req` | str | full_sun, partial_shade, full_shade |
| `water_needs` | str | low, medium, high |
| `zone` | int | hardiness zone |
| `native_only` | bool | Alberta natives only |
| `pollinator_only`, `host_plant_only`, `keystone_only`, `bird_food_only` | bool | ecological-use filters |
| `ab_ecoregion` | str | ecoregion tag (e.g. `aspen_parkland`) |

Each result dict includes `id` and `common_name`.

```python
list_polycultures(top_level_only: bool = True) -> list[dict]   # seeded communities; each has `id`
list_structures() -> list[dict]                                # habitat structures; each has `id`
```

### `Project`

```python
Project.create(name="Untitled Design", *, site_config=None, boundary=None) -> Project
Project.load(path: str) -> Project        # raises ProjectError if missing/invalid
```
`boundary` is a list of `(lat, lng)` tuples. `site_config` is an optional
dict (`latitude`, `longitude`, `hardiness_zone`, `soil_type`, …).

Mutators:
```python
proj.set_boundary(coords: list[tuple[float,float]], color="green")
proj.place_plant(plant_id, lat, lng, *, polyculture_name="", quantity=1)   # PlantNotFoundError on bad id
proj.place_polyculture(polyculture_id, center_lat, center_lng)             # PolycultureNotFoundError on bad id
proj.place_structure(struct_id, lat, lng)
proj.save(path: str)                                                       # ProjectError on I/O failure
```

Inspection:
```python
proj.name             -> str
proj.placed_plants    -> list[dict]   # {plant_id, common_name, lat, lng, placement_group_id, …}
proj.structures       -> list[dict]   # each struct_def (has `id`)
proj.as_dict()        -> dict         # the GUI-compatible project dict
proj.validate()       -> list[str]    # warnings (missing boundary, no plants, …)
proj.analyze()        -> dict         # convenience for run_analysis(proj)
```

### Analysis

```python
run_analysis(project: Project) -> dict
```
Returns:
```jsonc
{
  "habitat_score": {            // null if nothing placed
    "total": 44, "grade": "Foundation laid",
    "n_species": 8, "n_total_plants": 12,
    "components": {
      "native":     {"ratio": 0.91, "native_species": 10, "score": 18.3, "max": 20},
      "keystone":   {"species": [...], "score": 0.0, "max": 15},
      "host":       {"species": [...], "score": 0.0, "max": 10},
      "bird_food":  {"species": [...], "score": 3.0, "max": 10},
      "layers":     {"present": ["herbaceous", "shrub"], "score": 9, "max": 15},
      "structures": {"types": ["pond"], "score": 2, "max": 10},
      "bloom":      {"months": [...], "gap_months": [...], "score": 11.4, "max": 20}
    },
    "lepidoptera_supported": 3
  },
  "warnings": ["Hardiness zone not set", ...]
}
```
Raises `AnalysisError` if the plant DB can't be read.

### Export

```python
export_plant_catalogue_docx(out_path: str) -> str   # returns the written path
```
Headless DOCX export of the plant catalogue (needs `python-docx`; raises
`ExportError` otherwise). **PDF design export is GUI-only** — it needs a
live Qt printer and a rendered map screenshot, so it is intentionally not
exposed here.

### Errors (`src.errors`)

All subclass `PermaDesignError`, so a caller can catch the base:

`ProjectError`, `PlantNotFoundError`, `PolycultureNotFoundError`,
`AnalysisError`, `ExportError`.

### Minimal end-to-end

```python
from src.permadesign_api import Project, query_plants, run_analysis

proj = Project.create("My Yard", boundary=[
    (53.55, -113.50), (53.55, -113.49), (53.54, -113.49), (53.54, -113.50),
])
for p in query_plants(native_only=True, pollinator_only=True)[:5]:
    proj.place_plant(p["id"], 53.546, -113.494)
proj.place_structure("bee_hotel", 53.5462, -113.4935)
print(run_analysis(proj)["habitat_score"]["total"])
proj.save("my_yard.perma.geojson")
```

---

## 2. CLI (`src.cli`)

```bash
python -m src.cli <subcommand> …      # or `permadesign <subcommand> …` once installed
```

| subcommand | purpose |
|---|---|
| `query [text] [--type --zone --native --pollinator --host --keystone --bird-food --ecoregion --limit --json]` | search the catalogue |
| `list-communities [--json]` | seeded plant communities |
| `list-structures [--json]` | habitat structures |
| `analyze <project.perma.geojson> [--json]` | habitat score of a saved project |
| `export-catalogue <out.docx>` | plant catalogue → DOCX |
| `validate-data [--quiet --no-warnings]` | check shipped seed JSON |

`--json` gives machine-readable output. Exit code is `0` on success, `2`
on a `PermaDesignError` (e.g. missing project file), and argparse's `2`
for bad usage.

```bash
python -m src.cli query --native --pollinator "milkweed" --json
python -m src.cli analyze my_yard.perma.geojson
```

---

## 3. MCP server (`src.mcp_server`)

Exposes the scripting API as MCP tools for AI agents. Mutation tools are
**file-based and stateless**: each loads the project at `project_path`,
applies one change, and saves it back — matching MCP's request/response
model (no session state to lose between calls).

Install + run:
```bash
pip install -e '.[mcp]'      # or: pip install mcp
python -m src.mcp_server     # serves over stdio
```

Register with Claude Code:
```bash
claude mcp add permadesign -- python -m src.mcp_server
```

### Tools

| tool | args | returns |
|---|---|---|
| `query_plants` | `text`, plus `plant_type/zone/native_only/pollinator_only/host_plant_only/keystone_only/bird_food_only/ab_ecoregion/limit` | matching plant dicts |
| `list_communities` | — | seeded communities |
| `list_structures` | — | habitat structures |
| `create_project` | `project_path`, `name`, `boundary` (list of `[lat,lng]`) | project summary |
| `place_plant` | `project_path`, `plant_id`, `lat`, `lng` | updated summary |
| `place_community` | `project_path`, `polyculture_id`, `center_lat`, `center_lng` | updated summary |
| `place_structure` | `project_path`, `structure_id`, `lat`, `lng` | updated summary |
| `analyze_project` | `project_path` | habitat-score analysis |
| `project_summary` | `project_path` | name, counts, warnings |
| `export_catalogue` | `out_path` | `{"path": …}` |

A project summary is `{path, name, n_plants, n_structures, warnings}`.

The tool *logic* lives in plain `tool_*` functions in `src/mcp_server.py`
(testable without the MCP SDK); `build_server()` wires them into a
`FastMCP` server. `TOOL_SPECS` is the single registry — the
[architecture guard](../tests/test_architecture_guard.py) snapshots it so
the tool surface can't change by accident.

---

## Guarantees & boundaries

- **Headless / Qt-free.** None of the three layers import PyQt6
  (enforced by AST checks in the test suite).
- **Round-trip compatible.** Projects written by the API open in the GUI
  and vice-versa — same `*.perma.geojson` format
  ([`PROJECT_FILE_FORMAT.md`](PROJECT_FILE_FORMAT.md)).
- **Stable contract.** The facade surface and MCP tool set are snapshotted
  by `tests/test_architecture_guard.py`; changing them is a deliberate
  edit, not an accident.
- **GUI-only features.** PDF design export and live map interaction stay
  in the GUI. The headless export path is the plant-catalogue DOCX.
