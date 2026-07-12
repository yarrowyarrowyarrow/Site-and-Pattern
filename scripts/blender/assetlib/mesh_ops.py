"""Low-poly mesh helpers shared by every builder (bpy/bmesh, Blender 4.2+).

All primitives are built with bmesh *ops* (context-free — safe headless and
under the Blender MCP) into one bmesh per part, then converted to a mesh
object. Placement matrices are mathutils.Matrix composed by the callers.

Blender frame: Z-up, ground plane XY. The glTF exporter converts to Y-up.
"""

import math

import bmesh
import bpy
from mathutils import Matrix, Vector

from . import conventions as C


# ── object / collection plumbing ─────────────────────────────────────────────

def wipe_collection(name):
    """Delete the named collection and everything in it (idempotent builds)."""
    coll = bpy.data.collections.get(name)
    if not coll:
        return
    for obj in list(coll.objects):
        mesh = obj.data if obj.type == "MESH" else None
        bpy.data.objects.remove(obj, do_unlink=True)
        if mesh is not None and mesh.users == 0:
            bpy.data.meshes.remove(mesh)
    bpy.data.collections.remove(coll)


def get_collection(name, wipe=True):
    """A fresh (or existing) collection linked under the scene collection."""
    if wipe:
        wipe_collection(name)
    coll = bpy.data.collections.get(name)
    if not coll:
        coll = bpy.data.collections.new(name)
        bpy.context.scene.collection.children.link(coll)
    return coll


def bm_to_object(bm, name, coll, material=None):
    """Finalize a bmesh into a linked, flat-shaded, triangulated object."""
    bmesh.ops.triangulate(bm, faces=bm.faces[:])
    me = bpy.data.meshes.new(name)
    bm.to_mesh(me)
    bm.free()
    for poly in me.polygons:
        poly.use_smooth = False          # flat shading baked into normals
    obj = bpy.data.objects.new(name, me)
    if material is not None:
        obj.data.materials.append(material)
    coll.objects.link(obj)
    return obj


def make_empty(name, coll, location=(0, 0, 0)):
    e = bpy.data.objects.new(name, None)
    e.location = location
    coll.objects.link(e)
    return e


def tri_count(obj):
    return sum(max(0, len(p.vertices) - 2) for p in obj.data.polygons)


# ── primitive stamps (into an existing bmesh) ────────────────────────────────

def add_cone(bm, r_bottom, r_top, depth, segments, matrix):
    """Tapered cylinder from z=0..depth in its LOCAL frame, then matrix."""
    m = matrix @ Matrix.Translation((0, 0, depth / 2))
    bmesh.ops.create_cone(
        bm, cap_ends=True, cap_tris=True, segments=segments,
        radius1=max(1e-4, r_bottom), radius2=max(1e-4, r_top),
        depth=depth, matrix=m, calc_uvs=False)


def add_ellipsoid(bm, radius, scale_xyz, matrix, subdiv=1):
    """A faceted icosphere squashed to an ellipsoid (the foliage mass)."""
    m = matrix @ Matrix.Diagonal((*scale_xyz, 1.0))
    bmesh.ops.create_icosphere(
        bm, subdivisions=subdiv, radius=radius, matrix=m, calc_uvs=False)


def add_uv_ball(bm, radius, scale_xyz, matrix, u=10, v=8):
    """A smoother ball for fauna bodies (still low-poly)."""
    m = matrix @ Matrix.Diagonal((*scale_xyz, 1.0))
    bmesh.ops.create_uvsphere(
        bm, u_segments=u, v_segments=v, radius=radius, matrix=m, calc_uvs=False)


def place(x=0.0, y=0.0, z=0.0, rot_z=0.0, tilt_y=0.0):
    """Translation @ RotZ(azimuth) @ RotY(tilt) — the builders' one idiom."""
    return (Matrix.Translation((x, y, z))
            @ Matrix.Rotation(rot_z, 4, "Z")
            @ Matrix.Rotation(tilt_y, 4, "Y"))


# ── ribbons (grass blades / strap and lance leaves) ──────────────────────────

def add_ribbon(bm, points, half_widths, width_dir):
    """A flat quad-strip through `points` with per-point half-widths."""
    wd = Vector(width_dir).normalized()
    left, right = [], []
    for p, hw in zip(points, half_widths):
        p = Vector(p)
        left.append(bm.verts.new(p - wd * hw))
        right.append(bm.verts.new(p + wd * hw))
    for i in range(len(points) - 1):
        bm.faces.new((left[i], right[i], right[i + 1], left[i + 1]))


