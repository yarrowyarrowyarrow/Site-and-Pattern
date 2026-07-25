"""The whole generator↔viewer contract in one importable place.

Everything the 3D viewer's model loader (html/scene3d/09-models.js) relies on
is defined HERE, not scattered through the builders:

Unit frame (flora)
    Blender is Z-up; the glTF exporter converts to Y-up (export_yup).
    Every flora asset unit (one tier of a tree, one variant of a layer, one
    shrub/herb) is normalised to: base at z=0, total height exactly 1.0 —
    scaled UNIFORMLY, so the authored proportions survive. The resulting
    horizontal half-extent is the asset's own, published per unit as
    ``half_width`` in the manifest; the viewer measures the same number off
    the loaded geometry and scales instances by
    (canopy_m / (2·half_width), height_m, canopy_m / (2·half_width)) — which
    still lands the instance on exactly (canopy_m wide, height_m tall).

    WHY THIS IS NOT A FLAT 0.5 (the V2.29 fix). Until V2.28 every flora asset
    was squashed to a 1×1×1 box and then instanced by
    (canopy_m, height_m, canopy_m). Those are two different factors whenever a
    species is not as wide as it is tall — and prairie trees are emphatically
    not: height/canopy runs 1.2 (bur oak) to 4.2 (lodgepole pine) in
    data/plants_master.json. The mismatch stretched every sub-feature by that
    ratio, so a poplar's ~0.2-unit foliage clump rendered as a mass 6 m wide
    and 13 m tall — the "handful of giant leaves on a pole" look.

    The two transforms cancel — and clumps stay round — exactly when the
    asset's authored width/height equals the instance's canopy_m/height_m.
    So each archetype is now AUTHORED at the real aspect ratio of the species
    that map to it (CROWN_ASPECT below and the per-form tables in the flora
    builders), and normalisation is uniform so that authoring survives.
    Residual mismatch (one archetype serves several species, and colony
    spread widens canopy_m over time) is small and reads as natural variation.

Part names (flora)
    Woody assets carry exactly two mesh parts: PART_BARK and PART_FOLIAGE.
    Herbaceous/layer assets carry PART_FOLIAGE only. Because Blender object
    names are unique per .blend, parts nested under a tier/variant empty are
    prefixed with it: 'tier0_bark', 'v1_foliage'. Flat assets use bare names.
    A deciduous tree's bark part must be a COMPLETE winter silhouette
    (trunk + branch skeleton) — the viewer winter-hides only the foliage.

Vertex colors (flora)
    COLOR_0 is grayscale ambient occlusion (white = open, dark = crevice),
    optionally multiplied by a vertical gradient for foliage. NEVER hue: the
    viewer multiplies per-instance seasonal/health/presence tints through it.

Fauna
    One GLB per kind, authored at the same nominal in-scene proportions as
    the procedural critters (07-wildlife.js / 06-fly.js), forward = +Y in
    Blender (= -Z in the viewer), up = +Z. Named nodes are the animation and
    appearance contract (the NODE_* constants); wing objects have their
    ORIGIN AT THE HINGE with zero local rotation — the viewer wraps them in
    a pivot and drives roll. Named materials (the MAT_* constants) are
    placeholders the viewer replaces with tinted materials from the
    appearance bag; only the NAME matters. Multi-variant files (fly) prefix
    node names with the variant root: 'hover_WingL'.

Determinism
    Every builder takes random.Random(seed_for(key)) — crc32, never hash().
    Re-running the batch build must reproduce the same geometry.

The design rationale (P2 grown-not-designed silhouettes, P4 growth tiers,
P5 legible ecology, P9 archetype-not-species honesty) lives in
docs/3D_ASSETS.md and docs/DESIGN_PHILOSOPHY.md.
"""

import zlib

UNIT_HEIGHT = 1.0          # normalised asset height (Blender Z)
# The authored half-extent is whatever the archetype's real proportions give
# (see the unit-frame note above); this is only a sanity bound so a runaway
# builder can't ship a 40:1 pancake that the viewer would then divide by.
UNIT_HALF_WIDTH_MAX = 2.5

# Authored crown aspect (height ÷ full width) per tree archetype, and the same
# for the other flora families in their builder modules. Derived from the
# species that map to each archetype in data/plants_master.json:
# mature_height_m ÷ mature_canopy_m, where canopy defaults to 1.5 × spacing_m
# (db.plants.get_plant). Medians, rounded — an archetype serves several species,
# so this is a representative proportion, not a per-species claim (P9).
CROWN_ASPECT = {
    # conifers — narrow spires
    "spruce": 3.3,        # Picea glauca 25/7.5, P. mariana 15/4.5
    "fir": 3.3,           # Abies balsamea 20/7.5, Pseudotsuga menziesii 30/7.5
    "pine": 3.7,          # Pinus banksiana 15/4.5, P. contorta 25/6
    "larch": 3.3,         # Larix laricina 20/6
    "def_conifer": 3.0,
    # deciduous
    "aspen": 2.4,         # Populus tremuloides 20/7.5, P. balsamifera 25/12
    "birch": 2.2,         # Betula papyrifera 20/7.5, B. occidentalis 8/4.5
    "oak": 1.2,           # Quercus macrocarpa 18/15 — the broad one
    "willow": 1.8,        # Salix bebbiana 8/4.5
    "cherry": 1.8,        # Prunus pensylvanica 8/4.5
    "apple": 1.2,         # orchard apple — broad, low-branched
    "def_slender": 2.6,
    "def_oval": 1.8,
    "def_spreading": 1.2,
}

