# PermaDesign
Landscape design app
# Claude Code Prompt: PermaDesign V1 — Permaculture Landscape Design App

## What You’re Building

A desktop application called **PermaDesign** for permaculture landscape design. This is V1 — a working foundation, not a feature-complete product. The app should launch, display a map, let the user draw a property boundary, look up the climate/hardiness zone, browse and place plants from a local database, and save/load designs.

**Tech stack:** Python 3.11+, PyQt6 with QtWebEngineWidgets (for embedded map), SQLite (plant database), GeoJSON (project files).

**Target platform:** Windows desktop (the developer runs Windows with an RTX 5070 Ti / i7-14700F / 32GB DDR5). Linux compatibility is a nice-to-have but not required for V1.

-----

## Architecture

```
permadesign/
├── main.py                  # Entry point, app init
├── requirements.txt         # Dependencies
├── README.md                # Setup instructions
├── src/
│   ├── __init__.py
│   ├── app.py               # QApplication setup, main window
│   ├── map_widget.py         # QtWebEngine + Leaflet map
│   ├── plant_panel.py        # Side panel: plant browser, search, filters
│   ├── toolbar.py            # Drawing tools, mode switching
│   ├── project.py            # Save/load project as GeoJSON
│   ├── climate.py            # Hardiness zone lookup
│   └── db/
│       ├── __init__.py
│       ├── schema.sql        # SQLite schema for plant database
│       ├── seed_data.py      # Script to populate initial plant data
│       └── plants.py         # Database access layer
├── data/
│   └── hardiness_zones.json  # Simplified zone lookup data (lat/lng → zone)
├── html/
│   └── map.html              # Leaflet map HTML loaded by QtWebEngine
└── tests/
    └── test_climate.py       # Basic tests for zone lookup
```

-----

## Core Features to Implement

### 1. Main Window (app.py)

- PyQt6 QMainWindow with a horizontal split layout
- Left: map widget (70% width)
- Right: plant panel (30% width)
- Top toolbar for drawing tools and project actions
- Status bar showing cursor coordinates and current hardiness zone
- Menu bar: File (New, Open, Save, Save As, Exit)

### 2. Interactive Map (map_widget.py + map.html)

- Embed a Leaflet.js map inside QtWebEngineWidgets
- Use OpenStreetMap tiles (free, no API key needed) as the base layer
- Satellite imagery toggle using Esri World Imagery tiles (also free)
- Communication between Python and JS via QWebChannel:
  - Python → JS: add/remove/update map elements, set view
  - JS → Python: click coordinates, polygon complete events, element selection
- Drawing tools:
  - **Property boundary:** Draw a polygon. Only one per project. Clicking “Draw Boundary” enters polygon drawing mode; double-click or click first point to close.
  - **Plant placement:** Click to place a plant marker at a location. The marker should show the plant’s common name on hover.
  - **Zone circles:** Draw permaculture zones 0-5 as concentric circles/rings from a center point (the house/Zone 0). These are for visual reference, not hard boundaries.
- Layer visibility toggles in the toolbar

### 3. Plant Database (db/)

- SQLite database with a `plants` table:
  
  ```sql
  CREATE TABLE plants (
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      common_name TEXT NOT NULL,
      scientific_name TEXT,
      plant_type TEXT NOT NULL,  -- tree, shrub, herb, groundcover, vine, root
      hardiness_zone_min INTEGER,
      hardiness_zone_max INTEGER,
      sun_requirement TEXT,      -- full_sun, partial_shade, full_shade
      water_needs TEXT,          -- low, medium, high
      native_region TEXT,        -- e.g., "Western Canada", "North America"
      permaculture_uses TEXT,    -- comma-separated: nitrogen_fixer, dynamic_accumulator, pollinator, windbreak, etc.
      spacing_meters REAL,
      mature_height_meters REAL,
      notes TEXT
  );
  ```
- Seed with 40-60 plants relevant to **Canadian prairies / Alberta (Zone 3-4)**. Include a good mix:
  - Trees: poplar, spruce, birch, apple (hardy varieties like Goodland, Norland), cherry (Evans, Romance series), plum (Brookgold, Pembina), haskap, Siberian larch
  - Shrubs: saskatoon berry, chokecherry, buffalo berry, sea buckthorn, currant, gooseberry, raspberry, nanking cherry, potentilla, dogwood
  - Herbs/perennials: comfrey, yarrow, bee balm, echinacea, chives, horseradish, rhubarb, lovage, mint, chamomile
  - Groundcover: white clover, creeping thyme, kinnikinnick, wild strawberry
  - Nitrogen fixers: caragana, sea buckthorn, buffalo berry, white clover, alfalfa
  - Dynamic accumulators: comfrey, yarrow, dandelion, dock
  - Focus on species that are actually viable in Edmonton-area growing conditions

