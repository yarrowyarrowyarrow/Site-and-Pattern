"""
static_site_species.py — one species, as a web page.

Design principle P5 — see docs/DESIGN_PHILOSOPHY.md.

Split out of :mod:`src.static_site_render` in V2.48, when the architecture
guard fired at 974 lines against 900. The seam is the obvious one: the species
page is the only page here with real internal structure (a facts table, a
documented-animals section, a range map with its evidence, a provenance block),
and every other page in the site is a heading, a paragraph and a grid of cards.

Imports its shared pieces back from the renderer rather than duplicating them,
so escaping, the em-dash normaliser, the photo-attribution gate and the card
markup have exactly one definition each.
"""

from __future__ import annotations

from src import citations
from src.static_site import _first_photo, hub_slug, species_ecoregions
from src.static_site_render import (_crumb, _credit, _esc, _page, _photo_img,
                                    _swatch, _up)


def render_species(entry: dict, model: dict, photo_src: dict,
                   include_notes: bool = False) -> str:
    from src.ecoregion_map import (CAVEAT, frame_height,        # noqa: PLC0415
                                   map_svg, region_fill)
    from src.flower_colour import COLOUR_LABELS, COLOUR_SWATCHES, classify
    depth = 2
    row = entry.get("row") or {}
    colour = classify(row)
    photo = _first_photo(entry)

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

    regions = species_ecoregions(entry)
    eco_block = ""
    if regions:
        # A species' recorded range can name a region no hub page exists for:
        # the moisture niches (riparian, wet_meadow) have no polygon, and a
        # region nothing is filed under gets no page. Link when there is
        # somewhere to go and print plain text when there is not, rather than
        # emitting a link per range and hoping.
        eco_pages = {p["value"]: p["slug"]
                     for h in model["hubs"] if h["key"] == "ecoregion"
                     for p in h["pages"]}
        rows = []
        for r in entry.get("ranges") or []:
            n = int(r.get("occurrences") or 0)
            evidence = (f"{n} occurrence records" if n else
                        "from the catalogue's regional tag, not from "
                        "occurrence records")
            conf = (f', {_esc(r["confidence"])} confidence'
                    if r.get("confidence") else "")
            name = f'<strong>{_esc(r.get("name"))}</strong>'
            slug = eco_pages.get(r.get("key") or "")
            if slug:
                name = (f'<a href="{_up(depth)}plants/ecoregion/'
                        f'{_esc(slug)}/">{name}</a>')
            # The swatch is what connects this line to the shape on the map,
            # now that each region has a colour of its own. It carries the
            # confidence band too, so it matches the fill exactly rather than
            # being an approximation of it.
            keyed = r.get("key") in regions
            fill, _ = region_fill(r.get("key") or "", r.get("confidence") or "")
            dot = (f'<span class="ecokey-sw" style="background:{fill}"></span>'
                   if keyed else "")
            cls = ' class="haskey"' if keyed else ""
            rows.append(
                f'<li{cls}>{dot}{name}'
                f'<span class="src"> {_esc(r.get("where") or "")}: '
                f'{evidence}{conf}</span></li>')
        eco_block = f"""
<section>
  <h2>Where it has been recorded</h2>
  <div class="ecowrap">
    <figure class="mapfig">{map_svg(regions, width=420, height=frame_height(420),
                                    title=f'Range of {entry.get("name")}')}</figure>
    <div>
      <ul class="ranges">{"".join(rows)}</ul>
      <p class="note">A range seen three times is not the same claim as one
      seen three hundred, so the count travels with the region.
      {_esc(CAVEAT)}</p>
    </div>
  </div>
</section>"""

    colour_cell = ""
    if colour:
        src = (row.get("flower_colour_source") or "").strip()
        mark = ""
        if src in ("name", "epithet"):
            why = ("the species' own common name"
                   if src == "name" else "the Latin epithet")
            mark = f'<span class="src" title="Checkable against {why}">checked</span>'
        elif src == "estimated":
            mark = ('<span class="src" title="A genus-level default, not '
                    'observed for this species">not verified</span>')
        colour_cell = (
            f'<a class="chip" href="{_up(depth)}plants/colour/'
            f'{_esc(hub_slug("colour", colour))}/">'
            f'{_swatch(COLOUR_SWATCHES.get(colour, ""))}'
            f'{_esc(COLOUR_LABELS.get(colour, colour))}</a> {mark}')

    body = f"""
{_crumb([("plants/", "Plants"), ("", entry.get("name") or "")], depth)}
<article class="species">
  <header class="spechead">
    <div>
      <h1>{_esc(entry.get("name"))}</h1>
      <p class="sci">{_esc(entry.get("scientific_name"))}</p>
      <p class="badges">{badges}</p>
    </div>
  </header>
  {hero}
  {_facts_table(entry, colour_cell, depth, model)}
  {_wildlife_section(entry, model, depth)}
  {eco_block}
  {_extras_section(entry, include_notes)}
</article>
"""
    desc = (f'{entry.get("name")} ({entry.get("scientific_name")}): '
            f'{entry.get("sun") or "conditions unrecorded"}, '
            f'{entry.get("bloom") or "bloom window unrecorded"}, '
            f'{(entry.get("wildlife") or {}).get("total", 0)} documented '
            f'animal relationships.')
    return _page(f'{entry.get("name")} ({entry.get("scientific_name")})',
                 desc, body, depth)


