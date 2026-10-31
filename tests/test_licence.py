"""
tests/test_licence.py — the licence file, the About box and the README say the
same thing (V3.18, FN-1; the owner's decision D1).

The app was under the PolyForm Noncommercial License while built on PyQt6,
which Riverbank licenses under the GPL v3, and the GPL does not allow a
program built on it to be distributed with a noncommercial restriction added.
It is GPL-3.0 now. ``LICENSE`` is the Free Software Foundation's text, checked
here by its SHA-256 so an edit to it fails rather than drifts.
"""

import hashlib
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src import branding  # noqa: E402

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

#: SHA-256 of https://www.gnu.org/licenses/gpl-3.0.txt, which Debian ships
#: verbatim as /usr/share/common-licenses/GPL-3 (the copy V3.18 used).
GPL3_SHA256 = "3972dc9744f6499f0f9b2dbf76696f2ae7ad8af9b23dde66d6af86c9dfb36986"


def _read(*parts) -> str:
    with open(os.path.join(_ROOT, *parts), encoding="utf-8") as fh:
        return fh.read()


class TestTheLicence(unittest.TestCase):

    def test_the_file_is_the_gpl_v3_verbatim(self):
        with open(os.path.join(_ROOT, "LICENSE"), "rb") as fh:
            data = fh.read()
        self.assertEqual(hashlib.sha256(data).hexdigest(), GPL3_SHA256)
        head = data[:200].decode("utf-8")
        self.assertIn("GNU GENERAL PUBLIC LICENSE", head)
        self.assertIn("Version 3, 29 June 2007", head)

    def test_the_name_the_app_shows_is_that_licence(self):
        self.assertEqual(branding.LICENCE_NAME,
                         "GNU General Public License, version 3")
        self.assertEqual(branding.LICENCE_SPDX, "GPL-3.0-only")

    def test_the_readme_names_it(self):
        readme = _read("README.md")
        section = readme[readme.index("## License"):]
        section = section[:section.index("\n---")]
        first = section.split("\n\n")[1]
        self.assertIn(branding.LICENCE_NAME, first)
        self.assertIn("(LICENSE)", first)
        self.assertNotIn("PolyForm", first)
        self.assertIn(f"[`LICENSE`](LICENSE) — {branding.LICENCE_NAME}",
                      readme)

    def test_the_installer_carries_the_text(self):
        spec = _read("scripts", "packaging", "permadesign.spec")
        self.assertIn("(os.path.join(_ROOT, 'LICENSE'), '.')", spec)


class TestTheAboutBox(unittest.TestCase):

    def test_it_names_the_licence_and_where_the_text_is(self):
        try:
            from src.controllers.update_flow import about_licence_line
        except Exception as exc:                           # noqa: BLE001
            self.skipTest(f"update_flow needs PyQt6: {exc}")
        line = about_licence_line()
        self.assertIn(branding.LICENCE_NAME, line)
        self.assertIn("LICENSE file", line)
        self.assertIn("github.com/yarrowyarrowyarrow/Site-and-Pattern", line)


if __name__ == "__main__":
    unittest.main()
