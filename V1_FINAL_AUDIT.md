# PermaDesign — V1 Final Audit

_Audited: 2026-04-25 | Branch: `claude/audit-app-codebase-bx5oa`_

---

## 1. Feature Inventory

The app is substantially past its V1 spec. Here is everything present in the codebase:

### Core Map
- Leaflet.js map embedded via PyQt6 WebEngine (CartoDB Voyager tiles + Esri satellite toggle)
- Property boundary polygon drawing
- Permaculture zone circles (Z0–Z4) with labels
- Plant markers as scaled circles in real metres
- Measurement tool + freehand annotations
- Zoom-dependent label visibility
- Snap-to-grid placement option
- Legend overlay (toggleable)
- Keyboard shortcuts: `P/G/S/A/T/M/Z/N/L/Esc`

### Plant Browser & Database
- 52+ seeded plants (Alberta Zone 3–4 focus)
- Full-text search by common or scientific name
- Filters: type, sun, water, permaculture use, zone, native AB, edible, medicinal, N-fixer, pollinator, perennial
- Plant detail panel showing 20+ attributes
- Planting calendar (12-month grid, colour-coded by status, current month highlighted)
- Custom marker colour per plant
- Placed-plants counter badge on each card
- Permapeople API integration: search 8,500+ profiles, import to local DB, threaded to prevent UI freeze

### Guild System
- Create guilds from multiple plants with named roles (canopy, understory, groundcover, N-fixer, pollinator, etc.)
- Canvas-based visual offset editor for member positioning
- Place a full guild on the map with one click
- Guild library stored in DB
- Export / import as `.guild.json` files
- 8+ built-in starter guilds
- Guild member tooltips + right-click removal

### Site Analysis Tools
- **A1 — Sun Path / Shadow:** 6 date presets, sunrise/sunset times, shadow direction arrows
- **A2 — Sector Analysis:** 8 directional wedges (sun, wind, frost, noise, views, fire)
- **A3 — Slope / Contour:** Manual contour line drawing with elevation labels
- **A4 — Wind Sector:** Prevailing wind direction + 10× height shelter zone overlay
- Seasonal view toggle (opacity adjustments for deciduous / evergreen / herbaceous)

### Landscape Elements
- **S1 — Structures:** 16 placeable objects across 5 categories (water, growing, animal, storage, infrastructure)
- **S2 — Hedgerows:** Polyline drawing, plant species selection, spacing, 4 visual styles
- **S3 — Custom Shapes:** 7 presets (bed, pathway, patio, etc.), fill/stroke colour picker, labels, area calculation

### Planning Tools
- **P2 — Maintenance Estimator:** Hours/year per plant type + capacity check
- **P3 — Harvest Calendar:** Monthly table grouped by plant, parses `fruit_period`
- **P6 — Water Budget Calculator:** Demand vs. rainfall + rain barrel / swale / pond catchment
- **V4 — Design Notes / Journal:** Per-project timestamped text entries
- Succession/timeline planner (partial — growth curve scaling by year to maturity exists)

### Project Management
- Save / load `.perma.geojson` (GeoJSON FeatureCollection containing all element types)
- Autosave every 5 minutes to `~/.permadesign_autosave.perma.geojson`
- New / Open / Save / Save As with file dialogs
- Undo / redo for plant placement (50-entry stack)
- Shopping list export grouped by plant type
- PDF export (map screenshot + title block + plant list + notes, 3+ pages)

---

## 2. Plant Data — Where It Lives & How It's Loaded

### Storage
- **SQLite database** at `~/.local/share/PermaDesign/permadesign.db` (platform path via `QStandardPaths`)
- Schema version 5 (`src/db/schema.sql`, 79 lines)

### Schema (key columns)
| Column | Notes |
|---|---|
| `id`, `common_name`, `scientific_name`, `plant_type` | Core identity |
| `zone_min`, `zone_max` | Hardiness range |
| `sun_requirement`, `water_needs`, `native_region` | Environment |
| `spacing_meters`, `mature_height_meters` | Physical size |
| `bloom_period`, `fruit_period`, `perennial_or_annual` | Phenology |
| `edible_parts`, `deciduous_evergreen`, `soil_ph_min/max`, `native_to_alberta` | Added in schema v2 |
| `growth_rate`, `years_to_maturity`, `growth_curve` | Added in schema v5 |
| `marker_color` | Custom hex per plant |

