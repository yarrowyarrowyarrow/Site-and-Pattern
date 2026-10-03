"""
tests/test_boundary_press.py — the boundary can be pressed to change it (V3.11).

The owner: "The boundary work seems to have regressed? I want to be able to
press the boundary to change it." It had. The plants are drawn on one canvas
the size of the whole map (``canvasRenderer``, 04-tools.js), in the pane above
the boundary's (``boundaryPane``, V2.37), so from the first plant on every
click, right-click and drag on the boundary reached the canvas, which found no
plant and handed it to the map. With no plants the boundary still worked, which
is why it read as a regression. And even then, letting go of a dragged corner
ended the edit, so a boundary was reshaped one corner per click.

Since V3.11 the boundary takes no events itself and the map decides when one is
on it (``boundaryClicked`` and its neighbours in 02-boundary.js). This boots the
real map in headless Chromium with ``html/boundary_probe.html`` (the harness
``tests/test_scene3d_render.py`` uses) and presses it with mouse events sent to
whatever is under each point, so a layer drawn over another catches them as it
would a hand. Run against V3.10 it fails eight of the fifteen browser checks
below and all three source guards (see the V3.11 plan).

Every host but the local server is unresolvable for the run: the map asks the
tile servers for its basemap, and the suite stays offline (tests/__init__.py).
Self-skips with no Chromium. The source guards at the bottom need neither.
"""

import json
import os
import pathlib
import re
import subprocess
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from tests.test_scene3d_render import _find_chromium, _Server  # noqa: E402

_MAP = pathlib.Path(__file__).resolve().parent.parent / "html" / "map"


def _run_probe():
    chrome = _find_chromium()
    try:
        server = _Server()
    except OSError as exc:                              # no loopback port
        raise unittest.SkipTest(f"cannot bind a local port: {exc}")
    try:
        url = f"http://127.0.0.1:{server.port}/boundary_probe.html"
        proc = subprocess.run(
            [chrome, "--headless", "--no-sandbox",
             "--host-resolver-rules=MAP * ~NOTFOUND , EXCLUDE 127.0.0.1",
             "--window-size=1000,800", "--virtual-time-budget=20000",
             "--dump-dom", url],
            capture_output=True, text=True, timeout=240, encoding="utf-8")
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise unittest.SkipTest(f"Chromium would not run headlessly: {exc}")
    finally:
        server.stop()
    match = re.search(r"MEASURED (\{.*?\})</title>", proc.stdout, re.S)
    if not match:
        raise unittest.SkipTest(
            f"the probe never reported (chromium exit {proc.returncode})")
    return json.loads(match.group(1))


@unittest.skipIf(_find_chromium() is None,
                 "no Chromium binary (set CHROME= to run this gate)")
