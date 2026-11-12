"""
tests/test_walk_walls.py — Walk the garden gets past the house, and starts
outside it (V3.43).

A building was a circle to the walker, reaching 90% of the way to its farthest
corner (``buildWalkObstacles``, html/scene3d/08-modes.js). On the review's lot
the house is 10.8 x 12 m on a lot 15.2 m wide: a circle 7.3 m in radius, centred
7.6 m from each side line. With his own 0.35 m there was no way down either side
yard, so nothing led from the front yard to the back. And he started at the
centre of the stage, which on that lot is inside the house.

A building stops him at its walls now, and in a yard he starts where a neighbour
stands (``scene.views.street``, src/scene_views.py). A walk through a wild
community has no street and keeps its centre, which its layout leaves clear for
him (src/reference_layout.py). This runs the viewer's own functions in node, the
way tests/test_bee_spawn.py runs ``clearOfCrowns``.
"""

import json
import math
import pathlib
import re
import shutil
import subprocess
import unittest

_JS = pathlib.Path(__file__).resolve().parent.parent / "html" / "scene3d"

HOUSE = {"kind": "building", "height_m": 6.5,
         "ring": [[-5.4, -9.3], [5.4, -9.3], [5.4, 2.7], [-5.4, 2.7]]}
#: Scene y is north; the viewer's z is south. A point (x, y) is (x, -y) to it.


def _node():
    return shutil.which("node") or shutil.which("nodejs")


def _function(name, filename):
    src = (_JS / filename).read_text(encoding="utf-8")
    match = re.search(r"^function %s\(.*?^}\n" % name, src, re.S | re.M)
    if not match:
        raise AssertionError(f"{filename} no longer defines {name}")
    return match.group(0)


def _walker_radius():
    src = (_JS / "08-modes.js").read_text(encoding="utf-8")
    return float(re.search(r"const _WALKER_R = ([\d.]+);", src).group(1))


def _run(scene, tail, extra=""):
    script = "\n".join([
        "var lastSceneObj = %s;" % json.dumps(scene),
        "var walkObstacles = [];",
        "const _WALKER_R = %r;" % _walker_radius(),
        extra,
        _function("standing", "01-core.js"),
        _function("buildWalkObstacles", "08-modes.js"),
        _function("ringNearest", "08-modes.js"),
        _function("resolveWalkCollision", "08-modes.js"),
        "buildWalkObstacles();",
        tail,
    ])
    proc = subprocess.run([_node(), "-"], input=script, capture_output=True,
                          text=True, timeout=60, encoding="utf-8")
    if proc.returncode != 0:
        raise AssertionError(f"node failed: {proc.stderr}")
    return json.loads(proc.stdout)


def _resolve(scene, x, y):
    """Where the walker ends up when he tries to stand at scene (x, y)."""
    nx, nz = _run(scene, "console.log(JSON.stringify(resolveWalkCollision(%r, %r)));"
                  % (x, -y))
    return round(nx, 3), round(-nz, 3)


def _tree(x, y, **more):
    return {"x": x, "y": y, "plant_type": "tree", "height_m": 8.0, **more}


