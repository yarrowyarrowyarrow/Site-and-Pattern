"""Habitat-structure builders (Z-up, REAL METRES — no unit frame).

One GLB per placeable in src/db/structures.py, keyed by struct_id. Unlike
flora, structures keep their authored materials in the viewer (fixed real-
world colours — wood, stone, water — nothing seasonal), so builders assign
the shared palette from materials.structure_material; baked COLOR_0 AO
multiplies through in three.js.

Authored at the catalogue's default footprint (size_m = the LONG side; the
scene sends no rotation or width, so aspect is baked in). The viewer scales
placements uniformly in XZ by size_m/authored size; `scale_mode` in the
manifest says whether Y follows ("uniform" — objects) or stays authored
("footprint" — flat/linear features like ponds, lawns, fences).

build_structure(struct_id, rng, coll) -> list of objects.
"""

import math

import bmesh
from mathutils import Matrix, Vector

from .materials import structure_material
from .mesh_ops import (add_box, add_cone, add_ellipsoid, add_uv_ball,
                       bm_to_object, place)

# struct_id -> (authored size_m, authored height_m, scale_mode)
STRUCTURE_SPECS = {
    "pond":              (6.0, 0.35, "footprint"),
    "swale":             (10.0, 0.40, "footprint"),
    "rain_garden":       (4.0, 0.35, "footprint"),
    "rain_barrel":       (0.8, 1.30, "uniform"),
    "native_bee_log":    (1.2, 0.45, "uniform"),
    "bee_hotel":         (0.6, 1.60, "uniform"),
    "brush_pile":        (2.5, 1.00, "uniform"),
    "snag":              (1.0, 3.50, "uniform"),
    "rock_xeriscape":    (3.0, 0.60, "footprint"),
    "native_lawn_patch": (6.0, 0.10, "footprint"),
    "raised_bed":        (3.0, 0.45, "footprint"),
    "compost_bin":       (1.5, 1.00, "uniform"),
    "shed":              (3.0, 2.40, "uniform"),
    "fence":             (5.0, 1.25, "footprint"),
    "fire_pit":          (2.0, 0.45, "footprint"),
}


def _obj(bm, name, coll, mat_name):
    return bm_to_object(bm, name, coll, structure_material(mat_name))


def _ring_of_stones(bm, rng, radius, n, r_lo, r_hi, z=0.0, squash=0.7):
    for i in range(n):
        a = i / n * math.tau + rng.random() * 0.4
        r = r_lo + rng.random() * (r_hi - r_lo)
        m = Matrix.Translation((math.cos(a) * radius, math.sin(a) * radius,
                                z + r * squash * 0.5))
        m = m @ Matrix.Rotation(rng.random() * math.pi, 4, "Z")
        add_ellipsoid(bm, r, (1.0 + rng.random() * 0.3,
                              0.8 + rng.random() * 0.3, squash), m, subdiv=1)


def _disc(bm, rx, ry, z, segments=16):
    m = Matrix.Translation((0, 0, z)) @ Matrix.Diagonal((rx, ry, 1.0, 1.0))
    bmesh.ops.create_circle(bm, cap_ends=True, segments=segments,
                            radius=1.0, matrix=m)


# -- water features -----------------------------------------------------------

def _pond(rng, coll):
    water = bmesh.new()
    _disc(water, 2.55, 1.85, 0.10, segments=18)
    stones = bmesh.new()
    for i in range(14):                       # stone rim on the ellipse edge
        a = i / 14 * math.tau + rng.random() * 0.3
        r = 0.22 + rng.random() * 0.16
        m = Matrix.Translation((math.cos(a) * 2.75, math.sin(a) * 1.98,
                                r * 0.42))
        m = m @ Matrix.Rotation(rng.random() * math.pi, 4, "Z")
        add_ellipsoid(stones, r, (1.2, 0.9, 0.6), m, subdiv=1)
    return [_obj(water, "water", coll, "MatWater"),
            _obj(stones, "stones", coll, "MatStone")]


