# Site & Pattern — Philosophy-Driven Feature Roadmap

A catalogue of what the design philosophy ([`DESIGN_PHILOSOPHY.md`](DESIGN_PHILOSOPHY.md))
makes *possible*, grounded in what the codebase already does — and **ranked by impact** so
the next move can be chosen deliberately. Each entry states **Impact / Effort / Risk**,
the principle(s) it serves, and a concrete **how I'd build it** (the actual functions and
files it would lean on).

**Relationship to the other backlogs.** [`../FEATURE_BRAINSTORM.md`](../FEATURE_BRAINSTORM.md)
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

## Ranked summary

### High impact
| ID | Feature | Effort | Risk | Principle |
|----|---------|--------|------|-----------|
| F1 | "Why it matters" labels in the plant browser | M | Low | P6, P10 |
| F2 | Year 1 / 5 / 15 / 30 snapshot view | M | Low | P4 |
| F3 | Food-web completeness score | M | Low | P3, P6 |
| F4 | Pattern-language framing for communities | M (full L) | Med | P1, P7 |
| F5 | Relationship graph overlay (the distinctive frontier) | L | Med | P3, P5 |
| F6 | Site-walk field notes | L (slice M) | Med | P11 |
| F7 | Relationship-first data model (unified edges layer) | XL | High | P3, P10 |

### Medium impact
| ID | Feature | Effort | Risk | Principle |
|----|---------|--------|------|-----------|
| F8 | Uncertainty language pass | S | Low | P9 |
| F9 | Specialist-host spotlight | S | Low | P3, P6 |
| F10 | Lawn-equivalent counterfactual | S | Low | P6, P8 |
| F11 | Value-vs-price framing | S | Low | P6 |
| F12 | Inline "why this matters" provenance/citations | S | Low | P7, P6 |
| F13 | Reference-ecosystem fidelity score | M | Low | P2, P6 |
| F14 | Establishment-likelihood band | M | Med | P9 |
| F15 | Pollinator-pathway (bloom-in-space) overlay | M | Med | P5, P3 |
| F16 | Seasonal view toggle (spring/summer/fall/winter) | M | Med | P4, P5 |
| F17 | Phased conversion plan (year-by-year) | M | Low | P8 |
| F18 | Site-condition remediation advisor | M | Med | P8, P4 |
| F19 | "Why here?" composition reasoning toggle | M | Low | P2, P5 |
| F20 | Maintenance-over-time curve | S | Low | P4 |
| F21 | Ecosystem-services readout | M | Med | P6, P9 |
| F22 | Naturalistic drift placement | M | Med | P2 |
| F23 | Declarative, inspectable placement rules | M | Low | P1 |
| F24 | Site photo overlay + markup | M | Med | P11 |
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
| F35 | Self-seeding / spread simulation | M | Med | P1, P4 |
| F36 | Emergent community spacing | L | Med | P1, P4 |
| F37 | "What the bee sees" mode | M | Low | P5 |
| F38 | Mycoremediation / degraded-site notes | S | Low | P8 |
| F39 | Sensor integration hooks | L | High | P11 |

---

## High impact — detail

### F1 · "Why it matters" labels in the plant browser — *Impact High · Effort M · Risk Low (P6, P10)*
Make every plant carry its ecological role where the user already looks, not just in the
Habitat tab. **How:** add a Qt-free `ecological_role_summary(plant) -> list[str]` that
reuses the keystone / host / bird-food logic from `habitat_score.compute_habitat_score`
and `fauna.fauna_for_plant(plant_id)` (which returns `relationship` + `specificity`), and
renders short badges ("Keystone", "Hosts 7 caterpillars", "Bird food", "Specialist host").
Surface it first in the *expanded* detail row of `src/plant_list_view.py` (no delegate
paint changes → avoids the `plant_panel.py` guard ceiling), then in the collapsed row once
proven. **First slice:** expanded-row text only.

### F2 · Year 1 / 5 / 15 / 30 snapshot view — *Impact High · Effort M · Risk Low (P4)*
The philosophy's literal "most important feature": see the trajectory, not the install-day
moment. **How:** the engine already renders any year — `scene_contract.build_scene(project,
year=…)` → `scene3d.plant_3d_state(plant, lat, lng, year)` scales size via
`growth_scale_factor` and fades via `succession.presence_factor`. Build a four-up
comparison (2D thumbnails or 3D captures) calling `build_scene` at years {1,5,15,30}
clamped to `succession.timeline_max_years`. Reuse the 3D window's offscreen capture path
(the same one the "yard photo" bake uses). **First slice:** a 2×2 of 2D canopy renders.

### F3 · Food-web completeness score — *Impact High · Effort M · Risk Low (P3, P6)*
Score whether the design closes the Tallamy chain (host plants → caterpillars → bird
nestlings), not just whether species are present. **How:** add an 8th, *informational*
line to `habitat_score.compute_habitat_score` that cross-references host-plant counts
(already computed) with `fauna.fauna_supported_by_plants(…, relationship='larval_host')`
and bird-food producers — reporting "supports caterpillars **and** the birds that eat
them" vs. a broken link. Keep it un-summed (like the existing fauna counts) so historical
scores don't drift. Feed a gap line into `design_critic.critique_lines`.

