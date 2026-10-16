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

    def test_a_missing_planting_map_says_why(self):
        """The planting map page used to be dropped silently when it couldn't
        be built, so a user who asked for "a printable 2-D map with legend" got
        a PDF without one and no way to tell whether the feature existed. The
        design here has plants but no property boundary — and the map is a
        scale drawing, so it needs the outline to measure from."""
        from src.pdf_export import export_pdf
        _project, placed, structs = self._sample()
        no_boundary = {"properties": {"project_name": "T"}, "features": []}
        out = os.path.join(self._tmp, "no_map.pdf")
        export_pdf(out, no_boundary, placed, structs, notes="")
        self.assertTrue(os.path.exists(out))

        empty = os.path.join(self._tmp, "no_plants.pdf")
        export_pdf(empty, no_boundary, [], [], notes="")
        # An explanation page is only worth printing when there ARE plants to
        # map; an empty design needs no excuse.
        self.assertGreater(os.path.getsize(out), os.path.getsize(empty))

    def test_presentation_still_page_renders(self):
        """The F69 still page referenced `still_pixmap` and `still_caption`
        without either being a parameter, so export_pdf raised NameError on
        EVERY call and PDF export was dead from V2.33 until V2.37. It went
        unnoticed because these tests skip without PyQt6, which the CI image
        did not have. Passing a still exercises the branch that was never
        reachable."""
        from PyQt6.QtGui import QPixmap
        from PyQt6.QtCore import Qt
        from src.pdf_export import export_pdf
        project, placed, structs = self._sample()
        still = QPixmap(240, 160)
        still.fill(Qt.GlobalColor.darkGreen)
        out = os.path.join(self._tmp, "with_still.pdf")
        export_pdf(out, project, placed, structs, notes="",
                   still_pixmap=still, still_caption="Year 5, June")
        self.assertTrue(os.path.exists(out))

        plain = os.path.join(self._tmp, "no_still.pdf")
        export_pdf(plain, project, placed, structs, notes="")
        self.assertGreater(os.path.getsize(out), os.path.getsize(plain),
                           "the still did not add a page")


def _string_literals(module_path) -> list:
    """Every string constant in a module's code, docstrings and comments left
    out: what the code can draw, not what its notes say about the past."""
    import ast
    tree = ast.parse(module_path.read_text(encoding="utf-8"))
    docs = set()
    for node in ast.walk(tree):
        if isinstance(node, (ast.Module, ast.FunctionDef, ast.ClassDef,
                             ast.AsyncFunctionDef)) and node.body:
            first = node.body[0]
            if isinstance(first, ast.Expr) and isinstance(
                    getattr(first, "value", None), ast.Constant):
                docs.add(id(first.value))
    return [n.value for n in ast.walk(tree)
            if isinstance(n, ast.Constant) and isinstance(n.value, str)
            and id(n) not in docs]


def _pdf_module():
    import pathlib
    return (pathlib.Path(__file__).resolve().parent.parent
            / "src" / "pdf_export.py")


def _contrast(fg: str, bg: str) -> float:
    """WCAG 2 contrast ratio of two #rrggbb colours."""
    def lum(h):
        h = h.lstrip("#")
        c = [int(h[i:i + 2], 16) / 255 for i in (0, 2, 4)]
        c = [x / 12.92 if x <= 0.03928 else ((x + 0.055) / 1.055) ** 2.4
             for x in c]
        return 0.2126 * c[0] + 0.7152 * c[1] + 0.0722 * c[2]
    hi, lo = sorted((lum(fg), lum(bg)), reverse=True)
    return (hi + 0.05) / (lo + 0.05)