Related tables: `guilds`, `guild_members`, `planting_calendar`, `companion_friends`, `companion_enemies`, `structures`, `project_notes`.

### Seeded Data (first-run bootstrap)
1. **`src/db/seed_data.py`** — inserts 52 curated plants (trees, shrubs, herbs, groundcovers, vines, roots) with full metadata and 624 planting-calendar rows (52 plants × 12 months, Edmonton Zone 3b timing). Also seeds 30+ companion-planting relationships and 8+ starter guilds.
2. **`data/plants.json`** — 100+ additional plants auto-imported on first run; includes `growth_rate`, `years_to_maturity`, and `growth_curve` fields.
3. **`data/hardiness_zones.json`** — 35 bounding-box regions (BC / AB / SK / MB). Zone detection uses boundary-polygon centroid → smallest matching bounding box → latitude-band fallback. Lives in `src/climate.py` (92 lines).

### Runtime Access
- `src/db/plants.py` — data-access layer (200+ lines): search, filter, fetch by ID, upsert from API import, update `marker_color`.
- `src/api/permapeople.py` — threaded API client; normalises Permapeople schema to local schema before insert.

---

## 3. Bugs, Broken Features & TODOs

### From `SESSION_HANDOFF.md` (known, pre-existing)
| # | Issue | Severity |
|---|---|---|
| 1 | `QFont::setPointSize` console warnings on Windows | Cosmetic — harmless Qt noise |
| 2 | Permapeople `data` field may be list not dict | Guarded in `_normalize_plant()` |
| 3 | USDA import auto-download may fail if API changes | Medium — manual CSV workaround documented |
| 4 | Planting calendar timing is Edmonton-specific | Low — other zones need different month offsets |

### Issues Found in Code Review

**Medium priority**

- **JS string escaping is fragile** — Python builds JS call strings using `.replace("'", "\\'")`. A plant or guild name containing an apostrophe (e.g., `O'Brien's Mix`) will break the JS parser. Should use `json.dumps()` throughout. Affects: `app.py`, `map_widget.py` (multiple `run_js()` call sites).

- **Guild removal uses floating-point coordinate tolerance (1e-7 °)** — `_on_guild_removed()` in `app.py` matches placed guild members by comparing lat/lng within 1e-7 degrees (~1 cm). Works in practice but could mis-match or fail to match after many accumulated float operations at extreme latitudes. Refactoring to use opaque UUIDs would be safer.

- **PDF export silently falls back if map screenshot is `None`** — user gets a placeholder rectangle with no warning. Should at minimum show a dialog.

