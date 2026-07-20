# Phase 5 — Solo changes

**Goal:** real changes to the real app, graduated by risk, with you at the
keyboard and AI demoted to reviewer (Levels 3–4 of the roadmap's AI
ladder). Each lesson follows the full professional loop: branch → change →
test → commit → push. **Time:** open-ended — this phase *is* the practice
of being this codebase's developer. **Lessons:** 5.

Before starting, read two short house documents: the "Branch naming
convention" section of `CLAUDE.md` (branches are `V<major>.<minor>`; a
hook enforces it) and `.claude/skills/start-work/SKILL.md` (the
start-and-finish-work ritual). From now on you follow them like any other
contributor — because you are one.

Ritual: tick [PROGRESS.md](PROGRESS.md) → `python scripts/learning_progress.py`
→ commit `Learning: Lx.y complete`.

---

### L5.1 — The copy change

*Time: ~2 h · Builds on: L4.5*

**Purpose:** the smallest possible real change — rewording a label — walks
you through the *entire* professional loop with almost zero risk. The
loop is the lesson; the wording is the excuse.

**Aim:** one user-visible wording improvement, made by you, tested,
committed, and pushed on a proper V-branch.

**Steps:**
1. In the running app, find a label, button, or tooltip whose wording
   you've always wanted to improve. You designed this app's voice — 
   you'll find one.
2. Locate it in code with editor-wide search for the exact text. (If it
   appears in more than one file, pick the UI one — panels, dialogs — and
   journal why the others matched.)
3. Start the branch per the convention (check `git branch -a` for the
   highest `V*.*`, create the next one — `CLAUDE.md` shows the pattern).
   Make the edit. Launch the app and *see your words on screen*.
4. Run the full suite. (Copy changes can trip snapshot-style tests — if
   one fails, read it; `.claude/skills/testing` says whether updating it
   is the right response. That's not an error, that's the system
   working.)
5. Commit with a clear message describing the change (look at
   `git log --oneline -20` and match the house style), then push:
   `git push -u origin <branch>`.

**Done when:** your wording is live in the app, the suite is green, and
the branch is on `origin` — your first shipped change.

---

### L5.2 — A plant of your own

*Time: ~3 h · Builds on: L5.1*

**Purpose:** the L3.5 fire drill, now for real and for keeps: extend the
catalogue with a plant you know from the land, following the full
seed-data checklist. This is a genuine contribution to the app's
ecological content — the part only someone with your knowledge can do well.

**Aim:** one new plant in the shipped catalogue — complete entry, schema
bump, green suite, pushed.

**Steps:**
1. Read `.claude/skills/seed-data/SKILL.md` first — required fields, which
   file feeds which table, the data-quality gate, and the P12 rule
   (provenance and sourcing tags matter here).
2. On a fresh V-branch: copy the JSON entry of a similar plant in
   `data/plants_master.json` and rewrite every field for yours. Honest
   values only — `""` beats a guess (P9: never false precision).
3. Bump `_SCHEMA_VERSION` in `src/db/plants.py` — no drill this time;
   this bump ships.
4. Run the full suite. The data-quality tests will judge your entry —
   read any complaint carefully; it's usually a missing or malformed
   field, and it's protecting *your* catalogue.
5. Launch the app, search your plant, open its details. Then commit
   (message naming the plant) and push. Journal how this differed from
   the fire drill — what was the same, what carried weight this time?

**Done when:** your plant appears in the app's browser, the suite is
green, and the branch is pushed. Someone who installs the next release
gets a plant *you* added.

---

### L5.3 — The test-first tweak

*Time: ~3 h · Builds on: L5.2*

**Purpose:** the most powerful habit in professional practice: decide the
behaviour, write the test that demands it, *watch it fail*, then make it
pass. Working test-first means you always know what "done" looks like
before you start — and this repo's Qt-free cores make it natural.

**Aim:** one small behaviour change in a Qt-free module, driven by a test
you wrote before the code, both committed together.

**Steps:**
1. Choose a small behaviour you genuinely want different in a core module
   you know: a threshold or label in `src/succession.py`, a default in
   `src/planting_spacing.py` — your call, your reasons. Journal the
   before/after behaviour in one sentence each.
