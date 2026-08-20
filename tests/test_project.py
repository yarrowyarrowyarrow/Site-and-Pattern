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
    update_shape_geometry,
)
import math  # noqa: E402


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

    def test_existing_tree_foliage_reaches_map_and_colours(self):
        # V2.26: tree_foliage must survive project_to_map_data (it was
        # dropped, so 2D markers never differed by conifer/deciduous) and
        # drive the crown colour.
        def _tree(foliage):
            props = {"element_type": "existing_tree", "height_m": 12.0,
                     "canopy_radius_m": 3.0, "label": "Tree (detected)"}
            if foliage:
                props["tree_foliage"] = foliage
            return {"type": "Feature",
                    "geometry": {"type": "Point",
                                 "coordinates": [-113.3, 53.5]},
                    "properties": props}
        out = project_to_map_data(self._make(
            _tree("evergreen"), _tree("deciduous"), _tree("")))
        defs = [s["struct_def"] for s in out["structures"]]
        self.assertEqual(defs[0].get("tree_foliage"), "evergreen")
        self.assertEqual(defs[0]["color"], "#1b5e20")     # conifer blue-green
        self.assertEqual(defs[1].get("tree_foliage"), "deciduous")
        self.assertEqual(defs[1]["color"], "#8d6e00")     # broadleaf warm
        # Unknown foliage → neutral, distinct from both tagged colours.
        self.assertNotIn(defs[2]["color"], ("#1b5e20", "#8d6e00"))

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

    def test_canopy_footprint_round_trips_height_and_id(self):
        # V1.53: a shade-casting canopy_footprint loads back through the same
        # shapes channel, preserving its height and shape_id.
        ring = [[-113.5, 53.5], [-113.5, 53.6], [-113.4, 53.6], [-113.5, 53.5]]
        p = self._make({
            "type": "Feature",
            "geometry": {"type": "Polygon", "coordinates": [ring]},
            "properties": {
                "element_type": "canopy_footprint",
                "shape_id": "shape_abc",
                "label": "House",
                "height_m": 8.0,
                "cast_shade": True,
            },
        })
        shapes = project_to_map_data(p)["shapes"]
        self.assertEqual(len(shapes), 1)
        self.assertEqual(shapes[0]["height_m"], 8.0)
        self.assertEqual(shapes[0]["shape_id"], "shape_abc")

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

    def test_annotation_extracted(self):
        # V1.81: annotations must survive project_to_map_data so the
        # whole-project re-render (File→Open + undo/redo) redraws them.
        p = self._make({
            "type": "Feature",
            "geometry": {"type": "Point", "coordinates": [-113.5, 53.5]},
            "properties": {
                "element_type": "annotation",
                "annotation_id": "ann_1",
                "text": "Wet corner — sedges here",
            },
        })
        anns = project_to_map_data(p)["annotations"]
        self.assertEqual(len(anns), 1)
        self.assertEqual(anns[0]["annotation_id"], "ann_1")
        self.assertEqual(anns[0]["text"], "Wet corner — sedges here")
        self.assertEqual(anns[0]["lat"], 53.5)
        self.assertEqual(anns[0]["lng"], -113.5)


