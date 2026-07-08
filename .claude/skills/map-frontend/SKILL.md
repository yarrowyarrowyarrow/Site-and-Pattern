---
name: map-frontend
description: Use when editing the Leaflet map, html/map JS, overlays, map modes/tools, src/map_widget.py, src/map_js.py, or src/controllers/map_events.py. Covers the V1.64 six-file classic-script split (shared globals, load order), the QWebChannel Python↔JS bridge in both directions, the contract tests that pin it, the wind-shadow worked exemplar for adding an overlay, JS line ceilings, and how to see JS console output / renderer crashes.
---

# Map frontend — Leaflet inside QWebEngineView

## Purpose / when to use

The 2D map is a Leaflet page (`html/map.html` + `html/map/*.js`) embedded in
`src/map_widget.py:MapWidget` (a `QWebEngineView`). Use this skill whenever you:

- add/change a map overlay, drawing mode, marker behaviour, or layer toggle;
- add a new Python→JS call or a new JS→Python event;
- touch `src/map_js.py`, `src/map_widget.py`, `src/controllers/map_events.py`,
  or any `html/map/*.js` file;
- debug "the map is blank / frozen / nothing happens and no errors print".

## Architecture in one page

```
Python                                              JavaScript (embedded Chromium)
──────                                              ──────────────────────────────
src/app.py            calls MapWidget methods       html/map.html  (shell: CSS, legend,
  │                                                   <script> tags = LOAD ORDER)
  ▼                                                 html/map/01-core.js … 06-overlays.js
src/map_widget.py     MapWidget.<method>()            (six CLASSIC scripts, shared globals)
  │  builds JS via                                          ▲
  ▼                                                         │ page().runJavaScript(js)
src/map_js.py         typed string builders  ───────────────┘
                      (json.dumps escaping — the ONLY place JS strings are assembled)

JS gesture (click/drag/draw)
  │  bridge.onPlantMoved(...)          ← `bridge` = QWebChannel proxy of MapBridge
  ▼
src/map_widget.py     MapBridge @pyqtSlot onPlantMoved → emits pyqtSignal plant_moved
  ▼
src/app.py            _connect_signals(): b.plant_moved.connect(self._on_plant_moved)
  ▼
src/controllers/map_events.py   MapEventRouter._on_plant_moved  (mutates project,
                                @undoable checkpoints, marks modified)
```

Both directions are **contract-tested** (see below). The bridge is QWebChannel —
not polling, not custom URL schemes: `MapWidget.__init__` registers `MapBridge`
as object `"bridge"` on a `QWebChannel`; the page loads
`qrc:///qtwebchannel/qwebchannel.js` and `initChannel()` (bottom of
`html/map/06-overlays.js`, run on `window.load`) resolves
`bridge = channel.objects.bridge`, calls `initMap()` (defined in
`html/map/01-core.js`), then `bridge.onMapReady()` → the `map_ready` signal.
`initChannel` also has a no-QWebChannel fallback so the page opens in a plain
browser for dev — keep new bootstrap code inside that pattern.

## The V1.64 split — six SEQUENTIAL CLASSIC scripts, not ES modules

`html/map.html` was a 4,900-line monolith; V1.64 split its single `<script>`
into six files loaded **in order** at the bottom of `html/map.html`:

```html
<script src="map/01-core.js"></script>
<script src="map/02-boundary.js"></script>
<script src="map/03-plants.js"></script>
<script src="map/04-tools.js"></script>
<script src="map/05-features.js"></script>
<script src="map/06-overlays.js"></script>
```

That block **is** the load-order definition. Rules that follow from it:

- These are classic scripts sharing one global scope. ES modules cannot load
  from `file://` in Chromium without CORS flags, so **do not** convert them to
  modules or add `type="module"`. (The 3D viewer is the module app; it gets a
  localhost server for exactly this reason — see `src/web_assets.py`.)
- `var` declarations and top-level statements execute in file order. A
  *function call* can reference a function defined in a later file (resolved at
  call time), but top-level code must only touch state declared in the same or
  an earlier file. State lives in `01-core.js`; behaviour that runs at load
  time lives in `06-overlays.js` (`initChannel`).
