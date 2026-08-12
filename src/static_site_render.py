"""
static_site_render.py — the page model of :mod:`src.static_site`, as HTML.

Design principle P5 — see docs/DESIGN_PHILOSOPHY.md.

Plain files: no framework, no build step, no CDN, no external request of any
kind. That is the same discipline ``html/`` already follows for the map and the
3D viewer, and here it also means the site keeps working when a CDN does not and
can be read straight off a disk with ``file://``.

Links are **relative**, computed per page from its depth, so the output can be
published at a domain root, in a subdirectory, or opened locally without a
server. Root-relative ``/plants/...`` would have been shorter and would break
two of those three.

The browse page filters **client-side** over an embedded JSON index — the
directory's facet vocabulary, on the web, with no backend. It is the one piece
of interactivity here and it degrades to a plain list with JavaScript off.

The stylesheet and that script live in ``html/site/`` as real ``.css`` and
``.js`` files rather than as Python string constants. They were constants until
they took this module 190 lines over its ceiling, and the guard was right: CSS
embedded in a ``.py`` is CSS nobody can lint, highlight or diff sensibly.
"""

from __future__ import annotations

import html
import json
import os
import pathlib
import shutil
from typing import Callable, Optional

from src.flower_colour import COLOURS, COLOUR_LABELS, COLOUR_SWATCHES
from src.static_site import TAXON_GROUPS, _first_photo

#: Plain text, never pre-escaped — everything here goes through ``_esc`` at the
#: point of use. Storing the entity form instead produced ``&amp;amp;`` in every
#: page title, because the ``<title>`` path escapes and the header path did not.
SITE_NAME = "Site & Pattern — Plant Directory"
TAGLINE = ("Native plants of Alberta and the Canadian prairies, and the "
           "animals that depend on them.")


def _asset(name: str) -> str:
    """The text of ``html/site/<name>``.

    Resolved through :func:`src.resources.resource_path` so it works from a
    source checkout and from a frozen bundle alike, which is the same route
    ``web_assets`` takes to ``html/``.
    """
    from src.resources import resource_path                    # noqa: PLC0415
    return pathlib.Path(resource_path("html", "site", name)).read_text(
        encoding="utf-8")


def _esc(text) -> str:
    return html.escape(str(text if text is not None else ""), quote=True)


def _up(depth: int) -> str:
    return "../" * depth


# ── The shell ────────────────────────────────────────────────────────────────

def _page(title: str, description: str, body: str, depth: int,
          *, wide: bool = False) -> str:
    root = _up(depth)
    # Every nav target is a hub the build always writes. Pointing at
    # `plants/colour/yellow/` instead would be one empty seed bucket away from a
    # dead link in the header of every page on the site.
    nav = "".join(
        f'<a href="{root}{href}">{label}</a>'
        for href, label in (("plants/", "Plants"),
                            ("plants/blooming-in/", "In bloom"),
                            ("plants/colour/", "By colour"),
                            ("plants/for/", "By role"),
                            ("wildlife/", "Wildlife"),
                            ("about/", "About")))
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
<header class="top">
  <a class="brand" href="{root}">{_esc(SITE_NAME)}</a>
  <nav>{nav}</nav>
</header>
<main class="{'wide' if wide else ''}">
{body}
</main>
<footer class="foot">
  <p>{_esc(TAGLINE)}</p>
  <p>Generated from the <a href="https://github.com/yarrowyarrowyarrow/Site-and-Pattern">Site
  &amp; Pattern</a> catalogue. Photographs are open-licensed and credited
  individually to their photographers; every other figure carries its source on
  the page it appears on. Where a fact is unknown the page says so rather than
  filling the gap.</p>
  <p>This catalogue records horticultural, ecological and permaculture
  information only. It contains no Indigenous ecological knowledge, plant-use
  tradition or land-management practice, and none should be inferred from
  it.</p>
