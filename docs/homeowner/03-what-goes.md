# 3 · What goes, what hides, what gets simpler

*Part of the [homeowner-path plan](README.md). Work items **RM-1 to RM-9**;
owner decisions **G1 to G6** ([12-decisions.md](12-decisions.md)). The switch
that hides advanced tools is MD-1 ([02-two-ways-to-use-it.md](02-two-ways-to-use-it.md));
where this part and 02 disagree, this part wins.*

The owner: *"perhaps it needs to be refined… ranking which features or aspects
to remove or simplify"*, and *"I do agree about those 'not for a paying
customer at all' features that can be slated for removal."* And the goal behind
both: *"reach a place that I can move on to other projects rather than
ceaselessly working at this."*

## In one paragraph

Very little needs **deleting**. Four things do: Help › *Switch to a specific
version…*, File › *Import Yard Scan…* with its yard-photo layer, the Learn door
on the start screen with the window behind it, and a dead recipes module. The
local AI leaves the app but stays in the command line. These were the "not for a
paying customer" column of the first review, and the owner agreed. Most of the
rest of what makes the app busy is good work aimed at someone other than the
novice. It moves **behind the Advanced switch** (MD-1), where it costs the novice
nothing. A short list of what the novice keeps gets **simpler**. The bigger
saving for someone who wants to move on is not lines deleted but **surfaces
frozen**: the 3D preview and the website are finished as they are, by policy
(G4, G5), so they stop drawing work.

---

## 1. The five dispositions

| Disposition | Meaning | What happens to existing designs |
|---|---|---|
| **Delete** | The code leaves the app | Anything a design holds from it still opens: unknown feature kinds round-trip untouched (RM-2) |
| **Out of the product** | No menu, button or text in the shipped app; the code stays for the owner (scripts, the command line, the MCP server) | Unchanged |
| **Advanced** | Behind View → Advanced tools (MD-1), off by default | Drawn, selectable and printed whatever the switch says (02 §2) |
| **Simplify** | Stays in the simple app, made smaller or plainer | Unchanged |
| **Keep** | As it is, with the fixes other parts name | Unchanged |

## 2. How each feature was judged

Three questions, in this order:

1. **Does the novice need it to answer one of their five questions?** (What
   grows here; what goes where; what do I buy; how do I plant and keep it; will
   the neighbours accept it. See [01-personas.md](01-personas.md).) Yes →
   *Keep* or *Simplify*.
2. **Does anyone else use it: the enthusiast, the professional, the owner?**
   Yes → *Advanced* (or *Out of the product* if only the owner).
3. **What does keeping it cost?** Lines, tests, coupling to the rest, outside
   services that can change under it, and how often it has broken. A feature
   nobody but the owner can feed, with real upkeep, is *Delete*.

Sizes below are lines of Python in `src/` at V3.17 (101,892 lines in 295
modules in all), counted with `wc -l`. *Importers* are other `src/` modules that
import the feature's modules; *tests* are test modules that name them. The
script that counted them is described in §8.

---

## 3. Delete

| Feature | Size | Coupling | Why it goes | Item |
|---|---|---|---|---|
| **Help › Switch to a specific version…** | ~115 lines in `src/controllers/update_flow.py` (`_on_pick_version`, `:158-239`; `_frozen_pick_version`, `:567-598`) and the action (`src/app.py:645`) | None outside the updater; no test names it | A developer's tool in a gardener's Help menu. A person who needs an older release can still download its installer from GitHub Releases, which every release keeps | RM-1 |
| **File › Import Yard Scan…** and the **Yard photo** layer (phone point clouds, Gaussian splats) | 1,169 lines in 5 modules (`scan_import.py`, `scan_import_dialog.py`, `scan_align.py`, `splat_backdrop.py`, `splat_flow.py`), plus touch points in `scene_contract.py`, `controllers/persistence.py`, `scene3d_window.py`, `app.py:432` and the View row's *Yard photo* toggle (`toolbar.py:401`) | 4 test modules (`test_scan_import`, `test_scan_import_dialog`, `test_splat_backdrop`, `test_splat_flow`) go with it | Needs a phone scanning app, a point-cloud export and control points. No novice will feed it, and the first review found nobody but the owner had. Its shade and 3D benefits are what Features › *Scan this area* (V3.10) now gives without a scan | RM-2 |
| **The Learn door on the start screen** and the window behind it (`app_mode.py`, `learn_menu.py`, the studio half of `learn_flow.py`) | 129 + 144 + about 100 lines | `start_screen`, `main.py`'s routing, `test_start_menu.py` | The door is broken today (a NameError, `learn_flow.py:60`), it asks a question a beginner cannot answer yet (V2.42's own objection), and both things it leads to are on the View menu. Covered by [04-start-screen.md](04-start-screen.md) **ST-10**; listed here so the ranking is complete | ST-10 |
| **`src/db/recipes.py`** | 298 lines | Called once, from `db/plants.py:2333-2338`, to migrate QSettings recipes into a table **nothing reads** | Dead since the plant-mix builder stopped using recipes. Delete the module and the call; **leave the table** (dropping it needs a schema bump and gains nothing) | RM-6 |

