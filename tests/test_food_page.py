"""
tests/test_food_page.py — Design › Food, the owner's "what it feeds" page
(V3.08).

One animal, any animal: the Bees page answered "design for this bee", and the
owner wanted "a per species analysis but not one limited to just bees". Month
by month: Planning's Wildlife and Harvest calendars, merged "in such a way that
it is clear and distinct what is human forage and what is animal forage". And
the Planted list says, under each species, what eats it and when.
"""

import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

_TMP = tempfile.mkdtemp(prefix="sp_food_page_")
import src.db.plants as _plants_mod  # noqa: E402
_plants_mod._DATA_DIR = _TMP
_plants_mod._DB_PATH = os.path.join(_TMP, "food_page.db")

try:
    from PyQt6.QtWidgets import QApplication
    _HAVE_QT = True
except ImportError:                                        # pragma: no cover
    _HAVE_QT = False


@unittest.skipUnless(_HAVE_QT, "PyQt6 not installed in this env")
class TestFoodPage(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls._app = QApplication.instance() or QApplication(["sp-food-page"])
        _plants_mod.init_db()
        import src.permadesign_api as api
        api._DB_READY = True
        cls.rows = {r["common_name"]: r for r in api.query_plants()}
        cls.ids = [cls.rows[n]["id"] for n in
                   ("Wild Bergamot", "Showy Milkweed", "Chokecherry")]

    def _page(self, ids=None):
        from src.food_page import FoodPage
        page = FoodPage()
        self.addCleanup(page.close)
        page.set_placed_plants([{"plant_id": i} for i in
                                (self.ids if ids is None else ids)])
        page.refresh()
        return page

    def _select(self, page, taxon):
        """Pick the design's first animal of ``taxon``, as a person would."""
        combo = page._animal
        for i in range(combo.count()):
            data = combo.itemData(i)
            if data and data["taxon"] == taxon:
                combo.setCurrentIndex(i)
                combo.activated.emit(i)
                return data
        self.fail(f"no {taxon} in the list")

    def test_it_opens_on_the_animal_the_design_feeds_most(self):
        from src.what_it_feeds import animals_fed
        page = self._page()
        top = animals_fed(self.ids)[0]
        self.assertEqual(page._animal.currentData()["fid"], top["fauna_id"])
        self.assertIn("Fed by your design", page._animal.itemText(0))
        self.assertIn("Your plants feed", page._summary_line.text())

    def test_any_animal_not_only_bees(self):
        page = self._page()
        self._select(page, "lepidoptera")
        self.assertFalse(page._plan_is_bee)
        self.assertIn("In your design:", page._plants_box.text())
        self.assertEqual(page._needs_box.heading.text(), "What else it needs")
        self.assertIn("caterpillar host", page._plants_box.text()
                      + page._needs_box.text())
        self._select(page, "bird")
        self.assertIn("In your design:", page._plants_box.text())
        self.assertNotIn("caterpillar", page._plants_box.text())

    def test_a_bee_keeps_what_the_bees_page_said(self):
        page = self._page()
        self._select(page, "bee")
        self.assertTrue(page._plan_is_bee)
        self.assertEqual(page._needs_box.heading.text(),
                         "Nesting: give it a place to live")
        self.assertEqual(page._when_box.heading.text(),
                         "Food across its flight season")
        self.assertIn("Data confidence", page._footnote.text())

    def test_a_choice_is_kept_while_the_design_changes(self):
        page = self._page()
        chosen = self._select(page, "bird")
        page.set_placed_plants([{"plant_id": i} for i in self.ids[:2]]
                               + [{"plant_id": self.ids[2]}])
        page.refresh()
        self.assertEqual(page._animal.currentData(), chosen)

    def test_the_list_reaches_beyond_the_design(self):
        """The catalogue's animals follow the design's own, so a person can
        ask about one the design does not feed yet."""
        page = self._page()
        headers = [page._animal.itemText(i) for i in range(page._animal.count())
                   if page._animal.itemData(i) is None]
        self.assertTrue(any("Bees:" in h for h in headers))
        self.assertTrue(any("Birds" in h for h in headers))

    def test_find_narrows_the_list_and_says_when_nothing_matches(self):
        page = self._page()
        page._find.setText("zzzz no such animal")
        self.assertIsNone(page._animal.currentData())
        self.assertIn("No animal matches", page._who.text())
        page._find.setText("")
        self.assertIsNotNone(page._animal.currentData())

    def test_each_month_keeps_people_apart_and_last(self):
        page = self._page()
        self.assertEqual(page._tree.topLevelItemCount(), 12)
        for m in range(12):
            month = page._tree.topLevelItem(m)
            groups = [month.child(i).text(0) for i in range(month.childCount())]
            self.assertEqual(groups, ["For pollinators: flowers",
                                      "For birds: fruit and seed",
                                      "For people: what you can harvest"])
        # Chokecherry fruits in August: a harvest for people, with its part.
        august = page._tree.topLevelItem(7)
        people = august.child(2)
        harvest = [people.child(i).text(1) for i in range(people.childCount())]
        self.assertIn("Chokecherry — fruit", harvest)

    def test_an_empty_design_says_so(self):
        page = self._page(ids=[])
        self.assertEqual(page._summary_line.text(),
                         "Place plants to see who they feed.")
        self.assertEqual(page._tree.topLevelItemCount(), 1)

    def test_the_map_shows_the_plants_that_feed_it(self):
        page = self._page()
        sent, cleared = [], []
        page.map_overlay_requested.connect(sent.append)
        page.map_overlay_cleared.connect(lambda: cleared.append(True))
        self._select(page, "lepidoptera")
        page._map_btn.setChecked(True)
        styles = sent[-1]["styles"]
        here = {str(e["plant_id"]) for e in page._plan["here"]}
        self.assertLessEqual(here, set(styles))
        page._map_btn.setChecked(False)
        self.assertTrue(cleared)


@unittest.skipUnless(_HAVE_QT, "PyQt6 not installed in this env")
class TestPlantedSaysWhatEatsIt(unittest.TestCase):
    """The owner on On This Design's lists: "useful to see a list of all
    planted plants and communities and their stats, but this would be more
    useful along with the other stats of what eats this when"."""

    @classmethod
    def setUpClass(cls):
        cls._app = QApplication.instance() or QApplication(["sp-food-page"])
        _plants_mod.init_db()
        import src.permadesign_api as api
        api._DB_READY = True
        cls.rows = {r["common_name"]: r for r in api.query_plants()}

    def test_each_species_row_says_what_eats_it_and_when(self):
        from src.on_this_design_panel import OnThisDesignPanel
        panel = OnThisDesignPanel()
        self.addCleanup(panel.close)
        cherry = self.rows["Chokecherry"]["id"]
        panel.set_plants_counts({cherry: 3})
        name, line = panel._plants_list.item(0).text().split("\n")
        self.assertEqual(name, "Chokecherry  ×3")
        self.assertRegex(line, r"^feeds \d+: .* · flowers .* · fruit ")

    def test_the_rows_wrap_inside_the_list(self):
        """Qt measured the wrap without the item padding, and the first build
        drew rows 12 to 30 px wider than the list: a sideways scroll bar and
        the end of each line cut off."""
        from src.on_this_design_panel import OnThisDesignPanel
        panel = OnThisDesignPanel()
        self.addCleanup(panel.close)
        panel.resize(380, 600)
        panel.show()
        names = ("Blanketflower", "Boreal Yarrow", "Canada Goldenrod",
                 "Chokecherry", "Red Osier Dogwood", "Wild Strawberry")
        panel.set_plants_counts({self.rows[n]["id"]: 1 for n in names})
        for _ in range(5):
            self._app.processEvents()
        view = panel._plants_list
        self.assertEqual(view.horizontalScrollBar().maximum(), 0)
        for i in range(view.count()):
            rect = view.visualItemRect(view.item(i))
            self.assertLessEqual(rect.width(), view.viewport().width(),
                                 view.item(i).text())
            self.assertGreater(rect.height(), view.fontMetrics().height() * 2,
                               "a row with two lines was given one")

    def test_a_community_row_counts_its_animals_once(self):
        from src.on_this_design_panel import OnThisDesignPanel
        from src.what_it_feeds import animals_fed
        panel = OnThisDesignPanel()
        self.addCleanup(panel.close)
        ids = [self.rows[n]["id"] for n in ("Wild Bergamot", "Chokecherry")]
        panel.set_design_data([
            {"plant_id": pid, "polyculture_name": "Edge",
             "polyculture_center_lat": 53.5, "polyculture_center_lng": -113.5}
            for pid in ids])
        text = panel._communities_list.item(0).text()
        first, line = text.split("\n")
        self.assertTrue(first.startswith("Edge  — 1 instance, 2 members"))
        n = sum(1 for a in animals_fed(ids) if a["food"])
        self.assertTrue(line.startswith(f"feeds {n}: "), line)


if __name__ == "__main__":
    unittest.main()
