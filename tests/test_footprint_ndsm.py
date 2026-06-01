"""
tests/test_footprint_ndsm.py

V1.53 — the nDSM → footprint vectorizer (src/footprint_ndsm.py) and the
extracted-footprint → project-feature adder (src/footprint_extract.py).
The vectorizer core needs numpy + shapely (gated); the GeoTIFF reader (rasterio)
is not exercised here.
"""

import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import src.footprint_ndsm as fn          # noqa: E402
import src.footprint_extract as fe        # noqa: E402

# A north-up, 1 m/pixel geotransform mapping (col,row) → (x=col, y=-row).
_GT = (0.0, 1.0, 0.0, 0.0, 0.0, -1.0)


@unittest.skipUnless(fn._HAVE_NUMPY and fn._HAVE_SHAPELY,
                     "numpy + shapely required")
class TestVectorizeNdsm(unittest.TestCase):

    def _ndsm(self, fill_boxes):
        import numpy as np
        a = np.zeros((20, 20))
        for (r0, r1, c0, c1, h) in fill_boxes:
            a[r0:r1, c0:c1] = h
        return a

    def test_single_building(self):
        ndsm = self._ndsm([(3, 7, 3, 7, 8.0)])     # 4x4 @ 8 m
        res = fn.vectorize_ndsm(ndsm, _GT, min_height_m=2.0,
                                min_area_m2=4.0, pixel_size_m=1.0)
        self.assertEqual(len(res), 1)
        ring, height = res[0]
        self.assertEqual(height, 8.0)
        self.assertGreaterEqual(len(ring), 4)

    def test_two_separate_blobs(self):
        ndsm = self._ndsm([(2, 6, 2, 6, 5.0), (12, 18, 12, 18, 10.0)])
        res = fn.vectorize_ndsm(ndsm, _GT, min_height_m=2.0,
                                min_area_m2=4.0, pixel_size_m=1.0)
        self.assertEqual(len(res), 2)
        self.assertEqual(sorted(h for _, h in res), [5.0, 10.0])

    def test_below_height_threshold_ignored(self):
        ndsm = self._ndsm([(3, 7, 3, 7, 1.0)])      # 1 m < 2 m threshold
        res = fn.vectorize_ndsm(ndsm, _GT, min_height_m=2.0,
                                min_area_m2=4.0, pixel_size_m=1.0)
        self.assertEqual(res, [])

    def test_small_blob_filtered_by_area(self):
        ndsm = self._ndsm([(0, 1, 0, 1, 9.0)])      # 1 px = 1 m² < 4 m²
        res = fn.vectorize_ndsm(ndsm, _GT, min_height_m=2.0,
                                min_area_m2=4.0, pixel_size_m=1.0)
        self.assertEqual(res, [])

    def test_nan_treated_as_ground(self):
        import numpy as np
        ndsm = self._ndsm([(3, 7, 3, 7, 8.0)])
        ndsm[0, 0] = np.nan                          # nodata shouldn't crash
        res = fn.vectorize_ndsm(ndsm, _GT, min_height_m=2.0,
                                min_area_m2=4.0, pixel_size_m=1.0)
        self.assertEqual(len(res), 1)

    def test_empty_array(self):
        import numpy as np
        self.assertEqual(fn.vectorize_ndsm(np.zeros((0, 0)), _GT), [])


class TestNdsmExtractorRegistration(unittest.TestCase):

    def setUp(self):
        fe._extractor = None

    @unittest.skipUnless(fn._HAVE_NUMPY and fn._HAVE_SHAPELY,
                         "numpy + shapely required")
    def test_get_extractor_returns_ndsm_when_deps_present(self):
        # With no explicit registration, the built-in nDSM backend is offered.
        self.assertTrue(fe.extraction_available())
        self.assertIsInstance(fe.get_extractor(), fn.NdsmExtractor)


class TestAddExtractedFootprints(unittest.TestCase):

    def test_adds_canopy_footprint_features(self):
        project = {"type": "FeatureCollection", "features": []}
        rings = [
            ([(-113.50, 53.50), (-113.49, 53.50), (-113.49, 53.51)], 8.0),
            ([(-113.48, 53.50), (-113.47, 53.50), (-113.47, 53.51)], 6.0),
        ]
        added = fe.add_extracted_footprints(rings, project)
        self.assertEqual(len(added), 2)
        self.assertEqual(len(project["features"]), 2)
        props = project["features"][0]["properties"]
        self.assertEqual(props["element_type"], "canopy_footprint")
        self.assertEqual(props["height_m"], 8.0)
        self.assertTrue(props["cast_shade"])
        # Ring was closed.
        ring = project["features"][0]["geometry"]["coordinates"][0]
        self.assertEqual(ring[0], ring[-1])

    def test_skips_degenerate_rings(self):
        project = {"features": []}
        added = fe.add_extracted_footprints(
            [([(-113.5, 53.5), (-113.49, 53.5)], 5.0)], project)  # only 2 pts
        self.assertEqual(added, [])
        self.assertEqual(project["features"], [])

    def test_extracted_feature_round_trips_to_shape(self):
        from src.project import feature_to_shape
        import src.shade as shade
        project = {"features": []}
        fe.add_extracted_footprints(
            [([(-113.50, 53.50), (-113.49, 53.50), (-113.49, 53.51)], 7.0)],
            project)
        sh = feature_to_shape(project["features"][0])
        self.assertEqual(sh["height_m"], 7.0)
        self.assertIsNotNone(sh["shape_id"])
        # And it reads back as a shade caster.
        casters = shade.casters_from_project(project)
        self.assertEqual(len(casters), 1)
        self.assertEqual(casters[0]["height_m"], 7.0)


if __name__ == "__main__":
    unittest.main()
