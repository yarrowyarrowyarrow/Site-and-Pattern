# Site & Pattern — the forward roadmap (V2.32 →)

**This is the live roadmap.** [`PHILOSOPHY_ROADMAP.md`](PHILOSOPHY_ROADMAP.md) remains the
principle-by-principle map and the shipped record of F1–F62 — read it for *why* the app is
shaped the way it is and what has already landed. This file is what comes next, and why.

> **Looking for a list of everything not yet built?** That is
> [`BACKLOG.md`](BACKLOG.md) (V2.52) — one line per unbuilt item, all 41 of them, plus the
> data jobs, in one table you can read in a sitting. **This** file carries the *reasoning*
> for each: what it is, how it would be built, what it leans on. Follow the ID.

Feature IDs continue the same stable-handle sequence (F63, F64, …) so "let's do F70" keeps
working across both documents. **Next free ID: F145.**

### The ID ledger

Added in V2.52, because the "next free ID" has now been a sentence three times and been
wrong twice. **A sentence nobody updates is not a ledger.** This table is; the pointer above
is derived from it.

| ID | Claimant | Status |
|----|----------|--------|
| F63–F69 | Surfaces · species profiles · layer aspect · seed heads · creature variety · real wind · presentation still | ✅ V2.33 |
| F70–F72 | Photo slots · habit-first sourcing + bench · your own photos | ✅ V2.35–V2.36 |
| F73–F77 | In my yard on this date · seedling sheet · cues-to-care · before/after/five years · neighbour's-eye view | **F73–F74 open** · F75–F76 ✅ V2.56 · F77 ✅ V2.33 |
| F78–F82 | Herb aspect · Stylised/Balanced/Lifelike · florets · forked stems · bloom count | ✅ V2.34 |
| F83–F84 | Know the plant (ID lessons) · fauna morphology | **F83 open** · F84 ✅ V2.36 |
| F85–F89 | The companion · notes that add up · game-style saves · curriculum · 3D UX review | **open** except F87 ✅ V2.39. **F85 absorbs F106** |
| F90 | Plant directory | ✅ V2.41 — **and see the collision note below** |
| **F91–F92** | Ecological substitution · the order file a nursery accepts | ✅ V2.57 |
| F93–F94 | Reusable palettes · task-shaped home | **open** |
| F95 | — | **free** (skipped in V2.43) |
| F96–F103 | Two doors · editable references · species ledger · per-plant age · edit animations + net · split view · one 3D toolbar · flight physics | ✅ V2.43–V2.45 |
| **F104** | Sandbox undo + the graduation path into Design | ✅ V2.55 |
| F105–F107 | Challenges · the companion *(merged into F85)* · painted lep wings | **open** |
| F108–F110 | **Double-assigned — see below** | ✅ (both claimants) |
| F111–F112 | Colour in the plant panel · the website searchable and drawn | ✅ V2.48 |
| **F113** | Design variants + side-by-side comparison *(was F90)* | **open** |
| **F114–F119** | Wing-pattern geometry · shrub aspect · fern density · billboard fruit · better creature models · birds/mammals off name tables | **open** — assigned V2.52 |
| **F120** | Correct the use tags the cited edges contradict | ✅ **V2.65** — 117 by the time it was taken, cut to **80 real corrections** by requiring the right animal at the far end: 107 of 346 `larval_host` edges are bees, aphids, horntails and gall midges, and three `seed_food` edges name a deer mouse. `host_plant` 30 → **95** species, `bird_food` 78 → **104**; the worked example gains **+7 points**. Additive only |
| **F121** | Pause and slow the ambient wildlife in the 3D preview | ✅ V2.54 |
| **F122** | The Site Info glossary — every metric explains itself | ✅ V2.55 (was the unnumbered "glossary half" in Group E) |
| **F123** | The presentation still never reaches the PDF — `still_pixmap` is never passed | **open** — found by V2.56 |
| **F124** | `PLANT_TYPE_TO_LAYER` misses 311 of 437 species; a prairie meadow scores 0 of 15 on layer diversity | ✅ V2.60 |
| **F125** | Wildlife records for the 338 species that have none — needs egress | ✅ V2.59 (99 → 271 of 437; the remainder is F127) |
| **F126** | Rethink the "convince someone" artefact; F76's three panels were judged weaker than the idea sounded | **open** — opened by V2.58 |
| **F127** | Curate the held animals — AB/SK nativity, common name, taxon | ✅ **V2.63** (top 200) + ✅ **V2.64** (the 980-species tail, as F130). 998 animals admitted in total; fauna 167 → **1,147**, edges 2,813 → **7,714**, coverage 275 → **302 of 437**. What remains held is 120 species and 42 trinomials, none of it waiting on a decision |
| **F128** | Re-fetch GloBI with `includeObservations=true` for per-study citations | ✅ V2.62 — 2,406 of 2,452 edges now cite a named study, collection or dataset; bibliography 13 → 46 works. Body part came back 0% and is **dead**, so the sapsucker and browse records are not recoverable this way |
| **F131** | Recover the refused `larval_host` edges from F128's observed life stage | ✅ **V2.65** — 44 of 700 have an observed larva on that plant; 26 edges written, all with a named museum-specimen study. A pupa does not count (larvae wander off to pupate) and the adult → nectar reroute is Lepidoptera-only (an adult beetle on a leaf is chewing it). No Monarch reached a non-milkweed. Knock-on: 9 of V2.64's 18 orphan animals gained an edge and were written |
| **F130** | The 1,052-species tail F127 held: the animals below the top 200 | ✅ **V2.64** — 838 include, 103 hold, 39 reject; 820 written (18 admitted animals get no edge and so get no row). **Not the same review shape**: 457 singletons, no shortlist to take, and `larval_host` a quarter of the edges instead of a tenth |
| **F132** | The wildlife index is 1,138 chips in five fixed blocks: a list, not a way to find anything | ✅ **V2.71** — the same filtered search the plant index is, over the same `browse.js`, on five facets (kind · how it uses the plant · plants recorded, in bands · specialist · has a photograph). The last one is why it mattered: **58 credited, openly-licensed animal photographs had been in `fauna` unpublished**, because the wildlife model had no photo field. `photo_credit()` already refused any row without attribution, so the rule came free. Two hardcoded assumptions left `browse.js` (a `plants/<slug>/` card lookup, the word "plants" in the count) and it now drives both pages knowing neither vocabulary. Second thing nobody had seen: the animal page's prose block was keyed on `animal["notes"]` and **`fauna` has no `notes` column**, so it had read `None` on every row since the model was written and had never rendered once — while `description`, populated for all 1,156 rows with tongue length, nesting habit and forage genera, went unpublished |
| **F133** | No way to know whether anyone is reading the published catalogue | ✅ **V2.71** — `--analytics-token`, off by default, built as an explicit exception to the renderer's "no external request of any kind". Cloudflare Web Analytics because it sets no cookie and keeps no per-visitor identifier, so it needs no consent banner; disclosed in the footer of every page it appears on; a malformed token raises rather than landing in 2,000 pages, since the value sits inside a quoted JSON attribute. The build prints which kind of build it just made, either way |
| **F134** | F133 answers "is anybody reading this" and cannot answer "is that growing" — Cloudflare's free tier keeps about a day | ✅ **V2.73** — Umami added on the same three terms F133 set (off by default, no cookie and no per-visitor identifier, disclosed in the footer of every page it appears on), and **both providers can run together**, which is how you check a switchover is recording before dropping the old one. The vocabulary moved to `src/site_analytics.py`: the renderer was at 721 of 800 lines and one provider becoming two would have spent the headroom on a concern that is not rendering. The footer sentence is **generated from what is configured**, because a footer naming Cloudflare on a build carrying Umami is the class of quiet falsehood V2.71 already found on the About page; "sets no cookies" is now pinned present in every combination by a test. `--umami-src` exists because `cloud.umami.is/script.js` is on the common blocklists, so the count is a floor rather than a total and self-hosting is a real later move — a flag now means it costs a word in a build command, not a code change |
| **F142–F144** | The maps draw British Columbia; there is no bloom bar; the field the site is named for has no provenance mark | ✅ **V2.78** — **F142**: the GBIF query is bounded by the polygon *bounding box* plus half a degree and `map_svg` emits `overlay` outside its subject clip, so **175,876 records (31.7%)** were drawn over BC, Montana, Manitoba and the NWT. Kept honest at the edge by testing the coarse province outline **or** any surveyed ecoregion, because 193 vertices cannot adjudicate the continental divide. Also: the radius clamps were absolute units with 360 of 422 dots at the floor, and two versions shipped with no legend over three simultaneous encodings. **F143**: the phenology bar on 424 of 430 species pages, fruit on the same axis, nothing recorded drawing nothing. **F144**: VASCAN still 403s at the proxy, so instead the nativity claim finally carries the mark every other field has — 354 of 430 species publish "AB, SK" from an ecoregion inference and the retired generator's own docstring says the review was reading its output. Derived rather than stored, with a test that fails the day the sourced column lands |
| **F140–F141** | The occurrence records, drawn as the printed floras draw them: herbarium specimens under a licence that permits redrawing them | ✅ **V2.77** — asked for as a look before deciding about the CC-BY-NC observation layer, and preparing it found the fault underneath. **F140**: `MAX_RECORDS_PER_SPECIES = 6000` bounds the harvest per species and GBIF orders newest-first, so the 16 species at the cap hold **89,964 records dated 2021–2026 and thirty-one specimens between them** — *Amelanchier alnifolia* has 6,000 records and two specimens, none before 2024. Raising the cap would multiply the harvest for 434 species to rescue sixteen; `--specimen-pass` asks for `PRESERVED_SPECIMEN` as its own query instead, and `fetch_occurrences(truncated=…)` records the difference between *GBIF ran out* and *we stopped asking*, which nothing had, which is why this survived two increments of work on exactly this data. `--from-cache` finally reads the V2.75 cache for what it was built for: a re-derivation with no network. **F141**: `--specimens` and `--publishable`, composable, reusing the licence fetcher's own `PUBLISHABLE` so the two cannot disagree; a dataset absent from the licence table is dropped rather than defaulted. `species_svg(dots=)` filters the dots and never the shading — the published range is a claim about all the evidence — with a caption on every figure saying which number is which. **52,924 of 555,477 records drawable, 300–700 dots per species.** Nothing is published yet; that is the decision this was built to inform |
| **F135–F139** | The outside review: say what a range claims · containment not proximity · VASCAN nativity + taxonomy · a gate that can fail on it · plot the observations | ✅ **V2.75** — eight criticisms from a botanist with no connection to the project, checked one at a time. **F136** is the one they guessed and understated: `_NEAR_BOUNDARY_M` is a 5 km buffer written for *which ecoregion is this yard in*, inherited silently by `ranges_for_species`, crediting every record to every region within five kilometres — **16.4% of points inside the layer land in two or more**. Fixed with a parameter, not a new default, because site detection is still right to buffer. Plus the structural half: the seeder now caches the raw points, so the next question about the derivation costs nothing instead of 400,000 re-fetched records. **F138** found worse than the review did — `tag_prairie_provenance.py` was keyed off a vocabulary V2.72/73 had replaced, so a re-run would have moved **237 of 431 species**, and 303 of 430 gate warnings were the gate arguing with a migration the same release shipped (warnings → **127**). Two published pages both titled *Stiff Goldenrod* make opposite nativity claims about one taxon, known since V2.69 with nothing able to fail on it. **F135**: every answer the review wanted already existed in the repo and reached no reader — the retrieval date, the floor, that unshaded means uncollected. Now on `/method/`, computed from the modules that own the numbers. **F137** ships the replacement for the nativity claim (VASCAN: per-province establishment means *and* a taxonomic backbone in one request), report-by-default and needing egress. **F139** draws the records for the first time |
| **F129** | The five vegetation layers are the permaculture *forest-garden* stack, so a prairie is structurally capped at 6 of 15 — the component measures how woodland-like a design is and calls it habitat value | ✅ **V2.65** — the denominator is now the reference community's own layers. A prairie planting on prairie goes 6.0 → **10.0 / 15**; the same planting in Aspen Parkland *drops* to 3.8, which is the point. Reuses `reference_fidelity`'s layer judgement rather than copying it. Callers passing no ecoregion are unmoved |

