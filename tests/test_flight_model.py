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

    def test_the_visible_limit_is_not_nyquist(self):
        """The V2.45b correction. Nyquist reconstructs a signal; it does not
        let you SEE one. Two samples per beat reads as strobing, which is why
        every bird looked motionless while the maths was moving its wings."""
        from src.flight_model import (RENDER_FPS, SLOWED_HZ, VISIBLE_HZ,
                                      VISIBLE_FRAMES_PER_CYCLE)
        self.assertEqual(NYQUIST_HZ, RENDER_FPS / 2)
        self.assertLess(VISIBLE_HZ, NYQUIST_HZ,
                        "the visible limit must be stricter than Nyquist")
        self.assertEqual(VISIBLE_HZ, RENDER_FPS / VISIBLE_FRAMES_PER_CYCLE)
        self.assertLessEqual(SLOWED_HZ, VISIBLE_HZ)

    def test_everything_animates_at_a_rate_that_can_be_seen(self):
        """The property that actually matters: whatever we animate, there are
        at least six frames per cycle to show it in."""
        from src.flight_model import RENDER_FPS, VISIBLE_FRAMES_PER_CYCLE
        for hz in (2, 5, 5.2, 9, 11.5, 21, 26.8, 53, 166, 400):
            frames = RENDER_FPS / animation_hz(hz)
            self.assertGreaterEqual(
                frames, VISIBLE_FRAMES_PER_CYCLE - 0.01,
                f"{hz} Hz animates at {animation_hz(hz)} Hz — only "
                f"{frames:.1f} frames per cycle, which strobes")

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

    def test_a_songbird_is_slowed_rather_than_strobed(self):
        """21 Hz cannot be drawn on any ordinary display. Slowed keeps the
        rhythm, the bout and the stroke shape — all of it recognisable —
        where strobing keeps nothing."""
        from src.flight_model import SLOWED_HZ
        f = bird_flight(13, 225, style=BOUNDING)
        self.assertEqual(f["render"], "slowed")
        self.assertEqual(animation_hz(f["hz"]["mid"]), SLOWED_HZ)

    def test_the_boundaries(self):
        from src.flight_model import BLUR_ABOVE_HZ, VISIBLE_HZ
        self.assertEqual(render_mode(VISIBLE_HZ - 0.1), "discrete")
        self.assertEqual(render_mode(VISIBLE_HZ + 0.1), "slowed")
        self.assertEqual(render_mode(BLUR_ABOVE_HZ - 0.1), "slowed")
        self.assertEqual(render_mode(BLUR_ABOVE_HZ + 0.1), "blur")

    def test_a_slowed_beat_says_so(self):
        """P9: the screen is not showing this rate and the label must admit
        it, the same way an estimate admits it is an estimate."""
        text = describe(bird_flight(13, 225, style=BOUNDING))
        self.assertIn("slowed", text)


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


