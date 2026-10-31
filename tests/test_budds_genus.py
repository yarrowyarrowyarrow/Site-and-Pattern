"""Inheriting a flower colour from the genus a flora states it at (V2.80).

Budd's describes 140 of this catalogue's species without naming a colour for
them, because a flora states it once at the genus and notes only departures.
The author's condition on doing this:

    "I'm okay with reading the genus if the genus colour is stated and species
     is only stated for departures. This would hold for goldenrods (solidago)
     but I'm unsure about others. Perhaps a list of those that need checking
     would be worth while"

So the list has to be measured from the book rather than judged by anyone.
"""

import unittest

from src.budds_colour import read
from src.budds_genus import genus_blocks, genus_of, inherit, needs_checking, uniformity

#: One uniform genus and one that is not, written the way the real scan is:
#: family heading in capitals, genus heading as name + English common name on
#: its own line, species headings carrying an authority.
FLORA = """COMPOSITAE - composite family
Solidago goldenrod
Heads small and numerous, the rays yellow, in a branched inflorescence.

Solidago rigida L. stiff goldenrod
An erect stout-stemmed species with a densely fine-hairy rough stem.

Solidago canadensis L. Canada goldenrod
Tall, with small yellow flowers in a spreading panicle.

VIOLACEAE - violet family
Viola violet
Perennial herbs with basal leaves. Flowers blue, nodding on slender stalks.

Viola adunca J. E. Smith early blue violet
A low plant with slender stems. Flowers blue, 10-15 mm across.

Viola nuttallii Pursh yellow violet
Leaves lance-shaped. Flowers yellow, the lower petals purple-veined.

Viola canadensis L. western Canada violet
A tall plant of moist woods, with heart-shaped leaves.
"""

WANT = ["Solidago rigida", "Solidago canadensis",
        "Viola adunca", "Viola nuttallii", "Viola canadensis"]


def _inherited():
    found = read(FLORA, WANT)
    return {f.scientific_name: f for f in inherit(FLORA, WANT, {}, found)}


class TestTheGenusIsFoundAtAll(unittest.TestCase):
    def test_a_genus_heading_is_name_plus_common_name(self):
        blocks = genus_blocks(FLORA, ["Solidago", "Viola"])
        self.assertIn("Solidago", blocks)
        self.assertIn("rays yellow", blocks["Solidago"])

    def test_the_genus_block_stops_at_its_first_species(self):
        """Otherwise it swallows the species and reads their colours as the
        genus's."""
        self.assertNotIn("stiff goldenrod",
                         genus_blocks(FLORA, ["Solidago"])["Solidago"])

    def test_a_candidate_with_no_colour_under_it_is_refused(self):
        """A two-token line is also a species heading stripped of its
        authority, and the book's identification key pairs species names with
        colours on single lines throughout the front matter. So a candidate
        only counts if a real description follows it."""
        self.assertEqual(genus_blocks("Zzzzia thing\nA plant of dry soil.\n",
                                      ["Zzzzia"]), {})

    def test_genus_of_a_binomial(self):
        self.assertEqual(genus_of("Solidago rigida L."), "Solidago")
        self.assertEqual(genus_of(""), "")


class TestUniformityIsMeasuredNotJudged(unittest.TestCase):
    """The author was sure about goldenrods and unsure about everything else.
    Neither of us should be deciding it; the book already has."""

    def test_a_genus_whose_species_agree_is_uniform(self):
        self.assertEqual(uniformity(read(FLORA, WANT))["Solidago"], "uniform")

    def test_a_genus_whose_species_disagree_is_variable(self):
        """Blue violets and yellow violets sit in the same genus. Handing every
        unstated Viola the genus colour would fabricate."""
        self.assertEqual(uniformity(read(FLORA, WANT))["Viola"], "variable")


