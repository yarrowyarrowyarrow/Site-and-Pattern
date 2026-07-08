---
name: scene-3d
description: Use when working on the 3D preview, Scene JSON, html/scene3d.html, src/scene_contract.py, src/map3d_widget.py, src/map3d_js.py, sprites, the Gaussian-splat photoreal backdrop, or phone-scan import. Covers the versioned project→3D contract (build_scene), the built-in three.js viewer vs the web3d/dist fork, window.perma* hook mechanics and their contract test, the splat file→matrix→footprint→Spark→2D-bake pipeline, and what to test when touching any of it.
---

# The 2D→3D pipeline (View → 3D Preview)

## Purpose / when to use

Everything between the project dict and pixels in the 3D window. Use this
skill when you: add a field to the Scene JSON, change plant/building/terrain
rendering, touch the splat backdrop or scan import, add a `window.perma*`
hook, or edit `html/scene3d.html`.

## Architecture in one page

```
project dict (GeoJSON FeatureCollection)
  │
  ▼
src/scene_contract.py   build_scene(project, year=, when=, elevation=, scan=, splat=)
  │                     → Scene JSON (SCENE_VERSION = 1, local metres,
  │                       +x east / +y north, origin = design centroid)
  ▼
src/scene3d_window.py   Scene3DWindow._push_scene()  (year/month/hour sliders,
  │                     off-thread terrain fetch, wildlife push)
  ▼
src/map3d_widget.py     Map3DWidget.apply_scene(scene)  →  run_js(...)
  │                     (queues JS until loadFinished; splat path → localhost URL)
  ▼
src/map3d_js.py         builders emit "window.permaX && window.permaX(json)"
  │
  ▼
html/scene3d.html       built-in three.js viewer (ES modules + importmap,
                        vendored three.js + Spark in html/vendor/, served over
                        http://127.0.0.1 by src/web_assets.py)
        — OR —
web3d/dist/<index.html> optional map3d fork build (city context; see web3d/README.md)
```

Nothing renders until Python pushes a scene: every hook is registered by the
page and every builder is `&&`-guarded, so a push before load is a silent
no-op — which is why `Map3DWidget.run_js` queues JS until `loadFinished` and
replays it.

## The Scene JSON — the versioned project→3D contract

`src/scene_contract.py:build_scene` is **one pure function** (Qt-free,
DB-free — `get_plant` injectable) producing the renderer-agnostic scene. The
full schema lives in its module docstring; the shape:

`version, year, month, origin{lat,lng}, bounds, boundary, plants[],
buildings[] (kind: building|canopy), structures[], terrain|None,
scan_points|None, splat{path,matrix,opacity}|None, sun|None, is_night`.

Rules of the contract:

- **Coordinates are local metres** about the origin (+x east, +y north).
  The viewer remaps to three.js Y-up: `x_east → +x`, `y_north → −z`,
  `height → +y` (documented in the `html/scene3d.html` header). Never put
  lat/lng in a scene field — re-frame via `src/projection.py` first.
- **Plant sizing/presence comes from `src/scene3d.py`**
  (`plant_3d_state` ← `growth_scale_factor` / `spread_scale_factor` /
  `spread_aggressiveness`), the *same* module the 2D growth timeline uses —
  the two views agree by construction. Never compute growth in the window or
  the viewer. `tests/test_scene3d.py` pins the formulas;
  `tests/test_scene_contract.py:test_plants_match_scene3d_growth` pins the
  wiring.
- **Versioning judgment**: `SCENE_VERSION` is 1. *Additive* fields (a new key
  the viewer feature-checks) do NOT bump it — that's how `genus`,
  `flower_form`, `fruit_color`, `is_night` etc. landed. Bump only when the
  meaning/units/frame of an *existing* field changes so an old viewer would
  misrender. Either way: update the docstring schema, add a case to
  `tests/test_scene_contract.py`, and keep the scene `json.dumps`-able
  (`test_version_and_serialisable` enforces plain data).
- `year=0` means **mature reference** (full size), not "just planted" —
  `growth_scale_factor(0, …) == 1.0`. Off-by-one thinking here breaks the
  timeline slider.
- Scene bounds floor at ±25 m so near-empty designs still get a stage
  (`src/sprite_gallery.py` deliberately fights this for single specimens).

## Viewer selection: built-in vs fork

`src/map3d_widget.py:Map3DWidget.__init__` picks at construction:

1. a built `web3d/<dist/index.html>` exists → the **map3d fork** build, loaded
   via `file://` (self-contained classic bundle). That `dist/` output under
   `web3d/` is **not checked into the repo** — it's produced only when you
   build the optional fork; only `web3d/README.md` and
   `web3d/map3d-sun-shadows.patch` ship. Most installs don't have the fork.
