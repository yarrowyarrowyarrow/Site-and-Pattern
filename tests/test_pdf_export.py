"""
tests/test_pdf_export.py

P2 — the printable planting plan. Smoke-tests that export_pdf renders a
non-trivial PDF (title + map placeholder + summary with habitat score &
cost, plant list with nursery sources, notes) without raising. Qt smoke
test; skips when PyQt6 isn't installed.

    QT_QPA_PLATFORM=offscreen python -m unittest tests.test_pdf_export -v
"""

import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")


def _qt_available():
    try:
        import PyQt6  # noqa: F401
        from PyQt6.QtWidgets import QApplication  # noqa: F401
        from PyQt6.QtPrintSupport import QPrinter  # noqa: F401
        return True
    except Exception:
        return False


@unittest.skipUnless(_qt_available(), "PyQt6 not installed in this env")
class TestPdfExport(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls._tmp = tempfile.mkdtemp(prefix="permadesign_pdf_test_")
        import src.db.plants as plants_mod
        plants_mod._DATA_DIR = cls._tmp
        plants_mod._DB_PATH = os.path.join(cls._tmp, "t.db")
        from src.db.plants import init_db
        init_db()
        from PyQt6.QtWidgets import QApplication
        cls._app = QApplication.instance() or QApplication(["permadesign-tests"])

    def _sample(self):
        from src.db.plants import search_plants
        rows = search_plants()
        tree = next(r for r in rows if r["plant_type"] == "tree")
        herb = next(r for r in rows if r["plant_type"] == "herb")
        placed = [
            {"plant_id": tree["id"], "common_name": tree["common_name"],
             "plant_type": "tree"},
            {"plant_id": herb["id"], "common_name": herb["common_name"],
             "plant_type": "herb"},
        ]
        structs = [{"id": "pond", "name": "Pond"}]
        project = {
            "properties": {"project_name": "Test Yard", "hardiness_zone": "3a"},
            "features": [
                {"properties": {"element_type": "custom_shape", "area_m2": 40.0}}
            ],
        }
        return project, placed, structs

    def test_export_writes_nontrivial_pdf(self):
        from src.pdf_export import export_pdf
        project, placed, structs = self._sample()
        out = os.path.join(self._tmp, "design.pdf")
        export_pdf(out, project, placed, structs, notes="Soil test pending.")
        self.assertTrue(os.path.exists(out))
        self.assertGreater(os.path.getsize(out), 2000)
        # PDF magic header
        with open(out, "rb") as f:
            self.assertEqual(f.read(5), b"%PDF-")

    def test_export_handles_empty_design(self):
        # No plants / structures / map — must not raise.
        from src.pdf_export import export_pdf
        out = os.path.join(self._tmp, "empty.pdf")
        export_pdf(out, {"properties": {}, "features": []}, [], [], notes="")
        self.assertTrue(os.path.exists(out))


if __name__ == "__main__":
    unittest.main()
