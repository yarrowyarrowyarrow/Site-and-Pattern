"""
static_site_render.py — the page model of :mod:`src.static_site`, as HTML.

Design principle P5 — see docs/DESIGN_PHILOSOPHY.md.

Plain files: no framework, no build step, no CDN, no external request of any
kind. That is the discipline ``html/`` already follows for the map and the 3D
viewer, and here it also means the site keeps working when a CDN does not and
can be read straight off a disk with ``file://``.

**One opt-in exception, since V2.71:** ``write_site`` can embed a page-view
counter so the site's owner can find out whether anyone is reading it. Off
unless asked for, disclosed in the footer of every page it appears on, and
limited to scripts that set no cookie and keep no per-visitor identifier.
Everything above still holds for a build without it, which is the default.
The vocabulary, the validation and the footer sentence live in
:mod:`src.site_analytics`; this module holds one value and asks it things.
V2.73 added a second provider (Umami, which keeps history where Cloudflare's
free tier keeps a day), and the two can be on together.

Links are **relative**, computed per page from its depth, so the output can be
published at a domain root, in a subdirectory, or opened locally without a
server. Root-relative ``/plants/...`` would have been shorter and would break
two of those three.

The browse page filters **client-side** over an embedded JSON index, across
every axis in :mod:`src.site_facets`. It is the one piece of interactivity here
and it degrades to a plain list with JavaScript off.

The stylesheet and that script live in ``html/site/`` as real ``.css`` and
``.js`` files rather than as Python string constants. They were constants until
they took this module 190 lines over its ceiling, and the guard was right: CSS
embedded in a ``.py`` is CSS nobody can lint, highlight or diff sensibly.

**No em dashes anywhere in the output**, on the author's instruction. A colon, a
comma or a full stop does the same work. ``tests/test_static_site.py`` fails the
build if one reaches a rendered page, because prose written later will not
remember the rule.
"""

from __future__ import annotations

import html
import json
import os
import pathlib
import shutil
from typing import Callable, Optional

from src.site_analytics import Analytics, NONE as ANALYTICS_NONE, configure
from src.site_facets import FACETS, GROUPS
from src.static_site import _first_photo

#: Plain text, never pre-escaped: everything here goes through ``_esc`` at the
#: point of use. Storing the entity form instead produced ``&amp;amp;`` in every
#: page title, because the ``<title>`` path escapes and the header path did not.
#: The website's own name, which is NOT the desktop app's.
#:
#: The app is Site & Pattern and stays that way: `src/branding.py` owns it, the
#: installer carries it, and the user data folder is named after it. The public
#: catalogue got its own domain in V2.70 and is named for what somebody typing
#: it into a phone is trying to do. Two products from one catalogue, and the
#: only thing they need to share is the data.
SITE_NAME = "GrowNativePlants"
SITE_SUB = "Plant Directory"
TAGLINE = ("Native plants of Alberta and Saskatchewan, and the "
           "animals that depend on them.")

#: Every nav target is a page ``write_site`` emits unconditionally. Linking the
#: hub directories from here instead put ``plants/ecoregion/`` in the header of
#: all 595 pages and then skipped writing it whenever no species carried an
#: ecoregion tag: 46 dead links in the header, on a catalogue one column
#: different from the shipped one. The browse axes are reached from the home
#: page and the map page, both of which build their links from the model and so
#: cannot outrun it.
_NAV = (("plants/", "Plants"), ("map/", "Ecoregions"),
        ("wildlife/", "Wildlife"), ("method/", "Method"), ("about/", "About"))

#: What this build phones home to, if anything (V2.71; a second provider in
#: V2.73). Off by default and set for the length of one ``write_site`` call:
#: it is a property of the *publish*, not of any page, and threading it through
#: `_page`'s fifteen call sites in five modules to say one thing would be worse.
#:
#: Turning it on is the single exception to this module's "no external request
#: of any kind" rule. What that exception costs — opt-in, validated rather than
#: pasted into 2,000 pages, no cookie, no per-visitor identifier, and disclosed
#: in the footer of every page it appears on — is enforced in
#: :mod:`src.site_analytics`, which is also where a third provider would go.
_ANALYTICS: Analytics = ANALYTICS_NONE


def _beacon() -> str:
    """The analytics script tags, or ``""``. Never emitted unless asked for."""
    return _ANALYTICS.tags()


