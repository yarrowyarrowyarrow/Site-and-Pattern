---
name: seed-data
description: Use when editing shipped seed JSON in data/ (plants_master.json, garden_plants.json, fauna_master.json, plant_fauna_master.json, bee_attributes_master.json, lepidoptera_attributes_master.json, nurseries_master.json, *_fallback_prairie.json), adding a plant or fauna entry, running the data-quality gate, or applying provenance/safety/sourcing tags. Covers required fields, which file flows into which table, the mandatory schema-version bump, and the P12 Indigenous-knowledge hard rule.
---

# Editing shipped seed data (Site & Pattern)

## Purpose / when to use

Everything in `data/*.json` is **shipped reference data** that the app reseeds
into the SQLite DB on launch (see the `schema-change` skill for the reseed
mechanics). Editing it is how you add plants, fauna, and their relationships, or
fix a value everyone should get. Use this skill when adding/changing entries in
any of the files below, or when the data-quality gate fails.

**HARD RULE — P12 (read first).** The plant-use / traditions space is the
highest-risk area in this whole app. Do **not** encode, operationalize, or
redistribute Indigenous ecological knowledge, plant-use traditions, or
land-management frameworks in seed data, field labels, `notes`, or use tags
**without free, prior, and informed consent** from the relevant communities.
The project has already *removed* such content on purpose: the v16/v17 schema
changelog in `src/db/plants.py` records "First Nations Medicine Wheel" →
"Native Prairie Aromatics", "Medicinal Herb Circle" → "Aromatic Herb Circle",
and "Red Indian Paintbrush" → "Common Paintbrush". Keep it that way. If a task
points toward encoding such knowledge, **stop and raise it with the user** —
treat any reference as directional only.

## Seed-data change ⇒ schema-version bump (non-negotiable)

Per CLAUDE.md, **any meaningful change to a seeded JSON file requires bumping
`_SCHEMA_VERSION` in `src/db/plants.py`.** The reseed only runs when the stored
version is older than `_SCHEMA_VERSION` (or the plant count is `< 100`), so
without a bump existing installs never pick up your rows. Do the bump and add a
one-line changelog comment above the constant (the file's history is full of
"no DDL — reseed to pick up …" entries). See the `schema-change` skill for the
full protocol. Current value in this session: `_SCHEMA_VERSION = 84`.

**Nativity is the weakest claim in the seed data, and V2.75 retired the thing
that generated it.** `native_provinces` was written by
`scripts/tag_prairie_provenance.py` from a hand-authored `native_to_alberta`
boolean plus the plant's ecoregion tags — and V2.72/73 replaced that vocabulary
underneath it, so a re-run would have moved **237 of 431 species**. The script
now refuses to run without an explicit override, and
`data_quality.validate_provenance_generator` fails the build if its vocabulary
drifts again. Do not hand-edit `native_provinces` to "fix" a row.

**V2.80: the replacement ran.** The author downloaded VASCAN's Darwin Core
Archive and `scripts/fetch_flora_nativity.py --from-archive <path>` read it with
no network; `scripts/ingest_flora_nativity.py` reports, and `--apply` writes.
414 of 434 species now carry `native_provinces_source = "flora"` and 34 province
lists were narrowed where a published flora disagreed with the ecoregion
inference. Three things it deliberately does not touch, and each has its own
route: removals go through `data/excluded_taxa.json` with an authority (V2.74),
renames are their own increment (they move plant ids, `plant_fauna_master.json`
keys and public URLs), and `undetermined` is the archive reader failing to
follow a lineage rather than a finding about a plant -- run
`--explain "<species>"` on those before deciding anything. Those ~20 keep **no**
source and go on naming the heuristic, which for them is still true.

**Narrowing `native_provinces` means correcting `native_to_alberta` too.** They
are separate columns and the second is what the native filter and the Habitat
Value Score actually read; changing one alone leaves two fields in a row
contradicting each other, with the score reading the stale one. Note some rows
carry `"1?"` -- native to Alberta, editorially uncertain -- which `db/plants.py`
reads as truthy and a plain `int()` raises on.

**Removing a species is a seed-data change too (V2.74, and again in V2.75).** *Rudbeckia hirta*
came out because VASCAN and Moss's *Flora of Alberta* both record it as
introduced in Alberta, and a removal has a wider blast radius than an
addition: it took 150 documented edges, a `plant_ecoregions` entry, two seeded
polyculture memberships, a worked-example fallback, and **six animals whose
only documented edge was to that plant** — leaving those in `fauna` trips
`test_derived_edges`' orphan ceiling, and the answer is to remove them, not to
raise it. Record the call in `data/excluded_taxa.json` with its authority;
`data_quality.validate_excluded_taxa` then fails the build if the species
reappears in either plant file or as the `plant` of an edge.

