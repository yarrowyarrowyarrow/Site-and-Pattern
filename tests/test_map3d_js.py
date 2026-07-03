"""
tests/test_map3d_js.py

V1.56 — JS builders that drive the embedded map3d 3D view's sun (and the
shadows it casts) from src/solar.py. Pure string/JSON building + the existing
solar math; no Qt, no network.
"""

import os
import sys
import unittest
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import src.map3d_js as m3  # noqa: E402

# Edmonton — the project's reference location (src/solar.py).
_LAT, _LNG = 53.5461, -113.4938


class TestSetSun(unittest.TestCase):
    def test_emits_guarded_hook_call(self):
        js = m3.set_sun(180.0, 45.0)
        self.assertIn("window.permaSetSun && window.permaSetSun(", js)
        self.assertIn("180.0", js)
        self.assertIn("45.0", js)
        self.assertTrue(js.strip().endswith(");"))

    def test_values_are_json_encoded_numbers(self):
        # ints coerce to floats; no raw string interpolation that could inject.
        js = m3.set_sun(90, 30)
        self.assertIn("90.0", js)
        self.assertIn("30.0", js)


class TestSetSunFor(unittest.TestCase):
    def test_daytime_returns_hook_js(self):
        # Summer-solstice noon at Edmonton → sun well above the horizon.
        js = m3.set_sun_for(_LAT, _LNG, datetime(2025, 6, 21, 12, 0))
        self.assertIsNotNone(js)
        self.assertIn("window.permaSetSun", js)

    def test_night_returns_none(self):
        # 1 AM local → sun below the horizon → nothing to draw.
        self.assertIsNone(
            m3.set_sun_for(_LAT, _LNG, datetime(2025, 6, 21, 1, 0)))

    def test_matches_solar_sun_position(self):
        # The emitted azimuth/altitude are exactly solar.sun_position's, so the
        # 3D sun and the 2D shade engine agree by construction.
        from datetime import timedelta
        from src.solar import sun_position
        when = datetime(2025, 6, 21, 15, 0)
        sun = sun_position(_LAT, _LNG, when + timedelta(hours=-_LNG / 15.0))
        js = m3.set_sun_for(_LAT, _LNG, when)
        self.assertIn(str(float(sun.azimuth)), js)
        self.assertIn(str(float(sun.altitude)), js)


class TestSetScene(unittest.TestCase):
    def test_emits_guarded_hook_with_scene_json(self):
        scene = {"version": 1, "bounds": {"min_x": -25, "min_y": -25,
                                          "max_x": 25, "max_y": 25},
                 "plants": [], "buildings": [], "structures": [],
                 "boundary": None, "terrain": None, "sun": None}
        js = m3.set_scene(scene)
        self.assertIn("window.permaSetScene && window.permaSetScene(", js)
        self.assertIn('"version": 1', js)
        self.assertTrue(js.strip().endswith(");"))

    def test_round_trips_build_scene_output(self):
        # The builder must serialise a real contract dict untouched.
        import json
        from src.scene_contract import build_scene
        scene = build_scene({"type": "FeatureCollection",
                             "properties": {}, "features": []},
                            get_plant=lambda pid: None)
        js = m3.set_scene(scene)
        payload = js[js.index("(", js.index("permaSetScene(")) + 1:-2]
        self.assertEqual(json.loads(payload), scene)


class TestSplatBuilders(unittest.TestCase):
    def test_capture_ortho_emits_guarded_hook_with_rect(self):
        js = m3.capture_ortho({"min_x": -5, "max_x": 5,
                               "min_y": -10, "max_y": 10}, width=1024)
        self.assertIn("window.permaCaptureOrtho && window.permaCaptureOrtho(",
                      js)
        self.assertIn('"width": 1024', js)
        self.assertIn('"min_x": -5.0', js)
        self.assertTrue(js.strip().endswith(");"))

    def test_clear_splat_is_guarded(self):
        js = m3.clear_splat()
        self.assertIn("window.permaClearSplat && window.permaClearSplat()", js)


class TestSetPlants(unittest.TestCase):
    def test_emits_guarded_hook_with_json(self):
        recs = [{"plant_id": 1, "lat": 53.5, "lng": -113.5,
                 "height_m": 5.0, "canopy_m": 3.0}]
        js = m3.set_plants(recs)
        self.assertIn("window.permaSetPlants && window.permaSetPlants(", js)
        self.assertIn('"plant_id": 1', js)
        self.assertIn('"height_m": 5.0', js)
        self.assertTrue(js.strip().endswith(");"))

    def test_empty_list(self):
        js = m3.set_plants([])
        self.assertIn("window.permaSetPlants && window.permaSetPlants([]", js)


