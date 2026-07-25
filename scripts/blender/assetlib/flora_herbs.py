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

from .conventions import GRAIN_LEAF_SCALE, HERB_ASPECT, LAYER_ASPECT
from .mesh_ops import (CONE_TRIS, add_blade, add_blade_or_leaf,
                       add_cone_between, add_ellipsoid, add_leaf,
                       bm_to_object, leaf_extent, leaf_width_for,
                       shape_to_aspect, thin_leaf_nodes)

# Each form is shaped to its real height ÷ canopy, which lives with the rest of
# the contract in conventions.HERB_ASPECT / LAYER_ASPECT — shaping to it keeps
# the instance transform undistorted (see the unit-frame note there).
# Leaf and stem counts are ~3x what they were before V2.29. 211 of the 434
# species in the catalogue are wildflowers, and a 119-plant meadow was reading
# as scattered sticks on painted ground: each plant carried a dozen leaves at
# 130-380 triangles against a 1200 budget, so four fifths of the allowance was
# going unspent while the app's main subject looked sparse. This is the same
# plant drawn properly, not more plants (the design says how many there are).
HERB_FORMS = {
    "erect":   {"stems": (2, 4), "splay": 0.1, "leaf_from": 0.22,
                "leaf": (0.2, 0.04), "shape": "lance", "per_stem": (16, 26),
                "leaf_tilt": 1.1, "stalks": None, "basal": None, "fine": False},
    # Yarrow, tansy, meadow-rue: the flowering stems are LEAFY, not naked scapes.
    # `stalk_leaves` puts leaves up them; without it this form drew a low mound
    # with four bare wires sticking out of it, which is a rosette plant's
    # silhouette, not a yarrow's.
    "ferny":   {"stems": None, "splay": 0, "leaf_from": 0,
                "leaf": (0.13, 0.02), "shape": "lance", "per_stem": None,
                "leaf_tilt": 1.3, "stalks": (4, 6), "basal": (56, 92),
                "stalk_leaves": (5, 9), "fine": True},
    "rosette": {"stems": None, "splay": 0, "leaf_from": 0,
                "leaf": (0.26, 0.085), "shape": "ovate", "per_stem": None,
                "leaf_tilt": 1.32, "stalks": (4, 7), "basal": (26, 40),
                "fine": False},
    "clump":   {"stems": (4, 7), "splay": 0.42, "leaf_from": 0.12,
                "leaf": (0.22, 0.1), "shape": "ovate", "per_stem": (11, 18),
                "leaf_tilt": 0.95, "stalks": None, "basal": (5, 8),
                "fine": False},
    "grassy":  {"stems": None, "splay": 0, "leaf_from": 0,
                "leaf": (0.9, 0.035), "shape": "strap", "per_stem": None,
                "leaf_tilt": 0.16, "stalks": (3, 5), "basal": (20, 30),
                "fine": False},
    "mat":     {"stems": None, "splay": 0, "leaf_from": 0,
                "leaf": (0.14, 0.075), "shape": "ovate", "per_stem": None,
                "leaf_tilt": 1.45, "stalks": (2, 4), "basal": (40, 62),
                "fine": False, "low": True},
    "fern":    {"stems": None, "splay": 0, "leaf_from": 0,
                "leaf": (0.95, 0.11), "shape": "lance", "per_stem": None,
                "leaf_tilt": 0.5, "stalks": None, "basal": (14, 20),
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


def build_herb(form, rng, coll, name_prefix="", grain=1, leaf_shape=None,
               arrangement=None):
    """One herbaceous archetype.

    ``grain`` (0 fine · 1 medium · 2 coarse) scales the blade: a species' leaf
    length relative to its own height, bucketed, because instancing can only
    scale a whole plant and not its leaves (conventions.grain_class).
    ``leaf_shape`` is the species' recorded blade outline (schema v48) and
    ``arrangement`` where the leaves sit — opposite leaves are stamped in pairs
    rather than spiralled, which is most of what separates a penstemon from a
    goldenrod at a glance.
    """
    from . import conventions as C
    from .materials import preview_material

    F = HERB_FORMS[form]
    bm = bmesh.new()
    shape = leaf_shape or F["shape"]
    lL = F["leaf"][0] * GRAIN_LEAF_SCALE[max(0, min(2, int(grain)))]
    # Width follows the OUTLINE, not the form: a 20 cm arrowhead balsamroot leaf
    # and a 20 cm iris strap are the same length and nothing like the same leaf.
    lW = leaf_width_for(shape, lL)
    opposite = (arrangement or "") == "opposite"
    whorled = (arrangement or "") == "whorled"

    # Collect the plant in its natural frame first (leaves are what set an
    # herb's width, so they carry a scale factor of their own), then shape the
    # whole thing to the form's real aspect before stamping — a pussytoes mat
    # spreads flat instead of being stretched upright by the instance transform.
    nodes = []           # per node: [[anchor Vector, length, width, tilt, az], …]
    stems = []           # (base, tip, r_bot, r_top) — re-stamped after shaping
    if F["stems"]:                      # leafy stems, leaves spiralling up
        n_stems = _rint(rng, *F["stems"])
        for i in range(n_stems):
            az0 = i / max(1, n_stems) * math.tau + rng.random() * 0.7
            splay = F["splay"] * (0.5 + rng.random())
            h = 0.7 + rng.random() * 0.3
            rot = (Matrix.Rotation(az0, 4, "Z")
                   @ Matrix.Rotation(splay, 4, "Y"))
            stems.append([Vector((0, 0, 0)), rot @ Vector((0, 0, h)),
                          0.012, 0.006])
            n_leaf = _rint(rng, *F["per_stem"])
            # Alternate leaves spiral by the golden angle; opposite ones come in
            # pairs at the same node and whorled in rings of three.
            per_node = 2 if opposite else (3 if whorled else 1)
            n_nodes = max(1, n_leaf // per_node)
            for j in range(n_nodes):
                t = F["leaf_from"] + (1 - F["leaf_from"]) * (
                    j / max(1, n_nodes - 1))
                at = rot @ Vector((0, 0, h * t))
                base_az = (j * 1.5708 if per_node > 1 else j * 2.39996) + az0
                nodes.append([[at, lL, lW, F["leaf_tilt"],
                               base_az + k * math.tau / per_node]
                              for k in range(per_node)])

    if F["basal"]:                      # rosette / mound / tuft at the ground
        nb = _rint(rng, *F["basal"])
        for _ in range(nb):
            az = rng.random() * math.tau
            ln = lL * ((0.6 + rng.random() * 0.5) if F["fine"] else 1.0)
            rr = (0.18 if F.get("low") else 0.10) * rng.random()
            at = Vector((math.cos(az) * rr, math.sin(az) * rr,
                         0.01 if F.get("low") else 0.02))
            nodes.append([[at, ln, lW,
                           F["leaf_tilt"] * (0.8 + rng.random() * 0.4), az]])

    if F["stalks"]:                     # flower stalks rising above the foliage
        for _ in range(_rint(rng, *F["stalks"])):
            h = 0.75 + rng.random() * 0.25
            az = rng.random() * math.tau
            splay = 0.05 + rng.random() * 0.18
            rot = (Matrix.Rotation(az, 4, "Z")
                   @ Matrix.Rotation(splay, 4, "Y"))
            stems.append([Vector((0, 0, 0)), rot @ Vector((0, 0, h)),
                          0.008, 0.005])
            # A naked scape is right for a rosette (fleabane, pussytoes) and
            # wrong for a yarrow, whose flowering stems carry leaves the whole
            # way up. Forms say which they are.
            for j in range(_rint(rng, *F.get("stalk_leaves", (0, 0)))):
                t = 0.15 + 0.7 * rng.random()
                nodes.append([[rot @ Vector((0, 0, h * t)), lL * 0.75, lW,
                               F["leaf_tilt"] * (0.7 + rng.random() * 0.4),
                               rng.random() * math.tau]])

    # Leaf counts here are tuned for a simple blade; a lupine's palmate one costs
    # five times as much, so the population is thinned to what the budget affords
    # before anything is stamped (mesh_ops.thin_leaf_nodes).
    nodes = thin_leaf_nodes(nodes, shape, C.TRI_BUDGETS["herb"],
                            len(stems) * CONE_TRIS)
    leaves = [leaf for node in nodes for leaf in node]

    # Shape the SKELETON AND THE LEAF ANCHORS TOGETHER, the way the tree, shrub
    # and vine builders do (mesh_ops.shape_to_aspect on shared points, stems
    # re-stamped between their corrected endpoints).
    #
    # This replaces a fixed-point solve that scaled leaf anchors and blade sizes
    # but left the stems at full splay. A clump's factor is ~0.53, so every leaf
    # was pulled halfway back toward the axis and halved in size while the stem
    # it hung on stayed put: the leaves came off their stems, and the plant
    # rendered as a spray of bare stalks with a thin column of shrunken leaves up
    # the middle. That is the aster a user's screenshot caught. Moving the stem
    # tips through the same solve keeps every leaf on the stem it belongs to, and
    # leaves keep their authored size — build_all finishes on the exact measured
    # correction (squash_to_aspect), which scales the whole mesh at once and so
    # cannot detach anything.
    ext = [leaf_extent(ln, t, shape) for _a, ln, _w, t, _az in leaves]
    pts = [s[1] for s in stems] + [lf[0] for lf in leaves]
    shape_to_aspect(
        pts, HERB_ASPECT[form],
        radii=[0.0] * len(stems) + [e[0] for e in ext],
        radii_z=[0.0] * len(stems) + [e[1] for e in ext])

    for base, tip, r_bot, r_top in stems:
        add_cone_between(bm, base, tip, r_bot, r_top, 4)
    for at, ln, wd, tilt, az in leaves:
        add_blade_or_leaf(bm, rng, ln, wd, tilt, az, at, shape)

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
    _blades(bm, rng, 46 + int(rng.random() * 22),       # thick meadow clump
            lambda: 0.62 + rng.random() * 0.5,
            lambda: 0.016 + rng.random() * 0.018,
            lambda: 0.22 + rng.random() * 0.7, 1.5, LAYER_ASPECT["grass"])


def _layer_aquatic(bm, rng):
    _blades(bm, rng, 30 + int(rng.random() * 16),       # stiff strap reeds
            lambda: 0.85 + rng.random() * 0.35,
            lambda: 0.03 + rng.random() * 0.028,
            lambda: 0.06 + rng.random() * 0.32, 2.4, LAYER_ASPECT["aquatic"])


def _layer_vine(bm, rng):
    n_stems = 7 + int(rng.random() * 4)                 # sprawling tangle
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
        n_leaf = 7 + int(rng.random() * 4)
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
    for _ in range(10 + int(rng.random() * 7)):         # low textured mat
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
