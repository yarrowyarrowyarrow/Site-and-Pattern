# Site & Pattern — Philosophy-Driven Feature Roadmap

A catalogue of what the design philosophy ([`DESIGN_PHILOSOPHY.md`](DESIGN_PHILOSOPHY.md))
makes *possible*, grounded in what the codebase already does — and **ranked by impact** so
the next move can be chosen deliberately. Each entry states **Impact / Effort / Risk**,
the principle(s) it serves, and a concrete **how I'd build it** (the actual functions and
files it would lean on).

**Relationship to the other backlogs.** [`archive/FEATURE_BRAINSTORM.md`](archive/FEATURE_BRAINSTORM.md)
is the engineering backlog (what's shipped, effort-tiered); [`../ROADMAP.md`](../ROADMAP.md)
is the feature ledger. This is the *philosophical* lens over both, and is meant to be
amended alongside them. Feature IDs (F1, F2, …) are stable handles — say "let's do F5".

**Rating legend.**
- **Impact** — overall value (philosophical alignment × user value × conservation outcome):
  **High / Med / Low**.
- **Effort** — **S** (hours–a day), **M** (a few days), **L** (a week+ / multi-step),
  **XL** (a foundational program of work).
- **Risk** — chance of breakage / scope-creep / hard dependencies: **Low / Med / High**.
  Common risk flags: *schema bump* (`_SCHEMA_VERSION` + reseed, see `CLAUDE.md`),
  *guard ceiling* (a file near a `tests/test_architecture_guard.py` line limit — esp.
  `plant_panel.py` and the `html/map/*.js` files), *new UI surface*, *external data*.

---

## The funnel lens — ranking for *ecosystems created*

The ratings above weigh philosophical alignment × user value × conservation outcome. But the
ultimate goal is **more native ecosystems actually in the ground**, and that is gated by an
adoption funnel: a person has to *get started* (activation), *build a design*, *trust it enough
to act* (confidence), and then *actually buy and plant it* (action). Sorting F1–F39 by the funnel
stage each primarily serves is sobering:

| Funnel stage | # of features | Verdict |
|---|---|---|
| DESIGN (build/improve the design) | 18 | overweight |
| LEGIBILITY / EDUCATE (make ecology visible) | 13 | overweight |
| DECIDE / CONFIDENCE (trust it enough to act) | 7 | moderate |
| **ACT / OUTPUT (design → plants in the ground)** | **5** | **critical deficit** |
| **ONBOARD / ACTIVATE (cold start → first design)** | **1** | **severe deficit** |
| MAINTAIN (after planting) | 2 | minor |

The roadmap is a superb toolkit for an *already-engaged* user, and comparatively silent on the
two stages that actually move the conservation needle. Encouragingly, those two stages map onto
the philosophy's own **under-served principles** — P8 (repair/conversion), P9 (uncertainty/
confidence), P11 (the body & the site). Serving them is not a departure from the philosophy; it
strengthens its weakest spots. So the working rule for what comes next:

> **Lead with ACTION and ACTIVATION; keep (but defer) the DEPTH.** Optimize the funnel for the
> novice lawn-to-habitat converter — the long tail of yards where conversions create the most
> ecosystems — without losing the depth features that reward users who go further.

The new entries below (**F40–F45**) fill the ACT/OUTPUT and ONBOARD gaps; the **Defer** tier
parks the high-effort power-user-depth items until activation/action prove out.

---

## Shipped since this roadmap was written

These started life as entries below and have since landed — the State markers in
[`DESIGN_PHILOSOPHY.md`](DESIGN_PHILOSOPHY.md) reflect the lift. The detail entries are kept
(marked **✅ Shipped**) as the historical record of how they were built.

