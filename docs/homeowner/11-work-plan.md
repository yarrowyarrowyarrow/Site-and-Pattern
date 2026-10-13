# 11 · The work plan: what to build, in what order

*Part of the [homeowner-path plan](README.md). It schedules every work item in
parts 1–10, adds the first review's remaining fixes as **QF-1 to QF-19**, maps
the first review's **R1 to R40** to the item that fixes each, and reserves
feature IDs **F233 to F249** in the ledger. Decisions are in
[12-decisions.md](12-decisions.md); the scale bar's is **K1**, the only one this
part adds.*

> **The owner answered every decision on 13 October 2026** (12 §0). The
> increments below already include what changed: the Learn door stays (ST-10
> cancelled), the Plant Directory window goes (RM-10), the score counts the
> Edmonton list (ED-17), front and back yards are measured (PY-12), and there is
> no rules block, website work or donate link for now (ED-14, ED-12, FN-10). Every
> *Decisions* line below is answered; read the answers in 12 before starting.

## In one paragraph

Fifteen increments, one release branch each, from **V3.18** to **V3.32**. Eleven
are *must* (the app is not finished without them) and four are *should* (better
with them, finished without them); the cut line is there so the owner can stop
early and still stop somewhere coherent. The order puts the **trust fixes
first** (things that are wrong today, a printout you cannot read, a plan that
stacks on itself, a door that opens the wrong window), then the **simple app**
(the switch, the removals, the front door), then the **Edmonton region**, then
the three new things the homeowner sees (**plants that lead**, **how your yard
is doing**, **Plan My Yard**), then the words, then **finishing** and the
**usability sessions** that decide whether it worked. By the plan's own S/M/L
sizes that is about 167 developer-days, 133 of them *must*; the project's recent
pace with Claude Code has been far faster than those sizes assume, so the
calendar will be set by the owner's decisions and reviews more than by coding
(§7).

---

## 1. How to work through it (for whoever picks up an increment)

1. **Read the part** the increment's items come from, and its decisions. If a
   decision listed under *Decisions* is unclear, read its answer in
   [12](12-decisions.md) (and on the decisions page) before starting; ask the
   owner only if the answer itself is ambiguous.
2. **Make the branch** the repository's way (CLAUDE.md, *Branch naming
   convention*): the next `V<major>.<minor>`, never a `claude/*` name, never
   `git pull` on a V-branch. The session hook proposes the number.
3. **Write the increment's plan file first**, `docs/plans/V3.NN-<slug>.md`, and
   add its row to `docs/plans/README.md`. Copy the items' acceptance lines into
   it; amend it as the work changes your mind.
4. **Take the feature ID from §8** (reserved here, so nothing collides), and
   mark it shipped in `docs/ROADMAP_NEXT.md` and `docs/BACKLOG.md` when done.
5. **Run the suite the CI way** before pushing:
   `QTWEBENGINE_CHROMIUM_FLAGS=--no-sandbox QT_QPA_PLATFORM=offscreen python scripts/run_tests.py --exclude tests.test_undo_redo --max-skips 25`
   and read its `RESULT:` line, not the exit code.
6. **End with a *How to test this*** for the owner (CLAUDE.md), and explain
   every command handed over.
7. **Docs-only commits** carry `[skip ci]`, because every push to a V-branch
   builds and publishes installers until FN-7 makes them prereleases.

## 2. The order, and why

- **Trust before features.** Increments 1 and 2 fix what is wrong today. Each
  item is small and independent, so they can land in any order and none waits on
  a decision except D1 (whether to publish) and K1.
- **The switch before the surfaces.** Increment 4 (MD-1) is what lets the
  overview, the plant page and Plan My Yard each have a simple and an advanced
  form without two copies of each page. Increment 3 makes the advanced pages
  agree with each other first, because the overview will read their numbers.
- **The region before the plant list.** The plant list's default (ED-10) and
  the overview's regional sentences (OV-13) read the region pack (increment 7).
- **The overview before Plan My Yard.** Plan My Yard plants where the overview
  measures (`yard_overview.planting_area`, OV-1) and fills to the overview's
  cover measure (PY-4).
- **Finishing last, sessions after it.** Signing and the guide's screenshots
  need the final look; the sessions need the finished simple app.

**Can two people work in parallel?** Yes, along these seams: increments 1–3 are
independent of each other; 6 (front door) and 7–8 (region) touch different
files; data jobs (§6) run alongside everything, mostly for the owner.

## 3. The increments

### Increment 1 · V3.18 · Trust fixes (must; about 12 developer-days; F233, F235, F236, F240, F241, F242)

| ID | Item | Effort | Part |
|---|---|---|---|
| ST-1 | Fix the dead Lessons door | S | [04](04-start-screen.md) |
| ST-2 | Guard: no undefined names | S | [04](04-start-screen.md) |
| ST-3 | A start-screen action that fails says so | S | [04](04-start-screen.md) |
| QF-1 | The PDF's text is dark enough to print (R1) | S | [11](11-work-plan.md) |
| QF-4 | The worked example uses Edmonton-list plants (R14) | S | [11](11-work-plan.md) |
| QF-16 | One nursery list now: the PDF and plan read the directory, as the order file does (EDF-1) | S | [11](11-work-plan.md) |
| QF-17 | The PDF's place line from the design's own pin (EDF-2) | S | [11](11-work-plan.md) |
| PY-3 | Keep-out by polygon | S | [07](07-plan-my-yard.md) |
| PY-5 | Replace, not stack | S | [07](07-plan-my-yard.md) |
| WD-4 | Errors and confirmations | S | [09](09-words.md) |
| RM-1 | Delete the version picker | S | [03](03-what-goes.md) |
| FN-7 | A stable channel | S | [10](10-finishing.md) |
| FN-1 | Settle the licence: GPL-3.0 (D1) | S | [10](10-finishing.md) |

