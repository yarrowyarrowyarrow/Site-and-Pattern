"""
tests/test_wildlife_heading.py — critters must travel nose-first (V2.29).

Every critter model in the viewer faces **-Z**: the procedural builders in
``html/scene3d/07-wildlife.js`` put the beak/nose/head at negative z and the
tail/abdomen at positive z, and the baked GLBs follow the same rule, declared
in ``scripts/blender/assetlib/fauna.py``: *"forward = +Y in Blender = -Z in the
viewer"*.

The animator got the sign wrong and oriented +Z — the TAIL — along the travel
vector, so every bee, bird, butterfly and hare in the 3D preview flew exactly
backwards. Nothing caught it: the models were right, the routes were right, the
triangle budgets were right, and a still frame looks fine. It is only wrong once
something moves, which no test was watching. A user's eye caught it.

So this evaluates the real function rather than pattern-matching the source.
``critterHeading`` is lifted out of the viewer chunk and run in Node, and the
resulting yaw is applied to the model's local forward vector with three.js'
own rotation algebra. If the heading is reversed (or mirrored, which is what the
spotlight bee separately did), the nose lands somewhere other than the direction
of travel and these fail.

Self-skips when there is no Node binary, so the ordinary suite is unaffected.
"""

import json
import math
import os
import re
import shutil
import subprocess
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_WILDLIFE = os.path.join(_ROOT, "html", "scene3d", "07-wildlife.js")

# The eight compass directions plus a few obliques, as (dx, dz) travel vectors.
_DIRECTIONS = [
    (0.0, -1.0), (1.0, 0.0), (0.0, 1.0), (-1.0, 0.0),
    (1.0, -1.0), (1.0, 1.0), (-1.0, 1.0), (-1.0, -1.0),
    (0.3, -2.7), (-4.1, 0.9), (2.2, 3.8),
]


def _node():
    return shutil.which("node") or shutil.which("nodejs")


def _read(path):
    with open(path, "r", encoding="utf-8") as fh:
        return fh.read()


@unittest.skipIf(_node() is None, "no node binary")
class CritterHeadingTest(unittest.TestCase):
    """Run the viewer's own heading function and check where the nose ends up."""

    @classmethod
    def setUpClass(cls):
        src = _read(_WILDLIFE)
        fn = re.search(r"function critterHeading\(dx, dz\) \{.*?\n\}", src, re.S)
        if not fn:
            raise AssertionError(
                "07-wildlife.js: critterHeading() is gone — the two call sites "
                "shared it so they could not drift apart; if it was inlined "
                "again, restore it or this guard is meaningless")
        script = fn.group(0) + """
const out = [];
for (const [dx, dz] of %s) {
  const th = critterHeading(dx, dz);
  // three.js: rotation.y = th maps local (x,y,z) -> (x cos + z sin, y,
  // -x sin + z cos). The model's forward is (0,0,-1).
  out.push([-Math.sin(th), -Math.cos(th)]);
}
console.log(JSON.stringify(out));
""" % json.dumps(_DIRECTIONS)
        proc = subprocess.run([_node(), "-e", script],
                              capture_output=True, text=True, timeout=60)
        if proc.returncode != 0:
            raise AssertionError(f"node failed: {proc.stderr}")
        cls.noses = json.loads(proc.stdout)

    def test_the_nose_points_the_way_the_critter_is_going(self):
        for (dx, dz), (nx, nz) in zip(_DIRECTIONS, self.noses):
            with self.subTest(travel=(dx, dz)):
                mag = math.hypot(dx, dz)
                self.assertAlmostEqual(
                    nx, dx / mag, places=6,
                    msg=f"travelling ({dx}, {dz}), the model's nose points "
                        f"({nx:.3f}, {nz:.3f}) — it is not facing where it is "
                        f"going, so the creature moves sideways or backwards")
                self.assertAlmostEqual(nz, dz / mag, places=6)

    def test_it_is_never_the_tail_leading(self):
        """The specific regression: orienting +Z instead of -Z. Stated on its
        own because it is the failure a user actually reported seeing."""
        for (dx, dz), (nx, nz) in zip(_DIRECTIONS, self.noses):
            mag = math.hypot(dx, dz)
            dot = (nx * dx + nz * dz) / mag
            self.assertGreater(
                dot, 0.99,
                f"travelling ({dx}, {dz}) the creature is flying backwards "
                f"(nose·travel = {dot:.2f}; -1 means exactly tail-first)")


class CritterHeadingWiringTest(unittest.TestCase):
    """No browser, never skipped: every heading in the wildlife animator must go
    through the shared helper. Three different formulas existed at once before
    this — the roaming critters', the spotlight bee's, and the correct one."""

    def test_no_call_site_computes_its_own_heading(self):
        src = _read(_WILDLIFE)
        body = src.replace("function critterHeading(dx, dz) {", "@@HELPER@@ {")
        stray = re.findall(r"rotation\.y\s*=\s*Math\.atan2[^;]*;", body)
        self.assertEqual(
            [], stray,
            "a critter heading is being computed inline instead of through "
            "critterHeading(); that is exactly how the roaming critters and the "
            "spotlight bee ended up with two different wrong formulas")

    def test_the_model_forward_axis_is_still_negative_z(self):
        """critterHeading encodes -Z forward. If a builder ever moves a beak to
        +z, the helper is silently wrong, so pin the models' own convention."""
        src = _read(_WILDLIFE)
        for part in ("beak", "nose"):
            m = re.search(part + r"\.position\.set\(([^)]*)\)", src)
            self.assertIsNotNone(m, f"{part}.position.set not found")
            z = m.group(1).split(",")[2]
            self.assertIn(
                "-", z,
                f"{part} is no longer at negative z — the models' forward axis "
                f"changed, so critterHeading()'s sign is now wrong")
        gen = _read(os.path.join(_ROOT, "scripts", "blender", "assetlib",
                                 "fauna.py"))
        self.assertIn(
            "-Z in the viewer", gen,
            "assetlib/fauna.py no longer declares the baked models' forward "
            "axis; the viewer's heading math depends on it")


if __name__ == "__main__":
    unittest.main()
