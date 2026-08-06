"""
Flight physics (V2.45) — wingbeat frequency, bout structure, and the limits.

Author's report: birds *"are just gliding as if along a zip line"*, butterflies
should flap *"fast, fast, slow"*, and it *"should be mathematically correct"*.

The tests that matter most, in order:

1. **The predictions overlap published measurements.** A model that produced
   confident wrong numbers would be worse than the hardcoded constants it
   replaced, because it would look principled.
2. **The wing-folding distinction holds.** Applying the bounding correction to
   a gliding bird overpredicts a red-tailed hawk by a factor of three. The
   first cut did exactly that; this is the guard.
3. **Nothing above Nyquist is animated at its true rate.** A bee drawn at
   160 Hz on a 60 fps display aliases into a slow backwards flutter, which is
   confidently wrong rather than merely imprecise.
"""

from __future__ import annotations

import unittest

from src.flight_model import (BOUNDING, BURST, CONTINUOUS, FLAP_GLIDE,
                              HOVERING, NYQUIST_HZ, SOARING, animation_hz,
                              bee_flight, bird_flight, describe, flight_for,
                              lepidoptera_flight, measured_for,
                              pennycuick_hz, render_mode)


def _overlaps(band: dict, lo: float, hi: float) -> bool:
    return not (band["hi"] < lo or band["lo"] > hi)


class TestAgainstPublishedMeasurements(unittest.TestCase):
    """The model has to agree with birds that have actually been filmed."""

    #: (name, mass_g, span_mm, style, published_lo, published_hi)
    CASES = [
        ("Black-capped Chickadee", 11, 203, BOUNDING, 25, 30),
        ("American Goldfinch", 13, 225, BOUNDING, 20, 25),
        ("Downy Woodpecker", 27, 280, BOUNDING, 15, 18),
        ("American Robin", 77, 340, FLAP_GLIDE, 12, 14),
        ("Blue Jay", 85, 410, FLAP_GLIDE, 6, 8),
        ("Black-billed Magpie", 177, 600, FLAP_GLIDE, 5, 6),
        ("Ruffed Grouse", 600, 560, BURST, 10, 12),
        ("Red-tailed Hawk", 1030, 1220, SOARING, 2.6, 3.0),
    ]

    def test_every_prediction_overlaps_its_published_range(self):
        misses = []
        for name, m, b, style, lo, hi in self.CASES:
            band = bird_flight(m, b, style=style)["hz"]
            if not _overlaps(band, lo, hi):
                misses.append(f"{name}: predicted {band['lo']}–{band['hi']} Hz, "
                              f"published {lo}–{hi} Hz")
        self.assertFalse(misses, "\n".join(misses))

    def test_the_bands_are_not_so_wide_they_say_nothing(self):
        """A band from 1 to 100 Hz would 'overlap' everything and mean
        nothing. Uncertainty has to stay honest in both directions (P9)."""
        for name, m, b, style, _lo, _hi in self.CASES:
            band = bird_flight(m, b, style=style)["hz"]
            self.assertLess(band["hi"] / max(0.01, band["lo"]), 2.5,
                            f"{name}: band spans more than 2.5x")


