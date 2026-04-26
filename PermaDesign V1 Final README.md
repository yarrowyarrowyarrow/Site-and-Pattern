# PermaDesign

**A native plant landscape design tool for permaculture practitioners and gardeners in Alberta and the Canadian prairies.**

PermaDesign is a desktop application for designing landscapes with native plants. It combines site analysis, guild planning, plant companion relationships, structures and hedgerows, and a 433-plant database focused on Alberta and the Canadian prairies.

> **This is the final V1 release.** Active development has moved to a successor project, **Site & Pattern**, which is a cross-platform rewrite focused on ecological landscape design with deeper plant data, ecoregion-aware nativity, integrated environmental data layers, and modern web technologies. PermaDesign V1 will remain available here for users who want to continue using it. See [What's Next](#whats-next) for details.

---

## Features

- **Site analysis overlays** — sun, wind, water, and other site condition mapping
- **Guild planning** — plant communities and companion groupings with documented companion relationships
- **Structures and hedgerows** — windbreaks, fences, paths, and other design elements
- **Planning tools** — drag-and-place plant placement, undo/redo for plant placement
- **Plant database** — 433 native and naturalized species of Alberta and the Canadian prairies
- **Hardiness zone lookup** — automatic zone matching from location based on Canadian hardiness zone polygons
- **Permapeople API integration** — optional supplementary plant data from the [Permapeople](https://permapeople.org/) open database (requires free API credentials, see [Permapeople API Setup](#permapeople-api-setup-optional))
- **PDF export** — export your designs and plant lists as printable PDF documents
- **Local SQLite storage** — all your data stays on your machine

---

## Requirements

- Windows 10 or 11 (other platforms not officially supported in V1)
- Python 3.10 or newer
- ~200 MB disk space for the app and database

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

PermaDesign V1 is feature-complete and stable for its intended scope. Known limitations:

- **Windows-only.** macOS and Linux installers are not officially supported in V1. From-source installation may work on those platforms with Python 3.10+ but is untested for V1 Final.
- **Plant names with apostrophes** may cause issues in JavaScript-rendered components due to string escaping. Most plant names are unaffected.
- **Undo/redo** covers plant placement only, not structure placement, shape edits, or guild changes.
- **PDF export** falls back silently if a map screenshot cannot be captured. Designs export successfully but the embedded site map may be missing.
- **Guild placement tolerance** uses floating-point lat/lng matching, which is fragile in edge cases but works in normal use.

These limitations are documented and will not be patched in V1. They are addressed in the Site & Pattern rewrite.

---

## What's Next

PermaDesign is being rewritten as **Site & Pattern**, a successor project that builds on the same foundation with:

- **Cross-platform** — desktop (via Tauri) and browser (PWA) from one codebase
- **Ecoregion-aware nativity** — moves beyond province-level "native" flags to CEC Level III ecoregion attribution with confidence levels and source attribution
- **Two-layer environmental data** — direct rainfall, soil, elevation, and hardiness data integrated with site analysis
- **Source-tracked plant data** — every fact in the database links to a citable source
- **Open source under AGPL-3.0** — keeping the project genuinely free and copyleft
- **Geographic expansion** — Alberta first, with infrastructure designed to extend across western Canada and beyond

Site & Pattern is in early planning. The repository will be linked here when public.

> **For permaculture practitioners** who prefer the existing tool: PermaDesign V1 will remain available indefinitely. This release is the polished, final version for ongoing use.

---

## Project History

PermaDesign was built as a personal tool by Marci while studying permaculture and ecological design in Alberta, with the goal of bringing native plant communities into landscape design more easily. The V1 codebase has grown beyond its original scope to include guilds, site analysis, structures, planning tools, PDF export, and Permapeople integration.

The pivot to Site & Pattern reflects an evolution in the project's positioning: keeping the design ethos of working with site conditions and natural patterns, while moving away from permaculture's branded vocabulary toward plain-English equivalents that serve a broader audience.

---

## Documentation

- [`INSTALL.md`](INSTALL.md) — Installation instructions, including the one-click installer for friends and testers
- [`ROADMAP.md`](ROADMAP.md) — Original V1 development roadmap (kept for historical reference)
- [`SESSION_HANDOFF.md`](SESSION_HANDOFF.md) — Developer-facing notes from late-stage V1 development
- [`V1_FINAL_AUDIT.md`](V1_FINAL_AUDIT.md) — Codebase audit performed before the V1 Final release
- [`LICENSE`](LICENSE) — PolyForm Noncommercial License 1.0.0

---

## License

PermaDesign V1 is licensed under the **[PolyForm Noncommercial License 1.0.0](https://polyformproject.org/licenses/noncommercial/1.0.0/)**.

In plain English, this means:

- ✅ **Free for personal use** — install it, use it for your own garden, share it with friends
- ✅ **Free for non-profit use** — community gardens, educational settings, non-profit ecological work
- ✅ **Free to modify and redistribute** for non-commercial purposes
- ✅ **Free for research and academic use**
- ❌ **Not free for commercial use** — you may not sell PermaDesign or services built on PermaDesign, or use it as part of a commercial product or service, without separate permission

If you'd like to use PermaDesign commercially, please open an issue to discuss a separate licensing arrangement.

The successor project Site & Pattern will be released under AGPL-3.0, which permits commercial use under copyleft terms.

---

## Acknowledgments

Plant data draws on:
- The [Permapeople](https://permapeople.org/) open plant database
- Native plant references for Alberta and the Canadian prairies
- Hardiness zone data from Natural Resources Canada

PermaDesign was developed with significant assistance from AI coding tools.

---

## Contact

For questions about PermaDesign V1 or interest in Site & Pattern, open an issue on this repository.
