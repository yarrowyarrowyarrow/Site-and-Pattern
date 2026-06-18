"""
tests/test_github_releases.py

Covers the Qt-free GitHub Releases helpers used by the frozen-build updater
(src/github_releases.py). Network is injected (no real HTTP), so these run
offline and fast.
"""

import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src import github_releases as ghr  # noqa: E402


class TestParseReleaseVersion(unittest.TestCase):

    def test_valid(self):
        cases = {
            "V1.72": (1, 72),
            "v1.64": (1, 64),     # historical lowercase release tag
            "1.5": (1, 5),        # bare
            "V10.100": (10, 100),
            "  V2.0  ": (2, 0),   # stripped
        }
        for tag, expected in cases.items():
            with self.subTest(tag=tag):
                self.assertEqual(ghr.parse_release_version(tag), expected)

    def test_invalid(self):
        for tag in ["main", "V1", "1.2.3", "V1.2-beta", "", "release", None]:
            with self.subTest(tag=repr(tag)):
                self.assertIsNone(ghr.parse_release_version(tag))


def _sample_payload():
    """Mimics the shape of the GitHub /releases response."""
    return [
        {
            "tag_name": "V1.73", "name": "V1.73", "body": "Newest",
            "draft": False, "prerelease": False,
            "html_url": "https://example/V1.73",
            "assets": [
                {"name": "SiteAndPattern-V1.73.dmg",
                 "browser_download_url": "https://example/v173.dmg",
                 "size": 1000},
                {"name": "SiteAndPattern-Windows.zip",
                 "browser_download_url": "https://example/v173.zip",
                 "size": 2000},
            ],
        },
        {
            "tag_name": "V1.72", "name": "V1.72", "body": "Older",
            "draft": False, "prerelease": False,
            "html_url": "https://example/V1.72",
            "assets": [
                {"name": "SiteAndPattern-V1.72.dmg",
                 "browser_download_url": "https://example/v172.dmg",
                 "size": 900},
            ],
        },
        {  # drafts are ignored
            "tag_name": "V1.99", "draft": True, "prerelease": False,
            "assets": [],
        },
        {  # prereleases ignored by default
            "tag_name": "V2.0", "draft": False, "prerelease": True,
            "assets": [],
        },
        {  # non-version tag ignored
            "tag_name": "nightly", "draft": False, "prerelease": False,
            "assets": [],
        },
    ]


class TestListReleases(unittest.TestCase):

    def _fetch(self, _url):
        return _sample_payload()

    def test_sorted_newest_first_and_filtered(self):
        rels = ghr.list_releases(fetch_json=self._fetch)
        self.assertEqual([r.tag for r in rels], ["V1.73", "V1.72"])

    def test_prereleases_included_when_asked(self):
        rels = ghr.list_releases(fetch_json=self._fetch, include_prereleases=True)
        self.assertEqual([r.tag for r in rels], ["V2.0", "V1.73", "V1.72"])

    def test_latest_release(self):
        latest = ghr.latest_release(fetch_json=self._fetch)
        self.assertEqual(latest.tag, "V1.73")
        self.assertEqual(latest.version, (1, 73))

    def test_assets_parsed(self):
        latest = ghr.latest_release(fetch_json=self._fetch)
        self.assertEqual(len(latest.assets), 2)
        names = {a.name for a in latest.assets}
        self.assertIn("SiteAndPattern-V1.73.dmg", names)

    def test_non_list_payload_is_safe(self):
        rels = ghr.list_releases(fetch_json=lambda _u: {"message": "Not Found"})
        self.assertEqual(rels, [])


class TestAssetSelection(unittest.TestCase):

    def setUp(self):
        self.rel = ghr.list_releases(fetch_json=lambda _u: _sample_payload())[0]

    def test_macos_picks_dmg(self):
        a = self.rel.asset_for_extensions(ghr.platform_asset_extensions("darwin"))
        self.assertIsNotNone(a)
        self.assertTrue(a.name.endswith(".dmg"))

    def test_windows_prefers_exe_then_zip(self):
        a = self.rel.asset_for_extensions(ghr.platform_asset_extensions("win32"))
        # No .exe in the sample, so it should fall back to the .zip.
        self.assertIsNotNone(a)
        self.assertTrue(a.name.endswith(".zip"))

    def test_no_match_returns_none(self):
        self.assertIsNone(self.rel.asset_for_extensions((".rpm",)))

    def test_platform_extensions(self):
        self.assertEqual(ghr.platform_asset_extensions("darwin"), (".dmg",))
        self.assertEqual(ghr.platform_asset_extensions("win32")[0], ".exe")


class _FakeResponse:
    """Minimal context-manager HTTP response for download tests."""

    def __init__(self, chunks, total=None):
        self._chunks = list(chunks)
        self.headers = {}
        if total is not None:
            self.headers["Content-Length"] = str(total)
        self.closed = False

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self.close()
        return False

    def read(self, _size=-1):
        return self._chunks.pop(0) if self._chunks else b""

    def close(self):
        self.closed = True


class TestDownloadAsset(unittest.TestCase):

    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="ghr_dl_")
        self.addCleanup(lambda: __import__("shutil").rmtree(self.tmp, ignore_errors=True))
        self.asset = ghr.Asset("file.bin", "https://example/file.bin", size=6)
        self.dest = os.path.join(self.tmp, "file.bin")

    def test_downloads_and_reports_progress(self):
        seen = []

        def opener(_req, timeout=0):
            return _FakeResponse([b"abc", b"def"], total=6)

        def progress(done, total):
            seen.append((done, total))
            return True

        out = ghr.download_asset(self.asset, self.dest,
                                 progress=progress, opener=opener)
        self.assertEqual(out, self.dest)
        with open(self.dest, "rb") as f:
            self.assertEqual(f.read(), b"abcdef")
        self.assertEqual(seen[-1], (6, 6))
        # No leftover partial file.
        self.assertFalse(os.path.exists(self.dest + ".part"))

    def test_cancel_removes_partial(self):
        def opener(_req, timeout=0):
            return _FakeResponse([b"abc", b"def"], total=6)

        def progress(_done, _total):
            return False  # cancel immediately

        with self.assertRaises(ghr.DownloadCancelled):
            ghr.download_asset(self.asset, self.dest,
                               progress=progress, opener=opener)
        self.assertFalse(os.path.exists(self.dest))
        self.assertFalse(os.path.exists(self.dest + ".part"))

    def test_error_removes_partial(self):
        class Boom(Exception):
            pass

        def opener(_req, timeout=0):
            class R(_FakeResponse):
                def read(self, _size=-1):
                    raise Boom("network died")
            return R([b"x"], total=6)

        with self.assertRaises(Boom):
            ghr.download_asset(self.asset, self.dest, opener=opener)
        self.assertFalse(os.path.exists(self.dest))
        self.assertFalse(os.path.exists(self.dest + ".part"))


if __name__ == "__main__":
    unittest.main()
