# Phase 3 — The data layer: where the plants live

**Goal:** everything the app knows — plants, fauna, who-feeds-whom — sits
in a SQLite database seeded from the JSON files you met in L1.6. This
phase teaches you SQL, the schema, and the full pipeline from JSON to
screen, ending with a safe practice run of the repo's most important
convention. **Time:** ~12 hours across 3–5 weeks. **Lessons:** 5.

Ritual: tick [PROGRESS.md](PROGRESS.md) → `python scripts/learning_progress.py`
→ commit `Learning: Lx.y complete`.

---

### L3.1 — SQL on training wheels

*Time: ~4 h (split over several sittings) · Builds on: L2.4*

**Purpose:** SQL is a second, smaller language — but it reads almost like
English, and twelve short interactive lessons cover everything this app's
database asks of you.

**Aim:** finish [sqlbolt.com](https://sqlbolt.com) lessons 1–12, and prove
it by translating a query into English from sight.

**Steps:**
1. Work through SQLBolt lessons 1–6: `SELECT`, `WHERE`, filtering and
   sorting. These are the daily-driver skills.
2. Continue through lesson 12: `JOIN` (two tables linked by an id — the
   concept L3.2 hangs on), plus counting and grouping with aggregates.
3. No repo work this lesson — let the ideas set. But as you go, journal
   one running list: SQL words you've seen (`SELECT`, `WHERE`, `JOIN`,
   `GROUP BY`) with a one-line meaning each, in your words.
4. Final check, from sight (no running it): translate into English —
   `SELECT common_name FROM plants WHERE plant_type = 'shrub' ORDER BY common_name;`

**Done when:** SQLBolt lessons 1–12 are complete and your translation is
in the journal.

---

### L3.2 — Reading the blueprint: the schema

*Time: ~2 h · Builds on: L3.1*

**Purpose:** `src/db/schema.sql` is the single authoritative definition of
every table in the app. Reading a schema is like reading a seed
catalogue's legend — once you can, the whole database stops being a black
box. And this schema contains something lovely: ecology encoded as rules.

**Aim:** a journal sketch of the plants↔fauna relationship — three boxes,
two arrows — plus an explanation of why the middle table exists.

**Steps:**
1. Read `docs/DATABASE_SCHEMA.md` first — it's the narrated tour.
2. Open `src/db/schema.sql` beside it. Find the `plants` table (line ~1)
   and skim its columns — most will be old friends from L1.6, because the
   JSON fields became columns.
3. Find `fauna` (~line 178) and `plant_fauna` (~line 197). Read
   `plant_fauna` closely: it's nothing but two id columns and a
   `relationship`. Sketch the three tables as boxes, with arrows from
   `plant_fauna` to each neighbour.
4. Journal question: why can't a "which creature uses which plant" fact
   live *inside* the plants table? (Hint: one chokecherry feeds dozens of
   species — and one chickadee uses dozens of plants. Many-to-many needs
   a middle table. This is Principle 3 — the relationship itself is the
   unit of value — as a database shape.)
5. Find the `CHECK` constraint on `plant_fauna.relationship`: the database
   itself refuses any relationship type outside `larval_host`, `nectar`,
   `pollen`, `seed_food`, `fruit_food`, `nesting`, `cover`. Ecology,
   enforced by SQL.

**Done when:** your sketch is drawn and your journal explains, in your own
words, what a junction table is and why `plant_fauna` must be one.

---

### L3.3 — Querying the real catalogue

*Time: ~2 h · Builds on: L3.2*

**Purpose:** time to run SQL against the app's *actual* database — the one
your running app reads. Working on a copy, you can ask it anything with
zero risk, including the question this whole app exists to answer.

**Aim:** three queries against a copy of your real database, ending with a
two-JOIN query answering "which of my plants feed which creatures?"

**Steps:**
1. Find your real database (L0.4 of the roadmap): the file
   `permadesign.db` inside the Site & Pattern data folder for your OS
   (on Linux `~/.local/share/Site & Pattern/`). **Copy it** somewhere
   scratch — never open the original:
   `cp "path/to/permadesign.db" ~/plants-copy.db`
