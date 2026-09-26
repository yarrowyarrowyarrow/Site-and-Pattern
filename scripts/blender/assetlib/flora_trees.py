"""Tree archetype builders (Z-up, unit frame; see conventions.py).

Mirrors the viewer's archetype vocabulary rather than inventing a new one
(P9 — no species detail the data doesn't support): conifer KINDS
spruce/fir/pine/larch/def_conifer, deciduous GENUS profiles
aspen/birch/oak/willow/cherry/apple plus the three form-shaped defaults
def_slender/def_oval/def_spreading. Parameters echo the tuned values in
html/scene3d/02-plants.js (_PROF/CONIFER_KINDS/DECID_FORMS) so a GLB tree
reads as the same species the procedural one did — just better built:
real whorled boughs instead of cone stacks, a branching skeleton whose
foliage clumps sit ON the branches, a complete winter silhouette.

build_tree(archetype, tier, rng) → {'bark': obj, 'foliage': obj}
(objects are UNPARENTED and UNNORMALISED — build_all owns naming, tier
parenting, unit_frame, AO and export).
"""

import math

# `bpy` MUST be imported before `bmesh` and `mathutils`. Under the standalone
# bpy wheel those are C extensions that only become importable once bpy's
# __init__ has run its path setup, so the alphabetical order isort wants makes
# this module unimportable on its own — it works only because build_all imports
# bpy first. Same fix, same reason, as the note in mesh_ops.py.
import bpy                                        # isort: skip
import bmesh                                      # noqa: I001
from mathutils import Matrix, Vector

from .mesh_ops import (ICO_TRIS, add_blade_or_leaf, add_cone, add_cone_between,
                       add_ellipsoid, bm_to_object, leaf_extent, leaf_tris,
                       leaf_width_for, place, shape_to_aspect,
                       thin_groups_to_budget)

# A deciduous crown is stamped as rosettes of real leaf cards. The crown edge is
# where a tree is read from at yard distance, and until V2.29 every broadleaf's
# edge was the same ball of facets — aspen, birch, cherry and apple differed only
# in bark hex and crown proportion, which the sprite audit scored 3/10 for
# distinctness.
CROWN_LEAF_SEGMENTS = 2                   # 4 triangles a leaf

# How densely a rosette fills the clump it stands in, and the bounds on how many
# cards that is worth. Card length comes from the species' real leaf
# (conventions.crown_card_length) rather than from the clump radius, so the
# count has to make up the coverage the old oversized cards got for free: a card
# a quarter as long covers a sixteenth of the area. Squared, therefore, not
# linear. The cap is what stops a 25 m poplar (fine leaves, wide crown) asking
# for four hundred cards on one branch tip and starving the rest of the crown.
CROWN_LEAF_COVER = 1.5
CROWN_LEAVES_PER_CLUMP = (5, 11)
# A deciduous crown is ALL leaves now — no faceted filler ellipsoids anywhere in
# it. They existed because leaves used to be scarce and expensive, and they were
# invisible only because the oversized leaf paddles hung in front of them: take
# the paddles away and the crown turns out to have been a stack of 20-triangle
# boulders the whole time, and they render lighter than the leaves so they read
# as geometric blocks in the canopy. At life-sized leaves the budget buys 600+
# of them, which is enough to fill the volume as well as clothe the surface, so
# the sphere has nothing left to do. Interior clumps keep a tighter, less drooped
# fan than the crown edge — inside a canopy leaves are packed, not hanging.
INNER_FAN_TILT = (0.75, 0.55)             # base tilt, fan spread (rad)
OUTER_FAN_TILT = (1.05, 0.75)
INNER_MASS_PULL = 0.35                    # toward the bough, away from the edge
# Card origins are jittered inside the clump rather than all radiating from its
# centre, so a rosette of small leaves still fills the volume the clump stands
# for. Fraction of the clump radius.
CROWN_LEAF_SCATTER = 0.62

# ── parameter tables (echo 02-plants.js) ─────────────────────────────────────

# Whorls by tier are DENSE AT EVERY AGE. A young spruce is not a sparse adult —
# it is a small dense cone foliated to the ground, and the thing that actually
# changes with age is how far up the clear bole reaches and how open the crown
# gets. Tier 0 used to carry 3–5 whorls, which on a narrow (3.3:1) crown drew a
# 5 m sapling as a bare mast with a few twigs.
CONIFER_KINDS = {
    # whorls by tier          baseR  droop  spire  boughs  lift  base of crown
    "spruce":      {"whorls": (9, 12, 15), "base_r": 0.34, "droop": 0.16,
                    "spire": 1.15, "boughs": 9, "lift": 0.04,
                    "crown_base": (0.04, 0.08, 0.14)},
    "fir":         {"whorls": (10, 13, 16), "base_r": 0.30, "droop": 0.08,
                    "spire": 1.4, "boughs": 9, "lift": 0.02,
                    "crown_base": (0.04, 0.08, 0.16)},
    # Douglas-fir: half again as tall as a balsam fir on the same footprint
    # (30 m against 20 m), so a tighter, denser, more sharply-spired column with
    # a longer clear bole. Split from `fir` in V2.33 because pooling them put
    # both at a 3.3 aspect and neither is 3.3.
    "douglas":     {"whorls": (12, 16, 20), "base_r": 0.26, "droop": 0.06,
                    "spire": 1.5, "boughs": 8, "lift": 0.02,
                    "crown_base": (0.05, 0.12, 0.24)},
    "larch":       {"whorls": (6, 8, 10), "base_r": 0.36, "droop": 0.22,
                    "spire": 0.7, "boughs": 7, "lift": 0.05,
                    "crown_base": (0.06, 0.14, 0.26)},
    "def_conifer": {"whorls": (8, 10, 13), "base_r": 0.40, "droop": 0.14,
                    "spire": 1.0, "boughs": 7, "lift": 0.05,
                    "crown_base": (0.05, 0.10, 0.18)},
}

# `bole` is the first trunk segment's length and `len_scale` the exponent that
# shortens each child, so together they set how much of the tree is bare trunk
# versus crown. Both were tuned for a look, and the look was wrong: a user's
# screenshot showed an aspen whose live crown was the top 27% of its height above
# a trunk like a concrete pillar. Real open-grown prairie trees carry a live
# crown over 50-70% of their height, so the branch cloud has to START low and
# the children have to stay long enough to fill it. CROWN_FRAC below records the
# target each form is tuned against, and a test holds the built assets to it.
DECID_FORMS = {
    "slender":   {"angle": 0.52, "len_scale": 0.58, "clear_bole": 0.30,
                  "foliage_scale": 0.72, "split_bias": 0.15,
                  "bole": 0.26, "trunk_r": 0.013},
    "oval":      {"angle": 0.66, "len_scale": 0.54, "clear_bole": 0.24,
                  "foliage_scale": 0.90, "split_bias": 0.2,
                  "bole": 0.24, "trunk_r": 0.016},
    "spreading": {"angle": 0.85, "len_scale": 0.52, "clear_bole": 0.18,
                  "foliage_scale": 1.00, "split_bias": 0.3,
                  "bole": 0.22, "trunk_r": 0.030},
}

