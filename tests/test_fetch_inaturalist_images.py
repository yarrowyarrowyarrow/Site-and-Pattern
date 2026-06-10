"""
tests/test_fetch_inaturalist_images.py

F6 — the pure (network-free) core of the iNaturalist image sourcing script:
the licence whitelist, exact-name taxon matching, and photo extraction. Guards
that only redistributable licences (CC0 / CC BY / CC BY-SA) are ever accepted.
"""

import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "scripts"))

import fetch_inaturalist_images as F  # noqa: E402


class TestLicenseWhitelist(unittest.TestCase):
    def test_accepts_redistributable(self):
        for code in ("cc0", "cc-by", "cc-by-sa", "CC-BY", " cc0 "):
            self.assertTrue(F.license_ok(code), code)

    def test_rejects_nc_nd_and_arr(self):
        for code in ("cc-by-nc", "cc-by-nc-sa", "cc-by-nd", "c", "", None):
            self.assertFalse(F.license_ok(code), repr(code))


class TestBestTaxon(unittest.TestCase):
    _RESULTS = [
        {"name": "Amelanchier", "id": 1},                  # genus, not exact
        {"name": "Amelanchier alnifolia", "id": 2},        # exact species
    ]

    def test_requires_exact_match(self):
        t = F.best_taxon(self._RESULTS, "Amelanchier alnifolia")
        self.assertEqual(t["id"], 2)

    def test_case_insensitive(self):
        t = F.best_taxon(self._RESULTS, "amelanchier ALNIFOLIA")
        self.assertEqual(t["id"], 2)

    def test_no_match_returns_none(self):
        self.assertIsNone(F.best_taxon(self._RESULTS, "Salix bebbiana"))
        self.assertIsNone(F.best_taxon([], "x"))


class TestPhotoFromTaxon(unittest.TestCase):
    def _taxon(self, code, url="https://static.inaturalist.org/photos/1/medium.jpg"):
        return {"default_photo": {"license_code": code, "medium_url": url,
                                  "attribution": "(c) A. Botanist, some rights "
                                                 "reserved (CC BY-SA)"}}

    def test_accepts_open_license(self):
        out = F.photo_from_taxon(self._taxon("cc-by-sa"))
        self.assertIsNotNone(out)
        url, attr, code = out
        self.assertTrue(url.startswith("https://"))
        self.assertEqual(code, "cc-by-sa")
        self.assertIn("CC BY-SA", attr)

    def test_rejects_nc(self):
        self.assertIsNone(F.photo_from_taxon(self._taxon("cc-by-nc")))

    def test_none_when_no_photo(self):
        self.assertIsNone(F.photo_from_taxon({"default_photo": {}}))
        self.assertIsNone(F.photo_from_taxon({}))

    def test_falls_back_to_url_field(self):
        t = {"default_photo": {"license_code": "cc0",
                               "url": "https://static.inaturalist.org/x.jpg"}}
        out = F.photo_from_taxon(t)
        self.assertEqual(out[2], "cc0")


if __name__ == "__main__":
    unittest.main()