def _privacy_line() -> str:
    """The footer's disclosure of those tags, or ``""``."""
    return _ANALYTICS.disclosure()


def _asset(name: str) -> str:
    """The text of ``html/site/<name>``.

    Resolved through :func:`src.resources.resource_path` so it works from a
    source checkout and from a frozen bundle alike, the same route
    ``web_assets`` takes to ``html/``.
    """
    from src.resources import resource_path                    # noqa: PLC0415
    return pathlib.Path(resource_path("html", "site", name)).read_text(
        encoding="utf-8")


#: Em dash, and the double hyphen people type when they mean one. Replaced
#: rather than banned at the keyboard because most of the text on this site
#: comes out of the database, where the author of a safety note in 2026 cannot
#: be asked to remember a house style set in 2027. Applied in ``_esc``, which
#: every user-visible string already passes through, so there is exactly one
#: place to get it right and no way to route around it.
#:
#: A colon does the job of an em dash that introduces a clause, and the strings
#: this hits are overwhelmingly of that shape ("Toxicity not assessed, absence
#: of a warning is not a guarantee"). En dashes inside numeric ranges are left
#: alone: "Jun-Jul" and "pH 5.5-7" are a different mark doing a different job.
_DASHES = ((" — ", ", "), ("—", ", "), (" -- ", ", "))


def _nodash(text: str) -> str:
    for bad, good in _DASHES:
        if bad in text:
            text = text.replace(bad, good)
    # A dash swapped for a comma next to punctuation that already separates.
    return text.replace(" ,", ",").replace(",,", ",").replace(": ,", ": ")


def _esc(text) -> str:
    return html.escape(_nodash(str(text if text is not None else "")),
                       quote=True)


def _up(depth: int) -> str:
    return "../" * depth


# ── The shell ────────────────────────────────────────────────────────────────

def _page(title: str, description: str, body: str, depth: int,
          *, wide: bool = False, scripts: str = "") -> str:
    root = _up(depth)
    nav = "".join(f'<a href="{root}{href}">{label}</a>' for href, label in _NAV)
    return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{_esc(title)}</title>
<meta name="description" content="{_esc(description)}">
<link rel="stylesheet" href="{root}assets/site.css">
</head>
<body>
<a class="skip" href="#main">Skip to content</a>
<header class="top">
  <a class="brand" href="{root}">
    <span class="brand-mark" aria-hidden="true"></span>
    <span class="brand-name">{_esc(SITE_NAME)}</span>
    <span class="brand-sub">{_esc(SITE_SUB)}</span>
  </a>
  <nav aria-label="Sections">{nav}</nav>
</header>
<main id="main" class="{'wide' if wide else ''}">
{body}
</main>
<footer class="foot">
  <div class="foot-inner">
    <p class="foot-lede">{_esc(TAGLINE)}</p>
    <p>Generated from an <a href="https://github.com/yarrowyarrowyarrow/Site-and-Pattern">open
    catalogue</a> of native plants. Photographs are open-licensed and credited
    individually to their photographers. Every other figure carries its source
    on the page it appears on, and where a fact is unknown the page says so
    rather than filling the gap.</p>
    <p>This catalogue records horticultural and ecological information only. It
    contains no Indigenous ecological knowledge, plant-use tradition or
    land-management practice, and none should be inferred from it.</p>{_privacy_line()}
  </div>