> **Collision fixed in V2.37.** F78–F82 had each been assigned *twice*: the V2.34 3D work
> (herb aspect axis, Stylised/Balanced/Lifelike, florets, forked stems, bloom count) reused
> the IDs Theme D's unbuilt designer-workflow entries already held, and "a task-shaped home"
> was a third claimant on F82. The shipped assignments are kept — they are in the commit
> history — and the five unbuilt entries were renumbered to F90–F94. "Let's do F80" is
> unambiguous again, which is the whole point of a stable handle.

> **And it happened again, twice, and was flagged and skipped.** The V2.37 renumbering sent
> design variants to **F90**, which V2.41 then used for the shipped plant directory — a
> collision `docs/plans/V2.43-learn-and-design-two-doors.md` **explicitly told the next
> session to record**, along with correcting the pointer to F95. Neither edit was made. Three
> increments later V2.46 (life-size creatures, the three verbs and the net, bee mode at
> scale) and V2.47–V2.48 (the colour filter, the public website, colour per species) both
> reached for **F108, F109 and F110**, independently, because the pointer still read F111
> after F111 and F112 had shipped.
>
> Resolved on the same rule V2.37 used — **a shipped assignment is kept, because it is in the
> commit history**, so only an unbuilt claimant may be renumbered:
>
> - **F90 is the plant directory** (V2.41). Design variants becomes **F113**.
> - **F108/F109/F110 each have two shipped claimants** and neither can move. They are
>   disambiguated by release: F108/F109/F110-*V2.46* are the Learn-side 3D work, and
>   F108/F109/F110-*V2.47/48* are the colour and website work. Ugly, and honest.
> - The pointer is now **derived from the ledger above**, not asserted in a sentence.

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

### Scored against that list — V2.52

The five above were written before V2.33. Nineteen releases later, exactly one is paid down:

| | State |
|---|---|
| 1 · looks like a diagram | **Largely fixed** — V2.33/34/36: surfaces, four aspect axes, florets, seed heads, fauna morphology |
| 2 · photographs don't show the plant | **Unmoved.** 111 of 434 plants have none, **0 species have a habit shot**, 62 of 69 bees have none. The structure landed (F70/F71/F72); the content did not |
| 3 · never argues it is beautiful | **Unbuilt** — F75 and F76. P13 was adopted to name the gap and nothing has been built against it except F69/F77 |
| 4 · no professional workflow | **Entirely unbuilt** — F91, F92, F93, F113 |
| 5 · it sprawls | **Unbuilt** — F89, F94. It has grown since: ten buttons on the 3D toolbar now, not nine |

And where the effort went: **V2.43–V2.46 were Learn-side and 3D-creature work; V2.47–V2.51
were website, catalogue and data work.** The design side proper — the thing a person uses to
design a yard — has not had an increment since V2.42. That is not an argument against any of
it, and the website work in particular came straight from the owner. It is the context for
choosing what comes next, and this document has twice accused itself of exactly this drift
without the accusation changing anything.

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

**V2.53 — the confidence block, and the absence the app could not support
(F8, F12, F13, F14, F28).** Group A of the new backlog, on its thirteenth
appearance as "next". Plan:
[`V2.53-the-confidence-block`](plans/V2.53-the-confidence-block.md).

| ID | What landed | Where |
|----|-------------|-------|
| — | **One vocabulary, so five cards could not invent five scales.** Bands (three rungs plus `UNKNOWN`) and marks (one table over the edges layer's `documented/recorded/derived` and the seed data's `measured/flora/photo/checked/name/epithet/estimated`). Two rules are structural: **absent is not estimated** — a blank field is the app knowing it does not know, while `estimated` is a genus default that looks exactly like a measurement — and **a band needs evidence**, so `known=False` gives `UNKNOWN` rather than a middle rung. That second one is the V2.51 map bug, where a fabricated "medium confidence" was printed about regions with no data, turned into a guard. Thresholds are *not* restated here: the establishment floors belong to `ecoregion_ranges` and a test asserts they agree | `src/confidence.py` |
| **F8** | **The audit found something worse than loose wording.** Grepping the ten prose generators for deterministic phrasing found five uses of "will", all harmless — `phenology` already says "we predict", `plant_impact` "no *documented* wildlife". The real failure: `design_critic` asserted **absences** as facts, off a score component fed by use tags — while the app holds a second, cited source that disagrees for **48 species**. 37 carry a documented `larval_host` edge and no `host_plant` tag (Chokecherry, Balsam Poplar); 11 carry a fruit/seed edge and no `bird_food` tag. The contradiction is visible inside one dictionary: `components.host.score` is tag-derived and can read 0 while `food_web.caterpillars`, two keys over and edge-derived, reads True. The critic now reports the stronger source and phrases every remaining absence as an absence of *record* | `src/design_critic.py`, `data_quality.validate_use_tags_against_edges` |
| **F12** | **The citations reach the design side.** `src/citations.py` shipped in V2.42 and reached two screens, neither of them where a design is made. The 3D dossier card now carries a short citation per wildlife row plus a collapsible reference list, and the relationship web's summary names the works the picture rests on — a web resting on one work is a different object from one resting on six. An unattributable edge gets no citation rather than a placeholder dressed as one, and the unattributed count is reported | `src/scene_dossier.py`, `html/scene3d/10-inspect.js`, `src/relationship_graph.py` |
| **F14** | **The card proposed a false readout and it was not built.** Bucketing `score_cell_for_plant` would have printed confidence about nothing: `build_cell_env_map` fills every unread grid with a neutral 0.5, so on a site with no DEM *every* plant bands identically. F14 reads the **georeferenced occurrence records** instead (schema v59/v60, already carrying count, confidence and source per region). Below the three-record floor an absent species and an under-collected one are indistinguishable, so both get `UNKNOWN` — never "unlikely to establish", which would steer a real planting away from a species that belongs there. The design summary takes the **weakest** well-evidenced rung, not an average | `src/establishment.py` |
| **F13** | **Fidelity scores structure, not species.** Matching a hectare of parkland species-for-species on a front lot is neither possible nor desirable; what transfers is the shape. Per-layer presence and proportion, genus overlap as a capped bonus, `PRESENCE_FRACTION = 0.25` because four aspens is a canopy on a suburban lot. **Low is not a failure** and the blurb says so — a rain garden is deliberately unlike its reference. `LAYER_TYPES` is asserted equal to the walkable reference's, so the number and the 3D scene cannot disagree about the same design | `src/reference_fidelity.py` |
| **F28** | **One provenance vocabulary across three surfaces.** The directory printed the raw database token — "Flower detail: estimated" — which is honest and tells a reader nothing. Both it and the bloom-colour note now render through `confidence.mark`, so the desktop directory, the website (same `species_entry`) and the dossier cannot drift the way the four edge tables did before F7 | `src/plant_directory.py` |
| — | **Surfaced** as a "How sure are we?" block on Analysis → Habitat, refreshed from `set_placed_plants` rather than the score button — a read-out that only updates when a button is pressed is the V2.42 stale-list bug. Plus `establishment()` and `reference_fidelity()` on the frozen API contract | `src/analysis_panel.py`, `src/permadesign_api.py` |
| — | **Left alone on purpose:** the 48 tags themselves. Correcting them moves every affected design's Habitat Value Score, which the stability rule makes a deliberate decision rather than a side effect of a wording pass. Now a tracked warning in the data gate and a backlog row (**F120**) instead of an invisible contradiction | `docs/BACKLOG.md` |

