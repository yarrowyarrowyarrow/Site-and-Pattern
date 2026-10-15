"""
tests/test_habitat_page_tidy.py — the Habitat page, tidied (V3.20, OV-11).

R5: "characteristic species" matched on a name's first word, so the worked
example claimed nine and printed "Prairie, Purple, Wild" as species. R37: the
Tallamy line said 90% of insect biodiversity; the finding is 90% of
caterpillar species. Tips and the light/shade mix went (part 06 §7), and so
did the Report card's "What your spend creates".
"""

import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

_TMP = tempfile.mkdtemp(prefix="sp_habitat_tidy_")
import src.db.plants as _plants_mod  # noqa: E402
_plants_mod._DATA_DIR = _TMP
_plants_mod._DB_PATH = os.path.join(_TMP, "habitat_tidy.db")

from src import reference_fidelity  # noqa: E402

_SRC = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                    "src")


def _read(name):
    with open(os.path.join(_SRC, name), encoding="utf-8") as fh:
        return fh.read()


class NamesMatchWhole(unittest.TestCase):

    def test_a_common_name_is_not_its_first_word(self):
        self.assertEqual(reference_fidelity._tokens("Prairie Crocus"),
                         {"prairie crocus"})
        self.assertEqual(
            reference_fidelity._tokens("Amelanchier alnifolia"),
            {"amelanchier alnifolia", "amelanchier"})
        self.assertEqual(
            reference_fidelity._tokens("Wild Bergamot", scientific=False),
            {"wild bergamot"})

    def test_the_examples_matches_are_species(self):
        _plants_mod.init_db()
        from src.onboarding import resolve_example_planting
        placements, missing = resolve_example_planting()
        self.assertEqual(missing, [])
        placed = [_plants_mod.get_plant(p["plant_id"]) for p in placements]
        result = reference_fidelity.fidelity(placed, "aspen_parkland")
        matched = set(result["matched_species"])
        self.assertTrue(matched)
        for word in ("prairie", "purple", "wild"):
            self.assertNotIn(word, matched)
        self.assertTrue(all(" " in m or m.isalpha() for m in matched), matched)


class ThePageSaysWhatIsTrue(unittest.TestCase):

    def test_the_tallamy_line_is_about_caterpillars(self):
        text = _read("analysis_panel.py")
        self.assertNotIn("90% of insect biodiversity", text)
        self.assertIn("90% of caterpillar species", text)
        self.assertIn("Narango, Tallamy & Shropshire 2020", text)

    def test_tips_and_the_light_mix_are_gone(self):
        text = _read("analysis_panel.py")
        for gone in ("Tips for raising your score", "Light / shade mix",
                     "_build_habitat_tips", "set_shade_breakdown"):
            self.assertNotIn(gone, text)
        for name in ("app.py", os.path.join("controllers", "map_events.py")):
            self.assertNotIn("set_shade_breakdown", _read(name), name)

    def test_the_lawn_line_names_what_it_compares(self):
        self.assertNotIn("vs. lawn", _read("analysis_panel.py"))

    def test_the_report_card_no_longer_frames_the_spend(self):
        self.assertNotIn("What your spend creates",
                         _read("on_this_design_panel.py"))


if __name__ == "__main__":
    unittest.main()
