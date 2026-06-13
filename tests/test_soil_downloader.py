"""
tests/test_soil_downloader.py — the soil-pack download loop (V1.67).

Headless: the network opener is injected (a zip blob built in-memory), so the
download + .tif extraction is exercised without hitting the network.
"""

import io
import os
import sys
import tempfile
import unittest
import zipfile

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.soil_downloader import download_soil_pack


def _zip_with_tifs(names):
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        for n in names:
            zf.writestr(n, b"\x49\x49\x2a\x00fake-geotiff-bytes")
    return buf.getvalue()


class TestDownloadSoilPack(unittest.TestCase):

    def setUp(self):
        self.dest = tempfile.mkdtemp()

    def test_extracts_tifs_from_zip(self):
        blob = _zip_with_tifs(["readme.txt", "sub/sand_0-5.tif",
                               "ph_0-5.TIF"])
        n = download_soil_pack(self.dest, ["http://x/pack.zip"],
                               opener=lambda url: blob)
        self.assertEqual(n, 2)            # 2 tif members, .txt ignored
        files = set(os.listdir(self.dest))
        self.assertIn("sand_0-5.tif", files)   # flattened (basename)
        self.assertIn("ph_0-5.TIF", files)

    def test_direct_tif_url(self):
        n = download_soil_pack(self.dest, ["http://x/clay_0-5.tif"],
                               opener=lambda url: b"\x49\x49\x2a\x00data")
        self.assertEqual(n, 1)
        self.assertIn("clay_0-5.tif", os.listdir(self.dest))

    def test_cancel_stops_before_download(self):
        called = {"n": 0}

        def opener(url):
            called["n"] += 1
            return b""

        n = download_soil_pack(self.dest, ["http://x/a.zip"],
                               opener=opener, should_cancel=lambda: True)
        self.assertEqual(n, 0)
        self.assertEqual(called["n"], 0)

    def test_bad_source_skipped(self):
        def opener(url):
            raise RuntimeError("network down")
        n = download_soil_pack(self.dest, ["http://x/a.zip"], opener=opener)
        self.assertEqual(n, 0)            # no crash, just nothing written


if __name__ == "__main__":
    unittest.main()
