"""
tests/test_slope_render.py — the 3D preview on a sloped site (V3.04).

The owner sent two screenshots of the 3D preview of a sloped yard: the yard was
a raised patch with the sky showing under its edge as a white band, and the
trees' shadows lay on flat ground below and in front of them. Every plant stood
on ``terrainHeightAt`` (html/scene3d/02-plants.js), which follows the slope and
holds the grid's edge heights outside it. The things that *lie* on the ground
did not ask it:

- the ground was the terrain's own patch, the size of the boundary's bounding
  box, over a flat apron at the site's lowest point, so the patch's edges stood
  up to their whole relief above the apron and a plant outside the boundary
  stood on air;
- the contact shadows were drawn at a fixed 3 cm, the boundary line at 12 cm,
  buildings and fallback structure boxes from 0, the planting animation at 0;
- a click hit a flat plane at 0, which on a slope lies under nearly all of the
  yard, so a plant landed metres beyond the cursor;
- the orbit camera's floor was the plane through its pivot, which sat at 0, so
  an orbit turned low went into the hill on the uphill side, where the
  one-sided ground vanishes and the sky shows through.

This boots the real viewer in headless Chromium with ``html/slope_probe.html``
(the harness ``tests/test_scene3d_render.py`` uses), pushes a slope with 6 m of
relief, and asks each of those whether it agrees with ``terrainHeightAt``. Run
against V3.03 it fails on all of them (see the V3.04 plan for the numbers).

Self-skips with no Chromium or no WebGL. The source guards at the bottom need
neither and are never skipped.
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

_JS = pathlib.Path(__file__).resolve().parent.parent / "html" / "scene3d"


def _run_probe():
    chrome = _find_chromium()
    try:
        server = _Server()
    except OSError as exc:                              # no loopback port
        raise unittest.SkipTest(f"cannot bind a local port: {exc}")
    try:
        url = f"http://127.0.0.1:{server.port}/slope_probe.html"
        proc = subprocess.run(
            [chrome, "--headless", "--no-sandbox", "--disable-gpu-sandbox",
             "--enable-unsafe-swiftshader", "--use-angle=swiftshader",
             "--virtual-time-budget=30000", "--dump-dom", url],
            capture_output=True, text=True, timeout=240, encoding="utf-8")
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise unittest.SkipTest(f"Chromium would not run headlessly: {exc}")
    finally:
        server.stop()
    match = re.search(r"MEASURED (\{.*?\})</title>", proc.stdout, re.S)
    if not match:
        raise unittest.SkipTest(
            "the probe never reported — no WebGL in this environment "
            f"(chromium exit {proc.returncode})")
    return json.loads(match.group(1))


@unittest.skipIf(_find_chromium() is None,
                 "no Chromium binary (set CHROME= to run this gate)")
class TheGroundOnASlope(unittest.TestCase):
    m = None

    @classmethod
    def setUpClass(cls):
        cls.m = _run_probe()

    def test_the_ground_is_where_things_stand(self):
        """One ground, at terrainHeightAt everywhere: on the grid, just past its
        edges, under a tree well outside it, and out past the scene's bounds."""
        g = self.m["ground"]
        self.assertEqual(g["misses"], 0, f"no ground under {g['misses']} points")
        self.assertLessEqual(
            g["worst_m"], 0.05,
            f"the ground is {g['worst_m']} m from where things stand at "
            f"(x, y, ground, stand) = {g['worst_at']}: a step or a gap in it")

    def test_the_ground_reaches_the_fog(self):
        """An edge of the world is the white band again, seen from further off."""
        self.assertTrue(self.m["ground"]["reaches_fog"],
                        "the ground ends short of the fog in some direction")

    def test_contact_shadows_lie_on_the_slope(self):
        s = self.m["shadows"]
        self.assertGreaterEqual(s["count"], 4, "a tree or the tall shrub lost its shadow")
        self.assertLessEqual(s["worst_m"], 0.01,
                             f"a contact shadow is {s['worst_m']} m off the ground")
        self.assertGreaterEqual(
            s["worst_dot"], 0.9999,
            "a contact shadow is not tilted with the slope, so one side cuts "
            "into the hill and the other hangs over it")

    def test_the_boundary_is_draped_over_the_ground(self):
        b = self.m["boundary"]
        self.assertGreater(b["vertices"], 4 * 18,
                           "the boundary's 18 m edges are not cut into steps")
        self.assertLessEqual(b["worst_vertex_m"], 0.01)
        self.assertLessEqual(
            b["worst_midpoint_m"], 0.05,
            f"between its points the boundary is {b['worst_midpoint_m']} m off "
            f"the ground: it cuts through the slope")

    def test_a_building_stands_on_its_lowest_ground(self):
        b = self.m["building"]
        self.assertAlmostEqual(b["base_m"], b["low_ground_m"], delta=0.01,
                               msg="a building hangs in the air or sinks on a slope")
        self.assertAlmostEqual(b["top_m"], b["high_ground_m"] + b["height_m"],
                               delta=0.01, msg="a building is buried on its uphill side")

    def test_a_structure_box_stands_on_the_ground(self):
        s = self.m["structure"]
        self.assertAlmostEqual(s["foot_m"], s["ground_m"], delta=0.01)

    def test_the_planting_animation_starts_on_the_ground(self):
        a = self.m["plant_anim"]
        self.assertIsNotNone(a["y_m"], "animatePlant added nothing to the scene")
        self.assertAlmostEqual(a["y_m"], a["ground_m"], delta=0.01)

    def test_a_click_lands_under_the_cursor(self):
        c = self.m["click"]
        self.assertEqual(c["missed"], 0, "a click on the ground found no ground")
        self.assertLessEqual(
            c["worst_m"], 0.05,
            f"a click landed {c['worst_m']} m from the ground under the cursor")
        # The scenario has to be one where the old answer was wrong, or this
        # test would pass against the bug it exists for.
        flat = [p[4] for p in c["points"] if p[4] is not None]
        self.assertTrue(flat and min(flat) > 0.5,
                        f"the probe's slope no longer exercises the flat-plane bug: {flat}")

    def test_the_orbit_pivot_moves_onto_the_ground_when_terrain_arrives(self):
        o = self.m["orbit"]
        self.assertAlmostEqual(
            o["pivot_m"], o["ground_m"], delta=0.01,
            msg="the orbit still turns about the site's lowest point, under the hill")
        self.assertTrue(o["view_kept"], "the camera was not carried with the pivot")

    def test_the_orbit_camera_stays_out_of_the_hill(self):
        """Through the render loop where the browser draws frames; headless
        Chromium stops a few seconds in, and then the probe calls what the loop
        calls (TheSourceAsksTheGround checks the loop calls it)."""
        c = self.m["camera"]
        self.assertGreaterEqual(
            c["y_m"], c["ground_m"] + 0.45,
            f"the camera is at {c['y_m']} m over ground at {c['ground_m']} m: "
            f"inside the hill, where the sky shows through the ground")


