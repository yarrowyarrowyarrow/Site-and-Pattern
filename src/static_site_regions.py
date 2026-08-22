"""
static_site_regions.py — the website's pages about *places*.

Design principle P5 (make the invisible visible) and P9 (ship confidence, never
false precision) — see docs/DESIGN_PHILOSOPHY.md.

Split out of :mod:`src.static_site_render` in V2.68, when the ecoregion map
became a **drill-down** and took that module 57 lines over its ceiling. The seam
is the one the guard asks for rather than an arithmetic one: everything here
answers "where?", and every other page in the renderer answers "what?".

THE THREE LEVELS
-------------------------------------------------------------------------------
The author's ask was *"all 3 layers of the ecoregions selectable on the map ...
choose from the most broad then more specific within that and again more
specific within that"*, with three side-by-side maps offered as the
alternative. Drill-down won on three grounds:

* **The reader's question is sequential.** "Where am I" then "what grows here".
  Three maps at once asks them to cross-reference; one map at a time answers.
* **Twenty-four regions do not fit on one 700px map.** That crowding is what
  produced the abbreviation table that shipped "Parkland" as the name of Aspen
  Parkland. Six ecozones fit comfortably.
* **The nesting is the point.** A drill-down shows containment; three maps
  side by side hide it.

    /map/                          6 ecozones, coloured, clickable
    /plants/ecoregion/zone-*/      the ecoregions inside one ecozone
    /plants/ecoregion/<region>/    the Alberta subregions that overlap it
    /plants/subregion/<sub>/       one subregion, and what it belongs to

THE THIRD LEVEL IS NOT A THIRD TIER, AND THE PAGES SAY SO
-------------------------------------------------------------------------------
Alberta's natural subregions are a *parallel* classification of the same
ground, not a subdivision of the ELC ecoregions. Measured from the shipped
polygons, 12 of the 21 sit ≥90% inside a single ecoregion — but Montane is 42%
Northern Continental Divide across six ecoregions in two ecozones, and Central
Mixedwood is 31% of Mid-Boreal Uplands across nine.

So a subregion page is a **locator**, not a filter result. No species is tagged
at this level and none should be: the derivation resolves an occurrence to the
ecoregion its coordinate falls in, and pushing those records one level finer
would invent precision the records do not have. When one ecoregion accounts for
two thirds of a subregion the page borrows that list and says it is borrowed;
when none does, it lists the overlaps with their shares and lends nothing.
"""

from __future__ import annotations

from src.static_site_render import (SITE_NAME, TAGLINE, _crumb, _esc,
                                    _grid, _page, _up)

