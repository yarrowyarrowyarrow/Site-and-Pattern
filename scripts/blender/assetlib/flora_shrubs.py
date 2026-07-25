"""Shrub silhouette builders (Z-up, unit frame).

The five growth-form silhouettes from html/scene3d/02-plants.js SHRUB_FORMS —
vase / spreading / mound / thicket / irregular — as multi-stem woody clumps:
a branching cane skeleton (the bark part, a complete winter silhouette) clothed
in REAL LEAVES whose outline, size and arrangement come from the species' own
morphology (schema v47/v48). Parameters echo the tuned JS values.

Until V2.29 a shrub was a few straight cones with faceted ellipsoids stuck on
them — the "lollipop" look — and `leaf_shape`/`leaf_arrangement` had no
geometric consumer at all. It was also spending 12-30% of its triangle budget.

build_shrub(form, rng, grain=, leaf_shape=, arrangement=)
    → {'bark': obj, 'foliage': obj}
"""

import math

import bmesh
from mathutils import Matrix, Vector

from .mesh_ops import (COMPOUND_SHAPES, CONE_TRIS, add_blade_or_leaf,
                       add_cone_between, bm_to_object, leaf_extent,
                       leaf_width_for, shape_to_aspect, thin_leaf_nodes)

# Each form is shaped to its real height ÷ canopy, which lives with the rest of
# the contract in conventions.SHRUB_ASPECT, so the instance transform stays
# undistorted — see the unit-frame note there.
SHRUB_FORMS = {
    "vase":      {"stems": (4, 6), "splay": 0.26, "stem_h": (0.78, 1.0),
                  "masses": (2, 3), "start": 0.45, "mass_r": (0.16, 0.24),
                  "shape": (0.92, 0.92, 1.05), "basal": False},
    "spreading": {"stems": (4, 6), "splay": 0.62, "stem_h": (0.6, 0.85),
                  "masses": (2, 3), "start": 0.38, "mass_r": (0.18, 0.27),
                  "shape": (1.25, 1.25, 0.7), "basal": True},
    "mound":     {"stems": (5, 8), "splay": 0.52, "stem_h": (0.42, 0.66),
                  "masses": (2, 3), "start": 0.18, "mass_r": (0.16, 0.22),
                  "shape": (1.06, 1.06, 0.86), "basal": True},
    "thicket":   {"stems": (7, 11), "splay": 0.42, "stem_h": (0.55, 0.92),
                  "masses": (1, 2), "start": 0.34, "mass_r": (0.11, 0.17),
                  "shape": (0.9, 0.9, 1.0), "basal": True},
    "irregular": {"stems": (3, 6), "splay": 0.5, "stem_h": (0.5, 0.98),
                  "masses": (1, 3), "start": 0.3, "mass_r": (0.12, 0.2),
                  "shape": (1.0, 1.0, 0.9), "basal": False},
}


def _rint(rng, lo, hi):
    return lo + int(rng.random() * (hi - lo + 1))


def _canes(rng, F, n_stems):
    """A branching cane skeleton: each stem rises from the base and forks once
    or twice near its top. Returns [(start, end, r_bot, r_top, is_twig)].

    Shrubs used to be straight cones with ellipsoids stuck on them; a real
    multi-stemmed shrub is a spray of canes that divide, and the division is
    most of what tells a currant from a saskatoon at a glance.
    """
    segs = []
    for i in range(n_stems):
        az = i / n_stems * math.tau + rng.random() * 0.7
        splay = F["splay"] * (0.6 + rng.random() * 0.8)
        h = F["stem_h"][0] + rng.random() * (F["stem_h"][1] - F["stem_h"][0])
        rad = 0.016 + rng.random() * 0.012
        rot = Matrix.Rotation(az, 4, "Z") @ Matrix.Rotation(splay, 4, "Y")
        base = Vector((0, 0, 0))
        fork = rot @ Vector((0, 0, h * F["start"]))
        tip = rot @ Vector((0, 0, h))
        segs.append((base, fork, rad, rad * 0.7, False))
        segs.append((fork, tip, rad * 0.7, rad * 0.4, False))
        # Twigs ALONG the upper cane — fork to tip — because the leaves hang on
        # twigs and nowhere else. Sprouting them all at the fork (the first cut
        # of this builder) left the top two thirds of a 5 m chokecherry bare: it
        # read as dead sticks above a small green base, which is what a user's
        # screenshot caught. The foliage envelope has to span the crown the same
        # way the ellipsoid masses it replaced did (start → tip).
        n_twig = 4 + int(rng.random() * 4)
        for k in range(n_twig):
            t = 0.12 + 0.88 * (k / max(1, n_twig - 1))
            at = fork.lerp(tip, t)
            spread = 0.45 + rng.random() * 0.6
            twig_rot = (Matrix.Rotation(az + k * 2.39996 + rng.random() * 0.4,
                                        4, "Z")
                        @ Matrix.Rotation(splay + spread, 4, "Y"))
            # Shorter toward the tip, so the crown tapers instead of flaring.
            length = h * (0.16 + rng.random() * 0.20) * (1.0 - 0.35 * t)
            segs.append((at, at + (twig_rot @ Vector((0, 0, length))),
                         rad * 0.4, rad * 0.18, True))
    return segs