*Shipped in V3.18* ([plan](../plans/V3.18-trust-fixes.md)). **FN-1 was pulled
forward from increment 14**: the owner answered D1 with GPL-3.0, this release
publishes installers that bundle PyQt6, and an installer under the PolyForm
licence is exactly the conflict D1 names, so the release could not wait for it.

*Decisions (answered, see 12):* D1 (it decides whether this release may go public), G1, Y4. *Done when:* the Lessons door opens Lessons; a printed PDF is readable in black and white; the example has no plant off the Edmonton list; planning twice leaves one plan; a 1 m path no longer empties half the yard; a damaged file says so in a sentence; pushes publish prereleases.

### Increment 2 · V3.19 · What a stranger trips on (must; about 16 developer-days; F233, F241)

| ID | Item | Effort | Part |
|---|---|---|---|
| QF-2 | The map zooms to the yard when the pin is set (R7) | S | [11](11-work-plan.md) |
| QF-3 | Offline address search says it needs a connection (R6) | S | [11](11-work-plan.md) |
| QF-5 | Site Info does not scroll sideways with a pin (R8) | S | [11](11-work-plan.md) |
| QF-6 | Offline, the map says why it is blank (R9) | S | [11](11-work-plan.md) |
| QF-7 | Food page: citations by name, the flight months spaced (R17) | S | [11](11-work-plan.md) |
| QF-8 | No "0.0 m" label on a boundary's closing side (R19) | S | [11](11-work-plan.md) |
| QF-9 | The PDF key's spacing is the plant page's (R20) | S | [11](11-work-plan.md) |
| QF-10 | Community names wrap rather than cut (R21) | S | [11](11-work-plan.md) |
| QF-11 | The plan's soil line and its pointer to Draw › Shape (R24) | S | [11](11-work-plan.md) |
| QF-12 | The status bar's tasks are the design's, or none (R26) | S | [11](11-work-plan.md) |
| QF-13 | Growth Snapshots' years said the same everywhere (R28) | S | [11](11-work-plan.md) |
| QF-14 | A self-crossing outline is refused, with a reason (R29) | S | [11](11-work-plan.md) |
| QF-15 | An Edit menu: Undo, Redo, Delete, Select all (R33) | S | [11](11-work-plan.md) |
| QF-18 | The scale bar picks its units by itself, and can still be switched (R18, K1) | S | [11](11-work-plan.md) |
| QF-19 | An overlay switch with nothing to draw says so (R27, advanced pages) | S | [11](11-work-plan.md) |
| WD-6 | Retire pioneer | S | [09](09-words.md) |

*Decisions (answered, see 12):* K1 (the scale bar). *Done when:* each QF row's own test passes, and the first review's walkthrough (pin, outline, plant, export) shows none of R6–R9, R17–R21, R24, R26, R28, R29, R33.

### Increment 3 · V3.20 · One answer for each question (should; about 8 developer-days; F239)

| ID | Item | Effort | Part |
|---|---|---|---|
| OV-3 | One planting area, one bed area, one mulch depth (OVF-3) | S | [06](06-yard-overview.md) |
| OV-4 | One habitat score per design (OVF-1) | S | [06](06-yard-overview.md) |
| OV-5 | One wildlife count, worded as records (OVF-4, R15, R16) | S | [06](06-yard-overview.md) |
| OV-6 | Hours from the care calendar (OVF-2) | S | [06](06-yard-overview.md) |
| OV-7 | Water: all rows, the pin's rainfall, the weekly rule (R4, R38) | S–M | [06](06-yard-overview.md) |
| OV-8 | "This month" stops contradicting the care calendar (OVF-5) | S | [06](06-yard-overview.md) |
| OV-11 | Habitat page tidy for advanced | S | [06](06-yard-overview.md) |

*Decisions (answered, see 12):* O2, O6. *Done when:* the Report card, Habitat and the PDF show one score, one wildlife count and one set of hours for the same design; the Water page counts every plant.

### Increment 4 · V3.21 · Simple by default (must; about 10 developer-days; F234, F241)

| ID | Item | Effort | Part |
|---|---|---|---|
| MD-1 | The switch and its registry | M | [02](02-two-ways-to-use-it.md) |
| MD-2 | Every existing guard runs in both modes | S | [02](02-two-ways-to-use-it.md) |
| MD-3 | "This design uses advanced tools." | S | [02](02-two-ways-to-use-it.md) |
| MD-5 | Pointers and help text follow the mode | S | [02](02-two-ways-to-use-it.md) |
| RM-4 | The advanced registry, filled | S | [03](03-what-goes.md) |
| RM-8 | The community page in simple mode | S | [03](03-what-goes.md) |
| RM-9 | Structures grouped | S | [03](03-what-goes.md) |
| WD-1 | The glossary as a test | S | [09](09-words.md) |

