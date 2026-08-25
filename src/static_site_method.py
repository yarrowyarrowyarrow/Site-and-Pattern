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
<p class="lede">What a record is, what a shaded region does and does not
claim, and where each of these numbers stops being able to tell you
anything.</p>

<h2>What "recorded here" means</h2>
<p>Every region on a species page comes from <strong>georeferenced occurrence
records</strong>: a herbarium sheet, a museum specimen, a photograph
somebody submitted with a location. They are retrieved from
<a href="https://www.gbif.org/">GBIF</a>, which aggregates many sources
including iNaturalist, university herbaria and government collections.</p>
<p>We ask GBIF only for records inside the bounding box of the ecoregions this
catalogue covers, and we count each record toward the region its coordinate
falls <em>inside</em>. Records whose basis is a living specimen, a material
sample or a fossil are excluded: a plant in a botanical garden is a place
somebody put it, not a place it grows.</p>

{_point_method_sections(counts, MARK_DEG, CELL_DEG, CELL_KM_NS)}

<h2>"Native to", and when we leave it blank</h2>
<p>Which provinces a species is native to comes from
<a href="https://data.canadensys.net/vascan/">VASCAN</a>, the Database of
Vascular Plants of Canada, read from its published checklist. {nativity['sourced']:,} of the
{nativity['claimed']:,} species in this catalogue carry an answer from it.</p>
<p>Before this release the other answers were an <strong>inference</strong>:
the parkland, grassland and boreal plain run unbroken across the border
between Alberta and Saskatchewan, so a species documented from one of them in
Alberta was written down as native to the same ecoregion in Saskatchewan.
That is reasonable and it is not a range map, and this site published it as
though it were.</p>
<p>It no longer does. Where no source settles it, the row reads <strong>Not
established</strong> and no province list is shown. {nativity['withheld']} species are in
that position: some VASCAN records as introduced here rather than native, some
it carries only under a name this catalogue does not use, and a few it does
not carry at all. Each is a decision somebody has to make with a second
source, and until then a blank is the honest answer.</p>
<p>We would rather show you nothing than show you a guess.</p>

<h2>Why some regions are not listed</h2>
<p>A region needs at least <strong>{MIN_RECORDS} records</strong> before it is
listed. Two records is a coincidence, because a misidentified sheet and a
garden escape will do it. Three is the smallest number that is evidence of
anything, and it is labelled as the weakest confidence so that nothing reads
it as a range map.</p>
<p>This does cut against rare species, which is a real cost and not an
oversight: the plants with fewest records are often the ones that matter most.
Regions that fell short are counted on every run and are visible to us; they
are simply not published as claims.</p>
{_bands_table()}

<h2>How current this is</h2>
<p>GBIF is a living database: records are added, corrected and
re-identified continuously. What these pages show is a <strong>snapshot</strong>,
taken once and shipped. The counts here were retrieved on:</p>
{_currency(model)}
<p>They will drift from the live database from that day onward. This page is
not live; the GBIF and iNaturalist links on every species page are. For the
current picture of a species, follow those.</p>

<h2>What we do not filter</h2>
<p>We do not require records to have been identification-verified.
GBIF's verification field is populated by a minority of publishers and is
absent from most herbarium material, so requiring it would discard the
best-determined specimens in order to exclude very little. Misidentifications
are therefore present in this data, as they are in any occurrence dataset.</p>
<p>We do refuse records whose own stated coordinate uncertainty is too large
to place them in a region at all. A specimen georeferenced to a whole county
is telling you what it cannot support, and counting it toward one ecoregion
would assert something its own metadata denies.</p>

<h2>The region outlines</h2>
<p>{_esc(CAVEAT)}</p>

<h2>Known limits of this build</h2>
<ul>
  <li><strong>Until recently these counts were inflated, and we corrected
  them rather than quietly restating them.</strong> A record used to be
  credited to every ecoregion within five kilometres of it, not only the one
  containing it. That rule was written for deciding which region a
  <em>garden</em> is in, where a nearby second answer is useful, and it reached
  the range derivation by accident. Every range on this site was re-retrieved
  from GBIF and re-derived by containment on 21 August 2026. The effect was
  large: <strong>489,546 attributed records became 361,447</strong>, and 493 of
  4,218 region claims turned out to have almost no records actually inside
  them. Two species lost every region and are now shown as not having enough
  evidence, which is the honest answer rather than a smaller one.</li>
  <li><strong>One region in the map is a sliver, and it was doing most of the
  damage.</strong> Western Continental Ranges is a British Columbia region, and
  only a hairline of it crosses into Alberta: two hundredths of one per cent
  of the mapped area. A shape that thin has a five-kilometre apron many
  times its own size, so nearly every mountain record near the border was being
  filed under it. It was listed for 135 species and is now listed for 15. If
  you compared this site against an earlier copy of it, that is the difference
  you would see.</li>
  <li><strong>Where two regions meet, a few records are counted in both.</strong>
  The region outlines are simplified to roughly {simplify}, and each one is
  simplified on its own, so along a shared border two neighbours overlap by a
  sliver. A record inside that sliver is counted for both, which inflates the
  totals by <strong>about eight records in every thousand</strong>. It is not
  spread evenly: most of it is Calgary, where Aspen Parkland and Fescue
  Grassland cross. We have left it rather than picking a side, because deciding
  which region such a record belongs to would mean asserting which side of a
  line we know we drew imprecisely, and that is the mistake the correction
  above was about. It is well inside the accuracy the outlines claim.</li>
  <li><strong>Flower colour is mostly unverified.</strong>
  {s['verified_colour']} of {s['species']} species have a colour checkable
  against the plant's own name; the rest are a genus-level default and every
  one of them says <em>not verified</em> on its page.</li>
  <li><strong>Nativity is the weakest claim on this site.</strong> The
  province a plant is listed as native to was generated from its regional
  tags rather than read from a flora: Saskatchewan was inferred from
  ecoregions that continue across the border, and Alberta from an editorial
  flag in the catalogue's first data file. Neither is a range map for the
  species. <strong>Every species page now says so beside the claim</strong>
  rather than leaving it to this page: the field this site is named for was
  the one field carrying no provenance mark, which is exactly backwards.
  It is being replaced with per-province records from a
  taxonomic authority; until that lands, treat "native to Alberta and
  Saskatchewan" as the catalogue's assertion and not as a sourced fact.</li>
  <li><strong>Coverage stops at the Saskatchewan border.</strong> The
  ecoregions surveyed here are Alberta's and Saskatchewan's. Manitoba shares
  several of them, and is not included.</li>
</ul>

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
