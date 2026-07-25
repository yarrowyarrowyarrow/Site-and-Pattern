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
| Shrubs (31 morphology variants) | vase, spreading, mound, thicket, irregular | `SHRUB_FORMS` silhouette × leaf variant |
| Herbs (52 morphology variants) | erect, ferny, rosette, clump, grassy, mat, fern | `HERB_FORMS` growth form × leaf variant |
| Layers | grass ×3, aquatic ×3, vine ×3, groundcover ×2 variants | plant_type bucket |
| Fauna | bee, lep (butterfly+moth), bird, fly (hover+darner), beetle, bat, mammal | critter kind; species looks are tints |
| Structures | all 15 placeables (pond, swale, rain garden, rain barrel, bee log, bee hotel, brush pile, snag, rock xeriscape, lawn patch, raised bed, compost bin, shed, fence, fire pit) | `struct_id` |

52 GLBs + `manifest.json` under `html/assets/models/` — ~11 MB total, every
**unit** (a tier or a variant, which is what gets instanced) within the triangle
budgets in `scripts/blender/assetlib/conventions.py`.

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

- **Unit frame (flora):** base y=0, height 1.0, scaled **uniformly** so the
  authored proportions survive (the exporter converts Blender Z-up → glTF
  Y-up). Each unit's resulting half-width is published as `half_width` in the
  manifest; the viewer re-normalises with the same `normalizeUnit` the
  procedural builders use, reads the half-width off the geometry, and scales
  instances by `(canopy_m / 2·half_width, height_m, canopy_m / 2·half_width)`
  — landing on exactly canopy_m across, so growth-year and spread math are
  untouched.

  **Archetypes are authored at their species' real aspect ratio**
  (`conventions.CROWN_ASPECT` / `SHRUB_ASPECT` / `HERB_ASPECT` /
  `LAYER_ASPECT`, all medians over `data/plants_master.json`). This is not
  cosmetic. Until V2.29 every asset was squashed to a 1×1×1 box and then
  instanced by `(canopy_m, height_m, canopy_m)` — two different factors
  whenever a species isn't as wide as it is tall, which prairie trees are
  emphatically not (height ÷ canopy runs 1.2 for bur oak to 4.2 for lodgepole
  pine). Every sub-feature was stretched by that ratio, so a poplar's foliage
  clump rendered as a mass 6 m wide and 13 m tall — the "handful of giant
  leaves on a pole" look. The two transforms cancel, and clumps stay round,
  exactly when authored width/height equals canopy_m/height_m.

  Builders shape to the target by moving *anchor points* only
  (`mesh_ops.shape_to_aspect`), never by scaling finished geometry — a branch
  is re-stamped between its corrected endpoints (`add_cone_between`), so
  narrowing a crown shortens boughs instead of squashing them. Flat-leaf
  families (herbs, grass/reed tufts, vines) finish on the exact measured
  correction instead (`mesh_ops.squash_to_aspect`): a leaf is a flat ribbon,
  so a horizontal scale makes it a slightly narrower leaf rather than a
  deformed one, and predicting a leafy plant's extent from its parameters is
  biased ~30% narrow. Groundcover keeps anchor shaping — its domes are round.

- **Foliage granularity:** leaf-mass radius is a fraction of the crown's
  half-width, not of the asset height (`FOLIAGE_FRAC`), and the fraction
  *shrinks* with the size tier while the count grows (`CLUMPS_PER_TIP`,
  `DECID_MIN_R`). So a big tree carries many fine masses and a sapling a few
  coarse ones — structural detail tracks absolute size, not just growth year.
  Masses are 20-triangle icosahedra (subdiv 0), matching the viewer's own
  `makeFoliageMass`, which is what pays for the extra count.
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
- **Leaf variants (V2.29):** a herb or shrub file ships one unit per **(blade
  class × grain class)** its family's species actually use, and the manifest
  publishes the mapping as `variant_keys: {"broad_1": 0, "compound_2": 3, …}`.
  Instancing gives one 3-component scale per plant, so a species' leaf size and
  outline cannot be a per-instance transform — they have to be baked. The
  fourteen recorded `leaf_shape` values collapse into four construction classes
  (`narrow` / `broad` / `cut` / `compound`) and `leaf_size_cm ÷ mature_height_m`
  into three size classes. The generator reads `data/plants_master.json` and
  builds only the combinations that occur — 49 of 84 possible herb pairs, 29 of
  60 shrub ones — so the payload carries no archetype the app can select. Both
  files always include the neutral `broad_1` unit as the fallback. The viewer's
  copy of the classification is `02-plants.js` `bladeClassFor` / `grainClassFor`
  / `variantKeyFor`; `tests/test_model_assets.py` extracts those tables and
  compares them against `conventions.py`, because two independent
  implementations of one classification is the whole risk.
- **Leaf counts are budgeted, not fixed:** a compound leaf is a rachis plus
  `2n+1` leaflets, so it costs 3–9× a simple blade. `mesh_ops.thin_leaf_nodes`
  drops whole nodes — never half a pair, since opposite-vs-alternate is the field
  mark the leaves exist to show — until the foliage fits alongside the skeleton.
  A rose therefore ends up with fewer, larger leaves than a dogwood, which is
  also how the plants themselves resolve the same constraint.
- **Structures:** authored at REAL METRES (no unit frame) with their aspect
  baked in (the scene sends `size_m` only — no rotation/width), and their
  authored materials are KEPT (fixed real-world colours; the palette is
  sRGB, converted to linear at export — glTF `baseColorFactor` is linear).
  The viewer clones per placement and scales uniformly in XZ by
  `size_m / authored size_m`; `scale_mode: "footprint"` (ponds, lawns,
  fences, swales, beds) keeps the authored height, `"uniform"` scales it.

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
present, unit-frame bounds, declared nodes/materials, triangle budgets, that
each archetype is authored **at its species' aspect ratio**, and that the
manifest's `half_width` still matches the shipped geometry. The aspect check
is the one that would have caught the V2.29 deformation: triangle counts,
node names and materials were all correct while every tree was stretched 2–4×.

## Render gate

`tests/test_scene3d_render.py` boots the real viewer in headless Chromium via
`html/aspect_probe.html`, pushes one plant at a time of known dimensions, and
reads back the bounding box the viewer actually built
(`window.permaMeasure`). Every other guard checks a *part* — budgets, node
names, the manifest, the authored aspect. The V2.29 deformation slid past all of
them because each part was right and their **composition** was wrong. This is
the only test that would have caught it; it is verified to fail (2.3× error on
spruce) when the instancing fix is reverted. Self-skips without a Chromium
binary; set `CHROME=` to point at one.

```bash
python -m unittest tests.test_scene3d_render      # prints the worst error on pass
```

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

## Follow-ups (out of scope so far)

The fly-mode avatar and spotlight critter stay procedural (camera-tuned); an
`accent` third part (e.g. separate red dogwood canes) is reserved in the
conventions; structure rotation awaits a scene-contract field (the 2D map
doesn't orient placeables either — parity).
