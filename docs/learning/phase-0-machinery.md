# Phase 0 — Operate the machinery

**Goal:** before understanding any code, learn to *drive* — the terminal,
the app, the tests, and git. Everything later stands on these four skills.
**Time:** ~5 hours across 1–2 weeks. **Lessons:** 4.

After each lesson: tick its box in [PROGRESS.md](PROGRESS.md) and run
`python scripts/learning_progress.py` to watch the bar move. (Committing
your ticks starts in L0.4 — that lesson teaches you how.)

---

### L0.1 — Home in the terminal

*Time: ~1 h · Builds on: nothing*

**Purpose:** every lesson in this curriculum happens partly in a terminal.
Being at home there — knowing where you *are* and what's *around you* — is
the difference between following recipes and driving.

**Aim:** from a freshly opened terminal, navigate to this repository, list
its contents, and open the project in a text editor — without looking
anything up.

**Steps:**
1. Install a text editor if you don't have one. VS Code (free) is the
   default choice; any editor that can open a *folder* works.
2. Open a terminal. Learn the three orientation commands by using them:
   `pwd` (where am I), `ls` (what's here), `cd <folder>` (go there).
   `cd ..` goes up one level. Spend 15 minutes just wandering your own
   computer with these.
3. Navigate to this repository's folder. Run `ls` — you should recognize
   `main.py`, `src`, `docs`, `data`, `tests` from the roadmap.
4. Open the repository folder in your editor (in VS Code: File → Open
   Folder). Find this file (`docs/learning/phase-0-machinery.md`) in the
   editor's file tree, and also reach it in the terminal with
   `ls docs/learning`.
5. In your editor, open `docs/learning/journal.md` and write your first
   entry: today's date and one sentence.

**Done when:** you can close the terminal, reopen it, and get to the repo
folder and list its files from memory — and the journal has its first entry.

---

### L0.2 — Run the app from source

*Time: ~1–2 h (mostly one-time setup) · Builds on: L0.1*

**Purpose:** the code in this folder and the app on your screen are the
same object. Launching the app *from the code* makes that real, and it's
how you'll verify every change you ever make.

**Aim:** launch Site & Pattern from the terminal, place a plant, save a
design, and find the saved file on disk.

**Steps:**
1. Follow `INSTALL.md` (and `docs/BUILD.md` if needed) to set up Python
   and the dependencies. This is the fiddliest step of the whole phase —
   one-time pain, and asking AI to explain *error messages* here is fair.
2. From the repo folder, run: `python main.py`
3. In the app: draw a property boundary, place two or three plants.
4. File → Save. Name it something like `my-yard.perma.geojson` and save it
   somewhere you'll find it (e.g. your Documents folder).
5. Back in the terminal, `cd` to where you saved it and confirm it's there
   with `ls`. That single file *is* your whole design — Phase 4 opens it up.

**Done when:** you can quit everything and repeat launch → open your saved
design in under a minute.

---

### L0.3 — The test suite is your seatbelt

*Time: ~1 h · Builds on: L0.2*

**Purpose:** this repo contains ~1,800 automated checks that verify the app
still behaves correctly. They are what will let you change code *without
fear* — every experiment in this curriculum ends with "run the tests."

**Aim:** run the full suite, understand its verdict line, and run a single
test module on its own.

**Steps:**
1. From the repo folder run: `python -m unittest discover -s tests`
   It takes ~10 minutes. Let it run; watch the dots and letters stream by
   (`.` = pass, `s` = skipped, `F` = failure, `E` = error).
2. Read the final three lines. You should see something like
   `Ran 1770 tests`, then `OK (skipped=202)`. Skips are normal (some tests
   need a display or optional libraries). `OK` is the word that matters.
3. Now run just one module — this takes under a second:
   `python -m unittest tests.test_succession`
   Note the name form: `tests.test_succession`, dots not slashes, no `.py`.
4. In your journal, answer: what would it mean if the last line said
   `FAILED (failures=1)` instead of `OK`?

**Done when:** you can state what `OK` means, what a failure would look
like, and run any single test module by name without notes.

---

### L0.4 — Git is a time machine (and your progress journal)

*Time: ~1–2 h · Builds on: L0.3*

**Purpose:** git makes every experiment reversible, which removes the fear
of breaking things — and from today, its history is the real-time record of
your learning. This lesson makes your progress *visible* for the first
time.

**Aim:** your first learning commit: Phase 0 ticked off in PROGRESS.md, the
progress bars showing it, and the commit in the log.

**Steps:**
1. Do the "Main" intro sequence at
   [learngitbranching.js.org](https://learngitbranching.js.org) (~45 min).
   You need the ideas *commit* and *branch*; the rest can wait.
2. In the repo, run the three inspection commands and read their output:
   `git status` (what's changed), `git log --oneline -15` (recent history),
   `git diff` (the changes themselves, line by line).
3. In your editor, open `docs/learning/PROGRESS.md` and tick L0.1 through
   L0.4 — change `[ ]` to `[x]`.
4. Run `git diff` again — see your ticks as `-`/`+` lines. This is how all
   change in this repo is seen and reviewed.
5. Run the tracker: `python scripts/learning_progress.py` — Phase 0 should
   read 4/4, 100%.
6. Commit it:
   `git add docs/learning/PROGRESS.md docs/learning/journal.md`
   `git commit -m "Learning: Phase 0 complete"`
   Then `git log --oneline -3` to see your commit sitting on top.

**Done when:** the tracker shows Phase 0 at 100% and `git log` shows a
commit you made yourself.

---

**Phase complete.** From here on, the ritual after every lesson is: tick the
box → run the tracker → commit `Learning: Lx.y complete`. Next:
[phase-1-python.md](phase-1-python.md).
