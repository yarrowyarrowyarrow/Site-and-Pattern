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


# Typical leaf (or needle) length in cm for the species that map to each
# archetype — the median of their `leaf_size_cm` in data/plants_master.json,
# authored in scripts/seed_woody_morphology.py. This is what lets a bur oak's
# foliage read coarse and a spruce's fine at the same crown size: without it,
# every archetype carried identically-sized leaf masses and species identity
# stopped at colour.
LEAF_CM = {
    "spruce": 1.5, "fir": 2.2, "pine": 4.0, "larch": 2.5, "def_conifer": 2.0,
    "aspen": 8.0, "birch": 6.0, "oak": 20.0, "willow": 6.0, "cherry": 8.0,
    "apple": 8.0, "def_slender": 7.0, "def_oval": 7.0, "def_spreading": 7.0,
    "vase": 8.0, "spreading": 6.0, "mound": 5.5, "thicket": 6.0,
    "irregular": 4.0,
}

# A leaf mass in this visual language is a branch-end CLUSTER, not one leaf, so
# it tracks leaf length sub-linearly — and the reference is the median woody
# leaf (7 cm), which keeps the existing look as the centre of the range. The
# clamp stops a 50 cm yucca blade or a 1.2 cm juniper scale from producing a
# mass that is all crown or invisible.
LEAF_REFERENCE_CM = 7.0
# The upper bound is held at 1.35 rather than following the curve to 1.7 for a
# bur oak: past that the masses stop reading as coarse foliage and start reading
# as boulders in the crown. The coarse-vs-fine signal survives the cap.
GRAIN_RANGE = (0.62, 1.35)


def grain_for(archetype):
    """Foliage-mass size multiplier for an archetype, from its species' leaf
    length. 1.0 is the median woody leaf; bigger is coarser."""
    cm = LEAF_CM.get(archetype)
    if not cm:
        return 1.0
    g = (cm / LEAF_REFERENCE_CM) ** 0.5
    return round(max(GRAIN_RANGE[0], min(GRAIN_RANGE[1], g)), 3)


# Herb/shrub archetypes are shared across every species that maps to them, so a
# per-species leaf size cannot be a per-instance scale (instancing gives one
# 3-component scale, and using it would stretch the whole plant, not the leaves).
# Instead each family ships three GRAIN CLASSES and a species picks one from its
# leaf length relative to its own height — the ratio the renderer can actually
# show. Thresholds are the tertiles of leaf_size_cm / mature_height_m across the
# catalogue's herbaceous rows.
GRAIN_CLASSES = 3
# Tertiles of leaf_size_cm / mature_height_m across the catalogue, PER FAMILY.
# A shrub is a metre or three tall with leaves a few centimetres long, so its
# ratios sit an order of magnitude below a forb's: one shared threshold put 52
# of 55 shrubs in the same class and made the whole mechanism a no-op for them.
_GRAIN_BREAKS = {
    "herb":  (0.133, 0.200),      # 229 rows, ratios 0.025 – 1.00
    "shrub": (0.027, 0.047),      # 55 rows,  ratios 0.008 – 0.56
    # 32 rows, ratios 0.010 – 1.50 (median 0.200). A groundcover's leaf is a
    # LARGE fraction of its height — a strawberry leaf is a third of the plant —
    # so its breaks sit an order of magnitude above a shrub's.
    "groundcover": (0.120, 0.300),
}
# Leaf-size multiplier applied to a form's authored blade for each class.
GRAIN_LEAF_SCALE = (0.62, 1.0, 1.55)


# How a blade is BUILT, as opposed to its exact outline. Fourteen leaf shapes
# cannot each get a baked archetype, but they collapse cleanly into four
# construction classes, and that is what a viewer at yard scale can show.
BLADE_CLASSES = ("narrow", "broad", "cut", "compound")


def blade_class(leaf_shape):
    """Construction class for a recorded ``leaf_shape``. Unknown → 'broad',
    which is the profile the herb forms carried before there was any data."""
    sh = (leaf_shape or "").lower()
    if sh in ("trifoliate", "compound_pinnate", "compound_palmate", "bipinnate"):
        return "compound"
    if sh in ("linear", "strap", "needle", "awl", "scale", "lanceolate"):
        return "narrow"
    if sh in ("lobed", "pinnatifid", "sagittate"):
        return "cut"
    return "broad"


# The representative outline each class is baked with — one blade profile per
# class, since the class is what the geometry actually differs by.
#
# Each entry MUST be the member whose width/length sits at the class median
# (tests/test_model_assets.py checks this against the catalogue). Getting it
# wrong is not a rounding error: 'narrow' was baked as `linear` (width/length
# 0.06) while 65 of its 100 species are `lanceolate` (0.22) and only 22 truly
# linear — so the largest group of wildflowers, asters and goldenrods and
# penstemons among them, drew leaves 3.7x too narrow and rendered as thick bare
# stems with invisible threads on them. A class stands for its members, so its
# representative has to be typical of them, not the extreme of the range.
BLADE_SHAPE = {"narrow": "lanceolate", "broad": "ovate", "cut": "lobed",
               "compound": "compound_pinnate"}