# Live crown ÷ total height that each form is tuned to, from open-grown prairie
# trees. tests/test_model_assets.py checks the shipped GLBs against these.
CROWN_FRAC = {"slender": 0.58, "oval": 0.60, "spreading": 0.68}

# `trunk_r` is the trunk's radius in unit-frame terms, i.e. HALF its diameter as
# a fraction of the tree's height. The previous single value of 0.055 made every
# trunk 11% of the tree's height thick — a 20 m aspen with a 2.6 m bole. Real
# figures: trembling aspen ~0.4 m at 20 m (2%), paper birch ~0.4 m at 16 m
# (2.5%), open-grown bur oak ~1.0 m at 14 m (7%), shrub willow ~0.3 m at 7 m (4%).
DECID_GENERA = {
    "aspen":         {"form": "slender", "foliage_scale": 0.90,
                      "trunk_r": 0.011},
    # Water birch: an 8 m MULTI-STEMMED clump with red-brown non-peeling bark,
    # against paper birch's 20 m single-leadered white spire. One genus, two
    # trees — the same call the poplar/aspen split made in V2.30, and the reason
    # `branching` was seeded in the first place.
    # V2.92: and the clump is now drawn as one — four to six slender stems
    # leaving the ground and leaning apart, where the archetype used to be a
    # single trunk like every other (the audit's finding).
    "birch_water":   {"form": "spreading", "droop_outer": 0.35,
                      "foliage_scale": 0.86, "trunk_r": 0.022,
                      "stems": (4, 6), "stem_lean": 0.34, "bole": 0.36,
                      "angle": 0.45, "rise": 0.30, "twig_r": 1.3},
    # Evans cherry: a 4 m orchard tree, low and broad, against pin cherry's
    # 8 m slender wild form.
    "cherry_orchard": {"form": "spreading", "foliage_scale": 1.0,
                       "trunk_r": 0.030},
    # Balsam poplar: bigger, broader and coarser than an aspen, on a thicker
    # trunk with dark furrowed bark rather than chalky green-white.
    "poplar":        {"form": "oval", "foliage_scale": 1.02,
                      "trunk_r": 0.018},
    "birch":         {"form": "oval", "droop_outer": 0.55, "foliage_scale": 0.82,
                      "trunk_r": 0.013},
    "oak":           {"form": "spreading", "foliage_scale": 1.06,
                      "trunk_r": 0.035},
    # Bebb's willow, recorded multi_stem: three to five stems from the base
    # under a rounded crown (V2.92; it was one trunk).
    "willow":        {"form": "oval", "droop_outer": 0.70,
                      "foliage_scale": 0.85, "trunk_r": 0.020,
                      "stems": (3, 5), "stem_lean": 0.32, "bole": 0.30,
                      "angle": 0.50, "rise": 0.30},
    "cherry":        {"form": "oval", "trunk_r": 0.018},
    "apple":         {"form": "spreading", "trunk_r": 0.026},
    "def_slender":   {"form": "slender"},
    "def_oval":      {"form": "oval"},
    "def_spreading": {"form": "spreading"},
    # ── V2.92 (F178): the trees the audit found drawn as something else ──
    # American Elm: the vase. A short trunk forks low into four or five steep
    # leaders that curve out, so the crown is widest near the top, and the
    # outer twigs hang. It was the generic oval default.
    "elm":           {"form": "oval", "trunk_r": 0.024, "bole": 0.20,
                      "leaders": {"n": (4, 5), "angle": 0.55, "length": 0.46,
                                  "area": 1.3},
                      "angle": 0.80, "rise": 0.80, "twig_r": 0.6,
                      "droop_outer": 0.75, "clear_bole": 0.46,
                      "foliage_scale": 0.95},
    # Manitoba Maple (box elder): two or three trunks from near the ground,
    # leaning apart, under a broad irregular crown of compound leaves. It was
    # the generic spreading default, one trunk and simple leaves.
    "boxelder":      {"form": "spreading", "trunk_r": 0.026, "bole": 0.36,
                      "stems": (2, 3), "stem_lean": 0.40, "split_bias": 0.40,
                      "twig_r": 1.6, "leaflet_pairs": 1, "leaflet_len": 0.5},
    # Plains Cottonwood: a massive trunk dividing into three or four heavy
    # ascending limbs, a broad open crown with sky in it, coarse leaves. It
    # borrowed the trembling aspen, stretched 1.6x sideways.
    "cottonwood":    {"form": "oval", "trunk_r": 0.032, "bole": 0.26,
                      "leaders": {"n": (3, 4), "angle": 0.50, "length": 0.30,
                                  "area": 1.4},
                      "angle": 0.80, "rise": 0.35, "clumps": 0.95,
                      "foliage_scale": 1.05},
    # Narrowleaf Cottonwood: a slender tree with upright branches and a
    # willow's leaf. It borrowed the aspen too.
    "cottonwood_narrow": {"form": "oval", "trunk_r": 0.018, "bole": 0.22,
                          "leaders": {"n": (3, 3), "angle": 0.32,
                                      "length": 0.30, "area": 1.3},
                          "angle": 0.50, "rise": 0.40, "foliage_scale": 0.90},
    # Peach-leaved Willow: one or two leaning trunks and a broad irregular
    # crown with a drooping fringe. It borrowed Bebb's willow, 1.35x wider.
    "willow_peach":  {"form": "spreading", "trunk_r": 0.024, "bole": 0.32,
                      "stems": (1, 2), "stem_lean": 0.22,
                      "droop_outer": 0.65, "foliage_scale": 0.90},
}

# Skeleton figures an archetype in DECID_GENERA may set for itself, over its
# form's (V2.92).
_FORM_OVERRIDES = ("angle", "len_scale", "clear_bole", "split_bias", "bole")

DECID_DEPTH = (3, 5, 6)                  # skeleton depth by maturity tier
# Minimum branch radius before a limb is called terminal, as a FRACTION of the
# trunk's radius. This — not the depth cap — is what actually decides how many
# branch ends a crown has: each split takes a limb to ~0.55 of its parent, so a
# cutoff stops the walk after a fixed number of levels no matter how deep it is
# allowed to go. Expressed relatively so thinning a species' trunk to its real
# girth doesn't also thin out its crown (an absolute cutoff did exactly that).
# A larger tree carries finer twigs, hence more tips to hang leaf masses on.
DECID_MIN_R_FRAC = (0.34, 0.20, 0.12)

# Foliage-clump radius as a fraction of the crown's HALF-WIDTH, by size tier.
# Two things fall out of keying it to the crown rather than to the asset height:
#   * a narrow crown gets correspondingly small leaf masses instead of clumps
#     wider than the tree (what made a poplar read as six giant leaves), and
#   * bigger trees get relatively finer foliage — a 20 m aspen carries many
#     branch-end masses, a 4 m sapling a few — so structural detail tracks
#     absolute size, not just growth year (04-quality.js tierFor).
# Reduced in V2.29 after a user's screenshot: at a quarter of the crown radius
# each, the masses read as boulders stacked on a stick rather than as foliage.
# They are now ~1/7 of the crown radius, arriving in greater numbers, which is
# what the triangle budget affords (a mass is a 20-triangle icosahedron).
FOLIAGE_FRAC = (0.30, 0.22, 0.155)
# Clumps per terminal branch by tier. Finer masses have to arrive in greater
# numbers or the crown goes see-through — the first cut of the aspect fix left
# an aspen as a bare pole with a few crumbs at the top. Affordable because a
# foliage mass is a 20-triangle icosahedron (subdiv 0, matching the viewer's own
# makeFoliageMass), not an 80-triangle one.
# Raised in V2.33: with life-sized leaves the SILHOUETTE is made of many small
# rosettes rather than a few big paddles, and covering the crown's outer surface
# matters more than density at any one point.
CLUMPS_PER_TIP = (6, 9, 12)
FOLIAGE_SUBDIV = 0

