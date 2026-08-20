# Codebase Map — full module inventory

One line per module, taken from each module's own docstring (regenerate by
re-reading the docstrings — this file goes stale silently as modules are
added; trust the source over this list).


## App shell & controllers

| Module | One line |
|---|---|
| `main.py` | Site & Pattern entry point |
| `src/app.py` | Main application window for Site & Pattern |
| `src/toolbar.py` | Top toolbars for drawing tools, view layout, and project actions |
| `src/ui_style.py` | shared Qt stylesheet snippets so panels look consistent |
| `src/collapsible_panel.py` | Reusable header-with-chevron panel widget |
| `src/fill_tab_widget.py` | a QTabWidget whose tabs stretch to fill the full strip |
| `src/filter_widgets.py` | Shared search/filter widgets for the side-panel browsers |
| `src/branding.py` | the app's display identity (V1.69 rebrand) |
| `src/settings.py` | Persistent configuration storage |
| `src/preferences_dialog.py` | Map settings dialog for optional API tokens |
| `src/user_paths.py` | the single source of truth for the per-user data directory (incl. the PermaDesign→Site & Pattern rename migration) |
| `src/resources.py` | locate bundled, read-only data files in both source checkouts and frozen builds |
| `src/app_version.py` | what version the running build identifies as |
| `src/controllers/__init__.py` | src/controllers/ — Per-concern controllers extracted from MainWindow |
| `src/controllers/map_events.py` | MapBridge → MainWindow event router |
| `src/controllers/persistence.py` | Save / autosave / undo-stack controller |
| `src/controllers/mode.py` | Drawing-mode controller |
| `src/controllers/generation.py` | one-click "Generate Design" controller |
| `src/controllers/area_fill_controller.py` | place a polygon fill (N3′) |
| `src/controllers/update_flow.py` | Help menu + Check-for-Updates controller |
| `src/controllers/undo_support.py` | the @undoable decorator (V1.81) |

## Project state & errors

| Module | One line |
|---|---|
| `src/project.py` | Save/load Site & Pattern projects as GeoJSON (Step 4 implementation) |
| `src/project_store.py` | single write path for placed-plant state (V1.62) |
| `src/errors.py` | Typed exception hierarchy for the PermaDesign scripting API |

## DB layer

| Module | One line |
|---|---|
| `src/db/plants.py` | SQLite database access layer for the plant catalogue |
| `src/db/seed_data.py` | Plant catalogue seeding for Site & Pattern |
| `src/db/polycultures.py` | (no module docstring) |
| `src/db/recipes.py` | Polyculture Recipe persistence |
| `src/db/fauna.py` | Query API for the fauna registry and plant ↔ fauna junction |
| `src/db/nurseries.py` | Query API for the native-plant nursery directory (schema v44+) |
| `src/db/calendar_data.py` | Edmonton Zone 3b planting calendar seed data |
| `src/db/shade_zones.py` | Storage helper for the derived shade-tag cache (V1.53) |
| `src/db/structures.py` | Structure definitions for placeable landscape elements |
| `src/db/import_usda.py` | Import native-species data from the USDA PLANTS database CSV |

## Map frontend

| Module | One line |
|---|---|
| `src/map_widget.py` | QtWebEngine wrapper around the Leaflet map |
| `src/map_js.py` | Typed builders for every JS entry point in html/map.html |
| `src/member_colors.py` | marker colour tables for plant-community members |

## Side panels & Qt widgets

| Module | One line |
|---|---|
| `src/plant_panel.py` | Right-side panel: plant browser, search, filters, detail view, placement |
| `src/plant_list_view.py` | Model + delegate for the plant browser's virtualized |
| `src/on_this_design_panel.py` | The "On this design" review tab |
| `src/placement_controls.py` | Shared placement-controls widget used by the Plants tab and the Plant |
| `src/polyculture_panel.py` | (no module docstring) |
| `src/structure_panel.py` | Side-panel tab for browsing and placing structures, hedgerows, and shapes |
| `src/site_panel.py` | Side-panel tab for the property pin and auto-filled site data |
| `src/analysis_panel.py` | Side-panel tab for site analysis overlays |
| `src/planning_panel.py` | Side-panel tab for planning and analysis features |
| `src/wind_rose_widget.py` | a small QPainter wind-rose (V1.67) |
| `src/phenology_widget.py` | the "what's happening now" dashboard UI (F51) |
| `src/learn_panel.py` | the Learn side tab: Field Study / Lessons / Present (V2.25) |
| `src/docent_widget.py` | the docent / presentation-mode UI (F52) |
| `src/field_study_widget.py` | the Field Study quiz runner UI (F48) |
| `src/lesson_track_widget.py` | the guided lesson-track stepper UI (F53) |

