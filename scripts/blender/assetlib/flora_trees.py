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
    "birch_water":   {"form": "spreading", "droop_outer": 0.35,
                      "foliage_scale": 0.86, "trunk_r": 0.022},
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
    "willow":        {"form": "slender", "droop_outer": 0.70,
                      "foliage_scale": 0.85, "trunk_r": 0.020},
    "cherry":        {"form": "oval", "trunk_r": 0.018},
    "apple":         {"form": "spreading", "trunk_r": 0.026},
    "def_slender":   {"form": "slender"},
    "def_oval":      {"form": "oval"},
    "def_spreading": {"form": "spreading"},
}

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
                   "def_conifer",
                   "aspen", "poplar", "birch", "birch_water", "oak", "willow",
                   "cherry", "cherry_orchard", "apple",
                   "def_slender", "def_oval", "def_spreading")


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
# Lodgepole is the fire-regenerated pole — a dense narrow spire, almost a mast.
# Jack pine is the scraggly one: a short, irregular, open crown with tufts at
# odd angles and gaps between them, which is most of how it is recognised
# (`decurrent` in the seed data, against lodgepole's `excurrent`).
# `clumps` rose sharply in V2.33 with the tier budgets: a tuft is 72 triangles
# (18 needle ribbons at 4 each), so tier2's old 23 tufts spent 1,656 of a 3,500
# budget and the new 6,000 buys a crown that is actually opaque. A pine crown
# being SEE-THROUGH was the last of the "bottle brush on a pole" look left after
# V2.30 rebuilt the fascicles.
PINE_KINDS = {
    "pine":      {"clumps": (14, 26, 44), "z_base": 0.52, "reach": (0.16, 0.10),
                  "jitter": 0.04, "taper": 0.45, "pad": 1.0},
    "pine_jack": {"clumps": (11, 20, 32), "z_base": 0.42, "reach": (0.20, 0.20),
                  "jitter": 0.11, "taper": 0.20, "pad": 1.35},
}


def _build_pine(kind, tier, rng, aspect, grain):
    """Pinus: clear lower trunk, tufted open upper crown, flattish top."""
    K = PINE_KINDS.get(kind, PINE_KINDS["pine"])
    bark = bmesh.new()
    fol = bmesh.new()
    H = 1.0
    # Pine crowns are narrow (Pinus contorta runs 4:1), so the needle pads are
    # sized off the crown width like the deciduous leaf masses — and there are
    # more of them on a bigger tree.
    crown_half = 0.5 / aspect
    pad_r = crown_half * (0.62, 0.5, 0.42)[tier] * grain * K.get("pad", 1.0)
    # Fourteen needle tufts at tier2 left daylight between them and the crown
    # read as sparse; a tuft is 72 triangles, so the 3500 budget affords more
    # than twice that and the crown can actually be a crown.
    clumps = K["clumps"][tier]
    z_base = K["z_base"]
    tufts, pts = [], []
    for i in range(clumps):
        f = i / max(1, clumps - 1)
        z = z_base + (0.88 - z_base) * f + (rng.random() - 0.5) * K["jitter"]
        az = rng.random() * math.tau
        reach = (K["reach"][0] + rng.random() * K["reach"][1]) \
            * (1 - f * K["taper"])
        base = Vector((0, 0, z - 0.02))
        tip = Vector((math.cos(az) * reach, math.sin(az) * reach, z))
        r = pad_r * (0.8 + rng.random() * 0.4) * (1 - f * 0.20)
        tufts.append((base, tip, r))
        pts.extend((base, tip))
    # A tuft's real horizontal reach is what its NEEDLES span, not what the pad
    # it replaced did. The 1.5x figure here was inherited from the flat elliptic
    # pads and never updated when V2.30 turned them into needle fascicles that
    # overshoot the pad radius (`ln = r * 2.4` in _needle_tuft) — so the solve
    # was told the crown was 40% narrower than it is and let it grow wider than
    # the species' aspect. Invisible at a 3.7 target, a failure at lodgepole's
    # 4.2. leaf_extent is the same reach model add_leaf is built from.
    reach = leaf_extent(pad_r * NEEDLE_LEN_GAIN, 1.1, "needle")[0] / max(
        1e-6, pad_r)
    shape_to_aspect(pts, aspect, height=H,
                    radii=[v for _b, _t, r in tufts for v in (0.0, r * reach)])
    add_cone(bark, 0.034, 0.010, H * 0.96, 6, Matrix())
    for base, tip, r in tufts:
        # Visible branch out to the tuft (also the winter skeleton).
        add_cone_between(bark, base, tip, 0.014, 0.006, 4)
        _needle_tuft(fol, rng, tip, r)
    _needle_tuft(fol, rng, Vector((0, 0, 0.93)), pad_r)
    return bark, fol


