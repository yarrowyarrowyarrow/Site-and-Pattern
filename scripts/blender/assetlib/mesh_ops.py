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


# Width profile along a blade, t = 0 at the base to 1 at the tip. The three
# original entries (ovate / strap / lance) are joined by the shapes the seed data
# actually records (schema v47/v48 `leaf_shape`), so a species' blade outline is
# drawn rather than approximated by whichever of three its form happened to pick.
def _leaf_width(shape, t):
    tc = min(0.96, max(0.06, t))
    if shape in ("ovate", "elliptic"):
        return math.sin(math.pi * tc) ** 0.7          # widest at/below middle
    if shape in ("obovate", "spatulate"):
        # Widest ABOVE the middle — a pussytoes or fleabane rosette leaf, which
        # the ovate profile draws upside down.
        return math.sin(math.pi * tc) ** 0.7 * (0.35 + 0.9 * tc)
    if shape == "orbicular":
        return math.sin(math.pi * tc) ** 0.45         # near-round
    if shape == "reniform":
        return math.sin(math.pi * tc) ** 0.4 * (1.25 - 0.45 * tc)   # kidney
    if shape == "cordate":
        return math.sin(math.pi * tc) ** 0.55 * (1.35 - 0.6 * tc)   # heart
    if shape == "sagittate":
        # Arrowhead: flared basal lobes, then a long taper.
        return (1.15 if t < 0.16 else
                max(0.08, math.sin(math.pi * tc) ** 0.9 * 0.95))
    if shape in ("lobed", "pinnatifid", "bipinnate"):
        # Deeply cut blades read as a lobed silhouette on a flat ribbon: a
        # sinusoid on the base profile. True notches would need a triangulated
        # outline, which costs 2-3x the triangles for a sub-centimetre effect.
        lobes = 3 if shape == "lobed" else (5 if shape == "pinnatifid" else 7)
        wobble = 1.0 - (0.45 if shape == "bipinnate" else 0.32) * (
            0.5 - 0.5 * math.cos(2 * math.pi * lobes * tc))
        return max(0.06, math.sin(math.pi * tc) ** 0.7 * wobble)
    if shape in ("strap", "linear"):
        return 1.0 if t < 0.9 else max(0.15, (1 - t) / 0.1)
    if shape in ("needle", "awl", "scale"):
        return max(0.08, 1 - 0.55 * t)
    return max(0.05, 1 - 0.9 * t)          # lance / lanceolate / default


# Natural width ÷ length for each blade outline. Once `leaf_size_cm` sets the
# LENGTH from data, the width has to come from the shape or every species would
# be drawn at whatever ratio its growth form happened to carry — a 20 cm
# balsamroot arrowhead and a 20 cm iris strap are not the same leaf.
LEAF_WIDTH_RATIO = {
    "needle": 0.03, "awl": 0.05, "scale": 0.25, "linear": 0.06,
    "lanceolate": 0.22, "elliptic": 0.45, "ovate": 0.62, "obovate": 0.55,
    "spatulate": 0.40, "orbicular": 0.95, "cordate": 0.85, "reniform": 1.25,
    "sagittate": 0.55, "lobed": 0.75, "pinnatifid": 0.42, "bipinnate": 0.35,
    "trifoliate": 0.85, "compound_pinnate": 0.45, "compound_palmate": 0.9,
    "strap": 0.06,
}

# Blades stamped as a rachis carrying leaflets rather than one ribbon.
COMPOUND_SHAPES = frozenset({"trifoliate", "compound_pinnate",
                             "compound_palmate", "bipinnate"})
# Leaflet pairs (plus a terminal leaflet) per compound outline.
_LEAFLET_PAIRS = {"trifoliate": 1, "compound_pinnate": 3,
                  "compound_palmate": 2, "bipinnate": 4}


def leaf_width_for(shape, length):
    """Natural blade width for a leaf of ``length`` with this outline."""
    return length * LEAF_WIDTH_RATIO.get(shape, 0.3)


