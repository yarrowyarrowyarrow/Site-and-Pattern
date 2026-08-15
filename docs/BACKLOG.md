# Site & Pattern — the backlog

**Everything not yet built, in one place.** Written V2.52, verified against the
codebase rather than against the previous roadmap.

This file exists because the question *"what could I work on next?"* had no
answer that could be read in one sitting. The unbuilt entries were spread across
`ROADMAP_NEXT.md` (eight lettered themes, inside 1,052 lines that are mostly a
shipped record), `PHILOSOPHY_ROADMAP.md` (F1–F62), `ROADMAP.md` (the legacy
X/P/V ledger), `USER_FEEDBACK.md`, and the tails of `SPRITE_AUDIT.md` and
`DATA_GAPS.md`. Four entries had shipped and were still listed as open; two were
half-built with no note saying which half; one feature was described twice under
two IDs.

**How this relates to the other four documents.** This is the *index* — one line
per thing, enough to choose from. The **reasoning** for each entry (what it is,
how it would be built, what it leans on) stays where it was written:
[`ROADMAP_NEXT.md`](ROADMAP_NEXT.md) for F63 and up,
[`PHILOSOPHY_ROADMAP.md`](PHILOSOPHY_ROADMAP.md) for F1–F62. Follow the ID.

**The rule that keeps this file honest: a row leaves when it ships.** The shipped
record belongs in `ROADMAP_NEXT.md`'s Shipped section and the release plans under
[`plans/`](plans/). If this file ever starts carrying history, it has stopped
being useful.

**Ratings.** Effort: **S** (hours to a day) · **M** (a few days) · **L** (a week
or more) · **XL** (a program of work). Risk: Low / Med / High — chance of
breakage, scope creep or a hard dependency. **P** names the design principle from
[`DESIGN_PHILOSOPHY.md`](DESIGN_PHILOSOPHY.md).

**Totals: 34 code features · 6 data jobs · 4 legacy-ledger items.**
*(V2.52: 41. Shipped since: F8/F12/F13/F14/F28 in V2.53, F121 in V2.54, F122 and
F104 in V2.55, F76 and F75 in V2.56, F92 and F91 in V2.57. Opened since: F120,
F123, F124 — all three found by the increments themselves.)*

---

## The state of the argument

The roadmap's own list of *what this app is not good at yet* has five entries.
Since it was written, **two and a half have been paid down**:

| Weakness | State |
|---|---|
| "It looks like a diagram" | **Largely fixed** — V2.33/34/36 (surfaces, aspect axes, florets, seed heads, fauna morphology) |
| "Its photographs don't show the plant" | **Unmoved.** 111 of 434 plants have none, **0 species have a habit shot**, 62 of 69 bees have none. Group C |
| "It never argues that a native yard is beautiful" | **Paid down** — V2.56 (F76 before/after/five years, F75 cues to care) |
| "It has no professional workflow" | **Half built** — V2.57 (F92 the order file, F91 substitution). F113 and F93 remain |
| "It sprawls" | **Unbuilt.** Group F |

That observation had a companion, and it is worth recording that it stopped
being true: through V2.51 the note here read *"the design side proper has not
had an increment since V2.42."* V2.56 and V2.57 were both design-side, which is
why two of the five moved at once.

What is left is lopsided rather than long. **Photographs** are gated on a
licensing decision only the owner can make (Group C), **sprawl** is an L-effort
restructure (Group F), and the two remaining professional-workflow walls are
both bigger than the two that fell. The cheap work now is not in these five at
all — it is the three bugs the increments found while building other things
(F120, F123, F124), each of which is small and each of which is waiting on a
decision rather than on engineering.

---

## A · Confidence and provenance

> **✅ Shipped in V2.53** — F8, F12, F13, F14 and F28 together, over one shared
> vocabulary (`src/confidence.py`). Plan:
> [`V2.53-the-confidence-block`](plans/V2.53-the-confidence-block.md). One row
> survives, because the increment found a contradiction it deliberately did not
> resolve.

