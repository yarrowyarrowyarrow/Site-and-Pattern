# Site & Pattern — Native Habitat Designer

**Turn your lawn into native habitat.** A landscape design tool for native plants, ecological restoration, and pollinator/wildlife habitat in Alberta and the Canadian prairies.

Site & Pattern is a desktop application for designing landscapes with native plants — focused on lawn-to-habitat conversion, pollinator gardens, and ecological restoration projects. It combines site analysis, plant community planning, plant companion relationships, native habitat structures, and a catalogue of over 400 plants native to Alberta and Saskatchewan. Search and filter by habitat value (keystone species, larval host plants, bird food) to prioritize the natives that do the most for local food webs.

> **Status:** Site & Pattern is in active development. Recent releases have concentrated on the accuracy of the plant catalogue and on its public website, [grownativeplants.ca](https://grownativeplants.ca). See [Going Forward](#going-forward) for where the live plan is kept.

> **Why it's built this way:** [`docs/DESIGN_PHILOSOPHY.md`](docs/DESIGN_PHILOSOPHY.md) lays out the design philosophy — thirteen principles (relationships over components, time as a design variable, ecological value made legible, Indigenous knowledge honoured through relationship not extraction, beauty as the mechanism the ecology survives by, …) mapped to where each one lives in the code. See also [`docs/PHILOSOPHY_ROADMAP.md`](docs/PHILOSOPHY_ROADMAP.md) and [`docs/REFERENCES.md`](docs/REFERENCES.md).

---

## Features

- **Site analysis overlays** — sun, wind, water, and other site condition mapping
- **Plant community planning** — assemble layered native plant communities (overstory, understory, shrub, groundcover, herbaceous) with documented companion relationships
- **Native habitat structures** — bee hotels, native bee logs, rock xeriscape, brush piles, snags, native lawn patches, rain gardens, bioswales, and ponds
- **Habitat-focused plant filters** — surface keystone species, larval host plants, bird-food producers, and nesting-material plants
- **Flower-colour filter** — eleven buckets classified from the recorded hex, with grasses and sedges grouped separately because they are wind-pollinated and have no showy flower
- **Hedgerows** — draw layered native hedgerows for property edges and wildlife corridors
- **Planning tools** — drag-and-place plant placement, undo/redo for plant placement
- **Plant database** — over 400 species native to Alberta and Saskatchewan, each with its nativity read from VASCAN (the Database of Vascular Plants of Canada)
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
   git clone https://github.com/yarrowyarrowyarrow/Site-and-Pattern.git
   cd Site-and-Pattern
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

Site & Pattern ships with a catalogue of over 400 plants native to Alberta and Saskatchewan. The data covers:

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
python -m src.cli build-site public/                        # catalogue → static website
python -m src.cli validate-data                             # check seed JSON
```

### The catalogue as a website

`build-site` renders the plant directory as plain static files: a species page
per plant, a search page filtering on **21 fields** in the browser (colour, bloom
month, ecoregion, sun, water, hardiness zone, height, life cycle, foliage,
growth rate, ecological role, safety, availability and more), browse hubs per
value, an ecoregion map, and a page per animal listing **the plants documented
to support it**. No framework, no build step, no CDN, and no external request
unless you switch analytics on: it can be hosted anywhere or opened straight
off disk.

```bash
python -m src.cli build-site public/ --base-url https://plants.example.org
```

Each species page carries two maps. The first is **where the plant has been
recorded**: a 0.25° grid shaded by record count, with herbarium specimens and
field observations drawn as separate marks you can toggle between. The second
is **which ecoregions those records fall in**, with the count and a confidence
band per region. The region outlines are the National Ecological Framework for
Canada v2.2, simplified to about 900 m for display, and every map says so. The
`/method/` page says what a record is, as of when, and what the maps cannot
tell you.

To put it online, see [`docs/PUBLISHING_THE_SITE.md`](docs/PUBLISHING_THE_SITE.md):
static files host free on GitHub Pages, Netlify or Cloudflare Pages.

Three things it does on purpose. Photographs are copied out of the local image
cache where they exist and are **never published without their credit**: a
species we cannot attribute simply shows no photo. The free-text `notes` field
is **withheld by default**, because some of it describes traditional plant-use
practice and publishing that to the open web is not ours to do (see Principle 12
in [`docs/DESIGN_PHILOSOPHY.md`](docs/DESIGN_PHILOSOPHY.md)); `--include-notes`
overrides it. The `medicinal` use *category* is published, on the author's
ruling in V2.50 that it is a horticultural category rather than traditional
knowledge. And no em dash reaches a rendered page.

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

## Going Forward

What is being built next, and what is known to be wrong, is kept in
[`docs/BACKLOG.md`](docs/BACKLOG.md): one line per open item, verified against
the code, with a row leaving when it ships. The reasoning behind each release,
including what it measured and what it deliberately left alone, is in
[`docs/plans/`](docs/plans/). What real people have reported, in their words,
is in [`docs/USER_FEEDBACK.md`](docs/USER_FEEDBACK.md).

*(Until V2.83 this section and a "Known Limitations" list above it described a
V1-era sprint whose headline items, a one-click installer, global undo and
drag-to-reposition, have long since shipped. They were replaced rather than
updated so this file stops carrying a plan that goes stale. The limitations
were not re-checked one by one; the V2.83 plan lists them so none is lost.)*

---

## Project History

Site & Pattern was built as a personal tool by Marci while studying ecological design in Alberta, with the goal of bringing native plant communities into landscape design more easily. The codebase has grown to include plant communities, site analysis, native habitat structures, planning tools, PDF export, and a headless scripting API (with CLI and MCP surfaces for AI agents), and now centres on lawn-to-habitat conversion for Alberta and prairie ecosystems.

---

## Documentation

- [`INSTALL.md`](INSTALL.md) — Installation guide for all platforms (one-click installers + from source), plus updating and troubleshooting
- [`docs/USER_GUIDE.md`](docs/USER_GUIDE.md) — In-app feature reference
- [`docs/BUILD.md`](docs/BUILD.md) — Building the installers (Windows `.exe`, macOS `.dmg`, Linux zip) and the release/packaging internals
- [`docs/README.md`](docs/README.md) — **What every document in `docs/` is for** — start here
- [`docs/ROADMAP.md`](docs/ROADMAP.md) — The effort/impact feature ledger; [`docs/ROADMAP_NEXT.md`](docs/ROADMAP_NEXT.md) carries the live plan
- [`docs/AGENT_API.md`](docs/AGENT_API.md) — Headless scripting API, CLI, and MCP tool reference for automation & AI agents
- [`docs/PROJECT_FILE_FORMAT.md`](docs/PROJECT_FILE_FORMAT.md) — The `.perma.geojson` project file format
- [`docs/DATABASE_SCHEMA.md`](docs/DATABASE_SCHEMA.md) — SQLite schema, seeding, and the version-bump checklist
- [`docs/3D_ASSETS.md`](docs/3D_ASSETS.md) — Blender-generated GLB assets for the 3D viewer: the `scripts/blender/assetlib` generator package (headless + Blender-MCP workflows), the generator↔viewer contract, and regeneration
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

Every fact and photograph this app ships, with its source and its licence, is
listed in **[`docs/DATA_SOURCES.md`](docs/DATA_SOURCES.md)** — including what
each licence obliges us to do and where the gaps still are. In short:

- **Photographs** — [iNaturalist](https://www.inaturalist.org/) contributors,
  CC0 / CC BY / CC BY-SA only, credited individually wherever a photo appears
- **Hardiness zones** — Natural Resources Canada
- **Soil** — Gridded Soil Landscapes of Canada (AAFC) and SoilGrids v2.0 (ISRIC)
- **Buildings, geocoding and map tiles** — OpenStreetMap contributors (ODbL),
  with CARTO, Esri and Mapbox basemap layers
- **Climate, wind and elevation** — [Open-Meteo](https://open-meteo.com/)
- **Plant data** — native-plant references for Alberta and the Canadian prairies
  (see [`docs/REFERENCES.md`](docs/REFERENCES.md)), compiled for this project

If a photograph of yours is here and the credit is wrong — or you would rather it
weren't here at all — open an issue and it will be fixed or removed.

Site & Pattern was developed with significant assistance from AI coding tools.

---

## Contact

For questions, bug reports, or feature suggestions, open an issue on this repository.
