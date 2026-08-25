"""
static_site_method.py — how a range on this site is made, in the reader's words.

Design principle P9 — see docs/DESIGN_PHILOSOPHY.md (uncertainty is a feature:
ship ranges and confidence, never false precision).

Why this page exists (V2.75)
----------------------------
An outside botanical review read the published catalogue and asked, in
substance, five questions the site could not answer from any page on it:

* what does "a range seen three times" mean, and is *range* the right word;
* where did the observations come from, and **as of when** — the source is
  live and changes daily;
* where *in* the ecoregion are the records — scattered, or one cluster;
* why is a region with one or two records not listed;
* what is shaded, given that ecoregions are not ranges.

Every one of those had an answer already in the repo. The retrieval date was
in ``plant_ecoregions.source`` and on the desktop screen. The floor was
``ecoregion_ranges.MIN_RECORDS``. The near-misses were computed by
``dropped_regions`` every run. None of it reached a reader, so the site made
confident-looking claims with the uncertainty stripped off — which is P9
failing in the one place it is expensive.

The page is its own module because ``static_site_render.py`` sits near its
line ceiling and V2.73 already established the pattern: a page is a page, not
another paragraph in the renderer.

**Numbers here are computed, never written down.** The floor and the bands are
imported from the module that owns them, and the counts come from the build.
A hand-typed figure on this page in particular would be a page about honesty
that had stopped being accurate.
"""

from __future__ import annotations

from src.static_site_render import _crumb, _esc, _page


def _bands_table() -> str:
    """The confidence bands, from the module that owns them."""
    from src.ecoregion_ranges import CONFIDENCE_BANDS, MIN_RECORDS

    bands = sorted(CONFIDENCE_BANDS, key=lambda row: -row[0])
    rows = []
    for i, (floor, label) in enumerate(bands):
        upper = bands[i - 1][0] - 1 if i else None
        span = f"{floor} or more" if upper is None else f"{floor}–{upper}"
        rows.append(f"<tr><td>{_esc(label)}</td><td>{_esc(span)}</td></tr>")
    rows.append(
        f"<tr><td>not listed</td><td>fewer than {MIN_RECORDS}</td></tr>")
    return ("<table class=\"facts\"><thead><tr><th>Confidence</th>"
            "<th>Records in the region</th></tr></thead><tbody>"
            + "".join(rows) + "</tbody></table>")


def _currency(model: dict) -> str:
    """When the occurrence data was retrieved, off the rows themselves."""
    sources = set()
    for entry in model.get("species") or []:
        for row in entry.get("ranges") or []:
            source = (row.get("source") or "").strip()
            if source:
                sources.add(source)
    if not sources:
        return ("<p>No occurrence source is recorded on the ranges in this "
                "build, which is itself worth knowing.</p>")
    return ("<p>" + "</p><p>".join(
        f"<strong>{_esc(s)}</strong>" for s in sorted(sources)) + "</p>")


def _simplification() -> str:
    """How coarse the drawn outlines are, in the words the caveat already uses.

    Read out of :data:`src.ecoregion_map.CAVEAT` rather than restated, because
    that string is itself checked against the polygon file's own provenance --
    and because V2.69 shipped a caveat that had quietly become false and stayed
    on 432 public pages for a whole increment.
    """
    import re                                               # noqa: PLC0415
    from src.ecoregion_map import CAVEAT                    # noqa: PLC0415
    m = re.search(r"(\d[\d,]*\s*(?:m|km|metres|kilometres))", CAVEAT)
    return m.group(1) if m else "a kilometre"




def render_method(model: dict) -> str:
    """The Method page."""
    from src.ecoregion_map import CAVEAT
    from src.ecoregion_ranges import MIN_RECORDS
    from src.occurrence_points import MARK_DEG
    from src.species_range import CELL_DEG, CELL_KM_NS
    from src.static_site_points import (_nativity_counts,
                                        _point_method_sections,
                                        _published_counts)
    counts = _published_counts()
    nativity = _nativity_counts()

    s = model["stats"]
    simplify = _simplification()
    body = f"""
{_crumb([("", "Method")], 1)}
<h1>How these pages are made</h1>
<p class="lede">Where the data comes from, and where it stops being able to
tell you anything.</p>

<h2>What a record is</h2>
<p>A <strong>georeferenced occurrence record</strong>: a herbarium sheet, a
museum specimen, or a photograph submitted with a location. All of them come
from <a href="https://www.gbif.org/">GBIF</a>, which aggregates iNaturalist,
university herbaria and government collections. Records based on a living
specimen, a material sample or a fossil are excluded: a plant in a botanical
garden is a place somebody put it.</p>

{_point_method_sections(counts, MARK_DEG, CELL_DEG, CELL_KM_NS)}

<h2>"Native to", and when we leave it blank</h2>
<p>Which provinces a species is native to comes from
<a href="https://data.canadensys.net/vascan/">VASCAN</a>, the Database of
Vascular Plants of Canada. {nativity['sourced']:,} of {nativity['claimed']:,}
species carry an answer from it.</p>
<p>The other {nativity['withheld']} read <strong>Not established</strong> and
show no province list. VASCAN records some of them as introduced here, carries
some only under a name this catalogue does not use, and does not carry a few
at all. Each needs a second source before we can say anything.</p>
<p>We would rather show you nothing than show you a guess.</p>

<h2>The ecoregion counts</h2>
<p>Below the map, each species lists the ecoregions its records fall in. A
region needs at least <strong>{MIN_RECORDS} records</strong> to be listed: two
can be a misidentified sheet and a garden escape. This cuts against rare
species, which is a real cost. A region missing from the list means nobody has
recorded the plant there.</p>
{_bands_table()}

<h2>How current this is</h2>
<p>A <strong>snapshot</strong>, taken once and shipped. Retrieved on:</p>
{_currency(model)}
<p>GBIF changes daily and this page does not. The GBIF and iNaturalist links
on every species page are live; follow those for the current picture.</p>

<h2>Known limits</h2>
<ul>
  <li><strong>Misidentifications are in this data.</strong> We do not require
  records to be identification-verified: that field is absent from most
  herbarium material, so requiring it would discard the best-determined
  specimens to exclude very little.</li>
  <li><strong>Where two regions meet, a few records are counted in both.</strong>
  The outlines are simplified to roughly {simplify} and each is simplified on
  its own, so neighbours overlap by a sliver along a shared border. That
  inflates the region totals by about <strong>eight records in a
  thousand</strong>, most of it around Calgary where Aspen Parkland and Fescue
  Grassland cross.</li>
  <li><strong>Flower colour is mostly unverified.</strong>
  {s['verified_colour']} of {s['species']} species have a colour checkable
  against the plant's own name; the rest are a genus-level default and say
  <em>not verified</em> on the page.</li>
  <li><strong>Coverage stops at the Saskatchewan border.</strong> Manitoba
  shares several of these ecoregions and is not included.</li>
</ul>

<h2>The region outlines</h2>
<p>{_esc(CAVEAT)}</p>

<h2>Corrections</h2>
<p>These pages are wrong in places, and the useful thing to do with an error
is report it. The catalogue and its data are
<a href="https://github.com/yarrowyarrowyarrow/Site-and-Pattern">public</a>,
including the record of species removed for not being native here and the
authority for each removal.</p>
"""
    return _page("How these pages are made", "Where the occurrence records "
                 "come from, what a shaded region claims, and where these "
                 "numbers stop being able to tell you anything.",
                 body, 1)
