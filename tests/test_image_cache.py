"""
tests/test_image_cache.py

I1 — the local flora/fauna image cache/resolver. Stdlib-only (no Qt, no real
network): the fetch path is exercised against a ``file://`` URL so it runs
offline, and the schema test confirms plants/fauna carry the image columns.
"""

import os
import sys
import tempfile
import unittest
import pathlib

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import src.db.plants as _plants_mod  # noqa: E402
import src.image_cache as ic         # noqa: E402

# A 1x1 PNG (valid header + minimal body).
_PNG = (b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01"
        b"\x08\x06\x00\x00\x00\x1f\x15\xc4\x89\x00\x00\x00\nIDATx\x9cc\x00"
        b"\x01\x00\x00\x05\x00\x01\r\n-\xb4\x00\x00\x00\x00IEND\xaeB`\x82")


class TestImageCache(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls._tmp = tempfile.mkdtemp(prefix="permadesign_imgcache_")
        # Redirect the cache into a temp user-data dir.
        cls._orig = _plants_mod._user_data_dir
        _plants_mod._user_data_dir = lambda: pathlib.Path(cls._tmp)

    @classmethod
    def tearDownClass(cls):
        _plants_mod._user_data_dir = cls._orig

    def test_cache_dir_created(self):
        d = ic._cache_dir()
        self.assertTrue(os.path.isdir(str(d)))

    def test_local_file_resolves_directly(self):
        f = os.path.join(self._tmp, "local.png")
        with open(f, "wb") as fh:
            fh.write(_PNG)
        self.assertEqual(ic.get_cached_image(f), f)
        self.assertEqual(ic.resolve_image(f), f)

    def test_absent_and_empty(self):
        self.assertIsNone(ic.get_cached_image(""))
        self.assertIsNone(ic.get_cached_image("https://example.invalid/x.jpg"))
        self.assertIsNone(
            ic.resolve_image("https://example.invalid/x.jpg",
                             fetch_if_missing=False))

    def test_fetch_caches_and_records_attribution(self):
        # Serve the PNG from a file:// URL so the fetch path runs offline.
        src_png = os.path.join(self._tmp, "src.png")
        with open(src_png, "wb") as fh:
            fh.write(_PNG)
        url = pathlib.Path(src_png).as_uri()   # file:///...

        path = ic.fetch_and_cache_image(
            url, attribution="© Tester, CC0", license_str="CC0")
        self.assertIsNotNone(path)
        self.assertTrue(os.path.exists(path))
        # cached on a second call (no re-fetch needed)
        self.assertEqual(ic.get_cached_image(url), path)
        # attribution/license travel with the cached file
        meta = ic._load_meta().get(url)
        self.assertEqual(meta["attribution"], "© Tester, CC0")
        self.assertEqual(meta["license"], "CC0")


class TestCacheKeyAddressing(unittest.TestCase):
    """The key is how a cached photo reaches the 3D viewer without its URL
    leaving the app (src/web_assets.py `/__image`)."""

    @classmethod
    def setUpClass(cls):
        cls._tmp = tempfile.mkdtemp(prefix="permadesign_imgkey_")
        cls._orig = _plants_mod._user_data_dir
        _plants_mod._user_data_dir = lambda: pathlib.Path(cls._tmp)
        src_png = os.path.join(cls._tmp, "keyed.png")
        with open(src_png, "wb") as fh:
            fh.write(_PNG)
        cls.url = pathlib.Path(src_png).as_uri()
        cls.path = ic.fetch_and_cache_image(cls.url, "© Tester", "CC0")

    @classmethod
    def tearDownClass(cls):
        _plants_mod._user_data_dir = cls._orig

    def test_key_round_trips_to_the_cached_file(self):
        self.assertEqual(ic.cached_path_for_key(ic.cache_key(self.url)),
                         self.path)

    def test_key_is_stable_and_opaque(self):
        key = ic.cache_key(self.url)
        self.assertEqual(key, ic.cache_key(self.url))
        self.assertTrue(key.isalnum() and len(key) == 16)
        self.assertNotIn("/", key)

    def test_unknown_or_hostile_keys_resolve_to_nothing(self):
        # Anything that isn't a known cache stem must return None — the route
        # that serves these is the only thing standing between a URL parameter
        # and the filesystem.
        for bad in ("", "nope", "../../etc/passwd", "a/b", "..",
                    os.path.basename(self.path)):
            self.assertIsNone(ic.cached_path_for_key(bad), bad)

    def test_credit_line_needs_no_placeholder_when_half_the_data_is_missing(self):
        self.assertEqual(ic.credit_line("© A", "cc-by"), "© A · cc-by")
        self.assertEqual(ic.credit_line("© A", ""), "© A")
        self.assertEqual(ic.credit_line("", "cc-by"), "cc-by")
        self.assertEqual(ic.credit_line("", ""), "")

    def test_credit_line_does_not_state_the_licence_twice(self):
        """Every seeded iNaturalist attribution already names its licence in
        prose, so pasting the slug after it says the same thing in two
        notations."""
        inat = ("(c) Rob Foster, some rights reserved (CC BY), "
                "uploaded by Rob Foster")
        self.assertEqual(ic.credit_line(inat, "cc-by"), inat)
        for attribution, licence in (
                ("(c) X, some rights reserved (CC BY-SA)", "cc-by-sa"),
                ("(c) X, some rights reserved (CC BY-NC)", "cc-by-nc"),
                ("Public domain, via Wikimedia Commons", "cc0"),
                ("Creative Commons Attribution 4.0", "cc-by")):
            self.assertEqual(ic.credit_line(attribution, licence), attribution)

    def test_a_licence_that_is_not_already_stated_is_still_appended(self):
        """Broad on purpose: a doubled credit is cosmetic, a missing one is a
        licence violation, so anything uncertain keeps the slug."""
        self.assertEqual(ic.credit_line("Photo by A. Person", "cc-by-sa"),
                         "Photo by A. Person · cc-by-sa")
        self.assertEqual(ic.credit_line("© Someone 2019", "GFDL"),
                         "© Someone 2019 · GFDL")


class TestImageSchema(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls._tmp = tempfile.mkdtemp(prefix="permadesign_imgschema_")
        _plants_mod._DATA_DIR = cls._tmp
        _plants_mod._DB_PATH = os.path.join(cls._tmp, "t.db")
        from src.db.plants import init_db
        init_db()

    def test_plants_and_fauna_have_image_columns(self):
        from src.db.plants import get_connection
        conn = get_connection()
        try:
            need = {"image_url", "image_attribution", "image_license"}
            pcols = {r[1] for r in conn.execute("PRAGMA table_info(plants)")}
            fcols = {r[1] for r in conn.execute("PRAGMA table_info(fauna)")}
            self.assertTrue(need <= pcols)
            self.assertTrue(need <= fcols)
        finally:
            conn.close()

    def test_get_plant_exposes_image_fields(self):
        from src.db.plants import get_plant, search_plants
        rec = get_plant(search_plants()[0]["id"])
        self.assertIn("image_url", rec)
        self.assertIn("image_attribution", rec)

    def test_has_image_only_filter(self):
        """The 'Photo' browser filter narrows to plants with an image_url."""
        from src.db.plants import search_plants
        all_plants = search_plants()
        with_photo = search_plants(has_image_only=True)
        self.assertTrue(0 < len(with_photo) < len(all_plants))
        self.assertTrue(
            all((p.get("image_url") or "").strip() for p in with_photo))


if __name__ == "__main__":
    unittest.main()
