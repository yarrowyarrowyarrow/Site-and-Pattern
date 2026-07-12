"""Shrub silhouette builders (Z-up, unit frame).

The five growth-form silhouettes from html/scene3d/02-plants.js SHRUB_FORMS —
vase / spreading / mound / thicket / irregular — as multi-stem woody clumps:
splayed tapered stems (the bark part, a complete winter silhouette) clothed
with faceted foliage masses along their upper length, plus a basal mound for
the dense forms. Parameters echo the tuned JS values.

build_shrub(form, rng) → {'bark': obj, 'foliage': obj}
"""

import math

import bmesh
from mathutils import Matrix, Vector

from .mesh_ops import add_cone, add_ellipsoid, bm_to_object

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


def build_shrub(form, rng, coll, name_prefix=""):
    from . import conventions as C
    from .materials import preview_material

    F = SHRUB_FORMS[form]
    bark = bmesh.new()
    fol = bmesh.new()

    n_stems = _rint(rng, *F["stems"])
    for i in range(n_stems):
        az = i / n_stems * math.tau + rng.random() * 0.7
        splay = F["splay"] * (0.6 + rng.random() * 0.8)
        h = F["stem_h"][0] + rng.random() * (F["stem_h"][1] - F["stem_h"][0])
        rad = 0.016 + rng.random() * 0.012
        rot = Matrix.Rotation(az, 4, "Z") @ Matrix.Rotation(splay, 4, "Y")
        add_cone(bark, rad, rad * 0.4, h, 4, rot)
        n_mass = _rint(rng, *F["masses"])
        for j in range(n_mass):
            t = F["start"] + (1 - F["start"]) * (
                0.7 if n_mass == 1 else j / (n_mass - 1))
            at = rot @ Vector((0, 0, h * t))
            r = F["mass_r"][0] + rng.random() * (F["mass_r"][1] - F["mass_r"][0])
            jitter = Vector(((rng.random() - 0.5) * 0.08,
                             (rng.random() - 0.5) * 0.08, 0))
            m = Matrix.Translation(at + jitter) @ Matrix.Rotation(
                rng.random() * math.pi, 4, "Z")
            sc = tuple(F["shape"][k] * (0.85 + rng.random() * 0.3)
                       for k in range(3))
            add_ellipsoid(fol, r, sc, m, subdiv=1)
    if F["basal"]:
        for _ in range(2 + int(rng.random() * 2)):
            r = 0.15 + rng.random() * 0.08
            m = Matrix.Translation(((rng.random() - 0.5) * 0.34,
                                    (rng.random() - 0.5) * 0.34,
                                    0.10 + rng.random() * 0.12))
            add_ellipsoid(fol, r, F["shape"], m, subdiv=1)

    mat = preview_material()
    return {
        C.PART_BARK: bm_to_object(
            bark, C.part_name(name_prefix, C.PART_BARK), coll, mat),
        C.PART_FOLIAGE: bm_to_object(
            fol, C.part_name(name_prefix, C.PART_FOLIAGE), coll, mat),
    }
