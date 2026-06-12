"""
tests/test_shade.py

V1.51 — time-of-day / season shade and the shade overlay encoding. Pure
geometry + a stdlib PNG encode; no Qt, no network (the overlay payload's
elevation fetch is exercised only via a monkeypatched grid).
"""

import math
import os
import sys
import unittest
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import src.shade as shade  # noqa: E402

_N = 9
_BBOX = {"north": 53.50020, "south": 53.49980,
         "east": -113.49966, "west": -113.50034}
_ELEV = {"grid": [[100.0] * _N for _ in range(_N)], "rows": _N, "cols": _N,
         "bbox": _BBOX}
_CLAT = (_BBOX["north"] + _BBOX["south"]) / 2
_CLNG = (_BBOX["east"] + _BBOX["west"]) / 2
_TREE = [{"lat": _CLAT, "lng": _CLNG, "height_m": 12.0, "radius_m": 4.0}]


def _west(g):
    return sum(g[r][c] for r in range(_N) for c in range(0, 4))


def _east(g):
    return sum(g[r][c] for r in range(_N) for c in range(5, _N))


def _north(g):
    return sum(g[r][c] for r in range(0, 4) for c in range(_N))


def _south(g):
    return sum(g[r][c] for r in range(5, _N) for c in range(_N))


class TestSeasonAverage(unittest.TestCase):
    def test_shadow_falls_north(self):
        g = shade.shade_grid(_TREE, _ELEV)
        self.assertGreater(_north(g), _south(g))
        self.assertGreater(_north(g), 0.0)

    def test_no_casters_zero(self):
        g = shade.shade_grid([], _ELEV)
        self.assertTrue(all(v == 0.0 for row in g for v in row))

    def test_custom_dates_hours_accepted(self):
        # A single noon sample still yields a northward shadow.
        g = shade.shade_grid(_TREE, _ELEV, dates=[(6, 21)], hours=[12])
        self.assertGreater(_north(g), _south(g))


class TestTimeOfDay(unittest.TestCase):
    def test_morning_shadow_west(self):
        g = shade.shade_grid_at(_TREE, _ELEV, datetime(2025, 6, 21, 9, 0))
        self.assertGreater(_west(g), _east(g))

    def test_afternoon_shadow_east(self):
        g = shade.shade_grid_at(_TREE, _ELEV, datetime(2025, 6, 21, 15, 0))
        self.assertGreater(_east(g), _west(g))

    def test_evening_shadow_east(self):
        # Regression: the late-afternoon sun is in the west, so shadows fall
        # EAST. Before the solar_time wrap fix, 18:00 (which crosses midnight
        # UTC after the -lng/15 offset) mirrored the shadow back to the west.
        g = shade.shade_grid_at(_TREE, _ELEV, datetime(2025, 6, 21, 18, 0))
        self.assertGreater(_east(g), _west(g))

    def test_night_no_shade(self):
        g = shade.shade_grid_at(_TREE, _ELEV, datetime(2025, 6, 21, 2, 0))
        self.assertTrue(all(v == 0.0 for row in g for v in row))


class TestShadeRamp(unittest.TestCase):
    def test_rgba_dimensions(self):
        g = shade.shade_grid(_TREE, _ELEV)
        rgba, w, h = shade.shade_ramp_rgba(g)
        self.assertEqual(w, _N)
        self.assertEqual(h, _N)
        self.assertEqual(len(rgba), w * h * 4)

    def test_lit_cells_transparent(self):
        # A fully-lit grid encodes to all-transparent (alpha 0).
        lit = [[0.0] * 2 for _ in range(2)]
        rgba, w, h = shade.shade_ramp_rgba(lit)
        alphas = [rgba[i * 4 + 3] for i in range(w * h)]
        self.assertTrue(all(a == 0 for a in alphas))

    def test_deep_shade_opaque(self):
        deep = [[1.0]]
        rgba, _, _ = shade.shade_ramp_rgba(deep)
        self.assertGreater(rgba[3], 0)   # alpha > 0