## Generation & placement scoring

| Module | One line |
|---|---|
| `src/design_api.py` | Programmatic interface for generating landscape designs |
| `src/llm_design.py` | Prompt-driven design generation via a local LLM |
| `src/design_critic.py` | evaluate-and-repair intelligence for Generate Design |
| `src/placement_score.py` | Ecological cell-scoring for design generation (V1.51) |
| `src/layout.py` | Plant-group layout patterns for the design generator (V1.50) |
| `src/exclusion.py` | Keep-out zones for the design generator (V1.50) |
| `src/area_fill.py` | fill a drawn polygon with plants (N3′) |
| `src/zoning.py` | Derive wet / dry / shaded micro-zones for a property (V1.48) |
| `src/design_goals.py` | Registry mapping user-facing "design goals" to the |
| `src/planting_spacing.py` | layer/type-aware, spread-aware planting spacing (F22 / F35) |
| `src/sourcing.py` | cost / sourcing helpers for generated designs (V1.45) |
| `src/polyculture.py` | interplanting helpers |
| `src/pattern_language.py` | communities as Christopher Alexander patterns (F4) |
| `src/succession.py` | ecological-succession helpers for the growth timeline (N5) |
| `src/lawn_zones.py` | lawn-to-habitat conversion zones (N2) |
| `src/conversion_plan.py` | the year-by-year lawn → habitat conversion schedule (F17) |
| `src/generate_design_dialog.py` | the "Generate Design" dialog |
| `src/generate_worker.py` | background worker for one-click design generation |
| `src/design_review_flow.py` | On This Design ↔ map/tab cross-link glue (V2.13) |

## Ecology & analysis cores

| Module | One line |
|---|---|
| `src/habitat_score.py` | Qt-free Habitat Value Score computation |
| `src/ecological_role.py` | "why it matters" ecological-role badges for a plant (F1) |
| `src/plant_impact.py` | "pull-a-plant" impact simulator (F46) |
| `src/chickadee_scenario.py` | "feed a chickadee brood" provisioning scenario (F47) |
| `src/phenology.py` | the "what's happening now" phenology dashboard (F51) |
| `src/forage_calendar.py` | whole-design bloom succession + pollinator forage-gap |
| `src/lesson_track.py` | the guided lesson track (F53) |
| `src/field_study.py` | the Field Study quiz layer (F48) |
| `src/docent.py` | the docent / presentation-mode script (F52) |
| `src/bee_habitat.py` | "Design for a bee": turn the native-bee data spine into |
| `src/lep_habitat.py` | "Fly as a butterfly": turn the Alberta Lepidoptera data spine |
| `src/creature_community.py` | "Design a community for a creature": assemble a plant |
| `src/reference_ecosystem.py` | the walkable reference-ecosystem library (F50) |
| `src/reference_ecosystem_window.py` | the walkable reference-ecosystem window (F50) |
| `src/snapshot_timeline.py` | the Year 1 / 5 / 15 / 30 growth snapshots (F2) |
| `src/snapshot_window.py` | the "Growth Snapshots" window (F2) |
| `src/planting_plan.py` | the design → buy-it-and-plant-it handoff (F40) |
| `src/field_notes.py` | site-walk field notes (F6) |
| `src/data_quality.py` | Schema validation for the shipped plant JSON files |
| `src/plant_conditions.py` | helpers for multi-value plant condition fields (V1.84) |

## Terrain / sun / water / wind / snow / soil / climate