# `poplar` is split from `aspen` (V2.30). They are one genus but not one tree:
# a trembling aspen's leaf is ORBICULAR — round, on a flat petiole, which is why
# it trembles — and a balsam poplar's is ovate and half again as long, on a much
# broader crown. Splitting the archetype rather than adding a blade-class
# variant AXIS to trees is deliberate: with only 17 tree species in the whole
# catalogue, a variant axis would need a new manifest schema and four changed
# code paths to express what one more flat key already does, for +3 units.
TREE_ARCHETYPES = ("spruce", "fir", "douglas", "pine", "pine_jack", "larch",
                   "def_conifer", "juniper",
                   "aspen", "poplar", "birch", "birch_water", "oak", "willow",
                   "cherry", "cherry_orchard", "apple",
                   "def_slender", "def_oval", "def_spreading",
                   # V2.92 (F178)
                   "elm", "boxelder", "cottonwood", "cottonwood_narrow",
                   "willow_peach")


# ── conifers ─────────────────────────────────────────────────────────────────

def _bough(bm, origin, tip, girth):
    """One conifer bough: a flattened open cone from the trunk out to ``tip``.

    Stamped between two shaped points rather than from a rotation, so
    narrowing the crown to the species' aspect shortens the bough instead of
    squashing its needle plane (see mesh_ops.shape_to_aspect).
    """
    d = Vector(tip) - Vector(origin)
    if d.length < 1e-6:
        return
    rot = d.to_track_quat("Z", "Y").to_matrix().to_4x4()
    m = (Matrix.Translation(Vector(origin)) @ rot
         @ Matrix.Diagonal((1.0, 0.45, 1.0, 1.0)))     # flat needle plane
    add_cone(bm, girth, girth * 0.12, d.length, 4, m)


def _build_conifer(kind, tier, rng, aspect):
    p = CONIFER_KINDS[kind]
    bark = bmesh.new()
    fol = bmesh.new()
    H = 1.0
    whorls = max(2, p["whorls"][tier])
    # A sapling's lowest boughs sweep the ground; an old tree has self-pruned a
    # clear bole. That, not sparseness, is what makes a young conifer read young.
    z0, z1 = p["crown_base"][tier], 0.90
    # Lay the whorls out in the builder's natural frame first, collecting every
    # point; shape_to_aspect then pulls them in to the species' real crown width
    # before anything is stamped, so the boughs shorten and the needle planes
    # keep their authored thickness.
    boughs, stubs, pts = [], [], []
    bare_in_winter = kind == "larch"
    for i in range(whorls):
        f = i / max(1, whorls - 1)                      # 0 base … 1 top
        z = z0 + (z1 - z0) * f
        reach = (p["base_r"] * (1 - f) ** 0.85 + 0.05) * (0.9 + rng.random() * 0.2)
        n = max(4, round(p["boughs"] * (1 - 0.3 * f)))
        for b in range(n):
            az = b / n * math.tau + rng.random() * 0.5
            droop = p["droop"] * (0.7 + rng.random() * 0.6)
            girth = 0.035 + 0.03 * (1 - f)
            origin = Vector((0, 0, z + p["lift"]))
            tip = origin + Vector((math.cos(az) * reach, math.sin(az) * reach,
                                   -math.sin(droop) * reach))
            boughs.append((origin, tip, girth))
            pts.extend((origin, tip))
            # Short bare branch stub under the bough — the winter skeleton.
            # Only the larch needs one: it is the one conifer here that drops its
            # needles, and the viewer hides the foliage part for nothing else, so
            # on a spruce or fir these stubs are permanently buried under the
            # boughs while costing as much geometry as the boughs themselves.
            # Reclaiming that is what pays for a properly dense young crown.
            if bare_in_winter:
                s0 = Vector((0, 0, z))
                s1 = s0 + (tip - origin) * 0.55
                stubs.append((s0, s1))
                pts.extend((s0, s1))
    # The finished height is the trunk or the spire tip, whichever is taller —
    # not the nominal H, or the aspect lands a few percent narrow.
    shape_to_aspect(pts, aspect,
                    height=max(H * 0.98, z1 + 0.14 * p["spire"]))
    # Trunk: full winter silhouette on its own (larch drops needles).
    add_cone(bark, 0.030, 0.008, H * 0.98, 6, Matrix())
    for origin, tip, girth in boughs:
        _bough(fol, origin, tip, girth)
    for s0, s1 in stubs:
        add_cone_between(bark, s0, s1, 0.008, 0.004, 4)
    # Slim core cones fill the silhouette between whorls. Axial, so the aspect
    # shaping doesn't move them — their radius tracks the shaped crown instead.
    core_r = 0.5 / aspect
    for cz, cr in ((0.30, 0.40), (0.55, 0.30), (0.76, 0.22)):
        add_cone(fol, cr * core_r, 0.01, 0.30, 5,
                 place(z=cz, rot_z=rng.random()))
    # Spire.
    add_cone(fol, min(0.045, core_r * 0.5), 0.004, 0.14 * p["spire"], 5,
             place(z=z1))
    return bark, fol


# Both pines are built by _build_pine; the kind decides how ORDERLY it is.
# Lodgepole is the fire-regenerated pole: a long clear bole under a narrow crown
# of short upswept limbs with a rounded top. Jack pine is the scraggly one: a
# slightly crooked trunk, irregular spreading limbs, gaps between its clumps of
# foliage, a flat top and dead stubs kept low down (`decurrent` in the seed
# data, against lodgepole's `excurrent`).
#
# V2.92 (F178): rebuilt, not retuned. The builder it replaces spread 11 to 44
# needle tufts evenly from mid-height to the top on short stubs all round the
# trunk, so seen from a yard both pines were a cylinder of bristles on a pole,
# the audit's "bottle brush", and at yard distance each other. A pine is read by
# its LIMBS: foliage hangs in clusters at their ends, with sky between the
# clusters, and the crown has a top of a particular shape.
#
#   crown_base  where the live crown starts, by tier (young trees lower)
#   whorls      limb whorls in the live crown, by tier
#   per_whorl   limbs in one whorl (lo, hi)
#   tilt        a limb's angle off the vertical (lo, hi): upswept below 1.57
#   reach       limb length profile: the bottom whorl's, and how much the top
#               one keeps (1 flat-topped, 0 a point)
#   crook       sideways wander of the trunk, per segment
#   cluster     tufts along a limb's outer end, by tier
#   stubs       dead branch stubs on the bole
#   top_tufts   tufts closing the crown's top (a lodgepole's is rounded)
#   limb_crook  how far a limb kinks once, up or down (jack pine)
#   trunk_r     trunk radius at the ground, as a fraction of the height: a
#               25 m lodgepole's trunk is about 0.5 m across, a jack pine's a
#               little stouter for its height
PINE_KINDS = {
    "pine":      {"crown_base": (0.26, 0.36, 0.42), "whorls": (6, 8, 9),
                  "per_whorl": (4, 6), "tilt": (1.30, 1.52),
                  "reach": (1.0, 0.35), "crook": 0.0, "cluster": (2, 2, 2),
                  "stubs": 5, "top_tufts": 3, "limb_crook": 0.0,
                  "trunk_r": 0.014},
    "pine_jack": {"crown_base": (0.20, 0.28, 0.32), "whorls": (4, 6, 8),
                  "per_whorl": (2, 4), "tilt": (1.10, 1.45),
                  "reach": (1.0, 0.75), "crook": 0.022, "cluster": (2, 3, 4),
                  "stubs": 8, "top_tufts": 1, "limb_crook": 0.35,
                  "trunk_r": 0.019},
}


