"""
tests/test_plant_page_sections.py — the plant page in two modes (PR-4, WD-3,
WD-8; V3.26; docs/homeowner/05-plants-that-lead.md §7).

The simple page is about a hundred words a person can act on; the advanced
page is the long one it was, less the notes (L8, P12), under the ID line.
"""

import os
import shutil
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

_TMP = tempfile.mkdtemp(prefix="page_sections_")
import src.db.plants as _plants  # noqa: E402
_plants._DATA_DIR = _TMP
_plants._DB_PATH = os.path.join(_TMP, "permadesign_test.db")

from src import plant_page_sections as pps  # noqa: E402

try:
    from PyQt6.QtWidgets import QApplication, QLabel, QPushButton
    _HAVE_QT = True
except Exception:                                          # noqa: BLE001
    _HAVE_QT = False

#: What the simple page never says (§8, PR-4's acceptance).
_FORBIDDEN = ("VASCAN", "records, high confidence", "Estimate (",
              "Where these relationships came from", "Roles")


def tearDownModule():
    shutil.rmtree(_TMP, ignore_errors=True)


def _db():
    _plants._DATA_DIR = _TMP
    _plants._DB_PATH = os.path.join(_TMP, "permadesign_test.db")
    _plants.init_db()


def _named(name):
    return next(r for r in _plants.get_all_plants()
                if r["common_name"] == name)


def _entry(name):
    from src.plant_directory import species_entry
    return species_entry(_named(name)["id"])


class TheWords(unittest.TestCase):

    def test_growing_in_words(self):
        self.assertEqual(pps.growing_words(
            {"sun": "full sun,partial shade", "water": "medium,low"}),
            "Full sun to part shade. Dry to average soil.")
        self.assertEqual(pps.growing_words({}), "")

    def test_size_in_words_with_the_one_spacing(self):
        self.assertEqual(pps.size_words(
            {"mature_height_m": 5, "mature_canopy_m": 4.5,
             "years_to_maturity": 1, "spacing_m": 0.33}),
            "Grows to 5 m tall and 4.5 m wide in about 1 year. "
            "Plant 0.35 m apart.")
        self.assertEqual(pps.size_words({}), "")


class TheSimplePage(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        _db()

    def test_chokecherry_exactly(self):
        sections = pps.simple(_entry("Chokecherry"), place="edmonton")
        self.assertEqual([h for h, _b in sections if h != pps.SEASON],
                         ["Top pick", "Why this plant", "Good to know",
                          "Growing it", "Buying it", "Native around Edmonton."])
        self.assertLessEqual(pps.word_count(sections), 150)
        good = dict(sections)["Good to know"]
        self.assertIn("Poisonous to pets if eaten", good)

    def test_no_page_says_what_the_simple_page_keeps_out(self):
        for row in _plants.get_all_plants():
            entry = {"id": row["id"], "scientific_name": row["scientific_name"],
                     "sun": (row.get("sun_requirement") or "").replace("_", " "),
                     "water": row.get("water_needs") or "",
                     "sourcing": {}}
            sections = pps.simple(entry, row, place="edmonton")
            text = " ".join(f"{h} {b}" for h, b in sections)
            for word in _FORBIDDEN:
                self.assertNotIn(word, text, row["common_name"])
            notes = (row.get("notes") or "").strip()
            if len(notes) > 20:
                self.assertNotIn(notes[:20], text, row["common_name"])
            self.assertNotIn("_", text, row["common_name"])
            self.assertLessEqual(pps.word_count(sections), 150,
                                 row["common_name"])

    def test_an_off_list_plant_says_so_once(self):
        from src import native_here
        names = native_here.native_names("edmonton")
        row = next(r for r in _plants.get_all_plants()
                   if r["scientific_name"] not in names
                   and r.get("native_provinces"))
        heads = [h for h, _b in pps.simple({"id": row["id"]}, row,
                                           place="edmonton")]
        self.assertNotIn("Not native here", heads)
        self.assertIn("Not native around Edmonton.", heads)


@unittest.skipUnless(_HAVE_QT, "PyQt6 not installed in this env")
class ThePage(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls._app = QApplication.instance() or QApplication(["permadesign-tests"])
        _db()

    def setUp(self):
        from src.species_page import SpeciesPage
        self.page = SpeciesPage(actions=True, closable=True)
        self.addCleanup(self.page.deleteLater)
        self.page.resize(410, 600)
        self.page.show_plant(_named("Wild Bergamot"))

    def _texts(self):
        return " ".join(l.text() for l in self.page.findChildren(QLabel))

    def test_simple_by_default(self):
        texts = self._texts()
        self.assertIn("Why this plant", texts)
        for word in _FORBIDDEN + ("Notes", pps.ID_LINE):
            self.assertNotIn(word, texts)

    def test_everything_opens_below_and_never_the_notes(self):
        more = self.page.findChild(QPushButton, "speciesPageMore")
        self.assertIsNotNone(more)
        more.click()
        texts = self._texts()
        self.assertIn("Why this plant", texts)
        self.assertIn(pps.MORE, texts)
        self.assertIn(pps.ID_LINE, texts)
        self.assertIn("Roles", texts)
        self.assertIsNone(self.page.findChild(QPushButton, "speciesPageMore"))
        notes = _named("Wild Bergamot").get("notes") or ""
        self.assertTrue(notes)
        self.assertNotIn(notes[:20], texts)

    def test_the_switch_gives_the_long_page_and_a_new_plant_the_short(self):
        self.page.set_advanced_tools(True)
        texts = self._texts()
        self.assertIn("Roles", texts)
        self.assertNotIn("Why this plant", texts)
        self.assertNotIn(pps.MORE, texts)
        self.page.set_advanced_tools(False)
        self.page.findChild(QPushButton, "speciesPageMore").click()
        self.page.show_plant(_named("Chokecherry"))
        self.assertIsNotNone(self.page.findChild(QPushButton,
                                                 "speciesPageMore"))


if __name__ == "__main__":
    unittest.main()
