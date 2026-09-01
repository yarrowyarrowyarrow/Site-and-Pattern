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
