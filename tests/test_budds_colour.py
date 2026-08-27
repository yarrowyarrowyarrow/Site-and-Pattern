"""Reading flower colour out of a flora's prose (V2.80).

The catalogue's 350 guessed colours needed a source. USDA PLANTS was tried
first because a structured export is cheaper than parsing English, and the
author checked it at the binomial:

    "They say yarrow is yellow, the giant hyssop is red"

Both are wrong, so the first thing this module has to do is get those two
right from a flora's own sentences.
"""

import unittest

from src.budds_colour import (
    DESCRIPTIVE_STARTS, Finding, blocks, colour_in, normalise, peek, read,
)

#: Written in the register a regional flora actually uses -- authority after
#: the binomial, common name in caps, description in terse sentence fragments,
#: and one word broken across a line by the scan.
FLORA = """Achillea millefolium L.  YARROW
Perennial herb 20-60 cm high from creeping rhizomes. Leaves finely dissected,
fern-like, aromatic. Flowers white, rarely pinkish, in dense flat-topped
corymbs. Dry prairie and roadsides, common throughout.

Agastache foeniculum (Pursh) Kuntze  GIANT HYSSOP
Erect perennial 50-100 cm. Leaves ovate, anise-scented, whitish beneath.
Flowers blue to violet, crowded in a dense terminal spike. Moist woodland.

Opuntia polyacantha Haw.  PLAINS PRICKLY PEAR
Low spreading cactus with flattened joints. Flowers yel-
low, sometimes with a reddish centre, 5-7 cm across. Fruit dry and spiny.

Cornus sericea L.  RED OSIER DOGWOOD
Shrub to 3 m. Stems bright red in winter. Leaves opposite, green above.
Flowers white in flat cymes. Fruit a white berry.

Solidago rigida L.  STIFF GOLDENROD
Stout perennial. Leaves thick, rough, greyish. Heads yellow, in a dense flat
cluster. Dry prairie.
"""

NAMES = ["Achillea millefolium", "Agastache foeniculum", "Opuntia polyacantha",
         "Cornus sericea", "Solidago rigida"]


def _by_name(text=FLORA, names=NAMES):
    return {f.scientific_name: f for f in read(text, names)}


class TestTheTwoUsdaGotWrong(unittest.TestCase):
    """The species that decided against USDA. If a flora cannot get these
    right there is no reason to prefer it."""

    def test_yarrow_is_white_not_yellow(self):
        f = _by_name()["Achillea millefolium"]
        self.assertEqual(f.buckets[0], "white")
        self.assertNotIn("yellow", f.buckets)

    def test_giant_hyssop_is_blue_not_red(self):
        f = _by_name()["Agastache foeniculum"]
        self.assertEqual(f.buckets[0], "blue")
        self.assertNotIn("red", f.buckets)


class TestWhatTheScanDoesToWords(unittest.TestCase):
    def test_a_word_split_across_a_line_break_is_rejoined(self):
        """`yel-\\nlow` is not a word, and the colour is lost without this."""
        self.assertIn("yellow", normalise("Flowers yel-\nlow, 5 cm."))
        self.assertEqual(_by_name()["Opuntia polyacantha"].buckets[0], "yellow")

    def test_line_structure_survives_normalising(self):
        """Newlines are the heading signal and must not be collapsed.

        The first version turned every newline into a space, so the block
        finder had nothing to bound a species with and truncated all five
        descriptions at their first sentence -- silently, returning nothing.
        """
        self.assertIn("\n", normalise(FLORA))


class TestABlockIsOneSpecies(unittest.TestCase):
    def test_a_sentence_starting_like_a_genus_does_not_end_the_block(self):
        """"Leaves finely dissected" is Genus-then-epithet shaped. Reading it
        as the next species cut yarrow's block before its flower sentence."""
        block = blocks(FLORA, ["Achillea millefolium"])["Achillea millefolium"]
        self.assertIn("Flowers white", block)
        self.assertNotIn("Agastache", block)

    def test_the_stopword_list_covers_the_obvious_openers(self):
        for word in ("leaves", "flowers", "stems", "fruit", "perennial"):
            self.assertIn(word, DESCRIPTIVE_STARTS)

    def test_a_species_the_book_does_not_carry_yields_nothing(self):
        self.assertEqual(read(FLORA, ["Zzzzia nonexistens"]), [])


class TestOnlyTheBloomCounts(unittest.TestCase):
    def test_a_red_stem_is_not_a_red_flower(self):
        """Red osier dogwood is named for its winter stems and has white
        flowers. A parser that takes the first colour word gets this backwards.
        """
        f = _by_name()["Cornus sericea"]
        self.assertEqual(f.buckets, ("white",))

    def test_a_head_counts_as_a_flower(self):
        """A composite's bloom is a head, and a flora says so rather than
        saying flower."""
        self.assertEqual(_by_name()["Solidago rigida"].buckets, ("yellow",))

    def test_a_sentence_with_no_flower_word_is_ignored(self):
        self.assertEqual(colour_in("Leaves green above, purple beneath."),
                         ((), ""))


class TestConfidenceIsNotAGuess(unittest.TestCase):
    def test_one_colour_and_a_clean_sentence_is_confident(self):
        self.assertTrue(_by_name()["Solidago rigida"].confident)

    def test_two_colours_are_not_confident(self):
        """"white, rarely pinkish" is real variation. The catalogue stores one
        hex, so a person picks -- the parser must not."""
        f = _by_name()["Achillea millefolium"]
        self.assertEqual(len(f.buckets), 2)
        self.assertFalse(f.confident)

    def test_every_finding_carries_the_sentence_it_came_from(self):
        """The quote is the whole point: it makes a line checkable by reading
        rather than by looking the species up."""
        for f in read(FLORA, NAMES):
            self.assertTrue(f.quote.strip())
            self.assertIsInstance(f, Finding)


class TestLookBeforeParsing(unittest.TestCase):
    """The --columns lesson, applied to the next source along."""

    def test_peek_warns_when_there_is_almost_no_text(self):
        """An image-only PDF extracts to nearly nothing, and that has to be
        visible as a warning rather than as an empty result an hour later."""
        self.assertIn("OCR", peek("Flowers yellow."))

    def test_peek_counts_what_matters(self):
        out = peek(FLORA)
        self.assertIn("colour words", out)
        self.assertIn("binomial", out)


if __name__ == "__main__":
    unittest.main()
