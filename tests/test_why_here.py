"""
tests/test_why_here.py — why the generator put a plant there (F19, V3.05).

The generator scores every open cell for each plant (65% ecological fit, the
rest composition and spread) and kept none of it: a generated design could not
say why its milkweed was by the fence. The chosen cell's sub-scores are now
read back in words, carried on the plant's feature (``why_here``), and shown
first on its page when it is clicked on the map. With no terrain or shade for
the site the generator only spreads plants out, and says exactly that. A plant
placed by a rule rather than a score (a vine at its host's foot, a mixed stand,
a community, what the design review added, a pond plant) names the rule
(``src/why_here.py``).
"""

import os
import shutil
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

_TMP = tempfile.mkdtemp(prefix="sp_why_here_")
import src.db.plants as _plants  # noqa: E402
_plants._DATA_DIR = _TMP
_plants._DB_PATH = os.path.join(_TMP, "permadesign_test.db")

from src.placement_score import (CellEnv, NO_SITE_DATA_WHY,  # noqa: E402
                                 explain_cell_for_plant)

try:
    from PyQt6.QtWidgets import QApplication, QLabel
    _HAVE_QT = True
except Exception:                                          # noqa: BLE001
    _HAVE_QT = False


def tearDownModule():
    shutil.rmtree(_TMP, ignore_errors=True)


SUNNY_LOW = CellEnv(shade_fraction=0.05, elevation_pct=0.1, slope_pct=1.0,
                    aspect_deg=-1.0, is_edge=False)
SHADY_HIGH = CellEnv(shade_fraction=0.8, elevation_pct=0.9, slope_pct=1.0,
                     aspect_deg=-1.0, is_edge=False)


class TestTheWords(unittest.TestCase):

    def test_a_good_fit_says_so(self):
        why = explain_cell_for_plant(
            {"sun_requirement": "full_sun", "water_needs": "high"}, SUNNY_LOW)
        self.assertEqual(why[0], "Full sun, as it likes")
        self.assertEqual(why[1], "Low, moister ground, as it likes")

    def test_a_compromise_says_it_is_one(self):
        why = explain_cell_for_plant(
            {"sun_requirement": "full_sun", "water_needs": "high"}, SHADY_HIGH)
        self.assertIn("not its best", why[0])
        self.assertIn("not its best", why[1])

    def test_the_positioner_keeps_the_chosen_cells_reasons(self):
        from src.llm_design import ScoredPositioner
        cells = [(53.5, -113.5), (53.5001, -113.5)]
        pos = ScoredPositioner({cells[0]: SUNNY_LOW, cells[1]: SHADY_HIGH},
                               None, cells)
        got = pos.take_best({"sun_requirement": "full_sun",
                             "water_needs": "high", "plant_type": "wildflower"})
        self.assertEqual(got, cells[0])
        self.assertEqual(pos.last_why[0], "Full sun, as it likes")

    def test_the_reasons_ride_on_the_group_just_placed(self):
        from src.why_here import stamp as _stamp_why

        class _Proj:
            def __init__(self):
                self.d = {"features": [
                    {"properties": {"element_type": "plant"}},
                    {"properties": {"element_type": "plant"}},
                    {"properties": {"element_type": "plant"}}]}

            def as_dict(self):
                return self.d

        p = _Proj()
        _stamp_why(p, 2, ["Full sun, as it likes"])
        props = [f["properties"] for f in p.d["features"]]
        self.assertNotIn("why_here", props[0])
        self.assertEqual(props[1]["why_here"], ["Full sun, as it likes"])
        self.assertEqual(props[2]["why_here"], ["Full sun, as it likes"])
        _stamp_why(p, 3, [])                        # nothing to say, nothing written
        self.assertNotIn("why_here", props[0])

    def test_the_feature_keeps_them_through_the_store(self):
        from src.project_store import ProjectStore, plant_record_from_feature
        project = {"type": "FeatureCollection", "features": []}
        store = ProjectStore(project, [])
        store.add_plant(1, "Wild Bergamot", 53.5, -113.5,
                        why_here=[NO_SITE_DATA_WHY])
        rec = plant_record_from_feature(project["features"][0])
        self.assertEqual(rec["why_here"], [NO_SITE_DATA_WHY])
        store.add_plant(2, "Yarrow", 53.6, -113.5)       # by hand: no reasons
        self.assertNotIn("why_here", project["features"][1]["properties"])