</footer>
</body>
</html>
"""


def _crumb(items: list, depth: int) -> str:
    root = _up(depth)
    parts = [f'<a href="{root}{href}">{_esc(label)}</a>' if href else _esc(label)
             for href, label in items]
    return f'<p class="crumb">{" › ".join(parts)}</p>'


# ── Pieces ───────────────────────────────────────────────────────────────────

def _photo_img(photo: dict, depth: int, photo_src: dict, alt: str) -> str:
    """An ``<img>`` with its credit, or ``""``.

    ``photo_src`` maps a recorded URL to the path actually used (a copy in
    ``assets/photos/`` when the local cache had the bytes, the original URL when
    it did not). A photo with no attribution never reaches here — see
    :func:`src.static_site._first_photo`.
    """
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


def _colour_chip(key: str, depth: int, *, link: bool = True) -> str:
    if not key:
        return ""
    label = COLOUR_LABELS.get(key, key)
    swatch = COLOUR_SWATCHES.get(key, "#ccc")
    dot = f'<span class="dot" style="background:{_esc(swatch)}"></span>'
    inner = f'{dot}{_esc(label)}'
    if not link:
        return f'<span class="chip">{inner}</span>'
    return (f'<a class="chip" href="{_up(depth)}plants/colour/{_esc(key)}/">'
            f'{inner}</a>')


def _card(brief: dict, depth: int, photo_src: dict) -> str:
    root = _up(depth)
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
    swatch = COLOUR_SWATCHES.get(brief.get("colour") or "", "")
    dot = (f'<span class="dot" style="background:{_esc(swatch)}"></span>'
           if swatch else "")
    bloom = _esc(brief.get("bloom") or "")
    sci = _esc(brief.get("scientific_name") or "")
    star = ' <span class="star" title="Feeds a specialist">★</span>' \
        if brief.get("specialist") else ""
    return (
        f'<a class="card" href="{root}plants/{_esc(brief["slug"])}/">'
        f'<span class="thumb">{img}</span>'
        f'<span class="cardbody">'
        f'<strong>{_esc(brief.get("name"))}{star}</strong>'
        f'<em>{sci}</em>'
        f'<span class="meta">{dot}{_esc(brief.get("type") or "")}'
        f'{" · " + bloom if bloom else ""}</span>'
        f'</span></a>')


def _grid(briefs: list, depth: int, photo_src: dict) -> str:
    if not briefs:
        return '<p class="empty">Nothing in the catalogue matches this yet.</p>'
    cards = "".join(_card(b, depth, photo_src) for b in briefs)
    return f'<div class="grid">{cards}</div>'


# ── Pages ────────────────────────────────────────────────────────────────────

def render_home(model: dict, photo_src: dict) -> str:
    s = model["stats"]
    colours = "".join(
        f'<a class="chip" href="plants/colour/{_esc(c["slug"])}/">'
        f'<span class="dot" style="background:{_esc(c["swatch"])}"></span>'
        f'{_esc(c["name"])} <span class="n">{len(c["plants"])}</span></a>'
        for c in model["colours"])
    months = "".join(
        f'<a class="chip" href="plants/blooming-in/{_esc(m["slug"])}/">'
        f'{_esc(m["name"])} <span class="n">{len(m["plants"])}</span></a>'
        for m in model["months"])
    roles = "".join(
        f'<a class="chip" href="plants/for/{_esc(r["slug"])}/">{_esc(r["name"])}'
        f' <span class="n">{len(r["plants"])}</span></a>'
        for r in model["roles"])
    body = f"""
<section class="hero">
  <h1>{s['species']} native and prairie-hardy plants, and the {s['animals']}
  animals documented to use them.</h1>
  <p class="lede">{TAGLINE} Every relationship on this site is a
  <strong>documented</strong> record with a source — {s['edges']} of them, of
  which {s['specialist_edges']} involve an animal that has nowhere else to
  go.</p>
  <p><a class="button" href="plants/">Browse all {s['species']} plants</a></p>
</section>

<section>
  <h2>By flower colour</h2>
  <p>The grasses and sedges have a bucket of their own. They are
  wind-pollinated, so what you see is the seed head, not a bloom — filing them
  under "yellow" would claim something the data does not say.</p>
  <div class="chips">{colours}</div>
</section>

<section>
  <h2>By bloom month</h2>
  <p>A species with no recorded bloom window is listed under no month. We do
  not know when it flowers, and that is not the same as knowing it doesn't.</p>
  <div class="chips">{months}</div>
