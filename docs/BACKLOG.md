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

**Totals (at V3.08): 46 code features · 13 data jobs · 4 legacy-ledger items.**
*(V2.52: 41. Shipped since: F8/F12/F13/F14/F28 in V2.53, F121 in V2.54, F122 and
F104 in V2.55, F76 and F75 in V2.56, F92 and F91 in V2.57, F125 in V2.59, F124
and F127a in V2.60, F128 in V2.62, F127/F130 in V2.63–V2.64, **F120/F129/F131 in
V2.65**. Opened since: F120, F123, F124 — all three found by the increments
themselves — plus F126 from author feedback, F127/F128, which are the two
halves of F125 that its own gates refused to guess at, F129, which F124
exposed the moment it was fixed, and F131, which F128's own re-fetch made
possible two increments after it landed. **V2.83**: the VASCAN, synonym-merge and
occurrence-point data jobs had shipped in V2.80–V2.82 without leaving this file,
and six rows opened from the V2.83 review, F153–F158, as group M. The totals were
recounted from the rows rather than adjusted. **V2.84**: F153, F156 and F158 shipped,
F159 opened. **V2.85**: F154 and F155 shipped, F160 opened. **V2.86**: F162–F164 shipped; F161 staged and waiting on the author's VASCAN run; F165–F167 opened. **V2.87**: F161 shipped; F168–F171 opened. **V2.88**: nine opened by the 3D model audit, F172–F180 in group O, all counted as code features; F117 gained the fruit-size finding and F119 narrowed to birds and mammals. **V2.89**: F176 and F179 shipped; F181 and F182 opened, both found by that work; F172 gained the Wild Clematis flower. **V2.90**: F175 and F181 shipped; F183 opened, found by that work; F172 gained buckbean's leaf size. **V2.91**: F182 and F183 shipped; F184 opened, found by that work, and F185 numbered, the pond rule V2.90 left open. **V2.92**: F178 shipped; F186 opened, found by that work. **V2.93**: F177 shipped; F172 gained Roseroot's flower colour. **V2.94**: F186 shipped; F187 and F188 opened, both found by that work. **V2.95**: F185 shipped; F189 opened as a data job; F172 gained Spiked Water-milfoil's name. **V2.96**: F188 shipped; F180 gained the shrubs' shared leaf green. **V2.97**: F174 shipped; F190 opened, found by that work; F119 gained the birds' body length. **V2.98**: the review of picking and placing numbered its six steps F191–F196 and the start-screen race F197, as group P; F193 shipped, so six opened. **V2.99**: F191 shipped, on the owner's call, since it reversed V2.37; F198 opened, the half of the review's finding 10 no step answered. **V3.00**: F192 shipped, which took F194's "suits this site" order and its one filter set with it; F199 opened as a data job and F200 as a feature, both found by that work. **V3.01**: F194 shipped; F201 opened as a data job, found by that work. **V3.02**: F195's keyboard and screen-reader half shipped and its row narrowed to what can be seen, so the total is unchanged. **V3.03**: F195 shipped, its visual half, with a fix found on the way (Leaflet drew small plants as ellipses); F202 and F203 opened, both found by that work. **V3.04**: F197 shipped, with two fixes the owner reported (a filter list needing a second click to close, and the 3D preview on a slope); F204 opened, found by the second. **V3.05**: F19, F32, F123, F196, F198, F199 and F200 shipped, bundled with the retirement pass F94 and F89 asked for first ([`SURFACE_AUDIT.md`](SURFACE_AUDIT.md)), which leaves both open for the owner's decisions; F167 was found already done (its row arrived with `has_thorns` set when F161 promoted it in V2.87) and closed. Nothing opened: what the audit left is in its own page. **V3.06**: F205, the north arrow and scale bar, opened and shipped together on the owner's request, so the totals do not move. **V3.07**: the owner answered the audit; the first half of F94 shipped and it stays open, and the answers that are features of their own opened as F206–F211, group Q. **V3.08**: F94 shipped, its second half (Design's merges, Notes on one page, a Share place, Planning merged away), with F209 and F210; F89 narrowed to the 3D preview's creature list and F86 to its one store; F212 opened, found by that work.)*

---

## The state of the argument

The roadmap's own list of *what this app is not good at yet* has five entries.
Since it was written, **two and a half have been paid down**:

| Weakness | State |
|---|---|
| "It looks like a diagram" | **Largely fixed** — V2.33/34/36 (surfaces, aspect axes, florets, seed heads, fauna morphology) |
| "Its photographs don't show the plant" | **Barely moved.** 111 of 434 plants have none and 62 of 69 bees have none — but `plant_photos.json` shipped as a literal `[]` until V2.62, and **the first habit shot in the catalogue is now in it**. Group C |
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
all — it is the bugs the increments keep finding while building other things,
each of which is small and each of which is waiting on a decision rather than
on engineering. F124 shipped in V2.60 and produced F129; F129 and F120 both
shipped in V2.65 and F120 produced its own correction (the taxon requirement)
before it landed. **F123 is what is left of that seam.** The measured bugs are
a renewable resource, because measuring one exposes the next. *(F123 shipped in
V3.05.)*

---

## A · Confidence and provenance

> **✅ Shipped in V2.53** — F8, F12, F13, F14 and F28 together, over one shared
> vocabulary (`src/confidence.py`). Plan:
> [`V2.53-the-confidence-block`](plans/V2.53-the-confidence-block.md). One row
> survives, because the increment found a contradiction it deliberately did not
> resolve.

| ID | Feature | Effort | Risk | P |
|----|---------|--------|------|---|
| ~~**F124**~~ | ✅ **Shipped in V2.60.** The layer map knew six of the catalogue's eleven `plant_type` values, so 311 of 437 species — `wildflower` alone is 210 — occupied no vegetation layer and a prairie meadow scored 0 of 15. Now complete and **height-aware**, because filing all 292 herbaceous-group species under one layer would have reached 3 of 15 and called it fixed; the 0.30 m groundcover boundary is read off the catalogue's own `groundcover` type. The meadow reaches 6 of 15. **The residual is bigger than the fix and is now F129** | S | Done | P6, P2 |
| ~~**F129**~~ | ✅ **Shipped in V2.65.** The layer component's denominator is now the **reference community's own layers**, not the five-layer forest-garden stack. `reference_ecosystem`'s specs were already honest (Mixedgrass Prairie and Wet Meadow declare no canopy genera) and `reference_fidelity` already dropped zero-count layers, so the fix reuses that judgement rather than copying it — a test reads the source to prove it. A prairie planting on prairie: 6.0 → **10.0 / 15**. The same planting in Aspen Parkland **drops to 3.8**, which is the point: a measurement that could only raise the number would be a compliment. The 12 callers that pass no ecoregion are unmoved, and the panel row names its basis | M | Done | P6, P2, P9 |
| ~~**F120**~~ | ✅ **Shipped in V2.65.** 117 contradictions by the time it was taken. The first pass proposed 101 species and was wrong: reading the relationship alone let a bumblebee, a grasshopper, a gall midge, a horntail and a **deer mouse** vote. 107 of 346 `larval_host` edges are not lepidoptera, and `host_plant` is what drives design_critic's butterfly/moth line — so `_TAG_BACKED_BY_EDGE` now names the taxon that has to be at the far end, and the gate and the fixer read the one table. **80 real corrections**: `host_plant` 30 → 95, `bird_food` 78 → 104, worked example **+7 points**. Additive only — absence of an edge is absence of evidence (P9) | S | Done | P9, P3 |

---

## B · WANT and SHOW — the argument the app doesn't make

*The app argues superbly that a native yard is ecologically valuable. Nobody
converts a lawn on ecological grounds alone, and nobody's spouse, neighbour or
HOA does. Principle 13 exists to name this.*

**✅ F76 and F75 shipped in V2.56** — before / after / in five years as one page,
and the cues-to-care checker. Plan:
[`V2.56-the-argument-never-made`](plans/V2.56-the-argument-never-made.md).
F77 (the neighbour's-eye view) shipped in V2.33 as the `sidewalk` camera preset.
One row survived, a bug the increment found rather than a feature it declined
to build, and it shipped in V3.05.

| ID | Feature | Effort | Risk | P |
|----|---------|--------|------|---|
| ~~**F123**~~ | ✅ **Shipped in V3.05.** The 3D window keeps the last still it renders on the main window (`scene3d_window.keep_still`, as `before_after_flow` keeps F76's) and Export PDF passes it, so F69's page reaches the PDF; its status line says so. A new or opened design drops the last one's still and before/after, so one design's render cannot reach another's PDF | — | Done | — |

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
buttons on the 3D toolbar. (V3.05 counted them from the real window: 6 tabs, 26
pages, 169 controls, 18 in the 3D window; [`SURFACE_AUDIT.md`](SURFACE_AUDIT.md).)
Every one was justified when it landed. Together they
are why a novice cannot find the thing they need and a designer cannot get to a
deliverable quickly. There is precedent for fixing this well: the Forage tab was
retired in V2.25 once Planning → Wildlife covered the same question, and nothing
was lost.*

| ID | Feature | Effort | Risk | P |
|----|---------|--------|------|---|
| **F89** | **The 3D preview's UX review.** Ten buttons over two rows, plus three sliders and two combos. V2.37 reordered row 2 and flipped the mouse buttons; the structural question is untouched. An honest retirement pass first. *(V3.05: the pass is in [`SURFACE_AUDIT.md`](SURFACE_AUDIT.md). Its sliders, 15 px wide at 1366 × 768, have their own row now: when, how you move, what you do. Left: Refresh from design is a manual sync; the creature list is the 721 rows typing cannot search, F196's other copy, waiting on the split `scene3d_window.py`'s ceiling asks for; the outputs' place; the light window.)* *(V3.08: the preview follows the design, its two outputs are on Share › Export as well, and the window is dark ([plan](plans/V3.08-design-and-share.md)). Left: the creature list.)* | M | Med | P5 |
| ~~**F94**~~ | ✅ **Shipped in V3.07–V3.08.** The retirement pass came first, as this row asked ([`SURFACE_AUDIT.md`](SURFACE_AUDIT.md), V3.05), then the owner's decision on every page, then the restructure: five side tabs by the question a person brings (Site, Placement, Design, Share, Learn), Planning merged away, one Share place for what leaves the app, and every jump to a page made by the page, not its index (`src/side_panel_layout.py`; [plan](plans/V3.07-placement-and-the-site-tab.md), [plan](plans/V3.08-design-and-share.md)) | L | High | P5 |

---

## G · Notes, and going outside

*P11 (the body and the site know things the screen does not) is the principle
this app has always been thinnest on in practice.*

| ID | Feature | Effort | Risk | P |
|----|---------|--------|------|---|
| ~~**F32**~~ | ✅ **Shipped in V3.05.** Site › Field Notes › *Print this sheet…* prints the ten site-walk prompts in walking order on one page, each with a box to tick, what is already noted, and ruled lines to write on, then three lines for anything else; the ruling spaces itself to fill the page (`field_notes.walk_sheet`, `pdf_export.export_field_sheet`). The design PDF carries the same page as its first job, before Site prep. It was the last unbuilt item in the ACT/OUTPUT stage | — | Done | — |
| **F86** | **Notes that add up.** *"There should be an option to make a note from any menu or on the design itself and have all these notes feed a master note doc that can use this info in a functional way rather than just a record."* There are **five** disconnected note stores today: field notes (`properties.field_notes`, a closed vocabulary of 10 prompts), map annotations (GeoJSON points, free text, no timestamp), the design journal (`properties.notes`, one flat string), photo notes (a DB column), and a display-only mirror in `planning_panel.py`. `format_field_notes()` exists and is called from nowhere; none of it reaches the PDF except the journal. **The hard half is "functional rather than just a record"** — start by asking what a note should be able to *do* (become a task, pin to a plant, date-stamp an observation) before unifying the storage. *(V3.08: one page, Site › Notes, holds the site walk, the design journal and the notes pinned on the map; the stores are unchanged.)* | M | Med | P11, P4 |

---

## H · Depth and relationships

*Connoisseur depth. Ranked here by cost, cheapest first, because several got much
cheaper when F7 landed and nobody has re-read them since.*

| ID | Feature | Effort | Risk | P |
|----|---------|--------|------|---|
| ~~**F19**~~ | ✅ **Shipped in V3.05.** The cell the generator chose is read back in words (`placement_score.explain_cell_for_plant`: "Full sun, as it likes", "…not its best: the closest fit left", slope, edge, a tree's drip line), and every other placing rule names itself (`src/why_here.py`: a vine at its host's foot, a mixed stand, a community, the design review's additions, the pond), carried on the plant's feature as `why_here` and shown first on its page: 108 of 108 plants in a probe design, from 71 of 102 when only scored cells said. **A click on a placed plant now opens that page**: the map had always sent the click, and nothing in Python listened. With no terrain or shade for the site the page says the plants were only spread out. Hand-placed plants carry none. Left: the 3D preview's card is per species and a reason is per plant, so it does not show there | — | Done | — |
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
| **F117** | **Billboard fruit** — the last billboard in a scene that is otherwise geometry. **And sized (V2.88 audit):** every fruit sprite is drawn 17 to 34 cm across whatever the species, because nothing records how big a fruit is; a geometry fruit needs a fruit-size field to be drawn at | S–M | Low — schema for the size | sprite audit |
| **F118** | **Better creature models.** The bee is spheres plus two flat discs; the bird is spheres, a cone beak and a box tail. V2.45 made them *move* correctly, which raises rather than lowers the value of making them *look* correct. Blender work through `scripts/blender/assetlib/fauna.py`; the morphology to drive it now exists for all three flying taxa | M | Med | Theme H backlog |
| **F119** | **Birds and mammals still resolve from name tables.** Birds render 24 species as 16 looks; F84 gave bees and lepidoptera real morphology columns and left the rest on substring matching against the common name. The schema-v58 pattern is proven and repeatable. *(Other insects left the name tables in V2.88: `src/fauna_body_plan.py` reads the group each row's description records. V2.97 gave birds their body by genus (F174), and the colours are still the name table. It also left one span-to-length ratio per build, so a bird whose tail is long or short for its family is drawn 14-25% off: magpie and catbird short, the nuthatches, Red-eyed Vireo and House Finch long. `bird_morphology` records wingspan and not length; a recorded length would let the viewer size the body too)* | M | Med — schema | F84 |

---

## J · Data work — startable today, no code required

*The bottleneck on several features above is data, not engineering. These are the
jobs that move it, with the tooling that already exists.*

| Job | State, and the next step |
|---|---|
| **Flower colour** | *(Counts below are from V2.52. At V2.83, after V2.80 read 143 colours from a flora: **196 of 417** species are still `estimated`, 143 `flora`, 35 from the name or epithet, 43 blank.)* 359 species still carried a genus-level guess. 81 are grasses with no bloom colour and are excluded; of the 276 left, **110 sit in 25 genus groups sharing one hex** — the columbine bug's exact shape. `python scripts/colour_worklist.py --sheet colour-check.html` writes a contact sheet of the 199 that already have a photograph, worst group first, with the claimed colour as a swatch under each image. Two sittings. The 77 with no photograph need a flora, or a photo first |
| **Photo coverage** | **111 of 434 plants** have no photograph; **0 species have a habit shot**; 84 of 142 fauna and **62 of 69 bees** have none. The bench (`scripts/tune_morphology.py`) has the candidate picker and the slot editor. Gated on the bee-licence decision in Group C |
| **iNaturalist observation photos** | The remaining lever for the 111 species with nothing: `/v1/observations?taxon_id=…&photo_license=…&quality_grade=research` for species whose taxon photo set is thin. Scoped in V2.36, not built |
| ~~**Name the 1,194 held animals**~~ | ✅ **Shipped across V2.63 (F127) and V2.64 (F130).** The naming question was answered by the author — *scientific name only for those without a common name* — and it unblocked everything: **998 animals admitted, 820 written in V2.64 alone**, fauna 167 → **1,147**, edges 2,813 → **7,714**, coverage 275 → **302 of 437**. 101 of the last 820 have an accepted English name and **719 keep their binomial**, which for a solitary bee is the name rather than a shortfall. What is still held is 120 species I could not place and 42 trinomials the catalogue cannot key on — neither is waiting on a decision. **The unfinished thread is elsewhere**: 18 admitted animals get no row because every one of their records is an adult nectaring observation GloBI files as `eatenBy`, and F128's 41% life-stage data is the untaken route to the ~700 refused `larval_host` edges behind them |
| **The last 46 uncited edges** | ✅ **F128 shipped in V2.62** — 2,406 of 2,452 GloBI edges now cite a named study, specimen collection or GBIF dataset, and the bibliography grew from 13 works to 46. The 46 that remain matched no observation record and no further fetch will change that; they still cite the aggregator, honestly. **Body part came back 0% across all 13,665 records**, so the sapsucker and mammal-browse edges V2.60 dropped are not recoverable from `/interaction` in any mode — a closed door rather than an open task. Life stage came back at 41%, which is a real shot at the 700 refused `larval_host` records and is not yet taken | **F128** |
| ~~**Re-derive the ranges without the buffer**~~ | ✅ **Shipped V2.76.** Re-fetched from GBIF 2026-08-21 and derived by containment. Records 489,546 → **361,447**; region rows 4,215 → **3,643**; species with rows 422 → **420**. `--buffer-artefacts` put the error at **493 of 4,218 claims (11.7%)** and, more usefully, showed it was **concentrated in one region**: `western_continental_ranges` is the BC interior ranges clipped to a hairline inside Alberta (0.02% of the mapped area, 36× smaller than Northern Continental Divide), so its five-kilometre apron swept in nearly every montane record near the border — **135 species → 15**. Interior regions barely moved (Cypress Upland 231 → 228, Selwyn Lake Upland 10 → 8), which is what a boundary fix should look like. Two species lost every row (*Panicum virgatum* at 3 records, *Symphyotrichum campestre* at 6) and now band `unknown` rather than `unlikely`, because under-collected and absent are indistinguishable below the floor. The point cache means the next such question costs no network |
| ~~**Ask VASCAN about nativity and names**~~ | ✅ **Shipped in V2.80** (F137/F144/F149). The API could not be asked usefully, so the checklist was read from VASCAN's Darwin Core Archive instead; every one of 417 rows now carries `native_provinces_source = 'flora'`. Plans: [`V2.80-the-inference-gets-a-source`](plans/V2.80-the-inference-gets-a-source.md), [`V2.80-the-names-were-the-problem`](plans/V2.80-the-names-were-the-problem.md) |
| **The recombinations, and four names that need a flora** | *(Was "The Old World binomials"; the renames and merges shipped in V2.80 and V2.82.)* What is left is one decision and four look-ups. **18 recent recombinations** VASCAN accepts and the regional floras have not adopted (*Galium boreale* → *Trichogalium boreale*, *Spartina* → *Sporobolus*, *Ledum* → *Rhododendron*…) are allowlisted with a reason each in `data_quality.KNOWN_NOMENCLATURE`: which nomenclature the site follows is **the author's call**, made once for all 18. And four names need a printed flora rather than the archive: *Carex rostrata* / *utriculata* possibly exchanged, *Viburnum opulus* publishing a native claim under a name that covers the European guelder-rose, and "Indigenous Ricegrass" and "Rat Root" / "Bear Root" as P12 questions. Plan: [`V2.82-the-harebells-were-not-swapped`](plans/V2.82-the-harebells-were-not-swapped.md) |
| ~~**Merge the synonym duplicates**~~ | ✅ **Shipped across V2.80 and V2.82.** The Stiff Goldenrod pair was resolved by the archive (`KNOWN_NATIVITY_CONFLICTS` is empty), *Achillea millefolium* merged into *A. borealis*, and V2.82 merged five more pairs VASCAN showed to be one taxon (422 → 417). `validate_accepted_names` now fails the gate on a new one |
| **Manitoba** | *"'Prairie provinces' usually includes MB and some of the same ecozones extend through SW MB."* Fair, and the scope is one line: `tools/ecoregions/common.py` sets `SUBJECT_PROVINCES = ("Alberta", "Saskatchewan")`. V2.75 removed the MB filter chip the site was offering on the strength of **one species**, and said the limit plainly instead. Doing it properly is a `tools/ecoregions/` rebuild with MB as a subject province, a wider window and GBIF bbox, and a full re-derivation. Note `interlake_plain` already ships as the SK fragment of a mostly-Manitoba ecoregion, and is the only one of the 24 keys with **zero** species rows |
| ~~**Publish the occurrence points**~~ | ✅ **Shipped in V2.80 as F147**: 171,896 marks over 426 species, herbarium specimens and field observations as separate layers with a no-JavaScript toggle, CC-BY-NC admitted for a coordinate but not for a photograph on the author's V2.79 reasoning. Plan: [`V2.80-only-facts-backed-by-data`](plans/V2.80-only-facts-backed-by-data.md) |
| ~~**Promote the seven staged trees (F161)**~~ | ✅ **Done in V2.87** by the author's VASCAN and GBIF runs; all seven promoted, two widened to AB, SK. Plan: [`V2.87-the-trees-arrive`](plans/V2.87-the-trees-arrive.md) |
| **Candidate species (F168)** | 50 native plants the catalogue does not carry, in six groups with expected provinces and reasons: [`CANDIDATE_SPECIES.md`](CANDIDATE_SPECIES.md). In through the pending file and the author's VASCAN run, the route V2.87 proved |
| **Widen the under-claimed provinces (F170)** | 37 rows VASCAN records in Saskatchewan that the catalogue calls Alberta-only, filed by the ingest under *confirm*. Since V2.85 the designer follows the province, so a Saskatchewan yard never gets June Grass or Bluebunch Fescue. A `widen` bucket, reported before applied; waiting on the author's yes |
| **The Green Milkweed row (F171)** | Filed *Asclepias ovalifolia*, named, coloured and described as *A. viridiflora*. Rename (the common name is the edge key), review, then add the real Green Milkweed through the pending file |
| **Bur Oak's Saskatchewan fauna (F165)** | 2 documented caterpillar-host edges against Chokecherry's 17: the edge sources were Alberta-centric and the oak is a Saskatchewan tree. The 26 cached GloBI candidates are mostly gall wasps the registry does not carry, and two are records the filter rightly refused. A sourcing pass on a machine with egress |
| **"Native Prairie Aromatics" and P12 (F189)** | A seeded community of seven: wild bergamot, sweetgrass, prairie sage, rat root, wild licorice, Seneca snakeroot and yarrow. Four of them (sweetgrass, prairie sage, rat root, Seneca snakeroot) are widely known on the prairies as Indigenous medicines. The description says only "strong aromatics, pollinator support". Whether the grouping sits inside P12's hard rule is **the owner's call**. Found by V2.95, which left it exactly as authored: its rat root needs standing water, and pulling it out as a side effect of a placement rule was too close to that line |
| ~~**Black Hawthorn's thorns (F167)**~~ | ✅ **Done in V2.87, closed in V3.05.** The row arrived with `has_thorns` set when F161 promoted it; the kid-safe filter leaves it out (checked: 375 kid-safe plants, no Black Hawthorn). The row stayed open here two releases after it was true |
| ~~**The five '1?' nativity flags (F199)**~~ | ✅ **Shipped in V3.05** (schema 92): the five are 1, and `data_quality.NATIVE_TO_ALBERTA` no longer allows '1?', so a native-only generated design includes them. *The row as it stood:* `native_to_alberta` still carries the seed's '1?' on False Box, Flat-topped White Aster, Round-leaved Alumroot, Stiff Sunflower and Tall Anemone, all five recorded in Alberta by VASCAN. The pickers read `native_province` since V3.00 and show them; the generator, its critic, the design goals and the API still filter on the flag (`native_only`), so a native-only design leaves them out. Set the five to 1 in `plants_master.json`, bump the schema, and `data_quality.NATIVE_TO_ALBERTA` can stop allowing '1?'. Found by V3.00 |
| **The soil pH ranges' provenance (F201)** | All 424 rows carry `soil_ph_min`/`soil_ph_max` and none says where they came from: 35 distinct pairs, 102 rows at exactly 5.5–7.5 and 74 at 6.0–8.0. Since V1.67 they decide what Browse hides at a site, 105 of 424 at pH 8.0 and 270 at 8.3, and since V3.01 the reader can see and remove that filter. Record a source per row (`soil_ph_source`, as `flower_colour_source` does), mark genus or reference defaults as estimated, and put the owner's question beside it: should an estimated range hide a plant, or only rank it. Found by V3.01 |
| **Bird morphology** | All 24 rows ship `verified = 0` — entered from published literature in a session with no network. **Wing area is null for every row**, the one bird measurement not routinely published, currently inferred from span and a per-style aspect ratio. Needs a session with egress: AVONET (Tobias et al. 2022, CC BY 4.0) and Dunning's *CRC Handbook of Avian Body Masses* |
| ~~**Peace River Parkland**~~ | ✅ **Arrived with the survey in V2.67**, as an Alberta natural subregion of Peace Lowland rather than as a hand-added polygon — which is why it was right to hold it in V2.51: drawing one more shape would have put a *guess* where a published boundary was available, in a layer that decides what real properties get recommended. Selectable in the filter since V2.68, along with the other 20 subregions |
| ~~**Real CEC ecoregion polygons**~~ | ✅ **Shipped in V2.66–V2.68.** `tools/ecoregions/` is a six-stage pipeline (fetch → inspect → harmonize → validate → render → export) and the layer is the **National Ecological Framework v2.2** rather than CEC: 24 ecoregions in 6 ecozones clipped to Alberta and Saskatchewan, with Alberta's 21 natural subregions joined **spatially, never by name**. Two of the three sources refuse a proxied session, so the author ran those stages. Adoption cost almost no code because V2.38 made the polygon file the vocabulary — but it did expose that `lookup_ecoregions` had never handled MultiPolygon, answering *you are in no ecoregion* rather than raising. The heuristic `ab_ecoregion` tags were re-derived by measured overlap in V2.68, and three of the six old regions turned out misplaced rather than coarse |

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

## M · Found by the V2.83 review

*A review of the code and the published site in V2.83. The catalogue work of
V2.66–V2.82 held up; these are the places where it is not reaching the people it
is for, or is wrong in a way a reader can see. Reasoning per row in the
`ROADMAP_NEXT.md` ledger; evidence in
[`plans/V2.83-the-work-was-not-reaching-anyone`](plans/V2.83-the-work-was-not-reaching-anyone.md).*

| ID | Feature | Effort | Risk | P |
|----|---------|--------|------|---|
| ~~**F158**~~ | ✅ **Released 24 Sep as V2.83** (`release-V2.83`), so an install from 25 Aug is offered it by Help → Check for Updates. Plan: [`V2.83-the-work-was-not-reaching-anyone`](plans/V2.83-the-work-was-not-reaching-anyone.md) | — | Done | — |
| **F157** | **A production site build anybody can repeat.** The 13 Sep publish has no analytics and no feedback form (its feedback page says so), because the flags are typed by hand at publish time. A checked-in config plus a build that refuses to publish without it. Needs the author's Umami website ID and feedback URL | S | Low | P9 |
| ~~**F153**~~ | ✅ **Shipped in V2.84.** 43 rows to `other_insect`, the mapping fixed, `validate_bee_taxon` in the gate. Plan: [`V2.84-a-wasp-is-not-a-bee`](plans/V2.84-a-wasp-is-not-a-bee.md) | — | Done | — |
| ~~**F156**~~ | ✅ **Shipped in V2.84**, and reaches readers when the site is republished (F157). Plan: [`V2.84-a-wasp-is-not-a-bee`](plans/V2.84-a-wasp-is-not-a-bee.md) | — | Done | — |
| **F160** | **Communities a province's natives cannot fill.** Since V2.85 a seeded community is offered only when every member is native to the yard's province: **10 of 58 are withheld in Alberta**, six of them only because they include Canada Goldenrod (Saskatchewan-only per VASCAN; Alberta's is likely *Solidago lepida*), and **32 of 58 in Saskatchewan**, because most were written for Alberta. Swap the goldenrod, and write Saskatchewan communities | S–M | Low — seed data | P1, P9 |
| **F159** | **The German yellowjacket is filed as native.** *Vespula germanica* carries `ab_native = 1` and "Ground yellowjackets, native"; it is introduced in North America. Found in V2.84 while moving the wasps, and left for its own change because a nativity correction is a decision, as *Rudbeckia hirta* was | S | Low — reseed | P9 |
| ~~**F154**~~ | ✅ **Shipped in V2.85.** Province-aware nativity, locality ranking from the 0.25° grid (`src/site_fit.py`), communities and repairs under the same rules. Plan: [`V2.85-recommend-for-the-yard`](plans/V2.85-recommend-for-the-yard.md) | — | Done | — |
| ~~**F155**~~ | ✅ **Shipped in V2.85.** 4–21 → 64–121 plants on a 216 m² yard, more species, no single species above a quarter. Plan: [`V2.85-recommend-for-the-yard`](plans/V2.85-recommend-for-the-yard.md) | — | Done | — |

---

## N · Found by answering the Bur Oak question (V2.86)

*Which native trees can do what Bur Oak does, for Alberta and for small yards. The answer was a group of genera; asking it found four things wrong. Reasoning in [`plans/V2.86-trees-for-where-the-oak-is-not`](plans/V2.86-trees-for-where-the-oak-is-not.md). The data rows it opened (F161, F165, F167) are in J.*

| ID | Feature | Effort | Risk | P |
|----|---------|--------|------|---|
| **F169** | **Junipers beside saskatoons.** Juniper is the alternate host of the Gymnosporangium rusts that spot saskatoon and hawthorn fruit. Since V2.87 Rocky Mountain Juniper reaches most small-yard designs, beside a Saskatoon; Common and Creeping Juniper always could. Companion "enemy" pairs only push plants a spacing apart and the spores travel far, so it needs a design rule: no juniper in a design with saskatoons, or the design says why it has both | S | Low — generator rule | P3, P13 |
| **F166** | **Larval-host records by genus.** The Lepidoptera attribute file names host genera (*Salix* for ten species, *Populus* for nine) that `src/db/derived_edges.py` never expands, as it does for nectar and pollen. Doing so would give a new tree edges on arrival and would restate published genus-level records, not invent them | M | Medium — moves the edge layer and every score that reads it | P3, P9 |
| ~~**F162**~~ | ✅ **Shipped in V2.86.** Birch and oak join the keystone genera; `KEYSTONE_GENERA` gated both ways; schema v87 | — | Done | — |
| ~~**F163**~~ | ✅ **Shipped in V2.86.** A tree taller than the lot is wide is too big for it. Calgary's yard 64 → 119 plants once its Lodgepole Pine went | — | Done | — |
| ~~**F164**~~ | ✅ **Shipped in V2.86.** "Burr Oak" finds Bur Oak, desktop and website | — | Done | — |

---

## O · Found by the 3D model audit (V2.87–V2.89)

*Every plant and animal the 3D preview draws, rendered through the real viewer and
checked against the species: 424 plants and 1,144 animals
([report](https://claude.ai/artifact/4DxfwtbLxQsLHWMdUkELXD), summarised in the
sixth pass of [`SPRITE_AUDIT.md`](SPRITE_AUDIT.md)). Batch A, the code fixes,
shipped in V2.88 ([plan](plans/V2.88-reading-what-was-recorded.md)). These are the
batches that need a new model, a data decision or a flora. The audit's advice on
size: **one family per increment**, smallest first (horsetails, then the pond, then
succulents), because 5 to 20 species is what one contact sheet can show clearly.
F172's corrections can ride along with whichever increment touches those species.
V2.89 shipped the climbers and the horsetails ([plan](plans/V2.89-climbers-and-horsetails.md)) and found F181 and F182 on the way.
V2.90 shipped the pond and F181 ([plan](plans/V2.90-vines-find-hosts-and-the-pond.md)) and found F183.
V2.91 shipped F182 and F183 ([plan](plans/V2.91-additions-find-open-ground.md)) and found F184; F185 is the pond rule V2.90 left open, numbered.
V2.92 shipped F178, the trees ([plan](plans/V2.92-trees-with-their-own-shape.md)), and found F186.
V2.93 shipped F177, the succulents and cacti ([plan](plans/V2.93-succulents-and-cacti.md)).
V2.94 shipped F186, the dark crowns ([plan](plans/V2.94-leaves-let-light-through.md)), and found F187 and F188.
V2.95 shipped F185, water plants in the pond ([plan](plans/V2.95-water-plants-go-in-the-pond.md)).
V2.96 shipped F188, the shrubs' shade ([plan](plans/V2.96-shrubs-show-their-shade.md)).
V2.97 shipped F174, the birds' bodies and where they stand ([plan](plans/V2.97-birds-with-their-own-bodies.md)).*

| ID | Feature | Effort | Risk | P |
|----|---------|--------|------|---|
| **F172** | **Catalogue corrections the audit found.** Six flower colours that look wrong (Prairie Coneflower recorded purple, Fuzzy-tongue Penstemon red, Common Paintbrush green, Late Yellow Oxytropis purple, Dwarf Raspberry and Moss Campion white); three habit records (Northern Bedstraw "sprawling", Western Wood Lily "grassy", Water Arum (Wild Calla) with its spathe counted as 40 flowers); 21 bird colour rows (the Downy Woodpecker is flicker-buff, the Rufous Hummingbird green); 21 bee genera missing from the look table, so 64 bees wear the default. *(V2.95)* **Spiked Water-milfoil** is *Myriophyllum sibiricum*, the native, but the name is the usual one for the Eurasian *M. spicatum*, a prohibited aquatic invasive in Alberta; the row's own notes warn, the buy list carries only the name. It needs VASCAN's English name, and until then the generator never picks it on its own. *(V2.93)* Roseroot's flower is recorded `#8e6fc4`, a lavender, where the species' flowers are a dark red-purple; the flora's word is only "purple", so the shade needs a source. *(V2.90)* Buckbean's leaf is recorded at 8 cm and drawn as the whole trifoliate leaf, small for leaflets that reach about 10 cm. *(V2.89)* Wild Clematis carries Blue Clematis's flower (`solitary`, `bell`, 3 cm) where descriptions give many-flowered axillary clusters of small open white flowers, and all six vines carry the banded `flowering_stems: 14`. **The colours need a flora check first**: the audit judged them from renders, not from photographs | S | Low — reseed | P9, P13 |
| **F173** | **Insect body plans.** A wasp (narrow waist, four wings), a true bug / aphid / hopper, an ant, a grasshopper or cricket, and a moth at rest (wings roofed or flat, not spread like a butterfly's). V2.88 put these groups on the nearest existing model and flagged them `interim`; this gives them their own. Reaches 92 wasps and sawflies, 33 bugs, 6 ants, 7 grasshoppers and 189 moths | M | Med — Blender generator | P5, P10 |
| ~~**F174**~~ | ✅ **Shipped in V2.97.** Nine bird builds, each authored with its wings at its birds' real span and a folded pair shown at rest, picked by genus (`src/bird_body_plan.py`). **Every bird had been drawn about 2.4 times its length**, not only the twelve: the viewer sets a model's width to the wingspan and the old wings were paddles (robin 52 → 22 cm, crane three metres long → standing 1.07 m). Hawks and owls sit on a tall tree's top, a hawk soars over a young design, an owl with no tree is not drawn; grouse and cranes walk on the ground; the goose and duck float on a pond. Left: one span-to-length ratio per build draws long- and short-tailed birds 14-25% off (F119); the ptarmigans' range (F190); bird colours (F172); no dove build (no plant edge, never drawn) | — | Done | — |
| ~~**F175**~~ | ✅ **Shipped in V2.90.** Each wetland plant drawn by its own body from its recorded habit (`src/pond_habit.py`): floating leaves on a pond's water, submerged plants showing only what reaches the surface, broad leaves on stalks, mare's-tail's whorled stems. Four submerged plants and Water Parsnip recorded correctly | — | Done | — |
| ~~**F176**~~ | ✅ **Shipped in V2.89.** Horsetails drawn as jointed stems from a new `jointed` growth form: whorled, whorled above, or plain banded rods with a pointed tip. The two grass plumes they wore are gone | — | Done | — |
| ~~**F177**~~ | ✅ **Shipped in V2.93.** Each succulent drawn by its own body (`src/succulent_habit.py`, `24-succulents.js`): the prickly pears as chains of spiny pads with their flowers on the rims, the ball cactus as a cluster of spiny globes, soapweed yucca as blue-grey rosettes of sword leaves sending up flower stalks in their season, roseroot as leafy stems, and the stonecrop, which the audit had passed, as flowering stems over a mat. New growth forms `pads` and `globose` (schema v91) | — | Done | — |
| ~~**F178**~~ | ✅ **Shipped in V2.92.** Ten trees with models of their own at their species' proportions: the elm's vase, box elder's several trunks and three-leaflet leaves, both cottonwoods, Peach-leaved Willow, the juniper as a cone foliated to the ground, water birch and Bebb's willow as clumps of stems, and pines with whorls, a crooked trunk and dead stubs instead of bottle brushes. Black Spruce stays White Spruce's model (P9: nothing recorded tells them apart) | — | Done | — |
| ~~**F179**~~ | ✅ **Shipped in V2.89.** The owner's rule: a vine climbs the tree or shrub whose footprint touches its own, and with none it lies on the ground, 30 cm at most. Decided once in Python (`src/vine_habit.py`) and fitted to the host's drawn crown | — | Done | — |
| ~~**F181**~~ | ✅ **Shipped in V2.90.** The generator seats each vine at the base of a tree or shrub it planted, on the sunny side, and with none says so in the design notes (the owner's option c) | — | Done | — |
| ~~**F182**~~ | ✅ **Shipped in V2.91.** A grass, sedge or rush is never pollinator forage, bloom period or not (the owner's rule), in both forage calendars: the docent's and Planning → Wildlife. The docent's season beat, which had never played because its callers pass no bloom data, now does | — | Done | — |
| ~~**F183**~~ | ✅ **Shipped in V2.91.** What the design review adds goes in open ground, read from the plants actually placed (`src/open_ground.py`): free ground by the main pass's spacing, the ground that suits the plant, beside the planting; a vine at a shrub's foot. Never a plant that needs standing water; an animal fed only by such plants gets a note instead | — | Done | — |
| **F184** | **The habitat score counts grass bloom.** Bloom continuity (20 of 100 points) reads every `bloom_period`, graminoids included, and the critic's bloom-gap repairs read its gaps. Most designs do not move, because their wildflowers cover the grasses' months; a grass-heavy prairie mix does, 52 → 46, with June and July a real gap the score calls covered, so the critic never offers a June bloomer. **A headline change, reserved to the owner**; until then the forage calendars and the score disagree about grasses, on purpose | S | Low — but moves the headline | P6, P9 |
| ~~**F185**~~ | ✅ **Shipped in V2.95.** A plant that needs standing water goes in a pond or is not placed (`src/pond_planting.py`): floating and submerged plants in the open water, emergents in the shallows of the north two-thirds of the shore, floating leaves on at most half the water; with no pond they are left out and named. A pond the design left bare is planted, the pond communities are seated in the pond, and the wildlife and goal top-ups use it. **In the app the generated pond had never reached the map at all**: the controller copied only plants, so generated structures now come too | — | Done | — |
| ~~**F186**~~ | ✅ **Shipped in V2.94.** Leaves let light through: a leaf seen from its shaded side takes the sun and sky falling on its far side, times the share a leaf passes (0.55 for broad leaves, 0.45 for herbs, 0.3 for needles), and the baked shade now falls on the sky, with only 30% of it on the sun. The crown bake stands on the ground, not on the crown's lowest leaf. Over the 20 trees from 1.6 m, near-black 57% → 38%; Trembling Aspen 39% → 2%. The evergreen conifers improve least: dark recorded colours, opaque needles and the shade between tiers, with the weak ground bounce (F187) adding a little | — | Done | — |
| **F187** | **The ground bounce is a seventh of what it should be.** A surface facing down is lit only by the hemisphere light's ground colour, `0x5d6e51` at 0.9 (0.13 in luminance). The viewer's own noon sun and sky, falling on the ground it draws, would reflect about 0.9. It keeps a spruce's tier undersides, trunks, walls and animals' bellies dark on their shaded side. It is not the main reason the evergreen conifers are still 45-74% near-black from a path after V2.94: two brighter ground colours were tried and the conifers gained only 0.02-0.03 in luma, where their dark recorded colours, opaque needles and the real shade between tiers weigh more. **A look for the whole viewer, so the owner's call**: every scene changes | S | Med — every scene's look | P13 |
| ~~**F188**~~ | ✅ **Shipped in V2.96.** The shrub layer asked for its leaf material without saying its geometry carries colours, which reads as no, so no shrub had drawn its baked shade or Stylised's gradient. Turned on, the old bake put 35% of a shrub's pixels near-black from a path; the eight shrub models are rebaked with the trees' `CROWN_AO`. Over the 53 shrubs from 1.6 m, near-black 19% → 25%, still brighter than the trees; from above the shade between leaf clusters rises 19%. Every `surfaceMaterial` call must now state the argument | — | Done | — |
| **F190** | **Animals carry no range.** The three ptarmigans, alpine and arctic birds, are placed in 28% of simulated designs because they eat bearberry, bog blueberry and alpine bistort, which grow in yards too. Plants gained a locality check in V2.85 (`site_fit`, F154); animals have nothing like it, so any animal with an edge to a planted species can appear anywhere. The ranges need a source per animal, then the same rule: ranks and labels, not a filter, where the evidence is thin (P9) | M | Med — needs data | P9, P11 |
| **F180** | **Telling species apart.** 80 grasses, sedges and rushes share three shapes; 51 rosette wildflowers look like one dark lettuce; the asters read as grass; 45 species on the smallest narrow-leaf variant read as bare stems. *(V2.96)* 40 of the 53 shrubs share one leaf green, the viewer's shrub default `#4f7a3a` (`scene_contract._FOLIAGE_BY_TYPE`): nothing records a shrub's leaf colour, and those shrubs are the darkest from a path. A colour per species needs a source per species, as F172's do. Ongoing: 10 to 20 species per sitting against reference photographs, on the tuning benches (`scripts/tune_morphology.py`). Shrub stretch is F115, fruit size F117, butterfly wing patterns F114 | L, ongoing | Low | P5, P13 |

## P · Found by the V2.98 review of picking and placing

*The app run on a virtual display (1440 × 900 and 1366 × 768, Arial-metric fonts,
the example design) and its accessibility tree read through AT-SPI, to answer the
owner's "it seems somewhat crowded and somewhat inaccessible". The review proposed
six steps in order, numbered here **F191–F196** so "step 3" and "F193" are one
thing; the owner chose step 3 first. Its report lives outside the repo, so the
findings each step answers are summarised in its row. V2.98 shipped F193
([plan](plans/V2.98-placing-moves-to-the-map.md)), V2.99 F191
([plan](plans/V2.99-looking-is-not-placing.md)), V3.00 F192 ([plan](plans/V3.00-one-picker-one-species-page.md)),
V3.01 F194 ([plan](plans/V3.01-filters-people-can-read.md)), V3.02 F195's keyboard and screen-reader half ([plan](plans/V3.02-keyboard-and-screen-reader.md)), V3.03 its visual half ([plan](plans/V3.03-what-can-be-seen.md)), V3.04 F197 ([plan](plans/V3.04-start-screen-filters-and-the-slope.md)), V3.05 F196, F198 and F200 ([plan](plans/V3.05-every-surface-counted.md)).*

| ID | Feature | Effort | Risk | P |
|----|---------|--------|------|---|
| ~~**F191**~~ | ✅ **Shipped in V2.99.** Selecting only looks: it names the plant on a Place button under the list, or shows the community, and leaves the map alone. Measured on V2.98, a click, ▶, an arrow key and keyboard focus arriving in either list each armed the map. A Place action arms it (the button, Enter, a double-click, the context menu, which communities gained), and **once placing, choosing another plant switches to it**, so the V2.37 tester's "the last thing" still cannot be placed; a drag into the mix and ▶ do not switch. The map shows a footprint under the cursor: the plant, a Qty cluster as it will land, a pattern's first plant, a community's members at their offsets. Found on the way: a built mix rode along on any plant's Row/Grid/Circle and was planted instead; the pattern preview's rings had a 0.5 m floor, twice a forb's placed marker. Left: warnings after placing on other plants or over the boundary (F198); a keyboard way to put a plant down (F195) | — | Done | — |
| ~~**F192**~~ | ✅ **Shipped in V3.00.** Browse, the Plant Directory and the community builder are one picker (`plant_picker.py`) over one vocabulary (`plant_filters.py`): nine facets and nine qualities, the Directory's five role toggles folded into Role because they ran the same query. **The painted card is gone**: a plant's page, the Directory's widget page moved out of its window, opens beside the Browse list over the map's right edge on a click or an arrow, with Place and Add to mix; placing closes it. Each row badge has its own tooltip and a row reads its facts to a screen reader. The order is **Recorded near this site** when there is a pin (renamed from the review's "suits this site", which nothing here can know), then zone, pond plants last. The Directory's page can place when a design is open. Found on the way: the Native filter dropped five species VASCAN records in Alberta (F199), "Animals supported" had always sorted A–Z, and the page counted relationships as species (Boreal Yarrow 334, 296 animals). Left: Native follows Alberta wherever the pin is (F200) | — | Done | — |
| ~~**F193**~~ | ✅ **Shipped in V2.98.** A bar over the map while placing holds the pattern settings of both tabs and says what the next click does; it goes when placing stops, Esc in the map included, which Python could not see before: after Esc, one click on empty map planted a whole community outside the yard. The panels scroll instead of squeezing. Found and fixed on the way: community spacing did nothing for Row/Grid/Circle (16 communities in a 4.65 m row), a re-arm could fire after Esc, the spacing armed was the previous community's. Left: the habitat score live in Stats but behind Calculate in Analysis, the third bullet of the finding this step answered, which is not placing | — | Done | — |
| ~~**F194**~~ | ✅ **Shipped in V3.01.** A chosen filter reads its dimension and joins its values by its own rule ("Type: Tree or Shrub", "Role: Bird Food and Larval Host"), and each list opens on a line saying how ticked values combine, because Role keeps plants with *every* role and the rest keep plants with *any*. What is on is a row of chips, each removing its own filter, with Clear all; an empty result names the restriction that emptied it and offers to remove it, with the count that would bring back. The stale "● Shrub" had a cause: the wheel over a closed box, ↓, or Return in its list made Shrub the combo's current item, whose icon Qt draws and whose name Qt writes back when its tick changes; the combo now keeps no current item, the wheel scrolls the panel, and ↑, ↓ and Space open the list. The site's soil pH (hides 105 of 424 at pH 8.0) is a chip and a toggle, removable for the session, and leaves with the site, which it never had. Whether it should filter at all is the owner's call, raised; its ranges' provenance is F201 | M | Low | P9 |
| ~~**F195**~~ | ✅ **Shipped in V3.02 and V3.03.** *Keyboard and screen reader* (V3.02, [plan](plans/V3.02-keyboard-and-screen-reader.md)): focus visible everywhere, the map usable by keyboard, F6 between the map and the panel, the single letters scoped to the map, every control named, and Redo's Ctrl+Shift+Z, which never worked, fixed. *What can be seen* (V3.03, [plan](plans/V3.03-what-can-be-seen.md)): no text under 12 px (190 font sizes in the source, Plant Communities and Field Notes 90% under it), one muted grey at 5.5:1 for the four that failed, every control at least 24 px by one raise-only rule (`target_size.py`), and **plants coloured by type everywhere**: community members had been by layer until a reopen and the builder had five greens of its own. Each marker is outlined in its colour darkened 60% (grass 1.0:1 on the yard → 4.9:1; members on a canopy 1.0–1.8:1 → 4.5–6.7:1 on screen), and the legend is built from the markers' table: all eleven types, where it had six and no wildflower, and no "Community outline", which nothing drew (F202). Found on the way: Leaflet drew a sub-metre plant up to 44% out of round, and missed clicks on its top and bottom; every circle is round now. Also found: **an unticked checkbox's box was invisible** (1.11:1 under Fusion, 20 boxes on the window under 3:1), now drawn by one style (`indicator_style.py`, 6.3:1); and in DejaVu Sans, CI's font, Field Notes and Plant Communities scrolled sideways, now wrapping. Left: the edges of fields and buttons (F203), the satellite basemap, display scaling and high-contrast modes | — | Done | — |
| ~~**F196**~~ | ✅ **Shipped in V3.05.** Each community's row says its size, sun and moisture beside its name ("8 plants · Full Sun · Mesic"), a value left out when it is Unknown or Mixed; "For a creature…" has a find box that narrows its 721 rows and picks the first match (the Monarch was entry 446); the builder's Cancel asks before discarding a community laid out by hand, and closes at once when nothing was. Left: the sorts behind "No grouping" and "Sort: A–Z", and the builder's raw offsets and fixed-size dots | — | Done | — |
| ~~**F197**~~ | ✅ **Shipped in V3.04.** The start screen's Continue, Open a design, See a finished design and Recover waited for `map_ready`, which fires once per page load and had usually fired before anyone chose (traced in V2.98: ready at 1.92 s, Continue at 25.87 s, never loaded). The map now says whether it has loaded (`MapWidget.is_ready`) and a choice made after that is carried out at once, framed again when the map is first shown (`fitWhenShown`), since a map hidden behind the start screen is 0 × 0 | — | — | — |
| ~~**F198**~~ | ✅ **Shipped in V3.05.** The bar over the map says where each placement landed, with Undo beside it: "2 of 4 landed outside the boundary.", "It sits inside Blue Grama Grass's circle." (`src/landing_check.py`; inside means one plant's centre in the other's circle, half its spacing). It never refuses, since overlap is sometimes the design; it says nothing when the ground was clear, and nothing about a boundary when none is drawn. An undo clears it. Left: a tint on the markers that overlap | — | Done | — |
| ~~**F200**~~ | ✅ **Shipped in V3.05.** Native, the row badge and the Native toggle's tooltip follow the pin's province (`site_fit.province_at`): a Saskatoon yard's list keeps Saskatchewan's natives, as the generator beside it has since V2.85. No pin, or a pin outside the two provinces, keeps Alberta, as before | — | Done | — |
| **F202** | **A community drawn as one thing.** Nothing on the map outlines a placed community: its members share an id the move tool reads, and nothing else. Until V3.03 a freshly placed community's members were coloured by layer, which grouped them until the design was reopened and the loader drew them by type; V3.03 colours them by type from the start, so a community now reads as a cluster of plants, as a reopened one always did. V3.02's legend listed a "Community outline" that nothing drew. An outline in its own line (the members' hull, or the community's radius), drawn on placement and on load and following a move, with the community's name on hover, would make it one thing again. Found by V3.03 | M | Low | P10 |
| **F203** | **Edges you can see on fields and buttons.** 64 stylesheets outline text fields, dropdowns and secondary buttons in `#2e4a2e`, 1.52:1 on the panels, and a field's fill is 1.01:1 against the panel, so a field is found by its placeholder or its contents. WCAG 1.4.11 asks 3:1 of what identifies a control; a field says what it is in words, which is why V3.03 left it, but an empty field with no placeholder is a gap in the panel. `#5a8a5a` (3.75:1, the scroll handle's since V3.03) would carry it. Every panel's look changes, so it is the owner's call. Found by V3.03 | S | Low | — |
| **F204** | **3D terrain past the boundary.** The 3D view fetches elevation for the boundary's bounding box only (`zoning.site_elevation_grid`), and since V3.04 the ground beyond it holds the edge's heights, as `terrainHeightAt` has since V2.38: honest (no data, nothing invented), but on a hillside the view shows a level terrace past the fence, and a plant placed outside the boundary stands on that terrace rather than on the hill. Fetch the scene's extent, padded, for the 3D window (its own cache key; the grid limit is 10,000 cells at 10 m), keeping the boundary's grid for the generator. Found by V3.04 | S–M | Low | P9 |

## Q · From the owner's answers to the V3.05 surface audit

*The owner answered every page and question in [`SURFACE_AUDIT.md`](SURFACE_AUDIT.md)
on 2 October 2026. Most answers are moves inside F94 (the side panel), F89 (the 3D
preview) and F86 (notes); the asks that are features of their own are numbered here.
V3.07 enacted the first half of F94 ([plan](plans/V3.07-placement-and-the-site-tab.md));
V3.08 its merges, F89's answers, F209 and F210 ([plan](plans/V3.08-design-and-share.md)),
and opened F212; V3.09 is planned for F206, F207, F208 and F211.*

| ID | Feature | Effort | Risk | P |
|----|---------|--------|------|---|
| **F206** | **A community shown as a plant is.** The owner, keeping Plant Communities: "I quite like the way the 'plants' now show up in an adjacent 'pop up' and would like the same for plant communities for ease of scrolling, visibility and use. Selecting a plant community can show the pictures of the plants in the community in the pop up (not too big as I want it to be mostly all visible in one go) along with the description of the community and the ability to drop down into individual descriptions of the plants." A plant's page opens beside the list over the map since V3.00 (`species_page.py`, `species_flyout.py`); a community's would sit there too: its members as small photographs, its description, and each member's page a click away *(V3.09: the simple version shipped, a community's page beside the list with its members' photographs, its description and each member's page ([plan](plans/V3.09-community-page-and-features-scan.md), T2). Left: retiring the panel's own card, two side by side, editing from the page (T9).)* | M | Med | P10, P13 |
| **F207** | **Existing buildings and trees, read off the map and the satellite together.** The owner, on Site › Features: "a scan of both the map layer and the satellite layer to work in synchronicity to provide an accurate placement of existing buildings and trees … that can then be useful in the 3D view as well as the birds eye designers view." Today a building or tree comes from OpenStreetMap, an nDSM GeoTIFF, a phone scan or a hand drawing, and the satellite tiles are lined up by a manual nudge; nothing reads the two layers against each other. `footprint_extract.py` already has the seam for a segmentation backend (`set_extractor`) *(V3.10: the simple version shipped, *Scan this area*: buildings and trees in one click, one undo step, then a review ([plan](plans/V3.09-community-page-and-features-scan.md), T4). Trees from imagery already existed (`tree_detect.py`, `tree_detect_chm.py`, V2.26). Left: open building footprints, the satellite lined up automatically, buildings from the owner's own imagery (T6–T8).)* | L | High | P5, P11 |
| **F208** | **Field Study beyond a five-question quiz.** The owner, keeping it: "find ways to improve on this as it is currently quite rudimentary." It asks five recall questions from the design and the catalogue. F83's identification drawings and photo slots are the likeliest material; what "better" means is the first question for the owner | M | Med | P5, P7 |
| ~~**F209**~~ | ✅ **Shipped in V3.08.** Every primary button is the app's green: three were not (Sun & Shade's orange, Wind's teal and blue; the audit's purple had gone by then), and Refresh wind data is grey now the pin brings the rose. The 3D preview and Growth Snapshots wear the app's stylesheet (`ui_style.WINDOW_STYLE`), and a test fails on any button filled in a colour of its own | S | Low | P13 |
| ~~**F210**~~ | ✅ **Shipped in V3.08.** Nineteen opening paragraphs cut to what the page cannot say by itself, 3,487 characters to 2,103: lists the page shows anyway, restated headings, advice and slogans went; anything a person needs to act stayed | M | Low | P2 |
| **F211** | **3D on a machine whose graphics driver Chromium blocks.** QtWebEngine refuses WebGL on blocklisted drivers and the preview shows only its error message (V3.05 made that message plain). A software path, `--ignore-gpu-blocklist` or SwiftShader, would draw slowly rather than not at all; the owner said yes. The risk is a slow 3D view on a machine that should have used the hardware | M | Med | P5 |
| **F212** | **The address search reaches Saskatchewan.** Site Info's search is bounded to Alberta (the Nominatim query in `site_panel.py`'s geocode worker, "No Alberta results" when it finds nothing), while the generator's native filter (V2.85) and the plant list's Native (F200, V3.05) follow the pin into Saskatchewan, and the website covers both provinces. A Saskatchewan yard can be pinned by hand with Use Pin Drop, but not found by its address. Widening the bound to both provinces is small; the message and the view-centre bias go with it. Found by V3.08 | S | Low | P11 |

---

## If you want a recommendation

**The V2.83 review's order**, which puts delivery ahead of features: **F158** (release, so
installs get what has shipped) → **F157** (a site build that keeps its analytics and feedback
form) → **F153** (wasps out of bees) → **F156** (the site on a phone) → **F154** then **F155**
(recommendations fitted to the yard, and designs that fill it). Group M says why for each.

The list below is the V2.65-era recommendation, kept as it was written.

The pick is the owner's. Asked for one, in order:

1. **F123 — the presentation still never reaches the PDF.** The last of the
   measured-bug seam: F120 and F129 both shipped in V2.65, so the score now
   tells the truth about hosts, bird food and structure. F123 is a wire that
   was never connected — `still_pixmap` is computed and never passed — which
   makes it the cheapest remaining thing that a user can see.
2. **Group D — F113 (design variants) or F93 (reusable palettes).** Two walls of
   the professional workflow are down; these are the two left, and both are
   bigger than what shipped.
3. **Group F — the sprawl.** Named as a weakness, and the 3D toolbar's size
   ceiling has now shaped three increments running, which is the guard telling
   you something the backlog already says.

*(Group A's confidence block shipped in V2.53, Group B in V2.56, and half of
Group D and Group E besides. The pattern this file was written to expose —
"next" meaning "not this time, again" — is broken.)*