**Sourcing is enforced (V2.42).** Every `source` field in
`plant_fauna_master.json`, `bee_attributes_master.json` and
`lepidoptera_attributes_master.json` must resolve to a key in
`data/sources_master.json` — a free-text citation is now a build error, not a
style preference. A claim resting on several works uses a comma-separated key
list. Adding an edge without a source, or with a name that does not resolve
against the catalogues, fails `validate_plant_fauna`; the seeder used to drop
unresolvable names silently. Do not invent bibliographic detail to satisfy the
gate: entries carry `record_confidence: unverified` precisely so nobody has to.

`sources_master.json` is **an object with a `sources` list of records**, not a
key→citation map. A new work is a dict appended to that list carrying at least
`key`, `authors`, `year`, `title`, `kind`, `covers` and `record_confidence` — see
`_SOURCE_RECORD` in `scripts/ingest_fauna_edges.py` for a filled-in example.
V2.59 added `globi` as a top-level `{key, citation}` pair instead and every one
of its 2,439 new edges was rejected for citing a work that was not in the
bibliography. `validate_plant_fauna` was right; read the file before appending.

## Which file flows into which table

| File | Rows | Loaded by (`src/db/plants.py`) | Table(s) |
|---|---|---|---|
| `data/plants_master.json` | 432 native plants | `_seed_from_master_json` → `_seed_from_json_file` | `plants`, `planting_calendar` (from `cal_*`), `plant_uses` (from `permaculture_uses`) |
| `data/garden_plants.json` | 5 cultivated garden plants | `_seed_from_json_file` | same as above; skips names already present |
| `data/fauna_master.json` | 1147 fauna | `_seed_fauna` (phase 1) | `fauna` |
| `data/plant_fauna_master.json` | 7,714 links (+ metadata records) | `_seed_fauna` (phase 2) | `plant_fauna` |
| `data/bee_attributes_master.json` | 69 bees | `_seed_bee_attributes` | `bee_attributes` (keyed to `fauna.id`) |
| `data/lepidoptera_attributes_master.json` | 337 species | `_seed_lepidoptera_attributes` | `lepidoptera_attributes` (keyed to `fauna.id`) |
| `data/nurseries_master.json` | 13 suppliers (object w/ `nurseries` list) | `_seed_nurseries` | `nurseries` |
| `data/plant_ecoregions.json` | **optional** — absent until the GBIF derivation has been run | `_seed_plant_ecoregions` | `plant_ecoregions` (keyed by scientific name in the file, resolved to ids at seed time) |
| `data/rainfall_fallback_prairie.json` | 12 EC normals | `property_data._climate_normal_rainfall` (NOT reseeded) | none — read directly |
| `data/soil_fallback_prairie.json` | 11 regional profiles | `property_data._prairie_soil_fallback` (NOT reseeded) | none — read directly |
| `data/wind_fallback_prairie.json` | 8 regions | `wind_flow._fallback_rose` (NOT reseeded) | none — read directly |

`data/plant_ecoregions.json` is the one file here you **do not hand-edit**. It is
generated by `scripts/seed_ecoregion_ranges.py` from GBIF occurrence records
(dev-time, run-once, commit the result), and every row carries the record count
and confidence band behind its claim. Writing a range in by hand would put an
unsourced number in the one table whose whole purpose is that its numbers are
sourced. A missing file is normal and means "nothing derived yet" — each species
then keeps the tags in `plants.ecoregion`.

`data/plants_master.json`'s **flower colour** is likewise authored by a script
rather than by hand: `scripts/seed_flower_colour.py` is both the tool and the
provenance record, and every correction in it carries its reason. Read it before
editing a `flower_color` value. The cautionary tale is short: the column was
seeded per GENUS, which nobody noticed while it only tinted a floret in the 3D
preview, and the moment V2.47 made colour filterable it started answering "show
me the blue ones" with a red columbine. Anything you change there needs
`flower_colour_source` set alongside it, or the gate
(`data_quality.validate_flower_colour`) will treat it as an unchecked genus
default. A colour word in a common name is **not** sufficient evidence on its
own: it is very often the berry, the seed head or the foliage, and the five
species that trip that trap are listed in the script's `KEEP` table with the
reason each one is already correct.