### The release ledger

Added in V2.52. Eleven releases — **V2.37 through V2.46, and V2.50** — had shipped without
ever reaching this section: their record lived only in `docs/plans/` and, for the Learn-side
ones, in a prose sentence under Theme H. A "Shipped" section with holes in it is worse than
no section, because the holes are invisible. Detail tables for the releases that already had
one are kept below; everything else is here, one row each, with its plan.

| Release | What it was | Plan |
|---|---|---|
| **V2.76** | **The sliver that was doing the damage.** V2.75 fixed the range derivation and could not fix the data: correcting it needed ~400,000 records re-fetched from GBIF, and `/method/` disclosed the gap rather than hiding it. The author ran the fetch, and what came back reframed the finding. V2.75 had measured the **geometry** — 16.4% of random points inside the layer fall within 5 km of a second region — and led with it. `plot_occurrences.py --buffer-artefacts` measured the **outcome on real records**: 493 of 4,218 region claims (11.7%) had almost no records actually inside them, and **almost all of them were one region**. `western_continental_ranges` is the British Columbia interior ranges, clipped to a hairline inside Alberta — **0.02% of the mapped area**, 36× smaller than Northern Continental Divide — so a five-kilometre apron many times its own size had been sweeping in nearly every montane record near the border. **135 species → 15.** Confirmed real rather than a bug in the fix by testing the region's own computed interior point, which containment returns correctly. Records **489,546 → 361,447**, region rows 4,215 → **3,643**, species with rows 422 → **420**. **The interior regions barely moving is the confirmation**: Cypress Upland 231 → 228, Selwyn Lake Upland 10 → 8, because a boundary fix should bite at edges and leave the middle alone. Two species lost every region (*Panicum virgatum* at 3 records, *Symphyotrichum campestre* at 6) and band **`unknown`, not `unlikely`** — under-collected and absent are indistinguishable below the floor, and the second would steer a planting away from a species that may belong. Neither vanishes; both keep their ecozone tag. The V2.75 nativity gate noticed unprompted (9 rows → 11), which is the first time one of those checks earned its place on data it had never seen. Schema **76 → 77**, without which the correction reaches nobody already installed, and `/method/` now states what changed and names the sliver in the reader's language rather than quietly restating its numbers | [the-sliver-that-was-doing-the-damage](plans/V2.76-the-sliver-that-was-doing-the-damage.md) |
| **V2.75** | **What a shaded region claims.** The first feedback from outside the project: a botanist read grownativeplants.ca in public and sent eight criticisms. Nothing was broken and every page rendered — what they did was read what the pages *assert* and ask what stood behind each one. Six hits, two with a wrong premise and a right point, and **three faults found by checking the list that were worse than anything on it**. **The 5 km buffer**: `ecoregion._NEAR_BOUNDARY_M` was written in V2.67 to answer *which ecoregion is this yard in* — correct, because the outlines are accurate to about a kilometre and a garden near an edge belongs to both lists — and `ranges_for_species` inherited it by defaulting its lookup, crediting every record to every region within five kilometres. Measured over 4,000 random points inside the layer: **16.4% land in two or more**. The review guessed this and named 900 m, the display simplification; their worked example is in our data, *Aster alpinus* carrying 72 Aspen Parkland records. Fixed with `near_m`, default unchanged. **The frozen generator**: `tag_prairie_provenance.py` derives the SK half of every `native_provinces` value from ecoregion tags, and V2.72/73 replaced that vocabulary underneath it — four of six keys stopped existing, and a re-run would have moved **237 of 431 species**. The field the site publishes as "Native to" was the output of a routine that would no longer produce it. Retired, not repaired, with a gate that fails on future drift. **The gate that was noise**: `validate_plant` knew one level of a three-level vocabulary, so **303 of 430 warnings** were the gate disagreeing with a migration the same release shipped — and the volume had buried a real contradiction for six releases, two published pages both titled *Stiff Goldenrod* making opposite nativity claims about one taxon. Warnings → **127**, and three new checks, one of them an error. Everything the review asked for on the site already existed in the repo and reached no reader: the retrieval date (on the row since v59, printed by the desktop), the three-record floor, that unshaded means uncollected rather than absent. All on `/method/` now, with the numbers imported from the modules that own them — a page about honesty is the worst one to hand-type. Every species links out to GBIF and iNaturalist, which is the review's own suggestion and the only honest answer to *where in the region*: those coordinates are not ours to republish and for rare taxa are obscured at source. `scripts/plot_occurrences.py` draws them for us, over a **point cache the seeder now keeps** — before this, every question about the derivation cost 400,000 re-fetched records, which is why the buffer could be diagnosed and not corrected. *Helianthus giganteus* leaves (430 species, 7,580 edges) on a **different evidence shape from V2.74**: no occurrence entry at all, which is weaker than it looks, and the record says so. Plus 81 grass pages that read "not verified" beside a seed head, a photo count contradicting itself on two pages, a Manitoba filter backed by one species, and an em-dash rule CLAUDE.md said was guarded and was not | [what-a-shaded-region-claims](plans/V2.75-what-a-shaded-region-claims.md) |
| **V2.74** | **A plant that was never from here.** *"Remove Rudbeckia hirta from the app but particularly the website as it does not appear to be native to AB."* Correct, and the emphasis is right: inside the app a wrong row is one of 432, while on the public site it is a species page at a stable URL on a reference work called GrowNativePlants.ca, reachable from every hub its facets put it in — `site_facets.index_row` over the shipped record gives `colour: yellow`, `bloom: 7, 8, 9` and `role: bird_food, pollinator, wildlife_habitat`, so at least eight landing pages listed it — and the claim those pages make is not *here is a plant* but **this plant is native here**. VASCAN records it as introduced in AB, SK, MB and BC, native from Ontario eastward; Moss's *Flora of Alberta* agrees. **Nothing in the app could have disagreed**: the seed row asserted `native_to_alberta: 1` with the note *"Classic prairie wildflower"*, `tag_prairie_provenance.py` derived `native_provinces: "AB,SK"` from that flag plus the ecoregion tags, and `is_publishable` accepts either field — one editorial claim wearing three coats. The data that looked like corroboration was the trap: **215 georeferenced GBIF records across eight prairie ecoregions**, 102 in Aspen Parkland at high confidence, which is what a widely-planted self-seeder looks like and is exactly the read `establishment.py` exists to prevent. V2.61 drew this distinction for the fauna gate — *"a starling has tens of thousands of Alberta records"* — and never turned it on the flora, because measuring first had concluded the flora was already clean. Catalogue **432 → 431**, documented edges **7,740 → 7,590**. The 150 edges are all real and all beside the point: an aggregated flower-visitation record says a bee met a plant somewhere, not that the plant belongs where the bee lives, and one source is *Robertson 1929*, an **Illinois** survey — the plant's actual native range. On the site: 432 → **431** species pages, 1,138 → **1,132** wildlife pages, 7,574 → **7,424** published edges. **Six animals held exactly one documented edge and it was to this plant**, and the first answer — they simply stop getting wildlife pages — was wrong: `test_derived_edges` failed at **8 orphans against a ceiling of 5**, animals left in `fauna` connected to nothing at all. Raising the ceiling is the fix V2.64 explicitly refused — its first tail apply *"wrote 20 animals connected to nothing"* and the answer was to stop writing them — so the six came out too: fauna 1,156 → **1,150**, lepidoptera attributes 347 → **345**, orphans back to the pre-existing **2** (a kestrel and a bat, whose trophic level the model genuinely cannot express). `curate_new_fauna.writable()` had reached the same verdict independently, naming all six beside nine others never written for exactly this reason. Four placements got substitutes rather than holes: Prairie Coneflower in the worked example and the Boulevard strip, **Meadow Blazingstar** in the Tall Prairie Meadow, where a 0.5 m coneflower would have contradicted the argument that variation exists to make. Both polyculture descriptions were edited too. New guard: `data/excluded_taxa.json` + `validate_excluded_taxa`, because the way back in is live — `fauna_edges_candidates.json` still holds **389 GloBI records** naming it, and `ingest_fauna_edges`' only defence is *"plant is not in this catalogue"*. It matches on **both** names, since edges key on `common_name` and a binomial-only check would have readmitted all 150 in silence, and an entry with no `authority` is an error, because a bare prohibition sends the next person to re-derive the call that went wrong the first time | [a-plant-that-was-never-from-here](plans/V2.74-a-plant-that-was-never-from-here.md) |
| **V2.73** | **A second week of numbers.** *"Cloudflare only shows past 24 hours."* **F134**: Umami added beside the Cloudflare beacon F133 shipped, on the same three terms — off by default, no cookie and no per-visitor identifier, disclosed in the footer of every page it appears on — and **both can run at once**, because the fortnight you are switching is exactly when you want the old numbers and the new ones side by side to prove the new one is recording. Not a swap: Cloudflare answers *is anybody reading this*, Umami answers *which pages, and is that growing*, and only the second needs history. The analytics vocabulary moved into `src/site_analytics.py` — the renderer sat at 721 of 800 permitted lines and growing one provider into two in place would have spent the headroom on a concern that is not rendering. The footer sentence is now **generated from what is configured** rather than written down, which is the fix for the exact fault V2.71 found on the About page: prose asserting something that stopped being true and that nobody re-reads. `sets no cookies` is pinned present in every combination by a test, since it is the promise the whole exception rests on. `--umami-src` is a flag and not a constant because **`cloud.umami.is/script.js` is on the common blocklists**, so the count is a floor rather than a total and self-hosting under the site's own domain is a real later move — as a flag it costs a word in a build command instead of a code change | [V2.73](plans/V2.73-a-second-week-of-numbers.md) |
| **V2.72** | **The release tags were pointing at the wrong commit.** Chased down from a push that failed with *"src refspec V2.71 matches more than one"*. That ambiguity was local and self-inflicted (a recovery `git fetch origin V2.71` pulled the *tag* down beside the branch); the thing underneath was not. `softprops/action-gh-release` creates its tag when one does not exist, and with **no `target_commitish` GitHub anchors it to the default branch** — `main` has not moved since the V2.20 merge, so **99 of 101 version tags sit on the wrong commit and 51 share one that is fifty releases old**. Invisible for fifty releases because nothing users touch was affected: the `.dmg`/`.exe` are uploaded assets and the updater reads the release's `tag_name`, so only the "Source code" links lied. Cause fixed in **both** workflows (whichever finishes first creates the tag); history left to `scripts/retag_releases.py`, which the session could not run — **this credential cannot write tags at all**, force-move and fresh-create both 403 while branch pushes on the same remote succeed. Also recorded: deleting the tags, the first instinct, would have broken the in-app updater | [V2.72](plans/V2.72-the-tags-were-pointing-at-the-wrong-commit.md) |
| **V2.71** | **Fewer words, and a way into the animals.** Eight copy edits from reading the published site, plus the wildlife index becoming a filtered search over `browse.js` — kind of animal, how it uses the plant, plants recorded, specialist, has a photograph. That last facet is why the ask mattered: **58 credited, openly-licensed animal photographs had been in `fauna` unpublished** because the wildlife model had no photo field, and `photo_credit()` already refused any row without attribution, so the no-credit-no-photo rule came free. Removing the About page's "What it does not contain" section deleted a **claim that had been false since V2.50** — it said the `medicinal` tag was not published or searchable, while `WITHHELD_ROLES` has been `()` and the landing page carries a "Medicinal 108" chip; P12 is unaffected, because the one-line statement is in the footer of all 2,064 pages with a test behind it and the `notes` withholding is in code, not prose. Analytics added as an explicit **exception** to "no external request of any kind": opt-in, Cloudflare (no cookie, no per-visitor id), disclosed in the footer, malformed token refused rather than pasted into 2,000 pages | [V2.71](plans/V2.71-fewer-words-and-a-way-into-the-animals.md) |
| **V2.70** | **The website gets its own name.** `grownativeplants.ca` registered, and **two names rather than a rename**: `SITE_NAME` for the catalogue, `APP_NAME` untouched for the tool, one constant in the shell every page already passes through. The silent-breakage fix: **GitHub Pages keeps the custom domain in a `CNAME` at the root of the published branch, and publishing replaces that branch wholesale** — so a domain typed into the settings survives exactly one rebuild and then 404s with no error. Now derived from `--base-url`, because two settings that must agree and are set separately do not stay in agreement. `.nojekyll` likewise stopped depending on somebody remembering | [V2.70](plans/V2.70-the-website-gets-its-own-name.md) |
| **V2.69** | **Three levels you can click, and URLs that stop moving.** Page slugs broke a name collision with the row **id**, and the docstring claimed that kept URLs stable across rebuilds — while a reseed is exactly what does not preserve ids. Four live addresses changed silently between two publishes; collisions now break on the scientific name and no slug ends in a number. The website map became a **drill-down** rather than three maps side by side: 6 ecozones → the ecoregions in one → the Alberta subregions overlapping one → a page per subregion. All the geometry was already in the polygon file and nothing had ever grouped by anything but the ecoregion. **The measurement then killed the tidy version**: Alberta's subregions are a parallel classification, not a third tier — 12 of 21 sit ≥90% inside one ecoregion, Montane is 42% of Northern Continental Divide across six, Central Mixedwood 31% across nine. `sorted(parents)[0]` had filed Montane under Aspen Parkland on 6% of it, and **the same shortcut turned up in three modules independently**. Shares measured in the pipeline, shipped as `sub_share`, and a subregion page borrows a species list only when one ecoregion accounts for two thirds of it | [V2.69](plans/V2.69-three-levels-you-can-click.md) |
| **V2.68** | **The filter learns the hierarchy, and the tags learn the truth.** The two decisions V2.67 left open, and they are one decision: moving a heuristic tag onto a vocabulary that has split offers only fan-out (nine assertions from one record) or drop — until three levels exist, and then it can rest at the level its evidence supported. `src/ecoregion_tree.py` reads ecozone → ecoregion → subregion straight out of the polygon file; the dropdown opens with **8 rows instead of 26**, and Alberta's 21 natural subregions become selectable for the first time. The mapping is **measured against the old polygons, not read off the names** — the V2.67 plan wrote the name-based version down a day earlier and got **one of its four "clean renames" right**. Three of six old regions were *misplaced*, not coarse: `subalpine_montane` was drawn east of its own mountains (19% best overlap) and `aspen_parkland` matches the real parkland only 40%, so those tags are cleared rather than promoted to an ecozone that would disguise the error. 431 → **384 species tagged**. Also caught: the shipped `CAVEAT` had been telling 432 public pages the surveyed layer was "hand-traced ... not digitised from a survey" ever since V2.67 made that false | [V2.68](plans/V2.68-twenty-four-is-too-many-for-one-list.md) |
| **V2.67** | **The app adopts the surveyed layer.** 6 hand-traced regions → **24 ecoregions in 6 ecozones**, from the National Ecological Framework v2.2. Cheap, because V2.38 had made the polygon file *the vocabulary* — *"adding a region means adding a polygon and nothing else"* — so the filter, site detection, the validator and the range tags all followed from replacing one file. A principle adopted for an unrelated reason paying off years later. Found by reading the consumer before replacing its input: **`lookup_ecoregions` skipped MultiPolygon entirely**, which does not raise — it answers *you are in no ecoregion*, and every published ecoregion layer is full of MultiPolygons | [V2.67](plans/V2.67-the-app-learns-the-real-regions.md) |
| **V2.66** | **The map under the map.** *"The ecoregions, specifically the map — currently it looks a bit sloppy."* Shipped in two halves because only one was blocked. The **basemap** was worse than the polygons and nobody had looked: Saskatchewan and Manitoba were five-vertex rectangles, the AB/BC border was a straight line, and there was **no water layer at all**. Natural Earth 1:10m; Alberta 15 vertices → **187**. Projection became a re-centred **Albers equal-area conic** — the brief's `ESRI:102001` used verbatim came out tilted 12°. The **palette failed every colour-vision check**, with the boreal teal and foothills olive ΔE 7.7 apart *with full colour vision*; lightness now carries woody cover, and the one-off Cypress hatch became a rule enforced against whatever polygons ship. The new tests immediately caught the pale gold sitting ΔE 7.4 from the not-recorded grey, so three occurrence records looked like none | [V2.66](plans/V2.66-the-map-under-the-map.md) |
| **V2.65** | **F131 + F120 + F129 + the website's citations.** Three places the app already held the information and reported something else. **F131**: the gate refused 700 `larval_host` candidates for lacking GloBI's explicit `hostOf` verb, a rule that earned its place by stopping 23 false Monarch hosts — but unspecific is not false, and F128's observations file carries the life stage. **44 have an observed larva on that exact plant**, and the specialists prove the method: *Schinia florida* on Evening Primrose, *Cycnia tenera* on Spreading Dogbane, *Chlosyne harrisii* on Flat-topped White Aster. 26 edges, `larval_host` 320 → **346**, each with a named museum-specimen study. A **pupa does not count** (larvae wander off the host to pupate) and the adult → nectar reroute is **Lepidoptera-only**, because an adult beetle on a leaf is chewing it. Nine of V2.64's 18 orphan animals gained an edge and were finally written. **F120**: the score reads use tags, the citations live in edges, nothing kept them in agreement — a sourced host record for Chokecherry beside the sentence *"no butterfly/moth host plants"*. The first pass proposed 101 species and was wrong: a bumblebee, a grasshopper, a gall midge, a horntail and a **deer mouse** were voting, because **107 of 346 `larval_host` edges are not lepidoptera**. The tag table now names the taxon required at the far end, gate and fixer share it, and 117 became **80 real corrections** — `host_plant` 30 → 95, `bird_food` 78 → 104, worked example **+7 points**, additive only. **F129**: the five layers are the *forest-garden* stack, so a prairie was capped at 6 of 15 by a component measuring how woodland-like a design is. The denominator is now the reference community's own layers: prairie-on-prairie 6.0 → **10.0 / 15**, and the same planting in Aspen Parkland **drops to 3.8**, which is the point | [three-numbers-that-were-lying](plans/V2.65-three-numbers-that-were-lying.md) |
| **V2.64** | **F130** — the 980 animals V2.63 held, and a different problem from the 200 it read. Fauna 327 → **1,147**, edges 5,487 → **7,714**, coverage 293 → **302 of 437**, bibliography 46 → **114** works. The tail's median species carries two edges and 457 carry exactly one, so the concentration argument that bounded V2.63 has nothing left to bound — and 572 of its 609 genera had no rule. The relationships change kind too: `larval_host` goes from a tenth of the edges to nearly a quarter, and the animals behind them are leaf miners, gall formers, seedhead flies and aphids. That is the food web under the flowers, and it is *better* evidenced than a flower visit — a mine or a gall is recorded by finding it on the plant — but it makes the question per animal a second one: not only is it native, but **is this a relationship where the plant gives something**. Ambush bugs, crab spiders, robber flies, six genera of odonates and every arachnid are held on that ground (the arachnids twice over: `other_insect` is a false statement about a spider in a field the app prints); green lacewings are admitted on it. **Where the introduced species turned out to be**: not exotic bumblebees but the ordinary European insects of a settled landscape — carpet beetles, cluster flies, the Meadow Spittlebug, five weevil genera, a Chinese Mantis sold as a garden beneficial, and two deliberate biocontrol releases. **39 reject, 103 hold, 838 include.** Four superseded names would each have become a second row for an animal already admitted; 42 trinomials turned V2.63's seven hand-written rejects into a rule, placed above the genus lookup because most belong to admitted genera. Birds are excluded outright — all 30 were already decided in `curate_birds.py`. The guards caught the real bug at once: the first apply wrote **20 animals connected to nothing**, admitted honestly then stripped of every edge by the larval-host gate downstream. `writable()` asks the real ingest gates now; orphans 20 → 2 | [the-long-thin-end-of-the-list](plans/V2.64-the-long-thin-end-of-the-list.md) |
| **V2.63** | **F127** — the 200 animals carrying most of the held edges, read one at a time. Fauna 167 → **327**, edges 2,813 → **5,487**, coverage 275 → **293 of 437**. A fifth hand review rather than a fifth filter because the top of the gate-cleared list was *Apis mellifera* with 133 edges: V2.62 had only reviewed species GBIF *flagged*, and the strict Canada filter left the honeybee `unstated`, so nobody ever looked at it. Beside it a Central Asian bumblebee with 1,125 Saskatchewan records — a data error no threshold tells apart from a range. **159 include, 17 hold, 24 reject**, structured as genus defaults plus species overrides because that is how the knowledge is actually shaped. The guards caught two bugs immediately: the shortlist recomputed itself and slid 42 unread species in the moment rows were written, and pinning it then exposed *Polistes fuscatus* falling silently to "not reviewed". 103 of the 159 keep their binomial as their common name, which for a solitary bee is the name | [the-honeybee-at-the-top-of-the-list](plans/V2.63-the-honeybee-at-the-top-of-the-list.md) |
| **V2.62** | **F128 applied + the introduced review + schema v68.** The observation fetch returned a citation on all 13,665 edges, and **2,406 of 2,452** GloBI edges now name a study, a specimen collection or a dataset — 46 still cite only the aggregator, and the bibliography went 13 → 46 works. Life stage came back at **41%**, not the 6% a single-plant probe had suggested. GloBI calls four different things a "study" and collapsing them is the whole trick: 1,357 distinct specimen URLs are 8 institutions, 9 `urn:catalog:` numbers are one bee collection, and keyed per record the bibliography would have grown an entry per pinned beetle. `data_quality`'s existing `NOT_A_WORK` exemption — written because requiring an author "would force somebody to invent one" — now covers `specimen_record` and `dataset` for the same reason from the other side. **The introduced review** followed two failed attempts to automate the nativity question: the occurrence facet returns nothing on any species, and the checklist distributions contradict themselves, with strict filtering fixing the Summer Tanager, making the Red-eyed Vireo worse, and losing *Apis mellifera*. 24 candidates out of 3,064 is readable, so they were read — 19 introduced, 5 native, 1 `unsure` that fails closed — and **every clear false positive was a bird**, which the V2.60 curation had already protected. Also the catalogue's first two photographs, one of them the habit shot the backlog said no species had | [twenty-four-species-read-by-hand](plans/V2.62-twenty-four-species-read-by-hand.md) |
| **V2.61** | **F128 + the AB/SK nativity gate** — *"proper citations for each relationship, and only flora and fauna native to AB and SK"*. Both need egress, so this is the machinery and the gates with the fetches handed over in a runbook. Measuring first reshaped both halves: **the flora was already AB/SK**, all 432 rows carrying `native_provinces`, and the fauna turned out clean of the obvious introduced species but **unsourced** — 142 of 167 rows assert nativity as a boolean with no province data, and 2,898 held animals need the same call 2,898 times. GBIF answers that at one request per species per province, reusing the ecoregion seeder's throttle and its *a failure is not an absence* rule. The distinction the whole gate rests on is that **occurrence is not nativity** — a starling has tens of thousands of Alberta records — so presence, origin and verdict stay separate, `unstated` is the common and honest answer, and `introduced` is refused however many records back it. The gate does not re-litigate animals a person already decided about. Two self-corrections: the occurrence floor was invented as 5 and claimed to match `ecoregion_ranges` when `MIN_RECORDS` is 3, so it is imported now; and citation columns are read through an alias list, because V2.59 hard-coded a column that does not exist and its fixture repeated the guess | [a-count-instead-of-a-claim](plans/V2.61-a-count-instead-of-a-claim.md) |
| **V2.60** | **F124 + F127a** — two cases of the app claiming what its data does not support. **F124**: the layer map knew six of the catalogue's eleven plant types, so `wildflower` (210 species — the largest group by a factor of four), grass, sedge, rush, aquatic and fern counted as no vegetation layer at all, and a prairie meadow scored **0 of 15** on a component it plainly satisfies. The figure quoted when asking for the go-ahead was wrong: mapping all five to `herbaceous` gains *one* layer. Reading `mature_height_meters` — with the 0.30 m boundary taken off the catalogue's own `groundcover` type rather than invented — gets short forbs into groundcover, and the meadow reaches 6 of 15. The residual is larger than the fix and is raised, not taken (**F129**): those five layers are the *forest-garden* stack, so a grassland is capped at 6 by a component measuring how woodland-like it is. **F127a**: the 67 birds F125 held, decided one at a time — 37 include, 5 hold, 24 reject, the European Starling rejected *because* its chokecherry record is true and this app recommends plants FOR the animals it names. Behind them, V2.59's Monarch bug in new clothes: `eatenBy` had been read as `fruit_food` for any bird, and 10 of the 33 target plants bear no fruit — a crossbill on a tamarack eats seeds, a sapsucker on a birch drinks sap the schema cannot express, and GloBI filed three flower *visits* for a White-crowned Sparrow, which does not nectar. The first fix then binned 62 good edges belonging to the 24 birds already in the catalogue, and `Picoides pubescens` nearly became a second Downy Woodpecker. `--refit` re-derives already-written rows so a late gate leaves no sediment. 12 included birds are deliberately unwritten — every record drops, and the orphan-fauna guard caught it at 14. 115 candidate bird edges became 34 real ones | [a-nectaring-sparrow](plans/V2.60-a-nectaring-sparrow.md) |
| **V2.59** | **F125** — actually source the plant↔animal edges, after V2.58 had only made their absence visible. 361 edges → **2,800**; species with any documented record 99 of 437 → **271**; the author's own 16-plant design goes from 1 species with records to 12. Split into a fetcher that runs where there is internet and a **report-by-default** gated ingester that runs here — forced by the egress policy, and the right shape regardless. Three faults, none found by reasoning. The fetch 500'd on all 55 plants because the query was malformed *and* the handler swallowed the response body, so it said "failed" 55 times and never why; a `--probe` mode that reports the working query form and **what percentage of rows populate each column** settled it in one live run. Then all 14,111 candidates were binned for "no reporting study" — GloBI returns `study_title`, not `study_citation`, and **the fixture encoded the same wrong guess as the code**, so the test passed while both were wrong. Worst: the first apply put 23 Monarch caterpillars on goldenrod, aster and sunflower, because "life stage unrecorded → larval host" inverts for butterflies where adult nectaring is most of what GloBI holds; a years-old `test_monarch_only_hosts_on_milkweed` caught it, and `larval_host` now requires the explicit `hostOf` verb (drops 107 of 120). Applying the data broke a food-web test that was **right**: a real hummingbird nectar record on milkweed made a milkweed-only design claim a complete Tallamy chain, on the one caterpillar birds refuse to eat — the chain's bird count now excludes flower visits. 10,937 edges held on 2,872 uncurated animals (**F127**); per-study citations wait on an observations-mode re-fetch (**F128**) | [the-edges-were-real-all-along](plans/V2.59-the-edges-were-real-all-along.md) |
| **V2.57** | **F92 + F91** — Group D, the professional workflow, which was the largest wholly untouched category. **F92**: the buy list as a CSV you attach to an email, numbered to match the planting drawing so line 7 on the order is plant 7 on the map. Grouped by **availability class**, not by supplier — there is no plant-to-nursery stock data anywhere in the app, so "Supplier: Bow Point Nursery" would have been a guess printed as a fact; the class enum exists for exactly this and the real nurseries near the pin are named per group. XLSX deliberately skipped rather than adding `openpyxl` to a frozen build. **F91**: "similar plants" that means *ecologically equivalent* rather than similar height and colour — same group, overlapping envelope, overlapping supported fauna, and the trade reported in full because a list that only sells the alternative asks to be trusted on a judgement it has not shown. Three bugs found: `sun_requirement` is comma-separated and was being compared as a scalar (76 of 80 candidate grasses wrongly rejected), `hardiness_zone_min` can be `'4?'` and crashed `int()`, and **F124** — the layer map misses 311 of 437 species so a prairie meadow scores 0 of 15 on layer diversity | [the-last-centimetre](plans/V2.57-the-last-centimetre.md) |
| **V2.56** | **F76 + F75** — Group B, the argument the app had never made. It argues ecological value superbly, and nobody converts a lawn on those grounds alone. **F76**: your yard now, year 1 and year 5 on one page, in the PDF. Every ingredient had existed for three releases unassembled. Years come from `snapshot_timeline`'s own vocabulary, one camera across all panels (change the viewpoint and the panels stop comparing), and the two "before" cases are captioned differently on purpose — *your lawn as it is now* converts a spouse, *the design on install day* is a weaker but honest claim, and letting one stand in silently for the other is the small dishonesty this codebase keeps catching. **F75**: six Nassauer cues to care — mown strip, crisp edge, height graded, a path, a showy repeat, a sign — because a native planting is rarely removed for failing ecologically, it is removed because it read as neglect. No road data exists anywhere in the app, so the frontage reuses the `sidewalk` camera's documented south-edge assumption and **names it in the one line that depends on it**. Two findings: a corrupt site photo used to drop the before-panel silently, and **F123** — `still_pixmap` is never passed by `_on_export_pdf`, so F69's page has been unreachable since it shipped | [the-argument-never-made](plans/V2.56-the-argument-never-made.md) |
| **V2.55** | **F122 + F104** — Group E's two buildable rows, sharing a theme: the side of the app built for people who do not know what they are doing yet explained nothing and forgave nothing. **F122**: twenty Site Info metrics, **fifteen** of which explained themselves nowhere — worse than the backlog's "~12" — while `climate.zone_description()` had returned exactly the right sentence for years with no caller and the best account of GDD₅ in the repo was a developer comment. Now one Qt-free `glossary.py`, wired onto **both** the value and the **caption**, which is the half that was always missing: every tooltip the panel already had sat on the value, so hovering the word you are actually stuck on showed nothing. The zone's is refreshed where the value is measured, because set once at build time it would name the wrong winter. **F104**: the sandbox had no undo while Design had a full stack — `scene3d_edit_flow`'s own comparison table said `undo: none` — and **Reset is undoable too**, which is the point rather than a nicety. Plus the graduation path, which turned out to be nearly free: `main.py` already builds MainWindow in Learn mode and never shows it, *"so that stepping into Design later is instant"*. The window was at 450 of 450 lines, so the edit bar moved into `reference_edit_flow` — the module that owns what the buttons do now owns what they look like | [say-what-the-number-means](plans/V2.55-say-what-the-number-means.md) |
| **V2.54** | **F121** — pause and slow the ambient wildlife (Paused · ¼× · ½× · 1×), so a creature can be held still and looked at. V2.45b had answered *"the birds move too fast for me to see what they are doing"* by halving every bird's speed permanently, a compromise the source itself flags as "not a claim about airspeed"; this is the instrument that was missing. The trap: `animateWildlife` runs on **two** clocks — `dt` for travel, **absolute `t` for the wingbeat** (plus bob, wobble, hop, `beatGain`) — so scaling `dt` alone gives a bird hovering motionless with its wings at full speed. One wildlife-local clock now feeds both. Space was already "ascend" in bee mode, so the shortcut stands down in first-person; and the control is a HUD chip, not an eleventh button on the toolbar that *is* F89 | [hold-still](plans/V2.54-hold-still.md) |
| **V2.37** | The first outside tester's sixteen items; the ten cheap ones fixed. Three turned out to be features that already existed and could not be found — including **PDF export, raising `NameError` on every call for four minor versions** behind a test that skipped | [user-feedback-easy-wins](plans/V2.37-user-feedback-easy-wins.md) |
| **V2.38** | The ecoregion rebuild: heuristic tags replaced by ranges **derived from georeferenced occurrence records**, each row carrying its count and a confidence band (schema v59/v60). Plus the plants that were flying in the air, and the sun/shade merge | [ecoregion-rebuild](plans/V2.38-ecoregion-rebuild.md) · [runbook](plans/V2.38-ecoregion-runbook.md) |
| **V2.39** | **F87** — game-style saves: a `saves/` folder, Save that stops asking where, File → Open listing your designs. The crash-recovery autosave moved out of its `$HOME` dotfile | [game-style-saves](plans/V2.39-game-style-saves.md) |
| **V2.40** | The start menu, in two cuts — the second moved the whole menu *ahead of* `MainWindow`, which is what the ask meant. Verifying it turned up three stacked process aborts that had been stopping the test suite from printing a summary at all | [start-menu](plans/V2.40-start-menu.md) |
| **V2.41** | **F90** — the plant directory: the catalogue as a browsable reference work, opened from the landing page with no design in existence. Surfaced sixteen `search_plants` filters that had worked the whole time with nothing attached to them | [start-screen-and-directory](plans/V2.41-start-screen-and-directory.md) |
| **V2.42** | The biological-data audit, and `src/citations.py`. All 361 edges were properly cited and **not one citation was visible anywhere**; coverage doubled (22.6% → 51.3%) from host records already sitting unread in the shipped attribute files; `evidence` gained its honest third state | [biological-data-review](plans/V2.42-biological-data-review.md) · [first-user-on-the-relationship-web](plans/V2.42-first-user-on-the-relationship-web.md) |
| **V2.43** | **F96–F98** — Learn and Design as two doors, editable reference landscapes, the species-discovery ledger (schema v62) | [learn-and-design-two-doors](plans/V2.43-learn-and-design-two-doors.md) |
| **V2.44** | **F99–F102** — per-plant age and nursery stock, the edit animations and the net, split view, one 3D toolbar | [the-sandbox-becomes-a-place-you-can-work](plans/V2.44-the-sandbox-becomes-a-place-you-can-work.md) |
| **V2.45** | **F103** — real flight physics for birds, butterflies and bees. The wingbeat constants were not hertz *and* the body path was decoupled from the wings; birds were the only flying taxon with no morphology table at all | [wingbeats-that-come-from-the-animal](plans/V2.45-wingbeats-that-come-from-the-animal.md) |
| **V2.46** | **F108–F110 (Learn side)** — life-size creatures, flap-flap-glide, creature collision; the same three verbs in the 3D preview and a net that is held and has a reach; bee mode at the right scale. The scale error was 6–39× | [life-size-and-a-net-in-his-hand](plans/V2.46-life-size-and-a-net-in-his-hand.md) |
| **V2.50** | The duplicate species rows merged field by field under the author's chosen names, and the `medicinal` tag published on the author's call. **Also the branch correction** — V2.48, V2.49 and V2.50 had all been committed onto the V2.47 branch, so the release branches the in-app updater looks for did not exist | [merge-and-medicinal](plans/V2.50-merge-and-medicinal.md) |

