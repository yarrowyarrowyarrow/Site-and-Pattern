# PermaDesign — Native Habitat Feature Brainstorm

## Context

The early pivot (branding + taxonomy + structures swap) and the entire **Tier-0
reframe set** have shipped — the app no longer just *reads* as a Native Habitat
Designer, it scores and plans like one. Most of the original Tier-1 work landed
too. What remains splits three ways:

- **finishing started work** — the succession timeline and the polygon/zone
  drawing ideas were only partly built;
- **the next functional layer** — whole-design costing, group editing, and an
  Alberta-community preset library, most of which *extend* infrastructure that
  already exists rather than starting from scratch;
- **two larger bets** — a synchronized **3-D viewport** and a **flora/fauna image
  library**.

This document is the working backlog. The first section is an honest ledger of
what's already done so we stop re-proposing shipped features; everything after it
is the live list, grouped by effort tier, each item annotated with the code it
leans on.

---

## Status ledger — where the original brainstorm landed

| ID | Item | Status | Proof / where it lives |
|----|------|--------|------------------------|
| R1 | Bloom & Berry Calendar | ✅ Shipped | `planning_panel.py` "Wildlife Forage" tab — bloom vs. fruit split, nectar-gap warning |
| R2 | Habitat Value Score | ✅ Shipped | `analysis_panel.py` + `habitat_score.py` — 0–100, 7 weighted components |
| R3 | Native Plant Order List | ✅ Shipped | `app.py:_on_export_shopping_list()` — grouped by AB nursery, form column, footer links |
| R4 | Establishment Effort (Yr 1 vs Yr 3+) | ✅ Shipped | `planning_panel.py` "Effort" tab |
| R5 | Establishment Water Budget (Yr 1 vs Yr 3+) | ✅ Shipped | `planning_panel.py` "Water" tab |
| N1 | Reference ecosystem picker | ✅ Shipped (+) | `plant_panel.py` + `ecoregion.py`; `ab_ecoregion` on 100% of plants; **plus** auto-detect from lat/lng |
| N4 | Pollinator & bird species supported | ✅ Shipped (≠ plan) | Built on the `fauna`/`plant_fauna` DB junction (`db/fauna.py`) — richer than the planned flat JSON fields |
| N5 | Ecological succession | ◐ Partial | Year 0–20 timeline slider exists (`planning_panel.py` timeline tab + `controllers/map_events.py`), but **not** reframed to restoration stages; `early_successional` tag unused; no `climax` flag → see N5 below |
| N2 | Lawn conversion zones | ⬜ Not started | → carried forward below |
| N3 | Native seed-mix broadcast zones | ⬜ Not started | → reframed & carried forward as **N3′** below |
| L1 | "Convert my lawn" wizard | ⛔ Shelved | "no new wizards" — see Parked |
| L2 | Habitat corridor analysis | ⛔ Parked | not this round |
| L3 | Soil / disturbance overlay | ⛔ Parked | not this round |
| L4 | Crop rotation / input-output mapping | ✂ Dropped | permaculture-era, out of scope |

**Data enrichment recap:** `ab_ecoregion` is 100% populated and powers N1. The
planned `pollinator_specialists` / `bird_value` JSON fields were *not* added —
the fauna DB junction covers N4's purpose instead. `establishment_difficulty`
was never added; R4 uses plant-type heuristics.

---

## Active backlog

### Tier 0 — UX polish (low effort, immediate quality-of-life)

#### U1. Planning sub-tabs: all visible, none hidden — ✅ Done (V1.60)
- **Was:** the six Planning sub-tabs overflowed into a scroll chevron, hiding
  *Notes* until you clicked the arrow.
- **Fix:** `_FillTabBar` (`fill_tab_widget.py`) now **shrinks tabs to an equal
  share when crowded** — it previously only ever widened, which is why a scroll
  chevron appeared. The Planning bar (`planning_panel.py:_build_ui`) sets
  `setUsesScrollButtons(False)` + `setExpanding(True)` + `ElideRight`, and the
  two wide labels were shortened (Wildlife Forage → "Wildlife", Human Forage →
  "Harvest"). Verified offscreen: all six tabs visible across the full
  260–480 px side-panel range (≈44 px each at the 260 px minimum, filling the
  strip at 480 px). The shrink behaviour also benefits the Analysis/Site/outer
  tab strips, which previously could overflow too.

