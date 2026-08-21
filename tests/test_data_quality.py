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


class TestUseTagsAgainstEdges(unittest.TestCase):
    """V2.65 (F120). The score reads use tags; the citations live in edges.
    Nothing kept them in agreement, so the app held a sourced `larval_host`
    record for Chokecherry while telling the user their chokecherry planting
    had *"no butterfly/moth host plants"*.

    The reconciliation is additive, and the **taxon requirement is the part
    worth guarding** — without it a gall midge in a hawthorn, a horntail in a
    spruce and a deer mouse eating grama seed all voted, and 21 of the 101
    species would have been tagged on evidence that says nothing about
    caterpillars or birds.
    """

    def setUp(self):
        from src.data_quality import _TAG_BACKED_BY_EDGE, use_tags_vs_edges
        self.table = _TAG_BACKED_BY_EDGE
        self.found = use_tags_vs_edges

    def test_the_shipped_data_has_no_contradiction_left(self):
        """The headline. Every sourced edge that backs a tag now has it."""
        self.assertEqual(self.found(), {})

    def test_each_tag_names_the_taxon_that_has_to_be_at_the_far_end(self):
        """The table is `{tag: (relationships, taxon)}` and both halves are
        read. A three-element or bare-tuple entry means someone reverted to
        the relationship-only shape that shipped the wrong tags."""
        for tag, entry in self.table.items():
            self.assertEqual(len(entry), 2, tag)
            rels, want = entry
            self.assertIsInstance(rels, tuple, tag)
            self.assertTrue(rels, tag)
            self.assertIn(want, ("lepidoptera", "bird", "bee",
                                 "other_insect", "mammal"), tag)

    def test_a_non_lepidopteran_larval_host_does_not_earn_host_plant(self):
        """A gall midge developing in a hawthorn is a true larval-host record
        and says nothing whatever about butterflies. `host_plant` drives
        design_critic's butterfly/moth line, so it must not be earned here."""
        rels, want = self.table["host_plant"]
        self.assertEqual(rels, ("larval_host",))
        self.assertEqual(want, "lepidoptera")

    def test_a_mammal_eating_seed_does_not_earn_bird_food(self):
        """Three `seed_food` edges in the shipped data name a deer mouse."""
        rels, want = self.table["bird_food"]
        self.assertEqual(set(rels), {"fruit_food", "seed_food"})
        self.assertEqual(want, "bird")

    def test_every_tagged_species_that_the_edges_justify_still_has_the_tag(self):
        """The reconciliation ran over the shipped files, not a copy. Spot-check
        four the report named, one per justifying taxon and file."""
        rows = []
        for name in ("plants_master.json", "garden_plants.json"):
            with open(os.path.join(
                    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                    "data", name), encoding="utf-8") as fh:
                rows += [r for r in json.load(fh) if isinstance(r, dict)]
        by = {(r.get("common_name") or "").strip().lower(): r for r in rows}
        for common, tag in (("chokecherry", "host_plant"),
                            ("balsam poplar", "host_plant"),
                            ("bearberry", "host_plant"),
                            ("bur oak", "bird_food")):
            tags = {t.strip() for t in
                    (by[common].get("permaculture_uses") or "").split(",")}
            self.assertIn(tag, tags, common)

    def test_the_reconciler_only_ever_adds(self):
        """Absence of an edge is absence of evidence, not evidence of absence:
        the catalogue's edges cover a fraction of what is real, so removing a
        tag for want of a record would delete a human's judgement on the
        strength of a gap. Asserted by re-running the reconciler in report
        mode and checking it proposes nothing at all."""
        import importlib.util
        root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        path = os.path.join(root, "scripts", "reconcile_use_tags.py")
        spec = importlib.util.spec_from_file_location("reconcile_use_tags",
                                                      path)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        import contextlib
        import io
        with contextlib.redirect_stdout(io.StringIO()):
            result = mod.reconcile(write=False)
        self.assertEqual(result["needed"], {})


