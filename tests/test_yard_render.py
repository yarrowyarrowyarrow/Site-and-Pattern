"""
tests/test_yard_render.py — the whole-yard gate (V3.43).

Six audits of the 3D preview rendered one plant at a time. For years nobody
rendered a yard, and the faults of the whole picture went unseen while every
part-level guard stayed green: every house a see-through green box, the camera
framing a 50 m stage with the yard about 1% of it, Walk the garden starting
inside the house, the "sidewalk" view of the PDF's before/after page 22 m
outside the lot behind a trunk, fruit 17 cm across, a plant the timeline had
lost drawn as a pale ghost, and "Year 0 · 367 plants · 4 structure
footprint(s)" over a design fully grown with a third of those plants dead.

So this builds a yard through the real ``build_scene`` (a house, a drawn tree
crown, a boulevard tree, plants that the timeline shades out and lives out),
pushes it into the real viewer in headless Chromium, and reads the whole picture
back (``html/yard_probe.html``). Against V3.42's viewer 12 of the 18 checks
fail, which is how the gate was shown to see the faults it is for::

    YARD_VIEWER_ROOT=<a V3.42 checkout>/html python -m unittest tests.test_yard_render

Skips with no Chromium binary or no WebGL, as the other render gates do; a
viewer that THROWS fails (``fail_on_viewer_errors``, V3.37).
"""

import copy
import json
import math
import os
import re
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "scripts"))

import render_yard                                            # noqa: E402
from src.project_store import plant_feature                   # noqa: E402
from src.scene_contract import build_scene, standing_plants   # noqa: E402
from tests.test_scene3d_render import fail_on_viewer_errors   # noqa: E402
from tests.test_scene_contract import _FAKE_PLANTS            # noqa: E402

_LAT, _LNG = 53.5, -113.5
_KY = 111320.0
_KX = 111320.0 * math.cos(math.radians(_LAT))

#: One forb with an id of its own, so the probe can find the plant this test
#: marks as declining.
_PLANTS = dict(_FAKE_PLANTS)
_PLANTS[12] = {"plant_type": "wildflower", "years_to_maturity": 2,
               "growth_curve": "steady", "mature_height_meters": 0.9,
               "mature_canopy_m": 0.6, "common_name": "Marked forb"}
DECLINING = 12
YEAR = 25


def _ll(x, y):
    return [_LNG + x / _KX, _LAT + y / _KY]


def _ring(x0, y0, x1, y1):
    r = [_ll(x, y) for x, y in ((x0, y0), (x1, y0), (x1, y1), (x0, y1))]
    return r + [r[0]]


def _plant(pid, name, x, y):
    lng, lat = _ll(x, y)
    return plant_feature({"plant_id": pid, "common_name": name,
                          "lat": lat, "lng": lng})


