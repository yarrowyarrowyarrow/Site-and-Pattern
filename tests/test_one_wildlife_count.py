"""
tests/test_one_wildlife_count.py — one wildlife count, worded as records
(V3.20, OV-5).

The Report card counted every animal with any record on the design's plants,
food or shelter, as "wildlife species supported"; Design › Food counted food
edges and said "Your plants feed N animals". One design read 263 on one and 271
on the other (OVF-4), and "supported" or "feed" claims more than a record of an
animal eating a plant somewhere in two provinces can (R15). All three pages now
count food edges and say "recorded as food for".
"""

import os
import re
import sys
import tempfile
import unittest
import unittest.mock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

_TMP = tempfile.mkdtemp(prefix="sp_one_count_")
import src.db.plants as _plants_mod  # noqa: E402
_plants_mod._DATA_DIR = _TMP
_plants_mod._DB_PATH = os.path.join(_TMP, "one_count.db")

try:
    from PyQt6.QtWidgets import QApplication
    _HAVE_QT = True
except ImportError:                                        # pragma: no cover
    _HAVE_QT = False

_COUNT = re.compile(r"recorded as food for (\d+) kinds", re.I)


class TheCount(unittest.TestCase):

    def test_shelter_alone_does_not_count(self):
        from src import what_it_feeds as feeds
        fed = [{"taxon": "bird", "food": True}, {"taxon": "bee", "food": True},
               {"taxon": "bird", "food": False}]
        with unittest.mock.patch.object(feeds, "animals_fed",
                                        return_value=fed):
            counts = feeds.food_counts([1])
        self.assertEqual(list(counts.items()), [("bee", 1), ("bird", 1)])
        self.assertEqual(feeds.food_words(counts),
                         "recorded as food for 2 kinds of wildlife")
        self.assertEqual(feeds.food_words({}), "")


@unittest.skipUnless(_HAVE_QT, "PyQt6 not installed in this env")
class ThreePagesOneNumber(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls._app = QApplication.instance() or QApplication(["sp-one-count"])
        _plants_mod.init_db()
        from src.onboarding import resolve_example_planting
        placements, missing = resolve_example_planting()
        assert not missing, missing
        cls.placed = [{"plant_id": p["plant_id"]} for p in placements]

    def _number(self, text):
        found = _COUNT.search(re.sub(r"<[^>]+>", "", text))
        self.assertIsNotNone(found, text[:300])
        return int(found.group(1))

    def test_report_card_habitat_and_food_agree(self):
        from src.analysis_panel import AnalysisPanel
        from src.food_page import FoodPage
        from src.habitat_score import compute_habitat_score
        from src.on_this_design_panel import OnThisDesignPanel

        food = FoodPage()
        self.addCleanup(food.close)
        food.set_placed_plants(self.placed)
        food.refresh()
        on_food = self._number(food._summary_line.text())

        card = OnThisDesignPanel()
        self.addCleanup(card.close)
        card.set_design_data(self.placed)
        card.set_habitat_value(compute_habitat_score(self.placed, []))
        on_card = self._number(card._value_block_html())

        habitat = AnalysisPanel()
        self.addCleanup(habitat.close)
        habitat.set_placed_plants(self.placed)
        habitat._calc_habitat_score()
        on_habitat = self._number(habitat._habitat_breakdown.text())

        self.assertEqual((on_card, on_habitat), (on_food, on_food))
        self.assertGreater(on_food, 0)


class NoPageSaysSupported(unittest.TestCase):

    def test_no_visible_wildlife_species_supported(self):
        root = os.path.join(os.path.dirname(os.path.dirname(
            os.path.abspath(__file__))), "src")
        for name in sorted(os.listdir(root)):
            if not name.endswith(".py"):
                continue
            with open(os.path.join(root, name), encoding="utf-8") as fh:
                text = fh.read()
            self.assertNotIn("wildlife species supported", text, name)
            self.assertNotIn("Wildlife supported", text, name)


if __name__ == "__main__":
    unittest.main()
