"""
tests/test_hrdem.py — NRCan HRDEM elevation source (V2.17).

The STAC parsing, coverage logic and grid assembly are tested with canned STAC
JSON and an injected point-sampler, so they run with NO network and NO rasterio.
The real rasterio COG path is exercised against a synthetic Cloud-Optimized-ish
GeoTIFF only where rasterio is installed (skipped otherwise, like test_soil_grid).
A routing test confirms generate_terrain prefers HRDEM and falls back to Copernicus.
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

from src import hrdem
import src.terrain_store as _terrain_store  # noqa: E402

_REGINA = {"south": 50.44, "north": 50.47, "west": -104.66, "east": -104.60}


def _stac_with_assets(dtm="https://x/dtm.tif", dsm="https://x/dsm.tif",
                      collection="hrdem-mosaic"):
    assets = {}
    if dtm:
        assets["dtm"] = {"href": dtm, "roles": ["data"]}
    if dsm:
        assets["dsm"] = {"href": dsm, "roles": ["data"]}
    return {"features": [{"collection": collection, "assets": assets}]}


class TestStacParsing(unittest.TestCase):

    def test_has_coverage_true(self):
        self.assertTrue(hrdem.has_coverage(_REGINA,
                                           fetcher=lambda u: _stac_with_assets()))

    def test_has_coverage_false_when_empty(self):
        self.assertFalse(hrdem.has_coverage(_REGINA,
                                            fetcher=lambda u: {"features": []}))

    def test_has_coverage_failsafe_on_error(self):
        def boom(url):
            raise RuntimeError("network down")
        self.assertFalse(hrdem.has_coverage(_REGINA, fetcher=boom))

    def test_pick_cog_prefers_mosaic(self):
        items = [
            {"collection": "hrdem-lidar", "assets": {"dtm": {"href": "lidar.tif"}}},
            {"collection": "hrdem-mosaic", "assets": {"dtm": {"href": "mosaic.tif"}}},
        ]
        self.assertEqual(hrdem._pick_cog(items, hrdem._DTM_KEYS), "mosaic.tif")

    def test_asset_href_tolerant_of_spelling(self):
        item = {"assets": {"HRDEM-DTM-1m": {"href": "x.tif", "roles": ["data"]}}}
        self.assertEqual(hrdem._asset_href(item, hrdem._DTM_KEYS), "x.tif")


class TestGridAssembly(unittest.TestCase):
    """No rasterio needed — inject the point sampler directly."""

    def _ramp(self, points):
        # elevation rises to the north
        return [500.0 + (lat - 50.44) * 300 for lat, lng in points]

    def test_grid_shape_and_layout(self):
        g = hrdem._build_grid(_REGINA, 20.0, self._ramp, "test")
        self.assertIsNotNone(g)
        self.assertEqual(len(g["grid"]), g["rows"])
        self.assertEqual(len(g["grid"][0]), g["cols"])
        # row 0 is the north edge → higher than the south edge
        north = sum(g["grid"][0]) / g["cols"]
        south = sum(g["grid"][-1]) / g["cols"]
        self.assertGreater(north, south)

    def test_all_nodata_returns_none(self):
        self.assertIsNone(
            hrdem._build_grid(_REGINA, 20.0, lambda pts: [None] * len(pts), "t"))

    def test_partial_data_imputed(self):
        cols, rows = hrdem.grid_dims(_REGINA, 20.0)
        n = cols * rows
        half = [500.0] * (n // 2 + 1) + [None] * (n - n // 2 - 1)
        g = hrdem._build_grid(_REGINA, 20.0, lambda pts: half, "t")
        self.assertIsNotNone(g)
        self.assertGreater(g["missing_pct"], 0.0)

    def test_mostly_missing_returns_none(self):
        cols, rows = hrdem.grid_dims(_REGINA, 20.0)
        n = cols * rows
        sparse = [500.0] * (n // 4) + [None] * (n - n // 4)
        self.assertIsNone(hrdem._build_grid(_REGINA, 20.0, lambda pts: sparse, "t"))

    def test_ndsm_object_heights(self):
        nd = hrdem.fetch_hrdem_ndsm(
            _REGINA, 20.0,
            dsm_sampler=lambda pts: [512.0] * len(pts),
            dtm_sampler=lambda pts: [500.0] * len(pts))
        self.assertIsNotNone(nd)
        self.assertAlmostEqual(nd["grid"][0][0], 12.0, places=3)
        self.assertIn("nDSM", nd["source"])


class TestFetchGridSeams(unittest.TestCase):
    """These exercise fetch_hrdem_grid, which caches via the terrain store — so
    isolate that store to a throwaway DB (restored on teardown) rather than
    touching real user data or leaking the patch to other test modules."""

    def setUp(self):
        self._orig_db_path = _terrain_store._db_path
        cache_db = os.path.join(tempfile.mkdtemp(prefix="hrdem_terrain_"),
                                "terrain.db")
        _terrain_store._db_path = lambda: cache_db

    def tearDown(self):
        _terrain_store._db_path = self._orig_db_path

    def test_no_coverage_returns_none(self):
        # empty STAC, no injected sampler → None (caller falls back to Copernicus).
        # Distinct bbox so the srtm cache from other tests can't shadow the result.
        offshore = {"south": 48.0, "north": 48.02, "west": -60.0, "east": -59.98}
        self.assertIsNone(
            hrdem.fetch_hrdem_grid(offshore, 20.0,
                                   fetcher=lambda u: {"features": []}))

    def test_injected_sampler_builds_grid(self):
        g = hrdem.fetch_hrdem_grid(
            _REGINA, 20.0, sampler=lambda pts: [505.0] * len(pts))
        self.assertIsNotNone(g)
        self.assertIn("HRDEM", g["source"])


@unittest.skipUnless(_HAVE_RASTERIO, "rasterio not installed")
class TestRasterioSampler(unittest.TestCase):

    def _write_cog(self, path, base, crs="EPSG:4326",
                   bounds=(-104.66, 50.44, -104.60, 50.47)):
        w = h = 8
        # rows increase southward in array space; make elevation rise northward
        data = np.zeros((h, w), dtype="float32")
        for r in range(h):
            data[r, :] = base + (h - 1 - r) * 2.0
        transform = from_bounds(*bounds, w, h)
        with rasterio.open(path, "w", driver="GTiff", height=h, width=w, count=1,
                           dtype="float32", crs=crs, transform=transform,
                           nodata=-9999.0) as ds:
            ds.write(data, 1)

    def test_sampler_reads_local_geotiff(self):
        tmp = tempfile.mkdtemp()
        cog = os.path.join(tmp, "dtm.tif")
        self._write_cog(cog, 500.0)
        sampler = hrdem._rasterio_sampler(cog)
        self.assertIsNotNone(sampler)
        g = hrdem._build_grid(_REGINA, 20.0, sampler, "NRCan HRDEM (test)")
        self.assertIsNotNone(g)
        north = sum(g["grid"][0]) / g["cols"]
        south = sum(g["grid"][-1]) / g["cols"]
        self.assertGreater(north, south)


class TestGenerateTerrainRouting(unittest.TestCase):
    """generate_terrain prefers HRDEM, falls back to Copernicus."""

    def setUp(self):
        from src import terrain
        self.terrain = terrain
        self._orig_hrdem = hrdem.fetch_hrdem_grid
        self._orig_om = terrain.fetch_openmeteo_grid
        self.bbox = {"south": 50.445, "north": 50.450,
                     "west": -104.620, "east": -104.615}

    def tearDown(self):
        hrdem.fetch_hrdem_grid = self._orig_hrdem
        self.terrain.fetch_openmeteo_grid = self._orig_om

    def _grid(self, source):
        def _mk(bbox, res, **kw):
            cols, rows = self.terrain.grid_dims(bbox, res)
            pts = self.terrain._grid_points(bbox, cols, rows)
            els = [500.0 + (lat - bbox["south"]) * 300 for lat, lng in pts]
            grid = [[els[i * cols + c] for c in range(cols)] for i in range(rows)]
            return {"grid": grid, "cols": cols, "rows": rows, "bbox": bbox,
                    "resolution_m": res, "missing_pct": 0.0, "source": source}
        return _mk

    def test_prefers_hrdem(self):
        hrdem.fetch_hrdem_grid = self._grid("NRCan HRDEM (1 m LiDAR, DTM)")
        self.terrain.fetch_openmeteo_grid = lambda b, r: None
        res = self.terrain.generate_terrain(
            self.bbox, {"want_contours": True, "want_slope_overlay": False})
        self.assertTrue(res["ok"])
        self.assertIn("HRDEM", res["source"])

    def test_falls_back_to_copernicus(self):
        hrdem.fetch_hrdem_grid = lambda b, r, **kw: None
        self.terrain.fetch_openmeteo_grid = self._grid(
            "Open-Meteo / Copernicus DEM 30m")
        res = self.terrain.generate_terrain(
            self.bbox, {"want_contours": True, "want_slope_overlay": False})
        self.assertTrue(res["ok"])
        self.assertIn("Copernicus", res["source"])


if __name__ == "__main__":
    unittest.main()
