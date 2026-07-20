# Phase 2 — Tests as your textbook

**Goal:** the `tests/` folder is the best documentation in this repo,
because it can't go stale — it *runs*. This phase teaches you to read
tests as worked examples, use failures as information, and finally add a
test of your own to the real suite. **Time:** ~8 hours across 2–4 weeks.
**Lessons:** 4.

**Transferable skill:** reading and writing automated tests — the habit
that separates professional code from hopeful code, in every language and
every team.

**Review gate** (from memory, in the journal, then check): the difference
between `plant["key"]` and `plant.get("key")` on a missing key; what the
*bottom* line of a traceback tells you versus the lines above it; and what
`self` holds in a class method, in one sentence.

Ritual: tick [PROGRESS.md](PROGRESS.md) → `python scripts/learning_progress.py`
→ commit `Learning: Lx.y complete`.

---

### L2.1 — Anatomy of a test

*Time: ~2 h · Builds on: L1.9*

**Purpose:** a test is a tiny contract: "given this input, the app must
answer that." Once you can read them, every module in the repo comes with
a book of worked examples — written in Python you now know.

**Aim:** map every test in `tests/test_succession.py` to the function it
exercises, and translate one into plain English.

**Steps:**
1. Skim any short "unittest basics" intro (10 minutes): a test file has
   classes, methods named `test_*`, and assertions like
   `self.assertEqual(actual, expected)`. That's 90% of the grammar.
2. Open `tests/test_succession.py` (134 lines) beside `src/succession.py`.
   For each `test_*` method, note in your journal which function it
   targets (the calls inside give it away).
3. Pick one test and translate it into one English sentence of the form
   "when ___, succession must ___". Write it in the journal.
4. Run the module and watch it agree with you:
   `python -m unittest tests.test_succession -v`
   (the `-v` prints each test's name and verdict — satisfying.)
5. Notice what you never see in these tests: no map, no database, no Qt.
   Pure functions in, answers out — this is *why* the repo keeps logic
   Qt-free, and you're benefiting from it right now.

**Done when:** your journal maps every test to its function, and your
English translation matches what the assertions actually check.

---

### L2.2 — The break-it game

*Time: ~2 h · Builds on: L2.1*

**Purpose:** the fastest way to trust the safety net is to jump into it.
Deliberately breaking code — and watching the right test object — turns
failure output from an alarm into a map.

**Aim:** break `src/succession.py` three ways, predicting each time which
test fails, then restore everything with git.

**Steps:**
1. Round one: in `restoration_stage`, change `if year <= 2:` to
   `if year <= 3:`. **Before running anything**, journal your prediction:
   which test method fails, and what will the message say?
2. Run `python -m unittest tests.test_succession`. Read the failure block
   bottom-up: the `AssertionError` line shows *expected vs got*; above it,
   the exact file and line. Score your prediction.
3. Restore the file — this is the magic undo:
   `git checkout -- src/succession.py`
   Re-run the tests. Green again. Nothing you do in this game can hurt.
4. Rounds two and three, same rhythm (predict → break → run → read →
   restore): change a number in `_DEFAULT_YTM`, then change `"pioneer"`
   to `"Pioneer"` in `successional_role`. The capitalization round is the
   sneakiest — case matters to `==`.
5. Journal: which failure message was hardest to connect to your change,
   and what finally gave it away?

**Done when:** three rounds played, at least two predictions correct, and
`git status` shows a clean tree at the end.

---

### L2.3 — Write your first test

*Time: ~2 h · Builds on: L2.2*

**Purpose:** adding a test is the gentlest possible first contribution of
real code: small, safe, valuable, and judged instantly by the machine. 
After today, the suite that protects this app includes lines you wrote.

**Aim:** one new test method in `tests/test_succession.py`, passing, in
the suite, committed.

**Steps:**
1. Choose an input the existing tests don't cover — scan
   `tests/test_succession.py` first to confirm it's genuinely new. Good
   candidates: an untested year for `year_label`, an untested boundary in
   `restoration_stage` (what about year 4 vs 5?), or `years_to_maturity`
   with a plant dict of your own invention.
2. In the REPL, run your chosen function on your chosen input and note the
   answer — that's your expected value, verified before you write a line.
3. Add a method to the existing test class, following the shape of its
   neighbours exactly (naming style, assertion style). Three lines is a
   perfectly good test.
4. Run `python -m unittest tests.test_succession -v` and find your test's
   name in the output with `ok` beside it. Then run the full suite —
   still green, now one test bigger.
5. Commit with `Learning: L2.3 — first test (year_label)` (adjust to
   yours). Look at the diff first with `git diff --staged` — read your
   own contribution the way a reviewer would.

**Done when:** `-v` shows your test passing by name, the full suite is
green, and the commit is in `git log`.

---

### L2.4 — The guards: architecture written as tests

*Time: ~2 h · Builds on: L2.3*

**Purpose:** this repo's most unusual idea: its architectural rules aren't
in anyone's memory — they're tests that fail when a rule is broken. 
Knowing the guards exist (and how to respond when one trips) is what lets
you change things confidently in later phases.

**Aim:** a journal entry naming three guard tests and, for each, the rule
it enforces and what tripping it would mean you did.

**Steps:**
1. Read the module docstring at the top of
   `tests/test_architecture_guard.py` — just the docstring and the
   comments above each test class. You're reading *intent*, not
   implementation.
2. Do the same for `tests/test_project_store.py` (it literally searches
   the source tree for forbidden patterns) and
   `tests/test_philosophy.py` (it keeps the twelve principles woven in).
3. For each of the three, journal: the rule, the failure it prevents, and
   one sentence on why this project cared enough to automate it. (The
   `.claude/skills/legacy-lessons` file tells the war stories behind
   several — good reading.)
4. Bookmark the response protocol in `.claude/skills/testing/SKILL.md`:
   when a guard fails you someday, it tells you whether the correct
   response is "fix my code" or "update the snapshot deliberately."
5. Run the three guard modules yourself in one line:
   `python -m unittest tests.test_philosophy tests.test_architecture_guard tests.test_project_store`

**Done when:** you can name the three guards and their rules from memory —
including the one that will someday save you from mutating placed-plant
state by hand.

---

**Phase complete.** You can now read code *and* verify your reading
experimentally. Time to meet the database. Next:
[phase-3-data.md](phase-3-data.md).
