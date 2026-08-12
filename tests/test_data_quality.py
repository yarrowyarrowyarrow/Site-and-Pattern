"""
tests/test_data_quality.py

Wraps src.data_quality.validate_all() in the unit-test harness so
`python -m unittest discover -s tests -t .` fails if anyone introduces a
typo, unknown tag, or duplicate scientific name into the shipped
plant JSON. Also exercises the per-error pathway by feeding deliberately
malformed records to ``validate_records`` directly.
"""

import json
import os
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.data_quality import (  # noqa: E402
    _parse_month_period,
    _load_use_keys,
    _load_ecoregion_keys,
    validate_all,
    validate_file,
    validate_plant,
    validate_records,
)


class TestShippedDataIsClean(unittest.TestCase):
    """The headline test: the data we ship right now must pass at the
    error level. Warnings are allowed (they're the data-debt backlog
    that lives alongside the data, surfaced for visibility)."""

    def test_validate_all_returns_no_errors(self):
        errors, _warnings = validate_all()
        if errors:
            self.fail(
                f"{len(errors)} validation error(s) in shipped plant data:\n  "
                + "\n  ".join(errors[:20])
                + ("\n  …" if len(errors) > 20 else "")
            )


class TestValidateAllWiresFaunaValidators(unittest.TestCase):
    """validate_all() must run the fauna data-spine validators (bee attributes +
    fauna photo-licence compliance, F37/A1), not only the plant catalogues — so
    the central gate (CI, check_plant_data.py, cli.py) enforces them too. Guards
    against a future refactor silently dropping them."""

    def test_fauna_validator_errors_propagate(self):
        import src.data_quality as dq
        orig_img, orig_bee = dq.validate_fauna_images, dq.validate_bee_attributes
        try:
            dq.validate_fauna_images = lambda: (["SENTINEL_IMG_ERROR"], [])
            dq.validate_bee_attributes = lambda: (["SENTINEL_BEE_ERROR"], [])
            errors, _w = dq.validate_all()
        finally:
            dq.validate_fauna_images, dq.validate_bee_attributes = orig_img, orig_bee
        self.assertIn("SENTINEL_IMG_ERROR", errors)
        self.assertIn("SENTINEL_BEE_ERROR", errors)


class TestMonthPeriodParser(unittest.TestCase):

    def test_empty_passes(self):
        for s in ("", "—", "-", "–", None):
            ok, _ = _parse_month_period(s or "")
            self.assertTrue(ok)

    def test_single_short_month(self):
        for m in ("Jan", "Jul", "Dec"):
            ok, msg = _parse_month_period(m)
            self.assertTrue(ok, msg)

    def test_single_long_month(self):
        ok, _ = _parse_month_period("July")
        self.assertTrue(ok)

    def test_hyphen_range(self):
        ok, _ = _parse_month_period("Jul-Aug")
        self.assertTrue(ok)

    def test_en_dash_range(self):
        ok, _ = _parse_month_period("July–August")  # en-dash
        self.assertTrue(ok)

    def test_em_dash_range(self):
        ok, _ = _parse_month_period("Jul—Aug")
        self.assertTrue(ok)

    def test_comma_separated(self):
        ok, _ = _parse_month_period("Apr-May, Jul")
        self.assertTrue(ok)

    def test_typo_fails(self):
        ok, msg = _parse_month_period("Jun-Augst")
        self.assertFalse(ok)
        self.assertIn("Augst", msg)


