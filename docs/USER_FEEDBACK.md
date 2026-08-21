# Site & Pattern — what users actually said

The record of feedback from real people using the app, **in their words**, with
what was done about it.

This document exists because the other three backlogs cannot do this job.
[`ROADMAP.md`](ROADMAP.md) is the historical effort/impact ledger,
[`ROADMAP_NEXT.md`](ROADMAP_NEXT.md) is the live plan, and
[`PHILOSOPHY_ROADMAP.md`](PHILOSOPHY_ROADMAP.md) is the principle-by-principle
lens — all three are the *author's* view of what matters. None of them records
evidence from outside. `ROADMAP_NEXT.md` is candid that the stated priority
"keeps losing to whatever is more interesting" across nine increments; a
user-voice document is the thing that argues back.

**Conventions.** Quote verbatim — paraphrasing feedback is how it gets
comfortable. Give every item a verdict, and be willing to write "already
existed" or "we disagree" when that is the truth. Link to where it landed.

**Verdicts:** 🐞 bug · 🕳 gap · ✨ feature · 🔍 existed but unfindable

---

## 2026-07 — first outside tester

A friend of the author test-drove the app and sent sixteen observations over two
messages. Ten were fixed in **V2.37**; the rest are recorded as features below.

The single most useful thing about this round: **most items were not missing
features.** They were working features with a dead control in front of them, a
legend buried on page 4 of a PDF that could not be produced, or a facet never
wired to data the app already parsed. That pattern is worth remembering — the
next round of feedback is likelier to be about *reach* than about capability.

### Fixed in V2.37

| # | What they said | Verdict | What it was |
|---|---|---|---|
| 1 | *"Using the quiz in the Learn tab crashes the app!"* | 🐞 | Real, and a hard abort. `new_quiz()` returned early on failure while leaving the previous question's buttons live, so the next click indexed an empty list — and an `IndexError` escaping a Qt slot calls `qFatal()`. Underneath it the quiz was firing 8 concurrent photo fetches at a metadata index with no lock and no atomic write: 40 concurrent writers kept **1 of 40** entries. |
| 2 | *"Ecoregions are currently not inclusive. If a plant lives in 2 ecoregions it doesn't show up in both but rather only 1."* | 🐞 | The data was always multi-valued and `search_plants` always ORed it; the community library collapsed it to the single most common token. Also `moist_mixedgrass` — the most common tag in the catalogue, on 246 plants — was missing from the label table and silently read "Generalist". |
| 3 | *"Row placement does not work on top of a boundary. It places all the plants on the one spot. This is true of all placement types including grid, circle, etc."* | 🐞 | The pattern committed as soon as it held two anchors, with no check they differed. Three separate ways a boundary produced a coincident pair — the loudest being an interactive area label sitting at the polygon centroid, exactly where you start a row. |
| 4 | *"The layers that you can see with view and also placement layers need a hierarchy... Boundary should be the very lowest level of hierarchy."* | 🕳 | The whole map had two named panes; everything else stacked by accident of `addTo()` order. Boundary now has its own pane at the bottom, and the stack is written down. |
| 5 | *"Selecting a plant or plant community... should be sufficient to then place that unit on the map... often I end up placing the wrong thing (the last thing) because I haven't hit the button."* | 🕳 | Arming was a separate act, so the map kept holding the previous choice. Selecting now arms; the button became a live "● Placing: …" chip. |
| 6 | *"The hierarchy of tabs needs to be made more clear... My friend was confused by the UI of the tabs and subtabs."* | 🕳 | Every level used the *sub*-tab stylesheet verbatim, and "Plants" was a tab label at all three nesting levels simultaneously. |
| 7 | *"In 3D preview, the walk the garden should be the first option, fly as creature should be second and choosing the creature should be 3rd."* | 🕳 | The strip opened by asking you to pick a bee before anything said why. Reordered. |
| 8 | *"Consider the use of L and R click within the 3D view... flip which rotates the screen and which moves it side to side."* | 🕳 | Stock OrbitControls defaults (the 3D-modelling convention). Now left pans, right rotates. |
| 9 | *"Gap months are shown for a design but there is no option to choose plants that flower or fruit a particular month."* | 🕳 | The parser, the data (428/434 plants) and even a bloom-month matcher all existed; `search_plants` had no month parameter. Two new facets. |
| 10 | *"A printable 2-d Map of a design with legend would go a long way."* | 🔍 + 🐞 | It shipped in V2.31 with a numbered key, scale bar and north arrow — **and PDF export had been raising `NameError` on every call since V2.33**, behind a test that skipped without PyQt6. Fixed, and the menu now names what is in the document. |
| 11 | *"Sunlight analysis needs work. It should show an icon of the sun moving along the arc of the day..."* | 🐞 + 🕳 | The tab already had a time-of-day slider **connected to nothing**. It now scrubs a real sun marker and shadow ray, and changing the date redraws in place instead of demanding another map click. |
| 12 | *"There needs to be a very easy straightforward way for users/test-users to send me feedback directly via the app."* | 🕳 | Nothing existed. `Help → Send Feedback…`, deliberately broader than a bug tracker. |