| ID | Feature | Lives in | Advances |
|----|---------|----------|----------|
| F1 | "Why it matters" ecological-role labels in the plant browser | `src/ecological_role.py`, surfaced in `src/plant_list_view.py` | P6, P10 |
| F2 | Year 1 / 5 / 15 / 30 snapshot view | `src/snapshot_timeline.py`, `src/snapshot_window.py` | P4 |
| F3 | Food-web completeness score | `src/habitat_score.py` (`food_web`), `src/design_critic.py` | P3, P6 |
| F4 | Pattern-language framing for communities | `src/pattern_language.py`, `src/polyculture_panel.py` | P1, P7 |
| F6 | Site-walk field notes | `src/field_notes.py`, surfaced in `src/site_panel.py` (Field Notes tab) | P11 |
| F9 | Specialist-host spotlight | `src/habitat_score.py` + `src/db/fauna.py` specificity | P3, P6 |
| F10 | Lawn-equivalent counterfactual | `src/lawn_zones.py` (`lawn_counterfactual`), surfaced in `src/analysis_panel.py` | P6, P8 |
| F16 | Seasonal view toggle | `src/analysis_panel.py`, `src/map_js.py`, `src/scene_contract.py` | P4, P5 |
| F17 | Phased conversion plan (year-by-year) | `src/conversion_plan.py`, surfaced in `src/planning_panel.py` + `src/app.py` + `src/pdf_export.py` | P8, P4 |
| F22 / F35 | Naturalistic drift placement + spread-aware spacing | `src/layout.py`, `src/planting_spacing.py` | P1, P2, P4 |
| F24 | Site photo overlay + markup | `src/site_photo.py` + `src/site_photo_flow.py`, surfaced in `src/site_panel.py` + `html/map/06-overlays.js` | P11, P5 |
| F37 (part) | "Design for a bee" habitat builder + Alberta native-bee data spine | `src/bee_habitat.py`, `data/bee_attributes_master.json` (+ Apidae roster in `data/fauna_master.json`), `src/db/fauna.py`, surfaced in `src/analysis_panel.py` (Bees tab) | P8, P3, P10, P5, P9 |
| F40 | Planting Plan — buy-it / plant-it sheet (quantities, form, spacing, planting window, phased schedule) | `src/planting_plan.py`, surfaced in `src/app.py` + `src/pdf_export.py` | P8, P4, P11, P6, P9 |

Net effect on the principles: **P1 partial → strong** (pattern language is now explicit), and
P3/P4/P5 are visibly stronger. **F40 is the first real ACT/OUTPUT win** — it turns a design into
a nursery-ready, plant-it-this-way artifact, advancing the under-served P8 (repair/conversion as a
*plan*) and P11 (a printable field plan that drives the user outside). The latest batch deepens the
*legibility* and *repair* spine: **F1** puts each plant's ecological role (keystone / hosts N
caterpillars / specialist / bird food) where the user already looks (P6, P10); **F10** makes the
Tallamy contrast explicit — this design vs. the ≈0 an equivalent lawn provides (P6, P8); and
**F17** turns the drawn conversion zones into a year-by-year remove-this / plant-that schedule
(P8, P4). The next batch finally invests in the long-neglected **P11 (the body & the site)**:
**F6** captures what the *site* knows as a walked checklist of field observations saved with the
project, and **F24** drops a real yard/drone photo onto the map as a georeferenced underlay you
can mark up — together moving P11 from "fetches site data" toward "captures the user's own
ground-truth". The distinctive depth frontier that's still open is the **relationship graph
overlay (F5)** and the **unified edges layer (F7)** — now deliberately *after* the adoption work
(see "Defer" below).

---

## Ranked summary

### High impact
| ID | Feature | Effort | Risk | Principle |
|----|---------|--------|------|-----------|
| ✅ F1 | "Why it matters" labels in the plant browser | M | Low | P6, P10 |
| ✅ F2 | Year 1 / 5 / 15 / 30 snapshot view | M | Low | P4 |
| ✅ F3 | Food-web completeness score | M | Low | P3, P6 |
| ✅ F4 | Pattern-language framing for communities | M (full L) | Med | P1, P7 |
| F5 | Relationship graph overlay (the distinctive frontier) | L | Med | P3, P5 |
| ✅ F6 | Site-walk field notes | L (slice M) | Med | P11 |
| F7 | Relationship-first data model (unified edges layer) | XL | High | P3, P10 |

### Medium impact
| ID | Feature | Effort | Risk | Principle |
|----|---------|--------|------|-----------|
| F8 | Uncertainty language pass | S | Low | P9 |
| ✅ F9 | Specialist-host spotlight | S | Low | P3, P6 |
| ✅ F10 | Lawn-equivalent counterfactual | S | Low | P6, P8 |
| F11 | Value-vs-price framing | S | Low | P6 |
| F12 | Inline "why this matters" provenance/citations | S | Low | P7, P6 |
| F13 | Reference-ecosystem fidelity score | M | Low | P2, P6 |
| F14 | Establishment-likelihood band | M | Med | P9 |
| F15 | Pollinator-pathway (bloom-in-space) overlay | M | Med | P5, P3 |
| ✅ F16 | Seasonal view toggle (spring/summer/fall/winter) | M | Med | P4, P5 |
| ✅ F17 | Phased conversion plan (year-by-year) | M | Low | P8 |
| F18 | Site-condition remediation advisor | M | Med | P8, P4 |
| F19 | "Why here?" composition reasoning toggle | M | Low | P2, P5 |
| F20 | Maintenance-over-time curve | S | Low | P4 |
| F21 | Ecosystem-services readout | M | Med | P6, P9 |
| ✅ F22 | Naturalistic drift placement | M | Med | P2 |
| F23 | Declarative, inspectable placement rules | M | Low | P1 |
| ✅ F24 | Site photo overlay + markup | M | Med | P11 |
| F25 | Mycorrhizal / symbiosis model | L | Med | P3 |
| F26 | Successional-sequence edges | L | Med | P3, P4 |
| F27 | Habitat-corridor analysis | L | Med | P3 |

