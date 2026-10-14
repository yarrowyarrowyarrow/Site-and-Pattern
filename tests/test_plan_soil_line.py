"""
tests/test_plan_soil_line.py — what the plan says about the soil, and where it
sends you to draw the lawn (V3.19, QF-11).

The first review (R24) read the worked example's plan: "Soil: loam — unknown
texture", calling loam, which is a texture, unknown, because the regional soil
atlas spells its classes ``loam`` and ``sandy_loam`` and the advice table keys
them ``Loam`` and ``Sandy loam``. And "Draw your conversion zones on the map
first (Site → Features)", which is where buildings and trees are entered; the
lawn has been drawn with Draw › Shape since V3.07.
"""

import os
import shutil
import sys
import tempfile
import unittest
from types import SimpleNamespace

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

_TMP = tempfile.mkdtemp(prefix="plan_soil_")
import src.db.plants as _plants  # noqa: E402
_plants._DATA_DIR = _TMP
_plants._DB_PATH = os.path.join(_TMP, "permadesign_test.db")

from src import site_prep  # noqa: E402

try:
    from PyQt6.QtWidgets import QApplication
    _HAVE_QT = True
except Exception:                                          # noqa: BLE001
    _HAVE_QT = False

_APP = None


def setUpModule():
    _plants.init_db()


def tearDownModule():
    shutil.rmtree(_TMP, ignore_errors=True)


def _example():
    """The worked example with the soil the app reads for its pin when it is
    offline (the regional atlas: loam, pH 6.5 around Edmonton), put into the
    design the way the app puts it there."""
    from src import onboarding, property_data, soil_flow
    from src.project_store import ProjectStore
    project, missing = onboarding.build_example_project()
    assert not missing, missing
    sc = project["properties"]["site_config"]
    soil = property_data._prairie_soil_fallback(sc["latitude"],
                                                sc["longitude"])
    sc["soil"] = soil
    soil_flow.apply_soil_site_fields(
        SimpleNamespace(_project=project,
                        plant_panel=SimpleNamespace(set_soil_ph=lambda _ph: 0)),
        soil)
    return project, ProjectStore(project).placed_plants


class _Recorder:
    """A painter that keeps the text it is asked to draw."""

    def __init__(self):
        self.texts = []

    def drawText(self, *args):
        self.texts.append(str(args[-1]))

    def __getattr__(self, _name):
        return lambda *a, **k: None


class TestTheSoilLine(unittest.TestCase):

    def test_every_spelling_of_a_class_is_that_class(self):
        for raw in ("loam", "Loam", " LOAM ", "sandy_loam", "Sandy loam",
                    "silt_loam", "silty clay loam"):
            self.assertIn(site_prep.texture_class(raw),
                          site_prep._TEXTURE_ADVICE, raw)
        self.assertEqual(site_prep.texture_class("sandy_loam"), "Sandy loam")
        self.assertEqual(site_prep.texture_class(None), "")

    def test_the_atlas_spelling_gets_its_advice(self):
        prep = site_prep.build_site_prep(
            {"soil_texture": "loamy_sand",
             "soil": {"fallback": True,
                      "summary": {"texture_class": "loamy_sand"}}},
            [], bed_area_m2=20, get_plant=lambda _p: {})
        self.assertEqual(prep.soil_line, "loamy sand")
        self.assertIn("Sandy ground — choose, don't amend",
                      [s.title for s in prep.steps])

    def test_a_class_the_table_lacks_is_named_not_called_unknown(self):
        prep = site_prep.build_site_prep({"soil_texture": "peat"}, [],
                                         get_plant=lambda _p: {})
        self.assertEqual(prep.soil_line, "peat")

    def test_nothing_known_says_so_once(self):
        text = site_prep.render_prep_text(
            site_prep.build_site_prep({}, [], get_plant=lambda _p: {}))
        # It read "Soil:  Soil texture not known for this site yet", then
        # "pH not known for this site yet" under it.
        self.assertIn("Soil:  not known yet\n", text)
        self.assertNotIn("Soil:  Soil", text)
        self.assertNotIn("pH not known", text)

    def test_a_ph_with_no_texture_is_not_called_unknown_soil(self):
        prep = site_prep.build_site_prep({"soil_ph": 6.5}, [],
                                         get_plant=lambda _p: {})
        self.assertEqual(prep.soil_line, "texture not known yet")
        self.assertEqual(prep.ph_line, "pH 6.5")

    def test_a_texture_with_no_ph_says_which_is_missing(self):
        prep = site_prep.build_site_prep({"soil_texture": "Clay"}, [],
                                         get_plant=lambda _p: {})
        self.assertEqual(prep.soil_line, "clay")
        self.assertEqual(prep.ph_line, "pH not known for this site yet")


class TestTheWorkedExample(unittest.TestCase):
    """The acceptance: the example's plan text."""

    def test_its_plan_text(self):
        from src import planting_plan_export
        from src.planting_plan import build_planting_plan
        project, placed = _example()
        text = planting_plan_export.assemble(
            project, placed, [], build_planting_plan(placed))
        self.assertIn("Soil:  loam\n", text)
        self.assertNotIn("unknown texture", text)
        flat = " ".join(text.split())
        self.assertIn("Draw the lawn you are replacing on the map first, "
                      "with Draw › Shape, and this sheet will size the job.",
                      flat)
        self.assertNotIn("Site → Features", text)

    @unittest.skipUnless(_HAVE_QT, "PyQt6 not installed in this env")
    def test_its_site_prep_page(self):
        global _APP
        _APP = QApplication.instance() or QApplication(["permadesign-tests"])
        from src import pdf_export
        from src.lawn_zones import conversion_summary
        project, placed = _example()
        prep = site_prep.build_site_prep(
            project["properties"]["site_config"], placed,
            lawn_summary=conversion_summary(project["features"]))
        page = _Recorder()
        pdf_export._draw_site_prep(page, 600.0, 800.0, prep, 1.0)
        self.assertEqual(page.texts[1], "Soil: loam   ·   pH 6.5")
        drawn = " ".join(" ".join(page.texts).split())
        self.assertIn("with Draw › Shape,", drawn)
        self.assertNotIn("unknown texture", drawn)
        self.assertNotIn("Site → Features", drawn)


class TestSiteInfo(unittest.TestCase):

    @unittest.skipUnless(_HAVE_QT, "PyQt6 not installed in this env")
    def test_it_names_the_class_the_plan_names(self):
        """Site Info printed the atlas's own spelling, ``loam`` and
        ``sandy_loam``, beside a plan that now says *loam*."""
        global _APP
        _APP = QApplication.instance() or QApplication(["permadesign-tests"])
        from src import property_data
        from src.site_panel import SitePanel
        panel = SitePanel()
        self.addCleanup(panel.deleteLater)
        # The example's atlas row (Edmonton) is loam, the montane row's
        # sandy_loam, the Peace River row's silt_loam.
        for lat, lng in ((53.5, -113.5), (51.5, -116.5), (56.5, -118.0)):
            soil = property_data._prairie_soil_fallback(lat, lng)
            panel._on_soil(soil)
            raw = soil["summary"]["texture_class"]
            self.assertEqual(panel._lbl_soil_texture.text(),
                             site_prep.texture_class(raw))
            self.assertIn(panel._lbl_soil_texture.text(),
                          site_prep._TEXTURE_ADVICE, raw)


if __name__ == "__main__":
    unittest.main()
