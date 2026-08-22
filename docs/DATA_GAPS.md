# Data gaps — what the app cannot yet do because the data isn't there

The ledger of **seed-data debt**: things the code is ready for and the catalogue
is not. Kept version-free on purpose (it was `data_gaps_v1.44.md` until V2.35),
because the debt outlives any one release.

Two sections. The first is the original one — the **Generate Design goals**
(V1.44) that are honoured as an LLM *hint* because no column exists to filter
on. The second, added in V2.35, is the **photography and provenance** debt that
the 3D fidelity work exposed.

---

## Flower colour (V2.48)

**Status: 36 of 395 coloured species are checkable. The other 359 are a
genus-level guess, and now say so.**

`flower_color` has been on the row since schema v31, driving the 3D viewer's
florets. It was seeded per genus, which nothing displayed and therefore nobody
questioned until V2.47 turned it into a filter and the author noticed the
columbines:

| | |
|---|---|
| Genera with 3+ species sharing exactly one hex, before the fix | **32** |
| Rows whose common name contradicted their hex, before | **44** |
| Species now sourced `epithet` (the Latin states the colour) | 7 |
| Species now sourced `name` (the accepted common name states it) | 29 |
| Species still `estimated` (genus default, marked *not verified* in the UI) | 359 |
| Species with no recorded colour at all | 44 |

The column (`flower_colour_source`), the seeder
(`scripts/seed_flower_colour.py`), the validator
(`data_quality.validate_flower_colour`) and the "not verified" marker on both
the species page and the website are all in place.

### How to move this along (V2.51)

The paragraph above used to end at "what this needs is a flora and a network",
which is true and is not a next step. Asked directly — *"how can I move this
along, I read the data_gaps doc and wasn't sure what next steps to take"* — the
honest answer is that **the checking does not need a flora for most of it**. It
needs a photograph and thirty seconds, and 199 of the species already have the
photograph.

```bash
python scripts/colour_worklist.py --sheet colour-check.html
```

That writes a contact sheet: every still-guessed species that has a credited
photograph in the catalogue, grouped by how many siblings share its hex, worst
group first, with the claimed colour as a swatch under each image. Open it, and
the wrong ones are the ones where the swatch and the flower disagree. This is
the same failure the author caught by eye in the columbines, made systematic.

Then, for each one that disagreed, add a line to `CORRECTIONS` in
`scripts/seed_flower_colour.py` with the colour and the reason, run it, and bump
`_SCHEMA_VERSION`. `--paste` emits the blank lines to fill in; it deliberately
does not pre-fill a colour, because a value nobody looked at is exactly what
this backlog is made of.

**The order matters and the tool encodes it.** 81 of the 357 are grasses, sedges
and rushes and are excluded outright: they have no showy flower, so there is no
colour to get wrong. Of the 276 left, 110 sit in one of 25 genus groups where
three or more species carry one identical hex — those are single decisions
applied many times, and they are where the wrong answers concentrate. A species
holding a hex on its own was at least seen once.

| Batch | Species | What it costs |
|---|---|---|
| The 25 shared-hex groups, photographed | ~90 | one sitting with the contact sheet |
| The rest of the photographed backlog | ~109 | a second sitting |
| No photograph in the catalogue | 77 | needs a flora, or a photo first |

Two validator warnings are expected to stay: a genus that really is all one
colour (the goldenrods) keeps tripping the heuristic until somebody sources one
of its species. That is the right trade for a warning.

---

## Photographs and provenance (V2.35)

> **Catalogue size, V2.75: 430 species.** The `/434` denominators below are as-measured at V2.42 and are left as they were written — this repo corrects its ledger in place rather than rewriting history, and a table describing a past measurement is not a stale reference. Two species have been removed since (*Rudbeckia hirta* V2.74, *Helianthus giganteus* V2.75, both introduced or eastern) and two garden rows reclassified. **The live figures are printed by `python scripts/check_plant_data.py`**, which counts rather than remembers.

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
pair, and `verified` in the bench now means *both*.

> **Corrected in V2.42.** This said "every one of the 434 reads `estimated`
> today". It does not: `leaf_data_source` is **absent from all 434 records**, so
> a reseed writes the schema default `''` rather than `estimated`. The
> difference matters because `validate_morphology_provenance`'s error branch —
> the one that catches a record claiming `flora` with a blank citation — can
> never fire for leaves. It is a tripwire wired to nothing until the field is
> actually populated. The flower half of the pair *is* populated (307 records
> read `estimated`) and its check works. See [`BOTANY_FIELD_GUIDE.md`](BOTANY_FIELD_GUIDE.md) for what
to log, and which corrections actually change the render.

**Fauna morphology (v58, V2.36) — the same problem, one taxon over.** Until v58
an animal's appearance was computed from substrings of its common name in
`src/scene_wildlife.py`, so it could not be sourced, checked or corrected:

| | species | distinct appearances before v58 | after seeding |
|---|---|---|---|
| Bees | 69 | **12** (29 bumblebees identical) | 29 |
| Lepidoptera | 31 | **16** (Polyphemus = Cecropia = Isabella Tiger Moth) | 31 |

Every one of those values is now `morph_data_source: estimated` with a blank
citation — better than before and still not *checked*. `scripts/tune_fauna.py`
is where they get raised; see
[`FAUNA_FIELD_GUIDE.md`](FAUNA_FIELD_GUIDE.md) for what to log. Birds (24 → 16
looks), other insects and mammals still have no morphology columns at all.

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