2. On a fresh V-branch: write the test first, in the module's existing
   test file, asserting the *new* behaviour. Run it and **watch it fail**
   — the failure proves the test can detect the thing you're changing.
3. Now change the code until that test passes. Smallest change that
   works.
4. Run the module's other tests — if your change broke an old
   expectation, decide deliberately: is the old test now wrong (update
   it, with a journal note why), or is your change too broad (narrow
   it)? This judgment call is the actual skill.
5. Full suite, commit test + code together, push. The commit message
   should say *why* — behaviour changes deserve reasons.

**Done when:** red → green happened in that order, the suite is green,
and the commit contains both the test and the change it demanded.

---

### L5.4 — A tiny feature, AI as reviewer

*Time: ~4–8 h · Builds on: L5.3*

**Purpose:** your first multi-file change, following the repo's triad
pattern with the wind trace (L4.3) as your template — and your first
formal use of AI in the *reviewer* seat: it critiques your plan and your
diff, but every line is yours.

**Aim:** one small feature shipped through the triad pattern, planned and
written by you, reviewed (not written) by AI.

**Steps:**
1. Read `.claude/skills/add-feature/SKILL.md` — the playbook — and pick
   something genuinely small. Good shapes: a new stat on the Analysis
   panel computed from placed plants, or a small addition to an existing
   Qt-free core surfaced in an existing panel. (Steer clear of the map JS
   and 3D for now.)
2. Write the plan in your journal first: which Qt-free module (new or
   existing) holds the logic, what its test looks like, where the value
   surfaces in the UI, where the wiring goes. Ask AI to *review the
   plan*: "Here's my plan for this codebase — what am I missing?" Adjust;
   don't delegate.
3. Build it inside-out, the way the repo grew: core function + its test
   first (green before any UI), then the panel surface, then the wiring.
   Run the app often.
4. When it works: `git diff`, read the whole thing yourself first, then
   have AI review the diff. Take what's right, push back on what isn't —
   journal one suggestion you accepted and one you rejected, with
   reasons. (Rejecting AI advice with reasons is the graduation skill of
   this lesson.)
5. Full suite (guards included — if a ceiling or contract trips, the
   `testing` skill has the protocol), commit, push.

**Done when:** the feature works in the running app, every line was typed
by you, and your journal records the plan, the review, and one rejected
suggestion.

---

### L5.5 — Graduation: the bug hunt

*Time: when it happens · Builds on: L5.4*

**Purpose:** the final exam writes itself: the next real bug you notice
while using the app. Finding and fixing a bug nobody handed you — 
reproduce, hypothesize, instrument, fix, protect — is the full craft in
one loop. AI's role: hints on request, never the fix.

**Aim:** one real bug: reproduced, diagnosed by you, fixed by you,
protected by a regression test, pushed.

**Steps:**
1. When you next hit something odd in the app, *don't report it to AI*.
   Journal it as a reproduction recipe: steps, expected, actual. (If it
   isn't reliably reproducible yet, make it so first — that's half the
   diagnosis.)
2. Hypothesize before looking: which subsystem, from your L4.5 mental
   map? Write the guess down — being wrong is data.
3. Instrument: add temporary `print()` lines (or drop `breakpoint()` in
   and step with `n`/`p variable`/`c`) along the suspected path. Follow
   the evidence, not the guess. Allowed AI prompt: "hint at where to
   look, don't fix it."
4. Fix it — smallest change that makes the reproduction recipe pass.
   Remove your instrumentation (`git diff` to check nothing stray
   remains).
5. Write the regression test that would have caught this bug, watch it
   pass, run the full suite, commit (message: what was wrong, why, how
   fixed), push. Journal the hunt — first guess vs actual cause.

**Done when:** the bug is dead, a test now guards its grave, the fix is
pushed — and the diagnosis was yours. **That's graduation.** 

---

**Curriculum complete.** Run `python scripts/learning_progress.py` one
last time and look at the wall of full bars. Then redraw your L4.5
diagram, compare, and write the final journal entry: a letter to the
person who started Phase 0. After that — the app has a roadmap full of
features (`docs/PHILOSOPHY_ROADMAP.md`), and it has a developer.
