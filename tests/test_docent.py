"""
tests/test_docent.py — docent / presentation-mode script (F52).

Covers src/docent.py:
  1. A well-formed beat sequence (ids, titles, narration, camera/season state).
  2. Facts flow into the narration (score total, food-web status, species count).
  3. The season + brood beats appear/skip from their inputs.
  4. Empty design yields a graceful opening→close pair.
  5. Integration on the seeded temp DB + scripting-API surface.

Logic tests inject ``score`` / ``chickadee`` / ``forage`` (DB-free); the last
class uses the seeded temp DB.
"""

import os
import sys
import tempfile
import types
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

_TMP_DIR = tempfile.mkdtemp(prefix="permadesign_docent_test_")
import src.db.plants as _plants_mod  # noqa: E402
_plants_mod._DATA_DIR = _TMP_DIR
_plants_mod._DB_PATH = os.path.join(_TMP_DIR, "permadesign_test.db")

from src.docent import build_docent_script  # noqa: E402


def _score(total=62, status="complete", n_cat=5, n_bird=3):
    return types.SimpleNamespace(
        total=total, native_species=6, native_ratio=0.9,
        fauna_by_taxon={"lepidoptera": 5, "bird": 3, "bee": 4},
        food_web={"status": status, "n_caterpillars": n_cat, "n_birds": n_bird})


def _forage(peak=7, cov=6, total=7, gaps=None, flowering=8):
    return {"peak_month": peak, "covered_growing": cov, "growing_total": total,
            "gap_months": gaps or [], "flowering_plants": flowering}


def _chickadee(status="clears", lo=8000, hi=20000):
    return {"status": status, "caterpillars_low": lo, "caterpillars_high": hi}


def _placed(n=4):
    return [{"plant_id": i} for i in range(1, n + 1)]


class TestDocentLogic(unittest.TestCase):

    def _script(self, **kw):
        return build_docent_script(
            _placed(4), [], name="the pollinator garden",
            score=kw.pop("score", _score()),
            chickadee=kw.pop("chickadee", _chickadee()),
            forage=kw.pop("forage", _forage()), **kw)

    def test_beats_well_formed(self):
        s = self._script()
        self.assertTrue(s["title"] and s["subtitle"])
        self.assertEqual(s["n_beats"], len(s["beats"]))
        self.assertGreaterEqual(s["n_beats"], 5)
        ids = [b["id"] for b in s["beats"]]
        self.assertEqual(ids[0], "opening")
        self.assertEqual(ids[-1], "close")
        for b in s["beats"]:
            self.assertTrue(b["title"] and b["narration"])
            self.assertIn(b["camera"], ("overview", "orbit", "walk"))
            self.assertIn(b["season_month"], range(1, 13))

    def test_facts_reach_narration(self):
        s = self._script(score=_score(total=71, status="complete"))
        joined = " ".join(b["narration"] for b in s["beats"])
        self.assertIn("71", joined)               # score total
        self.assertIn("6,000", joined)            # the Tallamy brood number
        # species tally sums the taxon counts (5+3+4 = 12)
        self.assertIn("12", joined)

    def test_food_web_status_shapes_beat(self):
        complete = self._script(score=_score(status="complete"))
        fw = next(b for b in complete["beats"] if b["id"] == "food_web")
        self.assertIn("closed", fw["narration"].lower())
        no_birds = self._script(score=_score(status="no_birds"))
        fw2 = next(b for b in no_birds["beats"] if b["id"] == "food_web")
        self.assertIn("berry", fw2["narration"].lower())

    def test_season_and_brood_optional(self):
        # No forage flowering → no season beat; no chickadee → no brood beat.
        s = self._script(forage=_forage(flowering=0), chickadee=None)
        ids = [b["id"] for b in s["beats"]]
        self.assertNotIn("season", ids)
        self.assertNotIn("brood", ids)
        # season beat carries the peak month
        s2 = self._script(forage=_forage(peak=8))
        season = next(b for b in s2["beats"] if b["id"] == "season")
        self.assertEqual(season["season_month"], 8)

    def test_a_tie_is_not_narrated_as_a_peak(self):
        # V2.91: with one species in flower each month, every bloom month
        # ties, and the earliest used to be named the peak ("Bloom peaks
        # around March" for a prairie mix). The camera goes to midsummer.
        months = [{"month": m, "count": 1 if m in (3, 4, 5, 8, 9, 10) else 0}
                  for m in range(1, 13)]
        forage = dict(_forage(peak=3, cov=5, gaps=[6, 7], flowering=2),
                      months=months)
        season = next(b for b in self._script(forage=forage)["beats"]
                      if b["id"] == "season")
        self.assertNotIn("peaks", season["narration"])
        self.assertIn("Flowers open from March to October",
                      season["narration"])
        self.assertEqual(season["season_month"], 8)

    def test_a_real_peak_is_still_named(self):
        months = [{"month": m, "count": {6: 2, 7: 5, 8: 3}.get(m, 0)}
                  for m in range(1, 13)]
        forage = dict(_forage(peak=7), months=months)
        season = next(b for b in self._script(forage=forage)["beats"]
                      if b["id"] == "season")
        self.assertIn("Bloom peaks around July", season["narration"])
        self.assertEqual(season["season_month"], 7)

    def test_empty_design(self):
        s = build_docent_script([], [], score=None, chickadee=None, forage=None)
        ids = [b["id"] for b in s["beats"]]
        self.assertEqual(ids, ["opening", "close"])
        self.assertTrue(s["subtitle"])


class TestDocentIntegration(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from src.db.plants import init_db
        init_db()

    def test_real_db(self):
        from src.db.plants import get_all_plants
        placed = [{"plant_id": p["id"]} for p in get_all_plants()[:15]]
        s = build_docent_script(placed, [])
        self.assertGreaterEqual(s["n_beats"], 4)
        self.assertEqual(s["beats"][0]["id"], "opening")
        self.assertEqual(s["beats"][-1]["id"], "close")

    def test_api_surface(self):
        import src.permadesign_api as api
        self.assertIn("docent_script", api.__all__)
        self.assertTrue(hasattr(api, "docent_script"))

    def _placed_named(self, names):
        from src.db.plants import get_all_plants
        rows = {p["common_name"]: p for p in get_all_plants()}
        return [{"plant_id": rows[n]["id"], "common_name": n} for n in names]

    def test_the_season_beat_plays_from_placed_records(self):
        # V2.91: both real callers pass placed records, which carry no bloom
        # period, so the forage calendar saw nothing in flower and the season
        # beat never played on any design. `test_real_db` above did not ask.
        placed = self._placed_named(
            ["Prairie Crocus", "Wild Bergamot", "Smooth Aster"])
        ids = [b["id"] for b in build_docent_script(placed, [])["beats"]]
        self.assertIn("season", ids)

    def test_grass_bloom_is_not_narrated_as_forage(self):
        # V2.91 (F182): the grasses flower in June and July, which stay a gap.
        from src.docent import _with_catalogue
        from src.forage_calendar import build_forage_calendar
        placed = self._placed_named(
            ["Prairie Crocus", "Smooth Aster", "Rough Fescue",
             "Blue Grama Grass", "Needle and Thread Grass"])
        cal = build_forage_calendar(_with_catalogue(placed))
        self.assertIn(6, cal["gap_months"])
        self.assertIn(7, cal["gap_months"])
        season = next(b for b in build_docent_script(placed, [])["beats"]
                      if b["id"] == "season")
        self.assertIn("the gaps are where the next planting goes",
                      season["narration"])


if __name__ == "__main__":
    unittest.main()
