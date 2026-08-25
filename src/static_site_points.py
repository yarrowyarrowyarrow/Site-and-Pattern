"""
static_site_points.py — the records on the page, and the toggle between them.

Design principle P9 — see docs/DESIGN_PHILOSOPHY.md.

Split out of :mod:`src.static_site_range` in V2.80, when the architecture guard
fired at 291 lines against 260. The seam is a real one rather than a place to
cut: that module answers *which classified communities is this recorded from*,
counted per ecoregion, and this one answers *where exactly was it found*, drawn
from the records themselves. They were one file only because the ecoregion map
used to be the answer to both.

Holds the two shipped data files' readers as well, because 430 species pages are
rendered in one process and a page that re-read a 2.7 MB file would parse 1.2 GB
to draw the same dots.
"""

from __future__ import annotations

import json
from functools import lru_cache

from src.static_site_render import _esc, _up

# ── The shipped range data, read once ────────────────────────────────────────
#
# 430 species pages are rendered in one process. Reading a 2.7 MB points file
# per page would be 1.2 GB of parsing to draw the same dots.

@lru_cache(maxsize=1)
def _range_cells() -> dict:
    """``{species: [(lat, lng, records), ...]}`` from `data/plant_ranges.json`."""
    from src.species_range import parse_document
    return parse_document(_read("plant_ranges.json"))


@lru_cache(maxsize=1)
def _points() -> dict:
    """``{species: {"s": [...], "o": [...]}}`` from the shipped point file."""
    from src.occurrence_points import parse_document
    return parse_document(_read("plant_occurrence_points.json"))


def _read(name: str) -> dict:
    """One shipped JSON file, or ``{}``.

    Missing is not an error: the two files are derived offline from a cache
    that is never shipped, and a checkout that has not run the seeders should
    render a page without a map rather than fail to build the site.
    """
    from src.resources import resource_path
    try:
        with open(resource_path("data", name), encoding="utf-8") as fh:
            return json.load(fh)
    except (FileNotFoundError, json.JSONDecodeError, OSError):
        return {}


def occurrence_map(entry: dict, depth: int) -> str:
    """The range picture: the grid, the records, and a toggle between kinds.

    Replaces the ecoregion map on the species page (V2.80). Three reasons, and
    the third is the one that decided it:

    * **The shading was the overstatement the review objected to.** A whole
      ecoregion coloured in because three records fall somewhere inside it
      claims 100,000 km of ground for them.
    * **The dots are the answer to the question that was asked.** *"Usually you
      have the dots and a shaded area that shows the range."*
    * **It is 10x smaller.** A species page was 888 KB, of which 846 KB was
      2,291 ecoregion polygons repeated verbatim on all 430 pages. The range
      map is about 90 KB.

    The ecoregion **counts** stay on the page below it. Those are facts -- so
    many records, in so many regions, retrieved on a stated date -- and only
    the picture drawn from them overclaimed.
    """
    from src.occurrence_points import caption as points_caption
    from src.range_map import range_svg
    from src.species_range import CELL_DEG, caption as cells_caption

    name = entry.get("scientific_name") or ""
    cells = _range_cells().get(name) or []
    kinds = _points().get(name) or {}
    if not cells and not kinds:
        # Nothing recorded draws nothing (P9). An empty frame with a legend
        # would assert we looked everywhere and found nothing.
        return ""

    svg = range_svg(
        cells, specimens=kinds.get("s") or (), observations=kinds.get("o") or (),
        width=560, step=CELL_DEG, marks="all",
        title=f'Where {entry.get("name") or name} has been recorded')
    return f"""
<section>
  <h2>Where it has been recorded</h2>
  <figure class="rangefig">
    {_toggle(_slug(name))}
    <div class="rangemapwrap">{svg}</div>
    <figcaption class="note">{_esc(cells_caption(cells))}
      {_esc(points_caption(kinds))}
      <a href="{_up(depth)}method/">How this map is made</a>.</figcaption>
  </figure>
</section>"""


def _slug(scientific_name: str) -> str:
    """A DOM-id-safe token for one species."""
    return "".join(c if c.isalnum() else "-"
                   for c in (scientific_name or "x").lower()).strip("-")


def _toggle(slug: str) -> str:
    """Both / specimens / observations, as three radio inputs.

    Radios and `:checked ~` sibling selectors rather than JavaScript, so the
    control works with scripting off -- which is also how it survives being
    saved to a file or printed. `browse.js` is the site's only script and it is
    about the index pages; this needs none.

    Two structural details are load-bearing, and the first cut got both wrong:

    * **The inputs are siblings of the map**, not nested inside the label row.
      A general-sibling combinator cannot climb out of a wrapper, so with the
      inputs inside `.ranketoggle` the buttons highlighted correctly and hid
      nothing -- a control that looks like it works and does not.
    * **The radio group is named per species.** Two maps in one document
      sharing `name="rk"` are one group, so checking either unchecks the other.
      That cannot happen on a species page today, which is exactly why it would
      have gone unnoticed until something rendered two.
    """
    rows = (("all", "Both"), ("s", "Specimens"), ("o", "Observations"))
    inputs = "".join(
        f'<input type="radio" class="rk rk-{key}" name="rk-{slug}" '
        f'id="rk-{slug}-{key}"{" checked" if key == "all" else ""}>'
        for key, _ in rows)
    labels = "".join(
        f'<label class="lbl-{key}" for="rk-{slug}-{key}">{text}</label>'
        for key, text in rows)
    return (f'{inputs}<div class="ranketoggle" role="group" '
            f'aria-label="Which records to show">{labels}</div>')