- Don't shadow an existing global with `let`/`const` — a duplicate `let` of an
  existing `var` name throws at parse time and kills every later script.
- A new `html/map/<NN-name>.js` file needs a `<script>` tag added to
  `html/map.html` in position. The contract tests glob `html/map/*.js` so they
  pick it up automatically; the line-ceiling guard does **not** — add the new
  file to `LINE_CEILINGS` in `tests/test_architecture_guard.py`.

### Which file owns what

| File | Owns |
|------|------|
| `html/map/01-core.js` | All shared state (`map`, `plantMarkers`, `boundaries`, `currentMode`, `bridge`, …), unified selection model + marquee, `initMap`, map click routing, context menu, `deleteSelected` |
| `html/map/02-boundary.js` | Boundary draw/edit (vertex + bbox-scale handles), length/area labels, footprint-outline editing |
| `html/map/03-plants.js` | `escH()` HTML-escape guard, plant markers (`placePlantMarker`/`loadPlantMarker`), drag-to-reposition + drag-scope cycling, pattern placement (row/grid/circle), `plantLabels` |
| `html/map/04-tools.js` | Canvas renderer, geometry utils, snap-to-grid, canopy preview, growth timeline (`setTimelineYearByPlantId`), season view, measurement, annotations |
| `html/map/05-features.js` | Structures, hedgerows, custom shapes, `setMode` (mode control), satellite alignment (`initMapboxLayer`), layer visibility, project load/`clearAll`, zoom |
| `html/map/06-overlays.js` | Sun path, sectors, contours/terrain, shade/slope/water/splat/site-photo image overlays, wind + wind shadow + snow catch, legend, site pin, **QWebChannel bootstrap** |

## Bridge: Python → JS

1. **Never** assemble JS in an f-string at a call site. Add a builder function
   to `src/map_js.py` returning the JS string; strings/dicts go through
   `json.dumps` (`_jsstr`/`_jslit`) or `_jsobj` (double-encoded
   `JSON.parse("...")` — robust to quotes in plant names).
2. Add a thin wrapper method on `MapWidget` (`src/map_widget.py`) that calls
   `self.run_js(map_js.your_builder(...))`. Keep the "new typed methods"
   section of `MapWidget` alphabetical (the file asks for it — audit greps rely
   on it).
3. Define the JS function in the owning `html/map/*.js` file.
4. Add builder unit tests in `tests/test_map_js.py` AND add the JS function
   name to `TestJsEntryPointsExist.JS_NAMES` there — that test walks
   `html/map.html` + every `html/map/*.js` and fails if a name the builders
   emit has no JS definition (rename tripwire).

Gotchas encoded in existing builders — copy them, don't reinvent:

- Python `True` must land as JS `true` (`_jsbool`); a raw `True` in the page is
  a `ReferenceError` that silently kills the statement.
- `loadBoundary` takes a JSON **string** (single-encoded) plus a `fit` flag;
  most other payload entry points take an object via `_jsobj`.
- A few builders are inline IIFEs over globals (`undo_place_plant`,
  `restore_contour`) — acceptable, but they're pinned by tests too.
- `map_js.invalidate_size()` and `MapWidget.invalidate_size`/`resizeEvent`
  are **load-bearing**: the `console.log(...clientWidth...)` reads force
  Chromium layout reflows and the `_dbg()` file writes yield to the OS
  scheduler. Removing them reintroduces the Windows maximise-with-contours
  freeze. `tests/test_map_js.py:TestInvalidateSize` pins this. Do not "clean up".

## Bridge: JS → Python

1. In JS, call `bridge.onYourEvent(args…)` — always guard with
   `if (bridge && bridge.onYourEvent)` when the call can fire before
   `initChannel` completes.
2. Add a `@pyqtSlot(...)` method `onYourEvent` on `MapBridge`
   (`src/map_widget.py`) that re-emits a `pyqtSignal`. QWebChannel slot args
   are positional scalars (float/int/str/bool); anything structured crosses as
   a **JSON string** the slot parses (see `onBoundaryComplete`,
   `onPlantsRemovedBatch`) — lists/dicts do not marshal reliably otherwise.
