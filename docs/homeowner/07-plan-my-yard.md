# 7 · Plan My Yard: the generator, for someone who has never planted a bed

*Part of the [homeowner-path plan](README.md). Work items **PY-1 to PY-11**;
defects found here **PYF-1 to PYF-7**; owner decisions **Y1 to Y6**
([12-decisions.md](12-decisions.md)). The ranking the generator should use is
PR-1 and PR-6 ([05-plants-that-lead.md](05-plants-that-lead.md)); the coverage
measure is OV-1 ([06-yard-overview.md](06-yard-overview.md) §5.1); the AI
leaving the app is RM-3 ([03-what-goes.md](03-what-goes.md)).*

The persona has a yard and a wish, not a plant list. *Generate Design* is the
one place the app can turn that wish into a first planting. It has to work
first time, on whatever the person drew, and be easy to try again.

## In one paragraph

The generator is good at choosing plants and better than it looks at placing
them, but it ignores what a beginner draws. **A Garden Bed is ignored** (1 of 42
plants lands in it), **a Lawn Area gets 32 of the 42 plants**, and **a 1 m
path wipes out half the yard**, because drawn shapes are kept out as one circle
around their centre. Its density setting changes the count but **not the
cover** (31%, 32%, 34% at sparse, balanced and full), and it places about half
its own target. Running it twice stacks a second identical design on the first
(R2). The proposal renames it **Plan My Yard**, asks four questions a beginner
can answer (where, front or back, how full, any must-haves), plants where the
person drew beds, fills to a cover target the overview reports in the same
words, replaces the last plan rather than stacking, offers **Try another**, and
explains itself in a short *About this plan* instead of a box of developer
notes.

---

## 1. What a beginner meets today

`File › Generate Design…` and the getting-started strip's **✨ Generate Design**
open `src/generate_design_dialog.py` (253 lines). From the top:

1. An intro about "a local AI" that "picks fitting native plants and
   communities" (`:46-50`).
2. Ten goal checkboxes (`src/design_goals.py`), four of them pre-ticked on a
   first run (`FIRST_RUN_GOALS`, `src/onboarding.py:45`); two are hidden since
   V3.07 because no data backs them.
3. A wildlife picker over 1,144 animals (`:78-108`).
4. *Extra details (optional)*, a free-text brief (`:112-118`) that the offline
   path ignores (R3).
5. Budget, *Planting density* (sparse, balanced, full), *Match to site
   conditions & terrain*, and *Build without AI (offline)* (`:121-170`).

The controller (`src/controllers/generation.py:37-79`) saves the goals into the
design, hands the generator the design's features, and runs it on a thread.
When the AI is not there (always, for a beginner) the worker falls back to the
offline generator and adds a note quoting the raw error (`src/generate_worker.py:67-83`).
`_render` (`:171-232`) **adds** the result to the map as one undo step and shows
every generator warning in a modal *Design notes* box.

## 2. What it does with what the person draws (measured)

The script is [`prototypes/plan_my_yard_probe.py`](prototypes/plan_my_yard_probe.py);
the figures below are its output at V3.17. A 15 × 10 m yard in south Edmonton,
the first-run goals, the offline generator.

**Density alone** (nothing drawn but the outline, 150 m²):

| Density | Placed | Its own target (`_DENSITY_FRACTION` × 1 plant a m², `llm_design.py:1731, 1770`) | Covered once grown |
|---|---|---|---|
| sparse | 23 | 45 | 31% |
| balanced | 42 | 90 | 32% |
| full | 59 | 135 | 34% |

**One shape drawn**, balanced (42 plants when nothing is drawn):

| Shape drawn | Placed | On the shape | Covered | What a beginner meant |
|---|---|---|---|---|
| Garden Bed, 6 × 3 m (12% of the yard) | 42 | **1** | 32% | "Plant here" |
| Lawn Area, the south 60% | 42 | **32** | 32% | "Keep this as lawn" |
| Lawn — to convert, the south 60% | **6** | 6 | 30% | "Turn this into garden" |
| Patio / Deck, the south 60% | **5** | 0 | 14% | "Not here" |
| Pathway, 1 × 10 m (7% of the yard) | **18** | 0 | 26% | "Not on the path" |