def _cone_tris(segments):
    """What one capped add_cone costs: sides and two triangle-fan caps."""
    return 4 * segments


def _trunk_line(rng, crook, n=6, top=0.97):
    """The trunk as a polyline: straight, or wandering by ``crook`` a segment."""
    pts = [Vector((0.0, 0.0, 0.0))]
    for i in range(1, n + 1):
        z = top * i / n
        dx = (rng.random() - 0.5) * 2 * crook if crook else 0.0
        dy = (rng.random() - 0.5) * 2 * crook if crook else 0.0
        pts.append(Vector((pts[-1].x + dx, pts[-1].y + dy, z)))
    return pts


def _on_line(pts, z):
    """The point of polyline ``pts`` at height ``z``."""
    for a, b in zip(pts, pts[1:]):
        if a.z <= z <= b.z:
            t = (z - a.z) / max(1e-9, b.z - a.z)
            return a.lerp(b, t)
    return pts[-1].copy()


def _trunk_xy(pts, z):
    """How far a crooked trunk stands off the axis at height ``z``.

    The crown is laid out round a STRAIGHT axis and each limb is carried out to
    the trunk afterwards by this offset. Laid out on the crooked trunk itself,
    the aspect solve (which narrows everything toward the axis and not toward
    the trunk) pulled every limb's base off the wood it grows from, and shrank
    a jack pine's dead stubs to 15 cm nubs.
    """
    p = _on_line(pts, z)
    return Vector((p.x, p.y, 0.0))


def _build_pine(kind, tier, rng, aspect, grain):
    """Pinus: a bole, then whorls of limbs each ending in a cluster of tufts."""
    from . import conventions as C
    K = PINE_KINDS.get(kind, PINE_KINDS["pine"])
    bark = bmesh.new()
    fol = bmesh.new()
    crown_half = 0.5 / aspect
    pad_r = crown_half * (0.44, 0.36, 0.30)[tier] * grain
    trunk = _trunk_line(rng, K["crook"])
    z0, z1 = K["crown_base"][tier], 0.90
    whorls = K["whorls"][tier]
    r_bottom, r_top = K["reach"]
    limbs, groups, pts = [], [], []
    for i in range(whorls):
        f = i / max(1, whorls - 1)
        gap = (z1 - z0) / max(1, whorls - 1)
        z = z0 + (z1 - z0) * f + (rng.random() - 0.5) * gap * 0.5
        lo, hi = K["per_whorl"]
        n = lo + int(rng.random() * (hi - lo + 1))
        az0 = rng.random() * math.tau
        reach = (r_bottom + (r_top - r_bottom) * f) * crown_half * 2.2
        for b in range(n):
            az = az0 + b * math.tau / n + (rng.random() - 0.5) * 0.9
            tilt = K["tilt"][0] + rng.random() * (K["tilt"][1] - K["tilt"][0])
            length = reach * (0.7 + rng.random() * 0.5)
            origin = Vector((0.0, 0.0, z))       # on the axis; see _trunk_xy
            shift = _trunk_xy(trunk, z)
            d = Vector((math.sin(tilt) * math.cos(az),
                        math.sin(tilt) * math.sin(az), math.cos(tilt)))
            tip = origin + d * length
            mid = None
            if K["limb_crook"]:
                # A jack pine limb kinks once: out, then up or down.
                mid = origin + d * length * 0.55
                tip = tip + Vector((0, 0, (rng.random() - 0.4)
                                    * K["limb_crook"] * length))
            limbs.append([origin, mid, tip, shift])
            pts.extend(p for p in (origin, mid, tip) if p is not None)
            cluster = []
            for k in range(K["cluster"][tier]):
                t = 1.0 - k * 0.22
                base = mid if (mid is not None and t < 0.8) else origin
                at = base.lerp(tip, t if base is origin else (t - 0.55) / 0.45)
                at = at + Vector(((rng.random() - 0.5) * pad_r * 0.6,
                                  (rng.random() - 0.5) * pad_r * 0.6,
                                  pad_r * (0.2 + rng.random() * 0.3)))
                cluster.append([at, pad_r * (0.85 + rng.random() * 0.3), az,
                                shift])
            groups.append(cluster)
    top = []
    for k in range(K["top_tufts"]):
        az = rng.random() * math.tau
        top.append([Vector((
            math.cos(az) * pad_r * 0.5 * (k > 0), math.sin(az) * pad_r * 0.5
            * (k > 0), 0.93 - 0.03 * k)), pad_r * 0.9, None,
            _trunk_xy(trunk, 0.93)])
    if top:
        groups.append(top)
    # Dead stubs on the bole: most on a jack pine, which keeps them. They stay
    # out of the aspect solve, so they keep their authored length: a stub is
    # not crown, and narrowing it with the crown drew it as a nub.
    stubs = []
    for _ in range(K["stubs"]):
        z = 0.08 + rng.random() * max(0.02, z0 - 0.12)
        az = rng.random() * math.tau
        o = Vector((0.0, 0.0, z))
        L = crown_half * (0.25 + rng.random() * 0.35)
        stubs.append([o, o + Vector((math.cos(az) * L, math.sin(az) * L,
                                     -0.25 * L * rng.random())),
                      _trunk_xy(trunk, z)])
    limb_segs = sum(1 if mid is None else 2 for _o, mid, _t, _s in limbs)
    bark_tris = (_cone_tris(5) * (len(trunk) - 1)
                 + _cone_tris(4) * (limb_segs + len(stubs)))
    groups = thin_groups_to_budget(groups, _tuft_tris(),
                                   C.TRI_BUDGETS[f"tree_tier{tier}"], bark_tris)
    tufts = [t for g in groups for t in g]
    reach = (leaf_extent(pad_r * NEEDLE_LEN_GAIN, 1.1, "needle")[0]
             / max(1e-6, pad_r) + TUFT_CORE * 0.8)
    pts.extend(t[0] for t in tufts)
    rads = ([0.0] * (len(pts) - len(tufts))
            + [t[1] * reach for t in tufts])
    shape_to_aspect(pts, aspect, height=1.0, radii=rads)
    # Now carry every limb, tuft and stub out to where the trunk really is.
    for origin, mid, tip, shift in limbs:
        for p in (origin, mid, tip):
            if p is not None:
                p += shift
    for t in tufts:
        t[0] += t[3]
    for o, e, shift in stubs:
        o += shift
        e += shift
    tr = K["trunk_r"]
    for a, b in zip(trunk, trunk[1:]):
        add_cone_between(bark, a, b, max(0.005, tr * (1 - a.z * 0.72)),
                         max(0.004, tr * (1 - b.z * 0.72)), 5)
    for origin, mid, tip, _shift in limbs:
        if mid is None:
            add_cone_between(bark, origin, tip, 0.008, 0.004, 4)
        else:
            add_cone_between(bark, origin, mid, 0.008, 0.006, 4)
            add_cone_between(bark, mid, tip, 0.006, 0.004, 4)
    for o, e, _shift in stubs:
        add_cone_between(bark, o, e, 0.005, 0.002, 4)
    for at, r, aim, _shift in tufts:
        _needle_tuft(fol, rng, at, r, aim)
    return bark, fol


