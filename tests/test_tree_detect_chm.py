"""
Tests for src/tree_detect_chm.py — canopy-height-map tree detection (V2.26).

The algorithm (variable-window local-maxima on real heights) is exercised on
synthetic canopy-height rasters — cones standing for tree crowns — so treetop
count, measured height, position and crown separation are checked against
ground truth with no network and no rasterio. The live Meta-CHM fetch is
injected as a fake reader (mirroring how the RGB detector's tile fetch is
stubbed).
"""

import math
import unittest

try:
    import numpy as np
    _HAVE_NUMPY = True
except ImportError:
    _HAVE_NUMPY = False

from src import tree_detect_chm as chm

_LAT, _LNG = 53.5, -113.3       # must work anywhere; a prairie acreage here


def _geo(px_m=1.0):
    """A north-up metric geotransform (world = metres E/N from origin) plus a
    to_lnglat that places the origin near (_LAT, _LNG). pixel (col,row) → world
    (col·px, −row·px); world → lat/lng via the cosLat metric."""
    gt = (0.0, px_m, 0.0, 0.0, 0.0, -px_m)
    cos_lat = math.cos(math.radians(_LAT))

    def to_lnglat(x, y):
        return (_LNG + x / (111320.0 * cos_lat), _LAT + y / 111320.0)
    return gt, to_lnglat


def _cone(arr, row_c, col_c, apex, radius_px):
    """Add a cone (height = apex·(1−d/radius)) into a 2D array, taking the max
    so overlapping cones merge like real touching crowns."""
    rows, cols = arr.shape
    r0, r1 = max(0, row_c - radius_px), min(rows, row_c + radius_px + 1)
    c0, c1 = max(0, col_c - radius_px), min(cols, col_c + radius_px + 1)
    for r in range(r0, r1):
        for c in range(c0, c1):
            d = math.hypot(r - row_c, c - col_c)
            if d <= radius_px:
                arr[r, c] = max(arr[r, c], apex * (1.0 - d / radius_px))
    return arr


def _px_of(top, gt, to_lnglat):
    """Ground distance (m) from a detected top to a known pixel apex center."""
    x, y = chm._pixel_to_xy(top[1] + 0.5, top[0] + 0.5, gt)
    lng, lat = to_lnglat(x, y)
    return lat, lng


@unittest.skipUnless(_HAVE_NUMPY, "numpy not installed")
class TestDetectTreetops(unittest.TestCase):
    def test_single_cone(self):
        gt, to_ll = _geo()
        arr = np.zeros((60, 60))
        _cone(arr, 30, 30, 12.0, 9)
        tops = chm.detect_treetops(arr, gt, to_ll)
        self.assertEqual(len(tops), 1)
        t = tops[0]
        self.assertAlmostEqual(t["height_m"], 12.0, delta=0.6)
        alat, alng = _px_of((30, 30), gt, to_ll)
        self.assertLess(chm._ground_m(alat, alng, t["lat"], t["lng"]), 2.5)
        self.assertEqual(t["source"], "canopy-height")
        self.assertIsNone(t["foliage"])
        self.assertGreater(t["radius_m"], 0.9)

    def test_two_separated_cones(self):
        gt, to_ll = _geo()
        arr = np.zeros((60, 80))
        _cone(arr, 30, 20, 12.0, 8)
        _cone(arr, 30, 60, 9.0, 7)
        tops = chm.detect_treetops(arr, gt, to_ll)
        self.assertEqual(len(tops), 2)
        heights = sorted(t["height_m"] for t in tops)
        self.assertAlmostEqual(heights[0], 9.0, delta=0.7)
        self.assertAlmostEqual(heights[1], 12.0, delta=0.7)

    def test_close_shorter_peak_is_suppressed(self):
        # Two peaks 3 px apart — the shorter falls inside the taller's crown
        # and merges into one tree (variable-window non-max suppression).
        gt, to_ll = _geo()
        arr = np.zeros((60, 60))
        _cone(arr, 30, 30, 13.0, 9)
        _cone(arr, 30, 33, 8.0, 6)
        tops = chm.detect_treetops(arr, gt, to_ll)
        self.assertEqual(len(tops), 1)
        self.assertAlmostEqual(tops[0]["height_m"], 13.0, delta=0.7)

    def test_min_height_filters_shrubs(self):
        gt, to_ll = _geo()
        arr = np.zeros((40, 40))
        _cone(arr, 20, 20, 2.4, 6)          # a 2.4 m shrub
        self.assertEqual(chm.detect_treetops(arr, gt, to_ll,
                                             min_height_m=3.0), [])
        # Lower the bar and it appears.
        self.assertEqual(len(chm.detect_treetops(arr, gt, to_ll,
                                                 min_height_m=1.0)), 1)

    def test_flat_ground_no_trees(self):
        gt, to_ll = _geo()
        self.assertEqual(chm.detect_treetops(np.zeros((30, 30)), gt, to_ll), [])
        self.assertEqual(
            chm.detect_treetops(np.full((30, 30), 1.0), gt, to_ll), [])

    def test_nan_and_negative_treated_as_ground(self):
        gt, to_ll = _geo()
        arr = np.zeros((50, 50))
        _cone(arr, 25, 25, 10.0, 8)
        arr[0, 0] = np.nan
        arr[1, 1] = -9999.0
        tops = chm.detect_treetops(arr, gt, to_ll)
        self.assertEqual(len(tops), 1)

    def test_pixel_size_scales_crowns(self):
        # A coarser raster (2 m/px) makes the same cone's crown ~2× wider in
        # metres — radius tracks ground scale, not pixel count.
        gt2, to_ll2 = _geo(px_m=2.0)
        arr = np.zeros((40, 40))
        _cone(arr, 20, 20, 12.0, 8)
        t2 = chm.detect_treetops(arr, gt2, to_ll2,
                                 pixel_size_m=2.0)[0]
        gt1, to_ll1 = _geo(px_m=1.0)
        t1 = chm.detect_treetops(arr, gt1, to_ll1, pixel_size_m=1.0)[0]
        self.assertAlmostEqual(t1["height_m"], t2["height_m"], delta=0.1)


