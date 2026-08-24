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
_SCENE3D = os.path.join(_ROOT, "html", "scene3d")

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


def _read_all():
    """Every viewer chunk, concatenated.

    For claims that are about the VIEWER and not about a particular file — "the
    bird's beak is at negative z", "the perching bird has a real wingbeat". Both
    of those were asserted against ``07-wildlife.js`` by name and both broke
    when the creature bodies moved to ``21-critters.js`` (V2.46d), neither
    having found a defect. Which chunk holds a builder is housekeeping; where
    the beak points is the contract.
    """
    return "\n".join(
        _read(os.path.join(_SCENE3D, n))
        for n in sorted(os.listdir(_SCENE3D)) if n.endswith(".js"))


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
                              capture_output=True, text=True, timeout=60, encoding="utf-8")
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


class BirdFlightTest(unittest.TestCase):
    """A bird must actually beat its wings, in both the procedural and the baked
    path.

    It didn't, for two independently sufficient reasons, which is why fixing
    either alone would have looked like no change at all:
      1. ``animateWildlife``'s ``perch`` branch — every non-hummingbird bird —
         never called ``flapWings``; only the flier/hover branch did.
      2. the bird's flap amplitude was ``0.0`` in BOTH the procedural table
         (07-wildlife.js) and the GLB table (09-models.js), so a call would have
         produced a constant angle anyway.
    The wing pivots were registered correctly the whole time and fauna_bird.glb
    exports WingL/WingR — only the animation was dead. A user watching the
    preview noticed; nothing in the suite did.
    """

    def test_the_procedural_bird_has_a_real_wingbeat(self):
        # Chunk-agnostic: the builders moved to 21-critters.js at V2.46d and
        # this failed without having found a defect. The claim is about the
        # bird, not about which file draws it.
        src = _read_all()
        m = re.search(r"} else \{\s*(?://[^\n]*\n\s*)*"
                      r"g\.userData\.flap = \{([^}]*)\};\s*\n\s*"
                      r"g\.userData\.anim = 'perch';", src)
        self.assertIsNotNone(
            m, "the perching bird's flap config moved")
        amp = re.search(r"amp:\s*([0-9.]+)", m.group(1))
        self.assertIsNotNone(amp, "no amp in the bird's flap config")
        self.assertGreater(
            float(amp.group(1)), 0.1,
            "the perching bird's wingbeat amplitude is ~0 — its wings cannot "
            "move however often flapWings is called")

    def test_the_baked_bird_matches(self):
        src = _read(os.path.join(_ROOT, "html", "scene3d", "09-models.js"))
        m = re.search(r"bird:\s*\{.*?\n\s*scale:", src, re.S)
        self.assertIsNotNone(m, "09-models.js: the _GLB_CRITTER bird entry moved")
        amps = [float(a) for a in re.findall(r"amp:\s*([0-9.]+)", m.group(0))]
        self.assertTrue(amps, "no flap amplitudes in the GLB bird entry")
        self.assertGreater(
            min(amps), 0.1,
            "the baked bird has a zero-amplitude wingbeat — the GLB path "
            "repeated the procedural bug verbatim, so fixing one is not enough")

    def test_the_perch_branch_flaps(self):
        # Anchored to the 4-space indent on purpose: there are TWO
        # `else if (c.anim === 'perch')` blocks — the travel one nested inside
        # the movement branch, and this one in the per-kind height section. An
        # unanchored pattern matches the travel block and then runs on THROUGH
        # the flier branch, whose own flapWings call makes the assertion pass
        # with the perch call deleted. It did, until I checked.
        src = _read(_WILDLIFE)
        m = re.search(r"\n    \} else if \(c\.anim === 'perch'\) \{(.*?)"
                      r"\n    \} else if", src, re.S)
        self.assertIsNotNone(m, "the perch branch of animateWildlife moved")
        # Comments stripped first. The branch carries a comment EXPLAINING the
        # bug, which contains the word flapWings — so a naive substring check
        # passes with the call deleted. It did.
        code = re.sub(r"//[^\n]*", "", m.group(1))
        self.assertIn(
            "flapWings(", code,
            "the perch branch never calls flapWings, so every bird in the app "
            "sits with its wings locked in the authored rest pose")

    def test_a_travelling_bird_faces_where_it_is_going(self):
        """The perch TRAVEL branch had no heading call, unlike every other
        travel branch — a gap the V2.29 nose-first fix left behind, so birds
        crossed the yard sideways."""
        src = _read(_WILDLIFE)
        m = re.search(r"\} else if \(c\.anim === 'perch'\) \{(.*?)\n      \} else \{",
                      src, re.S)
        self.assertIsNotNone(m, "the perch travel branch moved")
        self.assertIn("critterHeading", m.group(1),
                      "a travelling bird never sets its heading")


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
        +z, the helper is silently wrong, so pin the models' own convention.

        Read across every chunk: which file holds a builder is housekeeping
        (they moved to 21-critters.js at V2.46d), and where the beak points is
        the contract."""
        src = _read_all()
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
