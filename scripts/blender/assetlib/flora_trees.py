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

from .mesh_ops import add_cone, add_ellipsoid, bm_to_object, place

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

DECID_DEPTH = (2, 3, 4)                  # skeleton depth by maturity tier

TREE_ARCHETYPES = ("spruce", "fir", "pine", "larch", "def_conifer",
                   "aspen", "birch", "oak", "willow", "cherry", "apple",
                   "def_slender", "def_oval", "def_spreading")


# ── conifers ─────────────────────────────────────────────────────────────────

def _bough(bm, origin, azimuth, length, girth, droop):
    """One conifer bough: a flattened open cone pointing outward-down."""
    m = (Matrix.Translation(origin)
         @ Matrix.Rotation(azimuth, 4, "Z")
         @ Matrix.Rotation(math.pi / 2 + droop, 4, "Y")
         @ Matrix.Diagonal((1.0, 0.45, 1.0, 1.0)))     # flat needle plane
    add_cone(bm, girth, girth * 0.12, length, 4, m)


def _build_conifer(kind, tier, rng):
    p = CONIFER_KINDS[kind]
    bark = bmesh.new()
    fol = bmesh.new()
    H = 1.0
    # Trunk: full winter silhouette on its own (larch drops needles).
    add_cone(bark, 0.030, 0.008, H * 0.98, 6, Matrix())
    whorls = max(2, p["whorls"][tier])
    z0, z1 = 0.10, 0.90
    for i in range(whorls):
        f = i / max(1, whorls - 1)                      # 0 base … 1 top
        z = z0 + (z1 - z0) * f
        reach = (p["base_r"] * (1 - f) ** 0.85 + 0.05) * (0.9 + rng.random() * 0.2)
        n = max(4, round(p["boughs"] * (1 - 0.3 * f)))
        for b in range(n):
            az = b / n * math.tau + rng.random() * 0.5
            droop = p["droop"] * (0.7 + rng.random() * 0.6)
            girth = 0.035 + 0.03 * (1 - f)
            _bough(fol, Vector((0, 0, z + p["lift"])), az,
                   reach, girth, droop)
            # Short bare branch stub under the bough — the winter skeleton.
            add_cone(bark, 0.008, 0.004, reach * 0.55, 4,
                     place(z=z, rot_z=az, tilt_y=math.pi / 2 + droop * 0.6))
    # Slim core cones fill the silhouette between whorls.
    for cz, cr in ((0.30, 0.16), (0.55, 0.12), (0.76, 0.09)):
        add_cone(fol, cr * p["base_r"] / 0.4, 0.01, 0.30, 5,
                 place(z=cz, rot_z=rng.random()))
    # Spire.
    add_cone(fol, 0.045, 0.004, 0.14 * p["spire"], 5, place(z=z1))
    return bark, fol


def _build_pine(tier, rng):
    """Pinus: clear lower trunk, tufted open upper crown, flattish top."""
    bark = bmesh.new()
    fol = bmesh.new()
    H = 1.0
    add_cone(bark, 0.034, 0.010, H * 0.96, 6, Matrix())
    clumps = 4 + tier * 2
    z_base = 0.48
    for i in range(clumps):
        f = i / max(1, clumps - 1)
        z = z_base + (0.88 - z_base) * f + (rng.random() - 0.5) * 0.05
        az = rng.random() * math.tau
        reach = (0.18 + rng.random() * 0.13) * (1 - f * 0.45)
        # Visible branch out to the tuft (also the winter skeleton).
        add_cone(bark, 0.014, 0.006, reach + 0.05, 4,
                 place(z=z - 0.02, rot_z=az, tilt_y=1.05))
        # Flat, wide needle pad at the branch tip — the open, scraggly
        # jack/lodgepole look, not a deciduous blob.
        tip = Vector((math.cos(az) * reach, math.sin(az) * reach, z))
        r = (0.10 + rng.random() * 0.05) * (1 - f * 0.20)
        add_ellipsoid(fol, r, (1.5, 1.5, 0.42),
                      Matrix.Translation(tip), subdiv=1)
    add_ellipsoid(fol, 0.10, (1.3, 1.3, 0.45),
                  Matrix.Translation(Vector((0, 0, 0.93))), subdiv=1)
    return bark, fol


# ── deciduous ────────────────────────────────────────────────────────────────

