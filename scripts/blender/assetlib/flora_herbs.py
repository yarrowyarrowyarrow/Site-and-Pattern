"""Herbaceous growth-form + layer builders (Z-up, unit frame).

The seven herb forms from html/scene3d/03-herbs.js HERB_FORMS — erect /
ferny / rosette / clump / grassy / mat / fern — built from real leaf blades
with width profiles (lance / ovate / strap), leafy stems and bare flower
stalks (the viewer's flower sprite lands on top). Plus the four simple-layer
kinds: grass and aquatic blade tufts, sprawling vines, groundcover domes.
All single-part ('foliage') — herb stems are green.

build_herb(form, rng)          → {'foliage': obj}
build_layer(kind, variant_rng) → {'foliage': obj}
"""

import math

import bmesh
from mathutils import Matrix, Vector

from .conventions import HERB_ASPECT, LAYER_ASPECT
from .mesh_ops import (add_blade, add_cone, add_cone_between, add_ellipsoid,
                       add_leaf, bm_to_object, leaf_extent, shape_to_aspect)

# Each form is shaped to its real height ÷ canopy, which lives with the rest of
# the contract in conventions.HERB_ASPECT / LAYER_ASPECT — shaping to it keeps
# the instance transform undistorted (see the unit-frame note there).
HERB_FORMS = {
    "erect":   {"stems": (1, 3), "splay": 0.1, "leaf_from": 0.22,
                "leaf": (0.2, 0.04), "shape": "lance", "per_stem": (6, 10),
                "leaf_tilt": 1.1, "stalks": None, "basal": None, "fine": False},
    "ferny":   {"stems": None, "splay": 0, "leaf_from": 0,
                "leaf": (0.13, 0.02), "shape": "lance", "per_stem": None,
                "leaf_tilt": 1.3, "stalks": (3, 5), "basal": (20, 34),
                "fine": True},
    "rosette": {"stems": None, "splay": 0, "leaf_from": 0,
                "leaf": (0.26, 0.085), "shape": "ovate", "per_stem": None,
                "leaf_tilt": 1.32, "stalks": (3, 6), "basal": (8, 13),
                "fine": False},
    "clump":   {"stems": (3, 6), "splay": 0.42, "leaf_from": 0.12,
                "leaf": (0.22, 0.1), "shape": "ovate", "per_stem": (4, 7),
                "leaf_tilt": 0.95, "stalks": None, "basal": (2, 3),
                "fine": False},
    "grassy":  {"stems": None, "splay": 0, "leaf_from": 0,
                "leaf": (0.9, 0.035), "shape": "strap", "per_stem": None,
                "leaf_tilt": 0.16, "stalks": (2, 4), "basal": (6, 9),
                "fine": False},
    "mat":     {"stems": None, "splay": 0, "leaf_from": 0,
                "leaf": (0.14, 0.075), "shape": "ovate", "per_stem": None,
                "leaf_tilt": 1.45, "stalks": (2, 4), "basal": (14, 22),
                "fine": False, "low": True},
    "fern":    {"stems": None, "splay": 0, "leaf_from": 0,
                "leaf": (0.95, 0.11), "shape": "lance", "per_stem": None,
                "leaf_tilt": 0.5, "stalks": None, "basal": (6, 9),
                "fine": False},
}

LAYER_KINDS = {"grass": 3, "aquatic": 3, "vine": 3, "groundcover": 2}

# Layers built entirely from flat blades and leaves, so build_all can finish
# them with the exact mesh-measuring correction (mesh_ops.squash_to_aspect).
# Groundcover is deliberately absent — it is round domes, which that correction
# would flatten into discs; it stays on anchor shaping.
FLAT_LEAF_LAYERS = frozenset({"grass", "aquatic", "vine"})


def _rint(rng, lo, hi):
    return lo + int(rng.random() * (hi - lo + 1))


