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

import bmesh
from mathutils import Matrix, Vector

from .mesh_ops import (add_cone, add_cone_between, add_ellipsoid, bm_to_object,
                       place, shape_to_aspect)

# ── parameter tables (echo 02-plants.js) ─────────────────────────────────────

CONIFER_KINDS = {
    # whorls by tier          baseR  droop  spire  boughs  lift
    "spruce":      {"whorls": (4, 7, 10), "base_r": 0.34, "droop": 0.16,
                    "spire": 1.15, "boughs": 8, "lift": 0.04},
    "fir":         {"whorls": (5, 8, 11), "base_r": 0.30, "droop": 0.08,
                    "spire": 1.4, "boughs": 8, "lift": 0.02},
    "larch":       {"whorls": (3, 5, 7), "base_r": 0.36, "droop": 0.22,
                    "spire": 0.7, "boughs": 6, "lift": 0.05},
    "def_conifer": {"whorls": (3, 5, 8), "base_r": 0.40, "droop": 0.14,
                    "spire": 1.0, "boughs": 7, "lift": 0.05},
}

DECID_FORMS = {
    "slender":   {"angle": 0.46, "len_scale": 0.84, "clear_bole": 0.52,
                  "foliage_scale": 0.72, "split_bias": 0.15},
    "oval":      {"angle": 0.62, "len_scale": 0.70, "clear_bole": 0.38,
                  "foliage_scale": 0.90, "split_bias": 0.2},
    "spreading": {"angle": 0.85, "len_scale": 0.64, "clear_bole": 0.28,
                  "foliage_scale": 1.00, "split_bias": 0.3},
}

DECID_GENERA = {
    "aspen":         {"form": "slender", "foliage_scale": 0.90},
    "birch":         {"form": "oval", "droop_outer": 0.55, "foliage_scale": 0.82},
    "oak":           {"form": "spreading", "foliage_scale": 1.06},
    "willow":        {"form": "slender", "droop_outer": 0.70, "foliage_scale": 0.85},
    "cherry":        {"form": "oval"},
    "apple":         {"form": "spreading"},
    "def_slender":   {"form": "slender"},
    "def_oval":      {"form": "oval"},
    "def_spreading": {"form": "spreading"},
}

DECID_DEPTH = (2, 4, 5)                  # skeleton depth by maturity tier
# Minimum branch radius before a limb is called terminal, by tier. This — not
# the depth cap — is what actually decides how many branch ends a crown has:
# each split takes a limb to ~0.55 of its parent, so a fixed cutoff stops the
# walk after three levels no matter how deep it is allowed to go. A larger tree
# carries finer twigs, hence more tips to hang the (now smaller) leaf masses on.
DECID_MIN_R = (0.020, 0.016, 0.011)

# Foliage-clump radius as a fraction of the crown's HALF-WIDTH, by size tier.
# Two things fall out of keying it to the crown rather than to the asset height:
#   * a narrow crown gets correspondingly small leaf masses instead of clumps
#     wider than the tree (what made a poplar read as six giant leaves), and
#   * bigger trees get relatively finer foliage — a 20 m aspen carries many
#     branch-end masses, a 4 m sapling a few — so structural detail tracks
#     absolute size, not just growth year (04-quality.js tierFor).
FOLIAGE_FRAC = (0.46, 0.36, 0.28)
# Clumps per terminal branch by tier. Finer masses have to arrive in greater
# numbers or the crown goes see-through — the first cut of the aspect fix left
# an aspen as a bare pole with a few crumbs at the top. Affordable because a
# foliage mass is a 20-triangle icosahedron (subdiv 0, matching the viewer's own
# makeFoliageMass), not an 80-triangle one.
CLUMPS_PER_TIP = (3, 4, 5)
FOLIAGE_SUBDIV = 0

