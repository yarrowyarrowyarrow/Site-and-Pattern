"""
static_site_gallery.py — a species page's photographs on the website (V3.35,
F251).

Design principle P13 — see docs/DESIGN_PHILOSOPHY.md.

A species page led with one photograph. Now the first still leads, full width,
and the others follow as a row of thumbnails, each a link to its larger copy,
in the order the app shows them (``src.db.plants.photo_order``: the owner's
picks, the flower first). **Every photograph shown carries its own credit**,
the licence's one condition: the lead's under it, the rest as a numbered list
under the row, each linked to the photograph's page on iNaturalist, which
states its licence. A photograph with no credit is not shown at all, the rule
``static_site.photo_credit`` holds. No script, like the rest of the site.

Split from ``static_site_species.py`` and ``static_site_render.py``, both at
their line ceilings.
"""

from __future__ import annotations

from src.photo_picks import SLOT_WORDS, photo_page
from src.static_site_render import _esc, _photo_img, _up

NO_PHOTO = ('<p class="note">No openly-licensed photograph of this species is '
            'in the catalogue yet. We show a photo only when we can credit the '
            'photographer.</p>')


def credited(entry: dict) -> list:
    """The photographs a page may show, in order: each with a URL and a
    credit. The first is ``static_site._first_photo``'s."""
    return [p for p in entry.get("photos") or []
            if (p.get("url") or "").strip()
            and (p.get("attribution") or "").strip()]


def _credit_text(photo: dict) -> str:
    from src.image_cache import credit_line                  # noqa: PLC0415
    line = credit_line(photo.get("attribution") or "", photo.get("license") or "")
    page = photo_page(photo.get("url") or "")
    return (f'<a href="{_esc(page)}">{_esc(line)}</a>' if page
            else _esc(line))


def _src(photo: dict, depth: int, photo_src: dict) -> str:
    url = (photo.get("url") or "").strip()
    src = photo_src.get(url, url)
    return src if src.startswith(("http://", "https://")) else _up(depth) + src


def gallery_html(entry: dict, depth: int, photo_src: dict) -> str:
    """The lead photograph with its credit, then the rest as linked
    thumbnails with a numbered credit each; the no-photograph note when
    there is nothing that may be shown."""
    photos = credited(entry)
    if not photos:
        return NO_PHOTO
    name = entry.get("name") or ""
    lead = photos[0]
    out = [f'<figure class="hero-photo">{_photo_img(lead, depth, photo_src, name)}'
           f'<p class="credit">{_credit_text(lead)}</p></figure>']
    rest = photos[1:]
    if rest:
        items = []
        for n, photo in enumerate(rest, 2):
            words = SLOT_WORDS.get(photo.get("slot") or "", "")
            alt = f"{name}, photo {n}" + (f": {words}" if words else "")
            items.append(
                f'<li><a href="{_esc(_src(photo, depth, photo_src))}">'
                f'{_photo_img(photo, depth, photo_src, alt)}</a></li>')
        credits = "".join(f'<li class="credit">{_credit_text(p)}</li>'
                          for p in rest)
        out.append(f'<ul class="photo-strip">{"".join(items)}</ul>'
                   f'<ol class="photo-credits" start="2">{credits}</ol>')
    return "".join(out)