2. else `html/scene3d.html` → the **built-in viewer**, served over a loopback
   HTTP server (`src/web_assets.py:builtin_viewer_url`). It is an ES-module
   app (importmap); `file://` module loading broke on a newer bundled Chromium
   (V1.76), hence the server. three.js + Spark are **vendored** under
   `html/vendor/three` and `html/vendor/spark` — `tests/test_scene3d_assets.py`
   fails the build if a CDN import sneaks back into `html/scene3d.html`.
   (An older comment in `src/map3d_widget.py` still says "fetches from a CDN"
   — the code and the guard test win.)

Both register the shared hooks; only the built-in viewer implements the full
set (`permaSetScene`, wildlife, splat, ortho bake…).

## The `window.perma*` hook mechanic (Python→JS only)

Unlike the 2D map there is **no QWebChannel here** — the 3D bridge is
one-directional: `src/map3d_js.py` builders emit
`window.permaX && window.permaX(<json.dumps payload>);` and
`Map3DWidget.run_js` executes them. Results come back only via
`page().runJavaScript(js, callback)` (see `capture_ortho`).

To add a hook:

1. Builder in `src/map3d_js.py` (json.dumps everything; keep the `&&` guard).
2. Thin `Map3DWidget` method calling `run_js`.
3. Register `window.permaYourHook = function (…) {…}` in `html/scene3d.html`.
4. Run `python -m unittest tests.test_bridge_contract` —
   `TestScene3DHooks` asserts every `window.perma*` named in `src/map3d_js.py`
   is registered by `html/scene3d.html`, **and the reverse**: a
   `window.permaSet*` registered in the viewer that no builder drives fails as
   naming drift. Land builder + registration in the same change.
5. `tests/test_map3d_js.py` unit-tests the builder strings.

`window.permaResetView` is the one hook driven raw (the window's Reset-view
button and the sprite gallery) — it has its own contract test.

## The 3D window (`src/scene3d_window.py`)

`open_3d_view(main)` is the View-menu entry point (singleton on
`main._scene3d_window` — no new MainWindow method; the architecture guard's
method ceiling is why). The window owns **no geometry**: sliders (year 0–25,
month, hour 0–23 — past dusk = moonlit night scene) just call `_push_scene`,
which calls `build_scene` and `viewer.apply_scene`. Terrain arrives
cache-first on a worker QThread (`src/zoning.py:site_elevation_grid`) and the
scene is re-pushed when it lands — never fetch on the UI thread. Each push
also recomputes ambient wildlife (`src/scene_wildlife.py:wildlife_for_scene`
+ `support_by_taxon`) — only creatures with a *documented* plant↔fauna edge to
a present plant are placed (design principle P9: nothing invented).

Sun convention everywhere: azimuth **degrees clockwise from north**, altitude
above horizon; `map3d_js.set_sun_for` applies the same `-lng/15 h` local-solar
shift as the 2D shade engine, so 2D shade and 3D shadows agree by
construction.

## Sprites and the sprite gallery

Plants render as instanced procedural archetypes in `html/scene3d.html`:
genus (from `scientific_name`, sent as `plants[].genus`) selects species
geometry; `flower_form`/`flower_color` + bloom window drive billboard flower
sprites; `fruit_color` + fruit window drive berries. The catalogue with the
builder-function names (`buildConiferGeo`, `generateDaVinciTree`,
`buildShrubGeo`…) is `docs/3D_SPRITES.md` — read it before adding a form.

- `src/sprite_gallery.py:gallery_scenes()` builds one specimen scene per
  archetype/flower form **through the real `build_scene`** — so the gallery
  can never drift from the contract.
- In-app: View → 3D Sprite Gallery (`src/sprite_gallery_window.py`).
- Standalone: `html/sprite_gallery.html` + generated
  `html/sprite_gallery_scenes.json`; regenerate with
  `scripts/make_gallery_scene.py` (and `scripts/render_flower_sprites.py` for
  the docs image) whenever sprite forms or exemplar seed data change.
- `tests/test_sprite_gallery.py` guards the scene set.

## Gaussian-splat photoreal backdrop (V1.65)

Pipeline, end to end — Qt-free core in `src/splat_backdrop.py`, glue in
`src/splat_flow.py`:

1. **Detect**: `src/scan_import.py:is_gaussian_splat_ply` sniffs splat PLYs by
   vertex properties (`f_dc_0`, `scale_0`, `rot_0`). Splat vertices are the
   gaussian centres, so the normal scan georeference applies.
2. **Align**: 2+ control-point pairs ("this scan corner = this map spot") →
   `scan_import.similarity_transform_2d` (Horn least-squares: scale +
   rotation + translation) →
   `splat_backdrop.feature_from_alignment` builds the persisted feature.
