"""
static_site_wildlife.py — the wildlife index and the per-animal pages.

Split out of `static_site_render` in V2.71, when the wildlife index stopped
being a wall of 1,138 chips and became a filtered search like the plant one.
Same seam as `static_site_species` / `_about` / `_regions`: this module imports
the shell helpers from `static_site_render`, and `write_site` imports these
renderers back at call time so the dependency runs one way only.

Two things changed at once, and they are the same change. The index was a flat
list because there was nothing to sort it *by*; giving it facets — kind of
animal, how it uses the plant, how many plants are recorded, whether it is a
specialist, whether we have a photograph — is what makes 1,138 rows navigable
instead of merely long. And the photographs had been sitting in the `fauna`
table, credited and openly licensed, unpublished, since the iNaturalist fetch.

The facets are declared here rather than in `src/site_facets.py` on purpose:
that table describes what a *plant* can be searched by and is baked into every
browse-index row, and an animal is not a row in it. What they do share is the
runtime — `html/site/browse.js` reads whatever `data-f` attributes the page
rendered, so one script filters both pages without knowing either vocabulary.
"""

from __future__ import annotations

import json

from src.static_site import TAXON_GROUPS
from src.static_site_render import (SITE_NAME, _crumb, _esc, _grid, _page, _up)


#: Relationship key to a plain-language checkbox label. `scene_dossier`'s
#: `_REL_FROM_ANIMAL` says "sips nectar at", which reads correctly as a heading
#: over a list of plants and badly as the label on a tickbox.
_USE_LABELS: tuple = (
    ("nectar", "Drinks nectar"),
    ("pollen", "Gathers pollen"),
    ("larval_host", "Lays eggs on it"),
    ("fruit_food", "Eats the fruit"),
    ("seed_food", "Eats the seed"),
    ("nesting", "Nests in it"),
    ("cover", "Shelters in it"),
    ("other", "Some other way"),
)

#: How many plants are recorded for this animal, in bands. Bands rather than a
#: number, because the number is a fact about the catalogue's coverage as much
#: as about the animal (P9) and a slider would invite reading it as the latter.
_BANDS: tuple = (
    ("1", "1 plant"),
    ("2-5", "2 to 5 plants"),
    ("6-20", "6 to 20 plants"),
    ("21+", "21 or more plants"),
)

#: ``(key, label, group, combine, options)``. `combine="all"` makes a facet's
#: own ticks AND rather than OR — ticking "has a photograph" and "is a
#: specialist" should narrow to animals that are both, the way the plant page's
#: safety facet works.
_FACETS: tuple = (
    ("taxon", "Kind of animal", "The animal", "any", TAXON_GROUPS),
    ("uses", "How it uses the plant", "The animal", "any", _USE_LABELS),
    ("count", "Plants recorded", "The record", "any", _BANDS),
    ("has", "Also", "The record", "all",
     (("photo", "Has a photograph"), ("specialist", "Is a specialist"))),
)


def _band(total: int) -> str:
    if total <= 1:
        return "1"
    if total <= 5:
        return "2-5"
    if total <= 20:
        return "6-20"
    return "21+"


def facets_for(animal: dict) -> dict:
    """The filter values one animal answers to.

    A key left out means "this animal answers nothing in that facet", which
    `browse.js` treats as no match — the same rule the plant index runs on, and
    the reason an animal with no photograph disappears when the photograph box
    is ticked rather than surviving as an unknown.
    """
    has = []
    if (animal.get("image") or "").strip() and (animal.get("credit") or ""):
        has.append("photo")
    if int(animal.get("specialists") or 0):
        has.append("specialist")
    known = {key for key, _label in _USE_LABELS}
    out = {
        "taxon": [animal.get("taxon") or ""],
        "uses": sorted({k if k in known else "other"
                        for k in (animal.get("kinds") or [])}),
        "count": [_band(int(animal.get("total") or 0))],
    }
    if has:
        out["has"] = has
    return out


def _photo(animal: dict, photo_src: dict, root: str) -> tuple:
    """``(src, credit)`` for an animal's photograph, or ``("", "")``.

    The credit is not optional and not separable: `static_site.photo_credit`
    already returned nothing at all when the attribution was missing, so an
    empty credit here means there is no publishable photograph, not a photograph
    with the credit left off.
    """
    url = (animal.get("image") or "").strip()
    credit = animal.get("credit") or ""
    if not url or not credit:
        return "", ""
    src = photo_src.get(url, url)
    if not src.startswith(("http://", "https://")):
        src = root + src
    return src, credit


def _card(animal: dict, depth: int, photo_src: dict) -> str:
    root = _up(depth)
    src, credit = _photo(animal, photo_src, root)
    img = (f'<img src="{_esc(src)}" alt="{_esc(credit)}" '
           f'title="{_esc(credit)}" loading="lazy">' if src
           else '<span class="nophoto" aria-hidden="true"></span>')
    total = int(animal.get("total") or 0)
    star = (' <span class="star" title="A specialist on at least one of '
            'them">&#9733;</span>' if int(animal.get("specialists") or 0)
            else "")
    return (
        f'<a class="card" href="{root}wildlife/{_esc(animal["slug"])}/">'
        f'<span class="thumb">{img}</span>'
        f'<span class="cardbody">'
        f'<strong>{_esc(animal.get("name"))}{star}</strong>'
        f'<em>{_esc(animal.get("scientific_name") or "")}</em>'
        f'<span class="meta">{_esc(animal.get("taxon_label") or "")}'
        f' &middot; {total} plant{"" if total == 1 else "s"}</span>'
        f"</span></a>")


