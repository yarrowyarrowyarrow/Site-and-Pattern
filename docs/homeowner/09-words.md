# 9 · The words: one name for each thing, in the reader's language

*Part of the [homeowner-path plan](README.md). Work items **WD-1 to WD-8**;
owner decisions **W1 to W5** ([12-decisions.md](12-decisions.md)). The house
rules this builds on are [`../UI_PRINCIPLES.md`](../UI_PRINCIPLES.md) (Krug) and
the vocabulary rules in [`../review.md`](../review.md); this part does not
repeat them, it applies them to the simple app.*

> **The owner's answers (13 October 2026):** the glossary is accepted (W1) and the
> other W answers took the recommendation. One rule changes: for **spreading**, a
> plant not yet checked shows nothing (L5), an exception to rule 5 below; the
> must-have that filters on it reads *Leave out plants known to spread*. No
> donation copy is needed for now (G5, D6).

The persona reads every word the app shows and believes it (01 §3). Today the
simple surfaces still speak the code's language in places: *boundary*,
*polyculture*, *forb*, *keystone*, *pioneer*, *Restoring toward*, *AB retail
estimate*, and raw error text. The owner's two rules frame the fix: *"concise
in its instruction"* (V3.05) and *"not intended to be a flora reference
(certainly not an ID reference)"* (this pass).

## In one paragraph

Give each thing **one name** a homeowner already uses (§2), keep the
scientist's words for the Advanced side, and write every message to say what
happened and what to do (§4). The glossary in §2 is the contract: a word in its
*Simple* column may appear in the simple app, a word in its *Advanced* column
only behind the switch, and a word in its *Never* column nowhere. A guard test
holds it (WD-1), the way the visual floors hold contrast. §3 is the rewrite
list for the screens the simple app keeps, with file and line.

---

## 1. The register

These add to `UI_PRINCIPLES.md`'s checklist; they do not replace it.

1. **The reader's words, not the data's.** "Plants that feed the most
   caterpillars", not "keystone species". The data's word may follow in
   Advanced.
2. **One name per thing, everywhere.** The same thing is not a *boundary* on
   the strip, an *outline* in the dialog and a *property* in the PDF.
3. **Buttons start with a verb and say what happens.** *Plan my yard*, *Print
   the plan*, *Try another*. Not *OK*, not *Generate*.
4. **Numbers come with "about" and a range when they are estimates**: *about
   $760–$1,520*, *about a third of the bed*. Never a precise-looking figure the
   app cannot stand behind (P9).
5. **Say what is not known.** *Not checked for toxicity* rather than silence
   that reads as safe (R10). *Not yet reviewed for spreading* rather than "Well
   behaved" by default (R11).
6. **English names first.** A Latin name may follow in italics; it never leads
   in the simple app. An animal with no English name is counted, not listed
   (§3.6).
7. **No apology for missing machinery.** No mention of an AI, a generator, a
   database, a cache or a network unless the person must act on it.
8. **The ID line.** Wherever the app shows a photograph as information, it
   does not invite identification. One sentence, in one place (W3).
9. **Short.** A page's instruction is one line, or it is not there (the owner's
   V3.05 answer). A message is two sentences at most.
10. **Canadian spelling**, as the app already uses (colour, neighbour, centre).

## 2. The glossary: one name for each thing

