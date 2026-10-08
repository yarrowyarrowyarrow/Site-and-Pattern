# CLAUDE.md — Working Notes for Claude Code Sessions

This file is read automatically at the start of every Claude Code session
in this repository. It documents conventions and context that are easy to
miss otherwise.

## Project at a glance

**Site & Pattern** is a PyQt6 desktop app (Python 3.10+) for designing
landscapes with native plants — focused on lawn-to-habitat conversion,
pollinator gardens, and ecological restoration in Alberta and the
Canadian prairies. Local SQLite storage; Leaflet inside QWebEngineView
for the map; PyInstaller + NSIS for the Windows installer.

Entry point: `python main.py` → `src.app.MainWindow`.

The product was named **PermaDesign** before the V1.69 rebrand; user-facing surfaces
now read **Site & Pattern** (`src/branding.py`), while several internal identifiers keep
the legacy name on purpose (see the Database-path note below). The design philosophy that
drives the app lives in `docs/DESIGN_PHILOSOPHY.md` — strongly-aligned modules carry a
one-line `Design principle P#` anchor pointing back to it, guarded by
`tests/test_philosophy.py`.

## Design philosophy (read this first — weave it through your work)

This project is not a generic plant-placement tool; it is built on a coherent philosophy, and
work that ignores it tends to be technically fine but spiritually off. Before designing a
feature, skim where it sits in that philosophy. The sources of truth:

- [`docs/DESIGN_PHILOSOPHY.md`](docs/DESIGN_PHILOSOPHY.md) — the thirteen principles, each with a
  "Where this lives in the code" note and an honest **State** marker (*strong / partial / gap*).
- [`docs/BACKLOG.md`](docs/BACKLOG.md) — **everything not yet built, in one place** (V2.52). Read
  this before re-deriving the backlog from the two roadmaps; it is the index, and it carries the
  verified status of every open ID.
- [`docs/ROADMAP_NEXT.md`](docs/ROADMAP_NEXT.md) — the live plan and the *reasoning* per feature,
  plus the **ID ledger** (F63–F171) and the shipped record. Feature IDs have collided four times;
  take the next free ID from that ledger, never from memory.
- [`docs/PHILOSOPHY_ROADMAP.md`](docs/PHILOSOPHY_ROADMAP.md) — features (F1–F62) organized by the
  principle they serve, with a "Shipped" section at the top.
- [`docs/REFERENCES.md`](docs/REFERENCES.md) — the full bibliography.

**The thirteen principles, in one line each:**

1. Living systems self-organize from the bottom up — encode generative rules, not fixed layouts.
2. The best designs disappear into their context — aim for "grown, not designed".
3. Relationships matter more than components — the edge between species is the unit of value.
4. Time is the most undervalued design variable — design the trajectory, not the install day.
5. Perception is constructed, not received — make invisible ecology *visible*.
6. Conventional value metrics miss ecological value — make ecological value legible.
7. Generalist knowledge produces the most original insights — cross domains deliberately.
8. Repair is more sophisticated than creation — restoration/conversion is first-class.
9. Uncertainty is a feature, not a bug — ship ranges and confidence, never false precision.
10. Design for relationships, not objects — plants are nodes in a network.
11. The body and the site know things the screen does not — drive the user outside.
12. Indigenous knowledge is honoured through relationship, not extraction.
13. A native planting has to be loved to survive — beauty is the mechanism the ecology
    survives contact with people by, not decoration on top of it (adopted V2.33).

**HARD RULE (P12):** Do **not** incorporate Indigenous ecological knowledge, land-management
practices, plant-use traditions, or design frameworks into the data model, recommendations, seed
data, or UI without explicit **free, prior, and informed consent** from the relevant communities.
Until that consent exists, treat any reference as *directional only* — point toward the knowledge,
never encode or operationalize it. If a task seems to push in that direction, stop and raise it
with the user rather than proceeding.

**Keep the weave intact.** When you build something strongly aligned with a principle, add the
`Design principle P# — see docs/DESIGN_PHILOSOPHY.md` anchor at the top of the file, and keep the
doc's State markers and the roadmap's Shipped section honest. `tests/test_philosophy.py` guards
that the doc documents all thirteen themes and that every anchor names a real principle (1–13).

## Branch naming convention (READ FIRST)

**Release branches are named `V<major>.<minor>`** — for example `V1.31`,
`V1.32`, `V1.33`. Each release branch contains a single increment of work.

When starting a new piece of work:
- Inspect the existing branches (local + `origin/`) to find the highest
  numbered `V<major>.<minor>`.
- Create the next branch by **incrementing the minor version by 1**
  (e.g. if `V1.32` is the latest, start `V1.33`).
- Push the new branch to `origin` when work is committed.

**Do not** create branches with the FleetView-style codename pattern
(`claude/wizardly-goldberg-Ntd5l`, etc.), and do not push to such a
branch even if the harness suggests one as the default. If the system
default branch is a codename, override it and use the next `V*.*`.

**Releases up to V2.79 also have a TAG of the same name, and that is a trap
(V2.72; fixed for new releases in V2.80).** `V2.71` names both
`refs/heads/V2.71` and `refs/tags/V2.71`. If both are in a clone, git refuses to
guess: `git push -u origin V2.71` fails with *"src refspec V2.71 matches more
than one"*. Worse, **`git pull origin V2.71` does not refuse** — it silently
resolves the tag, rebases your branch onto it, and rewinds you to whatever
commit that tag points at. That happened during V2.80 and undid a pushed fix
without a single error message.

**New releases tag `release-V<major>.<minor>`** (both workflows'
`tag_name:`), which collides with nothing. `github_releases._TAG_RE` accepts
both spellings and **must keep accepting the old one**: ~102 remote tags use it
and each anchors a GitHub Release the in-app updater reads by `tag_name`.

The old tags are still out there, so a clone that has fetched them still has the
collision for those versions. Fix a clone once with:

```bash
git config remote.origin.tagOpt --no-tags   # or a bare fetch drags all 102 back
git tag -d $(git tag)                       # local refs only; remote untouched
```

and prefer `git switch <V>` (branches only) over `git checkout <V>`, and
`git push -u origin HEAD` over naming the branch.

**To get a release branch that is not in the clone yet** — the case that bites
first, because the obvious command is the broken one:

```bash
git fetch origin refs/heads/V2.78:refs/remotes/origin/V2.78
git switch V2.78
```

Both halves of that refspec are load-bearing. `refs/heads/` says *the branch,
not the tag*, and without it git may resolve the tag instead. The
`:refs/remotes/origin/...` half says where to put it, and without it even a
correctly resolved branch lands only in `FETCH_HEAD`, leaving `git switch`
nothing to find. Two failure messages, so the next person can match rather than
re-diagnose:

| message | what happened |
|---|---|
| `fatal: invalid reference: V2.78` | no local ref of that name at all; the fetch went to `FETCH_HEAD` only. Use the refspec above. |
| `fatal: a branch is expected, got tag 'V2.78'` | a local tag of that name exists. Run the `git tag -d` cleanup above. |
| `* tag V2.78 -> FETCH_HEAD` then `Successfully rebased` | **the silent one.** `git pull origin V2.78` took the tag, and your branch is now at the tag's commit — behind the branch, with pushed work missing and no error. Recover with the refspec fetch above plus `git switch -C V2.78 origin/V2.78`. |

**Never use `git pull` for a V-branch.** Always the two-line refspec fetch, then
`git switch`. The tag/branch collision means `pull` has no safe form here for
any release up to V2.79.

**Never delete the remote tags**: each anchors a GitHub Release, and
`github_releases.parse_release_version` reads `tag_name` off those releases to
drive the in-app updater.

**One branch, one version: V2.81 and V2.82 are the cautionary case.** Both were
committed on the `V2.80` branch, so each push re-ran the release workflows
against the existing `release-V2.80` release, whose tag still points at the
25 Aug commit (schema v78). The updater compares `(major, minor)` only, so an
install from 25 Aug believes it is current and never received v78 → v85.
Their plan files keep their numbers; **the next branch after them is V2.83**.
The hook below proposes newest-on-origin + 1, which reads V2.81 until V2.83 is
pushed, so check `docs/plans/` for a higher number before accepting it.

