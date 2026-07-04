"""
tests/test_lesson_track.py — the guided lesson track (F53).

Covers src/lesson_track.py:
  1. Four steps in the taught order, each well-formed.
  2. Keystone step reads the design's host plants (good vs. attention).
  3. Food-web step mirrors habitat_score.food_web status.
  4. Succession step rewards a pioneer+climax spread.
  5. Ranges step is always present; empty design → 'empty' statuses.
  6. Integration on the seeded temp DB + scripting-API surface.

Logic tests inject ``get_plant`` / ``get_keystone`` / ``score`` (DB-free); the
last class uses the seeded temp DB.
"""

import os
import sys
import tempfile
import types
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

_TMP_DIR = tempfile.mkdtemp(prefix="permadesign_lesson_test_")
import src.db.plants as _plants_mod  # noqa: E402
_plants_mod._DATA_DIR = _TMP_DIR
_plants_mod._DB_PATH = os.path.join(_TMP_DIR, "permadesign_test.db")

from src.lesson_track import build_lesson_track  # noqa: E402


# Fake plant rows: 1 = keystone pioneer, 2 = climax tree, 3 = mid.
_ROWS = {
    1: {"id": 1, "common_name": "Willow", "plant_type": "shrub",
        "permaculture_uses": "pioneer"},
    2: {"id": 2, "common_name": "Bur Oak", "plant_type": "tree",
        "years_to_maturity": 30, "permaculture_uses": "climax"},
    3: {"id": 3, "common_name": "Yarrow", "plant_type": "herb",
        "permaculture_uses": ""},
}
_RANKS = {1: 20, 2: 8, 3: 0}


def _get_plant(pid):
    return _ROWS.get(pid)


def _get_keystone(pid):
    return _RANKS.get(pid, 0)


def _score(status, n_cat=0, n_bird=0):
    return types.SimpleNamespace(food_web={
        "status": status, "n_caterpillars": n_cat, "n_birds": n_bird})


def _placed(*ids):
    return [{"plant_id": i} for i in ids]


class TestLessonLogic(unittest.TestCase):

    def _track(self, ids, status="complete", **kw):
        return build_lesson_track(
            _placed(*ids), [], score=_score(status, 5, 3),
            get_plant=_get_plant, get_keystone=_get_keystone, **kw)

    def test_four_steps_in_order(self):
        t = self._track([1, 2, 3])
        self.assertEqual(t["n_steps"], 4)
        self.assertEqual([s["id"] for s in t["steps"]],
                         ["keystone", "food_web", "succession", "ranges"])
        for s in t["steps"]:
            self.assertTrue(s["title"] and s["lesson"] and s["your_design"])
            self.assertIn(s["status"], ("good", "attention", "empty"))

    def test_keystone_reads_hosts(self):
        good = self._track([1, 2])["steps"][0]
        self.assertEqual(good["status"], "good")
        self.assertIn("Willow", good["your_design"])
        # Only weak/no hosts → attention.
        weak = self._track([3])["steps"][0]
        self.assertEqual(weak["status"], "attention")

    def test_food_web_mirrors_status(self):
        complete = self._track([1], status="complete")["steps"][1]
        self.assertEqual(complete["status"], "good")
        no_birds = self._track([1], status="no_birds")["steps"][1]
        self.assertEqual(no_birds["status"], "attention")
        self.assertIn("bird", no_birds["your_design"].lower())

    def test_succession_rewards_spread(self):
        mixed = self._track([1, 2])["steps"][2]      # pioneer + climax
        self.assertEqual(mixed["status"], "good")
        one_sided = self._track([2])["steps"][2]     # climax only
        self.assertEqual(one_sided["status"], "attention")

    def test_ranges_always_present_and_empty_design(self):
        t = self._track([1, 2, 3])
        self.assertEqual(t["steps"][3]["id"], "ranges")
        empty = build_lesson_track([], [], score=_score("empty"),
                                   get_plant=_get_plant, get_keystone=_get_keystone)
        self.assertTrue(all(s["status"] == "empty" for s in empty["steps"]))


class TestLessonIntegration(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from src.db.plants import init_db
        init_db()

    def test_real_db(self):
        from src.db.plants import get_all_plants
        ids = [p["id"] for p in get_all_plants()[:20]]
        t = build_lesson_track([{"plant_id": i} for i in ids], [])
        self.assertEqual(t["n_steps"], 4)
        for s in t["steps"]:
            self.assertTrue(s["your_design"])

    def test_api_surface(self):
        import src.permadesign_api as api
        self.assertIn("lesson_track", api.__all__)
        self.assertTrue(hasattr(api, "lesson_track"))


if __name__ == "__main__":
    unittest.main()
