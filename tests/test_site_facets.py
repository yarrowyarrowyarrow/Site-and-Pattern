"""
tests/test_site_facets.py — the website's searchable axes (V2.48).

Reported: *"there is a lot of data that is not being included in a searchable
way ... searching by ecoregion, whether it flowers, sun/water, etc."* There was:
the catalogue holds 68 columns per species and the first cut of the site let you
filter on four.

What these hold down:

  * **every value in the catalogue has a label.** A facet option list that has
    drifted from the data renders a blank checkbox that filters to nothing,
    which is the V2.37 dead-control bug wearing a different hat;
  * **every facet actually divides the catalogue.** A derivation that silently
    returns nothing looks exactly like "no plant has that";
  * **absence is not a value.** A plant that records nothing for an axis is left
    out of it rather than defaulted into one (P9);
  * **the withholding mechanism still works** (P12).
"""

import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

_TMP_DIR = tempfile.mkdtemp(prefix="permadesign_facets_test_")
_DB_PATH = os.path.join(_TMP_DIR, "permadesign_test.db")

import src.db.plants as _plants_mod  # noqa: E402

_plants_mod._DATA_DIR = _TMP_DIR
_plants_mod._DB_PATH = _DB_PATH

from src.db.plants import init_db, search_plants            # noqa: E402


def _use_our_db() -> None:
    """Re-point the DB globals at run time, not just at import time.

    Every test module in the suite patches ``_plants_mod._DB_PATH`` when it is
    imported, and the last import wins. Whichever module is imported after this
    one therefore owns the path by the time these tests run, so a test that
    asserts an exact set of rows reads somebody else's fixture: this module
    failed in the full suite with ``PlantA``, ``PlantB`` and
    ``Filterable Region Plant`` in a set that should have held five apple and
    cherry cultivars, while passing on its own.

    ``tests/test_cli.py`` hit this first and documented the fix; this is the
    same one.
    """
    _plants_mod._DATA_DIR = _TMP_DIR
    _plants_mod._DB_PATH = _DB_PATH
    init_db()
from src.site_facets import (                               # noqa: E402
    FACETS, FACETS_BY_KEY, GROUPS, HUB_FACETS, WITHHELD_ROLES, index_row,
)
from src.static_site import is_publishable                  # noqa: E402


