"""
static_site_render.py — the page model of :mod:`src.static_site`, as HTML.

Design principle P5 — see docs/DESIGN_PHILOSOPHY.md.

Plain files: no framework, no build step, no CDN, no external request of any
kind. That is the discipline ``html/`` already follows for the map and the 3D
viewer, and here it also means the site keeps working when a CDN does not and
can be read straight off a disk with ``file://``.

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

from src.site_facets import FACETS, GROUPS
from src.static_site import TAXON_GROUPS, _first_photo

#: Plain text, never pre-escaped: everything here goes through ``_esc`` at the
#: point of use. Storing the entity form instead produced ``&amp;amp;`` in every
#: page title, because the ``<title>`` path escapes and the header path did not.
SITE_NAME = "Site & Pattern"
SITE_SUB = "Plant Directory"
TAGLINE = ("Native plants of Alberta and the Canadian prairies, and the "
           "animals that depend on them.")

#: Every nav target is a page ``write_site`` emits unconditionally. Linking the
#: hub directories from here instead put ``plants/ecoregion/`` in the header of
#: all 595 pages and then skipped writing it whenever no species carried an
#: ecoregion tag: 46 dead links in the header, on a catalogue one column
#: different from the shipped one. The browse axes are reached from the home
#: page and the map page, both of which build their links from the model and so
#: cannot outrun it.
_NAV = (("plants/", "Plants"), ("map/", "Ecoregions"),
        ("wildlife/", "Wildlife"), ("about/", "About"))


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
    <p>Generated from the <a href="https://github.com/yarrowyarrowyarrow/Site-and-Pattern">Site
    and Pattern</a> catalogue. Photographs are open-licensed and credited
    individually to their photographers. Every other figure carries its source
    on the page it appears on, and where a fact is unknown the page says so
    rather than filling the gap.</p>
    <p>This catalogue records horticultural and ecological information only. It
    contains no Indigenous ecological knowledge, plant-use tradition or
    land-management practice, and none should be inferred from it.</p>
  </div>
</footer>
{scripts}
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
    from src.ecoregion_map import CAVEAT, map_svg               # noqa: PLC0415
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
    eco = map_svg({k: "medium" for k in eco_pages}, width=520, height=330,
                  link_for=lambda k: (f"plants/ecoregion/{eco_pages[k]}/"
                                      if k in eco_pages else ""))

    body = f"""
<section class="hero">
  <p class="kicker">A reference work for prairie habitat</p>
  <h1>{s['species']} native and prairie-hardy plants, and the {s['animals']}
  animals documented to use them.</h1>
  <p class="lede">{_esc(TAGLINE)} Every relationship here is a
  <strong>documented</strong> record with a source: {s['edges']} of them, of
  which {s['specialist_edges']} involve an animal that has nowhere else to
  go.</p>
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
    <p>Each region below is a page. On a species page the same map is shaded to
    show where that plant has actually been recorded, with the occurrence count
    and confidence behind every region.</p>
    <p class="note">{_esc(CAVEAT)}</p>
    <p><a class="more" href="map/">The full map</a></p>
  </div>
  <figure class="mapfig">{eco}</figure>
</section>

<section>
  <h2>By flower colour</h2>
  <p>Grasses and sedges have a bucket of their own. They are wind-pollinated,
  so what you see is the seed head, not a bloom, and filing them under yellow
  would claim something the data does not say.</p>
  <div class="chips">{chips("colour", "plants/colour")}</div>
</section>

<section>
  <h2>By bloom month</h2>
  <p>A species with no recorded bloom window is listed under no month. We do not
  know when it flowers, and that is not the same as knowing it does not flower
  then.</p>
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
  <p>Most plant catalogues can tell you what a plant looks like. This one can
  tell you which caterpillars eat it, which bees can physically reach its
  nectar, and which of them have no alternative, because the catalogue is built
  on the relationships rather than on the plants.</p>
  <p><a class="button" href="wildlife/">{s['animals']} animals</a></p>