def _fn(path: str, name: str) -> str:
    src = (_JS / path).read_text(encoding="utf-8")
    start = src.index(f"function {name}(")
    return src[start:src.index("\n}", start)]


class TheSourceAsksTheGround(unittest.TestCase):
    """What the render gate checks, at the source, for a machine without a
    browser. Each names the one function it is about."""

    def test_the_ground_is_built_from_terrain_height(self):
        body = _fn("02-plants.js", "buildGround")
        self.assertIn("terrainHeightAt(", body)
        self.assertNotIn("apron", body, "a separate flat apron is back")

    def test_the_contact_shadows_lie_on_the_ground(self):
        src = (_JS / "04-quality.js").read_text(encoding="utf-8")
        block = src[src.index("// Contact shadows"):src.index("plantsGroup.add(sh)")]
        self.assertIn("onGround(", block)

    def test_the_boundary_and_buildings_are_given_the_terrain(self):
        src = (_JS / "05-flowers.js").read_text(encoding="utf-8")
        self.assertIn("buildBoundary(designGroup, sc.boundary, sc.terrain)", src)
        self.assertIn("buildBuildings(designGroup, sc.buildings, sc.terrain)", src)
        for name in ("buildBoundary", "buildBuildings"):
            self.assertIn("terrainHeightAt(", _fn("02-plants.js", name), name)

    def test_a_click_asks_the_ground(self):
        self.assertIn("terrainHeightAt(", _fn("16-editing.js", "groundPointAt"))

    def test_the_orbit_keeps_the_camera_above_the_ground(self):
        src = (_JS / "08-modes.js").read_text(encoding="utf-8")
        self.assertRegex(src, r"controls\.update\(\);\s*keepAboveGround\(\);")


if __name__ == "__main__":
    unittest.main()
