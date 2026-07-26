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

import math
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
    "spruce": 3.3,        # Picea glauca 25/7.5, P. mariana 15/4.5 — SAME aspect
    "fir": 2.7,           # Abies balsamea 20/7.5
    "douglas": 4.0,       # Pseudotsuga menziesii 30/7.5 — much taller and tighter
    "pine": 4.2,          # Pinus contorta 25/6 — the lodgepole spire
    "pine_jack": 3.3,     # Pinus banksiana 15/4.5 — shorter and scraggly
    "larch": 3.3,         # Larix laricina 20/6
    "def_conifer": 3.0,
    # deciduous
    "aspen": 2.7,         # Populus tremuloides 20/7.5
    "poplar": 2.1,        # Populus balsamifera 25/12 — broader
    "birch": 2.7,         # Betula papyrifera 20/7.5
    "birch_water": 1.8,   # Betula occidentalis 8/4.5 — a multi-stemmed clump
    "oak": 1.2,           # Quercus macrocarpa 18/15 — the broad one
    "willow": 1.8,        # Salix bebbiana 8/4.5
    "cherry": 1.8,        # Prunus pensylvanica 8/4.5 — the wild one
    "cherry_orchard": 1.0,  # Prunus cerasus 'Evans' 4/4 — low and spreading
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
    "vase": 1.07,        # saskatoon, chokecherry, hazelnut, green alder
    "spreading": 0.86,   # dogwood, viburnum, buckthorn, Labrador tea
    "mound": 0.73,       # rose, spirea, snowberry, blueberry
    "thicket": 0.86,     # the upright currants
    "irregular": 0.80,   # sagebrush, buffaloberry
    # V2.33 (F64): silhouettes the genus table could not express, selected from
    # the species' own recorded `branching` — see shrub_form_for below.
    "arching": 0.67,     # raspberry, thimbleberry, gooseberry, the bowing currants
    "prostrate": 0.67,   # creeping juniper, creeping Oregon-grape, false box
    "upright": 1.33,     # pussy willow, hawthorn, thinleaf alder, buffaloberry
}

HERB_ASPECT = {
    "erect": 1.20, "ferny": 1.19, "rosette": 0.83, "clump": 1.11,
    "grassy": 1.33, "mat": 0.42, "fern": 1.00,
}

# grass/sedge/rush share the grass tuft, so its figure is theirs pooled. This
# stays the representative figure for the family (the manifest-level target and
# the groundcover's single aspect); the per-unit targets are the axis below.
LAYER_ASPECT = {"grass": 1.31, "aquatic": 1.20, "vine": 1.72,
                "groundcover": 0.42}

# ── the layer aspect axis (V2.33, F65) ──────────────────────────────────────
#
# `LAYER_ASPECT["grass"]` is 1.31, the POOLED figure over grasses, sedges and
# rushes — and the catalogue's graminoids run 0.56 (golden sedge) to 2.67
# (mountain brome). The viewer scales an instance by
# (canopy_m / 2·half_width, height_m, …), so every species away from the pooled
# figure was being stretched by the ratio between the two: up to 2x on Canada
# wild rye and big bluestem. That is precisely the distortion the unit frame
# exists to prevent, and `conventions` used to call the residual "small …
# natural variation" — at this spread it is not.
#
# The fix is the same variant axis herbs, shrubs and groundcover already have,
# on a different character. It costs NOTHING in payload: grass, aquatic and vine
# already shipped three units each, chosen by a plant-id hash — three random
# draws of one shape. They become three real shapes, chosen by the species.
#
# Class targets are the MEDIAN of each tertile of the real spread, and the
# breaks are the tertile boundaries, so each class stands for a third of the
# catalogue and no species sits further than half a class from its own figure.
LAYER_ASPECT_CLASSES = {
    "grass":   (1.07, 1.33, 1.78),
    "aquatic": (0.55, 1.00, 1.78),   # lo pulled up off the floating-leaf floor
    "vine":    (1.47, 1.72, 3.00),
}
LAYER_ASPECT_BREAKS = {
    "grass":   (1.17, 1.50),
    "aquatic": (0.67, 1.33),
    "vine":    (1.67, 2.00),
}
# Which layer kinds carry the axis. Groundcover is absent on purpose: its
# variant axis is already (blade × grain), it is the one layer looked straight
# down at, and its species' aspects cluster tightly.
ASPECT_LAYERS = tuple(LAYER_ASPECT_CLASSES)


