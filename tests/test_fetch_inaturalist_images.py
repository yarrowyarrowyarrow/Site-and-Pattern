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


class TestWiderPhotoSet(unittest.TestCase):
    """Scan beyond the default photo so a species with an NC default but an
    openly-licensed alternate still gets an image."""

    def _photo(self, pid, code):
        return {"id": pid, "license_code": code,
                "medium_url": f"https://static.inaturalist.org/{pid}.jpg",
                "attribution": f"(c) someone {pid}"}

    def test_default_preferred_when_open(self):
        taxon = {"default_photo": self._photo(1, "cc-by"),
                 "taxon_photos": [{"photo": self._photo(2, "cc0")}]}
        out = F.pick_photo(F.taxon_candidates(taxon))
        self.assertEqual(out[0], "https://static.inaturalist.org/1.jpg")  # default

    def test_rescues_species_with_nc_default(self):
        # Default is NonCommercial; a later photo is CC0 → use it.
        taxon = {
            "default_photo": self._photo(1, "cc-by-nc"),
            "taxon_photos": [
                {"photo": self._photo(2, "cc-by-nd")},     # also unusable
                {"photo": self._photo(3, "cc0")},          # ← redistributable
                {"photo": self._photo(4, "cc-by")},
            ],
        }
        out = F.pick_photo(F.taxon_candidates(taxon))
        self.assertIsNotNone(out)
        self.assertEqual(out[2], "cc0")
        self.assertEqual(out[0], "https://static.inaturalist.org/3.jpg")

    def test_none_when_all_unusable(self):
        taxon = {
            "default_photo": self._photo(1, "cc-by-nc"),
            "taxon_photos": [{"photo": self._photo(2, "c")},
                             {"photo": self._photo(3, "cc-by-nd")}],
        }
        self.assertIsNone(F.pick_photo(F.taxon_candidates(taxon)))

    def test_dedupes_by_photo_id(self):
        # Same photo as default and in taxon_photos — counted once, no crash.
        p = self._photo(1, "cc-by-nc")
        taxon = {"default_photo": p, "taxon_photos": [{"photo": p}]}
        self.assertEqual(len(F.taxon_candidates(taxon)), 2)
        self.assertIsNone(F.pick_photo(F.taxon_candidates(taxon)))

    def test_candidates_order_default_first(self):
        taxon = {"default_photo": self._photo(9, "cc0"),
                 "taxon_photos": [{"photo": self._photo(8, "cc-by")}]}
        cands = F.taxon_candidates(taxon)
        self.assertEqual([c["id"] for c in cands], [9, 8])


if __name__ == "__main__":
    unittest.main()