def _swale(rng, coll):
    turf = bmesh.new()                        # two soft berms along the sides
    for side in (-1, 1):
        for i in range(6):
            x = -4.4 + i * 1.76 + rng.random() * 0.3
            m = Matrix.Translation((x, side * 0.62, 0.05))
            add_ellipsoid(turf, 0.55, (1.9, 0.5, 0.35), m, subdiv=1)
    gravel = bmesh.new()                      # the channel bed
    add_box(gravel, (9.6, 0.55, 0.06), Matrix.Translation((0, 0, 0.03)))
    for i in range(10):                       # scattered cobbles
        m = Matrix.Translation((-4.3 + i * 0.95 + (rng.random() - 0.5) * 0.6,
                                (rng.random() - 0.5) * 0.34, 0.09))
        add_ellipsoid(gravel, 0.07 + rng.random() * 0.05, (1.2, 1.0, 0.7),
                      m, subdiv=1)
    return [_obj(turf, "turf", coll, "MatTurf"),
            _obj(gravel, "gravel", coll, "MatGravel")]


def _rain_garden(rng, coll):
    mulch = bmesh.new()                       # saucer of mulch
    _disc(mulch, 1.85, 1.35, 0.04, segments=16)
    stones = bmesh.new()
    _ring_of_stones(stones, rng, 1.65, 10, 0.10, 0.18, squash=0.6)
    water = bmesh.new()                       # small central pool
    _disc(water, 0.75, 0.55, 0.06, segments=12)
    return [_obj(mulch, "mulch", coll, "MatSoil"),
            _obj(stones, "stones", coll, "MatStone"),
            _obj(water, "water", coll, "MatWater")]


def _rain_barrel(rng, coll):
    barrel = bmesh.new()
    add_cone(barrel, 0.38, 0.36, 0.95, 12, Matrix.Translation((0, 0, 0.18)))
    add_cone(barrel, 0.40, 0.40, 0.05, 12,                       # lid rim
             Matrix.Translation((0, 0, 1.13)))
    add_cone(barrel, 0.36, 0.10, 0.08, 12,                       # lid dome
             Matrix.Translation((0, 0, 1.18)))
    stand = bmesh.new()
    add_box(stand, (0.62, 0.62, 0.18), Matrix.Translation((0, 0, 0.09)))
    spigot = bmesh.new()
    add_cone(spigot, 0.03, 0.025, 0.12, 6,
             Matrix.Translation((0, 0.36, 0.34))
             @ Matrix.Rotation(-math.pi / 2, 4, "X"))
    return [_obj(barrel, "barrel", coll, "MatWood"),
            _obj(stand, "stand", coll, "MatWoodDark"),
            _obj(spigot, "spigot", coll, "MatMetal")]


# -- habitat features ---------------------------------------------------------

def _native_bee_log(rng, coll):
    log = bmesh.new()                          # horizontal log, slight taper
    add_cone(log, 0.19, 0.16, 1.15, 10,
             Matrix.Translation((-0.575, 0, 0.20))
             @ Matrix.Rotation(math.pi / 2, 4, "Y"))
    holes = bmesh.new()                        # drilled nest holes in the end
    for i in range(9):
        a = i / 9 * math.tau
        r = 0.10 * (0.4 + 0.6 * rng.random())
        add_cone(holes, 0.016, 0.016, 0.02, 6,
                 Matrix.Translation((0.575, math.cos(a) * r,
                                     0.20 + math.sin(a) * r))
                 @ Matrix.Rotation(math.pi / 2, 4, "Y"))
    return [_obj(log, "log", coll, "MatBark"),
            _obj(holes, "holes", coll, "MatHole")]


def _bee_hotel(rng, coll):
    pole = bmesh.new()
    add_cone(pole, 0.035, 0.03, 1.0, 6, Matrix())
    house = bmesh.new()                        # box + gable roof
    add_box(house, (0.55, 0.28, 0.42), Matrix.Translation((0, 0, 1.21)))
    roof = bmesh.new()
    for s in (-1, 1):
        m = (Matrix.Translation((0, s * 0.09, 1.50))
             @ Matrix.Rotation(s * 0.6, 4, "X"))
        add_box(roof, (0.62, 0.24, 0.03), m)
    holes = bmesh.new()                        # tube openings on the face
    for r in range(3):
        for c in range(5):
            add_cone(holes, 0.020, 0.020, 0.02, 6,
                     Matrix.Translation((-0.18 + c * 0.09, -0.145,
                                         1.09 + r * 0.12))
                     @ Matrix.Rotation(math.pi / 2, 4, "X"))
    return [_obj(pole, "pole", coll, "MatWoodDark"),
            _obj(house, "house", coll, "MatWood"),
            _obj(roof, "roof", coll, "MatWoodDark"),
            _obj(holes, "holes", coll, "MatHole")]