</section>
"""
    return _page(f"{s['species']} native plants of Alberta and the prairies",
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
                for value, label in facet.options)
            note = (f'<p class="fnote">{_esc(facet.note)}</p>'
                    if facet.note else "")
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
    return _page(f"Search {len(briefs)} native prairie plants", TAGLINE, body, 1,
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


def render_map_page(model: dict) -> str:
    from src.ecoregion_map import CAVEAT, map_svg               # noqa: PLC0415
    hub = {h["key"]: h for h in model["hubs"]}.get("ecoregion", {"pages": []})
    pages = {p["value"]: p["slug"] for p in hub["pages"]}
    svg = map_svg({k: "medium" for k in pages}, width=760, height=470,
                  link_for=lambda k: (f"../plants/ecoregion/{pages[k]}/"
                                      if k in pages else ""))
    rows = "".join(
        f'<li><a href="../plants/ecoregion/{_esc(p["slug"])}/">'
        f'<strong>{_esc(p["name"])}</strong></a> '
        f'<span class="src">{len(p["plants"])} species</span></li>'
        for p in hub["pages"])
    body = f"""
{_crumb([("", "Ecoregion map")], 1)}
<h1>The ecoregions</h1>
<p class="lede">Alberta and Saskatchewan divided into the six regions this
catalogue records ranges against. Click a region for its plants.</p>
<figure class="mapfig wide-map">{svg}</figure>
<p class="note">{_esc(CAVEAT)}</p>
<ul class="ranges cols">{rows}</ul>
"""
    return _page(f"Ecoregion map | {SITE_NAME}",
                 "The prairie ecoregions this catalogue records plant ranges "
                 "against.", body, 1, wide=True)


def render_wildlife_index(model: dict, listed: int, total_fauna: int) -> str:
    blocks = []
    for taxon, heading in TAXON_GROUPS:
        animals = [a for a in model["wildlife"] if a["taxon"] == taxon]
        if not animals:
            continue
        links = "".join(
            f'<a class="chip" href="{_esc(a["slug"])}/">{_esc(a["name"])}'
            f'<span class="n">{a["total"]}</span></a>' for a in animals)
        blocks.append(f'<section><h2>{_esc(heading)} '
                      f'<span class="n">{len(animals)}</span></h2>'
                      f'<div class="chips">{links}</div></section>')
    omitted = total_fauna - listed
    note = ""
    if omitted > 0:
        note = (f'<p class="note">{omitted} more animals are in the catalogue '
                f'with no plant relationship documented yet. They are not '
                f'listed here, because a page reading "0 plants support this '
                f'species" would publish a fact about our coverage as though '
                f'it were a fact about the animal.</p>')
    body = f"""
{_crumb([("", "Wildlife")], 1)}
<h1>{listed} animals, and the plants that support them</h1>
<p class="lede">Each relationship below is a documented record with a source,
not an inference. A star marks a specialist: an animal that cannot simply move
to another plant.</p>
{note}
{"".join(blocks)}
"""
    return _page("Wildlife of the prairies and the plants they need",
                 "Native bees, butterflies, moths, birds and mammals, and the "
                 "documented plants each one depends on.", body, 1)


def render_wildlife(animal: dict, photo_src: dict) -> str:
    depth = 2
    blocks = []
    for group in animal["groups"]:
        blocks.append(f'<h2>{_esc(group["how"])}</h2>'
                      f'{_grid(group["items"], depth, photo_src)}')
    spec = animal["specialists"]
    lede = (f'{animal["total"]} documented plant '
            f'{"relationship" if animal["total"] == 1 else "relationships"}'
            + (f', {spec} of them as a specialist with no alternative'
               if spec else "") + ".")
    notes = f'<p>{_esc(animal["notes"])}</p>' if animal.get("notes") else ""
    body = f"""
{_crumb([("wildlife/", "Wildlife"), ("", animal["name"])], depth)}
<h1>{_esc(animal["name"])}</h1>
<p class="sci">{_esc(animal.get("scientific_name"))}
  <span class="src">{_esc(animal.get("taxon_label"))}</span></p>