@unittest.skipUnless(_qt_available(), "PyQt6 not installed in this env")
class TestThePrintedPageCanBeRead(unittest.TestCase):
    """V3.18, first-pass review R1: the body of every text page was drawn in
    the app's dark-theme greens on white paper, rows at 1.34:1 and headings at
    1.64:1, so a printed buy list was close to blank."""

    def test_text_on_the_page_is_at_least_4_5_to_1(self):
        from src import pdf_export as pe
        for name in ("INK", "HEAD", "MUTED"):
            self.assertGreaterEqual(_contrast(getattr(pe, name), "#ffffff"),
                                    4.5, name)

    def test_text_on_the_title_bar_is_at_least_4_5_to_1(self):
        from src import pdf_export as pe
        for name in ("BAR_TEXT", "BAR_SUBTEXT"):
            self.assertGreaterEqual(_contrast(getattr(pe, name), pe.BAR),
                                    4.5, name)

    def test_the_pale_greens_are_only_ever_bar_colours(self):
        """Each pale colour may appear once in the code, as its constant; a
        literal anywhere else is pale text on white paper again."""
        literals = [v.lower() for v in _string_literals(_pdf_module())]
        for colour in ("#a5d6a7", "#c8e6c9", "#78909c", "#90a4ae"):
            self.assertLessEqual(literals.count(colour), 1, colour)


@unittest.skipUnless(_qt_available(), "PyQt6 not installed in this env")
class TestThePlaceLine(unittest.TestCase):
    """V3.18, EDF-2: every PDF was subtitled "Edmonton, Alberta" wherever the
    pin was. It now says where the design's own pin is, or nothing."""

    def test_an_address_without_its_postal_code_and_country(self):
        from src.pdf_export import place_line
        sc = {"pin_label": "10123, 99 Street NW, Downtown, Edmonton, "
                           "Alberta, T5J 0H5, Canada",
              "latitude": 53.54, "longitude": -113.49}
        self.assertEqual(place_line(sc),
                         "10123, 99 Street NW, Downtown, Edmonton, Alberta")

    def test_a_pin_with_no_address_gives_its_coordinates(self):
        from src.pdf_export import place_line
        self.assertEqual(place_line({"latitude": 50.4452,
                                     "longitude": -104.6189}),
                         "50.4452, -104.6189")

    def test_a_pin_with_no_address_in_the_region_names_the_region(self):
        """V3.24 (ED-5): the region pack's name, never a borrowed one; a
        Regina pin's line (above) does not say Edmonton."""
        from src.pdf_export import place_line
        self.assertEqual(place_line({"latitude": 53.54, "longitude": -113.49}),
                         "Edmonton region, Alberta")
        self.assertNotIn("Edmonton", place_line({"latitude": 50.4452,
                                                 "longitude": -104.6189}))

    def test_no_pin_claims_no_place(self):
        from src.pdf_export import place_line
        self.assertEqual(place_line({}), "")
        self.assertEqual(place_line(None), "")

    def test_edmonton_is_no_longer_written_into_every_pdf(self):
        self.assertFalse([v for v in _string_literals(_pdf_module())
                          if "Edmonton" in v])


@unittest.skipUnless(_qt_available(), "PyQt6 not installed in this env")
class TestTheSummaryCountsEveryType(unittest.TestCase):
    """V3.18: the summary named six types and not wildflower or grass, so the
    worked example's 19 plants printed as "3 shrubs, 2 groundcovers"."""

    def test_wildflowers_and_grasses_are_counted(self):
        from collections import Counter
        from src.pdf_export import type_breakdown
        self.assertEqual(
            type_breakdown(Counter({"shrub": 3, "wildflower": 12,
                                    "grass": 3, "groundcover": 1})),
            "3 shrubs, 12 wildflowers, 1 groundcover, 3 grasses")

    def test_every_catalogue_type_has_a_word(self):
        from src.pdf_export import _TYPE_PLURALS
        from src.plant_facets import _TYPE_LABELS
        self.assertEqual(set(_TYPE_LABELS) - set(_TYPE_PLURALS), set())

    def test_an_unknown_or_missing_type_is_still_counted(self):
        from collections import Counter
        from src.pdf_export import type_breakdown
        self.assertEqual(type_breakdown(Counter({None: 1, "aquatic": 2})),
                         "2 aquatic plants, 1 other")