3. Connect the signal in `src/app.py:_connect_signals` — either straight to a
   `MapEventRouter` handler (`self._map_events._on_…`) or to a one-line
   MainWindow shim that delegates (both patterns exist; new handlers go **in
   the controller**, never as fat MainWindow methods — the method/line
   ceilings in `tests/test_architecture_guard.py` enforce this).
4. Write the handler in `src/controllers/map_events.py:MapEventRouter`.
   Decorate any handler that mutates `project["features"]` with
   `@undoable("label")` (`src/controllers/undo_support.py`) so it becomes one
   undo step for free.
5. `tests/test_bridge_contract.py:TestJsToPythonBridge` scrapes every
   `bridge.<name>(` call across `html/map.html` + `html/map/*.js` and fails if
   it doesn't resolve to a `MapBridge` method — a renamed slot otherwise fails
   *silently* inside the page at runtime. Run it after any bridge change.

**Placed-plant state has ONE write path**: handlers touching plant features go
through `src/project_store.py` (`store_for(...)`) — `tests/test_project_store.py`
greps `src/` and fails the build on new direct `_placed_plants` mutation.

## Worked exemplar: the V1.68 wind-shadow overlay

The dynamic wind shadow is the reference implementation for "live JS ghost +
authoritative Python geometry". Read these five pieces together before adding
any interactive overlay:

1. **JS layer** — `html/map/06-overlays.js`, "Dynamic wind shadow (V1.68)"
   section: two layers (`windGhostLayer` per-plant wedges redrawn every dial
   tick in pure JS; `windShadowLayer` the merged result Python pushes on
   commit), state (`_windCasters`, `_windAngle`, `_windShadowOn`), and entry
   points `setWindCasters` / `setWindAngleLive` / `drawMergedWindShelter` /
   `setWindShadowVisible` / `clearWindShadow`. The JS wedge math deliberately
   mirrors `src/wind_shadow.py` so ghost ≈ merged.
2. **Builders** — `src/map_js.py` (`set_wind_casters`, `set_wind_angle_live`,
   `draw_merged_wind_shelter`, …) + thin `MapWidget` methods.
3. **Qt-free geometry** — `src/wind_shadow.py` (`merged_shelter`,
   `casters_from_project`) computes the authoritative shapely-merged bands.
4. **Flow module** — `src/wind_shadow_flow.py`: free functions taking `main`
   (`enable`, `on_angle_live`, `on_angle_commit`, `on_plants_changed`,
   `recompute_merged`). It exists *because* `MainWindow` and
   `MapEventRouter` are at their guard ceilings — wiring goes from `src/app.py`
   straight to these functions via lambdas. Copy this pattern when the
   controller has no headroom.
5. **Tests** — `tests/test_wind_shadow.py` (geometry),
   `tests/test_map_js.py:TestWindShadowBuilders` (builders).

Key judgment split: **interaction-rate updates stay in JS** (no Python
round-trip per drag frame — push data once via `setWindCasters`, re-orient in
JS); **authoritative geometry is Python-computed on commit** (dial release,
plant placed/moved). Follow the same split for anything drag- or slider-driven.

## Adding a simple image/vector overlay (non-interactive)

Mirror the shade overlay: builder `draw_shade_overlay` + `set_…_opacity` +
`clear_…` in `src/map_js.py`; JS `drawShadeOverlay` in `html/map/06-overlays.js`
holds one `L.imageOverlay`/`L.layerGroup` global, replaces on redraw; a View
toggle wired in `src/app.py`. Vector overlays take `[[lat, lng], …]` ring lists
(see `drawShadowPolygons`); rasters take `{image: dataURL, bbox, opacity}`.
Give each overlay its **own** layer global so overlays compose instead of
replacing each other.

## Line ceilings — extract, don't grow