</section>

<section>
  <h2>By what it does</h2>
  <div class="chips">{roles}</div>
</section>

<section>
  <h2>Start from the animal instead</h2>
  <p>Most plant catalogues can tell you what a plant looks like. This one can
  tell you which caterpillars eat it, which bees can physically reach its
  nectar, and which of them have no alternative — because the catalogue is
  built on the relationships rather than on the plants.</p>
  <p><a class="button" href="wildlife/">{s['animals']} animals →</a></p>
</section>
"""
    return _page(f"{s['species']} native plants of Alberta and the prairies",
                 TAGLINE, body, 0)


def render_browse(model: dict, photo_src: dict) -> str:
    briefs = [_brief_of(e) for e in model["species"]]
    # `</script>` inside the payload would close the block early and spill JSON
    # into the document. No botanical name does that today, but the index is
    # built from free-text database columns and one day one of them will —
    # escaping `<` costs nothing and JSON parses `<` identically.
    index = json.dumps(briefs, separators=(",", ":")).replace("<", "\\u003c")
    colour_opts = "".join(
        f'<label><input type="checkbox" value="{_esc(k)}" data-f="colour">'
        f'<span class="dot" style="background:{_esc(sw)}"></span>{_esc(lbl)}</label>'
        for k, lbl, sw, _n in COLOURS)
    type_opts = "".join(
        f'<label><input type="checkbox" value="{_esc(t)}" data-f="type">'
        f'{_esc(t.title())}</label>'
        for t in sorted({b["type"] for b in briefs if b["type"]}))
    month_opts = "".join(
        f'<label><input type="checkbox" value="{_esc(m["slug"])}" data-f="month">'
        f'{_esc(m["name"])}</label>' for m in model["months"])
    body = f"""
{_crumb([("", "Plants")], 1)}
<h1>All {len(briefs)} plants</h1>
<p class="lede">Filter without leaving the page. Every plant links to its own
page, with its documented animals, its recorded range and the evidence behind
both.</p>

<form class="filters" id="filters" onsubmit="return false">
  <input type="search" id="q" placeholder="Search name or botanical name"
         autocomplete="off">
  <details><summary>Flower colour</summary><div class="opts">{colour_opts}</div></details>
  <details><summary>Type</summary><div class="opts">{type_opts}</div></details>
  <details><summary>Blooms in</summary><div class="opts">{month_opts}</div></details>
  <label class="toggle"><input type="checkbox" id="nativeonly">
    Native to Alberta only</label>
  <button type="button" id="clear">Clear</button>
  <p class="count" id="count">{len(briefs)} plants</p>
</form>

<noscript><p class="note">Filtering needs JavaScript. The full list is
below.</p></noscript>