def build_herb(form, rng, coll, name_prefix=""):
    from . import conventions as C
    from .materials import preview_material

    F = HERB_FORMS[form]
    bm = bmesh.new()
    lL, lW = F["leaf"]

    # Collect the plant in its natural frame first (leaves are what set an
    # herb's width, so they carry a scale factor of their own), then shape the
    # whole thing to the form's real aspect before stamping — a pussytoes mat
    # spreads flat instead of being stretched upright by the instance transform.
    leaves = []          # [anchor Vector, length, width, tilt, azimuth]
    stems = []           # (rot, h, r_bot, r_top) — axial, unaffected by shaping
    if F["stems"]:                      # leafy stems, leaves spiralling up
        n_stems = _rint(rng, *F["stems"])
        for i in range(n_stems):
            az0 = i / max(1, n_stems) * math.tau + rng.random() * 0.7
            splay = F["splay"] * (0.5 + rng.random())
            h = 0.7 + rng.random() * 0.3
            rot = (Matrix.Rotation(az0, 4, "Z")
                   @ Matrix.Rotation(splay, 4, "Y"))
            stems.append((rot, h, 0.012, 0.006))
            n_leaf = _rint(rng, *F["per_stem"])
            for j in range(n_leaf):
                t = F["leaf_from"] + (1 - F["leaf_from"]) * (
                    j / max(1, n_leaf - 1))
                at = rot @ Vector((0, 0, h * t))
                leaves.append([at, lL, lW, F["leaf_tilt"], j * 2.39996 + az0])

    if F["basal"]:                      # rosette / mound / tuft at the ground
        nb = _rint(rng, *F["basal"])
        for _ in range(nb):
            az = rng.random() * math.tau
            ln = lL * ((0.6 + rng.random() * 0.5) if F["fine"] else 1.0)
            rr = (0.18 if F.get("low") else 0.10) * rng.random()
            at = Vector((math.cos(az) * rr, math.sin(az) * rr,
                         0.01 if F.get("low") else 0.02))
            leaves.append([at, ln, lW,
                           F["leaf_tilt"] * (0.8 + rng.random() * 0.4), az])

    if F["stalks"]:                     # bare flower stalks rising above
        for _ in range(_rint(rng, *F["stalks"])):
            h = 0.75 + rng.random() * 0.25
            az = rng.random() * math.tau
            splay = 0.05 + rng.random() * 0.18
            stems.append(((Matrix.Rotation(az, 4, "Z")
                           @ Matrix.Rotation(splay, 4, "Y")), h, 0.008, 0.005))

    # A leaf's own length is most of the horizontal reach, so the shaping factor
    # applies to the blade as well as its anchor — the leaf keeps its shape.
    # That couples the two axes: shrinking a rosette's leaves lowers the plant
    # as well as narrowing it, so the factor is found by iterating to a fixed
    # point rather than divided out once (a single pass lands ~35% off on the
    # basal forms, where leaves are the whole plant).
    ext = [leaf_extent(ln, t, F["shape"]) for _a, ln, _w, t, _az in leaves]
    stem_h = max([h for _r, h, _a, _b in stems] + [1e-6])
    reach = max([math.hypot(a.x, a.y) + e[0]
                 for (a, *_r), e in zip(leaves, ext)] + [1e-6])
    k = 1.0
    for _ in range(24):
        tallest = max([stem_h] + [a.z + e[1] * k
                                  for (a, *_r), e in zip(leaves, ext)])
        k = (tallest / HERB_ASPECT[form] / 2.0) / reach
    for leaf in leaves:
        leaf[0] = Vector((leaf[0].x * k, leaf[0].y * k, leaf[0].z))
        leaf[1] *= k
        leaf[2] *= k

    for rot, h, r_bot, r_top in stems:
        add_cone(bm, r_bot, r_top, h, 4, rot)
    for at, ln, wd, tilt, az in leaves:
        add_leaf(bm, rng, ln, wd, tilt, az, at, F["shape"])

    mat = preview_material()
    return {C.PART_FOLIAGE: bm_to_object(
        bm, C.part_name(name_prefix, C.PART_FOLIAGE), coll, mat)}


# ── simple layers ────────────────────────────────────────────────────────────

def _blades(bm, rng, n, height_fn, hw_fn, lean_fn, erect, aspect):
    """Stamp a tuft of arched blades shaped to ``aspect``.

    A blade's horizontal reach is its lean, so the tuft is generated first and
    every lean scaled by one factor — the blades bend out further or stand
    tighter, rather than the whole tuft being stretched by the instance
    transform.
    """
    specs = [(height_fn(), hw_fn(), lean_fn()) for _ in range(n)]
    tallest = max([h for h, _w, _l in specs] + [1e-6])
    reach = max([ln for _h, _w, ln in specs] + [1e-6])
    k = (tallest / aspect / 2.0) / reach
    for h, hw, ln in specs:
        add_blade(bm, rng, h, hw, ln * k, erect)