class TestUpdateShapeGeometry(unittest.TestCase):
    """V1.58 — editing a footprint's outline updates the project geometry and
    re-sizes its keep-out / circle radius from the new ring (Step F)."""

    def _osm_building(self, half_m=4.0, clat=53.5, clng=-113.5):
        dlat = half_m / 111320.0
        dlng = half_m / (111320.0 * math.cos(math.radians(clat)))
        ring = [[clng - dlng, clat - dlat], [clng + dlng, clat - dlat],
                [clng + dlng, clat + dlat], [clng - dlng, clat + dlat],
                [clng - dlng, clat - dlat]]
        return {
            "type": "Feature",
            "geometry": {"type": "Polygon", "coordinates": [ring]},
            "properties": {
                "element_type": "canopy_footprint", "shape_id": "shape_osm_0",
                "height_m": 6.0, "cast_shade": True, "canopy_radius_m": half_m,
                "lat": clat, "lng": clng, "source": "osm"},
        }

    def test_enlarging_outline_grows_radius_and_keepout(self):
        from src.exclusion import keepout_circles
        p = new_project("t")
        p["features"].append(self._osm_building(half_m=4.0))
        r0 = keepout_circles(p)[0][2]
        # A larger outline (~12 m half-extent), as the [lat,lng] open ring the
        # map sends after a vertex drag.
        clat, clng, half_m = 53.5, -113.5, 12.0
        dlat = half_m / 111320.0
        dlng = half_m / (111320.0 * math.cos(math.radians(clat)))
        bigger = [[clat - dlat, clng - dlng], [clat - dlat, clng + dlng],
                  [clat + dlat, clng + dlng], [clat + dlat, clng - dlng]]
        self.assertTrue(update_shape_geometry(p, "shape_osm_0", bigger))
        ring = p["features"][0]["geometry"]["coordinates"][0]
        self.assertEqual(ring[0], ring[-1])          # ring re-closed
        self.assertGreater(p["features"][0]["properties"]["canopy_radius_m"], 4.0)
        self.assertGreater(keepout_circles(p)[0][2], r0 + 1.0)   # keep-out grew

    def test_unknown_shape_id_is_noop(self):
        p = new_project("t")
        p["features"].append(self._osm_building())
        self.assertFalse(update_shape_geometry(
            p, "nope", [[53.5, -113.5], [53.6, -113.5], [53.6, -113.4]]))

    def test_non_cast_shape_updates_geometry_only(self):
        # A plain custom_shape (not a caster) gets its outline rewritten but must
        # NOT acquire a canopy_radius_m, so it never becomes a keep-out zone.
        p = new_project("t")
        p["features"].append({
            "type": "Feature",
            "geometry": {"type": "Polygon", "coordinates": [[
                [-113.5, 53.5], [-113.499, 53.5], [-113.499, 53.501],
                [-113.5, 53.501], [-113.5, 53.5]]]},
            "properties": {"element_type": "custom_shape", "shape_id": "s1"},
        })
        new = [[53.50, -113.50], [53.50, -113.48], [53.52, -113.48]]
        self.assertTrue(update_shape_geometry(p, "s1", new))
        props = p["features"][0]["properties"]
        self.assertNotIn("canopy_radius_m", props)      # still not a keep-out
        ring = p["features"][0]["geometry"]["coordinates"][0]
        self.assertEqual(ring[0], ring[-1])             # rewritten + re-closed

    def test_area_m2_refreshed_after_edit(self):
        # Reshaping the outline must refresh the stored area so the readout/tooltip
        # don't go stale. A ~10 m square is ~100 m².
        p = new_project("t")
        p["features"].append({
            "type": "Feature",
            "geometry": {"type": "Polygon", "coordinates": [[
                [-113.5, 53.5], [-113.5, 53.5], [-113.5, 53.5]]]},
            "properties": {"element_type": "custom_shape", "shape_id": "s1",
                           "area_m2": 1.0},
        })
        half = 5.0
        dlat = half / 111320.0
        dlng = half / (111320.0 * math.cos(math.radians(53.5)))
        square = [[53.5 - dlat, -113.5 - dlng], [53.5 - dlat, -113.5 + dlng],
                  [53.5 + dlat, -113.5 + dlng], [53.5 + dlat, -113.5 - dlng]]
        self.assertTrue(update_shape_geometry(p, "s1", square))
        self.assertAlmostEqual(
            p["features"][0]["properties"]["area_m2"], 100.0, delta=2.0)

    def test_osm_building_round_trips_as_shape(self):
        p = new_project("t")
        p["features"].append(self._osm_building())
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, "t.perma.geojson")
            save_project(p, path)
            reloaded = load_project(path)
        shapes = project_to_map_data(reloaded)["shapes"]
        self.assertEqual(len(shapes), 1)
        self.assertEqual(shapes[0]["shape_id"], "shape_osm_0")
        self.assertEqual(shapes[0]["height_m"], 6.0)


class TestSchemaVersionStable(unittest.TestCase):
    """If anyone bumps SCHEMA_VERSION, they should also touch the round-trip
    tests above — this assertion is a tripwire prompting that thought."""

    def test_schema_version_value(self):
        # 1.9 (V2.22): plant features carry a stable feature_id (additive;
        # legacy files keep working through the coordinate fallback —
        # see tests/test_project_store.py TestFeatureIdentity).
        self.assertEqual(SCHEMA_VERSION, "1.9")

    def test_existing_feature_types_round_trip(self):
        # The new shade-caster features must survive save → reload, and the
        # loader must tolerate them (it ignores unknown element_types).
        import json
        import tempfile
        from src.project import save_project, load_project, project_to_map_data
        p = new_project("t")
        p["features"].append({
            "type": "Feature",
            "geometry": {"type": "Point", "coordinates": [-113.5, 53.5]},
            "properties": {"element_type": "existing_tree", "height_m": 8.0,
                           "canopy_radius_m": 3.0},
        })
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, "t.perma.geojson")
            save_project(p, path)
            reloaded = load_project(path)
        ets = [f["properties"]["element_type"]
               for f in reloaded["features"]]
        self.assertIn("existing_tree", ets)
        # loader doesn't crash on the unknown type
        project_to_map_data(reloaded)

    def test_site_photo_and_field_notes_round_trip(self):
        # 1.8 additions: a site_photo feature (F24) and a field_notes properties
        # block (F6) must survive save → reload, and the map loader must tolerate
        # the new feature type (it isn't a map shape).
        import tempfile
        from src.project import save_project, load_project, project_to_map_data
        from src import site_photo, field_notes
        p = new_project("t")
        site_photo.set_feature(p, site_photo.build_feature(
            image="data:image/jpeg;base64,QUJD",
            center={"lat": 53.5, "lng": -113.5}, width_m=30.0, aspect=0.75))
        field_notes.set_field_notes(p, {
            "observations": {"water_pools": {"checked": True, "note": "NE corner"}},
            "free_text": "clay near the fence"})
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, "t.perma.geojson")
            save_project(p, path)
            reloaded = load_project(path)
        # site_photo feature survives and is recoverable
        self.assertIsNotNone(site_photo.feature_from_project(reloaded))
        # field notes survive
        fn = field_notes.get_field_notes(reloaded)
        self.assertEqual(fn["observations"]["water_pools"]["note"], "NE corner")
        # loader doesn't crash and doesn't mistake the photo for a drawn shape
        md = project_to_map_data(reloaded)
        self.assertEqual(md["shapes"], [])


if __name__ == "__main__":
    unittest.main()