class TestExcludedTaxaStayExcluded(unittest.TestCase):
    """A species removed on purpose (V2.74) must not drift back in.

    The first entry is *Rudbeckia hirta*, which VASCAN and Moss's *Flora of
    Alberta* both record as introduced in Alberta and which nonetheless shipped
    flagged `native_to_alberta = 1`, all the way onto the public website. It
    has a live route back: `data/fetched/fauna_edges_candidates.json` still holds 389
    GloBI records naming it, and re-adding the plant row is all it would take
    for the next sourcing pass to re-propose its 150 edges."""

    def setUp(self):
        import src.data_quality as dq
        self.dq = dq
        self._orig_dir = dq.DATA_DIR
        self.tmp = Path(tempfile.mkdtemp())
        for name in ("excluded_taxa.json", "plants_master.json",
                     "garden_plants.json", "plant_fauna_master.json"):
            (self.tmp / name).write_text(
                (self._orig_dir / name).read_text(encoding="utf-8"),
                encoding="utf-8")
        dq.DATA_DIR = self.tmp

    def tearDown(self):
        self.dq.DATA_DIR = self._orig_dir

    def _write(self, name, records):
        (self.tmp / name).write_text(json.dumps(records), encoding="utf-8")

    def test_the_shipped_catalogue_carries_none_of_them(self):
        self.dq.DATA_DIR = self._orig_dir
        errors, _w = self.dq.validate_excluded_taxa()
        self.assertEqual(errors, [])

    def test_the_binomial_coming_back_is_an_error(self):
        records = json.loads((self.tmp / "plants_master.json").read_text())
        records.append({"scientific_name": "Rudbeckia hirta",
                        "common_name": "Black-eyed Susan"})
        self._write("plants_master.json", records)
        errors, _w = self.dq.validate_excluded_taxa()
        self.assertTrue(any("Rudbeckia hirta" in e for e in errors), errors)

    def test_an_edge_naming_it_is_an_error_too(self):
        """Edges key on `common_name`, not on the binomial, so a check that
        only knew scientific names would have let all 150 back silently."""
        edges = json.loads((self.tmp / "plant_fauna_master.json").read_text())
        edges.append({"plant": "Black-eyed Susan", "fauna": "Bombus ternarius",
                      "relationship": "nectar", "source": "globi_ecdysis_org"})
        self._write("plant_fauna_master.json", edges)
        errors, _w = self.dq.validate_excluded_taxa()
        self.assertTrue(
            any("plant_fauna_master.json" in e for e in errors), errors)

    def test_the_error_names_the_authority(self):
        """The point of the file is the reasoning, so the failure has to carry
        it — a bare "not allowed" sends the next person to re-derive the call
        from scratch, which is how it got in the first time."""
        records = json.loads((self.tmp / "plants_master.json").read_text())
        records.append({"scientific_name": "Rudbeckia hirta",
                        "common_name": "Black-eyed Susan"})
        self._write("plants_master.json", records)
        errors, _w = self.dq.validate_excluded_taxa()
        self.assertTrue(any("VASCAN" in e and "V2.74" in e for e in errors),
                        errors)

    def test_the_second_removal_is_recorded_with_its_own_evidence_shape(self):
        """*Helianthus giganteus* (V2.75), and the difference from the first.

        V2.74 removed a species the occurrence data actively defended -- 215
        georeferenced records -- because presence is not nativity. This one had
        no occurrence entry at all, which is weaker evidence than it looks: the
        derived file records only species WITH rows, so an absence there means
        either no records or a fetch GBIF refused, and it cannot tell them
        apart afterwards. The entry has to say that rather than let a silence
        read as a finding."""
        self.dq.DATA_DIR = self._orig_dir
        blob = json.loads(
            (self._orig_dir / "excluded_taxa.json").read_text(encoding="utf-8"))
        entry = next(t for t in blob["taxa"]
                     if t["scientific_name"] == "Helianthus giganteus")
        self.assertIn("VASCAN", entry["authority"])
        self.assertIn("cannot tell them apart", entry["disagreement"])
        self.assertTrue(entry.get("not_machine_verified"))

    def test_the_removed_sunflower_is_gone_from_every_file(self):
        """Both names, because the two catalogues key on different ones."""
        self.dq.DATA_DIR = self._orig_dir
        for name in ("plants_master.json", "garden_plants.json",
                     "plant_fauna_master.json"):
            text = (self._orig_dir / name).read_text(encoding="utf-8")
            self.assertNotIn("Helianthus giganteus", text, name)
            self.assertNotIn("Giant Sunflower", text, name)

    def test_the_community_it_anchored_names_only_plants_it_contains(self):
        """A community whose prose names a plant its member list no longer has
        is the drift V2.74 went looking for, and it is invisible."""
        from src.db.polycultures import EXAMPLE_POLYCULTURES
        for poly in EXAMPLE_POLYCULTURES:
            for variation in poly.get("variations") or []:
                if variation["name"] != "Tall Prairie Meadow":
                    continue
                members = {m[0] for m in variation["members"]}
                self.assertIn("Maximilian Sunflower", members)
                self.assertIn("Nuttall's Sunflower", members)
                self.assertNotIn("Giant Sunflower", members)
                self.assertNotIn("Giant sunflower",
                                 variation["description"])
                self.assertIn("Maximilian sunflower",
                              variation["description"])
                return
        self.fail("Tall Prairie Meadow not found")

    def test_an_exclusion_without_an_authority_is_an_error(self):
        """An entry here removes a species from a public reference work. It has
        to say who says so."""
        self._write("excluded_taxa.json",
                    {"taxa": [{"scientific_name": "Fictitia exempla",
                               "reason": "because"}]})
        errors, _w = self.dq.validate_excluded_taxa()
        self.assertTrue(any("has no authority" in e for e in errors), errors)
        self.assertTrue(any("has no removed_in" in e for e in errors), errors)

    def test_the_gate_runs_it(self):
        """Wired into validate_all, not only reachable from its own test."""
        self.dq.DATA_DIR = self._orig_dir
        orig = self.dq.validate_excluded_taxa
        try:
            self.dq.validate_excluded_taxa = lambda: (["SENTINEL_EXCLUDED"], [])
            errors, _w = self.dq.validate_all()
        finally:
            self.dq.validate_excluded_taxa = orig
        self.assertIn("SENTINEL_EXCLUDED", errors)


