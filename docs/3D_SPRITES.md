# 3D Sprites — reference & gallery

Every unique "sprite" the 3D viewer (`html/scene3d.html`) can render, in two
families: **plant-body geometry archetypes** (procedural meshes) and **flower
billboard sprites** (camera-facing textured points). This doc is the catalogue;
the **live gallery** below lets you rotate and inspect each one.

> **Since V2.27** the procedural plant/wildlife geometry documented here is the
> **built-in fallback set**: when Blender-generated GLB archetypes exist under
> `html/assets/models/`, the viewer renders those instead, per archetype, and
> falls back to these forms for anything missing. The GLB pipeline and its
> generator↔viewer contract live in [`3D_ASSETS.md`](3D_ASSETS.md). Flower and
> berry sprites below are unaffected — they layer on top of either geometry.
>
> **Since V2.29** archetypes are authored at each species' **real aspect ratio**
> and normalised uniformly, so the instance transform no longer stretches
> foliage (see the unit-frame note in
> [`3D_ASSETS.md`](3D_ASSETS.md#the-generatorviewer-contract)). Two consequences
> for the tables below: a tree's **tier is a size class, not a growth stage**
> (`tierFor` reads `height_m`, so a young conifer is a small dense cone rather
> than a sparse adult), and **foliage grain comes from the species' leaf
> length** (`leaf_size_cm`, schema v47) — a bur oak reads coarse beside an aspen
> at the same crown size. Clicking any plant or creature opens a card built from
> the app's sourced ecology (`src/scene_dossier.py` →
> `html/scene3d/10-inspect.js`), topped by the species' own open-licensed
> iNaturalist photograph with its credit — so the card shows both the model and
> the real thing, which is the fastest way to judge whether the model is any
> good. Photos are warmed into the local cache in the background
> (`src/photo_warm.py`); until one lands, the card simply has no photo.
>
> **Also since V2.29**, a shrub or herb archetype is no longer one shape per
> growth form. Each form ships one baked unit per **(blade class × grain class)**
> its species actually use — so a rose's alternate compound leaves, a dogwood's
> opposite ovate ones and a blue-eyed grass's linear ones are different geometry
> rather than the same form at three sizes. The classes come from the species'
> own `leaf_shape` / `leaf_size_cm` / `leaf_arrangement` (schema v47/v48); the
> viewer's classifier is `bladeClassFor` / `grainClassFor` / `variantKeyFor` in
> `02-plants.js`, and the shrub builders now grow a branching **cane skeleton
> clothed in real leaves** instead of ellipsoids on straight stems. Where a
> species records nothing, the neutral variant and the tuned form defaults apply
> — an honest empty rather than an invented leaf (P9).
>
> **Shrub density.** Real leaves cost triangles, and the first cut of that
> rebuild bought only ~180 of them per shrub, which on a 4 m saskatoon reads as
> bare canes with green flecks. Three changes brought it to **~600**: a shrub
> blade is stamped as a **2-segment ribbon** (4 triangles, not 8) whose single
> interior vertex sits on the blade's *widest point*, so the outline still
> separates a lanceolate willow leaf from an ovate dogwood one at a fraction of
> the cost; twigs are stamped as 3-sided rather than 4-sided cones, handing a
> quarter of the skeleton back to the foliage; and `TRI_BUDGETS["shrub"]` went
> to 3600, since shrubs sit at the fringe of a bed where they are looked *at*
> rather than under. The lobed family (currant, gooseberry, hawthorn) keeps
> 4-segment blades — a cut leaf has nowhere to put its lobes on one vertex.
> `mesh_ops.leaf_tris` and `add_blade_or_leaf` share `blade_segments` so the
> budget can never disagree with what is actually stamped
> (`tests/test_model_assets.py:LeafCostModelTest`).
>
> Even so, this is a **stylised** shrub, not a census: a real saskatoon carries
> thousands of leaves and this one carries hundreds, so it reads airier than the
> plant does in a hedge. The honest trade is legibility per triangle.

## See them live

**In the app:** **View → 3D Sprite Gallery…** — a native window that drives the
real viewer; pick any sprite from the sidebar, and set a **Detail** level
(Low / Medium / High) if the view is sluggish on your machine.

**Standalone (browser):** the same gallery as a web page — drag to orbit, scroll
to zoom, pick any item from the sidebar.

**Contact sheet (V2.29).** Both galleries have a **▦ Contact sheet** toggle that
renders every listed sprite to a thumbnail and lays them out in a grid. Single
view is for studying one plant; the sheet is for judging the *library*, because
you cannot see that two sprites are the same sprite until they are next to each
other. It honours the search box — type `Ribes` and get a sheet of just the
currants — and clicking a tile opens it. Every tile is drawn by the real viewer
(`window.permaSnapshot`), so the sheet can never drift from what the app renders;
both views wait on `window.permaModelsReady` first, since a sheet built before
the baked GLBs land is a sheet of the procedural fallback geometry.

The standalone page takes `?sheet=1` and `?q=`, so a sheet of one genus is a
shareable link:
`sprite_gallery.html?sheet=1&q=Ribes`.

**Groups worth knowing.** *Plant-body geometry* is the labelled archetype
reference; *Species* is every seeded plant; and **Body × flower combos** is the
deduplicated vocabulary — one specimen per (growth form × flower form) pair the
catalogue actually uses, 75 of them across 436 species. A sprite here is a body
wearing a bloom, so that group is the honest answer to "how many different things
can this app draw". If two combos look alike there, every species built from them
looks alike in a design.

**How good are they, really?** [`SPRITE_AUDIT.md`](SPRITE_AUDIT.md) scores every
archetype for fidelity *and* distinctness, names what is wrong with each, and
ranks what it would cost to improve them.

```bash
# from the repo root
python -m http.server 8000
# then open:
#   http://localhost:8000/html/sprite_gallery.html
```

**Every seeded species has a page.** Alongside the labelled archetype specimens,
the gallery lists all ~436 seeded species, grouped by plant type, each rendered
from its own seed record — so the sprite you see is exactly the one a design
containing that plant shows, with its real growth form, leaf shape and
arrangement, flower form and bloom window. There is a search box; it matches
common names, Latin names and the descriptions, so "Populus" finds the aspens.
The archetype specimens stay: they are the labelled reference for what the
builders can draw, and they are what this doc points at.

Berries are the one thing a species page can miss. `fruit_color` is curated in
the database rather than the seed JSON, and `src/sprite_gallery.py` is
deliberately DB-free so `scripts/make_gallery_scene.py` can build the standalone
page offline; only the hand-authored specimens fruit.

**Wildflower specimens are paired.** Five of the herb entries exist to make the
V2.29 morphology work visible: they hold the growth form constant and vary only
the leaf character, so the difference is attributable. Fireweed (erect ·
lanceolate) against Lupine (erect · palmate compound); Smooth Aster (clump ·
alternate) against Bergamot (clump · **opposite**, same leaf shape); Yarrow
(ferny · bipinnate) against Columbine (ferny · pinnate compound); Fleabane
(rosette · spatulate) against Prairie Crocus (rosette · deeply cut); Pussytoes
(mat · spatulate) against Bedstraw (mat · **whorled**). One example per form
could not show any of this — there are 46 baked wildflower archetypes.

Each specimen is framed to fill the same share of the view. The framing box used
to have a 0.7 m floor, which only ever applied to plants shorter and narrower
than that — most wildflowers — so pussytoes filled 12% of the frame while every
tree filled 43%: the gallery was worst at exactly the species it was most needed
for (`src/sprite_gallery.py:_scene_for`).

Deep-link a single sprite with `?sprite=KEY`, e.g.
`…/sprite_gallery.html?sprite=conifer_pine` or `?sprite=shrub_dogwood`.

### The catalogue bench (V2.34, a plant bench since V2.36)

```bash
python scripts/tune_morphology.py          # → http://127.0.0.1:8756
```

The gallery shows you what is wrong; this is where you fix it. Four panes: the
catalogue with triage filters, the **real viewer** rendering the species at year
6 in July, the characters, and the photographs. `←`/`→` pages the catalogue,
`S` saves straight to `data/plants_master.json`, and `R` drops a **10 cm scale
rule** into the render so "is that bloom really 7 cm?" is answerable by eye
instead of by faith.

**It edits the whole plant, not just the flower (V2.36).** A second control
group covers `leaf_shape`, `leaf_size_cm`, `leaf_arrangement`, `leaf_surface`,
`growth_form`, `branching` and `mature_height_m` — which is where the fidelity
actually is, because `growth_form` picks the plant's entire body and all seven
arrived pre-filled by a genus-level guess. Two consequences:

- **Every species is reachable.** `_flowering` was a gate that hid 123 of 434
  records — every grass, sedge and rush, and a dozen trees. It is now a filter
  (`flowering only`, on by default), and the flower group greys out where it
  does not apply.
- **Provenance per group.** `leaf_data_source` / `leaf_data_citation` (schema
  v57) mirror the flower pair; the row badge shows two letters, leaf then
  flower, and `verified` means both.

### The fauna bench (V2.36)

```bash
python scripts/tune_fauna.py          # → http://127.0.0.1:8757
```

The same tool for the animals. Until schema v58 a creature's appearance was
computed from substrings of its common name, so **69 bees rendered as 12 animals
and 31 lepidoptera as 16** — 29 bumblebees pixel-identical, and a Polyphemus,
a Cecropia and an Isabella Tiger Moth all the same moth. Now it is data:
per-tergite band patterns, real wingspans, wing shape and pattern, resting
posture and flight style, each with its own provenance pair.

The band editor is the centrepiece — thorax then T1…T6, the order every
bumblebee key names them, **drawing the bee as you type it** so the pattern can
be held against the plate. `flight_style` is the other one worth the time: it is
a real character and it drives how the animal moves in the preview. See
[`FAUNA_FIELD_GUIDE.md`](FAUNA_FIELD_GUIDE.md).

**Two more fields now change what you see** (V2.45/V2.46). `wingspan_min_mm` /
`wingspan_max_mm` and the bees' `body_length_mm` are no longer only data: the
viewer draws every creature at **life size** from them, so a wrong wingspan is
now a visibly wrong animal standing next to a 1.75 m person. And
`flight_style` picks the *bout* — how many beats before the glide, and how long
the glide lasts — so `gliding` really does sail and `darting` really does buzz.
Both are the same argument as the band editor: the value is worth entering
because it is visible.

**What this bench does not do yet is painting.** A per-species wing *texture* —
the author drawing a monarch's veins rather than choosing three colours — is
F107 in [`ROADMAP_NEXT.md`](ROADMAP_NEXT.md), and it is a real piece of work
because the fauna GLBs ship with no UVs and no textures by design.

**The vocabulary is drawn (V2.36).** Asking somebody to choose *corymb* or
*cyme* from a dropdown of bare words is a coin flip with extra steps, so each
vocabulary select carries a line drawing, and clicking it opens the whole
vocabulary side by side — where clicking the one that matches sets the value.
The drawings live in [`html/botany/diagrams.js`](../html/botany/diagrams.js),
outside the dev tool because they are also the glossary in
[`BOTANY_FIELD_GUIDE.md`](BOTANY_FIELD_GUIDE.md) and the raw material for a
plant-ID lesson (F83). Every dropdown is built from `src/data_quality.py`'s own
allowlists, served over `/api/vocab` — the HTML used to carry three hand-typed
copies, which is how the V2.35 photo-slot list drifted.

It exists because the preview's remaining fidelity gap is **not a code gap**: it
is roughly ten characters × 434 species, and for most of them no single flora
records all ten. Flower diameter in cm, ray count, how far the bloom sits above
the leaves and how many flowering stems a mature plant carries are exactly the
numbers floras skip — and they are the four the generator most needs. Someone
who knows these plants can fix a wrong value faster than anyone can look it up.

**The photo pane is where most of the answers are (V2.36).** Petal count,
symmetry, petal shape, architecture, disc colour, rosette and branching are all
readable off a good photograph, and flowering stems and bloom height come off a
habit shot — only diameter in cm really needs a ruler or a flora. So the strip
does three jobs:

- **Sort what is already here.** The 323 photographs the catalogue ships appear
  in an `unsorted` bucket rather than being assumed to be flower macros; one
  click files each into its real slot, carrying its credit across verbatim. The
  "sorted" and "habit" counters therefore start at zero and mean something.
- **Find more.** An empty slot pulls the species' wider openly-licensed
  iNaturalist set (~12 photos) so a whole-plant shot can be chosen by looking.
- **Say where a number came from.** `flower_data_source` (what kind) and
  `flower_data_citation` (which one) travel with the values. `--flora-fetch`
  additionally offers to read the four numbers off one published description —
  off by default, `robots.txt`-gated, one species per click; see
  [`DATA_SOURCES.md`](DATA_SOURCES.md) for why it is shaped that way.

`--report` prints every shipped value that differs from what the family-first
seeder (`scripts/seed_flower_morphology.py`) would produce, so hand-tuned
species can be folded back into its `SPECIES_OVERRIDE` and survive a re-seed.
A dev tool, not an app panel: the seed catalogue is the project's, not the end
user's.

![All archetypes in the gallery](3d/sprite_gallery_overview.png)

## Flower sprites

These are drawn by `makeFlowerTexture()` and rendered in each plant's real
`flower_color`, only while the scene month falls inside the plant's bloom window.
The image below is the **actual** `makeFlowerTexture` output (extracted from
`scene3d.html`), tinted with a representative real colour per form.

**Berries (V2.0):** fleshy-fruited plants (curated `fruit_color` — saskatoon,
chokecherry, currants, viburnum, dogwood, rose hips, blueberry…) show clusters of
shaded berries through the canopy during their `fruit_period` (`buildFruit`).
Dry-fruited plants (acorns, cones, catkins) carry no `fruit_color`, so they never
grow berries.

![Flower sprite sheet](3d/flower_sprites.png)

| Form | Looks like | Example plant (place to test) |
|------|-----------|-------------------------------|
| `daisy` | ringed petals + disc | Alpine Aster |
| `rays` | big composite sunflower | Balsamroot |
| `spike` | stacked tapering florets | Alberta Penstemon |
| `plume` | feathery tapering spray / seed-head | Alkali Cord Grass, goldenrod |
| `umbel` | flat-topped dot cluster | Golden Alexanders, Yarrow |
| `globe` | dense spherical head | Green Milkweed |
| `cluster` | rounded bunch of florets (default) | Alpine Forget-me-not |
| `bell` | hanging bell | Alaska Harebell |
| `trumpet` | 5-point tubular star | Blue Columbine |
| `cattail` | brown emergent spike *(V1.92)* | Cattail (Typha) |
| `pea` | legume raceme (banner + wings) *(V1.94)* | Silky Lupine, vetches, milkvetches |
| `whorl` | tubular whorl / shaggy head *(V1.94)* | Wild Bergamot (Monarda) |
| `star` | 5 broad rounded petals *(V2.1)* | Wild Blue Flax, geranium, phlox, prairie smoke |
| `cross` | 4 petals (mustard family) *(V2.1)* | Golden Draba |
| `lily` | 6 pointed tepals *(V2.1)* | Wood Lily, Blue-eyed Grass, camas, glacier lily |

## Plant-body geometry archetypes

Procedural meshes, bucketed by `plant_type` in `buildPlants()` → `byKind`.

**Species geometry (V1.94):** the most impactful keystone/host trees and shrubs
are differentiated by **genus** (from `scientific_name`) so they read as
themselves — see `TREE_PROFILES` / `_SPROF` in `scene3d.html`. Trees are still
built per crown form (slender / oval / spreading, forced per genus where it
matters) × maturity tier × per-individual sub-variation; a genus a profile
doesn't list falls back to the generic look.

| Archetype | Builder | Looks like | Place to test |
|-----------|---------|-----------|---------------|
| **Spruce** (Picea) | `buildConiferGeo` (spruce) | dense narrow bluish spire | White Spruce, Black Spruce |
| **Pine** (Pinus) | `buildPineGeo` | open, scraggly; clear trunk + tufted upper crown, yellow-green | Jack Pine, Lodgepole Pine |
| **Fir** (Abies/Pseudotsuga) | `buildConiferGeo` (fir) | narrow dark conic, sharp thin summit | Balsam Fir, Douglas Fir |
| **Larch / Tamarack** (Larix) | `buildConiferGeo` (larch) | soft sparse cone; deciduous needles (gold→bare) | Tamarack |
| **Aspen / Poplar** (Populus) | `generateDaVinciTree` | slender, pale bark, open round crown | Trembling Aspen, Balsam Poplar |
| **Birch** (Betula) | `generateDaVinciTree` | white bark, finer pendulous twigs | Paper Birch, Water Birch |
| **Oak** (Quercus) | `generateDaVinciTree` | broad gnarled spreading, dark | Bur Oak |
| **Willow** (Salix) | `generateDaVinciTree` | pale grey bark, weeping fringe | Bebb's Willow |
| Other tree | `generateDaVinciTree` | generic branch crown + foliage | cherry, apple, etc. |
| **Shrubs** (multi-stem clumps) | `buildShrubGeo` | a few ascending woody stems clothed with faceted low-poly leaf masses, silhouette by growth form *(V1.96)* | see below |

Shrubs are no longer a single dome — they're a multi-stem woody clump whose
**growth form** (`SHRUB_FORMS`) differs by genus, with crisp flat-shaded faceted
foliage masses:

| Form | Looks like | Genera |
|------|-----------|--------|
| `vase` | upright, clean base, fountain crown | Saskatoon, willow, hazelnut, alder, hawthorn, cherry |
| `spreading` | broad low clump (dogwood adds **red** stems) | Dogwood (Cornus), Viburnum |
| `mound` | low dense rounded thicket to the ground | Rose, spirea, snowberry, blueberry |
| `thicket` | many fine arching canes, airy | Currant (Ribes), raspberry |
| `irregular` | sparse asymmetric woody (often silvery) | Sagebrush, buffaloberry |
| **Herbaceous** (by growth form) | `buildPerennialGeo` | leaves built to the species' real habit *(V1.98)* | wildflower / herb / fern — see below |
| Grass / sedge / rush tuft | `buildGrassGeo` | dense fan of flat arching blades *(V1.92)* | a grass, sedge, or rush |
| Aquatic / emergent clump | `buildAquaticGeo` | tall erect strap leaves *(V1.92)* | an aquatic (Cattail, Great Bulrush) |
| Groundcover mat | `buildGroundcoverGeo` | low scatter of textured domes | Bearberry |
| Vine | `buildVineGeo` | sprawling/twining leafy stems *(V1.99)* | Blue Clematis, vetch, peavine |

Herbaceous plants (wildflower / herb / fern) are built to their **growth form**
(`HERB_FORMS`, keyed by genus via `_HPROF`, else inferred from flower form +
aspect) — leaves placed where the real plant carries them:

| Form | Looks like | Genera |
|------|-----------|--------|
| `erect` | tall leafy stem, lance leaves spiralling up | Fireweed, goldenrod, penstemon, blazingstar, lupine, paintbrush |
| `ferny` | low mound of fine feathery foliage + flat stalks | Yarrow, tansy, meadow rue, columbine, cinquefoil |
| `rosette` | basal leaf rosette under wiry flower stalks | Fleabane, arnica, evening primrose, avens, shooting star |
| `clump` | bushy upright leafy clump | Asters, sunflower, milkweed, bee balm |
| `grassy` | upright strap / linear basal leaves | Onion, harebell, blue-eyed grass, lily, camas |
| `mat` | low cushion of basal leaves | Pussytoes, umbrella-plant, violets, moss campion |
| `fern` | arching divided fronds | ferns |

Everything stays procedural + instanced + archetype-cached; genus changes
silhouette and colour, not per-frame cost. The **Detail** toggle scales build-time
density (blade / blob / leaf / tier counts) for weak hardware.

## What V2.33 added to this vocabulary

The procedural set here is the permanent fallback, so it moves with the baked
archetypes wherever the difference would be visible:

- **Shrub silhouettes are eight, not five** — `arching`, `prostrate` and
  `upright` joined the genus-derived five, and a shrub picks its silhouette from
  its own recorded `branching` before falling back to its genus
  (`02-plants.js shrubFormFor`). Creeping juniper and creeping Oregon-grape were
  drawing as upright bushes; that was a correctness bug, not a refinement.
- **Tree profiles resolve by SPECIES first** — `TREE_SPECIES_PROFILES` grew from
  the one balsam poplar to jack pine, water birch, Evans cherry and Douglas-fir.
- **Ten surface classes** (`01b-surface.js`) instead of one bark grain and one
  leaf mottle, picked per species from `bark_texture` / `leaf_surface`.
- **Eight graminoid seed heads** (`12-seedheads.js`), keyed on
  `inflorescence_form` and drawn as oriented quads with the flower system's
  attitude machinery, so a nodding brome nods. They are held from flowering
  through winter rather than only in bloom, because that persistence is most of
  what a prairie grass gives a yard from October to April.
- **Fauna builds** — four bee body plans, four lepidopteran wing plans, three
  bird outlines, selected by `app.build` from `src/scene_wildlife.py`. The
  procedural critters draw the colourway only; the baked ones carry the shape.
- **Sway follows the site's real wind** (`applySceneWind`), damped inside the
  design's own windbreaks, with each material's wind constant acting as a
  stiffness class.

## Regenerating the gallery & images

The gallery scenes and the flower sheet are generated — re-run these if the
sprite set or seed data changes:

```bash
python scripts/make_gallery_scene.py      # → html/sprite_gallery_scenes.json
python scripts/render_flower_sprites.py   # → docs/3d/flower_sprites.png
```

`make_gallery_scene.py` builds each specimen scene through the real
`src.scene_contract.build_scene` (so every field matches the contract the viewer
reads); `render_flower_sprites.py` extracts the real `makeFlowerTexture` from
`scene3d.html` (no duplication) and renders it with headless Chromium.