### Recorded, not yet built

| # | What they said | Where it went |
|---|---|---|
| 13 | *"A 'clippy' like helper (I would make it a fauna like a caterpillar or bird) that guides you through using the app and explains/breaks down certain things. For example Site Info is overwhelming to most beginner users and even long time landscape designers."* | **F85** — needs a glossary reachable from Python, a widget-anchoring concept, a beginner/expert flag and mascot art, none of which exist. Note ~12 of 20 Site Info metrics still have no explanation at all, while `climate.zone_description()` returns exactly the right sentence and is never called — that half is cheap and should go first. |
| 14 | *"Note taking should be more functional. There should be an option to make a note from any menu or on the design itself and have all these notes feed a master note doc that can use this info in a functional way rather than just a record."* | **F86** — there are five disconnected note stores today, and `field_notes.format_field_notes()` is called from nowhere. |
| 15 | *"Saving a file should be more simple and similar to how game files are saved and loaded... They should appear as a list of past save files and we can also include an example/test file/design."* | **Shipped V2.39.** A `saves/` folder beside the database, Save that stops asking where, and File → Open showing your designs with enough to tell them apart (name · when · plants · species · site). The crash-recovery autosave moved out of its hidden `$HOME` dotfile at the same time — nobody's mental model of where their work lives, and the one moment it matters is the moment a user is most upset. |
| 16 | *"Learn tab can include a range of topics from learn the app, learn landscape design/philosophy, learn about native flora and fauna. Can gamify this somewhat too."* | **F88** — a curriculum, not a patch. |
| — | *"This whole 3-D preview could use an UI and UX review."* | **F89** — ten buttons over two rows. `ROADMAP_NEXT.md` Theme F already prescribes an honest retirement pass before any restructure. |

### What this round changed about how we work

- **Tests that skip are not tests.** PDF export was broken for four minor
  versions behind a green suite, because `tests/test_pdf_export.py` skips
  without PyQt6 and the environment did not have it. Same story for the quiz
  widget, which had no tests at all. And `tests/test_pattern_placement.py` was
  running **zero** of its ~25 geometry cases, because they are module-level
  functions that `unittest` does not collect.
- **A dead control is worse than a missing one.** The sun slider and the
  never-applied right/wrong colouring in the quiz both taught users that a
  feature existed and did not work.
- **Silent fallbacks hide missing data.** `moist_mixedgrass` reading
  "Generalist" was a lookup-table default doing exactly what it was told.

---

## 2026-08 — second round, from testing the first round

The same tester went back through the app with V2.37 in hand and sent six more
observations. The shape of this round is different and worth naming: **half of
it is regression or bug, and one of the bugs is mine** — the auto-arm from
item 5 above read the placement pattern at *selection* time, so a count typed
afterwards was ignored. Shipping fixes creates its own feedback.

The other half is a data problem the first round had only glimpsed. Round 1
said ecoregions "are not inclusive"; the fix made the *filter* multi-valued,
which was true and insufficient — the underlying per-species tags were
generated heuristically and never sourced. Round 2 named a specific casualty.

### Fixed in V2.38

| # | What they said | Verdict | What it was |
|---|---|---|---|
| 17 | *"some plants are flying in the air rather than being on the ground lol."* | 🐞 | `terrainHeightAt` clamped the elevation grid's *indices* but not the interpolation *fractions*, so any point outside the fetched grid got a linear **extrapolation** instead of the nearest edge height: 2 m of fall over 100 m became 22 m of climb a kilometre out. One function; six callers fixed at once. |
| 18 | *"I manually increased the number using the arrows from auto to 11. When I placed it it was only 3 plants instead of 11."* | 🐞 | **My regression, V2.37.** `PlacementControlsWidget` emitted a signal for the pattern *kind* and for nothing else — count, rows, columns, stagger, drift and fill were silent. Harmless while "Place on Map" was pressed after setup; fatal once selection armed the map early. Every parameter now re-arms, debounced. |
| 19 | *"I want the full ecoregion name and below in smaller writing for the geographic area to be listed in brackets."* | 🕳 | The names were packed into one line and elided mid-word — "Moist Mixed Gras…ina (Saskatoon)" lost both the ecoregion *and* the place. Two-line items now, name first and whole. |
| 20 | Sun and shade should be one thing — raised again after testing V2.37, which had only done half of round 1's item 11: *"mix this with the shade so you can see the sun casting the shadows across the day"* | 🕳 | The arc and the cast shade were two tabs with two date pickers and two clocks, computing the same instant from the same module. Merged into **Analysis → Sun & Shade**: one date, one clock, and the arc now centres on your property instead of demanding a map click first. |

