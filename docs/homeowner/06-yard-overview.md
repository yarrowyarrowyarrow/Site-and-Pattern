# 6 · How your yard is doing: the analysis as an overview

*Part of the [homeowner-path plan](README.md). Work items **OV-1 to OV-14**;
owner decisions **O1 to O7** ([12-decisions.md](12-decisions.md)). The switch
that hides the in-depth pages is [02-two-ways-to-use-it.md](02-two-ways-to-use-it.md)
(MD-1 to MD-5). The plant ranking used by some of the actions here is
[05-plants-that-lead.md](05-plants-that-lead.md) (PR-1).*

The owner values the ecosystem analysis **as an overview**, and finds that its
in-depth form hides what it is useful for. The persona is an Edmonton homeowner
who knows little about native plants. They want answers to a few plain
questions: is this working, is it right for here, what will it cost me, and
will the neighbours accept it.

## In one paragraph

Today the Design tab has six pages and, for the worked example, **2,202 words**.
It gives **two habitat scores for the same design** (83 on the Report card, 78 on
Habitat), **two wildlife counts** (263 and 271), **two sets of hours** (55 → 9 h
on screen, 36–75 → 6–13 h in the PDF) and **advice that contradicts itself**
("prune Tall Goldenrod" in October, beside a care calendar that says leave the
stems standing). It also never says how much of the bed will actually be
planted. A bed about a third covered when grown scores "Excellent habitat".
The proposal is one new first page, **Overview**: six items in plain words,
each with one action, in under 300 words. Every number on it comes from the
same function the advanced page and the PDF use. Everything in depth stays,
behind Advanced, with the defects below fixed. All numbers in this section were
measured on the worked example (11 × 8 m, central Edmonton) and on a design the
offline generator made for a 9 × 6 m front bed at 53.5232, −113.5263, using
the app's own code (method in §10).

**A note on coverage figures.** The first review (`SALE_READINESS_REVIEW.md`,
R13) counted each plant as the square of its catalogue spacing and reported 24%
for the example and 11% for the 41 × 31 m yard. This part counts each plant's
mature canopy disc (`mature_canopy_m`, 1.5 × spacing for every plant today),
which gives 35% and 17%. Different methods, same conclusion; this plan's
figures are the ones to use, because they are what `yard_overview.cover()` will
compute.

---

## 1. What the Design tab says today

### 1.1 The pages, measured

Visible text captured from the real window at 1366 × 768 (Xvfb, offline):

| Page | Built by | Words (example) | Words (generated bed) |
|---|---|---|---|
| Report card | `on_this_design_panel.py:181-200, 602-691` | 295 | 262 |
| Planted (Species, Communities) | `on_this_design_panel.py:119-179, 252-381` | 300 | 245 |
| Habitat | `analysis_panel.py:889-1072, 1522-1689` | 717 | 624 |
| Food | `food_page.py:70-687` | 372 | 381 |
| Over time (This month, Year by year, Hours of work) | `side_panel_layout.py:105-141`, `phenology_widget.py`, `planning_panel.py:142-340, 807-887` | 406 | 450 |
| Water | `planning_panel.py:393-659` | 112 | 120 |
| **Design tab total** | | **2,202** | **2,082** |
| Site › Sun & Shade | `analysis_panel.py:142-615` | 76 | 76 |
| Site › Wind | `analysis_panel.py:620-868` | 112 | 112 |

### 1.2 The headline numbers, measured

