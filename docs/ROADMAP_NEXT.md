# Site & Pattern — the forward roadmap (V2.32 →)

**This is the live roadmap.** [`PHILOSOPHY_ROADMAP.md`](PHILOSOPHY_ROADMAP.md) remains the
principle-by-principle map and the shipped record of F1–F62 — read it for *why* the app is
shaped the way it is and what has already landed. This file is what comes next, and why.

Feature IDs continue the same stable-handle sequence (F63, F64, …) so "let's do F70" keeps
working across both documents. **Next free ID: F107.**

> **Collision fixed in V2.37.** F78–F82 had each been assigned *twice*: the V2.34 3D work
> (herb aspect axis, Stylised/Balanced/Lifelike, florets, forked stems, bloom count) reused
> the IDs Theme D's unbuilt designer-workflow entries already held, and "a task-shaped home"
> was a third claimant on F82. The shipped assignments are kept — they are in the commit
> history — and the five unbuilt entries were renumbered to F90–F94. "Let's do F80" is
> unambiguous again, which is the whole point of a stable handle.

---

## Where the app actually stands

> **First outside feedback landed in V2.37** — sixteen observations from a real tester, ten
> of them fixed in that release. The record is [`USER_FEEDBACK.md`](USER_FEEDBACK.md) and the
> remaining five are **Theme G** below. Read it before planning: it is the only document here
> that is not the author's own view of the product, and several items were features that
> already existed and could not be found — including one (PDF export) that had been raising
> an exception on every call for four minor versions behind a test that skipped.



An honest summary, because a roadmap that flatters the codebase is useless.

### What this app is genuinely good at — better than anything else in its category

1. **It models ecological relationships, and almost nothing else does.** 500+ sourced
   plant↔fauna edges, four edge shapes unified behind one query API and vocabulary
   (`src/db/relationships.py`, F7), a design drawn as its own network (F5), a simulator that
   teaches by *breaking* an edge (F46), and one that follows a single edge from a host plant to
   a fledged chickadee (F47). Every other landscape tool is a catalogue of objects.
2. **It treats time as real.** Not a growth slider — a succession *engine* where the maturing
   overstory shades the understory year by year, sun-lovers over-topped past their tolerance
   decline and die, deciduous crowns only shade in leaf-on season, canopy trees are suppressed
   rather than culled, and the gaps that open get **recruited into** by self-seeders. The year-30
   scene shows survivors, not everything frozen healthy.
3. **It knows the site.** DEM/slope/contours, soil rasters, seasonal wind roses and live wind,
   wind shadow, snow-catch microsites, canopy-height tree detection that measures real heights off
   a global 1 m raster, OSM buildings, phone scans, Gaussian-splat backdrops — all offline-first
   with honest fallbacks.
4. **It closes the loop to the ground.** Prep → buy → a numbered scale plan drawing → a phased
   schedule → a maintenance calendar whose hours actually fall year over year (and a test that
   fails if that curve ever flattens).
5. **It is honest.** Ranges not points, `documented` vs `derived` on every edge, "we don't know"
   as a shippable answer. This is rare and it is the app's character.

### What it is not good at yet

1. **It looks like a diagram.** The 3D preview has **~75 distinguishable plant looks for 434
   species**. That ratio, not the triangle budget, is the whole problem —
   [`SPRITE_AUDIT.md`](SPRITE_AUDIT.md) says so plainly and measured it.
2. **Its photographs don't show the plant.** One photo per species, chosen by *licence order*
   rather than usefulness, which is exactly why so many are macro shots of a single flower.
   Coverage: **323 of 434 plants** (74%), **58 of 142 fauna** (41%), and **7 of 69 bees** (10%).
3. **It never argues that a native yard is beautiful.** It argues, superbly, that a native yard is
   ecologically valuable. Nobody converts a lawn on ecological grounds alone — and nobody's
   spouse, neighbour or HOA does.
4. **It has no professional workflow.** One design at a time, no variants, no substitution when
   the nursery is out, no order file a nursery would accept, no reusable palette.
5. **It sprawls.** Six side tabs, roughly twenty sub-tabs, nine modes on the 3D toolbar.

---

## The lens: the funnel is cleared, so what replaces it?

The previous roadmap's organizing idea was an **adoption funnel** — ONBOARD → DESIGN →
CONFIDENCE → ACT → MAINTAIN — and it earned its keep: it named ONBOARD and ACT/OUTPUT as the
deficits, and V2.31 cleared both (F44/F45 and F40–F43). A user can now go from a blank map to a
printable, phased, sized planting document.

So the funnel has done its job, and the ranking question has to change. The app can take someone
from nothing to plants in the ground. What it still cannot do is make them **want to**, and then
let them **recognise what they planted** when they walk out to it in May.

Those are the two gaps, and they are the two the owner named independently — the 3D models and the
species photographs. That is not a coincidence: they are the same gap seen from two sides.

> **The new lens — three conditions the funnel never covered:**
>
> - **WANT** — would anyone choose this over a lawn, and would they still choose it after seeing
>   what it looks like? (Today the app answers with a score, not a picture.)
> - **SHOW** — can the user sell it to the person whose agreement they need — a client, a spouse,
>   a neighbour, a board? (Docent mode gestures at this; there is no artefact to hand over.)
> - **RECOGNISE** — six weeks after planting, can they tell their milkweed from a weed? (Today: one
>   500-pixel photo of a flower that will not appear for two years.)
>
> These are not funnel *stages* — they're conditions that hold or fail all the way along. WANT
> gates activation. SHOW gates the second yard. RECOGNISE gates whether the first one survives.

Ranked against that lens, the two priorities on the owner's list are also the two highest-value
items on the roadmap. The rest of this document sequences them and says what else follows.

---

## Shipped

