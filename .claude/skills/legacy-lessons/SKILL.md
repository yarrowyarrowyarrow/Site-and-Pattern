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