class TestTheWingsCanActuallyBeFound(unittest.TestCase):
    """The bug that made this whole increment invisible on screen.

    ``flapWings`` returns immediately unless ``obj.userData.wings`` is set, and
    ``09-models.js`` only sets it if it can find nodes called ``WingL`` /
    ``WingR``. Inside a MULTI-VARIANT fauna GLB the nodes are prefixed with the
    build name (``passerine_WingL``), and the prefix is only applied when the
    creature's spec carries a ``node`` picker.

    ``bird`` had no ``node``. So every baked bird was drawn as passerine +
    woodpecker + hummer superimposed, with no wing pivots at all — and no
    amount of correct wingbeat physics could move them. It was invisible from
    Python, invisible in the scene JSON, and on screen only an absence.

    These tests read the actual .glb files, so they fail if a model is
    re-exported with different node names as well.
    """

    @staticmethod
    def _glb_nodes(path):
        import json
        import struct
        data = path.read_bytes()
        off = 12                                   # skip the 12-byte header
        while off < len(data):
            clen, ctype = struct.unpack_from("<II", data, off)
            if ctype == 0x4E4F534A:                # 'JSON'
                doc = json.loads(data[off + 8:off + 8 + clen].decode("utf-8"))
                names = [n.get("name", "") for n in doc.get("nodes", [])]
                scene = (doc.get("scenes") or [{}])[0].get("nodes", [])
                return names, [names[i] for i in scene]
            off += 8 + clen + ((4 - clen % 4) % 4)
        return [], []

    def _models_dir(self):
        import pathlib
        return (pathlib.Path(__file__).resolve().parent.parent
                / "html" / "assets" / "models")

    def _specs(self):
        """`_GLB_CRITTER` read as text — the table is JS, and parsing it with a
        regex is still better than trusting a comment about it."""
        import pathlib
        import re
        src = (pathlib.Path(__file__).resolve().parent.parent / "html"
               / "scene3d" / "09-models.js").read_text(encoding="utf-8")
        body = src[src.index("const _GLB_CRITTER = {"):]
        body = body[:body.index("\n};")]
        out = {}
        for m in re.finditer(r"^\s{2}(\w+):\s*\{", body, re.M):
            kind = m.group(1)
            entry = body[m.end():]
            nxt = re.search(r"^\s{2}\w+:\s*\{", entry, re.M)
            entry = entry[:nxt.start()] if nxt else entry
            out[kind] = {
                "key": (re.search(r"key:\s*'(\w+)'", entry) or [None, ""])[1],
                "has_node": "node:" in entry,
                "flaps": "flap: null" not in entry and "flap:" in entry,
            }
        return out

    def test_the_spec_table_parsed(self):
        specs = self._specs()
        self.assertIn("bird", specs)
        self.assertIn("butterfly", specs)
        self.assertTrue(specs["bird"]["flaps"])

    def test_a_multi_variant_model_must_have_a_node_picker(self):
        """The rule the bird broke, stated generally: if the wing nodes are
        prefixed, the spec needs a `node` or the prefix is never applied and
        `byName('WingL')` cannot resolve."""
        models = self._models_dir()
        if not models.exists():                    # pragma: no cover
            self.skipTest("model assets not present in this checkout")
        problems = []
        for kind, spec in self._specs().items():
            if not spec["flaps"] or not spec["key"]:
                continue
            glb = models / f"fauna_{spec['key']}.glb"
            if not glb.exists():
                continue
            names, roots = self._glb_nodes(glb)
            wings = [n for n in names if "Wing" in n]
            if not wings:
                continue
            prefixed = all("_Wing" in w for w in wings)
            if prefixed and not spec["has_node"]:
                problems.append(
                    f"{kind}: {glb.name} has prefixed wing nodes "
                    f"({wings[0]}) but the spec has no `node` picker, so "
                    f"userData.wings is never set and it cannot flap")
        self.assertFalse(problems, "\n".join(problems))

    def test_every_flapping_creature_can_reach_a_wing(self):
        """End to end: for each kind that flaps, at least one resolvable wing
        node exists in its model."""
        models = self._models_dir()
        if not models.exists():                    # pragma: no cover
            self.skipTest("model assets not present in this checkout")
        for kind, spec in self._specs().items():
            if not spec["flaps"] or not spec["key"]:
                continue
            glb = models / f"fauna_{spec['key']}.glb"
            if not glb.exists():
                continue
            names, _roots = self._glb_nodes(glb)
            self.assertTrue([n for n in names if n.endswith("WingL")],
                            f"{kind}: {glb.name} has no WingL node at all")

    def test_the_bird_builds_match_the_model(self):
        """`_bird_appearance` picks a build name; the GLB has to carry it, or
        the lookup falls back to the first variant and every woodpecker is a
        passerine."""
        models = self._models_dir()
        if not (models / "fauna_bird.glb").exists():   # pragma: no cover
            self.skipTest("model assets not present in this checkout")
        _names, roots = self._glb_nodes(models / "fauna_bird.glb")
        from src.scene_wildlife import _BIRD_BUILD_WORDS
        builds = {plan for _word, plan in _BIRD_BUILD_WORDS} | {"passerine"}
        self.assertFalse(builds - set(roots),
                         f"builds with no model variant: {builds - set(roots)}")

    def test_every_appearance_build_has_a_model_variant(self):
        """The same class of bug as the bird, generalised: a `build` the GLB
        does not carry degrades silently to the first variant, so every
        woodpecker would render as a passerine and nobody would be told.

        Only birds were actually broken — lep builds (butterfly / skipper /
        swallowtail) and bee builds (round / stout / slender / leafcutter) all
        matched. This is here so the next drift between
        `src/scene_wildlife.py` and the exported models fails a test instead of
        quietly changing what an animal looks like.
        """
        models = self._models_dir()
        if not models.exists():                    # pragma: no cover
            self.skipTest("model assets not present in this checkout")
        import json
        import pathlib
        root = pathlib.Path(__file__).resolve().parent.parent
        fauna = json.loads((root / "data" / "fauna_master.json")
                           .read_text(encoding="utf-8"))
        from src.scene_wildlife import (_bee_appearance, _bird_appearance,
                                        _lep_appearance)
        wanted = {"bird": set(), "lep": set(), "bee": set()}
        for r in fauna:
            name = r.get("common_name", "")
            sci = r.get("scientific_name", "") or " "
            if r.get("taxon") == "bird":
                wanted["bird"].add(_bird_appearance(name).get("build"))
            elif r.get("taxon") == "lepidoptera":
                wanted["lep"].add(
                    _lep_appearance(name, sci, "butterfly", None).get("build"))
            elif r.get("taxon") == "bee":
                wanted["bee"].add(
                    _bee_appearance(sci.split(" ")[0], name, None).get("build"))
        for key, builds in wanted.items():
            glb = models / f"fauna_{key}.glb"
            if not glb.exists():
                continue
            _names, roots = self._glb_nodes(glb)
            missing = {b for b in builds if b} - set(roots)
            self.assertFalse(
                missing,
                f"fauna_{key}.glb has no variant for builds {missing} — "
                f"they will silently render as {roots[0] if roots else '?'}")

    def test_birds_travel_at_constant_speed_not_an_exponential_ease(self):
        """`pos.lerp(tgt, dt * k)` launches a bird at enormous speed and
        decelerates into the perch. Nothing alive moves like that, and it is
        half of "the birds move too fast for me to see what they are doing".
        A real bird holds a roughly steady airspeed and brakes at the end."""
        import pathlib
        src = (pathlib.Path(__file__).resolve().parent.parent / "html"
               / "scene3d" / "07-wildlife.js").read_text(encoding="utf-8")
        code = "\n".join(ln for ln in src.splitlines()
                         if not ln.lstrip().startswith("//"))
        self.assertNotIn("c.pos.lerp(tgt", code,
                         "a travel branch is easing exponentially again")

    def test_the_wingbeat_stays_exact_even_though_travel_is_slowed(self):
        """Bird travel speed is a legibility choice and says so; the wingbeat
        is physics and must not be quietly tuned for looks. If someone ever
        "fixes" the flap by editing the model, this is the tripwire."""
        from src.flight_model import bird_flight, BOUNDING
        band = bird_flight(11, 203, style=BOUNDING)["hz"]
        self.assertTrue(19 <= band["lo"] and band["hi"] <= 28,
                        f"chickadee band drifted to {band}")

    def test_a_wing_pivot_must_actually_contain_geometry(self):
        """The bug that made butterflies "horizontal and flat" (V2.45b).

        Birds, bees and flies carry the wing mesh on the ``WingL``/``WingR``
        node itself. **Lepidoptera do not**: theirs are EMPTY grouping nodes
        and the geometry is in six siblings — ``ForeL/HindL/RimL`` per side.
        So the pivot rotated an empty node at exactly the right frequency
        while the meshes that are actually the wings sat untouched.

        Finding the node is not the same as finding the wing, and this is the
        test that knows the difference. It reads the real .glb files and, for
        every variant that flaps, asserts that some geometry is reachable under
        each side once the adoption rule in 09-models.js has been applied.
        """
        models = self._models_dir()
        if not models.exists():                    # pragma: no cover
            self.skipTest("model assets not present in this checkout")
        import json
        import struct

        def doc(path):
            data = path.read_bytes()
            off = 12
            while off < len(data):
                clen, ctype = struct.unpack_from("<II", data, off)
                if ctype == 0x4E4F534A:
                    return json.loads(
                        data[off + 8:off + 8 + clen].decode("utf-8"))
                off += 8 + clen + ((4 - clen % 4) % 4)
            return {}

        # The parts 09-models.js adopts into a wing pivot when the wing node
        # itself is empty — READ FROM THE CODE, not restated here. A copy in
        # the test would keep passing after somebody deleted the adoption loop,
        # which is exactly the failure this test exists to prevent (and is what
        # the first cut of it did).
        import pathlib
        import re
        js = (pathlib.Path(__file__).resolve().parent.parent / "html"
              / "scene3d" / "09-models.js").read_text(encoding="utf-8")
        m = re.search(r"for \(const part of \[([^\]]*)\]\)", js)
        ADOPTED = tuple(re.findall(r"'(\w+)'", m.group(1))) if m else ()
        problems = []
        for kind, spec in self._specs().items():
            if not spec["flaps"] or not spec["key"]:
                continue
            glb = models / f"fauna_{spec['key']}.glb"
            if not glb.exists():
                continue
            j = doc(glb)
            nodes = j.get("nodes", [])
            named = {n.get("name", ""): n for n in nodes}

            def has_geom(node):
                if node is None:
                    return False
                if "mesh" in node:
                    return True
                return any(has_geom(nodes[c]) for c in node.get("children", []))

            for wing in [n for n in named if n.endswith("WingL")]:
                variant = wing[:-5]              # strip 'WingL'
                side = "L"
                reachable = has_geom(named.get(wing))
                if not reachable:
                    reachable = any(has_geom(named.get(variant + p + side))
                                    for p in ADOPTED)
                if not reachable:
                    problems.append(
                        f"{kind}: {glb.name} → {wing} has no geometry and no "
                        f"{'/'.join(variant + p + side for p in ADOPTED)} to "
                        f"adopt, so its pivot rotates nothing")
        self.assertFalse(problems, "\n".join(problems))

    def test_the_lep_models_are_the_case_that_needs_adoption(self):
        """Pins WHY the adoption rule exists, so nobody deletes it as dead
        code: the lep wing nodes really are empty in the shipped model."""
        models = self._models_dir()
        glb = models / "fauna_lep.glb"
        if not glb.exists():                       # pragma: no cover
            self.skipTest("model assets not present in this checkout")
        names, _roots = self._glb_nodes(glb)
        for part in ("butterfly_ForeL", "butterfly_HindL", "butterfly_RimL"):
            self.assertIn(part, names,
                          "the lep wing parts moved — update the adoption "
                          "list in 09-models.js to match")
        import pathlib
        js = (pathlib.Path(__file__).resolve().parent.parent / "html"
              / "scene3d" / "09-models.js").read_text(encoding="utf-8")
        self.assertIn("['Fore', 'Hind', 'Rim']", js)

    def test_the_diagnostic_hook_exists(self):
        """`permaFlightReport()` answers "why isn't this flapping?" in one
        call. It exists because doing it from the outside took a session."""
        import pathlib
        js = (pathlib.Path(__file__).resolve().parent.parent / "html"
              / "scene3d" / "18-flight.js").read_text(encoding="utf-8")
        self.assertIn("window.permaFlightReport", js)
        self.assertIn("hasWings", js)
