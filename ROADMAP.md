# PermaDesign — Feature Roadmap

A prioritized list of features requested by permaculture practitioners, drawn from community forums (Permies.com, Reddit r/Permaculture), existing tool reviews, and user feedback. Organized by effort/impact tiers.

---

## Tier 1 — Structures & Map Elements (Medium effort, high impact)

Placeable landscape elements beyond plants.

| ID | Feature | Description | Status |
|----|---------|-------------|--------|
| S1 | **Structures library** | Placeable icons/shapes for: pond, herb spiral, hugelkultur bed, swale, rain garden, compost bin, greenhouse, cold frame, chicken coop/tractor, shed, raised bed, keyhole bed, fire pit, beehive, rain barrel, fence/wall | Done |
| S2 | **Hedgerow / fence line tool** | Draw a polyline that renders as a hedge or fence with selectable plant species along it | Done |
| S3 | **Custom shape drawing** | Free-form polygon drawing for garden beds, pathways, patios — with fill color/pattern and labels | Done |

---

## Tier 2 — Analysis & Simulation (Medium-high effort, very high impact)

Tools that help designers understand their site.

| ID | Feature | Description | Status |
|----|---------|-------------|--------|
| A1 | **Sun path / shadow overlay** | Given lat/lng + date, draw the sun arc and show shadow direction arrows for morning/noon/evening — helps place shade-sensitive crops | Planned |
| A2 | **Sector analysis layer** | Draw directional wedges on the map for sun, prevailing wind, frost flow, noise, views — standard permaculture sector map | Planned |
| A3 | **Slope / contour indicator** | Manual or imported contour lines to show terrain; helps place swales and ponds correctly | Planned |
| A4 | **Wind sector & windbreak effect** | Mark prevailing wind direction; windbreak structures/hedges show a "shelter zone" behind them (10x their height) | Planned |

---

## Tier 3 — Planning & Data (Low-medium effort, high value)

Features for long-term planning and tracking.

| ID | Feature | Description | Status |
|----|---------|-------------|--------|
| P1 | **Succession / timeline planner** | A time slider showing how the design evolves: Year 1 (annuals), Year 3 (young shrubs), Year 10 (full canopy). Plants grow/appear based on their mature size over time | Planned |
| P2 | **Maintenance / labor estimator** | Each element gets estimated hours/year. The app totals it up so you know if you're over-designing for your available time | Planned |
| P3 | **Harvest calendar** | Monthly view of what you'll be harvesting from placed plants — "August: Saskatoon berries, raspberries, chokecherries" | Planned |
| P4 | **Crop rotation tracker** | For annual beds, track what was planted where each season to avoid repeating families | Planned |
| P5 | **Input/output mapping** | Tag elements with inputs (water, fertilizer) and outputs (manure, mulch, food). Highlight "energy leaks" where outputs aren't connected to nearby inputs | Planned |
| P6 | **Water budget calculator** | Estimate total water needs of placed plants vs. rainfall + any catchment (rain barrels, swales, pond) | Planned |

---

## Tier 4 — Visual & UX Enhancements (Low effort, nice polish)

| ID | Feature | Description | Status |
|----|---------|-------------|--------|
| V1 | **Food forest layer indicators** | Visual markers for the 7 food forest layers (canopy, understory, shrub, herbaceous, groundcover, vine, root) with layer toggle | Planned |
| V2 | **Season view toggle** | Switch map appearance between spring/summer/fall/winter to see deciduous vs. evergreen coverage | Planned |
| V3 | **Print / PDF export** | Export the current map view as a presentation-quality PDF with legend, title block, and plant list | Planned |
| V4 | **Design notes / journal** | Per-project text area for recording observations, soil test results, and design rationale | Planned |
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
| Zone circles (Zone 0–4) | Done |
| 118-plant Edmonton Zone 3-4 database | Done |
| Plant canopy circle visualization | Done |
| Guild system (8 guilds + variations) | Done |
| Guild canopy circle visualization | Done |
| Visual offset editor for guild members | Done |
| Planting calendar | Done |
| Snap-to-grid | Done |
| Measurement tool | Done |
| Annotations / notes | Done |
| Labels toggle | Done |
| Canopy preview overlay | Done |
| Plant filters (Native AB, Edible, Medicinal, N-Fixer, Pollinator, Perennial) | Done |
| Plant count badges and right-click context menu | Done |
| Guild search, tooltips, double-click to place | Done |
| Map legend (toggleable) | Done |
| Keyboard shortcuts (P/G/B/M/Z/N/L/Esc) | Done |
| Status bar seasonal tasks | Done |
| Project save/load (GeoJSON) | Done |
| Shopping list export | Done |
| Undo/redo | Done |
| Permapeople API integration | Done |
| Structures library (16 placeable structures across 5 categories) | Done |
| Hedgerow / fence line tool (4 styles, plant spacing, species) | Done |
| Custom shape drawing (7 presets, fill/stroke, labels, area calc) | Done |

---

## Sources & Inspiration

- [Permies: All-in-One Permaculture Design App](https://permies.com/w/240148/Permaculture-Design-App)
- [Permies: Permaculture Design Software](https://permies.com/t/7924/permaculture/Permaculture-Design-Software)
- [Permies: Digital Permaculture Design Tools](https://permies.com/t/157765/permaculture/digital-permaculutre-design-tools)
- [EcoDesignHive: Landscape Design Apps for Permaculture](https://www.ecodesignhive.com/landscape-design-apps/)
- [Permaculture Apprentice: 7 Smartphone Apps](https://permacultureapprentice.com/permaculture-apps/)
- [Permaculture Practice: Sector Planning](https://permaculturepractice.com/permaculture-sector-planning/)
- [Permalogica: Sector Analysis and Mapping](https://www.permalogica.com/post/permaculture-design-by-sectors-permaculture-sector-analysis-and-mapping)
- [NC State: Appendix G Permaculture Design](https://content.ces.ncsu.edu/extension-gardener-handbook/appendix-g-permaculture-design)
- [Tenth Acre Farm: 6 Maps for Permaculture Site Design](https://www.tenthacrefarm.com/6-maps-permaculture-farm-design/)
- [Verge Permaculture: How to Design a Food Forest](https://vergepermaculture.ca/how-to-design-a-permaculture-food-forest/)
- [Shadowmap.org](https://shadowmap.org/) — Sun path visualization
- [ShadeMap.app](https://shademap.app/) — Shadow simulation
- [Software Tools for Professional Permaculture Design](https://tiag.substack.com/p/software-tools-for-professional-permaculture)