class TestNativityGate(unittest.TestCase):
    """The claim the public catalogue leads with, which had no gate at all.

    An outside botanical review of grownativeplants.ca said many species listed
    as native to AB and SK are native to only one. They were right, and nothing
    in the repo could have told them apart: `native_provinces` is generated,
    plants carry no citation field, and no check compared the claim to anything.
    """

    def setUp(self):
        import src.data_quality as dq
        self.dq = dq
        self._orig_dir = dq.DATA_DIR
        self.tmp = Path(tempfile.mkdtemp())
        for name in ("plants_master.json", "garden_plants.json",
                     "plant_ecoregions.json"):
            (self.tmp / name).write_text(
                (self._orig_dir / name).read_text(encoding="utf-8"),
                encoding="utf-8")
        dq.DATA_DIR = self.tmp

    def tearDown(self):
        self.dq.DATA_DIR = self._orig_dir

    def _write(self, name, blob):
        (self.tmp / name).write_text(json.dumps(blob), encoding="utf-8")

    # ── consistency ────────────────────────────────────────────────────────
    def test_the_shipped_catalogue_has_no_unrecorded_contradiction(self):
        self.dq.DATA_DIR = self._orig_dir
        errors, _w = self.dq.validate_nativity_consistency()
        self.assertEqual(errors, [])

    def test_two_rows_with_one_common_name_may_not_disagree(self):
        records = json.loads((self.tmp / "plants_master.json").read_text())
        records.append({"scientific_name": "Fictitia exempla",
                        "common_name": "Invented Sage",
                        "native_to_alberta": 1, "native_provinces": "AB,SK"})
        records.append({"scientific_name": "Exempla fictitia",
                        "common_name": "Invented Sage",
                        "native_to_alberta": 0, "native_provinces": "SK"})
        self._write("plants_master.json", records)
        errors, _w = self.dq.validate_nativity_consistency()
        self.assertTrue(any("Invented Sage".lower() in e for e in errors),
                        errors)

    def test_two_rows_that_agree_are_fine(self):
        """A shared common name is not itself the defect. Two rows saying the
        same thing is a duplicate; two rows saying opposite things is a lie on
        one of two published pages."""
        records = json.loads((self.tmp / "plants_master.json").read_text())
        for sci in ("Fictitia exempla", "Exempla fictitia"):
            records.append({"scientific_name": sci,
                            "common_name": "Invented Sage",
                            "native_to_alberta": 1,
                            "native_provinces": "AB,SK"})
        self._write("plants_master.json", records)
        errors, _w = self.dq.validate_nativity_consistency()
        self.assertEqual(errors, [])

    def test_the_known_pair_is_a_warning_and_carries_its_reason(self):
        """Stiff Goldenrod ships twice and the rows disagree. Resolving it means
        choosing an accepted name, which waits on the taxonomic backbone — so it
        is recorded with the reason rather than silenced."""
        self.dq.DATA_DIR = self._orig_dir
        _e, warnings = self.dq.validate_nativity_consistency()
        hits = [w for w in warnings if "stiff goldenrod" in w]
        self.assertEqual(len(hits), 1, warnings)
        self.assertIn("Oligoneuron rigidum", hits[0])
        self.assertIn("F137", hits[0])

    def test_an_unlisted_pair_is_an_error_not_a_warning(self):
        """The allowlist buys silence for one named pair, not for the class."""
        self.assertIn("stiff goldenrod", self.dq.KNOWN_NATIVITY_CONFLICTS)

    # ── evidence ───────────────────────────────────────────────────────────
    def test_a_claim_with_no_occurrence_record_anywhere_is_named(self):
        records = json.loads((self.tmp / "plants_master.json").read_text())
        records.append({"scientific_name": "Fictitia exempla",
                        "common_name": "Invented Sage",
                        "native_to_alberta": 1, "native_provinces": "AB,SK"})
        self._write("plants_master.json", records)
        _e, warnings = self.dq.validate_nativity_evidence()
        self.assertTrue(any("Fictitia exempla" in w for w in warnings),
                        warnings)

    def test_it_is_a_warning_because_occurrence_is_not_nativity(self):
        """The check must never read as an occurrence gate. A species with 215
        records can still be introduced — that is exactly what V2.74 removed —
        so absence of records is a prompt to look, never a verdict."""
        records = json.loads((self.tmp / "plants_master.json").read_text())
        records.append({"scientific_name": "Fictitia exempla",
                        "common_name": "Invented Sage",
                        "native_to_alberta": 1})
        self._write("plants_master.json", records)
        errors, _w = self.dq.validate_nativity_evidence()
        self.assertEqual(errors, [])

    def test_a_row_claiming_nothing_is_not_flagged(self):
        records = json.loads((self.tmp / "plants_master.json").read_text())
        records.append({"scientific_name": "Fictitia exempla",
                        "common_name": "Invented Sage"})
        self._write("plants_master.json", records)
        _e, warnings = self.dq.validate_nativity_evidence()
        self.assertFalse(any("Fictitia exempla" in w for w in warnings),
                         warnings)

    # ── generator drift ────────────────────────────────────────────────────
    def test_the_shipped_generator_speaks_the_current_vocabulary(self):
        self.dq.DATA_DIR = self._orig_dir
        errors, _w = self.dq.validate_provenance_generator()
        self.assertEqual(errors, [])

    def test_a_drifted_key_is_an_error(self):
        """The fault this exists for: V2.72 replaced the ecoregion vocabulary
        and four of the generator's six keys stopped existing, so the field the
        website publishes was the output of a routine that would no longer
        produce it. 237 of 431 species would have moved on a re-run."""
        import src.data_quality as dq
        real = dq._load_ecoregion_keys
        try:
            dq._load_ecoregion_keys = lambda: {"aspen_parkland"}
            errors, _w = dq.validate_provenance_generator()
        finally:
            dq._load_ecoregion_keys = real
        self.assertTrue(errors)
        self.assertIn("no longer defines", errors[0])

    def test_not_finding_the_constant_fails_rather_than_passing(self):
        """A parser that quietly finds nothing is how the previous AST-based
        vocabulary loader failed. Not checking is reported as not checking."""
        import src.data_quality as dq
        script = self.tmp / "tag_prairie_provenance.py"
        script.write_text("SK_SHARED_RENAMED = {'aspen_parkland'}\n",
                          encoding="utf-8")
        real_root = dq.PROJECT_ROOT
        fake_root = self.tmp / "root"
        (fake_root / "scripts").mkdir(parents=True)
        (fake_root / "scripts" / "tag_prairie_provenance.py").write_text(
            "SK_SHARED_RENAMED = {'aspen_parkland'}\n", encoding="utf-8")
        try:
            dq.PROJECT_ROOT = fake_root
            errors, _w = dq.validate_provenance_generator()
        finally:
            dq.PROJECT_ROOT = real_root
        self.assertTrue(any("could not be checked" in e for e in errors),
                        errors)

    def test_the_generator_refuses_to_run(self):
        """A comment saying 'do not run this' does not stop anybody running it.
        Re-running it moves 237 of 431 species."""
        import subprocess
        proc = subprocess.run(
            [sys.executable, "scripts/tag_prairie_provenance.py"],
            cwd=str(Path(__file__).resolve().parent.parent),
            capture_output=True, text=True)
        self.assertEqual(proc.returncode, 2, proc.stdout + proc.stderr)
        self.assertIn("REFUSING TO RUN", proc.stderr)

    # ── wiring ─────────────────────────────────────────────────────────────
    def test_the_gate_runs_all_three(self):
        self.dq.DATA_DIR = self._orig_dir
        for name in ("validate_nativity_consistency",
                     "validate_nativity_evidence",
                     "validate_provenance_generator"):
            orig = getattr(self.dq, name)
            try:
                setattr(self.dq, name, lambda n=name: ([f"SENTINEL_{n}"], []))
                errors, _w = self.dq.validate_all()
            finally:
                setattr(self.dq, name, orig)
            self.assertIn(f"SENTINEL_{name}", errors)


class TestTheEcoregionVocabularyIsThreeLevels(unittest.TestCase):
    """The gate knew one level of a three-level vocabulary (V2.75).

    V2.68 put an ecozone above the ecoregion and an Alberta subregion below it;
    V2.73's migration then wrote `zone_prairies` onto 303 species. This
    validator, reading only the 24 bare ecoregion keys, called every one of them
    unknown — 303 of 430 warnings were the gate disagreeing with a migration the
    same release shipped, and the noise buried everything else in the file.
    """

    def test_ecozone_and_subregion_keys_are_accepted(self):
        import src.data_quality as dq
        keys = dq._load_ecoregion_keys()
        self.assertIn("zone_prairies", keys)
        self.assertIn("aspen_parkland", keys)
        self.assertTrue(any(k.startswith("sub_") for k in keys), sorted(keys)[:5])

    def test_the_shipped_catalogue_no_longer_trips_it(self):
        import src.data_quality as dq
        _e, warnings = dq.validate_all()
        stale = [w for w in warnings if "unknown ecoregion key" in w]
        self.assertEqual(stale, [])


if __name__ == "__main__":
    unittest.main()
