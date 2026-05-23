# PermaDesign — Native Habitat Feature Brainstorm

## Context

The first pivot pass (branding + taxonomy + structures swap) shipped on `claude/youthful-mayer-VpuXj`. The app now *reads* as a Native Habitat Designer but most analysis/planning panels still reflect their food-forest origins (harvest calendar, water budget, maintenance estimator). This document proposes the next round of **functional** changes — reframes and additions that make the app genuinely useful for lawn-to-habitat conversion in Alberta, while keeping the landscape-design core.

Grouped by effort tier so you can pick a sprint slice. Each item notes what existing code it leans on.

---

## Tier 0 — Reframes of existing features (low effort, high payoff)

These reuse infrastructure that already exists; mostly UI copy + small data joins.

### R1. Bloom & Berry Calendar (replaces Harvest Calendar) — **SHIPPED**
- Existing: `src/planning_panel.py` P3 tab; plants already have `bloom_period` + `fruit_period` strings.
- Change: split the P3 table into two columns — **"When pollinators feed"** (bloom_period) and **"When birds feed"** (fruit_period). Highlight **nectar gaps** (months with no blooming species) in red.
- Why: same data, but framed for habitat continuity instead of human harvest scheduling.

### R2. Habitat Value Score (new tab on Analysis panel) — **SHIPPED**
- Existing: `src/analysis_panel.py`; plant-tag system already includes `keystone_species`, `host_plant`, `bird_food`, `nesting_material`, `native_to_alberta`.
- Change: composite 0–100 score with breakdown — % natives, # keystone species, # host plant species, vegetation-layer diversity (overstory/understory/shrub/herb/groundcover), structural diversity (snag/brush pile/bee log/water feature), bloom continuity months. Tallamy-style live readout as the user places elements.
- Why: gives the user a single ecological-quality dial to optimize against.

### R3. Native Plant Order List (replaces generic Shopping List export) — **SHIPPED**
- Existing: shopping list export already produces a plant tally.
- Change: group by **Alberta nursery source** (ALCLA, Bow Valley Habitat Development, Wild About Flowers, Bedrock Seed Bank); add a "seed vs. plug vs. container" column inferred from plant type; surface a footer link to each nursery.
- Why: removes the biggest friction step between *design* and *actually planting it*.

### R4. Maintenance estimator → Establishment Effort — **SHIPPED**
- Existing: `src/planning_panel.py` P2 tab.
- Change: split the labour number into **Year 1 establishment hours** (watering-in, weeding bare zones, smother prep) vs. **Year 3+ stewardship hours** (much lower for established native communities). Communicates the "front-load now, hands-off later" reality of native plantings.

### R5. Water Budget → Establishment Water Budget — **SHIPPED**
- Existing: `src/planning_panel.py` P6 tab.
- Change: same calculation, but two columns — Year 1 (full demand, irrigation often needed) and Year 3+ (most natives at 0–25% of base demand). Caveat for newly-seeded zones.

---

## Tier 1 — New native-habitat features (medium effort)

These need a small amount of new schema or new UI but reuse the placement / map / DB infra.

### N1. Reference ecosystem picker — **SHIPPED**
- New tag on plant records: `ab_ecoregion` (one or more of: Aspen Parkland, Mixedgrass Prairie, Fescue Grassland, Foothills, Boreal Mixedwood, Riparian, Wet Meadow, Subalpine).
- New top-of-app selector: "Restoring toward: \[Aspen Parkland Edge ▼\]". Filters the plant panel and tints out-of-region species.
- Tagging the 433-plant DB is the bulk of the work; could be done with a Permapeople / iNaturalist cross-reference pass.

### N2. Lawn conversion zones
- Existing: custom shape / boundary drawing tools (`html/map.html`, `src/map_widget.py`).
- Change: add a `zone_type` enum to drawn polygons — `lawn_remaining`, `restoration_year_1`, `restoration_year_3`, `established_native`, `existing_remnant`. Show a status-bar readout of square metres converted, with a year-by-year breakdown.
- Why: makes "I converted X m² of lawn this year" a first-class number the app tracks for you.

### N3. Native seed-mix broadcast zones
- Alternative to point-placing individual plants in large meadow areas.
- Draw a polygon → assign a built-in Alberta seed mix ("Boulevard pollinator strip", "Dry foothills fescue meadow", "Wet sedge meadow", "Riparian willow understory"). Each mix is a recipe of species + relative cover %.
- Renders as a hatched fill; counts toward all the habitat-value metrics.