</footer>
{scripts}{_beacon()}
</body>
</html>
"""


def _crumb(items: list, depth: int) -> str:
    root = _up(depth)
    parts = [f'<a href="{root}{href}">{_esc(label)}</a>' if href else
             f"<span>{_esc(label)}</span>" for href, label in items]
    return ('<nav class="crumb" aria-label="Breadcrumb">'
            + '<span class="sep">/</span>'.join(parts) + "</nav>")


# ── Pieces ───────────────────────────────────────────────────────────────────

def _photo_img(photo: dict, depth: int, photo_src: dict, alt: str) -> str:
    """An ``<img>``, or ``""``. A photo with no attribution never reaches here:
    see :func:`src.static_site.photo_credit`."""
    url = (photo.get("url") or "").strip()
    if not url:
        return ""
    src = photo_src.get(url, url)
    if not src.startswith(("http://", "https://")):
        src = _up(depth) + src
    return f'<img src="{_esc(src)}" alt="{_esc(alt)}" loading="lazy">'


def _credit(photo: dict) -> str:
    from src.image_cache import credit_line
    line = credit_line(photo.get("attribution") or "", photo.get("license") or "")
    return f'<p class="credit">{_esc(line)}</p>' if line else ""


def _swatch(hex_value: str) -> str:
    return (f'<span class="dot" style="background:{_esc(hex_value)}"></span>'
            if hex_value else "")


def _card(brief: dict, depth: int, photo_src: dict) -> str:
    root = _up(depth)
    from src.flower_colour import COLOUR_SWATCHES               # noqa: PLC0415
    img = ""
    url = (brief.get("image") or "").strip()
    if url:
        src = photo_src.get(url, url)
        if not src.startswith(("http://", "https://")):
            src = root + src
        # The credit rides on the image itself. A card has no room for a caption
        # and a CC BY photo still has to say who took it, so it goes in `title`
        # (hover) and `alt` (assistive tech) rather than being dropped.
        credit = brief.get("credit") or ""
        img = (f'<img src="{_esc(src)}" alt="{_esc(credit)}" '
               f'title="{_esc(credit)}" loading="lazy">')
    else:
        img = '<span class="nophoto" aria-hidden="true"></span>'
    dot = _swatch(COLOUR_SWATCHES.get(brief.get("colour") or "", ""))
    bloom = _esc(brief.get("bloom") or "")
    star = (' <span class="star" title="Feeds a specialist">&#9733;</span>'
            if brief.get("specialist") else "")
    return (
        f'<a class="card" href="{root}plants/{_esc(brief["slug"])}/">'
        f'<span class="thumb">{img}</span>'
        f'<span class="cardbody">'
        f'<strong>{_esc(brief.get("name"))}{star}</strong>'
        f'<em>{_esc(brief.get("sci") or "")}</em>'
        f'<span class="meta">{dot}{_esc(brief.get("type") or "")}'
        f'{" &middot; " + bloom if bloom else ""}</span>'
        f"</span></a>")


def _grid(briefs: list, depth: int, photo_src: dict, gid: str = "") -> str:
    if not briefs:
        return '<p class="empty">Nothing in the catalogue matches this yet.</p>'
    cards = "".join(_card(b, depth, photo_src) for b in briefs)
    ident = f' id="{gid}"' if gid else ""
    return f'<div class="grid"{ident}>{cards}</div>'


# ── Pages ────────────────────────────────────────────────────────────────────

def render_home(model: dict, photo_src: dict) -> str:
    from src.ecoregion_map import (CAVEAT, frame_height,        # noqa: PLC0415
                                   map_svg)
    s = model["stats"]
    hubs = {h["key"]: h for h in model["hubs"]}

    def chips(key: str, folder: str, limit: int = 0) -> str:
        hub = hubs.get(key)
        if not hub:
            return ""
        pages = hub["pages"][:limit] if limit else hub["pages"]
        return "".join(
            f'<a class="chip" href="{folder}/{_esc(p["slug"])}/">'
            f'{_swatch(p["swatch"])}{_esc(p["name"])}'
            f'<span class="n">{len(p["plants"])}</span></a>' for p in pages)

    # Link only regions that actually got a page. The geojson carries every
    # region the vocabulary knows; the hub carries the ones some plant is filed
    # under, and those are not always the same set.
    eco_pages = {p["value"]: p["slug"]
                 for p in hubs.get("ecoregion", {}).get("pages", [])}
    eco = map_svg(width=520, height=frame_height(520), reference=True,
                  link_for=lambda k: (f"plants/ecoregion/{eco_pages[k]}/"
                                      if k in eco_pages else ""))

    body = f"""
<section class="hero">
  <p class="kicker">A reference work for Alberta and Saskatchewan</p>
  <h1>{s['species']} native plants, and the {s['animals']} animals
  documented to use them.</h1>
  <p class="lede">{_esc(TAGLINE)} Every relationship here is a
  <strong>documented</strong> record with a source.</p>
  <p class="cta">
    <a class="button" href="plants/">Search all {s['species']} plants</a>
    <a class="button ghost" href="wildlife/">Start from an animal</a>
  </p>
  <dl class="figures">
    <div><dt>Species</dt><dd>{s['species']}</dd></div>
    <div><dt>Documented relationships</dt><dd>{s['edges']}</dd></div>
    <div><dt>Searchable fields</dt><dd>{s['facets']}</dd></div>
    <div><dt>With a credited photograph</dt><dd>{s['with_photo']}</dd></div>
  </dl>