def _panels(animals: list) -> str:
    """The facet sidebar, pruned to values something actually answers.

    Same rule the plant sidebar learned in V2.68: a checkbox that can only ever
    return nothing is worse than a missing one, because the empty result reads
    as a fact about the prairie rather than about the catalogue.
    """
    in_use: dict = {}
    for animal in animals:
        for key, values in facets_for(animal).items():
            in_use.setdefault(key, set()).update(v for v in values if v)
    groups: dict = {}
    for key, label, group, combine, options in _FACETS:
        opts = "".join(
            f'<label><input type="checkbox" data-f="{_esc(key)}" '
            f'value="{_esc(value)}"><span>{_esc(text)}</span></label>'
            for value, text in options if value in in_use.get(key, ()))
        if not opts:
            continue
        groups.setdefault(group, []).append(
            f'<details class="facet" data-facet="{_esc(key)}" '
            f'data-combine="{_esc(combine)}">'
            f'<summary>{_esc(label)}<span class="on" hidden></span></summary>'
            f'<div class="opts">{opts}</div></details>')
    return "".join(
        f'<section class="fgroup"><h3>{_esc(group)}</h3>'
        f'<div class="facets">{"".join(blocks)}</div></section>'
        for group, blocks in groups.items())


def render_wildlife_index(model: dict, listed: int, total_fauna: int,
                          photo_src: dict) -> str:
    animals = model["wildlife"]
    index = [dict(facets_for(a), s=a["slug"],
                  n=(a["name"] + " " + (a.get("scientific_name") or "")).lower())
             for a in animals]
    # `</script>` inside the payload would close the block early. Same guard as
    # the plant index: no animal is named that today, but the strings come out
    # of free-text database columns.
    payload = json.dumps(index, separators=(",", ":")).replace("<", "\\u003c")
    cards = "".join(_card(a, 1, photo_src) for a in animals)

    omitted = total_fauna - listed
    note = ""
    if omitted > 0:
        note = (f'<p class="note">{omitted} more animals are in the catalogue '
                f'with no plant relationship recorded yet, so they have no '
                f'page. An empty page would say more about our coverage than '
                f'about the animal.</p>')

    body = f"""
{_crumb([("", "Wildlife")], 1)}
<div class="searchhead">
  <h1>Search {listed} animals</h1>
  <p class="lede">Pick an animal to see the plants it feeds on, lays eggs on or
  shelters in. Every one is a documented record with a source.</p>
</div>
{note}

<div class="searchlayout">
  <form class="filters" id="filters" onsubmit="return false"
        aria-label="Filters">
    <div class="fhead">
      <div class="fbar">
        <input type="search" id="q" placeholder="Name or scientific name"
               autocomplete="off" aria-label="Search by name">
        <button type="button" id="clear" hidden>Clear</button>
      </div>
      <p class="count" id="count" role="status">{listed} animals</p>
      <div id="active" class="active"></div>
    </div>
    <div class="fscroll">{_panels(animals)}</div>
  </form>

  <div class="results">
    <noscript><p class="note">Filtering needs JavaScript. The full list is
    below.</p></noscript>
    <div class="grid" id="results" data-noun="animal"
         data-noun-plural="animals">{cards}</div>
    <p class="empty" id="noresults" hidden>No animal matches all of those.
    Try removing a filter.</p>
  </div>
</div>
<script id="catalogue" type="application/json">{payload}</script>
"""
    return _page(f"Search {listed} animals | {SITE_NAME}",
                 "Native bees, butterflies, moths, birds and mammals, and the "
                 "documented plants each one depends on.", body, 1, wide=True,
                 scripts=f'<script src="{_up(1)}assets/browse.js"></script>')


def render_wildlife(animal: dict, photo_src: dict) -> str:
    depth = 2
    blocks = "".join(f'<h2>{_esc(group["how"])}</h2>'
                     f'{_grid(group["items"], depth, photo_src)}'
                     for group in animal["groups"])
    spec = animal["specialists"]
    total = animal["total"]
    lede = (f'{total} documented plant '
            f'{"relationship" if total == 1 else "relationships"}'
            + (f', {spec} of them as a specialist with no alternative'
               if spec else "") + ".")
    notes = f'<p>{_esc(animal["notes"])}</p>' if animal.get("notes") else ""
    # The description leads when there is one: it is the sentence a reader came
    # for, and the relationship count is a fact about the catalogue.
    blurb = animal.get("description") or ""
    lede_html = (f'<p class="lede">{_esc(blurb)}</p><p>{_esc(lede)}</p>'
                 if blurb else f'<p class="lede">{_esc(lede)}</p>')
    src, credit = _photo(animal, photo_src, _up(depth))
    # `hero-photo narrow`: the same figure the species page uses, capped in
    # width because an animal page is a wide layout and a bee photographed
    # close up does not want to be 60rem across.
    figure = (f'<figure class="hero-photo narrow"><img src="{_esc(src)}" '
              f'alt="{_esc(animal.get("name"))}" loading="lazy">'
              f'<figcaption class="credit src">{_esc(credit)}</figcaption>'
              f'</figure>' if src else "")
    body = f"""
{_crumb([("wildlife/", "Wildlife"), ("", animal["name"])], depth)}
<h1>{_esc(animal["name"])}</h1>
<p class="sci">{_esc(animal.get("scientific_name"))}
  <span class="src">{_esc(animal.get("taxon_label"))}</span></p>
{figure}
{lede_html}
{notes}
{blocks}
"""
    return _page(f'{animal["name"]}: the plants it needs',
                 (f'{blurb} ' if blurb else "")
                 + f'{total} documented plant relationships with '
                   f'{animal.get("scientific_name")}.',
                 body, depth, wide=True)