### Lower impact / nice-to-have
| ID | Feature | Effort | Risk | Principle |
|----|---------|--------|------|-----------|
| F28 | Confidence marks on inferred fields | S | Low | P9 |
| F29 | Scenario *ranges* on the timeline | M | Low | P9, P4 |
| F30 | Invisible-relationship legend | S | Low | P5, P7 |
| F31 | Glossary / concept explainers | S | Low | P7, P5 |
| F32 | Field-mode checklist (printable) | S | Low | P11 |
| F33 | Seasonal observation journal | M | Low | P11, P4 |
| F34 | Shearing-layers data audit | S | Low | P4 |
| ✅ F35 | Self-seeding / spread simulation | M | Med | P1, P4 |
| F36 | Emergent community spacing | L | Med | P1, P4 |
| F37 | "What the bee sees" mode | M | Low | P5 |
| F38 | Mycoremediation / degraded-site notes | S | Low | P8 |
| F39 | Sensor integration hooks | L | High | P11 |

---

## High impact — detail

### ✅ F1 · "Why it matters" labels in the plant browser — *Shipped · was Impact High / Effort M / Risk Low (P6, P10)*
**Shipped** as the Qt-free `src/ecological_role.py` (`ecological_role_summary(plant) -> list[str]`),
surfaced as a leading **Role:** line in the expanded detail row of `src/plant_list_view.py`. Every
plant now carries its ecological role where the user already looks, not just in the Habitat tab.
**How (as built):** `ecological_role_summary` reuses the same use-tag membership the Habitat Value
Score keys off (keystone / host / bird-food / pollinator / nitrogen-fixer, from the synthesised
`permaculture_uses` blob) plus `fauna.fauna_for_plant(plant_id)` (its `relationship` + `specificity`
columns) to emit short badges — "Keystone", "Hosts 7 caterpillars", "Specialist host", "Bird food",
"Pollinator plant" — highest-value first. The delegate caches the line per `plant_id` (paint runs on
every scroll) and renders it text-only as the first detail row, avoiding the `plant_panel.py` guard
ceiling (the logic and tests live outside the widget). The collapsed-row badge remains the next slice.

### ✅ F2 · Year 1 / 5 / 15 / 30 snapshot view — *Shipped · was Impact High / Effort M / Risk Low (P4)*
**Shipped** in `src/snapshot_timeline.py` + `src/snapshot_window.py`. The philosophy's literal
"most important feature": see the trajectory, not the install-day moment. **How:** the engine already renders any year — `scene_contract.build_scene(project,
year=…)` → `scene3d.plant_3d_state(plant, lat, lng, year)` scales size via
`growth_scale_factor` and fades via `succession.presence_factor`. Build a four-up
comparison (2D thumbnails or 3D captures) calling `build_scene` at years {1,5,15,30}
clamped to `succession.timeline_max_years`. Reuse the 3D window's offscreen capture path
(the same one the "yard photo" bake uses). **First slice:** a 2×2 of 2D canopy renders.

### ✅ F3 · Food-web completeness score — *Shipped · was Impact High / Effort M / Risk Low (P3, P6)*
**Shipped** as the `food_web` line in `src/habitat_score.py`, fed into `src/design_critic.py`.
Score whether the design closes the Tallamy chain (host plants → caterpillars → bird
nestlings), not just whether species are present. **How:** add an 8th, *informational*
line to `habitat_score.compute_habitat_score` that cross-references host-plant counts
(already computed) with `fauna.fauna_supported_by_plants(…, relationship='larval_host')`
and bird-food producers — reporting "supports caterpillars **and** the birds that eat
them" vs. a broken link. Keep it un-summed (like the existing fauna counts) so historical
scores don't drift. Feed a gap line into `design_critic.critique_lines`.

### ✅ F4 · Pattern-language framing for communities — *Shipped (presentation-first) · was Impact High / Effort M / Risk Med (P1, P7)*
**Shipped** in `src/pattern_language.py` + `src/polyculture_panel.py` (the schema-bump "full
version" remains optional). Present plant communities as Alexander patterns (problem → context
→ forces → solution → related) — the app's namesake made literal. **How (presentation-first, no schema bump):**
in `src/polyculture_panel.py`, render each community under the five headings, deriving
*problem/solution* from the existing `description`, *context* from members' `ab_ecoregion`
+ sun/moisture envelope, *forces* from member `functions` and the layer mix, and *related
patterns* from the existing `parent_id` hierarchy. **Full version (schema bump):** add
authored `problem` / `context` / `forces` columns to `polycultures` and seed them.