</section>

<section class="split">
  <div>
    <h2>Where things grow</h2>
    <p>Pick a region to see the plants recorded there. Every species page
    carries this map too, with each region shaded when the plant has been
    recorded somewhere inside it.</p>
    <p class="note">These are ecoregions, not range maps: a shaded region
    means records exist in it, not that the plant grows throughout it.
    {_esc(CAVEAT)} <a href="method/">How this is made</a>.</p>
    <p><a class="more" href="map/">The full map</a></p>
  </div>
  <figure class="mapfig">{eco}</figure>
</section>

<section>
  <h2>By flower colour</h2>
  <p>Pick a colour to see the plants that bloom in it.</p>
  <div class="chips">{chips("colour", "plants/colour")}</div>
</section>

<section>
  <h2>By bloom month</h2>
  <div class="chips">{chips("bloom", "plants/blooming-in")}</div>
</section>

<section>
  <h2>By what it does</h2>
  <div class="chips">{chips("role", "plants/for")}</div>
</section>

<section>
  <h2>By growth form</h2>
  <div class="chips">{chips("type", "plants/type")}</div>
</section>

<section class="pitch">
  <h2>Start from the animal instead</h2>
  <p>Most plant catalogues tell you what a plant looks like. This one also
  tells you which caterpillars eat it, which bees feed on it, and which of them
  have no alternative.</p>
  <p><a class="button" href="wildlife/">{s['animals']} animals</a></p>
</section>
"""
    return _page(f"{s['species']} native plants of Alberta and Saskatchewan",
                 TAGLINE, body, 0)


def render_browse(model: dict, photo_src: dict) -> str:
    """The search page: every facet, filtered in the browser."""
    briefs = [e["brief"] for e in model["species"]]
    index = [dict(e["facets"], s=e["slug"],
                  n=(e["brief"]["name"] + " " + e["brief"]["sci"]).lower())
             for e in model["species"]]
    # `</script>` inside the payload would close the block early and spill JSON
    # into the document. No botanical name does that today, but the index is
    # built from free-text database columns and one day one of them will.
    payload = json.dumps(index, separators=(",", ":")).replace("<", "\\u003c")

    # Values the catalogue can actually answer. The hub pages have always
    # pruned on this rule — "a value nothing matches gets no page rather than
    # an empty one, because an empty page is a URL that reads as a fact about
    # the flora when it is a fact about the catalogue" — but the sidebar
    # rendered every option regardless, so the two disagreed. It went unnoticed
    # while the vocabularies were small and complete; V2.68 took the ecoregion
    # facet from 6 values to 32, of which the catalogue currently answers 4,
    # and 28 dead checkboxes is a filter that mostly returns nothing.
    in_use = {facet.key: {v for e in model["species"]
                          for v in (e["facets"].get(facet.key) or [])}
              for facet in FACETS}

    panels = []
    for group in GROUPS:
        facets = [f for f in FACETS if f.group == group]
        if not facets:
            continue
        blocks = []
        for facet in facets:
            opts = "".join(
                f'<label><input type="checkbox" data-f="{_esc(facet.key)}" '
                f'value="{_esc(value)}">{_swatch(facet.swatches.get(value, ""))}'
                f'<span>{_esc(label)}</span></label>'
                for value, label in facet.options
                if value in in_use[facet.key])
            # A facet note may name a count, and if it does the count comes
            # from the build rather than from the source (V2.75): the photo
            # note read "323 of 434" while the About page computed the same
            # sentence, so one site contradicted itself on two pages.
            text = facet.note
            if text and "{" in text:
                try:
                    text = text.format(**model["stats"])
                except (KeyError, IndexError, ValueError) as exc:
                    raise ValueError(
                        f"facet {facet.key!r} note names a statistic the "
                        f"build does not compute: {exc}") from exc
            note = f'<p class="fnote">{_esc(text)}</p>' if text else ""
            blocks.append(
                f'<details class="facet" data-facet="{_esc(facet.key)}" '
                f'data-combine="{_esc(facet.combine)}">'
                f'<summary>{_esc(facet.label)}'
                f'<span class="on" hidden></span></summary>'
                f'{note}<div class="opts">{opts}</div></details>')
        panels.append(f'<section class="fgroup"><h3>{_esc(group)}</h3>'
                      f'<div class="facets">{"".join(blocks)}</div></section>')

    body = f"""
{_crumb([("", "Plants")], 1)}
<div class="searchhead">
  <h1>Search {len(briefs)} plants</h1>
  <p class="lede">Every filter runs in your browser, with no page reload.
  A plant that records nothing for a filter is left out of it rather than
  guessed at.</p>