# A pine's foliage is NEEDLES IN FASCICLES bunched at the ends of its shoots —
# that spiky, open, scraggly look is the whole reason a jack pine reads as a
# jack pine. It was drawn as a flat 1.5:1.5:0.42 ellipsoid per branch end: a
# stack of smooth hexagonal plates on a bare pole, which the sprite audit scored
# 4/10 and called a pagoda.
#
# A needle at two ribbon segments is 4 triangles.
#
# V2.92 (F178): each tuft is a MASS with a fringe. Needles alone, however many,
# made a tuft a ball of spikes around nothing, and at yard distance a crown of
# them read as bristles. A small faceted core stands for the dense inner shoot
# the eye actually reads, and its faces catch the light where a needle ribbon,
# edge-on to most views, renders as a dark line; the sprays radiating out of it
# are the texture.
NEEDLES_PER_TUFT = 10
NEEDLE_SEGMENTS = 2
TUFT_CORE = 0.55                  # core radius / tuft radius
TUFT_CORE_SQUASH = 0.75           # its height / width: a shoot splays outward

# One ribbon here stands for a SHOOT'S SPRAY of needles, not a single needle.
# Drawn at true proportion (leaf_width_for('needle') is 3% of length) a jack
# pine's needle is a few millimetres on a 15 m tree — far under a pixel at any
# distance the viewer is ever at, so it aliases to a dark wire and the crown
# renders as a bottle brush on a pole. Widening the ribbon is what makes a mass
# of needles read AS a mass. (V2.92: 4.0 -> 5.5, with the core.)
NEEDLE_FASCICLE_GAIN = 5.5


# How far a needle spray overshoots the pad radius it is stamped at. Named
# because the aspect solve has to declare the same reach the stamp produces.
# V2.92: 2.4 -> 1.7. At 2.4 each tuft was a ball of long spikes and a crown of
# them read as bristles; shorter sprays make each cluster a rounded mass.
NEEDLE_LEN_GAIN = 1.7


def _off_core(at, tilt, az, core_r):
    """Where a spray leaves its core: on the core's surface, not at its centre.

    A spray rooted at the centre buries its base inside a closed mesh, where
    every ray of the occlusion bake hits the core from within: a tuft baked on
    its own came out at 0.22 of full brightness rooted inside, 0.66 rooted on
    the surface.
    """
    k = core_r * 0.8
    return at + Vector((math.sin(tilt) * math.cos(az) * k,
                        math.sin(tilt) * math.sin(az) * k, math.cos(tilt) * k))


def _tuft_tris():
    """What one :func:`_needle_tuft` costs: the core and its sprays."""
    return ICO_TRIS + leaf_tris("needle", NEEDLE_SEGMENTS) * NEEDLES_PER_TUFT


def _needle_tuft(fol, rng, at, r, aim=None):
    """A shoot end: a dense core with needle sprays radiating out of it.

    ``aim`` is the bearing of the limb the tuft ends: its sprays splay about
    that bearing, near level, the way a shoot's needles point along it. With
    none (the leader's top) they point up all round.
    """
    add_ellipsoid(fol, r * TUFT_CORE, (1.0, 1.0, TUFT_CORE_SQUASH),
                  place(at.x, at.y, at.z, rot_z=rng.random() * math.tau),
                  subdiv=0)
    ln = r * NEEDLE_LEN_GAIN         # needles overshoot the old pad's radius
    wd = leaf_width_for("needle", ln) * NEEDLE_FASCICLE_GAIN
    az0 = rng.random() * math.tau
    for i in range(NEEDLES_PER_TUFT):
        u = i / NEEDLES_PER_TUFT
        if aim is None:
            # Golden-angle spiral up and out from the leader's tip.
            tilt = 0.30 + u * 0.9 + rng.random() * 0.25
            az = az0 + i * 2.39996 + rng.random() * 0.3
        else:
            # Fanned about the limb's bearing and close to level, so a whorl
            # of tufts reads as a tier with sky between tiers, not as one
            # continuous sleeve of bristles (the ball of spikes this replaces
            # pointed every way, a third of it straight up).
            tilt = 1.05 + rng.random() * 0.45
            az = aim + (u - 0.5) * 2.6 + (rng.random() - 0.5) * 0.3
        add_blade_or_leaf(fol, rng, ln, wd, tilt, az,
                          _off_core(at, tilt, az, r * TUFT_CORE), "needle",
                          NEEDLE_SEGMENTS)


# ── juniper (V2.92, F178) ────────────────────────────────────────────────────
#
# Rocky Mountain Juniper was drawn as the default conifer: a spruce's stacked
# tiers, widened 1.7x to a juniper's footprint. A juniper has no tiers. It is a
# short trunk under a dense, irregular cone of scale-leaved sprays, foliated
# nearly to the ground, its surface a mass of small tufts rather than shelves.
#
# Built on one leader with many short branches at irregular heights and
# bearings (never whorls), more of them low down where a cone's surface is,
# spreading at the bottom and ascending at the top, long below and short above,
# each carrying spray tufts along its OUTER part. The inside of the cone is left
# empty: a first build that also filled the core with tufts came out as a black
# column, every spray shading every other. Many small branches rather than a
# few long ones, because the triangle budget drops whole branches when it
# thins, and dropping a few big ones left the cone lopsided.
#
# A tuft is the pine's, a faceted core with sprays out of it, and for the same
# reason: it reads as a mass. The sprays are short, so the surface is a lumpy
# fuzz; long ones stood out from it as dark planks.
JUNIPER = {
    "branches": (26, 42, 60),        # by tier
    "tilt": (0.55, 1.50),            # off the vertical: top, bottom
    "crown_base": (0.02, 0.04, 0.05),
    "tufts": (2, 2, 2),              # along each branch's outer part
    "outer": 0.55,                   # ... that part, as a fraction of it
    "core": 0.85,                    # core radius / tuft radius
    "sprays": 5,                     # ribbons in one tuft
    "spray_gain": 0.8,               # spray length / tuft radius
    "spray_width": 2.4,              # x the scale leaf's own width ratio
    "apex_tufts": 3,                 # on the leader's last stretch
}


