"""
tests/test_scene_contract.py — the Scene JSON contract (V1.62).

Pins the schema the 3D viewer (and any future renderer/exporter) consumes:
version field, local-metre coordinates about the boundary centroid, plant
growth state matching src.scene3d, building extraction, terrain block
conversion, and JSON-serialisability. Pure Python — injected get_plant,
no Qt, no DB, no network.
"""

import json
import math
import os
import sys
import unittest
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.scene_contract import SCENE_VERSION, build_scene   # noqa: E402
from src.project_store import plant_feature                 # noqa: E402

_LAT, _LNG = 53.5, -113.5

_FAKE_PLANTS = {
    1: {"plant_type": "tree", "years_to_maturity": 20, "growth_curve": "steady",
        "mature_height_meters": 10.0, "mature_canopy_m": 6.0,
        "deciduous_evergreen": "evergreen"},
    2: {"plant_type": "shrub", "years_to_maturity": 5, "growth_curve": "steady",
        "mature_height_meters": 2.0, "mature_canopy_m": 1.5,
        "marker_color": "#123456"},
    3: {"plant_type": "wildflower", "years_to_maturity": 2, "growth_curve": "steady",
        "mature_height_meters": 0.5, "mature_canopy_m": 0.4,
        "scientific_name": "Solidago canadensis", "bloom_period": "Aug-Sep",
        "flower_color": "#f2c11e", "flower_form": "spike"},
}


def _get_plant(pid):
    return _FAKE_PLANTS.get(pid)


def _boundary_feature(half_deg=0.0005):
    ring = [
        [_LNG - half_deg, _LAT - half_deg],
        [_LNG + half_deg, _LAT - half_deg],
        [_LNG + half_deg, _LAT + half_deg],
        [_LNG - half_deg, _LAT + half_deg],
        [_LNG - half_deg, _LAT - half_deg],
    ]
    return {"type": "Feature",
            "geometry": {"type": "Polygon", "coordinates": [ring]},
            "properties": {"element_type": "property_boundary",
                           "boundary_id": "b1"}}


def _project(features):
    return {"type": "FeatureCollection", "properties": {"site_config": {}},
            "features": list(features)}