class TestBeeMode(unittest.TestCase):
    def test_set_bee_mode_guarded_bool(self):
        on = m3.set_bee_mode(True)
        self.assertIn("window.permaSetBeeMode && window.permaSetBeeMode(", on)
        self.assertIn("true", on)
        self.assertTrue(on.strip().endswith(");"))
        self.assertIn("false", m3.set_bee_mode(False))

    def test_set_bee_targets_json_int_list(self):
        js = m3.set_bee_targets([3, 7, 12])
        self.assertIn("window.permaSetBeeTargets && window.permaSetBeeTargets(", js)
        self.assertIn("[3, 7, 12]", js)
        self.assertTrue(js.strip().endswith(");"))

    def test_set_bee_targets_coerces_and_handles_empty(self):
        # ids arrive as ints even if passed as strings; empty → []
        self.assertIn("[1, 2]", m3.set_bee_targets(["1", "2"]))
        self.assertIn("permaSetBeeTargets([]", m3.set_bee_targets([]))

    def test_set_bee_targets_passes_label(self):
        # The bee's display name feeds the nectar-run HUD (V2.12); it is JSON-
        # quoted (never raw-interpolated) and defaults to "".
        js = m3.set_bee_targets([3], "Mining Bees (any Andrena)")
        self.assertIn('[3], "Mining Bees (any Andrena)"', js)
        self.assertIn('[], ""', m3.set_bee_targets([], ""))
        self.assertIn('""', m3.set_bee_targets([1]))

    def test_set_bee_targets_kind_and_hosts(self):
        # Lepidoptera (V2.12): kind picks the avatar, host_ids are larval-host
        # "nursery" markers. Both are JSON-encoded; defaults are 'bee' + [].
        js = m3.set_bee_targets([3, 4], "Monarch", "butterfly", [7, 9])
        self.assertIn('[3, 4], "Monarch", "butterfly", [7, 9]', js)
        self.assertTrue(js.strip().endswith(");"))
        # Host ids are coerced to ints like the nectar ids.
        self.assertIn("[1, 2]", m3.set_bee_targets([], "", "moth", ["1", "2"]))
        # Default kind/hosts when omitted.
        self.assertIn('"bee", []', m3.set_bee_targets([1]))

    def test_set_bee_tour_guarded_bool(self):
        on = m3.set_bee_tour(True)
        self.assertIn("window.permaSetBeeTour && window.permaSetBeeTour(", on)
        self.assertIn("true", on)
        self.assertTrue(on.strip().endswith(");"))
        self.assertIn("false", m3.set_bee_tour(False))

    def test_set_bee_targets_appearance(self):
        # The flown avatar's look spec is JSON-encoded as the 5th arg; None by
        # default so an un-styled bee still flies (V2.12).
        app = {"kind": "bee", "fuzz": "#3fae5a", "metallic": True}
        js = m3.set_bee_targets([1], "Green Sweat Bee", "bee", [], app)
        self.assertIn('"metallic": true', js)
        self.assertIn('"#3fae5a"', js)
        self.assertIn("null", m3.set_bee_targets([1]))   # default appearance


class TestWildlifeAndWalk(unittest.TestCase):
    def test_set_wildlife_json(self):
        crit = [{"kind": "bee", "x": 1.0, "y": 2.0, "h": 0.5,
                 "app": {"kind": "bee", "fuzz": "#f2c12e"}}]
        js = m3.set_wildlife(crit)
        self.assertIn("window.permaSetWildlife && window.permaSetWildlife(", js)
        self.assertIn('"kind": "bee"', js)
        self.assertIn('"#f2c12e"', js)
        self.assertTrue(js.strip().endswith(");"))
        self.assertIn("permaSetWildlife([]", m3.set_wildlife([]))

    def test_set_walk_mode_guarded_bool(self):
        on = m3.set_walk_mode(True)
        self.assertIn("window.permaSetWalkMode && window.permaSetWalkMode(", on)
        self.assertIn("true", on)
        self.assertTrue(on.strip().endswith(");"))
        self.assertIn("false", m3.set_walk_mode(False))

    def test_set_cinematic_guarded_bool(self):
        on = m3.set_cinematic(True)
        self.assertIn("window.permaSetCinematic && window.permaSetCinematic(", on)
        self.assertIn("true", on)
        self.assertTrue(on.strip().endswith(");"))
        self.assertIn("false", m3.set_cinematic(False))

    def test_set_cinematic_caption_json(self):
        js = m3.set_cinematic_caption("Year 5", "the canopy fills in")
        self.assertIn("window.permaSetCinematicCaption && "
                      "window.permaSetCinematicCaption(", js)
        self.assertIn('"Year 5", "the canopy fills in"', js)
        self.assertIn('"", ""', m3.set_cinematic_caption("", ""))

    def test_set_wildlife_labels_guarded_bool(self):
        on = m3.set_wildlife_labels(True)
        self.assertIn("window.permaSetWildlifeLabels && window.permaSetWildlifeLabels(", on)
        self.assertIn("true", on)
        self.assertTrue(on.strip().endswith(");"))
        self.assertIn("false", m3.set_wildlife_labels(False))

    def test_set_plant_spotlight_json(self):
        items = [{"plant_id": 5, "name": "Wild Bergamot", "x": 1.0, "y": 2.0, "h": 0.9}]
        app = {"kind": "bee", "fuzz": "#f2c12e"}
        js = m3.set_plant_spotlight(items, app)
        self.assertIn("window.permaSetPlantSpotlight && window.permaSetPlantSpotlight(",
                      js)
        self.assertIn('"Wild Bergamot"', js)
        self.assertIn('"#f2c12e"', js)
        self.assertTrue(js.strip().endswith(");"))
        # Empty clears; appearance defaults to null.
        self.assertIn("permaSetPlantSpotlight([], null", m3.set_plant_spotlight([]))


if __name__ == "__main__":
    unittest.main()