<p class="lede">{_esc(lede)}</p>
{notes}
{"".join(blocks)}
"""
    return _page(f'{animal["name"]}: the plants it needs',
                 f'{animal["name"]} ({animal.get("scientific_name")}): '
                 f'{animal["total"]} documented plant relationships.',
                 body, depth, wide=True)


def render_about(model: dict) -> str:
    s = model["stats"]
    body = f"""
{_crumb([("", "About")], 1)}
<h1>About this catalogue</h1>
<p class="lede">{s['species']} plants, {s['animals']} animals with documented
plant relationships, {s['edges']} relationships between them, and
{s['facets']} searchable fields. Built for Alberta and the Canadian
prairies.</p>

<h2>What it is</h2>
<p>This is the reference half of <a
href="https://github.com/yarrowyarrowyarrow/Site-and-Pattern">Site and
Pattern</a>, a desktop application for designing landscapes with native plants:
lawn-to-habitat conversion, pollinator gardens and ecological restoration. The
application does the site analysis, the design and the planting plan. These
pages are its catalogue, published so you can read it without installing
anything.</p>

<h2>What it is honest about</h2>
<ul>
  <li><strong>Unknowns stay unknown.</strong> A species with no recorded bloom
  window appears under no month. A plant with no recorded flower colour appears
  under no colour. Absence of a record is never rendered as a fact.</li>
  <li><strong>Evidence travels with the claim.</strong> Recorded ranges carry
  their occurrence counts and a confidence band. A region derived from three
  records is not presented like one derived from three hundred.</li>
  <li><strong>Flower colour says whether it was checked.</strong> The colour was
  originally seeded per genus, which put a red flower on the blue columbine.
  {s['verified_colour']} species now carry a colour checkable against their own
  common name or Latin epithet and are marked <em>checked</em>; the rest are
  marked <em>not verified</em> rather than quietly presented as observed.</li>
  <li><strong>Relationships are documented, not inferred.</strong> Every animal
  listed on a plant page comes from a sourced record.</li>
  <li><strong>Grasses and sedges are not yellow.</strong> They are
  wind-pollinated and have no showy flower, so they get a bucket that says
  so.</li>
  <li><strong>Photographs are credited or absent.</strong> {s['with_photo']} of
  {s['species']} species have an openly-licensed photograph we can attribute.
  The rest show none.</li>
  <li><strong>The maps are diagrams.</strong> The region outlines are
  hand-drawn boxes standing in for surveyed boundaries. The occurrence counts
  inside them are real.</li>
</ul>

<h2>What it does not contain</h2>
<p>No Indigenous ecological knowledge, plant-use tradition, land-management
practice or design framework appears in this catalogue, and none should be
inferred from it. That knowledge is held by the communities it belongs to and is
theirs to share on their own terms, through relationship rather than
extraction.</p>
<p>Two things follow from that and are worth stating plainly, because both are
deliberate omissions rather than gaps. The underlying dataset has a free-text
notes field in which some entries describe traditional medicinal use; it is
<strong>withheld from these pages</strong>. The dataset also tags some species
with a generic <em>medicinal</em> use category; that tag is <strong>not
published or searchable here</strong> either. Putting a public, indexed index of
medicinal native plants on the web would operationalize knowledge that was never
ours to publish. The horticultural facts those notes also carried, such as how a
plant spreads, whether it is toxic and where to buy it, are recorded in
structured fields and do appear.</p>

<h2>Corrections</h2>
<p>Errors and photograph credit problems can be reported as issues on the
<a href="https://github.com/yarrowyarrowyarrow/Site-and-Pattern">project
repository</a>. If a photograph of yours is here and the credit is wrong, or you
would rather it were not here at all, it will be fixed or removed.</p>

