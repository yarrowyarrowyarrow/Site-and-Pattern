"""
tests/test_map_js.py

Unit tests for src/map_js.py — the typed JS-string-builder catalogue
that replaces the f-string-soup in src/map_widget.py and the direct
``self.map_widget.run_js(...)`` calls scattered through src/app.py.

The builders are pure (no Qt, no I/O), so this whole suite runs without
PyQt6. The tests cover three properties for every builder:

  1. The right JS entry-point name appears in the output (catches typos
     and silent JS renames).
  2. Boolean / string / dict args are escaped through JSON, never via
     raw f-string interpolation (catches injection from quote-bearing
     plant names, label text, etc.).
  3. The argument order matches the JS function signature in
     html/map.html.

There is also a presence test that walks ``html/map.html`` and asserts
every JS function name we name-drop in a builder actually exists on the
JS side — a tripwire for accidental drift.
"""

import json
import os
import re
import sys
import unittest
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import src.map_js as mj  # noqa: E402


_HTML_PATH = Path(__file__).resolve().parent.parent / "html" / "map.html"


class TestEscapeHelpers(unittest.TestCase):

    def test_jsbool(self):
        self.assertEqual(mj._jsbool(True), "true")
        self.assertEqual(mj._jsbool(False), "false")

    def test_jsstr_escapes_quotes(self):
        # A plant name with an apostrophe must not break out of the JS
        # string literal it lands in.
        out = mj._jsstr("Saskatoon's Berry")
        # json.dumps wraps in double quotes and escapes inner quotes
        # as needed — both shapes are acceptable for our purposes.
        self.assertTrue(out.startswith('"'))
        self.assertTrue(out.endswith('"'))
        # And it round-trips.
        self.assertEqual(json.loads(out), "Saskatoon's Berry")

    def test_jsstr_escapes_backslash_and_newline(self):
        for s in ("path\\with\\slashes", "line1\nline2", "tab\there"):
            self.assertEqual(json.loads(mj._jsstr(s)), s)

    def test_jslit_handles_int_float_dict(self):
        self.assertEqual(mj._jslit(5), "5")
        self.assertEqual(mj._jslit(2.5), "2.5")
        self.assertEqual(mj._jslit({"a": 1}), '{"a": 1}')

    def test_jsobj_double_encodes(self):
        out = mj._jsobj({"common_name": "Yarrow"})
        # JSON.parse(<single string literal>) — the inner JSON is itself
        # a quoted string in the outer JS source.
        self.assertTrue(out.startswith("JSON.parse("))
        self.assertTrue(out.endswith(")"))
        inner_literal = out[len("JSON.parse("):-1]
        # The inner literal is a JSON-encoded string whose value is the
        # original JSON object encoded as JSON.
        parsed_once = json.loads(inner_literal)
        parsed_twice = json.loads(parsed_once)
        self.assertEqual(parsed_twice, {"common_name": "Yarrow"})


# ── Sanity: every JS name we use exists on the JS side ──────────────────────

