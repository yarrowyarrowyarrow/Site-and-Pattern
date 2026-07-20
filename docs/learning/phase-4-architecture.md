# Phase 4 — The architecture: how the pieces talk

**Goal:** the big picture. The app follows one repeating pattern — Qt-free
core → flow glue → widget → wiring — and once you can see it, the 100+
files in `src/` collapse into a handful of shapes. This phase is mostly
*reading with intent*, and it ends with you drawing the whole app from
memory. **Time:** ~12 hours across 4–6 weeks. **Lessons:** 5.

Ritual: tick [PROGRESS.md](PROGRESS.md) → `python scripts/learning_progress.py`
→ commit `Learning: Lx.y complete`.

---

### L4.1 — A design is one file

*Time: ~2 h · Builds on: L3.5*

**Purpose:** every design you've ever saved is a single, human-readable
GeoJSON file — the app's spine. Opening yours in a text editor collapses
the distance between "my garden design" and "data I can read."

**Aim:** open your own saved design, identify every feature in it by eye,
and watch one edit you make in the app appear in the file.

**Steps:**
1. Open your `my-yard.perma.geojson` (from L0.2) in your editor. It's JSON
   — a dict, exactly the shape you learned in L1.5. Find the
   `"features"` list.
2. For each feature, read its `element_type` and properties, and match it
   to what you drew: your boundary, each placed plant. Journal the
   feature types you find.
3. Keep `docs/PROJECT_FILE_FORMAT.md` open beside it — it's the legend
   for everything you're seeing, including feature types you haven't
   drawn yet.
