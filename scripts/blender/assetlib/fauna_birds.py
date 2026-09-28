"""The bird builds (F174, V2.97): nine body plans in one file.

Proportions live in :mod:`bird_builds` (bpy-free, so the tests can read them);
this draws them. Same contract as every critter (:mod:`fauna`): Z-up, forward
+Y, per-species colour by material NAME, wing objects with their origin at the
hinge so the viewer can wrap them in a pivot and roll them to beat.

Two pairs of wings per build. ``WingL``/``WingR`` are spread at the build's real
span, and beat in flight; ``FoldL``/``FoldR`` lie along the back, and show on a
perch, walking or swimming. The viewer switches between them (07-wildlife.js
``_wingState``). The spread pair is what makes the model's width its wingspan,
which is how the viewer sizes a bird.
"""

import math

import bpy                                        # isort: skip  (see fauna.py)
import bmesh                                      # noqa: I001
from mathutils import Matrix, Vector

from . import conventions as C
from .bird_builds import BIRD_BUILDS, BIRD_VARIANTS
from .materials import fauna_material
from .mesh_ops import add_cone_between, add_uv_ball, bm_to_object, make_empty


def _obj(name, coll, mat, draw):
    bm = bmesh.new()
    draw(bm)
    return bm_to_object(bm, name, coll, fauna_material(mat))


def _ell(bm, at, radii, tilt=0.0, u=10, v=8):
    """An ellipsoid at ``at``, tipped ``tilt`` about X (+ puts its rear down)."""
    add_uv_ball(bm, 1.0, radii,
                Matrix.Translation(Vector(at)) @ Matrix.Rotation(tilt, 4, "X"),
                u=u, v=v)


def _toward(droop):
    """The forward direction dipped ``droop`` radians below level."""
    return Vector((0.0, math.cos(droop), -math.sin(droop)))


