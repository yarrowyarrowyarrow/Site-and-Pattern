"""
site_analytics.py — who, if anyone, is reading the published catalogue.

:mod:`src.static_site_render` opens with a promise: no framework, no build
step, no CDN, **no external request of any kind**. V2.71 made analytics the one
opt-in exception to it and set the price of that exception in three parts:

1. **Off unless asked for.** A build given no analytics argument emits no
   third-party script and the site phones nowhere.
2. **No cookie, no per-visitor identifier.** Which is what makes it the kind
   of measurement a catalogue can carry without a consent banner. A script
   that needed one would not be admitted here, whatever it measured.
3. **Disclosed in the footer of every page it appears on**, in words, not in a
   privacy policy nobody opens.

This module owns all three, plus the question V2.73 added: **which** provider,
now that there are two.

**Why two.** Cloudflare Web Analytics answers *"is anybody reading this at
all"* and it answers it well, but its free tier keeps a short window, so
*"is readership growing"* and *"which pages do people arrive on over a season"*
are not in it. Umami keeps history. They are not alternatives during the
fortnight you are switching, either: running both is how you find out the new
one is actually recording before you turn the old one off.

**Everything here is validated, and validation raises.** These values land
inside quoted HTML attributes on ~2,000 pages. A loose check is markup
injection across the whole site, and a silently-degraded value is worse than an
error, because a build that recorded nothing looks exactly like one that
worked.
"""

from __future__ import annotations

from dataclasses import dataclass

import re

#: Umami Cloud's US script. The default, because it is what somebody who has
#: just signed up is handed, and it needs no hosting decision.
#:
#: The other two real destinations are ``https://eu.umami.is/script.js`` (their
#: EU region) and a self-hosted instance on your own domain. The third is worth
#: keeping reachable for a reason that is not ideology: ``cloud.umami.is`` sits
#: on the common blocklists, so a share of visitors go uncounted, and serving
#: the script from the site's own domain is the fix. That is why this is a
#: parameter and not a constant in the renderer.
UMAMI_CLOUD = "https://cloud.umami.is/script.js"

#: What a valid Cloudflare beacon token looks like (V2.71). Deliberately
#: strict: the value goes inside a quoted JSON attribute on every page.
_CF_TOKEN_OK = re.compile(r"^[A-Za-z0-9]{16,64}$")

#: Umami identifies a website by a UUID. Checking the shape rather than merely
#: "not empty" costs one regex and refuses a value with a quote in it before it
#: reaches 2,000 pages.
_UMAMI_ID_OK = re.compile(
    r"^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}"
    r"-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$")

#: An https URL with a hostname, an optional port and a path, and nothing that
#: could close an attribute. ``https`` only: the site is served over https, and
#: a script loaded over http would be blocked by the browser anyway, so
#: accepting one would only produce a build that looks fine and records
#: nothing.
_SRC_OK = re.compile(
    r"^https://[A-Za-z0-9]([A-Za-z0-9.\-]*[A-Za-z0-9])?(:\d{1,5})?"
    r"(/[A-Za-z0-9._~\-]*)*$")

#: Provider display names, used in the footer sentence and in what the build
#: prints. One table, so the page and the console cannot disagree about what
#: went into the build.
_CLOUDFLARE = "Cloudflare Web Analytics"
_UMAMI = "Umami"


@dataclass(frozen=True)
class Analytics:
    """What one build carries. Frozen: a build's analytics do not change
    half way through rendering it.

    Construct through :func:`configure`, which validates. Constructing this
    directly skips the checks, which is fine for :data:`NONE` and for a test
    and is not fine for anything reading operator input.
    """

    cf_token: str = ""
    umami_id: str = ""
    umami_src: str = UMAMI_CLOUD

    def __bool__(self) -> bool:
        return bool(self.cf_token or self.umami_id)

    def providers(self) -> tuple:
        """Display names of what is switched on, in the order they are
        emitted. Empty for a build that phones nowhere."""
        names = []
        if self.cf_token:
            names.append(_CLOUDFLARE)
        if self.umami_id:
            names.append(_UMAMI)
        return tuple(names)

    def tags(self) -> str:
        """The ``<script>`` tags for the end of ``<body>``, or ``""``.

        **Each vendor's tag is reproduced attribute for attribute**, including
        the parts that look redundant. V2.71 learned this the hard way with
        Cloudflare: the first cut wrote ``defer``, which is what Cloudflare's
        *older* snippet used, and the beacon ships as an ES module now.
        Loading a module as a classic script records nothing and reports no
        error. Umami's tag is ``defer`` and a plain script, and is left that
        way for the same reason. There is no reason to paraphrase a vendor.
        """
        out = []
        if self.cf_token:
            out.append(
                '<script type="module" src="https://static.cloudflareinsights'
                '.com/beacon.min.js" data-cf-beacon=\'{"token": "'
                + self.cf_token + '"}\'></script>')
        if self.umami_id:
            out.append('<script defer src="' + self.umami_src
                       + '" data-website-id="' + self.umami_id
                       + '"></script>')
        return "".join(out)

    def disclosure(self) -> str:
        """The footer paragraph, or ``""``.

        **Generated from what is configured, never written down.** A footer
        naming Cloudflare on a build carrying Umami is exactly the class of
        quiet falsehood this repo keeps finding in its own prose, and prose is
        the half nobody re-reads. The phrase "sets no cookies" survives every
        combination on purpose, and a test holds it there: it is the promise,
        and it must not be lost to a rewording.
        """
        names = self.providers()
        if not names:
            return ""
        if len(names) == 1:
            who = (names[0] + ", which sets no cookies and records nothing "
                   "that identifies you. It is the only request this site "
                   "makes to anywhere else.")
        else:
            who = (" and by ".join(names) + ". Each sets no cookies and "
                   "records nothing that identifies you. They are the only "
                   "requests this site makes to anywhere else.")
        return "\n    <p>Page views are counted by " + who + "</p>"


#: A build that phones nowhere. The default, and the state every build before
#: V2.71 was in.
NONE = Analytics()


def configure(*, cloudflare_token: str = "", umami_website_id: str = "",
              umami_src: str = "") -> Analytics:
    """Validate operator input into an :class:`Analytics`. Raises
    ``ValueError`` on anything malformed rather than publishing it.

    All arguments optional and all default to off; passing none of them
    returns :data:`NONE`. ``umami_src`` is ignored without an id, because a
    script URL alone does not identify a site and silently doing nothing with
    it would be the surprising reading.
    """
    cf = (cloudflare_token or "").strip()
    uid = (umami_website_id or "").strip()
    src = (umami_src or "").strip() or UMAMI_CLOUD

    if cf and not _CF_TOKEN_OK.match(cf):
        raise ValueError(
            "analytics token must be 16-64 plain alphanumeric characters; "
            "got something else, and this value is written into every page. "
            "Copy only the value after '\"token\":' from Cloudflare's snippet")
    if uid and not _UMAMI_ID_OK.match(uid):
        raise ValueError(
            "umami website id must be a UUID like "
            "'0f8c1a2b-3d4e-5f60-7182-93a4b5c6d7e8'; got something else, and "
            "this value is written into every page. It is on the website's "
            "Settings page in Umami, not the tracking URL")
    if uid and not _SRC_OK.match(src):
        raise ValueError(
            "umami script url must be an https:// URL with no quotes or "
            f"spaces; got {src!r}. Umami Cloud is {UMAMI_CLOUD}; a "
            "self-hosted instance serves the same file from its own domain")

    return Analytics(cf_token=cf, umami_id=uid, umami_src=src)
