---
name: add-feature
description: End-to-end playbook for adding a feature to Site & Pattern. Use when adding a feature, extending MainWindow, adding a menu item, panel tab, overlay, analysis, or background fetch. Covers the philosophy-fit check, the Qt-free core + _flow + widget triad, the controller shim pattern, architecture-guard line/method ceilings (and what to do when one trips), signal/menu wiring from app.py, tests to add, and the docs to update.
---

# Adding a Feature

## Purpose / when to use

Any new user-visible behaviour: a new analysis, overlay, data fetch, panel
section, menu action, import, or generator improvement. The repo enforces its
architecture with tests — a feature built "the obvious PyQt way" (fat method on
MainWindow, logic in a widget) will FAIL the build. Follow this playbook and
the guards work for you instead.

## Step 0 — Philosophy fit (before designing anything)

This app is opinionated. Work that ignores the philosophy is "technically fine
but spiritually off" and tends to get reworked.

1. Skim `docs/DESIGN_PHILOSOPHY.md` — find which of the twelve principles your
   feature serves. If none, question the feature.
2. Check `docs/PHILOSOPHY_ROADMAP.md` — your feature may already exist as an
   F-number (F1–F53) with a thought-through "how I'd build it". Use it.
3. **HARD RULE (P12):** never encode Indigenous ecological knowledge into data,
   recommendations, or UI without documented free, prior, and informed
   consent. If the task drifts that way, stop and raise it with the user.
4. Ship ranges and confidence, not false precision (P9) — e.g.
   `src/chickadee_scenario.py` reports a capacity *range* against a need range.

## The architecture in one picture

```
Qt-free core          orchestration/glue         Qt display
src/<feature>.py  →   src/<feature>_flow.py  →   src/<feature>_widget.py
(pure math, fetch,    (free functions taking     (paints only; zero maths)
 parse, geometry;      `main`; threads; pushes
 injectable fetchers)  results into panels/map)
        ↑ wired together from src/app.py:_connect_signals / _build_menu
```

Exemplar to copy — the wind feature (V1.67/68):

- `src/wind.py` — Qt-free: Open-Meteo fetch (`fetch_historical_wind`), pure
  aggregation (`compute_wind_rose`), DB-cached `get_wind_summary(…, _fetcher=…)`
  with an injectable fetcher, and `wind_rose_geometry` which pre-computes
  wedges **so the widget stays dumb**.
- `src/wind_flow.py` — free functions taking `main`: `fetch_wind_for_site`
  spins a `QThread` + worker, applies results to `main.analysis_panel`,
  persists to `site_config`, falls back to `data/wind_fallback_prairie.json`
  offline. Note the `_HAVE_QT` guard so the module still imports Qt-free.
- `src/wind_rose_widget.py` — 69-line QPainter widget; `set_block(dict)` +
  `paintEvent`. No network, no math beyond bearing→angle.
- Wiring in `src/app.py` `_connect_signals`:
  `self.analysis_panel.wind_data_requested.connect(self._map_events._on_fetch_wind_requested)`
  — and that controller method is 2 lines: import `wind_flow`, delegate.
- JS-overlay variant: `src/wind_shadow.py` (shapely geometry, Qt-free) +
  `src/wind_shadow_flow.py` (pushes casters/angle to the map; live scrub is
  JS-only, Python recomputes the authoritative merge on commit) — wired from
  `app.py` **straight to the flow via lambdas** because both MainWindow and
  `src/controllers/map_events.py` are at their guard ceilings.
- Tests: `tests/test_wind.py` (temp-DB + monkeypatched `wind._http_get_json`),
  `tests/test_wind_shadow.py`.

## The procedure

1. **Branch**: work happens on the next `V<major>.<minor>` branch
   (`.claude/hooks/branch_policy.py` auto-enforces; current is V2.19). Never
   `claude/*` branches.
2. **Philosophy fit** (Step 0 above). Note the principle number(s).
3. **Write the Qt-free core** `src/<feature>.py`. Rules:
   - No `PyQt6` import. Network via `src/http_utils.py:http_get_json`, always
     returning `None` on failure (network-graceful, never raising into the UI).
   - Make external effects injectable (`_fetcher=…` parameter) for tests.
   - Cache expensive fetches in the DB (see `wind_cache` usage in
     `src/wind.py`) or fall back to a bundled `data/*fallback*.json`.
   - If strongly aligned with a principle, put the anchor in the module
     docstring: `Design principle P# — see docs/DESIGN_PHILOSOPHY.md`
     (`tests/test_philosophy.py` validates the number is 1–12).
