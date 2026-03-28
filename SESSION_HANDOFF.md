# PermaDesign — Session Handoff

**Branch:** `claude/build-step-1-v1-hTpZB`
**Repo:** `yarrowyarrowyarrow/PermaDesign`
**Last updated:** 2026-03-28
**Stack:** Python 3.11+, PyQt6 + QtWebEngine, SQLite, Leaflet.js, GeoJSON

---

## What Has Been Built (Steps 1–4 + A + B)

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
- Schema version tracking in `_schema_version` table (current = 2)
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

### Plant Catalogue
- 52 plants: 10 trees, 16 shrubs, 16 herbs/perennials, 5 groundcovers,
  3 vines, 2 roots
- Focus on Zone 3–4 Alberta / Canadian Prairies
- Invasive species removed (Dandelion, German Chamomile, Spearmint,
  Sea Buckthorn, Caragana, Valerian)
- 10 native Edmonton species added (Prickly Rose, Snowberry, Wild Mint,
  Prairie Crocus, Fireweed, Canada Goldenrod, Blanketflower, Harebell,
  Wild Lupine, Wild Clematis)

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
│   ├── plant_panel.py          PlantPanel — Local + Permapeople tabs
│   ├── project.py              GeoJSON save/load helpers
│   ├── settings.py             Config file + SettingsDialog
│   ├── toolbar.py              MainToolbar
│   ├── api/
│   │   └── permapeople.py      Permapeople API client + QThread worker
│   └── db/
│       ├── plants.py           DB access layer — init, search, get, companions
│       ├── schema.sql          SQL schema (v2) — plants + companion tables
│       └── seed_data.py        52 seed plants + SEED_COMPANIONS list
├── data/
│   ├── hardiness_zones.json    35 bounding-box hardiness regions
│   └── permadesign.db          SQLite DB (git-ignored, auto-created)
└── tests/
    └── test_climate.py         18 passing zone-lookup tests
```

---

## Next Steps (Steps C and D — Not Yet Started)

### Step C — Edmonton Planting Calendar
**Goal:** Month-by-month planting/growing status per plant, specific to
Zone 3b Edmonton (last frost ~May 20, first frost ~Sep 20).

**What to build:**
- New DB table: `planting_calendar(plant_id, month, status)` where status is
  one of: `start_indoors` | `direct_sow` | `transplant` | `harvest` |
  `dormant` | `growing`
- Populate calendar data for all 52 seed plants
- New panel or tab showing a 12-month grid for the selected plant,
  colour-coded by status
- Optionally: a "What to do this month" summary based on current date

**Schema addition:**
```sql
CREATE TABLE IF NOT EXISTS planting_calendar (
    plant_id INTEGER NOT NULL REFERENCES plants(id) ON DELETE CASCADE,
    month    INTEGER NOT NULL CHECK (month BETWEEN 1 AND 12),
    status   TEXT NOT NULL,
    notes    TEXT,
    PRIMARY KEY (plant_id, month)
);
```

### Step D — USDA Bulk CSV Import for Native Species Flag
**Goal:** Use the USDA PLANTS database bulk CSV to automatically populate
the `native_to_alberta` flag from authoritative data rather than manual entry.

**What to build:**
- Download script or one-time import script that reads the USDA PLANTS CSV
- Match on scientific name to existing plants in local DB
- Update `native_to_alberta = 1` where USDA data confirms Alberta nativity
- The USDA CSV is available at: plants.usda.gov/csvdownload (State = Alberta
  or Province AB lookup)

**Key file:** `src/db/import_usda.py` (new script, run once via CLI)

---

## Known Issues / Notes

- `QFont::setPointSize` warnings in the console on Windows — harmless Qt noise,
  can be suppressed by setting `QT_LOGGING_RULES=qt.qpa.*=false` env var
- Permapeople API response format: `POST /api/search` with JSON body `{"q":"term"}`;
  the `data` field in each plant object may be a list rather than a dict —
  already guarded against in `_normalize_plant()`
- Companion planting data in `SEED_COMPANIONS` in `seed_data.py` is currently
  an empty list `[]` — a future task is to populate known companion relationships
  for the 52 seed plants
- The Permapeople `_normalize_plant()` field mapping is best-effort; some fields
  (hardiness zone, spacing) may come back as None for plants with sparse data

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
> Steps 1–4 (core app), Step A (expanded plant schema with bloom/fruit/native/
> edible/pH/companion fields), and Step B (Permapeople live API search + import)
> are complete and working.
>
> Please read `SESSION_HANDOFF.md` in the repo root for the full current state,
> file structure, and detailed specs for the next steps.
>
> **Today's goal is Step C:** an Edmonton-specific planting calendar
> (Zone 3b, last frost ~May 20, first frost ~Sep 20) showing month-by-month
> status per plant, and/or Step D: USDA bulk CSV import to populate the
> `native_to_alberta` flag from authoritative data.
>
> Please read the relevant files before making any changes.