`tests/test_architecture_guard.py:TestStructuralCeilings.LINE_CEILINGS` caps
(current ceilings): `src/app.py` 2600, `src/plant_panel.py` 1600,
`src/controllers/map_events.py` 1950, `html/map.html` 400,
`01-core.js` 950, `02-boundary.js` 750, `03-plants.js` 950, `04-tools.js` 450,
`05-features.js` 1100, `06-overlays.js` 1560. `MainWindow` is also capped at
135 methods. When your change would trip one:

- Python: put behaviour in a new/existing flow module (the
  `src/wind_shadow_flow.py` pattern) or controller, wired from `app.py`.
- JS: extract a new numbered file (add its `<script>` tag + a ceiling entry)
  rather than raising an existing ceiling. Raising a ceiling is a deliberate,
  reviewed act with a comment explaining why — never a drive-by +200.

## Debugging the embedded page

- **JS console output**: `_LoggingPage` in `src/map_widget.py` forwards every
  `console.*` and uncaught error. JS **errors** go to stderr; info/warn go
  file-only to `~/site-and-pattern-debug.log` (via `_dbg`). If "nothing
  happens", tail that log — a JS exception aborts the rest of the statement
  batch silently otherwise.
- **Renderer crashes**: `MapWidget._on_render_terminated` prints
  `*** RENDER PROCESS TERMINATED ***` to stderr when Chromium's render process
  dies (blank map, dead controls, no JS errors). Grep for it.
- **Blank/half-painted map after resize**: call `MapWidget.invalidate_size()`;
  see the load-bearing block comment above it before touching anything there.
- **Bridge silence**: a JS call to a misnamed `bridge.onFoo` fails without a
  trace — `python -m unittest tests.test_bridge_contract` catches it statically.
- The page loads Leaflet/leaflet-draw from unpkg CDN and tiles from the
  network; `LocalContentCanAccessRemoteUrls` is enabled for that. Offline, the
  map page itself won't fully boot — don't mistake that for your bug.

## Pitfalls & gotchas (real ones)

- **XSS guard**: every user/file-sourced string concatenated into Leaflet
  `html:`/`bindTooltip`/`setContent` must pass through `escH()`
  (`html/map/03-plants.js`). Project files are untrusted input.
- `clearAll()` (JS) does **not** clear annotations — the whole-project
  re-render calls `clearAnnotations()` explicitly. Match that if you add a new
  persistent marker family.
- Marker-matching IIFEs compare coordinates with `1e-7` tolerance
  (`undo_place_plant`, `revert_plant_position`) — don't round lat/lng before
  sending or undo stops finding markers.
- `set_structures_visible` has **no** JS function; the builder inlines loops
  over three globals. Check `src/map_js.py` before assuming a JS name exists.
- The map stores only `(lat, lng)`; all metre math belongs in Python via
  `src/projection.py` (see the `geo-projection` skill). JS-side metric math
  that must exist (wind ghost, measurement) uses the same
  `111320 · cos(lat)` model — keep constants in sync with the Python twin.
- Mode changes go through `setMode` in `html/map/05-features.js`; payload-
  carrying modes use `map_js.set_mode_with_payload`. New modes must handle
  `cancelDraw()` and reset `currentMode`.
- `tests/test_map_features.py` is **pytest-style bare functions** with a
  self-runner — `python -m unittest tests.test_map_features` collects 0 tests.
  Run it as a script (below).

## Validation

Run from the repo root (stdlib unittest only — no pytest in this repo):

```bash
python -m unittest tests.test_map_js tests.test_bridge_contract -v   # bridge contract, both directions
python -m unittest tests.test_architecture_guard                     # line/method ceilings
python tests/test_map_features.py                                    # JS-mirror geometry (script-style runner)
python -m unittest tests.test_wind_shadow                            # if you touched the wind-shadow exemplar
python -m unittest discover -s tests                                 # full suite before finishing
```

All of the above pass headlessly (Qt-dependent tests self-skip). After any JS
edit also do a real smoke test if a display is available: `python main.py`,
draw a boundary, place a plant, toggle the overlay you touched, and tail
`~/site-and-pattern-debug.log` for `[js:ERROR]` lines.