4. **Write the flow module** `src/<feature>_flow.py` if the feature touches
   MainWindow state, threads, or multiple widgets. Free functions taking
   `main` as first arg. Off-thread work = `QThread` + worker object with a
   `done` signal (copy `src/wind_flow.py:_WindFetchWorker` verbatim, including
   the deleteLater/quit cleanup and holding `main._<x>_thread` refs so the
   thread isn't GC'd mid-flight).
5. **Write the widget/UI**, if any: a paint-only widget module, a new sub-tab
   on an existing panel (panels emit signals; they never reach into `main`),
   or a self-managing `src/<feature>_window.py` opened from the menu via
   lambda.
6. **Wire it from `src/app.py`** (see next section). Prefer, in order:
   lambda → flow function; signal → existing controller method; only lastly a
   new MainWindow shim (the method ceiling is FULL — see Pitfalls).
7. **Feature mutates `project["features"]`?** Route placed-plant writes
   through `src/project_store.py` (see the `placed-plants` skill) and decorate
   the mutating handler with `@undoable("label")` from
   `src/controllers/undo_support.py` — that alone makes it undoable.
8. **Tests** (stdlib `unittest`, no pytest):
   - Core: pure unit tests, temp-DB pattern if it touches the DB
     (redirect `src.db.plants._DATA_DIR`/`_DB_PATH` **before** importing
     consumers — copy the header of `tests/test_wind.py`).
   - If you added a MainWindow shim: nothing to do —
     `tests/test_controller_shims.py` statically checks every
     `self._<controller>.<method>()` in `MainWindow` resolves to a real
     controller method.
   - Qt widgets: AST-level or smoke tests that skip headless (pattern in
     `tests/test_app_smoke.py`).
9. **Docs**: mark the F-number **✅ Shipped** in `docs/PHILOSOPHY_ROADMAP.md`
   ("Shipped since this roadmap was written" section is the record), and
   upgrade the principle's **State** marker in `docs/DESIGN_PHILOSOPHY.md` if
   your feature genuinely moved it (gap → partial → strong). Keep these honest
   — an inflated State marker is worse than none.
10. **Validate** (see Validation) and run the app end-to-end before declaring
    done.

## Wiring from app.py

- **Menu**: add to `MainWindow._build_menu`. For self-managing windows use a
  lambda, not a method — existing comment in `src/app.py`: *"Lambda (not a
  MainWindow method) on purpose: the window manages itself in
  src/scene3d_window.py and the architecture guard's method ceiling"*.
- **Signals**: add to `MainWindow._connect_signals`. Three sanctioned shapes,
  all present around the wind wiring in `src/app.py`:
  1. panel signal → existing controller method:
     `…wind_data_requested.connect(self._map_events._on_fetch_wind_requested)`
  2. panel signal → lambda → flow function:
     `…wind_angle_changed_live.connect(lambda d: wind_shadow_flow.on_angle_live(self, d))`
  3. map bridge signal → flow reaction:
     `b.plant_moved.connect(lambda *a: wind_shadow_flow.on_plants_changed(self))`
- **New map JS?** Add the function in the right `html/map/0*.js` file, a typed
  builder in `src/map_js.py`, and a thin method on `src/map_widget.py`. Never
  format JS strings inline elsewhere (see the `map-frontend` skill).

## Architecture-guard ceilings (quote of current state)

