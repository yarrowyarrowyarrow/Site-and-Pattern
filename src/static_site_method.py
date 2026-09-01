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
    # A sentence rather than a bare bold string (V2.80): the line above it used
    # to be "Retrieved on:" and the author's rewrite cut that scaffolding, so
    # the date has to read as prose on its own. Still off the rows, never typed
    # -- the split below only re-punctuates what the row already says, and a
    # source not written in that shape is printed verbatim instead of forced.
    return "<p>" + "</p><p>".join(_sentence(s) for s in sorted(sources)) + "</p>"


def _sentence(source: str) -> str:
    """``"GBIF occurrence search, retrieved 2026-08-25"`` as a sentence."""
    what, sep, when = source.partition(", retrieved ")
    if not sep:
        return f"<strong>{_esc(source)}</strong>."
    return f"The <strong>{_esc(what)}</strong> was retrieved {_esc(when)}."


def _border_margin() -> tuple:
    """``(margin_phrase, discarded_phrase)`` for the near-border rule (V2.81).

    Both read out of the shipped ``plant_ecoregions.json`` envelope, which the
    seeder writes with the margin it actually applied and a tally of what that
    cost. Restating either here would be this page's own failure mode: a page
    about how the numbers are made, carrying a number nobody remade.

    A file from before V2.81 has neither, and then the second half is empty
    rather than invented.
    """
    from src.ecoregion import SIMPLIFICATION_M                  # noqa: PLC0415
    from src.ecoregion_ranges import load_document              # noqa: PLC0415

    doc = load_document()
    margin = doc.get("boundary_margin_m") or SIMPLIFICATION_M
    tally = doc.get("tally") or {}
    seen = sum(v for v in tally.values() if isinstance(v, int))
    unsettled = tally.get("unsettled") or 0
    share = ""
    if seen and unsettled:
        # Carries its own leading space and trailing stop, so the sentence that
        # embeds it reads correctly when there is no tally to report. Written
        # the other way first, and a build against a pre-V2.81 file would have
        # published "to count for it.. It also means".
        # First person, because the page around it is: V2.80 rewrote the Method
        # copy in the author's own voice and a generated clause dropped into
        # the middle of it has to speak the same way.
        share = (f" That sets aside {unsettled / seen:.1%} of the records I "
                 f"hold, which then count for no region rather than a guess.")
    return f"{margin:.0f} m", share


def _simplification() -> str:
    """How coarse the drawn outlines are, in the words the caveat already uses.

    Read out of :data:`src.ecoregion_map.CAVEAT` rather than restated, because
    that string is itself checked against the polygon file's own provenance --
    and because V2.69 shipped a caveat that had quietly become false and stayed
    on 432 public pages for a whole increment.
    """
    import re                                               # noqa: PLC0415
    from src.ecoregion_map import CAVEAT                     # noqa: PLC0415
    m = re.search(r"(\d[\d,]*\s*(?:m|km|metres|kilometres))", CAVEAT)
    return m.group(1) if m else "a kilometre"




def _nativity_claim(nativity: dict) -> str:
    """How many species carry a VASCAN answer, said correctly at either end.

    **This sentence shipped reading "The other 0 read Not established", with a
    paragraph after it explaining why those zero species are unresolved.** It
    was written when 20 were withheld and stayed on the page when the renames
    of V2.80 took the number to none, because the count was computed and the
    prose around it was not. A number that cannot be wrong sitting inside a
    sentence that can is the same bug the "computed, never written down" rule
    exists to prevent, one level up.

    So the *shape* of the sentence follows the count too: no withheld species
    and the paragraph about them does not exist.
    """
    if not nativity["withheld"]:
        return (f"At the moment all {nativity['claimed']:,} species carry an "
                f"answer from it.")
    return (f"{nativity['sourced']:,} of {nativity['claimed']:,} species carry "
            f"an answer from it. The other {nativity['withheld']:,} read "
            f"<strong>Not established</strong> and show no province list, "
            f"because VASCAN either records them as introduced here, carries "
            f"them only under a name this catalogue does not use, or does not "
            f"carry them at all. I would rather show you nothing than a guess.")