def layer_aspect_class(kind, height_m, canopy_m):
    """0 low · 1 medium · 2 tall, from a species' own height ÷ canopy.

    Unknown or unusable dimensions land on the middle class, which is the
    pooled figure the archetype carried before this axis existed.
    """
    breaks = LAYER_ASPECT_BREAKS.get(kind)
    if not breaks:
        return 1
    try:
        h = float(height_m or 0)
        c = float(canopy_m or 0)
    except (TypeError, ValueError):
        return 1
    if h <= 0 or c <= 0:
        return 1
    ratio = h / c
    return 0 if ratio < breaks[0] else (1 if ratio < breaks[1] else 2)


def aspect_variant_key(index):
    """Stable name for one aspect-axis unit."""
    return f"aspect_{int(index)}"


# Typical leaf (or needle) length in cm for the species that map to each
# archetype — the median of their `leaf_size_cm` in data/plants_master.json,
# authored in scripts/seed_woody_morphology.py. This is what lets a bur oak's
# foliage read coarse and a spruce's fine at the same crown size: without it,
# every archetype carried identically-sized leaf masses and species identity
# stopped at colour.
LEAF_CM = {
    "spruce": 1.5, "fir": 2.0, "douglas": 2.5, "pine": 5.0, "pine_jack": 3.0,
    "larch": 2.5, "def_conifer": 2.0,
    "aspen": 6.0, "poplar": 10.0, "birch": 8.0, "birch_water": 4.0,
    "oak": 20.0, "willow": 6.0, "cherry": 8.0, "cherry_orchard": 7.0,
    "apple": 8.0, "def_slender": 7.0, "def_oval": 7.0, "def_spreading": 7.0,
    "vase": 8.0, "spreading": 6.0, "mound": 5.5, "thicket": 6.0,
    "irregular": 4.0, "arching": 6.0, "prostrate": 3.0, "upright": 7.0,
}

# The blade OUTLINE for each deciduous tree archetype — the mode of
# `leaf_shape` over the species that map to it in data/plants_master.json,
# exactly as LEAF_CM is their median leaf length.
#
# Since V2.29 a deciduous crown's outermost clumps are stamped as real leaf
# cards rather than faceted ellipsoids, so this is what puts a species' leaf
# into its SILHOUETTE. It is the difference the audit found missing between
# aspen, birch, cherry and apple, which until now differed only in bark hex
# and crown proportion — a genuine "grown, not designed" tell (P2), and one a
# viewer at yard distance can actually resolve, because the crown edge is where
# a tree is read from.
#
# Conifers are absent on purpose: their foliage is needle skirts, not clumps,
# and a needle card at crown scale is a sub-pixel sliver.
DECID_LEAF_SHAPE = {
    "aspen": "orbicular",    # Populus tremuloides — the ROUND one
    "poplar": "ovate",       # Populus balsamifera
    "birch": "ovate",        # Betula papyrifera
    "birch_water": "ovate",  # Betula occidentalis — same outline, half the size
    "oak": "lobed",          # Quercus macrocarpa — the deep-lobed one
    "willow": "elliptic",    # Salix bebbiana (narrow for a broadleaf)
    "cherry": "lanceolate",  # Prunus pensylvanica — the wild one
    "cherry_orchard": "ovate",   # Prunus cerasus 'Evans'
    "apple": "elliptic",     # Malus domestica
    "def_slender": "ovate", "def_oval": "ovate", "def_spreading": "ovate",
}