class TestTheFacetsAgainstTheRealCatalogue(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        _use_our_db()
        cls.rows = search_plants()

    def test_every_value_in_use_has_a_label(self):
        """The failure this catches is silent: an unlabelled value renders an
        empty checkbox that matches real plants nobody can find."""
        unlabelled = {}
        for facet in FACETS:
            labels = dict(facet.options)
            used = {v for row in self.rows for v in facet.values(row)}
            missing = sorted(used - set(labels))
            if missing:
                unlabelled[facet.key] = missing
        self.assertEqual(unlabelled, {})

    def test_every_facet_divides_the_catalogue(self):
        """A derivation that returns nothing for every plant is a broken facet
        that looks like an empty one."""
        dead = [f.key for f in FACETS
                if not any(f.values(row) for row in self.rows)]
        self.assertEqual(dead, [])

    def test_a_facet_with_one_value_everywhere_would_be_useless(self):
        """Not an error, but worth knowing: a filter every plant passes filters
        nothing. None exists today."""
        useless = []
        for facet in FACETS:
            used = {tuple(sorted(facet.values(row))) for row in self.rows}
            if len(used) == 1 and used != {()}:
                useless.append(facet.key)
        self.assertEqual(useless, [])

    def test_absence_is_never_defaulted_into_a_value(self):
        """44 species record no flower colour and 148 no fruit window. They
        must appear under no value in those facets, not under a fallback."""
        blank = [r for r in self.rows
                 if not (r.get("flower_color") or "").strip()]
        self.assertGreater(len(blank), 0)
        for row in blank:
            self.assertEqual(FACETS_BY_KEY["colour"].values(row), [])

    def test_the_zone_facet_covers_the_whole_recorded_range(self):
        """Filtering by zone means "will it survive here", so a plant rated 2
        to 7 has to match a search for 4."""
        row = {"hardiness_zone_min": 2, "hardiness_zone_max": 7}
        self.assertEqual(FACETS_BY_KEY["zone"].values(row),
                         ["2", "3", "4", "5", "6", "7"])

    def test_a_hedged_zone_still_parses(self):
        """One row ships '4?'. It used to crash the species page; it must not
        quietly drop out of the zone filter either."""
        row = {"hardiness_zone_min": "4?", "hardiness_zone_max": 8}
        self.assertEqual(FACETS_BY_KEY["zone"].values(row),
                         ["4", "5", "6", "7", "8"])

    def test_showy_flower_is_a_fact_not_a_gap(self):
        sedge = {"flower_form": "none", "flower_color": ""}
        forb = {"flower_form": "daisy", "flower_color": "#f2c11e"}
        unknown = {"flower_form": "", "flower_color": ""}
        self.assertEqual(FACETS_BY_KEY["flowers"].values(sedge), ["not-showy"])
        self.assertEqual(FACETS_BY_KEY["flowers"].values(forb), ["showy"])
        self.assertEqual(FACETS_BY_KEY["flowers"].values(unknown), [])

    def test_safety_is_a_denylist(self):
        """"Pet safe" means no KNOWN toxicity. An unassessed species passes,
        and the facet's own note says so."""
        unassessed = {"toxicity_pets": "", "toxicity_humans": "", "has_thorns": 0}
        toxic = {"toxicity_pets": "high", "toxicity_humans": "", "has_thorns": 0}
        self.assertIn("pet-safe", FACETS_BY_KEY["safety"].values(unassessed))
        self.assertNotIn("pet-safe", FACETS_BY_KEY["safety"].values(toxic))
        self.assertIn("silence is not a clearance",
                      FACETS_BY_KEY["safety"].note.lower())

    def test_the_ecoregion_facet_is_searchable(self):
        """The headline ask. Every geographic region must select plants."""
        facet = FACETS_BY_KEY["ecoregion"]
        for value, _label in facet.options:
            matched = [r for r in self.rows if value in facet.values(r)]
            self.assertGreater(len(matched), 0, value)

    def test_index_row_covers_every_facet(self):
        row = index_row(self.rows[0])
        self.assertEqual(set(row), {f.key for f in FACETS})

    def test_every_facet_sits_in_a_rendered_group(self):
        for facet in FACETS:
            self.assertIn(facet.group, GROUPS, facet.key)

    def test_hub_facets_declare_a_directory(self):
        for facet in HUB_FACETS:
            self.assertTrue(facet.hub_dir, facet.key)
            self.assertNotIn(" ", facet.hub_dir)


class TestTheReportedFilterBugs(unittest.TestCase):
    """Four things the author found by using the filters (V2.49)."""

    @classmethod
    def setUpClass(cls):
        _use_our_db()
        cls.rows = [r for r in search_plants() if is_publishable(r)]

    def _count(self, key, values):
        facet = FACETS_BY_KEY[key]
        want = set(values)
        n = 0
        for row in self.rows:
            have = set(facet.values(row))
            hit = (want <= have) if facet.combine == "all" else bool(want & have)
            n += 1 if hit else 0
        return n

    def test_adding_a_safety_filter_never_widens_the_result(self):
        """The report: pet-safe gave 388 and adding human-safe gave **404**.
        Two safety claims were being unioned, and somebody ticking both wants a
        plant that is safe around the dog *and* the kids."""
        self.assertEqual(FACETS_BY_KEY["safety"].combine, "all")
        pets = self._count("safety", ["pet-safe"])
        both = self._count("safety", ["pet-safe", "child-safe"])
        all_three = self._count("safety", ["pet-safe", "child-safe", "thornless"])
        self.assertLessEqual(both, pets)
        self.assertLess(all_three, both)

    def test_roles_narrow_too_and_match_the_desktop(self):
        """``search_plants`` has ANDed use tags since V1.85; the website
        ORed them, so the two surfaces disagreed about the same question."""
        self.assertEqual(FACETS_BY_KEY["role"].combine, "all")
        one = self._count("role", ["keystone_species"])
        two = self._count("role", ["keystone_species", "host_plant"])
        self.assertLess(two, one)

    def test_a_wind_pollinated_plant_is_never_showy(self):
        """The report: *"showy flower seems incorrect as it includes sedges."*
        81 graminoids carry a hex and a plume, which the first cut read as a
        showy flower."""
        facet = FACETS_BY_KEY["flowers"]
        wrong = [r["common_name"] for r in self.rows
                 if r.get("plant_type") in ("grass", "sedge", "rush")
                 and "showy" in facet.values(r)]
        self.assertEqual(wrong, [])

    def test_the_photograph_gap_is_searchable(self):
        """Requested as a worklist: which species still need a photograph."""
        facet = FACETS_BY_KEY["photo"]
        self.assertEqual({v for v, _ in facet.options}, {"photo", "no-photo"})
        have = self._count("photo", ["photo"])
        missing = self._count("photo", ["no-photo"])
        self.assertGreater(missing, 0)
        self.assertEqual(have + missing, len(self.rows))

    def test_the_photograph_filter_comes_first(self):
        self.assertEqual(FACETS[0].key, "photo")

    def test_a_native_is_always_available_from_a_native_nursery(self):
        """*"Any natives should also be listed in native nursery as even if
        they are sold at the bigger stores this does not mean the local nursery
        would not have it."*"""
        facet = FACETS_BY_KEY["availability"]
        missing = [r["common_name"] for r in self.rows
                   if "native_specialist" not in facet.values(r)]
        self.assertEqual(missing, [])

    def test_but_the_other_tiers_still_discriminate(self):
        """Widening native_specialist must not flatten the axis: asking for
        big-box still has to return the big-box list."""
        big = self._count("availability", ["big_box"])
        self.assertGreater(big, 0)
        self.assertLess(big, len(self.rows))

    def test_the_shape_facets_are_gone(self):
        """Removed on request. Asserted so a later tidy-up does not restore
        them from an old branch without a reason."""
        keys = {f.key for f in FACETS}
        self.assertNotIn("leaf", keys)
        self.assertNotIn("flowerform", keys)


class TestOnlyNativesArePublished(unittest.TestCase):
    """*"I don't want any non-natives, i see the garden plants were included,
    cherries and apples, etc. so remove those."*"""

    @classmethod
    def setUpClass(cls):
        _use_our_db()
        cls.rows = search_plants()

    def test_the_garden_cultivars_are_dropped(self):
        dropped = {r["common_name"] for r in self.rows if not is_publishable(r)}
        self.assertEqual(dropped, {"Goodland Apple", "Norland Apple",
                                   "Evans Cherry", "Nanking Cherry",
                                   "Bee Balm (Wild Bergamot)"})

    def test_a_non_alberta_prairie_native_is_kept(self):
        """Stiff Goldenrod is flagged non-Alberta and is a genuine
        Saskatchewan and Manitoba native. Filtering on the flag instead of on
        the garden file would have thrown it out."""
        rows = [r for r in self.rows
                if r.get("scientific_name") == "Oligoneuron rigidum"]
        self.assertTrue(rows)
        for row in rows:
            self.assertFalse(row.get("native_to_alberta"))
            self.assertEqual(row.get("native_provinces"), "SK,MB")
            self.assertTrue(is_publishable(row))

    def test_the_duplicate_bergamot_goes_but_the_native_one_stays(self):
        """Both rows are Monarda fistulosa and both are flagged native; only
        one came from the garden file."""
        kept = {r["common_name"] for r in self.rows
                if r.get("scientific_name") == "Monarda fistulosa"
                and is_publishable(r)}
        self.assertEqual(kept, {"Wild Bergamot"})


class TestTheWithholdingMechanismStillWorks(unittest.TestCase):
    """P12, and a decision reversed.

    V2.48 kept the ``medicinal`` use tag off the public site, reasoning that a
    public, indexed "medicinal native plants" page is the same act as publishing
    the traditional-use notes. **The author has since ruled otherwise**: the tag
    is a generic horticultural category rather than sourced traditional
    knowledge, and it is published from V2.50.

    The mechanism stays and is tested against a temporary value, because the
    distinction it draws is still the right one, the next tag may not be so
    easy, and an empty tuple proves nothing about whether the filter works.
    What has *not* changed is the free-text ``notes`` column, which remains
    withheld: a use category is not the same artefact as a paragraph describing
    how a plant was prepared and for what.
    """

    @classmethod
    def setUpClass(cls):
        _use_our_db()
        cls.rows = search_plants()

    def test_medicinal_is_published_now(self):
        facet = FACETS_BY_KEY["role"]
        self.assertIn("medicinal", dict(facet.options))
        tagged = [r for r in self.rows if "medicinal" in facet.values(r)]
        self.assertGreater(len(tagged), 0)

    def test_nothing_is_withheld_today_and_that_is_deliberate(self):
        self.assertEqual(WITHHELD_ROLES, ())

    def test_the_mechanism_still_filters_when_asked_to(self):
        import src.site_facets as sf
        real = sf.WITHHELD_ROLES
        sf.WITHHELD_ROLES = ("pollinator",)
        try:
            values = FACETS_BY_KEY["role"].values(
                {"permaculture_uses": "pollinator,bird_food"})
        finally:
            sf.WITHHELD_ROLES = real
        self.assertEqual(values, ["bird_food"])


if __name__ == "__main__":
    unittest.main()