def _spray_tuft_tris():
    return ICO_TRIS + leaf_tris("scale", NEEDLE_SEGMENTS) * JUNIPER["sprays"]


def _spray_tuft(fol, rng, at, r, aim=None):
    """A tuft of flattened scale-leaf sprays round a core, up and out along
    the branch's bearing ``aim`` (all round at the apex, where it is None)."""
    J = JUNIPER
    add_ellipsoid(fol, r * J["core"], (1.0, 1.0, 0.8),
                  place(at.x, at.y, at.z, rot_z=rng.random() * math.tau),
                  subdiv=0)
    ln = r * J["spray_gain"]
    wd = leaf_width_for("scale", ln) * J["spray_width"]
    az0 = rng.random() * math.tau
    for i in range(J["sprays"]):
        u = i / J["sprays"]
        if aim is None:
            tilt = 0.20 + u * 0.8 + rng.random() * 0.3
            az = az0 + i * 2.39996 + rng.random() * 0.4
        else:
            tilt = 0.60 + rng.random() * 0.70
            az = aim + (u - 0.5) * 2.6 + (rng.random() - 0.5) * 0.4
        add_blade_or_leaf(fol, rng, ln, wd, tilt, az,
                          _off_core(at, tilt, az, r * J["core"]), "scale",
                          NEEDLE_SEGMENTS)


def _build_juniper(tier, rng, aspect, grain):
    from . import conventions as C
    J = JUNIPER
    bark = bmesh.new()
    fol = bmesh.new()
    crown_half = 0.5 / aspect
    tuft_r = crown_half * (0.30, 0.24, 0.20)[tier]
    trunk = _trunk_line(rng, 0.010, n=5, top=0.95)
    z0 = J["crown_base"][tier]
    branches, groups, pts = [], [], []
    nb = J["branches"][tier]
    for i in range(nb):
        # Irregular heights, more of them low down, where a cone's surface is.
        f = 1.0 - math.sqrt(1.0 - (i + rng.random()) / nb)
        z = z0 + (0.88 - z0) * f
        az = rng.random() * math.tau
        # Spreading at the bottom of the cone, ascending at the top.
        tilt = (J["tilt"][1] - (J["tilt"][1] - J["tilt"][0]) * f
                + (rng.random() - 0.5) * 0.25)
        # A cone: long below, short above, ragged throughout.
        length = crown_half * 2.2 * ((1 - f) ** 0.7 * 0.85 + 0.12) \
            * (0.8 + rng.random() * 0.4)
        o = Vector((0.0, 0.0, z))            # on the axis; see _trunk_xy
        shift = _trunk_xy(trunk, z)
        d = Vector((math.sin(tilt) * math.cos(az),
                    math.sin(tilt) * math.sin(az), math.cos(tilt)))
        tip = o + d * length
        branches.append([o, tip, shift])
        pts.extend((o, tip))
        g = []
        n = J["tufts"][tier]
        for k in range(n):
            t = 1.0 - J["outer"] * k / max(1, n - 1)
            at = o.lerp(tip, t) + Vector(((rng.random() - 0.5) * tuft_r,
                                          (rng.random() - 0.5) * tuft_r,
                                          (rng.random() - 0.3) * tuft_r * 0.5))
            # Finer toward the top, or a young tree's big tufts square off
            # the apex and the cone reads as a column.
            r = tuft_r * (0.8 + rng.random() * 0.4) * (1.0 - 0.45 * f)
            # Never below the ground: a core reaching under z=0 made the unit
            # frame lift the whole tree, and the youngest juniper's trunk
            # stood on its own foliage, clear of the ground.
            at.z = max(at.z, r * J["core"] * 0.8)
            g.append([at, r, az, shift])
        groups.append(g)
    # The apex: a few tufts on the leader's last stretch, so the cone closes.
    apex = []
    for k in range(J["apex_tufts"]):
        z = 0.95 - 0.07 * k
        az = rng.random() * math.tau
        apex.append([Vector((
            math.cos(az) * tuft_r * 0.3 * (k > 0),
            math.sin(az) * tuft_r * 0.3 * (k > 0), z)), tuft_r * 0.55, None,
            _trunk_xy(trunk, z)])
    groups.append(apex)
    bark_tris = (_cone_tris(5) * (len(trunk) - 1)
                 + _cone_tris(4) * len(branches))
    groups = thin_groups_to_budget(groups, _spray_tuft_tris(),
                                   C.TRI_BUDGETS[f"tree_tier{tier}"], bark_tris)
    tufts = [t for g in groups for t in g]
    reach = (leaf_extent(tuft_r * J["spray_gain"], 1.0, "scale")[0]
             / max(1e-6, tuft_r) + J["core"] * 0.8)
    pts.extend(t[0] for t in tufts)
    rads = [0.0] * (len(pts) - len(tufts)) + [t[1] * reach for t in tufts]
    shape_to_aspect(pts, aspect, height=1.0, radii=rads)
    for o, tip, shift in branches:
        o += shift
        tip += shift
    for t in tufts:
        t[0] += t[3]
    for a, b in zip(trunk, trunk[1:]):
        add_cone_between(bark, a, b, max(0.006, 0.022 * (1 - a.z * 0.7)),
                         max(0.005, 0.022 * (1 - b.z * 0.7)), 5)
    for o, tip, _shift in branches:
        add_cone_between(bark, o, tip, 0.008, 0.003, 4)
    for at, r, aim, _shift in tufts:
        _spray_tuft(fol, rng, at, r, aim)
    return bark, fol


# ── deciduous ────────────────────────────────────────────────────────────────