def add_blade(bm, rng, height, base_half_width, lean, erect, azimuth=None):
    """One arched, tapering grass/reed blade (port of makeBlade, Z-up)."""
    segs = 5
    az = rng.random() * math.tau if azimuth is None else azimuth
    d = Vector((math.cos(az), math.sin(az), 0))
    perp = Vector((-d.y, d.x, 0))
    pts, hws = [], []
    for s in range(segs + 1):
        t = s / segs
        off = lean * (t ** erect)
        pts.append(d * off + Vector((0, 0, height * t)))
        hws.append(base_half_width * (1 - t * 0.92) + 0.0015)
    add_ribbon(bm, pts, hws, perp)


def _leaf_width(shape, t):
    if shape == "ovate":
        return math.sin(math.pi * min(0.96, max(0.06, t))) ** 0.7
    if shape == "strap":
        return 1.0 if t < 0.9 else max(0.15, (1 - t) / 0.1)
    return max(0.05, 1 - 0.9 * t)          # lance / default


def add_leaf(bm, rng, length, width, tilt, azimuth, at, shape):
    """One flat leaf with a real width profile (port of makeLeaf, Z-up).

    Built along +Z, tilted `tilt` from vertical about Y, spun to `azimuth`
    about Z, then translated to `at` (a Vector or tuple, may be None).
    """
    segs = 4
    ln = length * (0.8 + rng.random() * 0.4)
    droop = (0.05 if shape == "strap" else 0.12) + rng.random() * 0.18
    mat = Matrix.Rotation(azimuth, 4, "Z") @ Matrix.Rotation(tilt, 4, "Y")
    if at is not None:
        mat = Matrix.Translation(Vector(at)) @ mat
    pts, hws = [], []
    for s in range(segs + 1):
        t = s / segs
        bend = droop * (t ** 1.4)
        pts.append(mat @ Vector((bend * ln, 0, ln * t)))
        hws.append(width * 0.5 * _leaf_width(shape, t) + 0.0008)
    wd = (mat.to_3x3() @ Vector((0, 1, 0))).normalized()
    add_ribbon(bm, pts, hws, wd)


# ── normalisation / budgets ──────────────────────────────────────────────────

def _joint_bounds(objs):
    lo = Vector((math.inf,) * 3)
    hi = Vector((-math.inf,) * 3)
    for obj in objs:
        for corner in obj.bound_box:
            w = obj.matrix_world @ Vector(corner)
            lo = Vector(map(min, lo, w))
            hi = Vector(map(max, hi, w))
    return lo, hi


def unit_frame(objs):
    """Normalise a set of part objects jointly to the contract frame:
    base z=0, height UNIT_HEIGHT, horizontal half-extent UNIT_HALF_WIDTH.
    Baked into the mesh data (objects keep identity transforms)."""
    objs = [o for o in objs if o is not None]
    if not objs:
        return
    lo, hi = _joint_bounds(objs)
    sz = max(1e-6, hi.z - lo.z)
    half = max(1e-6, abs(lo.x), abs(hi.x), abs(lo.y), abs(hi.y))
    s_z = C.UNIT_HEIGHT / sz
    s_xy = C.UNIT_HALF_WIDTH / half
    for obj in objs:
        me = obj.data
        for v in me.vertices:
            v.co.x *= s_xy
            v.co.y *= s_xy
            v.co.z = (v.co.z - lo.z) * s_z
        me.update()


def decimate_to_budget(obj, budget):
    """Collapse-decimate until the triangle count fits the budget (in place).

    Uses a modifier evaluated through the depsgraph (context-free), swapping
    the evaluated mesh in — no bpy.ops, works identically headless and MCP.
    """
    n = tri_count(obj)
    if n <= budget:
        return n
    mod = obj.modifiers.new("budget", "DECIMATE")
    mod.decimate_type = "COLLAPSE"
    for _ in range(4):
        mod.ratio = max(0.05, budget / max(1, n) * 0.97)
        deps = bpy.context.evaluated_depsgraph_get()
        ev = obj.evaluated_get(deps)
        me = bpy.data.meshes.new_from_object(
            ev, preserve_all_data_layers=True, depsgraph=deps)
        n_new = sum(max(0, len(p.vertices) - 2) for p in me.polygons)
        if n_new <= budget or n_new >= n:
            old = obj.data
            obj.modifiers.remove(mod)
            obj.data = me
            for poly in obj.data.polygons:
                poly.use_smooth = False
            if old.users == 0:
                bpy.data.meshes.remove(old)
            return n_new
        bpy.data.meshes.remove(me)
        n = n_new
    obj.modifiers.remove(mod)
    return n