# The same figure for the other flora families, by the archetype key each maps
# to in the viewer (02-plants.js _SPROF genus→form, 03-herbs.js _HPROF, and the
# plant_type buckets). Medians over data/plants_master.json as above. They live
# here rather than beside their builders so tests/test_model_assets.py can check
# the shipped GLBs against them without importing bpy.
SHRUB_ASPECT = {
    "vase": 1.11,        # saskatoon, willow, hazelnut, alder, hawthorn, cherry
    "spreading": 0.80,   # dogwood, viburnum
    "mound": 0.73,       # rose, spirea, snowberry, blueberry
    "thicket": 0.83,     # currant, raspberry
    "irregular": 0.96,   # sagebrush, buffaloberry
}

HERB_ASPECT = {
    "erect": 1.20, "ferny": 1.19, "rosette": 0.83, "clump": 1.11,
    "grassy": 1.33, "mat": 0.42, "fern": 1.00,
}

# grass/sedge/rush share the grass tuft, so its figure is theirs pooled.
LAYER_ASPECT = {"grass": 1.31, "aquatic": 1.20, "vine": 1.72,
                "groundcover": 0.42}


def aspect_for(key):
    """Target aspect for a manifest plant key ('tree.spruce', 'herb.mat', …),
    or None for a family that doesn't declare one."""
    fam, _, name = str(key).partition(".")
    return {"tree": CROWN_ASPECT, "shrub": SHRUB_ASPECT,
            "herb": HERB_ASPECT, "layer": LAYER_ASPECT}.get(fam, {}).get(name)

PART_BARK = "bark"
PART_FOLIAGE = "foliage"

TIER_NODES = ("tier0", "tier1", "tier2")      # tree maturity tiers
VARIANT_PREFIX = "v"                          # layer variants: v0, v1, ...

# Triangle budgets per asset unit (a tier / variant counts alone).
# Enforced by build_all (raises) and re-checked by tests/test_model_assets.py.
TRI_BUDGETS = {
    # tier0 was 1200 when a tier meant "how grown", and a young tree was drawn
    # as a sparse adult. Tiers are size classes now, and a small conifer is a
    # DENSE little cone foliated to the ground — the opposite of sparse — so the
    # young tier needs more geometry than it used to, not less.
    "tree_tier0": 1500,
    "tree_tier1": 2200,
    "tree_tier2": 3500,
    "shrub": 2000,
    "herb": 1200,
    "layer": 900,
    "fauna": 1500,
    "structure": 1500,
}

# Fauna node names (the JS animation/appearance contract).
NODE_BODY = "Body"
NODE_HEAD = "Head"
NODE_ABDOMEN = "Abdomen"
NODE_WING_L = "WingL"
NODE_WING_R = "WingR"
NODE_WING_L2 = "WingL2"      # rear (dragonfly) pair — never flapped
NODE_WING_R2 = "WingR2"
NODE_BEAK = "Beak"
NODE_TAIL = "Tail"
NODE_EAR_L = "EarL"
NODE_EAR_R = "EarR"
NODE_SPOTS = "Spots"         # beetle spot cluster (visibility-toggled)
NODE_BANDS = ("Band0", "Band1", "Band2")   # bee stripes (visibility-toggled)

# Fauna material names → what the viewer tints them with (09-models.js
# _glbFaunaMat). The Blender materials are neutral-coloured placeholders.
MAT_FUZZ = "MatFuzz"          # bee fuzz          <- app.fuzz
MAT_DARK = "MatDark"          # dark chitin/head  <- app.dark
MAT_BODY = "MatBody"          # bird/fly/beetle   <- app.body
MAT_BELLY = "MatBelly"        # bird belly        <- app.belly
MAT_WING = "MatWing"          # translucent wing  <- app.wing
MAT_FORE = "MatFore"          # lep forewing      <- app.fore
MAT_HIND = "MatHind"          # lep hindwing      <- app.hind
MAT_EDGE = "MatEdge"          # lep wing rim      <- app.edge
MAT_FUR = "MatFur"            # mammal fur        <- app.body
MAT_MEMBRANE = "MatMembrane"  # bat wing membrane (fixed dark)

FAUNA_NOMINAL_SIZE = 1.0     # authored at procedural-critter proportions


def seed_for(key):
    """Deterministic 32-bit seed for an asset key (crc32 — hash() is salted)."""
    return zlib.crc32(str(key).encode("utf-8")) & 0xFFFFFFFF


def part_name(prefix, part):
    """Object name for a part, honouring the per-file uniqueness prefix."""
    return f"{prefix}_{part}" if prefix else part