3. **Persist**: a `splat_backdrop` GeoJSON feature (`build_feature`): absolute
   `file_path` (the 50–200 MB `.ply` is referenced, never embedded), the
   transform, origin, lat/lng bbox footprint ring, and — once baked — the
   `ortho_png` **data URL embedded** so the 2D layer reloads instantly.
   (`docs/PROJECT_FILE_FORMAT.md` doesn't list this element type yet; the code
   is the source of truth.)
4. **Place in 3D**: `build_scene` auto-detects the feature
   (`feature_from_project`) → `scene_field` → `scene["splat"] =
   {path, matrix, opacity}`. `world_matrix` composes file→three.js as one 4×4
   (**column-major**, ready for `Matrix4.fromArray`; frames F_file→F_zup→
   F_proj→F_scene→F_three are documented in the module docstring).
   `origin_offset` shifts between the stored projector origin and the live
   scene origin — a constant offset between two cosLat frames.
5. **Render**: `Map3DWidget.apply_scene` swaps `path` for a same-origin
   `src/web_assets.py:local_file_url` (`/__localfile` route — only `.ply`
   files are served; a `file://` URL would be a cross-origin fetch the
   `http://` page refuses) and Spark renders it in `html/scene3d.html`.
6. **Bake to 2D**: the window's "Add yard photo to map" button →
   `splat_backdrop.scene_rect` frames the camera →
   `Map3DWidget.capture_ortho` → `map3d_js.capture_ortho` →
   `window.permaCaptureOrtho` returns a PNG data URL to the callback →
   `splat_flow.apply_baked_ortho` stores it on the feature and draws the 2D
   overlay (`MapWidget.draw_splat_ortho_overlay`).
   `splat_flow.restore_splat_overlay` redraws it on project open.

Gotchas: `capture_ortho` bypasses the JS queue — it returns `""` when the
page isn't loaded or the splat is still streaming; `apply_baked_ortho`
rejects non-`data:image` results, so surface the "let it finish loading" retry
message rather than treating it as an error. `scene_field` does **no**
filesystem check (pure contract); missing-file handling is
`apply_scene`'s job (it nulls the splat so the design still renders).

## Phone-scan import (overview)

`src/scan_import.py` (numpy required, shapely for vectorize): `read_points`
(.ply ASCII/binary, .xyz/.txt/.csv, .las/.laz via optional laspy) →
`align_scan` with control points → `rasterize_ndsm` (height-above-ground
grid) → `scan_to_footprints` via `src/footprint_ndsm.py:vectorize_ndsm` →
`src/footprint_extract.py` adds `canopy_footprint` features — at which point
the scanned shed/tree casts 2D shade and extrudes in 3D with **no further
wiring**. `sample_for_scene` additionally produces the session-only
`scene["scan_points"]` preview (stored on `main._scan_scene_sample`, not
persisted — the footprints are). Dialog/wiring: `src/scan_import_dialog.py`.

## What to test when touching any of this

| You touched | Run |
|-------------|-----|
| `src/scene_contract.py` / scene schema | `tests/test_scene_contract.py` |
| `src/scene3d.py` growth/spread math | `tests/test_scene3d.py` (and the 2D timeline still matches) |
| `src/map3d_js.py` builders / hooks | `tests/test_map3d_js.py` + `tests/test_bridge_contract.py` |
| `html/scene3d.html` | `tests/test_bridge_contract.py` + `tests/test_scene3d_assets.py` (no CDN, vendored files present) |
| `src/splat_backdrop.py` / `src/splat_flow.py` | `tests/test_splat_backdrop.py`, `tests/test_splat_flow.py` |
| `src/scan_import.py` | `tests/test_scan_import.py`, `tests/test_footprint_ndsm.py`, `tests/test_footprint_extract.py` |
| `src/scene_wildlife.py` | `tests/test_scene_wildlife.py` |
| `src/sprite_gallery.py` / sprite forms | `tests/test_sprite_gallery.py` (+ regenerate the gallery JSON) |
| `src/scene3d_window.py` / `src/map3d_widget.py` | `tests/test_scene3d_window.py`, `tests/test_map3d_widget.py` (Qt-gated; self-skip headless) |

## Validation

```bash
python -m unittest tests.test_scene_contract tests.test_scene3d tests.test_splat_backdrop -v
python -m unittest tests.test_map3d_js tests.test_scene3d_assets tests.test_scene_wildlife tests.test_sprite_gallery tests.test_splat_flow tests.test_scan_import
python -m unittest tests.test_bridge_contract          # perma* hook contract, both directions
python -m unittest tests.test_scene3d_window           # Qt-gated (skips headless)
python -m unittest discover -s tests                   # full suite before finishing
```

All of the above pass headlessly (numpy/shapely/Qt-gated cases self-skip when
those optional deps are absent). For a visual check with a display:
`python main.py` → View → 3D Preview, drag the year slider (plants grow),
drag hour past dusk (night scene), and — with a splat imported — bake the yard
photo and confirm the 2D overlay lands on the splat's bbox.
