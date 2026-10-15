"""
tests/test_one_habitat_score.py — one habitat score per design (V3.20, OV-4).

The Habitat page scored a design against its pin's ecoregion and the Report
card, the PDF, the design critic and the API without one, so one design read
two scores (OVF-1: 78 on Habitat, 83 on the Report card, for the generated
bed). The owner chose the rebased score everywhere (decision O2).
"""

import os
import re
import sys
import tempfile
import types
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

_TMP = tempfile.mkdtemp(prefix="sp_one_score_")
import src.db.plants as _plants_mod  # noqa: E402
_plants_mod._DATA_DIR = _TMP
_plants_mod._DB_PATH = os.path.join(_TMP, "one_score.db")

from src import habitat_score  # noqa: E402

_EDMONTON = (53.5461, -113.4938)


def _project_dict(lat=None, lng=None):
    sc = {} if lat is None else {"latitude": lat, "longitude": lng}
    return {"type": "FeatureCollection", "features": [],
            "properties": {"site_config": sc}}


class OneScore(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        _plants_mod.init_db()
        from src.onboarding import resolve_example_planting
        placements, missing = resolve_example_planting()
        assert not missing, missing
        cls.placed = [{"plant_id": p["plant_id"]} for p in placements]

    def test_the_pin_is_read_from_a_project_however_it_is_carried(self):
        d = _project_dict(*_EDMONTON)
        self.assertEqual(habitat_score.site_pin(d), _EDMONTON)
        self.assertEqual(habitat_score.site_pin(types.SimpleNamespace(project=d)),
                         _EDMONTON)
        self.assertEqual(habitat_score.site_pin(_project_dict()), (None, None))

    def test_the_critic_scores_as_the_habitat_page_does(self):
        from src.design_critic import evaluate_design
        page = habitat_score.compute_habitat_score(
            self.placed, [],
            ecoregion=habitat_score.ecoregion_at(*_EDMONTON)).total
        design = types.SimpleNamespace(project=_project_dict(*_EDMONTON),
                                       placed_plants=self.placed, structures=[])
        self.assertEqual(evaluate_design(design)["total"], page)
        self.assertEqual(habitat_score.score_for_project(
            self.placed, [], lat=_EDMONTON[0], lng=_EDMONTON[1]).total, page)

    def test_without_a_pin_the_score_is_the_universal_one(self):
        self.assertEqual(
            habitat_score.score_for_project(self.placed, []).total,
            habitat_score.compute_habitat_score(self.placed, []).total)

    def test_the_pin_matters_for_the_example(self):
        # 63 without the ecoregion, 64 against Aspen Parkland's own layers:
        # the Report card and Habitat page used to show one each.
        self.assertNotEqual(
            habitat_score.score_for_project(self.placed, []).total,
            habitat_score.score_for_project(
                self.placed, [], lat=_EDMONTON[0], lng=_EDMONTON[1]).total)


class NoPageScoresWithoutThePin(unittest.TestCase):

    def test_the_report_card_pdf_critic_and_api_ask_score_for_project(self):
        root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        for name in ("app.py", "pdf_export.py", "design_critic.py",
                     "permadesign_api.py"):
            with open(os.path.join(root, "src", name), encoding="utf-8") as fh:
                text = fh.read()
            self.assertIsNone(re.search(r"\bcompute_habitat_score\(", text),
                              name)
            self.assertIn("score_for_project(", text, name)


if __name__ == "__main__":
    unittest.main()
