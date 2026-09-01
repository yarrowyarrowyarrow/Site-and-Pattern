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

    The disclaimer above the list is not optional furniture. These details were
    transcribed from source records rather than checked against the works, and
    a bibliography that does not say so is claiming a verification nobody did.
    V2.80 restated it in the author's own voice for this page; both halves of
    `citations.disclaimer()` are still said, and that function is still the
    wording every other surface prints.
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

    # The disclaimer's *substance* in the author's own voice (V2.80), not a
    # weakening of it: the details were transcribed rather than checked, and
    # nobody has confirmed a cited work supports the claim citing it. Both are
    # still said. `citations.disclaimer()` remains the wording every other
    # surface uses; the website speaks in the first person and this is the one
    # page where that difference is the point.
    out = ['<h2>Where the data came from</h2>',
           '<p class="lede">These are the works the data cites. I copied the '
           'details out of the source records without opening the works '
           'themselves, so I can\'t yet tell you whether they back the claim '
           'citing it.</p>',
           '<p>A citation tells you where a claim came from. That\'s all.</p>']
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
<p class="lede">{s['species']:,} native plants of Alberta and Saskatchewan, the
{s['animals']:,} animals documented to use them, and {s['edges']:,}
relationships between plants and animals.</p>

<h2>Who's behind this</h2>
<p>I'm Marci, and I'm in Edmonton. I wanted to share my passion for nature and
encourage people to grow native plants, which are the cornerstone of the
ecosystem. By reducing the friction of deciding which plant is best, and
sharing just how much of the nature we love relies on them, I hope more folks
make the choice to include native plants in their gardens.</p>
<p>While I'm not a botanist, I do have years of permaculture knowledge as well
as years tending my own gardens. I see the life my little native plant garden
attracts and want that for my whole neighbourhood and beyond.</p>

<h2>What it is</h2>
<p>A reference to the native plants of Alberta and Saskatchewan and the animals
that depend on them. The ecoregions here stop at the Saskatchewan border, and
they're not all prairie; a third of these species are recorded from boreal or
montane ground.</p>
<p>It's also the catalogue behind <a
href="https://github.com/yarrowyarrowyarrow/Site-and-Pattern">{_esc(APP_NAME)}</a>,
a desktop app for lawn-to-habitat conversion, pollinator gardens and
restoration planting. I published this website so you can read it without
installing anything.</p>

<h2>What it won't tell you</h2>
<p><strong>Blanks stay blank.</strong> A plant with no recorded bloom window
shows up under no month, and one with no recorded flower colour shows up under
no colour. Nothing gets filled in to make a page look finished.</p>
<p><strong>The evidence comes with the claim.</strong> A region built from
three records doesn't look like one built from three hundred, because the count
sits right next to it.</p>
<p><strong>Every animal on a plant page comes from a sourced record.</strong>
Nothing is inferred from what a related species does.</p>
<p><strong>{s['with_photo']} of {s['species']} species have a photograph I can
credit.</strong> The other {s['species'] - s['with_photo']} show none. If I
can't name the photographer, there's no image.</p>
<p><strong>The occurrence records aren't identification-checked.</strong> They
come out of GBIF as submitted, so misidentifications are in here the way
they're in any occurrence dataset. I'm planning to check them against the
regional floras over <strong>winter '26-27</strong>.</p>

{_sources_section()}

<h2>Corrections</h2>
<p>If something here is wrong, tell me in the
<a href="../feedback/">Feedback</a> section.</p>
<p>Photo credits especially. If a picture of yours is on this site and the
credit is wrong, or you'd rather it weren't here at all, I'll fix it or take it
down.</p>

<p class="src">Catalogue built {_esc(model["built"])}.</p>
"""
    return _page(f"About the {SITE_NAME} plant catalogue",
                 "Where this catalogue comes from, what it is honest about, "
                 "and the works it cites.", body, 1)


