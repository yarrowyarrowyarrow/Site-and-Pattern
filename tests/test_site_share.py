"""What a link to this site unfolds into when somebody pastes it (V2.80).

Every page carried a title and a description and nothing else, so a link shared
to Facebook, Reddit, Slack or a text message rendered as a grey box. The whole
argument of this catalogue is that the plants are worth looking at, and the one
surface where a stranger meets it first had no picture on it.

The trap these tests exist for is that **a broken share card is invisible from
the page**. The HTML validates, the site renders, nothing errors, and the only
way to find out is for somebody else to paste the link somewhere.
"""

import unittest

from src import site_share


class TestTheAbsoluteUrlRule(unittest.TestCase):
    """The failure that has no symptom on the page it is on.

    A scraper fetches `og:image` from its own servers, with no page to resolve
    a relative path against, so `assets/photos/x.jpg` produces no card at all
    and no error anywhere.
    """

    def test_a_relative_path_needs_the_base_url(self):
        share = site_share.configure(base_url="https://grownativeplants.ca/")
        self.assertEqual(share.absolute("assets/photos/x.jpg"),
                         "https://grownativeplants.ca/assets/photos/x.jpg")

    def test_a_build_with_no_base_url_emits_no_image_rather_than_a_bad_one(self):
        share = site_share.configure(image="assets/photos/x.jpg", alt="A plant")
        self.assertEqual(share.absolute("assets/photos/x.jpg"), "")
        names = [name for _, name, _ in share.meta("T", "D")]
        self.assertNotIn("og:image", names)
        # And it says so, rather than promising a big picture it cannot supply.
        self.assertIn(("name", "twitter:card", "summary"), share.meta("T", "D"))

    def test_a_hotlinked_photo_passes_through(self):
        """A cold image cache leaves photos as links to iNaturalist
        (`_stage_photos`). Those are as fetchable as a staged copy."""
        share = site_share.configure(base_url="https://example.org")
        url = "https://inaturalist-open-data.s3.amazonaws.com/photos/1/x.jpg"
        self.assertEqual(share.absolute(url), url)

    def test_a_relative_base_url_is_refused_at_configure_time(self):
        """Not written into 2,000 pages first. The `site_analytics` rule."""
        with self.assertRaises(ValueError):
            site_share.configure(base_url="grownativeplants.ca")


class TestWhatTheCardSays(unittest.TestCase):

    def _share(self):
        return site_share.configure(base_url="https://example.org/",
                                    image="assets/photos/default.jpg",
                                    alt="Prairie Crocus. (c) Someone (CC BY)")

    def test_a_page_with_its_own_photo_uses_it(self):
        tags = dict((name, content)
                    for _, name, content in self._share().meta(
                        "Wild Bergamot", "A plant.",
                        "assets/photos/wild-bergamot.jpg", "Bergamot. (c) X"))
        self.assertEqual(tags["og:image"],
                         "https://example.org/assets/photos/wild-bergamot.jpg")
        self.assertEqual(tags["og:image:alt"], "Bergamot. (c) X")

    def test_the_default_photo_keeps_the_default_credit(self):
        """One page's image must never appear under another's attribution.

        These are open-licensed photographs and the credit is the licence
        condition, so a card that pairs the wrong two is not a cosmetic bug.
        """
        tags = dict((name, content)
                    for _, name, content in self._share().meta(
                        "Method", "How these pages are made.",
                        "", "an alt text belonging to nothing"))
        self.assertEqual(tags["og:image"],
                         "https://example.org/assets/photos/default.jpg")
        self.assertIn("Someone", tags["og:image:alt"])

    def test_both_vocabularies_are_emitted(self):
        """Facebook, Reddit, Slack and Discord read `og:`; Twitter/X reads
        `twitter:`. One set of values, two spellings."""
        names = [name for _, name, _ in self._share().meta("T", "D")]
        for want in ("og:title", "og:description", "og:image",
                     "twitter:title", "twitter:description", "twitter:card"):
            self.assertIn(want, names)

    def test_the_tags_come_back_unescaped_for_one_escaper(self):
        """`static_site_render._esc` also normalises em dashes, and a second
        escaper in a second module is how `&amp;amp;` reached every page title
        once already."""
        tags = dict((name, content) for _, name, content
                    in self._share().meta("A & B", "x < y"))
        self.assertEqual(tags["og:title"], "A & B")


class TestPickingTheDefaultPhotograph(unittest.TestCase):

    def _model(self, *species):
        return {"species": [
            {"scientific_name": sci, "name": name,
             "photos": ([{"url": url, "attribution": attr,
                          "license": "cc-by"}] if url else [])}
            for sci, name, url, attr in species]}

    def test_it_takes_the_first_listed_species_that_has_a_photo(self):
        model = self._model(
            ("Pulsatilla nuttalliana", "Prairie Crocus", "", ""),
            ("Gaillardia aristata", "Blanketflower", "http://x/g.jpg",
             "(c) Photographer, some rights reserved (CC BY)"))
        src, alt = site_share.default_card(model, {})
        self.assertEqual(src, "http://x/g.jpg")
        self.assertIn("Blanketflower", alt)
        self.assertIn("Photographer", alt)

    def test_the_credit_rides_in_the_alt_text(self):
        """`og:image:alt` is the only place a credit can travel when the photo
        is being shown inside somebody else's app and the page it came from is
        reduced to a link."""
        model = self._model(("Pulsatilla nuttalliana", "Prairie Crocus",
                             "http://x/p.jpg", "(c) Syd Cannings (CC BY)"))
        _, alt = site_share.default_card(model, {})
        self.assertIn("Syd Cannings", alt)

    def test_a_catalogue_with_no_credited_photo_shares_no_image(self):
        """Rather than an uncredited one. The site's standing rule: a photo
        with no attribution is not published (`static_site.photo_credit`)."""
        model = self._model(("Pulsatilla nuttalliana", "Prairie Crocus",
                             "", ""))
        self.assertEqual(site_share.default_card(model, {}), ("", ""))

    def test_it_prefers_the_staged_copy_over_the_hotlink(self):
        """`photo_src` maps a recorded URL to the file copied beside the
        pages. Sharing the site's own copy keeps the card working when the CDN
        changes, which is the reason those files are staged at all."""
        model = self._model(("Pulsatilla nuttalliana", "Prairie Crocus",
                             "http://x/p.jpg", "(c) Someone (CC BY)"))
        src, _ = site_share.default_card(
            model, {"http://x/p.jpg": "assets/photos/prairie-crocus.jpg"})
        self.assertEqual(src, "assets/photos/prairie-crocus.jpg")


if __name__ == "__main__":
    unittest.main()