class TestSceneBasics(unittest.TestCase):

    def test_version_and_serialisable(self):
        scene = build_scene(_project([]), get_plant=_get_plant)
        self.assertEqual(scene["version"], SCENE_VERSION)
        json.dumps(scene)   # must not raise

    def test_origin_is_boundary_centroid_and_metres_are_local(self):
        scene = build_scene(
            _project([
                _boundary_feature(),
                plant_feature({"plant_id": 1, "common_name": "Tree",
                               "lat": _LAT, "lng": _LNG}),
            ]),
            get_plant=_get_plant)
        self.assertAlmostEqual(scene["origin"]["lat"], _LAT, places=6)
        self.assertAlmostEqual(scene["origin"]["lng"], _LNG, places=6)
        # The plant sits at the centroid → (0, 0) in scene metres.
        p = scene["plants"][0]
        self.assertAlmostEqual(p["x"], 0.0, delta=0.05)
        self.assertAlmostEqual(p["y"], 0.0, delta=0.05)
        # Boundary should be roughly ±55 m (0.0005° of latitude).
        ys = [pt[1] for pt in scene["boundary"]]
        self.assertAlmostEqual(max(ys), 0.0005 * 111320, delta=1.0)

    def test_plants_match_scene3d_growth(self):
        proj = _project([
            plant_feature({"plant_id": 1, "common_name": "Tree",
                           "lat": _LAT, "lng": _LNG}),
        ])
        mature = build_scene(proj, year=0, get_plant=_get_plant)["plants"][0]
        young = build_scene(proj, year=10, get_plant=_get_plant)["plants"][0]
        self.assertEqual(mature["height_m"], 10.0)
        self.assertEqual(young["height_m"], 5.0)    # linear, 10/20 years
        self.assertEqual(young["canopy_m"], 3.0)
        self.assertEqual(mature["plant_type"], "tree")

    def test_foliage_type_and_month_for_3d_forms(self):
        # The 3D viewer keys crown shape (conifer vs deciduous) and seasonal
        # colour off these additive fields — see html/scene3d.html.
        proj = _project([
            plant_feature({"plant_id": 1, "common_name": "Tree",
                           "lat": _LAT, "lng": _LNG}),
            plant_feature({"plant_id": 2, "common_name": "Shrub",
                           "lat": _LAT, "lng": _LNG}),
        ])
        scene = build_scene(proj, get_plant=_get_plant,
                            when=datetime(2025, 10, 21, 13, 0))
        self.assertEqual(scene["month"], 10)
        by_id = {p["common_name"]: p for p in scene["plants"]}
        self.assertEqual(by_id["Tree"]["foliage_type"], "evergreen")
        # Plant 2 has no deciduous_evergreen → defaults to herbaceous.
        self.assertEqual(by_id["Shrub"]["foliage_type"], "herbaceous")

    def test_flower_and_foliage_fields_for_3d(self):
        # V1.90: the 3D viewer colours the body with a natural foliage colour and
        # draws real-coloured flowers (form + colour + bloom window).
        proj = _project([
            plant_feature({"plant_id": 3, "common_name": "Goldenrod",
                           "lat": _LAT, "lng": _LNG}),
        ])
        p = build_scene(proj, get_plant=_get_plant)["plants"][0]
        # Body colour is a natural green, NOT the wildflower type colour (purple).
        self.assertNotEqual(p["color"].lower(), "#ab47bc")
        self.assertEqual(p["flower_color"], "#f2c11e")
        self.assertEqual(p["flower_form"], "spike")
        self.assertEqual((p["bloom_start"], p["bloom_end"]), (8, 9))

    def test_grass_seedhead_default_bloom(self):
        # A flowering plant with no bloom_period (e.g. a grass seed-head plume)
        # falls back to a generic summer window so its sprite still appears.
        from src.scene_contract import _bloom_window
        self.assertEqual(
            _bloom_window({"flower_form": "plume", "bloom_period": ""}),
            {"bloom_start": 6, "bloom_end": 9})
        # A non-flowering plant stays at (0, 0) — no sprite.
        self.assertEqual(
            _bloom_window({"flower_form": "none", "bloom_period": ""}),
            {"bloom_start": 0, "bloom_end": 0})

    def test_marker_color_overrides_foliage(self):
        # An explicit user marker colour still wins for the body.
        proj = _project([
            plant_feature({"plant_id": 2, "common_name": "Shrub",
                           "lat": _LAT, "lng": _LNG}),
        ])
        p = build_scene(proj, get_plant=_get_plant)["plants"][0]
        self.assertEqual(p["color"], "#123456")

    def test_growth_and_spread_fields_for_3d_forms(self):
        # The 3D viewer keys the structural maturity tier off scale_factor and
        # the self-spread satellite scatter off spread_factor — see scene3d.html.
        proj = _project([
            plant_feature({"plant_id": 1, "common_name": "Tree",
                           "lat": _LAT, "lng": _LNG}),
        ])
        mature = build_scene(proj, year=0, get_plant=_get_plant)["plants"][0]
        young = build_scene(proj, year=10, get_plant=_get_plant)["plants"][0]
        # year 0 = mature reference (full size); year 10 of 20 = half-grown.
        self.assertEqual(mature["scale_factor"], 1.0)
        self.assertEqual(young["scale_factor"], 0.5)
        # No spread_habit on the fake plant → no colony widening or spread.
        self.assertEqual(mature["spread_factor"], 1.0)
        self.assertEqual(mature["spread_rate"], 0.0)
        self.assertEqual(mature["growth_curve"], "steady")

    def test_marker_color_wins_over_type_color(self):
        proj = _project([
            plant_feature({"plant_id": 2, "common_name": "Shrub",
                           "lat": _LAT, "lng": _LNG}),
        ])
        p = build_scene(proj, get_plant=_get_plant)["plants"][0]
        self.assertEqual(p["color"], "#123456")

    def test_bounds_floor_for_empty_scene(self):
        b = build_scene(_project([]), get_plant=_get_plant)["bounds"]
        self.assertLessEqual(b["min_x"], -25.0)
        self.assertGreaterEqual(b["max_y"], 25.0)


