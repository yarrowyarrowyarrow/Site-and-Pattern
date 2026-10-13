# 2 · Two ways to use it: simple by default, advanced on request

*Part of the [homeowner-path plan](README.md). Work items **MD-1 to MD-5**;
owner decisions **M1 to M4** ([12-decisions.md](12-decisions.md)). Which
feature goes where is ranked in [03-what-goes.md](03-what-goes.md); this part
is the mechanism and its rules.*

The owner: *"I also agree about the advanced features not muddying the waters
of what a novice sees so possibly 2 ways to interact with the app."*

## 1. The idea in one sentence

**Everyone starts in the simple app; the advanced tools are one remembered
switch away (View → Advanced tools), and nothing a person has made ever
disappears when the switch is off.**

The simple app is the homeowner's path: where is your yard, what is it like,
what should go where, how is it doing, what do I buy and do. Everything else,
the terrain analysis, the wind tools, the 3D windows, the in-depth habitat
analysis, the per-animal food pages, the presentation tools, stays in the app
for the people who want it, behind the switch.

## 2. Why this is not the toggle V2.42 argued against

`src/app_mode.py:27-41` quotes V2.42's plan:

> **What I would not do:** ship a top-level Design/Learn toggle that hides half
> the app. … A mode split that makes a beginner choose "am I designing or
> learning?" before they have a yard drawn asks a question they cannot answer
> yet. ([V2.42 plan](../plans/V2.42-first-user-on-the-relationship-web.md))

That objection is right, and the switch proposed here is built to avoid it:

1. **Nobody is asked to choose.** Simple is the default. There is no question
   on the start screen, no toolbar toggle, no first-run dialog. Advanced is a
   menu item for whoever goes looking, plus "More detail ▸" links on the
   overview (MD-4) for whoever wants to dig into one thing.
2. **It hides tools, never the person's work.** Anything already in the design
   (contours, measurements, structures, shapes, hedgerows, notes, an imported
   scan, a yard photo) still draws on the map, can be selected, moved, deleted
   and undone, and is printed, with the switch off.
3. **A design that uses advanced tools says so.** Opening one in simple mode
   shows one line above the map: `This design uses advanced tools.` with a link
   `Show them` that turns the switch on (MD-3).
4. **Switching is lossless.** It changes nothing in the file, the undo stack or
   the map; switching back and forth is free.
5. **It is progressive disclosure, not modes.** The same window, the same
   tabs where they exist, the same files. The switch only decides which tools
   are offered.

The V2.43 front-door split (Learn and Design as two doors at boot) is a
different thing, and [04-start-screen.md](04-start-screen.md) recommends
retiring it (ST-10). If it goes, `app_mode.py` goes with it, and the increment's
plan file records the reversal so it reads as a decision.

## 3. What each way shows

This is the target. [03-what-goes.md](03-what-goes.md) ranks every feature
with its cost, and some features there are recommended for deletion rather
than for the advanced side; where they disagree, 03 wins.

### 3.1 The side panel

| Tab | Simple | Advanced adds |
|---|---|---|
| **Site** | **Site Info**, rewritten as four plain lines with Details below ([09-words.md](09-words.md)); **Sun & Shade**, reduced to "which parts of my yard are sunny" (the planting-zone classification and *Scan this area* for buildings and trees, see [07-plan-my-yard.md](07-plan-my-yard.md)); **Notes** (the printable site walk and the journal) | Slope (contours, slope ramp, water flow, LiDAR), Wind, Features (imports, nDSM, satellite alignment, drawing existing trees and buildings by hand), Sun & Shade's sun-path and shadow-arrow controls |
| **Placement** | **Plants** (ranked, [05](05-plants-that-lead.md)), **Communities** (the ready-made plant groups, ranked, with readable names), **Structures** (bee hotel, brush pile, small pond: they score and they are easy) | The plant mix and community mix builders, the community builder (New, Edit, Variation, Import, Export), the creature picker, placing patterns beyond Single and Fill area (Row, Grid, Circle) |
| **Design** | **Overview** (one page, at most six items: [06-yard-overview.md](06-yard-overview.md)), **Planted** (what is in the design) | Report card in full, Habitat (score breakdown, relationship web, pull-a-plant, chickadee brood), Food (one animal, month by month), Over time's year slider and phased plan, Water |
| **Share** | **Export** (the PDF, the planting plan, the order file) and **Where to buy** | Present (the narrated tour), Growth Snapshots, the presentation still, before/after |
| **Learn** | — (the tab is hidden; see [03](03-what-goes.md) for whether it stays at all) | Field Study, Lessons, if kept |