**V2.33 — Theme A, the whole of it (F63–F69).** The 3D preview stopped being a
diagram. Detail entries below are kept as the record of what was asked for; what
was actually built, what it cost and what it left open is in
[`SPRITE_AUDIT.md`](SPRITE_AUDIT.md#third-pass--v233-roadmap-f63f69).

| ID | What landed | Where |
|----|-------------|-------|
| **F63** | Ten procedural surface classes (bark smooth/furrowed/papery/shaggy/scaly, leaf matte/glossy/pubescent/glaucous, needle), picked per species from the catalogue; triplanar foliage sampling | `html/scene3d/01b-surface.js`, `bark_texture` + `leaf_surface` (schema v52) |
| **F64** | Species profiles where the genus lied (jack pine, water birch, Evans cherry, Douglas-fir); shrub silhouettes resolved from the species' own `branching`, +`arching`/`prostrate`/`upright`; **and the oak** — crown leaf cards were 13–15× life size | `assetlib/flora_trees.py`, `flora_shrubs.py`, `conventions.crown_card_length` |
| **F65** | Aspect axis on grass / aquatic / vine — three real shapes instead of three random draws, at **zero payload cost** | `conventions.LAYER_ASPECT_CLASSES` |
| **F66** | Eight graminoid seed heads across 78 of 79 species — the field mark a grass is identified by | `inflorescence_form` (schema v52), `html/scene3d/12-seedheads.js` |
| **F67** | Four bee builds, four lepidopteran, three bird — the identification for the 62 native bees that have no photograph | `assetlib/fauna_variants.py`, `src/scene_wildlife.py` |
| **F68** | Sway follows the site's real seasonal wind and is damped inside the design's own windbreak lee | `src/wind_scene.py`, `01b-surface.js:applySceneWind` |
| **F69** | Presentation still — the docent's beats finally drive a camera; print-resolution render, a PDF page, and a sidewalk preset that is **F77** for free | `src/presentation_still.py`, `permaSetCameraPreset` |

**Principle 13 was adopted** (the proposal in Theme C below), on the owner's
decision: *a native planting has to be loved to survive*. Nassauer 1995 is in
[`REFERENCES.md`](REFERENCES.md); `tests/test_philosophy.py` now guards thirteen.

**V2.34 — the uncanny valley (F78–F80).** Prompted by the observation that the
preview read as "a really low quality video game" and that the *old polyhedrons
were more forgiving*. Both halves were right, and the second one is the
diagnosis: geometry that attempts realism invites a comparison that everything
still abstract in the scene then loses.

| ID | What landed | Where |
|----|-------------|-------|
| **F78** | **Herb aspect axis** — the gap F65 left. Three classes per growth form at the median of each tertile of the real spread; 169 of 228 species move off their form's single authored figure and the median proportion error falls **28% → 11%**. 52 units → 96, 2.5 → 4.4 MB | `conventions.HERB_ASPECT_CLASSES`, `manifest._variants_for` |
| **F79** | **Stylised is a style, not a thinning** — level 0 skips the baked models and the surface grain, flat-shades, and builds forbs as faceted masses. Levels renamed **Stylised / Balanced / Lifelike** | `html/scene3d/13-stylised.js`, `01b-surface.js:setStylised` |
| **F80** | **The bloom is geometry** — a floret from petal count × shape × symmetry plus a separate disc, placed by one of nine inflorescence architectures, and **lit**. 307 of 311 flowering species described | `html/scene3d/15-florets.js`, ten columns at schema v53, `scripts/seed_flower_morphology.py` |

**V2.34, second increment — the two gaps the first one left (F81–F82).**

| ID | What landed | Where |
|----|-------------|-------|
| **F81** | **Forb stems fork.** `stem_branching` was recorded at v53 and read by nothing; a goldenrod's silhouette IS its two orders of branching and it was a pole. Only the two forms with a stem take the axis; 96 units → 112 | `assetlib/flora_herbs._branch_skeleton`, `conventions.BRANCH_CLASSES`, `html/scene3d/03-herbs.js:branchSpans` |
| **F82** | **A bloom count from the plant, not the canopy** (schema v54). `flowering_stems`, falling back to the branching habit — one head per stem, or one per branch tip — instead of to spread | `flowering_stems`, `html/scene3d/15-florets.js` |

**V2.35 — Theme B, the structural half (F70 + F71's tool + F72).**

| ID | What landed | Where |
|----|-------------|-------|
| **F70** | **Photo sets with named slots.** `plant_photos`, keyed by `scientific_name` (ids are not stable across a reseed), seven slots, `image_url` synthesised on read so the plant browser, the 3D dossier and `photo_warm` all improve with no change at the call site. `data_quality` now counts COVERAGE, not just licence compliance — which is how "0 of 434 species have a habit shot" became a number instead of a feeling | `src/db/photos.py`, schema v55, `src/data_quality.py:validate_photo_coverage` |
| **F71** *(tool half)* | The curation loop, folded into the tuning bench: seven slots per species with import and delete, triage filters, a verified counter, and per-species deep links to the sources that actually publish these numbers | `scripts/tune_morphology.py`, `html/tune_morphology.html` |
| **F72** | **Your photographs, first-class.** Two destinations, one mechanism: shipped (`data/photos/` + `data/plant_photos.json`) or private (the user data dir, `origin='user'`, which the reseed never touches). Every import is downscaled and has its **EXIF stripped** — a photo of your own yard carries your home's coordinates | `src/photo_import.py`, `scripts/import_photos.py` |
| — | **Provenance on every flower number** (`flower_data_source`). 307 species are *described*; none was *verified*, and those were being quoted as the same figure | schema v55, `scripts/seed_flower_morphology.py` |

**V2.36 — F71 finished: the sourcing half, and the provenance to go with it.**

| ID | What landed | Where |
|----|-------------|-------|
| **F71** *(sourcing half)* | **The 323 photographs the catalogue already had, made visible and sortable.** V2.35's slot strip read only `plant_photos.json`, which was empty, so every existing photo vanished from the bench — the tool for comparing a sprite against a photograph had no photographs. They come back in an **`unsorted`** bucket rather than being assumed to be flower macros, and one click files each into its real slot with the credit carried across verbatim. The "sorted" and "habit" counters therefore start at zero and mean something | `scripts/tune_morphology.py:photos_by_slot`, `/api/photo-assign` |
| — | **The candidate picker.** An empty slot can pull the species' wider openly-licensed iNaturalist set (~12 photos) and a person picks the one that is actually a habit shot. The only route off "0 habit shots" — triage cannot turn flower macros into whole-plant photographs. Reuses the exact-name match and licence whitelist already in `fetch_inaturalist_images.py` (`pick_photo` → `open_candidates`) | `/api/candidates`, `scripts/fetch_inaturalist_images.py` |
| — | **Which source, not just what kind** (`flower_data_citation`, schema v56). v55 recorded that a number was `estimated` or read `flora`; naming the flora is what makes it a citation. Blank from the seeder on purpose | schema v56, `docs/DATA_SOURCES.md` |
| — | **The reading aid, built so it cannot become a scrape.** Four numbers off one published description, off unless `--flora-fetch`, `robots.txt` fail-closed, one species per click, no bulk path, no cache, no prose retained, and the citation filled in automatically | `src/flora_read.py`, `docs/DATA_SOURCES.md`, `docs/FNA_PERMISSION_LETTER.md` |

**V2.36, second increment — the vocabulary you are asked to use, drawn; and a
bench for the whole plant.**

| ID | What landed | Where |
|----|-------------|-------|
| — | **The 33 terms, drawn.** The bench asked for `corymb` or `obovate` from a dropdown of bare words and gave no way to know which was which — a control nobody can use honestly, and one that had already been collecting guesses for a release. Nine inflorescence architectures, nineteen leaf shapes and five leaf arrangements as generated inline SVG, beside each dropdown and as a full comparison chart where **clicking the drawing that matches sets the value**. Eleven of the leaf shapes come from one shared profile function, because that is what the terms actually are: one shape family varying in where it is widest | `html/botany/diagrams.js`, `docs/BOTANY_FIELD_GUIDE.md` |
| — | **The flower bench became a plant bench.** A second control group for `leaf_shape`, `leaf_size_cm`, `leaf_arrangement`, `leaf_surface`, `growth_form`, `branching`, `mature_height_m` — the group a flora's description actually gives you, and the one where the fidelity is (`growth_form` picks the plant's whole body). `_flowering` stopped being a gate that hid **123 of 434 species** and became a filter | `scripts/tune_morphology.py`, `html/tune_morphology.html` |
| — | **Leaf provenance** (`leaf_data_source`, `leaf_data_citation`, schema v57). Needed more than the flower pair: those columns are blank until described, whereas all seven leaf/habit columns were seeded with a genus-level estimate for every record — a guess that is invisible rather than absent | schema v57, `validate_morphology_provenance` |
| — | **One vocabulary, one definition.** The four flower enums moved into `src/data_quality.py` beside the leaf ones and joined the gate's hard-enum table — `flower_arch`, `flower_symmetry`, `petal_shape` and `stem_branching` had never been validated at all. Dropdowns are served from those sets over `/api/vocab`; the HTML's three hand-typed copies are gone | `src/data_quality.py`, `/api/vocab` |

**Deferred, and why:** F73 (in my yard, on this date) — the `taken_on` column is
in place so it becomes UI-only work; F74 (the seedling sheet) — cheap to
assemble, but it would print "no seedling photo" for essentially every species
until that slot has content.

**V2.36, third increment — the animals get the same treatment, and the
butterflies fly.**

| ID | What landed | Where |
|----|-------------|-------|
| **F84** | **Fauna morphology (schema v58).** Every creature's appearance was computed from SUBSTRINGS OF ITS COMMON NAME — a 12-genus bee table and seventeen `if "azure" in name` tests — so 69 bees rendered as 12 animals (29 bumblebees identical, all 20 cuckoo bees identical) and 31 lepidoptera as 16 (Polyphemus, Cecropia and Isabella Tiger Moth were one moth). None of it was in the database, sourced, or correctable without editing code. Bees gain body length, build, two colours, metallic, scopa, wing tint and the per-tergite **`band_pattern`**; leps gain a **wingspan range** — the fauna data's first real measurement — three wing colours, shape, pattern, eyespots, resting posture and **`flight_style`**. Seeded as `estimated`: 29 and 31 distinct animals | schema v58, `scripts/seed_fauna_morphology.py`, `validate_fauna_morphology` |
| — | **The fauna bench.** `scripts/tune_fauna.py` — the companion to the flora one, with a **band editor that draws the bee as you type it**, because a band code entered blind is unverifiable and the whole point is to hold it against the plate. Shared scaffolding in `scripts/_bench_common.py`; nothing else abstracted on two examples | `scripts/tune_fauna.py`, `html/tune_fauna.html` |
| — | **The fauna vocabulary, drawn** — six wing shapes, seven patterns, five postures, six flight styles, four bee builds, three scopa positions. The flight-style drawings are made from the *same* layered wander the viewer flies, so the picture is the behaviour | `html/botany/fauna.js`, `docs/FAUNA_FIELD_GUIDE.md` |
| — | **The butterflies fly properly.** `flapWings` had no phase, so every flier in the scene beat off one global clock in perfect unison — the wings were never frozen, they were a metronome, which in a still frame is indistinguishable from "they don't flap". Plus a skewed stroke (the downstroke snaps at 1.78× the recovery), a layered-noise wander in place of two pure sines, and wings that close when a lep settles. `flight_style` drives it per species | `html/scene3d/07-wildlife.js` |

**Deferred from F84, and why:** wing-pattern GEOMETRY — eyespots and bands as
procedural decals. Written and removed: the marks attached to the wing pivots
and positioned correctly but would not render, a coplanar-decal ordering problem
that resisted polygon offset, depth-test and explicit render order inside a
sensible budget. The data, the vocabulary, the drawings and the bench are all in
place, so this is geometry work on a settled contract rather than a rebuild.
Birds (24 → 16 looks), other insects and mammals keep their name tables.

**F83 · Know the plant, not just the design — *not started*.** The drawn
vocabulary, the per-species characters and the photo slots are three quarters of
a plant-identification lesson: show a photograph, ask for the character, score
it. What is missing is content, not code — it wants the `habit` and `leaf` slots
filled first, and `src/learn_panel.py` already has the Field Study tab and
`src/lesson_track.py` the progress model, so it is a feature rather than a
rebuild. Logged here so the V2.36 work is understood as its foundation.

Theme A's remaining gaps — within-silhouette shrub aspect, fern density and
billboard fruit — are listed at the end of the sprite audit rather than
re-opened here.

---

## Ranked summary

**Theme A — LOOK: the 3D preview** *(WANT)* — ✅ **all shipped in V2.33**

| ID | Feature | Impact | Effort | Risk | Principle | Status |
|----|---------|--------|--------|------|-----------|--------|
| F70 | Photo sets per species, with named slots | **High** | M | Med — schema v55 | P5, P9 | ✅ V2.35 |
| F71 | Habit-first sourcing + a curation tool | **High** | M | Med | P5, P9 | ✅ V2.36 (tool V2.35, sourcing V2.36) |
| F72 | Your own photos, first-class and reseed-proof | **High** | M | Med | P11, P5 | ✅ V2.35 |
| F81 | Forb stems fork — `stem_branching` finally read | **High** | M | Low | P5, P9 | ✅ V2.34 |
| F82 | Bloom count from the plant, not the canopy | Med | S | Low — schema v54 | P9 | ✅ V2.34 |
| F78 | Herb aspect axis — the gap F65 left | **High** | S | Low | P5, P9 | ✅ V2.34 |
| F79 | Stylised / Balanced / Lifelike — level 0 as a style | **High** | S | Low | P5, P13 | ✅ V2.34 |
| F80 | The bloom as geometry — florets + nine architectures | **High** | L | Med — schema v53 | P5, P13 | ✅ V2.34 |
| F63 | Shared surface atlas — bark / leaf / needle | **High** | M | Low–Med | P5, P2 | ✅ V2.33 |
| F64 | Species tables where genus tables lie (absorbs F60) | **High** | L | Med — asset size | P2, P9 | ✅ V2.33 |
| F65 | Aspect variant axis on layer archetypes (was F62) | Med | M | Med — asset size | P2, P9 | ✅ V2.33 |
| F66 | Seed heads & inflorescences — the graminoid field mark | Med | M | Med — schema + seed | P5, P2 | ✅ V2.33 |
| F67 | Creature variety within a kind | Med | M | Low | P5, P3 | ✅ V2.33 |
| F68 | Wind that blows from where the wind blows | Med | S–M | Low | P5, P11 | ✅ V2.33 |
| F69 | Presentation still — a render you can put in a proposal | **High** | M | Med | P5 → **P13** | ✅ V2.33 |

**Theme B — RECOGNISE: the photographs** *(RECOGNISE)*

| ID | Feature | Impact | Effort | Risk | Principle |
|----|---------|--------|--------|------|-----------|
| F70 | Photo **sets** per species, with named slots | **High** | M | Med — schema bump | P5, P9 |
| F71 | Habit-first sourcing + a curation tool | **High** | M | Med — data policy | P5, P9 |
| F72 | Your own photos, first-class and reseed-proof | **High** | M | Med — schema | P11, P5 |
| F73 | "In my yard, on this date" — the photo as an observation | Med | M | Low | P11, P4 |
| F74 | The seedling sheet — "is this my plant or a weed?" | **High** | S–M | Low | P11, P8 |

**Theme C — WANT / SHOW: the argument the app doesn't make**

| ID | Feature | Impact | Effort | Risk | Principle |
|----|---------|--------|--------|------|-----------|
| F75 | Cues-to-care checker | Med | S–M | Low | P2, (P13) |
| F76 | Before / after / in five years | **High** | M | Med | P4, P5, P8 |
| F77 | The neighbour's-eye view | Med | S | Low | P5, (P13) |

**Theme D — the designer's workflow**

| ID | Feature | Impact | Effort | Risk | Principle |
|----|---------|--------|--------|------|-----------|
| F90 | Design variants + side-by-side comparison | **High** | L | Med | P9, P1 |
| F91 | Ecological substitution — "the nursery is out" | Med | M | Low | P3, P10 |
| F92 | An order file a nursery accepts | Med | S | Low | P8 |
| F93 | Reusable palettes / go-to communities | Med | M | Low | P1 |

**Theme E — the confidence block** *(carried forward, and overdue)*
F8 · F12 · F13 · F14 · F28 — unchanged from `PHILOSOPHY_ROADMAP.md`, still one job, still cheap.

**Theme F — surface sprawl**
F94 · A task-shaped home, or an honest tab retirement pass.

---

## Theme A — LOOK: make it a place, not a diagram

[`SPRITE_AUDIT.md`](SPRITE_AUDIT.md) is the honest baseline here and it ranked five improvements.
Items 1–3 shipped (groundcover rebuilt, species leaves in tree crowns, oriented flower heads),
item 4 is a quarter done (the poplar/aspen split proved the mechanism), item 5 is untouched. The
audit's own conclusion is the right starting point and worth restating because it determines
everything below:

> "The current bottleneck is not the hardware budget. … We are using a small fraction of what a
> weak laptop can do. **Variety is** [the limit]."

### F63 · Shared surface atlas — bark, leaf, needle — *Impact High · Effort M · Risk Low–Med (P5, P2)*

The audit's item 5, and the step it calls "the real level up … moves the app from *diagram* to
*illustration*." Everything is flat-shaded vertex colour with procedural noise on top; nothing in
the scene has the texture of a living surface.

**How — and the constraint that shapes it.** The obvious implementation is wrong here. The GLBs
are texture-free *and UV-free by contract* — `tests/test_model_assets.py` fails the build if one
embeds an image, and there are no texture coordinates to sample even if it didn't. Do not break
that; it is load-bearing (instanced meshes would repeat one UV set identically across every copy
anyway, so per-archetype UVs buy nothing).

The path that fits is already half-built. `02-plants.js:makeDetailTexture` draws a procedural
canvas per kind at runtime and `plantMaterial({ detail, detailScale, detailAmount })` injects an
**object-space** lookup with a per-instance offset taken from the instance matrix. Keep that
machinery exactly and change only what it samples: one shared, hand-authored **1024² atlas**
(bark rows: smooth/furrowed/papery/shaggy; leaf rows: glossy/matte/pubescent/glaucous; needle) as
a viewer asset, sampled triplanar in object space. No UVs, no GLB change, no test to weaken, one
file to fetch, per-instance variation already solved.

Sequence it first among the 3D work: it is the largest perceived jump per unit effort, and — the
audit's own caution — it is worth doing *after* items 1–4 because "texturing a library that has 75
distinct looks just makes 75 nicer-looking repeats." Items 1–3 are done; F64 runs alongside.

**Watch:** add any new injected-shader option to `customProgramCacheKey` too, or three.js hands
two genuinely different shaders the same compiled program.

### F64 · Species tables where genus tables lie — *Impact High · Effort L · Risk Med (P2, P9)*

The audit's item 4, and the root cause of the 75-looks-for-434-species ratio. Concretely today:

- `TREE_PROFILES` (`html/scene3d/02-plants.js`) maps **11 genera** onto shared profile bags, so
  every species inside a genus is byte-identical geometry apart from the poplar/aspen split. Across
  `plants_master.json` + `garden_plants.json` that is 25 woody species resolving through 11 looks:
  Chokecherry, Pin Cherry, Evans Cherry and Nanking Cherry are *one sprite*; Goodland and Norland
  Apple are *one sprite*; six willows are *one sprite*.
- **Shrubs resolve to 5 silhouettes** (56 species, by the audit's count), varied since V2.29 by leaf
  blade/grain/arrangement, which genuinely helps — but a saskatoon and a pin cherry at similar
  heights still read alike because the branch architecture is one builder with different numbers.

**How.** The mechanism is already in place and proven: `03-herbs.js:treeFormFor` now prefers
species characters with `formBias` as fallback, `branching` (schema v47) is read, and the
poplar/aspen split showed what species-level authoring buys (two pixel-identical trees became a
broad dense crown and a slender open one). This is **authoring against a botanical reference, not
engineering** — roughly 17 tree and 56 shrub species each needing a handful of honest parameters
(crown aspect, leaf outline, branch angle, trunk girth fraction, bark colour).

Fold in **F60** (blade-class variant axis on tree archetypes) as the piece that makes per-species
leaf outlines possible at all: `DECID_LEAF_SHAPE` is currently the *mode* over the species mapping
to each archetype. Doing it generally roughly doubles the baked tree units — that is the risk flag,
and it is an asset-size question, not a fidelity one.

**Discipline (P9):** where a species' character isn't known, fall back to the archetype rather than
inventing one. An honest repeat beats a fabricated difference.

### F65 · Aspect variant axis on layer archetypes — *Impact Med · Effort M · Risk Med (P2, P9)*

Promoted out of "still deferred", because it is not polish — it is a **correctness bug of exactly
the kind V2.29's aspect work existed to kill**. `LAYER_ASPECT["grass"]` is 1.31, the pooled figure
over grasses, sedges and rushes; the catalogue's grasses run 0.67 (Rocky Mountain fescue) to 2.67
(Canada wild rye), so the instance transform stretches the unit by up to **2.4× on Big Bluestem**.
`conventions.py` calls the residual "small … natural variation"; at this spread the audit is right
that it is not. Same fix as the herb/shrub variant axes: bake an aspect axis, select per species.

### F66 · Seed heads & inflorescences — *Impact Med · Effort M · Risk Med — schema + seed (P5, P2)*

From the audit's still-open list: *"a big bluestem's turkey-foot inflorescence is most of how it is
identified in the field, and there is no geometry for it at all."* 79 grass/sedge/rush species share
one generic plume.

**How.** Follow the `fruit_form` precedent exactly (schema v49 + `seed_fruit_morphology.py`, which
took fruit from one sphere for 43 species to nine shaped sprites): add an `inflorescence_form`
column, seed it with a small honest vocabulary — turkey-foot, open panicle, contracted spike,
nodding/one-sided raceme, bristly, sedge cluster, rush umbel — and build the geometry against it.
Small vocabulary, large identification payoff, and it lands the field mark the plant is *named*
for. This is also the highest-value RECOGNISE item on the 3D side.

### F67 · Creature variety within a kind — *Impact Med · Effort M · Risk Low (P5, P3)*

"A bumblebee is not a honeybee." Sixty-nine bees resolve to about five genus looks; leps vary by
colourway. The data spine is already there (F37's `bee_attributes`: nesting habit, tongue length,
genus; `appearance_for_fauna`; per-species lep records).

**Why it ranks above cosmetics:** it is the *only* way most of this fauna will ever be
identifiable in the app. See F71 — 62 of 69 bees have no photograph and, under the current licence
policy, will not get one. Where there is no photo, the model has to carry the identification.

### F68 · Wind that blows from where the wind blows — *Impact Med · Effort S–M · Risk Low (P5, P11)*

Small, cheap, and the biggest "this is alive" jump per hour available.

`src/wind.py` already computes a seasonal wind rose for the actual site and `src/wind_shadow.py`
already computes porosity-aware shelter geometry. The 3D viewer already sways. Today the sway is
generic and unrelated to either. Wire them: drive sway **direction and amplitude from the site's
real prevailing wind for the displayed month**, modulate by a stiffness class (a grass whips, a
mature spruce barely moves), and let plants inside the computed lee move visibly *less*. The
windbreak analysis stops being a band on a 2D map and becomes something you can see happening —
P5 as literally as it gets, on data the app already has.

### F69 · Presentation still — *Impact High · Effort M · Risk Med (P5)*

**The single highest-value 3D feature for the professional persona.** A landscape designer's
deliverable is not an interactive viewer; it is an image in a document. The app has a flyover, a
docent script with camera beats, and offscreen capture plumbing already used for the yard-photo
bake and the F2 snapshots. What it does not have: *place a camera, choose a year and a month,
render at print resolution, and drop it into the PDF beside the plant schedule.*

**How.** Reuse the docent beat structure for camera placement (it already carries camera + season
+ year state), the existing offscreen capture path for the render, and `pdf_export.py` for the
page. The risk flag is high-resolution capture in QWebEngineView — mitigate by rendering at device
scale and compositing, the same way the planting-map page avoided the satellite-screenshot trap.

F77 (the neighbour's-eye view) then costs almost nothing.

---

## Theme B — RECOGNISE: photographs that show the plant

### The diagnosis

The problem is not that the photos are bad. It is that **the selection criterion was never
usefulness**. `scripts/fetch_inaturalist_images.py` takes *the first photo whose licence is in the
redistributable whitelist* — the docstring says so, and it is the right rule for a licence filter
and the wrong rule for a photograph. iNaturalist's leading photos skew heavily to macro shots of a
flower, because that is what people photograph and what identifies a plant *to a botanist*. It is
the least useful frame for someone deciding whether they want the plant in their yard, or trying to
find it in one.

Three structural facts follow from that, and they set the design:

1. **There is one photo slot.** `plants.image_url` is a single column. There is no place to put a
   whole-plant habit shot *and* a leaf detail, so improving the photo means *replacing* the one
   that is useful for ID with one that is useful for scale, or the reverse. Both are needed.
2. **Coverage is thin and unevenly thin.** 111 of 434 plants have no photo at all; 84 of 142 fauna;
   and 62 of 69 bees. The bee number has a specific, fixable cause — see F71.
3. **There is no path for the user's own photographs**, and the obvious one is a trap: anything
   written into the seed-backed columns is destroyed on the next reseed.

### F70 · Photo sets per species, with named slots — *Impact High · Effort M · Risk Med — schema bump (P5, P9)*

The structural fix everything else in this theme depends on.

**How.** A new `plant_photos` table (schema bump + reseed-wipe entry), one row per
(species, slot, photo):

| Slot | What it has to show | Who needs it |
|------|--------------------|--------------|
| `habit` | **the whole plant, in context, with something for scale** | everyone — this is the default and the one that is missing today |
| `flower` | the bloom, close | ID, and the "will I like it" question |
| `leaf` | foliage and arrangement | ID in the 10 months it isn't flowering |
| `fruit` | fruit or seed head | ID, and the wildlife-value story |
| `bark_stem` | bark, cane colour, stem section | winter ID; dogwood's whole argument |
| `winter` | the plant in January | what your yard looks like five months a year |
| `seedling` | the first true leaves | **see F74 — this one prevents a specific disaster** |

**Two design decisions worth stating, both with precedent in this codebase:**

- **Key the table by `scientific_name`, not `plant_id`.** Plant ids are not stable across
  reseeds — that is a documented trap in `CLAUDE.md`, and it is the same reason the worked example
  (F44) and the reference communities (F50) are authored as names and resolved at open time. A
  photo table keyed by id would silently repoint photos at the wrong species on some future schema
  bump, and nobody would notice for months.
- **Synthesise `image_url` on read** from the best available slot (`habit` → `flower` → anything),
  exactly the way `permaculture_uses` is synthesised from the `plant_uses` junction since v37. Every
  existing consumer — the plant browser, the 3D dossier card, the bee/lep panels, `photo_warm` —
  keeps working with no change, and gains better photos for free.

Also: teach `src/data_quality.py` to report **coverage**, not just licence compliance. It currently
validates that a bee photo is CC0/CC-BY and has attribution; it has no opinion about 62 bees having
no photo at all. A coverage report per taxon and per slot turns an invisible gap into a tracked one.

### F71 · Habit-first sourcing + a curation tool — *Impact High · Effort M · Risk Med — data policy (P5, P9)*

**The honest engineering position first: there is no reliable automated signal for "this photo shows
the whole plant."** iNaturalist exposes no zoom, scale or framing metadata. Aspect ratio and
dimensions don't correlate. Anything clever here would be a guess dressed as a filter, which is
precisely what P9 forbids. So do not build a classifier.

**Build a curation loop instead**, which is cheap and honest:

1. **Fetch candidates, not a winner.** The script already pulls the taxon's wider photo set (~12
   photos) as a licence-rescue path — keep them all as candidates in `plant_photos` rather than
   taking the first acceptable one and discarding the rest. Extend to observation photos
   (`/v1/observations?taxon_id=…&photo_license=…&quality_grade=research`) for species whose taxon
   set is thin, which is most of the 111 with nothing.
2. **A contact sheet and seven keys.** `scripts/curate_photos.py` plus a static HTML contact sheet —
   the exact pattern `html/sprite_gallery.html` already uses for its 441 tiles. Page through 6–12
   candidates per species, press a key to assign a slot, skip what's useless. At ~5 seconds a
   species that is a few evenings for the whole catalogue, and it is genuinely a job for someone who
   knows the plants rather than for a heuristic.
3. **Ship the assignments in the seed JSON** so every install gets them; re-runnable and idempotent
   like the existing script.

> **Shipped V2.36**, with one departure from the plan above: the curation loop went into the
> existing tuning bench rather than a separate `scripts/curate_photos.py` + contact sheet. The
> bench already had the species list, the triage filters and — crucially — the *render*, and
> judging a photograph is much easier next to the sprite it is supposed to correct. Candidates
> are fetched per species on a click (`/api/candidates`, reusing `open_candidates`) instead of
> being bulk-imported as unassigned rows, which keeps the catalogue free of hundreds of
> photographs nobody chose. The observation-photo endpoint for thin taxa is not done and remains
> the next lever for the 111 species with nothing.

**One decision belongs to the owner, not to the roadmap.** Bees are held to a stricter licence bar
than everything else — CC0/CC-BY only, no ShareAlike (the F37 A1 decision, mirrored in
`data_quality.validate_fauna_images`) — and that policy is *why* only 7 of 69 have photographs. The
options are: (a) accept CC-BY-SA for bees as for other taxa and take on the ShareAlike obligation,
(b) keep the bar and accept that most native bees ship without a photo, leaning on F67's models
instead, or (c) source them ourselves. Worth deciding explicitly before the curation pass, because
it changes what there is to curate.

### F72 · Your own photos, first-class and reseed-proof — *Impact High · Effort M · Risk Med (P11, P5)*

Directly requested, and the right instinct: the owner's own photographs of Alberta natives, taken
in Alberta conditions, are better reference material than a CC-licensed macro shot from another
continent — and they are already licence-clean.

**How.**
- A **"Use my photo…"** action on the plant detail row and on the 3D dossier card, writing to
  `plant_photos` with `is_user = 1` and a path under the user data dir (`src/user_paths.py`, the
  single source of truth) — never inside the source tree.
- **The reseed rule is the whole point:** the wipe becomes `DELETE FROM plant_photos WHERE
  is_user = 0`, the same `origin='seed'` discipline that already protects user-authored polycultures
  (schema v46). Combined with F70's name keying, a user's photo library survives every future
  reseed and schema bump. Getting this wrong once would destroy user data silently, so it belongs
  in the design from the start rather than as a later fix.
- **User photos win** over sourced ones in the same slot.
- **Bulk import:** point at a folder; match filenames to species by scientific or common name;
  report what didn't match rather than guessing.
- Free consequence: a user-photo path is also the only sane route for **other free sources** —
  Wikimedia Commons, provincial herbarium images, a nursery's own catalogue photos with permission —
  since they all arrive as "a file plus a credit" rather than as an API.

### F73 · "In my yard, on this date" — *Impact Med · Effort M · Risk Low (P11, P4)*

The extension that turns a photo library into something no database can ship.

Tag a user photo to a **placed plant** and a **date**, and it stops being reference material and
becomes an observation. Three things fall out at once:

- **F51's phenology dashboard gets evidence.** It already ends each month with "we predict X in
  bloom around now — is it early, late, on time?" Today that question has nowhere to land. Now the
  answer is a dated photograph.
- **The seasonal observation journal (old F33) is delivered** — with the best possible entries.
- **After two or three seasons the user owns something unique: their own site's bloom dates**,
  against which the app's shipped ranges can be checked. That is P9 running in reverse, the user
  correcting the app, which is exactly the relationship the philosophy describes.

P11 is the principle this app has always been thinnest on in practice. This is the first feature
that sends the user outside *and takes something back from the trip*.

### F74 · The seedling sheet — *Impact High · Effort S–M · Risk Low (P11, P8)*

**The most valuable novice feature nobody builds.**

In May, a first-year lawn conversion is forty unidentifiable green rosettes. The beginner, doing
exactly what they were told to do, weeds their own milkweed. Alongside year-one drought — which F42
already addresses, and correctly calls out as the commonest killer — this is how a conversion
quietly fails, and the user concludes native plants "didn't take."

**How.** Mostly assembly once F70 exists:
- the `seedling` slot supplies the images;
- **key it to the numbered planting map (F41)** — "position 7 is Saskatoon; three weeks after
  planting it looks like this" — so the sheet and the plan use one numbering, as F41 and F40 already
  do;
- print it with the planting document (`planting_plan_export.py`), which is already assembled in
  job order and already goes outside;
- and be honest where the data is missing: a species with no seedling photo says so rather than
  showing an adult and implying it (P9). The gaps are then a visible target for F71/F72.

Serves P8 (repair carried past install day) and P11, and it is squarely aimed at the novice
persona.

---

## Theme C — WANT / SHOW: the argument the app doesn't make

### ✅ ADOPTED in V2.33: Principle 13 — *a native planting has to be loved to survive*

**Accepted by the owner and now core principle #13** in
[`DESIGN_PHILOSOPHY.md`](DESIGN_PHILOSOPHY.md#13-a-native-planting-has-to-be-loved-to-survive);
Nassauer 1995 is in [`REFERENCES.md`](REFERENCES.md) and
`tests/test_philosophy.py` guards thirteen themes and the P1–P13 anchor range.
F69 is anchored to it. The original proposal is kept below as the record of the
argument.

**This was a proposal for the owner to accept or reject.** The philosophy
document is the founding text and P12 is the only principle ever promoted into it; adding a
thirteenth is the owner's call. But the review turned up a real hole, and it sits directly under
the two priorities that prompted this roadmap.

**The gap.** Twelve principles cover ecology, emergence, relationship, time, perception, value,
generalism, repair, uncertainty, embodiment and consent. None of them covers *why anyone chooses
this over a lawn*, or how the planting survives contact with a spouse, a neighbour and a bylaw
officer. The nearest is P2 — "the best designs disappear into their context" — but that is an
argument about naturalism, not about desire or social licence, and the app reads it as a placement
rule.

**The missing citation.** Joan Nassauer, *Messy Ecosystems, Orderly Frames* (Landscape Journal,
1995) — absent from `REFERENCES.md` and from the codebase entirely. Its finding is that ecological
quality and legible human care are not in tension: a mown edge, a crisp border, a path, a sign, a
deliberate repeat are **cues to care** that buy an ecologically messy planting its social licence.
Tallamy's whole strategy — the app's stated *why* — depends on suburban neighbours tolerating and
then copying each other's yards, which is a social mechanism, not an ecological one.

**Why it belongs here rather than in a UX backlog.** The app already half-implements it with no
principle to hang it on: the aesthetic-composition terms in `placement_score`
(`_height_gradient`, `_cohesion`, `_rhythm`) are cues-to-care logic; docent mode exists explicitly
to present a design to *"a neighbour, an HOA board, a class"*; the lawn counterfactual is an
argument aimed at a sceptic. Naming the principle makes the 3D and photography work **core rather
than cosmetic** — which is the correct reading of them. As it stands, an honest reviewer would have
to file "make the preview beautiful" under polish, and that is wrong.

Suggested wording, if it lands:

> ### 13. A native planting has to be loved to survive
>
> Nassauer's *cues to care*, Alexander's "quality without a name", and the plain evidence of every
> converted front yard converge on a point the ecological case alone cannot carry: a planting that
> nobody finds beautiful gets removed, and one that a neighbour admires gets copied. Ecological
> quality and legible human care are not opposed — a mown edge, a crisp border, a visible path and
> a deliberate repeat are what buy an ecologically rich planting its social licence. Beauty is not
> decoration layered over the ecology; it is the mechanism by which the ecology survives contact
> with people. The application must therefore make its designs *desirable*, not only defensible —
> and must help the user show them to whoever has to agree.

*(Note: `tests/test_philosophy.py` bounds anchors at P1–P12 and asserts twelve themes; both would
need their range widened. Small change, but it is the thing that makes the principle real rather
than decorative.)*

### F75 · Cues-to-care checker — *Impact Med · Effort S–M · Risk Low (P2, proposed P13)*

Critique the design for the moves that decide whether it survives socially, not just ecologically:
a mown or hard edge along the public frontage, a defined border, height graded toward the back
(already scored — surface it), a visible path or entry, one showy repeat that reads as intentional,
room for a sign. **How:** extend `design_critic.critique_lines` and the habitat nudges; every input
either already exists (`placement_score`'s aesthetic sub-scores, `lawn_zones` geometry, the boundary
and frontage) or is a one-line geometric test. Cheap, and the first feature that argues the app's
missing half of the case.

### F76 · Before / after / in five years — *Impact High · Effort M · Risk Med (P4, P5, P8)*

The one image that makes people act, and the app has every ingredient and has never assembled them:
the **user's own lawn photo** (F24's site-photo underlay, or the splat backdrop), the design at
**year 1**, and the design at **year 5** (F2's snapshot timeline, F69's render). Three panels, one
page, on screen and in the PDF.

For the novice this is what converts a spouse. For the designer it is the first page of the
proposal. For P4 it is the philosophy's "design the trajectory, not the install day" made into a
single artefact instead of a slider someone has to be persuaded to drag.

### F77 · The neighbour's-eye view — *Impact Med · Effort S · Risk Low (P5, proposed P13)*

Camera at the sidewalk, at eye height, each season. Not the designer's orbit — the view that
actually decides whether this planting gets a complaint or a question about where to buy the seeds.
Nearly free once F69 lands, and it is the honest test of F75's advice.

---

## Theme D — the designer's workflow

The app is built for the owner-occupier converting their own lawn, and does that well. A landscape
designer using it professionally hits four walls, none of which is about ecology.

### F90 · Design variants + side-by-side comparison — *Impact High · Effort L · Risk Med (P9, P1)*

**No designer presents one option.** The app holds exactly one project, so producing an Option A and
an Option B means two files, two windows and a manual comparison.

**How.** "Duplicate as a variant", then a comparison view: habitat score, cost range, first-year and
steady-state effort hours, food-web status, species and wildlife counts, native ratio — side by
side, with the deltas named. Every number already exists (`habitat_score`, `sourcing`,
`PLANT_MAINTENANCE_HOURS`, `plant_impact`, `lawn_counterfactual`); the missing part is holding two
projects at once and diffing them. It is also philosophically on-message: presenting *options with
their trade-offs* rather than one confident answer is P9 at the level of the whole design.

### F91 · Ecological substitution — *Impact Med · Effort M · Risk Low (P3, P10)*

Every plant tool has "similar plants" and they all mean *similar height and colour*. This app can do
something none of them can: **ecologically equivalent**. Same vegetation layer, overlapping site
envelope, and an overlapping set of supported fauna via `relationships.edges_for_plant` — then
report the trade honestly, which is `plant_impact` run on a swap rather than a removal:

> *Chokecherry for Saskatoon: keeps 9 of 12 supported species and the food-web chain. You lose the
> July fruit window — waxwings and robins have nothing else in the design that month.*

Triggered by the real-world moment: the nursery is out of stock, or a species is out of budget.

### F92 · An order file a nursery accepts — *Impact Med · Effort S · Risk Low (P8)*

F40 produces the buy list as text and as a PDF page. A designer needs it as **CSV/XLSX grouped by
supplier**, botanical names, pot size / form, quantity, unit price range, total — the thing you
attach to an email. Small, unglamorous, and it is the last centimetre between a design and a
purchase order.

### F93 · Reusable palettes / go-to communities — *Impact Med · Effort M · Risk Low (P1)*

A designer repeats themselves across sites; that is craft, not laziness. Save the current selection
as a named palette and apply it to a new site **with site-fit re-checking** — which is the part a
human cannot do quickly and this app can (`placement_score`, `search_plants` envelopes,
`soil_flow`). Extends `polycultures`, which already carries user-authored rows through reseeds.

---

## Theme E — the confidence block (carried forward, and overdue)

**F8 · F12 · F13 · F14 · F28**, exactly as specified in
[`PHILOSOPHY_ROADMAP.md`](PHILOSOPHY_ROADMAP.md#tier-2--the-confidence-block-cheap-and-all-one-theme):
say how sure we are, and say who says so. All cheap, all one audit pass and one visual vocabulary,
and all still unbuilt.

**Worth naming plainly:** the V2.31 review criticised this roadmap for stating a priority and then
skipping it for seven consecutive increments of depth work. It then declared the confidence block
"next" — and V2.32 went to 3D realism. That is the same pattern a second time.

Two honest readings, and only the owner can pick:

1. The stated priority is right and keeps losing to whatever is more interesting — in which case
   schedule the block and hold to it.
2. **The stated priority is wrong.** The revealed preference across nine increments is that this app
   is a depth-and-delight tool, and depth-and-delight is what gets built because it is what the
   product actually is. In which case say so, drop the block to Tier 3, and stop paying review
   attention to a promise nobody intends to keep.

This roadmap's own ranking implicitly takes reading (2) — Themes A–C are DESIGN/LEGIBILITY/WANT
work, and they are ranked first because the owner named them and because the WANT/RECOGNISE lens
says they matter more than another confidence badge. That is defensible, but it should be a decision
rather than a drift.

---

## Theme F — surface sprawl (a named risk, not yet a feature)

Six side tabs (Site, Plants, Structures, Analysis, Planning, Learn), roughly twenty sub-tabs
between them, three inner tabs under Plants, and nine mode buttons in the 3D viewer. Every one was
justified when it landed. Together they are the reason a novice cannot find the thing they need and
a designer cannot get to a deliverable quickly.

There is precedent for fixing this well: the Forage tab was **retired** in V2.25 once Planning →
Wildlife covered the same question, and nothing was lost. That is the cheap move — an honest
retirement pass — and it should happen before any restructure.

**F94 · A task-shaped home** — *Effort L · Risk High.* The larger version: organise by what the user
is trying to do (Design · Understand · Plant · Learn) rather than by which subsystem owns the code.
High risk, and it should not be attempted until the retirement pass shows what is genuinely
load-bearing. Listed so it is on the record, not because it should be next.

---

## Theme G — what the first outside tester said (V2.37)

The full record, in their words, is [`USER_FEEDBACK.md`](USER_FEEDBACK.md). Ten of the
sixteen items shipped in V2.37; these five are what is left, and they are ranked here rather
than in Themes A–F because they came from evidence rather than from the author's model of the
product — which this roadmap has historically been short of.

| ID | Feature | Impact | Effort | Risk | Principle |
|----|---------|--------|--------|------|-----------|
| F85 | The guide — a fauna companion that explains the app, starting with Site Info | **High** | L | Med — new UI surface | P5, P13 |
| F86 | Notes that add up — one store, notes from anywhere, a document that does something | Med | M | Med | P11, P4 |
| ~~F87~~ | ~~Game-style save/load~~ — **shipped V2.39**: `user_data_dir()/saves`, Save stops asking, File → Open lists your designs (name · when · plants · species · site), and the crash-recovery autosave moved out of the `$HOME` dotfile | **High** | M | Low | P13 |
| F88 | The Learn tab as a curriculum — the app, design, flora & fauna; gamified | Med | L | Low | P5, P7 |
| F89 | The 3D preview's UX review — ten buttons over two rows | Med | M | Med | P5 |

### F85 · The guide — *Impact High · Effort L · Risk Med (P5, P13)*

*"A 'clippy' like helper (I would make it a fauna like a caterpillar or bird) that guides you
through using the app and explains/breaks down certain things. For example Site Info is
overwhelming to most beginner users and even long time landscape designers. The helper could
say, this is what this means for your site, this is what growing degree days are, etc."*

**Do the cheap half first, and separately.** About **12 of ~20 Site Info metrics have no
explanation at all** — no tooltip, nothing — while `src/climate.py:96` `zone_description()`
returns exactly the right sentence for the hardiness zone and is **called by nothing**, and
`climate.py:112-124` holds an excellent plain-English account of GDD₅ that exists only as a
developer comment. A Qt-free glossary module plus one `setToolTip` per metric answers the
tester's actual example at a fraction of the cost, and gives the guide something to read out
when it is built.

**Then the companion.** Reuse: `onboarding.py`'s three-step progress model, `docent.py:102`'s
beat shape (`id + title + narration + viewer state` — the same skeleton with a different
payload), `onboarding_flow.on_step_clicked`'s tab/tool navigation, and
`welcome_dialog._ChoiceButton`. Genuinely net-new: a beginner/expert flag (none exists
anywhere), any widget-anchoring concept, tour-progress persistence, and the art — there is no
caterpillar drawing in the repo in any format, and the only bird is a `.glb`.

**The risk worth naming:** a helper that keeps people looking at the screen argues against
**P11** (the body and the site know things the screen does not). The guide should push people
outside, not substitute for going.

### F86 · Notes that add up — *Impact Med · Effort M · Risk Med (P11, P4)*

*"There should be an option to make a note from any menu or on the design itself and have all
these notes feed a master note doc that can use this info in a functional way rather than just
a record."*

There are **five** disconnected note stores today: field notes (`properties.field_notes`, a
closed vocabulary of 10 prompts), map annotations (GeoJSON point features, free text, no
timestamp), the design journal (`properties.notes`, one flat string), photo notes (a DB
column), and a display-only mirror at `planning_panel.py:1096`. `format_field_notes()` exists
and is called from nowhere; none of it reaches the PDF except the journal. "Functional rather
than just a record" is the hard half — start by asking what a note should be able to *do*
(become a task, pin to a plant, date-stamp an observation) before unifying the storage.

### F87 · Game-style save/load — *Impact High · Effort M · Risk Low (P13)*

*"Saving a file should be more simple and similar to how game files are saved and loaded.
There should be a folder that they automatically save to. When loading a previously saved file
they should be listed in the app rather than opening the computer's file explorer."*

The precedent is already here: the worked example builds, saves to `user_data_dir()` and opens
through the ordinary load path with no dialog (`onboarding_flow.py:110-165`). Missing: a
`saves/` folder, per-save metadata (date, plant count, thumbnail), an in-app browser, and a
recent list. Worth fixing alongside: the autosave writes a **hidden dotfile in `$HOME`**
(`persistence.py:37`) rather than the data dir, which is nobody's mental model of where their
work lives.

### F88 · The Learn tab as a curriculum — *Impact Med · Effort L · Risk Low (P5, P7)*

*"Learn tab can include a range of topics from learn the app, learn landscape design/philosophy,
learn about native flora and fauna. Can gamify this somewhat too."*

`lesson_track.py` already has the shape (id / title / teaching text / live readout / status)
but every step is about *the design*, not about the app or the discipline, and progress is not
persisted — `LessonTrackWidget._i` resets on every refresh. **P12 applies with force here:** a
"learn about native flora" track must not become a route to Indigenous plant-use knowledge by
the back door.

### F89 · The 3D preview's UX review — *Impact Med · Effort M · Risk Med (P5)*

*"This whole 3-D preview could use an UI and UX review."* Ten buttons across two rows, plus
three sliders and two combos. V2.37 reordered row 2 and flipped the mouse buttons; the
structural question is untouched. Theme F's prescription applies — an honest retirement pass
before any restructure.

---

## Theme H — the Learn side (V2.43 → )

Recorded here in V2.45 at the author's request, so it stops living only inside plan
documents. V2.43 split the app into **Learn** and **Design** at boot; V2.44 made the
sandbox a place you can work in; V2.45 gave the animals real flight. What follows is
the rest of it, in the order I would take it.

**Shipped so far:** F96 two doors · F97 editable reference landscapes · F98 species
ledger · F99 per-plant age + nursery stock · F100 edit animations + the net · F101
split view · F102 one 3D toolbar · F103 flight physics.

### F104 · Undo in the sandbox, and the graduation path — *Impact High / Effort M / Risk Low*

Two gaps V2.43 left, and the first is the more embarrassing:

* **The sandbox has no undo at all.** Design mode has full undo/redo; Learn mode — the
  side built for people who do not know what they are doing yet — makes every misclick
  permanent. That is exactly backwards.
* **There is no bridge between the two doors.** "Take this landscape into Design" —
  turn the fen you built into a real design at your address — is what would make Learn
  *lead* somewhere instead of being a side room. Mostly a coordinate transform: the
  sandbox is already a real project (`src/reference_edit.py`).

### F105 · Challenges and achievements — *Impact High / Effort M / Risk Med*

Briefs with win conditions over the sandbox: *"support 5 bee species on 20 m²"*,
*"keep something in bloom every week April→October"*. Scored by machinery that already
exists — `habitat_score.py`, `forage_calendar.py`, `habitat_nudges()`. **F13**
(reference-community fidelity) drops to effort S now that F50 resolves the community,
and is the natural win condition for "rebuild the parkland from memory".

**Bank achievements for going outside.** This is the P11 counterweight and it is not
optional: a game that rewards screen time argues against the principle the app is
built on. F32 (printable field checklist) and F33 (observation journal) are the hooks —
an achievement for logging a first bloom date beats one for clicking a button.

Also here: the ledger's `how` column records only the *first* sighting's method, so
catching something you had already glimpsed still reads as "inspected". An achievement
tier wants that upgraded; it is a deliberate hold from V2.44, not an oversight.

### F106 · The companion, and the glossary half of it — *Impact Med / Effort L / Risk Med*

Pick a native bee, butterfly or chickadee at first boot; it explains things as you go.
Reuses `docent.py`'s beat shape and `learn_state` (schema v62) for the choice.
**The art does not exist in this repo in any form**, so this is mostly a drawing
problem, not a code one — budget accordingly.

**Do the cheap half first and separately.** ~12 of ~20 Site Info metrics have no
explanation anywhere, and `src/climate.py:zone_description()` returns exactly the right
sentence and is called by nothing. A Qt-free glossary module plus one `setToolTip` per
metric answers the tester's actual complaint at a fraction of the cost, and gives the
companion something to read out later.

**Risk on file (P11):** a helper that keeps people looking at the screen argues against
the principle. Mitigate by having it push you outside.

### The curriculum, and plant ID — *see F88 and F83*

Four tracks: the plants, the ecosystem, design principles, the app itself.
`lesson_track.py` already has the shape and `learn_state` can now persist position.
**F83 is three-quarters built already** — 33 botanical and 31 zoological drawn SVGs
exist in `html/botany/`, served over `/api/vocab`, with a working "click the drawing
that matches" interaction in the tuning bench. What is missing is content, not code.

**P12 applies with force here.** A "learn about native flora" track must not become a
back door to Indigenous plant-use knowledge. There is already a test scanning labels
and headings for ethnobotanical vocabulary; any new learning surface must be added to
its scan.

### Smaller, cheap, high-value — carried from the V2.43 backlog

* **Citations in the UI (F12).** The V2.42 audit found all 361 edges properly cited and
  *not one citation visible anywhere*. The V2.45 hover tip finally shows one number's
  basis; the other 361 are still invisible.
* **Ornamental → native swap card (F49)** — a 25-row starter list proves it.
* **Better creature models.** The bee is spheres plus two flat discs; the bird is
  spheres, a cone beak and a box tail. V2.45 made them *move* correctly, which raises
  rather than lowers the value of making them *look* correct. Blender work through
  `scripts/blender/assetlib/fauna.py`; the morphology to drive it now exists for all
  three flying taxa.
* **Photo coverage** — 111/434 plants and 84/142 fauna have no photograph, which caps
  how good the net's species page can be.
* **Verify the bird morphology** (V2.45). All 24 rows ship `verified = 0`: they were
  entered from published literature in a session with no network access. A session with
  egress should re-derive them from AVONET (Tobias et al. 2022, CC BY 4.0) and Dunning's
  *CRC Handbook of Avian Body Masses*, then flip the flag. **Wing area is null for every
  row** — the one bird measurement not routinely published, currently inferred from span
  and a per-style aspect ratio.

---

## Recommended sequence

Ordered for the WANT/RECOGNISE lens and for the owner's stated priorities.

### Increment 1 — the photographs (one coherent job)
**F70 → F71 → F72**, with **F74** riding along because it is the same table and the same print path.
One schema bump, one curation tool, one reseed rule. Do it first: it is the cheaper of the two
priorities, it unblocks F73/F74, and every existing surface that shows a photo improves for free the
moment `image_url` is synthesised from a `habit` slot.

### Increment 2 — the surface (the biggest look jump available)
**F63** (shared atlas) with **F65** (the aspect correctness bug) alongside it, since both touch the
generator and the viewer material path in the same week.

### Increment 3 — the variety that actually fixes the ratio
**F64** (species tables, absorbing F60) → **F66** (seed heads) → **F67** (creature variety). This is
the authoring-heavy stretch, and it is what takes the library past 75 looks. **F68** (real wind) is
a good palate-cleanser between them — a day's work for a disproportionate gain in liveliness.

### Increment 4 — WANT / SHOW
**F69** (presentation still) → **F76** (before/after/five years) → **F77** → **F75**. Decide the
P13 proposal before or during this increment, so the work has a principle to answer to.

### Increment 5 — the designer
**F92** (order file — a day) → **F91** (substitution) → **F90** (variants) → **F93** (palettes).

### Then
Theme E, or an explicit decision to demote it. Theme F's retirement pass whenever a release is
otherwise light.

---

## Corrections made to the existing documents

Two pieces of factual drift found during this review and fixed in place:

- **`DESIGN_PHILOSOPHY.md` P5 was stale.** Its State marker read *partial*, on the grounds that
  ecological relationships were "still not drawn as networks (roadmap F5, F15)". F5 shipped in
  V2.31 — the relationship web overlay is exactly that drawing — and F15 was merged into it. The
  marker and its reasoning have been updated.
- **`DESIGN_PHILOSOPHY.md` P9 cited "roadmap item C"**, which does not exist in any roadmap; the
  entry it means is F14 (establishment-likelihood band). Corrected.

Both are the kind of drift `tests/test_philosophy.py` cannot catch — it guards that the twelve
themes exist and that code anchors name real principles, not that the State markers still tell the
truth. Worth a periodic manual pass; worth *not* trying to automate, since the honesty of a State
marker is a judgement.

---

## Method notes (carried forward, plus one)

- **McHarg overlays (P5/P11):** new layers should compose, not replace.
- **Alexander patterns (P1/P7):** prefer generative rules over one-off layouts.
- **Tallamy "why" (P6/P8):** every recommendation answers "why does this matter?" with data.
- **Uncertainty (P9):** ranges and confidence, never false precision. Applies with particular force
  to F71 — do not build a classifier for "is this a whole-plant photo"; there is no signal, and a
  guess dressed as a filter is the exact failure this principle names.
- **Indigenous knowledge (P12):** directional only, gated on free, prior and informed consent. **No
  entry in this roadmap touches it**, and the photo-sourcing and curation work must not become a
  route to plant-use knowledge by the back door.
- **Discipline:** domain logic Qt-free and Python-side, map/viewer JS thin, mind the
  `tests/test_architecture_guard.py` ceilings — especially `plant_panel.py` for anything in
  Theme B, and `html/map/06-overlays.js` for anything on the map.