class TestTheFoldingDistinction(unittest.TestCase):
    """The one thing in the module that must not be got wrong."""

    def test_a_bounding_bird_beats_faster_than_the_raw_formula(self):
        """Wings folded through the pause means no lift through the pause,
        so the burst has to overcompensate."""
        raw = pennycuick_hz(11, 203, style=BOUNDING)
        band = bird_flight(11, 203, style=BOUNDING)["hz"]
        self.assertGreater(band["lo"], raw,
                           "the bounding correction is not being applied")

    def test_a_gliding_bird_is_NOT_corrected(self):
        """A hawk holds its wings out through the glide, so they keep carrying
        it and there is nothing to compensate for. Correcting it overpredicts
        by a factor of three — which is what the first cut did."""
        raw = pennycuick_hz(1030, 1220, style=SOARING)
        band = bird_flight(1030, 1220, style=SOARING)["hz"]
        self.assertLessEqual(band["lo"], raw)
        self.assertGreaterEqual(band["hi"], raw)

    def test_only_bounding_folds(self):
        from src.flight_model import _FOLDS_WINGS
        self.assertEqual(set(_FOLDS_WINGS), {BOUNDING})

    def test_the_correction_has_the_derived_magnitude(self):
        """f_burst = f_continuous / sqrt(duty). Not a tuned fudge — if
        somebody replaces it with one, this fails."""
        import math
        from src.flight_model import _STYLES
        duty_lo, duty_hi = _STYLES[BOUNDING][0], _STYLES[BOUNDING][1]
        raw = pennycuick_hz(11, 203, style=BOUNDING)
        band = bird_flight(11, 203, style=BOUNDING)["hz"]
        self.assertAlmostEqual(band["lo"], raw / math.sqrt(duty_hi), places=1)
        self.assertAlmostEqual(band["hi"], raw / math.sqrt(duty_lo), places=1)


class TestMeasurementsWin(unittest.TestCase):

    def test_a_published_value_beats_the_formula(self):
        f = bird_flight(1400, 1150, style=SOARING,
                        measured_hz=measured_for("Bubo virginianus"))
        self.assertEqual(f["basis"], "measured")
        self.assertEqual((f["hz"]["lo"], f["hz"]["hi"]), (2.2, 3.0))

    def test_the_owl_is_why_measurements_exist(self):
        """Great horned owls have exceptionally low wing loading and the
        formula overpredicts them badly. The right answer is to ship the
        measurement, not to tune a constant until one outlier fits."""
        predicted = bird_flight(1400, 1150, style=SOARING)["hz"]
        self.assertFalse(_overlaps(predicted, 2.2, 3.0),
                         "if the formula now fits the owl, drop the override")

    def test_every_measured_species_is_in_the_catalogue(self):
        """A measurement for an animal the app does not have is dead weight,
        and usually a typo in a scientific name."""
        import json
        import pathlib
        from src.flight_model import MEASURED_HZ
        root = pathlib.Path(__file__).resolve().parent.parent
        fauna = {r["scientific_name"] for r in
                 json.loads((root / "data" / "fauna_master.json")
                            .read_text(encoding="utf-8"))}
        # Apis mellifera is the bee calibration anchor and is deliberately not
        # in the catalogue — it is not native, which is rather the point.
        extra = set(MEASURED_HZ) - fauna - {"Apis mellifera"}
        self.assertFalse(extra, f"measured species not in fauna_master: {extra}")


