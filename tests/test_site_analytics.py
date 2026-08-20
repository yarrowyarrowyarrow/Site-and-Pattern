"""
V2.73. The analytics vocabulary, tested straight rather than through a whole
site build.

`tests/test_static_site.py:TestAnalyticsIsOptInAndDisclosed` proves the tags
and the disclosure reach every rendered page, which is the promise. That test
renders ~2,000 pages per case, so the *validation table* — every shape of bad
input, and the three provider combinations — belongs here where it costs
nothing to be exhaustive.
"""

import unittest

from src.site_analytics import UMAMI_CLOUD, Analytics, NONE, configure

_CF = "a" * 32
_UID = "0f8c1a2b-3d4e-5f60-7182-93a4b5c6d7e8"


class TestNothingUnlessAsked(unittest.TestCase):

    def test_the_default_phones_nowhere(self):
        for cfg in (NONE, configure()):
            self.assertFalse(cfg)
            self.assertEqual(cfg.tags(), "")
            self.assertEqual(cfg.disclosure(), "")
            self.assertEqual(cfg.providers(), ())

    def test_a_script_url_alone_is_not_a_site(self):
        """A src with no website id identifies nothing. Emitting a tag for it
        would produce a build that looks instrumented and records nothing."""
        cfg = configure(umami_src="https://analytics.example.org/script.js")
        self.assertFalse(cfg)
        self.assertEqual(cfg.tags(), "")


class TestMalformedInputIsRefused(unittest.TestCase):
    """These values land inside quoted HTML attributes on every page. A loose
    check is markup injection across the whole site, and a silently-degraded
    value is worse than an error because the build still looks fine."""

    def test_bad_cloudflare_tokens(self):
        for bad in ('x" onload="alert(1)', "short", "has spaces in it",
                    "tok'en", "a" * 65, "dashes-are-not-alnum-aaaaaaaaaaa"):
            with self.assertRaises(ValueError, msg=bad):
                configure(cloudflare_token=bad)

    def test_bad_umami_ids(self):
        for bad in ("not-a-uuid", "", " ", _UID[:-1], _UID + "0",
                    f'{_UID}" onload="alert(1)', _UID.replace("-", ""),
                    "0f8c1a2b_3d4e_5f60_7182_93a4b5c6d7e8"):
            if not bad.strip():
                # Empty is "off", not "malformed" — checked in the class above.
                continue
            with self.assertRaises(ValueError, msg=bad):
                configure(umami_website_id=bad)

    def test_bad_umami_script_urls(self):
        for bad in ("http://cloud.umami.is/script.js",      # not https
                    "//cloud.umami.is/script.js",
                    "https://cloud.umami.is/script.js\" onerror=\"x",
                    "https://cloud.umami.is/a b.js",
                    "javascript:alert(1)",
                    "cloud.umami.is/script.js"):
            with self.assertRaises(ValueError, msg=bad):
                configure(umami_website_id=_UID, umami_src=bad)

    def test_a_self_hosted_url_is_accepted(self):
        """The whole reason the URL is a parameter. A check so strict it only
        passes Umami Cloud would be a constant with extra steps."""
        for good in ("https://eu.umami.is/script.js",
                     "https://grownativeplants.ca/u.js",
                     "https://analytics.example.org:8443/umami/script.js"):
            cfg = configure(umami_website_id=_UID, umami_src=good)
            self.assertIn(f'src="{good}"', cfg.tags(), good)


class TestTheTagsAreTheVendorsTags(unittest.TestCase):
    """V2.71's lesson, kept: the first Cloudflare cut wrote `defer` because
    that is what their *older* snippet used, and the beacon ships as an ES
    module. Loading a module as a classic script records nothing and reports no
    error. So each vendor's attributes are reproduced, not paraphrased."""

    def test_cloudflare_is_a_module(self):
        tags = configure(cloudflare_token=_CF).tags()
        self.assertIn('<script type="module"', tags)
        self.assertIn("static.cloudflareinsights.com/beacon.min.js", tags)
        self.assertIn(_CF, tags)

    def test_umami_is_a_deferred_classic_script(self):
        tags = configure(umami_website_id=_UID).tags()
        self.assertIn("<script defer", tags)
        self.assertNotIn('type="module"', tags)
        self.assertIn(f'src="{UMAMI_CLOUD}"', tags)
        self.assertIn(f'data-website-id="{_UID}"', tags)

    def test_both_at_once_emits_both(self):
        """Allowed on purpose: the fortnight you are switching is exactly when
        you want to see the old numbers and the new ones together."""
        cfg = configure(cloudflare_token=_CF, umami_website_id=_UID)
        self.assertEqual(cfg.tags().count("<script"), 2)
        self.assertEqual(cfg.providers(),
                         ("Cloudflare Web Analytics", "Umami"))


class TestTheDisclosureSaysWhatIsActuallyThere(unittest.TestCase):

    _ALL = (dict(cloudflare_token=_CF),
            dict(umami_website_id=_UID),
            dict(cloudflare_token=_CF, umami_website_id=_UID))

    def test_the_no_cookie_promise_survives_every_combination(self):
        """It is the reason these scripts are admitted at all, and prose is the
        half nobody re-reads. Pinned so it cannot be lost to a rewording."""
        for kw in self._ALL:
            text = configure(**kw).disclosure()
            self.assertIn("sets no cookies", text, str(kw))
            self.assertIn("nothing that identifies you", text, str(kw))

    def test_it_names_the_providers_that_are_on_and_no_others(self):
        """A footer naming Cloudflare on a build carrying Umami is the class of
        quiet falsehood this repo keeps finding in its own prose."""
        cf_only = configure(cloudflare_token=_CF).disclosure()
        self.assertIn("Cloudflare", cf_only)
        self.assertNotIn("Umami", cf_only)

        umami_only = configure(umami_website_id=_UID).disclosure()
        self.assertIn("Umami", umami_only)
        self.assertNotIn("Cloudflare", umami_only)

        both = configure(cloudflare_token=_CF,
                         umami_website_id=_UID).disclosure()
        self.assertIn("Cloudflare", both)
        self.assertIn("Umami", both)

    def test_no_em_dash_reaches_the_footer(self):
        """House rule for everything rendered onto a page. `_esc` normalises
        database prose; this string is authored here and bypasses it."""
        for kw in self._ALL:
            self.assertNotIn("—", configure(**kw).disclosure(), str(kw))


class TestTheRecordIsImmutable(unittest.TestCase):

    def test_a_build_s_analytics_cannot_change_half_way_through_it(self):
        with self.assertRaises(Exception):
            Analytics(cf_token=_CF).cf_token = "b" * 32


if __name__ == "__main__":
    unittest.main()
