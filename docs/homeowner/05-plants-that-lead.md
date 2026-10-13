# 5 · Lead with the plants that do the most and are easiest to grow

*Part of the [homeowner-path plan](README.md). Work items **PR-1 to PR-9**;
owner decisions **L1 to L10** ([12-decisions.md](12-decisions.md)). Measured on
V3.17 against the shipped catalogue (424 plants, 250 on the Edmonton list).*

> **The owner's answers (13 October 2026) revise PR-1.** The ranking is **Impact
> only, with feasibility as words** (L1): the order is Impact (0–11, §4.1), the
> bands are cut on Impact (thresholds set when PR-1 is built so the top band
> holds about the top 40), and §4.2's feasibility points become the reasons and
> cautions on the row and page (where to buy, dry ground, fits, behaviour), not a
> score. A yard's size is **measured, not assumed** (L3): the *fits* words use
> the front and back yards measured from the outline less the house (PY-12 in
> [07](07-plan-my-yard.md)); with no outline there are no size words. A plant
> whose spreading is **not yet checked shows nothing** about spreading (L5) until
> the spread review (F246) records it. The other L answers took the
> recommendation, including Chokecherry leading (L4) and free-text notes never
> shown on the desktop (L8, P12).

The owner: the app *"is not intended to be a flora reference (certainly not an
ID reference) but the information provided should rather be useful for finding
the appropriate plants for the conditions at hand and in order to place them
most effectively. And the plants should focus on and lead with those making the
greatest impact ecologically and most feasibly to plant."*

## In one paragraph

Today nothing a beginner sees first is ordered by value or feasibility: the
plant list, the Plant Directory, the community library and the score tips are A
to Z, and around Edmonton the "Recorded near this site" order is also A to Z,
because 246 of the 250 Edmonton natives tie. This part proposes one Qt-free
ranking, `src/plant_priority.py`, in two halves a person can read: **Impact**
(what the plant does for local wildlife, from records the app already trusts)
and **Feasibility** (can a beginner buy it, plant it in an ordinary city yard
and keep it). It **orders and never hides** (P9), and every plant carries its
reasons and cautions in words. Computed for the 250 Edmonton natives, it leads
with Chokecherry, Joe-Pye Weed, Smooth Aster, Pussy Willow, Red Osier Dogwood
and the goldenrods and asters, and puts the 19 pond plants last. It also shows
that the shipped data cannot yet keep known spreaders (aspen, Late Goldenrod,
Fireweed, Wild Raspberry) out of the top: that needs the spread review (PR-7).
The second half proposes what the plant page shows in each of the two ways of
using the app.

The numbers below were produced by
[`prototypes/plant_priority_prototype.py`](prototypes/plant_priority_prototype.py);
its full output is in
[`prototypes/ranking-shipped-data.csv`](prototypes/ranking-shipped-data.csv)
and, with the candidate spread review applied,
[`prototypes/ranking-after-spread-review.csv`](prototypes/ranking-after-spread-review.csv).
Run it from the repository root against a seeded database:
`VARIANT=B python3 docs/homeowner/prototypes/plant_priority_prototype.py out/`
(`VARIANT=C` applies the candidate spread review; `VARIANT=A` is the first
draft, kept to show how sensitive the order is). It is a reference for PR-1,
not production code.

---

## 1. What decides what a beginner sees first today

| Surface | Where | Order today | What an Edmonton beginner sees first |
|---|---|---|---|
| Placement › Plants | `src/plant_panel.py:223`; order in `src/plant_picker.py:337-351` (`set_site` switches to "suits") | "Recorded near this site" with a pin (`src/plant_filters.py:442-450`), else Name | Alkali Cord Grass, Alpine Bluegrass, Alpine Hedysarum, American Brooklime, **American Elm** (not native to Alberta). Of the first 20, 4 are not native around Edmonton and none is a Top pick below |
| Filters shown first | `src/filter_area.py:35` `EVERYDAY` | Type, Sun, Water, Where to buy; Native, Edmonton native, Easy to find, Pet safe | *Edmonton native* is off by default (first-pass R30) |
| Plant Directory | `src/plant_directory_window.py:53` | Name | Alaska Harebell, Alberta Penstemon, Alder-leaved Buckthorn…; 13 of the first 20 are not native around Edmonton |
| Community library | `src/polyculture_panel.py:1099-1100`; keys `src/db/polycultures.py:532-556` | A to Z, in A to Z folders | "Easiest to buy" exists (V3.14) but is not the default |
| Score tips ("Try: …") | `src/analysis_panel.py:1893-1966` | First five Alberta natives per tag, `ORDER BY common_name` | Keystone: Alpine Aster, Balsam Poplar, Basket Willow, Bebb's Willow, Chokecherry (R39) |
| Generate (offline) | `src/llm_design.py:2457-2539` `_rank_offline_plants` | Nearby records first, then tag points plus `sourcing.ease`, round-robin by layer | Without the Edmonton goal, the first 21 for an Edmonton yard include Foothills Rough Fescue, Rocky Mountain Juniper and Alpine Bluegrass |
| AI palette | `src/llm_design.py:374-394` | Nearby records first, then catalogue order | Same tie |
| Design review's repairs | `src/llm_design.py:1940-1967` | Not rare first, then nearby | Ties broken by catalogue order |

The one existing order that comes close is **Animals supported**
(`src/plant_filters.py:457-462`): with *Edmonton native* on, 19 of its first 20
are Top or Good picks below. But it counts every documented animal, so bee-visit
counts lead it (Boreal Yarrow first), and it knows nothing of size, spread,
buying or ponds.