| 21 | *"Saskatoon Berry shows up for mixed grassland and moist mixed grassland but fails to show up for aspen parkland which it is a chief plant of."* | 🐞 | The tags were generated heuristically and never sourced — `moist_mixedgrass` on 246 plants and `aspen_parkland` on **136** in an Alberta-first app centred on Edmonton, with 39 native trees and shrubs carrying no parkland tag at all. Replaced by range **derived from georeferenced occurrence records**, each row carrying its count and a confidence band (schema v59/v60). 427 species now have a sourced range; Saskatoon Berry's parkland claim has 312 records behind it. |
| 22 | *"I'd prefer it breakdown into the individual ecoregions it exists in so when I add BC and other areas of turtle island we simply add more ecoregions."* | 🕳 | The vocabulary was a hard-coded list that had to be remembered separately from the shipped polygons. It **is** the polygon file now — add a region by adding a polygon and the filter, the validator, the habitat labels and the seeder all follow. Geography and moisture were also separated: `riparian`/`wet_meadow` are conditions, not places. |

### Still open

| # | What they said | Where it went |
|---|---|---|
| — | *"I'd like to have a start menu where the option to load a previous design or start a new one appears."* → *"I want an actual window to open (ahead of seeing the map)... I'm not seeing that."* → *"I would like a start up page to boot up as the first thing the user sees... This start/landing page will then direct the user to start a new design, load a previous design or explore the plant directory."* | **Shipped V2.40–V2.41, in three cuts, and the correction each time was the same shape: the previous cut had answered a smaller question than the one asked.** V2.40a gave the welcome dialog rows that appear only when they mean something. V2.40b moved it ahead of the map — the ordering, which is what "before the map loads" meant. V2.41 made it a landing page with a third door and built the room behind it (**F90**, below). Worth recording: the first two cuts were both *technically* responsive and both left the ask unfinished, because the visible half of a request is rarely the half that matters. |
| — | *"explore the plant directory (which we have not built yet but I think would be an excellent feature of a native plant education app and we have all the data)."* | **Shipped V2.41 as F90.** A browsable reference work over the whole catalogue, opened from the start screen with no design in existence: search, thirteen filters, and a species page carrying photo and credit, conditions, size, season, morphology in plain English, sourced range *with occurrence counts and confidence*, every documented animal with specialists flagged, companions, sourcing, safety, and where the numbers came from. Plus "Quiz me on these" over whatever you have filtered to. Almost entirely reuse — and it surfaced sixteen `search_plants` filters (keystone, larval host, specialist support, pet/child safety, price, commonness…) that had worked the whole time with no control attached to them. |
| — | *"I am on V2.41 and it is not showing up ahead of the map view... the box for it to not show up was not checked off."* | **Fixed in V2.41b, and the checkbox was innocent.** V2.31 wrote `onboarding/welcome_seen` itself the first time the welcome appeared, when the key meant "has been seen". V2.40 kept the key and redefined it as "asked not to see this again". Every install older than V2.40 therefore started with the screen switched off by a flag its owner never set, with no control able to turn it back on. New key, and the checkbox is now two-way. **A settings key's meaning is part of its contract**; changing it in place is a silent migration applied to everyone at once. |
| — | *"the UI (of this start menu) is pretty bad. I want you to reference the principles in Don't Make Me Think by Steve Krug."* | **Redesigned in V2.41b**, and written up as [`UI_PRINCIPLES.md`](UI_PRINCIPLES.md) so the next screen does not have to relearn it. Happy talk and instructions deleted; every row's second line became a fact about the user rather than a description of the button; real visual hierarchy; links that look like links. 682px to 509px with more information on it. The uncomfortable part: every one of those six mistakes was added in good faith to be helpful, which is the default failure mode of someone who knows the system well. |
| — | Feedback should reach the author by email, not only the clipboard | Blocked on a form-relay access key. The send path is written and tested against a stub, so dropping the key in is the last step. |

---

## 2026-08 — third round, from outside

A botanist with no connection to the project read **grownativeplants.ca** in
public and sent eight criticisms. This is the first feedback from someone who
was not a friend of the author, did not have the app, and knew the flora
better than the catalogue does.