class TestJsEntryPointsExist(unittest.TestCase):
    """Walk html/map.html once; assert every JS function our builders
    name actually has a JS definition. Acts as drift detection — if
    someone renames ``placePlantMarker`` to ``placeMarker`` in map.html
    without touching map_js.py, this fails."""

    @classmethod
    def setUpClass(cls):
        # V1.64: the map's JS lives in html/map/*.js (classic scripts the
        # 230-line map.html loads in order); definitions may sit in any of
        # them, so the walk covers the shell plus every split file.
        cls.html = _HTML_PATH.read_text(encoding="utf-8")
        for js in sorted((_HTML_PATH.parent / "map").glob("*.js")):
            cls.html += "\n" + js.read_text(encoding="utf-8")

    JS_NAMES = [
        "setMode",
        "cancelDraw", "clearMeasure", "clearAll", "clearSelection",
        "deleteSelected", "toggleLegend",
        "setSatelliteVisible", "setBoundaryVisible", "setMeasureVisible",
        "setPlantsVisible", "setLabelsVisible", "setCanopyVisible",
        "setSatelliteOffset",
        "setView", "setZoomSensitivity", "setGridStyle", "setSnapEnabled",
        "loadBoundary",
        "loadPlantMarker", "placePlantMarker", "setPlantGroupForLatest",
        "updateMarkerColor", "placeAnnotation", "clearAnnotations",
        "placeSitePin", "clearSitePin", "setSitePinDropMode",
        "loadStructure", "undoStructureAt",
        "loadHedgerow", "undoHedgerowById",
        "loadShape", "undoCustomShapeById",
        "drawSunPath", "clearSunPath",
        "drawSectors", "clearSectors",
        "drawWindOverlay", "clearWindOverlay",
        "setSeasonView", "setTimelineYearByPlantId",
        "clearContours", "undoLastContour", "finishContour",
        "emitTerrainBboxFromViewport", "emitTerrainBboxFromBoundary",
        "drawAutoContours", "drawSlopeOverlay", "setSlopeOverlayOpacity",
        "clearAutoTerrain",
        "drawShadeOverlay", "setShadeOverlayOpacity", "clearShadeOverlay",
        "drawShadeZones", "setShadeZonesVisible", "clearShadeZones",
        "_removeBoundaryEntry",
        # Globals touched by the inline IIFEs:
        "plantMarkers", "plantLabels",
        "structureMarkers", "hedgerowLayers", "shapeLayers",
        "contourPoints", "currentContour",
    ]

    def test_every_name_is_defined_in_map_html(self):
        missing = []
        for name in self.JS_NAMES:
            # Functions appear as `function name(`, `name = function`,
            # `var name = function`, or in object-literal form. Globals
            # appear as `var name` / `let name` / `const name` /
            # assignments like `name = {}`.
            patterns = [
                rf"\bfunction\s+{re.escape(name)}\s*\(",
                rf"\b{re.escape(name)}\s*=\s*function\b",
                rf"\bvar\s+{re.escape(name)}\b",
                rf"\blet\s+{re.escape(name)}\b",
                rf"\bconst\s+{re.escape(name)}\b",
                rf"\bwindow\.{re.escape(name)}\b",
            ]
            if not any(re.search(p, self.html) for p in patterns):
                missing.append(name)
        if missing:
            self.fail(
                "JS entry points named in map_js.py but not found in "
                f"html/map.html: {missing}"
            )


# ── Builder behaviour ───────────────────────────────────────────────────────

class TestModeBuilders(unittest.TestCase):

    def test_set_mode_simple(self):
        self.assertEqual(mj.set_mode("sun_anchor"),
                         'setMode("sun_anchor");')

    def test_set_mode_escapes_quotes_in_name(self):
        # Mode names don't carry quotes today, but the builder mustn't
        # care.
        out = mj.set_mode('weird"name')
        self.assertIn(r'\"', out)

    def test_set_mode_with_payload(self):
        out = mj.set_mode_with_payload("plant", {"id": 42})
        self.assertIn('setMode("plant"', out)
        self.assertIn("JSON.parse(", out)

    def test_cancel_draw(self):
        self.assertEqual(mj.cancel_draw(), "cancelDraw();")


