"""
tests/test_soil_grid.py — offline soil sampling + fetch_soil ordering (V1.67).

Headless: synthetic tiny GeoTIFFs in a temp pack dir (skip if rasterio absent),
and fetch_soil source ordering with the network + pack monkeypatched.
"""

import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

try:
    import numpy as np
    import rasterio
    from rasterio.transform import from_bounds
    _HAVE_RASTERIO = True
except ImportError:
    _HAVE_RASTERIO = False

from src import soil_grid


def _write_tif(path, value, crs="EPSG:4326", bounds=(-114.0, 53.0, -113.0, 54.0)):
    w = h = 4
    data = np.full((h, w), value, dtype="float32")
    transform = from_bounds(*bounds, w, h)
    with rasterio.open(path, "w", driver="GTiff", height=h, width=w, count=1,
                       dtype="float32", crs=crs, transform=transform,
                       nodata=-9999.0) as ds:
        ds.write(data, 1)


@unittest.skipUnless(_HAVE_RASTERIO, "rasterio not installed")
class TestSampleSoil(unittest.TestCase):

    def setUp(self):
        self.pack = tempfile.mkdtemp()

    def test_samples_all_attributes(self):
        _write_tif(os.path.join(self.pack, "ph_0-5.tif"), 6.4)
        _write_tif(os.path.join(self.pack, "sand_0-5.tif"), 35.0)
        _write_tif(os.path.join(self.pack, "silt_0-5.tif"), 40.0)
        _write_tif(os.path.join(self.pack, "clay_0-5.tif"), 25.0)
        out = soil_grid.sample_soil(53.5, -113.5, self.pack)
        self.assertIsNotNone(out)
        s = out["summary"]
        self.assertAlmostEqual(s["ph_top"], 6.4, places=1)
        self.assertAlmostEqual(s["sand_pct_top"], 35.0, places=1)
        self.assertEqual(s["clay_pct_top"], 25.0)
        self.assertTrue(s["texture_class"])
        self.assertIn("offline pack", out["source"])

    def test_normalizes_gkg_and_ph_times_ten(self):
        # g/kg-style texture (350) and pH×10 (64) should be coerced.
        _write_tif(os.path.join(self.pack, "ph_0-5.tif"), 64.0)
        _write_tif(os.path.join(self.pack, "sand_0-5.tif"), 350.0)
        _write_tif(os.path.join(self.pack, "silt_0-5.tif"), 400.0)
        _write_tif(os.path.join(self.pack, "clay_0-5.tif"), 250.0)
        s = soil_grid.sample_soil(53.5, -113.5, self.pack)["summary"]
        self.assertAlmostEqual(s["ph_top"], 6.4, places=1)
        self.assertAlmostEqual(s["sand_pct_top"], 35.0, places=1)

    def test_none_when_no_pack(self):
        self.assertIsNone(soil_grid.sample_soil(53.5, -113.5, self.pack))

    def test_reprojects_from_projected_crs(self):
        # A raster in a metres CRS (Web Mercator) must still sample at the
        # lat/lng point — build its bounds around the point's mercator coords.
        from pyproj import Transformer
        tr = Transformer.from_crs(4326, 3857, always_xy=True)
        x, y = tr.transform(-113.5, 53.5)
        _write_tif(os.path.join(self.pack, "ph_0-5.tif"), 7.1,
                   crs="EPSG:3857", bounds=(x - 500, y - 500, x + 500, y + 500))
        out = soil_grid.sample_soil(53.5, -113.5, self.pack)
        self.assertIsNotNone(out)
        self.assertAlmostEqual(out["summary"]["ph_top"], 7.1, places=1)


class TestFindAttrTif(unittest.TestCase):
    def setUp(self):
        self.pack = tempfile.mkdtemp()

    def test_prefers_topsoil_depth(self):
        for name in ("clay_30-60.tif", "clay_0-5.tif"):
            open(os.path.join(self.pack, name), "wb").close()
        chosen = soil_grid._find_attr_tif(self.pack, "clay")
        self.assertTrue(chosen.endswith("clay_0-5.tif"))


class TestNormalize(unittest.TestCase):
    def test_texture_and_ph(self):
        self.assertEqual(soil_grid._normalize("sand", 35.0), 35.0)
        self.assertEqual(soil_grid._normalize("sand", 350.0), 35.0)
        self.assertEqual(soil_grid._normalize("ph", 6.5), 6.5)
        self.assertEqual(soil_grid._normalize("ph", 65.0), 6.5)


class TestFetchSoilOrdering(unittest.TestCase):
    """fetch_soil: offline pack → SoilGrids → regional approximation."""

    def setUp(self):
        from src import property_data, soil_grid as sg
        self.pd = property_data
        self.sg = sg
        self._orig_sample = sg.sample_soil
        self._orig_http = property_data._http_get_json

    def tearDown(self):
        self.sg.sample_soil = self._orig_sample
        self.pd._http_get_json = self._orig_http

    def test_pack_first(self):
        sentinel = {"summary": {"ph_top": 6.0}, "properties": {},
                    "source": "Gridded Soil Landscapes of Canada (offline pack)"}
        # fetch_soil imports sample_soil from src.soil_grid at call time.
        self.sg.sample_soil = lambda lat, lng: sentinel
        out = self.pd.fetch_soil(53.5, -113.5)
        self.assertIs(out, sentinel)

    def test_falls_back_to_regional_when_pack_and_api_absent(self):
        self.sg.sample_soil = lambda lat, lng: None
        self.pd._http_get_json = lambda url, timeout=8.0: None
        out = self.pd.fetch_soil(53.5, -113.5)
        self.assertIsNotNone(out)
        self.assertIn("Regional approximation", out["source"])


if __name__ == "__main__":
    unittest.main()
