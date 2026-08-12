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
  * **the withheld role stays withheld** (P12).
"""

import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

_TMP_DIR = tempfile.mkdtemp(prefix="permadesign_facets_test_")

import src.db.plants as _plants_mod  # noqa: E402

_plants_mod._DATA_DIR = _TMP_DIR
_plants_mod._DB_PATH = os.path.join(_TMP_DIR, "permadesign_test.db")

from src.db.plants import init_db, search_plants            # noqa: E402
from src.site_facets import (                               # noqa: E402
    FACETS, FACETS_BY_KEY, GROUPS, HUB_FACETS, WITHHELD_ROLES, index_row,
)


class TestTheFacetsAgainstTheRealCatalogue(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        init_db()
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
        self.assertIn("Silence is not a clearance",
                      FACETS_BY_KEY["safety"].note)

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


class TestTheWithheldRole(unittest.TestCase):
    """P12. The desktop exposes a ``medicinal`` use tag; a public, indexed
    landing page listing medicinal native plants is the same act as publishing
    the traditional-use notes, which V2.47 decided against."""

    @classmethod
    def setUpClass(cls):
        init_db()
        cls.rows = search_plants()

    def test_medicinal_is_tagged_in_the_data(self):
        """The premise of the test below. If this fails the exclusion has
        become meaningless and the test is passing for the wrong reason."""
        tagged = [r for r in self.rows
                  if "medicinal" in (r.get("permaculture_uses") or "")]
        self.assertGreater(len(tagged), 0)

    def test_but_never_reaches_the_website_role_facet(self):
        facet = FACETS_BY_KEY["role"]
        self.assertNotIn("medicinal", dict(facet.options))
        for row in self.rows:
            self.assertNotIn("medicinal", facet.values(row))

    def test_the_exclusion_is_declared_rather_than_incidental(self):
        self.assertIn("medicinal", WITHHELD_ROLES)


if __name__ == "__main__":
    unittest.main()