# Representative mature height in metres for each tree archetype — the median
# of `mature_height_m` over the species that map to it, exactly as LEAF_CM is
# their median leaf length and CROWN_ASPECT their median proportion.
#
# It exists so a leaf can be sized against the tree that carries it. Leaf length
# alone says nothing: a 20 cm bur oak leaf on an 18 m tree and an 8 cm apple leaf
# on a 4.5 m tree are almost the same fraction of their tree, which is the ratio
# a viewer actually resolves.
ARCHETYPE_HEIGHT_M = {
    "spruce": 20.0, "fir": 20.0, "douglas": 30.0, "pine": 25.0,
    "pine_jack": 15.0, "larch": 20.0, "def_conifer": 20.0,
    "aspen": 20.0, "poplar": 25.0, "birch": 20.0, "birch_water": 8.0,
    "oak": 18.0, "willow": 8.0, "cherry": 8.0, "cherry_orchard": 4.0,
    "apple": 4.5,
    "def_slender": 15.0, "def_oval": 12.0, "def_spreading": 10.0,
}

# ── how big one crown-edge leaf card is (V2.33) ──────────────────────────────
#
# A deciduous crown's outermost clumps are stamped as real leaf cards, and until
# V2.33 a card's LENGTH came from the clump radius it replaced
# (`radius * CROWN_LEAF_SCALE`). Nothing tied it to the species' actual leaf, so
# every broadleaf drew cards 13-15x life size, and the bur oak — the widest crown
# (aspect 1.2, so the largest `crown_half`), the largest leaf (20 cm, pinning
# `grain_for` at its cap) and the only `lobed` outline in the table — came out at
# **2.6 m per leaf on an 18 m tree**. A rounded aspen blob at 14x still reads as
# "a clump of foliage"; an unmistakably lobed oak leaf at 14x reads as a green
# oven mitt, which is exactly what a user reported.
#
# It also silently narrowed the crown. `half_width` is measured off the WIDEST
# geometry, and the viewer divides the instance by it — so a sparse fringe of
# outsized cards sets the divisor while the dense crown sits well inside it. On
# the shipped oak the p90 foliage radius was 58% of the half-width, so an 18 m
# bur oak with a 15 m canopy rendered about 8.7 m across: a narrow column, not
# the broad spreading oak the archetype is authored as. One cause, two symptoms.
#
# The rule now mirrors the pine's NEEDLE_FASCICLE_GAIN, which solved the same
# tension from the other end: one stamp stands for a SHOOT'S worth of leaves, so
# it is drawn several leaves long — but bounded by the real leaf, not by the
# crown. The floor keeps a fine-leaved 25 m poplar from dissolving into
# sub-pixel confetti; the ceiling keeps a small tree's foliage from becoming
# boulders again.
LEAF_CLUSTER_GAIN = 4.0
CROWN_CARD_FRAC_RANGE = (0.012, 0.075)     # of unit height

# The floor is not a guess. A crown reads as foliage when its cards cover enough
# of its outer surface, and that is solvable: with `budget` triangles to spend at
# `cost` triangles a card, the number of cards is budget/cost whatever the
# rosette size, so total leaf area is (budget/cost)·len²·width_ratio and
# coverage is that over the crown's surface. Solve for len at MIN_COVER and you
# have the smallest card this archetype can afford to draw and still look leafy.
#
# It self-adjusts, which a hand-tuned floor would not: raise TRI_BUDGETS and
# every crown gets finer leaves for free; widen a crown and its floor rises
# because there is more surface to clothe. 0.45 comes from the renders — a bur
# oak at 0.52 reads as a tree and a paper birch at 0.29 reads as a bare pole
# with confetti on it.
MIN_CROWN_COVER = 0.45


