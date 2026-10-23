# A second round of test use, at V3.37

*Asked for by the owner on 23 October 2026: "another round of test use of the
actual app. Do all features work? Is the app simple and intuitive? Is there
anything that is overly wordy or cumbersome in a way that does not serve the
goal of the app?" No code was changed. The first round is
[`SALE_READINESS_REVIEW.md`](SALE_READINESS_REVIEW.md) (V3.17, R-numbers);
findings here carry **U-numbers** so the two cannot be confused. When one is
scheduled, take its F-number from the ledger in `ROADMAP_NEXT.md`.*

## How this was tested

| What | How | Result |
|---|---|---|
| Test suite | `scripts/run_tests.py --exclude tests.test_undo_redo --max-skips 25`, with PyQt6, WebEngine, rasterio, pyproj | **5,301 tests, 0 failed, 15 skipped** (Blender, WebGL, NSIS, root) |
| Every button | `scripts/surface_inventory.py --click --windows --dialogs`, `--mode simple` and `--mode advanced`, 1366 × 768, Liberation Sans (Arial metrics) | simple: 16 pages, 82 controls, 49 clicked; advanced: 27 pages, 164 controls, 100 clicked. **0 errors in either.** The "no visible effect" buttons are the site-walk tick boxes, Find with nothing typed, slope switches with no terrain (offline), and Reset to Year 0 at Year 0 |
| A first-time homeowner | `python main.py` on a fresh profile under Xvfb + openbox at 1366 × 768, driven with real clicks and typing, every step photographed: the seven tasks of `homeowner/01-personas.md` §6 in order, then Try another, About this plan, re-plan, Undo/Redo, close and reopen | All seven tasks *can* be completed. The findings below are what got in the way |
| Root causes | Code reading, the saved design file, the shipped database, and a throwaway headless probe built on `html/boundary_probe.html` | Named per finding |

**Could not be tested here:** anything online except the canopy-height map
(map tiles, address search, OSM buildings, live weather and soil were all
blocked, so this was again an offline run); the 3D views (no WebGL); a real
Windows laptop (U4 and U5 are inferred from the code and the installer
script, and need checking there); printing on paper; real people.

---

## Short answer

1. **Do all features work?** At the button level, yes: nothing crashed and
   nothing raised. In use, no: four bugs sit on the simple app's main path,
   and the tests miss them because they hand Python what the map *would*
   send instead of clicking the map. The worst is U1: once you draw a bed,
   you cannot click, drag or right-click a plant in it, and a right-click
   deletes the bed.
2. **Simple and intuitive?** Much better than at V3.17. The start screen,
   the four-line Site Info, the Plan my yard dialog, the Overview, the plant
   page, the Swap dialog, the save prompt and the close prompt are all plain
   and short. What remains is the map's behaviour (U1, U3, U6), the window not
   fitting the target laptop (U4), and several messages that send a person to
   controls the simple app hides (U16 to U19).
3. **Wordy or cumbersome?** A handful, listed under *Words*: the scan result
   is a log, three of the Overview's six follow-up buttons silently switch the
   whole app to Advanced tools, and Draw › Shape asks five questions where one
   matters. The bigger problem is not words but **numbers a homeowner would
   act on that are wrong**: 246–510 hours of work in the first year for a
   95 m² bed (U8), and "Leave out plants known to spread" leaving out 12 of
   424 plants, so the plan chose 32 Fireweed and 41 Late Goldenrod (U7).

---

## Broken: fix these first