def add_compound_leaf(bm, rng, length, width, tilt, azimuth, at, shape):
    """One compound leaf: a slim rachis carrying paired leaflets and a terminal.

    A third of the catalogue's leaves are compound — every pea (lupine,
    milkvetch, hedysarum), rose, cinquefoil, columbine, meadow rue and mountain
    ash — and drawing them as a single ribbon is what made a lupine and a
    fireweed differ only in size. ``compound_palmate`` fans its leaflets from
    one point (lupine); the rest run up the rachis.
    """
    pairs = _LEAFLET_PAIRS.get(shape, 3)
    ln = length * (_LEAF_LEN_MAX - 0.4 + rng.random() * 0.4)
    droop = 0.10 + rng.random() * _LEAF_DROOP_MAX
    mat = Matrix.Rotation(azimuth, 4, "Z") @ Matrix.Rotation(tilt, 4, "Y")
    if at is not None:
        mat = Matrix.Translation(Vector(at)) @ mat
    palmate = shape == "compound_palmate"
    # Rachis: a thin two-point ribbon, so it merges with the leaflets' attributes.
    r_from = 0.0 if palmate else 0.12
    stalk = [mat @ Vector((droop * (u ** 1.4) * ln, 0, ln * u))
             for u in (0.0, 0.55, 1.0)]
    add_ribbon(bm, stalk, [ln * 0.012, ln * 0.009, ln * 0.006],
               (mat.to_3x3() @ Vector((0, 1, 0))).normalized())
    leaflet_len = ln * (0.42 if palmate else 0.30)
    leaflet_w = leaflet_len * (0.5 if palmate else 0.42)
    n = pairs * 2 + 1
    for i in range(n):
        if palmate:
            # A fan from the rachis tip.
            frac, spread = 1.0, (i / (n - 1) - 0.5) * 2.2
        else:
            frac = r_from + (1 - r_from) * (i // 2) / max(1, pairs)
            spread = (-0.95 if i % 2 else 0.95) * (0.0 if i == n - 1 else 1.0)
        base = mat @ Vector((droop * (frac ** 1.4) * ln, 0, ln * frac))
        add_leaf(bm, rng, leaflet_len, leaflet_w,
                 tilt * 0.45 + abs(spread) * 0.55,
                 azimuth + spread, base, "elliptic")


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
    droop = (0.05 if shape in ("strap", "linear") else 0.12) + _LEAF_DROOP_MAX
    h = ln * (math.sin(tilt) + droop * math.cos(tilt))
    v = ln * max(0.0, math.cos(tilt) - droop * math.sin(tilt))
    if shape in COMPOUND_SHAPES:
        # A compound leaf's leaflets stick out sideways from the rachis, so it
        # is wider than a simple blade of the same length and no taller. The
        # aspect fixed point and shape_to_aspect both trust this figure.
        h += ln * (0.42 if shape == "compound_palmate" else 0.30) * 0.8
    return (h, v)


def add_blade_or_leaf(bm, rng, length, width, tilt, azimuth, at, shape):
    """Stamp the right primitive for ``shape`` — one ribbon, or a rachis with
    leaflets. The single entry point builders should call so a new compound
    outline never needs another branch at every call site."""
    if shape in COMPOUND_SHAPES:
        add_compound_leaf(bm, rng, length, width, tilt, azimuth, at, shape)
    else:
        add_leaf(bm, rng, length, width, tilt, azimuth, at, shape)


# ── triangle cost, so leaf counts can be budgeted before anything is stamped ──

# What each stamp costs. A builder tuned for simple blades blows its budget the
# moment the species turns out to carry compound ones, so the counts have to be
# derived from the outline rather than fixed — see thin_leaf_nodes.
CONE_TRIS = 16                            # add_cone(segments=4), fan-capped
_SIMPLE_LEAF_TRIS = 8                     # add_leaf: 4 ribbon segments
_RACHIS_TRIS = 4                          # add_compound_leaf's 3-point stalk


def leaf_tris(shape):
    """Triangles one :func:`add_blade_or_leaf` stamp costs for this outline."""
    if shape in COMPOUND_SHAPES:
        pairs = _LEAFLET_PAIRS.get(shape, 3)
        return _RACHIS_TRIS + (pairs * 2 + 1) * _SIMPLE_LEAF_TRIS
    return _SIMPLE_LEAF_TRIS


ICO_TRIS = 20                             # add_ellipsoid(subdiv=0) foliage mass


def thin_groups_to_budget(groups, cost_each, budget, structural_tris,
                          headroom=0.94):
    """Evenly drop whole GROUPS until their contents fit ``budget`` triangles
    alongside ``structural_tris`` of stem/branch geometry.

    A builder's element counts are tuned for one species and then asked to serve
    a family, so they have to be derived from the budget rather than fixed — and
    deriving them here means a builder can be made denser or a species coarser
    without anyone re-tuning a magic number per tier. Every flora builder thins
    through this: an over-budget asset is a hard export failure, and discovering
    that at export time is how three separate builders got hand-tuned counts that
    were wrong for most of the species they served.

    Groups, not items, because the grouping is meaningful: a leaf node's opposite
    pair or whorl of three must stay intact (the arrangement is the field mark the
    leaves exist to show, so halving a pair would misdraw the species), and a
    branch tip's cluster reads as one tuft.
    """
    allow = max(1, int((budget * headroom - structural_tris) / max(1, cost_each)))
    total = sum(len(g) for g in groups)
    if not groups or total <= allow:
        return groups
    step = len(groups) / max(1, int(len(groups) * allow / total))
    kept, spent, i = [], 0, 0.0
    while i < len(groups):
        group = groups[int(i)]
        if kept and spent + len(group) > allow:
            break
        kept.append(group)
        spent += len(group)
        i += step
    return kept


def thin_leaf_nodes(nodes, shape, budget, structural_tris, headroom=0.94):
    """:func:`thin_groups_to_budget` for leaf nodes, costed by blade outline.

    A compound leaf costs 3-9x a simple blade (a rachis plus 2n+1 leaflets), so
    this is what lets a rose and a dogwood share one builder: the rose ends up
    with fewer, larger leaves, which is also how the plants themselves resolve
    the same constraint.
    """
    return thin_groups_to_budget(nodes, leaf_tris(shape), budget,
                                 structural_tris, headroom)


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
    # Scale each DISTINCT vector once. Callers legitimately pass the same object
    # more than once — a cane's fork is the end of one segment and the start of
    # the next and of every twig on it; a node's opposite leaves share one
    # anchor — and scaling in list order would move those points by k², k³, k⁴,
    # collapsing exactly the joints that hold a plant together. Duplicates still
    # count toward the solve above (they are the same constraint), so only the
    # mutation needs to be unique.
    seen = set()
    for p in points:
        if id(p) in seen:
            continue
        seen.add(id(p))
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