def _brush_pile(rng, coll):
    branches = bmesh.new()                     # criss-crossed branch jumble
    for i in range(30):
        az = rng.random() * math.tau
        tilt = 0.9 + rng.random() * 0.5
        ln = 0.8 + rng.random() * 0.9
        r0 = 0.035 + rng.random() * 0.04
        h = 0.05 + rng.random() * 0.6 * (1 - ln / 2.0)
        off = Vector(((rng.random() - 0.5) * 1.2,
                      (rng.random() - 0.5) * 1.2, h))
        add_cone(branches, r0, r0 * 0.5, ln, 5,
                 Matrix.Translation(off)
                 @ Matrix.Rotation(az, 4, "Z")
                 @ Matrix.Rotation(tilt, 4, "Y"))
    return [_obj(branches, "branches", coll, "MatBark")]


def _snag(rng, coll):
    trunk = bmesh.new()                        # dead trunk, jagged broken top
    add_cone(trunk, 0.22, 0.11, 3.3, 8, Matrix())
    add_cone(trunk, 0.11, 0.02, 0.25, 5,       # splintered tip
             Matrix.Translation((0.03, 0, 3.3)))
    for i in range(4):                         # bare stub branches
        a = i * 1.7 + rng.random()
        z = 1.4 + i * 0.5
        add_cone(trunk, 0.045, 0.015, 0.5 + rng.random() * 0.3, 5,
                 place(z=z, rot_z=a, tilt_y=1.2 + rng.random() * 0.3))
    holes = bmesh.new()                        # woodpecker cavities
    for z, a in ((1.9, 0.4), (2.6, 2.6)):
        add_uv_ball(holes, 0.05, (0.6, 1, 1.3),
                    Matrix.Translation((math.cos(a) * 0.15,
                                        math.sin(a) * 0.15, z)), u=6, v=5)
    return [_obj(trunk, "trunk", coll, "MatWoodDark"),
            _obj(holes, "holes", coll, "MatHole")]


def _rock_xeriscape(rng, coll):
    gravel = bmesh.new()
    _disc(gravel, 1.5, 1.15, 0.03, segments=16)
    rocks = bmesh.new()                        # a few big boulders + cobbles
    for i in range(4):
        a = i / 4 * math.tau + rng.random()
        r = 0.28 + rng.random() * 0.18
        m = Matrix.Translation((math.cos(a) * 0.7, math.sin(a) * 0.5,
                                r * 0.55))
        m = m @ Matrix.Rotation(rng.random() * math.pi, 4, "Z")
        add_ellipsoid(rocks, r, (1.1, 0.9, 0.75), m, subdiv=1)
    for i in range(7):
        a = rng.random() * math.tau
        rr = 0.9 + rng.random() * 0.45
        r = 0.07 + rng.random() * 0.07
        add_ellipsoid(rocks, r, (1.2, 1.0, 0.7),
                      Matrix.Translation((math.cos(a) * rr,
                                          math.sin(a) * rr * 0.75, r * 0.4)),
                      subdiv=1)
    return [_obj(gravel, "gravel", coll, "MatGravel"),
            _obj(rocks, "rocks", coll, "MatStone")]


def _native_lawn_patch(rng, coll):
    turf = bmesh.new()                         # low rounded turf slab
    add_box(turf, (5.8, 3.8, 0.06), Matrix.Translation((0, 0, 0.03)))
    for i in range(9):                         # sparse tufts so it reads alive
        m = Matrix.Translation(((rng.random() - 0.5) * 5.2,
                                (rng.random() - 0.5) * 3.2, 0.06))
        add_ellipsoid(turf, 0.10 + rng.random() * 0.06, (1.2, 1.2, 0.7), m,
                      subdiv=1)
    return [_obj(turf, "turf", coll, "MatTurf")]


# -- growing / storage / infrastructure ---------------------------------------