class TestInsects(unittest.TestCase):

    def test_butterflies_match_their_anchors(self):
        # Monarch and cabbage white, the two species the fit is calibrated on.
        self.assertTrue(_overlaps(lepidoptera_flight(100)["hz"], 5, 6))
        self.assertTrue(_overlaps(lepidoptera_flight(45)["hz"], 9, 12))

    def test_bees_match_their_anchors(self):
        self.assertTrue(_overlaps(bee_flight(13)["hz"], 215, 245))   # honeybee
        self.assertTrue(_overlaps(bee_flight(20)["hz"], 150, 165))   # Bombus

    def test_a_tiny_bee_says_it_is_extrapolating(self):
        """Below ~10 mm the fit is past both anchors. It must say so rather
        than shipping a confident number nobody measured (P9)."""
        small = bee_flight(6)
        self.assertEqual(small["basis"], "extrapolated")
        self.assertGreater(small["hz"]["hi"] / small["hz"]["lo"],
                           bee_flight(13)["hz"]["hi"] / bee_flight(13)["hz"]["lo"])

    def test_the_flight_style_vocabulary_is_the_one_in_the_data(self):
        """The first cut matched substrings like 'fast' and 'swift' that
        appear nowhere in lepidoptera_attributes_master.json, so it silently
        did nothing for 31 of 31 species."""
        import json
        import pathlib
        from src.flight_model import _LEP_STYLE
        root = pathlib.Path(__file__).resolve().parent.parent
        rows = json.loads((root / "data" /
                           "lepidoptera_attributes_master.json")
                          .read_text(encoding="utf-8"))
        used = {(r.get("flight_style") or "").lower()
                for r in rows if r.get("flight_style")}
        self.assertTrue(used, "no flight_style values in the seed data")
        self.assertFalse(used - set(_LEP_STYLE),
                         f"unhandled flight styles: {used - set(_LEP_STYLE)}")

    def test_style_changes_the_answer(self):
        """A column that reaches the model and changes nothing is a column
        nothing reads — which is what flight_style was until V2.45."""
        darting = lepidoptera_flight(45, flight_style="darting")["hz"]["mid"]
        gliding = lepidoptera_flight(45, flight_style="gliding")["hz"]["mid"]
        self.assertGreater(darting, gliding * 1.3)

    def test_skippers_are_not_butterflies(self):
        """Hesperiidae are the buzzy exception and are a separate `kind` in
        the catalogue for exactly this reason."""
        self.assertGreater(lepidoptera_flight(30, kind="skipper")["hz"]["mid"],
                           lepidoptera_flight(30, kind="butterfly")["hz"]["mid"])


class TestTheRenderLimit(unittest.TestCase):

    def test_nyquist_is_half_the_frame_rate(self):
        self.assertEqual(NYQUIST_HZ, 30.0)

    def test_a_bee_is_never_animated_at_its_true_rate(self):
        """160 Hz on a 60 fps display is the wagon-wheel effect: a slow
        backwards flutter that is confidently wrong."""
        f = bee_flight(20)
        self.assertEqual(f["render"], "blur")
        self.assertLessEqual(animation_hz(f["hz"]["mid"]), NYQUIST_HZ)

    def test_a_butterfly_is_drawn_truthfully(self):
        f = lepidoptera_flight(100)
        self.assertEqual(f["render"], "discrete")
        self.assertAlmostEqual(animation_hz(f["hz"]["mid"]), f["hz"]["mid"])

    def test_the_boundary(self):
        self.assertEqual(render_mode(29.9), "discrete")
        self.assertEqual(render_mode(30.1), "blur")


class TestBoutStructure(unittest.TestCase):
    """The author's "fast, fast, slow"."""

    def test_a_bounding_bird_has_a_burst_and_a_pause(self):
        f = bird_flight(11, 203, style=BOUNDING)
        self.assertGreater(f["burst_beats"]["lo"], 0)
        self.assertGreater(f["pause_s"]["lo"], 0)
        self.assertGreater(f["bound_dip_m"]["mid"], 0)

    def test_a_bee_never_pauses(self):
        f = bee_flight(13)
        self.assertEqual(f["pause_s"]["hi"], 0.0)
        self.assertEqual(f["bound_dip_m"]["hi"], 0.0)
        self.assertEqual(f["style"], CONTINUOUS)

    def test_a_longer_pause_drops_the_bird_further(self):
        """The dip is derived from the pause by s = 1/4 g t^2, not tuned
        separately — so the two cannot drift apart."""
        from src.flight_model import _STYLES
        short = bird_flight(11, 203, style=BOUNDING)["bound_dip_m"]
        self.assertGreater(short["hi"], short["lo"])
        pause = _STYLES[BOUNDING]
        self.assertLess(pause[4], pause[5])

    def test_the_dip_is_capped(self):
        """A soaring bird's pause is measured in seconds; uncapped, s=1/4gt^2
        would drop a hawk through the floor."""
        f = bird_flight(1030, 1220, style=SOARING)
        self.assertLessEqual(f["bound_dip_m"]["hi"], 2.0)