<p class="src">Catalogue built {_esc(model["built"])}.</p>
"""
    return _page("About the Site and Pattern plant catalogue",
                 "How this catalogue is sourced, what it is honest about, and "
                 "what it deliberately does not contain.", body, 1)


# ── Writing it out ───────────────────────────────────────────────────────────

def write_site(model: dict, out_dir: str, *,
               base_url: str = "",
               copy_photos: bool = True,
               include_notes: bool = False,
               progress: Optional[Callable] = None) -> dict:
    """Render ``model`` into ``out_dir``. Returns a summary dict.

    ``out_dir`` is created if absent and written into, never emptied: a
    generator that deletes a directory the user pointed at is one bad argument
    away from removing something else.
    """
    # Imported here, not at module scope: static_site_species imports the shell
    # and the shared pieces back from this module, so a top-level import would
    # be a cycle. The species page is the only page that needed splitting out.
    from src.static_site_species import render_species       # noqa: PLC0415

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
                                extra=_hub_extra(hub, page, depth + 1)))
    say(f"{sum(len(h['pages']) for h in model['hubs'])} listing pages "
        f"across {len(model['hubs'])} axes")

    emit("wildlife/index.html",
         render_wildlife_index(model, len(model["wildlife"]),
                               int(model.get("total_fauna") or 0)))
    for animal in model["wildlife"]:
        emit(f"wildlife/{animal['slug']}/index.html",
             render_wildlife(animal, photo_src))
    say(f"{len(model['wildlife'])} wildlife pages")

    emit("assets/catalogue.json", json.dumps(
        [e["brief"] for e in model["species"]], indent=1))
    emit("sitemap.xml", _sitemap(written, base_url))
    emit("robots.txt", _robots(base_url))

    copied = sum(1 for v in photo_src.values() if not v.startswith("http"))
    return {"out_dir": str(root),
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


def _hub_extra(hub: dict, page: dict, depth: int) -> str:
    """The map, on ecoregion listings only. Everywhere else the axis has no
    geometry and a decorative map would be noise."""
    if hub["key"] != "ecoregion":
        return ""
    from src.ecoregion_map import CAVEAT, map_svg               # noqa: PLC0415
    svg = map_svg({page["value"]: "high"}, width=380, height=250,
                  title=f'{page["name"]} extent')
    if not svg:
        return ""
    return (f'<figure class="mapfig inline">{svg}'
            f'<figcaption class="note">{_esc(CAVEAT)}</figcaption></figure>')


def _stage_photos(model: dict, root: pathlib.Path, say: Callable) -> dict:
    """``{recorded url: path used}``.

    Prefers bytes already in the local image cache and copies them into
    ``assets/photos/``; falls back to the recorded URL when the cache is cold.
    ``get_cached_image`` never touches the network, so a cold cache degrades to
    links rather than turning a site build into 300 downloads.

    Both counts are reported at the end of the build, because "the site
    published with 321 hotlinks to iNaturalist" is something the operator should
    find out before uploading rather than when the CDN changes.
    """
    from src.image_cache import get_cached_image
    dest = root / "assets" / "photos"
    dest.mkdir(parents=True, exist_ok=True)
    out: dict = {}
    for entry in model["species"]:
        url = (_first_photo(entry).get("url") or "").strip()
        if not url or url in out:
            continue
        # Named for the species, so the staged file is identifiable on disk and
        # stable across rebuilds. Slugs are unique, so filenames are too.
        local = get_cached_image(url)
        if local and os.path.exists(local):
            name = f"{entry['slug']}{os.path.splitext(local)[1] or '.jpg'}"
            try:
                shutil.copyfile(local, dest / name)
                out[url] = f"assets/photos/{name}"
                continue
            except OSError:
                pass
        out[url] = url
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


def _robots(base_url: str) -> str:
    base = (base_url or "").rstrip("/")
    line = f"Sitemap: {base}/sitemap.xml\n" if base else ""
    return f"User-agent: *\nAllow: /\n{line}"
