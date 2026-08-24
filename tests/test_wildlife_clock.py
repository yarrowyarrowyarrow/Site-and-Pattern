"""
tests/test_wildlife_clock.py — the creature clock (F121, V2.54).

The 3D preview can pause and slow its ambient wildlife so you can actually look
at a creature. The reason that is a *design* and not a one-line multiplier is
that ``animateWildlife`` runs on two clocks:

    dt          -> travel and the dwell countdown (position integration)
    absolute t  -> the WINGBEAT (flapWings), the wander wobble, the bob, the
                   look-around, the hop, boundOffset and beatGain

Scale only ``dt`` — the intuitive implementation — and you get a bird hovering
motionless in mid-air with its wings beating at full speed. So both clocks are
driven from one wildlife-local clock advanced inside ``_wildDt``, and these
tests exist to stop that coupling being quietly undone later.

Like ``test_wildlife_heading.py``, the clock is lifted out of the viewer chunk
and executed under Node rather than pattern-matched, so the assertions are about
numbers the shipped code actually produces. Self-skips with no Node binary; the
source-shape guards at the bottom run everywhere.
"""

import json
import os
import re
import shutil
import subprocess
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_WILDLIFE = os.path.join(_ROOT, "html", "scene3d", "07-wildlife.js")
_ROSTER = os.path.join(_ROOT, "html", "scene3d", "19-roster.js")

# Ten frames at a steady 60 fps, in the milliseconds setAnimationLoop hands out.
_FRAMES = [1000.0 + 16.7 * i for i in range(10)]
# The same, but the third frame lands ten seconds late — a tab that was in the
# background, or a pause the user held.
_STALLED = [1000.0, 1016.7, 11016.7]


def _node():
    return shutil.which("node") or shutil.which("nodejs")


def _read(path):
    with open(path, "r", encoding="utf-8") as fh:
        return fh.read()


@unittest.skipIf(_node() is None, "no node binary")
class WildlifeClockTest(unittest.TestCase):
    """Run the viewer's own ``_wildDt`` and check what the clock does."""

    @classmethod
    def setUpClass(cls):
        src = _read(_WILDLIFE)
        fn = re.search(
            r"let _wildPrevT = 0;.*?\nfunction _wildDt\(t\) \{.*?\n\}", src, re.S)
        if not fn:
            raise AssertionError(
                "07-wildlife.js: the creature clock (_wildPrevT / _wildClock / "
                "_wildSpeed / _wildDt) is gone or was restructured — if the "
                "pause was reimplemented, re-point this guard at it rather "
                "than deleting it; the two-clock bug it pins is not obvious")
        script = fn.group(0) + """
function run(speed, times) {
  _wildPrevT = 0; _wildClock = 0; _wildSpeed = speed;
  const out = [];
  for (const t of times) {
    const before = _wildClock;
    const dt = _wildDt(t);
    out.push({ dt: dt, clock: _wildClock, delta: _wildClock - before });
  }
  return out;
}
console.log(JSON.stringify({
  paused:  run(0,    %(frames)s),
  quarter: run(0.25, %(frames)s),
  half:    run(0.5,  %(frames)s),
  normal:  run(1,    %(frames)s),
  resumed: run(1,    %(stalled)s)
}));
""" % {"frames": json.dumps(_FRAMES), "stalled": json.dumps(_STALLED)}
        proc = subprocess.run([_node(), "-e", script],
                              capture_output=True, text=True, timeout=60, encoding="utf-8")
        if proc.returncode != 0:
            raise AssertionError(f"node failed: {proc.stderr}")
        cls.runs = json.loads(proc.stdout)

    def test_paused_really_is_still(self):
        """Speed 0 is the pause. Nothing may advance — not the travel clock and
        not the creature clock the wingbeat reads."""
        frames = self.runs["paused"]
        self.assertEqual(len(frames), len(_FRAMES))
        for i, f in enumerate(frames):
            with self.subTest(frame=i):
                self.assertEqual(f["dt"], 0.0,
                                 "paused, but dt is non-zero — creatures would "
                                 "still be travelling")
        self.assertEqual(frames[-1]["clock"], 0.0,
                         "paused, but the creature clock advanced — the wings "
                         "would keep beating while the body held still, which "
                         "is the exact bug this design exists to prevent")

    def test_slow_motion_is_proportional(self):
        """A quarter speed advances the clock a quarter as far over identical
        frame timestamps — no drift, no rounding-in."""
        normal = self.runs["normal"][-1]["clock"]
        self.assertGreater(normal, 0)
        for name, mult in (("quarter", 0.25), ("half", 0.5)):
            with self.subTest(speed=name):
                self.assertAlmostEqual(
                    self.runs[name][-1]["clock"], normal * mult, places=9,
                    msg=f"{name} speed did not advance the creature clock "
                        f"{mult}x as far as normal speed did")

    def test_the_two_clocks_stay_in_lockstep(self):
        """The regression the whole design is shaped around: dt (travel) and the
        creature clock (wingbeat) must scale together at every speed. If these
        ever disagree, a bird stops flying and keeps flapping."""
        for name, frames in self.runs.items():
            for i, f in enumerate(frames):
                with self.subTest(speed=name, frame=i):
                    self.assertAlmostEqual(
                        f["delta"], f["dt"] * 1000.0, places=9,
                        msg=f"{name}: travel advanced {f['dt'] * 1000:.4f} ms "
                            f"but the wingbeat clock advanced {f['delta']:.4f} "
                            f"ms — they have come uncoupled")

    def test_resuming_cannot_teleport_a_creature(self):
        """However long the pause, the first frame after it advances at most the
        50 ms any other stall would. This is the pre-existing clamp; the test is
        here because the pause is what makes long gaps ordinary."""
        late = self.runs["resumed"][-1]
        self.assertLessEqual(
            late["delta"], 50.0 + 1e-9,
            f"a 10-second gap advanced the creature clock {late['delta']:.1f} "
            f"ms — creatures would jump across the yard on resume")
        self.assertLessEqual(late["dt"], 0.05 + 1e-9)