def _layer_grass(bm, rng):
    _blades(bm, rng, 26 + int(rng.random() * 16),       # thick meadow clump
            lambda: 0.62 + rng.random() * 0.5,
            lambda: 0.016 + rng.random() * 0.018,
            lambda: 0.22 + rng.random() * 0.7, 1.5, LAYER_ASPECT["grass"])


def _layer_aquatic(bm, rng):
    _blades(bm, rng, 16 + int(rng.random() * 12),       # stiff strap reeds
            lambda: 0.85 + rng.random() * 0.35,
            lambda: 0.03 + rng.random() * 0.028,
            lambda: 0.06 + rng.random() * 0.32, 2.4, LAYER_ASPECT["aquatic"])


def _layer_vine(bm, rng):
    n_stems = 4 + int(rng.random() * 3)                 # sprawling tangle
    stems, leaves, pts = [], [], []
    for i in range(n_stems):
        az = i / n_stems * math.tau + rng.random() * 0.8
        splay = 0.6 + rng.random() * 0.55
        h = 0.7 + rng.random() * 0.35
        rot = (Matrix.Rotation(az, 4, "Z") @ Matrix.Rotation(splay, 4, "Y"))
        base = Vector((0, 0, 0))
        tip = rot @ Vector((0, 0, h))
        stems.append((base, tip))
        pts.extend((base, tip))
        n_leaf = 4 + int(rng.random() * 3)
        for j in range(n_leaf):
            t = 0.3 + 0.65 * (j / max(1, n_leaf - 1))
            at = rot @ Vector((0, 0, h * t))
            leaves.append((at, j * 2.39996 + az))
            pts.append(at)
    # A vine's leaves reach well past the stem tips, so they are the overhang.
    leaf_len, leaf_wid, leaf_tilt = 0.16, 0.1, 1.05
    lr, lz = leaf_extent(leaf_len, leaf_tilt, "ovate")
    shape_to_aspect(pts, LAYER_ASPECT["vine"],
                    radii=[0.0] * (2 * len(stems)) + [lr] * len(leaves),
                    radii_z=[0.0] * (2 * len(stems)) + [lz] * len(leaves))
    for base, tip in stems:
        add_cone_between(bm, base, tip, 0.013, 0.007, 4)
    for at, az in leaves:
        add_leaf(bm, rng, leaf_len, leaf_wid, leaf_tilt, az, at, "ovate")


def _layer_groundcover(bm, rng):
    domes, pts = [], []
    for _ in range(5 + int(rng.random() * 4)):          # low textured mat
        r = 0.08 + rng.random() * 0.07
        az = rng.random() * math.tau
        rad = rng.random() * 0.42
        ys = 0.5 + rng.random() * 0.5
        centre = Vector((math.cos(az) * rad, math.sin(az) * rad, r * ys * 0.5))
        domes.append((centre, r, ys))
        pts.append(centre)
    # Domes keep their authored size; only how far they sprawl is shaped, so a
    # groundcover reads as a low mat rather than a stretched hummock.
    shape_to_aspect(pts, LAYER_ASPECT["groundcover"],
                    radii=[r for _c, r, _ys in domes],
                    radii_z=[r * ys for _c, r, ys in domes])
    for centre, r, ys in domes:
        add_ellipsoid(bm, r, (1.0, 1.0, ys), Matrix.Translation(centre),
                      subdiv=1)


_LAYER_BUILDERS = {"grass": _layer_grass, "aquatic": _layer_aquatic,
                   "vine": _layer_vine, "groundcover": _layer_groundcover}


def build_layer(kind, rng, coll, name_prefix=""):
    from . import conventions as C
    from .materials import preview_material

    bm = bmesh.new()
    _LAYER_BUILDERS[kind](bm, rng)
    mat = preview_material()
    return {C.PART_FOLIAGE: bm_to_object(
        bm, C.part_name(name_prefix, C.PART_FOLIAGE), coll, mat)}