### 3.2 The toolbar rows and the menus

| Where | Simple | Advanced adds |
|---|---|---|
| Draw row | Boundary, Shape (beds and paths), Select, Undo, Redo, Cancel | Measure, Note on the map |
| View row | Satellite, Plants | Boundary and Measurement layer switches, Grid, Canopy, Structures layer, Yard photo |
| File | New, Open…, Save, Save As…, Rename Design… (ST-7), Plan My Yard… ([07](07-plan-my-yard.md)), Export PDF…, Export Planting Plan…, Export order file…, Exit | Import Yard Scan… |
| View | Show Side Panel, Getting-started strip, North Arrow, Scale Bar, **Advanced tools** (the switch) | Split view, 3D Preview…, Plant Directory…, Walk a Wild Landscape…, Growth Snapshots…, Scale Units, Map Settings… |
| Help | Start Screen…, Open the Example Yard, Keyboard Shortcuts…, Send Feedback…, Where This Data Came From…, About / Version, Check for Updates…, Support this app… ([10-finishing.md](10-finishing.md)) | — (*Switch to a specific version…* is removed from the product, not moved: [03](03-what-goes.md)) |

**An edge case to decide (decision M2):** the 3D preview. It is the most
striking thing in the app (P13: beauty is how a native planting survives), but
it needs WebGL, which fails on some graphics drivers (backlog F211), and its
toolbar is the busiest window in the app. Recommendation: advanced, with one
plain entry point in simple mode on the overview ("See it grow in 3D ▸") that
turns the switch on and opens the preview.

### 3.3 The plant page and the plant list

Two modes of the same page and the same rows: [05-plants-that-lead.md](05-plants-that-lead.md)
§7 (page) and PR-3 (rows).

## 4. How it is built

### 4.1 One switch, one registry