### 4. Plant Panel (plant_panel.py)

- Search box (filters by common name or scientific name as you type)
- Filter dropdowns: plant type, sun requirement, water needs, permaculture use
- Results list showing: common name, scientific name, type icon, zone range
- Click a plant → shows detail view with all fields
- “Place on Map” button → enters plant placement mode on the map
- Placed plants list at the bottom: shows all plants currently on the design with count

### 5. Climate/Hardiness Zone Lookup (climate.py)

- Given a latitude/longitude, return the approximate USDA/Canadian hardiness zone
- For V1, use a simplified lookup: bundle a JSON file that maps lat/lng ranges to zones for Western Canada. Doesn’t need to be pixel-perfect — approximate zone assignment is fine.
- When the user draws a property boundary, auto-detect the zone from the centroid and display it in the status bar
- Filter the plant panel to highlight plants suitable for the detected zone

### 6. Project Save/Load (project.py)

- Save format: GeoJSON with custom properties
  
  ```json
  {
    "type": "FeatureCollection",
    "properties": {
      "project_name": "My Food Forest",
      "created": "2026-03-27T12:00:00",
      "hardiness_zone": 3,
      "notes": ""
    },
    "features": [
      {
        "type": "Feature",
        "geometry": { "type": "Polygon", "coordinates": [...] },
        "properties": { "element_type": "property_boundary" }
      },
      {
        "type": "Feature",
        "geometry": { "type": "Point", "coordinates": [-113.5, 53.5] },
        "properties": {
          "element_type": "plant",
          "plant_id": 12,
          "common_name": "Saskatoon Berry",
          "quantity": 1
        }
      },
      {
        "type": "Feature",
        "geometry": { "type": "Point", "coordinates": [...] },
        "properties": {
          "element_type": "zone_center",
          "zone_radii": [5, 15, 30, 60, 120]
        }
      }
    ]
  }
  ```
- File dialog for open/save with `.perma.geojson` extension
- Auto-save to a temp file every 5 minutes

-----

## Important Implementation Notes

1. **Leaflet ↔ PyQt communication:** Use QWebChannel. In map.html, include `qwebchannel.js` and set up a channel object. The Python side registers a QObject with slots that JS can call, and uses `page().runJavaScript()` to call JS functions.
1. **Map default view:** Center on Edmonton, Alberta (53.5461, -113.4938) at zoom level 12.
1. **Don’t over-engineer:** This is V1. No user accounts, no cloud sync, no AI recommendations, no companion planting validation yet. Just: map + draw + plants + save.
1. **Dependencies to use:**
- PyQt6 + PyQt6-WebEngine
- No external geospatial libraries needed for V1 (Leaflet handles map rendering)
- sqlite3 (stdlib)
- json (stdlib)
1. **Error handling:** Basic but present. Don’t crash on bad data — show a QMessageBox with the error. Handle missing database gracefully (auto-create on first run).
1. **Make it look reasonable:** Use a clean, muted color scheme. Dark sidebar, light map. Plant type icons can be simple colored circles (green for trees, yellow-green for shrubs, etc.) — no need for custom artwork.

-----

## What NOT to Build Yet (Future Versions)

- Google Earth Engine / AlphaEarth Foundations integration (requires API auth setup — V2)
- Companion planting / guild validation logic
- Water flow or slope analysis
- Sun path calculation
- PDF/image export of designs
- Plant spacing conflict detection
- Multi-user collaboration
- Installer/packaging

-----

## Success Criteria

The app is done when:

1. It launches and shows a map centered on Edmonton
1. You can draw a property boundary polygon on the map
1. The hardiness zone updates in the status bar based on the boundary location
1. You can search/filter plants in the side panel
1. You can click “Place on Map” and drop a plant marker on the map
1. You can save the design to a .perma.geojson file and reload it
1. The plant database contains real, zone-appropriate species for Alberta

-----

## Getting Started

```bash
# Create project directory
mkdir permadesign && cd permadesign

# Set up virtual environment
python -m venv venv
venv\Scripts\activate  # Windows

# Install dependencies
pip install PyQt6 PyQt6-WebEngine

# Initialize the database
python -m src.db.seed_data

# Run the app
python main.py
```

Build this step by step. Start with the main window and embedded map, then add drawing tools, then the plant database and panel, then save/load. Test each piece before moving on.