class TestBuildingsAndStructures(unittest.TestCase):

    def test_existing_building_square_with_height(self):
        proj = _project([
            _boundary_feature(),
            {"type": "Feature",
             "geometry": {"type": "Point", "coordinates": [_LNG, _LAT]},
             "properties": {"element_type": "existing_building",
                            "size_m": 10.0, "height_m": 7.5}},
        ])
        b = build_scene(proj, get_plant=_get_plant)["buildings"][0]
        self.assertEqual(b["kind"], "building")
        self.assertEqual(b["height_m"], 7.5)
        self.assertEqual(len(b["ring"]), 4)
        side = math.dist(b["ring"][0], b["ring"][1])
        self.assertAlmostEqual(side, 10.0, delta=0.1)

    def test_canopy_footprint_polygon(self):
        d = 0.0001
        ring = [[_LNG - d, _LAT - d], [_LNG + d, _LAT - d],
                [_LNG + d, _LAT + d], [_LNG - d, _LAT + d],
                [_LNG - d, _LAT - d]]
        proj = _project([
            _boundary_feature(),
            {"type": "Feature",
             "geometry": {"type": "Polygon", "coordinates": [ring]},
             "properties": {"element_type": "canopy_footprint",
                            "height_m": 9.0, "cast_shade": True}},
        ])
        b = build_scene(proj, get_plant=_get_plant)["buildings"][0]
        self.assertEqual(b["kind"], "canopy")
        self.assertEqual(len(b["ring"]), 4)   # closing vertex dropped

    def test_flat_shape_is_not_a_building(self):
        d = 0.0001
        ring = [[_LNG - d, _LAT - d], [_LNG + d, _LAT - d],
                [_LNG + d, _LAT + d], [_LNG - d, _LAT - d]]
        proj = _project([
            {"type": "Feature",
             "geometry": {"type": "Polygon", "coordinates": [ring]},
             "properties": {"element_type": "custom_shape",
                            "height_m": 0.0}},
        ])
        self.assertEqual(build_scene(proj, get_plant=_get_plant)["buildings"],
                         [])

    def test_existing_tree_becomes_scene_plant(self):
        proj = _project([
            {"type": "Feature",
             "geometry": {"type": "Point", "coordinates": [_LNG, _LAT]},
             "properties": {"element_type": "existing_tree",
                            "height_m": 12.0, "canopy_radius_m": 4.0}},
        ])
        p = build_scene(proj, get_plant=_get_plant)["plants"][0]
        self.assertTrue(p.get("existing"))
        self.assertEqual(p["height_m"], 12.0)
        self.assertEqual(p["canopy_m"], 8.0)
        self.assertEqual(p["plant_type"], "tree")

    def test_structure_point(self):
        proj = _project([
            {"type": "Feature",
             "geometry": {"type": "Point", "coordinates": [_LNG, _LAT]},
             "properties": {"element_type": "structure",
                            "struct_def": {"id": "bee_hotel",
                                           "name": "Bee hotel",
                                           "size_m": 0.5,
                                           "height_m": 1.5}}},
        ])
        s = build_scene(proj, get_plant=_get_plant)["structures"][0]
        self.assertEqual(s["struct_id"], "bee_hotel")
        self.assertEqual(s["height_m"], 1.5)


class TestTerrainAndSun(unittest.TestCase):

    def test_terrain_block_relative_heights(self):
        elevation = {
            "grid": [[660.0, 661.0], [662.0, 663.0]],
            "rows": 2, "cols": 2,
            "bbox": {"north": _LAT + 0.0005, "south": _LAT - 0.0005,
                     "east": _LNG + 0.0005, "west": _LNG - 0.0005},
        }
        proj = _project([_boundary_feature()])
        t = build_scene(proj, get_plant=_get_plant,
                        elevation=elevation)["terrain"]
        self.assertEqual(t["rows"], 2)
        self.assertEqual(t["base_m"], 660.0)
        self.assertEqual(t["heights"][0][0], 0.0)
        self.assertEqual(t["heights"][1][1], 3.0)
        self.assertLess(t["min_x"], 0)
        self.assertGreater(t["max_x"], 0)

    def test_no_elevation_means_no_terrain(self):
        scene = build_scene(_project([]), get_plant=_get_plant)
        self.assertIsNone(scene["terrain"])

    def test_summer_noon_sun_is_southish_and_high(self):
        proj = _project([_boundary_feature()])
        sun = build_scene(proj, get_plant=_get_plant,
                          when=datetime(2025, 6, 21, 13, 0))["sun"]
        self.assertIsNotNone(sun)
        self.assertGreater(sun["altitude_deg"], 40)      # high June sun
        self.assertTrue(120 < sun["azimuth_deg"] < 240)  # broadly south

    def test_midnight_sun_is_none(self):
        proj = _project([_boundary_feature()])
        sun = build_scene(proj, get_plant=_get_plant,
                          when=datetime(2025, 1, 21, 1, 0))["sun"]
        self.assertIsNone(sun)


if __name__ == "__main__":
    unittest.main()
