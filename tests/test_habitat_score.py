"""
tests/test_habitat_score.py

Characterization tests for src/habitat_score.py — the Qt-free habitat
scoring extracted out of AnalysisPanel in Chunk 6. These pin the maths
so the GUI panel and the headless scripting API can never drift.

Uses the temp-DB seed pattern from tests/test_polycultures.py: redirect
the DB to a tempdir and init_db() so real seeded plants back the score.
The pure-function tests (parse_month_range) need no DB at all.
"""

import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Redirect the DB to a temp dir BEFORE importing anything that opens it.
_TMP_DIR = tempfile.mkdtemp(prefix="permadesign_habitat_test_")
import src.db.plants as _plants_mod  # noqa: E402
_plants_mod._DATA_DIR = _TMP_DIR
_plants_mod._DB_PATH = os.path.join(_TMP_DIR, "permadesign_test.db")

from src.db.plants import init_db, get_connection, get_all_plants  # noqa: E402
from src.habitat_score import (  # noqa: E402
    compute_habitat_score,
    parse_month_range,
    HabitatScore,
    HabitatScoreError,
    CANONICAL_LAYERS,
    layer_for_plant,
    HABITAT_STRUCTURE_IDS,
)


class TestParseMonthRange(unittest.TestCase):
    """Pure parser — no DB."""

    def test_single_month(self):
        self.assertEqual(parse_month_range("May"), [5])
        self.assertEqual(parse_month_range("July"), [7])

    def test_simple_range(self):
        self.assertEqual(parse_month_range("June-August"), [6, 7, 8])

    def test_dash_variants(self):
        # en-dash and em-dash both normalise to a plain range.
        self.assertEqual(parse_month_range("Jun–Aug"), [6, 7, 8])
        self.assertEqual(parse_month_range("Jun—Aug"), [6, 7, 8])

    def test_year_wrap(self):
        # Nov-Feb wraps the year boundary.
        self.assertEqual(parse_month_range("Nov-Feb"), [11, 12, 1, 2])

    def test_empty(self):
        self.assertEqual(parse_month_range(""), [])
        self.assertEqual(parse_month_range(None), [])


class TestComputeHabitatScoreEmpty(unittest.TestCase):

    def test_nothing_placed_returns_none(self):
        self.assertIsNone(compute_habitat_score([], []))