TREE_ARCHETYPES = ("spruce", "fir", "pine", "larch", "def_conifer",
                   "aspen", "birch", "oak", "willow", "cherry", "apple",
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
    z0, z1 = 0.10, 0.90
    # Lay the whorls out in the builder's natural frame first, collecting every
    # point; shape_to_aspect then pulls them in to the species' real crown width
    # before anything is stamped, so the boughs shorten and the needle planes
    # keep their authored thickness.
    boughs, stubs, pts = [], [], []
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
            # Short bare branch stub under the bough — the winter skeleton.
            s0 = Vector((0, 0, z))
            s1 = s0 + (tip - origin) * 0.55
            stubs.append((s0, s1))
            pts.extend((origin, tip, s0, s1))
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


def _build_pine(tier, rng, aspect):
    """Pinus: clear lower trunk, tufted open upper crown, flattish top."""
    bark = bmesh.new()
    fol = bmesh.new()
    H = 1.0
    # Pine crowns are narrow (Pinus contorta runs 4:1), so the needle pads are
    # sized off the crown width like the deciduous leaf masses — and there are
    # more of them on a bigger tree.
    crown_half = 0.5 / aspect
    pad_r = crown_half * (0.62, 0.5, 0.42)[tier]
    clumps = 6 + tier * 4
    z_base = 0.48
    tufts, pts = [], []
    for i in range(clumps):
        f = i / max(1, clumps - 1)
        z = z_base + (0.88 - z_base) * f + (rng.random() - 0.5) * 0.05
        az = rng.random() * math.tau
        reach = (0.18 + rng.random() * 0.13) * (1 - f * 0.45)
        base = Vector((0, 0, z - 0.02))
        tip = Vector((math.cos(az) * reach, math.sin(az) * reach, z))
        r = pad_r * (0.8 + rng.random() * 0.4) * (1 - f * 0.20)
        tufts.append((base, tip, r))
        pts.extend((base, tip))
    # A needle pad is stamped 1.5× wide in XY, so that is its horizontal reach.
    shape_to_aspect(pts, aspect, height=H,
                    radii=[v for _b, _t, r in tufts for v in (0.0, r * 1.5)])
    add_cone(bark, 0.034, 0.010, H * 0.96, 6, Matrix())
    for base, tip, r in tufts:
        # Visible branch out to the tuft (also the winter skeleton).
        add_cone_between(bark, base, tip, 0.014, 0.006, 4)
        # Flat, wide needle pad at the branch tip — the open, scraggly
        # jack/lodgepole look, not a deciduous blob.
        add_ellipsoid(fol, r, (1.5, 1.5, 0.42),
                      Matrix.Translation(tip), subdiv=FOLIAGE_SUBDIV)
    add_ellipsoid(fol, pad_r, (1.3, 1.3, 0.45),
                  Matrix.Translation(Vector((0, 0, 0.93))), subdiv=FOLIAGE_SUBDIV)
    return bark, fol


# ── deciduous ────────────────────────────────────────────────────────────────

def _decid_skeleton(rng, form, max_depth, min_r):
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

    walk(Matrix(), 0.055, 0.40, 0)
    return segs


def _build_deciduous(genus, tier, rng, aspect):
    g = DECID_GENERA[genus]
    form = dict(DECID_FORMS[g["form"]])
    f_scale = form["foliage_scale"] * g.get("foliage_scale", 1.0)
    droop_outer = g.get("droop_outer", 0.0)
    bark = bmesh.new()
    fol = bmesh.new()

    # Leaf masses are sized off the crown's own width, so a narrow species gets
    # small masses and a broad one big ones — see FOLIAGE_FRAC.
    crown_half = 0.5 / aspect
    clump_r = crown_half * FOLIAGE_FRAC[tier] * f_scale

    segs = _decid_skeleton(rng, form, DECID_DEPTH[tier], DECID_MIN_R[tier])
    blobs = []          # [center, radius, z_of_tip] — clear-bole gated below
    for start, end, r_bot, r_top, depth, terminal in segs:
        tip = end
        if terminal:
            n = CLUMPS_PER_TIP[tier] + (1 if rng.random() < 0.6 else 0)
            base_r = clump_r * (0.85 + 0.3 * rng.random())
            spread = clump_r * (1 + droop_outer * 0.4)
            dz = -droop_outer * 0.11
            for _ in range(n):
                c = tip + Vector(((rng.random() - 0.5) * spread,
                                  (rng.random() - 0.5) * spread,
                                  dz + base_r * 0.35
                                  + (rng.random() - 0.2) * clump_r * 0.5))
                blobs.append([c, base_r, tip.z])
        elif depth >= 2:
            c = tip + Vector(((rng.random() - 0.5) * clump_r * 0.6,
                              (rng.random() - 0.5) * clump_r * 0.6,
                              clump_r * 0.3))
            blobs.append([c, clump_r * (0.6 + rng.random() * 0.35), tip.z])

    # Narrow (or widen) the whole crown to the species' real aspect BEFORE
    # stamping: branch endpoints and clump centres move, clump radii and branch
    # cross-sections don't. An aspen crown gets tall and tight with the same
    # sized leaf masses, instead of the same crown with stretched ones.
    pts = [p for s in segs for p in (s[0], s[1])] + [b[0] for b in blobs]
    rads = [0.0] * (2 * len(segs)) + [b[1] for b in blobs]
    shape_to_aspect(pts, aspect, radii=rads)

    for start, end, r_bot, r_top, _depth, _terminal in segs:
        add_cone_between(bark, start, end, max(0.006, r_bot),
                         max(0.004, r_top), 5)
    # Clear bole: no foliage below clear_bole × crown height.
    max_z = max((b[2] for b in blobs), default=1.0)
    gate = form["clear_bole"] * max_z
    for center, radius, tip_z in blobs:
        if tip_z < gate:
            continue
        add_ellipsoid(fol, radius, (1.0, 1.0, 0.72 + rng.random() * 0.2),
                      Matrix.Translation(center), subdiv=FOLIAGE_SUBDIV)
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
    if archetype == "pine":
        bark_bm, fol_bm = _build_pine(tier, rng, aspect)
    elif archetype in CONIFER_KINDS:
        bark_bm, fol_bm = _build_conifer(archetype, tier, rng, aspect)
    elif archetype in DECID_GENERA:
        bark_bm, fol_bm = _build_deciduous(archetype, tier, rng, aspect)
    else:
        raise KeyError(f"unknown tree archetype: {archetype}")
    mat = preview_material()
    return {
        C.PART_BARK: bm_to_object(
            bark_bm, C.part_name(name_prefix, C.PART_BARK), coll, mat),
        C.PART_FOLIAGE: bm_to_object(
            fol_bm, C.part_name(name_prefix, C.PART_FOLIAGE), coll, mat),
    }
