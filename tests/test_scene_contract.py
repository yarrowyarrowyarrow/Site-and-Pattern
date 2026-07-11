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
    4: {"plant_type": "aquatic", "years_to_maturity": 3, "growth_curve": "steady",
        "mature_height_meters": 1.6, "mature_canopy_m": 0.5,
        "scientific_name": "Typha latifolia", "bloom_period": "June–September",
        "flower_color": "#7a5230", "flower_form": "cattail"},
    5: {"plant_type": "tree", "years_to_maturity": 20, "growth_curve": "steady",
        "mature_height_meters": 18.0, "mature_canopy_m": 6.0,
        "deciduous_evergreen": "evergreen", "scientific_name": "Picea glauca"},
    6: {"plant_type": "shrub", "years_to_maturity": 4, "growth_curve": "steady",
        "mature_height_meters": 3.0, "mature_canopy_m": 2.0,
        "scientific_name": "Amelanchier alnifolia", "fruit_period": "July–August",
        "fruit_color": "#46295e"},
    # Regeneration fixtures: a fast deciduous overstory, a full-sun forb it shades
    # out, and a self-seeding native that colonises the gap.
    7: {"plant_type": "tree", "years_to_maturity": 12, "growth_curve": "fast_early",
        "mature_height_meters": 11.0, "mature_canopy_m": 8.0,
        "deciduous_evergreen": "deciduous", "common_name": "Aspen"},
    8: {"plant_type": "wildflower", "years_to_maturity": 2, "growth_curve": "steady",
        "mature_height_meters": 0.6, "mature_canopy_m": 0.4,
        "sun_requirement": "full_sun", "common_name": "Sun forb"},
    9: {"plant_type": "wildflower", "years_to_maturity": 3, "growth_curve": "steady",
        "mature_height_meters": 0.7, "mature_canopy_m": 0.5,
        "sun_requirement": "full_sun,partial_shade", "spread_habit": "self_seeding",
        "common_name": "Selfseeder"},
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


def _existing_tree(foliage=""):
    props = {"element_type": "existing_tree", "height_m": 10.0,
             "canopy_radius_m": 3.0, "label": "Tree"}
    if foliage:
        props["tree_foliage"] = foliage
    return {"type": "Feature",
            "geometry": {"type": "Point", "coordinates": [_LNG, _LAT]},
            "properties": props}


