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


def add_box(bm, size_xyz, matrix):
    """An axis-aligned box of the given (x, y, z) size, centred by `matrix`."""
    m = matrix @ Matrix.Diagonal((size_xyz[0], size_xyz[1], size_xyz[2], 1.0))
    bmesh.ops.create_cube(bm, size=1.0, matrix=m, calc_uvs=False)


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


# add_leaf randomises a blade's length and droop; the upper bounds live here so
# leaf_extent() below can predict the reach without duplicating the algorithm.
_LEAF_LEN_MAX = 1.2                       # length × (0.8 + rand·0.4)
_LEAF_DROOP_MAX = 0.18                    # droop = base + rand·0.18


def leaf_extent(length, tilt, shape="lance"):
    """Worst-case ``(horizontal, vertical)`` reach of a leaf :func:`add_leaf`
    would stamp at the origin.

    Builders need this *before* any geometry exists, to shape a plant to its
    species' aspect (mesh_ops.shape_to_aspect). Keeping the model next to
    add_leaf is the point: a fern frond is tilted only 0.5 rad from vertical but
    droops forward, so guessing ``sin(tilt)`` for the reach and ``cos(tilt)``
    for the rise puts the aspect out by 40%.
    """
    ln = length * _LEAF_LEN_MAX
    droop = (0.05 if shape == "strap" else 0.12) + _LEAF_DROOP_MAX
    return (ln * (math.sin(tilt) + droop * math.cos(tilt)),
            ln * max(0.0, math.cos(tilt) - droop * math.sin(tilt)))


def add_leaf(bm, rng, length, width, tilt, azimuth, at, shape):
    """One flat leaf with a real width profile (port of makeLeaf, Z-up).

    Built along +Z, tilted `tilt` from vertical about Y, spun to `azimuth`
    about Z, then translated to `at` (a Vector or tuple, may be None).
    """
    segs = 4
    ln = length * (_LEAF_LEN_MAX - 0.4 + rng.random() * 0.4)
    droop = ((0.05 if shape == "strap" else 0.12)
             + rng.random() * _LEAF_DROOP_MAX)
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
    """Normalise a set of part objects jointly to the contract frame and return
    the resulting horizontal half-extent.

    Base goes to z=0 and height to UNIT_HEIGHT, scaled **uniformly** — the
    authored aspect ratio is the asset's identity (a spruce is 3.3× taller than
    wide) and squashing it into a 1×1×1 box is what deformed every instance
    before V2.29; see the unit-frame note in conventions.py. The returned
    half-width is published in the manifest and re-measured by the viewer.
    Baked into the mesh data (objects keep identity transforms).
    """
    objs = [o for o in objs if o is not None]
    if not objs:
        return 0.0
    lo, hi = _joint_bounds(objs)
    sz = max(1e-6, hi.z - lo.z)
    s = C.UNIT_HEIGHT / sz
    for obj in objs:
        me = obj.data
        for v in me.vertices:
            v.co.x *= s
            v.co.y *= s
            v.co.z = (v.co.z - lo.z) * s
        me.update()
    half = max(1e-6, abs(lo.x), abs(hi.x), abs(lo.y), abs(hi.y)) * s
    if half > C.UNIT_HALF_WIDTH_MAX:
        raise ValueError(
            f"unit_frame: half-width {half:.2f} > {C.UNIT_HALF_WIDTH_MAX} — the "
            f"builder is producing a pancake; check its aspect shaping")
    return round(half, 5)


