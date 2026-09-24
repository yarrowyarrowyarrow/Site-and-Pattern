"""site_share.py — the card a link to this site unfolds into.

Design principle P13 — see docs/DESIGN_PHILOSOPHY.md (a native planting has to
be loved to survive: beauty is the mechanism the ecology survives contact with
people by, not decoration on top of it).

Why this module exists (V2.80)
------------------------------
Every page on this site carried a ``<title>`` and a ``<meta name=description>``
and nothing else, so a link pasted into Facebook, Reddit, Slack or a text
message unfolded into a grey box with a bare URL under it. That is not a
cosmetic gap. **The whole argument of this catalogue is that the plants are
worth looking at** and the one surface where a stranger meets it first was the
one surface with no picture on it.

What the scrapers actually need, and what each part of that costs here:

* **Open Graph tags in the head.** Facebook, Reddit, Slack, Discord, LinkedIn
  and iMessage all read ``og:*``; Twitter/X reads ``twitter:*`` and falls back
  to ``og:*``. Two vocabularies, one set of values.
* **An absolute ``og:image``.** The scraper fetches the image from its own
  servers, with no page to resolve a relative path against, so
  ``assets/photos/x.jpg`` silently produces no card at all. That is why
  :func:`configure` takes the build's ``base_url``: without one there is no
  honest absolute URL to give, and this module emits **no image tag** rather
  than a broken one. A build published to a directory or opened over
  ``file://`` therefore gets a text card, which is correct.
* **A photograph the site is allowed to hand to somebody else.** Every photo in
  the catalogue is openly licensed and credited (``static_site.photo_credit``
  refuses the rest), and the credit travels into ``og:image:alt`` so it is
  carried by the tag itself rather than left behind on the page.

Per-page where a page has its own photograph, and the site default otherwise.
Sharing a species page should show *that* species.

No new external request is created by any of this. The tags are inert text; a
scraper fetching the image is somebody else's client fetching a page that was
handed to it deliberately, which is the whole point of a share card.
"""

from __future__ import annotations

from dataclasses import dataclass

#: The species whose photograph fronts a shared link to a page with no
#: photograph of its own: the home page, the search page, About, Method, every
#: hub and every listing.
#:
#: A list rather than one name because a catalogue that drops a species, or a
#: photo whose licence is withdrawn, should cost the site its second choice and
#: not its card. The first name that has a credited photograph in the build
#: wins, so the order is the preference.
#:
#: Prairie Crocus leads on the argument this module opens with: it is the first
#: thing to flower on ground most people here have written off, which is the
#: catalogue's whole pitch in one photograph.
DEFAULT_SPECIES = (
    "Pulsatilla nuttalliana",     # Prairie Crocus
    "Gaillardia aristata",        # Blanketflower
    "Monarda fistulosa",          # Wild Bergamot
    "Liatris ligulistylis",       # Meadow Blazingstar
    "Rosa acicularis",            # Prickly Wild Rose
    "Opuntia polyacantha",        # Plains Prickly Pear Cactus
)