---

## 2. What the catalogue knows about each plant (the 250 Edmonton natives)

| Field or record | Where | Filled | Use in a ranking |
|---|---|---|---|
| On the Edmonton list | `src/native_here.py:155` `native_around` | 250 (191 by the evidence rule, 59 by the owner's rulings) | The place term (§4.4) |
| Recorded near the pin | `src/site_fit.py:112` `locality` | 246 "here", 4 "near" | Useless as an order in Edmonton; keep elsewhere |
| Use tags (`plant_uses`) | synthesized on read | keystone_species on 27 (genus rule, `src/data_quality.py:1796-1801`) | Keystone floor only; the other tags are authored and partly contradict the edges (ROADMAP F8) |
| Caterpillar host records (Lepidoptera `larval_host`) | `plant_fauna` | 54 plants; most is 19 | Core of Impact |
| Bee visits (nectar, pollen) | `plant_fauna` | 151 plants; median about 10 species; most 95 | Capped term |
| Bird records (fruit, seed, nesting, cover, nectar) | `plant_fauna` | 47 plants | Term |
| Specialist flag | `plant_fauna.specificity` | 15 plants (milkweed–Monarch, violets–fritillaries, snowberries–Snowberry Clearwing, nettle–Red Admiral…) | Small bonus |
| Bloom period | `bloom_period` | 244 | Season term |
| Availability tier | `availability_class` (`scripts/rank_availability.py`, a V3.14 judgment; owner review F227 open) | all 250: native nursery 150, seed or plug 47, rare 23, garden centre 21, big box 9 | Feasibility |
| Price | `price_low_cad`/`price_high_cad` | all 250, mostly the type default (`src/sourcing.py:26-38`) | Not used: says nothing a type does not |
| Photograph | `image_url` | 188 (62 without) | Feasibility: a person buys what they can recognise |
| Spread | `spread_habit` | 14 (236 blank) | Feasibility, once reviewed (PR-7) |
| Suckering | `branching = 'suckering'` | 5 | Feasibility |
| Toxicity | `toxicity_pets`, `toxicity_humans` | 29 and 22 assessed | Caution words only, never a score |
| Standing water | `src/zoning.py:216-228` `needs_standing_water` | 19 need it | Feasibility cap |
| Height and spread | `mature_height_meters`, `mature_canopy_m`, `spacing_meters` | all | Feasibility, using the generator's own rule (`src/llm_design.py:1814-1832`) |
| Water needs | `water_needs` | medium,high 85; low 78; low,medium 65; high 14; other 8 | "Copes with a dry spell" term; "wants moist soil" caution |
| Annual or biennial | `perennial_or_annual` | 8 | Small feasibility cost |
| Animal ranges | none finer than the province (`fauna.ab_native`) | | Backlog F190: say "on record in Alberta", never "lives here" |

## 3. Which records are trustworthy enough to rank on

| Record | Count (catalogue) | How it got in | Verdict |
|---|---|---|---|
| Caterpillar host, Alberta literature (Acorn & Sheldon 2006; Pohl et al. 2018) | 114 citations | Read from the regional books | **Rank on it** |
| Caterpillar host, GloBI (iNaturalist 52, SCAN specimen labels 55, others 12) | 119 citations | Gated on an explicit `hostOf` or an observed larva on that plant (`scripts/ingest_fauna_edges.py:188-221`, `scripts/fetch_fauna_edges.py:87-93`); North America bounding box | **Rank on it**; the page says "on record", not "in Edmonton" |
| Bird fruit, seed, nest (Cornell Birds of the World; GloBI for birds) | 115 rows | Literature and the bird gate | **Rank on it** |
| Bee and other nectar or pollen visits | 6,737 rows; 5,467 of 5,585 nectar rows from GloBI | Visitation records | **Capped** (at most 3 points): they measure how often people photographed the plant as much as its value |
| Specialist flag | 29 rows | Authored | Small bonus only |
| Derived genus edges (`plant_fauna_derived`, 1,045 rows) | | Genus-level restatements, mostly bumble bees | **Not ranked on**: the keystone floor is already the one genus-level term |
| Companion pairings, community co-membership, shared-fauna edges | | Authored or computed, uncited | **Not ranked on** |
| Keystone genera (9) | 27 Edmonton members | Genus rule from Tallamy & Shropshire 2009 and Narango, Tallamy & Shropshire 2020 (*Nature Communications* 11:5751) | **Floor** for caterpillar points, because species records are thin |

**Never rank on absence.** A plant with no records is "little recorded", not
"low value" (`src/confidence.py`: absent is not estimated).

---

## 4. The proposal: `src/plant_priority.py`

Qt-free, anchored `Design principle P6 — see docs/DESIGN_PHILOSOPHY.md` (make
ecological value legible), with P9 in its rules. Every weight lives in one table
at the top of the module, so an owner's correction is a one-line change.

### 4.1 Impact: what it does for local wildlife (0 to 11)

| Part | Points | Rule |
|---|---|---|
| Caterpillars | 0–4 | Distinct Lepidoptera with a `larval_host` record to an Alberta animal: 0 → 0, 1–2 → 1, 3–5 → 2, 6–12 → 3, 13+ → 4. **Keystone floor:** a woody keystone (oak, cherry, willow, birch, poplar) gets at least 4, a herbaceous one (goldenrods, asters, sunflowers) at least 3 |
| Specialist | 0–1 | Any documented edge flagged `specialist` |
| Birds | 0–2 | 1 for the `bird_food` tag or one bird on record; 2 for 5+ birds on record |
| Bees | 0–3 | Distinct bee species with a nectar or pollen record: 5+ → 1, 15+ → 2, 40+ → 3 |
| Season | 0–1 | Flowers in April or May, or into September (the thin ends of an Edmonton season). **Not for grasses, sedges and rushes**: wind-pollinated, their "bloom" feeds no bee |

### 4.2 Feasibility: can a beginner buy it, plant it and keep it (0 to 9)

| Part | Points | Rule |
|---|---|---|
| Buy | 0–3 | Big box or garden centre 3, native nursery 2, seed or plug 1, rare 0, unrecorded 1 (absent is not rare, as `src/sourcing.py:244-247` already rules) |
| Dry ground | 0–2 | 2 unless `zoning.needs_standing_water` |
| Fits | 0–2 | By the generator's own rule (`llm_design._too_big_for`): 2 if it fits a 100 m² bed, 1 if it fits the yard, 0 if not. The yard is the drawn boundary's area when there is one; before a boundary, a 180 m² city back yard (decision L3) |
| Behaves | −2–0 | `spread_habit` aggressive −2, self-seeding −1, `branching` suckering −1; blank scores 0 and the page says "Not yet checked for spreading" |
| Photo | 0–1 | Has a photograph |
| Life | −1–0 | Annual or biennial −1 |
| Dry spells | 0–1 | `water_needs` includes "low" |
| Caps | | Too big for the yard: at most 3. Needs standing water: at most 2 |

### 4.3 Bands and order

| Band (the words a person sees) | Rule | Edmonton natives (shipped data) |
|---|---|---|
| **Top pick** | Impact ≥ 6 and Feasibility ≥ 7 | 22 |
| **Good pick** | Impact ≥ 3 and Feasibility ≥ 6 | 55 |
| **Easy to grow** | Impact ≤ 2 and Feasibility ≥ 6 | 118 |
| **Needs the right spot** | Impact ≥ 3 and Feasibility < 6 | 8 |
| **For a pond or a specialist** | Impact ≤ 2 and Feasibility < 6 | 47 |

Order: band, then Impact × Feasibility, then Impact, then Feasibility, then
name. The product means a plant has to do well on both halves to lead; the
bands mean a 20 m tree that does not fit the yard comes after an easy flower,
and moves back up when the boundary is an acreage. **No number is shown to a
beginner** (P9: no false precision); the advanced plant page shows the parts.

### 4.4 The place term

When the pin is inside a place with a local list (`native_here.place_at`), a
plant not on that list goes to a sixth band, **"Not native around Edmonton"**,
at the end. An order, not a filter: the *Edmonton native* toggle stays the
filter, and the Edmonton edition may switch it on (decision L10). Without this
term, 7 non-Edmonton plants reach the top 40 of the whole catalogue, including
Canada Goldenrod and Showy Milkweed, the two the first pass objected to in the
worked example (R14). Outside any place the term does nothing, and
`site_fit.locality` stays a tie-break.

### 4.5 Words: reasons and cautions

Each plant gets reasons (what it does) and cautions (what to know) from a
closed table. They **never read the free-text Notes**, so nothing from a note
can reach them (P12).

| When | Reason words |
|---|---|
| 1+ caterpillar species on record | "Caterpillar food for 15 kinds of moth and butterfly" ("one kind" for 1) |
| Keystone genus, fewer than 6 on record | "Willows feed more kinds of caterpillar than almost any other plant" (cherries, willows, poplars and aspens, birches, oaks, goldenrods, asters, sunflowers) |
| Specialist | "The only caterpillar food of the Snowberry Clearwing" / "A nest site the Yellow Warbler depends on" |
| Birds on record | "Berries or seed for 14 kinds of bird"; tag only: "Seed or berries for birds" |
| 5+ bees | "Visited by 52 kinds of native bee" |
| Season | "Flowers in April or May, when early bees need it" / "Flowers into September, when little else does" |
| Impact ≤ 1 | "Little is recorded yet about what it feeds" |

| When | Caution words |
|---|---|
| Needs standing water | "Needs a pond or standing water" |
| Too big for the yard | "Grows to 20 m tall: too big for a yard this size" |
| Spreads (−2) | "Spreads by runners or suckers: give it room or an edge" |
| Suckers or seeds (−1) | "Suckers or self-seeds a little" |
| Spread blank | (page only) "Not yet checked for spreading" |
| Rare | "Hard to find for sale" |
| Seed or plug | "Usually sold as seed or small plugs" |
| Moist (no "low", has "high") | "Wants moist soil: a low spot, or water in dry spells" |
| Annual or biennial | "Lives one or two years and comes back from seed" |
| Toxicity high | "Poisonous to pets if eaten" / "Poisonous to people if eaten" |

The list row shows the band and the first reason; the page shows all of them;
advanced adds the citation behind each count.

### 4.6 Rules it keeps

- **Ranks, never filters** (P9): `rank(rows)` returns the same rows, reordered.
- **Absent is not low**: a blank field scores 0, never a penalty, and the words
  say "not yet checked" or "little recorded".
- **The Habitat Value Score does not move.** This module reads the same records
  but changes no score (`src/habitat_score.py` keeps its weights; the
  headline-stability rule is untouched).
- **The area follows the design**: one call with the boundary's area re-bands
  trees and large shrubs.
- **P12**: reasons and cautions come only from structured fields and edges.

---

## 5. What it produces for the 250 Edmonton natives

Distribution on the shipped data: Impact 0: 83 plants, 1: 40, 2: 42, 3: 30, 4:
17, 5: 11, 6: 12, 7: 10, 8: 4, 10: 1. Feasibility 2: 19, 3: 8, 4: 5, 5: 23, 6:
36, 7: 68, 8: 74, 9: 17. Of the 83 with no Impact points, 41 are grasses,
sedges and rushes and 14 aquatics: that is where the records are thinnest, not
where the value is lowest.

**Top 40** ("Records" = caterpillar / bee / bird species on record; last column
= rank after the candidate spread review in PR-7):

| # | Plant | Type | Impact | Feas. | Band | Records | After spread review |
|---|---|---|---|---|---|---|---|
| 1 | Chokecherry | shrub | 10 | 9 | Top pick | 15 / 52 / 14 | 1 |
| 2 | Joe-Pye Weed | wildflower | 8 | 8 | Top pick | 19 / 16 / 2 | 2 |
| 3 | Smooth Aster | wildflower | 7 | 9 | Top pick | 2 / 33 / 1 | 3 |
| 4 | Pussy Willow | shrub | 8 | 7 | Top pick | 15 / 14 / 2 | 4 |
| 5 | Fireweed | wildflower | 7 | 8 | Top pick | 6 / 89 / 1 | 20 (Good pick) |
| 6 | Late Goldenrod | wildflower | 7 | 8 | Top pick | 0 / 36 / 1 | 21 (Good pick) |
| 7 | Pin Cherry | tree | 7 | 8 | Top pick | 4 / 11 / 3 | 8 |
| 8 | Red Osier Dogwood | shrub | 7 | 8 | Top pick | 3 / 26 / 5 | 5 |
| 9 | Stiff Goldenrod | wildflower | 7 | 8 | Top pick | 0 / 17 / 1 | 6 |
| 10 | Common Snowberry | shrub | 6 | 9 | Top pick | 2 / 51 / 3 | 11 |
| 11 | Many-flowered Aster | wildflower | 7 | 7 | Top pick | 0 / 20 / 0 | 7 |
| 12 | Purple-stemmed Tall Aster | wildflower | 7 | 7 | Top pick | 0 / 18 / 0 | 9 |
| 13 | Lindley's Aster | wildflower | 6 | 8 | Top pick | 1 / 5 / 0 | 10 |
| 14 | Tall Goldenrod | wildflower | 6 | 8 | Top pick | 0 / 9 / 1 | 23 (Good pick) |
| 15 | Wild Raspberry | shrub | 6 | 8 | Top pick | 3 / 45 / 0 | 24 (Good pick) |
| 16 | Elegant Goldenrod | wildflower | 6 | 7 | Top pick | 0 / 11 / 0 | 12 |
| 17 | Marsh Aster | wildflower | 6 | 7 | Top pick | 0 / 5 / 0 | 13 |
| 18 | Nuttall's Sunflower | wildflower | 6 | 7 | Top pick | 0 / 6 / 1 | 190 (Needs the right spot) |
| 19 | Prairie Goldenrod | wildflower | 6 | 7 | Top pick | 0 / 30 / 1 | 14 |
| 20 | Stiff Sunflower | wildflower | 6 | 7 | Top pick | 0 / 5 / 1 | 191 (Needs the right spot) |
| 21 | Water Birch | tree | 6 | 7 | Top pick | 4 / 0 / 2 | 15 |
| 22 | Willow Aster | wildflower | 6 | 7 | Top pick | 0 / 11 / 0 | 192 (Needs the right spot) |
| 23 | Bebb's Willow | tree | 8 | 6 | Good pick | 3 / 5 / 1 | 16 |
| 24 | Sandbar Willow | shrub | 8 | 6 | Good pick | 9 / 11 / 2 | 17 |
| 25 | Bearberry | groundcover | 5 | 9 | Good pick | 1 / 23 / 2 | 18 |
| 26 | Saskatoon Berry | shrub | 5 | 9 | Good pick | 1 / 13 / 5 | 19 |
| 27 | Highbush Cranberry | shrub | 5 | 8 | Good pick | 5 / 3 / 5 | 22 |
| 28 | Pearly Everlasting | wildflower | 5 | 8 | Good pick | 1 / 50 / 0 | 28 |
| 29 | Giant Hyssop | wildflower | 4 | 9 | Good pick | 0 / 25 / 1 | 33 |
| 30 | Wild Bergamot | wildflower | 4 | 9 | Good pick | 0 / 42 / 3 | 25 |
| 31 | Woodland Strawberry | groundcover | 4 | 9 | Good pick | 0 / 22 / 1 | 26 |
| 32 | Basket Willow | shrub | 5 | 7 | Good pick | 5 / 0 / 0 | 27 |
| 33 | Evening Primrose | wildflower | 5 | 7 | Good pick | 3 / 8 / 2 | 38 |
| 34 | Sticky Goldenrod | wildflower | 5 | 7 | Good pick | 0 / 0 / 0 | 29 |
| 35 | Western Snowberry | shrub | 5 | 7 | Good pick | 2 / 20 / 1 | 30 |
| 36 | White Prairie Aster | wildflower | 5 | 7 | Good pick | 0 / 8 / 0 | 31 |
| 37 | Canada Milk Vetch | wildflower | 4 | 8 | Good pick | 4 / 19 / 0 | 32 |
| 38 | Flat-topped Goldenrod | wildflower | 4 | 8 | Good pick | 0 / 29 / 0 | 48 |
| 39 | Hairy Golden Aster | wildflower | 4 | 8 | Good pick | 0 / 33 / 0 | 34 |
| 40 | Meadowsweet | shrub | 4 | 8 | Good pick | 1 / 20 / 1 | 42 |

The per-part points for every plant are in the CSV. The top 40 are 24
wildflowers, 11 shrubs, 3 small trees and 2 groundcovers; no grass, because
grasses carry almost no records.

**Bottom 20** (ranks 231–250): Slough Grass and Turned Sedge (seed or plugs
only, no records), Western Wood Lily (hard to buy), Variegated Horsetail and
Common Scouring-rush (recorded spreaders), then 15 plants that need standing
water: Arum-leaved Arrowhead, Broad-leaved Water-plantain, Common Bladderwort,
Common Mare's-tail, Floating Marsh-marigold, Giant Bur-reed, Great Bulrush,
Ivy-leaved Duckweed, Rat Root, Sago Pondweed, Small Bottle Sedge, Spiked
Water-milfoil, Swamp Horsetail, Water Arum, Yellow Pond-lily.

**"Needs the right spot"** (8): Paper Birch, Trembling Aspen, Balsam Poplar,
Jack Pine, White Spruce (too tall for a 180 m² yard; they move up on a large
boundary), Bunchberry and Arctic Aster (hard to buy), Stinging Nettle (spreads).

**The first screen.** A ranked list of 24 wildflowers in its first 40 does not
look like a garden. For the simple mode's first rows, interleave by layer in a
fixed pattern per ten rows (4 flowers, 3 shrubs or trees, 2 grasses or sedges, 1
groundcover or vine), each layer in ranking order:

| Row | Plant | Layer | Band |
|---|---|---|---|
| 1 | Joe-Pye Weed | flower | Top pick |
| 2 | Chokecherry | shrub | Top pick |
| 3 | Smooth Aster | flower | Top pick |
| 4 | Creeping Spikerush | sedge | Easy to grow (questioned below) |
| 5 | Pussy Willow | shrub | Top pick |
| 6 | Fireweed | flower | Top pick |
| 7 | Bearberry | groundcover | Good pick |
| 8 | Pin Cherry | small tree | Top pick |
| 9 | Late Goldenrod | flower | Top pick |
| 10 | Rough Fescue | grass | Easy to grow |
| 11 | Stiff Goldenrod | flower | Top pick |
| 12 | Red Osier Dogwood | shrub | Top pick |
| 13 | Many-flowered Aster | flower | Top pick |
| 14 | Blue Grama Grass | grass | Easy to grow |
| 15 | Common Snowberry | shrub | Top pick |
| 16 | Purple-stemmed Tall Aster | flower | Top pick |
| 17 | Woodland Strawberry | groundcover | Good pick |
| 18 | Wild Raspberry | shrub | Top pick |
| 19 | Lindley's Aster | flower | Top pick |
| 20 | Canada Wild Rye | grass | Easy to grow |

**Compared with today:** the proposed top 20 sit at a median row of 141 (worst
274) in today's Placement › Plants list with an Edmonton pin. Today's first 20
contain no Top pick; the proposal's contain 16.

---

## 6. Sanity check: what an Edmonton gardener would question

| Plant | Where it lands | The question | Resolution |
|---|---|---|---|
| Trembling Aspen, Balsam Poplar | 197–198 for a city yard; would be top 15 on an acreage | Sucker far into lawns and beds; 20–25 m tall | The Fits rule already moves them down; the spread review (−2) keeps them out of the top on acreages too |
| Late Goldenrod, Tall Goldenrod, Fireweed, Nuttall's Sunflower, Stiff Sunflower, Willow Aster | Top picks on shipped data | Aggressive rhizomatous spreaders in a small bed | **Needs PR-7.** After the candidate review: Fireweed 20, Late Goldenrod 21, Tall Goldenrod 23, the two sunflowers and Willow Aster about 190 |
| Wild Raspberry, Common Snowberry | Top picks on shipped data | Sucker into thickets | Drop to 24 and 11 after the review, with "Spreads" in words |
| Chokecherry | First, before and after the review | Suckers; black knot is common in Edmonton; pets and pits | Defensible on value (15 caterpillars, 14 birds on record), but it must show "Spreads by suckers" and "Poisonous to pets if eaten" (decision L4) |
| Joe-Pye Weed | Second | 19 caterpillar records, all specimen labels with a `hostOf` verb; wants moist soil; on the list by the owner's ruling | Keep, with "Wants moist soil"; or count specimen-label hosts at half (decision L6) |
| Pussy Willow, Purple-stemmed Tall Aster, Marsh Aster, Red Osier Dogwood | Top picks | Moist-site plants in a dry yard | Shown with "Wants moist soil"; once the guided flow asks about moisture, the caution becomes a fit (decision L6) |
| Creeping Spikerush | First grass-like plant on the interleaved screen | A marsh spikerush | It wins on one caterpillar record. Count a dry-spell point twice for graminoids, or leave sedges to the advanced list (decision L6) |
| Wild Bergamot | 30 (Good pick) | Locally regarded as a top pollinator plant | No caterpillar record in the catalogue; 42 bees give it 3 points. Honest about what is recorded; still a Good pick |
| Saskatoon Berry | 26 (Good pick) | *Amelanchier* hosts many caterpillars elsewhere | One record here: a data gap, not a verdict |
| Grasses (Rough Fescue, Blue Grama, Canada Wild Rye) | "Easy to grow" | Under-recorded hosts of skippers and wood-nymphs | Honest band; the generator places grasses as the meadow matrix whatever their rank |
| Highbush Cranberry (*Viburnum opulus*) | 27 | Big-box stock may be the European variety | A buying caution (decision L9) |

---

## 7. The plant page in two modes

### 7.1 What it shows today (measured)

`src/species_page.py:271-311` renders up to 19 sections from
`src/plant_directory.py:90-184` (`species_entry`). Measured offscreen at 410 ×
600 with no photograph downloaded: Chokecherry 550 words, Wild Bergamot 489,
Smooth Aster 384; the bodies are 1,861, 1,731 and 1,395 px tall against a 460 px
visible area: three to four screens, before the photograph's 240 px. The longest
section is "Where these relationships came from", 155 to 253 words of
citations. **There is no line about spreading**: `spread_habit` is not in
`species_entry` and not on the page.

### 7.2 Section by section

| Section today | Lines (`species_page.py`) | Simple | Advanced | Note |
|---|---|---|---|---|
| Name, scientific name, "N in this design" | 252–269 | Keep (the Latin name is how nurseries label natives) | Keep | |
| Place button | 131–140 | Keep | Keep | |
| Add to mix | 141–155 | Hide | Keep | The mix is an advanced placing tool |
| Photograph and credit | 346–390 | Keep | Keep | The credit is a licence condition |
| Why here (generator's reasons) | 278–281 | Keep | Keep | |
| Why it matters (badges) | 282–283 | **Replace** with "Why this plant": band + reason sentences (§4.5) | Keep badges; add the points breakdown ("Impact 10 of 11: caterpillars 4, birds 2, bees 3, season 1") | |
| Roles (use tags) | 284–285 | Hide | Keep | Duplicates the badges; shows "Medicinal", "Wildlife Habitat" |
| Conditions | 286–288 | Sun and water in words ("Full sun to part shade. Dry to average soil.") | Keep pH and zone | Every Edmonton native is hardy at the city's zone; pH only as a caution when outside the site's |
| Size | 289–293 | Keep, **one spacing number** (first-pass R20) | Keep | |
| Season words, bar, calendar tasks | 294, 392–408 | Bar plus "Flowers May to June, white. Fruit August to September." | Keep the colour provenance note and tasks | |
| What it looks like (leaf shape, branching) | 295–296 | Hide | Keep, or remove (decision L7) | Identification; it exists to explain the 3D models |
| Native to (VASCAN province) | 410–416 | Hide in the Edmonton edition | Keep | |
| Around Edmonton | 417–419 | One line: "Native around Edmonton." / "Not native around Edmonton." | Keep the evidence sentence | |
| Found in (ecoregion record counts) | 421–442 | Hide | Keep | The website has range maps |
| Wildlife (counts and names) | 444–465 | One line by group, Alberta animals only: "On record with 52 kinds of native bee, 34 moths and butterflies (15 as caterpillars) and 14 birds." No list of names (72% of animals have no English name) | Keep names and "and N more" | F190: "on record", not "lives here" |
| Where these relationships came from | 467–492 | Hide | Keep | |
| Grows with (companions) | 494–503 | Hide | Keep | Uncited pairings; Wild Bergamot's include Bur Oak, which is not native around Edmonton |
| Edible parts | 301–302 | Hide | Keep | Not about choosing or placing |
| Where to get it | 505–512 | Keep the sentence; drop "Estimate (herb default); AB retail as of 2026"; add "See Where to buy" | Keep the note | |
| Safety | 304–305 | Recorded hazards only, plus "Not checked for toxicity" when blank (first-pass R10) | Keep | |
| Notes (free text) | 306–307 | Hide | Keep, or remove (decision L8) | Wild Bergamot's include "Traditional cold/flu remedy"; the website withholds notes under P12 |
| Where these numbers came from | 308–310 | Hide | Keep, or remove (decision L7) | |
| **New: How it behaves** | | "Stays in a clump." / "Spreads by runners or suckers: give it room or an edge." / "Not yet checked for spreading." | Same, with the source | Needs `spread_habit` in `species_entry` |

### 7.3 The simple page, written out (Chokecherry, about 110 words)

> **Chokecherry** · *Prunus virginiana*
> [Place Chokecherry on the map]
> [photograph] (credit)
> **Top pick**
> **Why this plant.** Caterpillar food for 15 kinds of moth and butterfly. Berries for 14 kinds of bird. Visited by 52 kinds of native bee. Flowers in May, when early bees need it.
> **Good to know.** Not yet checked for spreading *(after the review: Spreads by suckers into a thicket: give it room or an edge)*. Poisonous to pets if eaten.
> **Growing it.** Full sun to part shade. Dry to average soil; water weekly through its first summer. Grows to 5 m tall and 4.5 m wide in about 6 years. Plant 3 m apart. [season bar]
> **Buying it.** About $25 to $50 a plant, sometimes in big-box garden sections, usually as a cultivar. See Where to buy.
> **Native around Edmonton.**
> [Everything about this plant ▸] *(opens the advanced sections in place)*

### 7.4 Shape

A Qt-free `src/plant_page_sections.py` returns, for an entry and a mode, the
ordered `(heading, body, style)` list the page draws, with the simple wording.
`SpeciesPage._render` (`species_page.py:271-311`) loops over it instead of
calling each block in turn; the existing `_wildlife_block`, `_citation_block`
and the rest become the advanced bodies. `species_page.py` is at 667 of its
720-line ceiling (`tests/test_architecture_guard.py:149`), so the wording
belongs in the new module. The mode comes from the app-wide switch in
[02-two-ways-to-use-it.md](02-two-ways-to-use-it.md).

**Do not remove keys from `species_entry`**: the website builds its species
pages from the same function (`src/static_site_species.py`). Adding keys is safe.

---

## 8. Work items

| ID | Item | Effort | Depends on |
|---|---|---|---|
| **PR-1** | **`src/plant_priority.py`: the Impact and Feasibility ranking.** `Records` (caterpillars, bees, birds, specialists) read once from `plant_fauna JOIN fauna WHERE ab_native = 1` (no derived, companion or shared-fauna edges); `assess(plant, records=None, *, area_m2=None, place=None) -> Assessment(impact, feasibility, band, parts, reasons, cautions)`; `rank(rows, …)` returns the same rows reordered. Points and words exactly as §4; weights in one table. Read-only touch points: `data_quality.py:1796-1801` (`KEYSTONE_GENERA`), `llm_design.py:1814-1832` (`_too_big_for`), `zoning.py:216-228`, `native_here.py:123-160`. Move `animals_per_plant` (`plant_filters.py:494-510`) into it, to free room under that file's ceiling. Add a 300-line ceiling. Tests: `tests/test_plant_priority.py`: every part's thresholds from synthetic rows; the caps; blank spread scores 0 and says "Not yet checked for spreading"; `rank()` never drops a row; a no-record plant says "Little is recorded yet", never "low"; Trembling Aspen's band changes between 180 m² and 20,000 m²; on a freshly seeded catalogue, no standing-water or rare plant is in the Edmonton top 40, every aquatic is in the last band, and Chokecherry, Saskatoon Berry, Red Osier Dogwood and Smooth Aster are in the top 30; no reason or caution contains an underscore or Notes text. *Accept:* reproduces the top 40 above on the shipped data; 250 rows in, 250 out; all 424 plants assessed in under 0.3 s | M | — |
| **PR-2** | **"Best picks first" is the default order** of Placement › Plants and the Plant Directory. Add `('priority', 'Best picks first', 'Plants that feed the most local wildlife and are easiest to buy and grow in your yard come first. Nothing is hidden: the rest follow in the same list.')` as the first `ORDERS` entry (`plant_filters.py:173-188`); a `priority` branch in `order_plants` (`:425-468`) calling `plant_priority.rank` with the boundary's area and the pin's place; `PlantPicker` defaults to it (`plant_picker.py:73`) and `set_site` (`:337-351`) stops switching to "suits" (still offered); `plant_directory_window.py:53`; pass the boundary area on change (`app.py:2166`). Tests: `test_plant_filters.py` (priority first; equals `rank`); `test_plant_picker.py:124-146` rewritten. *Accept:* cold start, Placement › Plants reads "Best picks first", first rows Joe-Pye Weed, Chokecherry, Smooth Aster; with an Edmonton pin the first 20 hold no plant outside the Edmonton list; "Recorded near this site" still works and survives a new pin; `plant_filters.py` stays under 520 lines | S | PR-1 |
| **PR-3** | **Simple-mode plant row: band chip and one reason; layers interleaved on the first screen.** `PlantRowDelegate` (`src/plant_list_view.py:348-470`) replaces the zone badge (56 px) and the AB chip with a band chip and draws the first reason under the name (two-line row, 44 px); `row_description` (`:169-180`) adds band and reason for screen readers; the chip's tooltip lists every reason. First 20 rows interleaved (§5). Tests: interleave of the first 20; visual floors over the new chip. *Accept:* simple mode, Edmonton pin: row 1 "Joe-Pye Weed", chip "Top pick", "Caterpillar food for 19 kinds of moth and butterfly" beneath; advanced rows unchanged from today. Two-line rows halve the rows visible at 1366 × 768: check on screen with the owner | M | PR-1, MD-1 |
| **PR-4** | **The plant page in two modes** through `src/plant_page_sections.py` (§7), plus a "How it behaves" line. `species_entry` (`plant_directory.py:126-182`) gains `spread_habit`, `branching` and `priority`. Simple mode hides "Add to mix" and ends with "Everything about this plant ▸". Add a 250-line ceiling. Tests: `tests/test_plant_page_sections.py` (simple heading list exactly; advanced equals today's; word limit; forbidden strings; the four behaviour wordings); smoke: simple page shows "Why this plant", no "Roles". *Accept:* simple mode, Chokecherry: headings exactly Top pick, Why this plant, Good to know, Growing it, Buying it, Native around Edmonton; at most 150 words; none of "VASCAN", "records, high confidence", "Estimate (", "Where these relationships came from", or Notes text | M | PR-1, MD-1 |
| **PR-5** | **Score tips ordered by the ranking, from the Edmonton list, sized to the yard** (first-pass R39). In `analysis_panel.py:1893-1966` replace the three `ORDER BY common_name` queries with one fetch, filtered by tag, layer or month as now, then `plant_priority.rank(rows, area_m2=…, place=…)`, skipping placed plants and the two weakest bands; read `native_province`, not `native_to_alberta`. *Accept:* on the worked example, keystone tips start with Chokecherry or a willow, never Alpine Aster or Balsam Poplar; with an Edmonton pin no tip names a plant off the Edmonton list. **Superseded by OV-11** ([06](06-yard-overview.md)), which retires the Tips box; the overview's nudges carry plant examples ranked by PR-1 instead. Kept here for the record; not scheduled ([11](11-work-plan.md)) | S | PR-1 |
| **PR-6** | **The generator ranks its pool, palette and repairs by `plant_priority`.** `_rank_offline_plants` (`llm_design.py:2457-2539`), `_plant_palette` (`:374-394`), `_site_scoped_query` (`:1940-1967`): replace `value(p) + ease(p)` with `assess` (records loaded once per run; area = boundary; place = pin's place); keep the layer buckets, the wet/rare split and nearby-first outside a place. Tests: `tests/test_availability_rank.py:130-151` unchanged and passing; a new test: Edmonton pin, 216 m² boundary, the first 14 ranked candidates are all on the Edmonton list. Review each generator-fixture change rather than regenerating blindly. *Accept:* offline Generate on an Edmonton boundary with default goals places no plant off the Edmonton list among its first 14 picks and no standing-water plant without a pond | M | PR-1; coordinate with [07](07-plan-my-yard.md) |
| **PR-7** | **The spread review (first-pass R11).** `scripts/review_spread.py` in the pattern of `scripts/rank_availability.py`: an `OWNER` table `{scientific name: aggressive_rhizomatous | slow_spreader | self_seeding | clumping}` that wins over everything; dry-run prints changes, `--apply` writes `data/plants_master.json`; bump `_SCHEMA_VERSION`; a test fails if the catalogue and the script disagree (as `tests/test_availability_rank.py` does for tiers). **Candidate list for the owner to confirm** (a horticultural judgment, not catalogue data): −2 for Trembling Aspen, Balsam Poplar, Chokecherry, Wild Raspberry, Common Snowberry, Late Goldenrod, Tall Goldenrod, Flat-topped Goldenrod, Willow Aster, Nuttall's Sunflower, Stiff Sunflower, Fireweed, Canada Anemone, Prairie Sage, Spreading Dogbane, Golden Bean, Bluejoint Reed Grass, Silverweed, Cattail, Western Wheatgrass; −1 for Prickly Wild Rose, Pin Cherry, Meadowsweet, Pearly Everlasting, Evening Primrose, Giant Hyssop. About two hours of the owner's time for these 26 plus the blanks in the top 60. This also makes the Generate goal "Won't take over the yard" true for the plants it matters most for. *Accept:* every plant in the top 60 has a value or "clumping"; Nuttall's Sunflower, Stiff Sunflower and Willow Aster move to "Needs the right spot", Fireweed and Late and Tall Goldenrod to Good pick; each page says so in words | S (plus owner time) | P5 |
| **PR-8** | **Photographs for the top 60, and hero photos chosen for beauty** (first-pass R36). 12 of the top 60 have none (Many-flowered Aster, Elegant Goldenrod, Prairie Goldenrod, Stiff Sunflower, Bebb's Willow, Sticky Goldenrod, White Prairie Aster, Shrubby Cinquefoil, Western Willow Aster, Blanketflower, Prairie Thistle, Gumweed). Use the existing photo machinery (`src/db/photos.py`, `origin='seed'`), CC0, CC BY or CC BY-SA, credited. A test that the top 60 all have a photograph. *Accept:* each top-60 plant's first photograph shows it in flower or fruit. Needs network access to image sources | M | PR-1 for the order |
| **PR-9** | **Community library: "Best picks first" by default.** Add `('best', 'Sort: Best picks first')` first in `_SORT_BY_OPTIONS` (`polyculture_panel.py:167-174`) and as default (`:1099-1100`); in `sort_community_ids` (`db/polycultures.py:532-556`) key `best` = mean Impact × Feasibility of members, a member off the pin's local list sending the community after the rest. QSettings remembers an old choice, so the new default applies only where none is saved. *Accept:* Placement › Communities opens on "Best picks first"; a community with a non-Edmonton member sorts after every all-Edmonton one | S | PR-1 |

## 9. Data jobs this depends on

1. **The spread review** (PR-7).
2. **Photographs** for the 12 of the top 60 without one, and hero photographs
   chosen for beauty for the top 40 (PR-8).
3. **Toxicity** for the top 60 (48 blank): see first-pass R10 and
   [09-words.md](09-words.md) for the wording until then.

## 10. What could not be checked

- No Edmonton horticulturist or nursery reviewed the top 40 or the candidate
  spreader list; the sanity check uses general horticultural knowledge.
- Availability tiers are V3.14 judgments made without nursery catalogues
  (`scripts/rank_availability.py`'s header); the owner's review (F227) is open,
  and the Buy points inherit any error.
- Individual caterpillar, bee and bird records were not checked against their
  sources; GloBI records come from a North American bounding box, and animals
  have no range finer than the province (F190).
- The Narango, Tallamy & Shropshire 2020 paper could not be fetched (blocked);
  its summary figure (about 14% of native plant genera host about 90% of
  caterpillar species) is as reported by the National Wildlife Federation.
- The plant-page measurements were taken offscreen without photographs; with a
  photograph each page is about 240 px taller. The proposed simple page and row
  were not built.
- Typical Edmonton lot and yard sizes (a 15 × 36 m lot, about 180 m² of back
  yard) are typical figures, not city data; see [01-personas.md](01-personas.md).
