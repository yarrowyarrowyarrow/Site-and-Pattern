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
| 15 | *"Saving a file should be more simple and similar to how game files are saved and loaded... They should appear as a list of past save files and we can also include an example/test file/design."* | **F87** — the precedent exists: the worked example already auto-saves to the data dir and opens with no file dialog. |
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