The path is kept out by a circle of radius 5.0 m (79 m², half the yard) and the
patio by one of 8.1 m (205 m², more than the whole yard).

**The notes a balanced plan shows today:**

> Skipped 4 plant communities that did not fit inside the boundary or clear an
> existing feature.
> Added Basket Willow — covers the April bloom gap for pollinators
> Won't-take-over excludes plants known to spread aggressively; unassessed
> plants are still shown.
> Budget-friendly uses estimated Alberta retail prices (ranges, not quotes) and
> excludes only hard-to-source plants.

## 3. Defects

| ID | Severity | What happens | Cause | Fixed by |
|---|---|---|---|---|
| **PYF-1** | High | **A drawn Garden Bed is ignored.** The plan is identical with or without it; 1 of 42 plants lands in a bed covering 12% of the yard | Only the four conversion-zone labels are fill targets (`src/exclusion.py:55-74`); Garden Bed and Mulch Area are neither filled nor avoided | PY-2 |
| **PYF-2** | High | **A Lawn Area is planted.** 32 of 42 plants (76%) land on a lawn shape covering 60% of the yard | `_avoid_shape_types` (`src/exclusion.py:48-52`) leaves "lawn" plantable on purpose ("Garden-bed / lawn / mulch shapes stay plantable"); `cues_to_care` and the overview treat it as lawn | PY-2 |
| **PYF-3** | High | **A path, a patio or a building blots out far more than itself.** A 1 m path takes half a 15 × 10 m yard (42 → 18 plants); a patio more than all of it (42 → 5) | Drawn shapes and footprints are kept out as one circle around the centroid, radius to the farthest vertex (`src/exclusion.py:77-132`) | PY-3 |
| **PYF-4** | High | **Density changes the count, not the cover**, and reaches about half its own target. Restricting the ground (a conversion zone) collapses the count to 6 (R13) | The target is plants a m², checked against free anchor cells; drifts pile onto the same anchors rather than spreading into open ground | PY-4 |
| **PYF-5** | High | **Running it twice stacks a second identical design** on the first (R2): the generator is deterministic, so every plant lands on its twin | `_render` adds and never replaces | PY-5 |
| **PYF-6** | Medium | The brief is ignored without the AI, and the fallback note quotes raw error text (R3) | `generate_worker.py:67-83` | RM-3, PY-1 |
| **PYF-7** | Medium | **The notes are written for a developer**, arrive in a modal box after the plan is on the map, and two of the four are caveats about choices that belonged beside the choice | `_render` joins `generation_warnings` (`generation.py:228-232`) | PY-8 |

## 4. The proposal

### 4.1 Name and place

**Plan My Yard…** everywhere: the File menu (02 §3.2), the getting-started
strip's button, the overview's actions, the status line. "Generate" describes the
machine; "plan my yard" describes what the person wants. The advanced dialog
keeps the name and adds its extra controls (§4.7).

### 4.2 Before the dialog: what it needs

The dialog opens whatever the state, and says what is missing in its first line,
with buttons that do it (PY-9):

| State | First line | Buttons |
|---|---|---|
| No pin | *Find your yard first, so the plan can use your soil and sun.* | **Find my yard** (focuses the address search) |
| A pin, nothing outlined | *Outline where you want to plant: your whole yard, or just the beds.* | **Outline my yard** (arms Boundary) · **Draw a bed** (arms Shape with Garden Bed chosen, `shape_tool.set_type`) |
| Outside the area | ED-8's message ([08](08-edmonton-edition.md) §4.5) | — |
| Ready | the questions below | **Plan my yard** |

### 4.3 The four questions

Wireframe, with the exact copy:

```
Plan my yard
────────────────────────────────────────────────────────────────
Where should the plants go?
  (•) In the beds I drew  (2 beds, 31 m²)            ← only when beds exist
  ( ) Anywhere in my yard outline  (150 m², less paths and patio)

Is this a front yard or a back yard?
  (•) Front yard: seen from the street. A neat edge, shorter
      plants along the street.        The street is to the [South ▾]
  ( ) Back yard: room for a wilder look, a brush pile, a bee hotel.

How full?
  (•) Fill it now: about 95 plants, about $760–$1,520
  ( ) Over two or three summers: about 50 plants now, mulch between

Anything it must do?
  [x] Plants that stay where you put them
  [x] Easy to buy around Edmonton
  [ ] Leave out plants known to be poisonous to pets
  [ ] Leave out plants known to be poisonous to people
  [ ] Food for people: berries and fruit

  Budget (optional): [        ]

                                       [Cancel]  [Plan my yard]
```

