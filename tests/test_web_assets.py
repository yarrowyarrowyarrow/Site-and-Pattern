"""
tests/test_web_assets.py — the loopback asset server's routes (V2.29).

src/web_assets.py is Qt-free stdlib HTTP, so the real server is started here on
an ephemeral loopback port and driven with urllib. The interesting part is what it
REFUSES: it exists to serve a bundled html/ tree to an embedded browser, and each
extra route is a hole in that containment. The `/__image` route added for the 3D
click-to-learn card is the narrowest of them — a key resolved inside the photo
cache and nowhere else — and this is the test that keeps it that way.
"""

import os
import pathlib
import sys
import tempfile
import unittest
import urllib.error
import urllib.parse
import urllib.request

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import src.db.plants as _plants_mod           # noqa: E402
import src.image_cache as ic                  # noqa: E402
import src.web_assets as wa                   # noqa: E402

_PNG = (b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01"
        b"\x08\x06\x00\x00\x00\x1f\x15\xc4\x89\x00\x00\x00\nIDATx\x9cc\x00"
        b"\x01\x00\x00\x05\x00\x01\r\n-\xb4\x00\x00\x00\x00IEND\xaeB`\x82")


def _get(url):
    """(status, body, content_type). A 4xx/5xx comes back as a status, not a
    raised exception, so a test can assert on it."""
    try:
        with urllib.request.urlopen(url, timeout=10) as resp:
            return (resp.status, resp.read(),
                    resp.headers.get("Content-Type") or "")
    except urllib.error.HTTPError as exc:
        return exc.code, exc.read(), exc.headers.get("Content-Type") or ""


class ImageRouteTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls._tmp = tempfile.mkdtemp(prefix="permadesign_webassets_")
        cls._orig_dir = _plants_mod._user_data_dir
        _plants_mod._user_data_dir = lambda: pathlib.Path(cls._tmp)
        # Cache one photo through the real fetch path (a file:// URL, so this
        # runs offline) and remember how it is addressed.
        src_png = os.path.join(cls._tmp, "src.png")
        with open(src_png, "wb") as fh:
            fh.write(_PNG)
        cls.url = pathlib.Path(src_png).as_uri()
        cls.cached = ic.fetch_and_cache_image(cls.url, "© Tester", "CC0")
        cls.key = ic.cache_key(cls.url)
        # A file OUTSIDE the cache, to prove the route cannot reach it.
        cls.outside = os.path.join(cls._tmp, "secret.png")
        with open(cls.outside, "wb") as fh:
            fh.write(_PNG)
        cls.base = wa._ensure_server()

    @classmethod
    def tearDownClass(cls):
        _plants_mod._user_data_dir = cls._orig_dir

    def _image(self, key):
        return _get(self.base + "/__image?k=" + urllib.parse.quote(str(key)))

    def test_a_cached_photo_is_served_with_an_image_mime(self):
        status, body, ctype = self._image(self.key)
        self.assertEqual(status, 200)
        self.assertEqual(body, _PNG)
        self.assertTrue(ctype.startswith("image/"), ctype)

    def test_an_unknown_key_is_404_not_an_error_page(self):
        self.assertEqual(self._image("0123456789abcdef")[0], 404)

    def test_a_missing_or_empty_key_is_404(self):
        self.assertEqual(_get(self.base + "/__image")[0], 404)
        self.assertEqual(self._image("")[0], 404)

    def test_the_route_cannot_be_walked_out_of_the_cache(self):
        """The key is resolved against the cache's own metadata, so a path is
        not a key — but assert it explicitly, because this route's whole reason
        to be narrower than /__localfile is that it takes a URL parameter."""
        for hostile in ("../../etc/passwd",
                        "..%2f..%2fetc%2fpasswd",
                        "/etc/passwd",
                        self.outside,
                        os.path.basename(self.outside),
                        pathlib.Path(self.outside).as_uri()):
            status, _body, _ctype = self._image(hostile)
            self.assertEqual(status, 404, f"{hostile} was not refused")

    def test_a_non_image_in_the_cache_is_still_refused(self):
        """The cache dir also holds image_metadata.json; the route serves image
        MIME types only, so the sidecar is not reachable through it."""
        meta = ic._meta_path()
        self.assertTrue(meta.exists())
        self.assertEqual(self._image(meta.stem)[0], 404)


class ContainmentTest(unittest.TestCase):
    """The pre-existing routes, pinned alongside the new one."""

    @classmethod
    def setUpClass(cls):
        cls.base = wa._ensure_server()

    def test_the_html_tree_is_served(self):
        status, body, ctype = _get(self.base + "/scene3d.html")
        self.assertEqual(status, 200)
        self.assertIn(b"scene3d", body)
        self.assertTrue(ctype.startswith("text/html"), ctype)

    def test_nothing_outside_the_html_root_is_served(self):
        for path in ("/../main.py", "/..%2fmain.py", "/../../etc/passwd"):
            self.assertNotEqual(_get(self.base + path)[0], 200, path)

    def test_localfile_serves_only_ply(self):
        with tempfile.NamedTemporaryFile(suffix=".txt", delete=False) as fh:
            fh.write(b"not a point cloud")
            txt = fh.name
        try:
            url = (self.base + "/__localfile?path="
                   + urllib.parse.quote(os.path.abspath(txt)))
            self.assertEqual(_get(url)[0], 404)
        finally:
            os.unlink(txt)


if __name__ == "__main__":
    unittest.main()
