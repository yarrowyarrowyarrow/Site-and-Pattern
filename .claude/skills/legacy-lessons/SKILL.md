---
name: legacy-lessons
description: The ledger of this project's painful failures and the guard or convention each one spawned. Use when a guard test seems arbitrary, when you're tempted to "clean up" something odd (legacy PermaDesign names, load-bearing console.log calls, an empty-string safety value), when onboarding, or when writing a post-mortem for a new incident. Covers the V1.40 split fallout, the frozen-build and SSL failures, the Windows contour freeze, the codename-branch incident, the reseed-that-never-fired class of bugs, the P12 removals, and the rebrand's deliberate legacy names.
---

# Legacy lessons — why the guards exist

Every strict rule in this repo is a scar. This ledger records the
incident behind each one, so the next engineer treats the guard as
institutional memory rather than bureaucracy — and knows that the
correct response to tripping one is almost never to delete it.

Format per entry: **what happened → root cause → the scar (what now
prevents it) → the rule to carry forward.** Detail lives in the linked
skills; this file is the *why*.

## 1. The V1.40 panel-split fallout (two scars)

Splitting `src/plant_panel.py` moved constants and renamed methods.
Two distinct breakages shipped and needed a V1.40.1 patch:
- Function bodies still referenced `_UPPER_CASE` constants that no
  longer existed in their module — imports resolved, clicks crashed.
- MainWindow shims pointed at controller methods that had been renamed —
  again invisible at import time, fatal at click time.

**Scar:** `tests/test_imports_resolved.py` (dangling-name detection) and
`tests/test_controller_shims.py` (every shim must resolve statically).
**Rule:** after ANY move/rename, run both guards and grep `src/app.py`
for shims naming the old symbol. Import-time success proves nothing
about click-time. (See `add-feature`.)

## 2. The vanished Analysis tab

A `_build_*_tab` method was refactored so `addTab` happened elsewhere;
the method silently built a widget nobody attached. The Habitat tab
simply disappeared — no error, no test failure.

**Scar:** `TestAnalysisPanelTabsRegistered` in
`tests/test_architecture_guard.py` — every `_build_*_tab` must call
`addTab` inside itself.
**Rule:** a green suite doesn't prove a widget is visible. UI-visible
changes need eyes or an explicit registration guard. (See `verify`.)

## 3. The Windows maximise-with-contours freeze

Maximising the window with the contour overlay on froze the whole app
on Windows. The eventual fix looks like noise: `console.log(...)` reads
of `clientWidth` (which force Chromium layout reflows) and `_dbg()`
file writes (which yield to the OS scheduler) inside the map's
`invalidate_size` path. Any tidy-minded engineer would delete them.

**Scar:** `tests/test_map_js.py:TestInvalidateSize` pins the exact
statements, and the block comment in `src/map_widget.py` explains them.
**Rule:** in embedded-Chromium code, apparently-useless statements can
be load-bearing. Never "clean up" around map sizing without reading the
pinned test first. (See `map-frontend`.)

## 4. Frozen build: "No such file: schema.sql"

The installed Windows build crashed on first launch: bundled files were
resolved with `__file__`-relative joins, which point inside the
PyInstaller bundle differently than in a source checkout. Dev machines
never saw it.

**Scar:** `src/resources.py:resource_path` (source → repo root; frozen →
`sys._MEIPASS`) + `tests/test_resource_path.py`, plus the `datas` list
in `scripts/packaging/permadesign.spec`.
**Rule:** every bundled `data/`/`html/`/schema read goes through
`resource_path`. "Works from source" is not evidence for the frozen
build. (See `debugging` §7, `release-packaging`.)

## 5. rasterio/pyproj broke the DMG and EXE builds

