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
        block, how = blocks(FLORA, ["Achillea millefolium"])["Achillea millefolium"]
        self.assertIn("Flowers white", block)
        self.assertNotIn("Agastache", block)
        self.assertEqual(how, "name")

    def test_the_stopword_list_covers_the_obvious_openers(self):
        for word in ("leaves", "flowers", "stems", "fruit", "perennial"):
            self.assertIn(word, DESCRIPTIVE_STARTS)

    def test_a_species_the_book_does_not_carry_yields_nothing(self):
        self.assertEqual(read(FLORA, ["Zzzzia nonexistens"]), [])

    def test_a_family_heading_ends_a_block(self):
        """Budd's runs family headings in capitals -- `ELEAEAGNACEAE -
        oleaster family` -- which is not Genus-then-epithet, so it did not end
        a block and Opuntia polyacantha ran 968 characters into the
        Elaeagnaceae, picking up their flowers as well as its own."""
        text = ("Opuntia polyacantha Haw. prickly-pear\n"
                "A prostrate plant. Flowers showy, yellow, 5-8 cm across.\n"
                "ELEAEAGNACEAE - oleaster family\n"
                "Shrubs with silvery leaves. Flowers brown, in small clusters.\n")
        block, _how = blocks(text, ["Opuntia polyacantha"])["Opuntia polyacantha"]
        self.assertIn("yellow", block)
        self.assertNotIn("ELEAEAGNACEAE", block)
        self.assertEqual(read(text, ["Opuntia polyacantha"])[0].buckets,
                         ("yellow",))


class TestA1979FloraDoesNotUse2026Names(unittest.TestCase):
    """*Cornus sericea* is simply absent from Budd's, which files red osier
    dogwood under *Cornus stolonifera*. No parser finds a name the book does
    not contain, so the common name has to carry it."""

    TEXT = ("Cornus stolonifera Michx. red-osier dogwood\n"
            "Shrub to 3 m. Stems red. Flowers white in flat cymes.\n")
    COMMON = {"Cornus sericea": "Red Osier Dogwood"}

    def test_the_binomial_alone_finds_nothing(self):
        self.assertEqual(read(self.TEXT, ["Cornus sericea"]), [])

    def test_the_common_name_crosses_the_gap(self):
        got = read(self.TEXT, ["Cornus sericea"], self.COMMON)
        self.assertEqual(len(got), 1)
        self.assertEqual(got[0].buckets, ("white",))

    def test_hyphenation_between_the_two_books_does_not_matter(self):
        """Budd's writes 'red-osier dogwood', the catalogue 'Red Osier
        Dogwood'."""
        got = read(self.TEXT, ["Cornus sericea"], self.COMMON)
        self.assertEqual(got[0].found_as, "common name")

    def test_a_common_name_match_is_never_confident(self):
        """A weaker key deserves a look, so it goes to the CHECK pile whatever
        else is true of it."""
        self.assertFalse(read(self.TEXT, ["Cornus sericea"],
                              self.COMMON)[0].confident)

    def test_a_short_common_name_is_refused(self):
        """'Rose' or 'Sage' would match half a flora."""
        self.assertEqual(read(self.TEXT, ["Zzzzia nonexistens"],
                              {"Zzzzia nonexistens": "Rose"}), [])


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


def _pdf(path, lines):
    """A real, minimal PDF. `lines` empty means a page with marks and no words,
    which is structurally what a scan is."""
    if lines:
        body = "BT /F1 11 Tf 72 720 Td 14 TL\n" + "".join(
            "(" + ln.replace("(", r"\(").replace(")", r"\)") + ") Tj T*\n"
            for ln in lines) + "ET"
    else:
        body = "0.5 g 72 72 468 648 re f"
    stream = body.encode("latin-1")
    objs = [b"<</Type/Catalog/Pages 2 0 R>>",
            b"<</Type/Pages/Kids[3 0 R]/Count 1>>",
            b"<</Type/Page/Parent 2 0 R/MediaBox[0 0 612 792]/Contents 4 0 R"
            b"/Resources<</Font<</F1 5 0 R>>>>>>",
            b"<</Length " + str(len(stream)).encode() + b">>\nstream\n"
            + stream + b"\nendstream",
            b"<</Type/Font/Subtype/Type1/BaseFont/Helvetica>>"]
    out, offsets = bytearray(b"%PDF-1.4\n"), []
    for i, obj in enumerate(objs, 1):
        offsets.append(len(out))
        out += str(i).encode() + b" 0 obj\n" + obj + b"\nendobj\n"
    xref = len(out)
    out += b"xref\n0 " + str(len(objs) + 1).encode() + b"\n0000000000 65535 f \n"
    for off in offsets:
        out += ("%010d 00000 n \n" % off).encode()
    out += (b"trailer\n<</Size " + str(len(objs) + 1).encode()
            + b"/Root 1 0 R>>\nstartxref\n" + str(xref).encode() + b"\n%%EOF\n")
    path.write_bytes(bytes(out))


try:
    import pypdf  # noqa: F401
    _HAVE_PYPDF = True
except Exception:                                      # noqa: BLE001
    _HAVE_PYPDF = False


@unittest.skipUnless(_HAVE_PYPDF, "pypdf not installed")
class TestTellingTextFromAScan(unittest.TestCase):
    """The one question that decides how big this job is.

    A text PDF is an evening. An image-only PDF is an OCR project first. They
    look identical in a viewer because the reader's eyes do the OCR, so the
    difference has to be reported as a number.
    """

    def setUp(self):
        import tempfile
        from pathlib import Path
        self.tmp = Path(tempfile.mkdtemp())

    def test_a_text_pdf_extracts_its_words(self):
        from scripts.pdf_to_text import extract
        src = self.tmp / "a.pdf"
        _pdf(src, ["Achillea millefolium L. YARROW",
                   "Flowers white, rarely pinkish, in flat-topped corymbs."])
        pages, chars = extract(src, self.tmp / "a.txt", quiet=True)
        self.assertEqual(pages, 1)
        self.assertGreater(chars, 50)
        self.assertIn("Flowers white",
                      (self.tmp / "a.txt").read_text(encoding="utf-8"))

    def test_an_image_only_pdf_falls_under_the_scan_threshold(self):
        from scripts.pdf_to_text import SCAN_THRESHOLD, extract
        src = self.tmp / "b.pdf"
        _pdf(src, [])
        pages, chars = extract(src, self.tmp / "b.txt", quiet=True)
        self.assertEqual(pages, 1)
        self.assertLess(chars / pages, SCAN_THRESHOLD)

    def test_the_threshold_sits_between_the_two_cases(self):
        """A typed flora page runs to thousands of characters and a scanned one
        to nearly none, so the threshold is not a close call -- but it should
        still be checked rather than assumed."""
        from scripts.pdf_to_text import SCAN_THRESHOLD
        self.assertGreater(SCAN_THRESHOLD, 10)
        self.assertLess(SCAN_THRESHOLD, 500)


if __name__ == "__main__":
    unittest.main()
