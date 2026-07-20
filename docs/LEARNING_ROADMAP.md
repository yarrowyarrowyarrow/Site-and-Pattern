# Learning Roadmap — from zero to owning this codebase

This is a self-study path for learning to read, understand, and eventually
modify Site & Pattern yourself, starting from no programming background.
It is written for the project's owner, but anyone onboarding from scratch
can follow it.

Two things to hold onto before you start:

1. **You have an unfair advantage.** You know exactly what this app is
   supposed to do, why every feature exists, and what "correct" looks like on
   the screen. That is the hard half of programming. The syntax is the easy
   half, and it's learnable.
2. **This codebase is friendlier than most.** It has small, heavily-commented
   modules, a test suite that acts as executable documentation, guard tests
   that stop you from breaking the architecture by accident, and docs that
   explain *why* things are the way they are. It was built to be readable.

Total realistic timeline: **6–12 months at 4–6 hours/week** to genuine
independence on small-to-medium changes. That sounds long; the phases below
give you real wins from week one. Skipping ahead is allowed — boredom is
worse than gaps — but the phase order reflects real dependencies.

---

## How to use AI while you learn (read this first)

The goal is less reliance, not zero contact. The trap isn't using AI — it's
using it in a way where nothing sticks. Climb this ladder deliberately:

- **Level 1 (now):** AI does the work; you read every diff before it's
  committed and ask "explain line N" until the diff makes sense. Never accept
  a change you couldn't summarize out loud.
- **Level 2:** AI does the work, but you predict first. Before asking for a
  fix, write down (a sentence is enough) which file you think changes and
  roughly how. Compare against what actually happened. Being wrong is the
  learning.
- **Level 3:** You write the change; AI reviews it. "Here's my diff — what
  did I miss?" is the single highest-value prompt for a learner.
- **Level 4:** You write the change; the *test suite* reviews it. AI is for
  explaining error messages and unfamiliar concepts only.

Two prompts to use constantly at every level:

- *"Explain this function to me like I've been programming for three
  months."* — on any code you're reading.
- *"Don't fix it. Give me a hint about where to look."* — when debugging.

And one rule: **when AI explains something, close the chat and re-explain it
in your own words in a notebook.** If you can't, you didn't learn it — ask
again differently.

---

## Phase 0 — Operate the machinery (1–2 weeks)

Before learning to program, learn to *drive*: the terminal, git, running the
app, running the tests. No code understanding required, and everything after
this phase depends on it.

**Learn (external):**
- Terminal basics: any "command line crash course" — you need `cd`, `ls`,
  `pwd`, `mkdir`, and how to read a path. An hour or two.