| | Worked example | Generated 9 × 6 m bed | First pass's 41 × 31 m yard |
|---|---|---|---|
| Plants, kinds | 19, 14 | 19, 11 | 130 |
| Score: Report card / Habitat page | 63 / 63 "Solid" | **83 / 78** "Excellent" | 90 "Excellent" |
| Ground covered once grown | **35%** (30.7 of 88 m²) | **30%** (16.4 of 54 m²) | **17%** (217 of 1,269 m²) |
| Wildlife: Report card / Food page | 589 / 589 | **263 / 271** | 510 (first pass) |
| Native around Edmonton (owner's list) | 12 of 14 | 10 of 11 | not measured |
| Pollinator bloom gaps, Apr–Oct | October | none | not measured |
| Plant cost | $203–$406 | $234–$478 | not measured |
| Hours, year 1: screen / PDF | 55 h / 35.9–74.6 h | 69 h / 44.9–93.2 h | not measured |
| Hours later: screen "Year 3+" / PDF "Years 2–4" | 9 h / 18.5–38.4 h | 10 h / 22.4–46.6 h | not measured |
| Cues to care present | 2 of 5 | 3 of 5 | not measured |

---

## 2. Every readout: the question it answers, and where it goes

**Disposition key:**

- **Overview:** what it says moves, in plain words, onto the new first page.
- **Advanced:** kept on its page, shown only with View → Advanced tools on (MD-1).
- **Retire:** removed. Each retired readout either duplicates another or gives
  wrong advice.

| # | Readout (where) | The persona's question it answers | Known defects | Disposition |
|---|---|---|---|---|
| 1 | Report card: "19 plants placed · 14 species · 95% Alberta-native" (`on_this_design_panel.py:653-657`) | What is in it? | Uses the seed flag `native_to_alberta`, not the owner's Edmonton list (Showy Milkweed counted as native) | **Overview** (item 3 "Right plants for here", from `native_here`) |
| 2 | Report card: Plant types, Vegetation layers, Ecological functions (`:658-684`) | none | Layers and functions fill only for community members; tag words | **Advanced** |
| 3 | Report card: Lawn conversion tally (`:528-550`) | How much lawn am I replacing? (only if zones are drawn) | Empty unless lawn zones are drawn | **Advanced** |
| 4 | Report card: Habitat value "63/100 (Solid habitat)", "589 wildlife species supported" (`:414-444`) | Is it good for wildlife? | R12 (no coverage term), R15/F190 ("supported" means "recorded anywhere"), **OVF-1** (differs from Habitat's score) | **Overview** replaces it in simple mode (items 1 and 4); **Advanced** keeps the number, fixed by OV-4 and OV-5 |
| 5 | Report card: "Where to grow next" nudges (`habitat_score.py:296-383`) | What should I add? | Points at filter paths; generic layer advice | **Overview** actions replace it; **Advanced** keeps it |
| 6 | Report card: "How it will be read", cues to care (`:496-526`, `cues_to_care.py:330-369`) | Will the neighbours or the bylaw object? (review question 5) | Frontage is assumed to be south unless OSM roads are stored, and the line says so | **Overview** (item 5) |
| 7 | Report card: Estimated cost (`:552-600`) | What will it cost? | **OVF-3** (mulch is charged for lawn, path and patio shapes) | **Overview** (item 6) |
| 8 | Report card: "What your spend creates" (`:470-494`) | none: repeats #4's count | R15 | **Retire** |
| 9 | Planted › Species, second line "feeds 91: 36 bees, …" (`:252-278`, `what_it_feeds.py:369-386`) | What did I put in, and what does each do? | "feeds" overstates the records (F190) | **Simple**, reworded "food for 91 kinds" (OV-5) |
| 10 | Planted › Communities "N community instances across M community names" (`:341-381`) | none for a novice | Jargon | **Advanced** |
| 11 | Habitat: big score "78 / 100" (`analysis_panel.py:910-917, 1558-1562`) | as #4 | OVF-1 | **Advanced** |
| 12 | Habitat: "vs. lawn: This design 78 / 100 · lawn ~0 / 100" (`:919-929`, `lawn_zones.py:113-161`) | Is it better than lawn? | Restates the score against a constant 0; reinforces R12 | **Advanced** (reword to area: "You are replacing 88 m² of lawn") |
| 13 | Habitat: photo galleries, "Species doing the work / supported" (`:931-964, 1693-1780`) | none directly (P13: beauty) | Fauna gallery is unordered: "A Leafcutter Bee" first (R23) | **Advanced** |
| 14 | Habitat: monospace breakdown (`:966-976, 1580-1673`) | none for a novice | R12, R16, F184 | **Advanced** |
| 15 | Habitat: "How sure are we?" establishment and fidelity bands (`:1095-1166`) | Will these grow here? (partly) | R5 ("Prairie, Purple, Wild") | **Advanced**, R5 fixed (OV-11). Item 3 answers the persona's version with the Edmonton list |
| 16 | Habitat: Relationship web and its 5 layer filters (`:1168-1256`) | none for a novice | R27 (filters do nothing until drawn), F214 (under the plants' canvas) | **Advanced** |
| 17 | Habitat: Pull-a-plant (`:984-1009, 1283-1363`) | none for a novice | none found | **Advanced** |
| 18 | Habitat: Feed a chickadee brood (`:1011-1024, 1367-1386`) | Would it feed baby birds? (a story) | A model; ranges stated | **Advanced** |
| 19 | Habitat: Tips for raising your score (`:1026-1040, 1873-2063`) | What should I add? (duplicates #5) | R39 (A–Z, Balsam Poplar and Douglas Fir for a front bed), "Add a overstory layer" | **Retire**. Nudges (#5) and the overview's actions cover it; supersedes PR-5 |
| 20 | Habitat: Light / shade mix (`:1042-1057, 1388-1407`) | Which parts are sunny? | Duplicates Sun & Shade's classification | **Retire** here; Sun & Shade shows it |
| 21 | Habitat: Tallamy line (`:1059-1067`) | none | R37 (90% of caterpillars, not of insects) | **Advanced**, reworded (OV-11) |
| 22 | Food: "Your plants feed 589 animals: …" (`food_page.py:227-238`) | Who does it feed? | R16, F190 | **Overview** (item 1, from the same function) |
| 23 | Food: One animal (1,459-entry list) (`:103-161, 337-462`) | none for a novice | R17 (raw source keys `anbc_alberta_native_bees,…`), R23 | **Advanced** |
| 24 | Food: Month by month (`:163-179, 636-687`) | Is something flowering all season? | none (grasses excluded, correctly) | Its gaps feed **Overview** item 2; the tree is **Advanced** |
| 25 | Over time: This month (`phenology_widget.py`, `phenology.py:38-42`) | What do I do now? | **OVF-5** ("prune Tall Goldenrod", "harvest Smooth Aster" in October) | **Advanced**, fixed (OV-8) |
| 26 | Over time: The year at a glance (`phenology_widget.py:155-`) | none | none | **Advanced** |
| 27 | Over time: Year slider and phased conversion plan (`planning_panel.py:807-918`, `conversion_plan.py`) | How will it change? | "pioneer" (a banned word); plants already placed told to go in at years 3–4 | **Advanced** (the PDF keeps the plan) |
| 28 | Over time: Hours of work (`planning_panel.py:142-340`) | How much work is it? | **OVF-2** (screen and PDF disagree; per week is /52) | **Overview** (item 6, calendar ranges); **Advanced** table fixed (OV-6) |
| 29 | Water (`planning_panel.py:393-659`) | How much do I water? | R4 (rows missing), R38 (seasonal "surplus"), hard-coded rainfall | **Advanced**, fixed (OV-7); **Overview** gives the weekly rule (item 6) |
| 30 | Site › Sun & Shade (`analysis_panel.py:142-615`) | Which parts of my yard are sunny? | Points to Site → Features, which goes behind Advanced (MD-5) | **Simple**, reduced (see [02](02-two-ways-to-use-it.md) §3.1) |
| 31 | Site › Wind (`analysis_panel.py:620-868`) | Where should a windbreak go? (not this persona's question) | none | **Advanced** |

**Count:**

- Six readouts move onto the overview: #1, #4 to #7, #22, and #24's gaps. #28
  and #29 also feed item 6.
- Three are retired: #8, #19 and #20.
- One stays in simple mode, reworded: #9 (Species).
- Everything else is advanced.

---

## 3. Defects found in this pass

These add to the first pass's R-list. Each is an S fix.

| ID | What happens | Where | Fix |
|---|---|---|---|
| **OVF-1** | The Report card, PDF, critic and API score a design without the pin's ecoregion; the Habitat page scores it with one. The generated bed reads **83** on the Report card and **78** on Habitat (layers 12/15 against 7.5/15 "vs Aspen Parkland grove") | `app.py:2247`, `pdf_export.py:135`, `design_critic.py:57`, `permadesign_api.py:297` against `analysis_panel.py:1531-1533` | OV-4 |
| **OVF-2** | The hours page's "Year 3+" uses the year-10 multiplier (0.3). The example reads 9 h on screen; the PDF's calendar says 18.5–38.4 h for years 2–4. The screen gives a single figure where the calendar gives a ±35% range, and "per week" divides by 52 | `planning_panel.py:189-192, 281-285` against `maintenance_calendar.py:57-58, 63` | OV-6 |
| **OVF-3** | Mulch is costed for every drawn shape, lawn, path, patio and water included, in five places. Mulch depth is 7.5 cm in one module and 5–8 cm in another | `app.py:2025-2029, 2208-2212`; `pdf_export.py:140-144, 194-198, 222-226`; `sourcing.py:189-190` vs `site_prep.py:78` | OV-3 |
| **OVF-4** | Wildlife totals differ between the Report card and Food: 263 against 271 on the generated bed. The first counts any `plant_fauna` relationship, the second counts food edges | `habitat_score.py:513-518` against `what_it_feeds.py:171-196` | OV-5 |
| **OVF-5** | "This month" tells the user in October to "prune Tall Goldenrod; harvest Smooth Aster". Its source, `planting_calendar`, holds 612 "harvest" rows, mostly flowering or seeding months of plants nobody eats. The care calendar says cut back in spring and leave the stems standing | `phenology.py:38-42`; `maintenance_calendar.py:97, 139, 142-150` | OV-8 |
| **OVF-6** | "Find a substitute" offers plants off the Edmonton list (Canada Goldenrod, Self-heal and Dotted Blazingstar for Showy Milkweed) in ecologists' wording, and cannot actually swap | `substitution.py:209, 255`; `design_review_flow.py:103-140` | OV-10 |

A smaller inconsistency, for the record: the lesson track counts **3** keystone
hosts in the example, from edges, while the score counts **2**, from tags. It
is left to the advanced pages; the overview counts neither.

---

## 4. The overview: rules

1. **One page, first in the Design tab**, titled *Overview*, in both modes. In
   simple mode it replaces the Report card (MD-1's registry). In advanced mode
   the Report card stays beside it as the detail.
2. **At most six items, always the same six, in the same order.** Order is
   predictable, and a status word marks what needs attention. Items are not
   re-sorted.
3. **Plain words, under 300 words in all.** Titles and buttons are counted.
   Measured: 279 words for the example, 292 for the generated bed. No Latin
   names, no score out of 100, no "species", no tag words.
4. **One action per item.** Each is a button that does something on the map or
   opens the one place that does. "More detail ▸" links to advanced pages are
   MD-4's and do not count as the action.
5. **One number, one source.** Each figure is computed by the same function as
   the advanced page and the PDF that show it. A test reads all three and
   asserts they are equal (OV-2). The app's recurring failure is two numbers for
   one thing, and this rule is aimed at it.
6. **Ranges and hedges, never false precision (P9).** "About", "once grown",
   "recorded as food for"; costs as ranges; hours as the calendar's range.
7. **A status word, not only a symbol.** *Looks good* (green), *Worth a look*
   (amber), *To plan for* (neutral). Each follows the visual floors in
   `target_size.py` and `tests/_visual.py`: 12 px text, 4.5:1 contrast,
   24 px targets.
8. **Empty states say what to do.** With no plants, the page reads: *"Add some
   plants, or use Plan my yard, to see how your yard is doing."* with the
   button [Plan my yard] (07's flow) or [Add plants]. With no boundary, item 4
   asks for one. With no pin, item 3 asks for one.

---

## 5. The six items

| # | Title | Measures | From (existing code) | Status rule | Action |
|---|---|---|---|---|---|
| 1 | **Food for wildlife** | Kinds of bee, butterfly and moth, and bird with a **food** record on the design's plants; one familiar named example; birds that eat seed or fruit | `what_it_feeds.animals_fed` (`:171-196`) | *Worth a look* when fewer than 3 birds eat its seed or fruit | *Add a berry shrub* → Placement › Plants, Type: Shrub, Role: Bird food (`plant_picker.set_facet`, `:238`). Otherwise *See who it feeds ▸* (MD-4 → Food) |
| 2 | **Flowers through the season** | First and last month in flower for pollinators; gap months Apr–Oct; months with only one kind | `what_it_feeds.month_by_month` (`:268-318`) excludes grasses, so this item does not depend on F184 | *Worth a look* with any gap | *Find a {Month} flower* → Placement › Plants, Blooms in: {month}, Edmonton native on. Otherwise *See what flowers when ▸* |
| 3 | **Right plants for here** | Kinds native around the pin's place; names those that are not | `native_here.place_at` / `native_around` (`:123-160`); outside a place, `native_in(province)` | *Worth a look* when any plant is off the list | *Swap {plant}* → OV-10's swap. Otherwise *See the plant list* (Planted) |
| 4 | **How full it will be** | Share of the planting area covered by mature canopy | New `yard_overview.cover()`; canopy from `get_plant` | *Worth a look* under 70% | *Ways to fill the gaps* → OV-9's dialog. Otherwise *Show the bare ground* |
| 5 | **How it will look from the street** | Cues to care present, of those that can be judged; the first missing one; the region's rule | `cues_to_care.assess`/`tally` (`:330-369`); region text (OV-13) | *Worth a look* with any cue missing | *Draw a mown strip* / *Draw the bed's edge* / *Draw a path* → Draw › Shape with that type chosen (`shape_tool.set_type`, `:192`; open the menu at `toolbar.py:210-214`) |
| 6 | **What it will take** | Plant cost; mulch volume (and its cost if bought); year 1 hours; hours once filled in; first-summer water a week | `sourcing.estimate_cost`; mulch from the planting area × 5–8 cm (`site_prep.py:78`); `maintenance_calendar` bands; OV-7's `water_budget` | Always *To plan for* | *Print the shopping list and care plan* → File → Export PDF (`app.py:2064`) |

### 5.1 How full it will be (the coverage measure, R12)

- **Planting area.**
  - If any bed-like shape is drawn (Garden Bed, Mulch Area, Restoration — Year 1,
    Restoration — Year 3, Established native), the planting area is their union.
  - Otherwise it is the property boundary less Lawn Area, Pathway, Patio / Deck,
    Water Feature and building footprints (`canopy_footprint` whose
    `shape_type` starts "Building").
  - Projected through `src/projection.metres_per_deg`; geometry in shapely,
    already a hard requirement (`requirements.txt`).
- **Covered.** The union of one disc per placed plant, diameter
  `mature_canopy_m` (as `get_plant` returns it), clipped to the planting area.
  Every value today is the 1.5 × spacing default, so the copy says *about*.
- **Words.**

  | Share covered | Words |
  |---|---|
  | 85% or more | almost all |
  | 72% to 84% | about three quarters |
  | 60% to 71% | about two thirds |
  | 45% to 59% | about half |
  | 28% to 44% | about a third |
  | 18% to 27% | about a quarter |
  | under 18% | less than a fifth |

  The m² follow in brackets.
- **Results.** Example: about a third (31 of 88 m²). Generated bed: about a
  third (16 of 54 m²). The first pass's 41 × 31 m yard: less than a fifth
  (217 of 1,269 m²), the design that scores 90.
- **What filling costs** (the dialog, OV-9). Low plants 60 cm apart: **149 more
  plants, $1,192–$2,384** for the example; **101 plants, $808–$1,616** for the
  generated bed (herb default $8–16 each; plug flats are cheaper, which was not
  checked). At 30 cm the example needs 638.
  - This is why the item offers mulching as an equal choice, consistent with
    the care calendar's years 2–4 ("Expect gaps… a hole that fills itself is the
    design working", `maintenance_calendar.py:98-99`).
  - It is also why outlining only the beds is the third choice: it answers the
    whole-lot outline, the commonest way a novice gets a low share.
- **The generator is the other half (R13).** The generator places 16, 19 and 28
  plants on the 54 m² bed at sparse, balanced and full density; full's stated
  target is 0.9 a m², about 49 (`llm_design.py:1731, 1770`). Its density fix
  belongs to [07](07-plan-my-yard.md). The overview only reports, so it stays
  true whichever way the generator goes.

**The headline score (owner's call, O1).** Docs reserve headline changes to the
owner (`.claude/skills/generate-design/SKILL.md`, "the stability rule").
Three options:

- **(a) No 0–100 number on the overview (recommended).** The score stays on the
  advanced Report card and Habitat pages. The computation does not change, so
  no headline change is needed.
- **(b) Keep a number but say what it measures.** *"Plant choice: 78/100. About
  30% of the bed covered once grown."* (the first pass's wording). A wording
  change only.
- **(c) A coverage term in the score: a headline change.** For scale, scaling
  the total by min(1, cover ÷ 70%) moves the example 63 → 32, the generated bed
  78 → 34 and the first-pass yard 90 → 22. It would also move every generated
  design and the critic's inputs (`design_critic.py:57`).

### 5.2 Wildlife, given F190 (R15)

Animals have no range in the catalogue: 1,144 animals, free-text `range_notes`
only, and all three ptarmigans flagged `ab_native=1`. So the item:

- says **"recorded as food for"**, never "supports" or "feeds";
- counts only bees, butterflies and moths, and birds, the groups a person
  recognises, from food edges only (OV-5 makes every page use the same count);
- names **one** example, chosen by:
  1. a bird that eats the design's seed or fruit, else a butterfly or moth with
     an English name, else a bumble bee (*Bombus*);
  2. among those, the one recorded on the most of the design's plants;
  3. never a generic name ("A Leafcutter Bee").

  Once the owner has reviewed a short list of animals familiar in Edmonton
  yards (O4), the example comes from that list. That list is a
  region-pack field, the same template for Calgary or Regina;
- ends with one fixed sentence: *"Records from across Alberta and Saskatchewan:
  what visits depends on what lives nearby."*

The full count and the per-animal pages stay on Food (advanced).

### 5.3 Bloom gaps, cost, hours, water, and the street: what is sensible to say

- **Bloom.**
  - Say the months in flower and name the gap months. "Pollinator flowers" is
    `what_it_feeds`' definition: grasses, sedges and rushes flower for the
    wind and are excluded (`forage_calendar.is_pollinator_forage`).
  - Do not print the score's bloom component: it counts grass bloom (F184,
    the owner's open call). The overview does not need that call settled.
  - A seven-cell strip, Apr to Oct, shows the count of kinds in flower each
    month.
- **Cost.**
  - Plants as a range from `sourcing.estimate_cost` (the same as the PDF buy
    list).
  - Mulch as **cubic metres first**, with "often free" before the bought
    price, because `site_prep.py:316-321` already tells people arborist chip is
    usually free.
  - Structures appear only when there are some.
- **Hours.**
  - Year 1 and "once it has filled in", both as the maintenance calendar's
    ±35% range: Year 1 band and Year 10+ band, `maintenance_calendar.py:57-63,
    296-308`.
  - "Mostly weeding", from the calendar's Year 1 tasks.
  - Never a single figure, never per week over 52 weeks.
- **Water.**
  - The calendar's rule, as a weekly quantity: *"a deep soak once a week in any
    week without a good rain (about 130 L)"*. That is the Water page's year-1
    demand ÷ 22 growing weeks.
  - Never a seasonal surplus (R38): a new planting dies in a two-week dry spell
    whatever the season's total.
  - 130 L is less than one 200 L rain barrel, a comparison worth making in the
    PDF.
- **Street.**
  - A tally of signs present, e.g. "2 of 5 signs of care are in place", which
    names them.
  - Then the single most useful missing cue, in the module's own order of
    importance: mown edge, edge, height, path, showy repeat.
  - The south-side assumption is said in the line it affects, as
    `cues_to_care.py:131-132` already does.
  - The region's rule comes from region data (OV-13). For Edmonton the
    proposed sentence is *"Edmonton's bylaw asks for grass and weeds under
    10 cm; a clear edge helps a native bed read as a planted garden."*
  - The 10 cm figure is from the City's page via a search summary. **The page
    could not be opened here, and whether a planted bed is exempt was not
    established**, so the owner approves the sentence or drops it (O5).
  - The app must not tell anyone a bed is legally exempt.

---

## 6. Wireframe, with the exact copy

The side panel is about 420 px wide. Each item is a card: a title line with
its status word on the right, one to three lines of text, and one button
aligned right.

### 6.1 Worked example (19 plants, 11 × 8 m, central Edmonton)

```
┌ Design ───────────────────────────────────────────────────────────────┐
│ [Overview] Planted                                                    │
├───────────────────────────────────────────────────────────────────────┤
│ How your yard is doing                                                │
│ Example — Front Yard Lawn Conversion · 19 plants, 14 kinds            │
│                                                                       │
│ Food for wildlife                                          Looks good │
│ Recorded as food for 188 kinds of bee, 180 of butterfly and moth and  │
│ 21 of bird, such as the Cedar Waxwing.                                │
│ Records from across Alberta and Saskatchewan: what visits depends on  │
│ what lives nearby.                                                    │
│                                                 [ See who it feeds ▸ ]│
│                                                                       │
│ Flowers through the season                               Worth a look │
│ In flower from March to September. Nothing in October, and only one   │
│ kind in April.                                                        │
│  Apr 1 │ May 5 │ Jun 9 │ Jul 7 │ Aug 7 │ Sep 2 │ Oct 0                 │
│                                            [ Find an October flower ] │
│                                                                       │
│ Right plants for here                                    Worth a look │
│ 12 of 14 kinds of plant are native around Edmonton. Showy Milkweed    │
│ and Canada Goldenrod are not.                                         │
│                                               [ Swap Showy Milkweed ] │
│                                                                       │
│ How full it will be                                      Worth a look │
│ Once grown, the plants will cover about a third of the area you       │
│ outlined (31 of 88 m²). Weeds move into bare ground: fill the gaps,   │
│ or keep them mulched while the plants spread.                         │
│                                             [ Ways to fill the gaps ] │
│                                                                       │
│ How it will look from the street                         Worth a look │
│ 2 of 5 signs of care are in place: a clear edge, tall plants at the   │
│ back. Most useful next: a mown strip about a metre wide along the     │
│ street (taken to be the south side). Edmonton's bylaw asks for grass  │
│ and weeds under 10 cm; a clear edge helps a native bed read as a      │
│ planted garden.                                                       │
│                                                [ Draw a mown strip ]  │
│                                                                       │
│ What it will take                                         To plan for │
│ Plants: $203–$406 for 19 plants. Mulch: 4–7 m³ of wood chips (often   │
│ free; $154–$528 bought).                                              │
│ First year: 36–75 hours of work, mostly weeding, and a deep soak once │
│ a week in any week without a good rain (about 130 L).                 │
│ Once it has filled in: 6–13 hours a year.                             │
│                             [ Print the shopping list and care plan ] │
└───────────────────────────────────────────────────────────────────────┘
```

When the first pass's R14 is fixed (Canada Goldenrod and Showy Milkweed
replaced), item 3 becomes *"All 14 kinds of plant are native around Edmonton."*
with *Looks good*. Item 2's September falls to one kind (Blanketflower) unless
the replacement flowers then. Canada Goldenrod is one of the two September
bloomers.

### 6.2 Generated 9 × 6 m front bed (19 plants, 53.5232, −113.5263, default goals, balanced)

```
│ Food for wildlife                                        Worth a look │
│ Recorded as food for 103 kinds of bee, 85 of butterfly and moth and   │
│ 3 of bird, such as the American Goldfinch.                            │
│ Few birds: only 1 kind eats its seeds or berries; the others visit    │
│ its flowers.                                                          │
│ Records from across Alberta and Saskatchewan: what visits depends on  │
│ what lives nearby.                                                    │
│                                                 [ Add a berry shrub ] │
│                                                                       │
│ Flowers through the season                                 Looks good │
│ In flower from April to October. Only one kind in April and in        │
│ October.                                                              │
│  Apr 1 │ May 3 │ Jun 6 │ Jul 4 │ Aug 5 │ Sep 5 │ Oct 1                 │
│                                          [ See what flowers when ▸ ]  │
│                                                                       │
│ Right plants for here                                    Worth a look │
│ 10 of 11 kinds of plant are native around Edmonton. Golden Currant    │
│ (Buffalo Currant) is not.                                             │
│                                              [ Swap Golden Currant ]  │
│                                                                       │
│ How full it will be                                      Worth a look │
│ Once grown, the plants will cover about a third of the area you       │
│ outlined (16 of 54 m²). Weeds move into bare ground: fill the gaps,   │
│ or keep them mulched while the plants spread.                         │
│                                             [ Ways to fill the gaps ] │
│                                                                       │
│ How it will look from the street                         Worth a look │
│ 3 of 5 signs of care are in place: a clear edge, tall plants at the   │
│ back, a repeated showy flower. Most useful next: a mown strip about a │
│ metre wide along the street (taken to be the south side). Edmonton's  │
│ bylaw asks for grass and weeds under 10 cm; a clear edge helps a      │
│ native bed read as a planted garden.                                  │
│                                                [ Draw a mown strip ]  │
│                                                                       │
│ What it will take                                         To plan for │
│ Plants: $234–$478 for 19 plants. Mulch: 3–4 m³ of wood chips (often   │
│ free; $94–$324 bought).                                               │
│ First year: 45–93 hours of work, mostly weeding, and a deep soak once │
│ a week in any week without a good rain (about 160 L).                 │
│ Once it has filled in: 7–14 hours a year.                             │
│                             [ Print the shopping list and care plan ] │
```

(The generated design's Wild Raspberry is a known spreader, but its
`spread_habit` is blank. Once PR-7's spread review fills it, item 3 gains a
second line: *"Wild Raspberry spreads by its roots: give it an edge it cannot
cross."*)

### 6.3 The two dialogs behind the actions

**Ways to fill the gaps** (example):

> **Fill the gaps**
> About 57 m² of the area you outlined will still be bare when the plants are
> grown.
>
> **Plant low plants 60 cm apart:** about 149 more plants (Wild Strawberry and
> Blue Grama Grass, from your own design), $1,192–$2,384 at nursery prices.
> They fill in over two or three summers.  **[Plant them]**
>
> **Keep the gaps mulched** and let your plants spread. Cheapest; expect to weed
> the gaps for two to four years.  **[Keep them mulched]**
>
> **Only planting part of it?** Outline your beds and only they will be counted.
> **[Outline my beds]**
>
> **[Cancel]**

**Swap Showy Milkweed:**

> **Showy Milkweed is not native around Edmonton.** These do a similar job here:
>
> **Wild Bergamot**: flowers July to August; garden centres sell it.  **[Swap]**
> **Boreal Yarrow**: flowers June to August; garden centres sell it.  **[Swap]**
> **Spreading Dogbane**: flowers June to August; native nurseries sell it.  **[Swap]**
>
> A swap replaces both Showy Milkweed plants where they stand. Undo puts them
> back.

---

## 7. What the advanced view keeps

Everything in §2 marked **Advanced**, unchanged in what it does, with these
corrections so that what it says agrees with the overview:

- **Report card:** the score the Habitat page shows (OV-4); "recorded as food
  for N kinds" from the same count as Food (OV-5); mulch only for beds (OV-3).
  "What your spend creates" goes.
- **Habitat:**
  - The score, breakdown, confidence bands with R5 fixed, the relationship web,
    pull-a-plant and the chickadee brood all stay.
  - The Tallamy line is corrected (R37): *"Based on Doug Tallamy's keystone-plant
    research: about 14% of native plant genera host about 90% of caterpillar
    species (Narango, Tallamy & Shropshire 2020)."*
  - Tips and Light / shade mix go.
  - "vs. lawn" is reworded to the area being converted.
- **Food:** unchanged, except the source keys go through `citations.py` (R17).
- **Over time:**
  - This month draws its tasks from the maintenance calendar, not the planting
    calendar's "harvest" and "pruning" (OV-8).
  - Year by year is unchanged.
  - Hours of work shows the calendar's four bands as ranges (OV-6).
- **Water:** every plant type has a row; rainfall comes from the pin's normals;
  the weekly rule replaces the seasonal surplus (OV-7).
- **Site › Wind:** unchanged.

---

## 8. Touch points

| File | Lines | Change |
|---|---|---|
| `src/yard_overview.py` | new | Qt-free core: `planting_area`, `cover`, `bed_area_m2`, the six item builders, `overview(project) -> list[Item]` |
| `src/yard_overview_page.py` | new | The page widget, six cards |
| `src/yard_overview_flow.py` | new | Action routing (`run_action(main, target)`), the two dialogs |
| `src/side_panel_layout.py` | 144-194 (`arrange`; Report card moved at 166) | Insert *Overview* at Design index 0, current at start; its own `LiveRefresh` |
| `src/live_refresh.py` | 33-87 | No change: a second `LiveRefresh` on `design._tabs` for the Overview page |
| `src/app.py` | 2025-2029, 2133-2256 (sync), 2208-2215, 2245-2248 | Use `yard_overview.bed_area_m2`; score through one helper; poke the overview |
| `src/pdf_export.py` | 133-146, 194-198, 222-226; summary on page 1 | Same helpers; page-1 summary from `overview()` (OV-12) |
| `src/habitat_score.py` | 442-449, 513-518 | `score_for_project` helper; food-only counts (or panels call `what_it_feeds`) |
| `src/design_critic.py` | 56-57 | Through the helper |
| `src/permadesign_api.py` | 297 | Through the helper; add `overview(project)` to the facade (frozen contract: update `test_architecture_guard.py`) |
| `src/on_this_design_panel.py` | 414-444, 470-494, 552-600, 252-278 | Wording, counts, retire framing |
| `src/analysis_panel.py` | 1026-1067, 1388-1407, 1600-1614, 1873-2063 | Retire Tips and Light / shade mix; Tallamy wording; counts |
| `src/planning_panel.py` | 43-63, 142-340, 460-659 | Hours from the calendar; water through `water_budget` |
| `src/water_budget.py` | new | Qt-free water constants and calculation, moved from `planning_panel.py` |
| `src/phenology.py` | 38-42, 150 | Task source |
| `src/reference_fidelity.py` | 74-90 | Whole-name match only (R5) |
| `src/substitution.py` | 209-260 | `place=` filter |
| `src/design_review_flow.py` | 103-140 | The swap dialog |
| `src/shape_tool.py` | 192 (`set_type`) | Used by item 5's action |
| `src/toolbar.py` | 210-214 | Open the Shape menu programmatically |
| `src/plant_picker.py` | 238 (`set_facet`) | Used by items 1 and 2's actions |

`analysis_panel.py` is at 2,073 lines against a 2,450 ceiling, and `app.py` at
2,415 against 2,600 (`tests/test_architecture_guard.py:73, 107`). `MainWindow`
has 126 methods against 140: wire the overview through lambdas and a flow
module, as MD-1 does.

---

## 9. Work items

| ID | Item | Effort | Depends on |
|---|---|---|---|
| **OV-1** | **`src/yard_overview.py`, the Qt-free core.** `Item(key, title, status, lines, action, target)`; `planting_area(project)` and `cover(project, get_plant=None)` as §5.1; `bed_area_m2(project)`; one builder per item exactly as §5, reading only `what_it_feeds`, `native_here`, `cues_to_care`, `sourcing`, `maintenance_calendar`, `water_budget` (OV-7) and `get_plant`; `overview(project, *, get_plant=None) -> list[Item]` in the fixed order. Strings in one table at the top, so a region pack can override the region sentences (OV-13). 350-line ceiling in `test_architecture_guard.py`. **Tests** (`tests/test_yard_overview.py`, temp-DB pattern): a fixture project (a 10 × 5 m boundary, four known plants at known offsets) gives literal copy for every item; on the worked example, item numbers equal their sources (food count = `len([a for a in animals_fed(ids) if a['food']])`; gaps = `month_by_month(ids)['gaps']`; hours = calendar Year 1 band; cost = `estimate_cost`); a Pathway shape inside the boundary reduces the planting area by its area; a Garden Bed makes the planting area the bed; no plants → one empty-state item; no output contains "species", "/100", an underscore or a Latin binomial; word count ≤ 300; 0.5 s or less for the example. *Accept:* `python3 -c "from src.yard_overview import overview; …"` on the example prints the six items of §6.1 with the same numbers | M | — (OV-7 for water; can inline the current constants first) |
| **OV-2** | **The Overview page.** `src/yard_overview_page.py` (six cards, title and status word, lines, one button; accessible name "title, status"; no horizontal scroll at 1366 px) and `src/yard_overview_flow.py` (`run_action` for targets: `page:planted`, `advanced:food` via MD-4, `plants:role=bird_food`, `plants:blooms_in=N`, `substitute:<id>`, `fill_gaps`, `shape:<type>`, `export:pdf`). Inserted as Design's first page in `side_panel_layout.arrange` (`:166`) and made current; refreshed by its own `LiveRefresh` on `design._tabs`; poked from `_sync_planning_panel` (`app.py:2133`). **Tests:** `test_app_smoke.py`: Overview is the Design tab's first page and current on a cold start; six cards with the example open; each button reaches its target (filters set, Shape menu with the right type, dialog opened, export called with a stub); visual floors and the accessibility walk pass; the page has no horizontal scroll bar with the example at 1366 × 768. **Consistency test:** with the example and the generated fixture open, the overview's plant cost equals the Report card's and the PDF summary's; its wildlife total equals Food's summary line; its year 1 hours equal the Hours of work page's Year 1 range and the PDF's. *Accept:* cold start, open the example, click Design: Overview shows the six cards of §6.1; every button does what its words say | M | OV-1; MD-1 to hide the Report card in simple mode (not required to ship) |
| **OV-3** | **One planting area, one bed area, one mulch depth (OVF-3).** Replace the five `custom_shape` sums (`app.py:2025-2029, 2208-2212`; `pdf_export.py:140-144, 194-198, 222-226`) with `yard_overview.bed_area_m2(project)`: bed-like shapes only (§5.1), else the boundary less lawn, path, patio, water and buildings. Make `sourcing.DEFAULT_MULCH_DEPTH_CM` a range read from `site_prep.MULCH_DEPTH_CM` (5–8 cm). **Tests:** a project with a 10 m² Pathway and a 20 m² Garden Bed costs mulch for 20 m² in `design_cost`, the site-prep sheet and the planting plan; a project with only a boundary mulches the boundary. *Accept:* drawing a Pathway no longer changes the Report card's mulch line | S | — |
| **OV-4** | **One habitat score per design (OVF-1).** `habitat_score.score_for_project(placed, structures, *, lat=None, lng=None)` resolves the ecoregion as `analysis_panel._site_ecoregion` does (`:1465-1484`) and calls `compute_habitat_score(..., ecoregion=)`. Use it at `app.py:2247`, `pdf_export.py:135`, `design_critic.py:57`, `permadesign_api.py:297` and `analysis_panel.py:1531`. **Tests:** on the generated 9 × 6 m fixture (saved from `generate_design_offline` with the arguments in §10), Report card value = Habitat value = PDF summary value (78 today on Habitat); `tests/test_habitat_score.py` gains the case. Review generator fixture changes caused by the critic now seeing the rebased layer component; do not regenerate blindly. *Accept:* no design shows two different scores. **Owner confirms O2 first** | S | O2 |
| **OV-5** | **One wildlife count, worded as records (OVF-4, R15, R16).** Report card, Habitat's "Wildlife supported" line and the overview all take the food-only count from `what_it_feeds.animals_fed`. `fauna_by_taxon` stays in `HabitatScore` for the API, labelled in the breakdown as "linked by any record (food or shelter)", so the stability rule is untouched. Wording: "recorded as food for N kinds" on the Report card (`on_this_design_panel.py:431, 483`) and on Planted's second line (`what_it_feeds.eaters_line`, `:369-386`: "food for 91 kinds: 36 bees, …"). **Tests:** on the example, the Report card total equals Food's (589) and the per-group counts match (188, 180, 21, 199, 1); no visible string says "wildlife species supported". *Accept:* the generated bed shows 271 on the Report card and Food | S | — |
| **OV-6** | **Hours from the care calendar (OVF-2).** Over time › Hours of work renders `build_maintenance_calendar` bands (Year 1, Years 2–4, Years 5–9, Year 10+) as ranges, per type for Year 1 only. "Per week" becomes "a week from May to September" (÷ 22). Delete `_Y1_MULT_*`/`_Y3_MULT_*` (`planning_panel.py:189-192`). Update `tests/test_live_pages.py:223-241`. **Tests:** the example's Year 1 reads "36–75 h", equal to the PDF's band; no "Year 3+" label remains. *Accept:* screen and PDF quote the same hours for the same design | S | — |
| **OV-7** | **Water: all rows, the pin's rainfall, the weekly rule (R4, R38).** Move `_PLANT_WATER_NEEDS_L_WEEK`, `_WATER_MULTIPLIER`, the multipliers and the arithmetic (`planning_panel.py:43-63, 460-526`) to Qt-free `src/water_budget.py` with `first_summer_weekly_litres(plants)`. Rows for every type present, in `member_colors.TYPE_COLORS` order (as Effort does since V3.08). Rainfall from `site_config['rainfall']['monthly_mm']` when present, labelled with its source, else the Edmonton default, labelled "Edmonton normal". Replace the "surplus/deficit" callouts with *"First summer: about 130 L a week in any week without a good rain (15–20 mm). From year 3: only in a drought."* Keep supply as information. **Tests:** rows sum to the total on the example (2,937 L) and the generated bed (3,514 L); weekly = total ÷ 22; no visible "surplus" string; a site_config with normals changes the rainfall line. *Accept:* the generated bed's table lists Wildflowers 12 | S–M | — |
| **OV-8** | **"This month" stops contradicting the care calendar (OVF-5).** In `phenology.py:38-42`, drop "pruning" and keep "harvest" only for plants with `edible_parts`. Add, when the design has plants, the maintenance calendar's first-year line for the month (`maintenance_calendar._FIRST_YEAR_MONTHS`), headed "If you planted this year". Same filter for the status bar (`app.py:1073`, R26) or retire it there. **Tests:** generated bed in October: no "prune", no "harvest Smooth Aster"; November shows "LEAVE THE STEMS STANDING"; an edible plant still shows its harvest. *Accept:* nothing in the app tells a user to cut back natives in the fall | S | — |
| **OV-9** | **"Ways to fill the gaps."** `yard_overview.bare_ground(project)`: the planting area less the mature discs, slivers under 0.5 m² dropped. The dialog of §6.3:<br>• **Plant them:** filler = the design's own ground-layer species (grass, sedge, groundcover, or a wildflower ≤ 0.6 m), most numerous first; if none, the first two Edmonton grasses or sedges by PR-1. 60 cm grid by `area_fill.fill_points`, points inside the covered union removed. Count and cost previewed before placing; placed as one undoable step (`area_fill_controller.py:22`, `@undoable`).<br>• **Keep them mulched:** closes.<br>• **Outline my beds:** Draw › Shape with Garden Bed.<br>**Tests:** the example previews 149 plants and "$1,192–$2,384"; after Plant them, cover ≥ 90%; one Undo removes every added plant; the generated bed previews 101. *Accept:* item 4 turns *Looks good* after Plant them | M | OV-1, OV-3; PR-1 optional |
| **OV-10** | **Swap for a local native (OVF-6).** `substitution.substitutes(plant_id, place=…)` filters by `native_here.native_around` when the pin is in a place (else by the province). A plain dialog (§6.3): name, bloom months, where it is sold (`sourcing.describe`). *Swap* replaces every placed instance at the same coordinates through `ProjectStore.remove_plants_batch` + `add_plant`, one undo step. Keep the existing ecological detail behind "Why these? ▸" in advanced mode. **Tests:** example: swapping Showy Milkweed for Wild Bergamot leaves 2 Wild Bergamot at the milkweeds' coordinates and none of Showy Milkweed; Undo restores; no candidate is off the Edmonton list with an Edmonton pin. *Accept:* the overview's item 3 turns *Looks good* after two swaps | M | — (OV-2 for the button) |
| **OV-11** | **Habitat page tidy for advanced.**<br>• R5: `reference_fidelity._tokens` keeps the whole name only, plus the genus for scientific names, never a common name's first word.<br>• R37 wording (§7).<br>• Retire Tips (`analysis_panel.py:1026-1040, 1873-2063`) and Light / shade mix (`:1042-1057, 1388-1407`).<br>• Reword "vs. lawn".<br>• Fix "Add a overstory layer" if any tip text survives.<br>This supersedes PR-5: nudges, not tips, carry plant examples, ranked by PR-1. **Tests:** the example's matched species do not include "prairie", "purple" or "wild"; `test_architecture_guard`'s builder test still passes. *Accept:* the Habitat page has no Tips box and no A–Z plant list | S | — |
| **OV-12** | **The PDF's first-page summary is the overview** (the same six items' text, black on white, after R1). It replaces `_draw_summary`'s score block. The score stays in the PDF only if the owner keeps it (O1). **Tests:** `pdftotext` of an exported example contains the six titles and the same plant cost as the screen. *Accept:* screen and print say the same things | S | OV-1, R1 |
| **OV-13** | **Regional sentences as data.** The street rule, the place's short name and the price note ("Alberta nursery prices") come from the region pack ([08-edmonton-edition.md](08-edmonton-edition.md)) under keys `overview.street_rule`, `overview.street_rule_source`, `overview.price_note`. Edmonton's values are §5.3's, pending O5; a place with no rule omits the sentence. **Tests:** a fake region with no rule yields item 5 without a bylaw sentence; Edmonton's carries its source URL in the tooltip. *Accept:* Calgary or Regina needs only data to change these sentences | S (plus owner reading the bylaw) | ED items in [08](08-edmonton-edition.md); O5 |
| **OV-14** | *(Optional, later)* **Sun fit in item 3** when Sun & Shade's zones are classified: count placed plants whose `sun_requirements` exclude `shade_zones.tag_at(...)` at their spot; one sentence, *"2 plants are in spots shadier than they like."* **Tests:** a fixture with a full-shade tag under a full-sun plant. *Accept:* nothing shows when no zones are classified | S | OV-1 |

Suggested order:

1. **OV-3, OV-4, OV-5, OV-6, OV-7, OV-8** first, because they make the
   existing pages agree.
2. Then **OV-1, OV-2**.
3. Then **OV-10, OV-9, OV-12, OV-13**, and **OV-11** alongside MD-1.

---

## 10. How this was measured (to re-run)

- **Worked example:** `src.onboarding.build_example_project()` (19 plants, no
  structures).
- **Generated bed:** `src.llm_design.generate_design_offline(...)` with:
  - `site_config={latitude: 53.5232, longitude: -113.5263, hardiness_zone: 3,
    soil_ph: 6.5, soil_texture: "loam"}`;
  - `boundary` = a 9 × 6 m rectangle centred there;
  - `goals=FIRST_RUN_GOALS`, `density="balanced"`.

  Sparse, balanced and full gave 16, 19 and 28 plants.
- **Scores:** `compute_habitat_score` with and without `ecoregion=lookup_ecoregion(lat, lng)`.
- **Coverage:** shapely discs of `mature_canopy_m`, clipped to the boundary.
- **Page texts and word counts:** the real `MainWindow` under Xvfb at 1366 × 768,
  offline, each Design page shown with `keyboard_help.show_panel` and its labels,
  text boxes and lists read.
- **Prototype:** a working prototype of OV-1 produced the copy in §6, and runs
  in 0.5 s. The prototype and measuring scripts are in the review session's
  scratch space (`wf/overview/`), not in the repository; OV-1's tests re-create every number from the app's own code.

---

## 11. Decisions for the owner

- **O1.** Should the novice overview show the 0–100 score?
  - (a) **No number** (recommended). Plain items only; the score stays in Advanced.
  - (b) "Plant choice: N/100" beside the coverage line.
  - (c) A coverage term in the score itself: a headline change, which moves
    every design (example 63 → about 32).
- **O2.** Which score should the Report card, PDF and critic show? The one
  rebased on the reference community, which Habitat has shown since V2.65
  (recommended), or the universal-stack one? Today they differ (83 against 78
  on the generated bed).
- **O3.** The coverage target: is 70% of the planting area, once grown, "well
  filled" (recommended)? And should the overview present mulching the gaps as
  an equal choice to planting them (recommended, since filling the example's
  gaps costs $1,192–$2,384)?
- **O4.** Wildlife wording: group counts with "recorded as food for…" plus the
  fixed caveat (recommended), or no counts, only named animals? Also: review a
  short list of animals familiar in Edmonton yards (about 30) for the named
  examples, a data job.
- **O5.** The bylaw sentence: read Bylaw 14600 (the City's page could not be
  opened here) and approve §5.3's sentence, change it, or drop it.
- **O6.** Accept the care calendar's four bands as the only hours anywhere
  (recommended), retiring "Year 3+".
- **O7.** The order of the six items. Recommended: wildlife, flowers, right
  plants, how full, from the street, what it will take. The alternative leads
  with cost and work.

---

## 12. What could not be checked

- **The bylaw.** `edmonton.ca` was unreachable from this environment. The 10 cm
  rule is from a search summary; whether a planted bed is exempt is unknown.
- **The coverage figures.** They rest on `mature_canopy_m`, which is 1.5 ×
  spacing for all 424 plants (none explicit). Shrub canopies in particular are
  unverified.
- **Fill-the-gaps costs.** They use the app's herb default of $8–16 a plant;
  native plug flats are usually cheaper, and no nursery was checked. "Fill in
  over two or three summers" is a horticultural judgement, not data.
- **Water and hours.** The per-plant water figures and the hours model are the
  app's own unsourced constants; this section reuses them rather than
  validating them.
- **Named animals.** Whether the named examples (Cedar Waxwing, Silvery Blue,
  Brown-belted Bumble Bee, American Goldfinch) are common in central Edmonton
  yards is F190's question, unanswered.
- **Bloom months.** The example's March bloom (Prairie Crocus) comes from the
  catalogue's `bloom_period`. An Edmonton gardener would expect April; not
  checked.
- **The page's fit.** Whether six cards fit the side panel without scrolling at
  1366 × 768 was estimated (about 570 px of a roughly 620 px panel), not built
  and measured.
- **Online and real machines.** The GUI capture ran offline with no map tiles,
  on Linux with the Arial-metric font only; Windows, macOS and high-DPI screens
  were not seen.
- **Real people.** No homeowner has seen this page; R40's three-person test
  should include it.