@unittest.skipUnless(_qt_available(), "PyQt6 not installed in this env")
class TestTheNotesWrap(unittest.TestCase):
    """V3.18: the notes page cut every line at the right edge and dropped
    whatever ran past the bottom of the page."""

    def _fits(self, n):
        return lambda text: len(text) <= n

    def test_a_long_line_wraps_and_keeps_every_word(self):
        from src.pdf_export import wrap_line
        line = "the quick brown fox jumps over the lazy dog " * 3
        parts = wrap_line(line, self._fits(20))
        self.assertGreater(len(parts), 3)
        self.assertTrue(all(len(p) <= 20 for p in parts), parts)
        self.assertEqual(" ".join(parts).split(), line.split())

    def test_a_wrapped_bullet_hangs_under_its_text(self):
        from src.pdf_export import wrap_line
        parts = wrap_line("  • Design → Habitat: see its score, then look",
                          self._fits(24))
        self.assertTrue(parts[0].startswith("  • Design"), parts)
        self.assertTrue(all(p.startswith("    ") for p in parts[1:]), parts)

    def test_a_blank_line_stays_a_blank_line(self):
        from src.pdf_export import wrap_line
        self.assertEqual(wrap_line("", self._fits(20)), [""])

    def test_a_word_too_long_for_any_line_is_printed_whole(self):
        from src.pdf_export import wrap_line
        self.assertEqual(wrap_line("a " + "x" * 40, self._fits(20)),
                         ["a", "x" * 40])

    def test_long_notes_take_more_pages_rather_than_stopping(self):
        import re
        from src.pdf_export import export_pdf
        tmp = tempfile.mkdtemp(prefix="permadesign_pdf_notes_")
        from PyQt6.QtWidgets import QApplication
        QApplication.instance() or QApplication(["permadesign-tests"])

        def pages(notes):
            out = os.path.join(tmp, f"n{len(notes)}.pdf")
            export_pdf(out, {"properties": {}, "features": []}, [], [],
                       notes=notes)
            with open(out, "rb") as fh:
                return len(re.findall(rb"/Type\s*/Page\b(?!s)", fh.read()))

        short = pages("One line.")
        long_ = pages("\n".join(f"Line {i} of the notes." for i in range(200)))
        self.assertGreater(long_, short)


if __name__ == "__main__":
    unittest.main()


@unittest.skipUnless(_qt_available(), "PyQt6 not installed in this env")
class TestTheFirstPageIsTheOverview(unittest.TestCase):
    """OV-12 (V3.27): the screen and the print say the same things."""

    @classmethod
    def setUpClass(cls):
        cls._tmp = tempfile.mkdtemp(prefix="permadesign_pdf_overview_")
        import src.db.plants as plants_mod
        plants_mod._DATA_DIR = cls._tmp
        plants_mod._DB_PATH = os.path.join(cls._tmp, "t.db")
        plants_mod.init_db()
        from PyQt6.QtWidgets import QApplication
        cls._app = QApplication.instance() or QApplication(["permadesign-tests"])

    def test_the_six_titles_and_the_plant_cost(self):
        import shutil
        import subprocess
        if not shutil.which("pdftotext"):
            self.skipTest("pdftotext not installed")
        from src.onboarding import build_example_project
        from src.pdf_export import export_pdf
        from src.project_store import ProjectStore
        from src import yard_overview_items as yi
        project, _missing = build_example_project()
        placed = list(ProjectStore(project).placed_plants)
        out = os.path.join(self._tmp, "overview.pdf")
        export_pdf(out, project, placed, [], notes="")
        text = subprocess.run(["pdftotext", "-layout", out, "-"],
                              capture_output=True, text=True,
                              encoding="utf-8").stdout
        flat = " ".join(text.split())
        for item in yi.overview(project):
            self.assertIn(item.title, flat)
        cost = next(it for it in yi.overview(project) if it.key == "cost")
        self.assertIn(cost.lines[0].split(" for ")[0], flat)
        self.assertNotIn("Habitat Value Score", flat)
