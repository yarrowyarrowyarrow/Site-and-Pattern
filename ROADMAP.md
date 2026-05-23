# PermaDesign — Feature Roadmap

A prioritized list of features for the Alberta-focused **Native Habitat Designer** — turning lawns into native plant habitat. Organized by effort/impact tiers, with the active sprint at the top.

---

## Current Sprint (in progress)

| Area | Item | Status |
|------|------|--------|
| Pivot | Reframe app from "Permaculture Landscape Designer" to "Native Habitat Designer"; add habitat-focused plant tags (keystone species, host plant, bird food, nesting material); swap permaculture-coded structures for native bee logs, brush piles, snags, rock xeriscape, native lawn patch, bee hotel | Done |
| Cleanup | Drop deprecated "guilds" terminology in favour of "plant communities"; remove legacy/duplicate files | Done |
| Cleanup | Trim README/ROADMAP to current state and current-sprint plan | Done |
| Cleanup | Update Friend Setup Guide for the `.exe` one-click installer | Done |
| UI | Address finder: partial-match-first; fix "Clear" button crash | Planned |
| UI | Global Ctrl+Z / cancel across plants, structures, boundaries, contours | Planned |
| UI | Site panel: pin-drop cursor + reverse-geocode to actual address | Planned |
| Map | Remove zone circles entirely | Planned |
| Map | Reorder View tab to Satellite, Boundary, Measurement, Grid, Plants, Canopy, Structures | Planned |
| Map | Measurements: hide via toggle (don't delete); right-click to delete | Planned |
| Map | Grid menu: 1×1 / 5×5 / 10×10 / 100×100 m, opacity + colour | Planned |
| Plants | Plant panel: label or rainbow icon for the colour picker | Planned |
| Plants | Overlap slider range −50% to +50% (0 = no gap, no overlap) | Planned |
| Communities | Visual-grid plant community builder (5–8 plants), saved locally, AB-focused | Planned |
| Communities | Drag-to-reposition placed items: individual plants and whole plant communities | Planned |
| Data | Edmonton open-data parser fix or local bundling | Planned |
| Data | Soil fallback when SoilGrids v2.0 (ISRIC) is unavailable | Planned |
| Distribution | One-click `.exe` Windows installer | In progress |

> **Out of scope for this sprint:** SQLite schema expansion and dataset growth. These are being handled separately on a local AI workflow.

---

## Tier 1 — Structures & Map Elements (Medium effort, high impact)

Placeable landscape elements beyond plants.

| ID | Feature | Description | Status |
|----|---------|-------------|--------|
| S1 | **Structures library** | Placeable icons/shapes for: pond, bioswale, rain garden, rain barrel, compost bin, raised bed, shed, fire pit, fence/wall, plus native habitat elements — native bee habitat log, bee hotel, brush pile, snag, rock xeriscape, native lawn patch | Done |
| S2 | **Hedgerow / fence line tool** | Draw a polyline that renders as a hedge or fence with selectable plant species along it | Done |
| S3 | **Custom shape drawing** | Free-form polygon drawing for garden beds, pathways, patios — with fill color/pattern and labels | Done |

---

## Tier 2 — Analysis & Simulation (Medium-high effort, very high impact)

Tools that help designers understand their site.

| ID | Feature | Description | Status |
|----|---------|-------------|--------|
| A1 | **Sun path / shadow overlay** | Given lat/lng + date, draw the sun arc and show shadow direction arrows for morning/noon/evening — helps place shade-sensitive crops | Done |
| A2 | **Sector analysis layer** | Draw directional wedges on the map for sun, prevailing wind, frost flow, noise, views — directional site analysis | Done |
| A3 | **Slope / contour indicator** | Manual or imported contour lines to show terrain; helps place swales and ponds correctly | Done |
| A4 | **Wind sector & windbreak effect** | Mark prevailing wind direction; windbreak structures/hedges show a "shelter zone" behind them (10x their height) | Done |

---

## Tier 3 — Planning & Data (Low-medium effort, high value)

Features for long-term planning and tracking.

| ID | Feature | Description | Status |
|----|---------|-------------|--------|
| P1 | **Succession / timeline planner** | A time slider showing how the design evolves: Year 1 (annuals), Year 3 (young shrubs), Year 10 (full canopy). Plants grow/appear based on their mature size over time | Planned |
| P2 | **Maintenance / labor estimator** | Each element gets estimated hours/year. The app totals it up so you know if you're over-designing for your available time | Done |
| P3 | **Wildlife & Human Forage calendars** | Two expandable tree views — Wildlife Forage (pollinator nectar + bird food, nectar-gap flagging) and Human Forage (edible plants by harvest window). Each month expands to the individual plants providing forage. | Done |
| P4 | **Crop rotation tracker** | For annual beds, track what was planted where each season to avoid repeating families | Planned |
| P5 | **Input/output mapping** | Tag elements with inputs (water, fertilizer) and outputs (manure, mulch, food). Highlight "energy leaks" where outputs aren't connected to nearby inputs | Planned |
| P6 | **Water budget calculator** | Estimate total water needs of placed plants vs. rainfall + any catchment (rain barrels, swales, pond) | Done |

---

## Tier 4 — Visual & UX Enhancements (Low effort, nice polish)

| ID | Feature | Description | Status |
|----|---------|-------------|--------|
| V1 | **Vegetation layer indicators** | Visual markers for vegetation layers (overstory, understory, shrub layer, herbaceous, groundcover, vine, root) with layer toggle | Planned |
| V2 | **Season view toggle** | Switch map appearance between spring/summer/fall/winter to see deciduous vs. evergreen coverage | Planned |
| V3 | **Print / PDF export** | Export the current map view as a presentation-quality PDF with legend, title block, and plant list | Done |
| V4 | **Design notes / journal** | Per-project text area for recording observations, soil test results, and design rationale | Done |
| V5 | **Photo overlay** | Import a site photo or drone image as a semi-transparent overlay under the map for reference | Planned |

---

## Tier 5 — Integrations & Advanced (High effort, long-term)

| ID | Feature | Description | Status |
|----|---------|-------------|--------|
| X1 | **Google Earth integration** | Import KML/KMZ from Google Earth for property boundaries, elevations, and satellite imagery; export designs back to Google Earth for 3D fly-through visualization | Planned |
| X2 | **3D view** | Basic 3D visualization using plant heights and canopy sizes | Planned |
| X3 | **Elevation / LIDAR import** | Import terrain data for contour generation and water flow modeling | Planned |
| X4 | **Community design sharing** | Export/import complete designs with a shared online library | Planned |
| X5 | **Sensor integration** | Connect soil moisture / temperature sensors for real-time data overlay | Planned |

---

## Already Implemented

| Feature | Status |
|---------|--------|
| Interactive Leaflet map (street + satellite) | Done |
| Property boundary drawing | Done |
| 433-plant Alberta master database (Zone 2–7) | Done |
| Plant canopy circle visualization | Done |
| Plant community system (8 communities + variations) | Done |
| Community canopy circle visualization | Done |
| Visual offset editor for plant community members | Done |
| Planting calendar | Done |
| Snap-to-grid | Done |
| Measurement tool | Done |
| Annotations / notes | Done |
| Labels toggle | Done |
| Canopy preview overlay | Done |
| Plant filters (Native AB, Edible, Medicinal, N-Fixer, Pollinator, Perennial, Keystone, Host Plant, Bird Food) | Done |
| Plant count badges and right-click context menu | Done |
| Plant community search, tooltips, double-click to place | Done |
| Built-in plant communities (18 — original 8 + 10 habitat-focused: Keystone Pollinator Mound, Caterpillar Host Garden, Songbird Berry Patch, Continuous Bloom, Native Edible, Aspen Parkland Edge, Mixedgrass Prairie, Boreal Woodland Floor, Late-Season Pollinator Refuge, Riparian Willow Thicket) | Done |
| Help → Check for Updates (git-pull fast-forward for source installs; releases-page link for .exe installs) | Done |
| Establishment Effort estimator (Year 1 vs Year 3+ split, native plants drop ~70% post-establishment) | Done |
| Establishment Water Budget (Year 1 vs Year 3+ split, native plants drop to ~20% baseline demand) | Done |
| Reference Ecosystem picker (filter plants by AB ecoregion: aspen parkland, mixedgrass prairie, fescue foothills, boreal mixedwood, riparian, wet meadow, subalpine/montane) | Done |
| Map legend (toggleable) | Done |
| Keyboard shortcuts (P/G/B/M/Z/N/L/Esc) | Done |
| Status bar seasonal tasks | Done |
| Project save/load (GeoJSON) | Done |
| Native plant order list export (grouped by AB nursery source) | Done |
| Undo/redo | Done |
| Permapeople API integration | Done |
| Structures library (placeable structures across 5 categories: Water, Habitat, Growing, Storage, Infrastructure) | Done |
| Hedgerow / fence line tool (4 styles, plant spacing, species) | Done |
| Custom shape drawing (7 presets, fill/stroke, labels, area calc) | Done |
| Sun path / shadow overlay (6 key dates, shadow arrows) | Done |
| Sector analysis (8 presets: sun, wind, frost, noise, views, fire) | Done |
| Slope / contour indicator (manual contour lines, elevation labels, slope arrows) | Done |
| Wind sector & windbreak effect (16 directions, shelter zones 10× height) | Done |
| Maintenance / labour estimator (plants + structures, capacity check) | Done |
| Wildlife Forage calendar (bloom_period + fruit_period; expandable monthly tree; nectar-gap detection) | Done |
| Human Forage calendar (edible_parts gated; planting-calendar harvest months + fruit_period fallback) | Done |
| Habitat Value Score (composite 0–100; tips suggest concrete plants/structures for low-scoring categories) | Done |
| Alberta rainfall climate-normal fallback (Open-Meteo live → bundled AB station normals when offline) | Done |
| Water budget calculator (demand vs rainfall + catchment) | Done |
| Print / PDF export (map screenshot, plant list, notes, title block) | Done |
| Design notes / journal (per-project, timestamps, saved in GeoJSON) | Done |

---

## Sources & Inspiration

### Native habitat & ecological restoration
- [Doug Tallamy — Homegrown National Park](https://homegrownnationalpark.org/) — Lawn-to-habitat movement; keystone-species & host-plant concepts
- [Xerces Society](https://xerces.org/) — Pollinator conservation and habitat design
- [Audubon Native Plants Database](https://www.audubon.org/native-plants) — Plants that support local birds and ecosystems
- [ALCLA Native Plants](https://alclanativeplants.com/) — Alberta-focused native nursery and resources
- [Bow Valley Habitat Development](https://bowvalleyhabitat.com/) — Alberta riparian and grassland restoration
- [Pollinator Partnership Canada](https://pollinator.ca/) — Regional pollinator planting guides

### Site analysis & sun mapping
- [Shadowmap.org](https://shadowmap.org/) — Sun path visualization
- [ShadeMap.app](https://shademap.app/) — Shadow simulation
