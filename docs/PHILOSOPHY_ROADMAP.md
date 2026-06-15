# Site & Pattern — Philosophy-Driven Feature Roadmap

A map of what the design philosophy ([`DESIGN_PHILOSOPHY.md`](DESIGN_PHILOSOPHY.md))
makes *possible*, grounded in what the codebase already does. This is the "in breadth and
in depth" exploration — a generative backlog, organized by the eleven principles, rather
than a committed plan.

**How this relates to the other backlog.** [`../FEATURE_BRAINSTORM.md`](../FEATURE_BRAINSTORM.md)
is the engineering backlog (what's shipped, what's next, effort-tiered); [`../ROADMAP.md`](../ROADMAP.md)
is the feature ledger. This document is the *philosophical* lens over both: it asks "what
would it mean to take principle N seriously?" and points at the modules that would carry
the answer. Where an idea already has a brainstorm/roadmap ID, it's cited. The two docs
are meant to be amended together.

**How to read the annotations.** Each idea carries:
*Principle · Builds on (existing code) · Effort (S/M/L) · Risk/deps.*
Effort is rough; "schema bump" means `_SCHEMA_VERSION` + reseed (see `CLAUDE.md`); "guard
ceiling" flags a file near an `tests/test_architecture_guard.py` line limit.

---

## Priority set (the four pinned features)

These are the next concrete steps, chosen as high-philosophy / high-feasibility. Each
builds on existing infrastructure and is specified enough to start.

### A. "Why it matters" labels — make ecological value legible everywhere
*Principle P6 + P10 · Builds on `src/habitat_score.py`, `src/db/fauna.py`,
`src/plant_panel.py` + `src/plant_list_view.py` · Effort M · Risk: `plant_panel.py` guard
ceiling (1600; ~1390 now) — keep additions thin.*

**Problem.** The "why" of a plant (keystone species, larval host for *N* species, bird
food) currently surfaces only in the Habitat Value tab and filter checkboxes. Principle 6
says ecological value should be legible *at every interaction*.

**Build.** A small Qt-free helper — `ecological_role_summary(plant) -> list[str]` — that
reuses the keystone/host/bird-food detection already in `habitat_score.py` and the fauna
counts from `db/fauna.py`, returning short badges ("Keystone", "Hosts 7 caterpillars",
"Bird food"). Render them as a subtitle/badge row in the plant browser delegate
(`plant_list_view.py`) and in the expanded detail. Specialist host relationships
(`plant_fauna.specificity = 'specialist'`) get a distinct emphasis — they're the
highest-leverage.

**First slice.** Compute + show the badges in the *expanded* detail row only (no delegate
paint changes), then move to the collapsed row once the string is proven.

### B. Pattern-language framing for plant communities (the namesake)
*Principle P1 + P7 · Builds on `src/db/polycultures.py` (descriptions + `parent_id`),
`src/polyculture_panel.py` · Effort M (presentation) / L (data) · Risk: structured fields
= schema bump.*

**Problem.** Alexander's *A Pattern Language* is the app's namesake, yet communities are
presented as plant lists with a prose blurb. A pattern has structure: **problem → context
→ forces → solution → related patterns.**

**Build (presentation-first, no schema bump).** Render each community in the polyculture
panel under the five pattern headings, deriving:
- *Problem / Solution* from the existing `description`,
- *Context* from members' `ab_ecoregion` + sun/moisture envelope,
- *Forces* from member `functions` (nitrogen-fixer, pest-deterrent, …) and layer mix,
- *Related patterns* from `parent_id` (variation hierarchy already exists).

**Later (data pass, schema bump).** Add first-class `problem` / `context` / `forces`
columns to `polycultures` and author them per community, following the seed pattern in
`CLAUDE.md`. This turns the community library into a true generative pattern language.

### C. Uncertainty language pass — honest ranges over false precision
*Principle P9 · Builds on `src/llm_design.py`, `src/design_critic.py`,
`src/analysis_panel.py` summaries · Effort S · Risk: low (string-level).*

**Problem.** Cost/spacing/bloom are already ranges, but generated-design narration and
critique still read deterministically ("places X here"). Principle 9: prefer "tends to
establish well in these conditions."

**Build.** Audit user-facing generated strings and soften to probabilistic framing; add a
one-line establishment-confidence note to generated designs derived from how well the
site envelope matches each species (data the scorer already computes in
`placement_score.py`). No new model calls — reuse existing fitness scores.

### D. Site-walk field notes — drive the user outside
*Principle P11 · Builds on `.perma.geojson` project format (`src/project.py`),
`src/analysis_panel.py` · Effort L · Risk: new UI surface; mind `analysis_panel.py` /
`app.py` ceilings. Store in the project file to avoid a DB schema bump.*

**Problem.** The app fetches site data (wind, soil, terrain) but never asks the user what
*they* observed — where water pools, where snow drifts, where the soil is compacted, where
the wind tunnels. That embodied knowledge is, per principle 11, what the screen doesn't
have.

