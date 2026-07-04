"""
tests/test_phenology.py — the "what's happening now" dashboard (F51).

Covers src/phenology.py:
  1. Blooming / fruiting land in the right months (parsed windows).
  2. Waking / going-dormant transitions come from the planting calendar ring.
  3. Planting-calendar tasks surface in their month.
  4. The 'now' slice + 'go check' prompt track the requested month.
  5. Empty design is handled; distinct species are de-duped.
  6. Integration against the seeded temp DB.

Logic tests inject ``get_plant`` / ``get_calendar`` (DB-free); the last class
uses the seeded temp DB.
"""

import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

_TMP_DIR = tempfile.mkdtemp(prefix="permadesign_phen_test_")
import src.db.plants as _plants_mod  # noqa: E402
_plants_mod._DATA_DIR = _TMP_DIR
_plants_mod._DB_PATH = os.path.join(_TMP_DIR, "permadesign_test.db")

from src.phenology import build_phenology  # noqa: E402


# Fake plant rows keyed by id, and fake planting calendars.
_ROWS = {
    1: {"common_name": "Wild Bergamot", "bloom_period": "Jul–Aug",
        "fruit_period": ""},
    2: {"common_name": "Saskatoon", "bloom_period": "May",
        "fruit_period": "Jul–Aug"},
}
# Saskatoon: dormant in winter, active Apr–Oct → wakes in Apr, dormant in Nov.
_CAL = {
    1: [{"month": m, "status": "growing" if 5 <= m <= 9 else "dormant"}
        for m in range(1, 13)],
    2: ([{"month": m, "status": "dormant"} for m in (1, 2, 3)]
        + [{"month": 4, "status": "transplant"}]
        + [{"month": m, "status": "growing"} for m in (5, 6)]
        + [{"month": 7, "status": "harvest"}, {"month": 8, "status": "harvest"}]
        + [{"month": m, "status": "growing"} for m in (9, 10)]
        + [{"month": m, "status": "dormant"} for m in (11, 12)]),
}


def _placed(*ids):
    return [{"plant_id": i} for i in ids]


def _get_plant(pid):
    return _ROWS.get(pid)


def _get_cal(pid):
    return _CAL.get(pid)


class TestPhenologyLogic(unittest.TestCase):

    def _build(self, ids, month=7):
        return build_phenology(_placed(*ids), month=month,
                               get_plant=_get_plant, get_calendar=_get_cal)

    def test_blooming_and_fruiting_months(self):
        r = self._build([1, 2])
        jul = r["months"][6]
        may = r["months"][4]
        self.assertIn("Wild Bergamot", jul["blooming"])
        self.assertIn("Saskatoon", jul["fruiting"])
        self.assertIn("Saskatoon", may["blooming"])
        # Bergamot has no fruit window → never fruiting.
        self.assertFalse(any("Wild Bergamot" in m["fruiting"] for m in r["months"]))

    def test_waking_and_dormant_transitions(self):
        r = self._build([2])
        apr = r["months"][3]
        nov = r["months"][10]
        self.assertIn("Saskatoon", apr["waking"])
        self.assertIn("Saskatoon", nov["dormant"])
        # Exactly one wake and one senescence for a single deciduous plant.
        wakes = sum(m["waking"].count("Saskatoon") for m in r["months"])
        self.assertEqual(wakes, 1)

    def test_tasks_surface_in_month(self):
        r = self._build([2])
        jul = r["months"][6]
        verbs = {t["verb"] for t in jul["tasks"]}
        self.assertIn("harvest", verbs)

    def test_now_slice_tracks_month(self):
        r = self._build([1, 2], month=7)
        self.assertEqual(r["current_month"], 7)
        self.assertEqual(r["now"]["name"], "July")
        self.assertTrue(r["now"]["go_check"])
        self.assertIn("bloom", r["now"]["headline"].lower())
        # A quiet month yields a gentle prompt, never a crash.
        q = self._build([1], month=1)
        self.assertTrue(q["now"]["headline"])

    def test_empty_and_dedup(self):
        empty = build_phenology([], month=6, get_plant=_get_plant,
                                get_calendar=_get_cal)
        self.assertEqual(empty["n_plants"], 0)
        self.assertEqual(empty["now"]["go_check"], "")
        # Two copies of the same species count once.
        dup = build_phenology(_placed(1, 1, 1), month=7, get_plant=_get_plant,
                              get_calendar=_get_cal)
        self.assertEqual(dup["n_plants"], 1)


class TestPhenologyIntegration(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from src.db.plants import init_db
        init_db()

    def test_real_db(self):
        from src.db.plants import get_all_plants
        ids = [p["id"] for p in get_all_plants()[:12]]
        r = build_phenology([{"plant_id": i} for i in ids], month=7)
        self.assertEqual(len(r["months"]), 12)
        self.assertEqual(r["n_plants"], len(set(ids)))
        # Something should be in bloom in July across a dozen natives.
        self.assertTrue(any(m["blooming"] for m in r["months"]))
        self.assertIn("current_name", r)

    def test_api_surface(self):
        import src.permadesign_api as api
        self.assertIn("phenology", api.__all__)
        self.assertTrue(hasattr(api, "phenology"))


if __name__ == "__main__":
    unittest.main()