class TestVisibilityToggles(unittest.TestCase):

    def test_each_toggle_produces_lowercase_bool(self):
        for builder, js_name in [
            (mj.set_satellite_visible, "setSatelliteVisible"),
            (mj.set_boundary_visible, "setBoundaryVisible"),
            (mj.set_measure_visible, "setMeasureVisible"),
            (mj.set_plants_visible, "setPlantsVisible"),
            (mj.set_labels_visible, "setLabelsVisible"),
            (mj.set_canopy_visible, "setCanopyVisible"),
        ]:
            self.assertEqual(builder(True), f"{js_name}(true);")
            self.assertEqual(builder(False), f"{js_name}(false);")

    def test_set_structures_visible_inlines_three_layer_loops(self):
        out = mj.set_structures_visible(True)
        for layer in ("structureMarkers", "hedgerowLayers", "shapeLayers"):
            self.assertIn(layer, out)
        # Bool must be lowercased so JS doesn't ReferenceError on `True`.
        self.assertIn("if (true)", out)
        self.assertNotIn("True", out)

    def test_set_structures_visible_false(self):
        out = mj.set_structures_visible(False)
        self.assertIn("if (false)", out)

    def test_set_satellite_offset_emits_metres(self):
        self.assertEqual(mj.set_satellite_offset(-4.0, 2.5),
                         "setSatelliteOffset(-4.0, 2.5);")
        self.assertEqual(mj.set_satellite_offset(0, 0),
                         "setSatelliteOffset(0.0, 0.0);")

    def test_shade_zones_builders(self):
        cells = [{"lat": 53.5, "lng": -113.5, "tag": "full_sun"}]
        out = mj.draw_shade_zones(cells, 0.0001, 0.0002, 0.4)
        self.assertTrue(out.startswith("drawShadeZones("))
        self.assertIn("full_sun", out)
        self.assertIn("dLat", out)
        self.assertIn("0.0001", out)
        self.assertEqual(mj.set_shade_zones_visible(True),
                         "setShadeZonesVisible(true);")
        self.assertEqual(mj.clear_shade_zones(), "clearShadeZones();")


class TestClears(unittest.TestCase):

    def test_clears(self):
        self.assertEqual(mj.clear_measure(),  "clearMeasure();")
        self.assertEqual(mj.clear_all(),      "clearAll();")
        self.assertEqual(mj.clear_selection(),"clearSelection();")
        self.assertEqual(mj.delete_selected(),"deleteSelected();")
        self.assertEqual(mj.toggle_legend(),  "toggleLegend();")


class TestMapView(unittest.TestCase):

    def test_set_view(self):
        self.assertEqual(mj.set_view(53.5, -113.5, 17),
                         "setView(53.5, -113.5, 17);")

    def test_set_view_default_zoom(self):
        out = mj.set_view(0, 0)
        self.assertIn("setView(", out)
        self.assertTrue(out.endswith(", 14);"))

    def test_set_zoom_sensitivity_quotes_level(self):
        self.assertEqual(mj.set_zoom_sensitivity("coarse"),
                         'setZoomSensitivity("coarse");')

    def test_set_grid_style(self):
        out = mj.set_grid_style("#22aa55", 0.45)
        self.assertEqual(out, 'setGridStyle("#22aa55", 0.45);')

    def test_set_snap_enabled(self):
        self.assertEqual(mj.set_snap_enabled(True, 1.5),
                         "setSnapEnabled(true, 1.5);")

    def test_crosshair_cursor(self):
        out = mj.set_crosshair_cursor()
        self.assertIn("'crosshair'", out)


class TestBoundaries(unittest.TestCase):

    def test_load_boundary_double_encodes(self):
        out = mj.load_boundary({"id": "b_1", "points": [[53.5, -113.5]]})
        # loadBoundary takes a JSON *string* (it parses it itself) plus a
        # trailing fit flag (default true → recenter on the boundary), so the
        # payload appears once-encoded as a JS string literal, then ", true".
        self.assertTrue(out.startswith("loadBoundary("))
        m = re.match(r'loadBoundary\((.*), (true|false)\);$', out)
        self.assertIsNotNone(m)
        inner = m.group(1)
        # `inner` is a JSON string whose value is a JSON-encoded dict.
        parsed_once = json.loads(inner)
        parsed_twice = json.loads(parsed_once)
        self.assertEqual(parsed_twice["id"], "b_1")
        self.assertEqual(m.group(2), "true")          # default recenters

    def test_load_boundary_fit_false(self):
        # Undo/redo re-renders pass fit=False so the camera doesn't jump.
        out = mj.load_boundary({"id": "b_1", "points": [[53.5, -113.5]]},
                               fit=False)
        self.assertTrue(out.rstrip().endswith(", false);"))

    def test_undo_boundary_quotes_id(self):
        out = mj.undo_boundary("b_42")
        self.assertIn('_removeBoundaryEntry("b_42")', out)
        self.assertIn("typeof _removeBoundaryEntry === 'function'", out)