**Build.** A structured "Site Walk" capture: prompted observations (soil feel, drainage,
sun/shade by area, wind, existing plants, problem spots) stored as a `field_notes` block
in the project GeoJSON, optionally pinned to map points (reuse the existing annotation /
custom-shape pipeline). Feed the notes into design generation as soft constraints (e.g. a
"pools water" pin biases toward riparian/rain-garden species — wiring into the existing
`exclusion`/zone steering, brainstorm F5).

**First slice.** A non-pinned checklist + free-text per project, saved/loaded with the
design; map-pinning and generator-wiring follow.

---

## Feature exploration by principle

### P1 — Living systems self-organize from the bottom up
**Today:** scored-cell placement (`placement_score.py`), offline community selection by
goal/ecoregion (`llm_design._select_offline_communities`, brainstorm D2).
**Partial:** generative rules are mostly implicit (in the LLM / in templates).
**Ideas:**
- *Declarative placement rules* — surface the implicit rules (density per m², native-first,
  anti-monoculture, layer balance) as an inspectable, tweakable rule set. *P1 · placement_score.py · M · none.*
- *Emergent community spacing* — let `polyculture_members` offsets be generated from
  competition/▾canopy rules rather than fixed, so a community self-arranges to its site.
  *P1+P4 · polycultures.py, area_fill.py · L · schema (offset semantics).*
- *Self-seeding / spread simulation* — model `spread_habit` over time so aggressive
  spreaders fill gaps in the timeline view. *P1+P4 · succession.py, schema spread_habit · M.*

### P2 — The best designs disappear into their context
**Today:** aesthetic terms (`_height_gradient`/`_cohesion`/`_rhythm`).
**Ideas:**
- *Naturalistic drift placement* — Rainer/West "designed plant communities": matrix +
  scatter + drift patterns as layout options. *P2 · placement_score.py, area_fill.py · M.*
- *Show the composition reasoning* — a toggle that explains *why* a plant landed where it
  did (the aesthetic + ecological score breakdown), turning a black box into a teacher.
  *P2+P5 · placement_score.py · S.*
- *Reference-ecosystem fidelity score* — how closely the design matches the natural
  vegetation-layer ratios of its `ab_ecoregion`. *P2+P6 · habitat_score.py, ecoregion.py · M.*

### P3 / P10 — Relationships over components; design for relationships
**Today:** `plant_fauna` (500+ edges), companions, polyculture functions, `plant_uses`.
**Partial:** no network *visualization*; mycorrhizal/symbiosis only in `notes`.
**Ideas (high leverage — this is the app's distinctive frontier):**
- *Relationship graph overlay* — draw the live design as a network: plant↔pollinator,
  plant↔bird, companion friend/enemy edges (the companion graph is already computed in
  `placement_score.build_companion_graph`). *P3+P5 · fauna.py, placement_score.py, map JS ·
  L · guard ceiling on map JS.*
- *Mycorrhizal / symbiosis model* — promote the notes-level facts (Frankia, ericoid,
  AMF) to a `plant_symbiosis` table + inoculation hints. *P3 · schema + seed · L · schema bump.*
- *Successional sequence edges* — model "pioneer A prepares soil for climax B" as a
  first-class relationship, driving the timeline and planting-order advice. *P3+P4 ·
  succession.py, schema · L · schema bump.*
- *Specialist-host spotlight* — flag designs that support specialist species (monarch↔milkweed)
  vs. generalists; specialists are the conservation win. *P3+P6 · fauna.py (specificity) · S.*
- *Food-web completeness* — score whether the design closes a local food web
  (host plants → caterpillars → bird nestlings), the Tallamy chain. *P3+P6 · habitat_score.py · M.*

### P4 — Time is the most undervalued design variable
**Today:** `succession.py`, 3D year slider, scene contract, growth fields. **(Strong.)**
**Ideas:**
- *Year 1 / 5 / 15 / 30 snapshots* — the philosophy's literal ask: a four-up comparison
  view (the engine already computes presence + scale per year). *P4 · succession.py,
  scene_contract.py · M.*
- *Maintenance-over-time curve* — establishment effort fades as natives mature (brainstorm
  R4); plot it across the timeline. *P4 · planning_panel, succession.py · S.*
- *Seasonal view toggle* — spring/summer/fall/winter appearance (ROADMAP V2), deciduous vs.
  evergreen from `deciduous_evergreen`. *P4+P5 · scene_contract.py, map JS · M.*
- *Shearing-layers data audit* — Brand's frame: make sure every layer (tree/shrub/perennial/
  annual/soil) has the rate-of-change fields it needs. *P4 · schema · S.*

### P5 — Perception is constructed
**Today:** sun/wind/shade overlays, sector analysis.
**Ideas:**
- *Pollinator-pathway overlay* — bloom-time × forage location animated across the season,
  exposing nectar gaps spatially (the calendar already finds them temporally). *P5+P3 ·
  habitat_score bloom parsing, map JS · M.*