---

## The occurrence harvest is capped, and the cap is not neutral (V2.77)

`scripts/seed_ecoregion_ranges.py` stops asking GBIF after
`MAX_RECORDS_PER_SPECIES = 6000` records per species. That was written as a
politeness bound, and it is: the first run got rate-limited and this is part of
why the second did not. What nobody checked is **what falls outside the
window**.

GBIF's default result order is newest-first. So for a plant with tens of
thousands of records, six thousand is the last few years and nothing before
them. Measured on the cache:

| | records | specimens | year range |
|---|---|---|---|
| the 16 species at the cap | 89,964 | **31** | **2021-2026** |
| the other 418 | 401,877 | 54,238 | full historical record |

*Amelanchier alnifolia* holds 6,000 records, **two** of them herbarium
specimens, none dated before 2024. Saskatoon Berry has been collected in this
province for a century; the harvest simply never reached any of it.

**The species affected**, by cached count at or above 5,998: *Achillea
millefolium, Amelanchier alnifolia, Arctostaphylos uva-ursi, Chamaenerion
angustifolium, Cornus canadensis, Cornus sericea, Elaeagnus commutata, Fragaria
virginiana, Gaillardia aristata, Geum triflorum, Maianthemum stellatum, Populus
tremuloides, Prunus virginiana, Pulsatilla nuttalliana, Shepherdia canadensis,
Thermopsis rhombifolia.* Every one is a common, widely photographed plant,
which is exactly why it hit the cap.

**What this does and does not affect.** Each of these still has ~5,600
georeferenced records, which is far past the three-record floor everywhere they
grow, so the *shipped ranges* are unlikely to move — but "unlikely" is not
"checked", and `--from-cache` exists so the check costs no network. What it
plainly does affect is any map drawn from specimens: sixteen of the catalogue's
best-known plants would render blank, and blank for our reason rather than the
herbaria's.

**Two things changed rather than one.** `--specimen-pass` asks GBIF for
`PRESERVED_SPECIMEN` records as their own query, which is the only way to reach
records the cap cut; and `fetch_occurrences(truncated=...)` now reports when a
harvest stopped because *we* stopped asking rather than because GBIF ran out.
The second is the more important: a truncated harvest and a complete one looked
identical once cached, which is how this went unnoticed through two increments
of work on exactly this data.

## Taxonomy: no backbone, and the names that show it (V2.75)

**Status: the catalogue has no authority field, no synonym list and no taxon
key of any kind.** A `scientific_name` is a free string checked by one regex
(`data_quality._SCI_NAME_RE`). There is no mechanism by which the app could
know that two rows are one taxon, or that a binomial has been superseded.

An outside botanical review named this directly: *"A lot of species are listed
using out-of-date names (e.g.: the Old World species, instead of the separate
North American species)."* Checked, and true. The confirmed cases:

| Shipped as | The problem |
|---|---|
| `Achillea millefolium` | Ships **beside its own segregate**, `Achillea borealis` ("Boreal Yarrow"), and a third row `Achillea alpina` — all three claiming AB,SK. The North American plant is usually treated as `var. occidentalis` / formerly `A. lanulosa`; the bare Eurasian binomial standing next to its own segregate is the clearest case in the catalogue |
| `Fragaria vesca` | No infraspecific rank. North American material is `subsp. americana` / `bracteata`; the bare name is the European type |
| `Prunella vulgaris` | No infraspecific rank. The native North American plant is `ssp. lanceolata`; the type is European and introduced here |
| `Juniperus communis` | No infraspecific rank. North American material is `var. depressa`. Circumboreal, so the species-level claim is defensible; the rank is still missing |
| `Aster alpinus` | *Aster* s.str. is legitimately retained, but this is a widely sold Eurasian rock-garden plant, and it carries **72 Aspen Parkland occurrence records** — a montane species with parkland records, which is exactly the pattern a garden escape makes |
| `Deschampsia caespitosa` | An orthographic variant. FNA and POWO use `cespitosa`, and the accepted spelling appears **nowhere in this repo**, so any lookup keyed on it misses silently |
| `Solidago rigida` / `Oligoneuron rigidum` | One taxon, two published species pages, **disagreeing about nativity**. See the Backlog |

**What the catalogue got right, and it is most of the work.** The genus-level
segregations are done: Aster → *Symphyotrichum* (10 rows) with *Eurybia*,
*Doellingeria* and *Canadanthus* split out correctly; Polygonum →
*Persicaria*; Zigadenus → *Anticlea*; Disporum → *Prosartes*; Potentilla →
*Comarum*. `Pulsatilla nuttalliana` is the correct North American name, not
`Anemone patens` or `Pulsatilla patens`. No `Agropyron`, no `Elytrigia`, no
`Bromus inermis` and no `Poa pratensis` anywhere. This is a species-level
residue on a genus-level job that was done properly.

**Next step:** `scripts/fetch_flora_nativity.py` (V2.75). VASCAN returns the
accepted name and synonym status in the same request that answers nativity, so
one ~430-request run produces the whole list. **Renaming is not a data job** —
it moves plant ids, the `plant_fauna_master.json` keys that name a plant by
common name, and public URLs people may have linked to. Its own increment.
