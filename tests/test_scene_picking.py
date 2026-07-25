"""
tests/test_scene_picking.py — the click-to-learn pick contract (V2.30).

Three things went wrong at once, and the user experienced them as one symptom:
"sometimes I press a plant and the plant does not select".

1. **There was no hit tolerance anywhere.** A single exact ray against
   alpha-tested leaf ribbons means a small herb is a few tens of pixels of
   hittable geometry at orbit distance. This is the one that mattered: measured
   over a fixed 588-point grid in ``html/inspect_probe.html?sweep=1``, the hit
   rate went from **18/588 to 66/588** when the sample spiral was added.
2. **The flower heads were not pickable.** Pick data was attached in five
   places, all plant-BODY layers; the instanced flower quads carried none.
   Worth stating honestly: on that same grid this changed the hit rate **not at
   all**, because a bloom sits above a body that was already pickable and
   resolves to the same plant. It matters for blooms held clear of their own
   foliage — a nodding onion or blazingstar scape — not for the general case,
   and it was not "the biggest cause" as first assumed.
3. **Two raycasters had drifted apart.** The hover tip filtered on
   ``userData.pick`` and the inspect card on ``userData.pickId``, so a mesh could
   name itself on hover and refuse to open a card.

Plus: inspecting was disabled outright while flying as a bee, which is where a
user is closest to the plants and most likely to ask what one is.

These are source-level invariants rather than a render test on purpose — the
failure is "no data attached" and "the guard clause is still there", both of
which are exactly readable in the source and none of which a screenshot shows.
"""

import os
import re
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_SCENE3D = os.path.join(_ROOT, "html", "scene3d")


def _read(name):
    with open(os.path.join(_SCENE3D, name), encoding="utf-8") as fh:
        return fh.read()


def _strip_comments(src):
    """Line comments removed. A block that documents a bug tends to contain the
    very identifier the assertion looks for."""
    return re.sub(r"//[^\n]*", "", src)


class FlowerPickabilityTest(unittest.TestCase):
    def test_flower_heads_carry_pick_data(self):
        src = _strip_comments(_read("05-flowers.js"))
        self.assertRegex(
            src, r"mesh\.userData\.pick\s*=",
            "the instanced flower quads carry no `pick` names — a bloom is the "
            "biggest target a wildflower has and clicking it would do nothing")
        self.assertRegex(
            src, r"mesh\.userData\.pickId\s*=",
            "the flower quads carry no `pickId`, so a bloom can be named on "
            "hover but cannot open its card")

    def test_the_pick_arrays_are_filled_per_bloom(self):
        """Attaching empty arrays would satisfy the check above and still not
        work, so pin that the loop actually pushes one entry per bloom."""
        src = _strip_comments(_read("05-flowers.js"))
        self.assertRegex(src, r"names\.push\(", "names never filled")
        self.assertRegex(src, r"ids\.push\(", "ids never filled")


class ScenePickTest(unittest.TestCase):
    def test_there_is_one_shared_pick(self):
        core = _read("01-core.js")
        self.assertRegex(
            core, r"function scenePick\(",
            "01-core.js no longer defines the shared scenePick — the hover tip "
            "and the inspect card must not go back to separate raycasters")
        inspect = _strip_comments(_read("10-inspect.js"))
        self.assertNotIn(
            "new THREE.Raycaster()", inspect,
            "10-inspect.js has its own raycaster again; the two drifted apart "
            "once already, with different mesh filters")
        self.assertIn("scenePick(", inspect,
                      "the inspect card is not using the shared pick")

    def test_the_pick_accepts_both_body_and_flower_meshes(self):
        """The filter must admit anything carrying EITHER key. Filtering on
        pickId alone (what the card used to do) silently excludes meshes that
        only name themselves, and vice versa."""
        core = _strip_comments(_read("01-core.js"))
        m = re.search(r"function scenePick\(.*?\n\}", core, re.S)
        self.assertIsNotNone(m, "scenePick moved")
        self.assertRegex(
            m.group(0),
            r"o\.userData\.pick\s*\|\|\s*o\.userData\.pickId",
            "scenePick filters on only one of pick/pickId, so half the "
            "pickable meshes in the scene are invisible to it")

    def test_the_pick_samples_more_than_one_ray(self):
        core = _strip_comments(_read("01-core.js"))
        self.assertRegex(
            core, r"_PICK_OFFSETS",
            "the tolerance spiral is gone — a single exact ray makes small "
            "herbs and groundcover effectively unclickable at orbit distance")
        m = re.search(r"_PICK_RINGS\s*=\s*\[([^\]]*)\]", core)
        self.assertIsNotNone(m, "_PICK_RINGS moved")
        rings = [float(x) for x in m.group(1).split(",")]
        self.assertEqual(rings[0], 0,
                         "the centre ray must be sampled FIRST, so an exact "
                         "hit always beats a tolerated neighbour")
        self.assertLess(max(rings), 30,
                        "the tolerance radius is large enough to select a "
                        "plant the user is not pointing at")


class FirstPersonInspectTest(unittest.TestCase):
    """The card must work while flying and walking.

    It was gated off in bee mode on the belief that a click there was a flight
    control. It is not — flight is WASD and the mouse only turns the camera —
    so the existing "did the pointer travel?" test already separates a click
    from a look-around, in every mode.
    """

    def test_inspect_is_not_gated_on_a_mode(self):
        src = _strip_comments(_read("10-inspect.js"))
        m = re.search(r"addEventListener\('pointerup'.*?\n\}\);", src, re.S)
        self.assertIsNotNone(m, "the pointerup inspect handler moved")
        body = m.group(0)
        for mode in ("beeMode", "walkMode", "cinematic"):
            self.assertNotRegex(
                body, r"if\s*\(\s*" + mode + r"\s*\)\s*return",
                f"inspecting is disabled while {mode} is active — the "
                f"educational card is missing exactly where the user is "
                f"closest to the plants")

    def test_a_drag_still_does_not_inspect(self):
        """The travel gate is what makes mode-free inspecting safe; without it,
        every camera drag ending on a plant would open a card."""
        src = _strip_comments(_read("10-inspect.js"))
        m = re.search(r"addEventListener\('pointerup'.*?\n\}\);", src, re.S)
        self.assertRegex(
            m.group(0), r"Math\.abs\(e\.clientX - _downX\)\s*>",
            "the drag gate is gone")

    def test_a_miss_does_not_close_an_open_card(self):
        """A near miss used to call clearSelection(), shutting a card the user
        had deliberately opened. With tolerance added, an unresolvable hit is
        far more likely to be a mis-aim than an intent to dismiss."""
        src = _strip_comments(_read("10-inspect.js"))
        m = re.search(r"addEventListener\('pointerup'.*?\n\}\);", src, re.S)
        self.assertNotRegex(
            m.group(0), r"if\s*\(!entry\)\s*\{\s*clearSelection\(\);",
            "a hit with no dossier entry still closes the open card")

    def test_both_first_person_modes_advertise_it(self):
        walk = _read("08-modes.js")
        fly = _read("06-fly.js")
        self.assertIn("click a plant", walk,
                      "the walk hint never mentions click-to-learn, so it "
                      "stays undiscoverable even though it works")
        self.assertIn("click a plant", fly,
                      "the bee controls line never mentions click-to-learn")


if __name__ == "__main__":
    unittest.main()
