"""
tests/test_field_sheet.py — the site-walk sheet (F32, V3.05).

Site › Field Notes asks ten questions only the ground can answer; until V3.05
they could only be answered holding a laptop in the yard. The sheet prints them
with room to write, alone (``export_field_sheet``) and as the first job in the
design PDF, before Site prep.

Pages are counted from the PDF's own objects, since pypdf is not a dependency.
"""

import os
import re
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from src.field_notes import FIELD_PROMPTS, walk_sheet  # noqa: E402

try:
    from PyQt6.QtWidgets import QApplication
    _HAVE_QT = True
except Exception:                                          # noqa: BLE001
    _HAVE_QT = False


def _pages(path) -> int:
    with open(path, "rb") as fh:
        return len(re.findall(rb"/Type\s*/Page[^s]", fh.read()))


class TestTheRows(unittest.TestCase):

    def test_every_prompt_in_walking_order_then_the_catch_all(self):
        rows = walk_sheet({})
        self.assertEqual([r["question"] for r in rows[:-1]],
                         [q for _, q in FIELD_PROMPTS])
        self.assertEqual(rows[-1]["key"], "free_text")

    def test_what_is_noted_goes_out_with_the_sheet(self):
        rows = walk_sheet({"observations": {
            "water_pools": {"checked": True, "note": "low corner by the fence"}},
            "free_text": "magpies nest in the spruce"})
        first = rows[0]
        self.assertTrue(first["checked"])
        self.assertEqual(first["note"], "low corner by the fence")
        self.assertEqual(rows[-1]["note"], "magpies nest in the spruce")
        self.assertFalse(rows[1]["checked"])


@unittest.skipUnless(_HAVE_QT, "PyQt6 not installed in this env")
class TestThePage(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls._app = QApplication.instance() or QApplication(["sp-tests"])

    def test_the_sheet_alone_is_one_page(self):
        from src.pdf_export import export_field_sheet
        path = os.path.join(tempfile.mkdtemp(), "walk.pdf")
        export_field_sheet(path, {"type": "FeatureCollection", "features": [],
                                  "properties": {}})
        with open(path, "rb") as fh:
            self.assertEqual(fh.read(5), b"%PDF-")
        self.assertEqual(_pages(path), 1)

    def test_the_design_pdf_carries_it(self):
        from src.pdf_export import export_pdf
        project = {"type": "FeatureCollection", "features": [],
                   "properties": {"project_name": "Test yard"}}
        path = os.path.join(tempfile.mkdtemp(), "design.pdf")
        export_pdf(path, project, [], [], "")
        # The title page and the walk sheet, with nothing placed to plan.
        self.assertGreaterEqual(_pages(path), 2)


if __name__ == "__main__":
    unittest.main()
