# Data gaps — what the app cannot yet do because the data isn't there

The ledger of **seed-data debt**: things the code is ready for and the catalogue
is not. Kept version-free on purpose (it was `data_gaps_v1.44.md` until V2.35),
because the debt outlives any one release.

Two sections. The first is the original one — the **Generate Design goals**
(V1.44) that are honoured as an LLM *hint* because no column exists to filter
on. The second, added in V2.35, is the **photography and provenance** debt that
the 3D fidelity work exposed.

---

## Photographs and provenance (V2.35)

**Photo coverage.** `src/data_quality.py:validate_photo_coverage` counts this on
every run of the gate, so the numbers below are live rather than a snapshot:

| | |
|---|---|
| Plants with no photograph at all | **111 of 434** |
| Fauna with none | **84 of 142** — including **62 of 69 bees** |
| Species with a `habit` shot (the whole plant, with scale) | **0** |
| Photographs shipped but never *sorted* into a slot (V2.36) | **323** — the triage queue |

The bee number has a specific and deliberate cause: bee photos are held to a
stricter licence bar than everything else (CC0/CC-BY only, no ShareAlike — the
F37 decision), and most iNaturalist bee photos are NonCommercial. That is why
the V2.33 bee models exist. It is a policy gap, not an oversight.

The `habit` zero is the F70 diagnosis made countable: `plants.image_url` was one
slot, and `scripts/fetch_inaturalist_images.py` fills it with *the first photo
whose licence is redistributable* — which on iNaturalist is nearly always a
flower macro. Every photo the app has is the frame that identifies a plant to a
botanist, and none is the frame that tells you whether you want it in your yard.

**Fill it with:** `scripts/import_photos.py` (a folder of your own
`Genus_species_slot.jpg`) or the photo strip in `scripts/tune_morphology.py`.

**Sort what is already here first (V2.36).** The 323 shipped photographs now
appear in the bench in an `unsorted` bucket rather than being assumed to be
flower macros, and one click files each into its real slot. The counter's
"sorted" and "habit" figures therefore start at **zero and mean something**,
which the old "323 with a photo" did not. Where a slot stays empty, *find
candidates* pulls the species' wider openly-licensed iNaturalist set (usually
~12 photos) so a habit shot can be chosen by looking rather than by going
outside — the only realistic route off zero, since triage cannot turn a
catalogue of flower macros into whole-plant photographs.

**Flower-morphology provenance.** 307 of 311 flowering species carry a described
flower (schema v53/v54) and **almost none of it has been verified**. The
`flower_data_source` column records the difference:

| value | meaning | count today |
|---|---|---|
| `estimated` | the family-first seeder's genus default | **307** |
| `photo` | counted or judged off a photograph | 0 |
| `flora` | read from a published description | 0 |
| `measured` | a ruler on the plant | 0 |

Quoting "99% described" as though it meant 99% verified is exactly what P9
forbids, which is why the two are now separate numbers.

**And WHICH source (v56, V2.36).** `flower_data_source` records what *kind* of
source a number came from; `flower_data_citation` records which one — free text,
per species, the same shape as `safety_source`. "Read in a flora" that does not
name the flora is not a citation, and it stops being good enough the moment
values start coming out of published descriptions instead of genus conventions.
Blank everywhere today, deliberately: the seeder writes no citation rather than
naming a book nobody opened for that species.

**Leaf and habit provenance (v57, V2.36) — the bigger of the two gaps.** The
flower columns are at least *blank* until somebody describes a species. The leaf
and habit columns are not:

| field | blank | the rest is… |
|---|---|---|
| `leaf_shape` | 0 / 434 | a genus-level estimate |
| `leaf_size_cm` | 0 / 434 | a genus-level estimate |
| `leaf_arrangement` | 0 / 434 | a genus-level estimate |
| `mature_height_m` | 0 / 434 | a genus-level estimate |
| `growth_form` | 69 / 434 | a genus-level estimate |
| `leaf_surface` | 352 / 434 | authored where distinctive |
| `branching` | 365 / 434 | woody species only |

Nothing there is missing in a way anybody can see, and every one of them changes
what the 3D viewer draws — `growth_form` picks the plant's entire body. So
`leaf_data_source` / `leaf_data_citation` carry the same rule as the flower
pair, and `verified` in the bench now means *both*. Every one of the 434 reads
`estimated` today. See [`BOTANY_FIELD_GUIDE.md`](BOTANY_FIELD_GUIDE.md) for what
to log, and which corrections actually change the render.

**Where the real numbers are.** They exist, and they are not importable: Flora
of North America gives ray counts and laminae lengths outright (vols 19–21 cover
most prairie forbs) and is free to *read* but copyrighted, so a bulk scrape is
out. Budd's *Flora of the Canadian Prairie Provinces* is the regional
equivalent. TRY and BIEN are leaf/seed/height traits — floral morphology is
sparse there and mostly not redistributable. A person reading a description and
typing "13 rays" is recording a fact, and facts are nobody's property; that is
the loop `tune_morphology.py`'s "look it up" links exist to make fast.