@dataclass(frozen=True)
class Share:
    """One build's sharing configuration. Immutable; see :func:`configure`."""

    base_url: str = ""
    image: str = ""
    alt: str = ""

    def absolute(self, url: str) -> str:
        """``url`` as something a scraper on another machine can fetch, or ``""``.

        An already-absolute URL passes through: a photo left as a hotlink to
        iNaturalist (which is what a cold image cache produces, see
        ``_stage_photos``) is as fetchable as a staged copy.
        """
        url = (url or "").strip()
        if url.startswith(("http://", "https://")):
            return url
        if not url or not self.base_url:
            return ""
        return self.base_url + "/" + url.lstrip("/")

    def meta(self, title: str, description: str,
             image: str = "", alt: str = "") -> list:
        """``[(attribute, name, content), ...]`` — the tags, **unescaped**.

        Returned as data rather than markup so the one escaper this site has
        (``static_site_render._esc``, which also normalises em dashes) stays the
        only one. A second escaper in a second module is how ``&amp;amp;`` got
        into every page title once already.
        """
        from src.static_site_render import SITE_NAME          # noqa: PLC0415

        # The page's own photograph, or the site default with the site
        # default's credit. Never one page's image under another's attribution.
        src = self.absolute(image)
        if not src:
            src, alt = self.absolute(self.image), self.alt
        out = [("property", "og:type", "website"),
               ("property", "og:site_name", SITE_NAME),
               ("property", "og:title", title),
               ("property", "og:description", description),
               ("name", "twitter:title", title),
               ("name", "twitter:description", description)]
        if src:
            out += [("property", "og:image", src),
                    ("property", "og:image:alt", alt or title),
                    ("name", "twitter:image", src),
                    # The wide card. Worth it: these are photographs, and the
                    # small square variant crops a flower to a thumbnail.
                    ("name", "twitter:card", "summary_large_image")]
        else:
            out.append(("name", "twitter:card", "summary"))
        return out

    def page_url(self, rel: str) -> str:
        """The absolute URL of the page written at ``rel``, or ``""`` (V2.84).

        ``plants/fireweed/index.html`` is served as ``/plants/fireweed/``, and
        that trailing-slash form is the one every link on the site uses, so it
        is the one to declare canonical. Only pages, and only with a base URL.
        """
        if not self.base_url or not rel.endswith(".html"):
            return ""
        path = rel[:-len("index.html")] if rel.endswith("index.html") else rel
        return self.base_url + "/" + path

    def with_page_url(self, html: str, rel: str) -> str:
        """``html`` with ``<link rel=canonical>`` and ``og:url`` added (V2.84).

        Added at write time, where the page's path is already known, rather
        than threaded through ``_page``: V2.80 left ``og:url`` out because
        passing every page's path through six modules' call sites was the
        cost, and the file writer had the path all along.
        """
        from src.static_site_render import _esc               # noqa: PLC0415

        url = self.page_url(rel)
        if not url or "</head>" not in html:
            return html
        tags = (f'<link rel="canonical" href="{_esc(url)}">\n'
                f'<meta property="og:url" content="{_esc(url)}">\n')
        return html.replace("</head>", tags + "</head>", 1)


def page_title(title: str) -> str:
    """The ``<title>`` a search result or a browser tab shows (V2.84).

    Species pages were titled with the plant alone, *Saskatoon Berry
    (Amelanchier alnifolia)*, so a search result never said whose page it was.
    The site name is added unless the title already carries it.
    """
    from src.static_site_render import SITE_NAME              # noqa: PLC0415

    title = (title or "").strip()
    if not title:
        return SITE_NAME
    return title if SITE_NAME in title else f"{title} | {SITE_NAME}"


#: A build that shares nothing but its words. The default, and what a build
#: without a ``--base-url`` gets, because there is no absolute image URL to be
#: had and a card pointing at a path that 404s is worse than a text card.
NONE = Share()


def configure(base_url: str = "", image: str = "", alt: str = "") -> Share:
    """Validate and normalise one build's sharing configuration."""
    base = (base_url or "").strip().rstrip("/")
    if base and not base.startswith(("http://", "https://")):
        raise ValueError(
            f"base_url must be absolute for share cards to work: {base_url!r}")
    return Share(base_url=base, image=(image or "").strip(),
                 alt=(alt or "").strip())


def photo_card(photo: dict, photo_src: dict, name: str) -> tuple:
    """``(image path, alt text)`` for one entry's photograph, or ``("", "")``.

    ``alt`` is the subject **and** the credit, in that order. ``og:image:alt``
    is nominally alt text, and it is also the only place a credit can ride when
    the image is being displayed inside somebody else's app with the page it
    came from reduced to a link.
    """
    from src.image_cache import credit_line                   # noqa: PLC0415

    url = ((photo or {}).get("url") or "").strip()
    if not url:
        return "", ""
    credit = credit_line((photo or {}).get("attribution") or "",
                         (photo or {}).get("license") or "")
    alt = f"{name}. {credit}".strip().strip(".") if name else credit
    return photo_src.get(url, url), alt


def default_card(model: dict, photo_src: dict) -> tuple:
    """``(image path, alt text)`` for the site default, or ``("", "")``.

    Picked from the built model rather than pinned to a file, so the card can
    never show a photograph the catalogue has stopped publishing.
    """
    from src.static_site import _first_photo                  # noqa: PLC0415

    by_name = {e.get("scientific_name"): e for e in model.get("species") or []}
    for want in DEFAULT_SPECIES:
        entry = by_name.get(want)
        if not entry:
            continue
        src, alt = photo_card(_first_photo(entry), photo_src,
                              entry.get("name") or want)
        if src:
            return src, alt
    return "", ""