</div>

<div class="searchlayout">
  <form class="filters" id="filters" onsubmit="return false"
        aria-label="Filters">
    <div class="fhead">
      <div class="fbar">
        <input type="search" id="q" placeholder="Name or botanical name"
               autocomplete="off" aria-label="Search by name">
        <button type="button" id="clear" hidden>Clear</button>
      </div>
      <p class="count" id="count" role="status">{len(briefs)} plants</p>
      <div id="active" class="active"></div>
    </div>
    <div class="fscroll">{"".join(panels)}</div>
  </form>

  <div class="results">
    <noscript><p class="note">Filtering needs JavaScript. The full list is
    below.</p></noscript>
    {_grid(briefs, 1, photo_src, gid="results")}
    <p class="empty" id="noresults" hidden>No plant matches all of those.
    Try removing a filter.</p>
  </div>
</div>
<script id="catalogue" type="application/json">{payload}</script>
"""
    return _page(f"Search {len(briefs)} native plants", TAGLINE, body, 1,
                 wide=True,
                 scripts=f'<script src="{_up(1)}assets/browse.js"></script>')


def render_hub_index(hub: dict, depth: int, crumb: list) -> str:
    chips = "".join(
        f'<a class="chip" href="{_esc(p["slug"])}/">{_swatch(p["swatch"])}'
        f'{_esc(p["name"])}<span class="n">{len(p["plants"])}</span></a>'
        for p in hub["pages"])
    note = f'<p class="note">{_esc(hub["note"])}</p>' if hub.get("note") else ""
    title = f"Plants by {hub['label'].lower()}"
    body = f"""
{_crumb(crumb, depth)}
<h1>{_esc(title)}</h1>
<p class="lede">{_esc(hub.get("blurb") or "")}</p>
{note}
<div class="chips big">{chips}</div>
"""
    return _page(f"{title} | {SITE_NAME}", hub.get("blurb") or title, body, depth)


def render_listing(page: dict, depth: int, photo_src: dict, crumb: list,
                   extra: str = "") -> str:
    n = len(page["plants"])
    swatch = (f'<span class="dot big" style="background:'
              f'{_esc(page["swatch"])}"></span>' if page.get("swatch") else "")
    note = f'<p class="note">{_esc(page["note"])}</p>' if page.get("note") else ""
    body = f"""
{_crumb(crumb, depth)}
<h1>{swatch}{_esc(page["title"])}</h1>
<p class="lede">{_esc(page.get("intro") or "")}</p>
{note}
{extra}
<p class="count">{n} {"plant" if n == 1 else "plants"}</p>
{_grid(page["plants"], depth, photo_src)}
"""
    return _page(f'{page["title"]} | {SITE_NAME}',
                 f'{n} species. {page.get("intro") or ""}', body, depth,
                 wide=True)


# ── Writing it out ───────────────────────────────────────────────────────────

def write_site(model: dict, out_dir: str, *,
               base_url: str = "",
               copy_photos: bool = True,
               include_notes: bool = False,
               analytics_token: str = "",
               umami_website_id: str = "",
               umami_src: str = "",
               progress: Optional[Callable] = None) -> dict:
    """Render ``model`` into ``out_dir``. Returns a summary dict.

    ``out_dir`` is created if absent and written into, never emptied: a
    generator that deletes a directory the user pointed at is one bad argument
    away from removing something else.

    ``analytics_token`` (Cloudflare Web Analytics) and ``umami_website_id``
    (+ optional ``umami_src`` for a self-hosted instance or the EU region) opt
    this build into a page-view counter; see :mod:`src.site_analytics`. Either,
    both or neither. Neither means no analytics and no external request, which
    is the default and the state every build before V2.71 was in. A malformed
    value raises rather than being written into 2,000 pages.
    """
    # Imported here, not at module scope: static_site_species imports the shell
    # and the shared pieces back from this module, so a top-level import would
    # be a cycle. Two pages needed splitting out: the species page, and (V2.65)
    # the About page, once publishing the 114-work bibliography took this
    # module past its 800-line ceiling.
    # V2.68 adds a third: the pages about *places*, once the ecoregion map
    # became a three-level drill-down. Same seam, same cycle, same fix.
    from src.static_site_about import render_about           # noqa: PLC0415
    from src.static_site_method import render_method         # noqa: PLC0415
    from src.static_site_regions import (_hub_extra,         # noqa: PLC0415
                                         render_map_page, render_subregion)
    from src.static_site_species import render_species       # noqa: PLC0415
    # V2.71 adds a fourth: the wildlife index became a filtered search rather
    # than a wall of chips, and carries its own facet vocabulary.
    from src.static_site_wildlife import (render_wildlife,   # noqa: PLC0415
                                          render_wildlife_index)

    global _ANALYTICS
    # Validated before anything is written, and set unconditionally — never
    # restored afterwards. Restoring on the way out would leak the previous
    # build's configuration if a build raised half way; assigning on the way IN
    # cannot, because the next build's own arguments overwrite it whatever
    # happened to the last one. Fail-closed for the value that decides whether
    # a page phones home.
    _ANALYTICS = configure(cloudflare_token=analytics_token,
                           umami_website_id=umami_website_id,
                           umami_src=umami_src)

    say = progress or (lambda _m: None)
    root = pathlib.Path(out_dir)
    root.mkdir(parents=True, exist_ok=True)
    photo_src = _stage_photos(model, root, say) if copy_photos else {}
    written: list = []

    def emit(rel: str, text: str) -> None:
        path = root / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
        written.append(rel)

    emit("assets/site.css", _asset("site.css"))
    emit("assets/browse.js", _asset("browse.js"))
    emit("index.html", render_home(model, photo_src))
    emit("about/index.html", render_about(model))
    emit("method/index.html", render_method(model))
    emit("map/index.html", render_map_page(model))
    emit("plants/index.html", render_browse(model, photo_src))

    for entry in model["species"]:
        emit(f"plants/{entry['slug']}/index.html",
             render_species(entry, model, photo_src, include_notes))
    say(f"{len(model['species'])} species pages")

    for hub in model["hubs"]:
        depth = hub["dir"].count("/") + 1
        title = f"Plants by {hub['label'].lower()}"
        emit(f"{hub['dir']}/index.html",
             render_hub_index(hub, depth,
                              [("plants/", "Plants"), ("", title)]))
        for page in hub["pages"]:
            emit(f"{hub['dir']}/{page['slug']}/index.html",
                 render_listing(page, depth + 1, photo_src,
                                [("plants/", "Plants"),
                                 (f"{hub['dir']}/", title),
                                 ("", page["name"])],
                                extra=_hub_extra(hub, page, model)))
    say(f"{sum(len(h['pages']) for h in model['hubs'])} listing pages "
        f"across {len(model['hubs'])} axes")

    emit("wildlife/index.html",
         render_wildlife_index(model, len(model["wildlife"]),
                               int(model.get("total_fauna") or 0), photo_src))
    for animal in model["wildlife"]:
        emit(f"wildlife/{animal['slug']}/index.html",
             render_wildlife(animal, photo_src))
    say(f"{len(model['wildlife'])} wildlife pages")

    for sub in model.get("subregions") or []:
        emit(f'plants/subregion/{sub["slug"]}/index.html',
             render_subregion(sub, photo_src))
    if model.get("subregions"):
        say(f'{len(model["subregions"])} subregion pages')

    emit("assets/catalogue.json", json.dumps(
        [e["brief"] for e in model["species"]], indent=1))
    emit("sitemap.xml", _sitemap(written, base_url))
    emit("robots.txt", _robots(base_url))
    domain = _custom_domain(base_url)
    if domain:
        emit("CNAME", domain + "\n")
    # GitHub Pages runs Jekyll over a published folder unless this file exists,
    # which silently drops anything whose name starts with an underscore. The
    # site has no such paths today, so the failure would not appear until one
    # was added — and then as a 404 on a page that renders perfectly locally.
    # It was in the published branch as a file somebody had remembered to add
    # by hand; a build output should not depend on that.
    emit(".nojekyll", "")

    copied = sum(1 for v in photo_src.values() if not v.startswith("http"))
    return {"out_dir": str(root),
            "analytics": bool(_ANALYTICS),
            # Named, not just counted: "did this build have analytics in it"
            # and "which one" are different questions, and the second became
            # a real one the moment there were two providers.
            "analytics_providers": _ANALYTICS.providers(),
            # Pages plus the photo files staged beside them: the number the
            # operator is about to upload, not just the number rendered.
            "files": len(written) + copied,
            "pages": len(written),
            "species": len(model["species"]),
            "wildlife": len(model["wildlife"]),
            "listings": sum(len(h["pages"]) for h in model["hubs"]),
            "photos_copied": copied,
            "photos_hotlinked": sum(1 for v in photo_src.values()
                                    if v.startswith("http"))}


def _stage_photos(model: dict, root: pathlib.Path, say: Callable) -> dict:
    """``{recorded url: path used}``.

    Prefers bytes already in the local image cache and copies them into
    ``assets/photos/``; falls back to the recorded URL when the cache is cold.
    ``get_cached_image`` never touches the network, so a cold cache degrades to
    links rather than turning a site build into 300 downloads.

    Both counts are reported at the end of the build, because "the site
    published with 321 hotlinks to iNaturalist" is something the operator should
    find out before uploading rather than when the CDN changes.

    Animals are staged into ``assets/photos/wildlife/`` (V2.71). Their own
    subfolder rather than the same one: species slugs and animal slugs are each
    unique within their own set and nothing makes them unique across both, so
    one flat folder is a filename collision waiting for the first plant and
    insect that share a common name.
    """
    from src.image_cache import get_cached_image
    dest = root / "assets" / "photos"
    (dest / "wildlife").mkdir(parents=True, exist_ok=True)
    out: dict = {}

    def stage(slug: str, url: str, folder: str) -> None:
        if not url or url in out:
            return
        # Named for the species, so the staged file is identifiable on disk and
        # stable across rebuilds. Slugs are unique, so filenames are too.
        local = get_cached_image(url)
        if local and os.path.exists(local):
            name = f"{slug}{os.path.splitext(local)[1] or '.jpg'}"
            try:
                shutil.copyfile(local, dest / folder / name if folder
                                else dest / name)
                out[url] = (f"assets/photos/{folder}/{name}" if folder
                            else f"assets/photos/{name}")
                return
            except OSError:
                pass
        out[url] = url

    for entry in model["species"]:
        stage(entry["slug"], (_first_photo(entry).get("url") or "").strip(), "")
    for animal in model.get("wildlife") or []:
        stage(animal["slug"], (animal.get("image") or "").strip(), "wildlife")

    copied = sum(1 for v in out.values() if not v.startswith("http"))
    say(f"photos: {copied} copied from cache, {len(out) - copied} left as links")
    return out


def _sitemap(written: list, base_url: str) -> str:
    base = (base_url or "").rstrip("/")
    urls = []
    for rel in sorted(written):
        if not rel.endswith("index.html"):
            continue
        loc = rel[: -len("index.html")]
        urls.append(f"  <url><loc>{_esc(base + '/' + loc)}</loc></url>")
    return ('<?xml version="1.0" encoding="UTF-8"?>\n'
            '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
            + "\n".join(urls) + "\n</urlset>\n")


def _custom_domain(base_url: str) -> str:
    """The bare host to write into ``CNAME``, or ``""`` for a github.io URL.

    **GitHub Pages keeps a custom domain in a file at the root of the published
    branch**, and this publish replaces that branch's contents wholesale. So a
    CNAME added by hand in the Pages settings survives exactly until the next
    time the site is rebuilt, and then the domain silently reverts to
    ``*.github.io`` with the custom one 404ing. There is no error and nothing in
    the build output to notice.

    Derived from ``base_url`` rather than taken as its own flag, on the rule
    this codebase keeps relearning: two settings that must agree, set
    separately, do not stay in agreement. "The site is served from
    https://grownativeplants.ca/" already says what the domain is.

    A ``*.github.io`` base URL writes no CNAME, which is correct — that is the
    default domain and a CNAME naming it would be GitHub redirecting to itself.
    """
    from urllib.parse import urlparse                          # noqa: PLC0415

    host = (urlparse(base_url or "").hostname or "").strip().lower()
    if not host or host.endswith(".github.io") or host == "localhost":
        return ""
    return host


def _robots(base_url: str) -> str:
    base = (base_url or "").rstrip("/")
    line = f"Sitemap: {base}/sitemap.xml\n" if base else ""
    return f"User-agent: *\nAllow: /\n{line}"