class TestComputeHabitatScoreSeeded(unittest.TestCase):
    """Score real seeded plants so the component maths is exercised
    end-to-end against the shipped data."""

    @classmethod
    def setUpClass(cls):
        init_db()
        cls.plants = get_all_plants()
        # A handful of real plant_ids to place.
        cls.some_ids = [p["id"] for p in cls.plants[:8]]

    def test_returns_habitat_score_dataclass(self):
        placed = [{"plant_id": pid} for pid in self.some_ids]
        result = compute_habitat_score(placed, [])
        self.assertIsInstance(result, HabitatScore)
        self.assertGreaterEqual(result.total, 0)
        self.assertLessEqual(result.total, 100)

    def test_total_equals_sum_of_components(self):
        placed = [{"plant_id": pid} for pid in self.some_ids]
        r = compute_habitat_score(placed, [])
        component_sum = (r.score_native + r.score_keystone + r.score_host
                         + r.score_bird + r.score_layers + r.score_structs
                         + r.score_bloom)
        self.assertEqual(r.total, int(round(component_sum)))

    def test_species_dedup_but_total_counts_all(self):
        # Placing the same plant twice = 1 species, 2 total plants.
        pid = self.some_ids[0]
        r = compute_habitat_score(
            [{"plant_id": pid}, {"plant_id": pid}], []
        )
        self.assertEqual(r.n_species, 1)
        self.assertEqual(r.n_total_plants, 2)

    def test_native_ratio_bounds(self):
        placed = [{"plant_id": pid} for pid in self.some_ids]
        r = compute_habitat_score(placed, [])
        self.assertGreaterEqual(r.native_ratio, 0.0)
        self.assertLessEqual(r.native_ratio, 1.0)
        # score_native is exactly ratio * 20
        self.assertAlmostEqual(r.score_native, r.native_ratio * 20)

    def test_layers_are_canonical_only(self):
        placed = [{"plant_id": pid} for pid in self.some_ids]
        r = compute_habitat_score(placed, [])
        for layer in r.layers_present:
            self.assertIn(layer, CANONICAL_LAYERS)
        # 3 pts per layer, capped at 5 layers (15 pts).
        self.assertAlmostEqual(r.score_layers, min(len(r.layers_present), 5) * 3)

    def test_every_catalogue_plant_type_reaches_a_layer(self):
        """F124's guard. The map knew six of the catalogue's eleven types, so
        311 of 437 species — `wildflower` alone is 210 — counted as no
        vegetation layer at all, and a prairie meadow scored 0 of 15 on a
        component it plainly satisfies."""
        from src.db.plants import get_connection
        conn = get_connection()
        try:
            types = [r[0] for r in conn.execute(
                "SELECT DISTINCT plant_type FROM plants "
                "WHERE plant_type IS NOT NULL AND plant_type != ''")]
        finally:
            conn.close()
        self.assertGreater(len(types), 6, "seed the DB before asserting this")
        unmapped = [t for t in types if not layer_for_plant(t, 1.0)]
        self.assertEqual(unmapped, [], f"plant types with no layer: {unmapped}")

    def test_height_decides_the_layer_within_the_herbaceous_group(self):
        """`wildflower` spans 0.05 m to 3.00 m in this catalogue. Filing all
        210 under one layer would have taken the prairie meadow from 0 of 15 to
        3 of 15 and called it fixed."""
        self.assertEqual(layer_for_plant("wildflower", 0.05), "groundcover")
        self.assertEqual(layer_for_plant("wildflower", 1.50), "herbaceous")
        self.assertEqual(layer_for_plant("grass", 1.80), "herbaceous")
        self.assertEqual(layer_for_plant("grass", 0.10), "groundcover")

    def test_a_missing_height_keeps_the_type_answer(self):
        """Absent is not zero (P9) — an unrecorded height must not quietly
        file a species as groundcover."""
        self.assertEqual(layer_for_plant("wildflower", None), "herbaceous")
        self.assertEqual(layer_for_plant("wildflower", ""), "herbaceous")

    def test_height_does_not_refile_the_types_that_already_had_a_layer(self):
        """Eleven of the 56 shrubs are under a metre and a creeping juniper is
        arguably groundcover — but acting on that would LOWER scores, which is
        the opposite of the change that was approved. Left alone deliberately.
        """
        self.assertEqual(layer_for_plant("shrub", 0.30), "shrub")
        self.assertEqual(layer_for_plant("tree", 4.0), "overstory")
        self.assertEqual(layer_for_plant("groundcover", 0.60), "groundcover")

    def test_a_prairie_meadow_no_longer_scores_zero_on_layers(self):
        """The measurement that made F124 worth taking. Before: 0 of 15."""
        conn_ids = []
        from src.db.plants import get_connection
        conn = get_connection()
        try:
            for sql in (
                "SELECT id FROM plants WHERE plant_type IN "
                "('wildflower','grass','sedge') AND mature_height_meters >= 0.5"
                " LIMIT 10",
                "SELECT id FROM plants WHERE plant_type = 'wildflower' AND "
                "mature_height_meters < 0.3 LIMIT 2",
            ):
                conn_ids += [r[0] for r in conn.execute(sql)]
        finally:
            conn.close()
        self.assertGreaterEqual(len(conn_ids), 6)
        r = compute_habitat_score([{"plant_id": i} for i in conn_ids], [])
        self.assertEqual(sorted(r.layers_present),
                         ["groundcover", "herbaceous"])
        self.assertEqual(r.score_layers, 6)

    def test_structures_score(self):
        # Two recognised habitat structures + one bogus → 2 distinct types.
        placed = [{"plant_id": self.some_ids[0]}]
        structures = [
            {"id": "pond"},
            {"id": "bee_hotel"},
            {"id": "not_a_real_structure"},
        ]
        r = compute_habitat_score(placed, structures)
        self.assertEqual(set(r.habitat_struct_types), {"pond", "bee_hotel"})
        self.assertAlmostEqual(r.score_structs, 2 * 2)  # 2 pts per type

    def test_structure_id_fallbacks(self):
        # Structures matched by 'type' or slugified 'name', not just 'id'.
        placed = [{"plant_id": self.some_ids[0]}]
        r_type = compute_habitat_score(placed, [{"type": "swale"}])
        self.assertIn("swale", r_type.habitat_struct_types)
        r_name = compute_habitat_score(placed, [{"name": "Rain Garden"}])
        self.assertIn("rain_garden", r_name.habitat_struct_types)

    def test_structures_only_no_plants(self):
        # Structures alone still produce a score (not None).
        r = compute_habitat_score([], [{"id": "pond"}])
        self.assertIsInstance(r, HabitatScore)
        self.assertEqual(r.n_species, 0)
        self.assertAlmostEqual(r.score_structs, 2)

    def test_bloom_gap_months_within_growing_season(self):
        placed = [{"plant_id": pid} for pid in self.some_ids]
        r = compute_habitat_score(placed, [])
        for m in r.gap_months:
            self.assertIn(m, range(4, 11))
        # bloom + gap partition the 7 growing-season months.
        self.assertEqual(
            sorted(set(r.bloom_months) | set(r.gap_months)),
            list(range(4, 11)),
        )

    def test_as_dict_is_json_shaped(self):
        placed = [{"plant_id": pid} for pid in self.some_ids]
        d = compute_habitat_score(placed, []).as_dict()
        self.assertIn("total", d)
        self.assertIn("components", d)
        self.assertEqual(d["components"]["native"]["max"], 20)
        self.assertEqual(d["components"]["bloom"]["max"], 20)
        self.assertIn("lepidoptera_supported", d)
        # F3: food-web completeness is a top-level informational key, not a
        # scored component (no "max").
        self.assertIn("food_web", d)
        self.assertNotIn("food_web", d["components"])

    # ── F3: food-web completeness (informational, un-summed) ───────────

    def _pid(self, name):
        conn = get_connection()
        try:
            row = conn.execute(
                "SELECT id FROM plants WHERE common_name = ?", (name,)
            ).fetchone()
            return row["id"] if row else None
        finally:
            conn.close()

    def test_food_web_shape_and_consistency(self):
        placed = [{"plant_id": pid} for pid in self.some_ids]
        fw = compute_habitat_score(placed, []).food_web
        self.assertIsInstance(fw, dict)
        for k in ("caterpillars", "n_caterpillars", "birds", "n_birds",
                  "complete", "status"):
            self.assertIn(k, fw)
        # complete is exactly the conjunction of the two links…
        self.assertEqual(fw["complete"], fw["caterpillars"] and fw["birds"])
        # …and the status string agrees with the two booleans.
        expected = {(True, True): "complete", (True, False): "no_birds",
                    (False, True): "no_hosts", (False, False): "empty"}
        self.assertEqual(fw["status"],
                         expected[(fw["caterpillars"], fw["birds"])])

    def test_food_web_is_informational_not_summed(self):
        # The food-web signal must never move the headline (like the fauna
        # counts) — the total stays the sum of the seven scored components.
        placed = [{"plant_id": pid} for pid in self.some_ids]
        r = compute_habitat_score(placed, [])
        component_sum = (r.score_native + r.score_keystone + r.score_host
                         + r.score_bird + r.score_layers + r.score_structs
                         + r.score_bloom)
        self.assertEqual(r.total, int(round(component_sum)))

    def test_milkweed_only_food_web_broken_no_birds(self):
        # Milkweed hosts the Monarch caterpillar but nothing here feeds the
        # birds that would eat it → a broken chain.
        pid = self._pid("Showy Milkweed")
        self.assertIsNotNone(pid)
        fw = compute_habitat_score([{"plant_id": pid}], []).food_web
        self.assertTrue(fw["caterpillars"])
        self.assertFalse(fw["birds"])
        self.assertFalse(fw["complete"])
        self.assertEqual(fw["status"], "no_birds")

    def test_a_bird_at_the_flowers_does_not_close_the_chain(self):
        """The V2.59 guard, and the reason the test above still passes.

        F125's sourcing put a documented Ruby-throated Hummingbird nectar
        record on Showy Milkweed, and the food-web check counted *any* bird
        edge — so a milkweed-only design started reporting a complete food
        web. Milkweed is the worst case it could have picked: monarchs are the
        textbook caterpillar birds learn not to eat. Every line the status
        drives is about berries, seeds and nestling protein, so the count
        behind it excludes flower visits. The hummingbird is still reported;
        it is just not evidence of a food chain.
        """
        pid = self._pid("Showy Milkweed")
        fw = compute_habitat_score([{"plant_id": pid}], []).food_web
        self.assertGreater(fw["n_birds"], 0, "the nectar record is still there")
        self.assertEqual(fw["n_birds_forage"], 0)
        self.assertEqual(fw["birds_evidence"], "none")

    def test_a_bird_that_is_fed_does_close_the_chain(self):
        """The other half — the distinction must not simply refuse all birds."""
        pid = self._pid("Saskatoon Berry")
        self.assertIsNotNone(pid)
        fw = compute_habitat_score([{"plant_id": pid}], []).food_web
        self.assertGreater(fw["n_birds_forage"], 0)
        self.assertEqual(fw["birds_evidence"], "documented")

    def test_aspen_food_web_complete(self):
        # Aspen hosts many lepidoptera and supports birds → the chain closes.
        pid = self._pid("Trembling Aspen")
        self.assertIsNotNone(pid)
        fw = compute_habitat_score([{"plant_id": pid}], []).food_web
        self.assertTrue(fw["caterpillars"])
        self.assertTrue(fw["birds"])
        self.assertTrue(fw["complete"])
        self.assertEqual(fw["status"], "complete")

    def test_accepts_injected_connection(self):
        # Passing a connection avoids opening/closing one internally.
        conn = get_connection()
        try:
            placed = [{"plant_id": self.some_ids[0]}]
            r = compute_habitat_score(placed, [], connection=conn)
            self.assertIsInstance(r, HabitatScore)
            # Connection still usable afterward (not closed by the call).
            conn.execute("SELECT 1").fetchone()
        finally:
            conn.close()

    def test_scored_plant_ids_are_db_backed(self):
        # A bogus id contributes a placed plant but no DB row → excluded
        # from scored_plant_ids and species counts.
        placed = [{"plant_id": self.some_ids[0]}, {"plant_id": 10_000_000}]
        r = compute_habitat_score(placed, [])
        self.assertIn(self.some_ids[0], r.scored_plant_ids)
        self.assertNotIn(10_000_000, r.scored_plant_ids)
        self.assertEqual(r.n_species, 1)
        self.assertEqual(r.n_total_plants, 2)