### The releases with a detail table

**V2.51 — a colour per ecoregion, and a backlog you can start.** The last four
of the author's five follow-up items. Plan:
[`V2.51-colour-per-region`](plans/V2.51-colour-per-region.md).

| What landed | Where |
|-------------|-------|
| **Every ecoregion in its own colour**, after the convention the published natural-regions maps use. The constraint that made it more than a palette swap: the fill was already carrying GBIF confidence. Hue took identity, lightness took confidence, and neither claim lost its channel (P9). Plus a legend, and a `reference=True` mode so a navigation map stops claiming a fabricated "medium confidence" about nothing | `src/ecoregion_palette.py`, `src/ecoregion_map.py` |
| **Three bugs a flat green had hidden.** The map was letterboxed into a landscape frame at half size (AB+SK are nearly square; `frame_height` fixes it). "Montane" was printed in British Columbia, and the two western strips are 25px wide against a 50px word, so they are now set along the strip. British Columbia was drawn as a hole: Alberta's border leaves the divide at 54N and the ring was missing that corner | `frame_height`, `_LABEL_POINT`, `draw_ecoregions._british_columbia` |
| **A real coverage hole near Rocky Mountain House.** 0.1 degrees wide, so V2.49's 0.2-degree sweep passed straight over it: a gap narrower than the sample step is invisible to the sample. The parkland closed on a meridian while the foothills' edge runs diagonally. Sweep now at 0.05; verified independently at 0.03 over 227,540 points, zero uncovered | `draw_ecoregions._park_west`, `_coverage_gaps` |
| **The flower-colour backlog became work you can start.** 357 guessed colours was a number, not a next step. 81 are grasses with no bloom colour and are excluded; of the 276 left, 110 sit in 25 genus groups sharing one hex, which is exactly the columbine bug's shape. `--sheet` writes a contact sheet of the 199 that already have a photograph, so checking is a glance rather than a flora | `scripts/colour_worklist.py`, `docs/DATA_GAPS.md` |
| **The native nursery stopped matching everything.** V2.49 read half the report and added `native_specialist` to all 432 natives. The narrowing half: big-box and greenhouse plants also sit on the nursery shelf, seed-or-plug-only and rare ones do not. 343 now, not 432 | `site_facets._ALSO_SOLD_BY` |
| **How to publish it, in plain steps.** Free on GitHub Pages, Netlify or Cloudflare Pages, plus the two decisions worth making before going live rather than after | `docs/PUBLISHING_THE_SITE.md` |

