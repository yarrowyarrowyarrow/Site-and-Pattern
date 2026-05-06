# PermaDesign — Session Handoff

**Branch:** `claude/build-step-1-v1-hTpZB`
**Repo:** `yarrowyarrowyarrow/PermaDesign`
**Last updated:** 2026-03-28
**Stack:** Python 3.11+, PyQt6 + QtWebEngine, SQLite, Leaflet.js, GeoJSON

---

## What Has Been Built (Steps 1–4 + A + B + C + D)

### Core App (Steps 1–4)
- **Map** (`html/map.html`) — Leaflet.js with CartoDB Voyager tiles, Esri
  satellite toggle, polygon boundary drawing, permaculture zone circles (Z0–Z4
  with labels), plant markers as `L.circle` scaled to mature spacing in real
  metres, right-click to remove markers
- **Python ↔ JS bridge** (`src/map_widget.py`) — QWebChannel bidirectional
  communication; all signals and slots documented in file
- **Main window** (`src/app.py`) — project state, autosave every 5 min to
  `~/.permadesign_autosave.perma.geojson`, zone detection from boundary centroid
- **Toolbar** (`src/toolbar.py`) — Draw/Layer toggles + ⚙ Settings button
- **Plant panel** (`src/plant_panel.py`) — debounced search, Type/Sun/Water/Use
  filters, zone filter, Native AB filter, expanded detail view, placed-plants list
- **Hardiness zones** (`src/climate.py`, `data/hardiness_zones.json`) — 35
  bounding-box regions for BC/AB/SK/MB with lat-band fallback
- **Project save/load** (`src/project.py`) — `.perma.geojson` GeoJSON format

### Step A — Expanded Schema
- 8 new columns on the `plants` table:
  `bloom_period`, `fruit_period`, `native_to_alberta`, `edible_parts`,
  `deciduous_evergreen`, `soil_ph_min`, `soil_ph_max`, `perennial_or_annual`
- 2 new companion planting tables:
  `companion_friends(plant_id_a, plant_id_b)` — bidirectional
  `companion_enemies(plant_id_a, plant_id_b)` — bidirectional
- Auto-migration in `init_db()` via ALTER TABLE (safe on existing databases)
- Schema version tracking in `_schema_version` table (current = 3)
- 52 seed plants fully populated with new fields
- Detail panel shows all new fields including colour-coded companion display

### Step B — Permapeople API
- `src/api/permapeople.py` — urllib-based client (no extra dependencies),
  `POST /api/search` with JSON body `{"q": "term"}`, field normalisation
  mapping Permapeople schema → local schema, `PermapeopleWorker(QObject)`
  runs in `QThread` so UI never freezes
- `src/settings.py` — stores key_id + key_secret in
  `~/.permadesign_config.json`; `SettingsDialog` for entering/updating keys
- Plant panel has two tabs: **Local** (existing browser) and **Permapeople**
  (live search + import-to-DB button)
- Imported plants land in the local DB and can be placed on the map

### Step C — Edmonton Planting Calendar (NEW)
- New DB table: `planting_calendar(plant_id, month, status, notes)`
  - Status values: `dormant`, `start_indoors`, `direct_sow`, `transplant`,
    `growing`, `harvest`, `pruning`
- Full 12-month calendar data for all 52 seed plants, tuned for Edmonton
  Zone 3b (last frost ~May 20, first frost ~Sep 20)
- Colour-coded 12-month grid in the plant detail panel, with:
  - Current month highlighted with a yellow border
  - Tooltip per cell showing status + notes
  - Legend for all status colours
  - "This month" summary note showing current month's task
- Data stored in `src/db/calendar_data.py` (624 entries = 52 plants × 12 months)
- Auto-seeded on first run via schema v3 migration
- Query functions: `get_calendar(plant_id)` and `get_current_month_tasks()`

### Step D — USDA Bulk CSV Import (NEW)
- `src/db/import_usda.py` — standalone CLI script to update `native_to_alberta`
  flag from the USDA PLANTS database CSV
- Supports both manual CSV path and auto-download
- Matches on normalised scientific name (Genus species, case-insensitive)
- Dry-run mode (`--dry-run`) for safe preview
- Reports: matched, newly flagged, not-found summary

### Plant Catalogue
- 52 plants: 10 trees, 16 shrubs, 16 herbs/perennials, 5 groundcovers,
  3 vines, 2 roots