class PressingTheBoundary(unittest.TestCase):
    m = None

    @classmethod
    def setUpClass(cls):
        cls.m = _run_probe()

    def setUp(self):
        self.assertNotIn("error", self.m, self.m.get("error"))

    def test_the_canvas_does_cover_the_boundary(self):
        """The condition the rest is about: with a plant placed, what is under
        open ground inside the yard is the plants' canvas, not the boundary."""
        self.assertEqual(self.m["canvas_over_ground"], "CANVAS")

    def test_a_press_inside_opens_the_handles(self):
        self.assertEqual(self.m["no_plants"]["edit"], "b1")
        self.assertEqual(self.m["press"]["edit"], "b1",
                         "with a plant on the map the boundary cannot be pressed")
        self.assertEqual(self.m["press"]["handles"], 5, "one handle per corner")

    def test_a_press_on_or_beside_the_line_opens_them(self):
        self.assertEqual(self.m["press_line"]["edit"], "b1")
        self.assertEqual(self.m["press_near_line"]["edit"], "b1",
                         "a press 3 px outside the line misses it")

    def test_a_press_outside_closes_them(self):
        self.assertIsNone(self.m["press_outside"]["edit"])

    def test_what_is_drawn_on_top_keeps_its_own_press(self):
        """The boundary is the ground: a plant, a shape or a structure inside
        it is pressed for itself."""
        self.assertIsNone(self.m["press_plant"]["edit"])
        self.assertEqual(self.m["press_plant"]["plant_clicks"], 1)
        self.assertIsNone(self.m["press_shed"]["edit"])
        self.assertEqual(self.m["press_shed"]["shape_edit"], "s1")
        self.assertIsNone(self.m["press_pond"]["edit"],
                          "a structure's left click is read as the boundary's")

    def test_shift_press_selects_it(self):
        self.assertEqual(self.m["shift_press"]["selected"], 1)
        self.assertIsNone(self.m["shift_press"]["edit"])

    def test_right_click_opens_its_menu(self):
        self.assertTrue(self.m["right_click"]["menu"], "no menu on right-click")
        self.assertTrue(self.m["right_click"]["remove"])

    def test_a_drag_in_the_middle_moves_it_once(self):
        d = self.m["drag_middle"]
        self.assertAlmostEqual(d["moved_px"], 40, delta=2)
        self.assertEqual(d["sent"], 1, "Python was not told, or told twice")
        self.assertEqual(d["edit"], "b1")

    def test_a_press_that_does_not_move_says_nothing(self):
        d = self.m["press_still"]
        self.assertEqual((d["moved_px"], d["sent"]), (0, 0))
        self.assertEqual(d["edit"], "b1", "pressing the edited boundary ended the edit")

    def test_a_drag_on_a_plant_leaves_the_boundary(self):
        self.assertEqual(self.m["drag_plant"], {"moved_px": 0, "sent": 0})

    def test_the_edit_carries_on_after_a_corner(self):
        d = self.m["drag_corner"]
        self.assertAlmostEqual(d["moved_px"], 32, delta=2, msg="the corner did not follow")
        self.assertEqual(d["edit"], "b1", "letting go of a corner ended the edit")
        self.assertEqual(d["handles"], 5)

    def test_while_placing_a_press_places_once(self):
        self.assertEqual(self.m["placing"], {"placed": 1, "edit": None})

    def test_the_pin_drop_click_is_for_the_pin(self):
        self.assertEqual(self.m["pin_drop"], {"map_clicks": 1, "edit": None})

    def test_a_hidden_boundary_cannot_be_pressed(self):
        self.assertIsNone(self.m["hidden"]["edit"])

    def test_the_pointer_says_it_can_be_pressed(self):
        self.assertEqual(self.m["hover"], {"over": True, "outside": False})


class TheBoundaryIsNotItsOwnClickTarget(unittest.TestCase):
    """Source guards, never skipped: an interactive polygon in the low pane is
    unreachable under the plants' canvas, and its own handlers would be a
    second path to the same behaviour that only runs while there are no
    plants."""

    @classmethod
    def setUpClass(cls):
        cls.boundary = (_MAP / "02-boundary.js").read_text(encoding="utf-8")
        cls.core = (_MAP / "01-core.js").read_text(encoding="utf-8")

    def test_the_polygon_takes_no_events(self):
        poly = re.search(r"L\.polygon\(pts,\s*\{.*?\}\)", self.boundary, re.S)
        self.assertIsNotNone(poly)
        self.assertIn("interactive: false", poly.group(0))
        self.assertNotRegex(self.boundary, r"layer\.on\('(click|contextmenu|mousedown)'")
        self.assertNotIn("b.layer.on(", self.boundary)

    def test_the_map_routes_to_it(self):
        for call in ("boundaryClicked(e)", "boundaryContextMenu(e)",
                     "map.on('mousedown', boundaryPressed)", "boundaryHover(e)"):
            self.assertIn(call, self.core, f"01-core.js no longer calls {call}")

    def test_its_handles_are_marked_as_its_own(self):
        self.assertEqual(self.boundary.count("className: 'sp-boundary-handle'"), 2,
                         "a corner or scale handle is not marked, so letting go "
                         "of it ends the edit")


if __name__ == "__main__":
    unittest.main()
