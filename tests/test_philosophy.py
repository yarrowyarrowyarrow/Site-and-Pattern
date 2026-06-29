"""
tests/test_philosophy.py — keep the design philosophy woven into the code.

The design philosophy ("Site & Pattern — Design Philosophy & Intellectual
Foundation") is documented in docs/DESIGN_PHILOSOPHY.md, and the strongly-aligned
modules carry a one-line ``Design principle P# — see docs/DESIGN_PHILOSOPHY.md``
anchor. This test freezes that weave so it can't silently rot — the same
"the contract is a test" discipline as test_architecture_guard.py:

  1. The philosophy doc exists and documents all eleven core themes.
  2. Every ``Design principle P#`` anchor in src/ names a real principle (1–11),
     and the convention is actually in use across several modules.
  3. The user-facing app name flows from src.branding (the rebrand's single
     source of truth) rather than a hard-coded title string in app.py.

Pure file reads — no Qt, no DB.
"""

import re
import unittest
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
_SRC = _ROOT / "src"
_DOC = _ROOT / "docs" / "DESIGN_PHILOSOPHY.md"

_ANCHOR_RE = re.compile(r"Design principle P(\d+)")


class TestPhilosophyDoc(unittest.TestCase):
    def test_doc_exists(self):
        self.assertTrue(_DOC.is_file(),
                        "docs/DESIGN_PHILOSOPHY.md is missing")

    def test_doc_documents_all_eleven_themes(self):
        text = _DOC.read_text(encoding="utf-8")
        for n in range(1, 12):
            self.assertRegex(
                text, rf"(?m)^### {n}\. ",
                f"DESIGN_PHILOSOPHY.md is missing core theme #{n}",
            )

    def test_companion_docs_linked(self):
        text = _DOC.read_text(encoding="utf-8")
        self.assertIn("REFERENCES.md", text)
        self.assertIn("PHILOSOPHY_ROADMAP.md", text)


class TestCodeAnchors(unittest.TestCase):
    def test_anchors_name_real_principles(self):
        offenders = []
        anchored = set()
        for path in _SRC.rglob("*.py"):
            text = path.read_text(encoding="utf-8")
            found = _ANCHOR_RE.findall(text)
            if found:
                anchored.add(path)
            for num in found:
                if not (1 <= int(num) <= 11):
                    offenders.append(f"{path}: P{num} is not a real principle (1–11)")
        self.assertFalse(offenders, "\n".join(offenders))
        # The convention is actually in use — a refactor that strips every anchor
        # (losing the doc↔code link) should trip this.
        self.assertGreaterEqual(
            len(anchored), 6,
            f"expected several modules to carry a 'Design principle P#' anchor; "
            f"found {len(anchored)}",
        )


class TestBranding(unittest.TestCase):
    def test_app_name_is_site_and_pattern(self):
        from src.branding import APP_NAME, APP_TITLE
        self.assertEqual(APP_NAME, "Site & Pattern")
        self.assertTrue(APP_TITLE.startswith(APP_NAME))

    def test_window_title_flows_from_branding(self):
        app_src = (_SRC / "app.py").read_text(encoding="utf-8")
        self.assertIn("setWindowTitle(APP_TITLE)", app_src,
                      "MainWindow should set its title from branding.APP_TITLE")
        self.assertNotIn(
            '"PermaDesign — Native Habitat Designer"', app_src,
            "the old hard-coded window title should be gone")


if __name__ == "__main__":
    unittest.main()