*(Recorded without names, on the author's instruction. What was said matters;
who said it is not this file's business.)*

**The shape of this round is different from the first two, and worth naming.**
Rounds 1 and 2 were about the app: a dead control, a filter never wired to
data, a feature nobody could find. This round is about **claims**. Nothing was
broken. Every page rendered. What the reviewer did was read what the pages
*assert* and ask what stood behind each one — and behind most of it was an
inference that had been rendered as a fact, sometimes years earlier, by a
pipeline that had since changed underneath it.

Six of eight were hits. Two had a wrong premise with a right point underneath.
And checking them turned up **three faults the review only gestured at**, all
worse than the thing that prompted the look.

### Fixed in V2.75

| # | What they said | Verdict | What it was |
|---|---|---|---|
| 1 | *"So 'a range seen 3 times' actually means 3 observations in that ecozone, I think? The range of a plant species is normally the area in which it's documented to occur; using the word to mean other things is confusing. Defining terms and more of the study protocol would help."* | 🐞 | **They are quoting us.** `static_site_species.py` ended every range block with *"A range seen three times is not the same claim as one seen three hundred."* Our own sentence used *range* to mean one region entry. Rewritten, and the protocol they asked for is now a page: **`/method/`**, with the floor and the confidence bands imported from the module that owns them rather than typed. |
| 2 | *"Is there any concern about basing all the calculations on some undisclosed point-in-time of iNat data, while the iNat database is actually live and changing…? The currency of the data should at least be stated."* | 🐞 + 🔍 | Half right, and the half that was wrong does not help us. It is **GBIF**, which aggregates iNaturalist *plus* herbaria and museum collections — so identification is better than the question assumes and the snapshot problem is exactly as stated. The date **existed**: `plant_ecoregions.source` has carried *"GBIF occurrence search, retrieved 2026-08-18"* since schema v59, and the desktop app prints it. The website dropped it. It is now on all 421 species pages that have a sourced range, and every species links out to the live GBIF and iNaturalist maps, which are current where our snapshot never will be. |
| 3 | *"Listing # of observations in an ecozone doesn't explain where they are in the ecozone — are they scattered throughout a broad ecozone? In isolated outliers? Or is it, for another example, a mountain species that shows up in Aspen Parkland largely due to the stated 900 meter uncertainty…? (Some ecozone edges are probably more critical and may deserve more exactitude than others.)"* | 🐞 | **The best thing in the review, and understated.** The mechanism is real, the number is 5,000 m not 900, and the example is in our data. `ecoregion._NEAR_BOUNDARY_M` is a proximity buffer written in V2.67 to answer *which ecoregion is this yard in* — correct for a garden near an edge — and `ranges_for_species` inherited it by defaulting its lookup. Over 4,000 random points inside the layer, **16.4% are credited to two or more ecoregions**. *Aster alpinus*, a montane species, carries 72 Aspen Parkland records. Derivation is now containment-only; site detection keeps its buffer, because there the second answer is the point. |
| 4 | *"The site says, 'Where things grow: Pick a region to see the plants recorded there…' What is shaded is ecozones, not plant ranges. They are not necessarily the same thing."* | 🐞 | Correct. The fill is whole-polygon: three records in a 100,000 km² region shade all of it, one lightness step off three hundred. The home page no longer promises *"where that plant has been found"*, and every range block now says the region is shaded whole, that this is the resolution of the evidence, and that **unshaded means uncollected, not absent**. |
| 5 | *"Why are <9 observations in an ecozone excluded? This would exclude certain rare species."* | 🕳 | The number is wrong — the floor is **3**, and 8 is where the *medium* band starts — but neither figure appeared anywhere a reader could find, which is why the question had to be guessed at. Both are on `/method/` now, along with the cost they name: the plants with fewest records are often the ones that matter most, and `dropped_regions()` has been counting the near-misses on every run without publishing them. |
| 6 | *"In a cursory review of only the plant-related info, I found a lot of errors: Many species said to be native to 'AB, SK' are only native in one or the other; Helianthus giganteus is an eastern species, not native in either province."* | 🐞 | **Both true, and the first is worse than a scatter of wrong rows.** `native_provinces` is *generated* — `tag_prairie_provenance.py` derives the SK half from the plant's ecoregion tags, and its own docstring says so. 355 of 431 rows said exactly `"AB,SK"`. Then V2.72/73 replaced the ecoregion vocabulary underneath it: a re-run at V2.75 would have moved **237 of 431 species**, so the published field was the output of a routine that would no longer produce it. Retired rather than repaired, with a gate that fails on any future drift. *Helianthus giganteus* is gone (430 species, 7,580 edges). |
| 6b | *"A great many plant species are categorized under the wrong flower colour… even where it's said this is 'unchecked', one would expect this to be really basic info."* | 🕳 + 🐞 | Fair, and known: 351 of 431 colours are a genus-level default, documented in `DATA_GAPS.md` with a contact-sheet tool for working the backlog. One real bug though: **81 grass and sedge pages read "not verified"**, because the site re-derived the provenance mark instead of reading the one the entry handed it — and a grass has no showy flower to have got wrong. The desktop had said so since V2.48. |
| 8 | *"'Prairie provinces' usually includes MB and some of the same ecozones extend through SW MB. It's odd that it's not included?"* | 🕳 | Scope is one line: `SUBJECT_PROVINCES = ("Alberta", "Saskatchewan")`. What could not be defended is that the site offered a **Manitoba filter chip backed by exactly one species**, promising a coverage that does not exist. Removed, said plainly, and a backlog row opened for doing it properly. |

### Recorded, not yet built

| # | What they said | Where it went |
|---|---|---|
| 6c | *"A lot of species are listed using out-of-date names (e.g.: the Old World species, instead of the separate North American species)."* | **Correct, and the catalogue has no way to know.** There is no authority field, no synonym list and no taxon key anywhere: a scientific name is a free string checked by one regex. Confirmed cases in `DATA_GAPS.md` — `Achillea millefolium` shipped *beside its own segregate* `Achillea borealis`, both claiming AB,SK; `Fragaria vesca`, `Prunella vulgaris` and `Juniperus communis` as bare Eurasian binomials with no infraspecific rank; `Deschampsia caespitosa` where FNA and POWO use `cespitosa`. What the catalogue *did* get right is the genus-level work: Aster→Symphyotrichum, Polygonum→Persicaria, Zigadenus→Anticlea are all done, and `Pulsatilla nuttalliana` is the correct North American name. Renaming moves plant ids, edge keys and public URLs, so it is its own increment. |
| 7 | *"Up-to-date taxonomy/species names can be found and compared at various places: VASCAN, Vascular Flora of AB (Kershaw & Allen), the CDC vascular plant lists for AB and SK… Up-to-date range maps for AB can be seen at Vascular Flora of AB: Maps & Illustrations."* | **The fix for items 6 and 6c, and the machinery shipped in V2.75.** VASCAN answers both at once: `establishmentMeans` **per province** and an accepted-name/synonym backbone, in one request per species. `scripts/fetch_flora_nativity.py` + `scripts/ingest_flora_nativity.py` are written and tested; both need egress this container does not have, so the fetch runs on the author's machine and the ingest **reports rather than applies**. |
| 2b | *"It is possible to link iNat species observation maps as a proxy for range maps?"* | **Half shipped, half a decision.** Every species page now links out to GBIF and iNaturalist, which is the free half and answers the currency question permanently. Plotting the points *on our own map* is written (`scripts/plot_occurrences.py`, over the point cache the seeder now keeps) and is **not published**, on two grounds neither of which is effort: GBIF records carry per-record licences, and iNaturalist obscures coordinates for rare and collectible taxa so that publishing them does not lead a collector to the plant. Worth recording the irony — the rare species item 5 rightly says the floor under-serves are the same ones whose coordinates must stay coarse. |
| — | *"All of these errors would make me question the integrity of the data sources (and maybe prompt a review the project design/intent)."* | **Taken as the summary it is.** The three worst findings of V2.75 were not on the list above; they were found by checking the list. The nativity generator frozen against a dead vocabulary, 303 of 430 gate warnings being the gate arguing with the same release that shipped the data, and two published pages both titled *Stiff Goldenrod* making opposite claims about one taxon — known since V2.69, left as "a data decision", with no check that could fail on it. |

### What this round changed about how we work

- **An outside expert found in one reading what four increments of internal
  measurement had not** — because they read the *claims* and we kept reading
  the code. Every fact they asked for existed in the repo already.
- **A generated field must not outlive its generator's inputs.** The nativity
  heuristic was honest, documented and correct when written. It became false
  silently, two releases later, because something else moved. There is now a
  gate for exactly that.
- **A gate that is 70% noise is not a gate.** 303 of 430 warnings were one
  stale check shouting, and it had buried a real contradiction between two
  published pages for six releases.
- **Understating confidence is also a false claim.** `DESIGN_PHILOSOPHY.md`
  spent a whole increment saying the region outlines were "hand-drawn boxes"
  after they had become surveyed polygons. It sounds humble, which is exactly
  why nobody re-read it.
