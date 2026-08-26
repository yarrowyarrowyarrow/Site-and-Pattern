"""
static_site_range.py — "Where it has been recorded", and what that claims.

Design principle P9 — see docs/DESIGN_PHILOSOPHY.md (uncertainty is a feature:
ship ranges and confidence, never false precision).

Split out of :mod:`src.static_site_species` in V2.75, when the guard fired at
351 lines against 340. The seam was already named in that module's own
docstring, which lists "a range map with its evidence" as one of the species
page's four parts — and it is the part an outside botanical review spent most
of its words on, so it earned a file.

**What changed here, and why, because the words are the feature.** The section
used to end:

    "A range seen three times is not the same claim as one seen three hundred,
     so the count travels with the region."

Two things wrong with one sentence. It used *range* to mean one region entry,
where a range is the area a species is documented to occupy — the review
quoted this line back and said, correctly, that defining terms would help. And
it defended the count while saying nothing about the shape: a whole ecoregion
is shaded from records collected anywhere inside it, so a species restricted
to ten kilometres of mountain front draws the same picture as one spread
across the region.

The section now states the three things a reader cannot otherwise get, all of
which existed in the repo already and reached no page:

* **when** the records were retrieved (``plant_ecoregions.source``, on the row
  since schema v59, printed by the desktop and dropped by the website);
* that **unshaded is not absent** — under-collected and absent are
  indistinguishable from here (``src/confidence.py``);
* the floor, imported from :mod:`src.ecoregion_ranges` rather than restated.

And it links out to the live GBIF and iNaturalist maps, which is the review's
own suggestion and the only honest answer to *where in the region*: the points
are not ours to republish, and for rare taxa they are deliberately obscured at
source.
"""

from __future__ import annotations


from src.ecoregion_ranges import MIN_RECORDS
from src.static_site import species_ecoregions
from src.static_site_render import _esc, _up




def range_section(entry: dict, model: dict, depth: int) -> str:
    """The "Where it has been recorded" section, or "" when nothing is."""
    from src.ecoregion_map import (CAVEAT, frame_height,        # noqa: PLC0415
                                   map_svg, region_fill)
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
            evidence = (f"{n} records" if n else
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
        # The map came back in V2.80 after the author reviewed the build, and
        # it sits BELOW the occurrence map rather than instead of it. The two
        # answer different questions and the order says which is the range:
        # the dots are where the plant was found, and this is which classified
        # communities those fall in -- which is how a reader gets from one
        # species to what else grows alongside it, via the region hub pages.
        eco_block = f"""
<section>
  <h2>Which ecoregions the records fall in</h2>
  <div class="ecowrap">
    <figure class="mapfig">{map_svg(regions, width=420,
                                    height=frame_height(420), min_px=0.5,
                                    present_only=True,
                                    title=f'Ecoregions {entry.get("name")} is recorded from')}</figure>
    <div>
      <ul class="ranges">{"".join(rows)}</ul>
      <p class="note">These are counts of records collected
      <em>somewhere</em> in the region, which is the resolution of the
      evidence: the map above shows where inside it. A region with
      {_esc(str(MIN_RECORDS))} records is not the same claim as one with three
      hundred, so the count travels with the region. A region missing from
      this list means nobody has recorded it there, which is not the same as
      the plant being absent.
      {_esc(_range_source(entry))}
      {_esc(CAVEAT)}
      <a href="{_up(depth)}method/">How these counts are made</a>.</p>
      <p class="note">{_observation_links(entry)}</p>
    </div>
  </div>
</section>"""
    return eco_block




def _range_source(entry: dict) -> str:
    """"Retrieved <date>", from the row's own provenance (V2.75).

    ``plant_ecoregions.source`` has carried "GBIF occurrence search, retrieved
    2026-08-18" since schema v59. The desktop directory prints it; the website
    dropped it, so a published range carried a count and a confidence band and
    no indication of *when* — against a source that is live and changes daily,
    and which an outside review specifically asked the currency of.

    Read from the rows rather than written down, so it cannot go stale.
    """
    sources = {(r.get("source") or "").strip()
               for r in entry.get("ranges") or []}
    sources.discard("")
    if not sources:
        return ""
    if len(sources) == 1:
        return f"Source: {sources.pop()}."
    # More than one retrieval date in a single species' rows means a resumed
    # or partial harvest. Say so rather than picking one.
    return "Source: " + "; ".join(sorted(sources)) + "."


def _observation_links(entry: dict) -> str:
    """Out to the live maps (V2.75).

    The review's own suggestion, and the cheapest true thing on this page: the
    snapshot above was taken on one day against a database that changes daily,
    and these links are always current. They also answer the question the
    ecoregion shading structurally cannot — *where in the region* — by handing
    the reader a zoomable map of the actual points.

    Nothing is republished. We link to the record, we do not redraw it, which
    keeps this clear of both the licence question about redistributing
    coordinates and the harm question about rare species whose locations are
    deliberately obscured at source. Those two are why the points are not
    plotted here; see ``scripts/plot_occurrences.py``.

    Keyed on the scientific name, because that is what both sites resolve.
    """
    from urllib.parse import quote_plus                       # noqa: PLC0415

    name = (entry.get("scientific_name")
            or (entry.get("row") or {}).get("scientific_name") or "").strip()
    if not name:
        return ""
    gbif = f"https://www.gbif.org/species/search?q={quote_plus(name)}"
    inat = f"https://www.inaturalist.org/taxa/search?q={quote_plus(name)}"
    return (f'See every observation, live and current, on '
            f'<a href="{_esc(gbif)}" rel="noopener">GBIF</a> or '
            f'<a href="{_esc(inat)}" rel="noopener">iNaturalist</a>.')