The three `*_fallback_prairie.json` files are **offline regional approximations**
read at runtime by nearest-centroid lookup, not reseeded into the DB. Editing
them does **not** require a schema bump (no reseed involved), but they are still
gated: their shape is validated by the fetchers and their tests. See the
`external-data` skill for that side.

## Field reference (the required + load-bearing ones)

Grounded in `_seed_from_json_file` and `src/data_quality.py`.

**`plants_master.json` / `garden_plants.json`** — top-level JSON list of objects:
- **Required (else `data_quality` errors):** `common_name`,
  `scientific_name` (must look binomial — regex `_SCI_NAME_RE`), `plant_type`.
- **Strict enums (typo = ERROR):** `plant_type` ∈ {tree, shrub, herb,
  wildflower, groundcover, vine, grass, sedge, rush, fern, aquatic};
  `sun_requirement` ∈ {full_sun, partial_shade, full_shade} (may be a
  comma-list); `water_needs` ∈ {low, medium, high, moderate} (comma-list ok);
  `perennial_annual` ∈ {perennial, annual, biennial}; `deciduous_evergreen` ∈
  {deciduous, evergreen, herbaceous, semi-evergreen}; `growth_rate` ∈ {slow,
  moderate, fast}; `toxicity_pets` / `toxicity_humans` ∈ {none, low, high}
  (empty = unassessed, allowed); `spread_habit` ∈ {clumping, slow_spreader,
  aggressive_rhizomatous, self_seeding}; `availability_class` ∈ {big_box,
  garden_centre, native_specialist, seed_or_plug, rare}; `flower_form` ∈ the
  `FLOWER_FORMS` set (daisy, rays, spike, plume, umbel, globe, cluster, bell,
  trumpet, cattail, pea, whorl, star, cross, lily, none).
- **Hex-validated:** `flower_color`, `fruit_color` — empty or `#rrggbb`.
- **Numeric coherence (ERROR):** `soil_ph_min ≤ soil_ph_max`, both in [0,14];
  `hardiness_zone_min ≤ hardiness_zone_max`; `spacing_m` in [0,50];
  `mature_height_m` in [0,80].
- **Soft (WARNING, not blocking):** `growth_curve` ∈ {slow_start, steady,
  fast_early}; `native_to_alberta` ∈ {0,1,"0","1","1?","0?"}; `cal_*` statuses;
  `bloom_period`/`fruit_period` month tokens; unknown `permaculture_uses` tags;
  unknown `ecoregion`/`ab_ecoregion` keys; unknown `native_provinces` codes;
  duplicate `scientific_name`.
- **Calendar:** `cal_jan`…`cal_dec` → `planting_calendar` rows (anything not
  `""`/`"dormant"`). Status must match the schema CHECK (dormant, start_indoors,
  direct_sow, transplant, growing, harvest, pruning).
- **Uses:** `permaculture_uses` — comma-string or list of canonical keys from
  `_USE_DEFINITIONS` in `plants.py` (keystone_species, host_plant, bird_food,
  pollinator, nitrogen_fixer, …). Feeds the `plant_uses` junction. Unknown
  tokens are silently dropped at seed and warned by `data_quality`.
- **Province/ecoregion:** `native_provinces` (e.g. `"AB,SK"` or a list),
  `ecoregion`/`ab_ecoregion` (comma-list of ecoregion keys). If
  `native_provinces` is absent it's derived from `native_to_alberta`.
- Column name aliases the loader accepts: `spacing_m`↔`spacing_meters`,
  `mature_height_m`↔`mature_height_meters`, `perennial_annual`↔
  `perennial_or_annual`.

**`fauna_master.json`** — list; each entry needs `scientific_name`,
`common_name`, `taxon` (∈ lepidoptera, bird, bee, other_insect, mammal). Optional
`ab_native`, `native_provinces`, `range_notes`, `icon`, `description`,
`image_url`/`image_attribution`/`image_license`. Idempotent on
`scientific_name` (`INSERT OR IGNORE`).

**`plant_fauna_master.json`** — list of link objects with `plant` (a plant
`common_name`), `fauna` (a fauna `scientific_name`), `relationship` (∈
larval_host, nectar, pollen, seed_food, fruit_food, nesting, cover), optional
`specificity` (specialist/generalist), `source`, `notes`. Records **without**
`plant`+`fauna` keys (e.g. `{"_comment": …, "_sources": …}`) are metadata and
skipped. A link is dropped silently if either name doesn't resolve — so a
misspelled `plant`/`fauna` just disappears, it doesn't error. **Verify links land
by count** (see `check_community_coverage.py` idea; for fauna, assert a `SELECT
COUNT(*) FROM plant_fauna` in a temp-DB test).