### F4 · Pattern-language framing for communities — *Impact High · Effort M (full L) · Risk Med (P1, P7)*
Present plant communities as Alexander patterns (problem → context → forces → solution →
related) — the app's namesake made literal. **How (presentation-first, no schema bump):**
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

### F6 · Site-walk field notes — *Impact High · Effort L (slice M) · Risk Med — new UI surface (P11)*
Drive the user outside and capture what the *site* knows (where water pools, snow drifts,
soil compacts, wind tunnels). **How:** store a structured `field_notes` block in the
project FeatureCollection `properties` (in `src/project.py`) — no DB schema bump — with a
prompted checklist + free text. Optionally pin notes to map points by reusing the existing
annotation / custom-shape pipeline. Later, feed notes into generation as soft constraints
via the existing zone/`exclusion` steering (brainstorm F5) — e.g. a "pools water" pin
biases toward riparian species. **First slice:** non-pinned checklist + free text saved
with the project.

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

### F9 · Specialist-host spotlight — *Impact Med · Effort S · Risk Low (P3, P6)* — quick win
Flag the conservation wins — designs that feed *specialist* species (monarch↔milkweed),
not just generalists. **How:** `fauna.fauna_for_plant` already returns `specificity`;
surface a "supports N specialist species" badge/line in the habitat breakdown and on the
F1 plant labels. Pure read.

### F10 · Lawn-equivalent counterfactual — *Impact Med · Effort S · Risk Low (P6, P8)* — quick win
Make the Tallamy contrast explicit: "the same area as lawn supports ≈0 of this." **How:**
in the Habitat tab, render a side-by-side of the current score vs. a lawn baseline (a
constant ≈0 habitat value) over the converted area from `lawn_zones.conversion_summary`.

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

### F16 · Seasonal view toggle — *Impact Med · Effort M · Risk Med (P4, P5)*
Switch the scene between spring/summer/fall/winter (deciduous vs. evergreen reads).
**How:** `build_scene` already takes a `when` datetime (the 3D window has month/hour
sliders driving `_when()`); extend the scene/material logic to vary leaf-on/leaf-off and
bloom colour from `deciduous_evergreen` + `bloom_period`, and expose a season switch.

### F17 · Phased conversion plan — *Impact Med · Effort M · Risk Low (P8)*
Turn drawn conversion zones into a year-by-year "remove this / plant that, when" schedule.
**How:** `lawn_zones.conversion_summary` already returns a `by_stage` breakdown
(lawn → year-1 → year-3 → established); cross it with `succession.restoration_stage` to
emit an ordered task list into the planning panel and the PDF.

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

### F22 · Naturalistic drift placement — *Impact Med · Effort M · Risk Med (P2)*
Rainer/West "designed plant communities": matrix + scatter + drift, not rows. **How:** add
drift/matrix layout options to the `area_fill` / `placement_score` placement path alongside
the existing patterns.

### F23 · Declarative, inspectable placement rules — *Impact Med · Effort M · Risk Low (P1)*
Surface the implicit generative rules (density/m², native-first, anti-monoculture, layer
balance) as a small, tweakable rule set. **How:** lift the constants now embedded in
`placement_score` / `llm_design` into a named, documented rule object the UI can show and
adjust.

### F24 · Site photo overlay + markup — *Impact Med · Effort M · Risk Med (P11)*
Drop a site/drone photo as a map underlay with pins (ROADMAP V5; complements the Gaussian-
splat "yard photo"). **How:** store the image reference + world placement in the project
`properties` and render it as a toggle layer in the map JS, reusing the splat-overlay
plumbing.

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
- **F35 · Self-seeding / spread simulation** — *M · Med (P1, P4)*: use the `spread_habit`
  field to let spreaders fill gaps over the timeline (invert the `well_behaved_only` filter
  to find them).
- **F36 · Emergent community spacing** — *L · Med — schema (P1, P4)*: generate
  `polyculture_members` offsets from competition/canopy rules instead of fixed offsets.
- **F37 · "What the bee sees" mode** — *M · Low (P5)*: recolour the map by floral-resource
  value (Yong's Umwelt made literal); playful, optional.
- **F38 · Mycoremediation / degraded-site notes** — *S · Low (P8)*: well-cited restoration
  techniques for contaminated/compacted ground (content, directional).
- **F39 · Sensor integration hooks** — *L · High — external (P11)*: optional soil-moisture/
  temp import (ROADMAP X5) to ground-truth fetched data.

---

## How to choose

A few natural shortlists, depending on appetite:
- **Fastest visible wins:** F8, F9, F10, F11, F12, F20 (all S, Low risk) — a "legibility +
  honesty" sprint that advances P6/P9 with little risk.
- **Highest philosophical payoff:** F5 (relationship graph) and F2 (time snapshots) — the
  two features that most make invisible structure visible; F3 deepens the headline metric.
- **The namesake move:** F4 (pattern-language framing).
- **The big bet, sequenced:** prove edges with F9 → F5 → F25/F26, then unify in F7.

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
- **Indigenous knowledge:** anything touching Indigenous land knowledge is gated by the
  consent principles in [`DESIGN_PHILOSOPHY.md`](DESIGN_PHILOSOPHY.md) — directional only
  until consultation and FPIC.