class TestTheResolver(unittest.TestCase):
    """`flight_for` is what the app calls; it must never raise or return
    nothing, whatever it is handed."""

    def test_every_taxon_returns_a_usable_shape(self):
        for taxon in ("bird", "bee", "lepidoptera", "mammal",
                      "other_insect", "", "nonsense"):
            f = flight_for(taxon)
            for key in ("hz", "render", "style", "basis", "burst_beats",
                        "pause_s", "bound_dip_m"):
                self.assertIn(key, f, f"{taxon} is missing {key}")
            self.assertGreater(f["hz"]["mid"], 0, taxon)

    def test_a_known_species_gets_its_measurement_through_the_resolver(self):
        f = flight_for("bird", scientific_name="Poecile atricapillus",
                       mass_g=11, span_mm=203, style=BOUNDING)
        self.assertEqual(f["basis"], "measured")

    def test_missing_morphology_still_flies(self):
        """An animal with no measurements at all must still get a band, not a
        crash and not a zero."""
        f = flight_for("bird", scientific_name="Nothing here")
        self.assertGreater(f["hz"]["lo"], 0)

    def test_describe_always_names_the_basis(self):
        """"23-27 Hz" and "23-27 Hz (estimated)" are different claims and the
        app must not blur them (P9)."""
        for f in (bird_flight(11, 203, style=BOUNDING), bee_flight(6),
                  bird_flight(1400, 1150, style=SOARING,
                              measured_hz=(2.2, 3.0))):
            text = describe(f)
            self.assertTrue(
                any(w in text for w in ("measured", "estimated", "extrapolated")),
                text)


class TestTheDataFile(unittest.TestCase):

    def _rows(self):
        import json
        import pathlib
        root = pathlib.Path(__file__).resolve().parent.parent
        return json.loads((root / "data" / "bird_morphology_master.json")
                          .read_text(encoding="utf-8"))

    def test_every_bird_in_the_catalogue_has_morphology(self):
        import json
        import pathlib
        root = pathlib.Path(__file__).resolve().parent.parent
        birds = {r["scientific_name"] for r in
                 json.loads((root / "data" / "fauna_master.json")
                            .read_text(encoding="utf-8"))
                 if r.get("taxon") == "bird"}
        have = {r["scientific_name"] for r in self._rows()}
        self.assertEqual(birds - have, set(), "birds with no morphology")
        self.assertEqual(have - birds, set(), "morphology for absent birds")

    def test_nothing_claims_to_be_verified(self):
        """These were entered without network access to check them against
        primary sources. A number nobody has verified must not be presented as
        one that has been (P9). When a session with egress checks them against
        AVONET and Dunning, this test is what should be updated — deliberately.
        """
        unverified = [r["scientific_name"] for r in self._rows()
                      if not r.get("verified")]
        self.assertEqual(len(unverified), len(self._rows()),
                         "a row claims verification — was it actually checked?")

    def test_every_row_carries_a_citation(self):
        for r in self._rows():
            self.assertTrue(r.get("morph_data_citation"),
                            f"{r['scientific_name']} has no citation")

    def test_flight_styles_are_in_the_schema_vocabulary(self):
        allowed = {"bounding", "flap_glide", "soaring", "burst", "hovering",
                   "continuous", "unknown"}
        for r in self._rows():
            self.assertIn(r["flight_style"], allowed, r["scientific_name"])

    def test_masses_and_spans_are_plausible(self):
        """A decimal-point slip is the likeliest data error and the hardest to
        see: a 110 g chickadee would look fine in a table."""
        for r in self._rows():
            self.assertTrue(2.0 <= r["mass_g"] <= 2500.0, r)
            self.assertTrue(80.0 <= r["wingspan_mm"] <= 2000.0, r)
            # Bigger birds have bigger wings. Rough, but it catches a swap.
            self.assertGreater(r["wingspan_mm"], r["mass_g"] ** 0.33 * 40, r)


if __name__ == "__main__":
    unittest.main()