4. The experiment: in the app, open the design, move one plant a little,
   and save. Reopen the file in your editor and find what changed (the
   moved plant's coordinates). One drag on the map = two numbers in a
   file. That's all a design *is*.
5. Skim `src/project.py`'s docstring and function names — the module that
   reads and writes this format. Recognize `save`/`load`-shaped names.

**Done when:** your journal lists the feature types in your design, and
you found the moved plant's changed coordinates yourself.

---

### L4.2 — One door to the plant state

*Time: ~2 h · Builds on: L4.1*

**Purpose:** the repo's strictest architectural rule: every change to
placed plants goes through `src/project_store.py` — one door, guarded by a
test that greps the entire source tree for cheaters. Understanding *why*
teaches you more about software design than any tutorial: shared state
with many writers is where bugs breed.

**Aim:** a journal explanation of the single-write-path rule and how its
guard enforces it — plus one paragraph on what could go wrong without it.

**Steps:**
1. Read the module docstring of `src/project_store.py` slowly. Then skim
   its method names — place, remove, move; notice how the vocabulary is
   the app's vocabulary.
2. Read the docstring and comments of `tests/test_project_store.py` — the
   guard from L2.4, now with full context. Find the part that searches
   `src/` for forbidden direct mutations.
3. The why: the store keeps *two* structures in sync — the project dict's
   features (what gets saved) and a fast lookup index. Journal: what
   happens if code elsewhere updates one and forgets the other? (This
   class of bug — two copies drifting apart — has a name you've met:
   it's why the checklist in this curriculum has a guard test too.)
4. Undo/redo depends on this door: skim `src/controllers/undo_support.py`
   (the `@undoable` decorator) just enough to see that changes get
   snapshotted *because* they pass through known choke points.
5. Journal the rule in one sentence you'll remember. ("All plant changes
   go through the store" is fine. You'll thank yourself in Phase 5.)

**Done when:** you can state the rule, name its guard test, and give one
concrete drift bug the rule prevents.

---

### L4.3 — The wind trace: one feature, end to end

*Time: ~3 h · Builds on: L4.2*

**Purpose:** the wind rose is the repo's cleanest example of its core
pattern: a Qt-free brain (`wind.py`), thin glue (`wind_flow.py`), a widget
that only paints (`wind_rose_widget.py`). Tracing it end to end gives you
the template that almost every other feature is a variation of.

**Aim:** a written call-map, file by file, from "the site pin is set" to
"the wind rose is painted" — every hop pointing at a real line you found.

**Steps:**
1. Start in the brain: `src/wind.py` (300 lines — skim, reading
   docstrings and function names). Journal its jobs: fetch from
   Open-Meteo, cache in the DB, compute the rose. Notice: no Qt imports
   anywhere.
2. The glue: `src/wind_flow.py` (137 lines). Read `fetch_wind_for_site`.
   Its job is traffic direction: run the slow fetch off the UI thread,
   then hand results to the panel. Journal one sentence on why the fetch
   must not run on the UI thread (what would the user feel?).
3. The trigger: open `src/controllers/map_events.py` and search for
   `wind_flow` (~line 1408). This is the hop where "user set the site
   pin" becomes "go get wind data."
4. The pixels: `src/wind_rose_widget.py` (69 lines). It receives finished
   numbers and draws petals — no fetching, no math beyond angles. Then
   find where the Analysis panel houses it (search for `wind` in
   `src/analysis_panel.py`).
5. Assemble the call-map in your journal:
   `map_events.py (pin set) → wind_flow.fetch_wind_for_site → wind.py (fetch+cache+compute) → analysis_panel (Wind tab) → wind_rose_widget (paints)`
   — then verify the whole thing live: run the app, set a site pin, open
   Analysis → Wind, and narrate the hops as it appears.

**Done when:** the call-map is in your journal with a file per hop, and
you watched it happen in the running app.

---

### L4.4 — The switchboard: app.py and the controllers

*Time: ~2–3 h · Builds on: L4.3*

**Purpose:** `src/app.py` is 2,200 lines and *does almost nothing* — it
builds the window and connects wires; behaviour lives in controllers and
flow modules. Learning to navigate it by search instead of by reading
means no file in the repo can intimidate you by size again.

**Aim:** three completed "find the behaviour" hunts: menu item →
delegated code, documented in the journal.

**Steps:**
1. Open `src/app.py` and skim only the *shape*: the imports, `__init__`
   building panels, menu construction, `_connect_signals`. Read the class
   docstring — it states the delegation rule (one-line shims) outright.
2. Look at the wind-shadow wiring around line 772: signals connecting to
   `wind_shadow_flow` functions via one-line lambdas. That's the whole
   trick — `app.py` is a switchboard, not a brain.
3. Hunt 1: pick a menu item you use (say, the 3D preview). Find its menu
   wiring in `app.py` (search the menu label text), then follow to the
   module that does the work.
4. Hunts 2 and 3: pick two more — a button, a checkbox, anything in the
   UI — and repeat. Use editor-wide search; that's the professional
   navigation style, not scrolling.
5. Journal each hunt as one line: `<UI thing> → app.py:<line> → <module>.<function>`.
   Then skim the `src/controllers/` directory listing and match each
   controller file to what you now know it handles.

**Done when:** three hunts are journaled with real line numbers, and
`app.py`'s size no longer reads as complexity — just as a long patch bay.

---

### L4.5 — Capstone: draw the whole app

*Time: ~2 h · Builds on: L4.4*

**Purpose:** the test of a mental model isn't recognition — it's
reconstruction. Drawing the architecture from memory, then checking it
against the repo's own map, shows you (and honestly *proves* to you) that
the fog has lifted.

**Aim:** a from-memory diagram of the app's architecture, corrected
against `.claude/skills/codebase-map/SKILL.md`, kept in your journal — 
and a 30-second spoken tour to go with it.

**Steps:**
1. Close the editor. On paper (or a blank journal entry), draw the app
   from memory: the window, the map, the panels, the project file, the
   store, the database, the seed JSON, the Qt-free cores, the flow glue.
   Arrows for who calls whom. Fifteen minutes, no peeking.
2. Now open `.claude/skills/codebase-map/SKILL.md` and compare against
   its subsystem map. Mark your diagram: green where you were right, red
   where you missed or misplaced something.
3. Journal the three biggest corrections — the misses teach you more than
   the hits.
4. Redraw the diagram clean, corrections included, into your journal.
   Date it. (Redrawing it again after Phase 5 and comparing is genuinely
   motivating — schedule that now as a journal note.)
5. The spoken test: give the 30-second tour out loud — "a design is one
   GeoJSON file; plants change through one store; logic lives in Qt-free
   modules; flows glue them to the window; app.py just wires..." — 
   without looking at the diagram.

**Done when:** the corrected diagram is in your journal and you delivered
the 30-second tour aloud, unaided, without stalling.

---

**Phase complete.** You have the map and the mental model. Time to change
the territory: [phase-5-solo.md](phase-5-solo.md).
