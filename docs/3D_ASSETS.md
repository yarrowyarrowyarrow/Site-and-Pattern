# 3D GLB model assets — Blender pipeline & viewer contract

Since V2.27 the 3D viewer can render **Blender-authored low-poly GLB
archetypes** for plants and wildlife instead of (strictly: *in front of*) its
procedural geometry. The procedural builders documented in
[`3D_SPRITES.md`](3D_SPRITES.md) are the **permanent fallback set**, not a
transition: a build without `html/assets/models/`, a corrupted file, or a
single bad archetype silently renders exactly as before, per archetype.

**Design principles:** the assets are keyed by *archetype*, never by species —
a spruce is a spruce because the data says `genus: picea`, and per-species
identity stays what it always was: per-instance tints and profile parameters
(P9 — no invented detail). Geometry carries only grayscale ambient-occlusion
vertex colors so the viewer's seasonal color, winter bareness, health
withering, and presence fades all keep working (P4, P5); silhouettes aim for
"grown, not designed" (P2).

## What exists

| Family | Archetypes | Keyed by |
|--------|-----------|----------|
| Trees (×3 growth tiers each) | spruce, fir, pine, larch, def_conifer; aspen, birch, oak, willow, cherry, apple; def_slender/oval/spreading | genus profile (`02-plants.js _PROF`) / conifer kind / crown form |
| Shrubs | vase, spreading, mound, thicket, irregular | `SHRUB_FORMS` silhouette |
| Herbs | erect, ferny, rosette, clump, grassy, mat, fern | `HERB_FORMS` growth form |
| Layers | grass ×3, aquatic ×3, vine ×3, groundcover ×2 variants | plant_type bucket |
| Fauna | bee, lep (butterfly+moth), bird, fly (hover+darner), beetle, bat, mammal | critter kind; species looks are tints |

37 GLBs + `manifest.json` under `html/assets/models/` — ~3.6 MB total, every
asset within the triangle budgets in
`scripts/blender/assetlib/conventions.py`.

## The pipeline

```
scripts/blender/assetlib  (bpy generators — Blender 4.2 LTS+, never imported by the app)
        │  headless:  blender --background --python scripts/blender/build_assets.py -- \
        │                 --out html/assets/models [--only tree.spruce,fauna*] [--check]
        │  (also runs on the pip `bpy` wheel: python -c "…build_all(out_dir=…)")
        │  MCP:       bootstrap cell in scripts/blender/README.md → S.build/S.frame/
        │             get_viewport_screenshot → edit → reload → S.export_all(…)
        ▼
html/assets/models/*.glb + manifest.json      (committed — regenerate-and-commit,
        │                                      the render_flower_sprites.py pattern)
        ▼
html/scene3d/09-models.js                     (fetch manifest at boot, fire-and-forget;
        │                                      per-file failures skipped; on ready:
        │                                      clear archetype caches + re-push scene —
        │                                      the permaSetQuality idiom)
        ▼
window.glbTreeArch / glbShrubArch / glbHerbArch / glbLayerArch / glbCritter
        — consumed GLB-first, procedural-fallback, by 04-quality.js & 07-wildlife.js
```

Both drivers share `assetlib.build_all`, so an asset iterated live over the
[Blender MCP](https://github.com/ahujasid/blender-mcp) exports byte-identically
in batch (deterministic crc32 seeds). See `scripts/blender/README.md` for the
MCP bootstrap cell and the iterate→screenshot→export loop.

## The generator↔viewer contract

Defined once in `scripts/blender/assetlib/conventions.py`; the loader side is
`html/scene3d/09-models.js`. In brief:

- **Unit frame (flora):** base y=0, height 1.0, half-width 0.5 (the exporter
  converts Blender Z-up → glTF Y-up). The viewer re-normalises with the same
  `normalizeUnit` the procedural builders use, then scales instances by
  `(canopy_m, height_m, canopy_m)` — so growth-year and spread math are
  untouched.
- **Parts (flora):** meshes named `bark` + `foliage` (herb/layer assets:
  `foliage` only). Inside a tier/variant node the names are prefixed
  (`tier0_bark`, `v1_foliage`) because Blender object names are unique per
  file. A deciduous `bark` part is a **complete winter silhouette** — the
  viewer winter-hides only the foliage part (the epsilon-scale trick).
- **Materials (flora):** DISCARDED on load. Geometry is married to the
  viewer's own `plantMaterial` instances (wind sway, `vertexColors: true`),
  and `COLOR_0` is **grayscale AO** — per-instance tints multiply through.
  Never bake hue.
- **Fauna:** named nodes are the animation/appearance contract — `WingL` /
  `WingR` pivots **with origin at the hinge** (the viewer wraps them and
  drives the flap), `Band0..2` (bee stripes, shown per `app.bands`), `Spots`,
  `Beak` (stretched for hummingbirds), `EarL/R`, `Tail`. Named materials
  (`MatFuzz`, `MatBody`, `MatFore`…) are placeholders the viewer swaps for
  `_cmat`/`_wingMat`-built materials tinted from the species appearance bag
  (`src/scene_wildlife.py`). Multi-variant files prefix node names
  (`hover_WingL`).
- **Growth tiers:** trees ship `tier0/1/2` matching `tierFor(scale_factor)`;
  the young-tree structural simplification is authored, not decimated.

## Regenerating

```bash
# with a Blender install
blender --background --python scripts/blender/build_assets.py -- --out html/assets/models
# or with the pip wheel (Python 3.11):  pip install "bpy==4.2.*"
python -c "import sys; sys.path.insert(0,'scripts/blender'); \
           from assetlib.build_all import build_all; \
           build_all(out_dir='html/assets/models')"
# then
python -m unittest tests.test_model_assets
```

Commit the changed GLBs + `manifest.json` (`.gitattributes` marks `*.glb`
binary). `tests/test_model_assets.py` (stdlib-only — parses the GLB
containers directly) guards: manifest↔file consistency, key parity with the
viewer's own archetype vocabularies, no textures, `POSITION`+`COLOR_0`
present, unit-frame bounds, declared nodes/materials, triangle budgets.

## Smoke probe

`html/model_probe.html` (a dev page like the sprite gallery) pushes a
synthetic scene covering every archetype family + five critter kinds into the
real viewer and banners `MODELS ACTIVE` / fallback:

```bash
python -m http.server 8123 --directory html   # from the repo root
# browser: http://127.0.0.1:8123/model_probe.html
#   ?month=1   → winter: deciduous bare skeletons, conifers foliated
#   ?close=1   → critter close-up
# headless screenshot (the render_flower_sprites.py Chromium):
CHROME=$(ls /opt/pw-browsers/chromium*/chrome-linux/chrome | head -1)
"$CHROME" --headless --no-sandbox --enable-unsafe-swiftshader \
  --use-angle=swiftshader --window-size=1280,840 \
  --screenshot=/tmp/probe.png --virtual-time-budget=30000 \
  "http://127.0.0.1:8123/model_probe.html"
```

Prove the fallback by renaming `html/assets/models/` and reloading — the
viewer must render today's procedural look with one `console.info` and no
error overlay.

## Follow-ups (out of v1 scope)

The 15 habitat **structures** (`buildStructures` still extrudes plain boxes) —
one GLB each keyed by `struct_id` is the natural next increment; the fly-mode
avatar and spotlight critter stay procedural (camera-tuned); an `accent`
third part (e.g. separate red dogwood canes) is reserved in the conventions.