def _raised_bed(rng, coll):
    frame = bmesh.new()                        # plank walls
    for s in (-1, 1):
        add_box(frame, (3.0, 0.05, 0.40),
                Matrix.Translation((0, s * 0.575, 0.20)))
        add_box(frame, (0.05, 1.10, 0.40),
                Matrix.Translation((s * 1.475, 0, 0.20)))
    soil = bmesh.new()
    add_box(soil, (2.85, 1.05, 0.30), Matrix.Translation((0, 0, 0.20)))
    return [_obj(frame, "frame", coll, "MatWood"),
            _obj(soil, "soil", coll, "MatSoil")]


def _compost_bin(rng, coll):
    posts = bmesh.new()
    for sx in (-1, 1):
        for sy in (-1, 1):
            add_box(posts, (0.07, 0.07, 0.95),
                    Matrix.Translation((sx * 0.66, sy * 0.66, 0.475)))
    slats = bmesh.new()                        # horizontal slats, airy gaps
    for z in (0.16, 0.40, 0.64, 0.88):
        for s in (-1, 1):
            add_box(slats, (1.40, 0.04, 0.12),
                    Matrix.Translation((0, s * 0.70, z)))
            add_box(slats, (0.04, 1.40, 0.12),
                    Matrix.Translation((s * 0.70, 0, z)))
    mound = bmesh.new()                        # compost heap peeking over
    add_ellipsoid(mound, 0.52, (1.15, 1.15, 0.6),
                  Matrix.Translation((0, 0, 0.85)), subdiv=1)
    return [_obj(posts, "posts", coll, "MatWoodDark"),
            _obj(slats, "slats", coll, "MatWood"),
            _obj(mound, "mound", coll, "MatSoil")]


def _shed(rng, coll):
    walls = bmesh.new()
    add_box(walls, (2.9, 2.4, 1.9), Matrix.Translation((0, 0, 0.95)))
    roof = bmesh.new()                         # gable with overhang
    for s in (-1, 1):
        m = (Matrix.Translation((0, s * 0.66, 2.13))
             @ Matrix.Rotation(s * 0.42, 4, "X"))
        add_box(roof, (3.2, 1.48, 0.06), m)
    door = bmesh.new()
    add_box(door, (0.75, 0.05, 1.55), Matrix.Translation((-0.5, -1.21, 0.78)))
    return [_obj(walls, "walls", coll, "MatWood"),
            _obj(roof, "roof", coll, "MatWoodDark"),
            _obj(door, "door", coll, "MatWoodDark")]


def _fence(rng, coll):
    posts = bmesh.new()
    for i in range(4):
        add_box(posts, (0.09, 0.09, 1.25),
                Matrix.Translation((-2.4 + i * 1.6, 0, 0.625)))
    rails = bmesh.new()
    for z in (0.45, 0.85, 1.18):
        add_box(rails, (4.95, 0.05, 0.10), Matrix.Translation((0, 0, z)))
    return [_obj(posts, "posts", coll, "MatWoodDark"),
            _obj(rails, "rails", coll, "MatWood")]


def _fire_pit(rng, coll):
    stones = bmesh.new()
    _ring_of_stones(stones, rng, 0.82, 11, 0.16, 0.22, squash=0.75)
    ash = bmesh.new()
    _disc(ash, 0.62, 0.62, 0.05, segments=12)
    logs = bmesh.new()                         # two crossed logs
    for a in (0.5, 2.1):
        add_cone(logs, 0.06, 0.05, 0.7, 6,
                 place(-0.35 * math.cos(a), -0.35 * math.sin(a), 0.10,
                       rot_z=a, tilt_y=math.pi / 2 - 0.15))
    return [_obj(stones, "stones", coll, "MatStone"),
            _obj(ash, "ash", coll, "MatAsh"),
            _obj(logs, "logs", coll, "MatBark")]


_BUILDERS = {
    "pond": _pond, "swale": _swale, "rain_garden": _rain_garden,
    "rain_barrel": _rain_barrel, "native_bee_log": _native_bee_log,
    "bee_hotel": _bee_hotel, "brush_pile": _brush_pile, "snag": _snag,
    "rock_xeriscape": _rock_xeriscape, "native_lawn_patch": _native_lawn_patch,
    "raised_bed": _raised_bed, "compost_bin": _compost_bin, "shed": _shed,
    "fence": _fence, "fire_pit": _fire_pit,
}


def build_structure(struct_id, rng, coll):
    """Build one habitat structure at real-metre scale; returns its objects."""
    return _BUILDERS[struct_id](rng, coll)
