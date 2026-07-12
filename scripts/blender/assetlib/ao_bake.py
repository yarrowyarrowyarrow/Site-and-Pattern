"""Per-vertex ambient-occlusion bake → the 'Color' attribute (COLOR_0).

No render engine, no GPU, no bpy.ops: a BVH over the asset's own triangles,
cosine-weighted hemisphere rays per vertex, deterministic ray set. Identical
results headless and in a live Blender-MCP session.

The viewer multiplies COLOR_0 into its per-instance tint, so values are
GRAYSCALE brightness only (conventions: never hue). `gradient=True` folds in
the vertical light gradient the procedural foliage bakes (applyFoliageGradient
in html/scene3d/03-herbs.js): darker toward the shaded base, brightest at the
sunlit top — capped at 1.0 since COLOR_0 is normalised.
"""

import math
import random

from mathutils import Vector
from mathutils.bvhtree import BVHTree

from .conventions import seed_for


def _hemisphere_dirs(n, rng):
    """Cosine-weighted unit directions about +Z (deterministic)."""
    out = []
    for _ in range(n):
        u1, u2 = rng.random(), rng.random()
        r = math.sqrt(u1)
        theta = math.tau * u2
        out.append(Vector((r * math.cos(theta), r * math.sin(theta),
                           math.sqrt(max(0.0, 1.0 - u1)))))
    return out


def _basis(normal):
    n = normal.normalized()
    helper = Vector((1, 0, 0)) if abs(n.x) < 0.9 else Vector((0, 1, 0))
    t = n.cross(helper).normalized()
    b = n.cross(t)
    return t, b, n


def bake_ao(objs, samples=32, strength=0.85, max_dist=0.6, gradient=False,
            floor=True, seed_key="ao"):
    """Bake AO for all `objs` jointly (each occludes the others).

    strength : how dark full occlusion gets (0 = no effect).
    max_dist : ray reach in the asset's local units (unit frame ≈ 1 tall).
    floor    : treat the ground plane z=0 as an occluder (assets sit on it).
    """
    objs = [o for o in objs if o is not None]
    if not objs:
        return
    verts, polys = [], []
    for obj in objs:
        me = obj.data
        base = len(verts)
        verts.extend((obj.matrix_world @ v.co) for v in me.vertices)
        polys.extend(tuple(base + i for i in p.vertices) for p in me.polygons)
    if not polys:
        return
    bvh = BVHTree.FromPolygons([tuple(v) for v in verts], polys)

    rng = random.Random(seed_for(seed_key))
    dirs = _hemisphere_dirs(samples, rng)
    eps = 1e-3

    lo_z = min(v.z for v in verts)
    hi_z = max(v.z for v in verts)
    span = max(1e-6, hi_z - lo_z)

    for obj in objs:
        me = obj.data
        attr = me.color_attributes.get("Color")
        if attr is None:
            attr = me.color_attributes.new("Color", "FLOAT_COLOR", "POINT")
        me.attributes.active_color = attr
        for i, v in enumerate(me.vertices):
            origin = obj.matrix_world @ v.co
            t, b, n = _basis(v.normal)
            hits = 0
            for d in dirs:
                w = (t * d.x + b * d.y + n * d.z)
                if bvh.ray_cast(origin + w * eps, w, max_dist)[0] is not None:
                    hits += 1
                elif floor and w.z < -1e-4:
                    # Would the escaping ray hit the ground plane instead?
                    if (origin.z - lo_z) / -w.z <= max_dist:
                        hits += 1
            ao = 1.0 - strength * (hits / samples)
            val = ao
            if gradient:
                tt = min(1.0, max(0.0, (origin.z - lo_z) / span))
                tt = tt * tt * (3 - 2 * tt)          # smoothstep
                val = ao * (0.55 + 0.45 * tt)
            val = min(1.0, max(0.05, val))
            attr.data[i].color = (val, val, val, 1.0)
