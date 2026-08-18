"""
static_site_about.py — the About page and the bibliography behind it.

Split out of `static_site_render` in V2.65, when publishing the 114-work
bibliography pushed that module past its 800-line ceiling. Same shape as
`static_site_species`: the page renderers import the shell helpers from
`static_site_render`, and `write_site` imports them back at call time so the
dependency runs one way only.

The About page is where the catalogue says what it is honest about, what it
deliberately withholds (P12), and — since V2.65 — which works it is citing.
"""

from __future__ import annotations

from src import citations
from src.static_site_render import SITE_NAME, _crumb, _esc, _page


#: Bibliography kinds that are a *work* somebody wrote, as opposed to a
#: collection of records somebody exported. The split is not decoration: a
#: peer-reviewed checklist and a museum specimen dump are different weights of
#: evidence, and a reader deciding whether to trust an edge needs to see which
#: one is behind it.
_PUBLISHED_KINDS = frozenset({
    "study", "field_guide", "monograph", "journal_article", "chapter",
    "checklist", "book",
})


def _sources_section() -> str:
    """The works the catalogue cites, published (V2.65).

    `src.citations` has held this bibliography since V2.42 and it reached 114
    works in V2.62, when the observation re-fetch replaced "GloBI says so" with
    named studies on 2,406 edges. Every surface read it except the website,
    which printed the raw database key instead - so a page promising "a
    documented record with a source" showed the reader
    `globi_www_bumblebeewatch_org`.

    `citations.disclaimer()` is not optional furniture. These details were
    transcribed from source records rather than checked against the works, and
    a bibliography that does not say so is claiming a verification nobody did.
    """
    rows = [r for r in citations.all_sources()
            if not citations.is_placeholder(r.get("key") or "")]
    published, collections_ = [], []
    for r in sorted(rows, key=lambda x: (x.get("authors") or x.get("title") or "").lower()):
        (published if (r.get("kind") or "") in _PUBLISHED_KINDS
         else collections_).append(r)
    n_placeholder = len(citations.all_sources()) - len(rows)

    def items(group):
        return "".join(
            f'<li>{_esc(citations.format_citation(r["key"]))}</li>'
            for r in group)

    out = ['<h2>Where this data came from</h2>',
           f'<p class="lede">{_esc(citations.disclaimer())}</p>']
    if published:
        out.append(f'<h3>Published works ({len(published)})</h3>'
                   f'<ul class="sources">{items(published)}</ul>')
    if collections_:
        out.append(
            f'<h3>Databases and specimen collections ({len(collections_)})</h3>'
            '<p>Occurrence and interaction records exported from a collection '
            'or an aggregator. A record here means somebody observed the '
            'animal on the plant and filed it; it is not a paper arguing the '
            'relationship matters.</p>'
            f'<ul class="sources">{items(collections_)}</ul>')
    if n_placeholder:
        out.append(
            f'<p class="src">{n_placeholder} further entry in the dataset '
            'names no actual work and is omitted here rather than dressed up '
            'as a citation.</p>')
    return "\n".join(out)


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
<p>A reference to the native plants of Alberta and the Canadian prairies, and
the animals that depend on them. It is the catalogue behind <a
href="https://github.com/yarrowyarrowyarrow/Site-and-Pattern">a desktop
application</a> for designing landscapes with native plants: lawn-to-habitat
conversion, pollinator gardens and ecological restoration. That application does
the site analysis, the design and the planting plan; these pages are its
catalogue, published so you can read it without installing anything.</p>

<h2>What it is honest about</h2>
<ul>
  <li><strong>Unknowns stay unknown.</strong> A species with no recorded bloom
  window appears under no month. A plant with no recorded flower colour appears
  under no colour. Absence of a record is never rendered as a fact.</li>
  <li><strong>Evidence travels with the claim.</strong> Recorded ranges carry
  their occurrence counts and a confidence band. A region derived from three
  records is not presented like one derived from three hundred.</li>
  <li><strong>Relationships are documented, not inferred.</strong> Every animal
  listed on a plant page comes from a sourced record.</li>
  <li><strong>Grasses and sedges are not yellow.</strong> They are
  wind-pollinated and have no showy flower, so they get a bucket that says
  so.</li>
  <li><strong>Photographs are credited or absent.</strong> {s['with_photo']} of
  {s['species']} species have an openly-licensed photograph we can attribute.
  The rest show none.</li>
  <li><strong>The region outlines are surveyed.</strong> They come from the
  National Ecological Framework for Canada v2.2, simplified to about 900 m for
  display, so an outline is accurate to roughly a kilometre rather than to the
  metre. Until recently they were hand-traced and this page said so.</li>
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

{_sources_section()}

<h2>Corrections</h2>
<p>Errors and photograph credit problems can be reported as issues on the
<a href="https://github.com/yarrowyarrowyarrow/Site-and-Pattern">project
repository</a>. If a photograph of yours is here and the credit is wrong, or you
would rather it were not here at all, it will be fixed or removed.</p>

<p class="src">Catalogue built {_esc(model["built"])}.</p>
"""
    return _page(f"About the {SITE_NAME} plant catalogue",
                 "How this catalogue is sourced, what it is honest about, and "
                 "what it deliberately does not contain.", body, 1)