### F5 · Relationship graph overlay — *Impact High · Effort L · Risk Med — guard ceiling on map JS (P3, P5)*
The app's distinctive frontier: draw the design as a living network, making invisible
relationships visible. **How:** compute edges in Python (Qt-free) — companion friend/enemy
edges already come from `placement_score.build_companion_graph(plant_ids)`; plant↔fauna
edges from `fauna.fauna_for_plants(plant_ids)`. Emit an edges payload to the map and draw
it as a new toggle layer in `html/map/06-overlays.js`, mirroring the existing splat
"yard photo" overlay registration there (so it gets the View-toggle plumbing for free).
**First slice:** companion edges only (data already exists), then layer in pollinator/bird
edges. Watch the map-JS line ceiling — put geometry math in Python, keep the JS thin.

### ✅ F6 · Site-walk field notes — *Shipped (first slice) · was Impact High / Effort L (slice M) / Risk Med (P11)*
**Shipped** as the Qt-free `src/field_notes.py` (prompts catalogue + project-properties
read/write/format), surfaced as a **Field Notes** sub-tab in `src/site_panel.py`. Drives the user
outside and captures what the *site* knows. **How (as built):** a `field_notes` block lives on the
project FeatureCollection `properties` (no DB schema bump) holding a prompted walking checklist —
where water pools, where snow drifts, where soil compacts, where wind funnels, frost pockets, what's
already thriving, where people walk, sun morning vs. afternoon, and an embodied "stand here and
notice" — each a checkbox + one-line observation, plus a free-text catch-all. The panel debounces
edits into a `field_notes_changed` signal; `app.py` stores it on the project and marks it modified
(two thin lambdas — MainWindow is at its method ceiling). **Still to come:** pinning individual
observations to map points (reusing the annotation pipeline) and feeding them into generation as
soft constraints (zone/`exclusion` steering) — e.g. a "pools water" note biasing toward riparian
species.

### F7 · Relationship-first data model (unified edges layer) — *Impact High · Effort XL · Risk High — schema + UI (P3, P10)*
The synthesis of the whole philosophy: one queryable "edges" layer unifying mycorrhizal,
successional, trophic, and companion relationships, so the UI can ask "show me everything
connected to this plant." **How:** generalize the per-relationship tables
(`plant_fauna`, `companion_*`, and proposed `plant_symbiosis` / succession edges) behind a
single `relationships(plant_a, plant_b|fauna_id, kind, strength, source)` view/table and a
query API in a new `src/db/relationships.py`. This is the parent of F5, F9, F25, F26 — best
done *after* one or two of those prove the edge shapes. Schema bump + reseed; sequence it
deliberately.

---

## Medium impact — detail

### F8 · Uncertainty language pass — *Impact Med · Effort S · Risk Low (P9)* — quick win
Soften deterministic phrasing toward honest ranges ("tends to establish well here").
**How:** audit the deterministic strings in `design_critic.critique_lines` and
`design_goals.caveats_for_goals` (both pure, no LLM) and reword toward probabilistic
framing; nudge the `llm_design` system prompt the same way. No new computation.

### ✅ F9 · Specialist-host spotlight — *Shipped · was Impact Med / Effort S / Risk Low (P3, P6)*
**Shipped** via `fauna` specificity surfaced in `src/habitat_score.py`. Flag the conservation
wins — designs that feed *specialist* species (monarch↔milkweed), not just generalists. **How:** `fauna.fauna_for_plant` already returns `specificity`;
surface a "supports N specialist species" badge/line in the habitat breakdown and on the
F1 plant labels. Pure read.

### ✅ F10 · Lawn-equivalent counterfactual — *Shipped · was Impact Med / Effort S / Risk Low (P6, P8)*
**Shipped** in `src/lawn_zones.py` (`lawn_counterfactual` + `format_lawn_counterfactual`), surfaced
as a "vs. lawn" callout directly under the score in the Habitat tab (`src/analysis_panel.py`). Makes
the Tallamy contrast explicit: "this design: 62/100 · the same area as lawn: ~0/100." **How (as
built):** a constant ≈0 lawn baseline (`LAWN_HABITAT_SCORE`) is set beside the design's Habitat Value
total; when conversion zones are drawn, the contrast is grounded in the lawn+restoration area from
`lawn_zones.conversion_summary` ("you're reclaiming ~120 m² from lawn"). `app.py` pushes the same
summary it already computes for the "On This Design" tab into the analysis panel, so the callout stays
live with edits. Qt-free and unit-tested.