class TestOverlayPayload(unittest.TestCase):
    def test_payload_from_monkeypatched_grid(self):
        # Avoid the network: feed a fixed elevation grid + a marked tree.
        import src.zoning as zoning
        orig = zoning.site_elevation_grid
        zoning.site_elevation_grid = lambda *a, **k: _ELEV
        try:
            project = {"features": [
                {"geometry": {"type": "Point", "coordinates": [_CLNG, _CLAT]},
                 "properties": {"element_type": "existing_tree",
                                "height_m": 12.0, "canopy_radius_m": 4.0}},
            ]}
            payload = shade.shade_overlay_payload(project, None, {})
            self.assertIsNotNone(payload)
            self.assertTrue(payload["data_url"].startswith(
                "data:image/png;base64,"))
            for k in ("south", "north", "west", "east"):
                self.assertIn(k, payload["bbox"])
        finally:
            zoning.site_elevation_grid = orig

    def test_payload_none_without_casters(self):
        import src.zoning as zoning
        orig = zoning.site_elevation_grid
        zoning.site_elevation_grid = lambda *a, **k: _ELEV
        try:
            payload = shade.shade_overlay_payload({"features": []}, None, {})
            self.assertIsNone(payload)     # nothing shaded → nothing to draw
        finally:
            zoning.site_elevation_grid = orig


class TestPolygonCaster(unittest.TestCase):
    """V1.53 — a drawn canopy_footprint polygon casts shade north of a
    southern sun, and casters_from_project parses it."""

    def _ring(self, half_m=2.0):
        dlat = half_m / 111320.0
        dlng = half_m / (111320.0 * math.cos(math.radians(_CLAT)))
        return [[_CLNG - dlng, _CLAT - dlat], [_CLNG + dlng, _CLAT - dlat],
                [_CLNG + dlng, _CLAT + dlat], [_CLNG - dlng, _CLAT + dlat],
                [_CLNG - dlng, _CLAT - dlat]]

    def test_canopy_footprint_parsed_as_caster(self):
        project = {"features": [
            {"geometry": {"type": "Polygon", "coordinates": [self._ring()]},
             "properties": {"element_type": "canopy_footprint",
                            "height_m": 10.0}},
        ]}
        casters = shade.casters_from_project(project)
        self.assertEqual(len(casters), 1)
        self.assertIn("footprint", casters[0])
        self.assertEqual(casters[0]["height_m"], 10.0)

    def test_custom_shape_requires_cast_shade_flag(self):
        ring = self._ring()
        without = {"features": [
            {"geometry": {"type": "Polygon", "coordinates": [ring]},
             "properties": {"element_type": "custom_shape", "height_m": 5.0}}]}
        self.assertEqual(shade.casters_from_project(without), [])
        with_flag = {"features": [
            {"geometry": {"type": "Polygon", "coordinates": [ring]},
             "properties": {"element_type": "custom_shape", "height_m": 5.0,
                            "cast_shade": True}}]}
        self.assertEqual(len(shade.casters_from_project(with_flag)), 1)

    def test_polygon_caster_shades_north(self):
        casters = [{"lat": _CLAT, "lng": _CLNG, "height_m": 12.0,
                    "radius_m": 3.0, "footprint": self._ring(2.0)}]
        g = shade.shade_grid(casters, _ELEV, dates=[(6, 21)], hours=[12])
        self.assertGreater(_north(g), _south(g))
        self.assertGreater(_north(g), 0.0)