class TestExistingTreeFoliageShape(unittest.TestCase):
    """An existing tree's foliage must drive its 3D shape (the viewer keys
    tree shape off genus): evergreen → a conifer genus, deciduous/unknown →
    the broadleaf default. Without this the conifer/deciduous distinction is
    invisible in 3D (V2.26)."""

    def _tree_plant(self, foliage):
        scene = build_scene(_project([_existing_tree(foliage)]),
                            get_plant=_get_plant)
        trees = [p for p in scene["plants"] if p.get("existing")]
        self.assertEqual(len(trees), 1)
        return trees[0]

    def test_evergreen_renders_as_conifer(self):
        self.assertEqual(self._tree_plant("evergreen")["genus"], "spruce")

    def test_deciduous_and_unknown_stay_broadleaf(self):
        self.assertEqual(self._tree_plant("deciduous")["genus"], "")
        self.assertEqual(self._tree_plant("")["genus"], "")


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

    def test_regeneration_recruits_fill_gaps(self):
        # V2.24: when the closing canopy shades a plant to death, a self-seeding
        # native already in the design recruits into the gap — the mature scene
        # shows recovery, not a permanent bare spot.
        n2 = 2.0 / 111320.0
        n8 = 8.0 / 111320.0
        proj = _project([
            plant_feature({"plant_id": 7, "common_name": "Aspen",
                           "lat": _LAT, "lng": _LNG}),
            plant_feature({"plant_id": 8, "common_name": "Sun forb",
                           "lat": _LAT + n2, "lng": _LNG}),
            plant_feature({"plant_id": 9, "common_name": "Selfseeder",
                           "lat": _LAT + n8, "lng": _LNG}),
        ])
        young = build_scene(proj, year=1, get_plant=_get_plant)["plants"]
        mature = build_scene(proj, year=25, get_plant=_get_plant)["plants"]
        # Nothing recruited before anything died.
        self.assertFalse(any(p.get("recruit") for p in young))
        # The forb has been shaded out (opacity 0) and a recruit has grown in.
        forb = next(p for p in mature if p["common_name"] == "Sun forb")
        self.assertEqual(forb["health_state"], "dead")
        recruits = [p for p in mature if p.get("recruit")]
        self.assertTrue(recruits, "the gap should be colonised by year 25")
        self.assertEqual(recruits[0]["plant_type"], "wildflower")
        # It renders as a real (young, healthy) plant, not a ghost.
        self.assertEqual(recruits[0]["health_state"], "healthy")
        self.assertGreater(recruits[0]["opacity"], 0.0)

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

    def test_cattail_aquatic_flower_passthrough(self):
        # V1.92: a marsh cattail carries the brown "cattail" spike form + colour
        # and its bloom window through to the 3D viewer's aquatic geometry.
        proj = _project([
            plant_feature({"plant_id": 4, "common_name": "Cattail",
                           "lat": _LAT, "lng": _LNG}),
        ])
        p = build_scene(proj, get_plant=_get_plant)["plants"][0]
        self.assertEqual(p["plant_type"], "aquatic")
        self.assertEqual(p["flower_form"], "cattail")
        self.assertEqual(p["flower_color"], "#7a5230")
        self.assertEqual((p["bloom_start"], p["bloom_end"]), (6, 9))

    def test_genus_drives_species_geometry_and_colour(self):
        # V1.94: the scene plant carries `genus` (so the viewer can pick spruce vs
        # pine vs fir geometry) and a genus-specific foliage green (spruce blue-
        # green), not the generic dark-conifer colour.
        proj = _project([
            plant_feature({"plant_id": 5, "common_name": "White Spruce",
                           "lat": _LAT, "lng": _LNG}),
        ])
        p = build_scene(proj, get_plant=_get_plant)["plants"][0]
        self.assertEqual(p["genus"], "picea")
        self.assertEqual(p["color"].lower(), "#46685a")   # spruce blue-green
        self.assertNotEqual(p["color"].lower(), "#355e3b")  # not the generic conifer

    def test_fruit_color_and_window_for_fleshy_fruit(self):
        # V2.0: a fleshy-fruited plant carries its berry colour + fruit window so
        # the 3D viewer can show berries in season; dry/non-fruiting plants don't.
        proj = _project([
            plant_feature({"plant_id": 6, "common_name": "Saskatoon Berry",
                           "lat": _LAT, "lng": _LNG}),
        ])
        p = build_scene(proj, get_plant=_get_plant)["plants"][0]
        self.assertEqual(p["fruit_color"], "#46295e")
        self.assertEqual((p["fruit_start"], p["fruit_end"]), (7, 8))
        # A non-fruiting plant (the spruce) carries no berry colour.
        spruce = build_scene(_project([
            plant_feature({"plant_id": 5, "common_name": "White Spruce",
                           "lat": _LAT, "lng": _LNG}),
        ]), get_plant=_get_plant)["plants"][0]
        self.assertEqual(spruce["fruit_color"], "")

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

    def test_is_night_flag(self):
        # is_night tracks the sun being below the horizon — drives the moonlit
        # 3D render and nocturnal wildlife (V2.12).
        proj = _project([_boundary_feature()])
        noon = build_scene(proj, get_plant=_get_plant,
                           when=datetime(2025, 6, 21, 13, 0))
        night = build_scene(proj, get_plant=_get_plant,
                            when=datetime(2025, 1, 21, 1, 0))
        self.assertFalse(noon["is_night"])
        self.assertTrue(night["is_night"])


if __name__ == "__main__":
    unittest.main()