def render_method(model: dict) -> str:
    """The Method page."""
    from src.ecoregion_map import CAVEAT, frame_height, map_svg
    from src.ecoregion_ranges import MIN_RECORDS
    from src.species_range import CELL_DEG, CELL_KM_NS
    from src.static_site_points import (_nativity_counts,
                                        _point_method_sections,
                                        _published_counts)
    counts = _published_counts()
    nativity = _nativity_counts()

    simplify = _simplification()
    margin, discarded = _border_margin()
    body = f"""
{_crumb([("", "Method")], 1)}
<h1>How these pages are made</h1>
<p class="lede">What's behind the numbers and their reliability.</p>

<h2>What counts as a record</h2>
<p>Everything mapped here is a <strong>georeferenced occurrence</strong> (a
herbarium sheet, a museum specimen, or a photo someone uploaded with a location
attached). It all comes through <a href="https://www.gbif.org/">GBIF</a>, which
pools iNaturalist, university herbaria and government collections into one
search.</p>

{_point_method_sections(counts, CELL_DEG, CELL_KM_NS)}

<h2>"Native to," and the blanks in it</h2>
<p>Province-level native status comes from
<a href="https://data.canadensys.net/vascan/">VASCAN</a>, the Database of
Vascular Plants of Canada. {_nativity_claim(nativity)} So far I have included
AB and SK and plan to continue this project across the rest of Canada's
provinces and territories.</p>

<h2>The ecoregions</h2>
<figure class="mapfig methodfig">{map_svg(None, width=520,
                                          height=frame_height(520),
                                          reference=True,
                                          title="The ecoregions this catalogue covers")}
<figcaption class="note">{_esc(CAVEAT)}</figcaption></figure>
<p>Every species page lists the ecoregions its records fall in. That's how you
get from one plant to the rest of the community it sits in, which is part of
the reason this site exists.</p>
<p>A region needs <strong>{MIN_RECORDS} records</strong> before it shows up.
Two records can be a misidentified sheet or garden escapes, and I'd rather not
build a plant community out of that. The threshold costs me rare species which
are the ones most worth finding but that is the trade off at the moment.</p>
{_bands_table()}

<h2>How current this is</h2>
{_currency(model)}
<p>GBIF changes daily and this page does not. The GBIF and iNaturalist links
on every species page are live; follow those for the current picture.</p>

<h2>Known limits</h2>
<p><strong>Misidentifications are in here.</strong> I don't filter for
identification-verified records. That flag is missing from most herbarium
material, so requiring it would throw out the best-determined specimens in
order to exclude very little.</p>
<p><strong>Records near a border don't get counted.</strong> Each ecoregion
outline is simplified to roughly {simplify} on its own, so within about that
distance of one I can't tell which side of it a record really sits. A record
has to be more than <strong>{margin}</strong> inside a region before I count it
for that region.{discarded} It also stops a record being counted twice, which
used to happen where two outlines overlap by a sliver: mostly around Calgary,
where Aspen Parkland and Fescue Grassland run into each other.</p>
<p><strong>Flower colour is imperfect.</strong> I have verified some of the
flower colours but not all. This is a work in progress. If you notice gross
errors please <a href="../feedback/">send me feedback</a>.</p>

<h2>Corrections</h2>
<p>Not all the information has been checked by me by hand. If you come across
something you know to be false I would appreciate any
<a href="../feedback/">feedback</a>. The catalogue and its underlying data are
<a href="https://github.com/yarrowyarrowyarrow/Site-and-Pattern">public</a> and
I'd like this public facing resource to be as accurate as possible.</p>
"""
    return _page("How these pages are made",
                 "Where the occurrence records come from, what the map does "
                 "and does not claim, and how far these numbers can be "
                 "trusted.", body, 1)