def shape_to_aspect(points, aspect, height=None, radii=None, radii_z=None):
    """Scale the XY of ``points`` in place so the finished shape hits ``aspect``
    (height ÷ full width), leaving Z alone. Returns the applied factor.

    This is how a crown is narrowed to its species' real proportions: only the
    *anchor positions* move, so the foliage clumps and branch cross-sections
    stamped at them keep their authored size and stay round. Scaling the
    finished mesh instead (or letting the instance transform do it) is the
    deformation this whole contract exists to avoid.

    ``radii`` is the parallel list of how far the geometry stamped at each point
    will reach past it — a foliage clump's radius. What the viewer measures is
    the *mesh*, so a point at distance d contributes ``d·k + r`` to the final
    half-extent. Solving ``max(d·k + r) = target`` exactly (rather than guessing
    a single overhang) is what makes a broad oak and a narrow spruce both land
    on their real proportions; on a narrow crown the clumps are most of the
    width, so an approximation is off by tens of percent.

    ``radii_z`` is the same reach measured vertically, for geometry that is not
    round — a spreading shrub's leaf masses are 1.25 wide and 0.7 tall, and
    using the horizontal figure for both overestimates the height (and so the
    width target) by a fifth. Defaults to ``radii``.
    """
    if not points:
        return 1.0
    rads = list(radii) if radii is not None else [0.0] * len(points)
    rz = list(radii_z) if radii_z is not None else rads
    dists = [math.hypot(p.x, p.y) for p in points]
    if height is not None:
        h = height
    else:
        h = max(1e-6, max(p.z + r for p, r in zip(points, rz))
                - min(p.z - r for p, r in zip(points, rz)))
    target = h / max(1e-6, aspect) / 2.0
    # k so that every point's stamped extent fits, with the outermost touching.
    ks = [(target - r) / d for d, r in zip(dists, rads) if d > 1e-6]
    k = max(0.02, min(ks)) if ks else 1.0
    for p in points:
        p.x *= k
        p.y *= k
    return k


def add_cone_between(bm, start, end, r_bottom, r_top, segments):
    """A tapered cylinder from ``start`` to ``end`` (both Vectors).

    The branch-shaping companion to :func:`add_cone`: after
    :func:`shape_to_aspect` has moved a skeleton's endpoints, a segment is
    re-stamped from its two corrected points, so narrowing a crown changes each
    branch's length and direction — never its cross-section.
    """
    d = Vector(end) - Vector(start)
    depth = d.length
    if depth < 1e-6:
        return
    rot = d.to_track_quat("Z", "Y").to_matrix().to_4x4()
    add_cone(bm, r_bottom, r_top, depth, segments,
             Matrix.Translation(Vector(start)) @ rot)


def squash_to_aspect(objs, aspect):
    """Scale the built mesh's XY so it lands EXACTLY on ``aspect``. Returns the
    factor.

    **Only for flat-leaf geometry** — herbs, grass/reed tufts, vines. A leaf or
    blade is a flat ribbon, so scaling it horizontally makes it a slightly
    narrower leaf, not a deformed one; there is no sphere to go oblate. Woody
    crowns and groundcover domes must NOT use this — they carry round foliage
    masses and get :func:`shape_to_aspect` on their anchors instead.

    This exists because predicting a leafy plant's extent from its parameters is
    biased: the builder's worst-case reach assumes every blade takes its longest
    random length and points straight out, and a plant with a dozen leaves never
    draws that, so a model-only pass lands ~30% narrow. Measuring the finished
    mesh is exact.
    """
    objs = [o for o in objs if o is not None]
    if not objs:
        return 1.0
    lo, hi = _joint_bounds(objs)
    half = max(1e-6, abs(lo.x), abs(hi.x), abs(lo.y), abs(hi.y))
    h = max(1e-6, hi.z - lo.z)
    k = (h / max(1e-6, aspect) / 2.0) / half
    for obj in objs:
        me = obj.data
        for v in me.vertices:
            v.co.x *= k
            v.co.y *= k
        me.update()
    return k


def clamp_footprint(objs, max_half):
    """Scale XZ (Blender XY) down so the joint footprint fits max_half.
    Structures promise their authored size_m; a randomised builder (brush
    pile branches) can sprawl past it — this reins the geometry back in."""
    objs = [o for o in objs if o is not None]
    if not objs:
        return
    lo, hi = _joint_bounds(objs)
    half = max(abs(lo.x), abs(hi.x), abs(lo.y), abs(hi.y))
    if half <= max_half:
        return
    f = max_half / half * 0.98
    for obj in objs:
        me = obj.data
        for v in me.vertices:
            v.co.x *= f
            v.co.y *= f
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