The counts, prices and areas in the wireframe and in §4.4–§4.5 are
illustrative. PY-4 decides how many plants a 70% cover takes, and today's
generator reaches only 34% with 59 plants on this yard, so the real "fill it
now" figure may be well above 95.

Rules:

- **Where** (PY-2). The first choice is shown, and chosen, when the design has
  any Garden Bed, Mulch Area or conversion-zone shape; its figure is their area.
  The second is the planting area of 06 §5.1: the outline less Lawn Area,
  Pathway, Patio / Deck, Water Feature and buildings. One function,
  `yard_overview.planting_area`, answers both, so the plan plants exactly where
  the overview measures.
- **Front or back** (PY-7, decision Y2). A beginner can answer it; "styles"
  with names like *Prairie* or *Woodland edge* ask for a vocabulary they do not
  have yet. *Front* turns on the cues to care (`src/cues_to_care.py`): along
  the street side, a band 1 m deep gets only plants 60 cm or shorter at
  maturity that stay put; drifts repeat; no brush pile or snag. *Back* allows the
  meadow mix and adds at most two wildlife structures (Y5). The street side is
  pre-filled from `src/frontage.py`, which measures it from OpenStreetMap roads
  when the design has them (V2.58) and otherwise assumes south, as
  `cues_to_care.FRONTAGE_NOTE` says; the person's correction is remembered with
  the design and wins over both.