*Decisions (answered, see 12):* M1, M3, G6, W1. *Done when:* a cold start shows only 02's simple surfaces; View → Advanced tools shows everything that exists today; the smoke suite passes in both modes; the vocabulary test is in place.

### Increment 5 · V3.22 · What goes (must; about 8 developer-days; F235)

| ID | Item | Effort | Part |
|---|---|---|---|
| RM-2 | Delete Import Yard Scan and the splat backdrop | M | [03](03-what-goes.md) |
| RM-3 | The local AI leaves the app | S | [03](03-what-goes.md) |
| RM-5 | Record the reversals | S | [03](03-what-goes.md) |
| RM-6 | Delete `src/db/recipes.py` | S | [03](03-what-goes.md) |
| RM-7 | Trim the installer | S | [03](03-what-goes.md) |
| RM-10 | Retire the Plant Directory window | S | [03](03-what-goes.md) |

*Decisions (answered, see 12):* G1, G2, G3, Y1. *Done when:* no Import Yard Scan, no AI wording, no Plant Directory window; the Learn door still opens Walk a Wild Landscape and Lessons & Field Study; an old design holding a scan still opens; the installer is about 33 MB smaller.

### Increment 6 · V3.23 · The front door (must; about 8 developer-days; F236)

| ID | Item | Effort | Part |
|---|---|---|---|
| ST-4 | Rebuild the start screen as "Your designs" (Option B) | M | [04](04-start-screen.md) |
| ST-5 | A design takes its name from its address | S | [04](04-start-screen.md) |
| ST-6 | One way to start a new yard | S | [04](04-start-screen.md) |
| ST-7 | Rename a design | S | [04](04-start-screen.md) |
| ST-8 | Unsaved work is kept when Recover is passed over | S | [04](04-start-screen.md) |
| ST-9 | The example opens as a copy | S | [04](04-start-screen.md) |

*Decisions (answered, see 12):* S6–S9, S12, S13 (listed in 12). *Done when:* 04's three mockups match the running app; a new design is named from its address; the example opens as a copy; unsaved work survives a passed-over Recover.

### Increment 7 · V3.24 · The region pack (must; about 13 developer-days; F237)

| ID | Item | Effort | Part |
|---|---|---|---|
| ED-1 | The region layer and the Edmonton pack | M | [08](08-edmonton-edition.md) |
| ED-2 | The local flora read from packs | M | [08](08-edmonton-edition.md) |
| ED-3 | Labels and goals from the region | M | [08](08-edmonton-edition.md) |
| ED-4 | One nursery list | S | [08](08-edmonton-edition.md) |
| ED-5 | The place line on exports | S | [08](08-edmonton-edition.md) |
| ED-11 | Guard tests | S | [08](08-edmonton-edition.md) |
| ED-13 | The edition file and the installer's contents | S | [08](08-edmonton-edition.md) |

*Decisions (answered, see 12):* E1, E4, E9. *Done when:* the region guard passes; the Edmonton list is byte-identical after the move; one nursery list in every output; a Calgary test pack relabels the goal, the quality and the switch with no code change.

### Increment 8 · V3.25 · Climate and coverage from the region (should; about 13 developer-days; F237)

| ID | Item | Effort | Part |
|---|---|---|---|
| ED-6 | Climate from the region; fallbacks limited by distance | M | [08](08-edmonton-edition.md) |
| ED-7 | Map view and address search from the region | S | [08](08-edmonton-edition.md) |
| ED-8 | Coverage messages and out-of-area behaviour | M | [08](08-edmonton-edition.md) |
| ED-9 | Nativity by the pin's province | M | [08](08-edmonton-edition.md) |
| ED-17 | Native counts by the Edmonton list in the score | M | [08](08-edmonton-edition.md) |

*Decisions (answered, see 12):* E2, E3, E5, E7. *Done when:* a Toronto pin gets the outside-the-area sentence and no borrowed climate; frost dates agree everywhere; a Regina design scores a Saskatchewan native as native; an Edmonton design scores natives by the Edmonton list.

### Increment 9 · V3.26 · Plants that lead (must; about 17 developer-days; F238, F237, F241)

| ID | Item | Effort | Part |
|---|---|---|---|
| PR-1 | `src/plant_priority.py`: the Impact and Feasibility ranking | M | [05](05-plants-that-lead.md) |
| PR-2 | "Best picks first" is the default order | S | [05](05-plants-that-lead.md) |
| PR-3 | Simple-mode plant row: band chip and one reason; layers interleaved on the first screen | M | [05](05-plants-that-lead.md) |
| PR-4 | The plant page in two modes | M | [05](05-plants-that-lead.md) |
| PR-6 | The generator ranks its pool, palette and repairs by `plant_priority` | M | [05](05-plants-that-lead.md) |
| PR-9 | Community library: "Best picks first" by default | S | [05](05-plants-that-lead.md) |
| ED-10 | The region's defaults on | S | [08](08-edmonton-edition.md) |
| WD-3 | The plant list and page | S | [09](09-words.md) |
| WD-8 | The ID line and the not-known lines | S | [09](09-words.md) |

*Decisions (answered, see 12):* L1–L7, L9, L10 (listed in 12). *Done when:* Placement › Plants opens on the Edmonton list, best picks first, each row with a band and a reason; the plant page has two modes; the generator's pool follows the same ranking.

