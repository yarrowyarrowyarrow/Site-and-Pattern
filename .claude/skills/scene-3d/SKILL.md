---
name: scene-3d
description: Use when working on the 3D preview, Scene JSON, html/scene3d.html, src/scene_contract.py, src/map3d_widget.py, src/map3d_js.py, or sprites. Covers the versioned project→3D contract (build_scene), the built-in three.js viewer vs the web3d/dist fork, window.perma* hook mechanics and their contract test, what is left of the yard-scan/splat feature (removed V3.22), and what to test when touching any of it.
---

# The 2D→3D pipeline (View → 3D Preview)

## Purpose / when to use

Everything between the project dict and pixels in the 3D window. Use this
skill when you: add a field to the Scene JSON, change plant/building/terrain
rendering, add a `window.perma*`
hook, or edit `html/scene3d.html`.

## Architecture in one page

```
project dict (GeoJSON FeatureCollection)
  │
  ▼
src/scene_contract.py   build_scene(project, *, year=0, get_plant=None,
  │                       elevation=None, when=None, wind=True)
  │                     → Scene JSON (SCENE_VERSION = 1, local metres,
  │                       +x east / +y north, origin = design centroid)
  ▼
src/scene3d_window.py   Scene3DWindow._push_scene()  (year/month/hour sliders,
  │                     off-thread terrain fetch, wildlife push)
  ▼
src/map3d_widget.py     Map3DWidget.apply_scene(scene)  →  run_js(...)
  │                     (queues JS until loadFinished)
  ▼
src/map3d_js.py         builders emit "window.permaX && window.permaX(json)"
  │
  ▼
html/scene3d.html       built-in three.js viewer (ES modules + importmap,
                        vendored three.js in html/vendor/, served over
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

`version, year, month, origin{lat,lng}, bounds, focus|None,
views{street, house}, boundary, plants[], buildings[] (kind:
building|canopy, roof), structures[], ground, surfaces[], lines[],
street|None, terrain|None, sun|None, is_night`. (`scan_points` and `splat`
went with the yard scan in V3.22; `focus`, `views` and a plant's `gone` came
in V3.43, `views.house` in V3.44, and `ground`, `surfaces`, `lines`, `street`
and a building's `roof` in V3.45.)

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

## The whole yard (V3.43; read `docs/plans/V3.43-the-3d-preview-reviewed.md`)

The plan above is the programme for the preview (eight increments, F260–F267)
and its guardrails. Five rules came out of its first increment, each with a
test, and each is a mistake the viewer made for years because every audit
rendered one plant and nobody rendered a yard:

- **Frame `focus`, never `bounds`.** `bounds` is the stage, floored at ±25 m;
  `focus` is the design's own extent (`src/scene_views.py`). In the page ask
  `frameBox()`. A scene with no `focus` (the probes, the sprite gallery, which
  sets it to `None` on purpose) frames `bounds` as before.
- **Stand where `views.street` says.** A neighbour's spot at the real frontage,
  clear of trunks and buildings, the same in every year because it is worked
  out from the design as planted: the before/after page compares three years
  from it. The sidewalk and walk cameras and the walker's start read it.
- **A building is a `canopy_footprint` too.** `kind` is `canopy` only when the
  footprint says it is a tree's crown (`caster_kind`), as `src/shade.py` reads it.
- **`standing_plants(scene)` is what is in the yard this year.** A placed plant
  that is `gone` (`"shade"` or `"short_lived"`) stays in `plants` at opacity 0.
  The page's twin is `standing(p)` in `01-core.js`: use it for anything that
  draws, picks, blocks or counts. `opacity` below 1 means declining, nothing else.
- **Year 0 is the design fully grown.** Never caption it as planting day.

`tests/test_yard_render.py` pushes a yard built by the real `build_scene` into
the real viewer and reads the picture back (`html/yard_probe.html`).
`python scripts/render_yard.py --out DIR` draws the contact sheets every 3D
increment ends with; look at them, a green gate is not a picture.

## The yard itself (V3.45; `docs/plans/V3.45-your-yard-not-a-green-field.md`)

`src/scene_site.py` says what the ground is and `html/scene3d/02c-site.js`
draws it. The rules for anything you add there:

- **Decide in `scene_site.py`, draw in the chunk.** A new shape type gets a
  row in `SURFACE_KINDS` and its kind a look in `SURFACE_LOOK` (a `rank`, a
  `tile`, a base colour); `tests/test_scene_site.py` fails on either half
  missing. A type nobody mapped keeps the person's colour.
- **Texture, never geometry.** A surface is a flat polygon with a quiet
  procedural texture. No blades of grass, no chips of mulch (V2.29).
- **What is not the design is pale.** The ground outside the outline (the
  owner's D3), the sidewalk and the road. Houses are massing: light walls, a
  darker roof, and no window, door or colour nobody recorded.
- **Never draw what is only assumed.** `street` is `None` unless the street's
  side was told or measured; a roof never makes a building taller than its
  recorded height. A line's height, a road's width and a roof's pitch are
  estimates stated in the module, not measurements.
- **Use `drapedShape` for anything flat on the ground.** It follows a slope
  (cut in four, uniformly, so no crack opens) and `tests/test_slope_render.py`
  reads it back on 6 m of relief. Give a new look a `rank`: it orders
  overlapping surfaces and is the depth offset that stops them flickering.
- **Winter is part of a look.** Soft ground takes the snow texture, hard
  ground packed snow, water ice (`siteMat`).
- The materials are kept for the session: `siteSharedMats()` spares them from
  `disposeDesignGroup`. A per-surface material (a custom colour) is not shared
  and is disposed with the scene.

## The window a homeowner opens (V3.44; `docs/plans/V3.44-getting-to-3d.md`)

The 3D preview opens from the simple app (the plan strip's *See it in 3D*, the
Overview's street item) without turning Advanced tools on. What that asks of
anything you add to it:

- **Two short rows by default, the rest behind the switch.** *When*, *Season*,
  *Time of day* as lists of named stops and *View* (From the street, From the
  house, From above, Walk, Reset view). Their words and values are one Qt-free
  table, `src/scene3d_stops.py`; the widgets are `Scene3DToolBar`'s `WHEN` and
  `VIEWS` groups (`src/scene3d_named_groups.py`). Everything else sits in
  `Scene3DWindow.advanced_rows`, shown by `set_advanced_tools(on)`, which the
  registry reaches through `main.scene3d_tools` (the window does not exist
  until it is opened). **A new control goes in `advanced_rows` unless a
  homeowner needs it**, and a tool the switch hides must be stopped by
  `set_advanced_tools(False)`.
- **The sliders are the record of the moment.** `self._year` / `_month` /
  `_hour` are read in a dozen places; the lists set them and follow them
  (`when_bar.set_time(..., quiet=True)` in `_update_labels`). A list never
  names a stop the picture is not at: off a stop it gains one entry that says
  where it is ("Seventh summer").
- **It opens on `scene3d_stops.OPENING`** (the owner's D5: fifth summer, July,
  15:00, from the street), once per design (`_on_new_design`, keyed on the
  scene's origin), never while Walk, a flight or the Flyover owns the camera.
  The view itself is `scene_views.opening_view(views)`: the street unless
  `views.street.behind` (a building hides the planting, or it is all at the
  back), then the house, else the whole yard.
- **Named views are `window.permaShowView('street'|'house'|'above'|'whole')`**
  (`html/scene3d/27-views.js`, `Map3DWidget.show_view`). Where each stands is
  in the scene: `views.street`, `views.house` (`scene_views.house_view`: the
  largest building inside the outline, or the one under the pin when nothing
  is outlined; absent otherwise, and the button says what it needs), `focus`
  for above. **A yard with no outline is still a yard**: its own extent stands
  in for the outline (the simple app's usual design is a pin and a bed). A
  walk through a wild community (`reference_version` in the project's
  properties) has no views.
- **`27-views.js` is the last chunk.** A probe that needs it waits for
  `permaShowView`. Its two callers in earlier chunks (`hudText`, the speed
  bar) are `typeof`-guarded.
- **A scene push is cheap only because of two rules.** `build_scene(...,
  memo=self._memo)` keeps the shade simulation between pushes (a year already
  shown costs about 0.02 s, not 0.2 to 0.9 s), and `wind_scene` reads the wind
  from the cache only. **Never let anything `build_scene` calls reach the
  network**: it runs on the main thread on every slider tick, and the suite's
  network guard hides the cost by failing the request at once. Slider moves
  are coalesced (`PUSH_EVERY_MS`); a test that moves a slider twice calls
  `win._on_push_interval()` to end the interval.
- **The words are the simple app's.** The window's modules are in the
  vocabulary ratchet's `SIMPLE_MODULES`; the page and its scripts are under
  the 12 px floor (`tests/test_visual_floor.py`); the line over the picture
  says the year in the toolbar's words (`whenWords`, held equal to
  `scene3d_stops.when_words` by a test).

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
   (V1.76), hence the server. three.js is **vendored** under
   `html/vendor/three` — `tests/test_scene3d_assets.py`
   fails the build if a CDN import sneaks back into `html/scene3d.html`.
   (An older comment in `src/map3d_widget.py` still says "fetches from a CDN"
   — the code and the guard test win.)

Both register the shared hooks; only the built-in viewer implements the full
set (`permaSetScene`, wildlife, dossier, snapshot…).

## The `window.perma*` hook mechanic (Python→JS only)

Unlike the 2D map there is **no QWebChannel here** — the 3D bridge is
one-directional: `src/map3d_js.py` builders emit
`window.permaX && window.permaX(<json.dumps payload>);` and
`Map3DWidget.run_js` executes them. Results come back only via
`page().runJavaScript(js, callback)`.

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

## Click to inspect: the dossier (V2.29)

Clicking a plant or creature opens an in-viewer card. The learning content is
built **in Python** by `src/scene_dossier.py` (Qt-free, every collaborator
injectable) and pushed with each scene via `map3d_js.set_dossier` →
`window.permaSetDossier`; `html/scene3d/10-inspect.js` renders it and draws the
food-web threads. The bridge stays **one-directional** — that is the whole
reason the content ships with the geometry rather than being fetched on click,
and it is why the card works in walk / fly / bee modes.

Things that will bite you:

- `userData.pick` is the hover NAME; `userData.pickId` is the plant id. Both are
  parallel arrays per InstancedMesh — a new plant family must set both or it
  will hover but not open.
- Creatures carry `on_id` (the anchor plant's id) from
  `src/scene_wildlife.py`; threads bind on that, not on the display name, so
  two plantings of one species don't merge.
- The dossier is keyed `{plants: {id-as-string: …}, fauna: {common_name: …}}` —
  ids for plants, names for creatures, because that is what a click has in hand.
- Every collaborator is called **once per design**, not per plant, and "only
  source here" is a set operation over the same edge query — never recompute a
  habitat score per plant here.
- `tests/test_scene_dossier.py` pins the honesty rules: unassessed toxicity
  reports as unassessed, prices are labelled estimates, and "only source" is
  relative to the design on screen.

### Species photos on the card

The card shows the species' own open-licensed iNaturalist photo. Four rules,
each with a test:

- **The URL never reaches the browser.** `_photo()` emits
  `{key, credit}` where `key` is an opaque `image_cache.cache_key` handle; the
  viewer fetches `/__image?k=<key>` from the app's own loopback server, and that
  route (`src/web_assets.py`) resolves keys **inside the photo cache directory
  and nowhere else**: it never takes a path (the path-taking `/__localfile`
  route went with the splat in V3.22). `tests/test_web_assets.py` drives the real
  server and asserts what it refuses.
- **A photo without a credit is not shown at all.** Showing an open-licensed
  image obliges us to name its author, so `_photo()` returns `None` when it
  cannot build a credit line, and `10-inspect.js` puts the `<img>` and its
  `<figcaption>` in one `<figure>` with no state where the caption is hidden.
  Use the single shared formatter `image_cache.credit_line` — it also avoids
  restating a licence the attribution already names in prose.
- **Cache-only on the push path.** `_photo()` calls `get_cached_image`, never
  `resolve_image`: it runs while building a scene push and must not block.
  Photos that are not cached yet are simply absent.
- **`src/photo_warm.py` fills the cache** (Qt-free, cancellable, resumable) on a
  worker `QThread` started by `scene3d_window._start_photo_warm`, which re-pushes
  the dossier every dozen photos so they appear as they land.

Visual check: serve `inspect_probe.html` from the **app's own** server
(`web_assets._ensure_server()`), not `python -m http.server` — the latter has no
`/__image`, so the figure removes itself via `onerror` and the probe reports
`photo=dropped` (that is the graceful path working, not a failure). Against the
app server it reports `photo=<W>x<H> · <name> · <credit>`.

## Aspect ratio: the V2.29 trap

Flora assets are authored at their species' **real height ÷ canopy** and
normalised **uniformly**; the instance scale divides the canopy by the measured
`half_width` (`unitXZ` in `04-quality.js`). Before this, assets were squashed to
1×1×1 and instanced by `(canopy_m, height_m, canopy_m)` — two different factors
— which stretched every foliage clump by the species' aspect (up to 4.2× on a
lodgepole pine). If you add a flora builder: shape it with
`mesh_ops.shape_to_aspect` (moves anchor points; branches re-stamped between
corrected ends) for anything with round foliage masses, or
`mesh_ops.squash_to_aspect` (exact, measured) for flat-leaf geometry only.
`tests/test_model_assets.py` fails the build if an archetype's authored aspect
drifts from its species' proportions — the guard that was missing when this bug
shipped, since triangle counts and node names were all correct throughout.

Also: `tierFor` is a **size** class (reads `height_m`), not a growth stage.

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
- As a window: `python -m src.sprite_gallery_window` (off the View menu since V3.07).
- Standalone: `html/sprite_gallery.html` + generated
  `html/sprite_gallery_scenes.json`; regenerate with
  `scripts/make_gallery_scene.py` (and `scripts/render_flower_sprites.py` for
  the docs image) whenever sprite forms or exemplar seed data change.
- `tests/test_sprite_gallery.py` guards the scene set.

## GLB model assets (09-models.js, V2.27)

Blender-generated low-poly GLB archetypes under `html/assets/models/`
(manifest + 37 files) render **in place of** the procedural geometry above,
per archetype, with the procedural builders as the **permanent fallback** —
never delete them. Chunk `html/scene3d/09-models.js` fetches the manifest at
boot (fire-and-forget), and on ready clears the archetype
caches + re-pushes `lastSceneObj` (the `permaSetQuality` idiom). The lookups
(`window.glbTreeArch/glbShrubArch/glbHerbArch/glbLayerArch/glbCritter`) are
consumed GLB-first in `04-quality.js` and `07-wildlife.js`.

Rules that keep it green:
- **09 registers NO `window.perma*` hooks** (the bridge contract is
  bidirectional); the `window.glb*` functions are invisible to it.
- Imported GLB **materials are discarded**; geometry joins the viewer's own
  `plantMaterial`s. `COLOR_0` is grayscale AO — all seasonal/health tints
  multiply through. Fauna materials are swapped by NAME (`MatFuzz`…).
- GLB master geometries are protected from `disposeDesignGroup` via
  `window.glbSharedGeos` (05-flowers.js) — keep that hook if you touch
  disposal.
- Structures (`glbStructure`, consumed in 05-flowers.js buildStructures)
  are the one family that KEEPS its GLB materials — real-metre assets,
  cloned per placement, footprint-scaled by size_m; box fallback stays.
- The generator lives in `scripts/blender/assetlib` (headless + Blender-MCP,
  one shared build path); contract + regen commands: `docs/3D_ASSETS.md` and
  `scripts/blender/README.md`. Smoke probe: `html/model_probe.html`
  (`?month=1` winter bareness, `?close=1` critters).

## Yard scan and splat backdrop: removed (V3.22)

The phone-scan import and the Gaussian-splat backdrop (`scan_import*`,
`scan_align`, `splat_backdrop`, `splat_flow`, Spark, the `/__localfile` route,
`capture_ortho`, the scene's `scan_points`/`splat`) were deleted in V3.22, RM-2;
the reasoning is in `docs/plans/V3.22-what-goes.md`. What remains: buildings a
scan produced are ordinary `canopy_footprint` features and still draw, shade
and extrude; an old design's `splat_backdrop` feature still opens and is
carried untouched on save; nothing reads it (`tests/test_old_scan_designs.py`).
`src/footprint_ndsm.py` / `src/footprint_extract.py` stay.

## What to test when touching any of this

| You touched | Run |
|-------------|-----|
| `src/scene_contract.py` / scene schema | `tests/test_scene_contract.py` |
| `src/scene_views.py`, a camera, the walk start, what counts as standing | `tests/test_scene_views.py`, `tests/test_yard_render.py` (the real viewer on a whole yard), `tests/test_walk_walls.py`, then `scripts/render_yard.py` and look |
| `src/scene3d.py` growth/spread math | `tests/test_scene3d.py` (and the 2D timeline still matches) |
| `src/map3d_js.py` builders / hooks | `tests/test_map3d_js.py` + `tests/test_bridge_contract.py` |
| `html/scene3d.html` | `tests/test_bridge_contract.py` + `tests/test_scene3d_assets.py` (no CDN, vendored files present) |
| old designs carrying a `splat_backdrop` feature | `tests/test_old_scan_designs.py` |
| `src/footprint_ndsm.py` / `src/footprint_extract.py` | `tests/test_footprint_ndsm.py`, `tests/test_footprint_extract.py` |
| `src/scene_wildlife.py` | `tests/test_scene_wildlife.py` |
| `src/sprite_gallery.py` / sprite forms | `tests/test_sprite_gallery.py` (+ regenerate the gallery JSON) |
| `html/scene3d/09-models.js` / `html/assets/models/` | `tests/test_model_assets.py` + `tests/test_scene3d_assets.py` + `tests/test_bridge_contract.py` |
| `scripts/blender/assetlib` generators | regenerate (`docs/3D_ASSETS.md`), then `tests/test_model_assets.py` + the model_probe screenshots |
| `src/scene3d_window.py` / `src/map3d_widget.py` | `tests/test_scene3d_window.py`, `tests/test_map3d_widget.py` (Qt-gated; self-skip headless) |
| `src/scene_dossier.py` / `html/scene3d/10-inspect.js` | `tests/test_scene_dossier.py` + `tests/test_bridge_contract.py`; visual check via `scripts/make_inspect_probe.py` + `html/inspect_probe.html` |
| the ground, or anything drawn lying on it (`02-plants.js` `buildGround`/`onGround`, contact shadows, boundary, buildings, `16-editing.js` `groundPointAt`, the orbit) | `tests/test_slope_render.py` (the real viewer in headless Chromium on a 6 m slope: everything that lies on the ground must agree with `terrainHeightAt`, V3.04) + `tests/test_terrain_height.py` |
| flora aspect / `mesh_ops.shape_to_aspect` | `tests/test_model_assets.py` (authored aspect + manifest↔geometry half_width) **and** `tests/test_scene3d_render.py` (real viewer in headless Chromium, measures what got built — the only guard that sees geometry × instance transform together) |

## Validation

```bash
python -m unittest tests.test_scene_contract tests.test_scene3d tests.test_old_scan_designs -v
python -m unittest tests.test_map3d_js tests.test_scene3d_assets tests.test_scene_wildlife tests.test_sprite_gallery
python -m unittest tests.test_bridge_contract          # perma* hook contract, both directions
python -m unittest tests.test_scene3d_window           # Qt-gated (skips headless)
python -m unittest discover -s tests -t .                   # full suite before finishing
```

All of the above pass headlessly (numpy/shapely/Qt-gated cases self-skip when
those optional deps are absent). For a visual check with a display:
`python main.py` → View → 3D Preview, drag the year slider (plants grow),
and drag hour past dusk (night scene).