def _yard() -> dict:
    """A 15 x 37 m lot, street to the south, as a scan and a plan leave it."""
    feats = [
        {"type": "Feature",
         "geometry": {"type": "Polygon",
                      "coordinates": [_ring(-7.6, -18.3, 7.6, 18.3)]},
         "properties": {"element_type": "property_boundary"}},
        # The house, as Scan this area stores it: a canopy_footprint.
        {"type": "Feature",
         "geometry": {"type": "Polygon",
                      "coordinates": [_ring(-5.4, -9.3, 5.4, 2.7)]},
         "properties": {"element_type": "canopy_footprint", "height_m": 6.5,
                        "shape_type": "Building (OSM)", "cast_shade": True,
                        "source": "osm", "lat": _LAT, "lng": _LNG,
                        "canopy_radius_m": 6.0}},
        # A tree's crown drawn by hand, behind the house.
        {"type": "Feature",
         "geometry": {"type": "Polygon",
                      "coordinates": [_ring(2.0, 12.0, 6.0, 16.0)]},
         "properties": {"element_type": "canopy_footprint", "height_m": 8.0,
                        "shape_type": "Tree canopy", "caster_kind": "tree",
                        "cast_shade": True}},
        # The boulevard tree, between the sidewalk and the yard.
        {"type": "Feature",
         "geometry": {"type": "Point", "coordinates": _ll(-3.6, -20.8)},
         "properties": {"element_type": "existing_tree", "height_m": 14.0,
                        "canopy_radius_m": 5.5, "tree_foliage": "deciduous",
                        "label": "Tree"}},
        _plant(7, "Aspen", -3.0, -13.0),
        _plant(6, "Saskatoon", 4.5, -15.0),
        _plant(DECLINING, "Marked forb", 5.5, -12.0),
    ]
    for i in range(8):                    # full-sun forbs under the aspen
        feats.append(_plant(8, "Sun forb", -4.5 + (i % 4) * 0.8,
                            -14.0 + (i // 4) * 1.6))
    for i in range(30):                   # a short-lived kind, in the back
        feats.append(_plant(10, "Short-lived forb", -6.0 + (i % 6) * 0.9,
                            7.0 + (i // 6) * 0.9))
    return {"type": "FeatureCollection",
            "properties": {"site_config": {}}, "features": feats}


def _scenes():
    from datetime import datetime
    when = datetime(2025, 7, 21, 13, 0)
    scene = build_scene(_yard(), year=YEAR, get_plant=_PLANTS.get, wind=False,
                        when=when)
    for p in scene["plants"]:
        if p.get("plant_id") == DECLINING:
            # Marked by hand: the one thing here build_scene did not decide.
            p.update(health=0.3, health_state="declining", opacity=0.65)
    # What any scene made before V3.43 looks like to the viewer: no focus, no
    # views. Another origin, so the viewer frames it afresh.
    legacy = copy.deepcopy(build_scene(_yard(), year=0, get_plant=_PLANTS.get,
                                       wind=False, when=when))
    legacy["focus"], legacy["views"] = None, {}
    legacy["origin"]["lat"] += 0.01
    return scene, legacy


@unittest.skipIf(render_yard.find_chromium() is None,
                 "no Chromium binary (set CHROME= to run this gate)")
class TheWholeYard(unittest.TestCase):
    got = None
    scene = None

    @classmethod
    def setUpClass(cls):
        cls.scene, legacy = _scenes()
        job = {"scene": cls.scene, "legacy": legacy, "declining_id": DECLINING,
               "walk_points": [["side_yard", -6.6, -3.0],
                               ["in_the_house", 0.5, -3.0]]}
        try:
            server = render_yard.Server(
                {"/__yard/job.json": job},
                viewer_root=os.environ.get("YARD_VIEWER_ROOT", render_yard.HTML))
        except OSError as exc:
            raise unittest.SkipTest(f"cannot bind a local port: {exc}")
        try:
            dom = render_yard.run_probe(
                server.url("yard_probe.html?job=/__yard/job.json"),
                timeout=420)
        except (OSError, RuntimeError, Exception) as exc:    # noqa: BLE001
            server.stop()
            raise unittest.SkipTest(f"Chromium would not run headlessly: {exc}")
        server.stop()
        fail_on_viewer_errors(dom)
        match = re.search(r"<title>MEASURED (\{.*\})</title>", dom, re.S)
        if not match:
            raise unittest.SkipTest("the probe never reported: no WebGL in "
                                    "this environment")
        import html as _html
        cls.got = json.loads(_html.unescape(match.group(1)))

    # ── the scene is the one the gate needs ──────────────────────────────────

    def test_the_fixture_still_has_every_case_in_it(self):
        """Loud if the growth or succession models move the fixture out from
        under the assertions below."""
        plants = self.scene["plants"]
        kinds = {b["kind"] for b in self.scene["buildings"]}
        self.assertEqual(kinds, {"building", "canopy"})
        self.assertTrue(any(p.get("gone") == "shade" for p in plants))
        self.assertTrue(any(p.get("gone") == "short_lived" for p in plants))
        self.assertTrue(any(p["plant_id"] == 10 for p in
                            standing_plants(self.scene)))
        self.assertTrue(self.scene["views"]["street"])

    # ── buildings ────────────────────────────────────────────────────────────

    def test_a_house_is_solid_and_a_drawn_crown_is_not(self):
        house, crown = self.got["meshes"]["buildings"], self.got["meshes"]["canopys"]
        self.assertFalse(house["see_through"], "the house is see-through: "
                         "V3.42 drew every scanned building as a green canopy")
        self.assertTrue(crown["see_through"])
        self.assertNotEqual(house["colour"], crown["colour"])

    # ── the camera ───────────────────────────────────────────────────────────

    def test_the_window_opens_on_the_yard(self):
        yard = self.got["opening"]["yard"]
        self.assertTrue(yard["inside"], f"part of the yard is out of frame: {yard}")
        self.assertGreater(yard["tall"], 0.45,
                           f"the yard is a small part of the picture: {yard}")
        self.assertGreater(yard["wide"], 0.30, yard)

    def test_a_scene_with_no_focus_frames_the_stage_as_before(self):
        """The probe pages and any scene saved before V3.43 carry no focus."""
        b = self.scene["bounds"]
        r = max(b["max_x"] - b["min_x"], b["max_y"] - b["min_y"]) * 0.75
        far = r * math.sqrt(0.9 ** 2 + 0.85 ** 2 + 1.1 ** 2)   # frameCamera's
        self.assertAlmostEqual(self.got["legacy"]["camera"]["far"], far,
                               delta=0.5)
        self.assertGreater(self.got["legacy"]["camera"]["far"],
                           self.got["opening"]["camera"]["far"] * 1.15)

    def test_leaving_walk_frames_the_yard_again(self):
        self.assertTrue(self.got["after_walk"]["yard"]["inside"])
        self.assertGreater(self.got["after_walk"]["yard"]["tall"], 0.45)

    def test_the_street_view_stands_where_the_scene_says(self):
        street = self.scene["views"]["street"]
        (ex, ey), (lx, ly) = street["eye"], street["look"]
        at, looks = self.got["street"]["at"], self.got["street"]["looks_at"]
        self.assertAlmostEqual(at[0], ex, delta=0.02)
        self.assertAlmostEqual(at[2], -ey, delta=0.02)
        self.assertAlmostEqual(at[1], 1.65, delta=0.02)      # eye height
        self.assertAlmostEqual(looks[0], lx, delta=0.02)
        self.assertAlmostEqual(looks[2], -ly, delta=0.02)
        # Just outside the south edge (y = -18.3), not across the street.
        self.assertTrue(-18.3 - 8 < ey < -18.3, ey)

    def test_the_view_inside_the_yard_is_a_few_steps_on(self):
        lx, ly = self.scene["views"]["street"]["look"]
        at = self.got["in_yard"]["at"]
        self.assertAlmostEqual(math.hypot(at[0] - lx, -at[2] - ly), 3.0,
                               delta=0.1)
        self.assertAlmostEqual(at[1], 1.65, delta=0.02)

    def test_a_scene_with_no_street_view_keeps_the_old_preset(self):
        self.assertGreater(self.got["legacy"]["street"]["at"][2], 30)

    # ── walking ──────────────────────────────────────────────────────────────

    def test_the_walker_starts_on_the_street_side_facing_in(self):
        street = self.scene["views"]["street"]
        (ex, ey), (lx, ly) = street["eye"], street["look"]
        walk = self.got["walk"]
        self.assertFalse(walk["inside_a_building"],
                         "Walk the garden starts inside the house")
        self.assertAlmostEqual(walk["at"][0], ex, delta=0.02)
        self.assertAlmostEqual(walk["at"][1], ey, delta=0.02)
        self.assertAlmostEqual(walk["yaw"], math.atan2(lx - ex, ly - ey),
                               delta=0.01)

    def test_a_house_stops_him_at_its_walls_not_at_a_circle(self):
        """The house was a circle 7.3 m in radius on a lot 7.6 m to each side:
        both side yards were closed, and nothing led from front to back."""
        side = self.got["walls"]["side_yard"]
        self.assertEqual(side["to"], [-6.6, -3.0], "the side yard is blocked")
        pushed = self.got["walls"]["in_the_house"]
        self.assertFalse(pushed["inside"], "he was left standing in the house")
        x, y = pushed["to"]
        self.assertTrue(abs(x) > 5.4 or y > 2.7 or y < -9.3, pushed)

    # ── what stands ──────────────────────────────────────────────────────────

    def test_a_plant_that_is_gone_is_not_drawn(self):
        drawn = self.got["drawn"]
        self.assertNotIn("8", drawn, "plants lost to shade are still drawn")
        standing = sum(1 for p in standing_plants(self.scene)
                       if p["plant_id"] == 10)
        placed = sum(1 for p in self.scene["plants"] if p["plant_id"] == 10)
        self.assertLess(standing, placed)
        self.assertEqual(drawn.get("10"), standing,
                         "a short-lived kind past its years is drawn in full: "
                         "V3.42 drew the ones that were gone as pale ghosts")
        self.assertIn("7", drawn)

    def test_a_declining_plant_turns_toward_straw_never_sky(self):
        c = self.got["declining"]
        self.assertIsNotNone(c, "the marked forb was not drawn at all")
        self.assertLess(c["b"], c["r"], f"it is blended toward the sky: {c}")

    def test_fruit_is_no_wider_than_a_hand(self):
        sizes = self.got["fruit_m"]
        self.assertTrue(sizes, "the saskatoon carries no fruit in July")
        self.assertLessEqual(max(sizes), 0.16,
                             f"fruit drawn {max(sizes) * 100:.0f} cm across")

    # ── the words ────────────────────────────────────────────────────────────

    def test_the_line_at_the_top_says_what_is_there(self):
        hud = self.got["hud"]
        self.assertIn(f"Year {YEAR}", hud)
        self.assertIn("July", hud)
        self.assertIn("1 tree already here", hud)
        dead = sum(1 for p in self.scene["plants"] if p.get("gone") == "shade")
        lived = sum(1 for p in self.scene["plants"]
                    if p.get("gone") == "short_lived")
        self.assertIn(f"{dead} lost to shade", hud)
        self.assertIn(f"{lived} short-lived, gone", hud)
        standing = sum(1 for p in standing_plants(self.scene)
                       if p.get("plant_id") is not None)
        self.assertIn(f"{standing} plants", hud)
        self.assertNotIn("footprint", hud)

    def test_year_zero_is_called_fully_grown(self):
        hud = self.got["legacy"]["hud"]
        self.assertIn("Fully grown", hud)
        self.assertNotIn("Year 0", hud)
        self.assertNotIn("lost to shade", hud)

    # ── the frame-rate readout ───────────────────────────────────────────────

    def test_the_readout_shows_only_when_asked_for(self):
        perf = self.got["perf"]
        self.assertFalse(perf["before"], "the readout is on without being asked")
        self.assertTrue(perf["shown"], "Ctrl+Shift+F did not show it")
        self.assertTrue(perf["hidden"], "Ctrl+Shift+F did not hide it again")
        for key in ("fps", "frame_ms", "triangles", "calls", "plants", "detail"):
            self.assertIn(key, perf["reads"])


class TheProbeIsADevPage(unittest.TestCase):

    def test_the_viewer_knows_nothing_of_it(self):
        with open(os.path.join(render_yard.HTML, "scene3d", "chunks.js"),
                  encoding="utf-8") as fh:
            self.assertNotIn("yard_probe", fh.read())

    def test_it_loads_the_error_watcher(self):
        with open(os.path.join(render_yard.HTML, "yard_probe.html"),
                  encoding="utf-8") as fh:
            self.assertIn('src="probe_watch.js"', fh.read())


if __name__ == "__main__":
    unittest.main()