class TestCasterKind(unittest.TestCase):
    """V1.59 — casters carry a ``kind`` so trees cast a tapering canopy shadow
    while buildings extrude. casters_from_project derives it from element_type /
    caster_kind, and the raster path tapers tree shadows."""

    def _ring(self, half_m=3.0):
        dlat = half_m / 111320.0
        dlng = half_m / (111320.0 * math.cos(math.radians(_CLAT)))
        return [[_CLNG - dlng, _CLAT - dlat], [_CLNG + dlng, _CLAT - dlat],
                [_CLNG + dlng, _CLAT + dlat], [_CLNG - dlng, _CLAT + dlat],
                [_CLNG - dlng, _CLAT - dlat]]

    def test_existing_tree_is_tree_kind(self):
        project = {"features": [
            {"geometry": {"type": "Point", "coordinates": [_CLNG, _CLAT]},
             "properties": {"element_type": "existing_tree",
                            "height_m": 8.0, "canopy_radius_m": 3.0}}]}
        self.assertEqual(
            shade.casters_from_project(project)[0]["kind"], "tree")

    def test_existing_building_is_building_kind(self):
        project = {"features": [
            {"geometry": {"type": "Point", "coordinates": [_CLNG, _CLAT]},
             "properties": {"element_type": "existing_building",
                            "height_m": 8.0, "canopy_radius_m": 4.0}}]}
        self.assertEqual(
            shade.casters_from_project(project)[0]["kind"], "building")

    def test_canopy_footprint_kind_follows_caster_kind(self):
        tree = {"features": [
            {"geometry": {"type": "Polygon", "coordinates": [self._ring()]},
             "properties": {"element_type": "canopy_footprint",
                            "height_m": 10.0, "caster_kind": "tree"}}]}
        bldg = {"features": [
            {"geometry": {"type": "Polygon", "coordinates": [self._ring()]},
             "properties": {"element_type": "canopy_footprint",
                            "height_m": 10.0}}]}
        self.assertEqual(shade.casters_from_project(tree)[0]["kind"], "tree")
        self.assertEqual(shade.casters_from_project(bldg)[0]["kind"],
                         "building")

    def test_raster_tree_shadow_smaller_than_building(self):
        # Force the raster (capsule) path so this runs with or without shapely;
        # the tree tapers, so it shades strictly fewer cells than an equal
        # building. Uses a finer local grid so the taper resolves.
        orig = shade._HAVE_SHAPELY
        shade._HAVE_SHAPELY = False
        try:
            n = 21
            bbox = {"north": 53.5005, "south": 53.4995,
                    "east": -113.4992, "west": -113.5008}
            elev = {"grid": [[100.0] * n for _ in range(n)], "rows": n,
                    "cols": n, "bbox": bbox}
            clat = (bbox["north"] + bbox["south"]) / 2
            clng = (bbox["east"] + bbox["west"]) / 2
            base = {"lat": clat, "lng": clng, "height_m": 12.0, "radius_m": 4.0}
            gt = shade.shade_grid([dict(base, kind="tree")], elev,
                                  dates=[(6, 21)], hours=[16])
            gb = shade.shade_grid([dict(base, kind="building")], elev,
                                  dates=[(6, 21)], hours=[16])
            tot = lambda g: sum(v for row in g for v in row)   # noqa: E731
            self.assertGreater(tot(gb), 0.0)
            self.assertLess(tot(gt), tot(gb))
        finally:
            shade._HAVE_SHAPELY = orig