**This is now auto-enforced** by `.claude/hooks/branch_policy.py` (wired in
`.claude/settings.json`), so it no longer depends on remembering:
- On **SessionStart** the hook computes the next V-branch
  (`src/version_branch.py:next_version_branch` = newest `origin/V*.*` + 1 minor,
  or the current branch if it's already a V-branch) and, when the session starts
  on a `claude/*` codename / `main` / detached HEAD, **switches to it**
  (`git checkout -B <V>` from the current commit, no-clobber) and injects a
  directive into context. This **overrides** any harness-supplied "Git
  Development Branch Requirements" that names a codename branch.
- A **PreToolUse** guard **blocks** any `git push`/branch-create to a `claude/*`
  branch (deletes of codename branches are allowed — that's cleanup). Both hooks
  fail open so a hook bug can never block real work.

The "Check for Updates" button in the app
(`src/controllers/update_flow.py:_on_check_for_updates`) relies on this
convention to detect new versions on the server. Breaking the convention
silently breaks that feature. (V2.25: source checkouts update in-app with
one click — a stash-aware `git checkout -B <V> origin/<V>` + restart
prompt; the destructive `reset --hard` path deleted in V2.22 stays dead
and is pinned out by `tests/test_architecture_guard.py`. Frozen builds
update via GitHub Releases.)

## Schema versioning

The SQLite schema version is at `src/db/plants.py:_SCHEMA_VERSION`. The
current value is the one shipped with the latest `V*.*` branch.

**Always bump `_SCHEMA_VERSION` when you change `src/db/schema.sql` or
when the seeded data (`data/plants_master.json`, `data/garden_plants.json`,
`data/fauna_master.json`, `data/plant_fauna_master.json`) changes
meaningfully.** A bump triggers a one-time reseed on the user's next
launch — without it, existing installs will not pick up new tables or
new rows.

The reseed path (`src/db/plants.py:init_db` → "needs_reseed" block)
wipes `plants`, `planting_calendar`, `companion_friends`,
`companion_enemies`, `uses`, `plant_uses`, `fauna`, `plant_fauna` (and
the attribute/nursery/cache tables) and re-seeds them from the shipped
JSON. **Add any new dependent tables to that wipe list** or they will
accumulate stale rows across reseeds. **Never wipe a table holding
user-authored rows**: `polycultures` / `polyculture_members` and `plant_photos` are wiped
only where `origin='seed'` (schema v46 / v55) so builder-authored communities
survive upgrades — user member `plant_id`s are re-pointed by name after
the plants wipe (`_remap_user_polyculture_plants`), because plant ids
are NOT stable across reseeds.

## Save the plan (READ THIS BEFORE STARTING WORK)

**Every increment leaves a plan behind**, in `docs/plans/`, named
`V<major>.<minor>-<short-slug>.md` — version first, matching the branch
convention above, so plans sort in release order and pair with the branch that
carried them out. Write it before the work, amend it as investigation changes
your mind, and commit it alongside the code.

A plan records the *reasoning*: what was measured, what was decided and why,
what was deliberately left alone, and what could not be verified. The commit log
already says what changed. See [`docs/plans/README.md`](docs/plans/README.md)
for the house style and the index of past plans — and **add a row to that index
table** when you add a plan.

## Hand back a test plan (DO THIS AT THE END OF EVERY INCREMENT)

A green test suite tells the *author* the code works. It tells the **user**
nothing, because they cannot see it, and "I added a relationship web" is not
something a person can go and check. Every increment therefore ends with a
short **How to test this** section in the final reply — not in a doc, in the
reply, where it will actually be read.

For each user-visible thing that was added or changed, give:

1. **Where it is.** The literal click path from a cold start.
   *"Open the app → right panel → Analysis tab → Relationships sub-tab →
   tick 'Relationship web'."* Not "in the analysis panel".
2. **What you need first.** The preconditions, stated plainly — a design with
   plants placed, a boundary drawn, a site pin, an internet connection. Most
   "it doesn't work" reports are an unmet precondition.
3. **What you should see** when it works, concretely enough to disagree with.
   *"A ring of animal chips appears outside the planting, with lines running
   to the plants that support them."*
4. **What tells you it is broken.** The failure mode that is easy to mistake
   for "working but empty" — an empty list, a stale list, a silent skip.
5. **The fastest way to check it without the GUI**, when one exists — a
   `python3 -c` one-liner against `src/permadesign_api.py`, a script in
   `scripts/`, a single test module. Give the command, ready to paste.

Also say plainly **what you could not test yourself** and why (no display, no
network, needs a real desktop, needs data nobody has yet). An untested claim
labelled as tested is worse than an admitted gap.

Keep it to the things a person can actually see. Internal refactors, schema
bumps and guard tests do not need a click path — say in one line what would
have broken if it went wrong, and move on.

## Explain every command you hand over (ADOPTED V2.61)

**The owner of this repo is learning the tooling by using it.** So a command
is never handed over bare. Whenever you give a shell command to run — git,
a fetch script, a one-liner probe — say **what it does, why that one, and what
its output will mean** before they run it, in a sentence or two each.

This is not padding. It has already paid for itself three times in one week:

- `--observations` typed as `-- observations` silently ran a *different mode*
  for two hours and produced an identical uncited file, because nobody had
  explained that the space made it two arguments.
- `git pull` alone could not fetch a new release branch, which is not obvious
  and cost a round trip to discover.
- A `git diff --stat` reading `24 insertions, 1 deletion` was unreadable
  without knowing the tracked file was a single `[]` line — and that one fact
  turned "some noise in a data file" into "those are photos you imported,
  keep them".

What to cover, briefly:

1. **What it does**, in plain words — not the man page, the intent.
2. **Why this command and not the obvious one.** `git pull --rebase` rather
   than `git pull` is a choice with a reason; say the reason.
3. **How to read the output.** What the numbers mean, and which one is the
   number that matters.
4. **What failure looks like**, when a wrong-but-plausible outcome exists —
   the run that appears to work and did not.
5. **Anything destructive, flagged before the command**, never after.
   `git restore` discards work with no undo; `--force` and `reset --hard`
   likewise. If a safe alternative exists (`git stash` over `git restore`),
   lead with it and explain the difference.

Prefer explaining a real command they are about to run over teaching git in
the abstract. The concrete case is what sticks.

## Running tests

```bash
python -m unittest discover -s tests -t .
```

There is no `pytest` configuration; the suite uses stdlib `unittest`.

**CI runs it now (V2.83).** `.github/workflows/tests.yml` runs on every push to
a `V*.*` branch and on pull requests, with the whole Qt stack and
rasterio/pyproj installed, then `validate-data`. Until then the suite ran only
inside sessions, most without PyQt6, and a widget test was red from V2.80 to
V2.82 with nobody able to see it. CI calls the runner below rather than
`unittest` directly, and it is the better command in a container too:

```bash
QTWEBENGINE_CHROMIUM_FLAGS=--no-sandbox QT_QPA_PLATFORM=offscreen \
  python scripts/run_tests.py --exclude tests.test_undo_redo --max-skips 25
```

It prints the skip reasons with counts, **fails when more tests skip than
`--max-skips`** (17 skip with every dependency present, 16 on CI where the
runner is not root; a missing Qt runtime adds ~156), and exits before interpreter teardown, so the WebEngine segfault
described below cannot turn a green run into exit 139. Read its `RESULT:` line.

**The `-t .` is load-bearing (V2.38).** Without it `unittest discover` makes
`tests/` the top-level directory, its modules import as top-level names, and
`tests/__init__.py` is **never imported** — which is where the suite's offline
guard lives. Run it bare and the guard silently does not install, so the tests
go back to reaching the internet. `tests/test_ecoregion_ranges.py` fails loudly
with the right command when that happens.

**`rasterio` and `pyproj` unlock 42 more (found V2.38).** Without them the
raster paths — HRDEM elevation sampling, the offline soil pack — skip. That is
how `hrdem._rasterio_sampler` shipped unable to open a *local* GeoTIFF: it
prefixed GDAL's `/vsicurl/` HTTP reader onto file paths, so its test failed on
every machine with rasterio and skipped, therefore passed, on every machine
without.

```bash
pip install rasterio pyproj    # +42 tests actually run
```

**The suite is offline.** A measured run made **771 live requests** — 465 to
`api.open-meteo.com` from the design generator fetching a real elevation grid,
306 to iNaturalist from the photo warmer — and *nothing needed any of them*:
every fetcher already degrades gracefully. It made the suite slow, flaky and
dependent on somebody else's uptime, and a user on Windows started getting
`HTTP 429` back mid-run. `tests/__init__.py` now raises `URLError` for anything
past the machine (`file://` and localhost still work, since neither is the
internet). `SITEANDPATTERN_ALLOW_NETWORK=1` lifts it; nothing needs it today.

**The suite needs PyQt6 *and* the Qt runtime libs**, or ~156 widget tests skip
*silently* — which is how a `NameError` on every PDF export survived four minor
versions behind a green suite. On a bare container:

```bash
pip install PyQt6
apt-get update && apt-get install -y --no-install-recommends libegl1
```

The wheel alone is not enough (`ImportError: libEGL.so.1`), and the apt install
404s without the `update` first. A skipped test proves nothing — check the skip
count, not just the OK.

**And that is still not everything (found V2.38).** Without `PyQt6-WebEngine`
*every* test that drives a real `MainWindow` skips — 47 of them across
`test_undo_redo.py` and `test_app_smoke.py`, including the whole undo/redo
characterisation suite and the only tests that execute `app.py`'s signal
wiring. They skip with a message that reads like an environment limitation
(`No module named 'PyQt6.QtWebEngineWidgets'`) rather than a gap:

```bash
pip install PyQt6-WebEngine        # +47 tests actually run
```

With it installed the process **exits 139 (segfault) at teardown**, after the
summary — `Release of profile requested but WebEnginePage still not deleted`.
It fires even on a run where zero tests execute, so it is WebEngine shutdown,
not test code. **Read the `Ran N tests … OK` line, not the exit code** — and do
not confuse it with the V2.37 segfault, which was a real use-after-free
(worker threads emitting into deleted widgets, fixed in `src/qt_safety.py`) and
appeared *mid*-run.

**As root in a container, add `--no-sandbox`** or QtWebEngine's zygote refuses
to start and takes the process with it, with no summary line:

```bash
QTWEBENGINE_CHROMIUM_FLAGS=--no-sandbox python -m unittest discover -s tests -t .
```

### When the run dies with no summary at all (V2.40)

Three distinct process aborts hid behind each other here, and V2.98 found a
fourth, each printing in a *later* module than the one at fault and naming no
test. Three are now guarded by
`tests/test_architecture_guard.py:TestTheTestSuiteCanReachItsOwnSummary` — when
one fires, read the guard, not the abort.

| What you see | Cause |
|---|---|
| `Argument list is empty, the program name is not passed to QCoreApplication` | Some module built `QApplication([])`. The first one wins for the whole process, and the next `QWebEngineView` anywhere aborts. Pass a name. |
| `Running as root without --no-sandbox is not supported` | The env var above. |
| `QThread: Destroyed while thread '' is still running` | A teardown called `deleteLater()` on a window without `close()`, so `closeEvent` never stopped its workers. Nothing happens until the *next* event loop runs — some unrelated later test opening a dialog. |
| `Fatal Python error: Segmentation fault` with a bare `processEvents()` as the top Python frame; native frame `QMetaObjectPublisher::classInfoForObject` (V2.98) | An object registered on a `QWebChannel` was freed while its page lived on. `deleteLater()` hands a window to C++, the deferred delete never runs outside an event loop, and a garbage-collection pass then frees anything the window's wrappers were the only owner of. Give it a Qt parent. Guarded. |

`python -X faulthandler -m unittest …` is what actually locates these: it prints
the Python frame the abort came from, including the parked worker's stack. When
that frame is only `processEvents()`, the fault is in Qt: run the reproduction
under `gdb -batch -ex run -ex bt --args python …` (gdb is in the container) for
the native frame. A subset that includes `test_app_smoke` needs
`import PyQt6.QtWebEngineWidgets` before any `QApplication`, or its tests skip.

**The one that is not fixable in code:** with the three above cleared,
`tests/test_undo_redo.py` segfaults (139) *mid-run* in its own `tearDown`, at
`processEvents()` after `deleteLater()` — Chromium tearing a `QWebEngineView`
down in a GPU-less, dbus-less container, once per test. Reproduces identically
on a stashed tree, so it is the environment, not the diff. To get a number out
of a container, run everything else:

```bash
MODS=$(ls tests/test_*.py | sed 's#tests/##; s#\.py##' \
       | grep -v '^test_undo_redo$' | sed 's/^/tests./' | tr '\n' ' ')
QTWEBENGINE_CHROMIUM_FLAGS=--no-sandbox python -m unittest $MODS
```

and run `tests.test_undo_redo` on a real desktop.

Each test module redirects the DB to a `tempfile.mkdtemp` directory so
tests never touch the real user DB at `~/.local/share/Site & Pattern/`.

Some tests create temporary git repos via subprocess and disable
`commit.gpgsign` locally in those repos — this is test infrastructure
only, doesn't affect real commits.

## Key directories

| Path | What's there |
|------|--------------|
| `main.py` | Entry point. Installs Qt warning filter, constructs `MainWindow`. |
| `src/slot_errors.py` | **A button that fails says so, and the app carries on (V3.05).** PyQt6 ends the process on an exception escaping a slot unless `sys.excepthook` is replaced, with the traceback on a stderr a packaged build does not show: the V3.05 audit found one button that did that on every press. `install()` (from `main.py` only, never from tests, which must keep seeing exceptions) logs the traceback to the app's log and shows a non-blocking message, once per distinct fault and at most three a minute. |
| `src/app.py` | `MainWindow` — the top-level window, menu bar, "Check for Updates" logic. Behaviour lives in `src/controllers/` (shim pattern; see `tests/test_architecture_guard.py`). |
| `src/project_store.py` | **The single write path for placed-plant state** (V1.62). Never mutate `_placed_plants` / plant features directly — `tests/test_project_store.py` greps the tree for violations. |
| `src/controllers/` | MainWindow's extracted behaviour: map-event router, persistence/undo, mode, generation, area fill, update flow. |
| `scripts/surface_inventory.py` + `docs/SURFACE_AUDIT.md` | **Every surface, counted (V3.05).** The retirement pass F94 and F89 asked for first. The probe boots the real window at 1366 × 768 with the worked example, walks every tab at every depth, clicks every enabled button with every dialog, file picker and web link intercepted, opens every window and dialog, and writes `inventory.json` and a screenshot per page; the audit reads it into findings and a keep/merge/move/retire proposal per page, with an empty Decision column that is **the owner's**. Its click pass found a button that killed the app; re-run it (the command is in the audit) after any restructure and diff the JSON. **The owner's choices are recorded on the page linked at the audit's top**: read them (`ArtifactData`, `list` on `decisions`) before moving anything. |
| `src/db/schema.sql` | Authoritative DDL. Loaded on every `init_db`. |
| `src/db/plants.py` | Database access layer + migration logic + seed helpers. |
| `src/db/photos.py` | **Photo sets with named slots (F70, V2.35).** Many photos per species — habit / flower / leaf / fruit / bark_stem / winter / seedling — keyed by `scientific_name` (ids are not stable across a reseed) with `origin='seed'` vs `'user'` deciding what a reseed destroys. `plants.image_url` is synthesized on read from the best slot, so every existing screen improves without a change at the call site. |
| `src/photo_import.py` | Bringing a photograph in (F72, V2.35): downscale, re-encode, and **strip EXIF unconditionally** — a photo of your own yard carries your home's GPS coordinates and these get committed. The stripper is stdlib so it cannot be skipped by Pillow being absent. |
| `src/db/fauna.py` | Query API for the fauna registry and plant↔fauna junction (V1.31+), plus the schema-v58 morphology loaders (`bee_morphology`, `lep_morphology`). |
| `html/botany/diagrams.js` + `html/botany/fauna.js` | **The vocabularies, drawn (V2.36).** Every term a bench asks you to choose — 33 botanical (leaf shape, inflorescence architecture, leaf arrangement) and 31 zoological (wing shape/pattern, resting posture, flight style, bee build, scopa) — as generated inline SVG, plus a glossary line each. A word you cannot picture is not a control. Also the source for `docs/*_FIELD_GUIDE.md` via `scripts/render_botany_diagrams.js`. |
| `scripts/tune_morphology.py` + `scripts/tune_fauna.py` | The catalogue benches (dev tools, not app panels): plants and animals, each with a drawn vocabulary beside every dropdown, provenance that travels with the values, and out-of-vocabulary refusal at the save endpoint. Shared scaffolding in `scripts/_bench_common.py`. |
| `src/scene_wildlife.py` | Which animals appear in a design, where they sit, and what they look like. **Appearance is data since schema v58** — the genus/name tables here are the fallback for a species nobody has described, not the only answer. |
| `src/bird_body_plan.py` + `scripts/blender/assetlib/bird_builds.py` | **A bird's body and where it stands (F174, V2.97).** Until V2.97 every bird was drawn about 2.4 times its length: the viewer sizes a bird by setting its width to the recorded wingspan, and the builds' wings were paddles. **A build's width IS its wingspan**, wings authored spread at its birds' real span, with a folded pair (`FoldL`/`FoldR`) the viewer shows at rest; keep that true of any new build (`tests/test_bird_body_plan.py` reads the GLB). The build comes from the genus, the stance from the build: songbirds in the crown as before, hawks and owls on a tall tree's top (a hawk soars over young trees, an owl is not drawn), grouse and cranes walking, ducks and geese on a pond. Three numbers are copied from the bpy-free builds file into the app, kept equal by a test. |
| `src/confidence.py` | **One vocabulary for "how sure are we?" and "who says so?" (F8/F13/F14/F28, V2.53).** Bands (three rungs plus `UNKNOWN`) and marks (one table over the edges layer's `documented/recorded/derived` and the seed data's `measured/flora/photo/checked/name/epithet/estimated`). Two rules are load-bearing: **absent is not estimated** — a blank field is the app knowing it does not know, `estimated` is a genus default that looks like a measurement — and **a band needs evidence**, so `known=False` gives `UNKNOWN`, never a middle rung. It does *not* own thresholds another module already owns: establishment floors come from `ecoregion_ranges` and a test asserts they agree. |
| `src/ecoregion_ranges.py` + `scripts/seed_ecoregion_ranges.py` + `scripts/plot_occurrences.py` | **Which ecoregions a species is actually recorded from (V2.38, corrected V2.75, re-derived V2.76 and V2.81).** Counts derived from GBIF occurrence records, each row carrying its count and a confidence band. **A record counts for the region it is more than 900 m INSIDE, and for no other (V2.81).** Containment alone was still reading a border closer than it is drawn: *Penstemon albertinus* published 17 Aspen Parkland records that were **one montane population**, 663 m across, sitting 25-202 m inside a line the site's own `CAVEAT` calls accurate to a kilometre. `ecoregion.confident_ecoregion` requires a record to clear `SIMPLIFICATION_M` (900 m, read from the same number the caveat prints) measured to the nearest **different** region -- never to a ring, because the layer splits each ecoregion by Alberta subregion and Aspen Parkland alone is 9 features with seams through the middle. That also ends the V2.78 double count for free (0.81% of in-region points matched two regions, 85% of them at Calgary): an overlap exists *because* a shared border was simplified twice, so a doubly contained point is by construction inside the margin. Cost: 5.7% fewer records credited (3.6% of them set aside as too near a line), **108 region rows gone across 94 species and zero added** — `ranges_for_species` had defaulted its lookup to `ecoregion.lookup_ecoregions`, which applies a 5 km proximity buffer written for *which ecoregion is this yard in*, so 16.4% of points inside the layer were credited to two or more regions. Two questions, one geometry, kept apart by `near_m`. The seeder **caches the raw points** to `data/fetched/plant_occurrences.json` (dev artefact, never shipped, never published) so a re-derivation costs no network — before V2.75 only the counts survived a run, which is why that bug could be diagnosed here and not corrected. `plot_occurrences.py` draws them, and **V2.77 made the specimen layer real**: `--specimens --publishable` renders what the printed regional floras plot (52,924 of 555,477 records drawable, 300-700 dots per species), because for a herbarium the dataset licence IS the record's licence and a pressed sheet carries none of the rare-taxa coordinate obscuring iNaturalist applies. Whether any of it is *published* is still an open decision, not an effort problem. **Note `MAX_RECORDS_PER_SPECIES = 6000`**: GBIF orders newest-first, so for a common plant the harvest is the last few years and nothing before them - 16 species at the cap hold 89,964 records and thirty-one specimens between them. Use `--specimen-pass` to reach what the cap cut, and `--from-cache` to re-derive with no network. **Re-derived in V2.76** (schema v77) once the author ran the fetch: records 489,546 -> **361,447**, and the error turned out to be concentrated in one sliver — `western_continental_ranges` is a BC region clipped to 0.02% of the layer inside Alberta, claimed by **135 species and now by 15**. Interior regions barely moved (Cypress Upland 231 -> 228), which is the signature a boundary fix should have. |
| `src/static_site_method.py` + `src/static_site_range.py` | **What a shaded region claims (F135, V2.75).** An outside botanical review read the site and asked five things it could not answer from any page: what a record is, as of when, where in the region, why a region with two records is missing, and what the shading means. Every answer was already in the repo — the retrieval date on the row since schema v59 and printed by the *desktop*, the floor in `MIN_RECORDS`, the near-misses computed by `dropped_regions` every run — and none reached a reader. `/method/` states them, **computed from the modules that own them**, including what this build gets wrong. Every species page links out to GBIF and iNaturalist, which stays current in a way a shipped snapshot cannot. **V2.80 replaced the ecoregion map on the species page with the occurrence range map** (`static_site_range.occurrence_map`): the shading was the overstatement the review objected to, and the swap took the built site 421 MB -> 118 MB because 846 KB of every page was ecoregion polygons. **The ecoregion map then came back later in V2.80, below the occurrence map rather than instead of it**, on the author's review of the build, so the published site is 328 MB again with a median species page of 585 KB raw (about 180 KB compressed, which is what a reader downloads); `static_site_range.range_section` carries the reasoning. The region counts sit beside it, under a heading that says what they are. The record marks come from `data/plant_occurrence_points.json` and toggle between specimen and observation with **three radios and no JavaScript** -- the inputs must be siblings of the map, because `~` cannot climb out of a wrapper. |
| `src/occurrence_points.py` + `scripts/seed_occurrence_points.py` | **The records themselves, as the site may publish them (F147, V2.80).** 171,896 marks over 426 species, split into herbarium specimen and field observation, because a pressed sheet somebody can re-examine and a photograph identified by community agreement are different evidence. Three filters: 10 km precision, the two provinces, and `PUBLISHABLE_COORDINATES` -- which permits **CC_BY_NC for a coordinate but not for a photograph**, on the author's V2.79 reasoning that a photograph is redistributed as a work and a coordinate is a fact about a place. That is not academic: 329,267 of 365,092 drawable records are NC observations, so the photograph bar would have published a map that is 94% herbarium specimens. Records within 0.01 degrees are drawn once, which is **under half a pixel** -- a rendering decision, not subsampling, and the caption says which. |
| `src/establishment.py` + `src/reference_fidelity.py` | The two bands (V2.53). *Has anyone recorded this species growing here* — off the schema-v59/v60 occurrence records, where no record bands as **unknown rather than unlikely**, because under-collected and absent are indistinguishable below the floor. And *does this design have the shape of the natural community* — structure per layer, not species, with low explicitly not a failure. |
| `src/db/relationships.py` | **The unified edges layer (F7, V2.31).** One query API + one edge vocabulary (`EDGE_KINDS`) over the schema-v51 `relationship_edges` view, which unions `plant_fauna`, both companion tables and shared polyculture membership. Ask "what is connected to this plant?" here, not table by table. Every edge carries `evidence` — `documented` (seeded record + `source`) vs `derived` (computed, e.g. two plants feeding the same animal). |
| `src/relationship_graph.py` | Relationship-web overlay core (F5, V2.31): the design as a drawable graph — species at their planting centroid, wildlife on a ring outside it. All geometry Python-side; `html/map/07-network.js` only renders. |
| `src/site_prep.py` + `src/planting_map.py` + `src/maintenance_calendar.py` | The take-it-outside document (F43/F41/F42, V2.31), assembled in job order by `src/planting_plan_export.py` and drawn as PDF pages by `src/pdf_export.py`: prep the ground → buy it (F40) → dig it in the right places → phase it (F17) → keep it alive. The planting map is a **scale drawing**, not a map screenshot; numbers are per species and key to the F40 buy list. |
| `src/field_sheet_flow.py` | **The site-walk sheet (F32, V3.05).** Site › Field Notes' ten questions printed on one page with a box to tick and lines to write on, what is already noted filled in (`field_notes.walk_sheet`, drawn by `pdf_export._draw_site_walk`); alone from Field Notes › *Print this sheet…*, and the design PDF's first job, before Site prep. |
| `src/onboarding.py` + `src/onboarding_flow.py` | Cold-start path (F44/F45, V2.31): the three-step progress model (pin → boundary → plants) read from the project, the beginner Generate defaults, and the worked example — authored as species *names* + metre offsets and resolved against the live catalogue at open time (never a shipped `.perma.geojson`, because plant ids aren't stable across reseeds). Surfaced by `src/welcome_dialog.py` + `src/first_step_bar.py`. |
| `src/db/polycultures.py` | Polyculture CRUD + seeded example communities. |
| `src/db/recipes.py` | Ratio-only polyculture recipes (separate from spatial polycultures). |
| `src/db/structures.py` | Hard-coded list of habitat structures (bee hotels, brush piles, etc.). |
| `src/version_branch.py` | Helpers for the V-branch convention (V1.32+). |
| `src/github_releases.py` | Qt-free GitHub Releases lookup + installer download for the frozen-build in-app updater (V1.73). |
| `src/app_version.py` | Reads the build's `version.txt` so a frozen `.dmg`/`.exe` knows its own V-version (V1.73). |
| `.github/workflows/release-macos.yml` | Builds the macOS DMG on a cloud Mac and publishes it to a GitHub Release on every `V*` push, feeding the in-app updater (V1.73). |
| `src/subject_area.py` | **Is this coordinate on ground this catalogue speaks for? (F142, V2.78).** The GBIF harvest is bounded by the polygon layer's *bounding box* plus half a degree, so it reaches into BC, Montana, Manitoba and the NWT; `map_svg` emitted its overlay outside its own subject clip, and **175,876 of 555,477 cached records (31.7%)** were drawn over ground the layer has no authority over. **The province outline alone is not the test** — Natural Earth 1:10m gives Alberta and Saskatchewan 193 vertices between them, too coarse to adjudicate the continental divide — so a point counts if it is inside the coarse outline **or** any surveyed ecoregion. Separate from `site_facets.SUBJECT_PROVINCES`, which is the same two provinces as a filter vocabulary. |
| `src/site_fit.py` | **Has this plant been recorded near this yard? (F154, V2.85).** The one place the design side reads the 0.25° occupancy grid (`data/plant_ranges.json`) the website has drawn since V2.79. `province_at` (AB/SK by the 110th meridian inside the subject area, `""` outside) makes the generator's native filter follow the pin -- it had used the Alberta flag everywhere, and any goal with its own filter dropped even that, which is how Saskatchewan's Bur Oak reached an Edmonton yard. `locality` (here / near / elsewhere / unrecorded) **ranks, never filters**, and `unrecorded` ranks level with `elsewhere` (P9). It cannot stand in for nativity: Bur Oak has 115 records around Edmonton, planted trees. `llm_design` applies both, plus a size rule (footprint since V2.85, height since V2.86), to the offline pool, the AI palette, communities (`_communities_for_site`) and the critic's repairs (`_site_scoped_query`); the same increment sized small lots in plants, not 6 m anchor cells. |
| `src/pending_species.py` + `data/plants_pending_flora.json` | **Species that wait for a flora (V2.86).** A catalogue row ships only with its nativity read from VASCAN (`tests/test_nativity.py` fails otherwise), and cloud sessions cannot reach VASCAN. **A new species written in a session goes here, as a complete row, not into `plants_master.json`.** Nothing seeds from the file; the gate validates it by the catalogue's rules (`validate_pending_species`); `fetch_flora_nativity.py` asks VASCAN about it; `ingest_flora_nativity.py --apply` promotes each row VASCAN plainly confirms, writing **VASCAN's** provinces, not the row's. Empty since V2.87, when the seven V2.86 trees were promoted (F161); `docs/CANDIDATE_SPECIES.md` is the worklist of what could go in next (F168). **Rebuilding the range files after a promotion:** `seed_species_ranges.py` and `seed_occurrence_points.py` with no `--species` (given one, each replaces its whole file); since V2.87 they skip `excluded_taxa.json`, which the point cache still holds, and the gate fails if an excluded species reaches a derived file. |
| `src/phenology_bar.py` | **When a plant flowers, drawn (F143, V2.78).** Twelve cells, bloom and fruit on one axis because the gap between them is the information. The catalogue had carried `bloom_period` since its first seed file and shown it three ways, all text, none of which answer *what is flowering in July*. **Nothing recorded draws nothing** (P9): twelve empty cells asserts that we checked and it never flowers. Delegates parsing to `habitat_score.parse_month_range` rather than growing a second parser to disagree with the first. |
| `src/nativity.py` | **What "Native to Alberta and Saskatchewan" rests on (F144, V2.78; sourced V2.80).** Before V2.80, 354 of 430 species published "AB,SK" from an inference about ecoregions continuing across the 110th meridian, which was the outside review's actual criticism. VASCAN's checklist then landed (F137, from the Darwin Core Archive), and **every row now carries `native_provinces_source = 'flora'`**, which `provenance()` reads first. The inference notes remain as the fallback for a row that loses its source, which `rename_taxon.py` does on purpose so the next archive run refills it. |
| `src/local_flora.py` + `src/native_here.py` + `scripts/derive_local_flora.py` + `data/local_flora.json` + `data/local_flora_rulings.json` + `tools/local_flora_review/` | **Native around Edmonton (F220, V3.12).** VASCAN says *Alberta*, which is 415 of 424 species, the mountains' and the dry south's included; the owner asked for the plants of Edmonton. **The records cannot answer it alone**: within 50 km of downtown Bur Oak has 119 observations and 3 herbarium sheets, and VASCAN records it introduced in Alberta, because a city's records include its planted trees. So the rule is a gate and a floor: VASCAN native in Alberta, then **3 distinct collections** (sheets sharing a 0.01° spot and a year count once) whose **whole uncertainty circle** lies within 50 km, then the owner's answers, a plain yes or no and **no reason** (their word: answer where confident, leave the rest, and nothing they write is shown), which can move a species either way but never across the VASCAN gate. Below the floor a species is *not settled*, never "not native" (P9). `local_flora.py` is the rule and the file format; `derive_local_flora.py --write` derives the shipped list (no network, from the point cache), `--check` is what the tests run, and **`--merge` folds in the owner's review** (the page's export or its database rows), checking every ruling before writing any. `native_here.py` is the **one read side**: the picker's *Edmonton native* quality (`search_plants(native_near=)`), the species page's *Native to* and *Around Edmonton* lines, the community list's switch and page, the generator (pool, communities, repairs, the AI's resolver) and the website (a *Native area* facet and page, a row per species, `/method/#around`) all ask it, so they cannot disagree, which is what cost V2.38, V2.80, V2.85 and V3.00. The owner answered all 108 borderline species on the review page and V3.13 folded them in (59 yes, 49 no: **250 species** on the list, none unsettled); `tools/local_flora_review/README.md` has the link and the fold-in steps, which re-run after any changed answer. **Under the switch a parent community that fails is never listed, even as the heading of a variation that passes** (`filter_library` lists that variation on its own, V3.13): a heading row is selectable and placeable. Pages say only "Native, confirmed on review." or "Not native here, on review." with the evidence, and **a reason is dropped wherever one appears** (`parse_rulings`, `--merge`), guarded by tests. `rename_taxon.py` and `remove_taxon.py` carry a ruling with its species. The list is read from file, not seeded: a ruling needs no schema bump. |
| `src/flower_colour.py` | **Flower colour as something you can filter on (F108, V2.47).** The hex→bucket classifier behind `search_plants(flower_colours=…)`, the directory facet and the website's colour pages — one parser, so the three cannot disagree. The grasses/sedges/rushes bucket is *not* a bloom colour and is labelled so: they are wind-pollinated and `#cbbd80` is the absence of a showy flower, not an observation of one. |
| `src/site_facets.py` + `src/site_facet_values.py` | **What the website can be searched by (V2.48).** 22 facets in six groups as ONE table (the derivations moved to `site_facet_values.py` in V3.12, at the line ceiling; V3.12 added *Native area*, the Edmonton list), each declaring whether its own ticked values AND or OR (`combine`; safety and role are `all`, everything else `any`), driving the sidebar controls, the values baked into each browse-index row, and the landing pages generated per value. Deliberately *not* `search_plants` parameters: the site filters client-side, so an axis costs a derivation function rather than a thirty-first query parameter. `WITHHELD_ROLES` has been **empty since V2.50**: the author ruled the `medicinal` use tag a generic horticultural category and it is published; the mechanism stays, tested against a temporary value, because the free-text notes are the artefact P12 keeps off the web. |
| `src/ecoregion_map.py` + `src/ecoregion_basemap.py` + `src/ecoregion_palette.py` | **The ecoregions, drawn (V2.48, redrawn V2.49, reprojected V2.66).** Inline SVG, no script, no dependency. `_map.py` projects the thematic layer through an Albers equal-area conic; `_basemap.py` draws the ground under it from `data/basemap_prairie.geojson` (Natural Earth 1:10m: real province outlines, major lakes and rivers, generated by `tools/ecoregions/basemap.py`, superseding the hand-typed `data/provinces_prairie.geojson`); `_palette.py` says what a colour asserts and carries the hatch rule. **Below the ecozone, identity is a number, not a colour (V2.69)** — hue is the ecozone and lightness the ecoregion inside it, which collapses at ten siblings (Boreal Transition vs Clear Hills Upland: ΔE 0.3). A search over lightness, chroma and hue rotation together found the best sibling separation that still clears the cross-ecozone colour-vision floor is ΔE 1.7, so focus maps carry numbered discs keyed to a numbered legend, both ordered by one `numbered_order`. A subregion map also draws its **parent underneath**: Alberta surveys subregions and Saskatchewan does not, so without it a cross-border ecoregion showed a hard split down the provincial boundary. **The polygons are surveyed since V2.67** — National Ecological Framework v2.2, 24 ecoregions in 6 ecozones, built by `tools/ecoregions/`; `scripts/draw_ecoregions.py` drew the six that came before and is now history, not the source. `CAVEAT` still travels with every drawing but now discloses the ~900 m simplification instead of calling the outlines a diagram: **it kept saying "not surveyed boundaries" for a whole increment after that became false**, on 432 public pages, so its test checks the caption against the polygon file's own provenance rather than against a remembered string. |
| `src/static_site_regions.py` | **The website's pages about *places* (V2.69).** The ecoregion map is a **drill-down**: `/map/` colours 6 ecozones, an ecozone's page colours the ecoregions inside it, an ecoregion's page colours the Alberta subregions overlapping it, and each of the 21 subregions has a page. Chosen over three side-by-side maps because the reader's question is sequential and 24 regions do not fit on one 700px map — that crowding is what once shipped "Parkland" as the name of Aspen Parkland. **A subregion page is a locator, not a filter result**: no species is tagged at that level and none should be, so the page borrows its dominant ecoregion's list only when one accounts for two thirds of it, and otherwise lists the overlaps with their measured shares. Alberta's subregions are a *parallel* classification, not a third tier — Montane is 42% of Northern Continental Divide across six ecoregions. |
| `src/ecoregion_tree.py` | **The vocabulary has three levels (V2.68).** ecozone (6) → ecoregion (24) → Alberta natural subregion (21), all *read from the polygon file* rather than declared beside it — the one hand-transcribed copy that existed was already wrong about Interlake Plain. Drives the collapsible filter (`filter_widgets.build_ecoregion_tree`) so the first choice is six-way, not twenty-four-way. **Matching runs both ways along a lineage**: a plant tagged only "Boreal Plains" answers a Mid-Boreal Uplands query, because its evidence was never finer than the ecozone and that is *unknown*, not no (P9). Keys are prefixed `zone_`/`sub_` — "Athabasca Plain" is both an ELC ecoregion in Saskatchewan and an Alberta subregion, and they are different ground. |
| `src/static_site.py` + `src/static_site_render.py` + `src/static_site_species.py` + `src/static_site_wildlife.py` + `html/site/` | **The catalogue as a public website, branded GrowNativePlants (F109, V2.47; renamed V2.70).** The site is **not** called Site & Pattern: it got its own domain (grownativeplants.ca) and its own name, for what somebody typing it into a phone is trying to do. The desktop app keeps the old name and `src/branding.py` still owns it; `static_site_render.SITE_NAME` owns the website's. `--base-url` is load-bearing now — it writes the `CNAME` GitHub Pages reads, so publishing without it silently reverts the custom domain, and since V2.80 it is also the only source of the **absolute** image URL a share card needs. `python -m src.cli build-site <dir>` → **430 species pages, 1,132 wildlife pages** ("which plants feed this animal", over the 7,413 published edges), colour/month/role hubs, client-side filtering over an embedded JSON index. **Every count on the site is computed at build time, never written down** — the fauna work of V2.59-V2.65 took wildlife pages from 86 to 1,138 without a line of site code changing. Model and renderer are split so a test can assert the link graph without rendering. Every species page is the same `plant_directory.species_entry` the desktop window calls. **Notes are withheld by default (P12)** and no photo is published without its credit. **Sources render through `src/citations.py`** (V2.65) - a page shows "Acorn & Sheldon 2006", never the `globi_...` database key, and the About page publishes the whole 114-work bibliography with its disclaimer. **No em dashes reach a page**: normalised in `_esc` and, since V2.75, actually guarded by a test over every rendered page — `_esc` only protects strings that pass through it, and a dash written straight into an f-string template never does, which is what the V2.75 range copy shipped while the suite stayed green. V2.71: the **wildlife index is a filtered search too** (`static_site_wildlife.py`, its own facet vocabulary — an animal is not a row in `site_facets`), sharing `browse.js`, which reads whatever `data-f` attributes a page rendered and so knows neither vocabulary; the 58 credited animal photographs are published for the first time. **Analytics is off unless asked for** — the site otherwise makes no external request at all — and when it is on, every page says so in its footer and a malformed value raises rather than landing in 2,000 pages. V2.73: two providers, `src/site_analytics.py` owning the vocabulary, the validation and the generated footer sentence. `--analytics-token` (Cloudflare) answers *is anybody reading this* and its free tier keeps about a day; `--umami-website-id` (+ `--umami-src` for the EU region or a self-hosted instance) keeps history and answers *which pages, and is that growing*. Both at once is allowed on purpose: it is how a switchover is checked. |
| `src/site_share.py` | **What a link to the site unfolds into when somebody pastes it (F150, V2.80).** Every page carried a title, a description and nothing else, so a link shared to Facebook, Reddit, Slack or a text message rendered as a grey box, on a site whose whole argument is that the plants are worth looking at (P13, at first contact). **The trap is that a broken card is invisible from the page**: the HTML validates, nothing errors, and the only way to find out is somebody else pasting the link. So three rules are enforced rather than remembered. **`og:image` must be absolute** — the scraper fetches it from its own servers with no page to resolve a relative path against — so a build with no `--base-url` emits no image tag rather than a broken one. **Both vocabularies** (`og:*` for Facebook/Reddit/Slack/Discord/iMessage, `twitter:*` for X), one set of values. **The credit rides in `og:image:alt`**, because attribution is the licence condition on these photographs and the page carrying it is reduced to a link inside somebody else's app. Returns tags as tuples, not markup, so `static_site_render._esc` stays the site's only escaper. The default photograph is picked from the **built model** (`DEFAULT_SPECIES`, first credited photo wins), never pinned to a file, so it cannot show a species the catalogue has stopped publishing. |
| `src/plant_panel.py` | Right-side plant browser + custom delegate. |
| `src/placement_bar.py` + `src/placement_bar_flow.py` + `src/placement_controls.py` | **Placing happens on the map (F193, V2.98).** While the map is armed, a bar floats over its top edge: what the next click does, in words (`placement_arming.describe`), Done, and the current pattern's settings only. Both panels build their controls and the bar adopts them; the panels say what they armed (`armed_changed` / `armedChanged`). **The bar is a sibling of the map in its column, never a child of the web view**: `QWebEngineView`'s accessible interface reports only the page, so a child is invisible to screen readers (measured). **The map reports every mode it enters** (`bridge.onModeChanged(mode, _pyModeSeq)` at the end of `setMode`), stamped by `MapWidget._run_mode_js`: send any new Python mode change through it, or its report can look current next to a newer one. Python follows the map *out* of placing only (Esc in the map, a finished fill, another tool) and never calls `_cancel_draw` from a report. The side panels are `src/scroll_column.py` columns: they scroll rather than squeeze sections into each other. **Looking is not placing (F191, V2.99)**: selecting names the plant on a Place button and leaves the map alone. `src/place_action.py` turns a list's input into *place* (Enter, a double-click; never `activated`, which fires on one click under KDE) and *choose* (a finished click or an arrow; not focus arriving, not a drag, not ▶, which reports a `clicked` in Qt 6 and so says `took_click()`); while placing, choosing switches what is placed. **What is placed is what the Place action named**, a plant or the mix, never swapped by a pattern. The map draws the next click's footprint under the cursor (`html/map/08-footprint.js`; a community's shape from `src/placement_footprint.py`), at a placed marker's radius. |
| `src/community_page.py` + `src/community_flyout.py` | **A community shown as a plant is (F206, V3.09).** Chosen in Placement › Communities when not placing, a community's page opens in the plant page's frame over the map: its name and facts, Place, its members as small photographs three across (or the type's colour until a photo is cached), then its pattern card. A member opens its plant page in the same frame with *Back to <community>* above it. `CommunityFlyout` subclasses the plant frame (`species_flyout.py` has a 200-line ceiling); `wire` connects the list (`polyculture_panel.page_requested`, `place_by_id`). **Since V3.11 the panel no longer repeats the page** (`set_details_in_page`, set by `wire`): it keeps the list at full height and only the name with Place; a photograph keeps its type's colour as a 3 px frame (the owner: the colours "disappear with the plants that have pictures"), and a name wraps to two lines before it is cut (`two_lines`). |
| `src/features_scan_flow.py` | **Site › Features › Scan this area (F207, V3.10).** Buildings from OSM (or the offline pack) and trees from the canopy-height map (the satellite photo when that cannot be reached) in one click, off the UI thread, added as one undo step through the existing import tails (`import_osm_result`, `tree_detect_flow.import_tree_result`), then a non-modal review list where unticked finds come out as a second undo step. Trees from imagery are not new: `tree_detect.py` / `tree_detect_chm.py` have read them since V2.26. The heavier steps (open building footprints, automatic satellite alignment, buildings from the owner's own imagery) are the V3.09 plan's T6–T8, with a licensing question about Esri pixels in front of T7. |
| `src/landing_check.py` | **Where a placement landed, in words (F198, V3.05).** The bar over the map says when new plants came down outside the boundary or inside another plant's circle (a centre within half its spacing), with Undo beside it. **It never refuses**: overlap is sometimes the design, a groundcover under a shrub. Says nothing about a boundary when none is drawn. |
| `src/plant_picker.py` + `src/plant_filters.py` + `src/species_page.py` + `src/species_flyout.py` | **One picker, one species page (F192, V3.00).** Browse, the Plant Directory and the community builder were three pickers with three filter sets; they are one widget over one Qt-free vocabulary (9 facets, 10 qualities since V3.12's *Edmonton native*; the Directory's Keystone, Larval host, Bird food, Pollinator and Nitrogen fixer toggles ran exactly the Role facet's query and folded into it). A narrow picker starts with its filters **folded to one line that says what is on**, the pin's region included. **The painted card is gone**: a plant's page (`species_page.py`, labels a reader can select and hear) opens **beside** the Browse list, over the map's right edge, as the map's sibling (never the web view's child: the V2.98 accessibility rule). A finished click or an arrow shows it when not placing; → opens it with the keyboard inside; Esc or ✕ closes it; **placing closes it, and no page opens while placing** (the list is a palette then, V2.99). The order **Recorded near this site** (`site_fit.locality`, then zone, standing water last) ranks and never filters; the review called it "suits this site", which nothing here can know. **Native reads `native_province='AB'`** (VASCAN), not `native_to_alberta`, where five rows still carry the seed's `'1?'`; the generator's `native_only` is untouched. `species_entry` counts animals distinct (`animals`); `total` stays relationships, which is what the website says it is. **Filters people can read (F194, V3.01)**: a chosen dropdown reads its dimension and joins its values by its rule (`plant_filters.face`: "Type: Tree or Shrub"; Role is *all*, the rest *any*), each list opens on that rule, what is on is a row of removable chips and an empty result names what emptied it (`src/filter_status.py`, `plant_filters.what_emptied`). **`CheckableComboBox` keeps no current item**: one made by the wheel, an arrow or Return in the list is what left "● Shrub" on the box (Qt draws the current item's icon and writes its name back when its tick changes); keep it that way. The site's soil pH (`set_soil_ph`) is a chip and a toggle, not a silent filter, and it leaves with the site: a new design, a removed pin and a design opened without one all clear it. A control that removes itself hands the keyboard on, and chips and offers are put in the tab chain by hand: widgets made after their window join its end. |
| `src/focus_ring.py` + `src/keyboard_help.py` + `src/accessible_names.py` + `html/map/09-keyboard.js` | **The keyboard and the screen reader (F195, V3.02).** One ring follows keyboard focus in every window, **drawn over the control** (a `QFocusFrame` under a style that says so): Qt's own frame sits in a margin outside the control and was clipped wherever a layout packs a control to its parent's edge, which a test now reads in pixels. Qt sees the map as one widget while focus moves between the page's own controls, so `09-keyboard.js` draws the map's ring, makes **Enter act at the map's centre** with whichever tool is chosen (every tool goes through `onMapClick`) and Shift+Enter finish, and stops Leaflet making every label marker a Tab stop. `keyboard_help.MAP_LETTERS` is the one table the window's key handler and Help → Keyboard Shortcuts both read; the letters act **only while the map has focus** (WCAG 2.1.4). **F6** moves between the map and the side panel (`PaneSwitch`). **Bind a key once**: Qt calls a key bound twice ambiguous and fires neither, which is how Ctrl+Shift+Z never redid anything (`distinct_keys`; a smoke test fails on any duplicate). Containers no panel builds are named after their tab (`accessible_names`), and a guard walks the real window for any focusable control with no name. |
| `src/target_size.py` + `src/indicator_style.py` + `src/member_colors.py` + `html/map/10-plant-key.js` + `tests/_visual.py` | **What can be seen (F195, V3.03).** Three floors, each read off the real window tab by tab in `test_app_smoke` as well as from the source: **no text under 12 px** (`test_visual_floor` fails on any `font-size` under 12 px in the desktop app's source; the PDF export and the website keep their own scales), **4.5:1 for enabled text** (3:1 for a symbol; disabled controls are exempt), and **24 px for every control**. The last is one app-wide event filter (`target_size.install`, from `main.py` and the window) that **only ever raises a minimum**: a minimum set on a widget *replaces* Qt's own, and the first build, which set 24 everywhere, made the View toolbar squeeze its buttons to "S…ite" instead of moving them to its » menu. **A checkbox's box is drawn by `indicator_style`** (also installed by both): under Fusion an unticked box was 1.11:1, invisible, because Fusion outlines it in the panel's own colour darkened. **Width depends on the font**: CI draws in DejaVu Sans, about 12% wider than the Arial-metric fonts of Windows, and V3.03 found two tabs that fitted one and scrolled sideways in the other. `fc-match sans-serif` says which font a run uses; a fontconfig alias in `~/.config/fontconfig` changes it, and `XDG_CONFIG_HOME` pointed at an empty directory sets it aside. **Plants have one colour scheme, by type**: `member_colors.TYPE_COLORS` is the only table (the builder, the plant list, the 3D contract), mirrored by `10-plant-key.js` for the map and its legend, a test keeping them equal; a marker is outlined in its colour darkened 60%. Community members were coloured by layer until V3.03, and only until a reopen; nothing outlines a community on the map (F202). `10-plant-key.js` also rounds every `L.Circle`: Leaflet 1.9 drew a sub-metre circle up to 44% out of round, and its click test read the width alone. |
| `src/polyculture_panel.py` | Polyculture/community builder UI. |
| `src/analysis_panel.py` | The **Design** tab's widget, whose strip holds Report card, Planted, Habitat, Food, Over time and Water (V3.08; three of them built by other panels), and the builder of the **Site** tab's Sun & Shade and Wind pages, which it still runs. |
| `src/side_panel_layout.py` | **The side panel's five tabs (F94, V3.07–V3.08).** Site · Placement · Design · Share · Learn, by the question a person brings, from the owner's answers to the V3.05 surface audit (`docs/SURFACE_AUDIT.md`, the Decision column). The panels build their pages and own what they do; this module moves built pages between tab widgets, so nothing about how a page works moves with it. **Address a page by its widget, never by its index in a strip** (`keyboard_help.show_panel`, which opens every level a page is in): an index is exactly what this module changes, and three lookups that used one (`_habitat_tab_index`, `_bee_tab_index`, the pin's Site jump) would have opened the wrong page. **A strip hides the page it gives up**: one put into a layout rather than another strip must be `show()`n, or its heading sits over nothing (V3.08's first build did that to Over time and Notes), and an emptied container must leave the window (`_discard`), or the accessibility guard finds it unnamed. The Planning panel's pages all moved in V3.08 (Over time, Water, Notes); the panel stays, hidden, owning their state and signals. |
| `src/shape_tool.py` | **Draw › Shape (V3.07).** The Structures tab's Shapes and Hedgerow pages, as one form under a Draw-row button: areas (beds, paths, the lawn-conversion zones) and lines (hedge, fence, living fence, windbreak) in one Type list, emitting what the two pages did to the same handlers. A form in a `QMenu`: a choice in its dropdowns keeps the menu open (checked with real clicks under X), the system colour dialog closes it, so `_pick` opens it again where it was. |
| `src/live_refresh.py` + `src/design_inputs.py` | **Read-outs that follow the design (V3.05).** Five pages opened on a Calculate button over an empty box, and their result went stale with the next edit (Analysis › Habitat; Planning › Effort, Wildlife, Harvest, Water). `LiveRefresh` refills the page on screen when it is shown and after edits (150 ms, so a community of eight is one refill), and computes nothing for a page nobody is looking at. A page moved to another strip takes its refill with it by `move_to` (V3.08). `design_inputs` reads what the design already knows for Water (the boundary's area, the barrels, ponds and swales placed), which had started from 200 m² whatever the yard. |
| `src/learn_panel.py` | Learn side tab: Field Study quiz and guided Lessons (V2.25). It still builds and drives Present, which has been Share › Present since V3.08. |
| `src/food_page.py` + `src/what_it_feeds.py` | **Design › Food, the owner's "what it feeds" page (V3.08).** Analysis › Bees and Planning's Wildlife and Harvest calendars, merged: **one animal, any animal** (the design's plants that feed it and how, the catalogue's that would, the months it eats here; a bee keeps the Bees page's tongue fit, nesting and flight season), and **month by month with people kept apart** (pollinators, birds, then people, a harvest never read as forage). `what_it_feeds` is Qt-free and reads the edges layer; its `eaters_line` is the line under each species on Planted ("feeds 137: 53 bees … · flowers May–Jun · fruit Aug–Sep"), `together` a community's, each animal once. **`larval_host` is a caterpillar host only for a butterfly or moth**: the edges layer has it for bees (GloBI's *hostOf*, a flower record) and beetles too, so `kind_words` and `months_for` take the animal's group. |
| `src/share_panel.py` | **Share (V3.08):** what leaves the app. Present (moved from Learn) and Export: the PDF, the planting plan, the order file, Growth Snapshots, the 3D preview's presentation still and before / after, and Where to buy (moved from Site Info). Every button calls what the File menu or the 3D preview already does; nothing on the page is a second way of exporting. The report card's cost link opens it. |
| `src/follow_design.py` | **The windows that show the design follow it (F89, V3.08).** The 3D preview's *Refresh from design* and Growth Snapshots' *Refresh* are gone: every edit ends in `_mark_modified` (split view's hook since V2.44) and a design opened or undone in `_sync_planning_panel`, and both call `request_sync`, which rebuilds each open window once the edits pause (400 ms). A closed window pays nothing. Both windows wear `ui_style.WINDOW_STYLE` (F209): a top-level window inherits none of the main window's stylesheet, which moved to `ui_style.APP_STYLE` so they could share it. |
| `src/map_widget.py` + `html/map.html` + `html/map/*.js` | Leaflet map embedded via QWebEngineView. The JS is split into fourteen sequential classic scripts (V1.64; `07-network.js` V2.31, `08-footprint.js` V2.99, `09-keyboard.js` V3.02, `10-plant-key.js` V3.03, `11-map-furniture.js` V3.06, `02b-shape-edit.js`, `12-legend.js` and `13-species-numbers.js` V3.11) — shared-global model, NOT ES modules; load order matters. **The plants' canvas covers every pane below the overlay pane** (Leaflet gives a canvas renderer one `<canvas>` the size of the map, and it stays once anything is drawn on it), so nothing in a lower pane can take a click: from V2.37 to V3.10 that was the boundary, unpressable from the first plant on (F213), and it is still the relationship web's pane (F214, open). **The boundary takes no events itself**; the map decides when a click, right-click or drag is on it (`boundaryClicked` and its neighbours in `02-boundary.js`), treating anything with `leaflet-interactive` as a layer on top. A new layer that takes clicks must stop them or be interactive, or its clicks read as the boundary's. `tests/test_boundary_press.py` presses the real page in headless Chromium. |
| `src/map_settings_flow.py` | **View › Map Settings (V3.07):** the scroll-wheel zoom step, moved off the View row (where it was off-screen at 1366 px and never remembered), saved, and sent on every map load like the furniture below. |
| `src/map_furniture_flow.py` + `html/map/11-map-furniture.js` | **A north arrow and a scale bar on the map (F205, V3.06).** View → North Arrow / Scale Bar / Scale Units (kilometres by default, the owner's choice; metres on request, or by a click on the bar), remembered in QSettings and sent to the page on every load. Drawn by the page, so Export PDF's map picture (a `grab()` of the map) carries them: the arrow under the zoom buttons, the bar bottom centre, the two spots nothing else uses. The map never rotates, so the arrow never turns. The scale arithmetic is the pure `scaleBarFor`, run in node by `tests/test_map_furniture.py`. |
| `src/measurements.py` + `html/map/12-legend.js` + `html/map/13-species-numbers.js` + `src/legend_flow.py` | **A measurement is part of the design; the legend names what is drawn (F215–F217, V3.11).** A measurement lived only in the map page until V3.11, so Python's undo (a snapshot of the features) could not see it and Ctrl+Z after measuring undid the thing before it: it is a feature now (`element_type: "measurement"`, file format 1.10), told to Python by the page (`onMeasurementAdded`), drawn again on open and undo by `loadMeasurement`, and selectable. **One Delete is one bridge call** (`onSelectionDeleted`), which Python runs through each kind's own handler inside one checkpoint: one undo step. The legend is built from what is on the map and shown (Leaflet's `layeradd`/`layerremove`, debounced, only while open) as a pure `legendModel` + `legendHtml` node can test; boundaries Simple or Named (`name` on the boundary, asked for by Python's dialog), plants by Type or Species, **numbered as `planting_map._numbering` numbers them** and drawn on the map at every zoom by `13-species-numbers.js` (F218): a plant big enough holds its own number, smaller ones of a species close together share one, none covers another, and the legend counts the ones waiting; a species line rings its plants. A number was drawn only on a plant 7 px across until F218, so at a whole yard's zoom the owner saw none and did not know they existed. A boundary's **Corner Handles** (`show_handles`) switch whether a press shows its handles. The switches are remembered by `legend_flow` (QSettings). Shape outline editing moved to `02b-shape-edit.js`, unchanged. |
| `html/scene3d/01b-surface.js` | **Plant surfaces + `plantMaterial` (F63, V2.33).** Ten procedural surface classes (bark smooth/furrowed/papery/shaggy/scaly, leaf matte/glossy/pubescent/glaucous, needle) sampled triplanar in object space — no UVs, no textures in the GLBs, both of which are contract. Also owns the wind shader and `applySceneWind`. |
| `html/scene3d/01c-leaves.js` | **How a leaf is lit (F186, V2.94).** From a person's height every crown was more than half near-black, and green from above, which is how the V2.87 audit saw it. A leaf material now takes the sun and sky on its far side times the share it lets through (`LEAF_TRANSLUCENCY`: broad leaves 0.55, herbs 0.45, needles 0.3), and the baked grey shade is moved off the leaf's colour onto the light: all of it on the sky, `BAKE_ON_SUN` (0.3) on the sun, because the shadow map already shadows the sun. It edits three.js shader chunks by `String.replace`, which is a silent no-op on a renamed chunk, so `tests/test_leaf_light.py` checks every hook against the vendored three.js; **re-run it after any three.js upgrade**. The trees and, since V2.96, the shrubs are baked with `build_all.CROWN_AO` (the ground at 0, not at the crown's lowest leaf). Until V2.96 no shrub drew its bake: the shrub layer left out `surfaceMaterial`'s third argument, which reads as "no vertex colours" (F188). **Every call must now pass it** (`test_scene3d_render.VertexColourFlagTest`), `true` where the geometry carries colours, since a baked part always does and procedural bark does not. |
| `html/scene3d/02-plants.js` (`buildGround`, `terrainHeightAt`, `onGround`) + `tests/test_slope_render.py` | **The ground is `terrainHeightAt`, everywhere (V3.04).** Until V3.04 the terrain was a patch the size of the boundary's box over a flat apron at the site's lowest point, and only what *stands* asked how high the ground is: on the owner's sloped yard the sky showed under the patch's edge and the trees' shadows lay on the apron in front of them. Now one mesh is built from `terrainHeightAt` (its clamp carries the grid's edges outward, out to the fog), and **anything that lies on the ground must ask it too**: `onGround` for a flat thing (it tilts with the slope), `terrainHeightAt` for a base. A click meets it through `groundPointAt` (16-editing.js), never a plane at 0, and the orbit keeps the camera above it (`keepAboveGround`, 01-core.js). `html/slope_probe.html` is the headless check; headless Chromium stops drawing frames a few seconds in, so read a measurement off the scene, not off the render loop. |
| `html/scene3d/14-layers.js` | The procedural layer tufts (groundcover / grass / aquatic), split out of `04-quality.js` in V2.34, and since V2.89-V2.90 the horsetail and mare's-tail bodies (the vine column went in V2.89). The permanent fallback for the layer archetypes — Stylised skips the GLBs on purpose, so these run every session and cannot rot. |
| `html/scene3d/03b-trees.js` + `scripts/blender/assetlib/flora_trees.py` | **Trees with their own shape (F178, V2.92).** The procedural trees (split out of `03-herbs.js` in V2.92: crown form, the da Vinci skeleton, conifer and pine bodies) and the Blender builder behind the baked ones. A tree's architecture is per archetype and off by default: `stems` (a clump of trunks), `leaders` (the first fork), `rise` (limbs that keep climbing), `twig_r`, and a compound leaf's `leaflet_pairs`/`leaflet_len`, on the `_PROF` rows in `02-plants.js` and in `DECID_GENERA`, so adding one leaves every other tree byte-identical. `tests/test_tree_shapes.py` measures the shipped GLBs. Black Spruce shares White Spruce's model on purpose (P9). |
| `html/scene3d/15-florets.js` | **The bloom as geometry (F80, V2.34).** A floret built from petal count × petal shape × radial/bilateral symmetry, plus a separate disc in its own colour, placed by one of nine inflorescence architectures (`solitary·raceme·spike·panicle·corymb·umbel·head·cyme·whorl`) — and **lit**, where the old billboard was `MeshBasicMaterial`. Reads the ten schema-v53 columns; an empty `flower_arch` falls back to the 05-flowers.js billboard, and Stylised keeps the billboard on purpose. |
| `src/vine_habit.py` + `html/scene3d/22-vines.js` | **A vine is drawn on what it climbs (F179, V2.89).** The owner's rule: a vine climbs the tree or shrub whose footprint touches its own (nearest crown edge wins; an existing tree counts; a dead or not-yet-present one does not; since V2.93 a shrub recorded `branching: rosette`, the yucca, has no crown and does not, and `holds_vines` is the one test the scene and the generator's seating both ask) and otherwise lies on the ground, at most 30 cm tall. A vine's recorded height is how far it *climbs*. Python decides it once, in `build_scene`, as a `drawn` block that the viewer and `scene_wildlife` both read, the V2.88 lesson of the floating flowers. The viewer fits the stems to the host's **drawn** crown, measured per archetype along mesh edges (a trunk has vertices only at its two ends), because an ideal cone or ellipsoid misses a spruce by a metre. Nothing is baked for it: the retired `layer.vine` column could not fit whichever crown it landed on. |
| `src/vine_seating.py` | **Where the generator plants a vine (F181, V2.90).** At the base of a tree or shrub it planted: half the host's crown radius out (0.25-0.6 m), sunny side first, one vine per small shrub up to three per big tree. The base, not the drip line, because the V2.89 rule is re-asked every year of the timeline and a vine at the mature drip line is a metre from a young shrub. With no host it places the vine anyway and `vines_with_nothing_to_climb` names it in the design notes (the owner's option c), asking `build_scene` rather than re-deriving the rule, so the note cannot disagree with the 3D preview. Runs after the critic's repairs and the top-ups, which seat a vine they add the same way (V2.91). |
| `src/open_ground.py` | **Where the design review plants what it adds (F183, V2.91).** The critic's repairs and the goal and wildlife top-ups had put everything on the boundary's first 6 m grid cell. `OpenGround` answers one plant at a time from the plants actually placed, not from the main pass's positioner, which has no free cell left on a full yard: inside the boundary and the drawn fill zones, clear of keep-out (the design's own pond included), free ground by `_plant_spacing_m`, then the main pass's cell score, then nearest the planting; the least crowded spot when nothing is free; a vine at a shrub's foot by F181's seats. **None of the follow-up steps adds a plant that needs standing water** (`zoning.needs_standing_water`: 23 species, not the 139 that merely like it wet); an animal fed only by those gets a design note. `apply_repairs` hands `position_for` the row it is placing. |
| `src/pond_planting.py` | **Where the generator plants what grows in water (F185, V2.95).** A plant that needs standing water (`zoning.needs_standing_water`) goes in a pond or is not placed: floating and submerged plants in the open water, at most 70% of the way out, so on the water `pond_habit` draws; emergents in the shallows (85% out) of the north two-thirds of the shore; floating leaves on at most half the water. `split_water` takes water plants and the pond communities out of a resolved spec before anything is placed (so a dry design is laid out exactly as before, and density never multiplies cattails), `seat_water` seats them after the pond, and with no pond one note names them. `plant_bare_ponds` plants a pond the design placed and left bare (one floating, one submerged, two emergents); the wildlife and goal top-ups seat a water plant there when that is all that would serve. `NOT_CHOSEN_AUTOMATICALLY` keeps *Myriophyllum sibiricum* off lists the generator writes itself: its catalogue name is the Eurasian invasive's (F172). **The app had dropped every generated structure** (`controllers/generation._render` copied plants only); they now reach the map, one undo step with the design. |
| `src/pond_habit.py` + `html/scene3d/23-pond.js` | **Each wetland plant drawn by its own body (F175, V2.90).** floating / submerged / broadleaf / whorled / reed / herb, from `growth_form` and the leaves, decided once in `build_scene` as a `drawn` block. **The pond's water is an opaque sheet 10 cm up** (`struct_pond.glb`), so a floating plant inside a pond's ellipse is drawn at its surface, and a test reads the model file to keep the constants honest. A floating or submerged plant's recorded height is stem length under water, like a vine's length, not stature. Mare's-tail is the horsetail builder's unit 3; mind the layer's variant count, which once wrapped it onto the scouring-rush. |
| `src/succulent_habit.py` + `html/scene3d/24-succulents.js` | **Each succulent drawn by its own body (F177, V2.93).** pads (`growth_form: pads`, the prickly pears) / ball (`globose`) / swords (a shrub recorded `branching: rosette` with narrow leaves, the yucca) / fleshy (`succulent`; on a groundcover, over a mat), decided once in `build_scene`, with the counts the viewer builds to (balls, rosettes, stalks from `flowering_stems`) and the stalk season (bloom start to fruit end). **The blooms sit on the body**: the floret, billboard and fruit layers ask `succulentAnchorsFor(p)` after `vineAnchorsFor(p)`, and its anchors carry `top: true`, which means the bloom's top is there, not the leaf it rises from. Procedural and per plant like the pond and the vines, about 2,400 to 6,000 triangles each; keep it there, because the first build was 97,000. It made `scene3d.html` 399 of 400 lines: the next chunk needs the bootstrap's FILES list moved out of the page. |
| `html/scene3d/13-stylised.js` | **Stylised bodies (F79, V2.34).** Detail level 0 is a STYLE, not a thinning: no baked models, no surface grain, flat-shaded, forbs as faceted masses. The levels are **Stylised / Balanced / Lifelike**. Own the argument here, not in the quality knob. |
| `src/wind_scene.py` | The site's real seasonal wind + a rasterised shelter grid, as the 3D scene consumes it (F68, V2.33). Joins `wind.py` and `wind_shadow.py` — both years old — to the viewer that never read them. |
| `src/presentation_still.py` | The render you put in a proposal (F69, V2.33; `Design principle P13`). Turns the docent's beats — whose `year`/`season_month`/`camera` nothing had ever read — into still specs the 3D window renders at print resolution and `pdf_export` lays out. |
| `src/llm_design.py` | Generate Design: LLM spec → deterministic placement (scored cells, zones, keep-out, density). |
| `src/why_here.py` | **Why a generated plant is where it is (F19, V3.05).** Every rule that places a plant writes its reason onto the plant (`why_here`, carried by `project_store`): the chosen cell's score in words (`placement_score.explain_cell_for_plant`, or `NO_SITE_DATA_WHY` with no terrain or shade), or the rule's own words for a vine at its host's foot, a mixed stand, a community, the design review's additions and the pond. The plant's page shows them first when it is clicked on the map (`species_flyout.on_plant_clicked`; the click had never been listened to). A new placing rule should stamp its reason too, or its plants' pages fall silent. |
| `src/design_critic.py` | Evaluate→revise→repair loop for generated designs (V1.62). |
| `src/placement_score.py` | Per-cell ecological scoring + aesthetic composition terms (V1.62). |
| `src/scene_contract.py` | Versioned Scene JSON (`build_scene`) — the project→3D contract (V1.62). |
| `src/scene3d_window.py` + `src/map3d_widget.py` + `html/scene3d.html` | View → 3D Preview: built-in three.js viewer (or the `web3d/dist` map3d fork build when present). Its terrain and photo workers live in `src/scene3d_workers.py` (V3.08, moved to make room under the window's 950-line ceiling); it follows the design (`src/follow_design.py`). |
| `src/scan_import.py` + `src/scan_import_dialog.py` | Phone-scan import: point cloud → control-point georeference → nDSM → shade-casting footprints + 3D point layer (V1.62–63). Detects Gaussian-splat PLYs (V1.65). |
| `src/splat_backdrop.py` + `src/splat_flow.py` | Gaussian-splat photoreal backdrop (V1.65): file→three.js world matrix, lat/lng footprint, `splat_backdrop` feature (Qt-free core) + the map-side "yard photo" overlay glue. Rendered by Spark in `html/scene3d.html`; baked top-down onto the 2D map. |
| `src/building_store.py` + `src/building_downloader.py` + `src/building_flow.py` | Offline building-footprint pack (V1.66): SQLite `buildings.db` tile store + region bulk-downloader (OSM-sourced, mirrors the contour pack) + the import/download orchestration. Feeds the existing `osm_features.add_features_to_project` → `canopy_footprint` → shade + 3D. |
| `src/wind.py` + `src/wind_flow.py` + `src/wind_rose_widget.py` | Wind data (V1.67): Open-Meteo seasonal wind rose (DB-cached in `wind_cache` → offline) + live current reading + windbreak-orientation hint (Qt-free core in `wind.py`); off-thread fetch + QPainter rose in the Analysis → Wind tab. |
| `src/wind_shadow.py` + `src/wind_shadow_flow.py` | Dynamic wind shadow (V1.68): porosity-aware per-plant shelter merged via shapely (Qt-free core, reuses `shadow_geometry`); a 0–360 dial + "Live wind shadow" toggle drive a JS ghost (`06-overlays.js`, redrawn live on dial/drag) with Python computing the authoritative merged bands on commit. Wired from `app.py` (controllers at their ceilings). |
| `src/soil_grid.py` + `src/soil_downloader.py` + `src/soil_flow.py` | Offline soil pack (V1.67): download-once Gridded Soil Landscapes of Canada GeoTIFFs sampled by lat/lng (rasterio+pyproj). `property_data.fetch_soil` order = pack → SoilGrids → regional. `soil_flow.apply_soil_site_fields` wires soil pH into plant matching. |
| `src/permadesign_api.py` + `src/mcp_server.py` | Scripting facade + MCP tools (contract frozen by `test_architecture_guard.py`). |
| `src/terrain.py` etc. | DEM fetch + slope grid + contour rendering. |
| `data/*.json` | Shipped seed data (plants, fauna, plant↔fauna links). |
| `tools/ecoregions/` | **Dev-only ecoregion rebuild pipeline (V2.66).** Six stages: fetch → inspect schema → harmonize (ELC geometry + Alberta subregions as a spatial-join attribute) → validate (blocking point probes) → render (publication map with hillshade) → export (GeoPackage + GeoJSON). Two of its three classification sources need a machine with open egress; `python -m tools.ecoregions.fetch` prints exactly what to download. Reads `src/ecoregion_palette.py` so the printed map and the website cannot drift. See `tools/ecoregions/README.md`. |

## Architectural conventions worth knowing

- **Database path:** `~/.local/share/Site & Pattern/permadesign.db` (Linux),
  `%APPDATA%/Site & Pattern/` (Windows), `~/Library/Application Support/Site & Pattern/` (macOS).
  Never put the DB inside the source tree — `tests/test_polycultures.py`
  has an assertion that enforces this.
  - **The data folder was `PermaDesign` before the V1.69 rebrand** and is renamed
    to `Site & Pattern` once, in place, on first launch — `src/user_paths.py` is the
    single source of truth (`user_data_dir` / `data_dir_path` / `migrate_legacy_into`);
    all stores (`plants`, `building_store`, `terrain_store`, `soil_grid`, `image_cache`)
    go through it. The DB *filename* stays `permadesign.db` (internal). The display
    name lives in `src/branding.py` (`APP_NAME`); the QSettings org/app name, the repo,
    and the frozen `permadesign_api`/MCP symbols deliberately keep the legacy name.
- **FK constraints are ON at runtime** (`plants.py:get_connection`) but
  disabled temporarily during the bulk reseed (Python 3.14 enforces FKs
  at statement time rather than transaction-commit time).
- **`permaculture_uses` is junction-backed (schema v37, V2.2):** the
  denormalized comma-blob column was dropped from `plants`; the
  `plant_uses` junction (seeded from the JSON `permaculture_uses` field)
  is the single source of truth. Read-side consumers still see a
  `permaculture_uses` comma-string, but it is *synthesized on read* from
  the junction in `get_plant` / `get_all_plants` / `search_plants` /
  `get_companions` (via `_attach_permaculture_uses`). The keyword filter
  in `search_plants` matches use tags through an EXISTS-on-`plant_uses`
  subquery. The JSON seed field stays — it feeds both the junction and
  `data_quality` validation.
- **The map only stores `(lat, lon)`.** Distance/area math goes through
  `src/projection.py` — default backend is the legacy cosLat metric
  (~1% error at <2 km — centimetres at yard scale, the app's real domain).
  A parallel UTM backend existed until V2.22 but no code path ever enabled
  it; it was deleted. A future accurate backend belongs behind the same
  `Projector` interface.
- **Placed-plant state has ONE write path:** `src/project_store.py`
  (V1.62). The project dict's plant features and the `_placed_plants`
  index are kept in sync by the store; `tests/test_project_store.py`
  fails the build on any new direct mutation in `src/`.
- **Taxon names (V2.80–V2.82).** **The common name is the foreign key here and
  the scientific name is not**: edges in `plant_fauna_master.json` join on it and
  public URLs are slugged from it. Change one only with
  `scripts/rename_common_name.py`; rename a binomial with `scripts/rename_taxon.py`;
  merge two rows with `scripts/remove_taxon.py --merge-into`. Compare names with
  `src/taxon_names.binomial()`, never by eye: V2.80 read four renames off the
  wrong end of an authority string. Every row's `native_provinces` is read from
  VASCAN (`native_provinces_source = 'flora'`), and the 18 recombinations the site
  has not adopted (*Galium* → *Trichogalium* and the like) are one open decision,
  allowlisted in `data_quality.KNOWN_NOMENCLATURE`, which fails the gate on any
  new synonym. Before touching the range maps, the site build or nativity, read
  the **Handing this over** section of
  [`V2.79-the-range-stops-being-ecoregions.md`](docs/plans/V2.79-the-range-stops-being-ecoregions.md):
  the decisions listed there are the author's and are not to be reopened.

## When making schema/data changes

1. Edit `src/db/schema.sql`.
2. Bump `_SCHEMA_VERSION` in `src/db/plants.py`.
3. If you added a dependent table, also add a `DELETE FROM <table>` to
   the reseed block in `init_db`.
4. Update or add a seeding helper following the
   `_seed_uses_lookup` / `_seed_fauna` pattern.
5. Add tests under `tests/` using the temp-DB pattern from
   `test_polycultures.py` / `test_uses_junction.py`.
6. Run `python -m unittest discover -s tests -t .`.

## Do not

- Push to `claude/*-Ntd5l` style branches. Use `V*.*` instead.
- Skip the schema version bump when changing schema or seed data.
- Hand-edit user data files outside of the seed JSON (they get
  overwritten on reseed anyway).
- Use `git commit --no-verify` or `--no-gpg-sign` on real commits
  unless explicitly asked.