**V2.49 — a map of somewhere, and nine filter corrections.** Feedback on the
V2.48 site. Plan: [`V2.49-a-map-of-somewhere`](plans/V2.49-a-map-of-somewhere.md).

| What landed | Where |
|-------------|-------|
| **The ecoregions redrawn.** *"The map is atrocious."* Ten five-vertex placeholder rectangles became six shapes that follow real geography: the continental divide up the AB/BC border, the parkland as a crescent through Calgary, Edmonton and North Battleford, the grassland triangle split dry from moist, the boreal filling the north. Plus **provincial borders**, province codes and city dots, which is most of what makes a small map legible. Still hand-authored, still captioned as such | `scripts/draw_ecoregions.py`, `data/provinces_prairie.geojson`, `src/ecoregion_map.py` |
| **The authoring script self-checks before it writes.** These polygons are not decoration: `lookup_ecoregions` reads them to decide what a real property gets recommended. 15 pinned city lookups, 3 outside-everything points, 2 exactly-one points, and a coverage sweep over Alberta and Saskatchewan. The sweep earned its keep on the first run by finding **a band east of Calgary belonging to no region at all**, which is what tracing adjacent regions separately does. Regions are now cut from shared boundary lines | `scripts/draw_ecoregions.py:check` |
| **Ticking a second safety box no longer widens the result.** Reported: pet-safe 388, adding human-safe **404**. Values within a facet were ORed, which is right for colour and wrong for safety. A facet now declares `combine`; safety and role are `all`. Roles were quietly wrong the same way and had been disagreeing with `search_plants`, which has ANDed use tags since V1.85 | `Facet.combine`, `html/site/browse.js` |
| **81 grasses stopped having showy flowers.** Same root as the colour bug: a plume is a seed head, and a wind-pollinated plant does not advertise | `site_facets._flowers` |
| **Photograph is the first facet and has a "no photograph yet" value**, so the 111 species still missing one are a searchable worklist rather than an invisible gap | `site_facets._photo` |
| **A native is listed under a native nursery** whatever other tier it carries: `availability_class` names the *easiest* place to find a species, and reading that as "not at the specialist grower" was false | `site_facets._availability` |
| **Non-natives dropped, 439 to 434.** Matched against the garden file rather than the `native_to_alberta` flag, because the flag gets Stiff Goldenrod (a real SK/MB native) and the duplicate Bee Balm row backwards | `static_site.is_publishable` |
| **Less scrolling, and the count stays put.** Facets tile two-up; the search box, the live count and the active-filter chips are a sticky head that the facet list scrolls under. Leaf shape and flower shape removed | `html/site/site.css` |

