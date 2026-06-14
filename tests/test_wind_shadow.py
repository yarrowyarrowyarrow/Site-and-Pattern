"""
tests/test_wind_shadow.py — porosity-aware wind-shadow geometry (V1.68).

Headless: pure geometry + shapely. Skips the shapely-dependent cases when
shapely is absent (it's an optional dep, like the footprint/shadow tests).
"""

import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src import wind_shadow as ws
from src.shadow_geometry import _HAVE_SHAPELY


class TestReachAndPorosity(unittest.TestCase):
    def test_reach_peaks_at_half_porosity(self):
        peak = ws.reach_h_factor(0.5)
        self.assertGreater(peak, ws.reach_h_factor(0.0))   # solid shelters less
        self.assertGreater(peak, ws.reach_h_factor(1.0))   # open shelters less
        self.assertAlmostEqual(ws.reach_h_factor(0.0), ws.reach_h_factor(1.0))

    def test_porosity_trait_overrides_default(self):
        self.assertAlmostEqual(ws.porosity_for({"wind_porosity": 0.4}), 0.4)

    def test_conifer_denser_than_deciduous(self):
        self.assertLess(ws.porosity_for({"plant_type": "tree", "evergreen": 1}),
                        ws.porosity_for({"plant_type": "tree"}))
        self.assertEqual(ws.porosity_for({"plant_type": "shrub"}), 0.5)


@unittest.skipUnless(_HAVE_SHAPELY, "shapely not installed")
class TestMergedShelter(unittest.TestCase):

    def _caster(self, lat=53.5, lng=-113.5, h=6.0, hw=1.5, por=0.5):
        return {"lat": lat, "lng": lng, "height_m": h,
                "half_width_m": hw, "porosity": por}

    def test_projects_downwind(self):
        # Wind from the north (0°) → shelter extends SOUTH (lat decreases).
        out = ws.merged_shelter([self._caster()], wind_from_deg=0.0)
        self.assertTrue(out["bands"])
        ring = out["bands"][-1]["rings"][0][0]      # strong band, 1st poly, exterior
        clat = sum(p[0] for p in ring) / len(ring)
        self.assertLess(clat, 53.5)                 # centroid south of the plant

        # Wind from the south (180°) → shelter extends NORTH.
        north = ws.merged_shelter([self._caster()], wind_from_deg=180.0)
        nring = north["bands"][-1]["rings"][0][0]
        self.assertGreater(sum(p[0] for p in nring) / len(nring), 53.5)

    def test_overlapping_casters_merge(self):
        a = self._caster(lat=53.50000, lng=-113.50000)
        b = self._caster(lat=53.50001, lng=-113.50001)   # ~1 m away → overlap
        out = ws.merged_shelter([a, b], wind_from_deg=270.0)
        strong = [bd for bd in out["bands"] if bd["strength"] == "strong"][0]
        self.assertEqual(len(strong["rings"]), 1)        # merged into one

    def test_distant_casters_stay_separate(self):
        a = self._caster(lat=53.50, lng=-113.50)
        b = self._caster(lat=53.50, lng=-113.49)         # ~700 m away
        out = ws.merged_shelter([a, b], wind_from_deg=270.0)
        strong = [bd for bd in out["bands"] if bd["strength"] == "strong"][0]
        self.assertEqual(len(strong["rings"]), 2)        # two distinct footprints

    def test_bands_ordered_weak_first(self):
        out = ws.merged_shelter([self._caster()], wind_from_deg=0.0)
        strengths = [b["strength"] for b in out["bands"]]
        self.assertEqual(strengths, ["weak", "moderate", "strong"])

    def test_empty_casters(self):
        self.assertEqual(ws.merged_shelter([], 0.0)["bands"], [])


class TestCastersFromProject(unittest.TestCase):
    def test_only_trees_and_shrubs_with_height(self):
        project = {"type": "FeatureCollection", "properties": {}, "features": [
            {"type": "Feature",
             "geometry": {"type": "Point", "coordinates": [-113.5, 53.5]},
             "properties": {"element_type": "plant", "plant_id": 1}},
            {"type": "Feature",
             "geometry": {"type": "Point", "coordinates": [-113.5, 53.501]},
             "properties": {"element_type": "plant", "plant_id": 2}},
        ]}
        db = {1: {"plant_type": "tree", "mature_height_meters": 8.0,
                  "mature_canopy_m": 6.0},
              2: {"plant_type": "herb", "mature_height_meters": 0.4}}
        casters = ws.casters_from_project(project, year=0,
                                          get_plant=lambda pid: db.get(pid))
        self.assertEqual(len(casters), 1)               # herb excluded
        self.assertEqual(casters[0]["id"], 1)
        self.assertGreater(casters[0]["height_m"], 1.0)
        self.assertGreater(casters[0]["half_width_m"], 0.3)


if __name__ == "__main__":
    unittest.main()