### Increment 10 · V3.27 · How your yard is doing (must; about 19 developer-days; F239, F234, F241)

| ID | Item | Effort | Part |
|---|---|---|---|
| OV-1 | `src/yard_overview.py`, the Qt-free core | M | [06](06-yard-overview.md) |
| OV-2 | The Overview page | M | [06](06-yard-overview.md) |
| OV-9 | "Ways to fill the gaps." | M | [06](06-yard-overview.md) |
| OV-10 | Swap for a local native (OVF-6) | M | [06](06-yard-overview.md) |
| OV-12 | The PDF's first-page summary is the overview | S | [06](06-yard-overview.md) |
| OV-13 | Regional sentences as data | S (plus owner reading the bylaw) | [06](06-yard-overview.md) |
| MD-4 | "More detail ▸" from the overview | S | [02](02-two-ways-to-use-it.md) |
| WD-7 | Animals by English name | S | [09](09-words.md) |
| PY-12 | Front and back yards measured automatically | M | [07](07-plan-my-yard.md) |

*Decisions (answered, see 12):* O1, O3, O4, O5, O7. *Done when:* the Design tab opens on six items in under 300 words with the numbers of 06 §6; each More detail link lands on its advanced page; the PDF's first page is the overview; a drawn lot with its house reads front and back yard areas.

### Increment 11 · V3.28 · Plan My Yard (must; about 12 developer-days; F240)

| ID | Item | Effort | Part |
|---|---|---|---|
| PY-1 | The Plan My Yard dialog | M | [07](07-plan-my-yard.md) |
| PY-2 | One planting area | M | [07](07-plan-my-yard.md) |
| PY-4 | Fill to cover | M | [07](07-plan-my-yard.md) |
| PY-9 | The dialog's preconditions | S | [07](07-plan-my-yard.md) |
| PY-10 | The getting-started strip | S | [07](07-plan-my-yard.md) |
| PY-11 | Keep the probe honest | S | [07](07-plan-my-yard.md) |

*Decisions (answered, see 12):* Y3, Y6. *Done when:* plan_my_yard_probe.py --assert passes: plants go in the drawn bed, not on the lawn or the path, and cover rises with the fullness chosen.

### Increment 12 · V3.29 · Try another, front or back, about this plan (should; about 9 developer-days; F240)

| ID | Item | Effort | Part |
|---|---|---|---|
| PY-6 | Try another | M | [07](07-plan-my-yard.md) |
| PY-7 | Front or back yard | M | [07](07-plan-my-yard.md) |
| PY-8 | About this plan | M | [07](07-plan-my-yard.md) |

*Decisions (answered, see 12):* Y2, Y5. *Done when:* Try another three times gives three plans, each one undo step; a front-yard plan keeps the street band low; no modal notes box in the simple app.

### Increment 13 · V3.30 · Site Info and the printout (should; about 4 developer-days; F241)

| ID | Item | Effort | Part |
|---|---|---|---|
| WD-2 | The strip and Site Info | M | [09](09-words.md) |
| WD-5 | The printed plan and order file | S | [09](09-words.md) |

*Decisions (answered, see 12):* W5, E6, O5. *Done when:* Site Info is four lines at 1366 × 768; the printout says Where to buy around Edmonton.

### Increment 14 · V3.31 · Ready for strangers (must; about 13 developer-days; F242)

| ID | Item | Effort | Part |
|---|---|---|---|
| ~~FN-1~~ | Settle the licence: **moved to increment 1, shipped in V3.18** | S (a) / L (b) | [10](10-finishing.md) |
| FN-2 | Third-party notices | S | [10](10-finishing.md) |
| FN-3 | Sign the Windows installer | M | [10](10-finishing.md) |
| FN-4 | macOS | M / S | [10](10-finishing.md) |
| FN-5 | Credit every source and say what leaves the computer | S | [10](10-finishing.md) |
| FN-6 | Identify the app | S | [10](10-finishing.md) |
| FN-8 | Feedback without an account | S | [10](10-finishing.md) |
| FN-11 | The one-page guide | S | [10](10-finishing.md) |
| FN-12 | Pin the build | S | [10](10-finishing.md) |

*Decisions (answered, see 12):* D2, D3, D4, D6. *Done when:* the README and release notes show the SmartScreen and Mac steps; every service is credited; Send Feedback needs no account; the guide is in the README.

### Increment 15 · V3.32 · Watch five people use it, then hand it over (must; about 5 developer-days; F243, F242)