# A pine's foliage is NEEDLES IN FASCICLES bunched at the ends of its shoots —
# that spiky, open, scraggly look is the whole reason a jack pine reads as a
# jack pine. It was drawn as a flat 1.5:1.5:0.42 ellipsoid per branch end: a
# stack of smooth hexagonal plates on a bare pole, which the sprite audit scored
# 4/10 and called a pagoda.
#
# It was also spending almost nothing: tier2 came in at 548 triangles against a
# 3500 budget. A needle at two ribbon segments is 4 triangles, so a tuft of
# eighteen is 72, and twenty-odd tufts still leave the tier inside its
# allowance.
NEEDLES_PER_TUFT = 18
NEEDLE_SEGMENTS = 2

# One ribbon here stands for a SHOOT'S SPRAY of needles, not a single needle.
# Drawn at true proportion (leaf_width_for('needle') is 3% of length) a jack
# pine's needle is a few millimetres on a 15 m tree — far under a pixel at any
# distance the viewer is ever at, so it aliases to a dark wire and the crown
# renders as a bottle brush on a pole. That is exactly what the first cut of
# this builder did, and it was worse than the flat pads it replaced. Widening
# the ribbon is what makes a mass of needles read AS a mass.
NEEDLE_FASCICLE_GAIN = 4.0


# How far a needle spray overshoots the pad radius it is stamped at. Named
# because the aspect solve has to declare the same reach the stamp produces.
NEEDLE_LEN_GAIN = 2.4


def _needle_tuft(fol, rng, at, r):
    """A bunch of needle sprays radiating from one shoot end."""
    ln = r * NEEDLE_LEN_GAIN         # needles overshoot the old pad's radius
    wd = leaf_width_for("needle", ln) * NEEDLE_FASCICLE_GAIN
    az0 = rng.random() * math.tau
    for i in range(NEEDLES_PER_TUFT):
        # Golden-angle spiral out from the shoot, splayed from nearly along the
        # branch to nearly perpendicular — a fascicle sprays, it does not sit
        # flat like the disc this replaces.
        add_blade_or_leaf(
            fol, rng, ln, wd,
            0.45 + (i / NEEDLES_PER_TUFT) * 1.25 + rng.random() * 0.25,
            az0 + i * 2.39996 + rng.random() * 0.3,
            at, "needle", NEEDLE_SEGMENTS)


# ── deciduous ────────────────────────────────────────────────────────────────

def _decid_skeleton(rng, form, max_depth, min_r, trunk_r, bole):
    """Recursive da Vinci skeleton as explicit segments:
    [[start, end, r_bot, r_top, depth, terminal]] — radius² conserved across
    splits, child length scaling. Endpoints (not matrices) so the crown can be
    narrowed to the species' aspect by moving points, then each branch
    re-stamped between its corrected ends (mesh_ops.add_cone_between)."""
    segs = []

    def walk(mat, radius, length, depth):
        r_top = radius * 0.65
        terminal = depth >= max_depth or radius < min_r
        tip_mat = mat @ Matrix.Translation((0, 0, length))
        start = mat @ Vector((0, 0, 0))
        end = tip_mat @ Vector((0, 0, 0))
        segs.append([start, end, radius, r_top, depth, terminal])
        if terminal:
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
            walk(tip_mat @ rot, r_child, l_child, depth + 1)

    walk(Matrix(), trunk_r, bole, 0)
    return segs


def _build_deciduous(genus, tier, rng, aspect, grain):
    from . import conventions as C           # tier triangle budget
    g = DECID_GENERA[genus]
    form = dict(DECID_FORMS[g["form"]])
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
    segs = _decid_skeleton(rng, form, DECID_DEPTH[tier],
                           trunk_r * DECID_MIN_R_FRAC[tier], trunk_r,
                           form["bole"])
    blobs = []          # [center, radius, z_of_anchor] — clear-bole gated below
    for start, end, r_bot, r_top, depth, terminal in segs:
        tip = end
        if terminal:
            n = CLUMPS_PER_TIP[tier] + (1 if rng.random() < 0.6 else 0)
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
    one_leaf = leaf_tris(leaf_shape, CROWN_LEAF_SEGMENTS)
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
        card_len, 1.4, leaf_shape)[0]

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
                at, leaf_shape, CROWN_LEAF_SEGMENTS)
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
