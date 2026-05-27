"""
tests/test_project.py

Round-trip tests for src/project.py: new_project → save_project → load_project
should preserve the dict shape, and project_to_map_data should extract every
feature type (property_boundary, plant, structure, hedgerow, custom_shape,
contour_line, auto_contour, slope_overlay) from a synthetic GeoJSON.

This is part of the Chunk 2 safety net for the MainWindow decomposition in
Chunk 5 — `_on_save` / `_on_load` are thin wrappers around these helpers, so
locking down their behaviour means the refactor can't silently change the
on-disk format.
"""

import json
import os
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.project import (  # noqa: E402
    SCHEMA_VERSION,
    new_placement_group_id,
    new_project,
    save_project,
    load_project,
    project_to_map_data,
)


class TestNewProject(unittest.TestCase):

    def test_shape(self):
        p = new_project()
        self.assertEqual(p["type"], "FeatureCollection")
        self.assertEqual(p["features"], [])
        self.assertEqual(p["properties"]["schema_version"], SCHEMA_VERSION)
        self.assertEqual(p["properties"]["project_name"], "Untitled Design")

    def test_custom_name(self):
        p = new_project("My Garden")
        self.assertEqual(p["properties"]["project_name"], "My Garden")

    def test_site_config_has_expected_keys(self):
        site = new_project()["properties"]["site_config"]
        for key in ("latitude", "longitude", "area_m2", "hardiness_zone",
                    "soil_type", "sun_exposure", "wind_exposure", "priorities"):
            self.assertIn(key, site)


class TestPlacementGroupId(unittest.TestCase):

    def test_format(self):
        gid = new_placement_group_id()
        self.assertTrue(gid.startswith("pg_"))
        self.assertEqual(len(gid), 13)  # "pg_" + 10 hex chars

    def test_uniqueness(self):
        ids = {new_placement_group_id() for _ in range(100)}
        self.assertEqual(len(ids), 100)


class TestRoundTrip(unittest.TestCase):
    """save → load → equal preserves the dict on disk."""

    def setUp(self):
        self._tmp = tempfile.NamedTemporaryFile(
            mode="w", suffix=".perma.geojson", delete=False
        )
        self._tmp.close()
        self.path = self._tmp.name

    def tearDown(self):
        Path(self.path).unlink(missing_ok=True)

    def test_empty_project_round_trip(self):
        p = new_project("Round Trip Test")
        save_project(p, self.path)
        loaded = load_project(self.path)
        self.assertEqual(loaded, p)

    def test_round_trip_with_features(self):
        p = new_project()
        p["features"].append({
            "type": "Feature",
            "geometry": {"type": "Point", "coordinates": [-113.5, 53.5]},
            "properties": {
                "element_type": "plant",
                "plant_id": 42,
                "common_name": "Yarrow",
                "placement_group_id": "pg_abcdef0123",
            },
        })
        save_project(p, self.path)
        loaded = load_project(self.path)
        self.assertEqual(loaded["features"], p["features"])

    def test_disk_file_is_indented_json(self):
        save_project(new_project(), self.path)
        with open(self.path, encoding="utf-8") as f:
            text = f.read()
        # indent=2 means at least one line begins with two spaces.
        self.assertIn("\n  ", text)