**U1. A plant inside a drawn bed cannot be clicked; right-clicking it deletes
the bed.** Draw › Shape › Garden Bed, then Plan my yard (the simple app's main
path). Clicking any plant in the bed selects the *bed* (its corner handles and
"Click to edit outline · right-click to remove"); no plant page opens.
Right-clicking a plant (its own tooltip says "Right-click for options")
removes the bed at once, with no question and no message. A plant whose circle
reaches past the bed's edge opens its page when clicked *outside* the bed.
Reproduced after a fresh open, so it does not depend on drawing order.
*Cause:* Leaflet's own stylesheet stacks every SVG above every canvas in a
pane (`html/vendor/leaflet/leaflet.css:116-117`: canvas z-index 100, svg 200).
Shapes are SVG; the plants are one canvas (`canvasRenderer`, 04-tools.js), so a
shape is always on top. `tests/test_boundary_press.py`'s probe puts the shed
*beside* the plant, never under it, so nothing caught it. *Direction:* give the
plants' canvas its own pane above `overlayPane` and route shape presses through
the map, as V3.11 did for the boundary (`boundaryClicked`); add "a plant on a
bed" to the probe, for click, right-click and drag.

**U2. Swap turns the swapped plants into hand-placed ones, so a re-plan
stacks a second planting on top.** Swap Fireweed (32) for Wild Bergamot, then
Plan my yard again: the dialog says "Your last plan (134 plants) will be
replaced" (it was 166), and afterwards the design holds **198 plants**, the new
166 plus the 32 Bergamot sitting on them, while the strip says "Your plan: 166
plants". Try another adds its plan to the same 32. *Cause:*
`yard_overview_dialogs.replace` (`src/yard_overview_dialogs.py:199-200`)
re-adds each plant with only its id, name and position, dropping `plan_run`,
`why_here`, `placement_group_id` and `planted_year`. The plant page's "Why
here" goes with them.

**U3. Every Undo, Redo and Swap re-runs "a pin was dropped".** After each one
the side panel jumps to Site › Site Info, the plant page closes, the status
reads "Site data ready", and the log shows the site data fetched again (five
requests: reverse address lookup, elevation, two weather archives, soil).
*Cause:* the restore path re-places the pin
(`src/controllers/persistence.py:693`), the page's `placeSitePin` always calls
`bridge.onSitePinPlaced` (`html/map/06-overlays.js:1230`), and
`_on_site_pin_placed` (`src/controllers/map_events.py:761`) treats it as a new
pin: `show_panel(site_panel.info_page)`, a fetch, `_mark_modified`. Undo and
Redo themselves still work (checked: one Ctrl+Z undoes a swap, Ctrl+Shift+Z
brings it back). On a connection this is a reverse geocode to Nominatim on
every undo, which its usage policy does not want.

**U4. The window opens at 1400 × 860 whatever the screen, and does not
remember being maximised.** On the usability sessions' laptop (1366 × 768,
`homeowner/01-personas.md` §6) the right 34 px and bottom 92 px are off
screen: the Find button reads "Fin", Clear pin and the Share tab are cut, and
the close and maximise buttons are past the edge. Maximising fixes it until
the next launch. *Cause:* `self.resize(1400, 860)` (`src/app.py:110`), no
`availableGeometry` check, no `saveGeometry`. Every test resizes the window to
1366 × 768 first, which is why none saw it. Seen under X11; Windows should be
checked on the laptop, but Qt does not shrink a window to the screen there
either.

**U5. The exports start in the program's folder, with generic names.** Export
PDF opens on `design.pdf` in the working directory; the planting plan on
`planting_plan.txt`, the order file on `plant-order.csv`
(`src/app.py:2033` and `:2060`, `src/order_file_flow.py:29`). The Windows
installer creates its shortcuts right after `SetOutPath "$INSTDIR"`
(`scripts/packaging/installer.nsi:180-202`), so the working directory is
`C:\Program Files\Site & Pattern`, which a normal user cannot write to:
pressing Save as offered should fail, and the failure is shown as
`str(exc)` ("[Errno 13] Permission denied…"), against the V3.18 rule for
messages. *Not verified on Windows.* Default to Documents (or the saves folder)
and the design's name. Separately, after a successful PDF export nothing on
screen says where it went once the 3-second status line is gone.