def _decid_skeleton(rng, form, max_depth, min_r, trunk_r, bole, arch=None):
    """Recursive da Vinci skeleton as explicit segments:
    [[start, end, r_bot, r_top, depth, terminal]] — radius² conserved across
    splits, child length scaling. Endpoints (not matrices) so the crown can be
    narrowed to the species' aspect by moving points, then each branch
    re-stamped between its corrected ends (mesh_ops.add_cone_between).

    ``arch`` is the archetype's architecture (V2.92, F178), both parts optional:

    * ``stems`` (lo, hi) and ``stem_lean``: how many trunks leave the ground,
      each leaning out, sharing the trunk's cross-section between them. Water
      birch and Bebb's willow are recorded ``multi_stem`` and until V2.92 no
      archetype could draw a second stem.
    * ``leaders``: the trunk's FIRST fork, ``{"n": (lo, hi), "angle": rad,
      "length": unit, "area": x}``, where the rest of the tree forks in twos
      and threes. An elm's vase is four or five steep leaders; a cottonwood's
      three or four heavy limbs.
    * ``rise``: how strongly every later branch turns back toward the vertical.
      The walk has no sense of up, so after three forks a branch points
      anywhere and the crown is a ball on each limb; with ``rise`` the limbs
      keep climbing, and a crown whose leaders diverge comes out widest at the
      top, which is what a vase is.
    """
    arch = arch or {}
    lead = arch.get("leaders")
    rise = arch.get("rise", 0.0)
    segs = []

    def climb(mat):
        """``mat`` with its growth axis turned toward +Z by ``rise``."""
        d = (mat.to_3x3() @ Vector((0, 0, 1))).normalized()
        want = (d + Vector((0, 0, rise))).normalized()
        turn = d.rotation_difference(want).to_matrix().to_4x4()
        pos = mat.to_translation()
        return (Matrix.Translation(pos) @ turn
                @ Matrix.Translation(-pos) @ mat)

    def walk(mat, radius, length, depth, first=False):
        r_top = radius * 0.65
        terminal = depth >= max_depth or radius < min_r
        tip_mat = mat @ Matrix.Translation((0, 0, length))
        start = mat @ Vector((0, 0, 0))
        end = tip_mat @ Vector((0, 0, 0))
        segs.append([start, end, radius, r_top, depth, terminal])
        if terminal:
            return
        if first and lead:
            lo, hi = lead["n"]
            n = lo + int(rng.random() * (hi - lo + 1))
            shares = [0.85 + rng.random() * 0.3 for _ in range(n)]
            total = sum(shares)
            base_rot = rng.random() * math.tau
            for i in range(n):
                # The leaders share the trunk's cross-section (area x`area`),
                # so five of them are each half the trunk, not five trunks.
                r_child = r_top * math.sqrt(shares[i] / total * lead["area"])
                l_child = lead["length"] * (0.85 + rng.random() * 0.3)
                spread = lead["angle"] * (0.8 + rng.random() * 0.4)
                rot = (Matrix.Rotation(base_rot + i * math.tau / n
                                       + (rng.random() - 0.5) * 0.4, 4, "Z")
                       @ Matrix.Rotation(spread, 4, "X"))
                walk(tip_mat @ rot, r_child, l_child, depth + 1)
            return
        n = 3 if rng.random() < form["split_bias"] else 2
        # Split the parent's cross-section area among children.
        shares = [0.3 + rng.random() * 0.25 for _ in range(n)]
        total = sum(shares)
        base_rot = rng.random() * math.tau
        for i in range(n):
            r_child = r_top * math.sqrt(shares[i] / total * n * 0.72)
            l_child = length * max(0.05, r_child / radius) ** form["len_scale"]
            spread = form["angle"] * (0.8 + rng.random() * 0.4)
            rot = (Matrix.Rotation(base_rot + i * math.tau / n
                                   + rng.random() * 0.5, 4, "Z")
                   @ Matrix.Rotation(spread, 4, "X"))
            child = tip_mat @ rot
            walk(climb(child) if rise else child, r_child, l_child, depth + 1)

    stems = arch.get("stems")
    n_stems = 1
    if stems:
        lo, hi = stems
        n_stems = lo + int(rng.random() * (hi - lo + 1))
    if n_stems <= 1:
        lean = arch.get("stem_lean", 0.0)
        mat = Matrix()
        if lean:
            mat = (Matrix.Rotation(rng.random() * math.tau, 4, "Z")
                   @ Matrix.Rotation(lean * (0.8 + rng.random() * 0.4), 4, "X"))
        walk(mat, trunk_r, bole, 0, first=True)
        return segs
    # Stems rise from one clump, leaning apart; each carries the share of the
    # trunk's cross-section that keeps the whole clump's girth honest.
    r_each = trunk_r / math.sqrt(n_stems) * 1.15
    lean = arch.get("stem_lean", 0.2)
    base_rot = rng.random() * math.tau
    for i in range(n_stems):
        az = base_rot + i * math.tau / n_stems + (rng.random() - 0.5) * 0.6
        off = trunk_r * 1.2
        mat = (Matrix.Translation((math.cos(az) * off, math.sin(az) * off, 0))
               @ Matrix.Rotation(az + math.pi / 2, 4, "Z")
               @ Matrix.Rotation(lean * (0.7 + rng.random() * 0.6), 4, "X"))
        walk(mat, r_each, bole * (0.8 + rng.random() * 0.4), 0, first=True)
    return segs


