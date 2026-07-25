# Sprite accuracy audit — V2.29

> **Status: all five ranked improvements below have since been built, plus a
> second pass on grass, fern, pine and the poplar/aspen split.** The scores and
> per-archetype notes are kept as written, as the record of what was wrong and
> why — see [What changed](#what-changed-after-this-audit) and
> [Second pass](#second-pass--grass-fern-pine-poplar) for what each fix actually
> did, what regressed on the way, and what is still open.

An honest, per-archetype assessment of how well the 3D preview's plant sprites
represent the species they stand for, what is wrong with each, and what it would
take to fix it.

**Method.** Every archetype and flower form was rendered headless through the
real viewer (`html/sprite_gallery.html?sprite=<key>`, Chromium + SwiftShader) at
July, year 0 — the same path the in-app gallery uses, so these are the sprites
the app actually draws, not a mock-up. Renders were then compared against
reference photography for the named exemplar species. The full 441-tile contact
sheet was used to judge *distinctiveness*, which is the thing single-specimen
review cannot see.

**Scoring.** 0–10, against the question the app actually needs answered: *would
someone who knows this plant recognise it, and would they tell it apart from its
neighbours in the bed?* Not "is it photorealistic" — the target is a legible
stylised model, and a score of 7+ means the sprite is doing its job.

Two numbers, because they fail independently:

- **Fidelity** — does it look like the species?
- **Distinctness** — is it different from the sprites next to it?

---

## Summary

| | Fidelity | Distinctness |
|---|---|---|
| Deciduous trees | 6 | **3** |
| Conifers | 6 *(pine →6)* | 5 *(pine →7)* |
| Shrubs | 6 | 5 |
| Wildflower bodies | 6 | 6 |
| Flower heads | 6 | 7 |
| Grasses / sedges | 4 *(→6 mesh)* | **2** |
| Ferns | 3 *(→6)* | 5 *(→6)* |
| **Groundcover** | **1** | **1** |
| Fruit *(after this release)* | 7 | 7 |
| Creatures | 5 | 6 |

**The single worst thing in the library is the groundcover mat.** It is a lump
of untextured faceted polygons with no leaves at all — the only archetype the
V2.29 leaf work never reached. 32 species render as it, including both wild
strawberries, bearberry, bunchberry and all five creeping *Rubus*. The
strawberries you flagged look bad because the fruit was a sphere (fixed) sitting
on a green boulder (not fixed).

**The most pervasive problem is distinctness, not fidelity.** Individual sprites
are mostly acceptable; the library has far fewer distinct looks than it has
species, and the contact sheet makes that obvious in a way the old one-at-a-time
menu could not.

---

## Why so many look the same

This is a data-shape problem, not an art problem, and it is worth stating
precisely because it determines what "improving the sprites" costs.

**Trees resolve by GENUS, and there are only 11 genus profiles.**
`TREE_PROFILES` (`html/scene3d/02-plants.js:376`) maps *Picea, Abies,
Pseudotsuga, Pinus, Larix, Populus, Betula, Quercus, Salix, Prunus, Malus* to
eleven parameter bags — a bark hex, a crown-form bias, a foliage scale. Every
species inside a genus is byte-identical geometry. So:

- Pin Cherry, Chokecherry, Evans Cherry and Nanking Cherry are **one sprite**.
- Goodland Apple and Norland Apple are **one sprite**.
- Cherry and apple differ from each other only by `formBias` (oval vs spreading)
  and a bark hex — which is why, in the contact sheet, Evans Cherry, Goodland
  Apple and Norland Apple are three near-identical green blobs on trunks.

**Shrubs resolve to 5 silhouettes.** 56 shrub species → `vase | spreading |
mound | thicket | irregular`. Since V2.29 they also vary by (blade class × grain
class × arrangement), which genuinely helps, but a saskatoon and a pin cherry
sitting at similar heights still read alike because the *branch architecture* is
the same builder with different numbers.

**Herbs resolve to ~9 growth forms × 15 flower forms.** 75 of those 135 pairs
actually occur (the new **Body × flower combos** gallery group is exactly this
list). That is the real vocabulary of the app: **~75 distinguishable plant looks
for 436 species.**

That ratio is the honest headline. Nothing about triangle budgets or hardware
caused it.

---

## Per-archetype notes

### Groundcover mat — fidelity 1 · distinctness 1
A cluster of flat-shaded convex domes. No leaves, no stems, no structure. Every
groundcover in the catalogue is this shape at this colour; only the fruit
sprites differentiate them at all.
**Fix:** it needs the treatment herbs and shrubs already got — real leaves from
`leaf_shape`/`leaf_size_cm`, on runners for the stoloniferous ones. Wild
strawberry is *trifoliate* and *basal* and the data already says so; nothing
reads it. This is the highest value-per-hour fix in the library.

### Grass / sedge / rush tuft — fidelity 4 · distinctness 2 *(→ 6 · 2, see second pass)*
A narrow, near-vertical paintbrush of blades. Big bluestem is 1.6 m and should
arch out into a broad fan; this barely spreads. Blades are sub-pixel thin at
scene distance, so a tussock reads as a dark smudge. 51 grass + 20 sedge + 8
rush species share it, separated only by height and (in season) a `plume`.
**Fix:** widen the arch, thicken blades, and split at least *tussock* vs
*rhizomatous* vs *sedge triangular-culm* habits. Seed heads matter more than
blades for ID and are currently one generic plume.

### Fern — fidelity 3 · distinctness 5 *(→ 6 · 6, see second pass)*
Fronds are undivided lance blades, so the one thing that makes a fern a fern —
pinnate division — is absent. Too dark and too vertical; ostrich fern is a
broad arching vase.
**Fix:** `add_compound_leaf` already exists in the generator and is used for
pea/rose leaves. Ferns should use it (bipinnate), arch harder, and lighten.

### Pine — fidelity 4 · distinctness 6 *(→ 6 · 7, see second pass)*
Flat hexagonal plates stacked on a bare pole. Jack pine's actual character —
irregular open tufts at branch ends, scraggly asymmetry — is not there; the
plates read as a pagoda.
**Fix:** needle tufts at branch tips rather than horizontal discs. The other
conifers (spruce/fir 6/10, larch 6/10) are better because a stacked-cone skirt
genuinely is roughly right for them.

### Deciduous trees — fidelity 6 · distinctness 3
Crowns are much improved since the V2.29 rebuild (real boughs, deep crowns,
sensible trunk girth). Oak reads as a broad gnarled oak. But aspen/birch/cherry/
apple/willow differ mainly in bark hex and crown proportion.
**Fix:** the cheap win is not geometry — it is *leaf shape at silhouette scale*
and *branch angle*. Birch twigs pendulous and fine; aspen leaves fluttering flat
discs on flat petioles; oak leaves lobed and clumped. Second: apple and cherry
need blossom and fruit to be different sprites, which the new `fruit_form` now
partly delivers.

### Shrubs — fidelity 6 · distinctness 5
Much better after the double-sided fix and the ~600-leaf rebuild. Dogwood
(red stems, opposite ovate leaves) and currant (dense, lobed, berried) read
correctly. Weakest case is a tall shrub — a 5 m chokecherry spreads ~600 leaves
over a large crown and thins out.
**Fix:** scale leaf count with plant volume rather than a flat budget, and give
`vase` a distinct branch angle from `thicket`.

### Wildflower bodies — fidelity 6 · distinctness 6
The best-served group, because V2.29 gave them per-species blade class, grain
class and arrangement. Lupine (palmate), bergamot (opposite), bedstraw
(whorled), crocus (dissected) are genuinely distinguishable.
**Fix:** stems are still uniform vertical rods; real forbs branch. Basal
rosettes are too flat.

### Flower heads — fidelity 6 · distinctness 7
15 canvas sprites, camera-facing. Daisy, pea, cattail, plume and umbel read
well. The weakness is that they are **billboards**: they always face you, so a
bed of asters is a wall of discs with no sense of which way the flowers point,
and heads never nod, droop or turn.
**Fix:** the biggest single improvement is orientation — let a head have a
normal and tilt (a nodding onion should nod). That is a geometry change, not a
texture change.

### Fruit — fidelity 7 · distinctness 7 *(this release)*
Was 2/2: one sphere for all 43 species. Now nine shaped sprites driven by
`fruit_form`. Strawberries are conic and pipped, hips are urns with crowns,
chokecherry hangs in racemes, pin cherry on long pedicels.
**Remaining:** sprites are still flat billboards, and the calyx/stalk is drawn
in the same grey ramp as the flesh so it takes the fruit's tint — a green calyx
would need a second material.

### Creatures — fidelity 5 · distinctness 6
Now that they fly nose-first they read far better. Bee, butterfly, bird and
hare are distinguishable. Wings flap; bodies are simple ovoids.
**Fix:** more variation within a kind (a bumblebee is not a honeybee), and
per-species wing colour for the leps.

---

## What it would take to level up

You asked whether to move past "low-poly so it runs on any hardware" toward
something that looks better and still works on a mid-range laptop. Honest
answer: **the current bottleneck is not the hardware budget.**

The whole plant library is ~30 archetype GLBs at 1200–3600 triangles each. A
typical yard draws maybe 60–150 instanced plants — call it 300k triangles. A
2019 integrated GPU handles several million. **We are using a small fraction of
what a weak laptop can do**, so "low-poly for compatibility" is not currently
what is limiting fidelity. Variety is.

Ranked by value per unit of effort:

**1. Fix the groundcover archetype.** (Small.) One builder, reusing machinery
that already exists. Takes the worst thing in the library from 1/10 to ~6/10 and
fixes 32 species including the strawberries.

**2. Species-level leaf silhouettes for trees.** (Medium.) Trees already read
their `leaf_shape` and `leaf_size_cm` for foliage *grain*, but the foliage mass
is a faceted blob. Making the outer crown a shell of actual leaf cards shaped by
`leaf_shape` would separate birch from aspen from cherry without touching the
genus table. Costs triangles — but we have them.

**3. Give flower heads orientation.** (Medium.) Replace camera-facing points
with small oriented quads carrying a normal and tilt. Nodding onion nods,
sunflowers face the sun, spikes stand up. This is probably the largest
perceived-quality jump per triangle in the whole viewer.

**4. Break the genus tables into species tables.** (Large but shallow.) The
mechanism is already there — `TREE_PROFILES` is just a dict. The work is
*authoring*: ~17 tree and 56 shrub species each need a handful of honest
parameters. This is data entry with a botanical reference, not engineering, and
it is what actually fixes "the saskatoon looks like the pin cherry" at the root.

**5. Textures.** (Large, and the real "level up".) Everything is flat-shaded
vertex colour today — no bark texture, no leaf texture, no normal maps. A single
shared 512×512 atlas for bark/leaf/needle would transform the look at almost no
runtime cost, and is well within a mid-range laptop. This is the step that moves
the app from "diagram" to "illustration". It is also the biggest chunk of asset
work, and it is worth doing *after* 1–4, because texturing a library that has 75
distinct looks just makes 75 nicer-looking repeats.

**What I would NOT do:** raise triangle budgets much further, or chase
photorealism. The app's job (P5) is to make ecology legible, and a
clearly-drawn, correctly-proportioned, correctly-*different* plant does that
better than a detailed one. The gap between the preview and reality is currently
about **variety and structure**, and no amount of polygons closes it.

---

## What changed after this audit

All five, in the order ranked above.

**1 · Groundcover rebuilt** (`assetlib/flora_herbs.py:_layer_groundcover`).
Stolons radiating from a crown, 150–350 real leaves per mat, basal rosettes
distinguished from trailing carpets, morphology-keyed into 9 units so a
strawberry gets a trifoliate mat and a bearberry an elliptic one. Its own
triangle budget (1600) because it is the only layer you look straight down at.
**1/10 → ~6/10**, and 32 species with it.

**2 · Tree crowns carry their species' leaf**
(`assetlib/flora_trees.py`, `conventions.DECID_LEAF_SHAPE`). The outermost
clumps — the ones that make the silhouette — are rosettes of real leaf cards
instead of faceted ellipsoids; interior clumps stay spheres, where nobody can
see them and volume is cheapest. Cost-neutral by construction. Oak, birch,
aspen and cherry now differ in outline, not just bark hex.

**3 · Flower heads are oriented** (`05-flowers.js:_FLOWER_ATTITUDE`). Instanced
quads, each held at the attitude its form actually holds, with the attitude
decided by the viewpoint its texture is drawn from. Spikes stand, umbels
present upward, bells hang. Orbiting the view no longer slides the meadow
around like decals.

**4 · Species characters beat genus tables** (`03-herbs.js:treeFormFor`).
`formBias` became the fallback its own docstring always said it was rather than
an override, so a 20 m paper birch and an 8 m water birch stop being the same
shape; and `branching` (schema v47) is finally emitted and read, so a
multi-stemmed water birch or Bebb's willow is a broad clump rather than a
single-leadered spire.

**5 · Surface detail** (`02-plants.js:makeDetailTexture` / `plantMaterial`).
Procedural bark fissures and foliage mottle, sampled in object space with a
per-instance offset. Procedural rather than UV-mapped images because the baked
GLBs carry no texture coordinates and a test forbids them embedding textures —
and because instanced meshes would repeat one UV set identically anyway.

## Second pass — grass, fern, pine, poplar

**6 · The blade primitive could not arch.** `add_blade` climbed at a constant
rate (`z = height * t`) and displaced sideways: that is a *lean*, and no
authored value bends a straight line. This is why the tuft read as a shaving
brush and the fern as a bundle of uprights, and why the first attempt at
fixing the grass — widening the authored lean range — changed nothing visible.
Worse, it made the median blade *straighter*, because `_blades` normalises the
tuft against its widest member. `mesh_ops` now integrates a turning tangent
(`_arc_table` / `arc_extent`), `_blades` bisects the tuft's spread on the real
extent, and the same arc bends a compound rachis. Guarded by
`tests/test_model_assets.py:ArcBladeTest`, which fails on the old lean.

**7 · Grass — 4/10 → 6/10 for the mesh, unchanged on screen for tall species.**
The unit is now a genuine fountain (measured aspect 1.40 against a 1.31
target) and a species whose real proportions match it, like prairie dropseed
at 0.7 m × 0.9 m, renders as one. Big Bluestem still renders narrow, and that
is *correct*: it is recorded 1.6 m × 0.5 m, so the instance transform stretches
the 1.31 unit to 3.2. See "Still open" — this is an archetype/species mismatch,
not a builder bug, and no amount of tuft authoring fixes it.

**8 · Fern — 3/10 → ~6/10.** Fronds are divided (seven pinna pairs, overriding
the three that `compound_pinnate` means for a rose) and arched. Two things had
to change beyond dividing them: the rachis needed the arc, and the pinnae
needed to stand out square from it (`leaflet_flare`) — at the rose's forward
angle a divided frond is still a narrow brush, because leaflets pointing where
the rachis points add nothing to the silhouette. The plant is still thin: 16
fronds is what the 1200-triangle herb budget buys at 68 triangles a frond.

**9 · Pine — 4/10 → ~6/10, after a regression.** Needle fascicles replaced the
flat ellipsoid pads, and the first cut was *worse than what it replaced*: at
true proportion (3% of length) a jack pine's needle is sub-pixel on a 15 m tree,
so the crown aliased into a bottle brush of dark wires. One ribbon now stands
for a shoot's spray of needles (`NEEDLE_FASCICLE_GAIN`), and the crown carries
23 tufts instead of 14. 2120 triangles against a 3500 budget.

**10 · Poplar split from aspen** — the one genuinely unambiguous win here.
`tree.poplar` is its own archetype with its own crown aspect (2.1 vs the aspen's
2.7) and leaf (ovate 10 cm vs orbicular 6 cm), reached by species rather than
genus. Balsam poplar is now a broad dense crown and trembling aspen a slender
open one; they were pixel-identical before.

### Still open

- **Archetype aspect vs species aspect.** `LAYER_ASPECT["grass"]` is 1.31, the
  pooled figure for grasses, sedges and rushes; the catalogue's grasses run from
  0.67 (Rocky Mountain fescue) to 2.67 (Canada wild rye). The instance transform
  makes up the difference by stretching, which is exactly the distortion the
  unit frame exists to prevent — up to 2.4× on Big Bluestem. `conventions.py`
  calls the residual "small ... natural variation"; at this spread it is not.
  The fix is an aspect variant axis on the layers, like the grain axis
  groundcover already has.
- **Fern density** is budget-bound, not shape-bound. A lusher crown needs either
  a higher herb budget or a cheaper frond.
- **Per-species leaf outlines on trees** are still archetype-level everywhere
  except the poplar/aspen split done here: `DECID_LEAF_SHAPE` is the mode over
  the species mapping to each archetype. Doing it generally means a blade-class
  variant axis on the tree archetypes, roughly doubling the baked tree units.
- **Grass seed heads** — a big bluestem's turkey-foot inflorescence is most of
  how it is identified in the field, and there is no geometry for it at all.
- **Creature variety within a kind** — a bumblebee is not a honeybee.

## Verification note

Scores in the per-archetype table come from close inspection of individual
renders for: pine, spruce, oak, aspen, grass, fern, groundcover, daisy, saskatoon,
dogwood, currant, rose, strawberry, chokecherry and pin cherry; plus the full
441-tile contact sheet for cross-comparison. The remaining archetypes were judged
from the contact sheet alone, at thumbnail scale — adequate for distinctness,
weaker evidence for fidelity, and flagged here rather than presented as equally
grounded.