class TestLayersScoredAgainstTheReference(unittest.TestCase):
    """F129, V2.65. `CANONICAL_LAYERS` is the permaculture *forest-garden*
    stack — overstory / shrub / herbaceous / groundcover / vine. A prairie
    genuinely occupies two or three of those, so even after F124 fixed the
    plant-type map, a correct and complete grassland planting was capped at
    6 of 15 while a woodland-edge design reached 15. The component measured
    how woodland-like a design was and reported it as habitat value, in an
    app for prairie conversion.

    Now the denominator is the layers the *reference community* actually has.
    """

    @classmethod
    def setUpClass(cls):
        init_db()
        conn = get_connection()
        def ids(names):
            out = []
            for n in names:
                row = conn.execute(
                    "SELECT id FROM plants WHERE common_name=?", (n,)).fetchone()
                if row:
                    out.append({"plant_id": row[0]})
            return out
        cls.grassland = ids(["Big Bluestem", "Blue Grama Grass",
                             "Prairie Crocus", "Common Yarrow",
                             "Wild Bergamot", "Black-eyed Susan",
                             "Purple Prairie Clover", "Canada Goldenrod",
                             "Smooth Aster", "Prairie Sage"])
        conn.close()

    def test_without_an_ecoregion_nothing_changes(self):
        """Twelve callers pass no ecoregion and none of their scores may move.
        The universal stack stays the default, and says so."""
        r = compute_habitat_score(self.grassland, [])
        self.assertEqual(r.layer_basis, "")
        self.assertEqual(r.layer_detail, {})
        self.assertEqual(r.score_layers,
                         min(len(r.layers_present), 5) * 3)

    def test_a_grassland_scores_higher_against_a_grassland(self):
        """The fix, in one assertion. Mixedgrass Prairie declares no canopy
        genera at all, so a treeless design is no longer marked down for a
        layer its reference does not have either."""
        universal = compute_habitat_score(self.grassland, [])
        prairie = compute_habitat_score(self.grassland, [],
                                        ecoregion="mixedgrass_prairie")
        self.assertGreater(prairie.score_layers, universal.score_layers)
        self.assertEqual(prairie.layer_basis, "Mixedgrass Prairie")

    def test_the_same_grassland_scores_lower_against_a_woodland(self):
        """**The change is honest, not generous.** A grassland planted in
        Aspen Parkland really is missing the canopy and the shrub ring that
        belong there, and re-basing has to be able to say so — otherwise it is
        not a measurement, it is a compliment."""
        universal = compute_habitat_score(self.grassland, [])
        parkland = compute_habitat_score(self.grassland, [],
                                         ecoregion="aspen_parkland")
        self.assertLess(parkland.score_layers, universal.score_layers)

    def test_the_component_never_exceeds_its_maximum(self):
        for eco in (None, "mixedgrass_prairie", "aspen_parkland",
                    "boreal_mixedwood", "wet_meadow"):
            r = compute_habitat_score(self.grassland, [], ecoregion=eco)
            self.assertGreaterEqual(r.score_layers, 0.0, eco)
            self.assertLessEqual(r.score_layers, 15.0, eco)
            self.assertEqual(r.total, int(round(
                r.score_native + r.score_keystone + r.score_host + r.score_bird
                + r.score_layers + r.score_structs + r.score_bloom)), eco)

    def test_no_ecoregion_is_the_case_that_falls_back(self):
        """No reference resolved is a catalogue gap, not a design failure, and
        scoring 0 would report the one as the other (P9). `None` is that case:
        no pin, or a lookup that found nothing."""
        r = compute_habitat_score(self.grassland, [], ecoregion=None)
        self.assertEqual(r.layer_basis, "")
        self.assertEqual(r.score_layers,
                         compute_habitat_score(self.grassland, []).score_layers)

    def test_an_unknown_key_inherits_the_resolver_default_and_names_it(self):
        """An unrecognised *string* is not the same as no ecoregion.
        `reference_ecosystem.reference_community` has always fallen back to a
        default community for an unknown key, and the fidelity band one row up
        in the same panel already scores against it. Re-deriving that decision
        here would make the two disagree about one design — so this inherits
        it, and the reported basis names whatever it actually compared
        against, which is the part that keeps it honest."""
        r = compute_habitat_score(self.grassland, [], ecoregion="atlantis")
        from src.reference_ecosystem import reference_community
        self.assertEqual(r.layer_basis, reference_community("atlantis")["name"])

    def test_the_basis_travels_into_the_api_dict(self):
        """A number whose denominator changed has to carry its denominator, or
        a reader cannot tell 15/15 from a bug."""
        d = compute_habitat_score(
            self.grassland, [], ecoregion="mixedgrass_prairie").as_dict()
        layers = d["components"]["layers"]
        self.assertEqual(layers["basis"], "Mixedgrass Prairie")
        self.assertTrue(layers["detail"])
        for entry in layers["detail"].values():
            self.assertIn("have", entry)
            self.assertIn("want", entry)
            self.assertIn("present", entry)

    def test_it_reuses_the_fidelity_layer_judgement_rather_than_copying_it(self):
        """The presence fraction and the half credit for 'thin' live in
        `reference_fidelity`, one row above this in the same panel. A second
        copy would drift, and the two would disagree about one design."""
        import inspect

        from src import habitat_score as hs
        src = inspect.getsource(hs._reference_layer_score)
        self.assertIn("from src.reference_fidelity import fidelity", src)
        self.assertNotIn("PRESENCE_FRACTION", src)


if __name__ == "__main__":
    unittest.main()
