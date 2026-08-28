"""
A way to report an error without an account (V2.80).

The author's ask: *"I think github is too intimidating for most. I'd like it to
be a box where feedback can be filled in and sent directly from the website, no
account or personal info required."*

What these pin is mostly the promises around the form rather than the form: a
catalogue whose whole argument is "we tell you what we do not know" cannot
quietly start collecting things it did not say it collects, and cannot keep
advertising that it makes no external request once one of its pages can send.
"""

import os
import pathlib
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.static_site_feedback import (HONEYPOT,                # noqa: E402
                                      render_feedback, render_thanks)

ENDPOINT = "https://feedback.example.workers.dev"


class TestTheFormOnlyExistsWhenItCanSend(unittest.TestCase):
    """A button that goes nowhere is worse than no button."""

    def test_a_configured_build_gets_a_form(self):
        page = render_feedback({}, ENDPOINT)
        self.assertIn("<form", page)
        self.assertIn(ENDPOINT, page)

    def test_an_unconfigured_build_gets_no_form_and_says_why(self):
        page = render_feedback({}, "")
        self.assertNotIn("<form", page)
        self.assertIn("no feedback address configured", page)
        self.assertIn("github.com", page)

    def test_the_page_exists_either_way(self):
        """The header links it from every page, so it must always be written."""
        for endpoint in (ENDPOINT, ""):
            self.assertIn("What did you think?", render_feedback({}, endpoint))

    def test_it_does_not_only_ask_what_is_wrong(self):
        """It was headed "Tell us what is wrong" and every line assumed the
        reader had found a fault. A page that invites only complaints gets
        only complaints, and what people find useful is the thing this
        catalogue has no other way of learning: it counts page views and
        nothing else.

        The error path is deliberately still named. A wrong flower colour is
        worth more than a compliment; it is just no longer the only thing you
        are invited to write."""
        for endpoint in (ENDPOINT, ""):
            page = render_feedback({}, endpoint)
            self.assertNotIn("Tell us what is wrong", page)
            self.assertIn("What did you like and what can be improved", page)
            self.assertIn("Corrections are most", page,
                          "reporting an error must still be invited")

    def test_the_ask_is_made_once(self):
        """The rewrite that fixed the tone said it three times: a lede, a
        paragraph explaining the lede, and the field label asking again.
        Reported as "it's still doing too much".

        The label is checked for *presence* in the same breath, because the
        obvious way to stop repeating the question is to delete the label, and
        a textarea with no label has no name for a screen reader."""
        page = render_feedback({}, ENDPOINT)
        self.assertEqual(page.count("What did you like"), 1)
        self.assertIn('<label for="fb-msg">Your message</label>', page)


class TestItAsksForNothingItDoesNotNeed(unittest.TestCase):
    """"No account or personal info required" is a promise the markup has to
    keep, not a sentence in the lede."""

    def setUp(self):
        self.page = render_feedback({}, ENDPOINT)

    def test_only_the_message_is_required(self):
        self.assertEqual(self.page.count("required"), 1)
        self.assertIn('name="message" rows="8" required', self.page)

    def test_the_email_is_optional_and_labelled_so(self):
        self.assertIn('type="email"', self.page)
        self.assertNotIn('type="email" id="fb-email" name="email" required',
                         self.page)
        self.assertIn("only if you\n  want a reply", self.page)

    def test_there_is_no_name_field(self):
        for unwanted in ('name="name"', 'name="firstname"', 'name="author"'):
            self.assertNotIn(unwanted, self.page)

    def test_it_says_what_is_kept(self):
        self.assertIn("We keep the message, and the email only if you gave one",
                      self.page)


class TestItWorksWithoutJavaScript(unittest.TestCase):
    """`browse.js` is the site's only script and it is about the index pages.
    A form that needs `fetch` has a failure mode where the button does nothing
    and the reader cannot tell whether their words went anywhere."""

    def test_it_is_a_plain_post_form(self):
        page = render_feedback({}, ENDPOINT)
        self.assertIn('method="post"', page)
        self.assertNotIn("<script", page)
        self.assertNotIn("onsubmit", page)

    def test_there_is_somewhere_to_land_afterwards(self):
        """The Worker replies with a redirect, so this page IS the
        confirmation. It has to say plainly that the message arrived, or the
        reader cannot tell whether their words went anywhere."""
        thanks = render_thanks({})
        self.assertIn("Thank you", thanks)
        self.assertIn("has been sent", thanks)


class TestTheBotTrap(unittest.TestCase):

    def test_the_honeypot_is_present_and_hidden_from_people(self):
        page = render_feedback({}, ENDPOINT)
        self.assertIn(f'name="{HONEYPOT}"', page)
        self.assertIn('class="hp" aria-hidden="true"', page)
        self.assertIn('tabindex="-1"', page)

    def test_it_is_moved_off_screen_rather_than_display_none(self):
        """Some bots skip `display:none` inputs, and this one is meant to be
        filled. It must still never be focusable or read aloud."""
        css = (pathlib.Path(__file__).parent.parent / "html" / "site"
               / "site.css").read_text(encoding="utf-8")
        self.assertIn(".feedback .hp { position: absolute; left: -9999px;", css)
        self.assertNotIn(".feedback .hp { display: none", css)


class TestTheWorkerKeepsThePagesPromises(unittest.TestCase):
    """The endpoint is checked in beside the site, so what the page says it
    does and what the server does can be read against each other."""

    def setUp(self):
        self.js = (pathlib.Path(__file__).parent.parent / "workers"
                   / "feedback" / "worker.js").read_text(encoding="utf-8")

    def test_it_stores_no_identifier(self):
        """The page says no account and no personal info. A server logging the
        sender would make that false, and nobody reading the page would know."""
        for leak in ("cf-connecting-ip", "CF-Connecting-IP", "user-agent",
                     "User-Agent", "request.headers.get"):
            self.assertNotIn(leak, self.js)

    def test_the_email_is_absent_rather_than_empty_when_not_given(self):
        """A key that is always there reads as "we asked and they refused"."""
        self.assertIn('...(form.get("email")', self.js)

    def test_it_redirects_with_303_so_a_refresh_does_not_resend(self):
        self.assertIn("status: 303", self.js)

    def test_it_drops_the_honeypot_silently(self):
        self.assertIn(f'form.get("{HONEYPOT}")', self.js)

    def test_it_refuses_anything_but_post(self):
        self.assertIn('request.method !== "POST"', self.js)


class TestTheSiteStopsClaimingMoreThanItDoes(unittest.TestCase):
    """The site advertised "no external request of any kind". A page that can
    submit a form makes that the kind of claim this project keeps catching
    itself making, so it is narrowed rather than repeated loosely."""

    def test_the_renderer_says_no_request_ON_LOAD(self):
        src = (pathlib.Path(__file__).parent.parent / "src"
               / "static_site_render.py").read_text(encoding="utf-8")
        self.assertIn("no external request\nwhen a page loads", src)
        self.assertNotIn("no external request of any\nkind", src)

    def test_feedback_is_in_the_header_of_every_page(self):
        from src.static_site_render import _NAV
        self.assertIn(("feedback/", "Feedback"), _NAV)


if __name__ == "__main__":
    unittest.main()