def _decid_skeleton(rng, form, max_depth):
    """Recursive da Vinci skeleton: [(matrix, r_bot, r_top, length, depth,
    terminal)] — radius² conserved across splits, child length scaling."""
    segs = []

    def walk(mat, radius, length, depth):
        r_top = radius * 0.65
        terminal = depth >= max_depth or radius < 0.014
        segs.append((mat.copy(), radius, r_top, length, depth, terminal))
        if terminal:
            return
        n = 3 if rng.random() < form["split_bias"] else 2
        # Split the parent's cross-section area among children.
        shares = [0.3 + rng.random() * 0.25 for _ in range(n)]
        total = sum(shares)
        base_rot = rng.random() * math.tau
        tip = mat @ Matrix.Translation((0, 0, length))
        for i in range(n):
            r_child = r_top * math.sqrt(shares[i] / total * n * 0.72)
            l_child = length * max(0.05, r_child / radius) ** form["len_scale"]
            spread = form["angle"] * (0.8 + rng.random() * 0.4)
            rot = (Matrix.Rotation(base_rot + i * math.tau / n
                                   + rng.random() * 0.5, 4, "Z")
                   @ Matrix.Rotation(spread, 4, "X"))
            walk(tip @ rot, r_child, l_child, depth + 1)

    walk(Matrix(), 0.055, 0.40, 0)
    return segs


def _build_deciduous(genus, tier, rng):
    g = DECID_GENERA[genus]
    form = dict(DECID_FORMS[g["form"]])
    f_scale = form["foliage_scale"] * g.get("foliage_scale", 1.0)
    droop_outer = g.get("droop_outer", 0.0)
    bark = bmesh.new()
    fol = bmesh.new()

    segs = _decid_skeleton(rng, form, DECID_DEPTH[tier])
    blobs = []          # (center, radius, z_of_tip) — clear-bole gated below
    for mat, r_bot, r_top, length, depth, terminal in segs:
        add_cone(bark, max(0.006, r_bot), max(0.004, r_top), length, 5, mat)
        tip = mat @ Vector((0, 0, length))
        if terminal:
            n = 2 + (1 if rng.random() < 0.6 else 0)
            base_r = (0.16 + 0.05 * rng.random()) * f_scale
            spread = 0.16 * f_scale * (1 + droop_outer * 0.4)
            dz = -droop_outer * 0.11
            for _ in range(n):
                c = tip + Vector(((rng.random() - 0.5) * spread,
                                  (rng.random() - 0.5) * spread,
                                  dz + base_r * 0.35 + (rng.random() - 0.2) * 0.08))
                blobs.append((c, base_r + rng.random() * 0.10 * f_scale, tip.z))
        elif depth >= 2:
            c = tip + Vector(((rng.random() - 0.5) * 0.1,
                              (rng.random() - 0.5) * 0.1, 0.05))
            blobs.append((c, (0.11 + rng.random() * 0.06) * f_scale, tip.z))

    # Clear bole: no foliage below clear_bole × crown height.
    max_z = max((b[2] for b in blobs), default=1.0)
    gate = form["clear_bole"] * max_z
    for center, radius, tip_z in blobs:
        if tip_z < gate:
            continue
        add_ellipsoid(fol, radius, (1.0, 1.0, 0.72 + rng.random() * 0.2),
                      Matrix.Translation(center), subdiv=1)
    return bark, fol


# ── public entry ─────────────────────────────────────────────────────────────

def build_tree(archetype, tier, rng, coll, name_prefix=""):
    """Build one tree tier; returns {'bark': obj, 'foliage': obj}."""
    from . import conventions as C
    from .materials import preview_material

    if archetype == "pine":
        bark_bm, fol_bm = _build_pine(tier, rng)
    elif archetype in CONIFER_KINDS:
        bark_bm, fol_bm = _build_conifer(archetype, tier, rng)
    elif archetype in DECID_GENERA:
        bark_bm, fol_bm = _build_deciduous(archetype, tier, rng)
    else:
        raise KeyError(f"unknown tree archetype: {archetype}")
    mat = preview_material()
    return {
        C.PART_BARK: bm_to_object(
            bark_bm, C.part_name(name_prefix, C.PART_BARK), coll, mat),
        C.PART_FOLIAGE: bm_to_object(
            fol_bm, C.part_name(name_prefix, C.PART_FOLIAGE), coll, mat),
    }