- Focus on Zone 3–4 Alberta / Canadian Prairies
- Invasive species removed (Dandelion, German Chamomile, Spearmint,
  Sea Buckthorn, Caragana, Valerian)
- 10 native Edmonton species added (Prickly Rose, Snowberry, Wild Mint,
  Prairie Crocus, Fireweed, Canada Goldenrod, Blanketflower, Harebell,
  Wild Lupine, Wild Clematis)
- Companion planting relationships populated (30+ pairs in SEED_COMPANIONS)

---

## File Structure

```
PermaDesign/
├── main.py                     Entry point
├── requirements.txt            PyQt6>=6.6.0, PyQt6-WebEngine>=6.6.0
├── html/
│   └── map.html                Leaflet map (all JS lives here)
├── src/
│   ├── app.py                  MainWindow — project state, signal wiring
│   ├── climate.py              get_zone(lat, lng), zone_label()
│   ├── map_widget.py           MapBridge (QObject) + MapWidget (QWebEngineView)
│   ├── plant_panel.py          PlantPanel — Local + Permapeople tabs + calendar grid
│   ├── project.py              GeoJSON save/load helpers
│   ├── settings.py             Config file + SettingsDialog
│   ├── toolbar.py              MainToolbar
│   ├── api/
│   │   └── permapeople.py      Permapeople API client + QThread worker
│   └── db/
│       ├── plants.py           DB access layer — init, search, get, companions, calendar
│       ├── schema.sql          SQL schema (v3) — plants + companion + calendar tables
│       ├── seed_data.py        52 seed plants + SEED_COMPANIONS + SEED_CALENDAR import
│       ├── calendar_data.py    624 month-by-month entries for 52 plants (Edmonton 3b)
│       └── import_usda.py      USDA PLANTS CSV import for native_to_alberta flag
├── data/
│   ├── hardiness_zones.json    35 bounding-box hardiness regions
│   └── permadesign.db          SQLite DB (git-ignored, auto-created)
└── tests/
    └── test_climate.py         18 passing zone-lookup tests
```

---

## Next Steps (Ideas for Future Development)

### Step E — Layer Management & Plant Guilds
- Group plants into permaculture guilds (e.g. apple guild, nitrogen-fixer ring)
- Visual guild overlay on the map with toggle
- Guild template library for common food forest patterns

### Step F — Seasonal Timeline View
- Timeline showing all plants' activities across the year in one view
- Gantt-chart style display: "What's happening in my garden in July?"
- Export as printable monthly task sheet

### Step G — Soil & Microclimate Overlays
- Paint soil type zones on the map (clay, sand, loam)
- Shade analysis from tree canopy projections
- Moisture gradient overlay based on slope/drainage

### Step H — Export & Reporting
- Export plant list as CSV/PDF with full details
- Generate planting plan document with calendar
- Print-ready map export at scale

### Step I — Multi-Project & Collaboration
- Multiple project tabs
- Project templates for common Edmonton lot sizes
- Share/import project files with other users

---

## Known Issues / Notes

- `QFont::setPointSize` warnings in the console on Windows — harmless Qt noise,
  can be suppressed by setting `QT_LOGGING_RULES=qt.qpa.*=false` env var
- Permapeople API response format: `POST /api/search` with JSON body `{"q":"term"}`;
  the `data` field in each plant object may be a list rather than a dict —
  already guarded against in `_normalize_plant()`
- The Permapeople `_normalize_plant()` field mapping is best-effort; some fields
  (hardiness zone, spacing) may come back as None for plants with sparse data
- USDA import script (`import_usda.py`) auto-download may fail if the USDA API
  changes; manual CSV download is the reliable fallback
- Calendar data is Edmonton-specific; other zones would need different timing

---

## Prompt for Next Session

Paste this at the start of your next Claude Code session:

---

> I am continuing development of **PermaDesign**, a desktop permaculture
> landscape design app for Windows built with Python 3.11+, PyQt6 +
> QtWebEngine, SQLite, and Leaflet.js.
>
> **Repository:** yarrowyarrowyarrow/PermaDesign
> **Branch:** `claude/build-step-1-v1-hTpZB`
>
> Steps 1–4 (core app), Step A (expanded schema), Step B (Permapeople API),
> Step C (Edmonton planting calendar), and Step D (USDA CSV import) are
> complete and working.
>
> Please read `SESSION_HANDOFF.md` in the repo root for the full current state,
> file structure, and ideas for next steps.
>
> Please read the relevant files before making any changes.
