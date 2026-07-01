"""
tests/test_lawn_zones.py

N2 — the lawn-to-habitat conversion tally. Pure (no Qt / no DB): zones are
drawn custom_shape features whose shape_type is a zone label; conversion_summary
tallies m² per zone and derives the converted / remaining / breakdown numbers.
"""

import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.lawn_zones import (  # noqa: E402
    ZONE_TYPES, LABEL_TO_KEY, is_zone_label, zone_key_for,
    conversion_summary, format_conversion_summary,
    LAWN_HABITAT_SCORE, lawn_counterfactual, format_lawn_counterfactual,
)


def _shape(zone_key, area, element_type="custom_shape"):
    return {
        "type": "Feature",
        "properties": {
            "element_type": element_type,
            "shape_type": ZONE_TYPES[zone_key]["label"],
            "area_m2": area,
        },
    }


class TestZoneCatalogue(unittest.TestCase):
    def test_five_zone_types(self):
        self.assertEqual(
            set(ZONE_TYPES),
            {"lawn_remaining", "restoration_year_1", "restoration_year_3",
             "established_native", "existing_remnant"})

    def test_label_roundtrip(self):
        for key, spec in ZONE_TYPES.items():
            self.assertTrue(is_zone_label(spec["label"]))
            self.assertEqual(zone_key_for(spec["label"]), key)

    def test_non_zone_label(self):
        self.assertFalse(is_zone_label("Garden Bed"))
        self.assertIsNone(zone_key_for("Patio / Deck"))


class TestConversionSummary(unittest.TestCase):
    def test_empty(self):
        s = conversion_summary([])
        self.assertEqual(s["converted_m2"], 0.0)
        self.assertEqual(s["lawn_remaining_m2"], 0.0)
        self.assertEqual(s["pct_converted"], 0.0)
        self.assertEqual(format_conversion_summary(s), "")

    def test_tally_and_percentages(self):
        feats = [
            _shape("lawn_remaining", 100.0),
            _shape("restoration_year_1", 30.0),
            _shape("restoration_year_3", 20.0),
            _shape("established_native", 50.0),
            _shape("existing_remnant", 40.0),
        ]
        s = conversion_summary(feats)
        self.assertEqual(s["converted_m2"], 100.0)        # 30+20+50
        self.assertEqual(s["lawn_remaining_m2"], 100.0)
        self.assertEqual(s["remnant_m2"], 40.0)
        # converted / (converted + lawn) = 100 / 200 = 50%
        self.assertEqual(s["pct_converted"], 50.0)
        self.assertEqual(s["total_zone_m2"], 240.0)

    def test_ignores_non_zone_shapes(self):
        feats = [
            {"properties": {"element_type": "custom_shape",
                            "shape_type": "Garden Bed", "area_m2": 999}},
            _shape("established_native", 25.0),
        ]
        s = conversion_summary(feats)
        self.assertEqual(s["converted_m2"], 25.0)
        self.assertEqual(s["total_zone_m2"], 25.0)

    def test_format_nonempty(self):
        s = conversion_summary([_shape("lawn_remaining", 100.0),
                                _shape("established_native", 100.0)])
        text = format_conversion_summary(s)
        self.assertIn("Converted", text)
        self.assertIn("50%", text)


class TestLawnCounterfactual(unittest.TestCase):
    """F10 — the Tallamy lawn-equivalent contrast."""

    def test_lawn_baseline_is_zero(self):
        self.assertEqual(LAWN_HABITAT_SCORE, 0)

    def test_accepts_plain_number(self):
        cf = lawn_counterfactual(62)
        self.assertEqual(cf["design_score"], 62)
        self.assertEqual(cf["lawn_score"], 0)
        self.assertEqual(cf["delta"], 62)
        self.assertEqual(cf["area_m2"], 0.0)

    def test_accepts_habitat_score_object(self):
        class _Score:
            total = 48
        cf = lawn_counterfactual(_Score())
        self.assertEqual(cf["design_score"], 48)

    def test_none_score_is_zero(self):
        cf = lawn_counterfactual(None)
        self.assertEqual(cf["design_score"], 0)

    def test_area_comes_from_converted_plus_lawn(self):
        s = conversion_summary([
            _shape("lawn_remaining", 80.0),
            _shape("established_native", 40.0),
            _shape("existing_remnant", 1000.0),   # remnant is NOT lawn ground
        ])
        cf = lawn_counterfactual(55, s)
        # lawn(80) + converted(40) = 120; remnant excluded
        self.assertEqual(cf["area_m2"], 120.0)

    def test_format_lines(self):
        s = conversion_summary([_shape("lawn_remaining", 100.0)])
        lines = format_lawn_counterfactual(lawn_counterfactual(70, s))
        self.assertTrue(any("70 / 100" in ln for ln in lines))
        self.assertTrue(any("lawn" in ln.lower() for ln in lines))
        self.assertTrue(any("reclaim" in ln.lower() for ln in lines))

    def test_format_without_area_omits_reclaim_line(self):
        lines = format_lawn_counterfactual(lawn_counterfactual(70))
        self.assertTrue(lines)
        self.assertFalse(any("reclaim" in ln.lower() for ln in lines))

    def test_format_empty_input(self):
        self.assertEqual(format_lawn_counterfactual({}), [])


if __name__ == "__main__":
    unittest.main()