class TestPerRecordValidation(unittest.TestCase):
    """Sanity-check the individual rules against synthetic records — these
    are the failure modes the validator's supposed to catch."""

    @classmethod
    def setUpClass(cls):
        cls.use_keys = _load_use_keys()
        cls.ecoregion_keys = _load_ecoregion_keys()

    def _validate(self, record):
        """Return just the error list — most strict-enum tests assert
        on errors, not warnings."""
        errors, _w = validate_plant(
            record, source_label="test.json", idx=0,
            use_keys=self.use_keys,
            ecoregion_keys=self.ecoregion_keys,
        )
        return errors

    def _validate_full(self, record):
        return validate_plant(
            record, source_label="test.json", idx=0,
            use_keys=self.use_keys,
            ecoregion_keys=self.ecoregion_keys,
        )

    def _clean_record(self):
        return {
            "common_name": "Test Plant",
            "scientific_name": "Genus species",
            "plant_type": "herb",
            "sun_requirement": "full_sun",
            "water_needs": "medium",
            "perennial_annual": "perennial",
            "soil_ph_min": "5.5",
            "soil_ph_max": "7.0",
            "hardiness_zone_min": "3",
            "hardiness_zone_max": "5",
            "spacing_m": "0.3",
            "mature_height_m": "0.5",
            "bloom_period": "Jul-Aug",
            "fruit_period": "",
            "permaculture_uses": "pollinator,wildlife_habitat",
            "ab_ecoregion": "aspen_parkland",
            "native_to_alberta": 1,
            "cal_jan": "dormant",
        }

    def test_clean_record_passes(self):
        self.assertEqual(self._validate(self._clean_record()), [])

    def test_missing_plant_type_fails(self):
        r = self._clean_record()
        r["plant_type"] = ""
        errors = self._validate(r)
        self.assertTrue(any("plant_type" in e for e in errors))

    def test_bad_sun_requirement_fails(self):
        r = self._clean_record()
        r["sun_requirement"] = "partial_sun"  # common typo for partial_shade
        errors = self._validate(r)
        self.assertTrue(any("sun_requirement" in e and "partial_sun" in e
                            for e in errors))

    def test_ph_inversion_fails(self):
        r = self._clean_record()
        r["soil_ph_min"] = "8.0"
        r["soil_ph_max"] = "6.0"
        errors = self._validate(r)
        self.assertTrue(any("soil_ph_min" in e and "soil_ph_max" in e
                            for e in errors))

    def test_unknown_use_tag_warns(self):
        """Unknown use tags are soft drift — they surface as a warning so
        the data team can decide whether to promote them to canonical
        ``_USE_DEFINITIONS`` or treat as typos. Either way, not fatal."""
        r = self._clean_record()
        r["permaculture_uses"] = "pollinator,keystone_specie"  # typo
        errors, warnings = self._validate_full(r)
        self.assertEqual(errors, [])
        self.assertTrue(any("keystone_specie" in w for w in warnings))

    def test_unknown_ecoregion_warns(self):
        r = self._clean_record()
        r["ab_ecoregion"] = "aspen_parkland,prarie"
        errors, warnings = self._validate_full(r)
        self.assertEqual(errors, [])
        self.assertTrue(any("prarie" in w for w in warnings))

    def test_bad_bloom_period_warns(self):
        """Bloom period typos are soft — the data uses intentional
        uncertainty markers like 'August?' in places, so the validator
        flags them as warnings rather than failing."""
        r = self._clean_record()
        r["bloom_period"] = "Jun-Augst"
        errors, warnings = self._validate_full(r)
        self.assertEqual(errors, [])
        self.assertTrue(any("bloom_period" in w for w in warnings))

    def test_bad_calendar_status_warns(self):
        r = self._clean_record()
        r["cal_jul"] = "blooming"  # close to "flowering" but wrong
        errors, warnings = self._validate_full(r)
        self.assertEqual(errors, [])
        self.assertTrue(any("cal_jul" in w for w in warnings))

    def test_negative_spacing_fails(self):
        r = self._clean_record()
        r["spacing_m"] = "-0.5"
        errors = self._validate(r)
        self.assertTrue(any("spacing_m" in e for e in errors))