- Git basics: [learngitbranching.js.org](https://learngitbranching.js.org)
  (free, visual, genuinely fun) — the "Main" intro sequence only. You need:
  what a commit is, what a branch is, `git status`, `git log`, `git diff`.

**Do (in this repo):**
1. Get the app running from source: `python main.py` (setup is in
   `INSTALL.md` / `docs/BUILD.md`). Place a plant. Draw a boundary.
2. Run the whole test suite and watch it pass:
   ```bash
   python -m unittest discover -s tests
   ```
   That command is your seatbelt for the entire journey. Everything you ever
   change gets checked by it.
3. Run `git log --oneline -30` and read the history. Notice the `V2.x`
   branch/version rhythm — CLAUDE.md's "Branch naming convention" section
   explains it.
4. Find your real database: it lives at `~/.local/share/Site & Pattern/`
   (Linux), `%APPDATA%/Site & Pattern/` (Windows), or
   `~/Library/Application Support/Site & Pattern/` (macOS) — *outside* the
   code folder. Don't edit anything there; just know it exists. The code is
   the recipe; that folder is the cooked meal.

**Checkpoint:** you can run the app, run the tests, and say what branch
you're on — without asking anyone.

---

## Phase 1 — Python fundamentals (6–10 weeks)

The core investment. Use an external course for structure, and this repo as
your "field site" where you spot each new concept in the wild.

**Learn (external — pick ONE main track):**
- [*Automate the Boring Stuff with Python*](https://automatetheboringstuff.com)
  (free online) — practical, beginner-first, well-loved. Chapters 1–11 are
  the core.
- Alternative: the official [Python tutorial](https://docs.python.org/3/tutorial/)
  (drier, but authoritative) or [futurecoder.io](https://futurecoder.io)
  (interactive, in-browser).
- When code confuses you, paste it into
  [pythontutor.com](https://pythontutor.com) and step through it visually.

Concepts you must exit this phase with: variables, strings, numbers, `if`,
loops, **functions**, **lists and dictionaries** (this app is dictionaries
all the way down — a plant is a dict, a project is a dict, a map feature is
a dict), modules and `import`, reading error tracebacks, and a first
acquaintance with classes (`class`, `self`) — fluency with classes can wait.

**Do (in this repo — the "spot it in the wild" game):** after each course
chapter, open one of these files and find the concept you just learned.
They're ordered by size and difficulty; all are pure Python, no Qt, no
database:

| Step | File | Lines | What you'll recognize |
|---|---|---|---|
| 1 | `src/branding.py` | 35 | Variables and strings. The app's name lives here. |
| 2 | `src/app_version.py` | 38 | Functions, reading a file, `try/except`. |
| 3 | `src/errors.py` | 46 | Classes as labeled error types. |
| 4 | `src/geometry.py` | 70 | Functions doing math on lat/lng pairs. |
| 5 | `src/member_colors.py` | 92 | Dictionaries as lookup tables. |
| 6 | `src/projection.py` | 98 | A class with methods; why "the map only stores lat/lon". |
| 7 | `src/succession.py` | 131 | Everything above, in service of ecology you already understand. |

`src/succession.py` is a milestone: it computes which plants fade in/out as
a design matures — pioneer species out, climax species in. You understand
the *ecology* perfectly; by the end of this phase you'll understand the
*code*, and feeling those two click together is the whole game.

**Checkpoint:** open `src/succession.py`, read `years_to_maturity` and
`presence_factor` (or whatever function catches your eye), and explain to a
rubber duck / notebook what each line does. Then open
`tests/test_succession.py`, pick one test, predict whether it passes, and run
just that file:
```bash
python -m unittest tests.test_succession
```

---

## Phase 2 — Tests as your textbook (2–4 weeks)

The `tests/` folder is the best documentation in this repo, because it can't
go stale — it *runs*. Each test says "given this input, the app must do
that." Learning to read tests gives you a superpower: you can verify your
understanding of any module experimentally.

**Learn:** the shape of a stdlib `unittest` test — a class, `setUp`, methods
named `test_*`, and assertions (`assertEqual`, `assertTrue`). Ten minutes
with any unittest intro; then it's just reading.

**Do:**
1. Read `tests/test_succession.py` (134 lines) alongside `src/succession.py`.
   For each test, find the function it exercises.
2. Play the **break-it game** (this is safe — git undoes everything):
   change a number in `src/succession.py` (say, a default in
   `_DEFAULT_YTM`), run `python -m unittest tests.test_succession`, and read
   the failure message top to bottom. Then restore with
   `git checkout -- src/succession.py`. Do this until failure output feels
   like information instead of an alarm.
3. Read `tests/test_phenology.py` and `tests/test_projection.py` the same
   way.
4. Skim `tests/test_architecture_guard.py` — don't try to understand the
   code, just the *idea*: this project's architectural rules (file-size
   ceilings, frozen APIs, forbidden patterns) are written down **as tests**,
   so breaking a rule fails the build instead of relying on memory. When a
   guard test fails on you someday, the `.claude/skills/testing` skill
   explains whether to fix your code or update the snapshot.

**Checkpoint:** you can deliberately break a module, predict which test
fails, confirm it, and restore it.

---

## Phase 3 — The data layer: where the plants live (3–5 weeks)

Everything the app knows about plants, fauna, and communities sits in a
SQLite database seeded from JSON files in `data/`. This layer is the most
learnable subsystem — it's concrete, inspectable, and Qt-free.

**Learn (external):**
- SQL basics: [sqlbolt.com](https://sqlbolt.com) (free, interactive) —
  lessons 1–12. You need `SELECT`, `WHERE`, `JOIN`, and what a foreign key
  is.
- JSON: you already half-know it — it's the same braces-and-brackets as
  Python dicts and lists.

**Do:**
1. Open `data/plants_master.json` and find a plant you know from your own
   yard. Every field there becomes a database column or junction row.
2. Read `docs/DATABASE_SCHEMA.md` (the narrative), then skim
   `src/db/schema.sql` (the authoritative definition) with it side by side.
3. Open a **copy** of your real database (never the original) with the
   `sqlite3` command-line tool or a GUI like
   [sqlitebrowser.org](https://sqlitebrowser.org), and run your first
   queries:
   ```sql
   SELECT common_name, plant_type FROM plants WHERE plant_type = 'shrub';
   ```
4. Trace the full pipeline in prose: JSON in `data/` → seeding
   (`src/db/seed_data.py`) → tables (`schema.sql`) → query functions
   (`src/db/plants.py:search_plants`) → the plant panel on screen. You don't
   need to read all 1,900 lines of `src/db/plants.py` — read
   `search_plants` and skim the rest's docstrings.
5. Read the "Schema versioning" section of `CLAUDE.md` until the
   reseed model makes sense: bumping `_SCHEMA_VERSION` makes every user's
   install wipe-and-reseed the *catalogue* tables (never user-authored data)
   on next launch. This is the single most important convention in the repo,
   and forgetting the bump is its classic historical bug.

**Checkpoint:** you can answer, without help: "If I add a plant to
`plants_master.json`, what two other things must happen before a user ever
sees it?" (Answer: the `_SCHEMA_VERSION` bump in `src/db/plants.py`, and a
reseed on their next launch — which the bump triggers.)

---

## Phase 4 — The architecture: how the pieces talk (4–6 weeks)

Now the big picture. The app follows one repeating pattern, and once you see
it, the 100+ files in `src/` collapse into a handful of shapes.

**The pattern (plain-language version):**

- **Qt-free core** (`src/wind.py`): pure logic — fetch, compute, decide.
  No GUI imports. Testable by plain Python. *This is where truth lives.*
- **Flow module** (`src/wind_flow.py`): glue — connects the core to the main
  window, moves slow work off the UI thread.
- **Widget** (`src/wind_rose_widget.py`): pixels only. Draws what the core
  computed; computes nothing itself.
- **Wiring** (`src/app.py`): the main window connects signals ("user clicked
  X") to flows, one line each.

**Do (in order — this is the repo's official onboarding path, slowed down):**
1. Read `src/project.py` with `docs/PROJECT_FILE_FORMAT.md` beside it. A
   saved design is one GeoJSON file; every placed plant, boundary, and
   structure is a "feature" dict inside it. This is the app's spine.
2. Read `src/project_store.py`'s docstring and skim its methods. Rule: *all*
   changes to placed plants go through this one file — and a test greps the
   whole tree to enforce it. (The `.claude/skills/placed-plants` skill tells
   the story.)
3. Trace the **wind triad** end to end: `src/wind.py` →
   `src/wind_flow.py` → `src/wind_rose_widget.py` → search for "wind" in
   `src/app.py` to find its wiring. This exemplar was chosen because it's
   the cleanest; every other feature is a variation on it.
4. Now skim `src/app.py` (2,200 lines — skim, don't read): the layout
   section, the menu section, `_connect_signals`. Notice it *does* almost
   nothing itself; it delegates. Then skim the `src/controllers/` directory
   listing to see where the delegated behaviour lives.
5. Read the "Onboarding reading order" and decision tree in
   `.claude/skills/codebase-map/SKILL.md` — the map of where any new code
   belongs.

**Learn (external, light):** you do *not* need a PyQt6 course. When widget
code confuses you, the tutorials at
[pythonguis.com](https://www.pythonguis.com) (Martin Fitzpatrick) are the
standard reference — dip in per-topic (signals/slots first).

**Optional bolt-on, whenever curiosity strikes:** the map is JavaScript
(Leaflet) inside the Python window — `html/map/01-core.js` through
`06-overlays.js`, bridged to Python via QWebChannel. Treat it as a second,
smaller language to pick up later; the
[MDN "First steps" JS course](https://developer.mozilla.org/en-US/docs/Learn_web_development)
plus the `.claude/skills/map-frontend` skill cover it. Nothing else in the
roadmap depends on it.

**Checkpoint:** draw the app from memory — boxes for map / panels / project
dict / ProjectStore / DB / Qt-free cores, arrows for who calls whom. Compare
against the subsystem map in `.claude/skills/codebase-map/SKILL.md`.

---

## Phase 5 — Your first solo changes (ongoing)

Real changes, on a real branch, graduated by risk. For each one: make the
change yourself (Level 3–4 on the AI ladder), run the suite, commit with a
clear message, and follow the V-branch convention from CLAUDE.md.

**The ladder — in order:**

1. **A copy change.** Reword a tooltip or label (many live in the panel
   files and `src/branding.py`). Teaches: edit → run app → see it → commit.
2. **A seed-data change.** Add one plant you know well to
   `data/plants_master.json` (copy a similar entry; the required fields and
   quality gate are in the `.claude/skills/seed-data` skill), bump
   `_SCHEMA_VERSION`, run the suite, launch the app, find your plant.
   This exercises the full Phase 3 pipeline.
3. **A test-first logic tweak.** Pick a small behaviour in a Qt-free core
   you'd like different (a threshold in `src/succession.py`, a label, a
   default). Write the failing test *first*, then make it pass.
4. **A tiny feature via the triad.** Something small that follows the wind
   exemplar. Read `.claude/skills/add-feature` first — it's the playbook —
   and let AI review your plan before and your diff after (not write them).
5. **A bug of your own choosing.** Next time you hit a real bug while using
   the app, resist reporting it to AI. Reproduce it, hypothesize a file,
   add `print()` calls or use `breakpoint()`, and hunt. Ask for hints, not
   fixes. Your first self-found, self-fixed bug is graduation.

**House rules that protect you** (all from CLAUDE.md — reread it now; it
will finally all make sense):
- Branches are `V<major>.<minor>`; a hook auto-enforces this.
- Schema or seed-data change ⇒ `_SCHEMA_VERSION` bump. Always.
- Never mutate placed-plant state outside `src/project_store.py`.
- All distance/area math goes through `src/projection.py`.
- The P12 hard rule: no Indigenous knowledge is encoded into data,
  recommendations, or UI without free, prior, and informed consent — stop
  and think any time work drifts near it.
- When a guard test fails, it's telling you which rule you tripped —
  `.claude/skills/testing` maps each guard to the right response.

---

## Reference shelf

**In this repo, in the order they become useful:**

| When | Read |
|---|---|
| Phase 0 | `INSTALL.md`, `docs/BUILD.md`, `docs/USER_GUIDE.md` |
| Phase 1–2 | The small `src/` files in the Phase 1 table + their tests |
| Phase 3 | `docs/DATABASE_SCHEMA.md`, `src/db/schema.sql`, CLAUDE.md §Schema versioning |
| Phase 4 | `docs/PROJECT_FILE_FORMAT.md`, `.claude/skills/codebase-map/SKILL.md`, `docs/DESIGN_PHILOSOPHY.md` |
| Phase 5 | `.claude/skills/add-feature`, `seed-data`, `testing`, `debugging`, `start-work` |
| Anytime | `.claude/skills/legacy-lessons` — the war stories behind every odd-looking rule |

**External (all free):** Automate the Boring Stuff (Python) ·
pythontutor.com (visualize execution) · learngitbranching.js.org (git) ·
sqlbolt.com (SQL) · pythonguis.com (PyQt6, per-topic) · MDN (JavaScript,
later).

**A note on morale.** There will be a stretch — usually mid–Phase 1 — where
you can read individual lines but whole files still feel like fog. That fog
is normal, it's temporary, and it lifts through exposure, not talent. You
built the philosophy this app runs on; the code is just that philosophy
written very, very precisely. Keep a notebook, log one "today I understood
X" per session, and let the test suite tell you you're doing fine.