| ID | Feature | Effort | Risk | P |
|----|---------|--------|------|---|
| **F124** | **The layer map misses 311 of 437 species, and the Habitat Value Score reads low because of it.** Found while building F91 in V2.57. `habitat_score.PLANT_TYPE_TO_LAYER` knows six `plant_type` values; the catalogue holds eleven. The five it misses — `wildflower` (**210 species, the largest group**), `grass`, `sedge`, `rush`, `aquatic`, `fern` — map to no layer, so the vegetation-layer component counts them as nothing. **Measured: a 12-plant prairie meadow of wildflowers, grasses and sedges scores 0 of 15 on layer diversity**, which is this app's own central use case scoring zero on a component it plainly satisfies. Adding one shrub and one tree takes it to 6. The fix is a few dictionary rows; what makes it the author's call is that it **raises the score of every affected design**, which the headline-stability rule reserves to you. F91 works around it with its own complete map (`substitution.SUBSTITUTION_GROUPS`) rather than widening the canonical one as a side effect | S | Med — raises scores | P6, P2 |
| **F120** | **Correct the 48 use tags the cited edges contradict.** V2.53 measured it: **37 species carry a documented `larval_host` edge and no `host_plant` tag** (Chokecherry and Balsam Poplar among them) and 11 carry a `fruit_food`/`seed_food` edge and no `bird_food` tag. The Habitat Value Score's host and bird-food components read the *tags*, so those designs score lower than the app's own cited data supports. V2.53 stopped the prose asserting the absence and left the score alone on purpose — correcting the tags **moves every affected design's score**, which the stability rule says is a decision to take deliberately. Measured by `data_quality.validate_use_tags_against_edges`; needs a seed-data edit and a `_SCHEMA_VERSION` bump | S | Med — moves scores | P9, P3 |

---

## B · WANT and SHOW — the argument the app doesn't make

*The app argues superbly that a native yard is ecologically valuable. Nobody
converts a lawn on ecological grounds alone, and nobody's spouse, neighbour or
HOA does. Principle 13 exists to name this.*

