# 3D Sprites — reference & gallery

Every unique "sprite" the 3D viewer (`html/scene3d.html`) can render, in two
families: **plant-body geometry archetypes** (procedural meshes) and **flower
billboard sprites** (camera-facing textured points). This doc is the catalogue;
the **live gallery** below lets you rotate and inspect each one.

## See them live

The gallery embeds the real viewer and renders one specimen per sprite — drag to
orbit, scroll to zoom, pick any item from the sidebar.

```bash
# from the repo root
python -m http.server 8000
# then open:
#   http://localhost:8000/html/sprite_gallery.html
```

Deep-link a single sprite with `?sprite=KEY`, e.g.
`…/sprite_gallery.html?sprite=flower_cattail` or `?sprite=tree_spreading`.

![All archetypes in the gallery](3d/sprite_gallery_overview.png)

## Flower sprites

These are drawn by `makeFlowerTexture()` and rendered in each plant's real
`flower_color`, only while the scene month falls inside the plant's bloom window.
The image below is the **actual** `makeFlowerTexture` output (extracted from
`scene3d.html`), tinted with a representative real colour per form.

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

## Plant-body geometry archetypes

Procedural meshes, bucketed by `plant_type` in `buildPlants()` → `byKind`. Trees
are built per **crown class** (conifer vs deciduous) × **crown form** (slender /
oval / spreading, chosen from the plant's height-to-canopy aspect) × maturity
tier × per-individual sub-variation.

| Archetype | Builder | Looks like | Place to test |
|-----------|---------|-----------|---------------|
| Conifer tree | `buildConiferGeo` | stacked drooping cones | a tree marked evergreen (White Spruce, Balsam Fir) |
| Deciduous tree | `generateDaVinciTree` | branch skeleton + foliage crown | any deciduous tree (Aspen = slender, Bur Oak = spreading) |
| Shrub | `buildShrubGeo` | bushy cluster of merged domes | any shrub (Beaked Hazelnut) |
| Perennial / herb clump | `buildPerennialGeo` | thin stems + leaf rosettes over a mound | a wildflower, herb, or **fern** (shares this) |
| Grass / sedge / rush tuft | `buildGrassGeo` | dense fan of flat arching blades *(V1.92)* | a grass, sedge, or rush (Big Bluestem) |
| Aquatic / emergent clump | `buildAquaticGeo` | tall erect strap leaves *(V1.92)* | an aquatic (Cattail, Great Bulrush) |
| Groundcover mat | `buildGroundcoverGeo` | low scatter of textured domes | a groundcover (Bearberry) |
| Vine | `GEO.cone` | slim swaying cone | a vine (Blue Clematis) |

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
