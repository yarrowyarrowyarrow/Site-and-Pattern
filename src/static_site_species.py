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
from src.site_share import photo_card as share_photo
from src.sourcing import describe as sourcing_text
from src.static_site import _first_photo, hub_slug
from src.static_site_points import occurrence_map
from src.static_site_range import range_section
from src.static_site_render import (_crumb, _credit, _esc, _page, _photo_img,
                                    _swatch, _up)


def colour_cell_html(entry: dict, primary: str, depth: int) -> str:
    """The flower-colour cell: a chip per colour, then the provenance mark.

    **Its own function because this cell has been wrong three times, each time
    by re-deriving an answer the entry was already carrying.**

    * V2.75: it re-derived the provenance from the raw row with three
      hard-coded cases, so **81 grass, sedge and rush pages read "not
      verified"** -- a grass is wind-pollinated, so there is no showy flower to
      have got wrong -- and any provenance word added later would have rendered
      no mark at all and read as verified.
    * V2.80: it rendered ``COLOUR_LABELS[classify(row)]``, the PRIMARY colour
      only, while the entry held "Yellow to orange". The prickly pear, whose
      yellow hex under a magenta photograph started the whole flower-colour
      thread, published as "Yellow" on the very build meant to fix it.

    A species with a range gets a chip for each of its colours, because it
    genuinely belongs on both hub pages and ``search_plants`` already returns
    it for either query. ``primary`` is the fallback for a row with no range
    recorded, which is every row no flora has been read for.
    """
    from src.flower_colour import COLOUR_LABELS, COLOUR_SWATCHES

    keys = [k for k in (entry.get("bloom_colours") or ()) if k]
    if not keys:
        keys = [primary] if primary else []
    if not keys:
        return ""
    note = (entry.get("bloom_colour_note") or "").strip()
    mark = f'<span class="src">{_esc(note)}</span>' if note else ""
    chips = " ".join(
        f'<a class="chip" href="{_up(depth)}plants/colour/'
        f'{_esc(hub_slug("colour", key))}/">'
        f'{_swatch(COLOUR_SWATCHES.get(key, ""))}'
        f'{_esc(COLOUR_LABELS.get(key, key))}</a>' for key in keys)
    return f"{chips} {mark}"


def render_species(entry: dict, model: dict, photo_src: dict,
                   include_notes: bool = False) -> str:
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

    eco_block = occurrence_map(entry, depth) + range_section(
        entry, model, depth)

    # The provenance word comes from the entry, which got it from
    # `src.confidence` via `plant_directory._bloom_colour` (V2.75).
    #
    # This block used to re-derive it from the raw row with three hard-coded
    # cases, and the entry it was handed had carried the answer all along. Two
    # consequences, both live on the published site:
    #
    # * **81 grass, sedge and rush pages read "not verified"**, because
    #   `classify` returns `straw` from the plant's TYPE and never looks at the
    #   hex whose `estimated` provenance this was reporting. A grass is not an
    #   unverified purple: it is wind-pollinated, so there is no showy flower
    #   to have got wrong. The desktop has said so since V2.48 and only the
    #   website did not.
    # * Any provenance word added later (`measured`, `flora`, `photo`) would
    #   have rendered no mark at all here and read as verified, which is the
    #   silent-default failure `src.confidence` exists to prevent.
    colour_cell = colour_cell_html(entry, colour, depth)

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
    # Sharing a species page should show that species, not the site default.
    share_img, share_alt = share_photo(photo, photo_src,
                                       entry.get("name") or "")
    return _page(f'{entry.get("name")} ({entry.get("scientific_name")})',
                 desc, body, depth, image=share_img, image_alt=share_alt)


def _native(entry: dict) -> str:
    """The nativity claim with the mark it never had.

    This is the outside review's actual criticism, and the retired generator
    that produced the field says so in its own docstring: *"many species listed
    as native to AB and SK are native to only one. They are reading the output
    of this file."* Flower colour has carried a provenance note since V2.48 and
    the field a reference work is named after has not. `src.nativity` explains
    what replaces this (VASCAN, F144) and why the note is derived rather than
    stored until then.
    """
    from src.nativity import WITHHELD_NOTE, publishable
    value = _esc(_tokens(entry.get("native")))
    if not value:
        return ""
    if publishable(entry):
        return value
    # V2.80: an inferred claim is WITHHELD, not annotated. V2.78 printed it
    # with the heuristic named beside it, which was a real improvement on
    # printing it bare -- and it is still an inference published as this site's
    # answer to the question it is named after. `.src` is the class the
    # flower-colour note has used since V2.48, reused so the provenance marks
    # on this page read as the same kind of statement.
    return f'<span class="src">{_esc(WITHHELD_NOTE)}</span>'


def _phenology(entry: dict) -> str:
    """The bloom-and-fruit bar, or ``""`` when nothing is recorded.

    The page already carried this three times in words -- "Jun-Sep" in a cell,
    twelve month chips, and a sentence -- and none of them answer the question
    a person reading a plant list actually has, which is *what is flowering in
    July*. Six of 430 species have no bloom window and draw nothing rather than
    an empty calendar, which would assert that we checked and they never
    flower (P9).
    """
    from src.phenology_bar import CAVEAT, alt_text, parse_period, phenology_svg
    bloom = parse_period(entry.get("bloom") or "")
    fruit = parse_period(entry.get("fruit") or "")
    svg = phenology_svg(bloom, fruit)
    if not svg:
        return ""
    return (f'<div class="phenology" title="{_esc(CAVEAT)}">{svg}'
            f'<span class="phenology-alt">{_esc(alt_text(bloom, fruit))}'
            f'</span></div>')


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
        ("When", _phenology(entry)),
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
        ("Native to", _native(entry)),
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
              ("Edible parts", _tokens(entry.get("edible_parts")))]
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
    # Prose, not the dict's own key names: this printed
    # `price: ...; availability: ...; notes: ...` on all 422 pages (V2.80).
    # The estimate note rides in its own `.src` mark, like every other
    # provenance mark on this page, so it is not glued into the sentence.
    buying, estimate = sourcing_text(entry.get("sourcing"))
    if buying:
        mark = (f' <span class="src">{_esc(estimate)}</span>'
                if estimate else "")
        parts.append(f"<h3>Buying it</h3><p>{_esc(buying)}{mark}</p>")
    prov = entry.get("provenance") or []
    if prov:
        parts.append("<h3>Where these numbers came from</h3><ul>" + "".join(
            f"<li>{_esc(p)}</li>" for p in prov) + "</ul>")
    if not parts:
        return ""
    return f'<section><h2>Also worth knowing</h2>{"".join(parts)}</section>'
