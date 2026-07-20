# Phase 1 — Python fundamentals

**Goal:** the core investment. An external course provides structure
(*Automate the Boring Stuff with Python*, free at
[automatetheboringstuff.com](https://automatetheboringstuff.com) — "ATBS"
below); this repo is your field site, where every concept gets spotted in
the wild within days of learning it. **Time:** ~25–30 hours across 6–10
weeks. **Lessons:** 10.

Two standing tools for the whole phase:

- **The REPL** — run `python` with no arguments from the repo folder and
  you get an interactive prompt (`>>>`) where every line runs immediately.
  Exit with `exit()`. Most lessons below live here.
- **[pythontutor.com](https://pythontutor.com)** — paste confusing code,
  step through it visually. Use it whenever a loop or function feels foggy.

Ritual after every lesson: tick [PROGRESS.md](PROGRESS.md), run
`python scripts/learning_progress.py`, commit `Learning: Lx.y complete`.

---

### L1.1 — Conversations with Python: values, variables, strings

*Time: ~3 h · Builds on: L0.4*

**Purpose:** the REPL turns Python from a subject into a conversation —
type, see the answer, adjust. Variables and strings are the first words of
the language, and this app's own name is stored in one.

**Aim:** hold a REPL conversation using variables and strings, ending with
the app's real branding module.

**Steps:**
1. Read ATBS Chapter 1 and do its examples in your own REPL — arithmetic,
   variables, `print()`, strings and `+`.
2. Try f-strings (ATBS covers them): `name = "Marci"` then
   `print(f"{name} is learning Python")`.
3. In your editor, open `src/branding.py` (35 lines). Read all of it. It's
   nothing but variables holding strings — you can already read a real
   file in the codebase.
4. In the REPL (started from the repo folder):
   ```python
   from src.branding import APP_NAME
   print(f"I am learning to read the {APP_NAME} codebase")
   ```
5. Journal: in your own words, what is a variable? What are the quotes for?

**Done when:** step 4 works, and you can explain what `from src.branding
import APP_NAME` did — it reached into a file and borrowed a variable.

---

### L1.2 — Making decisions: if / elif / else

*Time: ~3 h · Builds on: L1.1*

**Purpose:** `if` is how code makes decisions, and this app makes an
ecological one you already understand: naming the restoration stage of a
site at a given year. You'll read that real decision today.

**Aim:** predict what `restoration_stage()` returns for seven different
years — then prove your predictions in the REPL.

**Steps:**
1. Read ATBS Chapter 2 (flow control): `if`, `elif`, `else`, comparisons
   (`<=`, `==`), and indented blocks.
2. Open `src/succession.py` and find `restoration_stage` (~line 43). Read
   it slowly. Notice the checks run top to bottom and the **first match
   wins** — that ordering is what makes it correct.
3. In your journal, predict the output for years 0, 1, 3, 5, 9, 10, 25.
4. Verify:
   ```python
   from src.succession import restoration_stage
   restoration_stage(3)
   ```
5. Tricky one: why does year 10 give `"Climax / canopy"` when there's no
   `if year >= 10` line anywhere? (Answer in one journal sentence.)

**Done when:** all seven predictions verified, and you can explain the
year-10 case — nothing matched, so the final `return` caught it.

---

### L1.3 — Functions: inputs in, answer out

*Time: ~2–3 h · Builds on: L1.2*

**Purpose:** functions are the unit this whole codebase is made of —
named machines with inputs and one job. Today you call a real geometric
one with your own yard's coordinates.

**Aim:** use `ring_bbox` and `point_in_ring` from `src/geometry.py` on a
rectangle you define around your own property.

**Steps:**
1. Read ATBS Chapter 3: `def`, parameters, `return`, and write a couple of
   toy functions in the REPL.
2. Get your yard's rough corner coordinates: right-click two opposite
   corners in Google Maps (or read them off the app's map). Note them as
   (lat, lng).
3. Open `src/geometry.py`. Read the module docstring — it warns you of a
   real trap: rings store points as **[lng, lat]**, but the functions take
   `(lat, lng)` arguments. Mixing those up is a rite of passage.
4. In the REPL, build a ring for your yard (a closed rectangle,
   `[[lng, lat], ...]`, repeating the first corner last) and try:
   ```python
   from src.geometry import ring_bbox, point_in_ring
   ring_bbox(my_ring)
   point_in_ring(lat_of_your_door, lng_of_your_door, my_ring)
   ```
5. Test a point you *know* is outside (the neighbour's yard) and confirm
   it returns `False`.

**Done when:** inside-point gives `True`, outside gives `False`, and you
can say what `ring_bbox` returns and in what order.

---

### L1.4 — Lists and loops: doing things many times

*Time: ~3 h · Builds on: L1.3*

**Purpose:** almost everything in this app is a list — plants, coordinates,
features — and loops are how code visits each item. Today you re-implement
a real function by hand and check yourself against it.

**Aim:** compute a ring's bounding box with your own `for` loop, and match
`ring_bbox`'s answer exactly.

**Steps:**
1. Read ATBS Chapter 4: lists, indexing (`ring[0]`), `for` loops, and
   `min()`/`max()`.
2. In the REPL, with your L1.3 yard ring: write a loop that collects every
   longitude into one list and every latitude into another, then take
   `min` and `max` of each.
3. Compare your four numbers to `ring_bbox(my_ring)`. They must match.
4. Now look at how `ring_bbox` itself does it (`src/geometry.py`, ~line
   68): `[p[0] for p in ring]` — a *list comprehension*, a loop folded
   into one line. Rewrite one of yours in that style.
5. Paste `point_in_ring` into pythontutor.com and step through it with a
   tiny triangle ring — watch `inside` flip as the ray crosses edges. You
   don't need to master the geometry; you need to *see* the loop visit
   each edge.

**Done when:** your hand-rolled loop matches `ring_bbox`, and you can read
`[p[0] for p in ring]` out loud as a sentence.

---

### L1.5 — Dictionaries: the app's native tongue

*Time: ~3 h · Builds on: L1.4*

**Purpose:** a plant in this app is a dictionary. A project is a
dictionary. A map feature is a dictionary. Fluency with `dict` *is*
fluency with this codebase's data.

**Aim:** build a plant dictionary of your own, and read a real lookup-table
module.

**Steps:**
1. Read ATBS Chapter 5: key/value pairs, `d["key"]`, `d.get("key")`, and
   looping over dicts.
2. In the REPL, build a dict for a plant you love —
   `{"common_name": ..., "plant_type": ..., "mature_height_m": ...}` —
   and practice reading and changing its fields.
3. Learn the difference the codebase relies on constantly:
   `plant["bloom_period"]` crashes if the key is missing;
   `plant.get("bloom_period")` returns `None`;
   `plant.get("bloom_period", "unknown")` returns a default. Try all
   three on a key your dict doesn't have.
4. Open `src/member_colors.py` (92 lines) — dictionaries as colour lookup
   tables for map markers. Pick a colour, then find where a `.get(...)`
   provides the fallback when a key isn't present.
5. Journal: why is `.get` with a default so common in an app whose plant
   records come from a database where fields can be empty?

**Done when:** you can predict, without running them, which of the three
lookup styles crashes on a missing key — and explain when you'd want each.

---

### L1.6 — Real data: 434 plants in your hands

*Time: ~2–3 h · Builds on: L1.5*

**Purpose:** the plant catalogue you've scrolled in the app is a JSON file
— a list of dictionaries — and you now know both of those words. Today the
dataset stops being scenery and becomes something you can interrogate.

**Aim:** load `data/plants_master.json` in the REPL and answer three
questions about the catalogue with loops you write yourself.

**Steps:**
1. In the REPL:
   ```python
   import json
   plants = json.load(open("data/plants_master.json"))
   len(plants)          # 434 — the catalogue
   plants[0]            # one plant, one dict
   ```
2. Question 1: print the `common_name` of every shrub (a loop with an
   `if plant["plant_type"] == "shrub"`).
3. Question 2: count plants per `plant_type` (build a dict of counters —
   ATBS ch 5 shows the pattern).
4. Question 3: your own. Tallest plant? Everything with white flowers?
   You know this data better than anyone — ask it something real.
5. Journal all three questions and answers. Note anything messy you spot
   in the data (you'll meet the mess again in L1.10).

**Done when:** all three answers are in your journal and you wrote the
counting loop without copying it from anywhere.

---

### L1.7 — When it breaks: reading tracebacks

*Time: ~2 h · Builds on: L1.6*

**Purpose:** error messages are the language Python answers in when
something's wrong — and beginners who learn to *read* them stop needing
rescue. An error is information, not a verdict.

**Aim:** cause three different exceptions on purpose, diagnose each from
its traceback alone, and read how this app names its own errors.

**Steps:**
1. In the REPL, deliberately trigger each of these, and before fixing
   anything, read the traceback **bottom line first**:
   - a `NameError` (use a variable you never defined),
   - a `KeyError` (look up a missing dict key with `[]`),
   - a `TypeError` (try `"5" + 5`).
2. For each: journal one line naming the error type and what it's telling
   you, in your own words.
3. Trigger one *inside* a call chain: `from src.geometry import ring_bbox`
   then `ring_bbox([])`. Read the traceback top to bottom — it's a trail
   of *where* the problem travelled, ending at `ValueError: empty ring`,
   raised on purpose by the function itself.
4. Open `src/errors.py` (46 lines): the app defines its *own* error types,
   with names that mean something. Read the class names and docstrings —
   that's all an error class is: a label.

**Done when:** shown any of your three tracebacks tomorrow, you could name
the error and point at the line that caused it.

---

### L1.8 — Modules and imports: how files find each other

*Time: ~2 h · Builds on: L1.7*

**Purpose:** you've typed `from src.X import Y` many times; today it stops
being an incantation. Imports are the wiring diagram of the codebase — 
being able to follow them means never being lost.

**Aim:** map every import in one real module to the file it comes from,
and verify a documented behaviour of `app_version.py` by prediction.

**Steps:**
1. Read ATBS's section on importing modules, then the rule of this repo:
   `from src.wind import fetch_wind` means "in the folder `src`, in the
   file `wind.py`, borrow `fetch_wind`."
2. Open `src/wind.py` and list its import lines in your journal. For each,
   name the actual file it points to (standard-library imports like
   `json` won't be in the repo — note them as "Python built-in").
3. Open `src/app_version.py` (38 lines) and read the docstring carefully.
   It states what `build_version()` returns in a source checkout like
   yours. Write your prediction down.
4. Verify: `from src.app_version import build_version` then
   `build_version()`. (Getting nothing back *is* the answer: `None`
   doesn't print in the REPL — `print(build_version())` shows it.)
5. Journal: why must the REPL be started from the repo folder for
   `from src...` imports to work?

**Done when:** your import map for `wind.py` is complete and your
`build_version()` prediction matched.

---

### L1.9 — Classes, gently: objects that remember

*Time: ~3 h · Builds on: L1.8*

**Purpose:** classes bundle data with the functions that use it. You don't
need to *write* them yet — you need to stop flinching when you see `self`.
The cleanest class in the repo measures distances in your own yard.

**Aim:** construct a `Projector` centred on your yard and use it to
measure your yard's width in metres.

**Steps:**
1. Read ATBS's intro to classes (or any "Python classes in 20 minutes"
   piece): `class`, `__init__`, methods, and `self` = "this particular
   object."
2. Read `src/projection.py` (98 lines), docstring included — it also
   explains *why* the maths is deliberately approximate, a P9 story
   (honest uncertainty) told in code.
3. In the REPL, with your L1.3 corner coordinates:
   ```python
   from src.projection import Projector
   p = Projector(lat0, lng0)           # one corner as origin
   p.distance_m(lat0, lng0, lat2, lng2)  # to the opposite corner
   ```
   Sanity-check the number against what you know your yard measures.
4. Round-trip: `x, y = p.to_xy(lat2, lng2)` then `p.to_latlng(x, y)` —
   you should get your corner back.
5. Journal: `p` *remembers* the origin you gave it — that's what `self`
   holds. Explain in two sentences why `distance_m` needs no origin
   argument.

**Done when:** the distance is plausible for your real yard, the
round-trip returns your input, and your `self` explanation would survive
being read aloud.

---

### L1.10 — Capstone: your first program

*Time: ~4 h · Builds on: L1.6, L1.8*

**Purpose:** everything so far ran line by line. A program is those lines
made permanent, runnable, and yours. This one answers a question you
actually have as a gardener — and gets committed to the repo like real
code, because it is.

**Aim:** a script, `sandbox/bloom_table.py`, that prints every plant
blooming in a month you choose — written by you, committed by you.

**Steps:**
1. In the repo folder: `mkdir sandbox`, then create `sandbox/bloom_table.py`
   in your editor.
2. Write the program — the shape is: import `json`, load
   `data/plants_master.json`, loop, `if` the month matches, `print`.
   Build it up in tiny runs (`python sandbox/bloom_table.py` after every
   few lines) rather than all at once.
3. The real-world wrinkle: `bloom_period` is human text — `"Jul-Aug"` in
   one record, `"July-August"` in another. Notice that lowercase `"jul"`
   is *contained in* both. `"jul" in plant["bloom_period"].lower()` is
   your friend — and handle records where the field is empty (L1.5's
   `.get` earns its keep).
4. Finish with a count line, e.g. `print(len(matches), "plants bloom in July")`.
   Run it for two different months and sanity-check against what you know.
5. Commit it: `git add sandbox/bloom_table.py`, commit as
   `Learning: L1.10 capstone — bloom table`. Your first program is now in
   the project's history.

**Done when:** the script runs cleanly for two months of your choosing,
survives plants with empty bloom data, and is committed. **This is the
milestone**: you wrote a program that reads the app's real data and tells
you something true about prairie plants.

---

**Phase complete.** The fog around whole files starts lifting in the next
phase, where the test suite becomes your reading guide. Next:
[phase-2-tests.md](phase-2-tests.md).