@unittest.skipUnless(_HAVE_NUMPY, "numpy not installed")
@unittest.skipUnless(_HAVE_NUMPY, "numpy not installed")
class TestHybridAugment(unittest.TestCase):
    """The CHM+RGB hybrid: photo crowns split the clusters the smooth height
    map merges, each inheriting the nearest CHM top's measured height; crowns
    that are the same tree, or off confirmed canopy, are dropped."""

    def _m_east(self, lng, metres):
        return lng + metres / (111320.0 * math.cos(math.radians(_LAT)))

    def test_near_distinct_crown_is_added_with_chm_height(self):
        chm_tops = [{"lat": _LAT, "lng": _LNG, "height_m": 12.0,
                     "radius_m": 3.0}]
        # An RGB crown 5 m east — same cluster, distinct tree the CHM merged.
        rgb = [{"lat": _LAT, "lng": self._m_east(_LNG, 5.0), "radius_m": 2.5}]
        extra = chm._augment_with_rgb(chm_tops, rgb)
        self.assertEqual(len(extra), 1)
        self.assertEqual(extra[0]["height_m"], 12.0)      # measured from CHM
        self.assertIn("photo-split", extra[0]["detect_confidence"])

    def test_coincident_crown_is_dropped_as_same_tree(self):
        chm_tops = [{"lat": _LAT, "lng": _LNG, "height_m": 12.0,
                     "radius_m": 3.0}]
        rgb = [{"lat": _LAT, "lng": self._m_east(_LNG, 1.0), "radius_m": 2.5}]
        self.assertEqual(chm._augment_with_rgb(chm_tops, rgb), [])

    def test_far_crown_is_dropped_as_off_canopy(self):
        chm_tops = [{"lat": _LAT, "lng": _LNG, "height_m": 12.0,
                     "radius_m": 3.0}]
        rgb = [{"lat": _LAT, "lng": self._m_east(_LNG, 30.0), "radius_m": 2.5}]
        self.assertEqual(chm._augment_with_rgb(chm_tops, rgb), [])

    def test_detect_chm_runs_augmenter_and_reports_count(self):
        gt, to_ll = _geo()
        arr = np.zeros((60, 60))
        _cone(arr, 30, 30, 12.0, 9)
        bbox = self._bbox()

        def rgb_augment():
            # Place an RGB crown ~5 m east of the single CHM treetop.
            res = chm.detect_trees_chm(bbox, _reader=lambda b: (arr, gt, to_ll))
            t = res["trees"][0]
            return {"trees": [{"lat": t["lat"],
                               "lng": self._m_east(t["lng"], 5.0),
                               "radius_m": 2.5}]}

        res = chm.detect_trees_chm(bbox, _reader=lambda b: (arr, gt, to_ll),
                                   _rgb_augment=rgb_augment)
        self.assertEqual(res["hybrid_added"], 1)
        self.assertEqual(len(res["trees"]), 2)

    def _bbox(self):
        gt, to_ll = _geo()
        lng_w, lat_s = to_ll(-30, -90)
        lng_e, lat_n = to_ll(90, 30)
        return {"west": lng_w, "south": lat_s, "east": lng_e, "north": lat_n}


