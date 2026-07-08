---
name: testing
description: Use when running the test suite, writing a new test, or when a guard test tripped and you need to know whether to fix your code or update a snapshot. Covers the stdlib-unittest invocations (full suite and single module), the temp-DB redirection template, offscreen-Qt and optional-dependency skips, and a catalogue of every guard test with the correct response when it fails.
---

# Testing

The suite is **stdlib `unittest` only** — there is no `pytest` config. Every
test module redirects the DB to a `tempfile.mkdtemp` directory, so tests
never touch the real user DB.

## Running

```bash
# Full suite (from the repo root)
python3 -m unittest discover -s tests

# One module
python3 -m unittest tests.test_project_store -v

# One class or one test
python3 -m unittest tests.test_architecture_guard.TestAgentApiContract -v
python3 -m unittest tests.test_philosophy.TestBranding.test_app_name_is_site_and_pattern -v
```

### What the full suite actually does here (observed)

- **Exit 0 — it passes.** Observed here: **1598 tests, ~9.5 min
  (575s), 178 skipped**. It's slow because a handful of tests make real
  network calls that wait on their own timeouts against the sandbox proxy —
  budget for it; don't assume it hung.
- The **178 skips are not failures** — they are optional-dependency and Qt
  gates (below), skipping cleanly when a dep is absent. In this container
  `PyQt6`, `shapely`, `numpy`, and `rasterio` are all absent, so every
  Qt-smoke, shapely-geometry, and raster test skips. On a fully-provisioned
  dev machine those run and the skip count drops.
- Because slow network tests dominate wall-clock, during iteration run the
  **specific module(s)** you touched plus the guard tests, and run the full
  suite once before you push.

### Fast, dep-light guard-only pass

These are pure file/AST/DB reads — fast and always runnable here:

```bash
python3 -m unittest tests.test_architecture_guard tests.test_philosophy \
  tests.test_project_store tests.test_imports_resolved \
  tests.test_skill_library -v
```

## The temp-DB pattern (copy-paste template)

Every DB-touching test redirects `src.db.plants` module globals **before**
`init_db()` runs, so nothing hits `~/.local/share/Site & Pattern/`:

```python
import os, sys, tempfile, unittest
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Redirect the DB to a temp dir BEFORE importing anything that opens it.
_TMP_DIR = tempfile.mkdtemp(prefix="permadesign_mytest_")
import src.db.plants as _plants_mod          # noqa: E402
_plants_mod._DATA_DIR = _TMP_DIR
_plants_mod._DB_PATH  = os.path.join(_TMP_DIR, "permadesign_test.db")

from src.db.plants import init_db, get_connection   # noqa: E402

class TestThing(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        init_db()                              # seeds the temp DB once
    # ... tests use get_connection() etc.
```

Copy the header from `tests/test_uses_junction.py` or
`tests/test_polycultures.py` verbatim — the ordering (patch globals, *then*
import the things that open the DB) is load-bearing. `tests/test_polycultures.py`
also asserts the DB never lands inside the source tree; don't defeat that.

## Offscreen Qt tests

Qt-touching tests set the platform to offscreen **before importing Qt**:

```python
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")   # before any Qt import
```

and gate the class on Qt being importable:

```python
@unittest.skipUnless(_qt_available(), "PyQt6 not installed in this env")
class TestAppSmoke(unittest.TestCase):
    ...
```

See `tests/test_app_smoke.py` and `tests/test_plant_panel_smoke.py`. When
PyQt6 *is* installed, run a Qt smoke test with:

```bash
QT_QPA_PLATFORM=offscreen python3 -m unittest tests.test_app_smoke -v
```

Optional-dependency gates follow the same shape with a module capability
flag, e.g. `@unittest.skipUnless(sg._HAVE_SHAPELY, "shapely not installed")`
in `tests/test_shadow_geometry.py`.

## Conventions for new tests

- One file per subsystem, named `tests/test_<subsystem>.py`; mirror the
  temp-DB header if it reads the DB.
