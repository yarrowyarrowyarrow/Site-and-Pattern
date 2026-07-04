"""
tests/test_reference_ecosystem.py — the walkable reference-ecosystem library (F50).

Covers src/reference_ecosystem.py:
  1. Every curated ecoregion resolves to real species per layer (logic + DB).
  2. build_reference_project places instances per the layer counts, as valid
     placed-plant Point features.
  3. The project feeds scene_contract.build_scene into a walkable scene.
  4. Unknown ecoregion falls back; empty-canopy communities place no canopy.
  5. Scripting-API surface (reference_community).

Logic tests inject ``resolve_genus``; DB-backed tests use the seeded temp DB.
"""

import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

_TMP_DIR = tempfile.mkdtemp(prefix="permadesign_ref_test_")
import src.db.plants as _plants_mod  # noqa: E402
_plants_mod._DATA_DIR = _TMP_DIR
_plants_mod._DB_PATH = os.path.join(_TMP_DIR, "permadesign_test.db")

from src.reference_ecosystem import (  # noqa: E402
    community_keys, reference_community, resolve_reference_community,
    build_reference_project, build_reference_scene,
)
from src.project_store import plant_record_from_feature  # noqa: E402


def _fake_resolver(genera):
    """Return one fake row per requested genus, typed by a lookup so layer
    filtering has something to bite on."""
    types = {"Populus": "tree", "Picea": "tree", "Betula": "tree",
             "Rosa": "shrub", "Salix": "shrub", "Amelanchier": "shrub",
             "Solidago": "wildflower", "Carex": "grass", "Festuca": "grass"}
    out = []
    for i, g in enumerate(genera):
        out.append({"id": 1000 + i, "common_name": f"{g} sp",
                    "scientific_name": f"{g} test",
                    "plant_type": types.get(g, "wildflower")})
    return out


class TestReferenceLogic(unittest.TestCase):

    def test_all_communities_have_layers(self):
        self.assertTrue(community_keys())
        for key in community_keys():
            c = reference_community(key)
            self.assertIn("layers", c)
            self.assertTrue(c["name"] and c["description"])
            self.assertLessEqual(set(c["layers"]),
                                 {"canopy", "shrub", "forb", "grass"})

    def test_resolve_uses_injected_data(self):
        r = resolve_reference_community("aspen_parkland",
                                        resolve_genus=_fake_resolver)
        self.assertEqual(r["key"], "aspen_parkland")
        self.assertGreater(r["n_species"], 0)
        # a species is never double-counted across layers
        flat = [n for names in r["layers"].values() for n in names]
        self.assertEqual(len(flat), len(set(flat)))

    def test_build_project_places_features(self):
        proj = build_reference_project("aspen_parkland", size_m=20,
                                       resolve_genus=_fake_resolver)
        self.assertEqual(proj["type"], "FeatureCollection")
        recs = [plant_record_from_feature(f) for f in proj["features"]]
        recs = [r for r in recs if r]
        self.assertTrue(recs)
        # counts sum to the community's layer counts (all genera resolve here)
        want = sum(l["count"] for l in
                   reference_community("aspen_parkland")["layers"].values())
        self.assertEqual(len(recs), want)
        for r in recs:
            self.assertIsNotNone(r["plant_id"])
            self.assertTrue(-90 <= r["lat"] <= 90 and -180 <= r["lng"] <= 180)

    def test_treeless_community_has_no_canopy_count(self):
        c = reference_community("mixedgrass_prairie")
        self.assertEqual(c["layers"]["canopy"]["count"], 0)

    def test_unknown_ecoregion_falls_back(self):
        c = reference_community("nowhere")
        self.assertEqual(c["name"], reference_community("aspen_parkland")["name"])


class TestReferenceIntegration(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from src.db.plants import init_db
        init_db()

    def test_real_communities_resolve(self):
        for key in community_keys():
            r = resolve_reference_community(key)
            self.assertGreater(r["n_species"], 0,
                               f"{key} resolved no species from the seed data")

    def test_build_scene_is_walkable(self):
        scene = build_reference_scene("boreal_mixedwood", size_m=22)
        self.assertIn("plants", scene)
        self.assertTrue(scene["plants"], "reference scene should place plants")
        # canopy trees should be taller than the forb layer
        heights = [p.get("height_m", 0) for p in scene["plants"]]
        self.assertGreater(max(heights), 3.0)

    def test_api_surface(self):
        import src.permadesign_api as api
        self.assertIn("reference_community", api.__all__)
        self.assertTrue(hasattr(api, "reference_community"))


if __name__ == "__main__":
    unittest.main()
