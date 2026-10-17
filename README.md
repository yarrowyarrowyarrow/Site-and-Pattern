# Site & Pattern — Native Habitat Designer

**Turn your lawn into native habitat.** A landscape design tool for native plants, ecological restoration, and pollinator/wildlife habitat in Alberta and the Canadian prairies.

Site & Pattern is a desktop application for designing landscapes with native plants — focused on lawn-to-habitat conversion, pollinator gardens, and ecological restoration projects. It combines site analysis, plant community planning, plant companion relationships, native habitat structures, and a catalogue of over 400 plants native to Alberta and Saskatchewan. Search and filter by habitat value (keystone species, larval host plants, bird food) to prioritize the natives that do the most for local food webs.

> **Status:** nearly finished. The homeowner's path (find your yard, plan it, read how it is doing, print it) is built; the last step is watching five homeowners use it ([`tools/usability/`](tools/usability/README.md)). After that it is maintained for fixes, by the runbook in [`docs/MAINTENANCE.md`](docs/MAINTENANCE.md).

> **Why it's built this way:** [`docs/DESIGN_PHILOSOPHY.md`](docs/DESIGN_PHILOSOPHY.md) lays out the design philosophy — thirteen principles (relationships over components, time as a design variable, ecological value made legible, Indigenous knowledge honoured through relationship not extraction, beauty as the mechanism the ecology survives by, …) mapped to where each one lives in the code. See also [`docs/PHILOSOPHY_ROADMAP.md`](docs/PHILOSOPHY_ROADMAP.md) and [`docs/REFERENCES.md`](docs/REFERENCES.md).

---

## Get started

### Download

Download the newest installer from the [Releases page](https://github.com/yarrowyarrowyarrow/Site-and-Pattern/releases): **`SiteAndPattern-V…-Setup.exe`** for Windows 10 or 11, **`SiteAndPattern-V….dmg`** for macOS 11 Big Sur or newer. The app is free and needs no account.

The installers are not code-signed, so the first launch shows a warning once:

- **Windows:** SmartScreen says *"Windows protected your PC"*. Click **More info**, then **Run anyway**. Then follow the installer.
- **macOS:** open the `.dmg` and drag **Site & Pattern** onto **Applications**. Double-click it once; macOS blocks it. Then open the Apple menu → **System Settings → Privacy & Security**, scroll down and click **Open Anyway**. (On macOS 11 to 14, right-click the app → **Open** → **Open** also works.) On Apple Silicon, click Install if macOS offers Rosetta.

After that it opens normally, and **Help → Check for Updates** installs new versions.

### Your first yard, in five steps

1. **Find your yard.** On the **Site** tab, type your address and press **Find**, or press **Click my yard on the map** and click it.
2. **Outline a bed.** Press **▱ Shape** above the map, choose *Garden Bed*, press **Draw on the map**, click the bed's corners and click the first corner again to close it.
3. **Plan my yard.** Press **Plan my yard** in the strip above the map. It fills the bed with plants native to your area, and **Try another** gives a different plan.
4. **Look at the overview.** **Design → Overview** says what the plan feeds, when it flowers, how full it is and what it will take.
5. **Print the plan.** **Share → Export → Export PDF…** gives the overview, the ground preparation, a shopping list, a planting map and a care calendar.

The same five steps open from **Help → How to Plan Your Yard**. The rest of the tools wait behind **View → Advanced tools**.

**It is not an identification guide.** The photographs and descriptions help you choose what to plant; check a plant's identity with a book or a person before you collect it from the wild or eat it.

**What leaves your computer.** The address you type goes to OpenStreetMap's address search when you press Find. Your yard's location goes to Open-Meteo and SoilGrids for its climate and soil, and the map's tile servers see the part of the map on screen. When you ask, a box around your yard goes to Overpass, Natural Resources Canada or the City of Edmonton. Nothing else leaves: no account, no analytics. **Help → About** says the same, and **Help → Where This Data Came From** credits every service.

**Feedback.** **Help → Send Feedback…** copies your message, ready to email, with no account needed; or [open an issue](https://github.com/yarrowyarrowyarrow/Site-and-Pattern/issues/new) if you have a GitHub account.

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

> **Installers** for Windows and macOS are on the [Releases page](https://github.com/yarrowyarrowyarrow/Site-and-Pattern/releases); [Get started](#get-started) says what the first launch looks like, and [INSTALL.md](INSTALL.md) has the details. The instructions below are for installing from source.

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
- [`docs/MAINTENANCE.md`](docs/MAINTENANCE.md) — the runbook: cutting and promoting a release, the pinned build, the yearly checks, what happens when a service breaks
- [`LICENSE`](LICENSE) — GNU General Public License, version 3
- [`THIRD_PARTY_NOTICES.txt`](THIRD_PARTY_NOTICES.txt) — the licences of Qt, PyQt6, Python, Leaflet, three.js and the other software the installer carries

---

## License

Site & Pattern is free software, licensed under the **[GNU General Public License, version 3](LICENSE)** (GPL-3.0-only).

In plain English, this means:

- **Free to use** — for your own garden, a community garden, a classroom, or anything else
- **Free to share** — give copies to anyone
- **Free to change** — and to share your changed version
- **What it asks in return** — a copy you pass on, changed or not, goes with its source code and these same freedoms, under this same licence

Until V3.18 the app was under the PolyForm Noncommercial License 1.0.0. The app is built on PyQt6, which is licensed under the GPL v3, and a program built on it cannot be distributed under a licence that forbids commercial use, so it was relicensed (decision D1 in [`docs/homeowner/12-decisions.md`](docs/homeowner/12-decisions.md)). The data and photographs the app ships keep their own licences, listed in [`docs/DATA_SOURCES.md`](docs/DATA_SOURCES.md).

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

For questions, bug reports, or feature suggestions, use **Help → Send Feedback…** in the app, or open an issue on this repository.