**The four numbers no flora publishes**, and so the four that need a plant in
front of you: flower diameter in cm, petals or rays on one floret, flowering
stems on a mature plant, and how far the bloom sits above the foliage.

---

## Generate Design goals (V1.44)

## How goals are backed today

| Goal (`key`) | Backed now? | Mechanism this release |
|---|---|---|
| `native_only` | ✅ | hard filter `native_only=True` (`plants.native_to_alberta`) |
| `pollinator` | ✅ | hard filter `pollinator_only=True` (`plant_uses` junction) |
| `food_producing` | ✅ | hard filter `edible_only=True` (`plants.edible_parts`) |
| `flowers_all_season` | ⛅ hint only | `bloom_period` is free text, not month-queryable |
| `pet_friendly` | ✅ denylist (chunk 2) | hard filter `pet_safe_only=True` excludes `toxicity_pets ∈ {low,high}`; unassessed pass (caveat) |
| `kid_friendly` | ✅ denylist (chunk 2) | hard filter `kid_safe_only=True` excludes `toxicity_humans ∈ {low,high}` or `has_thorns` |
| `well_behaved` | ✅ denylist (chunk 2) | hard filter `well_behaved_only=True` excludes aggressive `spread_habit` |
| `low_cost` | ✅ filter (V1.45) | hard filter `common_only=True` (excludes seed-only/rare) + the dialog Budget field caps the estimated total |
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

## Chunk 2 — Safety & small-lot fit  *(makes Pet/Kid friendly real)* — ✅ SHIPPED (schema v18)

Curated by `scripts/apply_safety_tags.py` — a re-runnable, idempotent, sourced
denylist (classifications from ASPCA + poison-control references, noted per
record in `safety_source`). What shipped:

- **Split toxicity, not a single `safety_rating`.** `plants` gained
  `toxicity_pets` and `toxicity_humans`, each `'' (unassessed) | none | low |
  high`. The split (vs. the originally sketched single field) lets a plant be
  *toxic to pets yet edible for people* — e.g. wild onion/chives and yarrow are
  flagged pets-only, so they fail Pet-friendly but still pass Kid-friendly.
- `has_thorns INTEGER DEFAULT 0` — kid-proximity safety (rose, hawthorn,
  raspberry, buffaloberry, gooseberry, thistle).
- `spread_habit TEXT` ∈ `clumping | slow_spreader | aggressive_rhizomatous |
  self_seeding` (the doc's `growth_habit_logic`) — flags Canada Anemone, mints,
  horsetails, Canada goldenrod, locoweeds, etc.
- `search_plants` gained `pet_safe_only` / `kid_safe_only` / `well_behaved_only`;
  `pet_friendly` / `kid_friendly` flipped to backed filters and a new
  **`well_behaved`** ("won't take over the yard") goal added. `_SCHEMA_VERSION`
  → **18**.

**Denylist semantics (important).** Per the "never default to safe" rule above,
the filters exclude only plants we have *classified* toxic/thorny/aggressive;
the large unassessed remainder still appears. "Pet/Kid friendly" therefore means
"no *known* hazard," not a guarantee — surfaced as a `Goal.caveat` (dialog
tooltip + a generation-warning advisory). Safety-critical natives in the
catalogue are covered, including **death camas (`Anticlea`)**, golden bean,
larkspur, baneberry, milkweeds, dogbane, nightshade and the cyanogenic `Prunus`
cherries (toxic foliage/pits, edible fruit — so they stay in *food* results
while dropping out of pet/kid-safe).

**Still open (future):** broaden coverage beyond the curated denylist (common
fruit trees with cyanogenic seeds such as `Malus` are intentionally left
unassessed for now); optionally promote positive `none` assertions if an
allowlist mode is ever wanted.

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
- ✅ **Shipped V1.45 (schema v19) — Sourcing & Budget.** `availability_class`
  (`big_box | garden_centre | native_specialist | seed_or_plug | rare`) — to
  prevent "ghost gardens" of plants users can't buy — plus a price *range*
  (`price_low_cad` / `price_high_cad`, defaulted by `plant_type` with curated
  overrides) and `sourcing_notes`, seeded by the re-runnable
  `scripts/apply_sourcing_data.py`. Wired: `search_plants(max_unit_price,
  common_only)`, the `src/sourcing.py` cost-estimate + budget-trim helpers, a
  `low_cost` goal, a "Budget $" field in the generate dialog, `--budget` on the
  CLI, and an estimated-cost line in the analysis panel. Prices are *estimates*
  (ranges, AB retail, as-of year), surfaced with that disclaimer.
- `polyculture_tags` table (or a `goals` CSV column on `polycultures`) so the
  offline fallback selects communities by **tag** rather than name-substring
  matching — the single biggest lever for making the no-LLM path precise.
- Optional: a canonical `edible` / `food` use-key in the `plant_uses` junction
  to distinguish human-edible from merely bird-food, refining `food_producing`.
