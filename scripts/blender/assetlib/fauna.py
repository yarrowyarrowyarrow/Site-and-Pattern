"""Fauna critter builders (Z-up; forward = +Y in Blender = -Z in the viewer).

One GLB per kind — bee, lep (butterfly+moth), bird, fly (hover + darner
variants in one file), beetle, bat, mammal (mouse) — authored at the SAME
nominal proportions as the procedural critters in html/scene3d/07-wildlife.js
and 06-fly.js, so the viewer's per-kind scale formulas apply unchanged.
Per-species looks are TINTS, not meshes: the viewer swaps every material by
NAME (conventions.MAT_*) and toggles named nodes (Band0..2, Spots, Beak).

Wing objects (WingL/WingR, rear pair WingL2/WingR2 static) have their ORIGIN
AT THE HINGE and zero local rotation — the viewer wraps them in a pivot and
drives roll for the flap. In multi-variant files node names are prefixed
with the variant root ('hover_WingL').

build_critter(kind, rng, coll) → dict of created objects (roots).
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

from . import conventions as C
from .fauna_variants import (BEE_VARIANTS, BIRD_VARIANTS,
                             LEP_VARIANTS)
from .materials import fauna_material
from .mesh_ops import add_cone, add_uv_ball, bm_to_object, make_empty

FAUNA_KINDS = ("bee", "lep", "bird", "fly", "beetle", "bat", "mammal")


def _ball(name, coll, mat_name, r, scale, at, u=10, v=8):
    bm = bmesh.new()
    add_uv_ball(bm, r, scale, Matrix.Translation(Vector(at)), u=u, v=v)
    return bm_to_object(bm, name, coll, fauna_material(mat_name))


def _flat_ellipse(bm, r, scale_xy, matrix, segments=12):
    m = matrix @ Matrix.Diagonal((scale_xy[0], scale_xy[1], 1.0, 1.0))
    bmesh.ops.create_circle(bm, cap_ends=True, segments=segments,
                            radius=r, matrix=m)


def _wing_obj(name, coll, mat_name, hinge_at, build):
    """A wing whose OBJECT ORIGIN is the hinge: mesh verts are hinge-relative."""
    bm = bmesh.new()
    build(bm)
    obj = bm_to_object(bm, name, coll, fauna_material(mat_name))
    obj.location = Vector(hinge_at)
    return obj


def _parent(children, parent):
    for c in children:
        if c is parent:
            continue
        c.parent = parent
        c.matrix_parent_inverse = parent.matrix_world.inverted()


# ── bee (avatar proportions: 06-fly.js makeBeeAvatar) ────────────────────────

# A bumblebee is not a honeybee, and 62 of the catalogue's 69 native bees will
# never have a photograph under the licence policy — so the MODEL has to carry
# the identification (F67). These are the body plans a person can actually see
# in the air: the four together cover every genus in bee_attributes.
#   round      Bombus — short, deep, densely furry; the bumble outline.
#   stout      Anthophora / Osmia / Colletes — the medium generalist build.
#   slender    Andrena / Halictus / Lasioglossum / Agapostemon — narrow, with a
#              longer tapering abdomen; the small dark and metallic-green bees.
#   leafcutter Megachile — a notably broad head and a flat, wide abdomen carried
#              with the pale pollen scopa UNDERNEATH rather than on the legs,
#              which is the one bee build a non-specialist reliably notices.
# (thorax r, thorax scale, head r, abdomen r, abdomen scale, abdomen y, wing len)
BEE_BUILDS = {
    "round":      {"thorax": 0.56, "th_scale": (1.05, 0.92, 0.98),
                   "head": 0.32, "abd": 0.58, "abd_scale": (1.0, 1.18, 0.98),
                   "abd_y": -0.72, "wing": 0.52},
    "stout":      {"thorax": 0.50, "th_scale": (1, 1, 0.9),
                   "head": 0.32, "abd": 0.55, "abd_scale": (0.92, 1.45, 0.88),
                   "abd_y": -0.80, "wing": 0.55},
    "slender":    {"thorax": 0.42, "th_scale": (0.92, 1.05, 0.86),
                   "head": 0.28, "abd": 0.46, "abd_scale": (0.82, 1.75, 0.78),
                   "abd_y": -0.86, "wing": 0.58},
    "leafcutter": {"thorax": 0.50, "th_scale": (1.02, 0.95, 0.88),
                   "head": 0.40, "abd": 0.56, "abd_scale": (1.12, 1.30, 0.66),
                   "abd_y": -0.82, "wing": 0.56},
}


def _build_bee_one(rng, coll, prefix="", build="stout"):
    B = BEE_BUILDS.get(build, BEE_BUILDS["stout"])
    n = lambda s: C.part_name(prefix, s)
    objs = []
    body = _ball(n(C.NODE_BODY), coll, C.MAT_FUZZ, B["thorax"], B["th_scale"],
                 (0, 0, 0))
    head = _ball(n(C.NODE_HEAD), coll, C.MAT_DARK, B["head"], (1, 1, 1),
                 (0, 0.62, 0), u=8, v=6)
    abdomen = _ball(n(C.NODE_ABDOMEN), coll, C.MAT_DARK, B["abd"],
                    B["abd_scale"], (0, B["abd_y"], -0.03))
    objs += [body, head, abdomen]
    # Antennae (part of the head look; fixed dark).
    bm = bmesh.new()
    for s in (-1, 1):
        add_cone(bm, 0.018, 0.012, 0.4, 4,
                 Matrix.Translation((0.1 * s, 0.82, 0.16))
                 @ Matrix.Rotation(-1.2, 4, "X")
                 @ Matrix.Rotation(0.25 * s, 4, "Y"))
    objs.append(bm_to_object(bm, n("Antennae"), coll, fauna_material(C.MAT_DARK)))
    # Abdomen stripes: three fuzz shells, visibility-toggled by app.bands.
    ar = B["abd"] * 1.04
    for i in range(3):
        band = _ball(n(C.NODE_BANDS[i]), coll, C.MAT_FUZZ, ar,
                     (B["abd_scale"][0] * 1.02, 0.36,
                      B["abd_scale"][2] * 1.02),
                     (0, B["abd_y"] + 0.30 - i * 0.45, -0.03), u=8, v=6)
        objs.append(band)
    objs.append(_ball(n("Tip"), coll, C.MAT_DARK, B["abd"] * 0.55,
                      (0.9, 1.1, 0.85),
                      (0, B["abd_y"] - B["abd"] * 0.92, -0.04), u=8, v=6))
    # Wings: swept-back translucent ovals, hinge on the thorax shoulder.
    for s, nm in ((-1, C.NODE_WING_L), (1, C.NODE_WING_R)):
        def wing(bm, s=s):
            _flat_ellipse(bm, B["wing"], (0.5, 1.0),
                          Matrix.Translation((0.42 * s, -0.18, 0.02))
                          @ Matrix.Rotation(-0.25 * s, 4, "Z")
                          @ Matrix.Rotation(0.1 * s, 4, "Y"))
        objs.append(_wing_obj(n(nm), coll, C.MAT_WING,
                              (0.14 * s, -0.05, 0.38), wing))
    return objs


def _build_bee(rng, coll, prefix=""):
    """All four bee builds in one file, each under its own prefixed root — the
    multi-variant layout _build_fly established (`hover_WingL`)."""
    return _multi(rng, coll, BEE_VARIANTS, _build_bee_one)


def _multi(rng, coll, variants, builder):
    objs = []
    for variant in variants:
        root = make_empty(variant, coll)
        children = builder(rng, coll, variant, variant)
        _parent(children, root)
        objs.append(root)
        objs.extend(children)
    return objs


# ── lep (butterfly / moth: 06-fly.js makeButterflyAvatar) ────────────────────

# Wing plan and body bulk, which is how the three lepidopteran silhouettes are
# told apart on the wing (F67) — the colourway alone made every lep in the
# roster the same shape. `lepidoptera_attributes.kind` already records
# butterfly / moth / skipper, so this reads the catalogue.
#   butterfly    broad rounded forewing, big rounded hindwing, slim body
#   moth         broad furry thorax, swept triangular forewing, small hindwing
#   skipper      stubby wings on a thick body — the "flying triangle"
#   swallowtail  a butterfly with the hindwing drawn out into a tail
LEP_BUILDS = {
    "butterfly":   {"body": 0.16, "body_s": (1, 1.4, 1), "fore": 0.42,
                    "fore_s": (0.85, 0.95), "hind": 0.30, "hind_s": (0.9, 1.05),
                    "hind_y": -0.30, "tail": 0.0},
    "moth":        {"body": 0.21, "body_s": (1.15, 1.3, 1.1), "fore": 0.44,
                    "fore_s": (0.62, 1.10), "hind": 0.24, "hind_s": (0.8, 0.85),
                    "hind_y": -0.26, "tail": 0.0},
    "skipper":     {"body": 0.20, "body_s": (1.1, 1.25, 1.1), "fore": 0.30,
                    "fore_s": (0.78, 0.92), "hind": 0.21, "hind_s": (0.9, 0.9),
                    "hind_y": -0.20, "tail": 0.0},
    "swallowtail": {"body": 0.15, "body_s": (0.95, 1.5, 0.95), "fore": 0.46,
                    "fore_s": (0.86, 0.98), "hind": 0.32, "hind_s": (0.9, 1.0),
                    "hind_y": -0.32, "tail": 0.30},
}


def _build_lep_one(rng, coll, prefix="", build="butterfly"):
    B = LEP_BUILDS.get(build, LEP_BUILDS["butterfly"])
    n = lambda s: C.part_name(prefix, s)
    objs = [
        _ball(n(C.NODE_BODY), coll, C.MAT_DARK, B["body"], B["body_s"],
              (0, 0, 0)),
        _ball(n(C.NODE_HEAD), coll, C.MAT_DARK, 0.12, (1, 1, 1),
              (0, 0.28, 0.02), u=8, v=6),
        _ball(n(C.NODE_ABDOMEN), coll, C.MAT_DARK, 0.13, (0.8, 2.6, 0.8),
              (0, -0.4, -0.01), u=8, v=6),
    ]
    bm = bmesh.new()
    for s in (-1, 1):
        add_cone(bm, 0.008, 0.006, 0.32, 4,
                 Matrix.Translation((0.06 * s, 0.42, 0.08))
                 @ Matrix.Rotation(-1.0, 4, "X")
                 @ Matrix.Rotation(0.28 * s, 4, "Y"))
    objs.append(bm_to_object(bm, n("Antennae"), coll, fauna_material(C.MAT_DARK)))
    # A wing = rim underlay + fore + hind lobes, flat in XY, hinge at midline.
    fr, fs = B["fore"], B["fore_s"]
    hr, hs, hy = B["hind"], B["hind_s"], B["hind_y"]
    for s, nm in ((-1, C.NODE_WING_L), (1, C.NODE_WING_R)):
        def wing(bm, s=s):
            _flat_ellipse(bm, fr, (fs[0] * 1.04, fs[1] * 1.03),   # rim peeks out
                          Matrix.Translation((fr * s, 0.1, -0.004)),
                          segments=14)
        objs.append(_wing_obj(n("Rim" + nm[-1]), coll, C.MAT_EDGE,
                              (0, 0, 0), wing))
        def fore(bm, s=s):
            _flat_ellipse(bm, fr, fs,
                          Matrix.Translation((fr * s, 0.1, 0)), segments=14)
        def hind(bm, s=s):
            _flat_ellipse(bm, hr, hs,
                          Matrix.Translation((hr * 1.33 * s, hy, -0.002)),
                          segments=12)
        f = _wing_obj(n("Fore" + nm[-1]), coll, C.MAT_FORE, (0, 0, 0), fore)
        h = _wing_obj(n("Hind" + nm[-1]), coll, C.MAT_HIND, (0, 0, 0), hind)
        parts = [objs[-1], f, h]
        if B["tail"]:
            def tail(bm, s=s, t=B["tail"]):
                add_cone(bm, 0.055, 0.012, t, 4,
                         Matrix.Translation((hr * 1.5 * s, hy - hr * 0.7, -0.003))
                         @ Matrix.Rotation(math.pi / 2, 4, "X")
                         @ Matrix.Rotation(-0.5 * s, 4, "Y"))
            parts.append(_wing_obj(n("Tail" + nm[-1]), coll, C.MAT_HIND,
                                   (0, 0, 0), tail))
        # Group them under the named wing node (an empty at the hinge).
        pivot = make_empty(n(nm), coll)
        _parent(parts, pivot)
        objs.extend(parts[1:])
        objs.append(pivot)
    return objs


def _build_lep(rng, coll, prefix=""):
    return _multi(rng, coll, LEP_VARIANTS, _build_lep_one)


# ── bird (07-wildlife.js makeBirdCritter) ────────────────────────────────────

# The three bird outlines a yard actually holds. A woodpecker propped on a trunk
# and a chickadee on a twig are not the same bird, and the roster shows both.
BIRD_BUILDS = {
    "passerine":  {"body": 0.16, "body_s": (0.85, 1.35, 0.9), "beak": 0.09,
                   "beak_r": 0.030, "tail": (0.12, 0.22), "tail_tilt": -0.3},
    "woodpecker": {"body": 0.17, "body_s": (0.78, 1.5, 0.86), "beak": 0.16,
                   "beak_r": 0.026, "tail": (0.09, 0.34), "tail_tilt": 0.55},
    "hummer":     {"body": 0.11, "body_s": (0.9, 1.25, 0.95), "beak": 0.22,
                   "beak_r": 0.012, "tail": (0.08, 0.14), "tail_tilt": -0.1},
}


def _build_bird_one(rng, coll, prefix="", build="passerine"):
    B = BIRD_BUILDS.get(build, BIRD_BUILDS["passerine"])
    n = lambda s: C.part_name(prefix, s)
    objs = [
        _ball(n(C.NODE_BODY), coll, C.MAT_BODY, B["body"], B["body_s"],
              (0, 0, 0)),
        _ball(n("Belly"), coll, C.MAT_BELLY, 0.13, (0.7, 1.0, 0.8),
              (0, -0.06, -0.05), u=8, v=6),
        _ball(n(C.NODE_HEAD), coll, C.MAT_BODY, 0.11, (1, 1, 1),
              (0, 0.16, 0.12), u=9, v=7),
    ]
    bm = bmesh.new()          # beak: cone forward (+Y), origin at its base
    add_cone(bm, B["beak_r"], 0.004, B["beak"], 5,
             Matrix.Rotation(-math.pi / 2, 4, "X"))
    beak = bm_to_object(bm, n(C.NODE_BEAK), coll, fauna_material(C.MAT_DARK))
    beak.location = Vector((0, 0.28, 0.12))
    objs.append(beak)
    bm = bmesh.new()          # tail: flat slab. A woodpecker's is long and
    tw, tl = B["tail"]        # propped DOWN against the trunk, not cocked up.
    bmesh.ops.create_cube(bm, size=1.0,
                          matrix=Matrix.Translation((0, -0.26 - tl * 0.4, 0.02))
                          @ Matrix.Rotation(B["tail_tilt"], 4, "X")
                          @ Matrix.Diagonal((tw, tl, 0.02, 1)))
    objs.append(bm_to_object(bm, n(C.NODE_TAIL), coll,
                             fauna_material(C.MAT_WING)))
    for s, nm in ((-1, C.NODE_WING_L), (1, C.NODE_WING_R)):
        def wing(bm, s=s):
            add_uv_ball(bm, 0.14, (0.5, 1.0, 0.14),
                        Matrix.Translation((0.12 * s, -0.02, 0)), u=8, v=4)
        objs.append(_wing_obj(n(nm), coll, C.MAT_WING,
                              (0.08 * s, -0.02, 0.04), wing))
    return objs


def _build_bird(rng, coll, prefix=""):
    return _multi(rng, coll, BIRD_VARIANTS, _build_bird_one)


# ── fly (hover fly + darner dragonfly variants in one file) ──────────────────

def _build_fly_hover(rng, coll, prefix):
    n = lambda s: C.part_name(prefix, s)
    objs = [
        _ball(n(C.NODE_BODY), coll, C.MAT_BODY, 0.07, (0.9, 1.3, 0.8),
              (0, 0, 0), u=9, v=7),
        _ball(n(C.NODE_HEAD), coll, C.MAT_DARK, 0.05, (1, 1, 1),
              (0, 0.12, 0.01), u=8, v=6),
    ]
    for s, nm in ((-1, C.NODE_WING_L), (1, C.NODE_WING_R)):
        def wing(bm, s=s):
            _flat_ellipse(bm, 0.16, (0.55, 1.0),
                          Matrix.Translation((0.14 * s, -0.03, 0))
                          @ Matrix.Rotation(-0.2 * s, 4, "Z"), segments=10)
        objs.append(_wing_obj(n(nm), coll, C.MAT_WING, (0.03 * s, 0, 0.05), wing))
    return objs


def _build_fly_darner(rng, coll, prefix):
    n = lambda s: C.part_name(prefix, s)
    objs = [
        _ball(n(C.NODE_BODY), coll, C.MAT_BODY, 0.06, (1, 1, 1),
              (0, 0, 0), u=8, v=6),
        _ball(n(C.NODE_HEAD), coll, C.MAT_DARK, 0.055, (1, 1, 1),
              (0, 0.1, 0), u=8, v=6),
    ]
    bm = bmesh.new()          # long thin abdomen backwards
    add_cone(bm, 0.03, 0.012, 0.5, 6,
             Matrix.Translation((0, -0.03, 0)) @ Matrix.Rotation(math.pi / 2, 4, "X"))
    objs.append(bm_to_object(bm, n(C.NODE_ABDOMEN), coll,
                             fauna_material(C.MAT_BODY)))
    pairs = ((C.NODE_WING_L, C.NODE_WING_R, 0.02),          # front (flapped)
             (C.NODE_WING_L2, C.NODE_WING_R2, -0.12))       # rear (static)
    for left, right, y in pairs:
        for s, nm in ((-1, left), (1, right)):
            def wing(bm, s=s):
                _flat_ellipse(bm, 0.2, (1.0, 0.22),
                              Matrix.Translation((0.2 * s, 0, 0)), segments=10)
            objs.append(_wing_obj(n(nm), coll, C.MAT_WING,
                                  (0.04 * s, y, 0.03), wing))
    return objs


def _build_fly(rng, coll, prefix=""):
    objs = []
    for variant, builder in (("hover", _build_fly_hover),
                             ("darner", _build_fly_darner)):
        root = make_empty(variant, coll)
        children = builder(rng, coll, variant)
        _parent(children, root)
        objs.append(root)
        objs.extend(children)
    return objs


# ── beetle / bat / mammal (07-wildlife.js critters) ──────────────────────────

def _build_beetle(rng, coll, prefix=""):
    n = lambda s: C.part_name(prefix, s)
    objs = [
        _ball(n(C.NODE_BODY), coll, C.MAT_BODY, 0.12, (1.0, 1.25, 0.62),
              (0, 0, 0.045)),
        _ball(n(C.NODE_HEAD), coll, C.MAT_DARK, 0.05, (1, 1, 1),
              (0, 0.15, 0.01), u=8, v=6),
    ]
    bm = bmesh.new()          # six spots over the elytra, one toggleable node
    for i in range(6):
        a = i / 6 * math.tau
        add_uv_ball(bm, 0.018, (1, 1, 1),
                    Matrix.Translation((math.cos(a) * 0.06,
                                        math.sin(a) * 0.08 - 0.02, 0.115)),
                    u=6, v=5)
    objs.append(bm_to_object(bm, n(C.NODE_SPOTS), coll,
                             fauna_material(C.MAT_DARK)))
    return objs


def _bat_wing_shape(bm, s):
    """Scalloped membrane fan (port of the makeBatCritter wing shape)."""
    pts = [(0, 0), (0.34, -0.06), (0.32, 0.05), (0.18, 0.08), (0.1, 0.12)]
    verts = [bm.verts.new((x * s, y, 0)) for x, y in pts]
    bm.faces.new(verts if s > 0 else list(reversed(verts)))


def _build_bat(rng, coll, prefix=""):
    n = lambda s: C.part_name(prefix, s)
    objs = [
        _ball(n(C.NODE_BODY), coll, C.MAT_FUR, 0.08, (0.8, 1.3, 0.9), (0, 0, 0)),
        _ball(n(C.NODE_HEAD), coll, C.MAT_FUR, 0.055, (1, 1, 1),
              (0, 0.1, 0.03), u=8, v=6),
    ]
    for s, nm in ((-1, C.NODE_EAR_L), (1, C.NODE_EAR_R)):
        bm = bmesh.new()
        add_cone(bm, 0.02, 0.002, 0.06, 4,
                 Matrix.Translation((0.03 * s, 0.11, 0.07)))
        objs.append(bm_to_object(bm, n(nm), coll, fauna_material(C.MAT_FUR)))
    for s, nm in ((-1, C.NODE_WING_L), (1, C.NODE_WING_R)):
        def wing(bm, s=s):
            _bat_wing_shape(bm, s)
        objs.append(_wing_obj(n(nm), coll, C.MAT_MEMBRANE,
                              (0.02 * s, 0, 0.02), wing))
    return objs


def _build_mammal(rng, coll, prefix=""):
    n = lambda s: C.part_name(prefix, s)
    objs = [
        _ball(n(C.NODE_BODY), coll, C.MAT_FUR, 0.13, (0.9, 1.5, 0.85),
              (0, 0, 0.11)),
        _ball(n(C.NODE_HEAD), coll, C.MAT_FUR, 0.09, (1, 1, 1),
              (0, 0.17, 0.15), u=9, v=7),
    ]
    bm = bmesh.new()          # nose
    add_cone(bm, 0.03, 0.004, 0.08, 5,
             Matrix.Translation((0, 0.26, 0.13))
             @ Matrix.Rotation(-math.pi / 2, 4, "X"))
    objs.append(bm_to_object(bm, n("Nose"), coll, fauna_material(C.MAT_FUR)))
    for s, nm in ((-1, C.NODE_EAR_L), (1, C.NODE_EAR_R)):
        objs.append(_ball(n(nm), coll, C.MAT_FUR, 0.04, (1, 0.4, 1),
                          (0.05 * s, 0.14, 0.23), u=7, v=5))
    bm = bmesh.new()          # tail: thin tapering cone trailing behind
    add_cone(bm, 0.012, 0.004, 0.3, 5,
             Matrix.Translation((0, -0.24, 0.09))
             @ Matrix.Rotation(math.pi / 2 - 0.35, 4, "X"))
    objs.append(bm_to_object(bm, n(C.NODE_TAIL), coll,
                             fauna_material(C.MAT_DARK)))
    return objs


_BUILDERS = {"bee": _build_bee, "lep": _build_lep, "bird": _build_bird,
             "fly": _build_fly, "beetle": _build_beetle, "bat": _build_bat,
             "mammal": _build_mammal}


def build_critter(kind, rng, coll):
    """Build one critter kind into `coll`; returns the created objects."""
    return _BUILDERS[kind](rng, coll)