#### U2. Sub-tab description text uses the full panel width — ✅ Done (V1.60)
- **Root cause (corrected from the plan's guess):** the description `QLabel`s
  contained **hard-coded `\n` line breaks**, which forced narrow wrapping no
  matter how wide the panel was — not a `sizePolicy` cap.
- **Fix:** stripped the embedded `\n` from the info labels in the Site,
  Structures, Analysis and Planning panels so `setWordWrap(True)` reflows them to
  the full available width. Intentional `\n\n` paragraph breaks and structural /
  table readouts (sun-path breakdown, shade mix) were left untouched.

### Tier 1 — habitat & design features (medium effort)

#### N2. Lawn conversion zones — ✅ Done (V1.60)
- **Reused the shape pipeline (no new JS):** a conversion zone is a drawn
  `custom_shape` whose `shape_type` is one of five zone labels, so zones get
  drawing / colour / area / save-load for free.
- **New pure core** `src/lawn_zones.py`: the zone catalogue (`lawn_remaining`,
  `restoration_year_1`, `restoration_year_3`, `established_native`,
  `existing_remnant` — label + fill/stroke/opacity + stage), `conversion_summary`
  (m² per zone → converted / lawn-remaining / remnant / % converted) and a
  compact formatter. One source of truth shared by the drawer and the readout.
- **Drawer:** the Structures → Shapes preset list now offers the five zones
  (`structure_panel.py`), styled from `ZONE_TYPES`.
- **Readouts:** a running "converted so far / lawn left" status-bar message when
  a zone is drawn (`map_events._on_shape_complete`), and a **Lawn conversion**
  block in the "On this design" → Stats tab fed from `_sync_planning_panel`.
- **Verified:** 7 `test_lawn_zones` cases (tally, %, non-zone exclusion,
  formatting); offscreen checks that the drawer carries the zone presets and the
  panel renders the conversion block.
- **Year-by-year:** the zone *stage* (Year 1 / Year 3 / established) is the
  breakdown; the percentage tracks "converted ÷ (lawn + restoration)".

#### N3′. Polygon-fill placement — single species *or* a community/mix — ✅ Done (V1.60)
- **Reused the verified shape-drawing flow (no new draw-mode JS):** you draw a
  shape (Structures → Shapes), then select a community and click **Fill Area** in
  the Plant Communities panel — the fill targets your most recently drawn shape.
- **New pure core** `src/area_fill.py` (fully unit-tested): `fill_points`
  (interior hex-offset grid at a metre spacing via `geometry.point_in_polygon`),
  `assign_members` (largest-remainder allocation by cover weight + round-robin so
  species are spatially intermixed), and `plan_fill`.
- **New `AreaFillController`** places the result through the *same* dual-store
  bookkeeping the design generator uses (markers + project features + one shared
  placement group, tagged `pattern_kind="area_fill"`) — so rendering, undo-as-a-
  unit, the habitat score and the cost readout all just work.
- **Wiring:** `polyculture_panel` gains a Fill Area button + `fillAreaRequested`
  signal; `app._on_fill_area_with_community` resolves the target polygon + the
  community's members and invokes the controller at the panel's cell spacing.
- **Verified:** 11 `test_area_fill` cases (geometry, proportional allocation,
  controller placement) + the app handler exercised end-to-end against a seeded
  DB (a drawn bed filled with a 6-member community → 64 plants across all 6
  species). The literal button-click (signal `.connect`) wasn't headless-tested.
- **Note:** mix weights are equal per member today (the polyculture schema has no
  cover %); `assign_members` already takes weights, so cover % drops in later.
  Single-species fill = a one-member spec. Markers render via the existing plant
  layer (no hatch fill — point markers, which is what the score/cost count).

#### N5. Finish Ecological Succession + extend the time horizon — ✅ Done (V1.60)
- **New pure core** `src/succession.py` (Qt-free, DB-free, fully unit-tested):
  restoration-stage labels, `successional_role`, `presence_factor`,
  `timeline_max_years`.
- **Reframed stages:** the timeline label now reads e.g. "Year 3 · Forb–grass
  matrix" / "Year 60 · Climax / canopy" instead of a bare year, via
  `succession.year_label` (`planning_panel.py`).
- **Flags used — fade in/out:** pioneers (`early_successional` tag, already on
  58 plants) fade *out* and climax species fade *in* as the design matures,
  rendered as a per-plant **presence opacity** sent to the map (backward-compatible
  3rd arg through `map_js` / `map_widget` / `html/map.html`).
  - **No schema bump needed:** roles read from the existing `permaculture_uses`
    blob; an explicit `climax` tag is honoured if present, and a **maturity
    heuristic** (long-lived woody species) covers climax until the dataset is
    enriched — so it works on today's data.
  - **Lifecycle-scaled fade:** the pioneer fade scales to the species' own
    maturity, so short-lived forbs fade within a few years while pioneer *trees*
    (lodgepole, aspen) persist for decades instead of vanishing at full canopy.
- **Extended horizon:** the slider now reaches the **slowest placed species'
  maturity** (clamped 20–60 yr) via `timeline_max_years`, refreshed whenever the
  design changes — verified extending to 60 yr for Lodgepole Pine.
- **Verified:** 18 `test_succession` cases + the timeline controller path
  exercised end-to-end against a seeded DB (stage text, presence, summary).

#### C1. Whole-design cost *(extend, not new)* — ✅ Done (V1.60)
- **Built on:** `sourcing.py`'s existing `plant_price_range` / `estimate_cost` /
  `format_cost` and the 100%-priced plant data.
- **Added:**
  - `install_cost_cad` (low, high) on every structure (`db/structures.py`), with
    a catalogue-lookup fallback so older saved projects still cost correctly.
  - `structure_cost`, `mulch_cost` (area × depth × per-m³ range), and
    `design_cost` (plants + structures + mulch + total) in `sourcing.py`.
  - A full **Estimated cost** block in the "On this design" → Stats tab
    (`on_this_design_panel.py`), fed from `_sync_planning_panel`.
  - **Per-line cost, section subtotals, a SITE PREP & STRUCTURES section
    (structures + bed mulch), and an estimated grand total** in the order export
    (`app.py:_on_export_shopping_list`).
- **Verified:** 21 `test_sourcing` cases (incl. the new costing fns + every
  structure priced); panel cost block rendered offscreen; order export run
  end-to-end against a real seeded DB (plant subtotals, catalogue-resolved Pond
  install cost, 50 m² mulch, grand total).
- **Note:** mulch area = sum of drawn `custom_shape` beds; estimates carry the
  same "varies by nursery/year/site" disclaimer as plant pricing.

#### G1. Group select-and-move *(extend, not new)* — ✅ Done (V1.60)
- **Built on** the existing shift+drag marquee (`selectedItems[]`,
  `deleteSelected()`, Delete/Escape) which already covered plants / boundaries /
  sun-sectors with bulk delete.
- **Extended selection + bulk-delete to structures:** the marquee hit-test,
  highlight and delete now include placed structures (reusing the existing
  `onStructureRemoved` bridge call) — so you can box a corner and delete plants +
  boundaries + sectors + structures together.
- **Group drag-move (marquee):** dragging a plant that's part of a ≥2-plant
  selection now moves the **whole selected set** as a unit. Added a `selection`
  drag scope (`_scopesFor` / `_markersInScope`) and a new **group-agnostic**
  persistence path — `onSelectionMoved` → `MapEventRouter._on_selection_moved`,
  which matches features by `plant_id` + old-coords *without* a placement-group
  constraint (the existing `onPlantGroupMoved` only matches within one group, so
  it couldn't move a cross-group selection).
- **Verified:** new `test_map_events_drag.TestSelectionMove` proves a selection
  spanning two placement groups moves correctly and leaves non-selected plants
  put; the inline map JS passes `node --check`; the `test_map_js` presence test
  is green. **Needs in-app verification:** the interactive marquee/drag gestures
  themselves (selecting structures, dragging the selection) can't be exercised in
  a headless environment — the logic underneath is tested, the Leaflet gestures
  are not.
- **Deferred within G1:** group *move* for non-plant types (structures/shapes)
  and selecting hedgerows / OSM buildings / measurements — those carry their own
  per-type geometry + persistence and are better done with the app running.

#### P1. Alberta community presets — ✅ Done (V1.60)
- **Mostly already there:** the seeded polyculture library already held ~18 AB
  communities (Continuous Bloom Pollinator Strip, Tall Prairie Meadow, Native
  Berry Hedge, Aspen Parkland Edge, Mixedgrass Prairie Patch, …), placeable via
  the existing community picker — no wizard.
- **Added the missing brainstorm-named starters** to `EXAMPLE_POLYCULTURES`
  (`db/polycultures.py`): **Boulevard Pollinator Strip** (tough hellstrip),
  **Backyard Meadow Patch** (residential meadow) and **Hedgerow Shelterbelt**
  (layered windbreak with an overstory tree) — all members are confirmed native
  catalogue rows (the legacy food-forest presets reference since-dropped names).
- **Reseed:** bumped `_SCHEMA_VERSION` 22 → 23 so existing installs re-run the
  polyculture seed (already in the reseed wipe list) and pick the starters up.
- **Verified:** new `test_polycultures.TestStarterCommunities` confirms all three
  seed with all six members resolved (guards against future name drift).
- **Fill-mode note:** "drop via N3′ fill" depends on N3′; until then they place
  through the existing point-based community placement.

#### P2. Printable planting plan — ✅ Done (V1.60)
- **Was already there:** `pdf_export.py` rendered a title + map snapshot, a plant
  list, and a notes page via QPrinter/QPainter (no external PDF lib).
- **Added (the brainstorm's missing pieces):** the **Habitat Value Score**
  (total + grade + native % / keystone / layer counts) and the **whole-design
  cost** (C1) now appear in the page-1 summary, and the plant-list page carries
  the **Alberta nursery sources** footer — so the one document now covers map +
  plant list + order sourcing + score + cost.
- **Verified:** `test_pdf_export` (guarded) renders a non-trivial `%PDF-` file
  for a seeded design and handles the empty-design case without raising; run
  end-to-end offscreen (27 KB PDF, score + cost present).

### Tier 2 — larger / longer-horizon

#### D1. 3-D viewport (synchronized with the 2-D canvas) — ◐ Foundation done (V1.60)
A bird's-eye + eye-level 3-D view that grows plants over time and casts
sun-accurate shadows. **Recommendation and refactor notes in the dedicated
section below.** This round delivers the **testable, low-risk foundation** the
brainstorm flagged as the real cost — not the live render (that needs the built
map3d fork + a browser):
- **Shared state — `src/scene3d.py`** (pure, Qt-free, fully tested): the single
  source of truth for "how big / how present is each plant at year N" —
  `growth_scale_factor` (matches the 2D timeline *exactly*; a parity test proves
  it), `plant_3d_state` (lat/lng + height/canopy scaled to the year +
  scale_factor + succession presence opacity), and `placed_plants_3d_state`.
  The 2D timeline controller was refactored to call `growth_scale_factor`, so the
  two views can never drift on the growth curve.
- **`src/map3d_js.set_plants`** — a guarded `window.permaSetPlants(...)` builder
  alongside the existing `set_sun` (tested).
- **`src/map3d_widget.Map3DWidget`** — a `QWebEngineView` scaffold mirroring
  `MapWidget`: loads `web3d/dist/` when the fork is built, else a placeholder;
  `set_sun_for` + `set_scene` drive the scene via `map3d_js` + `scene3d`.
- **Verified:** 11 `test_scene3d` (incl. exact-parity with the old 2D formula) +
  the `set_plants` builder; live 2D timeline re-checked (identical factors).
  **Not verified here:** `Map3DWidget` construction (QtWebEngine can't init in a
  headless container — same as `test_app_smoke`; runs under a display) and the
  actual 3-D rendering (needs the built map3d fork — npm build of the external
  repo + the sun-shadow patch).
- **Deliberately NOT mounted** in the main window yet — there's no built scene to
  show, and an empty "3D" tab would confuse users. Mounting is the next D1 step
  once the fork is built.

#### I1. Flora & fauna image library — ✅ Infrastructure done (V1.60)
- **Schema (v24):** added `image_url` / `image_attribution` / `image_license` to
  **plants and fauna** (`schema.sql` + `_migrate_to_v24` ALTERs existing installs;
  `_SCHEMA_VERSION` 23 → 24). The seed pipeline reads the three fields from the
  master JSON, so the dataset workflow just adds them per record.
- **Cache/resolver** `src/image_cache.py` (Qt-free, stdlib `urllib`, graceful
  degradation like `climate.py`): `get_cached_image` (cache-only, never blocks),
  `fetch_and_cache_image` / `resolve_image` (fetch once, store under the user-data
  dir with the attribution + license in a JSON sidecar). Local file paths resolve
  directly.
- **Plant detail UI:** the expanded plant row now shows the cached photo + its
  attribution above the detail rows (`plant_list_view.py`), **gated on a cached
  image** so it's completely inert until images exist (zero change to today's
  rows). A one-time **background fetch** (`QThreadPool`) warms the photo when a
  row is expanded and repaints it.
- **Verified:** 6 `test_image_cache` cases — incl. the fetch+cache+attribution
  path exercised offline via a `file://` URL — plus a schema test (both tables
  carry the columns; `get_plant` exposes them). Panel/model construct offscreen;
  128 DB-seeding tests green at v24.
- **Still the dataset workflow's job** (per the brief): sourcing the actual
  openly-licensed photos (Wikimedia/iNaturalist, CC0/CC-BY/PD) with citations —
  the app side is ready for them. Fauna images: columns + cache are in place; a
  fauna-picker thumbnail is the small remaining UI follow-up.
- **Licensing reality (unchanged):** book scans are copyrighted; every image
  needs an open license recorded with its citation — the schema now enforces a
  place for it.

#### D2. Generate Design improvements — ◐ First slice done (V1.60)
- **Shipped — community-aware offline placement:** the no-LLM path used to drop a
  single default community onto a flat species list. It now selects **2–3
  site/goal-fit seeded communities** as grouped polycultures via the new
  `_select_offline_communities` (`llm_design.py`), scored by goal-name match
  (+2 each) and **ecoregion-name match** (+3, e.g. an `aspen_parkland` site
  surfaces "Aspen Parkland Edge"). The budget path was upgraded from
  all-or-nothing to dropping the priciest/lowest-ranked communities one at a time
  until the set fits.
- **Verified:** 7 pure `test_offline_communities` cases (goal/ecoregion scoring,
  caps, budget fallback) + an integration test (`test_llm_design`) confirming a
  pollinator design now places ≥2 distinct communities.
- **Still open (future):** spacing/competition rules and LLM-path prompt/quality
  tuning — the remaining D2 candidates, deferred.
- **Unchanged base** (for reference): LLM path via local Ollama
  (`generate_worker.py`, `generate_design_dialog.py`, `controllers/generation.py`),
  goal/site filtering, layout patterns, and site micro-zoning.

---

## Parked / shelved

- **L1 — "Convert my lawn" onboarding wizard.** Shelved by preference ("no new
  wizards"). The useful kernel — drop a starter community — is delivered instead
  as **P1 presets** + **N3′ fill mode**, no multi-step flow.
- **L2 — Habitat corridor analysis.** Connect to adjacent natural features with a
  connectivity overlay. Good idea, not this round.
- **L3 — Soil / site-disturbance overlay.** Zone the site by disturbance and
  recommend a prep method; pairs with N2/N3′. Revisit after the fill/zone tools
  land.
- **L4 — Crop-rotation tracker & input/output mapping.** Dropped — annual-food /
  permaculture-era concepts that don't fit a native-habitat designer.

---

## Data work that unlocks the above

- **`climax` flag** on plant records (+ keep using `early_successional`) — unlocks
  the N5 succession fade-in/out. Schema + seed change → version bump + reseed step.
- **Open-licensed imagery + attribution/license fields** — unlocks I1; the biggest
  single data lift here.
- **`install_cost_cad` on structures** (+ mulch/material price reference) —
  unlocks the non-plant half of C1.
- *(Optional)* `establishment_difficulty` (`easy/moderate/hard`) — would let R4
  stop inferring Year-1 effort from plant type.

These are tractable as enrichment passes against Audubon / Xerces / iNaturalist /
ALCLA references and belong in the separate local-AI dataset workflow.

---

## 3-D viewport — architecture recommendation

The supplied blueprint asks which of three paths fits: **(A)** embedded Three.js
via `QWebEngineView`, **(B)** Panda3D, or **(C)** ModernGL. The answer, grounded in
how this codebase is already built:

**Recommend Option A — embedded Three.js in a second `QWebEngineView`, driven over
QWebChannel** — for two concrete reasons:

1. **The app is already all-in on that exact stack.** The 2-D map is a
   `QWebEngineView` (`map_widget.py`) talking to a mature `MapBridge` QWebChannel
   (~50 slots, JSON payloads). A 3-D view reuses the same transport — no new IPC
   mechanism, no native window-pinning headaches (B), no from-scratch engine (C).
2. **Scaffolding already exists.** `web3d/` documents adopting the MIT
   **map3d** (React + React-Three-Fiber) viewer and ships
   `map3d-sun-shadows.patch`, and `src/map3d_js.py` already builds the JS to drive
   its sun (`set_sun_for(lat, lng, when)`), reusing `src/solar.py`. By
   construction the 3-D shadows track the same solar positions as the 2-D shade
   engine (`shade.py` / `terrain_shade.py`).
   - **Honest caveat:** this is *scaffolding + a patch*, not a running feature —
     there is **no `Map3DWidget` mounted and no built `dist/` loaded** yet.

Panda3D and ModernGL both throw away the QWebChannel investment; ModernGL also
means writing shaders, a model loader, and camera math by hand. Reject both for
this codebase.

**The real cost is state, not rendering.** Placement is **lat/lon-only** today,
and plant size is *derived at render time* from the `plants` table
(`growth_curve`, `years_to_maturity`, `mature_height_*`, `mature_canopy_m`) — there
is no single source of truth a second view can subscribe to. The key refactor is
to **extract a shared placement/timeline state object** that both the 2-D Leaflet
markers and the 3-D scene read from, so the growth slider (N5) and a sun/time
control move both views in lockstep. *(Class names floated during exploration —
`PlacementStateStore`, `TimelineState` — are illustrative, not prescribed.)*

**Suggested staging:**
1. Mount the map3d fork as a second viewport with sun-driven shadows (reuses
   `map3d_js` + `solar`).
2. Extract the shared state object; pipe the N5 growth timeline into 3-D so plants
   scale with the year slider.
3. Real plant geometry / seasonal phenology / interactive 3-D placement.

---

## Verification (when an item here is built)

- **N5:** open a design with a slow tree (e.g. *Populus tremuloides*); confirm the
  slider extends past 20 yr and the tree keeps growing to maturity; confirm
  pioneers (`early_successional`) fade out and `climax` species fade in across
  stages.
- **N2:** draw lawn-remaining vs. restoration polygons; confirm the m²-converted
  readout updates and breaks down by year.
- **N3′:** fill a polygon with a community mix; confirm hatched render and that the
  R2 habitat score moves as if the plants were point-placed.
- **C1:** add mulch + a structure to a priced design; confirm the "On this design"
  breakdown and the exported order file both show line items, subtotals, and a
  grand total.
- **G1:** marquee-select a corner containing a plant, a structure, a building
  outline, and a measurement; confirm all are captured and move together, and that
  delete still removes the whole selection.
- **U1/U2:** open the Planning panel; confirm all six sub-tabs (incl. Notes) are
  visible without a scroll chevron, and that each sub-tab's description text
  reflows to the full panel width.
- **D1:** slide the time/season control; confirm 3-D shadows and the 2-D shade
  overlay agree, and that the growth year scales plants in both views.