**`bee_attributes_master.json`** — list keyed by `scientific_name` (must exist
as a `taxon='bee'` row in `fauna_master.json`). Fields: `genus`, `nesting_habit`
(∈ ground, cavity, pithy_stem, social_ground, cleptoparasite, unknown),
`host_genus`, `tongue_length` (∈ short, medium, long, unknown), `flight_season`
(free text), `floral_host_genera`, `pollen_specialist` (0/1/null),
`conservation_status`, `source`, `notes`. **Honesty invariant (P9, enforced by
`data_quality.validate_bee_attributes`):** a graded `tongue_length`
(short/medium/long) is only allowed for `Bombus ...` — use `unknown` elsewhere.

**`lepidoptera_attributes_master.json`** — list keyed by `scientific_name` (must
exist as `taxon='lepidoptera'`). Fields: `kind` (butterfly/moth/skipper),
`activity` (day/night/day_dusk/unknown), `flight_season`, `overwintering_stage`
(egg/larva/pupa/adult/migrant/unknown), `voltinism`, `nectar_flower_genera`
(NULL for non-feeding adults — do not fake a generalist default),
`larval_host_note`, `conservation_status`, `source`, `notes`. Larval host
*edges* live in `plant_fauna` (relationship=`larval_host`), not here.

**`nurseries_master.json`** — an **object** (not a bare list) with a `nurseries`
key plus `_comment`/`_disclaimer`/`_provenance` metadata. Each nursery: `name`
(required), `kind` (native_nursery/seed_house/garden_centre/society),
`province`, `city`, `lat`, `lng`, `url`, `sells` (mirrors `availability_class`),
`ships` (bool→0/1), `notes`.

## Adding a new plant end-to-end

1. Append the object to `data/plants_master.json` with at minimum
   `common_name`, `scientific_name`, `plant_type`, plus as many strict-enum
   fields as you can fill correctly. Use `""` for unassessed safety/sourcing
   (the filters treat empty as "no known toxicity / unassessed", a denylist —
   never invent a value to look complete).
2. If it hosts/nectars fauna, add the fauna to `data/fauna_master.json` (if new)
   and the edges to `data/plant_fauna_master.json` — matching `common_name` and
   `scientific_name` **exactly** (resolution is by exact string; a typo silently
   drops the row).
3. Optionally run the provenance/safety/sourcing scripts to stamp derived tags
   (below) rather than hand-filling — they are idempotent and auditable.
4. **Bump `_SCHEMA_VERSION`** and add a changelog line.
5. `python scripts/check_plant_data.py` must show **0 errors** (warnings ok).
6. Add/extend a temp-DB test asserting the plant (and any fauna links) seed in.
7. `python -m unittest discover -s tests -t .`.

## Provenance / safety / sourcing scripts

These curate derived tags in the JSON with their reasoning captured in-script —
**idempotent** (re-running reproduces the same result), so prefer them over
hand-edits for bulk classification. Run from the repo root; they rewrite the
JSON in place (review the diff, then bump the schema version).

| Script | What it stamps |
|---|---|
| `scripts/apply_safety_tags.py` | `toxicity_pets`/`toxicity_humans`/`has_thorns`/`spread_habit`/`safety_source` from a curated denylist (ASPCA + poison-control sources). Denylist model: tags only *known*-toxic plants; unassessed stay empty. |
| `scripts/apply_sourcing_data.py` | `price_low_cad`/`price_high_cad`/`availability_class`/`sourcing_notes` — Alberta retail ESTIMATES, defaults from `src/sourcing.py:TYPE_PRICE_DEFAULTS`. |
| `scripts/tag_prairie_provenance.py` | Adds `moist_mixedgrass` ecoregion + `native_provinces` (e.g. `"AB,SK"`) by ecoregion continuity across the AB/SK border (P9 — a coarse, transparent inference, not a per-species range map). |
| `scripts/check_community_coverage.py` | Read-only: reports which retail-native plants are missing from seeded communities and flags any community member name that won't resolve. |
| `scripts/expand_fauna.py`, `scripts/expand_fauna_sk.py`, `scripts/expand_prairie_flora.py` | Bulk roster expanders for fauna / prairie flora. |

## Correcting a morphology value by hand (the bench)

