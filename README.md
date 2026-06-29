# Site & Pattern — Native Habitat Designer

**Turn your lawn into native habitat.** A landscape design tool for native plants, ecological restoration, and pollinator/wildlife habitat in Alberta and the Canadian prairies.

Site & Pattern is a desktop application for designing landscapes with native plants — focused on lawn-to-habitat conversion, pollinator gardens, and ecological restoration projects. It combines site analysis, plant community planning, plant companion relationships, native habitat structures, and a 433-plant database focused on Alberta and the Canadian prairies. Search and filter by habitat value (keystone species, larval host plants, bird food) to prioritize the natives that do the most for local food webs.

> **Status:** Site & Pattern is in active development. The current focus is on UI polish, the in-app polyculture builder, map interaction (drag-to-reposition, global undo), terrain/soil data integration, and packaging as a one-click Windows installer. See [Going Forward](#going-forward) for the live development plan.

> **Why it's built this way:** [`docs/DESIGN_PHILOSOPHY.md`](docs/DESIGN_PHILOSOPHY.md) lays out the design philosophy — eleven principles (relationships over components, time as a design variable, ecological value made legible, …) mapped to where each one lives in the code. See also [`docs/PHILOSOPHY_ROADMAP.md`](docs/PHILOSOPHY_ROADMAP.md) and [`docs/REFERENCES.md`](docs/REFERENCES.md).

---

## Features

- **Site analysis overlays** — sun, wind, water, and other site condition mapping
- **Plant community planning** — assemble layered native plant communities (overstory, understory, shrub, groundcover, herbaceous) with documented companion relationships
- **Native habitat structures** — bee hotels, native bee logs, rock xeriscape, brush piles, snags, native lawn patches, rain gardens, bioswales, and ponds
- **Habitat-focused plant filters** — surface keystone species, larval host plants, bird-food producers, and nesting-material plants
- **Hedgerows** — draw layered native hedgerows for property edges and wildlife corridors
- **Planning tools** — drag-and-place plant placement, undo/redo for plant placement
- **Plant database** — 433 native and naturalized species of Alberta and the Canadian prairies
- **Hardiness zone lookup** — automatic zone matching from location based on Canadian hardiness zone polygons
- **PDF export** — export your designs and plant lists as printable PDF documents
- **Headless scripting** — a Qt-free Python API, CLI, and MCP server for automation and AI agents (see [AI agent usage](#ai-agent-usage-headless-scripting-cli-mcp))
- **Local SQLite storage** — all your data stays on your machine

---

## Requirements

- Windows 10 or 11, or macOS 11 Big Sur or newer (Linux from-source may work but is untested)
- Python 3.10 or newer (only required for from-source installs — the one-click Windows `.exe` and the macOS `.dmg` bundle their own runtime)
- ~200 MB disk space for the app and shipped data; up to ~16 GB if running with the full optional terrain/soil datasets

---

## Installation

> **One-click installer**: A standalone Windows installer is available — see [INSTALL.md](INSTALL.md) for details. The instructions below are for installing from source.

### From source

1. Clone this repository:
   ```bash
   git clone https://github.com/yarrowyarrowyarrow/PermaDesign.git
   cd PermaDesign
   ```

2. Create a virtual environment and install dependencies:
   ```bash
   python -m venv venv
   venv\Scripts\activate          # Windows
   source venv/bin/activate       # macOS / Linux
   pip install -r requirements.txt
   ```
   On macOS, `requirements.txt` automatically pins Qt to the 6.7 series —
   the last release that still runs on macOS 11 Big Sur.

3. Run the app:
   ```bash
   python main.py
   ```

On first run, the database is seeded automatically with the included plant data. The database lives at `~/.local/share/Site & Pattern/permadesign.db`.

---

## Plant Database

Site & Pattern V1 ships with a master database of 433 plants suitable for Alberta and the Canadian prairies. The data covers:

- Common and scientific names, plant type
- Hardiness zone range, sun and water requirements, soil pH range
- Mature dimensions, spacing, growth rate, years to maturity
- Bloom and fruit periods, monthly activity calendar (`cal_jan` through `cal_dec`)
- Ecological functions (keystone species, host plant, bird food, nesting material, pollinator, soil builder, nitrogen fixer, …), edible parts, native region
- Native to Alberta flag, deciduous/evergreen, perennial/annual

Plant data loads from `data/plants_master.json` on first run. The hardiness zone database (`data/hardiness_zones.json`) uses bounding-box matching from polygon centroids to look up zones by location.

---

## AI agent usage (headless scripting, CLI, MCP)

Site & Pattern can be driven entirely without the GUI through a Qt-free
scripting surface — useful for automation, batch design, and AI agents.
None of the surfaces below need a display, PyQt6, or a `QApplication`.

### Scripting API

`src/permadesign_api.py` is the single entry point. A complete worked
example lives in [`examples/agent_session.py`](examples/agent_session.py):

```python
from src.permadesign_api import Project, query_plants, run_analysis

proj = Project.create("My Yard", boundary=[
    (53.55, -113.50), (53.55, -113.49), (53.54, -113.49), (53.54, -113.50),
])
yarrow = query_plants(query="yarrow", native_only=True)[0]
proj.place_plant(yarrow["id"], 53.545, -113.495)
print(run_analysis(proj)["habitat_score"]["total"])   # → habitat score 0–100
proj.save("my_yard.perma.geojson")
```

Projects written here open in the GUI and vice-versa. Failures raise
typed exceptions from `src/errors.py` (never a GUI pop-up).

### Command line

```bash
python -m src.cli query --native --pollinator "milkweed"   # search plants
python -m src.cli list-communities                          # seeded communities
python -m src.cli analyze my_yard.perma.geojson             # habitat score
python -m src.cli analyze my_yard.perma.geojson --json      # machine-readable
python -m src.cli export-catalogue plants.docx              # plant catalogue → DOCX
python -m src.cli validate-data                             # check seed JSON
```

Installing the package registers a `permadesign` console script for the
same commands:

```bash
pip install -e .            # headless CLI + scripting API (no Qt deps)
pip install -e '.[mcp]'     # + the MCP server for AI agents
```

### MCP server (Claude Code & other MCP clients)

`src/mcp_server.py` exposes the scripting API as MCP tools
(`query_plants`, `list_communities`, `create_project`, `place_plant`,
`place_community`, `place_structure`, `analyze_project`,
`project_summary`, `export_catalogue`). Mutation tools are file-based:
each loads a project, applies one change, and saves it back.

```bash
pip install -e '.[mcp]'
python -m src.mcp_server        # runs over stdio
```

Register it with Claude Code:

```bash
claude mcp add permadesign -- python -m src.mcp_server
```

> PDF *design* export stays GUI-only — it needs a live Qt printer and a
> rendered map screenshot. The headless export path is the plant
> catalogue DOCX above.

---

## Project Status and Known Limitations

Site & Pattern is in active development. Known limitations being worked on in the current sprint:

- **Plant names with apostrophes** may cause issues in JavaScript-rendered components due to string escaping. Most plant names are unaffected.
- **Undo/redo** is being expanded from plant-only to a global undo across plants, structures, boundaries, and contours.
- **PDF export** falls back silently if a map screenshot cannot be captured. Designs export successfully but the embedded site map may be missing.
- **Polyculture placement tolerance** uses floating-point lat/lng matching, which is fragile in edge cases but works in normal use.
- **Soil data** outside of SoilGrids v2.0 (ISRIC) is incomplete; a fallback source is being integrated.
- **Edmonton open-data download** currently fails on field-name detection; under repair.

---

## Going Forward

The current development plan focuses on tightening the existing Alberta-focused tool rather than a full rewrite:

- **Plant community builder** — a visual grid for assembling 5–8-plant native plant communities in one screen and saving them locally
- **Map interaction** — drag-and-drop repositioning of placed plants and entire community groupings, plus global Ctrl+Z across all placements
- **View bar overhaul** — fixed ordering (Satellite, Boundary, Measurement, Grid, Plants, Canopy, Structures), measurement hide-vs-delete distinction, configurable grid base size and opacity
- **Address finder** — partial-match-first search and crash fix on the Clear button
- **Terrain & soil** — repair the Edmonton dataset parser (or bundle the dataset locally) and add a soil-data fallback when SoilGrids is unavailable
- **Distribution** — one-click `.exe` installer for non-technical users (see [INSTALL.md](INSTALL.md))

The longer-term direction (cross-platform rewrite, ecoregion-aware nativity, expanded coverage beyond AB) remains on the table but is gated on the items above.

---

## Project History

Site & Pattern was built as a personal tool by Marci while studying ecological design in Alberta, with the goal of bringing native plant communities into landscape design more easily. The codebase has grown to include plant communities, site analysis, native habitat structures, planning tools, PDF export, and a headless scripting API (with CLI and MCP surfaces for AI agents), and now centres on lawn-to-habitat conversion for Alberta and prairie ecosystems.

---

## Documentation

- [`INSTALL.md`](INSTALL.md) — Installation guide for all platforms (one-click installers + from source), plus updating and troubleshooting
- [`USER_GUIDE.md`](USER_GUIDE.md) — In-app feature reference
- [`BUILD.md`](BUILD.md) — Building the installers (Windows `.exe`, macOS `.dmg`, Linux zip) and the release/packaging internals
- [`ROADMAP.md`](ROADMAP.md) — Feature roadmap with shipped vs. planned items
- [`docs/archive/SESSION_HANDOFF.md`](docs/archive/SESSION_HANDOFF.md) — Archived developer session notes
- [`docs/AGENT_API.md`](docs/AGENT_API.md) — Headless scripting API, CLI, and MCP tool reference for automation & AI agents
- [`docs/PROJECT_FILE_FORMAT.md`](docs/PROJECT_FILE_FORMAT.md) — The `.perma.geojson` project file format
- [`docs/DATABASE_SCHEMA.md`](docs/DATABASE_SCHEMA.md) — SQLite schema, seeding, and the version-bump checklist
- [`examples/agent_session.py`](examples/agent_session.py) — Worked end-to-end headless scripting session (the canonical API example)
- [`LICENSE`](LICENSE) — PolyForm Noncommercial License 1.0.0

---

## License

Site & Pattern is licensed under the **[PolyForm Noncommercial License 1.0.0](https://polyformproject.org/licenses/noncommercial/1.0.0/)**.

In plain English, this means:

- **Free for personal use** — install it, use it for your own garden, share it with friends
- **Free for non-profit use** — community gardens, educational settings, non-profit ecological work
- **Free to modify and redistribute** for non-commercial purposes
- **Free for research and academic use**
- **Not free for commercial use** — you may not sell Site & Pattern or services built on Site & Pattern, or use it as part of a commercial product or service, without separate permission

If you'd like to use Site & Pattern commercially, please open an issue to discuss a separate licensing arrangement.

---

## Acknowledgments

Plant data draws on:
- Native plant references for Alberta and the Canadian prairies
- Hardiness zone data from Natural Resources Canada

Site & Pattern was developed with significant assistance from AI coding tools.

---

## Contact

For questions, bug reports, or feature suggestions, open an issue on this repository.
