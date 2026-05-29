# Data gaps & roadmap — Generate Design goals (V1.44)

The V1.44 "Generate Design" feature lets users pick **design goals** (food
producing, pet/kid friendly, flowers all season, year-round interest, …) and
have a local LLM — or a deterministic offline fallback — assemble a starting
design. Goals are wired through `src/design_goals.py` (the single registry the
GUI, CLI, and generation engine all read).

This release ships **no schema or seed-data change**. Goals are honoured
**hybrid**-style: a hard `search_plants` filter where the data already exists,
an LLM prompt hint where it doesn't, plus a post-generation check that warns
when an unbacked goal could only be applied as guidance.

This document is the **roadmap for the data work** that turns the hint-only
goals into real, filterable, verifiable design constraints — and folds in the
additional field ideas raised alongside the feature request.

## How goals are backed today

| Goal (`key`) | Backed now? | Mechanism this release |
|---|---|---|
| `native_only` | ✅ | hard filter `native_only=True` (`plants.native_to_alberta`) |
| `pollinator` | ✅ | hard filter `pollinator_only=True` (`plant_uses` junction) |
| `food_producing` | ✅ | hard filter `edible_only=True` (`plants.edible_parts`) |
| `flowers_all_season` | ⛅ hint only | `bloom_period` is free text, not month-queryable |
| `pet_friendly` | ❌ hint only | no toxicity data exists |
| `kid_friendly` | ❌ hint only | no toxicity / thorn data exists |
| `year_round_interest` | ⛅ hint only | `deciduous_evergreen` / `fruit_period` exist but aren't filterable |

## Standing conventions for every data chunk below

- **JSON stays the authored source of truth.** SQLite is *already* the runtime
  store — it is generated from `data/*.json` on launch by
  `src/db/plants.py:init_db`. There is no "switch to SQLite" to make; just keep
  editing the JSON (it diffs cleanly in review) and let the reseed pipeline run.
- **Per CLAUDE.md:** bump `_SCHEMA_VERSION` (`src/db/plants.py`) when schema or
  seed data changes; add any new dependent table to the `init_db` reseed
  `DELETE FROM` list; add a `_seed_*` helper; add tests using the temp-DB
  pattern from `tests/test_polycultures.py`.
- **Flip the goal as data lands.** When a field below ships, set the matching
  `Goal.backed = True` and add its `filters=` in `src/design_goals.py`. Every
  caller (GUI dialog, CLI `--goal`, LLM path, offline fallback) picks it up at
  once.
- **Safety fields must never default to "safe."** An unknown toxicity value is
  *not* a safe value — default to unknown/unrated and require an explicit,
  sourced classification before a plant counts as pet/kid safe.

## Reuse note — host-plant relationships already exist

The V1.31 `plant_fauna` junction (`src/db/schema.sql`) already records, per
plant↔fauna pair, a `relationship ∈ {larval_host, nectar, pollen, seed_food,
fruit_food, nesting, cover}` plus `specialist` / `generalist`. So "show me
plants that support the Two-tailed Swallowtail" is mostly a matter of
**exposing existing data** as a `search_plants` filter — not adding a new array
column to `plants`.

---

## Chunk 2 — Safety & small-lot fit  *(makes Pet/Kid friendly real)*

- `safety_rating TEXT` ∈ `safe | toxic_pets | toxic_humans` (e.g. Monkshood,
  Water Hemlock). Source per plant from ASPCA + provincial toxic-plant lists;
  record a `safety_source` note. Add `pet_safe_only` / `kid_safe_only` kwargs to
  `search_plants`.
- `has_thorns INTEGER DEFAULT 0` (kid-proximity safety).
- `growth_habit_logic TEXT` ∈ `clumping | slow_spreader |
  aggressive_rhizomatous | self_seeding` — critical on small urban Edmonton
  lots (e.g. flag Canada Anemone). Add a "well-behaved on small lots" filter.
- Flip `pet_friendly` / `kid_friendly` to hard filters; add a "won't take over"
  goal. → `_SCHEMA_VERSION` 18.

## Chunk 3 — Year-round aesthetics  *(makes Year-round + Flowers-all-season real)*

- `winter_structure TEXT` ∈ `high_structure | seed_heads | minimal_presence`
  (e.g. Red-Osier Dogwood) + `winter_interest_only` kwarg.
- Per-season visual-interest scores
  (`visual_interest_spring/summer/fall/winter` INTEGER 0–3) → enables a real
  "interesting every season" balance + validation.
- Month-coded bloom (`bloom_month_start` / `bloom_month_end`, or a
  `bloom_months` CSV) — turns free-text `bloom_period` into a queryable
  "fill the bloom calendar," letting the generator's goal check actually repair
  bloom gaps for Flowers-all-season.
- Flip `year_round_interest` + `flowers_all_season` to backed. → bump 19.

## Chunk 4 — Right plant, right spot  *(ecological site matching)*

- `moisture_regime TEXT` ∈ `xeric | mesic | hydric` — ecological upgrade over
  the coarse existing `water_needs`; the primary field for matching a plant to
  a spot (rain garden vs. dry south slope).
- `soil_preference TEXT` ∈ `heavy_clay | loam | sandy_gravel` — Edmonton clay
  vs. the sandy pockets around St. Albert / Strathcona County.
- `salt_tolerance TEXT` ∈ `high | low` — vital for boulevard / roadside designs.
- Add kwargs and feed the site pin's measured conditions (the Site panel fetch)
  into generation; new goals: "rain garden (hydric)", "dry slope (xeric)",
  "boulevard (salt-tolerant)". → bump 20.

## Chunk 5 — Ecology, plant communities & sourcing

- **Host-plant filter:** expose the existing `plant_fauna` junction as a
  `search_plants` filter (e.g. `host_for_fauna_id`, `supports_specialist`) plus
  a fauna picker in the dialog and the LLM context. Mostly query + UI.
- `root_strategy TEXT` ∈ `taproot | fibrous | shallow_runners` — the mechanical
  data for assembling plant communities without root competition.
- **Community Builder:** given a centerpiece plant (e.g. a Saskatoon Berry),
  query plants that share its `hardiness_zone` / `sun_requirement` but bring a
  *complementary* `root_strategy` and vegetation layer (`plant_type`) to suggest
  a vertical stack — saved as a new **plant community**. This is woven into the
  *existing* plant-community system (`src/db/polycultures.py`,
  `get_companions`, the builder UI in `src/polyculture_panel.py`), not a
  separate concept — it drops results into the same communities the app already
  uses. Expose via the scripting API + a "Build a community around this plant"
  GUI action.
- `availability_class TEXT` ∈ `big_box | standard_nursery | native_specialist |
  rare_seed_only` — prevents "ghost gardens" of plants users can't buy
  (Home Depot vs. Salisbury/Greengate vs. ALCLA/Wild About Flowers vs. seed
  only). Low effort / no safety risk → can be pulled earlier as an easy win.
- `polyculture_tags` table (or a `goals` CSV column on `polycultures`) so the
  offline fallback selects communities by **tag** rather than name-substring
  matching — the single biggest lever for making the no-LLM path precise.
- Optional: a canonical `edible` / `food` use-key in the `plant_uses` junction
  to distinguish human-edible from merely bird-food, refining `food_producing`.
