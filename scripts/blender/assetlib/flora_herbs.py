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

# `bpy` MUST be imported before `bmesh` and `mathutils`. Under the standalone
# bpy wheel those are C extensions that only become importable once bpy's
# __init__ has run its path setup, so the alphabetical order isort wants makes
# this module unimportable on its own — it works only because build_all imports
# bpy first. Same fix, same reason, as the note in mesh_ops.py.
import bpy                                        # isort: skip
import bmesh                                      # noqa: I001
from mathutils import Matrix, Vector

from . import conventions as C
from .conventions import GRAIN_LEAF_SCALE, HERB_ASPECT, LAYER_ASPECT
from .mesh_ops import (COMPOUND_SHAPES, CONE_TRIS, add_blade, add_blade_or_leaf,
                       add_cone_between, add_ellipsoid, add_leaf, arc_extent,
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
    # A fern's whole identity is that its fronds are DIVIDED and ARCHED, and
    # this form drew them as undivided lance blades — the sprite audit scored it
    # 3/10 for exactly that. add_blade_or_leaf has carried a compound primitive
    # since the pea/rose leaves needed one; at seven leaflet pairs a frond costs
    # 68 triangles, so sixteen of them fit the 1200 budget. The pair count is
    # overridden because `compound_pinnate` defaults to the THREE pairs a rose
    # really has, and three big paddles on a stick is not a frond.
    #
    # Dividing the frond alone still rendered a bundle of uprights, because a
    # compound rachis was a straight stick and tilting it only fanned the sticks
    # out. `leaf_arch` bends it: an ostrich fern's frond leaves the crown almost
    # vertical and flares near the top, which is the shuttlecock silhouette the
    # whole plant is known for (RACHIS_EASE puts the turn at the tip).
    #
    # The tilt is nearly zero on purpose. A fern's leaves all rise from one
    # crown, so shape_to_aspect has no anchors to move and the aspect is settled
    # entirely by squash_to_aspect scaling XY at the end. Tilting the fronds out
    # made the plant 3x wider than HERB_ASPECT allows, so the squash pulled it
    # back by a third — which is what flattened the fronds into vertical spikes
    # in the render, and it was doing that to the undivided blades before them
    # too. Arching to a natural aspect of ~1.05 leaves almost nothing to squash.
    "fern":    {"stems": None, "splay": 0, "leaf_from": 0,
                "leaf": (0.95, 0.11), "shape": "compound_pinnate",
                "per_stem": None, "leaf_arch": 0.65, "leaflet_pairs": 7,
                "leaf_tilt": 0.05, "stalks": None, "basal": (14, 20),
                "fine": False},
}

LAYER_KINDS = {"grass": 3, "aquatic": 3, "vine": 3, "groundcover": 2}
# Layers whose units are keyed by (blade class × grain class) like herbs and
# shrubs, rather than being N interchangeable random draws. Groundcover earned
# it: its 32 species carry 14 distinct leaf outlines and four arrangements, and
# they are looked at from a metre away.
VARIANT_LAYERS = frozenset({"groundcover"})

# Layers built entirely from flat blades and leaves, so build_all can finish
# them with the exact mesh-measuring correction (mesh_ops.squash_to_aspect).
# Groundcover was deliberately absent while it was round domes, which that
# correction would have flattened into discs. Since V2.29 it is flat leaves like
# the rest, and it NEEDS the measured pass: its leaves lie nearly horizontal, so
# their reach — not the runner anchors — is what sets the mat's width, and
# anchor shaping alone landed it at aspect 0.24 against a target of 0.42.
FLAT_LEAF_LAYERS = frozenset({"grass", "aquatic", "vine", "groundcover"})


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
            # Radii are HALF the stem's diameter as a fraction of the plant's
            # height. Real herbaceous stems are fine: a fireweed's is ~4 mm on a
            # 1.4 m plant (0.3% of height), a yarrow's flowering stem ~2 mm on
            # 0.5 m (0.4%). The old 0.012/0.008 drew them at 2.4%/1.6% — the same
            # 3-5x error that made the tree trunks read as concrete pillars, and
            # it is why the stalks, not the leaves, dominated every rosette and
            # mat specimen in the gallery.
            stems.append([Vector((0, 0, 0)), rot @ Vector((0, 0, h)),
                          0.005, 0.003])
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
                          0.0035, 0.0022])
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
    pairs = F.get("leaflet_pairs")
    arch = F.get("leaf_arch", 0.0)
    nodes = thin_leaf_nodes(nodes, shape, C.TRI_BUDGETS["herb"],
                            len(stems) * CONE_TRIS, pairs=pairs, arch=arch)
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
    ext = [leaf_extent(ln, t, shape, arch, pairs)
           for _a, ln, _w, t, _az in leaves]
    pts = [s[1] for s in stems] + [lf[0] for lf in leaves]
    shape_to_aspect(
        pts, HERB_ASPECT[form],
        radii=[0.0] * len(stems) + [e[0] for e in ext],
        radii_z=[0.0] * len(stems) + [e[1] for e in ext])

    for base, tip, r_bot, r_top in stems:
        add_cone_between(bm, base, tip, r_bot, r_top, 4)
    for at, ln, wd, tilt, az in leaves:
        add_blade_or_leaf(bm, rng, ln, wd, tilt, az, at, shape, arch=arch,
                          pairs=pairs)

    mat = preview_material()
    return {C.PART_FOLIAGE: bm_to_object(
        bm, C.part_name(name_prefix, C.PART_FOLIAGE), coll, mat)}