class TestWhatGetsInherited(unittest.TestCase):
    def test_a_species_with_no_colour_of_its_own_inherits(self):
        f = _inherited()["Solidago rigida"]
        self.assertEqual(f.buckets, ("yellow",))
        self.assertEqual(f.found_as, "genus (uniform)")

    def test_a_species_that_states_its_own_colour_is_left_alone(self):
        """Inheritance is only for the gap. A species with its own sentence
        must not be overwritten by its genus."""
        self.assertNotIn("Viola adunca", _inherited())
        self.assertNotIn("Solidago canadensis", _inherited())

    def test_an_inheritance_from_a_variable_genus_is_marked(self):
        self.assertEqual(_inherited()["Viola canadensis"].found_as,
                         "genus (variable)")

    def test_no_inheritance_is_ever_confident(self):
        """Even a uniform genus is a colour the book states about the genus
        rather than about this plant."""
        for f in _inherited().values():
            self.assertFalse(f.confident)

    def test_the_quote_names_the_genus_it_came_from(self):
        """A row whose evidence is a sentence about a different taxon has to
        say so, or the review sheet reads as a species-level reading."""
        self.assertTrue(_inherited()["Solidago rigida"].quote
                        .startswith("[Solidago]"))


class TestTheListOfThoseNeedingChecking(unittest.TestCase):
    """What the author actually asked for."""

    def test_variable_genera_sort_first(self):
        order = [f.scientific_name for f in needs_checking(
            list(_inherited().values()))]
        self.assertEqual(order[0], "Viola canadensis")

    def test_a_uniform_inheritance_sorts_last(self):
        order = [f.found_as for f in needs_checking(list(_inherited().values()))]
        self.assertEqual(order[-1], "genus (uniform)")


class TestTheProvenanceIsItsOwn(unittest.TestCase):
    def test_flora_genus_is_a_mark_the_vocabulary_knows(self):
        """'budds' was not, and would have printed 'not recorded' on every page
        whose colour had just been sourced."""
        from src.confidence import mark
        m = mark("flora_genus")
        self.assertTrue(m.recorded)
        self.assertIn("genus", m.label)

    def test_it_is_not_filed_as_inferred(self):
        """The book asserts it; we did not compute it. That is the whole
        distinction from 'estimated', this project's own genus default."""
        from src.confidence import mark
        self.assertFalse(mark("flora_genus").inferred)
        self.assertTrue(mark("estimated").inferred)

    def test_it_is_distinguishable_from_a_species_level_reading(self):
        from src.confidence import mark
        self.assertNotEqual(mark("flora_genus").label, mark("flora").label)



class TestTheUniformityTestNeedsTheWholeCatalogue(unittest.TestCase):
    """The bug that made this feature useless on its first real run.

    Uniformity was measured over the species still NEEDING a colour. But the
    species that state their own had been applied in an earlier pass and had
    left that list -- so there was nothing to measure against, and all 23
    inheritances came back "untested" when *Solidago* alone should have been
    uniform.

    A test with an empty sample does not fail loudly. It just stops testing,
    and reports a confident-sounding "untested" for everything.
    """

    def test_a_genus_is_judged_on_species_that_are_not_in_wanted(self):
        """Solidago canadensis states yellow. It is deliberately absent from
        `wanted` here, standing for a species sourced in an earlier pass -- and
        the genus must still be measured on it."""
        needing = ["Solidago rigida"]
        whole = read(FLORA, WANT)          # the catalogue, sourced or not
        got = inherit(FLORA, needing, {}, read(FLORA, needing),
                      measured_from=whole)
        self.assertEqual(len(got), 1)
        self.assertEqual(got[0].found_as, "genus (uniform)")

    def test_without_the_whole_catalogue_it_reads_untested(self):
        """The failing behaviour, pinned so nobody restores it by simplifying
        the signature back to one set."""
        needing = ["Solidago rigida"]
        got = inherit(FLORA, needing, {}, read(FLORA, needing))
        self.assertEqual(got[0].found_as, "genus (untested)")

    def test_a_variable_genus_is_still_caught_across_the_whole_catalogue(self):
        needing = ["Viola canadensis"]
        whole = read(FLORA, WANT)
        got = inherit(FLORA, needing, {}, read(FLORA, needing),
                      measured_from=whole)
        self.assertEqual(got[0].found_as, "genus (variable)")

if __name__ == "__main__":
    unittest.main()