class TestPlantMarkers(unittest.TestCase):

    def test_place_plant_marker_with_color_and_group(self):
        out = mj.place_plant_marker(
            7, "Yarrow", 53.5, -113.5,
            spacing_m=0.3, plant_type="herb",
            color="#ff0000", group_id="pg_abc",
        )
        self.assertIn("placePlantMarker(7,", out)
        self.assertIn('"Yarrow"', out)
        self.assertIn("53.5, -113.5", out)
        self.assertIn('"herb"', out)
        self.assertIn('"#ff0000"', out)
        self.assertIn('"pg_abc"', out)
        self.assertNotIn("null, null", out)

    def test_place_plant_marker_omits_color_and_group(self):
        out = mj.place_plant_marker(7, "Yarrow", 53.5, -113.5)
        # Missing color and group_id come through as JS `null`, not the
        # Python literal `None`.
        self.assertIn("null, null", out)
        self.assertNotIn("None", out)

    def test_place_plant_marker_escapes_quote_in_name(self):
        # The whole reason we use json.dumps instead of repr — a name
        # with an apostrophe must not break the surrounding JS.
        out = mj.place_plant_marker(7, "Saskatoon's Berry", 0, 0)
        self.assertIn("Saskatoon's Berry", out)
        # And the result is parseable as a complete JS function call —
        # no stray quotes.
        self.assertTrue(out.endswith(");"))

    def test_place_plant_marker_with_community_id(self):
        out = mj.place_plant_marker(
            7, "Yarrow", 53.5, -113.5,
            group_id="pg_abc", community_id="53.5_-113.5",
        )
        # community_id is the trailing JS argument.
        self.assertIn('"pg_abc", "53.5_-113.5");', out)

    def test_place_plant_marker_omits_community_id(self):
        out = mj.place_plant_marker(7, "Yarrow", 53.5, -113.5, group_id="pg_abc")
        # Missing community_id comes through as JS `null`, not Python `None`.
        self.assertIn('"pg_abc", null);', out)
        self.assertNotIn("None", out)

    def test_load_plant_marker_same_shape(self):
        out = mj.load_plant_marker(7, "Yarrow", 1, 2)
        self.assertTrue(out.startswith("loadPlantMarker(7,"))

    def test_load_plant_marker_passes_community_id(self):
        out = mj.load_plant_marker(
            7, "Yarrow", 1, 2, group_id="pg_x", community_id="1.0_2.0",
        )
        self.assertIn('"pg_x", "1.0_2.0");', out)

    def test_set_plant_group_for_latest(self):
        out = mj.set_plant_group_for_latest(7, 1.0, 2.0, "pg_x")
        self.assertEqual(out,
                         'setPlantGroupForLatest(7, 1.0, 2.0, "pg_x");')

    def test_update_marker_color(self):
        out = mj.update_marker_color(7, "#00ff00")
        self.assertEqual(out, 'updateMarkerColor(7, "#00ff00");')

    def test_place_annotation(self):
        out = mj.place_annotation("a_1", 1.0, 2.0, "Note <here>")
        self.assertIn('"a_1"', out)
        self.assertIn('"Note <here>"', out)
        self.assertIn("1.0, 2.0", out)


class TestPlantUndoBuilders(unittest.TestCase):
    """The inline IIFEs are still strings, but they're typed strings —
    invariants worth pinning."""

    def test_undo_place_plant_embeds_id_and_coords(self):
        out = mj.undo_place_plant(7, 53.5, -113.5)
        self.assertIn("plantMarkers", out)
        self.assertIn("=== 7", out)
        self.assertIn("- 53.5", out)
        self.assertIn("- -113.5", out)

    def test_revert_plant_position_swaps_old_and_new(self):
        out = mj.revert_plant_position(7, 1.0, 2.0, 10.0, 20.0)
        # The search clause matches the *new* (post-drag) position so
        # we find the right marker, then we setLatLng to the *old* one.
        self.assertIn("- 1.0", out)   # search: from_lat
        self.assertIn("- 2.0", out)   # search: from_lng
        self.assertIn("[10.0, 20.0]", out)  # target: to_lat, to_lng