- **No duplicate-placement guard** — placing the same plant at the same coordinates twice is allowed (may be intentional for quantity, but it's not documented or communicated to the user).

**Low priority**

- **Undo/redo covers only plant placement** — boundary drawing, structures, hedgerows, shapes, and guilds do not push to the undo stack. The toolbar `Undo` button is therefore misleading for most operations.
- **No input length validation** — guild names, annotations, and shape labels have no max-length or sanitisation.
- **Permapeople API client has no rate-limit backoff** — rapid successive searches could hit API rate limits with no retry logic.
- **Succession/timeline planner is partial** — growth-curve data and year-to-maturity exist in the DB and `data/plants.json`, but the P1 timeline UI is listed as "Planned" in `ROADMAP.md`. The seasonal view toggle signal exists but the full timeline panel does not appear to be wired up end-to-end.

### TODOs & Roadmap Items Not Yet Implemented
- P1: Full succession/timeline planner UI
- P4: Crop rotation tracker
- P5: Input/output mapping
- V1: Food forest layer indicators
- V2: Season view (partially wired)
- V3: Photo overlay
- V5: 3D view
- X1–X5: Google Earth export, LIDAR import, community sharing, sensor integration

---

## 4. README & Documentation State

### `README.md`
- Well-written, beginner-friendly V1 spec document
- Covers: architecture, features, database schema, setup steps, success criteria
- **Significantly outdated** — describes the original V1 scope only; does not mention guilds, structures, analysis overlays, planning tools, Permapeople API integration, PDF export, or any other post-V1 additions
- Should be updated or replaced with a current feature summary

### `ROADMAP.md` (111 lines)
- Detailed feature tracker with 50+ items across 5 tiers
- Status marked per item (Done / Planned)
- "Already Implemented" section is comprehensive and reasonably up to date
- Good internal reference but not user-facing

### `SESSION_HANDOFF.md`
- Developer handoff note from a previous session
- Covers: current state summary, file structure, schema version, known issues, suggested next steps
- Not a public document; contains prompt templates for continuing development

### `FRIEND_SETUP_GUIDE.md`
- Non-technical Windows setup guide (Python install, Git, pip, first run, API key setup, troubleshooting)
- Clear and accurate for getting the app running
- Does not cover features beyond basic use

### Code-Level Docs
- Docstrings present in `app.py`, `map_widget.py`, `climate.py`, `project.py`
- `MapBridge` signal list is documented with descriptions
- Inline comments are moderate; complex logic sections are explained
- Type hints used throughout (Python 3.10+ style)
- Test coverage: 2 files (`test_climate.py` — 18 passing; `test_guilds.py`)

---

## 5. File Map (Quick Reference)

```
PermaDesign/
├── main.py                    # Entry point
├── requirements.txt           # PyQt6, PyQt6-WebEngine, python-docx
├── README.md                  # V1 spec (outdated)
├── ROADMAP.md                 # Feature tracker
├── SESSION_HANDOFF.md         # Dev handoff notes
├── FRIEND_SETUP_GUIDE.md      # Windows user guide
├── html/
│   └── map.html               # Leaflet.js UI (~1000 lines)
├── src/
│   ├── app.py                 # MainWindow — core controller (1631 lines)
│   ├── map_widget.py          # Qt↔JS bridge (372 lines)
│   ├── plant_panel.py         # Plant browser UI (1184 lines)
│   ├── guild_panel.py         # Guild builder UI
│   ├── structure_panel.py     # Structures/shapes UI
│   ├── analysis_panel.py      # Analysis overlays UI
│   ├── planning_panel.py      # Planning tools UI
│   ├── toolbar.py             # Tool buttons (~170 lines)
│   ├── climate.py             # Zone lookup (92 lines)
│   ├── project.py             # GeoJSON I/O (132 lines)
│   ├── settings.py            # Config dialog
│   ├── solar.py               # Sun path math
│   ├── pdf_export.py          # PDF generation
│   ├── api/
│   │   └── permapeople.py     # Permapeople API client (threaded)
│   └── db/
│       ├── schema.sql         # SQLite v5 schema (79 lines)
│       ├── plants.py          # Plant data-access layer
│       ├── guilds.py          # Guild CRUD
│       ├── structures.py      # Structures DB
│       ├── calendar_data.py   # Planting calendar data
│       ├── seed_data.py       # 52-plant catalogue + companion data
│       └── import_usda.py     # USDA CSV import utility
├── data/
│   ├── hardiness_zones.json   # 35 zone bounding boxes (BC/AB/SK/MB)
│   └── plants.json            # 100+ extended plant catalogue
└── tests/
    ├── test_climate.py        # Zone lookup tests (18 passing)
    └── test_guilds.py         # Guild tests
```

---

## Summary

PermaDesign is a mature, feature-complete permaculture design desktop app that substantially exceeds its original V1 spec. The architecture (PyQt6 + Leaflet.js + SQLite) is sound and cleanly separated. Plant data is well-structured, richly seeded for Alberta Zone 3–4, and extensible via the Permapeople API.

**No critical bugs were found.** The main issues are:

1. JS string-building via `.replace()` is fragile for names with apostrophes — should use `json.dumps()`
2. Undo/redo is scoped only to plant placement, which is misleading
3. README is stale — describes V1 only; the app is effectively v1.5+
4. Test coverage is thin (2 files)
5. Several roadmap items remain unimplemented (timeline planner, crop rotation, photo overlay)