From `tests/test_architecture_guard.py` (ceilings set ~15% above the state at
the time; **current** counts move — measure, don't trust comments):

| File | Ceiling | Now (V2.19) | Headroom |
|---|---|---|---|
| `src/app.py` | 2600 lines | 2201 | comfortable |
| `src/plant_panel.py` | 1600 lines | 1467 | ok |
| `src/controllers/map_events.py` | 1950 lines | 1948 | **2 lines** |
| `html/map.html` | 400 lines | 235 | ok |
| `html/map/01-core.js` | 950 | 885 | tight |
| `html/map/02-boundary.js` | 750 | 623 | ok |
| `html/map/03-plants.js` | 950 | 931 | **tight** |
| `html/map/04-tools.js` | 450 | 367 | ok |
| `html/map/05-features.js` | 1100 | 1008 | ok |
| `html/map/06-overlays.js` | 1560 | 1490 | tight |
| `MainWindow` method count | 135 | **135 — FULL** | zero |

**When a ceiling trips: extract, don't raise.** The correct responses:

- MainWindow method ceiling → don't add the method. Use a lambda or wire the
  signal straight to a controller/flow function.
- `map_events.py` line ceiling → new handlers are 2–4 lines delegating to a
  `src/<feature>_flow.py`; or bypass the controller entirely and wire the
  signal to the flow from `app.py`.
- JS file ceiling → is the code really an overlay/tool/etc.? Move
  self-contained subsystems into better-fitting split files, or (rarely) a new
  numbered file added to `html/map.html`'s load order.
- Raising a ceiling is allowed only when the growth is legitimately in-domain
  (the file's own concern grew, not a foreign blob) — do it as a deliberate,
  commented edit to `LINE_CEILINGS`, the way V2.13 did for
  `html/map/06-overlays.js`.

## Pitfalls & gotchas (real ones)

- **`MainWindow` is at exactly 135/135 methods.** Adding ONE method fails
  `tests/test_architecture_guard.py:test_mainwindow_method_ceiling`. This is
  by design — it forces the flow-module pattern. Note the existing trick:
  `_project`/`_placed_plants` are `property(lambda …)` class attributes, not
  `@property` methods, precisely so they don't count.
- **`map_events.py` has ~2 lines of headroom.** A "small" handler there breaks
  the build. Delegate immediately (see `_on_fetch_wind_requested` — 2 lines).
- **Shim typos fail at click-time, not import-time.** That's why
  `tests/test_controller_shims.py` exists (the V1.40 fallout). If you rename a
  controller method, grep `src/app.py` for its shim.
- **Moved constants leave dangling references.** `tests/test_imports_resolved.py`
  catches `_UPPER_CASE` names referenced in function bodies but no longer
  defined/imported — the exact V1.40 `plant_panel` split regression. Run it
  after any move.
- **Qt import in a core module silently breaks headless tests + the agent
  API.** If a flow module must define a QObject worker, guard it like
  `src/wind_flow.py` (`try: from PyQt6… except ImportError`).
- **Workers must be kept referenced** (`main._wind_thread = thread`) and
  cleaned via `thread.finished` → `deleteLater`; otherwise Python GCs the
  QThread mid-run and the app crashes intermittently.
- **`_mark_modified()`** after every project mutation, or Save/autosave and
  the title-bar `*` silently stop reflecting the change.
- **AnalysisPanel tabs:** every `_build_*_tab` must call `addTab` inside
  itself — a misplaced `addTab` once made the Habitat tab vanish; the guard
  (`TestAnalysisPanelTabsRegistered`) now enforces it.
- **Don't hand-edit the docs' State markers casually** —
  `tests/test_philosophy.py` checks structure, but honesty is on you: the doc
  explicitly tracks *strong / partial / gap* per principle.

## Key files

| Path | Why you'll open it |
|---|---|
| `src/app.py` | `_build_menu`, `_connect_signals`, controller construction, shim examples. |
| `src/wind.py` / `src/wind_flow.py` / `src/wind_rose_widget.py` | The canonical triad to copy. |
| `src/wind_shadow.py` / `src/wind_shadow_flow.py` | The JS-overlay + live/commit variant. |
| `src/controllers/undo_support.py` | `@undoable` — one decorator = exhaustive undo. |
| `src/controllers/map_events.py` | Where gesture handlers live (delegate-only now). |
| `tests/test_architecture_guard.py` | The ceilings + frozen API contract. |
| `tests/test_controller_shims.py` | Shim → controller-method resolution guard. |
| `docs/DESIGN_PHILOSOPHY.md` / `docs/PHILOSOPHY_ROADMAP.md` | Principle fit, F-numbers, Shipped ledger. |

## Validation

```bash
# The guards your feature is most likely to trip:
python -m unittest tests.test_architecture_guard tests.test_controller_shims tests.test_philosophy -v

# If you touched placed-plant state:
python -m unittest tests.test_project_store -v

# Full suite (what CI runs; Qt tests self-skip headless):
python -m unittest discover -s tests
```

All must pass with `OK`. Then actually run the feature (GUI or via the
headless facade — see the `agent-api` skill for driving features without a
display) before calling it shipped.