### F11 · Value-vs-price framing — *Impact Med · Effort S · Risk Low (P6)*
Pair the cost estimate with the ecological value it buys (the Graeber/Raworth point).
**How:** put `sourcing.design_cost(...)` next to the habitat score in the Analysis panel
and the PDF, framed as "what your spend creates" rather than cost alone.

### F12 · Inline "why this matters" provenance — *Impact Med · Effort S · Risk Low (P7, P6)*
Cite the science at the point of use (Tallamy, Xerces, McHarg), not buried. **How:** add
short sourced one-liners next to the habitat components in `src/analysis_panel.py`
(the keystone framing already cites Tallamy — extend the pattern to host/bird/bloom).

### F13 · Reference-ecosystem fidelity score — *Impact Med · Effort M · Risk Low (P2, P6)*
Score how closely the design matches the *natural* community of its place. **How:**
`ecoregion.lookup_ecoregion(lat, lng)` already detects the site ecoregion; compare the
design's species against `search_plants(ab_ecoregion=detected)` and the natural
vegetation-layer ratios, reporting a 0–100 fidelity figure alongside the habitat score.

### F14 · Establishment-likelihood band — *Impact Med · Effort M · Risk Med (P9)*
Replace point-precision placement with "tends to establish well / variable / risky here."
**How:** `placement_score.score_cell_for_plant(plant, cell)` already returns a 0–1 site-fit
value; bucket it into a three-band confidence shown per plant in the generated-design
summary and (optionally) as a faint map heat cue. No new model calls.

### F15 · Pollinator-pathway (bloom-in-space) overlay — *Impact Med · Effort M · Risk Med (P5, P3)*
Show nectar availability across the *season and the map*, exposing gaps spatially (the
calendar already finds them in time). **How:** `habitat_score.parse_month_range` already
yields per-plant bloom months; emit per-month flowering locations to a scrubbable map layer
in `html/map/06-overlays.js`. Pairs naturally with F5.

### ✅ F16 · Seasonal view toggle — *Shipped · was Impact Med / Effort M / Risk Med (P4, P5)*
**Shipped** — season selector wired through `src/analysis_panel.py` → `src/map_js.py` →
`src/scene_contract.py`. Switch the scene between spring/summer/fall/winter (deciduous vs.
evergreen reads).
**How:** `build_scene` already takes a `when` datetime (the 3D window has month/hour
sliders driving `_when()`); extend the scene/material logic to vary leaf-on/leaf-off and
bloom colour from `deciduous_evergreen` + `bloom_period`, and expose a season switch.

### ✅ F17 · Phased conversion plan — *Shipped · was Impact Med / Effort M / Risk Low (P8)*
**Shipped** in the Qt-free `src/conversion_plan.py` (`build_conversion_schedule` +
`render_schedule_text`), surfaced in the planning **Timeline** tab (`src/planning_panel.py`), the
Planting Plan text export (`src/app.py`) and a dedicated PDF page (`src/pdf_export.py`). Turns drawn
conversion zones into a year-by-year "remove this / plant that, when" schedule. **How (as built):**
it crosses `lawn_zones.conversion_summary`'s `by_stage` breakdown (how much lawn is being converted)
with `succession.restoration_stage` (the five restoration bands: planting → pioneer forbs →
forb–grass matrix → shrubs establishing → climax/canopy) and the design's plants grouped by
successional role (woody structure / pioneers / matrix / self-spreaders / climax). The lawn-removal
step appears only when zones are drawn; the cadence is given as honest year *ranges*, never false
day-precision (P9). Dependency-injectable and unit-tested.

### F18 · Site-condition remediation advisor — *Impact Med · Effort M · Risk Med (P8, P4)*
From measured soil/disturbance, recommend a *repair sequence* (pioneer cover → soil
builders → target community). **How:** `property_data.fetch_soil` returns `ph_top` +
`texture_class`; combine with plant `soil_ph_min/max` (via `search_plants(soil_ph=…)`) and
`succession.successional_role` to stage a recommendation. Revives parked brainstorm L3
through a restoration lens.

### F19 · "Why here?" composition reasoning toggle — *Impact Med · Effort M · Risk Low (P2, P5)*
Explain why the generator placed a plant where it did — turn the black box into a teacher.
**How:** `placement_score` already produces the ecological + aesthetic sub-scores per cell;
surface them on plant click ("north edge: tall-to-the-back + full sun match").

### F20 · Maintenance-over-time curve — *Impact Med · Effort S · Risk Low (P4)*
Show effort dropping as natives establish (brainstorm R4) across the timeline. **How:**
plot the existing year-1-vs-year-3 effort estimate against `succession` years in the
planning panel.

### F21 · Ecosystem-services readout — *Impact Med · Effort M · Risk Med (P6, P9)*
Carbon, stormwater retention, cooling, pollination — as honest *ranges* beside the habitat
score. **How:** add range-based estimators (keyed off canopy area, leaf area, species mix)
in the spirit of `sourcing.py`'s ranged costing; surface in the Analysis panel with
explicit uncertainty.