2. Open the copy with the `sqlite3` terminal tool
   (`sqlite3 ~/plants-copy.db`) or, if you prefer buttons, 
   [DB Browser for SQLite](https://sqlitebrowser.org). In `sqlite3`,
   `.tables` lists tables and `.quit` exits.
3. Query 1 (warm-up): all shrubs, alphabetized — you wrote this from
   sight in L3.1; now run it for real.
4. Query 2 (aggregate): `SELECT plant_type, COUNT(*) FROM plants GROUP BY plant_type;`
5. Query 3 (the payoff):
   ```sql
   SELECT p.common_name AS plant, f.common_name AS creature, pf.relationship
   FROM plants p
   JOIN plant_fauna pf ON pf.plant_id = p.id
   JOIN fauna f ON f.id = pf.fauna_id
   WHERE f.taxon = 'bird'
   ORDER BY p.common_name;
   ```
   Read a few rows out loud. Paste query and a sample of results into
   your journal. Swap `'bird'` for `'bee'` or `'lepidoptera'` and run it
   again — this is the app's beating heart, and you just queried it by
   hand.

**Done when:** all three queries ran against your copy and the journal has
query 3 plus results — and you can point at which part of it is the
junction table doing its job.

---

### L3.4 — Follow a plant from JSON to screen

*Time: ~2 h · Builds on: L3.3*

**Purpose:** you've now touched every station of the data pipeline
separately. Tracing one plant through all of them — file to table to query
to pixels — is the moment the data layer becomes one connected picture
instead of four facts.

**Aim:** a five-hop written trace of a single named plant, with a file (and
function) named at every hop.

**Steps:**
1. Pick a plant you love. Find its entry in `data/plants_master.json`
   (your editor's search: Ctrl/Cmd-Shift-F across the folder).
2. Hop 2 — seeding: open `src/db/seed_data.py` and find the code that
   reads `plants_master.json` and inserts rows. You're skimming for the
   shape, not memorizing: JSON fields in, `INSERT` out.
3. Hop 3 — storage: confirm your plant exists as a row in your L3.3 copy:
   `SELECT * FROM plants WHERE common_name LIKE '%<name>%';`
4. Hop 4 — query: open `src/db/plants.py` and find `search_plants` (the
   function the plant browser calls). Find the SQL inside it — it's the
   grown-up cousin of your query 1.
5. Hop 5 — pixels: open `src/plant_panel.py` and search for
   `search_plants` to find the call site. Then launch the app, search for
   your plant, and watch hop 5 happen. Journal the full trace:
   `plants_master.json → seed_data.py → plants table → search_plants() → plant_panel.py → screen`,
   with one sentence per hop.

**Done when:** the five-hop trace is in your journal and every hop names a
real file you personally opened.

---

### L3.5 — Capstone: the schema-version fire drill

*Time: ~2 h · Builds on: L3.4*

**Purpose:** the repo's most important convention: change the seed data →
bump `_SCHEMA_VERSION` → every install reseeds on next launch. Forgetting
the bump is this project's classic historical bug. You're going to run the
whole drill once, safely, on a scratch branch — so that in Phase 5, doing
it for real is routine.

**Aim:** a seed-data change made visible in the running app via a version
bump — then fully reverted, with a journal explanation of the mechanism.

**Steps:**
1. Make a scratch branch so everything is throwaway:
   `git checkout -b learning-fire-drill`
2. In `data/plants_master.json`, find your L3.4 plant and make a harmless,
   *visible* edit — add a sentence to its `notes` field.
3. The bump: in `src/db/plants.py`, find `_SCHEMA_VERSION` near the top
   and increase it by 1. (Read the comment block around it — it says
   exactly what you're triggering.)
4. Run the suite (`python -m unittest discover -s tests` — the seeding
   tests exercise your change against a temp database), then launch the
   app, open your plant's details, and find your sentence. That's the
   reseed doing its one-time job on *your real* database.
5. Clean up: `git checkout V2.28` (or whatever branch you were on — 
   `git branch` shows you), then `git branch -D learning-fire-drill`.
   Journal, in your own words: what did the bump *cause*, and what would
   have happened without it? (Note: your real DB reseeds once more on
   next launch, back to the shipped data — harmless by design, and worth
   one journal sentence about *why* it's harmless: the catalogue tables
   are rebuilt from shipped JSON; your designs live in `.perma.geojson`
   files, untouched.)

**Done when:** you saw your sentence in the running app, the branch is
deleted, `git status` is clean — and your journal explains the
change→bump→reseed chain without notes.

---

**Phase complete.** You understand the app's memory. Next, its anatomy:
[phase-4-architecture.md](phase-4-architecture.md).
