"""
tests/test_pioneer_retired.py — "pioneer" is not a word a person reads (V3.19,
WD-6).

``docs/homeowner/09-words.md`` puts *pioneer* in the Never column, and
``docs/review.md`` had already banned it, yet the phased plan said "Plant
pioneer species to hold the soil", the PDF's care bands "Years 1–2 · Pioneer
forbs", Over time "pioneer forbs fill in first", Growth Snapshots "faint plants
are pioneers fading", the succession lesson "Pioneers — fast, sun-loving…" and
the website's role facet "Pioneer". What a person reads now says quick
starters, the first wildflowers, the early ones giving way. The successional
role keeps its key (``"pioneer"``) inside: only the words changed.
"""

import ast
import os
import pathlib
import re
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

_SRC = pathlib.Path(__file__).resolve().parent.parent / "src"

#: A lower-case identifier ("pioneer", "early_successional") is a key the
#: code compares against, not a word anybody reads.
_KEY = re.compile(r"^[a-z_]+$")


def _prose_saying_pioneer(path: pathlib.Path) -> list:
    """Every string constant in ``path`` that says pioneer, docstrings and
    keys aside, as ``"file:line: text"``. Parts of an f-string count."""
    tree = ast.parse(path.read_text(encoding="utf-8"))
    docstrings = set()
    for node in ast.walk(tree):
        if isinstance(node, (ast.Module, ast.ClassDef, ast.FunctionDef,
                             ast.AsyncFunctionDef)) and node.body:
            first = node.body[0]
            if (isinstance(first, ast.Expr)
                    and isinstance(first.value, ast.Constant)
                    and isinstance(first.value.value, str)):
                docstrings.add(id(first.value))
    found = []
    for node in ast.walk(tree):
        if (isinstance(node, ast.Constant) and isinstance(node.value, str)
                and id(node) not in docstrings
                and "pioneer" in node.value.lower()
                and not _KEY.match(node.value)):
            found.append(f"{path.parent.name}/{path.name}:{node.lineno}: "
                         f"{node.value.strip()[:60]!r}")
    return found


class TestNoScreenSaysPioneer(unittest.TestCase):

    def test_no_string_a_person_reads_says_pioneer(self):
        found = []
        for path in sorted(_SRC.rglob("*.py")):
            found += _prose_saying_pioneer(path)
        self.assertEqual(found, [], "pioneer is in the Never column of "
                         "docs/homeowner/09-words.md")

    def test_the_scan_sees_an_f_string_and_skips_a_key(self):
        """The scan is the guard, so it is checked against the shapes the
        words came in."""
        import tempfile
        with tempfile.TemporaryDirectory() as tmp:
            probe = pathlib.Path(tmp) / "probe.py"
            probe.write_text(
                '"""Docstrings may say pioneer."""\n'
                'role = "pioneer"\n'
                'line = f"{n} pioneer species fading"\n'
                'label = "Pioneer"\n', encoding="utf-8")
            found = _prose_saying_pioneer(probe)
        self.assertEqual(len(found), 2, found)


class TestTheWordsThatReplaceIt(unittest.TestCase):

    def test_the_first_stage_is_the_first_wildflowers(self):
        from src.succession import restoration_stage, year_label
        self.assertEqual(restoration_stage(1), "First wildflowers")
        self.assertEqual(year_label(2), "Year 2 · First wildflowers")

    def test_the_phased_plan_says_quick_starters(self):
        from src import conversion_plan as cp
        plants = {1: {"id": 1, "common_name": "Fireweed", "plant_type": "herb",
                      "permaculture_uses": "early_successional"}}
        sched = cp.build_conversion_schedule(
            [{"plant_id": 1, "common_name": "Fireweed"}],
            get_plant=lambda pid: dict(plants.get(pid, {})))
        text = cp.render_schedule_text(sched)
        self.assertIn("Plant quick starters to hold the soil: Fireweed.", text)
        self.assertIn("Years 1–2 · First wildflowers", text)
        self.assertNotIn("pioneer", text.lower())

    def test_the_printed_care_bands_do_not_say_it(self):
        """The PDF's "Years 1–2 · Pioneer forbs" came from these bands."""
        from src import maintenance_calendar as mc
        cal = mc.build_maintenance_calendar(
            [{"plant_id": 1, "common_name": "Fireweed"}],
            get_plant=lambda _p: {"plant_type": "herb"},
            fauna_edges=lambda _ids: [])
        text = mc.render_maintenance_text(cal)
        self.assertIn("First wildflowers", text)
        self.assertNotIn("pioneer", text.lower())

    def test_the_lesson_says_quick_starters(self):
        from src.lesson_track import _step_succession
        early = {"common_name": "Fireweed", "plant_type": "herb",
                 "permaculture_uses": "early_successional"}
        late = {"common_name": "White Spruce", "plant_type": "tree",
                "years_to_maturity": 40}
        for rows in ([early, late], [early], [late], []):
            step = _step_succession(rows)
            words = " ".join(str(v) for v in step.values())
            self.assertNotIn("pioneer", words.lower(), rows)
        self.assertIn("quick starter",
                      _step_succession([early, late])["your_design"])

    def test_the_website_names_the_role_plainly(self):
        from src.site_facets import _ROLES
        self.assertEqual(_ROLES["early_successional"], "Quick starter")


if __name__ == "__main__":
    unittest.main()