<div class="grid" id="results">{"".join(_card(b, 1, photo_src) for b in briefs)}</div>
<script id="catalogue" type="application/json">{index}</script>
<script>{_asset("browse.js")}</script>
"""
    return _page(f"All {len(briefs)} plants", TAGLINE, body, 1, wide=True)


def _brief_of(entry: dict) -> dict:
    """The listing row for a built species entry. Mirrors
    ``static_site._brief`` but reads the assembled entry, which already has the
    slug and the classified colour resolved."""
    from src.flower_colour import classify
    from src.image_cache import credit_line
    row = entry.get("row") or {}
    photo = _first_photo(entry)
    return {
        "slug": entry["slug"],
        "name": entry.get("name") or "",
        "scientific_name": entry.get("scientific_name") or "",
        "type": entry.get("plant_type") or "",
        "colour": classify(row),
        "bloom": entry.get("bloom") or "",
        "months": _bloom_months(row),
        "native": bool(entry.get("native_to_alberta")),
        "image": photo.get("url") or "",
        "credit": (credit_line(photo.get("attribution") or "",
                               photo.get("license") or "") if photo else ""),
    }


def _bloom_months(row: dict) -> list:
    try:
        from src.habitat_score import parse_month_range
        return sorted(parse_month_range(row.get("bloom_period") or ""))
    except Exception:                                     # noqa: BLE001
        return []


def render_species(entry: dict, model: dict, photo_src: dict,
                   include_notes: bool = False) -> str:
    from src.flower_colour import classify
    depth = 2
    row = entry.get("row") or {}
    colour = classify(row)
    photo = _first_photo(entry)
    hero = ""
    if photo:
        hero = (f'<figure class="hero-photo">'
                f'{_photo_img(photo, depth, photo_src, entry.get("name") or "")}'
                f'{_credit(photo)}</figure>')
    else:
        hero = ('<p class="note">No openly-licensed photograph of this species '
                'is in the catalogue yet. We show a photo only when we can '
                'credit the photographer.</p>')

    badges = "".join(f'<span class="badge">{_esc(b)}</span>'
                     for b in (entry.get("badges") or []))
    facts = _facts_table(entry, colour, depth)
    wildlife = _wildlife_section(entry, model, depth)
    ranges = _ranges_section(entry)
    extras = _extras_section(entry, include_notes)
    months = _bloom_months(row)
    month_links = " ".join(
        f'<a class="chip" href="{_up(depth)}plants/blooming-in/'
        f'{_esc(model["months"][m - 1]["slug"])}/">'
        f'{_esc(model["months"][m - 1]["name"])}</a>' for m in months)

    body = f"""
{_crumb([("plants/", "Plants"), ("", entry.get("name") or "")], depth)}
<article class="species">
  <header>
    <h1>{_esc(entry.get("name"))}</h1>
    <p class="sci">{_esc(entry.get("scientific_name"))}</p>
    <p class="badges">{badges}</p>
  </header>
  {hero}
  {facts}
  {'<section><h2>In bloom</h2><div class="chips">' + month_links + '</div></section>'
     if month_links else ''}
  {wildlife}
  {ranges}
  {extras}