- Prefer Qt-free assertions on core logic; reserve offscreen-Qt tests for
  widget wiring you can't check any other way.
- If your change adds a table/column or seed rows, the test belongs
  alongside a `_SCHEMA_VERSION` bump — see the `schema-change` skill.
- If your change edits `data/*.json`, add/extend a `data_quality` check —
  see `seed-data`.

## Guard-test catalogue — what trips and the correct response

Guard tests encode institutional decisions. When one fails, the default is
**fix your code**; only occasionally is the right move a *deliberate* edit
to the snapshot the test defends.

| Guard test | Protects | When it fails, you… |
|---|---|---|
| `tests/test_architecture_guard.py` `TestStructuralCeilings` | Per-file line ceilings + MainWindow method cap (decomposition won't backslide) | …**extract** the new logic into a module/controller. Don't just raise the ceiling — see `add-feature`. Raise it only with a written reason, as prior bumps did. |
| `tests/test_architecture_guard.py` `TestAgentApiContract` | The frozen scripting/MCP surface (`EXPECTED_*` maps) | …if the API change was intended, **deliberately** update the map; if not, you broke the surface — revert. See `agent-api`. |
| `tests/test_architecture_guard.py` `TestAnalysisPanelTabsRegistered` | Every `_build_*_tab` actually calls `addTab` (a real regression where a tab vanished) | …make your `_build_*_tab` register its tab; don't move `addTab` into a setter. |
| `tests/test_philosophy.py` | Doc documents all 12 themes; every `Design principle P#` anchor names a real principle; app name flows from `src/branding.py` | …fix the anchor/doc/branding. See `philosophy-check`. |
| `tests/test_project_store.py` | Single write path — no direct `_placed_plants` mutation in `src/` | …route the mutation through `ProjectStore`. See `placed-plants`. |
| `tests/test_controller_shims.py` | Controllers stay wired to MainWindow via shims | …keep the shim; put behaviour in the controller/module. |
| `tests/test_imports_resolved.py` | Every `src/` module imports cleanly (catches typos, bad lazy imports) | …fix the import; often a missing optional-dep guard. |
| `tests/test_safety_filters.py` | Plant safety-tag filtering behaves | …fix the data/filter; never weaken a safety filter to pass. |
| `tests/test_resource_path.py` | Frozen-build resource resolution via `resource_path` | …resolve bundled files through `src/resources.py`, not `__file__` joins. |
| `tests/test_skill_library.py` | This skill library (frontmatter, dead paths, index) | …fix the skill: update a moved path, add the missing `SKILL.md`, or list it in `.claude/skills/README.md`. |

## Pitfalls

- **A green suite is necessary but not sufficient** for UI-visible changes —
  many widgets only get an offscreen smoke test, and the map/3D pages aren't
  exercised headlessly at all. See the `verify` skill for the gap.
- **Don't add a real network call to a test.** The slow tests are a known
  tax; new tests must stub the fetch (see `external-data` for how existing
  tests inject a fake `fetch_json`).
- **Patch the DB globals before importing DB-openers**, or your test writes
  to the real user DB.
- Skips are green. If you *want* the Qt/shapely path exercised, install the
  dep locally — don't interpret `s` as broken.

## Key files

| Path | What |
|---|---|
| `tests/test_uses_junction.py` | Cleanest temp-DB header to copy. |
| `tests/test_polycultures.py` | Temp-DB + "DB not in source tree" assertion. |
| `tests/test_app_smoke.py` | Offscreen-Qt MainWindow smoke; `_qt_available()` gate. |
| `tests/test_plant_panel_smoke.py` | Offscreen-Qt widget smoke. |
| `tests/test_architecture_guard.py` | Structural ceilings + frozen API contract. |
| `tests/test_philosophy.py` | Philosophy anchors, themes, branding. |
| `tests/test_project_store.py` | Placed-plant single-write-path guard. |
| `tests/test_skill_library.py` | Skill-library guard. |

## Validation

```bash
python3 -m unittest discover -s tests      # full (slow, ~7min, expect skips, exit 0)
```