class WildlifeClockSourceTest(unittest.TestCase):
    """Shape guards that run without Node, because the coupling is easy to undo
    by accident and the symptom shows up only on screen."""

    def test_animate_wildlife_reads_the_creature_clock(self):
        src = _read(_WILDLIFE)
        body = re.search(r"function animateWildlife\((\w+)\)", src)
        self.assertIsNotNone(body, "animateWildlife is gone")
        self.assertNotEqual(
            body.group(1), "t",
            "animateWildlife's parameter is named `t` again — every motion "
            "expression in its body reads `t`, so naming the RAW frame time "
            "`t` silently reconnects the wingbeat to the unscaled clock and "
            "the pause stops working for everything except travel")
        self.assertRegex(
            src, r"const t = _wildClock;",
            "animateWildlife no longer binds `t` to the creature clock — the "
            "wingbeat, bob, wobble and hop are back on real time")

    def test_the_clock_advances_before_the_visibility_check(self):
        """19-roster.js's spotlight creature reads the same clock and can be on
        screen while wildlifeGroup is hidden. If the early return comes first,
        its wings freeze in a mode where nothing is paused."""
        src = _read(_WILDLIFE)
        fn = re.search(r"function animateWildlife\(\w+\) \{(.*?)\n  for ",
                       src, re.S)
        self.assertIsNotNone(fn)
        head = fn.group(1)
        self.assertLess(
            head.index("_wildDt("), head.index("wildlifeGroup.visible"),
            "animateWildlife checks visibility before advancing the clock — "
            "the spotlight creature's wingbeat stalls whenever the ambient "
            "wildlife is hidden")

    def test_the_spotlight_creature_obeys_the_speed(self):
        src = _read(_ROSTER)
        self.assertIn(
            "wildlifeSpeed()", src,
            "19-roster.js's spotlight creature no longer scales by the wildlife "
            "speed — the one creature the user deliberately asked to look at "
            "would be the only one that will not hold still")
        self.assertIn(
            "_wildClock", src,
            "the spotlight creature's wingbeat is back on raw frame time, so "
            "pausing stops its body and not its wings")

    def test_pause_does_not_steal_the_bees_ascend_key(self):
        """Space is bound to 'ascend' by _BEE_MOVE_CODES in 06-fly.js. The pause
        shortcut has to stand down in first-person modes or it breaks flying."""
        src = _read(_WILDLIFE)
        handler = re.search(r"addEventListener\('keydown'.*?\n\}\);", src, re.S)
        self.assertIsNotNone(handler, "the pause shortcut is gone")
        block = handler.group(0)
        self.assertIn("'Space'", block)
        self.assertIn("beeMode", block,
                      "the Space handler does not stand down in bee mode — it "
                      "steals the ascend key")
        self.assertIn("walkMode", block,
                      "the Space handler does not stand down in walk mode")

    def test_the_chip_drives_no_python_bridge_hook(self):
        """The speed control is deliberately JS-only: no window.perma* hook, so
        tests/test_bridge_contract.py's registered-but-undriven guard never has
        to carry an exemption for it, and the Qt toolbar gains no button."""
        src = _read(_WILDLIFE)
        self.assertNotRegex(
            src, r"window\.permaSetWildlifeSpeed\s*=",
            "the speed control registered a bridge hook. If Python genuinely "
            "needs to drive it, that is fine — but it must then be driven from "
            "src/map3d_js.py, or test_bridge_contract will fail")


if __name__ == "__main__":
    unittest.main()