**V2.48 — the colour was a guess, and the site only asked four questions
(F110–F112).** Four reports on V2.47. Plan:
[`V2.48-the-colour-was-a-guess`](plans/V2.48-the-colour-was-a-guess.md).

| ID | What landed | Where |
|----|-------------|-------|
| **F110** | **Flower colour, per species and provenanced** (schema v64). *"You have blue and yellow columbine as red."* All four *Aquilegia* carried one hex, and so did 32 other genera with three or more species: the column had always been a genus-level guess, correctly labelled `estimated` in a field nothing displayed. V2.47 did not create the error, it promoted it from a decorative tint to an answer. With no flora reachable, 36 species are corrected against evidence that travels with them (Latin epithet, accepted common name) and marked *checked*; the other 359 keep `estimated` and are now visibly *not verified*. Five audit trips are left alone **with their reasons** (red baneberry's `rubra` is the berry), because a colour word in a name usually is not about the flower. Guarded by `validate_flower_colour`: 0 errors, 21 warnings naming the remaining debt | `scripts/seed_flower_colour.py`, `flower_colour_source` at schema v64, `src/data_quality.py:validate_flower_colour` |
| **F111** | **Colour in the plant panel.** The directory got the filter and the picker beside the map did not, which is backwards: choosing a plant because of how it will look is a placement decision. Vocabulary imported, never restated. The test drives the real widget, because a facet wired to a parameter nobody reads is the V2.37 dead-control bug | `src/plant_panel.py` row 5, `_colour_icon` in `src/plant_list_view.py` |
| **F112** | **The website becomes searchable, and drawn.** 68 columns per species, four of them filterable. Now **23 facets** in six groups as one table driving the sidebar, the index rows and the landing pages together. Plus the ecoregion maps the author asked for: a site-wide clickable map and a per-species range map shaded by GBIF confidence band. The shipped outlines are hand-traced and every drawing says so (P9). Redesigned with real tokens and a dark theme, and **no em dashes reach a page**: normalised in `_esc`, which every string already passes through, and guarded | `src/site_facets.py`, `src/ecoregion_map.py`, `src/static_site_species.py`, `html/site/` |
| — | **A bug the maps exposed.** `_seed_plant_ecoregions` mapped scientific name to id with a dict comprehension, and three names appear twice in the catalogue (*Monarda fistulosa*, *Geum triflorum*, *Valeriana sitchensis*). The later row won; the earlier silently lost its GBIF ranges and fell back to the unsourced column, so Wild Bergamot's page said "not from occurrence records" while its twin had six of them. 427 species with ranges becomes 430 | `src/db/plants.py:_seed_plant_ecoregions` |
| — | **P12 again.** `medicinal` is a generic permaculture tag rather than sourced traditional knowledge, but a public indexed *medicinal native plants* landing page is the same act as publishing the traditional-use notes V2.47 withheld. Excluded from the website's role vocabulary, declared in `WITHHELD_ROLES`, tested, and stated on the About page | `src/site_facets.py` |

**V2.47 — the colour axis, and the catalogue leaves the installer (F108–F109).**
Prompted by a competitor read of [BloomsEye Studio](https://studio.bloomseye.com/)
— a browser-based ornamental designer with a content site attached. Two of its
advantages were real, and both were things we already had the material for.
Plan: [`V2.47-colour-and-a-public-catalogue`](plans/V2.47-colour-and-a-public-catalogue.md).

| ID | What landed | Where |
|----|-------------|-------|
| **F108** | **Flower colour as a filter.** `flower_color` has held a hex since schema v31 (V1.90) and `search_plants`' thirty parameters included no way to ask about it — the one axis a person uses when they are choosing a plant because they want to *look* at it (P13). Eleven buckets classified from HSV, thresholds set at the gaps between the 23 hexes actually in use. **The largest bucket is not a bloom colour and says so:** all 79 `#cbbd80` rows are grasses, sedges and rushes, every one with `flower_form='plume'`, and filing wind-pollinated seed heads under "yellow" beside a black-eyed susan would be a claim the data does not make. They get a bucket named for what they are, and it stays selectable because designing for winter texture means wanting exactly that set | `src/flower_colour.py`, `_colour_filter` in `src/db/plants.py`, a `FACETS` row in `src/plant_directory.py` |
| **F109** | **The plant directory as a public website.** F90 built the catalogue as a reference work and shipped it inside a 200 MB desktop installer. `build-site` renders the same pages as plain files: 439 species pages, 86 wildlife pages, hubs for colour / month / role, a client-side filter over an embedded JSON index, sitemap and robots. No framework, no CDN, no external request. Every species page is the *same* `species_entry` call the desktop window makes, so the two cannot drift. The two axes nobody else can publish: `/plants/colour/` (F108) and **`/wildlife/<slug>/` — which plants feed this animal**, over the 361 documented edges. **V2.65: 432 species / 1,138 wildlife pages over 7,574 edges** — every figure computed at build time, so five increments of fauna work reached the site with no change to it | `src/static_site.py` + `src/static_site_render.py` + `html/site/`, `python -m src.cli build-site` |
| — | **P12 gate on publication.** ~43 seeded `notes` rows describe traditional medicinal and plant-use practice. Publishing that to the open web is a different act from showing it in a desktop panel — indexed, scraped, archived, effectively irrevocable — so the notes field is **withheld by default** and the About page says why. `--include-notes` exists and is the author's call, not the generator's | `_extras_section`, `--include-notes` |
| — | **A crash the static build found.** `plant_directory._zone_range` did `int(hardiness_zone_min)`, one row ships `'4?'`, and `ValueError` took the whole species page down — False Box could not be opened in the directory *at all*, and had not been openable since F90 shipped. The `?` is a botanist's hedge and P9 says render it, so the page now reads `zone 4?–8`. Guarded by a sweep over every species rather than a case for that row | `src/plant_directory.py:_number` |

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

| ID | Feature | Impact | Effort | Risk | Principle | Status |
|----|---------|--------|--------|------|-----------|--------|
| F76 | Before / after / in five years | **High** | M | Med | P4, P5, P8 | open |
| F75 | Cues-to-care checker | Med | S–M | Low | P2, **P13** | open |
| F77 | The neighbour's-eye view | Med | S | Low | P5, **P13** | ✅ **V2.33** — the `sidewalk` preset F69 carried in |

**Theme D — the designer's workflow**

| ID | Feature | Impact | Effort | Risk | Principle |
|----|---------|--------|--------|------|-----------|
| F113 | Design variants + side-by-side comparison *(was F90 — renumbered V2.52)* | **High** | L | Med | P9, P1 |
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

### ✅ F77 · The neighbour's-eye view — *Shipped V2.33 · was Impact Med · Effort S · Risk Low (P5, P13)*

Camera at the sidewalk, at eye height, each season. Not the designer's orbit — the view that
actually decides whether this planting gets a complaint or a question about where to buy the seeds.
Nearly free once F69 lands, and it is the honest test of F75's advice.

**Shipped** exactly as predicted — F69 carried it in for free.
`src/presentation_still.py` declares `CAMERA_PRESETS = ("overview", "orbit", "walk",
"sidewalk")` and names this card in the comment above it; the camera itself is
`html/scene3d/08-modes.js:sidewalk`, eye at 1.65 m on the boundary's near edge. It stayed
on the open list until V2.52 purely because nobody came back and struck it off — which is
the failure mode a status marker exists to prevent.

---

## Theme D — the designer's workflow

The app is built for the owner-occupier converting their own lawn, and does that well. A landscape
designer using it professionally hits four walls, none of which is about ecology.

### F113 · Design variants + side-by-side comparison — *Impact High · Effort L · Risk Med (P9, P1)*

*(Held **F90** until V2.52. F90 is the plant directory, shipped V2.41; see the ID ledger.)*

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
| F85 | The guide — a fauna companion that explains the app, starting with Site Info. **Absorbs F106** (V2.52) | **High** | L | Med — new UI surface | P5, P13 |
| F86 | Notes that add up — one store, notes from anywhere, a document that does something | Med | M | Med | P11, P4 |
| ~~F87~~ | ~~Game-style save/load~~ — **shipped V2.39**: `user_data_dir()/saves`, Save stops asking, File → Open lists your designs (name · when · plants · species · site), and the crash-recovery autosave moved out of the `$HOME` dotfile | **High** | M | Low | P13 |
| F88 | The Learn tab as a curriculum — the app, design, flora & fauna; gamified | Med | L | Low | P5, P7 |
| F89 | The 3D preview's UX review — ten buttons over two rows | Med | M | Med | P5 |

### F85 · The guide — *Impact High · Effort L · Risk Med (P5, P13)* — **absorbs F106**

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
split view · F102 one 3D toolbar · F103 flight physics · F108 life-size creatures +
flap-flap-glide + creature collision · F109 the same three verbs in the 3D preview,
and a net that is held and has a reach · F110 bee mode at the right scale, with
the other animals and the walker in view.

### F107 · Hand-painted lepidoptera wings — *Impact High / Effort L / Risk Med*

> *"I also want the butterflies and bees in particular to accurately reflect reality
> with their sprites, a generic butterfly does nothing… With lepidoptera I would even
> be willing to digitally draw/paint the wings to make this happen."*

**Half of this already exists and the author should be pointed at it first.**
`scripts/tune_fauna.py` (`http://127.0.0.1:8757`, documented in `docs/3D_SPRITES.md`)
is the character editor being described — per species, it already edits bee build,
abdomen shape, **band count and band colours**, fuzz and metallic sheen; and lep
wingspan, forewing / hindwing / margin colours, wing shape, wing pattern, resting
posture and flight style, each with a drawn SVG vocabulary beside the dropdown. The
"7 bands of colour" memory is real: that is the bee band editor, shipped in V2.36.

**What genuinely does not exist is the painting**, and it is a real piece of work
rather than a bench extension:

* The fauna GLBs ship with **no UVs and no textures, by design** — a contract stated in
  `html/scene3d/01b-surface.js` and relied on by every procedural surface. A painted
  wing breaks it for one taxon, so the lep material needs its own path in
  `09-models.js` rather than a global change.
* Needs a **wing template** — an unwrapped fore/hind outline the author paints against
  — and a decision about whether one image covers both sides.
* Needs an **import path**, which should reuse `src/photo_import.py`: downscale,
  re-encode, and strip EXIF unconditionally. (A scan of a specimen photographed in a
  yard carries that yard's GPS coordinates.)
* Needs a schema slot with `origin='seed'` vs `'user'` semantics, like `plant_photos`
  (schema v55), so a reseed does not destroy work the author did by hand.

Scoped in V2.46 and deliberately not started: it wants its own increment and a
conversation about what the template looks like before any code.

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

### ~~F106~~ · The companion, and the glossary half of it — **merged into F85 in V2.52**

**This card and F85 are the same feature, written twice.** Both propose a fauna companion
that explains the app; both prescribe "do the cheap glossary half first, and separately";
both reuse `docent.py`'s beat shape; both flag the same P11 risk in the same words. Two IDs
for one feature is the ID-collision problem wearing a different hat — it makes the backlog
look longer than it is and splits the reasoning across two places. **F85** is the survivor
(it is the older handle, and it is the one `USER_FEEDBACK.md` points at); the paragraphs
below are kept here as the record and the ID is retired.

Pick a native bee, butterfly or chickadee at first boot; it explains things as you go.
Reuses `docent.py`'s beat shape and `learn_state` (schema v62) for the choice.
**The art does not exist in this repo in any form**, so this is mostly a drawing
problem, not a code one — budget accordingly.

**Do the cheap half first and separately.** ~12 of ~20 Site Info metrics have no
explanation anywhere, and `src/climate.py:zone_description()` returns exactly the right
sentence and is called by nothing — still true as of V2.52, on the third increment that has
written it down. A Qt-free glossary module plus one `setToolTip` per metric answers the
tester's actual complaint at a fraction of the cost, and gives the companion something to
read out later.

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
**F92** (order file — a day) → **F91** (substitution) → **F113** (variants) → **F93** (palettes).

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
