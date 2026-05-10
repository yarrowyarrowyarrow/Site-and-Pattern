# PermaDesign

**A native plant landscape design tool for ecological designers and gardeners in Alberta and the Canadian prairies.**

PermaDesign is a desktop application for designing landscapes with native plants. It combines site analysis, polyculture planning, plant companion relationships, structures and hedgerows, and a 433-plant database focused on Alberta and the Canadian prairies.

> **Status:** PermaDesign is in active development. The current focus is on UI polish, the in-app polyculture builder, map interaction (drag-to-reposition, global undo), terrain/soil data integration, and packaging as a one-click Windows installer. See [Going Forward](#going-forward) for the live development plan.

---

## Features

- **Site analysis overlays** — sun, wind, water, and other site condition mapping
- **Polyculture planning** — plant communities and companion groupings with documented companion relationships
- **Structures and hedgerows** — windbreaks, fences, paths, and other design elements
- **Planning tools** — drag-and-place plant placement, undo/redo for plant placement
- **Plant database** — 433 native and naturalized species of Alberta and the Canadian prairies
- **Hardiness zone lookup** — automatic zone matching from location based on Canadian hardiness zone polygons
- **Permapeople API integration** — optional supplementary plant data from the [Permapeople](https://permapeople.org/) open database (requires free API credentials, see [Permapeople API Setup](#permapeople-api-setup-optional))
- **PDF export** — export your designs and plant lists as printable PDF documents
- **Local SQLite storage** — all your data stays on your machine

---

## Requirements

- Windows 10 or 11 (primary target; macOS/Linux from-source may work but is untested)
- Python 3.10 or newer (only required for from-source installs — the one-click `.exe` bundles its own runtime)
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
   venv\Scripts\activate
   pip install -r requirements.txt
   ```

3. Run the app:
   ```bash
   python main.py
   ```

On first run, the database is seeded automatically with the included plant data. The database lives at `~/.local/share/PermaDesign/permadesign.db`.

---

## Plant Database

PermaDesign V1 ships with a master database of 433 plants suitable for Alberta and the Canadian prairies. The data covers:

- Common and scientific names, plant type
- Hardiness zone range, sun and water requirements, soil pH range
- Mature dimensions, spacing, growth rate, years to maturity
- Bloom and fruit periods, monthly activity calendar (`cal_jan` through `cal_dec`)
- Permaculture uses, edible parts, native region
- Native to Alberta flag, deciduous/evergreen, perennial/annual

Plant data loads from `data/plants_master.json` on first run. The hardiness zone database (`data/hardiness_zones.json`) uses bounding-box matching from polygon centroids to look up zones by location.

---

## Permapeople API Setup (optional)

The Permapeople integration is optional and disabled by default. If you'd like to enrich plant entries with additional data from the [Permapeople](https://permapeople.org/) open plant database, you'll need free API credentials.

1. Create a free account at [permapeople.org](https://permapeople.org/)
2. Request API access from your account settings
3. Add your credentials to a `.env` file in the project root:
   ```
   PERMAPEOPLE_KEY_ID=your_key_id_here
   PERMAPEOPLE_KEY_SECRET=your_key_secret_here
   ```
4. Restart the app

Without these credentials, the rest of PermaDesign works normally — only the Permapeople-specific lookups are unavailable.

---

## Project Status and Known Limitations

PermaDesign is in active development. Known limitations being worked on in the current sprint:

- **Plant names with apostrophes** may cause issues in JavaScript-rendered components due to string escaping. Most plant names are unaffected.
- **Undo/redo** is being expanded from plant-only to a global undo across plants, structures, boundaries, and contours.
- **PDF export** falls back silently if a map screenshot cannot be captured. Designs export successfully but the embedded site map may be missing.
- **Polyculture placement tolerance** uses floating-point lat/lng matching, which is fragile in edge cases but works in normal use.
- **Soil data** outside of SoilGrids v2.0 (ISRIC) is incomplete; a fallback source is being integrated.
- **Edmonton open-data download** currently fails on field-name detection; under repair.

---

## Going Forward

The current development plan focuses on tightening the existing Alberta-focused tool rather than a full rewrite:

- **Polyculture builder** — a visual grid for assembling 5–8-plant Alberta polycultures in one screen and saving them locally
- **Map interaction** — drag-and-drop repositioning of placed plants and entire polyculture groupings, plus global Ctrl+Z across all placements
- **View bar overhaul** — fixed ordering (Satellite, Boundary, Measurement, Grid, Plants, Canopy, Structures), measurement hide-vs-delete distinction, configurable grid base size and opacity
- **Address finder** — partial-match-first search and crash fix on the Clear button
- **Terrain & soil** — repair the Edmonton dataset parser (or bundle the dataset locally) and add a soil-data fallback when SoilGrids is unavailable
- **Distribution** — one-click `.exe` installer for non-technical users (see [INSTALL.md](INSTALL.md))

The longer-term direction (cross-platform rewrite, ecoregion-aware nativity, expanded coverage beyond AB) remains on the table but is gated on the items above.

---

## Project History

PermaDesign was built as a personal tool by Marci while studying ecological design in Alberta, with the goal of bringing native plant communities into landscape design more easily. The codebase has grown to include polycultures, site analysis, structures, planning tools, PDF export, and Permapeople integration, and now centres on Alberta ecosystems.

---

## Documentation

- [`INSTALL.md`](INSTALL.md) — Installation instructions, including the one-click `.exe` installer for friends and testers
- [`FRIEND_SETUP_GUIDE.md`](FRIEND_SETUP_GUIDE.md) — Plain-English setup guide for non-technical users
- [`ROADMAP.md`](ROADMAP.md) — Feature roadmap with shipped vs. planned items
- [`SESSION_HANDOFF.md`](SESSION_HANDOFF.md) — Developer-facing notes for active development sessions
- [`USER_GUIDE.md`](USER_GUIDE.md) — In-app feature reference
- [`LICENSE`](LICENSE) — PolyForm Noncommercial License 1.0.0

---

## License

PermaDesign is licensed under the **[PolyForm Noncommercial License 1.0.0](https://polyformproject.org/licenses/noncommercial/1.0.0/)**.

In plain English, this means:

- **Free for personal use** — install it, use it for your own garden, share it with friends
- **Free for non-profit use** — community gardens, educational settings, non-profit ecological work
- **Free to modify and redistribute** for non-commercial purposes
- **Free for research and academic use**
- **Not free for commercial use** — you may not sell PermaDesign or services built on PermaDesign, or use it as part of a commercial product or service, without separate permission

If you'd like to use PermaDesign commercially, please open an issue to discuss a separate licensing arrangement.

---

## Acknowledgments

Plant data draws on:
- The [Permapeople](https://permapeople.org/) open plant database
- Native plant references for Alberta and the Canadian prairies
- Hardiness zone data from Natural Resources Canada

PermaDesign was developed with significant assistance from AI coding tools.

---

## Contact

For questions, bug reports, or feature suggestions, open an issue on this repository.