@unittest.skipUnless(shade._HAVE_SHAPELY, "shapely not installed")
class TestShadowPolygonsPayload(unittest.TestCase):
    """V1.54 — the grid-independent vector shadow payload for the map overlay."""

    def _ring(self, half_m=4.0):
        dlat = half_m / 111320.0
        dlng = half_m / (111320.0 * math.cos(math.radians(_CLAT)))
        return [[_CLNG - dlng, _CLAT - dlat], [_CLNG + dlng, _CLAT - dlat],
                [_CLNG + dlng, _CLAT + dlat], [_CLNG - dlng, _CLAT + dlat],
                [_CLNG - dlng, _CLAT - dlat]]

    def _building_project(self, height_m=8.0):
        return {"features": [
            {"geometry": {"type": "Polygon", "coordinates": [self._ring()]},
             "properties": {"element_type": "existing_building",
                            "height_m": height_m}},
        ]}

    def test_none_when_no_casters(self):
        self.assertIsNone(
            shade.shadow_polygons_payload({"features": []}, None, {}))

    def test_instant_payload_has_polygons_north(self):
        # Summer-solstice noon: a small building still casts a real polygon.
        payload = shade.shadow_polygons_payload(
            self._building_project(), None, {},
            when=datetime(2025, 6, 21, 12, 0))
        self.assertIsNotNone(payload)
        self.assertTrue(payload["polygons"])
        pts = [pt for poly in payload["polygons"] for ring in poly for pt in ring]
        # Shadow reaches north of the building centre (sun is to the south).
        self.assertGreater(max(p[0] for p in pts), _CLAT)
        # bbox brackets the drawn rings.
        b = payload["bbox"]
        self.assertLessEqual(b["south"], min(p[0] for p in pts) + 1e-9)
        self.assertGreaterEqual(b["north"], max(p[0] for p in pts) - 1e-9)

    def test_low_sun_shadow_longer_than_noon(self):
        noon = shade.shadow_polygons_payload(
            self._building_project(), None, {},
            when=datetime(2025, 6, 21, 12, 0))
        evening = shade.shadow_polygons_payload(
            self._building_project(), None, {},
            when=datetime(2025, 6, 21, 18, 0))
        self.assertIsNotNone(noon)
        self.assertIsNotNone(evening)

        def _max_reach(p):
            # Longest distance (metres-ish) from the building centre to any
            # shadow vertex — direction-agnostic, since the evening sun throws
            # the shadow east, not north.
            cos = math.cos(math.radians(_CLAT))
            pts = [pt for poly in p["polygons"] for ring in poly for pt in ring]
            return max(math.hypot((q[0] - _CLAT),
                                  (q[1] - _CLNG) * cos) for q in pts)
        # Lower evening sun → longer shadow than the high noon sun.
        self.assertGreater(_max_reach(evening), _max_reach(noon))

    def test_typical_envelope_covers_instant(self):
        proj = self._building_project()
        envelope = shade.shadow_polygons_payload(proj, None, {}, when=None)
        instant = shade.shadow_polygons_payload(
            proj, None, {}, when=datetime(2025, 6, 21, 12, 0))
        self.assertIsNotNone(envelope)
        self.assertIsNotNone(instant)

        def _span(p):
            pts = [pt for poly in p["polygons"]
                   for ring in poly for pt in ring]
            lats = [q[0] for q in pts]
            lngs = [q[1] for q in pts]
            return (max(lats) - min(lats), max(lngs) - min(lngs))
        env_dlat, env_dlng = _span(envelope)
        ins_dlat, ins_dlng = _span(instant)
        # The all-day envelope is at least as wide/tall as a single moment.
        self.assertGreaterEqual(env_dlat, ins_dlat - 1e-9)
        self.assertGreaterEqual(env_dlng, ins_dlng - 1e-9)

    def test_none_without_shapely(self):
        orig = shade._HAVE_SHAPELY
        shade._HAVE_SHAPELY = False
        try:
            self.assertIsNone(
                shade.shadow_polygons_payload(self._building_project(), None, {}))
        finally:
            shade._HAVE_SHAPELY = orig

    def test_degenerate_ring_falls_back_to_radius_circle(self):
        # A caster whose footprint ring is collinear (shapely can't build a
        # polygon from it) must still cast via its radius circle, not silently
        # vanish — guards the V1.58 fallback in shadow_polygons_payload.
        d = 0.0001
        collinear = [[_CLNG - d, _CLAT], [_CLNG, _CLAT],
                     [_CLNG + d, _CLAT], [_CLNG - d, _CLAT]]   # all one line
        project = {"features": [
            {"geometry": {"type": "Polygon", "coordinates": [collinear]},
             "properties": {"element_type": "canopy_footprint",
                            "height_m": 8.0, "canopy_radius_m": 3.0}},
        ]}
        payload = shade.shadow_polygons_payload(
            project, None, {}, when=datetime(2025, 6, 21, 12, 0))
        self.assertIsNotNone(payload)            # caster wasn't dropped
        self.assertTrue(payload["polygons"])