class TestTileIndex(unittest.TestCase):
    def _index(self):
        return {"type": "FeatureCollection", "features": [
            {"properties": {"quadkey": "0231301"},
             "geometry": {"type": "Polygon", "coordinates": [[
                 [-114.0, 53.0], [-113.0, 53.0],
                 [-113.0, 54.0], [-114.0, 54.0], [-114.0, 53.0]]]}},
            {"properties": {"quadkey": "9999999"},
             "geometry": {"type": "Polygon", "coordinates": [[
                 [10.0, 10.0], [11.0, 10.0],
                 [11.0, 11.0], [10.0, 11.0], [10.0, 10.0]]]}},
        ]}

    def test_bbox_matches_covering_tile_only(self):
        bbox = {"west": -113.31, "south": 53.49,
                "east": -113.29, "north": 53.51}
        qks = chm.quadkeys_for_bbox(bbox, self._index())
        self.assertEqual(qks, ["0231301"])

    def test_tile_url(self):
        self.assertTrue(chm._quadkey_tile_url("0231301").endswith(
            "/chm/0231301.tif"))
        self.assertIn("dataforgood-fb-data", chm._quadkey_tile_url("x"))


@unittest.skipUnless(_HAVE_NUMPY, "numpy not installed")
class TestDetectTreesChm(unittest.TestCase):
    def _reader(self):
        gt, to_ll = _geo()
        arr = np.zeros((60, 80))
        _cone(arr, 30, 20, 14.0, 8)
        _cone(arr, 30, 60, 8.0, 7)

        def reader(bbox):
            return arr, gt, to_ll
        return reader

    def test_end_to_end_with_injected_reader(self):
        # bbox must contain the cones' lat/lng (origin-anchored geo).
        gt, to_ll = _geo()
        lng_w, lat_s = to_ll(0, -60)
        lng_e, lat_n = to_ll(80, 0)
        bbox = {"west": lng_w - 0.001, "south": lat_s - 0.001,
                "east": lng_e + 0.001, "north": lat_n + 0.001}
        res = chm.detect_trees_chm(bbox, _reader=self._reader())
        self.assertIsNotNone(res)
        self.assertEqual(res["source"], "canopy-height")
        self.assertEqual(len(res["trees"]), 2)
        self.assertAlmostEqual(res["m_per_px"], 1.0, delta=0.05)
        for t in res["trees"]:
            self.assertEqual(t["source"], "canopy-height")
            self.assertGreaterEqual(t["height_m"], 3.0)

    def test_reader_none_returns_none(self):
        self.assertIsNone(chm.detect_trees_chm(
            {"west": -113.4, "south": 53.4, "east": -113.2, "north": 53.6},
            _reader=lambda b: None))

    def test_import_adds_and_messages(self):
        res = chm.detect_trees_chm(
            self._bbox(), _reader=self._reader())
        project = {"features": []}
        out = chm.import_chm_result(res, project)
        self.assertEqual(out["added"], 2)
        self.assertEqual(len(project["features"]), 2)
        props = project["features"][0]["properties"]
        self.assertEqual(props["element_type"], "existing_tree")
        self.assertEqual(props["source"], "canopy-height")
        self.assertIn("canopy-height map", out["message"])
        self.assertIn("measured", out["message"])

    def test_import_none_is_silent(self):
        out = chm.import_chm_result(None, {"features": []})
        self.assertEqual(out["added"], 0)
        self.assertEqual(out["message"], "")

    def _bbox(self):
        gt, to_ll = _geo()
        lng_w, lat_s = to_ll(0, -60)
        lng_e, lat_n = to_ll(80, 0)
        return {"west": lng_w - 0.001, "south": lat_s - 0.001,
                "east": lng_e + 0.001, "north": lat_n + 0.001}


if __name__ == "__main__":
    unittest.main()
