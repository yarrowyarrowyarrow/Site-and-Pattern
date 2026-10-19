"""
tests/test_photo_strip.py — a plant's photographs on its page (V3.35, F251):
the first large, the rest as thumbnails, each with its own credit.
"""

import os
import shutil
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

_TMP = tempfile.mkdtemp(prefix="photo_strip_")
import src.db.plants as _plants  # noqa: E402
_plants._DATA_DIR = _TMP
_plants._DB_PATH = os.path.join(_TMP, "permadesign_test.db")

try:
    from PyQt6.QtGui import QColor, QImage
    from PyQt6.QtWidgets import QApplication, QToolButton
    _HAVE_QT = True
except Exception:                                          # noqa: BLE001
    _HAVE_QT = False

OPEN = "https://inaturalist-open-data.s3.amazonaws.com/photos"


def tearDownModule():
    shutil.rmtree(_TMP, ignore_errors=True)


def _app():
    return QApplication.instance() or QApplication(["permadesign-tests"])


def _image(name: str, colour: str) -> str:
    """A local photograph: the cache returns a local path as it is."""
    path = os.path.join(_TMP, name)
    img = QImage(80, 60, QImage.Format.Format_RGB32)
    img.fill(QColor(colour))
    img.save(path)
    return path


def _photos():
    return [
        {"url": _image("a.png", "#c04040"), "slot": "flower",
         "attribution": "(c) Ann, some rights reserved (CC BY)",
         "license": "cc-by"},
        {"url": _image("b.png", "#40c040"), "slot": "habit",
         "attribution": "(c) Bo, some rights reserved (CC BY-SA)",
         "license": "cc-by-sa"},
        {"url": _image("c.png", "#4040c0"), "slot": "fruit",
         "attribution": "no rights reserved, uploaded by Cy", "license": "cc0"},
    ]


@unittest.skipUnless(_HAVE_QT, "PyQt6 not installed in this env")
class TheStrip(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls._app = _app()

    def _strip(self, photos, **kw):
        from src.photo_strip import PhotoStrip
        strip = PhotoStrip(photos, "Woods' Rose", **kw)
        self.addCleanup(strip.deleteLater)
        return strip

    def test_the_first_large_the_rest_as_named_thumbnails(self):
        strip = self._strip(_photos())
        thumbs = strip.findChildren(QToolButton)
        self.assertEqual(len(thumbs), 3)
        self.assertEqual(thumbs[1].accessibleName(),
                         "Photo 2 of 3: the whole plant. (c) Bo, some rights "
                         "reserved (CC BY-SA)")
        self.assertTrue(thumbs[0].isChecked())
        self.assertFalse(strip._big.pixmap().isNull())
        self.assertIn("Ann", strip._credit.text())
        for thumb in thumbs:
            self.assertGreaterEqual(min(thumb.width(), thumb.height()), 24)

    def test_choosing_one_shows_it_with_its_own_credit(self):
        chosen = []
        strip = self._strip(_photos(), on_select=chosen.append)
        strip.findChildren(QToolButton)[2].click()
        self.assertEqual(chosen, [2])
        self.assertEqual(strip.selected(), 2)
        self.assertIn("Cy", strip._credit.text())
        self.assertNotIn("Ann", strip._credit.text())
        self.assertIn("in fruit", strip._big.accessibleName().replace(
            "fruit or seed", "in fruit"))

    def test_one_photo_has_no_thumbnails_and_none_says_so(self):
        self.assertEqual(self._strip(_photos()[:1]).findChildren(QToolButton), [])
        empty = self._strip([])
        self.assertEqual(empty._big.text(), "No photo yet.")
        self.assertFalse(empty._credit.isVisibleTo(empty))

    def test_a_credit_links_to_the_photo_on_inaturalist(self):
        photo = {"url": f"{OPEN}/123/medium.jpg", "slot": "flower",
                 "attribution": "(c) Di, some rights reserved (CC BY)",
                 "license": "cc-by"}
        strip = self._strip([photo])
        self.assertIn('href="https://www.inaturalist.org/photos/123"',
                      strip._credit.text())
        self.assertIn("not downloaded yet", strip._big.text())


@unittest.skipUnless(_HAVE_QT, "PyQt6 not installed in this env")
class ThePage(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls._app = _app()
        _plants.init_db()

    def test_the_page_shows_the_strip_and_keeps_the_choice(self):
        from src.photo_strip import PhotoStrip
        from src.plant_directory import species_entry
        from src.species_page import SpeciesPage
        row = next(r for r in _plants.search_plants(query="saskatoon")
                   if r["common_name"] == "Saskatoon Berry")
        page = SpeciesPage(entry_fn=lambda pid: dict(species_entry(pid),
                                                     photos=_photos()))
        self.addCleanup(page.deleteLater)
        page.resize(400, 700)
        page.show_plant(row)
        page.findChildren(PhotoStrip)[0].findChildren(QToolButton)[1].click()
        page.refresh_photo(row["id"])    # a download landed: a full redraw
        strips = [s for s in page.findChildren(PhotoStrip)
                  if s.parent() is not None and not s.isHidden()]
        self.assertEqual(strips[-1].selected(), 1,
                         "the photo chosen is still the one shown")


if __name__ == "__main__":
    unittest.main()