class TestProjectToMapData(unittest.TestCase):
    """Every feature type the project file format supports should round-trip
    through project_to_map_data without loss."""

    def _make(self, *features):
        p = new_project()
        p["features"].extend(features)
        return p

    def test_empty_project_yields_empty_buckets(self):
        out = project_to_map_data(new_project())
        for key in ("boundaries", "plants", "structures", "hedgerows",
                    "shapes", "contours", "auto_contours"):
            self.assertEqual(out[key], [])
        self.assertIsNone(out["boundary"])
        self.assertIsNone(out["slope_overlay"])

    def test_property_boundary(self):
        ring = [[-113.5, 53.5], [-113.5, 53.6], [-113.4, 53.6], [-113.5, 53.5]]
        p = self._make({
            "type": "Feature",
            "geometry": {"type": "Polygon", "coordinates": [ring]},
            "properties": {
                "element_type": "property_boundary",
                "boundary_id": "b_1",
                "color": "red",
                "show_lengths": False,
                "show_area": True,
            },
        })
        out = project_to_map_data(p)
        self.assertEqual(len(out["boundaries"]), 1)
        bd = out["boundaries"][0]
        self.assertEqual(bd["id"], "b_1")
        self.assertEqual(bd["color"], "red")
        self.assertFalse(bd["showLengths"])
        # GeoJSON stores [lng,lat]; map data uses [lat,lng].
        self.assertEqual(bd["points"][0], [53.5, -113.5])
        # Backward-compat alias points at the first boundary's points.
        self.assertEqual(out["boundary"], bd["points"])

    def test_plant_assigns_placement_group_when_missing(self):
        p = self._make({
            "type": "Feature",
            "geometry": {"type": "Point", "coordinates": [-113.5, 53.5]},
            "properties": {
                "element_type": "plant",
                "plant_id": 7,
                "common_name": "Wild Bergamot",
                # NOTE: deliberately no placement_group_id — legacy projects.
            },
        })
        plants = project_to_map_data(p)["plants"]
        self.assertEqual(len(plants), 1)
        self.assertTrue(plants[0]["placement_group_id"].startswith("pg_"))
        self.assertEqual(plants[0]["plant_id"], 7)
        self.assertEqual(plants[0]["lat"], 53.5)
        self.assertEqual(plants[0]["lng"], -113.5)

    def test_plant_preserves_existing_placement_group(self):
        p = self._make({
            "type": "Feature",
            "geometry": {"type": "Point", "coordinates": [-113.5, 53.5]},
            "properties": {
                "element_type": "plant",
                "plant_id": 7,
                "placement_group_id": "pg_keepme0001",
            },
        })
        plants = project_to_map_data(p)["plants"]
        self.assertEqual(plants[0]["placement_group_id"], "pg_keepme0001")

    def test_structure_hedgerow_shape(self):
        p = self._make(
            {
                "type": "Feature",
                "geometry": {"type": "Point", "coordinates": [-113.5, 53.5]},
                "properties": {
                    "element_type": "structure",
                    "struct_def": {"kind": "bee_hotel"},
                },
            },
            {
                "type": "Feature",
                "geometry": {
                    "type": "LineString",
                    "coordinates": [[-113.5, 53.5], [-113.4, 53.5]],
                },
                "properties": {
                    "element_type": "hedgerow",
                    "style": "hedge",
                    "species": "Saskatoon",
                },
            },
            {
                "type": "Feature",
                "geometry": {
                    "type": "Polygon",
                    "coordinates": [[[-113.5, 53.5], [-113.5, 53.6],
                                     [-113.4, 53.6], [-113.5, 53.5]]],
                },
                "properties": {
                    "element_type": "custom_shape",
                    "shape_type": "Pond",
                    "label": "Goldfish pond",
                },
            },
        )
        out = project_to_map_data(p)
        self.assertEqual(len(out["structures"]), 1)
        self.assertEqual(out["structures"][0]["struct_def"], {"kind": "bee_hotel"})
        self.assertEqual(len(out["hedgerows"]), 1)
        self.assertEqual(out["hedgerows"][0]["species"], "Saskatoon")
        self.assertEqual(len(out["shapes"]), 1)
        self.assertEqual(out["shapes"][0]["label"], "Goldfish pond")

    def test_shape_strips_closing_duplicate(self):
        ring = [[-113.5, 53.5], [-113.5, 53.6], [-113.4, 53.6], [-113.5, 53.5]]
        p = self._make({
            "type": "Feature",
            "geometry": {"type": "Polygon", "coordinates": [ring]},
            "properties": {"element_type": "custom_shape"},
        })
        shape = project_to_map_data(p)["shapes"][0]
        # Closing vertex was identical to opening; project_to_map_data drops it.
        self.assertEqual(len(shape["points"]), 3)

    def test_contour_line_and_auto_contour(self):
        p = self._make(
            {
                "type": "Feature",
                "geometry": {
                    "type": "LineString",
                    "coordinates": [[-113.5, 53.5], [-113.4, 53.5]],
                },
                "properties": {
                    "element_type": "contour_line",
                    "elevation_m": 670,
                },
            },
            {
                "type": "Feature",
                "geometry": {
                    "type": "MultiLineString",
                    "coordinates": [
                        [[-113.5, 53.5], [-113.4, 53.5]],
                        [[-113.5, 53.6], [-113.4, 53.6]],
                    ],
                },
                "properties": {
                    "element_type": "auto_contour",
                    "elevation_m": 675,
                },
            },
        )
        out = project_to_map_data(p)
        self.assertEqual(len(out["contours"]), 1)
        self.assertEqual(out["contours"][0]["elevation_m"], 670)
        self.assertEqual(len(out["auto_contours"]), 1)
        self.assertEqual(len(out["auto_contours"][0]["segments"]), 2)

    def test_slope_overlay_metadata(self):
        p = self._make({
            "type": "Feature",
            "geometry": {"type": "Point", "coordinates": [0, 0]},
            "properties": {
                "element_type": "slope_overlay",
                "bbox": {"north": 53.6, "south": 53.5, "east": -113.4, "west": -113.5},
                "stats": {"mean_slope_pct": 4.2},
                "interval_m": 0.5,
                "resolution_m": 1.0,
                "source": "lidar",
            },
        })
        meta = project_to_map_data(p)["slope_overlay"]
        self.assertEqual(meta["source"], "lidar")
        self.assertEqual(meta["interval_m"], 0.5)


class TestSchemaVersionStable(unittest.TestCase):
    """If anyone bumps SCHEMA_VERSION, they should also touch the round-trip
    tests above — this assertion is a tripwire prompting that thought."""

    def test_schema_version_value(self):
        self.assertEqual(SCHEMA_VERSION, "1.6")


if __name__ == "__main__":
    unittest.main()
