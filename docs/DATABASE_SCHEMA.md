# Site & Pattern Database Schema

Site & Pattern stores its plant catalogue and saved plant communities in a
local SQLite database. This is **not** the project file (see
[`PROJECT_FILE_FORMAT.md`](PROJECT_FILE_FORMAT.md)) — it's the shared,
seeded reference data every project draws from.

- **DDL:** [`src/db/schema.sql`](../src/db/schema.sql) (authoritative;
  loaded on every `init_db`)
- **Access layer:** [`src/db/plants.py`](../src/db/plants.py),
  [`polycultures.py`](../src/db/polycultures.py),
  [`recipes.py`](../src/db/recipes.py),
  [`structures.py`](../src/db/structures.py),
  [`fauna.py`](../src/db/fauna.py)
- **Current schema version:** `59` (`src/db/plants.py:_SCHEMA_VERSION` — the
  authoritative value; this doc's narrative may lag, the code wins)
- **Location:**
  - Linux: `~/.local/share/Site & Pattern/permadesign.db`
  - Windows: `%APPDATA%/Site & Pattern/`
  - macOS: `~/Library/Application Support/Site & Pattern/`

  The DB is **never** stored inside the source tree — `tests/test_polycultures.py`
  asserts this.

Structure definitions (bee hotels, ponds, …) are **not** in SQLite —
they're a hard-coded list in `src/db/structures.py`.

---

## Tables

### `plants` — the catalogue
One row per species. Key columns (full list in the DDL):

| column | notes |
|---|---|
| `id` | PK, referenced by project `plant_id` |
| `common_name`, `scientific_name` | |
| `plant_type` | tree, shrub, herb, groundcover, vine, root |
| `hardiness_zone_min/max` | |
| `sun_requirement` | full_sun, partial_shade, full_shade |
| `water_needs` | low, medium, high |
| `permaculture_uses` | comma-separated tag blob (legacy; see `plant_uses`) |
| `spacing_meters`, `mature_height_meters`, `mature_canopy_m` | `mature_canopy_m` NULL ⇒ heuristic (1.5× spacing) in `get_plant` |
| `bloom_period`, `fruit_period` | e.g. "May–June" |
| `native_to_alberta` | 1 = native |
| `edible_parts`, `deciduous_evergreen`, `soil_ph_min/max`, `perennial_or_annual` | |
| `marker_color` | custom map-marker hex |
| `growth_rate`, `years_to_maturity`, `growth_curve` | succession/timeline (curve: fast_early \| steady \| slow_start) |
| `ab_ecoregion` | comma-separated AB ecoregion tags |
| `leaf_shape`, `leaf_size_cm`, `leaf_arrangement` | botanical morphology (v47). `leaf_size_cm` sets 3D foliage grain in real metres — a 20 cm bur oak leaf reads coarse, a 2 cm dwarf-birch leaf fine, at the same crown size |
| `bark_color`, `fall_color` | hex (v47). The species' real trunk colour and autumn colour; `fall_color` empty = evergreen or no colouring, an honest empty rather than a guess |
| `branching` | excurrent \| decurrent \| multi_stem \| suckering \| arching \| prostrate \| rosette (v47) — woody habit |
| `growth_form` | herbaceous habit (v48). The **source of truth** for which 3D archetype a non-woody plant gets; the viewer's genus table is now only a fallback |
| `fruit_form` | fruit SHAPE (v49) — berry \| strig \| raceme \| cherry \| pome \| hip \| strawberry \| aggregate \| flat_cluster. The companion to `fruit_color`: before it, every fleshy fruit in the catalogue drew as the same sphere sprite |
| `bark_texture` | smooth \| furrowed \| papery \| shaggy \| scaly (v52). Which procedural bark grain the 3D viewer draws. Bark is how a woody plant is identified in winter, and one grain served all of them; note that within *Betula* only paper birch is `papery` — the kind of difference a genus table cannot hold. Seeded in `scripts/seed_surface_morphology.py` |
| `leaf_surface` | matte \| glossy \| pubescent \| glaucous (v52). Recorded only where the character is distinctive enough to draw — a silvery wolf-willow, a waxy bog blueberry, a glossy Oregon-grape. Empty is the common case and the honest default |
| `inflorescence_form` | turkey_foot \| one_sided_raceme \| open_panicle \| contracted_spike \| nodding_raceme \| bristly \| sedge_cluster \| rush_umbel \| cattail_spike (v52). **The graminoid field mark.** All 79 grasses, sedges and rushes carried `flower_form: plume` and drew one generic spray, while a grass is identified by its seed head — a big bluestem is *named* for its turkey-foot. Deliberately separate from `flower_form`, which stays `plume` because it feeds pollinator logic where a wind-pollinated grass correctly offers a bee nothing. Seeded in `scripts/seed_inflorescence_morphology.py`, so a strawberry, a rose hip and a chokecherry raceme were all "red dot". Empty on dry-fruited species, which draw nothing |
| `flower_arch` | solitary \| raceme \| spike \| panicle \| corymb \| umbel \| head \| cyme \| whorl (v53). **Where the florets sit in space**, which is most of a forb's silhouette — a goldenrod's plume, a yarrow's flat corymb and a lupine's spike are three architectures, not three textures. Drives `html/scene3d/15-florets.js`; empty falls back to the flat billboard |
| `flower_symmetry` | radial \| bilateral (v53). A pea and a daisy are not the same flower, and drawing a bilateral one radially is the commonest way a generated flower gives itself away |
| `petal_shape` | narrow \| oval \| notched \| tubular \| lipped (v53) |
| `petal_count` | Rays or petals on ONE floret (v53). **0 is a real value** — the rayless composites (thistle, sage, pussytoes) have none, and drawing them five is invented detail |
| `florets_per_head` | How many florets the drawn unit carries (v53): 40 on a daisy's head, 12 up a spike, and for the rayless composites whose drawn unit is the whole spray, the hundreds of heads in a goldenrod plume |
| `flower_diameter_cm` | ONE floret across (v53). The most valuable number the catalogue was missing: bloom size used to be derived from *canopy*, so a pasqueflower and a sunflower scaled with the plant rather than with the flower |
| `flower_center_color` | The disc/eye (v53). A black-eyed Susan **is** its dark disc; it was a yellow blob |
| `flower_height_frac` | How far the bloom is held above the foliage, as a fraction of height (v53) |
| `stem_branching` | unbranched \| branched_above \| branched_throughout (v53). **Read since V2.34**: the stem is a forked skeleton, and a goldenrod's silhouette IS its two orders of branching. Only the `erect` and `clump` growth forms have a stem to fork |
| `basal_rosette` | 0/1 (v53) |
| `flowering_stems` | How many inflorescences a MATURE plant carries (v54). Bloom display used to be sized off the plant's *canopy*, which is a proxy for spread and not for flowering: a pasqueflower holds three and a mature bergamot twenty-eight. **No flora records this** — the seeded values follow from the branching habit and are meant to be corrected in the field with `scripts/tune_morphology.py`. Empty falls back to a count derived from `stem_branching` |
| `flower_data_source` | measured \| flora \| photo \| estimated (v55). **Where each flower number came from.** The seeder's values are genus-level botanical judgement, which is a reasonable start and is not a measurement; reporting "307 described" as though it meant 307 verified is what P9 forbids. Raised by `scripts/tune_morphology.py` as species are actually checked |
| `flower_data_citation` | Free text (v56). **WHICH source** — `FNA vol. 21`, `Budd's 442`, `my yard 2026-07-12`. `flower_data_source` says what kind of source; "read in a flora" that does not name the flora is not a citation. Blank from the seeder on purpose: naming a book nobody opened for that species would be worse than an empty field. Same shape as `safety_source`. See [`DATA_SOURCES.md`](DATA_SOURCES.md) |
| `leaf_data_source` | measured \| flora \| photo \| estimated (v57). The same question for the **leaf and habit** characters — `leaf_shape`, `leaf_size_cm`, `leaf_arrangement`, `leaf_surface`, `growth_form`, `branching`, `mature_height_m`. It matters more here than for flowers: those columns are blank until somebody describes a species, whereas every one of these was seeded with a genus-level estimate for all 434 records, so a guess is invisible rather than absent. Kept separate from the flower pair because the two get verified in different sittings from different sources — a photograph settles petal count, a flora settles leaf length |
| `leaf_data_citation` | Free text (v57). As `flower_data_citation`. A claimed source with no citation is an **error** in the data-quality gate, not a warning |

Morphology is authored in two companion scripts, each documenting its fields
and where the values come from:
[`scripts/seed_woody_morphology.py`](../scripts/seed_woody_morphology.py) for the
69 trees and shrubs (v47), and
[`scripts/seed_non_woody_morphology.py`](../scripts/seed_non_woody_morphology.py)
for the 365 wildflowers, herbs, graminoids, aquatics, groundcovers and vines
(v48). Between them every species in the catalogue has morphology. Woody rows
carry `bark_color`/`fall_color`/`branching` and non-woody rows carry
`growth_form`; each leaves the other empty, because a plant has one habit or the
other and an honest empty beats an invented value.

### `companion_friends` / `companion_enemies`
Symmetric plant↔plant companion relationships (`plant_id_a`, `plant_id_b`).

### `planting_calendar`
12 rows per plant: `(plant_id, month, status, notes)`. `status` ∈
`dormant, start_indoors, direct_sow, transplant, growing, harvest, pruning`.

### `polycultures` / `polyculture_members`
Saved **spatial** plant communities. Members carry `offset_x`/`offset_y`
(metres from the community centre), a `layer`, and a JSON `functions`
array. `parent_id` supports variations. `origin` (schema v46) marks row
provenance — `'seed'` for the shipped examples, `'user'` for communities
authored in the builder; **only `'seed'` rows are wiped by the reseed**,
so user communities survive schema bumps (their member `plant_id`s are
re-pointed at the reseeded catalogue by name, since plant ids shift).

### `polyculture_recipes` / `polyculture_recipe_members`
**Ratio-only** mixes (no spatial layout): members carry an integer
`weight` instead of offsets. Drive ratio assignment for row/grid/circle
placement.

### `uses` / `plant_uses` (schema v13)
Canonical permaculture-use vocabulary (`uses.key`/`label`/`category`) and
the plant↔use junction that replaced substring matching on the legacy
`plants.permaculture_uses` blob for filter queries.

### `plant_ecoregions` (schema v59, V2.38)

Where a species is actually **recorded** growing, and how well attested each
claim is: one row per species per geographic ecoregion, carrying the
georeferenced record count (`occurrences`), a `confidence` band
(`high`/`medium`/`low`) and the `source` of the run.

It exists because `plants.ecoregion` did not have any of that. Those tags were
generated heuristically and never sourced, and a user caught the consequence:
Saskatoon Berry — a defining Aspen Parkland shrub — carried only
`mixedgrass_prairie,moist_mixedgrass`. Across the catalogue,
`moist_mixedgrass` sat on 246 of 434 plants and `aspen_parkland` on 136, in an
Alberta-first app centred on Edmonton, with 39 native trees and shrubs carrying
no parkland tag at all.

Derived by `scripts/seed_ecoregion_ranges.py` from GBIF occurrence records
(dev-time, run-once, commit the result) into `data/plant_ecoregions.json`,
which the reseed loads. The file is keyed by **scientific name**, because plant
ids are not stable across a reseed; ids are resolved at seed time.

Two rules the table encodes:

- **Geographic ecoregions only.** `riparian` and `wet_meadow` are site-scale
  moisture niches — no coordinate can assert that a species grows in wet ground
  — so those tags stay in `plants.ecoregion` and `_attach_ecoregions` carries
  them through untouched.
- **The column stays.** A species the derivation has not covered keeps its
  existing tags, so the catalogue never gets *smaller* because a download has
  not been run. This is the opposite of the v37 `permaculture_uses` move, which
  dropped the column outright — there, the junction covered everything on day
  one.

Read-side synthesis (`_attach_ecoregions` in `src/db/plants.py`) overlays the
derived rows onto each plant dict's `ecoregion` string, so every existing
consumer improves without a change at the call site, and adds
`ecoregion_evidence` — the rows with their counts — for anything that wants to
show how good the claim is (P9).

### `fauna` / `plant_fauna` (schema v13)
Native lepidoptera / bird / bee registry and the plant↔fauna junction,
tagged by `relationship` (`larval_host, nectar, pollen, seed_food,
fruit_food, nesting, cover`) and `specificity` (`specialist`/`generalist`).
Powers the wildlife column in the plant browser and the
lepidoptera-supported count in the habitat score.

### `plant_photos` (schema v55, F70)
Many photographs per species, each in a **named slot** — `habit`, `flower`,
`leaf`, `fruit`, `bark_stem`, `winter`, `seedling`. `plants.image_url` was one
slot, and that single fact is most of what was wrong with the app's photography:
`scripts/fetch_inaturalist_images.py` takes the first photo with a
redistributable licence, and on iNaturalist that is nearly always a flower
macro — the frame that identifies a plant to a botanist, and the least useful
one for deciding whether you want it in your yard.

Two things it is careful about:

- **Keyed by `scientific_name`, never `plant_id`.** Ids are not stable across a
  reseed, so an id-keyed photo table would silently re-point photos at the wrong
  species on some future schema bump.
- **`origin` decides what a reseed destroys** — the `polycultures` v46 pattern.
  `'seed'` rows are wiped and re-seeded; `'user'` rows never are. That single
  distinction is the whole of F72: the obvious place for a person's own
  photograph is `plants.image_url`, and it is a trap.

`plants.image_url` / `image_attribution` / `image_license` are **synthesized on
read** from the best available slot (`src/db/plants.py:_attach_photos`), the same
way `permaculture_uses` has been synthesized from `plant_uses` since v37 — so
every existing consumer keeps working and gains better photographs for free. A
person's own photo beats a shipped one in the same slot. Query API:
`src/db/photos.py`. Coverage is reported by
`src/data_quality.py:validate_photo_coverage`.

### `relationship_edges` — a VIEW, not a table (schema v51, F7)
The unified edges layer. One `UNION ALL` over `plant_fauna` (kind = the
`relationship` value), `companion_friends`, `companion_enemies` and shared
`polyculture_members` (kind `co_planted`, one row per unordered pair), giving
`(kind, a_type, a_id, b_type, b_id, directed, detail, source)`. Read through
the query API in [`relationships.py`](../src/db/relationships.py) — never
queried directly by feature code.

Deliberately a **view**: the per-relationship tables stay the single source of
truth, so there is no second copy to drift, no seeder to change and nothing new
for the reseed to wipe. `schema.sql` DROPs and recreates it on every `init_db`,
so the definition can evolve without a migration — only the `_SCHEMA_VERSION`
bump that any `schema.sql` change requires.

Derived edges (`shared_fauna` — two plants that feed the same animal) are
computed in Python and carry `evidence='derived'`; only documented records
appear in the view.

### `climate_cache` (schema v14)
One row per ~1 km² (`lat_q`, `lng_q` = lat/lng × 100, rounded) caching
growing-degree-day + frost-window stats from Open-Meteo. Never
auto-expires.

### Indexes
On `plants(plant_type)`, `plants(zone range)`, `plants(native_to_alberta)`,
`planting_calendar(plant_id)`, the two member junctions, and the three
`plant_fauna` columns. See the bottom of the DDL.

---

## Seeding & reseed

`init_db` (in `src/db/plants.py`) creates the tables, then **reseeds**
when the row count is low or the stored schema version is older than
`_SCHEMA_VERSION`. Seed data ships as JSON in `data/`:

- `data/plants_master.json`
- `data/garden_plants.json`
- `data/fauna_master.json`
- `data/plant_fauna_master.json`
- `data/plant_ecoregions.json` (schema v59) — ships as an **empty envelope**
  until `scripts/seed_ecoregion_ranges.py` has been run, so the format is
  documented and the first real run produces a reviewable diff rather than an
  unexplained new file. An empty (or missing) `species` map means "nothing
  derived yet" and every species keeps the tags in `plants.ecoregion`.

The reseed wipes and repopulates: `plants`, `planting_calendar`,
`companion_friends`, `companion_enemies`, `uses`, `plant_uses`,
`plant_ecoregions`, `fauna`,
`plant_fauna`, `bee_attributes`, `lepidoptera_attributes`, `nurseries`,
plus the derived caches (`climate_cache`, `wind_cache`,
`shade_zone_cache`). `polycultures` / `polyculture_members` are wiped
**only where `origin='seed'`** (schema v46) — user-authored communities
are never touched by the reseed.

> FK constraints are ON at runtime but disabled during the bulk reseed
> (Python 3.14 enforces FKs at statement time, not commit time).

### Fauna morphology (schema v58, V2.36)

`bee_attributes` and `lepidoptera_attributes` were purely ecological — nesting
habit, flight season, host genera. What an animal *looked like* was computed in
`src/scene_wildlife.py` from substrings of its common name, so 69 bees rendered
as 12 animals (29 bumblebees identical) and 31 lepidoptera as 16, none of it
sourced or correctable without editing code. v58 puts it in the catalogue.

| Table | Columns |
|---|---|
| `bee_attributes` | `body_length_mm`, `build`, `hair_colour`, `integument_colour`, `metallic`, `scopa_position`, `wing_tint`, **`band_pattern`** |
| `lepidoptera_attributes` | `wingspan_min_mm` + `wingspan_max_mm`, `forewing_colour`, `hindwing_colour`, `margin_colour`, `wing_shape`, `wing_pattern`, `eyespot_count`, `resting_posture`, **`flight_style`** |
| both | `morph_data_source`, `morph_data_citation` |

**`band_pattern`** is comma-separated colour tokens for **thorax + T1…T6**
(`yellow,yellow,orange,orange,yellow,black,black`) — named tokens rather than
hex because that is how every bumblebee key is written; the token→hex table is
`data_quality.BAND_COLOUR_HEX`. It is the field that makes 29 *Bombus* into 29
animals. **The wingspan is a RANGE** because that is what guides print, and
inventing a midpoint is the false precision P9 forbids; the viewer takes the mid
and that collapse is a rendering decision, not a data one. It is also the fauna
data's first real measurement — `size` was a hand-tuned 0.5–1.25 multiplier.

Provenance follows the plants' rule: a claimed source with no citation is an
**error** in the gate (`validate_fauna_morphology`). Everything ships
`estimated`. Vocabularies live in `src/data_quality.py`; the bench is
`scripts/tune_fauna.py`, and the terms are drawn in
[`FAUNA_FIELD_GUIDE.md`](FAUNA_FIELD_GUIDE.md).

Both tables are already wiped and repopulated with `fauna` on reseed, so v58
needed no new wipe entry.

---

## Changing the schema (checklist)

From `CLAUDE.md` — follow exactly so existing installs pick up changes:

1. Edit `src/db/schema.sql`.
2. **Bump `_SCHEMA_VERSION`** in `src/db/plants.py` (this triggers the
   one-time reseed on the user's next launch).
3. If you added a dependent table, add a `DELETE FROM <table>` to the
   reseed block in `init_db` (or it accumulates stale rows across
   reseeds).
4. Add/extend a seeding helper following the `_seed_uses_lookup` /
   `_seed_fauna` pattern.
5. Add tests under `tests/` using the temp-DB pattern from
   `test_polycultures.py` / `test_uses_junction.py`.
6. Run `python -m unittest discover -s tests -t .`.

Forgetting step 2 means existing installs silently keep the old schema —
no new tables, no new rows.
