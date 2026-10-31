"""
tests/test_bee_spawn.py — Fly as a bee starts clear of the plants (V3.37).

``beeSpawn`` (html/scene3d/06-fly.js) put the camera 6 m south of the design's
centre and 1.6 m up whatever stood there. A shrub there filled the view with its
stems, two dark walls either side of the bee (found while chasing the owner's
fly-mode screenshot, dark from edge to edge, which headless runs of the broken
viewer alone did not reproduce). The walker had the same fault and was moved
off trunks in V2.46. ``clearOfCrowns``
(08-modes.js) steps the start south until it clears every crown taller than the
bee flies and every building; this runs it in node over a scene's plants.
"""

import json
import pathlib
import re
import shutil
import subprocess
import unittest

_JS = pathlib.Path(__file__).resolve().parent.parent / "html" / "scene3d"


def _node():
    return shutil.which("node") or shutil.which("nodejs")


def _function(name, filename):
    src = (_JS / filename).read_text(encoding="utf-8")
    match = re.search(r"^function %s\(.*?^}\n" % name, src, re.S | re.M)
    if not match:
        raise AssertionError(f"{filename} no longer defines {name}")
    return match.group(0)


def _start(scene, x=0.0, z=6.0):
    """The z clearOfCrowns gives for a start at (x, z) in `scene`."""
    script = "\n".join([
        "var lastSceneObj = %s;" % json.dumps(scene),
        _function("clearOfCrowns", "08-modes.js"),
        "console.log(JSON.stringify(clearOfCrowns(%r, %r)));" % (x, z),
    ])
    proc = subprocess.run([_node(), "-"], input=script, capture_output=True,
                          text=True, timeout=60, encoding="utf-8")
    if proc.returncode != 0:
        raise AssertionError(f"node failed: {proc.stderr}")
    return json.loads(proc.stdout)


def _plant(x, y, h, c, kind="shrub"):
    return {"x": x, "y": y, "height_m": h, "canopy_m": c, "plant_type": kind}


@unittest.skipIf(_node() is None, "no node binary")
class TheBeeStartsInTheOpen(unittest.TestCase):

    def test_open_ground_is_left_where_it_was(self):
        self.assertEqual(_start({"plants": [_plant(0, 3, 4, 3)]}), 6.0)

    def test_a_shrub_on_the_spot_is_stepped_clear_of(self):
        """A 5 m chokecherry, 4.5 m across, right where the bee starts (scene
        y = -6 is z = 6): the start ends outside its crown, south of it."""
        z = _start({"plants": [_plant(0, -6, 5, 4.5)]})
        self.assertGreaterEqual(z - 6, 4.5 / 2)

    def test_flowers_under_the_bee_do_not_move_it(self):
        """A bee flies over a meadow; only what stands taller than it does."""
        flowers = [_plant(0, -6, 0.8, 0.45, "wildflower"), _plant(0.3, -6, 1.0, 0.6)]
        self.assertEqual(_start({"plants": flowers}), 6.0)

    def test_a_building_is_stepped_clear_of(self):
        house = {"ring": [[-4, -9], [4, -9], [4, -3], [-4, -3]], "height_m": 6}
        z = _start({"plants": [], "buildings": [house]})
        self.assertGreater(z, 9)

    def test_no_scene_leaves_it_alone(self):
        self.assertEqual(_start(None), 6.0)


class TheSpawnAsksForIt(unittest.TestCase):

    def test_bee_spawn_starts_where_it_is_clear(self):
        spawn = _function("beeSpawn", "06-fly.js")
        self.assertIn("clearOfCrowns(", spawn)


if __name__ == "__main__":
    unittest.main()