| ID | Item | Effort | Part |
|---|---|---|---|
| FN-9 | Usability sessions | M (people's time) | [10](10-finishing.md) |
| FN-13 | `docs/MAINTENANCE.md` | S | [10](10-finishing.md) |
| FN-14 | A second maintainer | S | [10](10-finishing.md) |

*Decisions (answered, see 12):* D5, D7. *Done when:* four of five homeowners complete 01 §6's tasks 1, 2, 6 and 7 unaided; the fixes they forced are in; the friend has cut a release; the release is promoted as the finished one.

Items not scheduled: **ST-10** is cancelled (the Learn door stays, S1); **ED-12** is deferred (no website work for now, G5); **ED-14** is cancelled (no rules block, E6); **FN-10** is cancelled (no donations for now, G5, D6); **PR-5** is superseded by OV-11 (the score tips are retired); **OV-14** is optional, after Sun & Shade's zones are classified; **ED-15** and **ED-16** come after finishing (F244, F245); **PR-7** and **PR-8** are data jobs (§6).

## 4. The quick fixes (QF-1 to QF-19)

The first review's findings that no other part owns, plus the two Edmonton
defects worth fixing before the region pack exists. Each is S.

| ID | Fix | Where | Test |
|---|---|---|---|
| **QF-1** | The PDF's body text in dark ink: replace the dark-theme greens (`#a5d6a7`, `#c8e6c9`) used for the Design Summary, the Planting Plan tables and Phased Conversion with the print palette (R1) | `src/pdf_export.py` (the summary and table styles, about `:300-585`) | Render the example's PDF; every text colour has 4.5:1 contrast against white |
| **QF-2** | Setting the pin zooms the map to about yard scale (zoom 19) (R7) | The pin-drop and address-pick handlers (`src/controllers/map_events.py`, `src/site_panel.py`) | After a pin, the map's zoom is ≥ 18 |
| **QF-3** | Offline address search says *Address search needs an internet connection…* (R6); `geocode_address` returns `None` for a failure and `[]` for no match | `src/property_data.py` `geocode_address`; `src/site_panel.py:2353` | The two cases give their two messages |
| **QF-4** | The worked example: Canada Goldenrod → Stiff Goldenrod, Showy Milkweed → Oval-leaf Milkweed (*A. ovalifolia*, catalogued as "Green Milkweed" until V3.18; L9), and the notes reworded (R14; 08 §3) | `src/onboarding.py:160-210` | Every example species is on the Edmonton list (the test ED-1's pack test later inherits) |
| **QF-5** | Site Info fits 1366 px with a pin set (R8), and the guard checks the pinned page, not only the empty one | `src/site_panel.py`; `tests/test_app_smoke.py:693` | The smoke test sets a pin, then checks for sideways scroll |
| **QF-6** | Offline, the map shows *The map needs an internet connection to load. Your design is safe.* instead of a blank grey area (R9) | `html/map/01-core.js` (the tile layer's error event) | A node test of the message function; manual check offline |
| **QF-7** | Food page: sources by name through `citations.format_sources(…, short=True)`, and the flight-season months spaced (R17) | `src/food_page.py:376-380` | No `_` in the footnote for the example |
| **QF-8** | No length label on a closing side shorter than 5 cm (R19) | `html/map/02-boundary.js:385-394` | `tests/test_boundary_press.py` style probe |
| **QF-9** | The PDF key prints the plant page's spacing (R20), one number from one function | `src/pdf_export.py`, `src/planting_map.py`; `src/species_page.py:289-293` | Wild Bergamot's spacing is the same on the page and in the PDF |
| **QF-10** | Community names in the library list wrap to two lines rather than being cut (R21), as the panel list does since V3.11 (`two_lines`) | `src/polyculture_panel.py` | At 1366 px no community name is elided |
| **QF-11** | The plan's soil line (*Soil: loam*, not *loam — unknown texture*) and its pointer to *Draw › Shape* (R24) | `src/planting_plan.py`, `src/site_prep.py` | The example's plan text |
| **QF-12** | The status bar shows the design's month tasks, or nothing, not the catalogue's first eight (R26) | `src/app.py:1073` (`_load_seasonal_tasks`) | With no plants, the status bar shows no tasks |
| **QF-13** | Share's Growth Snapshots line reads the years from `snapshot_timeline` (the window caps 30 at the design's horizon, so it shows 20) (R28) | `src/share_panel.py:65`; `src/snapshot_timeline.py:24-50` | The line and the window agree for the example |
| **QF-14** | A self-crossing outline is refused when closed: *The outline crosses itself. Click Undo and redraw the last corner.* (R29) | The boundary close handler; `shapely` `is_valid` | A bow-tie outline is not stored |
| **QF-15** | An Edit menu: Undo, Redo, Delete, Select all, wired through a flow module (MainWindow is at its method ceiling) (R33); 02 §3.2's menu table gains it | `src/app.py` menu bar; a new `src/edit_menu_flow.py` | The menu exists; each action matches its toolbar twin |
| **QF-16** | One nursery list now: the PDF and the planting plan read `nurseries.native_sources_near` as the order file does; delete `planting_plan.NURSERIES` (EDF-1). ED-4 later narrows it to the pack's list | `src/planting_plan.py:51-63`; `src/pdf_export.py` | One export of the example names the same suppliers in all three outputs |
| **QF-17** | The PDF's place line from the design's own pin (its geocoded place, else the coordinates); nothing without a pin (EDF-2). ED-5 later uses the region's name | `src/pdf_export.py:313` | A Regina pin's PDF does not say Edmonton |
| **QF-18** | The scale bar picks its units by itself (metres below 1 km) and can still be switched (R18). **Owner's answer K1**: "Automatic but able to change between the 2", so View › Scale Units becomes *Automatic* (the new default), *Kilometres*, *Metres*; V3.06's kilometres default is reversed | `html/map/11-map-furniture.js` (`scaleBarFor`), `src/map_furniture_flow.py` | The node test of `scaleBarFor` at yard scale gives metres |
| **QF-19** | An overlay switch with nothing to draw is disabled with a tooltip saying what it needs (R27); advanced pages only | The Slope, Wind and Habitat pages' overlay checkboxes | Each switch is disabled until its overlay exists |

## 5. The first review's findings, R1 to R40

Every R-number in [`../SALE_READINESS_REVIEW.md`](../SALE_READINESS_REVIEW.md)
and the item that fixes it. None is left alone.

| R | Finding (short) | Fixed by | Increment |
|---|---|---|---|
| R1 | PDF text too pale to print | QF-1 | 1 |
| R2 | Generate twice stacks a second design | PY-5 | 1 |
| R3 | Brief ignored without the AI; raw error text | RM-3, PY-1 | 5, 11 |
| R4 | Water table skips 14 of 19 plants; fixed rainfall | OV-7; ED-6 | 3; 8 |
| R5 | Characteristic species matched on a name's first word | OV-11 | 3 |
| R6 | Offline search says "No Alberta results" | QF-3; ED-7 | 2; 8 |
| R7 | No zoom after the pin | QF-2 | 2 |
| R8 | Site Info scrolls sideways with a pin | QF-5; WD-2 | 2; 13 |
| R9 | Offline map is blank grey | QF-6 | 2 |
| R10 | Pet and child safe treat blank data as safe | WD-3 (words), 07 Y6 (the boxes), F248 (data) | 9, 11, alongside |
| R11 | "Won't take over" on blank data | PR-7 (F246), PR-3 (the words) | alongside, 9 |
| R12 | Score with no coverage term | OV-1, OV-2 (coverage in words); O1 | 10 |
| R13 | Sparse generated designs | PY-4 | 11 |
| R14 | Example contains two plants not native here | QF-4 | 1 |
| R15 | "589 wildlife species supported" | OV-5 | 3 |
| R16 | Two breakdowns of the same animals | OV-5 | 3 |
| R17 | Raw citation keys; run-together months | QF-7 | 2 |
| R18 | Scale bar in km at yard scale | QF-18 (K1) | 2 |
| R19 | "0.0 m" label | QF-8 | 2 |
| R20 | Two spacing numbers for one plant | QF-9; PR-4 | 2; 9 |
| R21 | Community names cut | QF-10 | 2 |
| R22 | Plant list A–Z around Edmonton; American Elm first | PR-2, ED-10 | 9 |
| R23 | 72% of animals Latin only | WD-7 | 10 |
| R24 | "loam — unknown texture"; a stale pointer | QF-11 | 2 |
| R25 | Design notes are a run log | PY-8 | 12 |
| R26 | Catalogue-wide tasks in the status bar; the pin instruction three times | QF-12; WD-2 | 2; 13 |
| R27 | Overlay switches that do nothing | QF-19; MD-1 hides them | 2; 4 |
| R28 | Snapshots' years disagree | QF-13 | 2 |
| R29 | A self-crossing outline accepted | QF-14 | 2 |
| R30 | Edmonton natives off by default | ED-10 | 9 |
| R31 | No way to hide advanced tools | MD-1 | 4 |
| R32 | A Toronto pin gets prairie data and no warning | ED-8 | 8 |
| R33 | No Edit menu; exit prompt without Save | QF-15; WD-4 | 2; 1 |
| R34 | Designs never named | ST-5 | 6 |
| R35 | A damaged file shows Python's error | WD-4 | 1 |
| R36 | Hero photos chosen for documentation | PR-8 (F247) | alongside |
| R37 | Tallamy's 90% misquoted | OV-11 | 3 |
| R38 | Water's seasonal "surplus" | OV-7 | 3 |
| R39 | Score tips A–Z | OV-11 (retires the tips) | 3 |
| R40 | No usability test since August | FN-9 | 15 |

## 6. Alongside the code: data jobs

Mostly the owner's (or a knowledgeable friend's) time, run in parallel. Each
has a reserved ID.

| ID | Job | Feeds | Part |
|---|---|---|---|
| **F246** | The spread review: 26 candidate spreaders, plus "not yet checked" for blanks (PR-7) | PR-3's cautions, Plan My Yard's *stays where you put it* | [05](05-plants-that-lead.md) |
| **F247** | Photographs for the 12 of the top 60 without one, and hero photos chosen for beauty for the top 40 (PR-8) | The plant list and page | [05](05-plants-that-lead.md) |
| **F248** | Toxicity records for the top 60 (48 blank) | The poison wording (R10, Y6) | [05](05-plants-that-lead.md) §9 |
| **F249** | About 30 animals an Edmonton homeowner knows, for the named examples (O4). Related to F190 (animals carry no range) but not the same job | The overview's wildlife item, WD-7 | [06](06-yard-overview.md) |
| F227 (open) | The owner's review of the availability tiers | *Easy to buy* and the ranking's Buy points | [05](05-plants-that-lead.md) |
| ED-14 | Reading Edmonton's bylaw and the other rules' sources (E6, O5) | The rules block, the street sentence | [08](08-edmonton-edition.md) |

## 7. Effort, honestly

The S/M/L sizes in every part are a person's days: S up to a day, M two to four,
L a week or more. Summed, the fifteen increments are **about 167
developer-days, 133 of them *must***, plus the data jobs and the sessions'
people time. Two cautions about that number:

- **It is probably high for this project.** Five releases (V3.13 to V3.17) were
  published on 8 October 2026 alone, built with Claude Code. Coding is not the
  bottleneck here; the owner's decisions, reviews and testing on a real desktop
  are.
- **It is probably low for the parts that touch the outside world.** Signing
  accounts, identity checks, Riverbank's or a lawyer's answer, and homeowners'
  calendars take the time they take.

A realistic reading: the *must* increments in two to four months of evenings and
weekends between the owner and a friend, with Claude Code doing most of the
typing.

## 8. Feature IDs reserved (F233 to F249)

Taken from the ledger in [`../ROADMAP_NEXT.md`](../ROADMAP_NEXT.md) (next free
was F233) and registered there and in [`../BACKLOG.md`](../BACKLOG.md) (group S)
in the same commit as this plan. **Next free ID after this plan: F250.**

| ID | Feature | Items | Kind |
|---|---|---|---|
| **F233** | The first review's quick fixes | QF-1 to QF-19 | code |
| **F234** | Simple by default, advanced on request | MD-1 to MD-5, RM-4, RM-8, RM-9 | code |
| **F235** | What goes: the deletions | RM-1 to RM-3, RM-5 to RM-7, RM-10 (ST-10 cancelled: the Learn door stays) | code |
| **F236** | The front door: "Your designs" | ST-1 to ST-9 | code |
| **F237** | The region pack: Edmonton as a template | ED-1 to ED-11, ED-13, ED-17 (ED-12 deferred, ED-14 cancelled) | code |
| **F238** | Plants that lead | PR-1 to PR-6, PR-9 | code |
| **F239** | How your yard is doing: the overview | OV-1 to OV-14 | code |
| **F240** | Plan My Yard | PY-1 to PY-12 | code |
| **F241** | The words | WD-1 to WD-8 | code |
| **F242** | Finishing: licence, signing, services, releases, runbook | FN-1 to FN-8, FN-11 to FN-14 (FN-10 cancelled) | code and accounts |
| **F243** | Usability sessions with homeowners | FN-9 | people |
| **F244** | The Calgary edition | ED-15 | code and data; after finishing |
| **F245** | The Regina edition | ED-16 | waits for herbarium data |
| **F246** | The spread review | PR-7 | data job |
| **F247** | Photographs for the top 60 | PR-8 | data job |
| **F248** | Toxicity records for the top 60 | — | data job |
| **F249** | The animals an Edmonton homeowner knows | — (O4) | data job |

## 9. Every work item, and its increment

| ID | Item | Increment |
|---|---|---|
| QF-1 | The PDF's text is dark enough to print (R1) | 1 |
| QF-2 | The map zooms to the yard when the pin is set (R7) | 2 |
| QF-3 | Offline address search says it needs a connection (R6) | 2 |
| QF-4 | The worked example uses Edmonton-list plants (R14) | 1 |
| QF-5 | Site Info does not scroll sideways with a pin (R8) | 2 |
| QF-6 | Offline, the map says why it is blank (R9) | 2 |
| QF-7 | Food page: citations by name, the flight months spaced (R17) | 2 |
| QF-8 | No "0.0 m" label on a boundary's closing side (R19) | 2 |
| QF-9 | The PDF key's spacing is the plant page's (R20) | 2 |
| QF-10 | Community names wrap rather than cut (R21) | 2 |
| QF-11 | The plan's soil line and its pointer to Draw › Shape (R24) | 2 |
| QF-12 | The status bar's tasks are the design's, or none (R26) | 2 |
| QF-13 | Growth Snapshots' years said the same everywhere (R28) | 2 |
| QF-14 | A self-crossing outline is refused, with a reason (R29) | 2 |
| QF-15 | An Edit menu: Undo, Redo, Delete, Select all (R33) | 2 |
| QF-16 | One nursery list now: the PDF and plan read the directory, as the order file does (EDF-1) | 1 |
| QF-17 | The PDF's place line from the design's own pin (EDF-2) | 1 |
| QF-18 | The scale bar picks its units by itself, and can still be switched (R18, K1) | 2 |
| QF-19 | An overlay switch with nothing to draw says so (R27, advanced pages) | 2 |
| ST-1 | Fix the dead Lessons door | 1 |
| ST-2 | Guard: no undefined names | 1 |
| ST-3 | A start-screen action that fails says so | 1 |
| ST-4 | Rebuild the start screen as "Your designs" (Option B) | 6 |
| ST-5 | A design takes its name from its address | 6 |
| ST-6 | One way to start a new yard | 6 |
| ST-7 | Rename a design | 6 |
| ST-8 | Unsaved work is kept when Recover is passed over | 6 |
| ST-9 | The example opens as a copy | 6 |
| ST-10 | Retire the Learn door and its menu | cancelled: the Learn door stays (S1) |
| MD-1 | The switch and its registry | 4 |
| MD-2 | Every existing guard runs in both modes | 4 |
| MD-3 | "This design uses advanced tools." | 4 |
| MD-4 | "More detail ▸" from the overview | 10 |
| MD-5 | Pointers and help text follow the mode | 4 |
| RM-1 | Delete the version picker | 1 |
| RM-2 | Delete Import Yard Scan and the splat backdrop | 5 |
| RM-3 | The local AI leaves the app | 5 |
| RM-4 | The advanced registry, filled | 4 |
| RM-5 | Record the reversals | 5 |
| RM-6 | Delete `src/db/recipes.py` | 5 |
| RM-7 | Trim the installer | 5 |
| RM-8 | The community page in simple mode | 4 |
| RM-9 | Structures grouped | 4 |
| RM-10 | Retire the Plant Directory window | 5 |
| PR-1 | `src/plant_priority.py`: the Impact and Feasibility ranking | 9 |
| PR-2 | "Best picks first" is the default order | 9 |
| PR-3 | Simple-mode plant row: band chip and one reason; layers interleaved on the first screen | 9 |
| PR-4 | The plant page in two modes | 9 |
| PR-5 | Score tips ordered by the ranking, from the Edmonton list, sized to the yard | superseded by OV-11 (the tips are retired) |
| PR-6 | The generator ranks its pool, palette and repairs by `plant_priority` | 9 |
| PR-7 | The spread review (first-pass R11) | data job F246, runs alongside (owner) |
| PR-8 | Photographs for the top 60, and hero photos chosen for beauty | data job F247, runs alongside (owner) |
| PR-9 | Community library: "Best picks first" by default | 9 |
| OV-1 | `src/yard_overview.py`, the Qt-free core | 10 |
| OV-2 | The Overview page | 10 |
| OV-3 | One planting area, one bed area, one mulch depth (OVF-3) | 3 |
| OV-4 | One habitat score per design (OVF-1) | 3 |
| OV-5 | One wildlife count, worded as records (OVF-4, R15, R16) | 3 |
| OV-6 | Hours from the care calendar (OVF-2) | 3 |
| OV-7 | Water: all rows, the pin's rainfall, the weekly rule (R4, R38) | 3 |
| OV-8 | "This month" stops contradicting the care calendar (OVF-5) | 3 |
| OV-9 | "Ways to fill the gaps." | 10 |
| OV-10 | Swap for a local native (OVF-6) | 10 |
| OV-11 | Habitat page tidy for advanced | 3 |
| OV-12 | The PDF's first-page summary is the overview | 10 |
| OV-13 | Regional sentences as data | 10 |
| OV-14 | Sun fit in item 3 | optional, after Sun & Shade's zones are classified |
| PY-1 | The Plan My Yard dialog | 11 |
| PY-2 | One planting area | 11 |
| PY-3 | Keep-out by polygon | 1 |
| PY-4 | Fill to cover | 11 |
| PY-5 | Replace, not stack | 1 |
| PY-6 | Try another | 12 |
| PY-7 | Front or back yard | 12 |
| PY-8 | About this plan | 12 |
| PY-9 | The dialog's preconditions | 11 |
| PY-10 | The getting-started strip | 11 |
| PY-11 | Keep the probe honest | 11 |
| PY-12 | Front and back yards measured automatically | 10 |
| ED-1 | The region layer and the Edmonton pack | 7 |
| ED-2 | The local flora read from packs | 7 |
| ED-3 | Labels and goals from the region | 7 |
| ED-4 | One nursery list | 7 |
| ED-5 | The place line on exports | 7 |
| ED-6 | Climate from the region; fallbacks limited by distance | 8 |
| ED-7 | Map view and address search from the region | 8 |
| ED-8 | Coverage messages and out-of-area behaviour | 8 |
| ED-9 | Nativity by the pin's province | 8 |
| ED-10 | The region's defaults on | 9 |
| ED-11 | Guard tests | 7 |
| ED-12 | The website reads every pack | deferred: no website work for now (G5) |
| ED-13 | The edition file and the installer's contents | 7 |
| ED-14 | The Edmonton rules content | cancelled: no rules block (E6) |
| ED-15 | The Calgary pack | after finishing: F244, needs a Calgary reviewer |
| ED-16 | The Regina pack | after finishing: F245, waits for herbarium data |
| ED-17 | Native counts by the Edmonton list in the score | 8 |
| WD-1 | The glossary as a test | 4 |
| WD-2 | The strip and Site Info | 13 |
| WD-3 | The plant list and page | 9 |
| WD-4 | Errors and confirmations | 1 |
| WD-5 | The printed plan and order file | 13 |
| WD-6 | Retire pioneer | 2 |
| WD-7 | Animals by English name | 10 |
| WD-8 | The ID line and the not-known lines | 9 |
| FN-1 | Settle the licence | 1 (moved from 14) |
| FN-2 | Third-party notices | 14 |
| FN-3 | Sign the Windows installer | 14 |
| FN-4 | macOS | 14 |
| FN-5 | Credit every source and say what leaves the computer | 14 |
| FN-6 | Identify the app | 14 |
| FN-7 | A stable channel | 1 |
| FN-8 | Feedback without an account | 14 |
| FN-9 | Usability sessions | 15 |
| FN-10 | Support this app | cancelled: no donations for now (G5, D6) |
| FN-11 | The one-page guide | 14 |
| FN-12 | Pin the build | 14 |
| FN-13 | `docs/MAINTENANCE.md` | 15 |
| FN-14 | A second maintainer | 15 |

## 10. What this plan cannot promise

- The increment boundaries are a proposal. If an increment grows, split it
  rather than letting it run on; the plan file records why.
- The sizes were estimated from reading the code, not from doing the work.
- Every *Done when* that involves a person (the sessions, the owner's reading
  of a bylaw, a signing account's identity check) depends on that person.