def crown_card_length(archetype, *, crown_half=None, crown_frac=None,
                      leaf_cost=None, foliage_budget=None, width_ratio=None):
    """Unit-frame length of one crown-edge leaf card for a tree archetype.

    `LEAF_CLUSTER_GAIN` leaves' worth of shoot, expressed as a fraction of the
    tree's own height so it survives the unit frame — the pine's
    NEEDLE_FASCICLE_GAIN trade, made from the other end: honest proportion,
    bounded below by legibility.

    Pass the crown geometry and triangle costs and the legibility floor is
    computed from them (MIN_CROWN_COVER above); called with the archetype alone
    it returns the species-derived figure against the fixed range, which is what
    the guard test checks. An archetype with no recorded leaf falls back to the
    middle of the range (P9 — an honest default, not an invented measurement).
    """
    lo, hi = CROWN_CARD_FRAC_RANGE
    cm = LEAF_CM.get(archetype)
    h = ARCHETYPE_HEIGHT_M.get(archetype)
    want = (LEAF_CLUSTER_GAIN * (cm / 100.0) / h) if (cm and h) else (lo + hi) / 2
    if crown_half and crown_frac and leaf_cost and foliage_budget and width_ratio:
        surface = 2 * math.pi * crown_half * crown_frac
        lo = max(lo, math.sqrt(MIN_CROWN_COVER * surface * leaf_cost
                               / (foliage_budget * width_ratio)))
    return round(max(lo, min(hi, want)), 4)


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


# Where a shrub's own `branching` (schema v47) beats its genus (V2.33, F64).
#
# The same demotion 03-herbs.js:treeFormFor did to `formBias`: the species'
# recorded character wins and the genus table becomes the fallback it always
# should have been. `branching` is seeded for 100% of the catalogue's 56 shrubs,
# and three of its values name silhouettes the five genus forms simply cannot
# express —
#   prostrate  creeping juniper, creeping Oregon-grape and false box are
#              GROUND-HUGGING, and were all drawing as an upright `spreading`
#              bush; this is a correctness fix, not a refinement.
#   arching    the Ribes/Rubus canes that rise and then bow back to the ground
#              and root there. `thicket` gets the cane count right and the
#              posture wrong, and the posture is the field mark.
#   upright    a tall multi-stemmed shrub — pussy willow at 2:1, hawthorn and
#              the alders at 1.33:1 — reads as a small tree, not as the 1.11:1
#              fountain `vase` draws.
# Everything else keeps the genus form, which is the honest answer: a suckering
# snowberry really does read as a mound (P9 — an honest repeat over a
# fabricated difference).
_UPRIGHT_ASPECT = 1.25


def shrub_form_for(rec):
    """Shrub silhouette for a catalogue record.

    The species' own recorded habit wins; the genus table is the fallback, and
    an unknown genus spreads.
    """
    habit = (rec.get("branching") or "").lower()
    if habit == "prostrate":
        return "prostrate"
    if habit == "arching":
        return "arching"
    if habit == "multi_stem":
        try:
            h = float(rec.get("mature_height_m") or 0)
            c = float(rec.get("mature_canopy_m") or 0) \
                or float(rec.get("spacing_m") or 0) * 1.5
        except (TypeError, ValueError):
            h = c = 0.0
        if c > 0 and h / c >= _UPRIGHT_ASPECT:
            return "upright"
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


def aspect_for(key, unit=None):
    """Target aspect for a manifest plant key ('tree.spruce', 'herb.mat', …),
    or None for a family that doesn't declare one.

    ``unit`` is a variant key ('aspect_2', 'broad_1', 'tier0'): on a layer
    carrying the aspect axis the target is that unit's own class, since the
    whole point of the axis is that the three units are DIFFERENT shapes.
    """
    fam, _, name = str(key).partition(".")
    if fam == "layer" and name in LAYER_ASPECT_CLASSES and unit:
        if str(unit).startswith("aspect_"):
            try:
                return LAYER_ASPECT_CLASSES[name][int(str(unit).split("_")[1])]
            except (ValueError, IndexError):
                pass
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
    #
    # Raised in V2.33 with `crown_card_length`. A life-sized leaf card is a
    # quarter the length of the oversized one it replaces, so it covers a
    # sixteenth of the area and the crown needs many more of them to stay a
    # crown rather than becoming see-through — the same trade the pine made when
    # its needle pads became fascicles. The headroom was already there and
    # unspent: the shipped bur oak drew 1,796 triangles against a 3,500 budget,
    # and the sprite audit's own conclusion is that the triangle budget was never
    # what limited this library ("we are using a small fraction of what a weak
    # laptop can do"). A yard draws a handful of trees and 60-150 instanced
    # plants in total.
    "tree_tier0": 2200,
    "tree_tier1": 3600,
    "tree_tier2": 6000,
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