- **`src/advanced_tools.py`** (new, Qt-free): `is_on() -> bool` and
  `set_on(bool)` over a QSettings key (`ui/advanced_tools`, default `False`),
  plus a **registry**: `ADVANCED_PAGES`, `ADVANCED_ACTIONS` and
  `ADVANCED_TOOLBAR_ITEMS`, each a tuple of stable names (an attribute path
  such as `"site_panel.slope_page"`, or an action's object name). One table,
  read by the code that applies it and by the tests that check it.
- **`src/advanced_tools_flow.py`** (new): `apply(main)` walks the registry and
  hides or shows each page with `QTabWidget.setTabVisible` (pages are already
  moved by widget, never by index: `side_panel_layout.py`'s rule), each action
  with `setVisible`, each toolbar item with its action's visibility. Called
  once after `side_panel_layout.arrange` and again whenever the switch
  changes. **Address pages by their widget**, as `keyboard_help.show_panel`
  does; never by index.
- **View → Advanced tools**, a checkable action wired from `app.py` to the flow
  through a lambda, so `MainWindow`'s method count does not grow (the ceiling in
  `tests/test_architecture_guard.py`).
- **A tab strip with nothing visible is hidden** (the Learn tab in simple
  mode), and a strip whose current page is hidden moves to its first visible
  page.

### 4.2 Things that must keep working

- **Keyboard and screen reader** (V3.02): a hidden page drops out of the tab
  chain; F6 still moves between the map and the panel; the single-letter map
  keys for advanced tools (Measure, Note) do nothing in simple mode rather than
  arming a hidden tool (`keyboard_help.MAP_LETTERS`).
- **Pointers in the app's own words.** Text such as "Placement → Plants" is
  read against the real window by `tests/test_app_smoke.py` (V3.05). A pointer
  to an advanced page must either be reworded or carry "(advanced)", and the
  test must run in both modes.
- **Live refresh** (`src/live_refresh.py`) computes only pages on screen; a
  hidden page costs nothing, which is the existing behaviour.
- **Undo** is untouched: no snapshot records the switch.

## 5. Work items

| ID | Item | Effort | Depends on |
|---|---|---|---|
| **MD-1** | **The switch and its registry.** `src/advanced_tools.py` and `src/advanced_tools_flow.py` (§4.1); View → Advanced tools; `apply(main)` after `side_panel_layout.arrange` (`src/side_panel_layout.py:144`) and on toggle; the registry filled from §3 as amended by [03](03-what-goes.md). Tests: a new `tests/test_advanced_tools.py`: with the switch off, every registered page's tab is not visible and every registered action is hidden; on, all are visible; toggling twice leaves `main._project` byte-identical and the undo stack unchanged; the setting survives a restart (QSettings in a temp dir); a strip with no visible page is hidden. *Accept:* cold start shows only the simple surfaces of §3; View → Advanced tools shows everything that exists today; turning it off again hides them without changing the design | M | M1 |
| **MD-2** | **Every existing guard runs in both modes.** `tests/test_app_smoke.py`'s walks (every tab, the pointer check, the keyboard chain, the visual floors) iterate over both settings; `scripts/surface_inventory.py` gains `--mode simple|advanced` and the surface audit's numbers are re-measured for simple mode. *Accept:* the smoke suite passes in both modes; the inventory reports the simple app's page and control counts (target: fewer than half of today's 156 controls) | S | MD-1 |
| **MD-3** | **"This design uses advanced tools."** A Qt-free `uses_advanced(project) -> list[str]` (contours, measurements, map notes, hedgerows, custom shapes other than beds and paths, imported scans, a yard or site photo, wind overlays); in simple mode, a one-line bar above the map (the pattern of `src/landing_check.py`'s bar) reading `This design uses advanced tools.` with `Show them`, which turns the switch on. Tests: the detector on fixture projects; the bar appears only in simple mode and only when the list is non-empty. *Accept:* open a design with contours in simple mode: the contours draw, the bar shows, and "Show them" turns on advanced tools and opens the Slope page | S | MD-1 |
| **MD-4** | **"More detail ▸" from the overview.** Each overview item ([06](06-yard-overview.md)) may carry a link to the advanced page that explains it (the habitat score to Habitat, wildlife to Food, hours to Over time); following it turns the switch on and shows that page by widget (`keyboard_help.show_panel`), with a status line `Advanced tools are on. View → Advanced tools turns them off.` *Accept:* each link lands on the right page with the switch on; the status line appears once per session | S | MD-1, OV-1 |
| **MD-5** | **Pointers and help text follow the mode.** Every "A → B" pointer in the source that names an advanced page is rewritten or marked "(advanced)"; the getting-started strip's steps and Help → Keyboard Shortcuts name only what the current mode offers. *Accept:* the pointer test passes in both modes; no simple-mode text points at a hidden page | S | MD-1 |

## 6. Decisions

- **M1.** Accept "simple by default, one remembered switch" (recommended), or
  ask on first run, or offer it on the start screen.
- **M2.** The 3D preview: advanced with one plain entry on the overview
  (recommended), simple for everyone, or advanced only.
- **M3.** The switch's name: *Advanced tools* (recommended), *More tools*,
  *Expert mode*.
- **M4.** Whether the Learn tab survives at all (see [03](03-what-goes.md) and
  decisions S2 and S3).