class TestSitePin(unittest.TestCase):

    def test_place_site_pin_default_label(self):
        out = mj.place_site_pin(53.5, -113.5)
        self.assertIn("placeSitePin(53.5, -113.5,", out)
        self.assertIn('""', out)

    def test_place_site_pin_escapes_label(self):
        out = mj.place_site_pin(0, 0, 'My "Garden" Plot')
        self.assertIn(r'\"Garden\"', out)

    def test_clear_site_pin(self):
        self.assertEqual(mj.clear_site_pin(), "clearSitePin(false);")

    def test_set_site_pin_drop_mode(self):
        self.assertEqual(mj.set_site_pin_drop_mode(True),
                         "setSitePinDropMode(true);")


class TestStructuresHedgerowsShapes(unittest.TestCase):

    def test_load_structure(self):
        out = mj.load_structure({"kind": "bee_hotel"}, 53.5, -113.5)
        self.assertIn("loadStructure(JSON.parse(", out)
        self.assertIn("53.5, -113.5", out)

    def test_undo_structure_at(self):
        out = mj.undo_structure_at("s_1", 1.0, 2.0)
        self.assertEqual(out, 'undoStructureAt("s_1", 1.0, 2.0);')

    def test_load_hedgerow(self):
        out = mj.load_hedgerow({"id": "h_1"})
        self.assertTrue(out.startswith("loadHedgerow(JSON.parse("))

    def test_undo_hedgerow_by_id_quotes(self):
        self.assertEqual(mj.undo_hedgerow_by_id("h_2"),
                         'undoHedgerowById("h_2");')

    def test_load_shape(self):
        out = mj.load_shape({"shape_type": "Pond"})
        self.assertTrue(out.startswith("loadShape(JSON.parse("))

    def test_undo_custom_shape_by_id_quotes(self):
        self.assertEqual(mj.undo_custom_shape_by_id("sh_3"),
                         'undoCustomShapeById("sh_3");')


class TestOverlays(unittest.TestCase):

    def test_draw_sun_path_without_anchor(self):
        out = mj.draw_sun_path({"hours": [9, 12, 15]})
        self.assertTrue(out.startswith("drawSunPath(JSON.parse("))
        self.assertFalse(",  ," in out)  # no stray separators

    def test_draw_sun_path_with_anchor(self):
        out = mj.draw_sun_path({"hours": []}, lat=53.5, lng=-113.5)
        self.assertIn(", 53.5, -113.5", out)

    def test_draw_sectors_pair(self):
        self.assertTrue(mj.draw_sectors({}).startswith("drawSectors(JSON.parse("))
        self.assertIn(", 1.0, 2.0", mj.draw_sectors({}, 1.0, 2.0))

    def test_clear_overlays(self):
        self.assertEqual(mj.clear_sun_path(), "clearSunPath();")
        self.assertEqual(mj.clear_sectors(), "clearSectors();")
        self.assertEqual(mj.clear_wind_overlay(), "clearWindOverlay();")

    def test_draw_wind_overlay(self):
        out = mj.draw_wind_overlay({"speed_kts": 8})
        self.assertTrue(out.startswith("drawWindOverlay(JSON.parse("))

    def test_set_season_view(self):
        out = mj.set_season_view("July", {"7": True, "42": False})
        self.assertIn('"July"', out)
        self.assertIn('"7": true', out)

    def test_set_timeline_year_by_plant_id(self):
        out = mj.set_timeline_year_by_plant_id(5, {"7": 0.4})
        self.assertIn("setTimelineYearByPlantId(5", out)


