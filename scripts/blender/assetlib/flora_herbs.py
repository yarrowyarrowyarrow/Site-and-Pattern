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

from .mesh_ops import add_blade, add_cone, add_ellipsoid, add_leaf, bm_to_object

HERB_FORMS = {
    "erect":   {"stems": (1, 3), "splay": 0.1, "leaf_from": 0.22,
                "leaf": (0.2, 0.04), "shape": "lance", "per_stem": (6, 10),
                "leaf_tilt": 1.1, "stalks": None, "basal": None, "fine": False},
    "ferny":   {"stems": None, "splay": 0, "leaf_from": 0,
                "leaf": (0.13, 0.02), "shape": "lance", "per_stem": None,
                "leaf_tilt": 1.3, "stalks": (3, 5), "basal": (20, 34), "fine": True},
    "rosette": {"stems": None, "splay": 0, "leaf_from": 0,
                "leaf": (0.26, 0.085), "shape": "ovate", "per_stem": None,
                "leaf_tilt": 1.32, "stalks": (3, 6), "basal": (8, 13), "fine": False},
    "clump":   {"stems": (3, 6), "splay": 0.42, "leaf_from": 0.12,
                "leaf": (0.22, 0.1), "shape": "ovate", "per_stem": (4, 7),
                "leaf_tilt": 0.95, "stalks": None, "basal": (2, 3), "fine": False},
    "grassy":  {"stems": None, "splay": 0, "leaf_from": 0,
                "leaf": (0.9, 0.035), "shape": "strap", "per_stem": None,
                "leaf_tilt": 0.16, "stalks": (2, 4), "basal": (6, 9), "fine": False},
    "mat":     {"stems": None, "splay": 0, "leaf_from": 0,
                "leaf": (0.14, 0.075), "shape": "ovate", "per_stem": None,
                "leaf_tilt": 1.45, "stalks": (2, 4), "basal": (14, 22),
                "fine": False, "low": True},
    "fern":    {"stems": None, "splay": 0, "leaf_from": 0,
                "leaf": (0.95, 0.11), "shape": "lance", "per_stem": None,
                "leaf_tilt": 0.5, "stalks": None, "basal": (6, 9), "fine": False},
}

LAYER_KINDS = {"grass": 3, "aquatic": 3, "vine": 3, "groundcover": 2}


def _rint(rng, lo, hi):
    return lo + int(rng.random() * (hi - lo + 1))


def _stem(bm, rng, r_bot, r_top, h, azimuth, splay):
    rot = (Matrix.Rotation(azimuth, 4, "Z")
           @ Matrix.Rotation(splay, 4, "Y"))
    add_cone(bm, r_bot, r_top, h, 4, rot)
    return rot


def build_herb(form, rng, coll, name_prefix=""):
    from . import conventions as C
    from .materials import preview_material

    F = HERB_FORMS[form]
    bm = bmesh.new()
    lL, lW = F["leaf"]

    if F["stems"]:                      # leafy stems, leaves spiralling up
        n_stems = _rint(rng, *F["stems"])
        for i in range(n_stems):
            az0 = i / max(1, n_stems) * math.tau + rng.random() * 0.7
            splay = F["splay"] * (0.5 + rng.random())
            h = 0.7 + rng.random() * 0.3
            rot = _stem(bm, rng, 0.012, 0.006, h, az0, splay)
            n_leaf = _rint(rng, *F["per_stem"])
            for j in range(n_leaf):
                t = F["leaf_from"] + (1 - F["leaf_from"]) * (
                    j / max(1, n_leaf - 1))
                at = rot @ Vector((0, 0, h * t))
                add_leaf(bm, rng, lL, lW, F["leaf_tilt"],
                         j * 2.39996 + az0, at, F["shape"])

    if F["basal"]:                      # rosette / mound / tuft at the ground
        nb = _rint(rng, *F["basal"])
        for _ in range(nb):
            az = rng.random() * math.tau
            ln = lL * ((0.6 + rng.random() * 0.5) if F["fine"] else 1.0)
            rr = (0.18 if F.get("low") else 0.10) * rng.random()
            at = Vector((math.cos(az) * rr, math.sin(az) * rr,
                         0.01 if F.get("low") else 0.02))
            add_leaf(bm, rng, ln, lW,
                     F["leaf_tilt"] * (0.8 + rng.random() * 0.4), az, at,
                     F["shape"])

    if F["stalks"]:                     # bare flower stalks rising above
        for _ in range(_rint(rng, *F["stalks"])):
            h = 0.75 + rng.random() * 0.25
            _stem(bm, rng, 0.008, 0.005, h, rng.random() * math.tau,
                  0.05 + rng.random() * 0.18)

    mat = preview_material()
    return {C.PART_FOLIAGE: bm_to_object(
        bm, C.part_name(name_prefix, C.PART_FOLIAGE), coll, mat)}


# ── simple layers ────────────────────────────────────────────────────────────

def _layer_grass(bm, rng):
    for _ in range(26 + int(rng.random() * 16)):        # thick meadow clump
        add_blade(bm, rng, 0.62 + rng.random() * 0.5,
                  0.016 + rng.random() * 0.018,
                  0.22 + rng.random() * 0.7, 1.5)


def _layer_aquatic(bm, rng):
    for _ in range(16 + int(rng.random() * 12)):        # stiff strap reeds
        add_blade(bm, rng, 0.85 + rng.random() * 0.35,
                  0.03 + rng.random() * 0.028,
                  0.06 + rng.random() * 0.32, 2.4)


def _layer_vine(bm, rng):
    n_stems = 4 + int(rng.random() * 3)                 # sprawling tangle
    for i in range(n_stems):
        az = i / n_stems * math.tau + rng.random() * 0.8
        splay = 0.6 + rng.random() * 0.55
        h = 0.7 + rng.random() * 0.35
        rot = _stem(bm, rng, 0.013, 0.007, h, az, splay)
        n_leaf = 4 + int(rng.random() * 3)
        for j in range(n_leaf):
            t = 0.3 + 0.65 * (j / max(1, n_leaf - 1))
            at = rot @ Vector((0, 0, h * t))
            add_leaf(bm, rng, 0.16, 0.1, 1.05, j * 2.39996 + az, at, "ovate")


def _layer_groundcover(bm, rng):
    for _ in range(5 + int(rng.random() * 4)):          # low textured mat
        r = 0.08 + rng.random() * 0.07
        az = rng.random() * math.tau
        rad = rng.random() * 0.42
        ys = 0.5 + rng.random() * 0.5
        m = Matrix.Translation((math.cos(az) * rad, math.sin(az) * rad,
                                r * ys * 0.5))
        add_ellipsoid(bm, r, (1.0, 1.0, ys), m, subdiv=1)


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