class TestDuplicateScientificNames(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.use_keys = _load_use_keys()
        cls.ecoregion_keys = _load_ecoregion_keys()

    def test_duplicates_surface_as_warning(self):
        """Duplicate sci names surface as warnings rather than errors —
        the existing duplicates in plants_master.json have NOTE: / FLAG:
        markers in their own notes acknowledging the data debt."""
        records = [
            {"common_name": "A", "scientific_name": "Genus species",
             "plant_type": "herb"},
            {"common_name": "B", "scientific_name": "Genus species",
             "plant_type": "herb"},
        ]
        errors, warnings = validate_records(
            records, "test.json",
            use_keys=self.use_keys,
            ecoregion_keys=self.ecoregion_keys,
        )
        self.assertEqual(errors, [])
        self.assertTrue(any("duplicate scientific_name" in w for w in warnings))


class TestValidateFile(unittest.TestCase):
    """End-to-end: write a JSON file, run validate_file on it, confirm
    we get the error we expect."""

    def test_file_with_strict_error_fails(self):
        """A file with a hard error (bad sun_requirement enum) returns
        a non-empty error list."""
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".json", delete=False, encoding="utf-8",
        ) as f:
            json.dump([{
                "common_name": "Bad Plant",
                "scientific_name": "Genus species",
                "plant_type": "herb",
                "sun_requirement": "partial_sun",  # close to "partial_shade"
            }], f)
            tmp_path = Path(f.name)
        try:
            errors, _w = validate_file(tmp_path)
            self.assertTrue(errors)
            self.assertTrue(any("partial_sun" in e for e in errors))
        finally:
            tmp_path.unlink()

    def test_file_with_bloom_typo_warns(self):
        """The canonical 'Augst' typo lands in warnings, not errors."""
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".json", delete=False, encoding="utf-8",
        ) as f:
            json.dump([{
                "common_name": "Bad Plant",
                "scientific_name": "Genus species",
                "plant_type": "herb",
                "bloom_period": "Augst",
            }], f)
            tmp_path = Path(f.name)
        try:
            errors, warnings = validate_file(tmp_path)
            self.assertEqual(errors, [])
            self.assertTrue(any("Augst" in w for w in warnings))
        finally:
            tmp_path.unlink()

    def test_missing_file_reports_cleanly(self):
        errors, warnings = validate_file(Path("/no/such/path/plants.json"))
        self.assertEqual(len(errors), 1)
        self.assertIn("not found", errors[0])
        self.assertEqual(warnings, [])

    def test_malformed_json_reports_cleanly(self):
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".json", delete=False, encoding="utf-8",
        ) as f:
            f.write("{ not valid json")
            tmp_path = Path(f.name)
        try:
            errors, _w = validate_file(tmp_path)
            self.assertEqual(len(errors), 1)
            self.assertIn("JSON parse error", errors[0])
        finally:
            tmp_path.unlink()


class TestFlowerColourGate(unittest.TestCase):
    """V2.48. The colour column was a genus-level guess and nothing checked it,
    which is how both columbines came to be red. This gate is what stops that
    class of error returning silently."""

    def test_the_shipped_data_passes(self):
        from src.data_quality import validate_flower_colour
        errors, warnings = validate_flower_colour()
        self.assertEqual(errors, [])
        # The warnings are the honest remaining debt (genera where no species
        # is checkable yet), not noise. If they hit zero, either somebody did
        # the sourcing work or the check stopped working.
        self.assertGreater(len(warnings), 0)

    def test_a_name_that_contradicts_its_hex_is_an_error(self):
        from src.data_quality import validate_flower_colour
        import src.data_quality as dq
        real = dq._load_json_list
        dq._load_json_list = lambda _p: [{
            "scientific_name": "Testus blueus", "common_name": "Blue Testflower",
            "plant_type": "wildflower", "flower_color": "#f2c11e",
        }]
        try:
            errors, _ = validate_flower_colour()
        finally:
            dq._load_json_list = real
        self.assertEqual(len(errors), 1)
        self.assertIn("its own name says 'blue'", errors[0])

    def test_a_uniform_uncheckable_genus_is_a_warning(self):
        from src.data_quality import validate_flower_colour
        import src.data_quality as dq
        real = dq._load_json_list
        dq._load_json_list = lambda _p: [
            {"scientific_name": f"Testus sp{i}", "common_name": f"Test {i}",
             "plant_type": "wildflower", "flower_color": "#f2c11e",
             "flower_colour_source": "estimated"} for i in range(3)]
        try:
            errors, warnings = validate_flower_colour()
        finally:
            dq._load_json_list = real
        self.assertEqual(errors, [])
        self.assertEqual(len(warnings), 1)
        self.assertIn("Testus", warnings[0])

    def test_one_checkable_species_clears_its_genus(self):
        """The warning means "nobody has verified any of these", so verifying
        one is what should silence it."""
        from src.data_quality import validate_flower_colour
        import src.data_quality as dq
        real = dq._load_json_list
        rows = [{"scientific_name": f"Testus sp{i}", "common_name": f"Test {i}",
                 "plant_type": "wildflower", "flower_color": "#f2c11e",
                 "flower_colour_source": "estimated"} for i in range(3)]
        rows[0]["flower_colour_source"] = "epithet"
        dq._load_json_list = lambda _p: rows
        try:
            _, warnings = validate_flower_colour()
        finally:
            dq._load_json_list = real
        self.assertEqual(warnings, [])


if __name__ == "__main__":
    unittest.main()