def _published_counts() -> dict:
    """``{"s", "o", "marks"}`` counted from the shipped point file.

    Computed, never written down. Every count on this site is (V2.47), and the
    reason is on the wall of this repo: a number typed into prose is correct
    once. `static_site_range` owns the file, so the reader is borrowed rather
    than a second one written.
    """
    from src.occurrence_points import KEY_OBSERVATION, KEY_SPECIMEN
    from src.static_site_points import _points
    spec = obs = 0
    for kinds in _points().values():
        spec += len(kinds.get(KEY_SPECIMEN) or [])
        obs += len(kinds.get(KEY_OBSERVATION) or [])
    return {"s": spec, "o": obs, "marks": spec + obs}


def _nativity_counts() -> dict:
    """How many province claims are sourced, and how many are withheld.

    Counted from the shipped rows through `nativity.publishable`, so this page
    cannot claim a number the species pages disagree with -- they call the same
    function.
    """
    import json                                          # noqa: PLC0415
    from src.nativity import publishable                 # noqa: PLC0415
    from src.resources import resource_path              # noqa: PLC0415

    rows = []
    for name in ("plants_master.json", "garden_plants.json"):
        try:
            with open(resource_path("data", name), encoding="utf-8") as fh:
                got = json.load(fh)
        except (FileNotFoundError, json.JSONDecodeError, OSError):
            continue
        rows += got if isinstance(got, list) else got.get("plants", [])
    claimed = [r for r in rows if (r.get("native_provinces") or "").strip()]
    sourced = [r for r in claimed if publishable(r)]
    # `claimed` and not `len(rows)`: the denominator a reader will check is
    # the number of species pages, and a row with no claim at all has no
    # answer to be sourced or withheld.
    return {"claimed": len(claimed), "sourced": len(sourced),
            "withheld": len(claimed) - len(sourced)}



def _point_method_sections(counts: dict, MARK_DEG, CELL_DEG, CELL_KM_NS) -> str:
    """The `/method/` sections about the map and the records it draws.

    Lives here rather than in `static_site_method` because this module owns the
    data being disclosed, and a disclosure that drifts from what the code
    actually does is worse than none. The numbers are computed, never written
    down -- every count on this site is (V2.47), because a number typed into
    prose is correct once.
    """
    return f"""<h2>The map on a species page</h2>
<p>The map draws two things. The <strong>shaded squares</strong> are a
{CELL_DEG} degree grid, about {CELL_KM_NS:.0f} km north to south, and one square
means at least one usable record falls inside it. Darker squares hold more
records. The <strong>dots</strong> are the records themselves.</p>
<p>Until this release the species map shaded a whole <em>ecoregion</em>
because records fell somewhere inside it. That is a claim over 100,000 square
kilometres made from three records, and an outside botanical review said so.
The region counts are still on the page, below the map, because a count is a
fact; only the picture drawn from it overclaimed.</p>
<p><strong>A darker square is not more plant.</strong> It is more collecting.
The squares holding Calgary and Edmonton are dark for nearly every species in
this catalogue, because that is where the people with cameras are.</p>
<p><strong>An empty square is not absence.</strong> It means nobody has
recorded the plant there. Under-collected ground and genuinely absent ground
look identical from here, and we will not print the difference we cannot
see.</p>
<p><strong>Recorded is not native.</strong> Occurrence says a plant was found
somewhere; it does not say it belongs there. A widely planted garden escape
can accumulate hundreds of records. Nativity comes from a published flora, not
from these counts; see below.</p>

<h2>The two kinds of record, and why you can switch between them</h2>
<p>A <strong>herbarium specimen</strong> is a pressed sheet in a collection
with a determination on it. Somebody can go and re-examine it. It is drawn as
a <strong>filled dot</strong>.</p>
<p>A <strong>field observation</strong> is a photograph somebody uploaded,
identified by community agreement. It is drawn as a <strong>hollow
ring</strong>.</p>
<p>Filled against hollow rather than two colours, so the distinction survives
greyscale, printing and red-green colour deficiency. Both are evidence and
they are not the same evidence, so the map lets you look at either alone.</p>
<p>Of the {counts["marks"]:,} marks we publish, {counts["s"]:,} are specimens and
{counts["o"]:,} are observations. The imbalance is real and worth knowing when
you read a map: for most of this catalogue the dense southern clouds are
photographs, and the northern dots are usually sheets.</p>

<h2>Which records we can publish</h2>
<p>Not all of them. A record is drawn here only if:</p>
<ul>
<li>its coordinate is precise to within <strong>10 km</strong>: a dot
placed from a county centroid is a claim the record does not make;</li>
<li>it falls inside <strong>Alberta or Saskatchewan</strong>, the ground this
catalogue speaks for;</li>
<li>its dataset licence permits redrawing the coordinate.</li>
</ul>
<p>That last one is a judgement we should state. We publish coordinates from
non-commercial-licensed datasets, which we do <em>not</em> do for photographs.
A photograph is somebody's work being redistributed; a coordinate is a fact
about a place. A dataset whose licence we could not determine is dropped
rather than assumed permissive.</p>
<p>Records closer together than {MARK_DEG} degrees are drawn once. That is
under half a pixel at the size these maps are shown, so two records 200 m
apart were already one dot.</p>"""