**U6. One plant dragged moves the whole plan.** The first click on any planned
plant arms "Move: whole grouping (166 plants) — click to narrow"; dragging a
shrub 1 m moved all 166, out of the bed and past the outline. Undo restores it.
For a generated plan, the whole group is the wrong default for a first drag.

---

## Wrong or misleading: trust

**U7. "Leave out plants known to spread" leaves out 12 plants.** In the
shipped database 408 of 424 plants have no `spread_habit`; 10 are
`aggressive_rhizomatous`, 2 `self_seeding`. With the box ticked, the first plan
for a front-yard bed chose **32 Fireweed** and Chokecherry; *Try another*
chose **41 Late Goldenrod** and **4 Wild Raspberry**. Canada Goldenrod is
marked aggressive and Late Goldenrod is not. The PDF's Phase 3 then calls Wild
Bergamot and Wild Strawberry "self-spreaders". This is R11 from the first
review: the box's wording became honest ("known to"), the plan did not change.
It needs a reviewed spread habit for the plants the generator actually picks
(the owner's call, with sources); until then the box over-promises.

**U8. The work estimate is several times too high, and grows with density.**
"First year: 246–510 hours of work" for one 95 m² front bed, 37–76 hours a year
once filled in. That is 12–25 hours a week through a growing season. *Cause:*
`maintenance_calendar.PLANT_MAINTENANCE_HOURS` is per plant (a wildflower
1.5 h/year, doubled in year 1), so 97 wildflowers and 65 strawberries give
~378 h ± 35%. Weeding scales with ground, not plant count, and a denser
planting is *less* work, not more. The model needs to be area-based or capped;
which figures to use is the owner's call.

**U9. False precision, and two figures for one thing.** The Overview and the
PDF say "$1,406–$2,847" and mulch "$166–$571" where the dialog said
"$1,400–$3,000" (P9: ranges, never false precision). The PDF's first page says
"5–8 m³" of mulch; its Site Prep page says "4.8–7.6 m³".

**U10. Wild Vetch is filed as a tree or shrub.** PDF: under "Native trees &
shrubs", "Phase 1 — Structure (trees & shrubs)", and "Shrubs and young trees
(Pin Cherry, Chokecherry, Pussy Willow, Wild Vetch) close in". It is a vine.

**U11. "Easy to buy around Edmonton" against "on no Edmonton list".** With the
box ticked, the plan's Chokecherry page says "Not on any Edmonton native-plant
nursery list on file"; the order file files the same plant under "Widely sold".
Three words for one plant's availability.

**U12. Plant choices a homeowner would question.** 31 Purple-stemmed (Swamp)
Aster (water: medium–high) and a Pussy Willow in a dry-loam front bed; no
grass in either plan, because a front yard gets no "meadow"
(`street_band`) and grasses rank low on impact. Grasses are what hold a native
bed together and keep weeds out; whether a front yard should have none is a
question for the owner, not a bug.

**U13. Shrubs hang over the yard outline.** The Chokecherry (4.5 m wide) and
Pussy Willow sit at the bed's west edge; their circles cross the property
line onto the neighbour's side.

**U14. The plant list's first rows.** Placement › Plants, *Best picks first*:
Joe-Pye Weed, Chokecherry, Fireweed, **Creeping Spikerush** (a wetland plant),
Pussy Willow, Swamp Aster…, with three willows in the top dozen. Close to R22.
Three filter chips are on that the person never set ("Restoring toward Aspen
Parkland", "Native around Edmonton", "Your soil: pH 6.5").

**U15.** The Overview says "In flower from March to October" over a month row
that starts in April (`yard_overview_items.STRIP` is April–October).

---

## Words, and controls that are not there

**U16. Site › Features.** The intro mentions "the margin below" (hidden in the
simple app) and "The shade is only as real as these". The scan's result is a
~70-word log ("Read the 1 m canopy-height map; found 0 trees taller than 2 m;
kept 0 (0 inside your boundary + 0 neighbours within 30 m); added 0 new…") that
ends "lower the height threshold, or mark trees by hand below": neither exists
in the simple app. Say what was found, and one thing to do.

**U17. Site › Sun & Shade** says "import or draw them on Site → Features", and
there is nothing to draw with there; it also shows an Opacity slider and
"Classify planting zones".

**U18. The address search's failure messages** say click "Use Pin Drop…"
(`src/site_panel.py:2578` and `:2586`); the button is "Click my yard on the
map".

**U19. Draw › Shape in the simple app** asks Type, Label, Fill colour, Outline
colour, Opacity (0.25), Line style and "Casts shade, height". Only Type matters
to a homeowner. There is no House or Building type, so offline (or where
OpenStreetMap has no footprint) the house cannot be marked at all. The list
ends with "Restoration — Year 1", "Restoration — Year 3", "Established native",
"Existing remnant"; the status-bar tip promises "a hedge, fence or windbreak",
which the simple list does not offer.

**U20. The getting-started strip.** At 1366 px step 2's instruction is cut to
"Click around your…", losing "Click the first point again to finish". And
clicking around the yard on the map, as it says, does nothing: the Boundary
tool must be chosen first (the chip does it).

**U21. Three Overview buttons switch on the whole of Advanced tools.** "See
who it feeds ▸", "See what flowers when ▸" and "See the hours ▸"
(`advanced:food`, `advanced:over_time`). The toolbar doubles, a Learn tab
appears, the Design strip grows to seven tabs cut to "Overvi…", "Report c…",
"Plan…", "Habi…", "Fo…", and the hours asked for are below the fold. Only a
status-bar line says what happened. Turning it off lands on Planted, not the
Overview. Show the answer where it was asked (a small window or an expanding
section) and leave the mode alone.

**U22. On a bed, the map's colours do not match the legend.** A wildflower's
purple at 35% opacity over the bed's green mixes to grey (sampled rgb
159,166,164); the legend shows solid purple and has no grey.

**U23. The printed planting map cannot be dug from.** It is scaled to the
whole 15 × 40 m outline, so the 95 m² bed is a strip about 4 cm tall at the
foot of the page; circles overlap, most numbers are hidden, the bed's own
outline is not drawn and the four woody plants cannot be picked out. Fit it to
the planted area.

**U24. Small things.** The offline notice sits over the bottom of the map,
which is where a front bed is; "Location: (custom pin)"; "Boundary added
(green)"; "Site data ready." in the warning amber; Share has a strip with one
tab; the start screen's "In flower around Edmonton" line is missing on the
very first launch (the database is made after the start screen) and ends
"and 1 more"; the File menu and Share name the three exports differently.

---

## What works well (keep it)

- The start screen, both times: one obvious door, and next week the design is
  the highlighted row ("Strathcona front yard · just now").
- Site Info's four lines (Where, Cold, Rain, Soil), each saying when a figure
  is regional.
- The pin zooms the map to the yard; the outline shows its sides and area.
- Plan my yard's dialog: plain questions, a cost range, sensible defaults, and
  "Your last plan … will be replaced. Plants you placed yourself stay."
- The plan strip (Try another · About this plan · Undo) and About this plan's
  five lines.
- The Overview: six items, a status word each, one action each, under 300
  words.
- The plant page: a flowering photo with its credit, why this plant, good to
  know, growing it, the season bar, buying it, in about a hundred words.
- The Swap dialog: three alternatives with bloom months and price, and "Undo
  puts them back".
- The close prompt (Save · Don't save · Cancel) and the first-save name box.
- The PDF's prose: site prep in job order, "do NOT enrich", "cut back in
  spring, not fall", the site-walk sheet.

---

## Suggested order

1. **U1, U2, U3** (the map and the plan on the main path), with probe and
   window tests that press the real page.
2. **U4, U5** (the window and the exports), checked on the Windows laptop
   before the usability sessions.
3. **U7, U8** need the owner's decisions (which spread habits and which hour
   figures to trust) before code.
4. The words, U16 to U21, as one pass.