# ── simple layers ────────────────────────────────────────────────────────────

def _blades(bm, rng, n, length_fn, hw_fn, arch_fn, ease, aspect):
    """Stamp a tuft of arched blades shaped to ``aspect``.

    Every blade's authored arch is scaled by ONE factor, so the tuft opens or
    closes as a whole rather than being stretched by the instance transform.
    Arching both widens the tuft and lowers it, so the factor is solved by
    bisection on the real extent (mesh_ops.arc_extent) instead of the old
    closed form, which assumed a blade's height was its length — true only
    while blades were straight.
    """
    specs = [(length_fn(), hw_fn(), arch_fn()) for _ in range(n)]

    def aspect_at(k):
        w = h = 1e-6
        for ln, _hw, arch in specs:
            fwd, up = arc_extent(ln, arch * k, ease)
            w, h = max(w, fwd), max(h, up)
        return h / (2.0 * w)

    # aspect_at falls monotonically as k opens the tuft: at k=0 the blades are
    # vertical and the tuft has no width at all. If even fully arched it is
    # still too tall and narrow, take everything the authored range allows.
    if aspect_at(1.0) > aspect:
        k = 1.0
    else:
        lo, hi = 0.0, 1.0
        for _ in range(30):
            mid = (lo + hi) * 0.5
            lo, hi = (mid, hi) if aspect_at(mid) > aspect else (lo, mid)
        k = (lo + hi) * 0.5
    for ln, hw, arch in specs:
        add_blade(bm, rng, ln, hw, arch * k, ease)


def _layer_grass(bm, rng):
    # A real bunchgrass FOUNTAINS: the blades rise, tip over and hang. This drew
    # straight blades leaned sideways, which is why it read as a shaving brush
    # and the audit scored it 4/10 — and why widening the lean range alone did
    # nothing, since a leaned straight line is still a straight line. The arch
    # is authored NARROW and high rather than wide: `_blades` normalises the
    # tuft's spread against LAYER_ASPECT off its WIDEST blade, so a range open
    # at the bottom buys a couple of splayed outliers and leaves the median
    # blade nearly upright — the brush again. Clustering the range puts every
    # blade on the arc (25-44 deg of turn after the solve) instead of a few.
    # `ease` below 1 puts the bend low down, where a grass blade bends. Blades
    # are also thicker than they were (1.6-3.4% of height), since a blade under
    # a pixel wide at scene distance just disappears.
    _blades(bm, rng, 46 + int(rng.random() * 22),       # thick meadow clump
            lambda: 0.66 + rng.random() * 0.54,
            lambda: 0.026 + rng.random() * 0.026,
            lambda: 1.05 + rng.random() * 0.90, 0.85, LAYER_ASPECT["grass"])


def _layer_aquatic(bm, rng):
    # Bulrush and cattail leaves stand stiff and only nod at the tip, so the
    # bend is pushed to the top (ease > 1) and the total turn kept small.
    _blades(bm, rng, 30 + int(rng.random() * 16),       # stiff strap reeds
            lambda: 0.85 + rng.random() * 0.35,
            lambda: 0.03 + rng.random() * 0.028,
            lambda: 0.05 + rng.random() * 0.70, 1.9, LAYER_ASPECT["aquatic"])


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


# A groundcover leaf is seen from almost directly above, at close range, and its
# outline is most of what there is to see — but there are a lot of them, so two
# ribbon segments (4 triangles) buys the count that reads as a MAT.
GC_LEAF_SEGMENTS = 2