class TestContoursAndAutoTerrain(unittest.TestCase):

    def test_clear_contours(self):
        self.assertEqual(mj.clear_contours(), "clearContours();")

    def test_undo_last_contour(self):
        self.assertEqual(mj.undo_last_contour(2.5),
                         "undoLastContour(2.5);")

    def test_restore_contour_primes_globals(self):
        out = mj.restore_contour({"points": [[1, 2]], "elevation_m": 670})
        # Primes the JS-side drawing globals, calls finishContour,
        # then clears them.
        for token in ("contourPoints = d.points", "currentContour = d",
                      "finishContour()", "contourPoints = []"):
            self.assertIn(token, out)

    def test_terrain_bbox_requests(self):
        self.assertEqual(mj.request_terrain_viewport(),
                         "emitTerrainBboxFromViewport();")
        self.assertEqual(mj.request_terrain_boundary_bbox(),
                         "emitTerrainBboxFromBoundary();")

    def test_draw_auto_contours_payload_shape(self):
        out = mj.draw_auto_contours(
            [{"elevation_m": 670, "segments": []}],
            color="#5d4037",
            show_labels=False,
        )
        self.assertTrue(out.startswith("drawAutoContours(JSON.parse("))
        # Boolean stays a JSON-encoded bool, not Python's True/False.
        self.assertIn("false", out)
        self.assertNotIn("False", out)

    def test_draw_slope_overlay_payload(self):
        out = mj.draw_slope_overlay(
            "data:image/png;base64,iVBORw0KGgo=",
            {"north": 53.6, "south": 53.5, "east": -113.4, "west": -113.5},
            opacity=0.7,
        )
        self.assertTrue(out.startswith("drawSlopeOverlay(JSON.parse("))

    def test_set_slope_overlay_opacity_coerces_float(self):
        out = mj.set_slope_overlay_opacity(1)  # int input
        self.assertEqual(out, "setSlopeOverlayOpacity(1.0);")

    def test_clear_auto_terrain(self):
        self.assertEqual(mj.clear_auto_terrain(), "clearAutoTerrain();")


class TestSplatOrthoOverlay(unittest.TestCase):

    def test_draw_splat_ortho_overlay_payload(self):
        out = mj.draw_splat_ortho_overlay(
            "data:image/png;base64,iVBORw0KGgo=",
            {"north": 53.6, "south": 53.5, "east": -113.4, "west": -113.5},
            opacity=0.9,
        )
        self.assertTrue(out.startswith("drawSplatOrthoOverlay(JSON.parse("))

    def test_set_splat_ortho_visible_is_json_bool(self):
        self.assertEqual(mj.set_splat_ortho_visible(True),
                         "setSplatOrthoVisible(true);")
        self.assertEqual(mj.set_splat_ortho_visible(False),
                         "setSplatOrthoVisible(false);")

    def test_set_splat_ortho_opacity_coerces_float(self):
        self.assertEqual(mj.set_splat_ortho_opacity(1),
                         "setSplatOrthoOpacity(1.0);")

    def test_clear_splat_ortho(self):
        self.assertEqual(mj.clear_splat_ortho(), "clearSplatOrtho();")


class TestWindShadowBuilders(unittest.TestCase):

    def test_set_wind_casters_json(self):
        out = mj.set_wind_casters([{"lat": 53.5, "lng": -113.5, "height_m": 6}])
        self.assertTrue(out.startswith("setWindCasters(JSON.parse("))

    def test_set_wind_angle_live_float(self):
        self.assertEqual(mj.set_wind_angle_live(270), "setWindAngleLive(270.0);")

    def test_draw_merged_wind_shelter_json(self):
        out = mj.draw_merged_wind_shelter(
            {"bands": [{"strength": "strong", "rings": []}], "wind_from_deg": 90})
        self.assertTrue(out.startswith("drawMergedWindShelter(JSON.parse("))

    def test_visibility_and_clear(self):
        self.assertEqual(mj.set_wind_shadow_visible(True),
                         "setWindShadowVisible(true);")
        self.assertEqual(mj.clear_wind_shadow(), "clearWindShadow();")


class TestInvalidateSize(unittest.TestCase):
    """The invalidate_size string is load-bearing — see the block comment
    in src/map_widget.py. Pin its essential parts."""

    def test_contains_load_bearing_reflow_reads(self):
        out = mj.invalidate_size()
        # Reflow-forcing reads (do not remove from the JS side).
        self.assertIn("clientWidth", out)
        self.assertIn("clientHeight", out)
        # The two console.log calls bracket invalidateSize.
        self.assertEqual(out.count("console.log"), 2)
        self.assertIn("map.invalidateSize(false)", out)


if __name__ == "__main__":
    unittest.main()