### N4. Pollinator & bird species attracted
- New small static dataset: maps key Alberta natives → specialist pollinator / bird species supported (Asclepias → Monarch; willow → Mourning Cloak, Tiger Swallowtail, ~30 native bee species; chokecherry → cedar waxwing, Bohemian waxwing; etc.).
- New analysis-panel readout: "Your design supports an estimated 4 specialist bee species, 12 bird species, 2 butterfly species."
- Most impactful when paired with R2 habitat score.

### N5. Reframe P1 "Succession timeline" as **Ecological Succession**
- Already planned in ROADMAP (Tier 3 P1).
- Reframe slider stages from food-forest years to restoration years: Year 1 (bare/seeded, pioneer forbs), Year 3 (forb–grass matrix), Year 5 (shrubs establishing), Year 10+ (climax community / canopy).
- Plants flagged `early_successional` show up at Year 1–3 and fade; climax species emerge over time.

---

## Tier 2 — Larger / longer-horizon (high impact, more work)

### L1. "Convert my lawn" onboarding flow
- Optional wizard: draw lot → mark existing lawn → pick ecoregion → pick a starter community (boulevard pollinator strip, backyard meadow patch, hedgerow shelterbelt) → wizard drops a seed mix + 1–2 habitat structures (bee log, brush pile) onto the map.
- Lower priority than the rest because you previously said "no new wizards" — listed here in case opinion shifts after seeing R1–R5 land.

### L2. Habitat corridor analysis
- If the user marks an adjacent natural feature (river valley, ravine, park, undeveloped lot), suggest planting strips that bridge to it; visual heat overlay of connectivity. Most relevant for Edmonton river valley, Calgary Bow corridor, Red Deer.

### L3. Soil / site disturbance overlay
- Mark zones as `lawn_turf`, `compacted_subsoil`, `bare_disturbed`, `remnant_native`. Each zone surfaces a recommended prep method (smother / sheet mulch / solarize / no-till broadcast).
- Pairs naturally with N2 seed-mix zones.

### L4. Drop from roadmap entirely
- **P4 Crop rotation tracker** — annual food-garden feature, doesn't fit.
- **P5 Input/output mapping** — permaculture energy-flow concept; drop or shelve indefinitely.

---

## Data work that unlocks the above

The biggest single unlock is **enriching `data/plants_master.json`** with a few new fields. None of this requires schema migrations beyond the existing JSON ingest:
- `ab_ecoregion` — list of ecoregions where the species naturally occurs (enables N1).
- `pollinator_specialists` — list of bee/butterfly/moth species the plant hosts (enables N4 + boosts R2).
- `bird_value` — short list of bird species that use the plant for food / cover / nesting (enables N4).
- `establishment_difficulty` — `easy/moderate/hard` for Year-1 effort (refines R4).

These are tractable as a one-shot enrichment pass against Audubon / Xerces / iNaturalist / ALCLA references. You previously noted that schema expansion and dataset growth are being handled separately on a "local AI workflow" — that workflow is the natural home for this enrichment.

---

## First slice (shipped)

The first focused PR shipped R1 + R2 + R3 — all UI / scoring work over existing data, no plant-DB enrichment needed. Together they shift the feel of the app from "permaculture planner with new labels" to "habitat designer that scores my design."

1. **R1** — Bloom & Berry Calendar (`src/planning_panel.py`)
2. **R2** — Habitat Value Score, new tab on Analysis panel (`src/analysis_panel.py`)
3. **R3** — Native Plant Order List export grouped by AB nursery source (`src/app.py`)

Remaining tier-0 reframes (R4 establishment-effort split, R5 establishment-water-budget split) are good follow-up candidates.

---

## Verification (when something from this list is built)

- Open an existing project — confirm Year-1 vs. Year-3+ readouts make sense for known native plantings (e.g., a chokecherry / saskatoon / wolf willow community).
- Habitat value score: place a known high-keystone Alberta species (Populus tremuloides, Salix bebbiana, Solidago canadensis) and confirm the score rises meaningfully.
- Bloom & berry calendar: confirm a design heavy on Asteraceae shows late-summer nectar coverage; confirm spring-gap warning surfaces on a shrub-only design.
- Invasive warning: try placing creeping bellflower or ornamental caragana — banner should appear.
- Order list export: groupings by Alberta nursery should be present and clickable.