def _layer_groundcover(bm, rng, grain=1, leaf_shape=None, arrangement=None):
    """A creeping mat of real leaves on runners.

    Until V2.29 this was ten to seventeen faceted ellipsoids — a lump of green
    boulders with no leaves, no stems and no structure, identical for all 32
    groundcover species in the catalogue. It was the one archetype the V2.29 leaf
    work never reached, and it is what a wild strawberry, a bearberry, a
    bunchberry and five creeping Rubus all rendered as.

    A groundcover is a *creeping* plant: stolons or trailing woody stems radiate
    from a crown and root as they go, carrying leaves at nodes along their
    length. That is the structure built here — and because these species are
    looked at from above at close range, the leaf outline (`leaf_shape`) and the
    arrangement (`basal` rosettes vs leaves spaced along a runner) are the two
    things actually visible. Both come from the species' own record.
    """
    shape = leaf_shape or "ovate"
    # Basal species (strawberry, violet, pussytoes) hold their leaves on erect
    # petioles from a crown; trailing ones (bearberry, twinflower, creeping
    # Rubus) space them along the runner. That is the difference between a
    # rosette-studded mat and an even carpet, and it is the field mark here.
    basal = (arrangement or "") == "basal"
    per_node = 2 if (arrangement or "") == "opposite" else (
        3 if (arrangement or "") == "whorled" else 1)
    # Leaf length as a fraction of the mat's own (tiny) height. Groundcovers are
    # centimetres tall with centimetre leaves, so unlike a shrub these fractions
    # are LARGE — a strawberry leaf is a third of the plant's height.
    leaf_len = (0.30, 0.42, 0.62)[max(0, min(2, int(grain)))]
    if shape in COMPOUND_SHAPES:
        leaf_len *= 1.25
    leaf_wid = leaf_width_for(shape, leaf_len)

    segs, nodes = [], []
    n_run = 8 + int(rng.random() * 6)
    for i in range(n_run):
        az = i / n_run * math.tau + rng.random() * 0.6
        reach = 0.55 + rng.random() * 0.45
        rise = 0.12 + rng.random() * 0.10          # runners hug the ground
        start = Vector((0, 0, 0.02))
        end = Vector((math.cos(az) * reach, math.sin(az) * reach, rise))
        segs.append((start, end))
        n_nodes = 7 + int(rng.random() * 6)
        for j in range(n_nodes):
            t = 0.2 + 0.8 * (j / max(1, n_nodes - 1))
            at = start.lerp(end, t)
            if basal:
                # Held up off the runner on a petiole, fanning from the node.
                at = at + Vector((0, 0, 0.10 + rng.random() * 0.10))
            base_az = az + (0 if per_node > 1 else j * 2.39996)
            nodes.append([[at,
                           # Basal leaves stand up and out; trailing ones lie
                           # nearly flat, which is what makes a carpet a carpet.
                           (0.75 if basal else 1.15) + rng.random() * 0.35,
                           base_az + k * math.tau / per_node + rng.random() * 0.4]
                          for k in range(per_node)])

    structural = len(segs) * CONE_TRIS
    nodes = thin_leaf_nodes(nodes, shape, C.TRI_BUDGETS["groundcover"],
                            structural, segments=GC_LEAF_SEGMENTS)
    leaves = [leaf for node in nodes for leaf in node]

    pts = [p for s in segs for p in s] + [l[0] for l in leaves]
    reach = [leaf_extent(leaf_len, l[1], shape) for l in leaves]
    shape_to_aspect(
        pts, LAYER_ASPECT["groundcover"],
        radii=[0.0] * (2 * len(segs)) + [r[0] for r in reach],
        radii_z=[0.0] * (2 * len(segs)) + [r[1] for r in reach])

    for start, end in segs:
        add_cone_between(bm, start, end, 0.012, 0.006, 3)
    for at, tilt, az in leaves:
        add_blade_or_leaf(bm, rng, leaf_len, leaf_wid, tilt, az, at, shape,
                          GC_LEAF_SEGMENTS)


_LAYER_BUILDERS = {"grass": _layer_grass, "aquatic": _layer_aquatic,
                   "vine": _layer_vine, "groundcover": _layer_groundcover}


def build_layer(kind, rng, coll, name_prefix="", **morph):
    """One layer archetype. ``morph`` (grain / leaf_shape / arrangement) is
    passed only to the builders in VARIANT_LAYERS; the rest take none, so a
    caller can hand the same bag to every kind."""
    from .materials import preview_material

    bm = bmesh.new()
    if kind in VARIANT_LAYERS:
        _LAYER_BUILDERS[kind](bm, rng, **morph)
    else:
        _LAYER_BUILDERS[kind](bm, rng)
    mat = preview_material()
    return {C.PART_FOLIAGE: bm_to_object(
        bm, C.part_name(name_prefix, C.PART_FOLIAGE), coll, mat)}