| Thing | Simple app says | Advanced may also say | Never |
|---|---|---|---|
| The file you work on | **design** (*Your designs*, *Rename design*) | — | project, `.perma.geojson` in prose |
| What Plan My Yard makes, and the printout | **plan** (*Your plan*, *Print the plan*) | generated design | spec |
| The pin on the map | **your yard's pin**, *pin* | property pin, site | — |
| The outline of the yard | **yard outline** (*Outline my yard*) | boundary | property boundary in simple text |
| A drawn planting area | **bed** | Garden Bed (the shape type), planting area | fill zone, fill region |
| A kind of plant | **plant**, *kind of plant* (*14 kinds of plants*) | species | taxon |
| A ready-made planting | **community**, explained once as *plants that grow well together* (the owner's tab name, V3.07) | plant community, mix | **polyculture**, guild |
| A wildflower | **wildflower** | forb (with the word explained) | — |
| The grasses between the flowers | **grasses** | matrix grasses | — |
| The plants that feed the most caterpillars | **plants that feed the most caterpillars** | keystone plants | — |
| A plant a caterpillar must eat | **caterpillar food plant** | larval host | — |
| Animals with one food | **depends on this plant** | specialist | — |
| Native within 50 km of downtown | **native around Edmonton** | Edmonton list | — |
| Native in the province (VASCAN) | **native to Alberta** | native (VASCAN) | "Alberta native" as a seller's label, AB |
| How far apart to plant | **plant about 60 cm apart** | spacing | — |
| How wide it grows | **grows about 1 m wide** | canopy, spread | — |
| Spreads by roots or seed | **spreads**, *stays where you put it* | aggressive rhizomatous, self-seeding | well behaved |
| Poisonous | **poisonous to pets / to people if eaten** | toxicity | pet friendly, pet safe (they promise too much, R10) |
| The first two years | **the first two summers**, *getting it started* | establishment | — |
| Early plants that fade | **fills in first, then gives way** | early successional | **pioneer**, colonizer (`review.md`) |
| The habitat score | — (the overview has no 0–100 number, O1) | Habitat score | Habitat Value Score in simple text |
| A natural region | **the Edmonton region** | ecoregion, natural subregion | — |
| The middle of the moisture scale | **medium moisture** (neither dry nor wet; the Water filter's *Medium*) | — | mesic (the owner, V3.37: "not understandable to many") |
| Prices | **about $X–$Y at Edmonton native nurseries** | estimated retail price | AB retail estimate |

The *Never* column is enforced in all user text; the *Advanced* column only in
the modules that build simple surfaces (WD-1).

## 3. The rewrite list

File and line at V3.17. "Now" is the text as the app shows it; "Proposed" is
the replacement. Where another part owns the screen, it is named.

### 3.1 The start and the strip

| Where | Now | Proposed |
|---|---|---|
| `src/onboarding.py:61-63` | *Drop a pin* / *Drop a property pin* / *Search your address in the Site tab, or click "Use Pin Drop…" and click your yard on the map. This is what fetches your climate, soil and frost dates.* | *Find your yard* / *Type your address, or click your yard on the map.* |
| `src/onboarding.py:70-72` | *Draw the boundary* / *Draw your boundary* / *Draw → ⬡ Boundary, then click around the area you want to plant. Click the first point again to close it.* | *Outline where to plant* / *Click around your yard, or around one bed. Click the first point again to finish.* |
| `src/onboarding.py:83-84` | *Add your plants — or let the app draft it* / *…Or use ✨ Generate Design to fill the boundary from your goals and edit from there.* | *Plan it, or pick plants yourself* / *Plan my yard suggests a planting you can change.* (PY-10) |
| `src/app.py:497` | *Show the three-step strip above the map (pin → boundary → plants)* | *Show the getting-started steps above the map* |
| Start screen | [04-start-screen.md](04-start-screen.md) §5 | as specified there |

### 3.2 Site Info

The owner's V3.05 answer and 02 §3.1 ask for **four plain lines with Details
below**. The four lines, filled from the site data and the region pack (ED-6):

> **Where:** South Edmonton, in the Edmonton region.
> **Cold:** Plants hardy to zone 3 grow here. Frost-free from about May 15 to
> September 16.
> **Rain:** About 460 mm a year, most of it in June and July.
> **Soil:** Dark, loamy and slightly alkaline (pH 7.4), as mapped near your yard.

*Details ▸* opens what Site Info shows today (growing-degree days, the snow and
melt lines, soil texture percentages, the climate normal's station). Each line
says where its figure came from when it is a fallback: *typical for the
Edmonton region* rather than *near your yard*. Rules: the zone and frost dates
come from the region pack once E7 is decided; no line is shown for a value the
app does not have.

| Where | Now | Proposed |
|---|---|---|
| `src/site_panel.py:476` | *Search an Alberta address, or drop the pin on the map, and the site's climate and soil fill in. Drag the pin to adjust it.* | (deleted; the strip says it, R26) |
| `src/site_panel.py:492` | *Search Alberta address or place name…* | *Your address* (the pack's wording, ED-7) |
| `src/site_panel.py:506` | *Look the address up and list matches below — click one to drop the property pin there. No internet? Use "Use Pin Drop…" instead.* | Tooltip: *Find this address on the map.* |
| `src/site_panel.py:540-542` | *Use Pin Drop…* / *Click then click the map to drop the property pin manually* | *Click my yard on the map* |
| `src/site_panel.py:617` | *Open the Plant Community Library filtered to communities whose member plants are documented from this ecoregion.* | (advanced only) |
| `src/site_panel.py:754-757` | *⬇ Download soil data (offline)* / *One-time download of Canadian gridded soil data…* | (advanced only) |
| `src/site_panel.py:773` | *Where to buy — native plant sources* | (moved to Share, V3.08; the heading there: *Where to buy*) |
| `src/site_panel.py:786` | *From the Native Plant Society of Saskatchewan's list (npss.sk.ca)…* | The pack's `nursery_note` (ED-4, EDF-5) |
| `src/site_panel.py:2353` (offline search) | *No Alberta results. Try a nearby intersection or town name —* | *Couldn't search for addresses just now. Check your internet connection and try again, or click “Use Pin Drop…” and then your yard on the map.* (ED-7; R6; shipped V3.19, reworded on review: a busy or refusing service gives the same answer as no connection, so the words cannot blame the connection alone) |

### 3.3 The plant list and the plant page

| Where | Now | Proposed |
|---|---|---|
| `src/plant_filters.py` `QUALITIES` | *Native* | *Native to Alberta* (advanced; simple shows *Native around Edmonton*, on by default, ED-10) |
| same | *Edmonton native* | *Native around Edmonton* |
| same | *Feeds a specialist* | *Food for a fussy eater* — or advanced only (W4) |
| same | *Pet safe* / *Child safe* | *Not known to be poisonous to pets* / *…to people* (R10) |
| same | *Well behaved* | *Leaves out known spreaders* (owner's answer L5: a plant not yet checked shows nothing about spreading; the label claims only what the data knows) |
| same | *Easy to find* | *Easy to buy* |
| `src/plant_filters.py:117` facet | *Restoring toward* | (advanced only; simple has the region) |
| `src/plant_filters.py:112` facet | *Role* | *What it does* |
| `src/species_page.py:144` | *Add this plant to the mix under the plant list, to place several species together in a row, grid, circle or area.* | (advanced; the mix is an advanced tool, 03 §5) |
| `src/species_page.py:183` | *Pick a species to read about it.* | *Choose a plant to read about it.* |
| `src/species_page.py:386-387` | *No photograph of this species yet.* / *Photograph not downloaded yet.* | *No photo yet.* / *Photo not downloaded yet: it appears when you are online.* |
| `src/species_page.py:447` | *No documented animal relationships yet, which means unrecorded, not absent.* | *No animals recorded on it yet. That means nobody has written it down, not that nothing uses it.* |
| `src/species_page.py:456` | *with nowhere else to go (⚑)* | *that depend on it (⚑)* |
| `src/species_page.py:489` | *…of these relationships were seeded without naming a specific work, and are not yet attributable.* | (advanced only) |
| The page's sections | [05](05-plants-that-lead.md) §7 | as specified there |

### 3.4 Communities, structures, the bar over the map

| Where | Now | Proposed |
|---|---|---|
| `src/controllers/persistence.py:885` | *Undo: polyculture move (N plants)* | *Undo: moved a community (N plants)* |
| Placement › Communities heading | *Communities* | *Communities*, with the line *Plants that grow well together. Place one in a bed.* |
| Community names (R21) | *Boreal Conifer…* (cut at 1366 px) | Readable names that fit: [05](05-plants-that-lead.md); E9 for the "Edmonton …" names |
| Structures | one list of 15 | three headings (RM-9): *For wildlife*, *For water*, *Around the yard* |

### 3.5 Plan My Yard and its notes

Owned by [07-plan-my-yard.md](07-plan-my-yard.md) §4.3 and §4.5. The words to
retire, with their sources: *A local AI picks fitting native plants…*
(`src/generate_design_dialog.py:48-50`); *Build without AI (offline)*
(`:163-165`); *(local AI, with an offline fallback)* (`src/app.py:428`); the
fallback note quoting the error (`src/generate_worker.py:79-83`); *Generated
design — placed N plants. Fine-tune by dragging or deleting.*
(`src/controllers/generation.py:223-226`), which becomes the bar of 07 §4.4.

### 3.6 Animals

820 of 1,144 animals (72%) have no English name (R23). In the simple app an
animal is named only when it has an English name; the rest are counted: *Food
for 120 kinds of animals: bumble bees, the Canadian tiger swallowtail, the
black-capped chickadee and 117 others.* Pickers that list animals (the creature
picker, Food) are advanced (03 §5). Which named animals lead is decision O4
(06).

### 3.7 Errors and confirmations

Every message says what happened, whether work is safe, and what to do. The
technical detail goes to the log, through the existing `src/slot_errors.py`
pattern, never into the message.

| Where | Now | Proposed |
|---|---|---|
| `src/app.py:1912` | *Open failed* + the raw exception (a JSON parser's message for a damaged file) | *Couldn't open "Back yard.perma.geojson". The file may be damaged or from a newer version. Your other designs are fine.* · *Details* (the log path) |
| `src/controllers/persistence.py:208` | *Save failed* + the raw exception | *Couldn't save "Back yard". Your work is still open; try Save As… to a different folder.* |
| `src/controllers/generation.py:132-133` | *Couldn't generate a design:* + message | *Couldn't make a plan. Check that your yard outline or bed is closed, then try again.* |
| `src/app.py:2322` | *You have unsaved changes. Exit anyway?* | *Save changes to "Back yard" before closing?* · Save · Don't save · Cancel |
| `src/app.py:1842` | *Current design has unsaved changes. Discard and start new?* | ST-6's wording: *Discard unsaved changes to "Back yard" and start a new yard?* |
| `src/controllers/persistence.py:289-293` | *Restore autosaved design?* / *Site & Pattern closed without saving last time. An autosaved copy of "…" was recovered (last saved to: …). Restore it now?* | ST-8: *Site & Pattern closed without saving last time. Open the copy it kept of "Back yard"?* · Open it · Not now (kept) |
| Raw citation keys (R17), `src/food_page.py:376-380` | *globi_…* | `citations.format_sources(source, short=True)` ("Acorn & Sheldon 2006"), as the website does |

### 3.8 The printed plan and the order file

| Where | Now | Proposed |
|---|---|---|
| `src/pdf_export.py:313` | *… | Edmonton, Alberta* on every PDF | The place line from coverage (ED-5, EDF-2) |
| `src/pdf_export.py:458, 588`; `src/planting_plan.py:402` | *Alberta native plant / seed sources* | *Where to buy around Edmonton* (ED-4) |
| `src/on_this_design_panel.py:597` | *AB retail/install …* | *About $X–$Y at Edmonton native nurseries* |
| The PDF's pale text (R1) | `#a5d6a7`/`#c8e6c9` on white | the print palette's dark text (R1's fix) |
| *pioneer* on screen and in the PDF: `src/conversion_plan.py:163`, `src/planning_panel.py:814`, `src/snapshot_window.py:171` | *Plant pioneer species to hold the soil*; *pioneer forbs fill in first*; *faint plants are pioneers fading* | *Plant quick starters to hold the soil*; *the first wildflowers fill in, then give way*; *faint plants are the early ones giving way* |

## 4. Two lines that must appear

- **The ID line** (W3). On the plant page's *More about this plant* and in
  Help › About: *These photos help you choose plants. They are not a guide to
  identifying plants in the wild.* Recommended placement: those two places
  only, not on every page.
- **The not-known line.** A filter or a must-have that rests on partial data
  says so beside the control, once: *Most plants have not been checked for
  poison; this leaves out the ones known to be.* (R10, 07 Y6)

## 5. Work items

| ID | Item | Effort | Depends on |
|---|---|---|---|
| **WD-1** | **The glossary as a test.** `src/vocabulary.py` (Qt-free): the §2 table as data, `NEVER` and `ADVANCED_ONLY` word lists. `tests/test_vocabulary.py` reads every prose string (string constants with a space, excluding docstrings, log calls and SQL; found with `ast`, not regex) in `src/` for `NEVER`, and in the simple-surface modules (a list kept in the test, grown as MD-1 lands) for `ADVANCED_ONLY`, with an allowlist of path → reason. *Accept:* the test fails on today's tree with the list in §3 and passes after WD-2 to WD-6. A rough count today (prose strings, all of `src/`): *species* 179, *boundary* 90, *ecoregion* 68, *polyculture* 43, *keystone* 42, *forb* 31, *AI/LLM* 24, *pioneer* 6 | S | — |
| **WD-2** | **The strip and Site Info** (§3.1, §3.2), including the four lines and Details. *Accept:* Site Info shows four lines at 1366 × 768 with no sideways scroll (R8) | M | ED-6 for frost and zone; MD-1 |
| **WD-3** | **The plant list and page** (§3.3). | S | PR-3, PR-4 |
| **WD-4** | **Errors and confirmations** (§3.7), through `slot_errors`' logging. **Tests:** the damaged-file case shows the new text and no parser message; the exit prompt has three buttons. | S | — |
| **WD-5** | **The printed plan and order file** (§3.8). | S | ED-4, ED-5 |
| **WD-6** | **Retire *pioneer*** in the three places on screen and the PDF (§3.8), as `review.md` already requires. | S | — |
| **WD-7** | **Animals by English name** (§3.6): `what_it_feeds.eaters_line` and the overview name only animals with English names and count the rest. | S | OV-5 |
| **WD-8** | **The ID line and the not-known lines** (§4). | S | PR-4 |

## 6. Decisions for the owner

- **W1.** Accept the glossary (§2) as the contract for the simple app.
  Especially: *yard outline* for boundary, *bed* for Garden Bed, *plant* for
  species, and *community* kept (the owner's tab name) but *polyculture* never.
- **W2.** *Plan* for what Plan My Yard makes and what is printed, *design* for
  the file. Recommended: yes.
- **W3.** The ID line: on the plant page's *More* section and in About
  (recommended), on every plant page, or nowhere.
- **W4.** *Feeds a specialist*: reword (*Food for a fussy eater*) or move to
  Advanced (recommended: Advanced; the plant page already marks dependants
  with ⚑).
- **W5.** Site Info's four lines as §3.2 (recommended), or keep today's page
  for everyone.

## 7. What could not be checked

- The rough counts in WD-1 count prose-like string constants, which include
  some identifiers and SQL; WD-1's test does it properly with `ast`.
- The four Site Info lines were written from the data's fields, not rendered;
  the soil words ("dark, loamy") need a small mapping from the soil fields that
  has not been written.
- No homeowner has read any of this copy. 01 §6's sessions are where the
  glossary gets corrected: every word a tester does not understand goes into
  §2.