def build_shrub(form, rng, coll, name_prefix="", grain=1, leaf_shape=None,
                arrangement=None):
    """One shrub archetype: a branching cane skeleton clothed in real leaves.

    ``grain`` (0/1/2) sets leaf size from the species' leaf length against its
    height; ``leaf_shape`` its blade outline; ``arrangement`` whether leaves sit
    in opposite pairs (dogwood, viburnum, honeysuckle) or alternate (rose,
    saskatoon, currant) — which is the field mark that separates them.
    """
    from . import conventions as C
    from .materials import preview_material

    F = SHRUB_FORMS[form]
    bark = bmesh.new()
    fol = bmesh.new()
    shape = leaf_shape or "ovate"
    opposite = (arrangement or "") == "opposite"
    whorled = (arrangement or "") == "whorled"
    # Leaf length as a fraction of the shrub's own height, by grain class. A
    # shrub is metres tall with centimetre leaves, so these are much smaller
    # fractions than a forb's.
    leaf_len = (0.055, 0.085, 0.13)[max(0, min(2, int(grain)))]
    if shape in COMPOUND_SHAPES:
        leaf_len *= 1.5          # a compound leaf is a whole spray, so longer
    leaf_wid = leaf_width_for(shape, leaf_len)

    segs = _canes(rng, F, _rint(rng, *F["stems"]))
    per_node = 2 if opposite else (3 if whorled else 1)
    nodes = []                   # per node: [[anchor, tilt, azimuth], ...]
    for start, end, _rb, _rt, is_twig in segs:
        if not is_twig:
            continue
        n_nodes = 4 + int(rng.random() * 4)
        for j in range(n_nodes):
            t = 0.25 + 0.75 * (j / max(1, n_nodes - 1))
            at = start.lerp(end, t)
            base_az = (j * 1.5708 if per_node > 1 else j * 2.39996)
            nodes.append([[at, 0.75 + rng.random() * 0.5,
                           base_az + k * math.tau / per_node
                           + rng.random() * 0.3] for k in range(per_node)])
    # A rose's compound leaf costs nine times a dogwood's simple one, so the leaf
    # population is sized to what the budget affords rather than fixed — bare
    # twigs read as a real shrub, a blown budget fails the export.
    top_node = max(nodes, key=lambda n: n[0][0].z) if nodes else None
    nodes = thin_leaf_nodes(nodes, shape, C.TRI_BUDGETS["shrub"],
                            len(segs) * CONE_TRIS)
    # Thinning strides through the node list, which is in cane order, not height
    # order — so the highest node on the plant can be one of the ones it drops,
    # and the shrub grows a bare top again. Put it back: it is one node, and a
    # bare crown is the exact failure tests/test_model_assets.py guards.
    if top_node is not None and top_node not in nodes:
        nodes.append(top_node)
    leaves = [leaf for node in nodes for leaf in node]

    # Narrow (or widen) the clump to the form's real aspect before stamping —
    # anchors move, leaves keep their authored size (mesh_ops.shape_to_aspect).
    pts = [p for s in segs for p in (s[0], s[1])] + [l[0] for l in leaves]
    reach = [leaf_extent(leaf_len, l[1], shape) for l in leaves]
    shape_to_aspect(
        pts, C.SHRUB_ASPECT[form],
        radii=[0.0] * (2 * len(segs)) + [r[0] for r in reach],
        radii_z=[0.0] * (2 * len(segs)) + [r[1] for r in reach])

    for start, end, r_bot, r_top, _twig in segs:
        add_cone_between(bark, start, end, r_bot, r_top, 4)
    for at, tilt, az in leaves:
        add_blade_or_leaf(fol, rng, leaf_len, leaf_wid, tilt, az, at, shape)

    mat = preview_material()
    return {
        C.PART_BARK: bm_to_object(
            bark, C.part_name(name_prefix, C.PART_BARK), coll, mat),
        C.PART_FOLIAGE: bm_to_object(
            fol, C.part_name(name_prefix, C.PART_FOLIAGE), coll, mat),
    }