def _facts_table(entry: dict, colour_cell: str, depth: int,
                 model: dict) -> str:
    facets = entry.get("facets") or {}
    months = facets.get("bloom") or []
    hub = {h["key"]: h for h in model["hubs"]}
    month_pages = {p["value"]: p["slug"]
                   for p in hub.get("bloom", {}).get("pages", [])}
    month_links = " ".join(
        f'<a class="chip" href="{_up(depth)}plants/blooming-in/'
        f'{_esc(month_pages[m])}/">{_esc(_MONTH_NAMES[int(m) - 1])}</a>'
        for m in months if m in month_pages)

    rows = [
        ("Type", _esc(entry.get("plant_type"))),
        ("Sun", _esc(_tokens(entry.get("sun")))),
        ("Water", _esc(_tokens(entry.get("water")))),
        ("Soil", _esc(entry.get("soil_ph"))),
        ("Hardiness", _esc(entry.get("zones"))),
        ("Mature height", _esc(_metres(entry.get("mature_height_m")))),
        ("Mature spread", _esc(_metres(entry.get("mature_canopy_m")))),
        ("Spacing", _esc(_metres(entry.get("spacing_m")))),
        ("Years to maturity", _esc(entry.get("years_to_maturity"))),
        ("Bloom", _esc(entry.get("bloom"))),
        ("Flower colour", colour_cell),
        ("In bloom", month_links),
        ("Fruit", _esc(entry.get("fruit"))),
        ("Native to", _esc(_tokens(entry.get("native")))),
    ]
    cells = "".join(f"<tr><th>{_esc(label)}</th><td>{value}</td></tr>"
                    for label, value in rows if value)
    morph = entry.get("morphology") or ""
    if isinstance(morph, (list, tuple)):
        morph = "; ".join(str(m) for m in morph)
    morph_html = f'<p class="morph">{_esc(morph)}</p>' if morph else ""
    return (f'<section><h2>Growing it</h2><table class="facts">{cells}</table>'
            f"{morph_html}</section>")


_MONTH_NAMES = ("January", "February", "March", "April", "May", "June", "July",
                "August", "September", "October", "November", "December")


def _tokens(value) -> str:
    """``"full_sun,partial shade"`` becomes ``"Full sun, partial shade"``.

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
                'That is a gap in the catalogue, not evidence that nothing '
                'uses it.</p></section>')
    by_name = {a["name"]: a["slug"] for a in model["wildlife"]}
    blocks = []
    for group in wildlife.get("groups") or []:
        items = []
        for item in group.get("items") or []:
            label = _esc(item.get("name"))
            slug = by_name.get(item.get("name") or "")
            if slug:
                label = (f'<a href="{_up(depth)}wildlife/{_esc(slug)}/">'
                         f"{label}</a>")
            star = ('<span class="star" title="Specialist: has nowhere else to '
                    'go">&#9733;</span>') if item.get("specialist") else ""
            # A source KEY is not a citation (V2.65). This printed the raw
            # database slug — `globi_www_bumblebeewatch_org` — on 290 species
            # pages, next to prose promising "a documented record with a
            # source". The bibliography that would make it readable has been
            # sitting in `src.citations` since V2.42 and grew to 114 works in
            # V2.62; the website was the one surface never wired to it.
            # Short form inline, full reference in the tooltip, and an
            # unregistered key falls back to itself rather than vanishing.
            src = ""
            if item.get("source"):
                key = item["source"]
                src = (f'<span class="src" '
                       f'title="{_esc(citations.format_citation(key))}">'
                       f'{_esc(citations.format_citation(key, short=True))}'
                       f'</span>')
            items.append(f"<li>{label} {star}{src}</li>")
        blocks.append(f'<h3>{_esc(group.get("how"))}</h3>'
                      f'<ul class="animals">{"".join(items)}</ul>')
    spec = int(wildlife.get("specialists") or 0)
    note = (f"{total} documented relationships"
            + (f", {spec} with a specialist that has no alternative"
               if spec else "") + ".")
    return (f'<section><h2>Documented animals</h2><p class="lede">{_esc(note)}'
            f'</p>{"".join(blocks)}</section>')


def _extras_section(entry: dict, include_notes: bool = False) -> str:
    parts = []
    fields = [("Safety", entry.get("safety")),
              ("Edible parts", _tokens(entry.get("edible_parts"))),
              ("Buying it", entry.get("sourcing"))]
    # `notes` is unaudited free text and ~43 rows of it describe traditional
    # medicinal and plant-use practice. Publishing that to the open web is a
    # different act from showing it in a desktop panel: indexed, scraped,
    # archived, effectively irrevocable, and P12 forbids operationalizing that
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
