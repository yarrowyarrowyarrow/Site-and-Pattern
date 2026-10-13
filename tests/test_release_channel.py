"""
tests/test_release_channel.py — a push publishes a prerelease; the owner
promotes it (V3.18, FN-7, decision D5).

Both release workflows ran on every push to a V branch and published a full
release, and the in-app updater offers every full release to every installed
copy: on 8 October 2026 that was five in one day. Each push now publishes a
prerelease, which the updater skips, and ``promote-release.yml`` makes one a
full release. Read as text: the workflows are YAML that only GitHub runs.
"""

import os
import re
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src import github_releases as ghr  # noqa: E402

_WF = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                   ".github", "workflows")


def _read(name):
    with open(os.path.join(_WF, name), encoding="utf-8") as fh:
        return fh.read()


def _release_step(text):
    """The ``with:`` block of the action-gh-release step."""
    start = text.index("softprops/action-gh-release")
    return text[start:]


class TestEveryPushIsAPrerelease(unittest.TestCase):

    def test_both_workflows_publish_prereleases(self):
        for name in ("release-windows.yml", "release-macos.yml"):
            step = _release_step(_read(name))
            self.assertRegex(step, r"\n\s+prerelease:\s*true\s*\n", name)

    def test_the_tag_is_unchanged(self):
        for name in ("release-windows.yml", "release-macos.yml"):
            self.assertIn("tag_name: release-${{ github.ref_name }}",
                          _read(name), name)

    def test_the_updater_skips_prereleases(self):
        payload = [
            {"tag_name": "release-V3.18", "prerelease": True, "assets": []},
            {"tag_name": "release-V3.17", "prerelease": False, "assets": []},
        ]
        rels = ghr.list_releases(fetch_json=lambda _u: payload)
        self.assertEqual([r.tag for r in rels], ["release-V3.17"])

    def test_the_last_promoted_release_is_found_pages_back(self):
        """A hundred prereleases since the last promotion must not hide it."""
        def fetch(url):
            page = int(re.search(r"[?&]page=(\d+)", url).group(1))
            if page == 1:
                return [{"tag_name": f"release-V9.{n}", "prerelease": True,
                         "assets": []} for n in range(100)]
            if page == 2:
                return [{"tag_name": "release-V3.17", "prerelease": False,
                         "assets": []}]
            raise AssertionError("read past the last page")
        rels = ghr.list_releases(fetch_json=fetch)
        self.assertEqual([r.tag for r in rels], ["release-V3.17"])


class TestThePromoteWorkflow(unittest.TestCase):

    def setUp(self):
        self.text = _read("promote-release.yml")

    def test_it_runs_only_when_asked(self):
        triggers = self.text[self.text.index("\non:"):self.text.index("\npermissions:")]
        self.assertIn("workflow_dispatch:", triggers)
        self.assertNotIn("push:", triggers)
        self.assertIn("version:", triggers)

    def test_it_makes_the_release_full_and_latest(self):
        self.assertIn('gh release edit "release-$VERSION"', self.text)
        self.assertIn("--prerelease=false", self.text)
        self.assertIn("--latest", self.text)

    def test_it_refuses_a_bad_name_or_a_missing_installer(self):
        self.assertIn(r"^V[0-9]+\.[0-9]+$", self.text)
        self.assertIn("Setup\\.exe$", self.text)
        self.assertIn("\\.dmg$", self.text)

    def test_it_can_write_releases(self):
        self.assertRegex(self.text, r"permissions:\s*\n\s+contents:\s*write")


if __name__ == "__main__":
    unittest.main()