- **How full** (PY-4, decision Y3). Two choices, defined by **cover once grown**
  as the overview measures it: *Fill it now* aims for 70% (O3's "well filled");
  *Over two or three summers* aims for 40% and the plan's notes say where to
  mulch. The counts and cost in the labels are estimated before the plan is made
  (`plant_count_for(area, cover)` from the ranked pool's average canopy, and
  `sourcing` for the cost range), so they say *about*.
- **Must-haves** (decision Y6). The words say what the data supports. 376 of
  424 plants have no toxicity record (R10), so the box leaves out plants *known*
  to be poisonous, and says so; it does not promise safety. *Plants that stay
  where you put them* and *Easy to buy* are on by default (the first-run goals).
  *Native around Edmonton* is not a box: in the simple app it is the default
  (ED-10).
- **No AI and no brief** (RM-3, decision Y1). Nothing in the dialog needs a
  network.

### 4.4 Replace, add, try another

- **Replace by default** (PY-5, decision Y4). Each run stamps its plants and
  structures with a `plan_run` id. When the design already holds a plan, the
  button reads **Replace my plan**, and a line above it says *Your last plan
  (42 plants) will be replaced. Plants you placed yourself stay.* A link, *Add
  to it instead*, keeps both. Replacing is one undo step: Ctrl+Z brings the old
  plan back.
- **Try another** (PY-6). After a plan lands, the bar over the map (the
  `landing_check` bar, V3.05) reads:

  > **Your plan: 95 plants of 14 kinds.** [Try another] [About this plan] [Undo]

  *Try another* re-runs with the same answers and the next `variant`, replacing
  the plan just made. `variant` seeds the layout and rotates choices among
  plants of the same band and layer (PR-1), so a variant is a different plan of
  the same quality, not a worse one. The generator stays deterministic: the same
  answers and the same variant give the same plan, which the critic and the
  tests rely on (the skill's *Determinism is load-bearing*). A plan takes about
  five seconds on the test machine; the bar shows *Planning…* meanwhile.

### 4.5 About this plan (PYF-7)

A short, non-modal panel opened from the bar, in the overview's voice
([06](06-yard-overview.md) §4). For a plan like the one above it would read
(illustrative figures):

> **About this plan**
> 95 plants of 14 kinds in your two beds. Shrubs at the back, where they will
> not shade the rest; shorter plants along the street.
> Flowers from April to September. Food for 120 kinds of animals, 40 of them
> caterpillars.
> About $760–$1,520 at Edmonton native nurseries.
>
> **What I could not do**
> - Your north bed is mostly shaded, so it has fewer kinds of plants.
> - No vine: nothing in the plan is tall enough to climb yet.

Rules: at most six lines and two *could not* lines; no "community", "boundary",
"species" or "existing feature"; the caveats about filters move into the dialog
beside their box; a note that only matters to the advanced user (community
counts skipped, the critic's repairs) goes to the advanced Design notes, which
stay. Strings live in one table in a new Qt-free `src/plan_notes.py`, which reads
`generation_warnings` codes rather than their English (PY-8 gives each warning
a code).

### 4.6 What the generator must do differently

1. **Plant where the person drew** (PY-2). The fill target is
   `yard_overview.planting_area(project)`: beds when there are beds, else the
   outline less what is not for planting. Lawn Area is not planted.
2. **Keep out exactly what is drawn** (PY-3). Drawn shapes and building
   footprints are tested as polygons (shapely, already required); circles stay
   for points (existing trees, structures), where they are right.
3. **Fill to cover, not to a count** (PY-4). Place in layer order as now; then,
   while `cover(project)` is under the target and the pool has a fitting plant,
   add the best-ranked plant at the free spot that adds the most uncovered
   ground (`open_ground.OpenGround`, which already finds free ground by spacing,
   F183). Stop at the target, at `_MAX_GENERATED_PLANTS`, or when nothing fits,
   and say which in the notes. The habitat score does not change (a headline
   change is the owner's, O1); only how many plants go in.
4. **Rank by PR-1** (PR-6, owned by [05](05-plants-that-lead.md)): the offline
   pool, the critic's repairs and the top-ups choose by `plant_priority`, so a
   plan leads with the plants the plant list leads with.
5. **Front yard cues** (PY-7), as §4.3.

### 4.7 What the advanced dialog adds

With Advanced on (MD-1), the same dialog shows below the four questions: the
wildlife picker, the three densities as cover targets (25%, 45%, 70%), *Match to
site conditions & terrain*, every goal in `design_goals.GOALS` (including
province-wide natives), and the full Design notes after a run. The AI stays
out of the app entirely (Y1); the command line keeps it.

---

## 5. Work items

Effort: S = up to a day, M = two to four days, L = a week or more.

| ID | Item | Effort | Depends on |
|---|---|---|---|
| **PY-1** | **The Plan My Yard dialog.** Rebuild `generate_design_dialog.py` as §4.2-§4.3 (simple) and §4.7 (advanced); rename the File action, the strip's button and the status lines. **Tests** (`tests/test_generate_dialog.py`, extended): the four states of §4.2 show their line and buttons; the *Where* choice appears only with beds; with Advanced off there is no wildlife picker, density triple, brief or AI text; the must-have labels match §4.3 word for word. *Accept:* a first-run user with a pin and an outline sees four questions and one button | M | RM-3, MD-1 |
| **PY-2** | **One planting area** (PYF-1, PYF-2). The generator's fill target becomes `yard_overview.planting_area` (OV-1); Lawn Area joins the avoided shapes; Garden Bed and Mulch Area become fill targets. **Tests:** the probe's Garden Bed case puts at least 90% of plants in the bed; the Lawn Area case puts none on the lawn; `tests/test_exclusion.py` and `tests/test_yard_overview.py` share one fixture. *Accept:* `plan_my_yard_probe.py` shows those two rows fixed | M | OV-1 |
| **PY-3** | **Keep-out by polygon** (PYF-3). `exclusion.is_clear` tests polygons for drawn shapes and footprints; circles stay for points. Keep the perf contract (no shapely in the inner scoring loop: precompute a prepared geometry once a pass). **Tests:** the 1 × 10 m path case places within 10% of the no-path count and none on the path; the patio case places plants on the 40% of the yard left. *Accept:* the probe's path and patio rows | S | — |
| **PY-4** | **Fill to cover** (PYF-4, R13). §4.6 item 3, with the targets of §4.3 and §4.7, stopping reasons reported. **Tests:** on the probe yard, *Fill it now* reaches ≥ 65% cover and *Over two or three summers* 35–45%; the conversion-zone case places at least as many plants a m² as the open yard; `_MAX_GENERATED_PLANTS` still holds. The headline score's tests are untouched. *Accept:* the probe's density table shows cover rising with the choice | M | OV-1, PY-2, PY-3 |
| **PY-5** | **Replace, not stack** (PYF-5, R2). A `plan_run` id on every plan feature (carried by `project_store`); `_render` removes the last run's features when replacing, inside the same checkpoint; *Add to it instead* skips that. **Tests:** two runs leave one plan; undo after a replace restores the first plan exactly; hand-placed plants survive both. *Accept:* plan twice, count once | S | — |
| **PY-6** | **Try another.** `variant: int = 0` on `generate_design_offline` and the facade (the frozen MCP and CLI surfaces get it as an optional argument, which the contract test allows; check `agent-api` first); the bar's three actions. **Tests:** variant 0 twice gives identical plans; variants 0 and 1 differ in at least a third of positions and share the cover target within 5 points. *Accept:* *Try another* three times gives three different plans, each one undo step | M | PY-5, PR-6 |
| **PY-7** | **Front or back yard.** The `setting` and `street_side` answers on `generate_design_offline` (remembered in `site_config`; `frontage.frontage_for_project` reads the remembered side first, so the overview's street item agrees); the street band rule and the structure rule of §4.3. **Tests:** in a front-yard plan no plant within 1 m of the street side is taller than 60 cm at maturity or spreads; a back-yard plan may add a brush pile; `cues_to_care.tally` scores the front plan at least one cue higher. *Accept:* a front-yard plan reads as a garden from the street side | M | PY-2, decision Y2 |
| **PY-8** | **About this plan** (PYF-7). Warning codes in `generation_warnings` (keeping the English for the advanced notes); `src/plan_notes.py` (Qt-free) turns codes into §4.5's lines; the panel; filter caveats moved into the dialog. **Tests:** the example plan's summary has no banned word (§4.5) and at most eight lines; every warning code has simple-mode words or is marked advanced-only. *Accept:* no modal box after a plan in simple mode | M | PY-1 |
| **PY-9** | **The dialog's preconditions** (§4.2), wired to the existing tools (`shape_tool.set_type`, the address search, ED-8). **Tests:** each state's buttons arm the right tool. | S | PY-1 |
| **PY-10** | **The getting-started strip** reworded: *Find your yard · Outline where to plant · Plan it, or pick plants yourself*, with **Plan my yard** as its button (`src/onboarding.py:51-90`, `src/first_step_bar.py`). The boundary step is done by a boundary **or** a bed. *Accept:* drawing only a bed completes step 2 | S | PY-1 |
| **PY-11** | **Keep the probe honest.** Move the probe into `scripts/probe_plan_my_yard.py` with an `--assert` mode that fails on the PY-2 to PY-4 thresholds, and run that mode from a test module that skips without shapely. *Accept:* the test fails on today's code and passes after PY-4 | S | — |

## 6. Decisions for the owner

- **Y1.** The local AI: out of the app, kept in the command line and MCP
  (recommended), or kept as an advanced option. Nobody in the persona can run
  it.
- **Y2.** How the plan's look is chosen: **front or back yard** (recommended),
  named styles (*Tidy garden*, *Meadow*, *Woodland edge*), or no choice.
- **Y3.** *How full*: two choices by cover (70% now, 40% over two or three
  summers; recommended, matching O3), or keep the three densities.
- **Y4.** A second plan replaces the first by default (recommended), asks every
  time, or adds.
- **Y5.** May a back-yard plan add structures (a brush pile, a bee hotel), at
  most two (recommended), or never unless asked?
- **Y6.** The poison boxes: offer them as *leave out plants known to be
  poisonous* (recommended), or hide them until the top 60 plants have toxicity
  records (a data job; [05](05-plants-that-lead.md) §9).

## 7. What could not be checked

- **How it feels.** The dialog and the bar were not built; the wireframe is
  copy and layout only.
- **The cost estimates** use the app's own price defaults ($8–16 a herbaceous
  plant), not nursery prices; plug flats would be cheaper.
- **The 60 cm street band** is a horticultural judgement for a front yard, not
  a bylaw figure; Edmonton's long-grass rule is decision O5/E6.
- **Five seconds a plan** was measured in this container, without a display;
  a slow laptop may take longer, which is why *Try another* shows progress.
- **The online AI path** was not run (no model available); it leaves the app
  under Y1 either way.
