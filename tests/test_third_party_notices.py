"""
tests/test_third_party_notices.py — the installer carries the licences of what
it bundles (FN-2, V3.31) and says which versions it was built with (FN-12).
"""

import os
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "scripts"))

import write_third_party_notices as notices  # noqa: E402


def _read(*parts):
    with open(os.path.join(ROOT, *parts), encoding="utf-8") as f:
        return f.read()


class TheNoticesNameEverything(unittest.TestCase):

    def test_every_requirement_and_vendored_library_is_named(self):
        self.assertEqual(notices.main(["--check"]), 0)
        text = _read("THIRD_PARTY_NOTICES.txt")
        for name in ("Qt 6", "Qt WebEngine", "PyQt6", "Python", "three.js",
                     "Leaflet 1.9.4", "Leaflet.draw", "PyInstaller"):
            self.assertIn(name, text)

    def test_a_new_vendored_library_would_be_caught(self):
        self.assertIn("leaflet-draw", notices.required_names())
        self.assertEqual(notices.missing("nothing named"),
                         notices.required_names())

    def test_the_licence_texts_are_there(self):
        text = _read("THIRD_PARTY_NOTICES.txt")
        self.assertIn("GNU LESSER GENERAL PUBLIC LICENSE", text)
        self.assertIn(_read("html", "vendor", "leaflet", "LICENSE").strip()
                      .splitlines()[0], text)
        self.assertIn("Copyright © 2010-2025 three.js authors", text)


class TheInstallerShipsThem(unittest.TestCase):

    def test_the_spec_bundles_the_notices_and_the_build_versions(self):
        spec = _read("scripts", "packaging", "permadesign.spec")
        self.assertIn("'THIRD_PARTY_NOTICES.txt'", spec)
        self.assertIn("'build-versions.txt'", spec)

    def test_both_build_scripts_record_the_versions(self):
        for script in ("build_installer.sh", "build_installer.bat"):
            text = _read("scripts", "packaging", script)
            self.assertIn("pip freeze > build-versions.txt", text, script)
            self.assertLess(text.index("pip freeze"),
                            text.index("pyinstaller scripts"), script)
        self.assertIn("build-versions.txt", _read(".gitignore"))

    def test_both_release_notes_say_the_same(self):
        """FN-3, FN-4, FN-11: one body, whichever job finishes last."""
        bodies = []
        for name in ("release-windows.yml", "release-macos.yml"):
            wf = _read(".github", "workflows", name)
            body = wf[wf.index("          body: |"):
                      wf.index("          generate_release_notes")]
            for words in ("More info → Run anyway", "Open Anyway",
                          "Your first yard, in five steps",
                          "What leaves your computer", "Send Feedback"):
                self.assertIn(words, body, name)
            bodies.append(body)
        self.assertEqual(bodies[0], bodies[1])

    def test_the_windows_build_is_pinned(self):
        wf = _read(".github", "workflows", "release-windows.yml")
        self.assertIn("runs-on: windows-2025", wf)
        self.assertIn('python-version: "3.11.9"', wf)
        self.assertIn('PY_VERSION: "3.11.9"',
                      _read(".github", "workflows", "release-macos.yml"))


if __name__ == "__main__":
    unittest.main()