class TestEveryRuleNamesItself(unittest.TestCase):
    """A generated design end to end, with a fake model: the plants the
    generator scored, and the ones it placed by a rule."""

    @classmethod
    def setUpClass(cls):
        import src.permadesign_api as api
        _plants.init_db()
        api._DB_READY = True

    def _generate(self, spec, **kw):
        import src.llm_design as llm

        class _Client:
            endpoint, model = "fake://", "fake"

            def generate_spec(self, prompt, context, extra_hints=None):
                return spec

        lat0, lng0, d = 53.5461, -113.4938, 0.0006
        ring = [[lat0, lng0], [lat0, lng0 + 2 * d], [lat0 + d, lng0 + 2 * d],
                [lat0 + d, lng0], [lat0, lng0]]
        return llm.generate_design(
            "habitat", site_config={"latitude": lat0, "longitude": lng0},
            boundary=ring, client=_Client(), revise=False, density="sparse",
            **kw)

    def _plants(self, project):
        return [f["properties"] for f in project.as_dict()["features"]
                if f["properties"].get("element_type") == "plant"]

    def test_vines_stands_and_communities_say_how_they_were_placed(self):
        from src import why_here
        project = self._generate({
            "plants": [{"query": "trembling aspen", "quantity": 1},
                       {"query": "clematis", "quantity": 1}],
            "plant_mixes": [{"plants": [{"query": "blue grama"},
                                        {"query": "prairie crocus"}],
                             "quantity": 6}],
            "communities": [{"query": "Backyard Meadow Patch"}]})
        plants = self._plants(project)
        vines = [p for p in plants if "Clematis" in p.get("common_name", "")]
        stand = [p for p in plants
                 if p.get("common_name") in ("Blue Grama Grass", "Prairie Crocus")
                 and not p.get("polyculture_name")]
        community = [p for p in plants
                     if p.get("polyculture_name") == "Backyard Meadow Patch"]
        self.assertTrue(vines and stand and community,
                        (len(vines), len(stand), len(community)))
        # A vine with no host left to climb is placed by score like any plant.
        self.assertIn([why_here.VINE_SEAT], [p.get("why_here") for p in vines])
        self.assertTrue(all(p.get("why_here") for p in vines))
        for p in stand:
            self.assertEqual(p["why_here"][0], why_here.MIX)
        for p in community:
            self.assertEqual(p["why_here"], [why_here.COMMUNITY.format(
                name="Backyard Meadow Patch")])

    def test_the_review_says_why_it_added_a_plant(self):
        from src import why_here
        from src.design_critic import apply_repairs
        from src.permadesign_api import Project, query_plants
        project = Project.create("t", site_config={"latitude": 53.5,
                                                   "longitude": -113.5})
        project.place_plant(query_plants(query="yarrow")[0]["id"], 53.5, -113.5)
        msgs = apply_repairs(project, query_plants, lambda row: (53.5, -113.5))
        self.assertTrue(msgs)
        added = self._plants(project)[1:]
        self.assertEqual(len(added), len(msgs))
        for p in added:
            self.assertTrue(p["why_here"][0].startswith(
                why_here.REVIEW.split("{")[0]), p)


@unittest.skipUnless(_HAVE_QT, "PyQt6 not installed in this env")
class TestThePage(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls._app = QApplication.instance() or QApplication(["sp-tests"])
        _plants.init_db()

    def _texts(self, page):
        return [l.text() for l in page.findChildren(QLabel)]

    def test_why_here_comes_first_when_given_and_not_otherwise(self):
        from src.db.plants import search_plants
        from src.species_page import SpeciesPage
        row = search_plants()[0]
        page = SpeciesPage()
        page.show_plant(row, why=["Full sun, as it likes",
                                  "Low, moister ground, as it likes"])
        joined = " ".join(self._texts(page))
        self.assertIn("Why here", joined)
        self.assertIn("Full sun, as it likes. Low, moister ground, as it likes.",
                      joined)
        page.show_plant(row)                     # opened from the list
        self.assertNotIn("Why here", " ".join(self._texts(page)))


if __name__ == "__main__":
    unittest.main()
