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

import bmesh
from mathutils import Matrix, Vector

from . import conventions as C
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

def _build_bee(rng, coll, prefix=""):
    n = lambda s: C.part_name(prefix, s)
    objs = []
    body = _ball(n(C.NODE_BODY), coll, C.MAT_FUZZ, 0.5, (1, 1, 0.9), (0, 0, 0))
    head = _ball(n(C.NODE_HEAD), coll, C.MAT_DARK, 0.32, (1, 1, 1),
                 (0, 0.62, 0), u=8, v=6)
    abdomen = _ball(n(C.NODE_ABDOMEN), coll, C.MAT_DARK, 0.55,
                    (0.92, 1.45, 0.88), (0, -0.8, -0.03))
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
    for i in range(3):
        band = _ball(n(C.NODE_BANDS[i]), coll, C.MAT_FUZZ, 0.57,
                     (0.94, 0.36, 0.90), (0, -(0.5 + i * 0.45), -0.03),
                     u=8, v=6)
        objs.append(band)
    objs.append(_ball(n("Tip"), coll, C.MAT_DARK, 0.30, (0.9, 1.1, 0.85),
                      (0, -1.31, -0.04), u=8, v=6))
    # Wings: swept-back translucent ovals, hinge on the thorax shoulder.
    for s, nm in ((-1, C.NODE_WING_L), (1, C.NODE_WING_R)):
        def wing(bm, s=s):
            _flat_ellipse(bm, 0.55, (0.5, 1.0),
                          Matrix.Translation((0.42 * s, -0.18, 0.02))
                          @ Matrix.Rotation(-0.25 * s, 4, "Z")
                          @ Matrix.Rotation(0.1 * s, 4, "Y"))
        objs.append(_wing_obj(n(nm), coll, C.MAT_WING,
                              (0.14 * s, -0.05, 0.38), wing))
    return objs


# ── lep (butterfly / moth: 06-fly.js makeButterflyAvatar) ────────────────────

def _build_lep(rng, coll, prefix=""):
    n = lambda s: C.part_name(prefix, s)
    objs = [
        _ball(n(C.NODE_BODY), coll, C.MAT_DARK, 0.16, (1, 1.4, 1), (0, 0, 0)),
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
    for s, nm in ((-1, C.NODE_WING_L), (1, C.NODE_WING_R)):
        def wing(bm, s=s):
            _flat_ellipse(bm, 0.42, (0.88, 0.98),                 # rim peeks out
                          Matrix.Translation((0.42 * s, 0.1, -0.004)),
                          segments=14)
        objs.append(_wing_obj(n("Rim" + nm[-1]), coll, C.MAT_EDGE,
                              (0, 0, 0), wing))
        def fore(bm, s=s):
            _flat_ellipse(bm, 0.42, (0.85, 0.95),
                          Matrix.Translation((0.42 * s, 0.1, 0)), segments=14)
        def hind(bm, s=s):
            _flat_ellipse(bm, 0.30, (0.9, 1.05),
                          Matrix.Translation((0.40 * s, -0.3, -0.002)),
                          segments=12)
        f = _wing_obj(n("Fore" + nm[-1]), coll, C.MAT_FORE, (0, 0, 0), fore)
        h = _wing_obj(n("Hind" + nm[-1]), coll, C.MAT_HIND, (0, 0, 0), hind)
        # Group the three under the named wing node (an empty at the hinge).
        pivot = make_empty(n(nm), coll)
        _parent([objs[-1], f, h], pivot)
        objs.append(pivot)
    return objs


# ── bird (07-wildlife.js makeBirdCritter) ────────────────────────────────────

def _build_bird(rng, coll, prefix=""):
    n = lambda s: C.part_name(prefix, s)
    objs = [
        _ball(n(C.NODE_BODY), coll, C.MAT_BODY, 0.16, (0.85, 1.35, 0.9),
              (0, 0, 0)),
        _ball(n("Belly"), coll, C.MAT_BELLY, 0.13, (0.7, 1.0, 0.8),
              (0, -0.06, -0.05), u=8, v=6),
        _ball(n(C.NODE_HEAD), coll, C.MAT_BODY, 0.11, (1, 1, 1),
              (0, 0.16, 0.12), u=9, v=7),
    ]
    bm = bmesh.new()          # beak: cone forward (+Y), origin at its base
    add_cone(bm, 0.03, 0.004, 0.09, 5, Matrix.Rotation(-math.pi / 2, 4, "X"))
    beak = bm_to_object(bm, n(C.NODE_BEAK), coll, fauna_material(C.MAT_DARK))
    beak.location = Vector((0, 0.28, 0.12))
    objs.append(beak)
    bm = bmesh.new()          # tail: flat slab, tilted up behind
    bmesh.ops.create_cube(bm, size=1.0,
                          matrix=Matrix.Translation((0, -0.28, 0.02))
                          @ Matrix.Rotation(-0.3, 4, "X")
                          @ Matrix.Diagonal((0.12, 0.22, 0.02, 1)))
    objs.append(bm_to_object(bm, n(C.NODE_TAIL), coll,
                             fauna_material(C.MAT_WING)))
    for s, nm in ((-1, C.NODE_WING_L), (1, C.NODE_WING_R)):
        def wing(bm, s=s):
            add_uv_ball(bm, 0.14, (0.5, 1.0, 0.14),
                        Matrix.Translation((0.12 * s, -0.02, 0)), u=8, v=4)
        objs.append(_wing_obj(n(nm), coll, C.MAT_WING,
                              (0.08 * s, -0.02, 0.04), wing))
    return objs


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
