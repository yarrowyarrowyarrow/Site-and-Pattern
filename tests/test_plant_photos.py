"""
tests/test_plant_photos.py — photo sets with named slots (V2.35, schema v55, F70/F72).

Three things here can fail silently, which is why they are tested rather than
trusted:

1. **A person's own photograph surviving a reseed.** The obvious place to put
   one is ``plants.image_url``, and that column is wiped and re-seeded on every
   schema bump — the photo would vanish months later, on an upgrade, with no
   error. The whole design rests on ``origin='seed'`` vs ``'user'``, and a
   regression there looks like nothing at all until someone loses their photos.

2. **The read-side synthesis.** ``image_url`` is derived from the best slot now.
   If ``_attach_photos`` stops running, every screen quietly falls back to the
   old flower macro and nobody notices they lost the habit shot.

3. **EXIF stripping.** A photo of your own yard carries your home's GPS
   coordinates, and the natural next step for a photo you like is to commit it
   somewhere public. This one is a privacy property, not a feature.

Temp-DB pattern from tests/test_polycultures.py — never touches the real user DB.
"""

import io
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

_TMP_DIR = tempfile.mkdtemp(prefix="sitepattern_photos_")

import src.db.plants as _plants_mod                      # noqa: E402

_plants_mod._DATA_DIR = _TMP_DIR
_plants_mod._DB_PATH = os.path.join(_TMP_DIR, "photos_test.db")

from src.db import photos                                # noqa: E402
from src.db.plants import (PHOTO_SLOTS, get_all_plants,  # noqa: E402
                           get_connection, init_db)
from src import photo_import                             # noqa: E402

_SCI = "Rudbeckia hirta"


def _reseed():
    """Force the reseed path exactly as a schema bump does."""
    conn = get_connection()
    _plants_mod._set_schema_version(conn, 1)
    conn.commit()
    conn.close()
    _plants_mod._plant_cache = None
    init_db()


class TestSlots(unittest.TestCase):
    def test_slot_vocabulary_agrees_everywhere(self):
        """schema.sql, the DB layer, the query API, the data gate and the bench
        each name the slots. They are an INDEX into a preference order, so a
        drift does not error — it silently reorders which photo the app shows."""
        from src import data_quality                      # noqa: PLC0415
        self.assertEqual(tuple(photos.SLOTS), tuple(PHOTO_SLOTS))
        self.assertEqual(tuple(data_quality.PHOTO_SLOTS), tuple(PHOTO_SLOTS))
        self.assertEqual(set(photos.SLOT_PURPOSE), set(PHOTO_SLOTS))
        with open(os.path.join(os.path.dirname(__file__), os.pardir,
                               "src", "db", "schema.sql"), encoding="utf-8") as fh:
            schema = fh.read()
        for slot in PHOTO_SLOTS:
            self.assertIn(slot, schema, f"schema.sql does not mention {slot!r}")

    def test_habit_leads_the_preference_order(self):
        """The whole diagnosis behind F70: the app had 323 flower macros and
        zero photographs of a whole plant, because the fetch script's rule was
        'first redistributable licence' and iNaturalist's leading photo is a
        flower. `habit` leading is what makes the fix show up on screen."""
        self.assertEqual(PHOTO_SLOTS[0], "habit")