def render_map_page(model: dict) -> str:
    from src.ecoregion_map import (CAVEAT, frame_height,         # noqa: PLC0415
                                   legend_html, map_svg)
    hub = {h["key"]: h for h in model["hubs"]}.get("ecoregion", {"pages": []})
    pages = {p["value"]: p["slug"] for p in hub["pages"]}
    link = lambda k: f"../plants/ecoregion/{pages[k]}/" if k in pages else ""
    # The top of the drill-down: six ecozones, not twenty-four ecoregions.
    # Six is a number somebody can hold, the hues are the palette's primary
    # axis, and each one opens onto its own page of ecoregions. Drawing all
    # twenty-four here was what forced the abbreviated labels that ended up
    # calling Aspen Parkland "Parkland" on a public page.
    from src.ecoregion_tree import ECOZONE                     # noqa: PLC0415

    svg = map_svg(width=700, height=frame_height(700), reference=True,
                  level=ECOZONE, link_for=link)
    # Counted, not written down. The lede said "the six regions" for a whole
    # increment after the survey made it twenty-four — and the whole list was
    # sitting right underneath it, contradicting the sentence above it. Two
    # numbers because the page shows two kinds of thing: the moisture niches
    # in `hub["pages"]` are conditions rather than places and belong in
    # neither count.
    from src.ecoregion_tree import ECOREGION, ECOZONE, level_of  # noqa: PLC0415

    levels = {p["value"]: level_of(p["value"]) for p in hub["pages"]}
    n_zones = sum(1 for lv in levels.values() if lv == ECOZONE)
    n_listed = sum(1 for lv in levels.values() if lv == ECOREGION)

    # V2.76: the map DRAWS every ecoregion in the layer; the list below it can
    # only hold the ones with a page, and a region with no species recorded in
    # it gets none. Those were the same number until they were not:
    # `interlake_plain` is a Manitoba ecoregion clipped to a fragment of
    # Saskatchewan and has never had a species. So the page said "23 finer
    # ecoregions" over a picture of 24 shapes, and a reader who counted would
    # have found the extra one and had no way to learn why.
    #
    # Both numbers, and the difference explained in the same breath. The
    # alternative -- quietly printing the smaller one -- is the habit this
    # release exists to break.
    from src.ecoregion_tree import tree                      # noqa: PLC0415
    n_drawn = 0

    def _count(nodes):
        nonlocal n_drawn
        for key, _name, lv, children in nodes:
            if lv == ECOREGION:
                n_drawn += 1
            _count(children)

    _count(tree())
    # The list is already in tree order (each ecozone followed by what is inside
    # it), so the nesting only needs saying in the markup for it to be visible.
    _CLASS = {ECOZONE: " class=\"eco-zone\"", ECOREGION: " class=\"eco-region\""}
    rows = "".join(
        f'<li{_CLASS.get(levels.get(p["value"]), "")}>'
        f'<a href="../plants/ecoregion/{_esc(p["slug"])}/">'
        f'<strong>{_esc(p["name"])}</strong></a> '
        f'<span class="src">{len(p["plants"])} species</span></li>'
        for p in hub["pages"])
    body = f"""
{_crumb([("", "Ecoregion map")], 1)}
<h1>The ecoregions</h1>
<p class="lede">Alberta and Saskatchewan in {n_zones} broad ecozones. Click one
for its plants. The map draws {n_drawn} finer ecoregions inside them; the
{n_listed} with plants recorded in them are listed below.</p>
<figure class="mapfig wide-map">{svg}{legend_html(link, level=ECOZONE)}</figure>
<p class="note">{_esc(CAVEAT)}</p>
<ul class="ranges cols">{rows}</ul>
"""
    return _page(f"Ecoregion map | {SITE_NAME}",
                 "The ecoregions of Alberta and Saskatchewan this catalogue "
                 "against.", body, 1, wide=True)


def render_subregion(page: dict, photo_src: dict) -> str:
    """One Alberta natural subregion: the third level of the drill-down.

    A subregion page is **not** a filter result. No species is tagged at this
    level and none should be — the derivation resolves an occurrence to the
    ecoregion its coordinate falls in, and pushing those records one level
    finer would invent precision the records do not have.

    It is a *locator*. "I am in Dry Mixedgrass" is a sentence somebody in
    southern Alberta can say about their own yard, and this page answers it:
    that is inside Mixed Grassland, and here is what is recorded there.

    When no ecoregion accounts for two thirds of the subregion the page lists
    the overlaps and lends nothing. That is not a gap: Montane spans three
    ecoregions across two ecozones, and there is no one set of plants that
    "the Montane subregion" could honestly mean.
    """
    from src.ecoregion_map import CAVEAT, frame_height, map_svg  # noqa: PLC0415
    from src.ecoregion_tree import SUBREGION                   # noqa: PLC0415

    svg = map_svg(width=420, height=frame_height(420), reference=True,
                  level=SUBREGION, within=page["key"], labels=False,
                  title=f'{page["name"]} within its ecoregions')
    figure = (f'<figure class="mapfig inline">{svg}'
              f'<figcaption class="note">{_esc(CAVEAT)}</figcaption></figure>'
              if svg else "")

    rows = []
    for overlap in page["overlaps"]:
        name = _esc(overlap["name"])
        # An ecoregion with no plants recorded has no page, so it is named
        # rather than linked. Better than a 404 and better than hiding it: the
        # overlap is a real fact about the ground either way.
        label = (f'<a href="../../ecoregion/{_esc(overlap["slug"])}/">{name}</a>'
                 if overlap["slug"] else f"<span>{name}</span>")
        rows.append(f'<li>{label} <span class="src">'
                    f'{overlap["share"]:.0%} of this subregion</span></li>')
    rows = "".join(rows)

    if page["parent_key"]:
        lede = (f'{_esc(page["name"])} is an Alberta natural subregion. '
                f'{page["share"]:.0%} of it lies inside the '
                f'{_esc(page["parent_name"])} ecoregion.')
        borrowed = (
            f'<h2>Plants recorded in {_esc(page["parent_name"])}</h2>'
            f'<p class="note">Ranges are recorded against ecoregions, not '
            f'subregions, so this is the {_esc(page["parent_name"])} list. '
            f'A record inside this subregion is one of these; a plant on this '
            f'list may have been recorded elsewhere in the ecoregion.</p>'
            f'<p class="count">{len(page["plants"])} '
            f'{"plant" if len(page["plants"]) == 1 else "plants"}</p>'
            f'{_grid(page["plants"], 3, photo_src)}')
    else:
        lede = (f'{_esc(page["name"])} is an Alberta natural subregion that '
                f'spans {len(page["overlaps"])} ecoregions, none of which '
                f'accounts for two thirds of it.')
        borrowed = (
            '<h2>Which list applies depends where you are</h2>'
            '<p class="note">Ranges are recorded against ecoregions. This '
            'subregion crosses several, so there is no single species list '
            'that describes it. Follow the ecoregion your own site falls in.'
            '</p>')

    body = f"""
{_crumb([("plants/", "Plants"), ("map/", "Ecoregions"),
         ("", page["name"])], 3)}
<h1>{_esc(page["name"])}</h1>
<p class="lede">{lede}</p>
{figure}
<h2>Where it sits</h2>
<ul class="ranges">{rows}</ul>
{borrowed}
"""
    return _page(f'{page["name"]} | {SITE_NAME}',
                 f'{page["name"]}, an Alberta natural subregion, and the '
                 f'ecoregions it overlaps.', body, 3)