@unittest.skipIf(_node() is None, "no node binary")
class AHouseHasWalls(unittest.TestCase):

    def test_the_side_yard_is_open(self):
        """1.2 m from the west wall, 1 m inside the lot line: the old circle
        (7.3 m round the house's middle) reached past it."""
        scene = {"plants": [], "buildings": [HOUSE]}
        self.assertEqual(_resolve(scene, -6.6, -3.0), (-6.6, -3.0))

    def test_he_can_walk_from_the_front_yard_to_the_back(self):
        scene = {"plants": [], "buildings": [HOUSE]}
        end = _run(scene, """
          let x = -6.6, z = 15;                       // front yard, y = -15
          for (let i = 0; i < 120; i++) [x, z] = resolveWalkCollision(x, z - 0.25);
          console.log(JSON.stringify([x, -z]));""")
        self.assertAlmostEqual(end[0], -6.6, places=6)
        self.assertGreater(end[1], 10.0, "he was stopped beside the house")

    def test_a_wall_stops_him_a_body_width_out(self):
        scene = {"plants": [], "buildings": [HOUSE]}
        r = _walker_radius()
        x, y = _resolve(scene, 0.0, -9.4)             # 10 cm off the south wall
        self.assertAlmostEqual(y, -9.3 - r, places=3)
        self.assertAlmostEqual(x, 0.0, places=3)

    def test_inside_a_building_he_is_put_outside_its_nearest_wall(self):
        scene = {"plants": [], "buildings": [HOUSE]}
        r = _walker_radius()
        x, y = _resolve(scene, 4.9, -3.0)             # half a metre in from the east wall
        self.assertAlmostEqual(x, 5.4 + r, places=3)
        self.assertAlmostEqual(y, -3.0, places=3)

    def test_walking_into_a_wall_never_lets_him_through(self):
        scene = {"plants": [], "buildings": [HOUSE]}
        end = _run(scene, """
          let x = 0, z = 12;                          // south of the house
          for (let i = 0; i < 80; i++) [x, z] = resolveWalkCollision(x, z - 0.25);
          console.log(JSON.stringify([x, -z]));""")
        self.assertLess(end[1], -9.3, "he walked through the south wall")

    def test_a_drawn_tree_canopy_is_not_a_wall(self):
        """He strolls under a crown; only a trunk stops him."""
        crown = dict(HOUSE, kind="canopy")
        self.assertEqual(_resolve({"plants": [], "buildings": [crown]}, 0.0, -3.0),
                         (0.0, -3.0))

    def test_a_trunk_still_stops_him_and_a_tree_that_is_gone_does_not(self):
        standing = {"plants": [_tree(0.0, 0.0)], "buildings": []}
        x, y = _resolve(standing, 0.1, 0.0)
        self.assertGreater(math.hypot(x, y), 0.45)
        for lost in ({"health_state": "dead", "gone": "shade"},
                     {"gone": "short_lived"}):
            gone = {"plants": [_tree(0.0, 0.0, **lost)], "buildings": []}
            self.assertEqual(_resolve(gone, 0.1, 0.0), (0.1, 0.0), lost)


_SPAWN_STUBS = """
var walkAvatar = { position: { set(x, y, z) { this.x = x; this.y = y; this.z = z; } },
                   rotation: {} };
var walkYaw, walkPitch, walkFacing, walkPrevT;
function groundAt() { return 0; }
var lastBounds = %s, lastViews = %s;
"""


def _spawn(bounds, views):
    out = _run({"plants": [], "buildings": [HOUSE]}, "\n".join([
        _function("walkSpawn", "08-modes.js"),
        "walkSpawn();",
        "console.log(JSON.stringify({x: walkAvatar.position.x,"
        " y: -walkAvatar.position.z, yaw: walkYaw, turned: walkAvatar.rotation.y}));",
    ]), extra=_SPAWN_STUBS % (json.dumps(bounds), json.dumps(views)))
    return out


@unittest.skipIf(_node() is None, "no node binary")
class WhereHeStarts(unittest.TestCase):
    BOUNDS = {"min_x": -25, "min_y": -25, "max_x": 25, "max_y": 25}

    def test_in_a_yard_he_starts_where_a_neighbour_stands_facing_in(self):
        street = {"eye": [-0.8, -22.3], "look": [-2.3, -13.2], "bearing": 180.0}
        got = _spawn(self.BOUNDS, {"street": street})
        self.assertEqual((got["x"], got["y"]), (-0.8, -22.3))
        # Forward is (sin yaw, cos yaw) in scene (east, north): toward the look.
        want = math.atan2(-2.3 - -0.8, -13.2 - -22.3)
        self.assertAlmostEqual(got["yaw"], want, places=6)
        self.assertAlmostEqual(got["turned"], want, places=6)
        self.assertGreater(math.cos(got["yaw"]), 0.9, "he faces away from the yard")

    def test_the_street_can_be_to_the_east(self):
        street = {"eye": [11.6, 0.0], "look": [3.0, 0.0], "bearing": 90.0}
        got = _spawn(self.BOUNDS, {"street": street})
        self.assertAlmostEqual(math.sin(got["yaw"]), -1.0, places=6)   # facing west

    def test_a_wild_landscape_keeps_its_centre(self):
        """No outline, no street: the walk's layout leaves the middle clear for
        him, and he starts there facing north as he always did."""
        for views in ({}, None):
            got = _spawn({"min_x": -30, "min_y": -20, "max_x": 20, "max_y": 30},
                         views)
            self.assertEqual((got["x"], got["y"], got["yaw"]), (-5, 5, 0))


if __name__ == "__main__":
    unittest.main()