class TestReseedSurvival(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        init_db()

    def setUp(self):
        conn = get_connection()
        conn.execute("DELETE FROM plant_photos WHERE origin = 'user'")
        conn.commit()
        conn.close()

    def test_a_user_photo_survives_a_reseed_and_a_seed_photo_is_replaced(self):
        photos.add_photo(_SCI, "habit", "/photos/mine.jpg",
                         attribution="me", license="cc-by-sa",
                         source="owner", origin="user")
        before = photos.photos_for(_SCI)
        self.assertTrue(any(p["origin"] == "user" for p in before))

        _reseed()

        after = photos.photos_for(_SCI)
        mine = [p for p in after if p["origin"] == "user"]
        self.assertEqual(len(mine), 1,
                         "a person's own photograph did not survive the reseed "
                         "— this is the failure the origin column exists for")
        self.assertEqual(mine[0]["url"], "/photos/mine.jpg")
        self.assertEqual(
            sum(1 for p in after if p["origin"] == "seed"), 1,
            "the shipped photo was either lost or duplicated by the reseed")

    def test_a_user_photo_does_not_suppress_the_shipped_one(self):
        """The back-fill's dedupe was scoped to the SPECIES at first, so adding
        one photo of your own permanently deleted the shipped photo for that
        plant on the next reseed. It is scoped to the URL now."""
        photos.add_photo(_SCI, "winter", "/photos/january.jpg", origin="user")
        _reseed()
        after = photos.photos_for(_SCI)
        self.assertTrue([p for p in after if p["origin"] == "seed"],
                        "the shipped photo did not come back")
        self.assertTrue([p for p in after if p["origin"] == "user"])

    def test_repeated_reseeds_do_not_accumulate_rows(self):
        _reseed()
        n1 = len(photos.photos_for(_SCI))
        _reseed()
        self.assertEqual(len(photos.photos_for(_SCI)), n1,
                         "the reseed is duplicating shipped photo rows")


class TestReadSynthesis(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        init_db()

    def setUp(self):
        conn = get_connection()
        conn.execute("DELETE FROM plant_photos WHERE origin = 'user'")
        conn.commit()
        conn.close()
        _plants_mod._plant_cache = None

    def _rudbeckia(self):
        _plants_mod._plant_cache = None
        return next(p for p in get_all_plants()
                    if p.get("scientific_name") == _SCI)

    def test_the_backfill_gave_every_photographed_species_a_flower_row(self):
        """Nothing curated may be lost by the upgrade."""
        cov = photos.coverage()
        self.assertGreater(cov["by_slot"]["flower"], 250,
                           "the legacy image_url column was not carried across")
        self.assertGreater(len(cov["missing"]), 0,
                           "the gap should be counted, not zero")

    def test_image_url_prefers_a_habit_photo_over_a_flower_macro(self):
        before = self._rudbeckia()["image_url"]
        photos.add_photo(_SCI, "habit", "/photos/whole-plant.jpg",
                         attribution="Yarrow", license="cc-by-sa",
                         source="owner", origin="user")
        after = self._rudbeckia()
        self.assertNotEqual(after["image_url"], before)
        self.assertEqual(after["image_url"], "/photos/whole-plant.jpg")
        self.assertEqual(after["image_attribution"], "Yarrow",
                         "the credit must travel with the photo it belongs to")

    def test_every_plant_carries_a_photos_list(self):
        """Consumers iterate it; a missing key is an AttributeError in a paint
        path, which is the worst place to find one."""
        for p in get_all_plants()[:50]:
            self.assertIsInstance(p.get("photos"), list)


class TestPhotoImport(unittest.TestCase):
    """The privacy property, and the thing that keeps the repo a sane size."""

    def _jpeg_with_gps(self):
        try:
            from PIL import Image                         # noqa: PLC0415
        except ImportError:
            self.skipTest("Pillow not installed")
        buf = io.BytesIO()
        Image.new("RGB", (2400, 1600), (90, 140, 70)).save(buf, "JPEG")
        blob = buf.getvalue()
        payload = b"Exif\x00\x00GPSLatitude 51.0500 GPSLongitude -114.0700"
        seg = b"\xff\xe1" + (len(payload) + 2).to_bytes(2, "big") + payload
        return blob[:2] + seg + blob[2:]

    def test_gps_coordinates_never_reach_the_library(self):
        blob = self._jpeg_with_gps()
        self.assertIn(b"GPSLatitude", blob, "the fixture lost its EXIF")
        d = tempfile.mkdtemp()
        src = os.path.join(d, "yard.jpg")
        with open(src, "wb") as fh:
            fh.write(blob)
        res = photo_import.import_photo(src, _SCI, "habit",
                                        os.path.join(d, "out"))
        with open(res["path"], "rb") as fh:
            out = fh.read()
        self.assertNotIn(b"GPSLatitude", out,
                         "a photo of the user's own yard was stored with their "
                         "home coordinates in it")
        self.assertTrue(res["stripped"])

    def test_stripping_does_not_depend_on_pillow(self):
        """Downscaling is a nicety and may be absent. Removing the coordinates
        is a safety property and must not be."""
        blob = self._jpeg_with_gps()
        self.assertNotIn(b"GPSLatitude", photo_import.strip_metadata(blob))

    def test_a_phone_photo_comes_out_a_sensible_size(self):
        try:
            from PIL import Image                         # noqa: PLC0415
        except ImportError:
            self.skipTest("Pillow not installed")
        d = tempfile.mkdtemp()
        src = os.path.join(d, "big.jpg")
        Image.new("RGB", (4000, 3000), (80, 120, 60)).save(src, "JPEG", quality=95)
        res = photo_import.import_photo(src, _SCI, "flower",
                                        os.path.join(d, "out"))
        with Image.open(res["path"]) as im:
            self.assertLessEqual(max(im.size), photo_import.MAX_EDGE)

    def test_a_non_image_is_refused_rather_than_stored(self):
        d = tempfile.mkdtemp()
        bad = os.path.join(d, "notes.txt")
        with open(bad, "w") as fh:
            fh.write("x" * 500)
        with self.assertRaises(ValueError):
            photo_import.import_photo(bad, _SCI, "habit", d)

    def test_filenames_are_keyed_by_name_not_by_id(self):
        self.assertEqual(photo_import.slugify("Rudbeckia hirta"), "rudbeckia_hirta")
        self.assertEqual(photo_import.slugify("Aster × versicolor"), "aster_versicolor")


class TestCoverageReport(unittest.TestCase):
    def test_missing_photos_are_warnings_not_errors(self):
        """A missing photograph is a gap in the work, not a defect in the data:
        the app renders fine without one, and a red gate nobody can fix in a
        commit gets ignored. What it must not be is invisible."""
        from src.data_quality import validate_photo_coverage   # noqa: PLC0415
        errors, warnings = validate_photo_coverage()
        self.assertEqual(errors, [])
        self.assertTrue(any("no photograph" in w for w in warnings),
                        "the coverage gap stopped being reported")
        self.assertTrue(any("'habit'" in w for w in warnings),
                        "per-slot coverage stopped being reported")

    def test_a_shipped_photo_must_carry_its_credit(self):
        from src import data_quality                          # noqa: PLC0415
        real = data_quality._load_json_list
        data_quality._load_json_list = lambda p: (
            [{"scientific_name": "X", "slot": "habit", "url": "u",
              "license": "cc-by", "attribution": ""}]
            if "plant_photos" in str(p) else real(p))
        try:
            errors, _ = data_quality.validate_photo_coverage()
        finally:
            data_quality._load_json_list = real
        self.assertTrue(any("attribution" in e for e in errors))


if __name__ == "__main__":
    unittest.main()