**✅ F76 and F75 shipped in V2.56** — before / after / in five years as one page,
and the cues-to-care checker. Plan:
[`V2.56-the-argument-never-made`](plans/V2.56-the-argument-never-made.md).
F77 (the neighbour's-eye view) shipped in V2.33 as the `sidewalk` camera preset.
One row survives, and it is a bug the increment found rather than a feature it
declined to build.

| ID | Feature | Effort | Risk | P |
|----|---------|--------|------|---|
| **F123** | **The presentation still never reaches the PDF.** Found while wiring F76 in V2.56. `pdf_export.export_pdf` takes `still_pixmap` and `_draw_presentation_still` draws a full page from it — and `app.py`'s `_on_export_pdf` calls `export_pdf(path, project, enriched, structs, notes, pixmap)` and **never passes it**, so F69's page has been unreachable from the app's own Export PDF since it shipped. The 3D window can save a still to a PNG but does not retain the pixmap, so the fix is a small design decision (retain it, or let the export offer a still picker) rather than a one-line wiring change — which is why V2.56 reported it instead of taking it | S | Low | P13 |

---

## C · RECOGNISE — the photographs

*Six weeks after planting, can they tell their milkweed from a weed? The
structural work landed in V2.35/V2.36 (seven named slots, user photos that
survive a reseed, the curation bench, the candidate picker). What is left is two
features and one decision, and the decision gates most of the remaining data
work — see also Group J.*

| ID | Feature | Effort | Risk | P |
|----|---------|--------|------|---|
| **F73** | **"In my yard, on this date."** Tag a user photo to a *placed plant* and a *date*, and it stops being reference material and becomes an observation. F51's phenology prompt ("we predict X in bloom around now — is it early, late, on time?") finally has somewhere to land; the old F33 observation journal is delivered with the best possible entries; and after two or three seasons the user owns their own site's bloom dates, against which the app's shipped ranges can be checked. **The `taken_on` column already exists** (`src/db/photos.py`, schema v55) — this is UI work now, not a schema bump | M | Low | P11, P4 |
| **F74** | **The seedling sheet.** In May a first-year conversion is forty unidentifiable green rosettes and the beginner weeds their own milkweed. Mostly assembly: the `seedling` slot supplies the images, keyed to F41's numbered planting map so the sheet and the plan share one numbering, printed with the planting document. Be honest where there is no photo (P9) — which makes the gaps a visible target. **Blocked on content, not code:** essentially no species has a seedling photo yet | S–M | Low | P11, P8 |
| — | **The bee photo-licence decision — the owner's call, not the roadmap's.** 62 of 69 bees have no photograph *because* bees are held to a stricter bar than everything else: CC0/CC-BY only, no ShareAlike (the F37 A1 decision, enforced in `data_quality.validate_fauna_images`). Options: **(a)** accept CC-BY-SA for bees as for other taxa and take on the ShareAlike obligation, **(b)** keep the bar and accept that most native bees ship without a photo, leaning on F67's models to carry the identification, **(c)** source them ourselves. Worth deciding before any curation pass, because it changes what there is to curate | — | — | — |

---

## D · The designer's workflow

*A landscape designer using this professionally hits four walls, none of which is
about ecology.*

**✅ F92 and F91 shipped in V2.57** — the order file a nursery accepts, and
ecological substitution when the nursery is out. Plan:
[`V2.57-the-last-centimetre`](plans/V2.57-the-last-centimetre.md). Two walls
left, and both are larger than the two that fell.

| ID | Feature | Effort | Risk | P |
|----|---------|--------|------|---|
| **F113** | **Design variants + side-by-side comparison.** *(Renumbered from F90 in V2.52 — F90 is the shipped plant directory.)* No designer presents one option, and the app holds exactly one project. "Duplicate as a variant", then a comparison view: habitat score, cost range, first-year and steady-state hours, food-web status, species and wildlife counts, native ratio, with the deltas named. Every number exists; holding two projects at once and diffing them is the missing part. Also on-message — presenting options with their trade-offs rather than one confident answer is P9 at the scale of a whole design | L | Med | P9, P1 |
| **F93** | **Reusable palettes / go-to communities.** A designer repeats themselves across sites; that is craft, not laziness. Save the current selection as a named palette and apply it to a new site **with site-fit re-checking**, which is the part a human cannot do quickly and this app can. Extends `polycultures`, which already carries user-authored rows through a reseed | M | Low | P1 |

---

## E · The Learn side and the curriculum

*V2.43 split the app into Learn and Design at boot; V2.44–V2.46 made the sandbox
a place you can work in and gave the animals real flight. This is the rest of it.
F85 and F106 were the same feature described twice and are merged here.*

| ID | Feature | Effort | Risk | P |
|----|---------|--------|------|---|
| **F105** | **Challenges and achievements.** Briefs with win conditions over the sandbox: *"support 5 bee species on 20 m²"*, *"keep something in bloom every week April→October"*. Scored by machinery that exists — `habitat_score`, `forage_calendar`, `habitat_nudges` — with **F13** as the natural win condition for "rebuild the parkland from memory". **Bank achievements for going outside**, which is not optional: a game that rewards screen time argues against the principle the app is built on. F32 and F73 are the hooks | M | Med | P11, P13 |
| **F85** | **The companion.** *(Absorbs F106 — the two entries proposed the same thing in the same words.)* A fauna guide (a caterpillar, a bee, a chickadee) that explains the app as you go, starting with Site Info. Reuses `onboarding.py`'s progress model, `docent.py`'s beat shape (`id + title + narration + viewer state`), `onboarding_flow.on_step_clicked`'s navigation, and `learn_state` (schema v62) for the choice. Genuinely net-new: a beginner/expert flag, any widget-anchoring concept, tour-progress persistence, **and the art — there is no caterpillar drawing in this repo in any format**. Risk on file: a helper that keeps people looking at the screen argues against P11, so it should push you outside | L | Med | P5, P13 |
| **F107** | **Hand-painted lepidoptera wings.** *"A generic butterfly does nothing."* Half of this already exists and is worth looking at first — `scripts/tune_fauna.py` already edits wingspan, forewing/hindwing/margin colours, wing shape, pattern, resting posture and flight style, each with a drawn SVG vocabulary. What does not exist is the painting: the fauna GLBs ship with **no UVs and no textures by contract**, so the lep material needs its own path in `09-models.js`; plus a wing template to paint against, an import path (reuse `photo_import` — a specimen photographed in a yard carries that yard's coordinates), and a schema slot with `origin='seed'` vs `'user'` semantics so a reseed cannot destroy hand-painted work. Wants a conversation about the template before any code | L | Med | P13, P5 |
| **F83** | **Know the plant, not just the design.** Plant-identification lessons: show a photograph, ask for the character, score it. **Three quarters built** — 33 botanical and 31 zoological drawn SVGs exist in `html/botany/`, served over `/api/vocab`, with a working "click the drawing that matches" interaction in the tuning bench, and `learn_panel.py` already has Field Study while `lesson_track.py` has the progress model. What is missing is content: it wants the `habit` and `leaf` photo slots filled first | M | Low | P5, P7 |
| **F88** | **The Learn tab as a curriculum.** Four tracks: the app, design and philosophy, the flora, the fauna. `lesson_track.py` already has the shape (id / title / teaching text / live readout / status) but every step is about *the design* rather than about the app or the discipline, and progress is not persisted (`LessonTrackWidget._i` resets on every refresh — `learn_state` can now hold it). **P12 applies with force:** a "learn about native flora" track must not become a route to Indigenous plant-use knowledge by the back door, and any new learning surface must be added to the test that scans labels and headings for ethnobotanical vocabulary | L | Low | P5, P7 |

---

## F · Surface and sprawl

*Six side tabs, roughly twenty sub-tabs, three inner tabs under Plants, ten
buttons on the 3D toolbar. Every one was justified when it landed. Together they
are why a novice cannot find the thing they need and a designer cannot get to a
deliverable quickly. There is precedent for fixing this well: the Forage tab was
retired in V2.25 once Planning → Wildlife covered the same question, and nothing
was lost.*

| ID | Feature | Effort | Risk | P |
|----|---------|--------|------|---|
| **F89** | **The 3D preview's UX review.** Ten buttons over two rows, plus three sliders and two combos. V2.37 reordered row 2 and flipped the mouse buttons; the structural question is untouched. An honest retirement pass first | M | Med | P5 |
| **F94** | **A task-shaped home**, or (first) **an honest tab retirement pass**. Organise by what the user is trying to do — Design · Understand · Plant · Learn — rather than by which subsystem owns the code. High risk, and it should not be attempted until the retirement pass shows what is genuinely load-bearing | L | High | P5 |

---

## G · Notes, and going outside

*P11 (the body and the site know things the screen does not) is the principle
this app has always been thinnest on in practice.*

| ID | Feature | Effort | Risk | P |
|----|---------|--------|------|---|
| **F32** | **Printable field-mode checklist.** A site-walk sheet through `pdf_export.py` so the user records outside and enters findings afterwards. Pairs with F6's field notes, and it is **the last unbuilt item in the ACT/OUTPUT stage** — everything else in that column shipped in V2.31 | S | Low | P11 |
| **F86** | **Notes that add up.** *"There should be an option to make a note from any menu or on the design itself and have all these notes feed a master note doc that can use this info in a functional way rather than just a record."* There are **five** disconnected note stores today: field notes (`properties.field_notes`, a closed vocabulary of 10 prompts), map annotations (GeoJSON points, free text, no timestamp), the design journal (`properties.notes`, one flat string), photo notes (a DB column), and a display-only mirror in `planning_panel.py`. `format_field_notes()` exists and is called from nowhere; none of it reaches the PDF except the journal. **The hard half is "functional rather than just a record"** — start by asking what a note should be able to *do* (become a task, pin to a plant, date-stamp an observation) before unifying the storage | M | Med | P11, P4 |

---

## H · Depth and relationships

*Connoisseur depth. Ranked here by cost, cheapest first, because several got much
cheaper when F7 landed and nobody has re-read them since.*

| ID | Feature | Effort | Risk | P |
|----|---------|--------|------|---|
| **F19** | **"Why here?" — the placement rationale.** Half already built: the V2.29 click-to-learn dossier answers "what is this and what does it support" on click. The only missing piece is *why the generator put it there*, which is a few sub-score lines from `placement_score` added to a card that exists (verified absent from `scene_dossier`) | S | Low | P2, P5 |
| **F49** | **Ornamental → native swap card.** The garden-centre moment, and the single most likely place to change a real purchase. Needs a curated `data/native_swaps_master.json` (ornamental name, the aesthetic role it plays, the native substitute keyed to a real `plants` row, the ecological gain), a table, a schema bump and a lookup module. **A 25-row starter list of the ornamentals actually sold in Alberta big-box garden centres is enough to prove it**, which is a much smaller commitment than the card implies | S–M | Med | P6, P8 |
| **F38** | **Mycoremediation / degraded-site notes.** Well-cited restoration techniques for contaminated and compacted ground. Content, directional | S | Low | P8 |
| **F18** | **Site-condition remediation advisor.** From measured soil and disturbance, recommend a *repair sequence* — pioneer cover → soil builders → target community. `property_data.fetch_soil` returns pH and texture; combine with the plants' pH envelopes and `succession.successional_role` | M | Med | P8, P4 |
| **F23** | **Declarative, inspectable placement rules.** P1's honest gap: the generative rules (density per m², native-first, anti-monoculture, layer balance) exist but are constants buried in `placement_score` and `llm_design`. Lifting them into a named, documented, tweakable rule object is the difference between *claiming* generative design and showing it | M | Low | P1 |
| **F25** | **Mycorrhizal / symbiosis edges.** Promote the facts now buried in plant `notes` (Frankia, ericoid, AMF, inoculation needs) to first-class data. **Since F7 this is no longer a subsystem** — seed a table, add a `UNION ALL` arm to the `relationship_edges` view, register an `EdgeKind`, and it appears in the relationship web, `neighbourhood()` and the scripting API for free. The remaining work is the data, which is the honest bottleneck: most of these facts are genus-level | M | Med — schema | P3 |
| **F26** | **Successional-sequence edges.** "Pioneer A prepares the ground for climax B" as a real relationship, driving planting order and the timeline. Same discount as F25, and it is the one edge kind that is genuinely *directed* between two plants, so it exercises the `directed` flag the view already carries | M | Med — schema | P3, P4 |
| **F29** | **Scenario ranges on the timeline.** A growth/maturity *band* rather than a single line, from a slow/expected/fast spread of `years_to_maturity` | M | Low | P9, P4 |
| **F21** | **Ecosystem-services readout.** Carbon, stormwater retention, cooling, pollination as honest ranges beside the habitat score. **Only worth building if the ranges stay wide and loud** — otherwise it invites exactly the false precision P9 forbids | M | Med | P6, P9 |
| **F36** | **Emergent community spacing.** Generate `polyculture_members` offsets from competition and canopy rules instead of fixed offsets. F22/F35 already give naturalistic spacing, so this is refinement | L | Med — schema | P1, P4 |
| **F27** | **Habitat-corridor analysis.** Connect the design to adjacent natural features — relationship thinking at landscape scale. Speculative, and it needs external data | L | Med | P3 |

---

## I · 3D fidelity leftovers

*What the sprite audit and the V2.36 fauna work left open. New IDs assigned in
V2.52 so each has a handle.*

| ID | Feature | Effort | Risk | Where it came from |
|----|---------|--------|------|---|
| **F114** | **Wing-pattern geometry** — eyespots and bands as procedural decals. Written and then **removed**: the marks attached to the wing pivots and positioned correctly but would not render, a coplanar-decal ordering problem that resisted polygon offset, depth-test and explicit render order inside a sensible budget. The data, the vocabulary, the drawings and the bench are all in place, so this is geometry work on a settled contract rather than a rebuild | M | Med | deferred from F84 |
| **F115** | **Shrub aspect within a silhouette** — the within-class spread the herb and layer axes already got | M | Med — asset size | sprite audit |
| **F116** | **Fern density** | S | Low | sprite audit |
| **F117** | **Billboard fruit** — the last billboard in a scene that is otherwise geometry | S | Low | sprite audit |
| **F118** | **Better creature models.** The bee is spheres plus two flat discs; the bird is spheres, a cone beak and a box tail. V2.45 made them *move* correctly, which raises rather than lowers the value of making them *look* correct. Blender work through `scripts/blender/assetlib/fauna.py`; the morphology to drive it now exists for all three flying taxa | M | Med | Theme H backlog |
| **F119** | **Birds, mammals and other insects still resolve from name tables.** Birds render 24 species as 16 looks; F84 gave bees and lepidoptera real morphology columns and left the rest on substring matching against the common name. The schema-v58 pattern is proven and repeatable | M | Med — schema | F84 |

---

## J · Data work — startable today, no code required

*The bottleneck on several features above is data, not engineering. These are the
jobs that move it, with the tooling that already exists.*

| Job | State, and the next step |
|---|---|
| **Flower colour** | 359 species still carry a genus-level guess. 81 are grasses with no bloom colour and are excluded; of the 276 left, **110 sit in 25 genus groups sharing one hex** — the columbine bug's exact shape. `python scripts/colour_worklist.py --sheet colour-check.html` writes a contact sheet of the 199 that already have a photograph, worst group first, with the claimed colour as a swatch under each image. Two sittings. The 77 with no photograph need a flora, or a photo first |
| **Photo coverage** | **111 of 434 plants** have no photograph; **0 species have a habit shot**; 84 of 142 fauna and **62 of 69 bees** have none. The bench (`scripts/tune_morphology.py`) has the candidate picker and the slot editor. Gated on the bee-licence decision in Group C |
| **iNaturalist observation photos** | The remaining lever for the 111 species with nothing: `/v1/observations?taxon_id=…&photo_license=…&quality_grade=research` for species whose taxon photo set is thin. Scoped in V2.36, not built |
| **Bird morphology** | All 24 rows ship `verified = 0` — entered from published literature in a session with no network. **Wing area is null for every row**, the one bird measurement not routinely published, currently inferred from span and a per-style aspect ratio. Needs a session with egress: AVONET (Tobias et al. 2022, CC BY 4.0) and Dunning's *CRC Handbook of Avian Body Masses* |
| **Peace River Parkland** | A missing ecoregion. Raised in V2.51 rather than taken, because adding a polygon changes what real properties get recommended |
| **Real CEC ecoregion polygons** | The shipped outlines are hand-authored and every drawing says so (`CAVEAT`). The download is written up in [`plans/V2.38-ecoregion-runbook.md`](plans/V2.38-ecoregion-runbook.md) and needs a machine with open egress |

---

## K · Legacy ledger

*Still marked "Planned" in [`ROADMAP.md`](ROADMAP.md), which is otherwise a
historical document. Listed for completeness; none is ranked.*

| ID | Feature | Note |
|----|---------|---|
| **X1** | Google Earth KML/KMZ import and export | Unranked. The scan-import and OSM pipelines cover most of what it was for |
| **X4** | Community design sharing — export/import designs through a shared online library | Unranked. `.perma.geojson` is already a portable file; the missing part is a place to put it |
| **V1** | Vegetation layer indicators — per-layer markers and a layer toggle | Unranked. Partly covered by the relationship web's layer filter and the 3D layer archetypes |
| **P4 / P5** | Crop rotation tracker · input/output ("energy leak") mapping | **Retirement candidates.** Both are permaculture-era, from before the V1.x pivot to native habitat, and neither has been coherent with the product for a long time |

---

## L · Retired from the open lists

*Carried here once, so the next reader does not go looking for them. Each was
listed as open somewhere and is not.*

| ID | Why it is closed |
|----|---|
| **F77** · the neighbour's-eye view | **Shipped V2.33.** `src/presentation_still.py` declares `CAMERA_PRESETS = ("overview", "orbit", "walk", "sidewalk")` and names it as F77 in a comment; the camera is in `html/scene3d/08-modes.js` |
| **F62** · aspect axis on layer archetypes | **Shipped V2.33 as F65** (renumbered on the way in) |
| **F60** · blade-class axis on tree archetypes | **Absorbed by F64**, shipped V2.33 |
| **F20** · maintenance-over-time curve | Delivered in substance by **F42** — `maintenance_calendar` ships 36–76 → 18–38 → 9–19 → 6–11 hours a year, with a test that fails if the curve ever flattens. Only a chart is missing, and it belongs inside F42 rather than as its own card |
| **F33** · seasonal observation journal | **Subsumed by F73 + F86.** A dated photograph tied to a placed plant is a better journal entry than a timestamped string, and F86 owns the unification |
| **F15** · pollinator-pathway overlay · **F30** · invisible-relationship legend | **Merged into F5**, which shipped in V2.31 with a legend and a filter row. A month scrubber on that overlay is the remaining cheap follow-on |
| **F31** · glossary page | **Folded into F45.** In-context definitions beat a separate page — but note the *Site Info tooltips* half in Group E is genuinely unbuilt |
| **F34** · shearing-layers data audit | **Retired as a feature.** It is a data-quality check and belongs as an assertion in `src/data_quality.py` |
| **F39** · sensor integration hooks | **Dropped until a user asks.** Speculative IoT, external dependency, no evidence of demand, unchanged on the list for a very long time |

---

## If you want a recommendation

The pick is the owner's. Asked for one, in order:

1. **F124 then F120 — make the score tell the truth.** Both are small, both are
   measured, and both are gated only on your decision to let scores move. F124
   is the starker of the two: the app's central use case, a prairie meadow,
   scores **zero** on a component it obviously satisfies.
2. **Group D — F113 (design variants) or F93 (reusable palettes).** Two walls of
   the professional workflow are down; these are the two left, and both are
   bigger than what shipped.
3. **Group F — the sprawl.** Named as a weakness, and the 3D toolbar's size
   ceiling has now shaped three increments running, which is the guard telling
   you something the backlog already says.

*(Group A's confidence block shipped in V2.53, Group B in V2.56, and half of
Group D and Group E besides. The pattern this file was written to expose —
"next" meaning "not this time, again" — is broken.)*
