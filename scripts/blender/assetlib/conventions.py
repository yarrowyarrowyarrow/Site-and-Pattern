"""The whole generator↔viewer contract in one importable place.

Everything the 3D viewer's model loader (html/scene3d/09-models.js) relies on
is defined HERE, not scattered through the builders:

Unit frame (flora)
    Blender is Z-up; the glTF exporter converts to Y-up (export_yup).
    Every flora asset unit (one tier of a tree, one variant of a layer, one
    shrub/herb) is normalised to: base at z=0, total height exactly 1.0,
    horizontal half-extent 0.5. The viewer re-normalises with the same math
    (normalizeUnit) as belt-and-braces, then scales instances by
    (canopy_m, height_m, canopy_m) — identical to the procedural archetypes.

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
UNIT_HALF_WIDTH = 0.5      # normalised horizontal half-extent (X and Y)

PART_BARK = "bark"
PART_FOLIAGE = "foliage"

TIER_NODES = ("tier0", "tier1", "tier2")      # tree maturity tiers
VARIANT_PREFIX = "v"                          # layer variants: v0, v1, ...

# Triangle budgets per asset unit (a tier / variant counts alone).
# Enforced by build_all (raises) and re-checked by tests/test_model_assets.py.
TRI_BUDGETS = {
    "tree_tier0": 1200,
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