`scripts/tune_morphology.py` (plants) and `scripts/tune_fauna.py` (animals) are
the benches. **A correction there is refused unless it says where it came
from** — and understanding why saves a confusing afternoon:

The `seed_*_morphology.py` seeders overwrite any species whose `*_data_source`
still reads `estimated`. That is deliberate — it stops a genus-level default
from erasing the only real numbers in the catalogue. The corollary is easy to
miss: **changing a number and leaving the source at `estimated` produces an edit
the next seeder run deletes.** It happened (a `florets_per_head` corrected 24 →
1) and surfaced only weeks later, as `test_the_seeder_is_idempotent` failing
with a message that names neither the species nor the cause.

So the save endpoint now refuses it, while the person is still looking at the
screen (`_provenance_gap`). To make a correction stick, set **in the same
save**:

| field | value |
|---|---|
| `flower_data_source` / `leaf_data_source` | `photo`, `flora` or `measured` — never leave `estimated` |
| `flower_data_citation` / `leaf_data_citation` | *which* source: `FNA vol. 21`, `Budd's 442`, `my yard 2026-08-03` |

The refusal is deliberately not an auto-fill: inventing a source would assert
provenance nobody supplied, which is worse than the bug (P9).

## Data-quality validation gate

`src/data_quality.py:validate_all()` is the gate. It returns `(errors,
warnings)`; **tests assert `errors == []`** while warnings are the visible
data-debt backlog (uncertainty markers like `"August?"`, known duplicate sci
names with `NOTE:`/`FLAG:` markers, unpromoted use tags). The split is
deliberate: errors are things the running app actively mis-parses (a typo in a
strict enum silently falls back to a default and breaks a score); warnings are
gracefully handled.

Two extra fauna validators run inside `validate_all`, not just in isolation:
`validate_bee_attributes` (the Bombus-only tongue invariant, fauna
cross-reference) and `validate_fauna_images` (bee photos must be **CC0 or
CC-BY** — commercial-safe, no NC/SA — and any non-CC0 photo needs a non-empty
attribution). If you add a bee photo, mind the licence.

`validate_all` only covers `plants_master.json` + `garden_plants.json` + the
fauna spine. **If you ship a NEW seeded data file, add it to the `files` list in
`validate_all()`** (and to the reseed wipe list per the `schema-change` skill).

## Pitfalls & gotchas

- **Forgetting the schema bump** is the #1 failure: your rows never reach
  existing installs. The reseed also fires on `count < 100`, so a local dev DB
  might mask the bug.
- **Silent drops on name mismatch.** `plant_fauna`, companions
  (`SEED_COMPANIONS` in `src/db/seed_data.py`), and community members all
  resolve by exact `common_name` / `scientific_name`. A typo doesn't error — the
  row just vanishes. Assert counts in a test.
- **`garden_plants.json` is skipped by name.** `_seed_from_json_file` drops any
  entry whose `common_name` (lowercased) already exists from
  `plants_master.json`. Don't rely on it to *override* a native entry.
- **Empty string ≠ `"none"` for safety.** The pet/kid-safe filters are a
  denylist: `""` (unassessed) passes and is surfaced with a "no known toxicity,
  not a guarantee" caveat. Don't backfill `"none"` to look thorough — you'd be
  asserting a safety claim you didn't verify.
- **`bee_attributes` / `lepidoptera_attributes` seed AFTER `fauna`.** They
  resolve `scientific_name → fauna_id`; a bee/lep whose species isn't in
  `fauna_master.json` is skipped. Add the fauna row first.
- **`nurseries_master.json` is an object, not a list** — the loader reads
  `payload["nurseries"]`. Adding entries at the top level (as a bare list) would
  seed zero rows.
- **P12** — restated because it matters most here: never operationalize
  Indigenous plant-use knowledge in `permaculture_uses`, `medicinal` tags,
  `notes`, or community names without FPIC. When in doubt, stop.

## Validation (run these)

From the repo root:

```bash
# The seed-data gate — must exit 0 (warnings are allowed):
python scripts/check_plant_data.py --quiet

# The unit-test wrapper of the same gate + junction seeding invariants:
python -m unittest tests.test_data_quality tests.test_uses_junction tests.test_fauna tests.test_nurseries -v

# Full suite before done (stdlib unittest only — no pytest):
python -m unittest discover -s tests -t .
```

`check_plant_data.py --quiet` and the `unittest` commands were run in this
session and pass (CLI exits 0 with warnings only; the modules report `OK`).