- *"What the bee sees" mode* — recolour the map by floral resource value / UV-ish cues
  (Yong's Umwelt made literal). *P5 · map JS · M (playful, optional).*
- *Invisible-relationship legend* — a perception primer that names what each overlay is
  teaching the user to see. *P5+P7 · analysis_panel.py · S.*

### P6 — Conventional metrics miss ecological value
**Today:** Habitat Value Score (7 components), honest cost framing. **(Strong.)**
**Ideas:**
- *Ecosystem-services readout* — carbon, stormwater retention, cooling, pollination as
  ranges alongside the habitat score. *P6+P9 · habitat_score.py, sourcing.py · M.*
- *"Value vs. price" framing* — pair the cost estimate with the ecological value it buys,
  making the Graeber/Raworth point explicit. *P6 · sourcing.py, habitat_score.py · S.*
- *Lawn-equivalent counterfactual* — show what the same area as lawn provides (≈nothing),
  the Tallamy contrast. *P6+P8 · lawn_zones.py, habitat_score.py · S.*

### P7 — Generalist knowledge / cross-domain
**Today:** architecture itself; deep modules guarded by `test_architecture_guard.py`.
**Ideas:**
- *Inline "why this matters" provenance* — short citations (Tallamy, Xerces, McHarg) at
  the point of use, not buried. *P7+P6 · analysis_panel.py · S.*
- *Glossary / concept map* — link keystone, host, succession, mycorrhiza to plain-language
  explainers. *P7+P5 · docs + UI · S.*

### P8 — Repair is more sophisticated than creation
**Today:** lawn-conversion zones (`lawn_zones.py`), design critique/repair loop
(`design_critic.py`). **(Strong.)**
**Ideas:**
- *Site-condition remediation advisor* — from soil/compaction/disturbance, recommend a
  repair sequence (pioneer cover → soil builders → target community). Revives parked
  brainstorm L3 (soil/disturbance overlay) through a restoration lens. *P8+P4 · soil_grid.py,
  succession.py · M.*
- *Phased conversion plan* — turn conversion zones into a year-by-year "what to remove /
  plant when" schedule. *P8 · lawn_zones.py, succession.py · M.*
- *Mycoremediation / degraded-site notes* — surface restoration techniques for contaminated
  or compacted ground (directional, well-cited). *P8 · data/docs · S.*

### P9 — Uncertainty is a feature
**Today:** ranges everywhere, `backed` flags, un-summed informational counts. **(Strong.)**
**Ideas:**
- *Establishment-likelihood band* — "tends to establish well / variable / risky here" from
  site-envelope match, shown per plant. *P9 · placement_score.py · M.*
- *Confidence on data-gap fields* — visibly mark inferred vs. sourced values (e.g. R4
  effort heuristic). *P9 · design_goals.py · S.*
- *Scenario ranges in the timeline* — show a band, not a line, for growth/maturity. *P9+P4 ·
  succession.py · M.*

### P11 — The body and the site know things the screen does not
**Today:** fetches wind/soil/terrain/elevation; phone-scan import. **Partial — no capture of
the user's own observation.**
**Ideas (beyond priority item D):**
- *Photo overlay / markup* — drop site photos as map underlays with pins (ROADMAP V5).
  *P11 · map JS, project.py · M.*
- *Seasonal observation journal* — timestamped notes ("first bloom", "where snow lingered")
  that accrue into site knowledge. *P11+P4 · project.py · M.*
- *Field-mode checklist export* — a printable site-walk sheet so the user records outdoors,
  then enters findings. *P11 · pdf_export.py · S.*
- *Sensor hooks* — optional soil-moisture/temp import (ROADMAP X5) to ground-truth the
  fetched data. *P11 · property_data.py · L.*

---

## Cross-cutting larger bets

- *Relationship-first data model* — the synthesis of P3/P10: a unified "edges" layer
  (mycorrhizal, successional, trophic, companion) the UI can query and draw. The single
  highest-impact, highest-effort direction. *Schema + UI · L.*
- *Generative pattern language* (priority B, full form) — communities as authored
  Alexander patterns with related-pattern graphs.
- *Habitat-corridor analysis* (parked brainstorm L2) — connect the design to adjacent
  natural features; a landscape-scale expression of P3. *L.*

---

## Method notes (keep these honest)

- **McHarg overlays (P5/P11):** the site-analysis tabs *are* McHarg's overlay method
  digitized; new layers should compose, not replace.
- **Alexander patterns (P1/P7):** prefer generative rules and reusable patterns over
  one-off layouts.
- **Tallamy "why" (P6/P8):** every recommendation should be able to answer "why does this
  matter?" with data.
- **Uncertainty (P9):** ship ranges and confidence, never false precision.
- **Indigenous knowledge:** anything touching Indigenous land knowledge is gated by the
  consent principles in [`DESIGN_PHILOSOPHY.md`](DESIGN_PHILOSOPHY.md) — directional only
  until consultation and FPIC.