def variant_key(blade, grain):
    """Stable name for one (blade class, grain class) archetype variant."""
    return f"{blade}_{int(grain)}"


def grain_class(leaf_size_cm, height_m, family="herb"):
    """0 fine · 1 medium · 2 coarse, from a species' leaf length against its own
    height — the ratio the renderer can actually show. Unknown data lands on
    medium, i.e. exactly today's look."""
    try:
        cm = float(leaf_size_cm or 0)
        h = float(height_m or 0)
    except (TypeError, ValueError):
        return 1
    if cm <= 0 or h <= 0:
        return 1
    lo, hi = _GRAIN_BREAKS.get(family, _GRAIN_BREAKS["herb"])
    ratio = (cm / 100.0) / h
    if ratio < lo:
        return 0
    return 1 if ratio < hi else 2


# ── which archetype a catalogue record maps to ───────────────────────────────
#
# The generator's copy of the viewer's herbFormFor() / shrubProfileFor(), living
# here beside the aspect tables (whose keys ARE the form vocabulary) rather than
# beside the builders — it is bpy-free record-reading, and putting it in a module
# that imports bmesh would make the "every species has a baked variant" guard in
# tests/test_model_assets.py unrunnable without Blender.

# Habits the seed data records that this archetype set has no distinct form for.
# Mirrors _FORM_ALIAS in html/scene3d/03-herbs.js and flora_herbs.
HERB_FORM_ALIAS = {"cushion": "mat", "succulent": "mat", "sprawling": "mat",
                   "vining": "clump", "tussock": "grassy", "emergent": "grassy",
                   "floating": "mat"}


def herb_form_for(rec):
    """Herb archetype for a catalogue record. The species' own recorded habit
    wins (schema v48); ferns are their own form; anything unrecorded lands on the
    generic clump."""
    if rec.get("plant_type") == "fern":
        return "fern"
    gf = (rec.get("growth_form") or "").lower()
    if gf in HERB_ASPECT:
        return gf
    return HERB_FORM_ALIAS.get(gf, "clump")


# Genus → silhouette, mirroring _SPROF in html/scene3d/02-plants.js.
SHRUB_GENUS_FORM = {
    "cornus": "spreading", "salix": "vase", "amelanchier": "vase",
    "prunus": "vase", "corylus": "vase", "alnus": "vase", "crataegus": "vase",
    "viburnum": "spreading", "rosa": "mound", "spiraea": "mound",
    "symphoricarpos": "mound", "vaccinium": "mound", "ribes": "thicket",
    "rubus": "thicket", "artemisia": "irregular", "shepherdia": "irregular",
}


def shrub_form_for(rec):
    """Shrub silhouette for a catalogue record; unknown genera spread."""
    genus = (rec.get("scientific_name") or "").split(" ")[0].lower()
    return SHRUB_GENUS_FORM.get(genus, "spreading")


# family name → (the plant_type values it covers, its form resolver). One place
# for "what does this record map to", so a consumer never re-derives the pairing.
# family -> (plant_types it covers, record -> form, manifest key prefix).
# The prefix is here rather than assumed to equal the family name because
# groundcover's units live under `layer.groundcover` (it is a layer archetype)
# while its variant axis is a family's (blade × grain). Both the manifest
# builder and tests/test_model_assets.py read this one definition, so a
# family whose assets live somewhere unexpected cannot silently look up a
# key that was never baked.
FAMILY_FORMS = {
    "herb": (("wildflower", "herb", "fern"), herb_form_for, "herb"),
    "shrub": (("shrub",), shrub_form_for, "shrub"),
    # One form, but 32 species with 14 distinct leaf outlines between them, so
    # the variant axis that matters here is blade × grain, not silhouette.
    "groundcover": (("groundcover",), lambda _rec: "groundcover", "layer"),
}


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
    # A shrub is ONE unit serving 0.3 m sagewort to 5 m chokecherry, with no
    # size tiers to spread the cost over, and since V2.29 its foliage is real
    # leaves rather than 20-triangle masses. At 2000 the vase/spreading/
    # irregular forms could only afford ~180 leaves, which on a 4 m saskatoon
    # reads as bare canes with flecks on them. A tree of that size gets
    # tree_tier1 = 2200, and shrubs sit at the fringe of a bed where they are
    # looked AT rather than under, so they earn tier2-ish geometry. Paired with
    # the 4-triangle shrub blade (flora_shrubs.LEAF_SEGMENTS) this is ~600-700
    # leaves per shrub instead of ~180.
    "shrub": 3600,
    "herb": 1200,
    "layer": 900,
    # Groundcover is its own budget because it is the only layer you look
    # straight DOWN at from a metre away — it carpets the front of a bed, so its
    # leaves are the closest geometry in the scene. At the shared 900 it was
    # ~17 faceted domes; at 1600, with 4-triangle blades, it is ~350 real
    # leaves, which is what makes a mat read as a mat.
    "groundcover": 1600,
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