</article>
"""
    desc = (f'{entry.get("name")} ({entry.get("scientific_name")}) — '
            f'{entry.get("sun") or "conditions unrecorded"}, '
            f'{entry.get("bloom") or "bloom window unrecorded"}. '
            f'{(entry.get("wildlife") or {}).get("total", 0)} documented '
            f'animal relationships.')
    return _page(f'{entry.get("name")} ({entry.get("scientific_name")})',
                 desc, body, depth)


def _facts_table(entry: dict, colour: str, depth: int) -> str:
    rows = [
        ("Type", entry.get("plant_type")),
        ("Sun", _tokens(entry.get("sun"))),
        ("Water", _tokens(entry.get("water"))),
        ("Soil", entry.get("soil_ph")),
        ("Hardiness", entry.get("zones")),
        ("Mature height", _metres(entry.get("mature_height_m"))),
        ("Mature spread", _metres(entry.get("mature_canopy_m"))),
        ("Spacing", _metres(entry.get("spacing_m"))),
        ("Years to maturity", entry.get("years_to_maturity")),
        ("Bloom", entry.get("bloom")),
        ("Flower colour", _colour_chip(colour, depth) if colour else ""),
        ("Fruit", entry.get("fruit")),
        ("Native to", _tokens(entry.get("native"))),
    ]
    cells = "".join(
        f"<tr><th>{_esc(label)}</th><td>{value if label == 'Flower colour' else _esc(value)}</td></tr>"
        for label, value in rows if value not in (None, "", []))
    morph = entry.get("morphology") or ""
    morph_html = (f'<p class="morph">{_esc(morph)}</p>'
                  if isinstance(morph, str) and morph else "")
    if isinstance(morph, (list, tuple)) and morph:
        morph_html = "<ul class=\"morph\">" + "".join(
            f"<li>{_esc(m)}</li>" for m in morph) + "</ul>"
    return (f'<section><h2>Growing it</h2><table class="facts">{cells}</table>'
            f'{morph_html}</section>')


def _tokens(value) -> str:
    """``"full_sun,partial shade"`` → ``"Full sun, partial shade"``.

    Several columns hold comma-delimited tokens with no spaces (a plant that
    tolerates a range, V1.84). Printed raw they read as a typo.
    """
    if not isinstance(value, str) or not value.strip():
        return value if isinstance(value, str) else ""
    parts = [t.strip().replace("_", " ") for t in value.split(",") if t.strip()]
    if not parts:
        return ""
    return ", ".join([parts[0][:1].upper() + parts[0][1:]] + parts[1:])


def _metres(value) -> str:
    try:
        f = float(value)
    except (TypeError, ValueError):
        return ""
    return f"{f:g} m" if f else ""


def _wildlife_section(entry: dict, model: dict, depth: int) -> str:
    wildlife = entry.get("wildlife") or {}
    total = int(wildlife.get("total") or 0)
    if not total:
        return ('<section><h2>Documented animals</h2><p class="note">No animal '
                'relationships are documented for this species in our sources. '
                'That is a gap in the catalogue, not evidence that nothing uses '
                'it.</p></section>')
    by_name = {a["name"]: a["slug"] for a in model["wildlife"]}
    blocks = []
    for group in wildlife.get("groups") or []:
        items = []
        for item in group.get("items") or []:
            label = _esc(item.get("name"))
            slug = by_name.get(item.get("name") or "")
            if slug:
                label = (f'<a href="{_up(depth)}wildlife/{_esc(slug)}/">'
                         f'{label}</a>')
            star = (' <span class="star" title="Specialist — has nowhere else '
                    'to go">★</span>') if item.get("specialist") else ""
            src = (f' <span class="src">{_esc(item.get("source"))}</span>'
                   if item.get("source") else "")
            items.append(f"<li>{label}{star}{src}</li>")
        blocks.append(f'<h3>{_esc(group.get("how"))}</h3><ul class="animals">'
                      f'{"".join(items)}</ul>')
    spec = int(wildlife.get("specialists") or 0)
    note = (f"{total} documented relationships"
            + (f", {spec} with a specialist that has no alternative"
               if spec else "") + ".")
    return (f'<section><h2>Documented animals</h2><p class="lede">{_esc(note)}'
            f'</p>{"".join(blocks)}</section>')


def _ranges_section(entry: dict) -> str:
    ranges = entry.get("ranges") or []
    if not ranges:
        return ""
    rows = []
    for r in ranges:
        n = int(r.get("occurrences") or 0)
        evidence = (f"{n} occurrence records" if n
                    else "from the catalogue's regional tag, not from "
                         "occurrence records")
        conf = f' · {_esc(r["confidence"])} confidence' if r.get("confidence") else ""
        where = f' <span class="src">{_esc(r["where"])}</span>' if r.get("where") else ""
        rows.append(f'<li><strong>{_esc(r.get("name"))}</strong>{where}'
                    f'<span class="src"> — {_esc(evidence)}{conf}</span></li>')
    return ('<section><h2>Where it has been recorded</h2>'
            '<ul class="ranges">' + "".join(rows) + '</ul>'
            '<p class="note">A range seen three times is not the same claim as '
            'one seen three hundred times, so the count travels with the '
            'region.</p></section>')


def _extras_section(entry: dict, include_notes: bool = False) -> str:
    parts = []
    fields = [("Safety", entry.get("safety")),
              ("Edible parts", _tokens(entry.get("edible_parts"))),
              ("Buying it", entry.get("sourcing"))]
    # `notes` is unaudited free text and ~43 rows of it describe traditional
    # medicinal and plant-use practice. Publishing that to the open web is a
    # different act from showing it in a desktop panel — indexed, scraped,
    # archived, effectively irrevocable — and P12 forbids operationalizing that
    # knowledge without free, prior and informed consent. Off by default; the
    # structured columns that carry the *horticultural* half of these notes
    # (spread habit, toxicity, sourcing) publish either way.
    if include_notes:
        fields.append(("Notes", entry.get("notes")))
    for heading, value in fields:
        if not value:
            continue
        if isinstance(value, dict):
            value = "; ".join(f"{k}: {v}" for k, v in value.items() if v)
        elif isinstance(value, (list, tuple)):
            value = "; ".join(str(v) for v in value)
        parts.append(f"<h3>{_esc(heading)}</h3><p>{_esc(value)}</p>")
    prov = entry.get("provenance") or []
    if prov:
        parts.append("<h3>Where these numbers came from</h3><ul>" + "".join(
            f"<li>{_esc(p)}</li>" for p in prov) + "</ul>")
    if not parts:
        return ""
    return f'<section><h2>Also worth knowing</h2>{"".join(parts)}</section>'


def render_hub(title: str, intro: str, pages: list, depth: int,
               crumb: list) -> str:
    """A landing page for one browse axis — every colour, every month, every
    role, with its count. These are what the header links to, so they must
    exist on every build regardless of what the seed data happens to contain."""
    chips = "".join(
        f'<a class="chip" href="{_esc(p["slug"])}/">'
        + (f'<span class="dot" style="background:{_esc(p["swatch"])}"></span>'
           if p.get("swatch") else "")
        + f'{_esc(p["name"])} <span class="n">{len(p["plants"])}</span></a>'
        for p in pages)
    body = f"""
{_crumb(crumb, depth)}
<h1>{_esc(title)}</h1>
<p class="lede">{_esc(intro)}</p>
<div class="chips">{chips}</div>
"""
    return _page(f"{title} · {SITE_NAME}", intro, body, depth)


def render_listing(page: dict, depth: int, photo_src: dict,
                   crumb: list) -> str:
    n = len(page["plants"])
    swatch = ""
    if page.get("swatch"):
        swatch = (f'<span class="dot big" style="background:'
                  f'{_esc(page["swatch"])}"></span>')
    body = f"""
{_crumb(crumb, depth)}
<h1>{swatch}{_esc(page["title"])}</h1>
<p class="lede">{_esc(page.get("intro") or "")}</p>
<p class="count">{n} {"plant" if n == 1 else "plants"}</p>
{_grid(page["plants"], depth, photo_src)}
"""
    return _page(f'{page["title"]} · {SITE_NAME}',
                 f'{n} species. {page.get("intro") or ""}', body, depth,
                 wide=True)


def render_wildlife_index(model: dict, listed: int, total_fauna: int) -> str:
    blocks = []
    for taxon, heading in TAXON_GROUPS:
        animals = [a for a in model["wildlife"] if a["taxon"] == taxon]
        if not animals:
            continue
        links = "".join(
            f'<a class="chip" href="{_esc(a["slug"])}/">{_esc(a["name"])}'
            f' <span class="n">{a["total"]}</span></a>' for a in animals)
        blocks.append(f'<section><h2>{_esc(heading)} '
                      f'<span class="n">{len(animals)}</span></h2>'
                      f'<div class="chips">{links}</div></section>')
    omitted = total_fauna - listed
    note = ""
    if omitted > 0:
        note = (f'<p class="note">{omitted} more animals are in the catalogue '
                f'with no plant relationship documented yet. They are not '
                f'listed here, because a page reading "0 plants support this '
                f'species" would publish a fact about our coverage as though it '
                f'were a fact about the animal.</p>')
    body = f"""
{_crumb([("", "Wildlife")], 1)}
<h1>{listed} animals, and the plants that support them</h1>
<p class="lede">Each relationship below is a documented record with a source,
not an inference. A ★ marks a specialist — an animal that cannot simply move to
another plant.</p>
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
    return _page(f'{animal["name"]} — the plants it needs',
                 f'{animal["name"]} ({animal.get("scientific_name")}): '
                 f'{animal["total"]} documented plant relationships.',
                 body, depth, wide=True)