class TestClassifyZoneTags(unittest.TestCase):
    """V1.53 — classify_zone_tags turns the shade grid into per-cell tag rows
    for the SQLite cache, without touching geometry."""

    def test_rows_have_tags_and_centroids(self):
        import src.zoning as zoning
        orig = zoning.site_elevation_grid
        zoning.site_elevation_grid = lambda *a, **k: _ELEV
        try:
            project = {"features": [
                {"geometry": {"type": "Point", "coordinates": [_CLNG, _CLAT]},
                 "properties": {"element_type": "existing_tree",
                                "height_m": 12.0, "canopy_radius_m": 4.0}},
            ]}
            rows = shade.classify_zone_tags(project, None, {})
            self.assertIsNotNone(rows)
            self.assertEqual(len(rows), _N * _N)
            valid = {"full_sun", "partial_shade", "full_shade"}
            for row in rows:
                self.assertIn(row["shade_tag"], valid)
                self.assertIn("centroid_lat", row)
                self.assertTrue(row["zone_id"].startswith("r"))
            # The tree shades some cells → at least one non-full-sun tag.
            self.assertTrue(any(r["shade_tag"] != "full_sun" for r in rows))
        finally:
            zoning.site_elevation_grid = orig

    def test_none_without_grid(self):
        import src.zoning as zoning
        orig = zoning.site_elevation_grid
        zoning.site_elevation_grid = lambda *a, **k: None
        try:
            self.assertIsNone(shade.classify_zone_tags({"features": []}, None, {}))
        finally:
            zoning.site_elevation_grid = orig


class TestBothPathsAgree(unittest.TestCase):
    """The circle fallback and the polygon path both return a same-shaped grid
    in [0, 1] with a northward shadow, so downstream consumers are unaffected
    by which path runs."""

    def _run(self, have_shapely):
        orig = shade._HAVE_SHAPELY
        shade._HAVE_SHAPELY = have_shapely
        try:
            return shade.shade_grid(_TREE, _ELEV, dates=[(6, 21)], hours=[12])
        finally:
            shade._HAVE_SHAPELY = orig

    def test_shape_and_range_both_paths(self):
        for have in (True, False):
            g = self._run(have)
            self.assertEqual(len(g), _N)
            self.assertEqual(len(g[0]), _N)
            self.assertTrue(all(0.0 <= v <= 1.0 for row in g for v in row))
            self.assertGreater(_north(g), _south(g))


class TestTerrainSelfShadow(unittest.TestCase):
    """V1.55 — the DEM horizon pass shades cells from terrain relief even with
    no footprint casters, and leaves flat sites bit-for-bit unchanged."""

    def _south_wall(self, height=80.0, base=100.0):
        # A tall E–W wall along the south edge (rows 7-8; row 0 = north). The
        # Edmonton sun stays in the southern sky, so the wall shades the ground
        # to its north at every sampled moment.
        grid = [[base] * _N for _ in range(_N)]
        for r in (7, 8):
            for c in range(_N):
                grid[r][c] = base + height
        return {"grid": grid, "rows": _N, "cols": _N, "bbox": _BBOX}

    def test_terrain_shades_without_any_casters(self):
        # No footprint casters at all — the shade comes purely from terrain.
        g = shade.shade_grid([], self._south_wall())
        self.assertTrue(any(v > 0.0 for row in g for v in row))

    def test_shadow_appears_just_north_of_the_wall(self):
        g = shade.shade_grid([], self._south_wall())
        # Row 6 sits one cell north of the southern wall → in its shadow.
        self.assertGreater(sum(g[6]), 0.0)

    def test_flat_grid_identical_with_or_without_terrain(self):
        # A flat site must be untouched by the terrain pass (back-compat).
        self.assertEqual(shade.shade_grid(_TREE, _ELEV, terrain=True),
                         shade.shade_grid(_TREE, _ELEV, terrain=False))

    def test_flat_no_casters_still_zero(self):
        self.assertTrue(
            all(v == 0.0 for row in shade.shade_grid([], _ELEV) for v in row))


if __name__ == "__main__":
    unittest.main()