def _hub_extra(hub: dict, page: dict, model: dict) -> str:
    """The map, on ecoregion listings only. Everywhere else the axis has no
    geometry and a decorative map would be noise.

    **This is the middle and bottom of the drill-down.** The overview map
    colours six ecozones; an ecozone's page colours the ecoregions inside it
    and links each one; an ecoregion's page colours the Alberta natural
    subregions that overlap it and links those. Each map answers "what is
    inside this?", which is the question somebody arriving on the page has.

    A moisture niche has no polygon at all, so it gets no map: `riparian` is a
    condition that occurs inside every region, and drawing the whole province
    in the not-recorded grey to say so would be a picture of nothing.
    """
    if hub["key"] != "ecoregion":
        return ""
    from src.ecoregion_map import (CAVEAT, frame_height,        # noqa: PLC0415
                                   legend_html, map_svg)
    from src.ecoregion_tree import (ECOREGION, ECOZONE,         # noqa: PLC0415
                                    SUBREGION, level_of, subregions_in)

    key = page["value"]
    level = level_of(key)
    if not level:
        return ""                                   # riparian / wet_meadow
    # A shape is only ever a link when its page exists. The alternative is a
    # map that 404s on click for any region the catalogue has no records in,
    # which the link checker catches on a fixture and a reader would meet in
    # production as a dead end on the most inviting control on the page.
    region_slug = {p["value"]: p["slug"] for p in hub["pages"]}
    sub_slug = {s["key"]: s["slug"] for s in (model.get("subregions") or [])}
    # Labels off, legend on. These maps are a third of a column wide and the
    # first cut drew the names into the polygons, where "Moist Mixed Grassland"
    # and "Aspen Parkland" landed on top of each other. The legend wraps, links
    # each region, and is generated from the same geometry call as the map, so
    # a key naming a colour that is not on screen is not reachable.
    shown, link, caption = None, None, ""
    if level == ECOZONE:
        shown, within = ECOREGION, key
        def link(k):
            return f"../{region_slug[k]}/" if k in region_slug else ""
        caption = f'Ecoregions of the {page["name"]}'
    elif subregions_in(key) and sub_slug:
        shown, within = SUBREGION, key
        def link(k):
            return f"../../subregion/{sub_slug[k]}/" if k in sub_slug else ""
        caption = f'Natural subregions of {page["name"]}'
    if shown:
        svg = map_svg(width=460, height=frame_height(460), reference=True,
                      level=shown, within=within, labels=False,
                      numbered=True, link_for=link, title=caption)
        key_html = legend_html(link, level=shown, within=within, numbered=True)
    else:
        # Saskatchewan has no subregion layer, so the bottom of the drill-down
        # simply is not there. Falling back to "here is where this region is"
        # rather than pretending otherwise.
        svg = map_svg({key: "high"}, width=360, height=frame_height(360),
                      title=f'{page["name"]} extent')
        key_html = ""
    if not svg:
        return ""
    return (f'<figure class="mapfig inline">{svg}{key_html}'
            f'<figcaption class="note">{_esc(CAVEAT)}</figcaption></figure>')