**Old designs and deleted features.** A design saved with a yard scan or a
splat backdrop must still open. The loader already ignores feature kinds it does
not draw; RM-2 adds a test that such a file opens, saves and re-opens with the
feature byte-identical, and that the 3D preview builds without it.

## 4. Out of the product (the code stays)

| Feature | Size | Why it stays | Why it leaves the app | Item |
|---|---|---|---|---|
| **The local AI** in Generate Design: the AI wording in the dialog, *Build without AI (offline)*, the Ollama error text (R3) | About 800 lines of `src/llm_design.py` are AI-only: the client (`:35-237`), the prompt digests (`:238-595`) and `generate_design` (`:1044-1279`). The other ~2,300 lines are the placement every design uses | `generate_design` is part of the CLI (`src/cli.py:132-153`) and the MCP server's frozen contract (`src/mcp_server.py:159-206`, guarded by `test_architecture_guard.py`) | A novice cannot install and run a local language model, and when it is missing they see raw error text and a brief that is silently ignored (R3). Plan My Yard ([07](07-plan-my-yard.md)) replaces the brief with plain choices | RM-3, with PY items in 07 |
| **The 3D Sprite Gallery** | 959 lines | A tuning bench the scripts use (`scripts/make_gallery_scene.py`) | Already off the menu since V3.07 (the owner's *Retire*). Its 844 KB scene file and the tuning pages still ship in the installer | RM-7 |
| **Developer pages in the installer**: `html/*_probe.html` (7), `html/tune_morphology.html`, `html/tune_fauna.html`, `html/sprite_gallery*`, `html/inspect_probe_data.json` | about 1.1 MB | Tests and benches read them from the source tree | Nothing in the shipped app opens them | RM-7 |
| **`data/fetched/`** in the installer | 32 MB | The dev artefact the range derivations re-run from | Never read at runtime, and it holds CC BY-NC records the app has no reason to redistribute. Same item as ED-13 | ED-13 |
| **The command line, `permadesign_api` and the MCP server** | 1,406 lines | The owner's scripting and Claude's way into the app; frozen contract | They have no menu today; nothing changes | — |
| **The website builder** (`src/static_site*.py` and its helpers) | about 5,700 lines | A separate product (grownativeplants.ca) | It has no menu in the app; it is a separate product with its own upkeep, frozen by G5 | — |

## 5. Advanced (behind the switch)

Ranked by how much each removes from what the novice sees. The owner's earlier
choices from the V3.05 surface audit ([`../SURFACE_AUDIT.md`](../SURFACE_AUDIT.md),
*Page by page*) are all respected: every page the owner chose to **Keep** stays,
behind the switch where it is not for the novice.

| Rank | Feature | Where today | Size | Owner's V3.05 choice | Why advanced, not deleted |
|---|---|---|---|---|---|
| 1 | **The Design tab in depth**: Report card in full, Habitat (breakdown, relationship web, pull-a-plant, chickadee brood), Food (one animal, month by month), Over time (year slider, phased plan), Water | Design › six pages, 2,202 words for the example | `analysis_panel.py` 2,073; `food_page.py` 687; `planning_panel.py` 981; `relationship_graph.py` 547; `chickadee_scenario.py` 191 | Keep (Habitat, Water, Timeline); merges enacted V3.08 | The owner values it; the overview ([06](06-yard-overview.md)) answers the novice's questions from the same functions. Fixes first: OV-2 to OV-6, OV-11 |
| 2 | **Site › Slope**: contours, slope ramp, water flow, the 1 GB LiDAR download | Site tab | terrain group 3,094 | Keep | Useful on a sloped lot, unreadable without a lesson in contours |
| 3 | **Site › Wind**, wind shadow, snow catch | Site tab, map overlays | 768 + 350 | Move to Site (done V3.07) | A windbreak decision; a novice's question is "is it windy here", which Site Info can say in a line |
| 4 | **Site › Features** beyond *Scan this area*: OSM and offline building imports, nDSM GeoTIFF import, satellite alignment, drawing trees and buildings by hand | Site tab | tree detection 2,194; buildings 1,182 | Keep, and rework | The one-click scan covers the novice; the rest is for fixing what it misses |
| 5 | **Placement's builders**: plant mix and community mix, the community builder (New, Edit, Variation, Import, Export), the creature picker, placing patterns Row, Grid and Circle | Placement tab | creature picker 226; much of `polyculture_panel.py` (2,669) | Keep | Authoring communities is an enthusiast's job; the novice places ready ones |
| 6 | **The View menu's windows**: 3D Preview, Split view, Plant Directory, Walk a Wild Landscape, Growth Snapshots | View menu | 3D: 6,295 Python + 11,475 JS + 30 MB of models; split view 253; Directory 748; Walk 1,030 with graduation 283; Snapshots 303 | Keep (names chosen V3.07) | Each is somebody's favourite. The 3D preview gets one plain door from the overview (decision M2) |
| 7 | **Share's presentation outputs**: Present (the narrated tour), Growth Snapshots, the presentation still, before/after | Share tab | 414 + 303 + 131 + 430 | Move to Share (done V3.08) | For a neighbour, a board or a class: real, but after the yard is planned |
| 8 | **The Learn tab**: Field Study, Lessons | Learn tab | part of the Learn group's 1,904 | Keep; improve Field Study | Learning about plants is not planning a yard; it stays one switch away. Whether it survives at all is G2 |
| 9 | **Map tools**: Measure, notes on the map, the grid and base size, canopy and structures layer switches, scale units, Map Settings | Draw and View rows, View menu | small | Move Map Settings (done V3.07) | Every one adds a button to a row the novice must read past |
| 10 | **Province-wide choices**: "All Alberta natives", the province chips, the "Native to" facets | Picker, Communities, Plan My Yard | small | — | The simple app defaults to the Edmonton list (ED-10) |

### 5.1 A policy, not a feature: freeze the 3D preview (G4)

The 3D preview is the largest single surface in the app: 6,295 lines of Python,
11,475 lines of JavaScript, 30 MB of models, a dependency (three.js) whose
upgrades must be re-checked by hand (`tests/test_leaf_light.py`), and a WebGL
path that fails on some graphics drivers (backlog F211). It is also, by P13, the
part most likely to make someone fall for a design. **Recommendation:** keep it,
behind the switch with one door from the overview, and **freeze it**: no new 3D
features; a 3D problem that is not a crash or a wrong plant is *won't fix*. That
turns its upkeep from open-ended into almost nothing.

## 6. Simplify (stays in the simple app)

| Surface | Today | Simpler | Where specified |
|---|---|---|---|
| **Start screen** | Five near-identical rows, a dead door | One way to start, then your designs by name | [04](04-start-screen.md) |
| **Site › Site Info** | Zone, climate, rainfall, soil, glossary, nurseries, in a column that scrolls sideways once a pin is set (R8) | Four plain lines (where, how cold, how wet, what soil) with Details below | [09](09-words.md) |
| **Site › Sun & Shade** | Sun path, cast shade, planting zones, shadow arrows | "Which parts of my yard are sunny", and *Scan this area* | [07](07-plan-my-yard.md) |
| **Site › Field Notes** | Ten site-walk prompts, a journal, a site photo | Unchanged; already plain and printable | — |
| **Placement › Plants** | 424 species, A–Z or by locality | The Edmonton list, best first, with a band and a reason | [05](05-plants-that-lead.md) PR-1 to PR-4 |
| **Placement › Communities** | 73 communities, some with names a novice cannot read | The ones that pass the Edmonton list, ranked, with plain names; the pattern card on the community page moves to advanced | [05](05-plants-that-lead.md); RM-8 |
| **Placement › Structures** | 15 structures in one list | Grouped: *For wildlife* (pond, brush pile, bee hotel, bee log, snag, rock pile), *For water* (rain garden, rain barrel, bioswale), *Around the yard* (raised bed, compost, shed, fence or wall, fire pit, native lawn patch) | RM-9 |
| **Generate Design…** | Goals, a brief, an AI, a budget, density, site matching, an offline switch | **Plan My Yard…**: a few plain choices and a result you can try again | [07](07-plan-my-yard.md) |
| **Design tab** | Six pages | **Overview** and **Planted** | [06](06-yard-overview.md) |
| **Share tab** | Present and Export (eight buttons) | Export: the PDF, the planting plan, the order file; Where to buy | [02](02-two-ways-to-use-it.md) |
| **The plant page** | Every field the catalogue has | What it needs, why it matters, how big, where to buy; the rest under *More about this plant* | [05](05-plants-that-lead.md) §7 |
| **Help menu** | Eight items including a developer tool | Start Screen, the example, shortcuts, feedback, sources, About, updates, *Support this app* | [02](02-two-ways-to-use-it.md) §3.2; [10](10-finishing.md) |

## 7. The ten removals that matter most

Ranked by how much each takes out of a novice's first hour, then by how little
it costs. "Removal" here means *from what the novice sees*: most are Advanced,
not Delete.

| # | Removal | Disposition | What the novice stops seeing | Effort |
|---|---|---|---|---|
| 1 | The Learn door and its window | Delete (ST-10) | A door that opens the wrong thing, on the first screen | S |
| 2 | The local AI in Generate Design | Out of the product (RM-3) | An AI they cannot install, raw error text, a brief that is ignored | S |
| 3 | The Design tab in depth | Advanced (MD-1, OV-1) | Five pages and about 1,900 words, two scores that disagree | M (with the overview) |
| 4 | The province-wide plant list as the default | Simplify (ED-10) | 174 plants that are not native around Edmonton | S (after ED-3) |
| 5 | Site › Slope, Wind and most of Features | Advanced (MD-1) | Three pages of terrain, wind and imports | S |
| 6 | Placement's builders and patterns | Advanced (MD-1) | A second toolbox inside the plant list | S |
| 7 | The View menu's windows and Split view | Advanced (MD-1) | Five windows, each with its own toolbar | S |
| 8 | Share's presentation outputs | Advanced (MD-1) | Five buttons before Export PDF | S |
| 9 | Help › Switch to a specific version | Delete (RM-1) | A developer's tool | S |
| 10 | Import Yard Scan and the Yard photo layer | Delete (RM-2) | A menu item and a layer switch that need a phone scan | M |

## 8. Work items

| ID | Item | Effort | Depends on |
|---|---|---|---|
| **RM-1** | **Delete the version picker.** Remove `_on_pick_version`, `_frozen_pick_version` and the Help action; keep *Check for Updates* and its frozen and source paths. **Tests:** `test_app_smoke.py`'s menu walk no longer finds the item; `test_architecture_guard.py`'s ceilings still pass (the file shrinks). *Accept:* Help has no *Switch to a specific version…*; Check for Updates still offers a newer release | S | — |
| **RM-2** | **Delete Import Yard Scan and the splat backdrop.** Remove the five modules, the File action, the View row's *Yard photo* toggle, the scene contract's `splat` and `scan` inputs (keep the keys' absence harmless), the 3D window's bake button, and the four test modules. **Old files:** a design holding a `splat_backdrop` or scan feature opens, saves and re-opens with that feature byte-identical, and the 3D preview builds without it (a new test with a fixture file). Update the CLAUDE.md rows that name these modules. *Accept:* the suite passes; the example and a fixture design with a splat feature both open | M | — |
| **RM-3** | **The local AI leaves the app.** The dialog stops offering the AI and the offline switch; the app always calls `generate_design_offline`; `generate_worker.py`'s AI branch goes; the command line and MCP keep `generate_design`. The dialog itself is rebuilt by [07](07-plan-my-yard.md). **Tests:** no string in `src/` outside `llm_design.py`, `cli.py` and `mcp_server.py` contains "AI" as a word or "Ollama" (a grep test); the MCP contract test is unchanged. *Accept:* with no network and no Ollama, Plan My Yard builds a design and shows no error text | S | PY-1 |
| **RM-4** | **The advanced registry, filled.** MD-1's `ADVANCED_PAGES`, `ADVANCED_ACTIONS` and `ADVANCED_TOOLBAR_ITEMS` from §5, as amended by the owner's G decisions. *Accept:* the registry names every surface in §5 and nothing in §6 | S | MD-1 |
| **RM-5** | **Record the reversals.** The increment that does RM-1 to RM-3 says in its plan file which earlier decisions it reverses (the V1.63 scan import, the V2.43 Learn door, the AI path), so the next reader sees decisions, not disappearances | S | RM-1 to RM-3 |
| **RM-6** | **Delete `src/db/recipes.py`** and its migration call; leave the table. *Accept:* the suite passes; an old database still opens | S | — |
| **RM-7** | **Trim the installer.** Exclude `data/fetched/` (with ED-13), `html/*_probe.html`, `html/tune_*.html`, `html/sprite_gallery*` and `html/inspect_probe_data.json` from `scripts/packaging/permadesign.spec`'s `datas`. **Tests:** a test reads the spec and asserts the exclusions; `test_app_smoke` still finds every page the app opens. *Accept:* the installer is about 33 MB smaller uncompressed | S | — |
| **RM-8** | **The community page in simple mode**: name, what it is for, its members as photographs, Place. The Alexander pattern card (`src/pattern_language.py`) shows with Advanced on. *Accept:* in simple mode the page has no pattern card | S | MD-1 |
| **RM-9** | **Structures grouped** under three headings (§6), in the simple app; Existing tree and Existing building stay with Features. *Accept:* the list shows three headings and the same 15 structures | S | — |

## 9. Decisions for the owner

- **G1.** Accept the four deletions (RM-1, RM-2, ST-10, RM-6) and the AI
  leaving the app (RM-3)? Recommended: yes; the owner already agreed to the
  first review's list.
- **G2.** The Learn tab (Field Study and Lessons): keep it behind Advanced
  (recommended, and consistent with the V3.05 *Keep*), or retire it? Retiring
  saves about 1,000 lines and 11 test modules but undoes a recent choice.
- **G3.** Split view: keep it behind Advanced (recommended), or delete it,
  since the 3D preview window now follows the design (V3.08) and split view is
  a second way to see the same thing?
- **G4.** Freeze the 3D preview (§5.1): no new 3D features; anything short of a
  crash or a wrong plant is *won't fix*. Recommended: yes.
- **G5.** Freeze the website at its current build, rebuilt only when the
  catalogue changes. Recommended: yes ([10-finishing.md](10-finishing.md)).
- **G6.** Anything in §5 the owner wants in the simple app after all. The most
  likely candidates are **Measure** (a homeowner measuring a bed) and **Walk a
  Wild Landscape** (the most beautiful thing in the app after the 3D preview).

## 10. How this was counted, and what it cannot tell

Line counts are `wc -l` on the files named. Importers and test modules were
found by a short script that searches `src/` for `import` lines naming each
module and `tests/test_*.py` for the module names. It counts mentions, not
dependencies a deletion would break, so each Delete item above was also read by
hand (the coupling column). Not measured: how many users use each feature (the
app collects nothing), and how many controls the simple app will have, which
MD-2 measures with the surface probe once the switch exists.