Adding heavy geo dependencies to `requirements.txt` broke the frozen
macOS/Windows builds outright (commit "Fix macOS DMG (and Windows EXE)
build: move rasterio/pyproj to optional reqs").

**Scar:** `requirements-optional.txt` + the guarded-import pattern
(`_HAVE_SHAPELY`-style flags, features degrade when the dep is absent).
**Rule:** heavy/compiled deps are optional; modules guard the import and
skip the feature. Tests gate on the capability flag, never assume the
dep. (See `run`, `geo-projection`.)

## 6. Silent HTTPS death on macOS and frozen builds

Photos, elevation, OSM import, and address search all "just didn't
work" on packaged builds — no errors, because every fetcher degrades
gracefully to offline fallbacks. Root cause: no usable CA bundle, so
every `urlopen` failed `CERTIFICATE_VERIFY_FAILED` while the Leaflet
map (Chromium's own cert store) kept working, making the app look
half-online.

**Scar:** `src/ssl_bootstrap.py:ensure_ca_bundle()` at startup +
`tests/test_ssl_bootstrap.py`.
**Rule:** when networked features die together, suspect certs before
logic — and never disable TLS verification as a fix. Graceful
degradation is a feature that *hides* bugs; test happy paths with
canned JSON. (See `external-data`.)

## 7. The codename-branch incident

Coding-agent harnesses kept suggesting `claude/*` codename branches as
the session default — but the in-app updater detects new versions by
scanning `origin/V*.*` branch names (`src/version_branch.py`, consumed
by `src/controllers/update_flow.py`). Work pushed to a codename branch
is invisible to it: the release simply never reaches users, with no
error anywhere.

**Scar:** `.claude/hooks/branch_policy.py` — SessionStart auto-switches
to the correct V-branch; a PreToolUse guard *blocks* pushes to codename
branches. The convention is enforced by machinery, not memory.
**Rule:** conventions that other systems consume must be enforced by a
hook or a test, never by remembering. And: the branch push IS the
release action (the workflows key on it). (See `start-work`.)

## 8. "I edited the seed JSON but nothing changed"

The single most-repeated failure class: editing `data/*.json` without
bumping `_SCHEMA_VERSION` in `src/db/plants.py`. Existing installs only
reseed when the stored version is older, so the change silently never
ships. Worse, dev machines often have `count < 100` toy DBs that reseed
anyway — masking the bug until release.

**Scar:** the bump-on-any-seed-change rule in `CLAUDE.md`, the
changelog-comment convention above the constant, and the wipe-list
discipline in `init_db`.
**Rule:** schema or seed change ⇒ version bump, no exceptions; note
`schema vNN` in the commit subject. (See `schema-change`, `seed-data`.)

## 9. Python 3.14 broke the reseed (FKs at statement time)

The bulk reseed inserted parents and children in one transaction, which
was fine until Python 3.14's sqlite3 enforced FK constraints per
statement instead of at commit — mid-reseed failures on user upgrade.

**Scar:** the reseed block flips `PRAGMA foreign_keys` OFF for the wipe
+ insert and back ON after; runtime connections keep FKs ON.
**Rule:** seed data must be internally consistent on its own (resolve
names→ids yourself); never assume transaction-scoped FK deferral. (See
`schema-change`.)

## 10. The denormalized `permaculture_uses` blob

`plants.permaculture_uses` was a comma-string column duplicating the
`plant_uses` junction — two stores of the same fact, one string-matched
by filters and one read by scores, free to drift apart. Schema v37
dropped the column; the comma-string consumers still see is synthesized
on read from the junction.

**Scar:** `tests/test_uses_junction.py:test_permaculture_uses_column_dropped`.
**Rule:** one source of truth per fact; synthesize legacy shapes on
read rather than storing them twice. Don't reintroduce the column, and
don't `SELECT` it. (See `schema-change`.)

## 11. Hand-rolled placed-plant mutations (why ProjectStore exists)

Before V1.62, placement gestures appended to `project["features"]` and
the `_placed_plants` index separately, in many call sites. Missed
updates desynced the map, the saved file, and the analytics — the class
of bug where "the panel says 12 plants, the map shows 11".

**Scar:** `src/project_store.py` (the single write path) +
`tests/test_project_store.py`, which **greps the whole `src/` tree** and
fails the build on any new direct mutation.
**Rule:** two structures that must agree get one mutator and a
consistency checker; enforcement by grep beats enforcement by review.
(See `placed-plants`.)

## 12. The P12 removals (medicine wheel, paintbrush)

Early seed data shipped a "First Nations Medicine Wheel" community and
the name "Red Indian Paintbrush". Both operationalized or carried
Indigenous framing without consent. The v16/v17 changelog in
`src/db/plants.py` records the deliberate renames ("Native Prairie
Aromatics" / "Aromatic Herb Circle"; "Common Paintbrush").

**Scar:** the P12 hard rule in `CLAUDE.md` + the SessionStart primer
hook. This is the only rule in the repo with a **stop-and-ask** — not a
judgment call you make alone.
**Rule:** free, prior, informed consent before encoding Indigenous
knowledge anywhere (data, recommendations, prompts, UI copy). Until
then, references are directional only. (See `philosophy-check`.)

## 13. The rebrand's deliberate legacy names (V1.69)

PermaDesign became Site & Pattern — but only where users can see it.
Things that keep the legacy name **on purpose** (each broke something
or someone when "fixed" naively):

| Keeps `PermaDesign` | Why |
|---|---|
| DB filename `permadesign.db` | Renaming it orphans every existing install's data. |
| `src/permadesign_api.py`, CLI prog, MCP server name | Frozen public contract — renaming breaks every agent/script (see `agent-api`). |
| QSettings org/app name | Renaming silently resets all user preferences. |
| HTTP User-Agent (`src/http_utils.py`) | Stable identity for API providers' allow/rate lists. |
| `~/.permadesign_config.json` | Existing users' LLM endpoint config. |

The data *folder* did migrate (`PermaDesign` → `Site & Pattern`, once,
in place — `src/user_paths.py:migrate_legacy_into`), and all
user-facing strings flow from `src/branding.py` (guarded by
`tests/test_philosophy.py`).
**Rule:** a rebrand renames surfaces, not identities. Before "fixing" a
legacy name, find out who depends on it. When you meet a weird name,
check this table before renaming.

## 14. The tests that silently run nothing

`tests/test_property_data.py`, `tests/test_climate.py`, and
`tests/test_map_features.py` are pytest-style bare `def test_*`
functions. There is no pytest in this repo, so `python -m unittest`
collects **0 tests** from them and reports `OK` — green with zero
assertions executed. This misled more than one session into believing
a change was covered.

**Scar:** the warnings in the `testing`/`external-data` skills;
`test_map_features.py` has a self-runner (`python
tests/test_map_features.py`).
**Rule:** new tests are `unittest.TestCase` subclasses, full stop. If
you touch those modules' subject areas, run them as scripts or wrap
them. "OK (0 tests)" is a failure mode, not a pass.

## 15. QThread workers garbage-collected mid-flight

Background fetches crashed the app intermittently and unreproducibly:
the Python-side `QThread`/worker objects weren't referenced anywhere,
so the GC destroyed them while the OS thread still ran.

**Scar:** the worker pattern in `src/wind_flow.py` and
`src/controllers/generation.py` — hold `main._<x>_thread` /
`self._thread` refs, tear down via `finished → deleteLater`.
**Rule:** copy the canonical worker verbatim, including the cleanup
lines that look optional. Intermittent crashes near threads = missing
reference, not a Qt bug. (See `add-feature`, `external-data`.)

## 16. The top-band design (V2.20)

A user screenshot showed a generated design with every plant crammed
along the boundary's north edge and one corner — ~80% of a 3,372 m² lot
empty. Three compounding causes, none of which any test caught because
the tests asserted *validity* (inside boundary, no duplicates) but never
*distribution*:
- The placement pool (`grid_cells_in_boundary`) is row-major from the
  NW corner, and the no-terrain `_Positioner` consumed it **in list
  order** — anchors marched along the top rows.
- On flat sites the scored path's strict-`>` tie-break degenerated to
  the same first-cell-in-list choice, and the bed-cohesion aesthetic
  term then actively pulled every later group toward the first.
- Each species' whole quantity landed as **one blob** at a single
  anchor (a qty-12 wildflower at 0.5 m spacing is a 2 m dot), so even
  well-spread anchors couldn't use the space.

**Scar:** farthest-point anchor sampling (spread term at 20% of the
placement score; first anchor still decided by ecology + composition,
with centrality as an epsilon tie-break — `tests/test_aesthetics.py`
caught the first draft of this fix overriding the tall-tree-north
rule), `_split_into_drifts` (species repeat as capped drifts),
habit-weighted density expansion, ecological ranking of the offline
pick (wetland specialists demoted for unknown-moisture sites) — all in
`src/llm_design.py` — plus `tests/test_llm_design.py:TestPlacementSpread`
and `tests/test_placement_score.py:TestAnchorSpread`, which assert
coverage, drift separation, ecology-beats-spread, and determinism.
**Rule:** when an algorithm selects from an ordered pool, list order is
a hidden bias — either randomize deterministically or make the ordering
criterion explicit. And test the *shape* of an output (spans, spacing,
distribution), not just its validity; "all plants inside the boundary"
was green while the feature was visibly broken. (See `generate-design`.)

## 17. The updater's self-made dead end (V2.29)

A user screenshot: **"Update failed — git merge --ff-only failed: error:
Merging is not possible because you have unmerged files"**, followed by
the dialog's advice, *"You can finish from a terminal instead: `git pull
--ff-only`"* — which fails with the **identical** error. The app had
painted itself into a corner and then handed the user a map back to the
same corner.

It had also *built* the corner. `update_to_branch` stashes local edits,
switches branch, then pops. A conflicting `git stash pop` keeps the stash
(good) but leaves the working tree **full of unmerged files** (bad), and
the old code returned `(True, "kept safe in the stash")` — truthful about
the stash, silent about the wreckage. git then refuses every merge,
switch *and* stash, so every later Check for Updates hit the same wall.
Reproduced in six lines of git; the tests had covered the
successful-stash-and-restore path and the diverged-branch path, but never
a **conflicting** pop.

**Scar:** `version_branch.unmerged_paths` +
`abort_conflicted_state` (`git reset --merge` — *not* `--hard`: it resets
only paths differing between HEAD and index and refuses rather than
clobbering unrelated edits); `update_to_branch` now aborts the half
application so the checkout it hands back is always updatable;
`update_flow._clear_conflicts_if_any` runs before both update paths and
offers the way out *with consent* (a conflict the user is hand-resolving
must never be discarded silently); and the failure text only suggests a
terminal command when that command can actually work.
`tests/test_version_branch.py:TestConflictedCheckoutRecovery` pins the
symptom itself — including that `git pull --ff-only` cannot fix it — and
`test_architecture_guard.py` pins the wiring plus a **tightened**
destructive-git check: exact-token matching (so the files may keep
documenting the `--hard` they must not run), now covering `clean`, `-f`,
`--force` and `version_branch.py` as well.
**Rule:** an error message is a dead end unless it names a command that
works *from the state the user is actually in*. Check the state, then
advise. And when a recovery path can conflict, test the conflict — the
happy path proves nothing about the corner your code leaves behind.

## 18. The half-deleted foliage (V2.29)

Another user screenshot: every shrub in the app a bundle of dark wiry
canes, in midsummer, described as *"still looking wirey and bare year
round"*. Every guard was green. The leaves were provably built, budgeted
under their triangle ceiling, sized from each species' `leaf_size_cm`,
shaped by its `leaf_shape`, arranged opposite-vs-alternate by its
`leaf_arrangement`, and positioned across the whole crown — a test even
pinned that foliage reaches 90% of every woody unit's height.

None of that is what draws pixels. The V2.29 rebuild replaced the shrubs'
closed 20-triangle icosahedral leaf blobs with **flat leaf ribbons**, and
`MATS.shrubFoliage` stayed on `THREE.FrontSide` — correct and cheaper for
a solid, fatal for a ribbon, which simply is not drawn from behind. About
half of every shrub's foliage rendered as nothing at all.

The interesting part is the guard that *would not* have worked. The
obvious instinct is a render-level check: boot the viewer, hide the mesh,
count the pixels that change. Built it (`window.permaVisibility`) and
measured — the culled foliage still drew **9,492 pixels against 16,782**
fixed, because half of a leaf's faces do point at the camera. A
"does this draw anything" assertion sails straight past a 44% loss. The
invariant that actually bites is a source-level one:
`tests/test_scene3d_render.py:FlatLeafMaterialsTest` — every material
applied to flat leaf geometry must be double-sided, plus a check that
`plantMaterial` still maps the flag onto `THREE.DoubleSide` so the first
check means something.

**Scar:** `doubleSide: true` on `MATS.shrubFoliage`, joining `leaf` and
`blade`, which had always been ribbons.
**Rule:** when geometry changes *kind* — solid to ribbon, closed to open,
opaque to alpha — every material applied to it is now unreviewed. And
before trusting a proposed guard, measure what it would actually have
reported on the real bug; a guard that would have passed is worse than
none, because it will be believed.

## 19. The cp1252 crash, twice (V1.95, then V2.78)

The author ran the full suite on Windows and got **seven errors, all the
same**:

```
records = json.loads((self.tmp / "plants_master.json").read_text())
...
UnicodeDecodeError: 'charmap' codec can't decode byte 0x8f in position 899031
```

`Path.read_text()` and the builtin `open()` decode with the **locale**
codec, not UTF-8. On Linux that is UTF-8 and everything works; on Windows
it is cp1252, and `data/plants_master.json` carries 966 non-ASCII bytes
(en dashes, accented names) that cp1252 cannot decode at all.

**This project had already learned this.** V1.95 hit it in
`src/sprite_gallery.py`, fixed it, left an explanatory comment beside the
fix, and wrote a guard — `test_seed_reads_pin_utf8_encoding` — which reads
**exactly one file**. So when V2.75's data-quality tests read the same seed
JSON the same bare way, nothing objected. Two releases shipped a suite that
was green on every Linux machine and had seven errors on the only machine
whose owner reads the output.

Chasing the fix surfaced a second dress of the same bug.
`PYTHONWARNDEFAULTENCODING=1` with `-W error::EncodingWarning` turned up
**17 `subprocess(text=True)` calls** with no encoding — including
`scripts/retag_releases.py` reading `git log --format=%s`, i.e. this
repo's own commit subjects, which are full of em dashes. It would have
died on the first one.

**Scars:** 37 text-file call sites and 17 subprocess calls pinned to
`encoding="utf-8"`; `TestEveryTextFileReadPinsItsEncoding` in
`tests/test_architecture_guard.py` covering `src/`, `scripts/`, `tests/`
and `tools/`.

**Rules:**

1. **Never open a text file or a text-mode subprocess without an explicit
   encoding.** There is no case in this repo where the locale codec is the
   right answer.
2. **A guard scoped to the file where the bug was found does not stop the
   bug — it stops that instance of it.** The V1.95 guard was correct, tested,
   green, and useless, because the second occurrence was in a different file.
   When writing a guard, ask what *class* of thing is wrong and scope it to
   the tree.
3. **Scope a tree-wide guard precisely or it gets switched off.** An earlier
   draft flagged `rasterio.open`, `Image.open`, `fiona.open` and
   `webbrowser.open` — eleven false positives that have nothing to do with
   text encoding. It checks pathlib's `read_text`/`write_text` and the
   *builtin* `open` in text mode, and nothing else.
4. **A green suite on one OS is evidence about one OS.** Both the tests and
   `PYTHONWARNDEFAULTENCODING=1` are cheap; the author's machine was the only
   instrument that could see this.

## 20. A failure is not an absence, the third time (V2.79)

The VASCAN nativity fetch ran clean -- 434 species, zero failures -- and
reported **182 species not recorded from Alberta or Saskatchewan**. Forty-two
per cent of a native plant catalogue, including *Amelanchier alnifolia*, the
defining parkland shrub the whole range pipeline was started over.

Two probes found the cause, and it was not about the flora:

| query | rank | distribution |
|---|---|---|
| `Amelanchier alnifolia` | species | **absent** |
| `Amelanchier alnifolia var. alnifolia` | variety | AB, SK, MB native |

**VASCAN attaches distribution to the lowest accepted taxon.** A species with
recognised varieties carries none on its own record. The parser was reading the
right key all along; `assess()` let a **missing** block fall through to
`origin: absent, verdict: not_here`, with a `why` reading *"VASCAN records no
Alberta or Saskatchewan distribution."* A sentence the data did not support,
about 173 species.

**Scars:** `lookup()` records `has_distribution` and `taxon_rank`; `assess()`
has a fourth origin, `undetermined`, that can never reach `not_here`; the
ingest gives it its own bucket; `--reassess` re-runs verdicts over an
already-fetched file with no network, so a parser fix costs a re-read rather
than 434 requests.

**Rules:**

1. **Every external field is three states, not two.** Present-and-says-yes,
   present-and-says-no, and *not present*. Code that models two will publish
   the third as whichever of the other two it falls through to. This is now the
   third instance: V2.75's rate limit logged 208 throttled species as growing
   nowhere; V2.78's harvest cap made a truncated fetch indistinguishable from a
   complete one; this one turned a missing field into an absence.
2. **Cache the raw answer and make re-parsing cheap.** `--reassess` and the
   occurrence point cache are the same idea. Without it every parser bug costs
   a re-fetch on somebody's laptop, which is why V2.75 could diagnose a bug it
   could not fix.
3. **A result that is plausible in shape is not verified.** 182 absences looked
   like a finding and read like one in a report. What caught it was checking a
   single species whose answer was known in advance.

## 21. A picture with no test and no caller (V2.80)

**What happened.** V2.79 shipped `src/range_map.py`, a new species range map,
with three palettes for the author to choose between. The verdict was *"all
look identical."* The handover explained it with arithmetic — 10-30 record
marks land in each grid square, so the range wash underneath is buried — and
recommended shading the squares by record count instead.

The arithmetic was right and it was not the cause. The renderer draws the
subject provinces, then the range squares, then the province outlines **again**
so a border stays legible where the wash sits against it. That second pass
reused `.subj`, whose fill is opaque white. Every build drew all 361 squares and
then painted a white province over the top of them.

The wash had never been on the page. Three palettes that differ only in the
wash rendered byte-identically apart from the hex in their stylesheet, and a
fourth would have too.

Rendering the SVG standalone found a second one immediately: `water_svg` and
`cities_svg` are shared with the ecoregion maps and emit `ecomap-*` classes,
styled in `html/site/site.css`. The range map's inline `<style>` did not carry
them, so every lake drew **black** (SVG's default fill) and every river drew
nothing (`<polyline fill="none">` with no stroke rule) — in a module whose
docstring calls its output *"one self-contained ``<svg>`` string"*. The `water`,
`river` and `city` entries in all three palettes had never been applied to
anything. They were prose in a table.

**The scar.** Both are pure *paint order and applied colour*. Nothing raises,
nothing parses wrong, the SVG is well-formed, and the module was well
documented. `range_map.py` shipped with **no test file and no caller** — it
existed to produce PNGs to email to the author — so the only check it ever got
was somebody looking at the picture, and V2.79 recorded that looking at the
picture was the one thing it could not do.

The fix was one CSS class. It cost an increment because the wrong cause was
written down confidently, in a plan, twice.

**Rules:**

1. **A renderer with no test asserts nothing.** `tests/test_range_map.py` now
   checks byte offsets: no filled province polygon may appear after the last
   range cell, and the palettes must produce distinct output. Both fail against
   the old renderer. A test that only proves the SVG parses would have passed
   through every version of this bug.
2. **Render it and look at it, in the session.** The container's headless
   Chromium screenshots an SVG in one command
   (`chrome --headless --no-sandbox --screenshot=out.png file://…`), and Claude
   can read the PNG. Three renders found both faults in about a minute. "Could
   not be verified here — renders were sent to the author" was true of the
   whole V2.75-V2.79 line of work and was never quite true.
3. **A palette entry nothing applies is not a decision, it is a comment.**
   Assert that every key in a palette table reaches the output. Three releases
   of colour choices were being made about water that was rendering black.
4. **Suspect the confident diagnosis in a handover.** It is the part a fresh
   session is likeliest to adopt without re-deriving, and correct-looking
   arithmetic about the wrong layer is indistinguishable from a root cause
   until you look.

## 22. The fixture agreed with the parser (V2.80)

**What happened.** V2.79 built a Darwin Core Archive reader for VASCAN and,
unable to reach `data.canadensys.net`, verified it against a **synthetic
archive it also wrote**. The plan said so honestly: *"tested against a synthetic
archive and has never met the real one."*

The author downloaded the real archive and it was refused outright:

```
the distribution file has no taxonID column; header was
['id', 'locationID', 'locality', 'countryCode', ...]
```

`distribution.txt` is a Darwin Core *extension*, and an extension joins on the
column `meta.xml` declares as `<coreid>` — `id` — rather than repeating
`taxonID`. The synthetic archive had written `taxonID` in both files. **The
fixture and the parser shared one assumption, so the tests could only ever
confirm it.** Nine tests passed against a reader that could not open the file
it exists to read.

A second bug survived the same way. `_canonical` reduces a name to its first
two words, and VASCAN files a hybrid formula at rank *species* — so
`Chamaenerion angustifolium` and `C. angustifolium subsp. angustifolium ×
C. latifolium` scored identically, and the winner was **dict iteration order**.
The hybrid won, the roll-up began at a nothotaxon with no children, and
fireweed was published as unrecorded in Alberta while two AB/SK/MB-native
subspecies hung off the real species, unvisited. No synthetic fixture contained
a hybrid, because nobody writing one thinks to.

**The scar.** Both bugs were invisible to a green suite, and the second was
invisible even to the *real* run — it produced a plausible answer, not an
error. What found it was a diagnostic (`--explain`) that printed the archive's
own rows, and the person who knew fireweed grows in Alberta.

Then the fix's own regression test **passed without the fix**: the plant's name
happened to be shorter than the hybrid's, so an unrelated length tiebreak
carried it and the new rule was doing nothing.

**Rules:**

1. **A fixture you wrote cannot test an assumption you made.** When the real
   input is unreachable, the fixture's *shape* is the thing least likely to be
   right, and it is the thing under test. Build fixtures from a real header,
   real names and real ids the moment any arrive — the tests here now carry
   VASCAN's eight-column header verbatim, trailing columns included.
2. **Always break the fix and watch the test fail.** Twice in this increment a
   new test passed against the unfixed code, for an incidental reason. A test
   written after a fix is a hypothesis until it has been seen to fail.
3. **Ship the diagnostic, not just the fix.** `--explain` cost twenty minutes,
   found the cause in one run, and is what the next unexplainable species will
   be pointed at. Where the failure is a *plausible answer* rather than an
   error, a way to print the intermediate state is the only tool that works.
4. **Sort keys need a total order.** Ties broken by dict iteration are a bug
   that changes between runs, between Python versions, and between the machine
   that reproduces it and the one that does not.
5. **An empty result should say which kind of empty it is.** "No descendants
   found" and "descendants found, none carrying a row" have different fixes,
   and a diagnostic that cannot tell them apart sends the reader looking in the
   wrong place.

## 23. `cd` and then `rm -rf .git` (V2.81)

**What happened.** The publish recipe in `docs/PUBLISHING_THE_SITE.md` read
`cd public`, then `rm -rf .git`, `git init -b gh-pages`, `git push -f origin
gh-pages`. Run as a sequence of separate shell invocations, the working
directory returned to the repository root between two of them. The `rm -rf
.git` then **destroyed the repository's entire history**, `git init` replaced
it with an empty `gh-pages` branch containing the source tree, and the
force-push **published 887 source files as the website**.

**Why it was recoverable, and what that turned on.** Every commit had already
been pushed to `origin/V2.80`, so `git fetch` + `git checkout -B V2.80
origin/V2.80` restored the history exactly, and the site was rebuilt from the
committed catalogue in ten minutes. **Push before you do anything destructive**
is what made a catastrophe into twenty minutes; nothing else in the recovery
was clever.

**The trap is not `rm -rf`.** It is a command whose blast radius depends on a
`cd` that ran in a different invocation. `rm -rf .git` is harmless in
`public/` and unrecoverable one directory up, and nothing about the command
says which one it is in.

**The fix.** Never let a destructive command inherit its directory. Name the
directory on the command itself:

```bash
git -C public init -b gh-pages      # not: cd public && git init -b gh-pages
rm -rf /abs/path/public             # not: rm -rf public
```

And check the target is what you think before publishing it:

```bash
ls public/index.html public/CNAME && ! test -d public/src && echo "this is a site"
```

**The related near-miss in the same incident.** The fresh `git init` had no
`remote.origin.tagOpt = --no-tags`, so the recovery fetch dragged in all ~102
release tags and recreated the V-branch/tag collision CLAUDE.md warns about.
Cleared with the documented `git tag -d $(git tag)`, but a clone that starts
from scratch starts with that trap re-armed.

## The meta-lessons

1. **Silence is the enemy.** Nearly every entry above failed *silently*:
   graceful fallbacks masking cert failures, reseeds that never fired,
   shims failing only at click time, tests collecting zero cases. When
   you build a degradation path, also build the thing that makes its
   activation visible (a `source` label, a warning, a guard test).
2. **Enforce by machinery, not memory.** Every rule that survived is a
   hook, a grep-guard, or a contract snapshot. If your change creates a
   new invariant, ship the guard with it — that's how this ledger stops
   growing.
3. **When a guard blocks you, the guard is usually right.** The
   sanctioned escapes are documented per-guard in `testing`'s catalogue;
   deleting or loosening a guard requires knowing which incident above
   it answers to.
4. **Add to this ledger.** When something painful happens, append the
   entry (what/why/scar/rule) in the same commit as the fix — while it
   still hurts. That is the whole point of this file.

## Validation

This skill is a ledger, not a procedure — but its claims are executable:

```bash
python3 -m unittest tests.test_imports_resolved tests.test_controller_shims \
  tests.test_resource_path tests.test_project_store tests.test_uses_junction \
  tests.test_philosophy tests.test_skill_library -v
```