def render_about(model: dict) -> str:
    s = model["stats"]
    body = f"""
{_crumb([("", "About")], 1)}
<h1>About this catalogue</h1>
<p class="lede">{s['species']} plants, {s['animals']} animals with documented
plant relationships, {s['edges']} relationships between them. Built for
Alberta and the Canadian prairies.</p>

<h2>What it is</h2>
<p>This is the reference half of <a
href="https://github.com/yarrowyarrowyarrow/Site-and-Pattern">Site &amp;
Pattern</a>, a desktop application for designing landscapes with native plants
— lawn-to-habitat conversion, pollinator gardens and ecological restoration.
The application does the site analysis, the design and the planting plan. These
pages are its catalogue, published so you can read it without installing
anything.</p>

<h2>What it is honest about</h2>
<ul>
  <li><strong>Unknowns stay unknown.</strong> A species with no recorded bloom
  window appears under no month. A plant with no recorded flower colour appears
  under no colour. Absence of a record is never rendered as a fact.</li>
  <li><strong>Evidence travels with the claim.</strong> Recorded ranges carry
  their occurrence counts and a confidence band; a region derived from three
  records is not presented like one derived from three hundred.</li>
  <li><strong>Relationships are documented, not inferred.</strong> Every animal
  listed on a plant page comes from a sourced record.</li>
  <li><strong>Grasses and sedges are not "yellow".</strong> They are
  wind-pollinated and have no showy flower; they get a bucket that says
  so.</li>
  <li><strong>Photographs are credited or absent.</strong> {s['with_photo']} of
  {s['species']} species have an openly-licensed photograph we can attribute.
  The rest show none.</li>
</ul>

<h2>What it does not contain</h2>
<p>No Indigenous ecological knowledge, plant-use tradition, land-management
practice or design framework appears in this catalogue, and none should be
inferred from it. That knowledge is held by the communities it belongs to and
is theirs to share on their own terms, through relationship rather than
extraction.</p>
<p>This is why the plants here carry no medicinal or traditional-use
information. The underlying dataset has a free-text notes field in which some
entries describe such uses; it is <strong>withheld from these pages</strong>
rather than published, because putting it on the open web would operationalize
knowledge that was never ours to publish. The horticultural facts those notes
also carried — how a plant spreads, whether it is toxic, where to buy it — are
recorded in structured fields and appear above.</p>

<h2>Corrections</h2>
<p>Errors and photograph credit problems can be reported as issues on the
<a href="https://github.com/yarrowyarrowyarrow/Site-and-Pattern">project
repository</a>. If a photograph of yours is here and the credit is wrong — or
you would rather it were not here at all — it will be fixed or removed.</p>

<p class="src">Catalogue built {_esc(model["built"])}.</p>
"""
    return _page("About the Site & Pattern plant catalogue",
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
    emit("index.html", render_home(model, photo_src))
    emit("about/index.html", render_about(model))
    emit("plants/index.html", render_browse(model, photo_src))

    for entry in model["species"]:
        emit(f"plants/{entry['slug']}/index.html",
             render_species(entry, model, photo_src, include_notes))
    say(f"{len(model['species'])} species pages")

    for axis, folder, hub_title, hub_intro in (
            ("months", "plants/blooming-in", "Plants by bloom month",
             "A species with no recorded bloom window is listed under no "
             "month. We do not know when it flowers, and that is not the same "
             "as knowing it doesn't."),
            ("colours", "plants/colour", "Plants by flower colour",
             "Grasses and sedges have a bucket of their own: they are "
             "wind-pollinated, so what you see is the seed head, not a bloom."),
            ("roles", "plants/for", "Plants by what they do",
             "The ecological work a plant does, from the same documented "
             "records the species pages cite.")):
        pages = model[axis]
        emit(f"{folder}/index.html",
             render_hub(hub_title, hub_intro, pages, folder.count("/") + 1,
                        [("plants/", "Plants"), ("", hub_title)]))
        for page in pages:
            emit(f"{folder}/{page['slug']}/index.html",
                 render_listing(page, folder.count("/") + 2, photo_src,
                                [("plants/", "Plants"),
                                 (f"{folder}/", hub_title),
                                 ("", page["name"])]))

    emit("wildlife/index.html",
         render_wildlife_index(model, len(model["wildlife"]),
                               int(model.get("total_fauna") or 0)))
    for animal in model["wildlife"]:
        emit(f"wildlife/{animal['slug']}/index.html",
             render_wildlife(animal, photo_src))
    say(f"{len(model['wildlife'])} wildlife pages")

    emit("assets/catalogue.json", json.dumps(
        [_brief_of(e) for e in model["species"]], indent=1))
    emit("sitemap.xml", _sitemap(written, base_url))
    emit("robots.txt", _robots(base_url))

    copied = sum(1 for v in photo_src.values() if not v.startswith("http"))
    return {"out_dir": str(root),
            # Pages plus the photo files staged beside them — the number the
            # operator is about to upload, not just the number rendered.
            "files": len(written) + copied,
            "pages": len(written),
            "species": len(model["species"]),
            "wildlife": len(model["wildlife"]),
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
