"""
static_site_about.py — the About page and the bibliography behind it.

Split out of `static_site_render` in V2.65, when publishing the 114-work
bibliography pushed that module past its 800-line ceiling. Same shape as
`static_site_species`: the page renderers import the shell helpers from
`static_site_render`, and `write_site` imports them back at call time so the
dependency runs one way only.

The About page is where the catalogue says what it is honest about and — since
V2.65 — which works it is citing.

V2.71 cut the long "What it does not contain" section at the owner's request,
as part of a plainer-language pass. That did **not** weaken P12: the one-line
statement ("no Indigenous ecological knowledge, plant-use tradition or
land-management practice … and none should be inferred from it") lives in the
site footer and therefore appears on every page, and the withholding itself was
never a promise made in prose — it is enforced in code by
`site_facets.WITHHELD_ROLES` and by notes being off by default.
"""

from __future__ import annotations

from src import citations
from src.branding import APP_NAME
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
the animals that depend on them.</p>
<p>It is the catalogue behind <a
href="https://github.com/yarrowyarrowyarrow/Site-and-Pattern">{_esc(APP_NAME)}</a>,
a desktop application for lawn-to-habitat conversion, pollinator gardens and
restoration planting. {_esc(APP_NAME)} is for the site analysis, the design and
the planting plan. These pages are its catalogue, published so you can read it
without installing anything.</p>

<h2>What it is honest about</h2>
<ul>
  <li><strong>Unknowns stay unknown.</strong> A plant with no recorded bloom
  window appears under no month, and one with no recorded flower colour appears
  under no colour. A blank is never filled in.</li>
  <li><strong>Evidence travels with the claim.</strong> Every recorded range
  carries how many records it rests on, so a region built from three sightings
  does not look like one built from three hundred.</li>
  <li><strong>Relationships are documented, not guessed.</strong> Every animal
  on a plant page comes from a sourced record.</li>
  <li><strong>Photographs are credited or absent.</strong> {s['with_photo']} of
  {s['species']} species have an openly-licensed photograph we can attribute.
  The rest show none.</li>
  <li><strong>The region outlines are surveyed.</strong> They come from the
  National Ecological Framework for Canada v2.2, simplified to about 900 m for
  display, so an outline is accurate to roughly a kilometre rather than to the
  metre.</li>
</ul>

{_sources_section()}

<h2>Corrections</h2>
<p>Errors and photograph credit problems can be reported as issues on the
<a href="https://github.com/yarrowyarrowyarrow/Site-and-Pattern">project
repository</a>. If a photograph of yours is here and the credit is wrong, or you
would rather it were not here, it will be fixed or removed.</p>

<p class="src">Catalogue built {_esc(model["built"])}.</p>
"""
    return _page(f"About the {SITE_NAME} plant catalogue",
                 "Where this catalogue comes from, what it is honest about, "
                 "and the works it cites.", body, 1)


