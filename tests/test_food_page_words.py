"""
tests/test_food_page_words.py — Design › Food reads as words (V3.19, QF-7,
R17).

The first review found the Food page printing the database's source keys
("anbc_alberta_native_bees,sheffield_et_al_2014_grasslands,…") where the
website names the works through ``src/citations.py``, and the flight-season
strip reading "MarAprMayJunJulAugSepOct": a label's rich text drops a span's
padding and margin, so the months ran together. Checked on the worked example,
where the review saw both.
"""

import os
import re
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

_TMP = tempfile.mkdtemp(prefix="sp_food_words_")
import src.db.plants as _plants_mod  # noqa: E402
_plants_mod._DATA_DIR = _TMP
_plants_mod._DB_PATH = os.path.join(_TMP, "food_words.db")

try:
    from PyQt6.QtGui import QTextDocument
    from PyQt6.QtWidgets import QApplication
    _HAVE_QT = True
except ImportError:                                        # pragma: no cover
    _HAVE_QT = False

#: A database key: lower-case words joined by underscores.
_KEY = re.compile(r"\b[a-z0-9]+_[a-z0-9_]+\b")
_MONTHS = ("Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec")
#: Two month names with nothing between them: "MarApr".
_RUN_TOGETHER = re.compile(rf"(?:{_MONTHS})(?:{_MONTHS})")


def _plain(html: str) -> str:
    doc = QTextDocument()
    doc.setHtml(html)
    return doc.toPlainText()


@unittest.skipUnless(_HAVE_QT, "PyQt6 not installed in this env")
class TestTheFoodPageReadsAsWords(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls._app = QApplication.instance() or QApplication(["sp-food-words"])
        _plants_mod.init_db()
        from src.onboarding import resolve_example_planting
        placements, missing = resolve_example_planting()
        assert not missing, missing
        cls.placed = [{"plant_id": p["plant_id"]} for p in placements]

    def _page(self):
        from src.food_page import FoodPage
        page = FoodPage()
        self.addCleanup(page.close)
        page.set_placed_plants(self.placed)
        page.refresh()
        return page

    def _each(self, page, taxon):
        """Each animal of ``taxon`` the example feeds, shown in turn."""
        combo, seen = page._animal, 0
        for i in range(combo.count()):
            data = combo.itemData(i)
            if data and data["taxon"] == taxon:
                combo.setCurrentIndex(i)
                seen += 1
                yield data
            if seen >= 12:
                break
        self.assertGreater(seen, 0, f"the example feeds no {taxon}")

    def test_the_bee_footnote_names_its_sources(self):
        page, cited = self._page(), []
        for _bee in self._each(page, "bee"):
            note = page._footnote.text()
            self.assertEqual(_KEY.findall(note), [], note)
            if (page._plan.attrs or {}).get("source"):
                self.assertIn("Sources: ", note)
                cited.append(note)
        self.assertTrue(cited, "no bee in the example carries its sources")
        self.assertIn("Sheffield et al. 2014", cited[0])

    def test_the_flight_season_reads_as_months(self):
        page = self._page()
        strips = 0
        for _bee in self._each(page, "bee"):
            if not page._plan.forage.flight_months:    # a sentence, no strip
                continue
            words = _plain(page._when_box.text())
            self.assertEqual(_RUN_TOGETHER.findall(words), [], words)
            self.assertRegex(words, r"Mar\s+Apr\s+May")
            strips += 1
        self.assertGreater(strips, 0, "no bee in the example has a strip")

    def test_no_bee_in_the_catalogue_cites_a_key(self):
        """Every source a bee's facts rest on, not only the example's."""
        import json
        from src.food_page import FoodPage
        from src.resources import resource_path
        with open(resource_path("data", "bee_attributes_master.json"),
                  encoding="utf-8") as fh:
            sources = {row.get("source") or "" for row in json.load(fh)}
        for source in sources:
            line = FoodPage._sources(source)
            self.assertEqual(_KEY.findall(line), [], line)
            if source:
                self.assertTrue(line.startswith(" Sources: "), line)

    def test_any_animals_months_read_as_months(self):
        page = self._page()
        for _animal in self._each(page, "lepidoptera"):
            words = _plain(page._when_box.text())
            self.assertEqual(_RUN_TOGETHER.findall(words), [], words)
            self.assertRegex(words, r"Jan\s+Feb\s+Mar")


if __name__ == "__main__":
    unittest.main()