def _build_deciduous(genus, tier, rng, aspect, grain):
    from . import conventions as C           # tier triangle budget
    g = DECID_GENERA[genus]
    form = dict(DECID_FORMS[g["form"]])
    # An archetype may override its form's skeleton figures (V2.92): the elm's
    # branches spread wider than its oval form's, the box elder forks lower.
    form.update({k: g[k] for k in _FORM_OVERRIDES if k in g})
    f_scale = form["foliage_scale"] * g.get("foliage_scale", 1.0)
    droop_outer = g.get("droop_outer", 0.0)
    bark = bmesh.new()
    fol = bmesh.new()

    # Leaf masses are sized off the crown's own width, so a narrow species gets
    # small masses and a broad one big ones (FOLIAGE_FRAC) — and then off the
    # species' real leaf length, so a bur oak (20 cm leaves) reads coarse beside
    # an aspen (8 cm) at the same crown size (conventions.grain_for).
    crown_half = 0.5 / aspect
    clump_r = crown_half * FOLIAGE_FRAC[tier] * f_scale * grain

    trunk_r = g.get("trunk_r", form["trunk_r"])
    # `twig_r` scales the thinnest limb that still forks (V2.92): below 1 a
    # crown carries more, finer ends (the elm's), above 1 fewer, coarser ones
    # (the box elder's, whose compound leaves cost four simple ones each and
    # cannot afford to spend a third of the tree's triangles on twigs).
    segs = _decid_skeleton(rng, form, DECID_DEPTH[tier],
                           trunk_r * DECID_MIN_R_FRAC[tier] * g.get("twig_r", 1.0),
                           trunk_r, form["bole"], arch=g)
    blobs = []          # [center, radius, z_of_anchor] — clear-bole gated below
    per_tip = max(2, round(CLUMPS_PER_TIP[tier] * g.get("clumps", 1.0)))
    for start, end, r_bot, r_top, depth, terminal in segs:
        tip = end
        if terminal:
            n = per_tip + (1 if rng.random() < 0.6 else 0)
            base_r = clump_r * (0.85 + 0.3 * rng.random())
            spread = clump_r * (1 + droop_outer * 0.4)
            dz = -droop_outer * 0.11
            # The FIRST clump sits exactly on the tip, so the twig end is buried
            # in its own foliage. Once the masses shrank to a seventh of the crown
            # radius they stopped covering the tips they hang off, and a birch grew
            # four bare pale sticks out of the top of its crown — which reads as
            # damage, not as fine twigs.
            blobs.append([tip.copy(), base_r, tip.z, True])
            for _ in range(n - 1):
                c = tip + Vector(((rng.random() - 0.5) * spread,
                                  (rng.random() - 0.5) * spread,
                                  dz + base_r * 0.35
                                  + (rng.random() - 0.2) * clump_r * 0.5))
                blobs.append([c, base_r, tip.z, True])
        elif depth >= 1:
            # Foliage ALONG the bough, not only at its tip. Tip-only clumps can
            # never put a leaf below the outermost twigs, so the crown collapsed
            # into the top quarter of the tree however low the first split was —
            # the pole-with-a-tuft aspen in a user's screenshot. A real crown is
            # leafy over the whole outer surface of the branch cloud, lower
            # boughs included, and this is what fills it downward.
            n = 2 if depth >= 2 else 1
            for j in range(n):
                t = 0.45 + 0.55 * ((j + rng.random()) / n)
                at = start.lerp(end, t)
                # Pulled back down the bough, so a filler mass sits inside the
                # branch cloud rather than out at the tip where the leaf shell is.
                at = at.lerp(start, INNER_MASS_PULL)
                c = at + Vector(((rng.random() - 0.5) * clump_r * 0.8,
                                 (rng.random() - 0.5) * clump_r * 0.8,
                                 clump_r * 0.25 - droop_outer * 0.05))
                blobs.append([c, clump_r * (0.62 + rng.random() * 0.33),
                              at.z, False])

    # The species' blade outline, and the size ONE leaf card is drawn at — which
    # comes from the species' real leaf against its own stature, not from the
    # clump radius (conventions.crown_card_length, and the long note there for
    # what keying it to the crown did to the bur oak). A lobed leaf needs four
    # ribbon segments (mesh_ops.blade_segments refuses to flatten a cut leaf on
    # one vertex), so an oak's cards cost twice an aspen's and it carries
    # correspondingly fewer — which is also how the tree resolves the same
    # constraint.
    leaf_shape = C.DECID_LEAF_SHAPE.get(genus, "ovate")
    # A compound leaf's leaflet count, where the species' differs from the
    # outline's default of three pairs (V2.92): the box elder carries three
    # leaflets, and at seven each leaf cost eight simple ones and the crown
    # could afford a sparse handful of long cards.
    pairs = g.get("leaflet_pairs")
    # ... and its leaflets' length against the leaf's: at a frond's default a
    # three-leaflet leaf covers a fifth of what a simple one does, and the crown
    # came out as specks on bare twigs.
    leaflet = g.get("leaflet_len")
    one_leaf = leaf_tris(leaf_shape, CROWN_LEAF_SEGMENTS, pairs=pairs)
    bark_tris = len(segs) * (5 * 2 + 5 * 2)
    card_len = C.crown_card_length(
        genus, crown_half=crown_half, crown_frac=CROWN_FRAC[g["form"]],
        leaf_cost=one_leaf, width_ratio=leaf_width_for(leaf_shape, 1.0),
        foliage_budget=max(1.0, C.TRI_BUDGETS[f"tree_tier{tier}"] * 0.94
                           - bark_tris))
    lo, hi = CROWN_LEAVES_PER_CLUMP
    leaves_per = int(max(lo, min(hi, round(
        CROWN_LEAF_COVER * (clump_r / max(1e-6, card_len)) ** 2))))
    outer_cost = leaves_per * one_leaf
    card_reach = clump_r * CROWN_LEAF_SCATTER + leaf_extent(
        card_len, 1.4, leaf_shape, pairs=pairs, leaflet=leaflet)[0]

    # Fit the crown to the tier's triangle budget before anything is stamped.
    # A branch cross-section is 5 segments capped both ends; the crown is what
    # has to give, and thinning it evenly just makes the canopy slightly airier
    # (mesh_ops.thin_groups_to_budget). Every clump is a leaf rosette now, so
    # there is one cost and no way for a cheap kind to be billed at an expensive
    # kind's rate.
    blobs = [b for group in thin_groups_to_budget(
        [[b] for b in blobs], outer_cost,
        C.TRI_BUDGETS[f"tree_tier{tier}"], bark_tris) for b in group]

    # Narrow (or widen) the whole crown to the species' real aspect BEFORE
    # stamping: branch endpoints and clump centres move, clump radii and branch
    # cross-sections don't. An aspen crown gets tall and tight with the same
    # sized leaf masses, instead of the same crown with stretched ones.
    pts = [p for s in segs for p in (s[0], s[1])] + [b[0] for b in blobs]
    # An outer clump's geometry is a leaf ROSETTE scattered inside the clump, so
    # its real reach is the scatter plus one card — not the clump radius, which
    # under-states it and lets the solve grow the crown past its species' aspect
    # (an apple came out 0.77 against a target of 1.20, i.e. half again too
    # wide). leaf_extent is the same reach model add_leaf is built from, so this
    # is exact rather than a fudge.
    rads = [0.0] * (2 * len(segs)) + [card_reach] * len(blobs)
    shape_to_aspect(pts, aspect, radii=rads)

    for start, end, r_bot, r_top, _depth, _terminal in segs:
        add_cone_between(bark, start, end, max(0.006, r_bot),
                         max(0.004, r_top), 5)
    # Clear bole: no foliage below clear_bole × crown height.
    max_z = max((b[2] for b in blobs), default=1.0)
    gate = form["clear_bole"] * max_z
    wd = leaf_width_for(leaf_shape, card_len)
    for center, radius, tip_z, outer in blobs:
        if tip_z < gate:
            continue
        # A rosette of real leaf cards at the species' own leaf size, scattered
        # through the clump rather than all radiating from its centre, so the
        # mass reads as foliage instead of as a handful of paddles on a twig.
        # Crown-edge rosettes fan wide and droop past the horizontal, which is
        # what gives a silhouette its ragged, un-spherical outline; interior
        # ones sit tighter, because inside a canopy leaves are packed.
        tilt0, fan = OUTER_FAN_TILT if outer else INNER_FAN_TILT
        scatter = radius * CROWN_LEAF_SCATTER
        az0 = rng.random() * math.tau
        for k in range(leaves_per):
            at = center + Vector(((rng.random() - 0.5) * 2 * scatter,
                                  (rng.random() - 0.5) * 2 * scatter,
                                  (rng.random() - 0.5) * 1.4 * scatter))
            add_blade_or_leaf(
                fol, rng, card_len, wd,
                tilt0 + (k / max(1, leaves_per - 1)) * fan + rng.random() * 0.2,
                az0 + k * 2.39996 + rng.random() * 0.35,
                at, leaf_shape, CROWN_LEAF_SEGMENTS, pairs=pairs,
                leaflet=leaflet)
    return bark, fol


# ── public entry ─────────────────────────────────────────────────────────────

def build_tree(archetype, tier, rng, coll, name_prefix=""):
    """Build one tree tier; returns {'bark': obj, 'foliage': obj}."""
    from . import conventions as C
    from .materials import preview_material

    # The species' real height ÷ canopy, from the seed data — the crown is
    # shaped to it so the instance transform stays undistorted (see the
    # unit-frame note in conventions.py).
    aspect = C.CROWN_ASPECT.get(archetype, 1.8)
    grain = C.grain_for(archetype)
    if archetype in PINE_KINDS:
        bark_bm, fol_bm = _build_pine(archetype, tier, rng, aspect, grain)
    elif archetype == "juniper":
        bark_bm, fol_bm = _build_juniper(tier, rng, aspect, grain)
    elif archetype in CONIFER_KINDS:
        bark_bm, fol_bm = _build_conifer(archetype, tier, rng, aspect)
    elif archetype in DECID_GENERA:
        bark_bm, fol_bm = _build_deciduous(archetype, tier, rng, aspect, grain)
    else:
        raise KeyError(f"unknown tree archetype: {archetype}")
    mat = preview_material()
    return {
        C.PART_BARK: bm_to_object(
            bark_bm, C.part_name(name_prefix, C.PART_BARK), coll, mat),
        C.PART_FOLIAGE: bm_to_object(
            fol_bm, C.part_name(name_prefix, C.PART_FOLIAGE), coll, mat),
    }