def _build_bird_one(rng, coll, prefix="", build="passerine"):
    B = BIRD_BUILDS[build]
    n = lambda s: C.part_name(prefix, s)
    objs = []
    at, radii = B["body"]
    objs.append(_obj(n(C.NODE_BODY), coll, C.MAT_BODY,
                     lambda bm: _ell(bm, at, radii)))
    at_b, radii_b = B["belly"]
    objs.append(_obj(n("Belly"), coll, C.MAT_BELLY,
                     lambda bm: _ell(bm, at_b, radii_b, u=8, v=6)))
    head_at, head_r = B["head"]
    objs.append(_obj(n(C.NODE_HEAD), coll, C.MAT_BODY,
                     lambda bm: _ell(bm, head_at, (head_r,) * 3, u=9, v=7)))
    if "neck" in B:
        chain = [(Vector(B["body"][0]) + Vector((0, B["body"][1][1] * 0.6,
                                                  B["body"][1][2] * 0.4)),
                  B["neck"][0][1])] + [(Vector(p), r) for p, r in B["neck"]]

        def neck(bm):
            for (a, ra), (b, rb) in zip(chain, chain[1:]):
                add_cone_between(bm, a, b, ra, rb, 7)
        objs.append(_obj(n("Neck"), coll, C.MAT_BODY, neck))

    # The beak: a cone from its base along the forward direction, dipped by its
    # droop (a hawk's hooks down, a crane's is nearly level).
    base, length, radius, droop = B["beak"]
    d = _toward(droop)

    def beak(bm):
        add_cone_between(bm, Vector(base), Vector(base) + d * length,
                         radius, radius * 0.15, 6)
    objs.append(_obj(n(C.NODE_BEAK), coll, C.MAT_DARK, beak))

    t_at, t_radii, t_tilt = B["tail"]
    objs.append(_obj(n(C.NODE_TAIL), coll, C.MAT_WING,
                     lambda bm: _ell(bm, t_at, t_radii, t_tilt, u=8, v=6)))
    if "bustle" in B:
        bu_at, bu_radii = B["bustle"]
        objs.append(_obj(n("Bustle"), coll, C.MAT_WING,
                         lambda bm: _ell(bm, bu_at, bu_radii, 0.4, u=8, v=6)))

    if "disc" in B:
        # The owl's face, looking along the disc's droop from the head.
        out, r, droop = B["disc"]
        f = _toward(droop)
        centre = Vector(head_at) + f * out
        rot = f.to_track_quat("Z", "Y").to_matrix().to_4x4()

        def disc(bm):
            add_uv_ball(bm, 1.0, (r, r, 0.03), Matrix.Translation(centre) @ rot,
                        u=10, v=6)
        objs.append(_obj(n("Disc"), coll, C.MAT_BELLY, disc))
        spacing, er = B["eyes"]
        side = Vector((1.0, 0.0, 0.0))
        up = side.cross(f).normalized()      # toward the crown of the head

        def eyes(bm):
            for s in (-1, 1):
                add_uv_ball(bm, er, (1, 1, 1), Matrix.Translation(
                    centre + side * (spacing * s) + up * 0.02 + f * 0.025), u=6, v=4)
        objs.append(_obj(n("Eyes"), coll, C.MAT_DARK, eyes))
        sp, tl, tr = B["tufts"]
        # "Up" on the perch: the build is level and tipped up by its perch
        # pitch there, so the tufts point along that pitch in the build.
        from .bird_builds import BIRD_PERCH_PITCH   # noqa: PLC0415
        p = BIRD_PERCH_PITCH.get(build, 0.0)
        tip_dir = Vector((0.0, math.sin(p), math.cos(p)))

        def tufts(bm):
            for s in (-1, 1):
                a = Vector(head_at) + Vector((sp * s, 0.0, 0.0)) + tip_dir * (head_r * 0.8)
                add_cone_between(bm, a, a + tip_dir * tl, tr, tr * 0.2, 5)
        objs.append(_obj(n("Tufts"), coll, C.MAT_BODY, tufts))

    if "legs" in B:
        hip, lr = B["legs"]

        def legs(bm):
            for s in (-1, 1):
                h = Vector((hip[0] * s, hip[1], hip[2]))
                foot = Vector((hip[0] * s, hip[1] + 0.02, lr * 0.5))
                add_cone_between(bm, h, foot, lr, lr * 0.8, 5)
                # Toes: a flat spread under the foot.
                add_uv_ball(bm, 1.0, (lr * 2.2, lr * 3.2, lr * 0.5),
                            Matrix.Translation((foot.x, foot.y + lr, lr * 0.5)),
                            u=6, v=4)
        objs.append(_obj(n("Legs"), coll, C.MAT_DARK, legs))

    f_at, f_radii, f_tilt = B["fold"]
    for s, nm in ((-1, "FoldL"), (1, "FoldR")):
        a = (f_at[0] * s, f_at[1], f_at[2])
        objs.append(_obj(n(nm), coll, C.MAT_WING,
                         lambda bm, a=a: _ell(bm, a, f_radii, f_tilt, u=8, v=6)))

    # Spread wings at the build's real span. The origin is the hinge; the wing
    # reaches (span/2 - hinge) out from it, so tip to tip is exactly the span.
    hinge, span, chord = B["wing"]
    half = (span / 2.0 - hinge[0]) / 2.0
    for s, nm in ((-1, C.NODE_WING_L), (1, C.NODE_WING_R)):
        bm = bmesh.new()
        add_uv_ball(bm, 1.0, (half, chord, 0.018),
                    Matrix.Translation((half * s, 0.0, 0.0)), u=8, v=4)
        wing = bm_to_object(bm, n(nm), coll, fauna_material(C.MAT_WING))
        wing.location = Vector((hinge[0] * s, hinge[1], hinge[2]))
        objs.append(wing)
    return objs


def build_bird(rng, coll, prefix=""):
    """All nine builds in one file, each under its own prefixed root."""
    objs = []
    for variant in BIRD_VARIANTS:
        root = make_empty(variant, coll)
        children = _build_bird_one(rng, coll, variant, variant)
        for c in children:
            c.parent = root
            c.matrix_parent_inverse = root.matrix_world.inverted()
        objs.append(root)
        objs.extend(children)
    return objs