### ✅ F22 · Naturalistic drift placement — *Shipped · was Impact Med / Effort M / Risk Med (P2)*
**Shipped** — drift/matrix/scatter generators in `src/layout.py` with layer/spread-aware
spacing in `src/planting_spacing.py` (this also delivered F35). Rainer/West "designed plant
communities": matrix + scatter + drift, not rows.

### F23 · Declarative, inspectable placement rules — *Impact Med · Effort M · Risk Low (P1)*
Surface the implicit generative rules (density/m², native-first, anti-monoculture, layer
balance) as a small, tweakable rule set. **How:** lift the constants now embedded in
`placement_score` / `llm_design` into a named, documented rule object the UI can show and
adjust.

### ✅ F24 · Site photo overlay + markup — *Shipped · was Impact Med / Effort M / Risk Med (P11, P5)*
**Shipped** in the Qt-free `src/site_photo.py` (bbox maths + the `site_photo` GeoJSON feature) plus
`src/site_photo_flow.py` (image load/embed + map glue), surfaced as a "Site photo (map underlay)"
group on the Site → Field Notes tab and a new image layer in `html/map/06-overlays.js`. Drops a
yard/drone photo onto the map as a georeferenced underlay (complementing the Gaussian-splat "yard
photo"). **How (as built):** the chosen image is scaled, embedded as a data URL on a `site_photo`
feature, and placed centred on the property pin (or the current map centre) at a real-world **width
across** in metres, preserving aspect — so placement maths is Python-side and the map JS stays a
thin `L.imageOverlay`, mirroring the splat-ortho plumbing (`draw/set-visible/set-opacity/clear`).
Width + opacity are live; it persists with the project and restores through `render_project_to_map`
(so undo/redo and reload stay in sync). **Markup** reuses the existing map annotation pins — no
separate machinery. (The 06-overlays.js guard ceiling was deliberately bumped 1400 → 1480 for the
new overlay block.)

### F25 · Mycorrhizal / symbiosis model — *Impact Med · Effort L · Risk Med — schema bump (P3)*
Promote the facts now buried in plant `notes` (Frankia, ericoid, AMF, inoculation needs)
to first-class data. **How:** add a `plant_symbiosis` table + seed it, with inoculation
hints surfaced on the plant detail and fed into F5/F7. Schema bump + reseed.

### F26 · Successional-sequence edges — *Impact Med · Effort L · Risk Med — schema bump (P3, P4)*
Model "pioneer A prepares the ground for climax B" as a real relationship, driving planting
order and the timeline. **How:** a successional-edge table read by `succession.py` and the
timeline; feeds F2/F17 and the F7 edges layer.

### F27 · Habitat-corridor analysis — *Impact Med · Effort L · Risk Med (P3)*
Connect the design to adjacent natural features (parked brainstorm L2) — relationship
thinking at landscape scale. **How:** overlay nearby habitat (OSM/landcover) and score
connectivity to the design's planted areas; a new analysis layer.

---

## Lower impact / nice-to-have — detail

- **F28 · Confidence marks on inferred fields** — *S · Low (P9)*: visibly mark inferred vs.
  sourced values using the existing `design_goals.Goal.backed` flag pattern.
- **F29 · Scenario ranges on the timeline** — *M · Low (P9, P4)*: show a growth/maturity
  *band* rather than a single line, from a slow/expected/fast spread of `years_to_maturity`.
- **F30 · Invisible-relationship legend** — *S · Low (P5, P7)*: a short primer in the
  analysis panel naming what each overlay teaches the eye to see.
- **F31 · Glossary / concept explainers** — *S · Low (P7, P5)*: plain-language definitions
  for keystone, host, succession, mycorrhiza, linked from the UI and docs.
- **F32 · Field-mode checklist (printable)** — *S · Low (P11)*: a site-walk sheet via
  `pdf_export.py` so the user records outside, then enters findings (pairs with F6).
- **F33 · Seasonal observation journal** — *M · Low (P11, P4)*: timestamped notes
  ("first bloom", "snow lingered here") in the project `properties` that accrue site
  knowledge over years.
- **F34 · Shearing-layers data audit** — *S · Low (P4)*: confirm every layer (tree/shrub/
  perennial/annual/soil) carries the rate-of-change fields Brand's framing needs.
- **✅ F35 · Self-seeding / spread simulation** — *Shipped (P1, P4)*: `src/planting_spacing.py`
  reads the `spread_habit` field so self-spreaders are spaced wider and fill gaps over the
  timeline (delivered alongside F22).
- **F36 · Emergent community spacing** — *L · Med — schema (P1, P4)*: generate
  `polyculture_members` offsets from competition/canopy rules instead of fixed offsets.
- **F37 · "See what a bee sees" family** — *P8, P3, P10, P5, P9*: one Alberta native-bee data
  spine (nesting habit, tongue length, flight season, floral-host genera per species — schema
  v39 `bee_attributes`, seeded from the ANBC Apidae tables after Sheffield et al. 2014) feeding
  three lenses that share one *chosen bee → relevant flowers* selection (`src/bee_habitat.py`).
  - **✅ Increment 1 — "Design for a bee" habitat builder (shipped):** pick a genus or species and
    get floral hosts matched from your own plants (with a *Bombus* tongue↔flower-form fit), nesting
    guidance mapped to the real habitat structures (bee hotel, drilled log, brush pile, unmown lawn)
    or "support the host bee" for cuckoos, and a flight-season forage-coverage check that flags
    bloom gaps. Qt-free core + a Bees tab in `src/analysis_panel.py`. Honest about thin data (P9):
    tongue length is graded only for *Bombus*; undocumented flight seasons skip the coverage check.
  - **✅ Increment 2 — "Be a bumblebee" 3D fly-through (shipped):** a "Fly as a bee" toggle + target-bee
    selector in `src/scene3d_window.py` drops into a first-person fly camera in `html/scene3d.html`
    (WASD/arrows + Q/E + drag-look), with a CSS "bee-vision" tint/vignette overlay and glowing beacons
    floating over the chosen bee's floral-host plants (from `bee_habitat.target_plant_ids_for_bee`,
    driven through `map3d_js.set_bee_mode` / `set_bee_targets`). Purely additive to the viewer — when
    off, OrbitControls owns the camera exactly as before. (A true UV/compound-eye post-process pass is
    a later polish; the vendored three.js addons don't ship EffectComposer.)
  - **Increment 3 — "What the bee sees" map recolour** *(M · Low, P5)*: recolour the Leaflet map by
    floral-resource value for the selected bee (the original card; Yong's Umwelt made literal).
- **F38 · Mycoremediation / degraded-site notes** — *S · Low (P8)*: well-cited restoration
  techniques for contaminated/compacted ground (content, directional).
- **F39 · Sensor integration hooks** — *L · High — external (P11)*: optional soil-moisture/
  temp import (ROADMAP X5) to ground-truth fetched data.

---

## Activation & Action — the adoption frontier (F40–F45)

New entries that fill the ONBOARD and ACT/OUTPUT gaps the funnel lens exposed. These lead the
roadmap now — novices first, depth deferred (not dropped).

| ID | Feature | Stage | Effort | Risk | Principle |
|----|---------|-------|--------|------|-----------|
| ✅ F40 | Planting Plan (buy-it / plant-it sheet) | ACT | M | Low | P8, P4, P11, P6, P9 |
| F41 | Numbered plant-by-numbers map | ACT | M | Med | P5, P11 |
| F42 | Design-specific maintenance calendar | ACT / MAINTAIN | S–M | Low | P4, P9 |
| F43 | Site-prep & soil-amendment sheet | ACT | M | Med | P8, P11 |
| F44 | First-run activation pack | ONBOARD | M | Low | P1, P9 |
| F45 | In-context guidance | ONBOARD | S | Low | P5 |

### ✅ F40 · Planting Plan — buy-it / plant-it sheet — *Shipped · was Impact High / Effort M / Risk Low (P8, P4, P11, P6, P9)*
**Shipped** in `src/planting_plan.py`, surfaced in the text export (`app.py`) and the PDF
(`pdf_export.py`). Answers the three questions that otherwise strand a design on the screen:
*what to buy* (species, quantity, nursery form, per-species price range, grouped by Alberta
source), *when to plant* (per-species window from `db/calendar_data.py` + a phased
structure → matrix → fill schedule), and *how far apart* (spacing from `planting_spacing.py`).
Reuses `sourcing`, `planting_spacing`, `succession`, `calendar_data`; Qt-free and unit-tested;
consolidated the 165-line in-`MainWindow` order-list builder into the testable module.

### F41 · Numbered plant-by-numbers map — *Impact High · Effort M · Risk Med — map capture (P5, P11)*
The companion to F40: a keyed, numbered planting map so "buy 3 Saskatoon" becomes "dig holes 7,
8, 9 — here." **How:** number the placed plants in the same order as the F40 list, draw numbered
markers onto the captured map image (the offscreen capture path the PDF / yard-photo bake already
uses), and key them to the plan table. Watch the map-capture / coordinate plumbing.

### F42 · Design-specific maintenance calendar — *Impact Med · Effort S–M · Risk Low (P4, P9)*
Extends F20 from a curve into an actionable cadence: "Year 1 — water weekly to establish, mulch in
October; Year 2 — taper water; Year 5+ — annual cut-back, no irrigation." **How:** derive stages
from `succession.restoration_stage` + structures' `maintenance_hours_year`, rendered into the
Planting Plan output as honest *ranges*, not false precision (P9).

### F43 · Site-prep & soil-amendment sheet — *Impact Med · Effort M · Risk Med (P8, P11)*
Turn measured site data into a do-this-first prep step (the repair sequence *before* planting).
**How:** from `property_data.fetch_soil` (`ph_top`, `texture_class`) + the design's plant soil
needs, emit "this bed reads heavy clay → loosen and top with 5–8 cm compost" into the plan. Pairs
with F18.

### F44 · First-run activation pack — *Impact High · Effort M · Risk Low (P1, P9)*
The biggest ONBOARD gap: the app opens to a silent blank map and the easy path ("Generate
Design") is buried in File → Ctrl+G. **How:** a first-run welcome (QSettings flag) offering
*Generate / Start blank / Open example*; an empty-state map hint ("drop a pin → draw a boundary →
Generate"); surface **"Generate Design ✨"** as a visible button; ship a sample `.perma.geojson`;
pre-check sensible Generate defaults (budget-friendly, won't-take-over). Reuses
`generate_design_dialog`, `design_goals`.

### F45 · In-context guidance — *Impact Med · Effort S · Risk Low (P5)*
Lower the learning curve in place: tooltips on the boundary tool, placement modes and plant
filters; a geocode-failure toast that points to pin-drop; a bolded first-step line in the Site
panel. **How:** small, local UI additions — no new surfaces.

---

## Defer — depth & connoisseurship (after activation/action prove out)

Kept on the roadmap (the depth is the delight), but **parked** behind the adoption work: these
are high-effort and serve already-engaged power users, so they don't move "ecosystems created"
until the funnel above is healthier.

- **F7 · Unified edges layer** — *XL*: the synthesis, but invisible until F5/F25/F26 prove the
  edge shapes. Sequence last.
- **F25 · Mycorrhizal / symbiosis model** — *L · schema*: connoisseur depth, not a planting
  blocker.
- **F26 · Successional-sequence edges** — *L · schema*: `succession.py` roles already cover the
  timeline on today's data.
- **F27 · Habitat-corridor analysis** — *L*: landscape-scale, speculative, needs external data.
- **F36 · Emergent community spacing** — *L · schema*: F22/F35 already give naturalistic spacing.
- **F37 · "What the bee sees" mode** — *M*: delightful, optional.
- **F39 · Sensor integration hooks** — *L · external*: speculative IoT; defer until asked.

---

## How to choose

Sequenced for **more ecosystems created** — Action and Activation first, Depth deferred
(✅ F1/F2/F3/F4/F6/F9/F10/F16/F17/F22/F24/F35/F40 have shipped):
- **Now — close the loop to the ground (ACTION):** ✅ F40 (Planting Plan) → ✅ F17 (phased
  conversion schedule) → **F41** (numbered plant-by-numbers map) → **F42** (maintenance calendar).
  This is where a design actually becomes a planted ecosystem.
- **Next — get more people to a first design (ACTIVATION):** **F44** (first-run pack) → **F45**
  (in-context guidance), plus the quick confidence wins ✅ F10 (lawn counterfactual) → **F11 / F14
  / F20** (all S–M, Low risk) that build the trust to act.
- **Then — reward the engaged (DEPTH):** F5 (relationship graph), with ✅ F1 (ecological-role
  labels) and ✅ F9 already in; then F15 and F33 (observation journal).
- **Defer:** F7, F25, F26, F27, F36, F37, F39 — see the Defer tier above.

---

## Method notes (keep these honest)

- **McHarg overlays (P5/P11):** the site-analysis tabs *are* McHarg's overlay method
  digitized; new layers should compose, not replace.
- **Alexander patterns (P1/P7):** prefer generative rules and reusable patterns over
  one-off layouts.
- **Tallamy "why" (P6/P8):** every recommendation should answer "why does this matter?"
  with data.
- **Uncertainty (P9):** ship ranges and confidence, never false precision.
- **Discipline:** respect the architecture guard — keep map-JS thin and domain logic
  Qt-free/Python-side; mind `plant_panel.py`'s line ceiling for any browser change.
- **Indigenous knowledge (P12):** anything touching Indigenous land knowledge is gated by
  **core principle #12** in [`DESIGN_PHILOSOPHY.md`](DESIGN_PHILOSOPHY.md) (*Indigenous
  knowledge is honoured through relationship, not extraction*) — directional only until
  consultation and free, prior, and informed consent. This is a hard guardrail, not a backlog
  item: there is no feature to "build" here without consent.