| Module | One line |
|---|---|
| `src/terrain.py` | Auto-generate slope contour lines and slope-ramp overlays |
| `src/hrdem.py` | NRCan HRDEM (High Resolution Digital Elevation Model) elevation |
| `src/terrain_shade.py` | DEM horizon ray-march for terrain self-shadowing (V1.55) |
| `src/terrain_store.py` | SQLite-backed store for offline terrain data |
| `src/terrain_downloader.py` | QThread worker that bulk-downloads the full |
| `src/solar.py` | Solar position calculations for sun path overlay |
| `src/shade.py` | Cast-shade estimation for the design grid (V1.48; polygon V1.53) |
| `src/shadow_geometry.py` | Footprint-polygon shadow casting (V1.53) |
| `src/hydrology.py` | Where the water actually goes: D8 flow routing + accumulation |
| `src/water_flow.py` | map-side glue for the water flow & accumulation overlay (V2.13) |
| `src/precip_split.py` | separate precipitation by *when its water is available* |
| `src/wind.py` | seasonal wind rose + live current wind from Open-Meteo (V1.67) |
| `src/wind_flow.py` | orchestration for fetching site wind data (V1.67) |
| `src/wind_shadow.py` | porosity-aware shelterbelt (wind shadow) geometry (V1.68) |
| `src/wind_shadow_flow.py` | orchestration for the live wind-shadow overlay (V1.68) |
| `src/snow.py` | winter snow cover & survival metrics (the *insulation* function) |
| `src/snow_microsite.py` | where snow drifts and lingers (the *spatial* snow lever) |
| `src/snow_microsite_flow.py` | map-side wiring for the snow-catch overlay (Step 3) |
| `src/soil_grid.py` | offline soil sampling from the Gridded Soil Landscapes of |
| `src/soil_downloader.py` | one-time download of the offline soil pack (V1.67) |
| `src/soil_flow.py` | orchestration for the one-time soil-pack download (V1.67) |
| `src/climate.py` | Hardiness zone lookup + growing-degree-day stats |
| `src/ecoregion.py` | Point-in-polygon lookup of Alberta ecoregions (V1.36) |
| `src/property_data.py` | Auto-fill site data for a property pin |

## Buildings / OSM / shared plumbing

| Module | One line |
|---|---|
| `src/osm_features.py` | Import existing trees & buildings from OpenStreetMap (V1.51) |
| `src/building_store.py` | SQLite-backed offline store for building footprints (V1.66) |
| `src/building_downloader.py` | bulk-download a region's building footprints into the |
| `src/building_flow.py` | orchestration for the offline building pack (V1.66) |
| `src/tile_store.py` | Shared primitives for the offline SQLite tile packs |
| `src/http_utils.py` | Shared stdlib JSON-over-HTTP helper |
| `src/ssl_bootstrap.py` | point Python's SSL stack at a usable CA bundle |
| `src/image_cache.py` | local cache + resolver for flora/fauna photos (I1) |
| `src/geometry.py` | Shared 2-D geometry helpers (Qt-free, no external deps) |
| `src/projection.py` | Lat/lng ↔ local-metre projection with a UTM upgrade path |

## 3D & scene

| Module | One line |
|---|---|
| `src/scene_contract.py` | the versioned Scene JSON contract (V1.62) |
| `src/scene3d.py` | shared placement/timeline state for the 2D map and a future |
| `src/scene3d_window.py` | the "3D Preview" window (V1.62) |
| `src/map3d_widget.py` | Map3DWidget, the embedded 3D viewport |
| `src/map3d_js.py` | Python→JS builders for the embedded map3d 3D view (V1.56) |
| `src/scene_wildlife.py` | populate a 3D scene with the animals the design's plants |
| `src/sprite_gallery.py` | specimen scenes for the 3D sprite gallery (V1.93–94) |
| `src/sprite_gallery_window.py` | the in-app 3D Sprite Gallery (V1.94) |
| `src/splat_backdrop.py` | georeferenced 3D Gaussian-splat backdrop (V1.65) |
| `src/splat_flow.py` | map-side wiring for the Gaussian-splat backdrop (V1.65) |
| `src/web_assets.py` | a localhost HTTP server for the built-in 3D viewer (V1.77) |

## Import pipelines & export

| Module | One line |
|---|---|
| `src/scan_import.py` | phone-scan (point cloud) import → nDSM → footprints |
| `src/scan_import_dialog.py` | the "Import Yard Scan…" flow (V1.63) |
| `src/footprint_extract.py` | Pluggable 2D footprint extraction from raster tiles |
| `src/footprint_ndsm.py` | nDSM height-raster → footprint polygons + heights |
| `src/site_photo.py` | site/drone photo map underlay (F24) |
| `src/site_photo_flow.py` | map-side wiring for the site photo overlay (F24) |
| `src/pdf_export.py` | Export the current design as a presentation-quality PDF |

## Agent / scripting / release

| Module | One line |
|---|---|
| `src/permadesign_api.py` | Public, Qt-free scripting facade for PermaDesign |
| `src/cli.py` | Command-line interface for Site & Pattern's headless operations |
| `src/mcp_server.py` | Model Context Protocol server exposing PermaDesign to |
| `src/version_branch.py` | Helpers for the V<major>.<minor> release-branch |
| `src/github_releases.py` | GitHub Releases lookup for the in-app updater |
