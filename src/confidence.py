"""
confidence.py — one vocabulary for "how sure are we?" and "who says so?" (F8,
F13, F14, F28).

Design principle P9 (uncertainty is a feature, not a bug — ship ranges and
confidence, never false precision) — see docs/DESIGN_PHILOSOPHY.md.

The roadmap carried five separate cards — an uncertainty language pass, inline
citations, confidence marks on inferred fields, an establishment band and a
reference-fidelity band — and said they were really one job: *say how sure we
are, and say who says so*. Done apart, each invents its own words for the same
idea, and the app ends up with four scales that cannot be compared. This module
is the shared vocabulary so that cannot happen.

It owns two things and deliberately not a third:

* **Bands** — the three-plus-unknown scale a hedged answer is reported on, with
  the *words* for each band per context. It does **not** own the thresholds
  where a domain already has them: an establishment band comes from
  :func:`src.ecoregion_ranges.confidence_for`, which sets its floors against
  record counts and documents why. Restating those here would create exactly
  the second source of truth this module exists to prevent.
* **Marks** — one table over the two provenance vocabularies the app already
  ships: the edges layer's ``documented / recorded / derived`` (V2.42) and the
  seed data's ``measured / flora / photo / checked / name / epithet /
  estimated`` (V2.35–V2.48). A caller asks for a mark and gets the same word
  everywhere, so the plant directory, the website and the 3D dossier cannot
  drift apart the way the four edge tables did before F7.

**The distinction the whole module turns on: absent is not estimated.**
A blank provenance field means nobody has written a value — the app knows it
does not know. ``estimated`` means a genus-level default *was* written in and
looks exactly like a measurement. The second is more dangerous than the first,
because it is invisible, and it is what put a red flower on the blue columbine
(V2.48). They get different marks and different words, and
:attr:`Mark.inferred` separates them from anything anyone actually checked.

**And: a band needs evidence.** Every scoring function in this codebase degrades
to a neutral 0.5 on missing input — ``score_cell_for_plant`` says so in its own
docstring — which is correct for ranking and catastrophic for reporting, because
a neutral score banded naively reads as "medium confidence" about nothing. Pass
``known=False`` and you get :data:`UNKNOWN`, whose label says the app cannot
tell. That is the same trap ``ecoregion_map`` fell into in V2.51, printing a
fabricated "medium confidence" for regions it had no data on.

Qt-free and dependency-free, so panels, the PDF export, the static site and the
scripting API can all share it.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

# ── Bands ─────────────────────────────────────────────────────────────────────


@dataclass(frozen=True)
class Band:
    """One rung of a hedged answer.

    ``key`` is stable and safe to switch on; ``label`` is the short phrase a
    panel shows; ``blurb`` is the sentence that says what the band is *based
    on*, which is the part that stops a label being read as a measurement.
    ``known`` is False only for :data:`UNKNOWN`.
    """
    key: str
    label: str
    blurb: str
    known: bool = True


#: The answer when there is nothing to answer from. Deliberately not a middle
#: band: "we don't know" and "medium" are different claims, and collapsing them
#: is how a neutral default becomes a confident-looking readout.
UNKNOWN = Band(
    "unknown", "Not enough to say",
    "The catalogue holds no evidence either way for this one, so no band is "
    "shown rather than a guessed middle.",
    known=False,
)


#: Named scales. Each maps a band key to its words in that context. The keys are
#: shared across scales on purpose — ``high``/``medium``/``low`` mean the same
#: shape of claim everywhere, and only the wording changes with the subject.
SCALES: dict[str, dict[str, Band]] = {
    # F14. Fed by occurrence counts, whose thresholds belong to
    # `ecoregion_ranges.CONFIDENCE_BANDS` — see the module docstring.
    "establishment": {
        "high": Band(
            "high", "Well recorded here",
            "Twenty or more georeferenced records of this species in your "
            "ecoregion — a documented population, not an outlier."),
        "medium": Band(
            "medium", "Recorded here",
            "Between eight and nineteen georeferenced records in your "
            "ecoregion: consistently present, thinly collected."),
        "low": Band(
            "low", "Barely recorded here",
            "Three to seven georeferenced records in your ecoregion. Present, "
            "but on the edge of what the occurrence data can support."),
    },
    # F13. Thresholds are this module's own, and are set in `fidelity_band`.
    "fidelity": {
        "high": Band(
            "high", "Close to the reference",
            "Most of the layers the natural community of your ecoregion is "
            "built from are represented here."),
        "medium": Band(
            "medium", "Part of the way there",
            "Some of the reference community's structure is present and some "
            "layers are thin or missing."),
        "low": Band(
            "low", "A long way from the reference",
            "This design shares little of the structure of the natural "
            "community for your ecoregion. That can be a deliberate choice."),
    },
}


def band(scale: str, key: str, *, known: bool = True) -> Band:
    """The :class:`Band` for ``key`` on ``scale``.

    ``known=False``, an empty key, or a key the scale does not define all give
    :data:`UNKNOWN` — a caller can never accidentally turn missing evidence into
    a confident band, which is the failure this module exists to prevent.
    """
    if not known:
        return UNKNOWN
    return SCALES.get(scale, {}).get((key or "").strip().lower(), UNKNOWN)


def establishment_band(occurrences: Optional[int]) -> Band:
    """Band a species' occurrence count in one ecoregion (F14).

    Thresholds come from :mod:`src.ecoregion_ranges`, which owns them. Below its
    floor — including zero, and including "we have no row at all" (``None``) —
    the answer is :data:`UNKNOWN`, because the app cannot distinguish a species
    that is absent from one nobody has collected. Reporting that difference
    honestly is the entire point of the band.
    """
    if occurrences is None:
        return UNKNOWN
    from src.ecoregion_ranges import confidence_for          # noqa: PLC0415
    return band("establishment", confidence_for(int(occurrences)))


#: Where the fidelity bands break. Deliberately generous at the top: a yard is
#: not a wild community and never will be, so demanding near-parity would make
#: the score say "you failed" about every real design, which teaches nothing.
FIDELITY_HIGH = 0.60
FIDELITY_MEDIUM = 0.30


def fidelity_band(value: Optional[float], *, known: bool = True) -> Band:
    """Band a 0–1 reference-community fidelity score (F13)."""
    if value is None or not known:
        return UNKNOWN
    v = max(0.0, min(1.0, float(value)))
    if v >= FIDELITY_HIGH:
        return band("fidelity", "high")
    if v >= FIDELITY_MEDIUM:
        return band("fidelity", "medium")
    return band("fidelity", "low")


# ── Marks ─────────────────────────────────────────────────────────────────────


@dataclass(frozen=True)
class Mark:
    """How a single value came to be, in one word plus one symbol.

    ``inferred`` is the flag a UI should actually branch on: True means nobody
    checked this particular value, whether it was computed from other records or
    filled in from a genus default. ``recorded`` is False only when there is no
    value at all — the honest empty, which must not be dressed up as a guess or
    hidden behind one.
    """
    key: str
    symbol: str
    label: str
    inferred: bool
    recorded: bool = True


#: One table over both vocabularies. The symbols are deliberately plain text
#: rather than emoji: they end up in a PDF, a Qt label and a static HTML page,
#: and the PDF path renders with a font that has no emoji coverage.
MARKS: dict[str, Mark] = {
    # ── the edges layer (V2.42) ──
    "documented": Mark(
        "documented", "✓", "documented — a record, with a source cited",
        inferred=False),
    "recorded": Mark(
        "recorded", "–", "recorded, but no source named", inferred=True),
    "derived": Mark(
        "derived", "≈", "derived — computed from other records, not "
        "observed", inferred=True),
    # ── seed-data provenance (V2.35 flower/leaf, V2.48 colour, v58 fauna) ──
    "measured": Mark(
        "measured", "✓", "measured", inferred=False),
    "flora": Mark(
        "flora", "✓", "read from a published flora", inferred=False),
    # A flora states the obvious once at the genus and then notes only
    # departures from it, so 140 of this catalogue's species are described in
    # Budd's with no colour of their own. Reading the genus recovers them, and
    # a botanist reads a flora that way -- the genus description IS part of
    # each species entry by the book's own convention.
    #
    # It gets its own mark rather than borrowing "flora" because it is a
    # weaker reading and the reader deserves to weigh it. NOT inferred: the
    # book asserts it, we did not compute it. That is the whole distinction
    # from "estimated", which is this project's own genus default and the
    # thing all of this exists to remove.
    "flora_genus": Mark(
        "flora_genus", "✓", "from the genus description in a flora",
        inferred=False),
    "photo": Mark(
        "photo", "✓", "read off a photograph", inferred=False),
    "checked": Mark(
        "checked", "✓", "checked", inferred=False),
    "name": Mark(
        "name", "✓", "checked against its common name", inferred=False),
    "epithet": Mark(
        "epithet", "✓", "checked against its Latin name", inferred=False),
    # The dangerous one. A value IS present and looks like every other value on
    # the row; nobody has ever looked at it for this species.
    "estimated": Mark(
        "estimated", "≈", "not verified, a genus-level estimate",
        inferred=True),
}

#: No value at all. Separate from ``estimated`` on purpose — see the module
#: docstring. A UI should say "not recorded" here, never leave it blank, because
#: a blank cell and a checked value look identical.
UNRECORDED = Mark("unrecorded", "—", "not recorded", inferred=False,
                  recorded=False)


def mark(value: Optional[str]) -> Mark:
    """The :class:`Mark` for a provenance or evidence value.

    An empty value gives :data:`UNRECORDED`. An **unknown** value is treated as
    unrecorded rather than guessed at, so a new provenance word added to the
    seed data shows up as an honest gap here instead of silently borrowing the
    wording of whichever mark it happened to sort next to.
    """
    return MARKS.get((value or "").strip().lower(), UNRECORDED)


def is_inferred(value: Optional[str]) -> bool:
    """True when nobody checked this particular value (F28's whole question)."""
    return mark(value).inferred


def annotate(text: str, value: Optional[str], *, symbol: bool = True) -> str:
    """``text`` with its provenance appended, or unchanged when it is checked.

    The rule this encodes: **a verified value carries no mark**. Marking
    everything trains the eye to skip the mark, which loses the one case that
    matters. Only an inferred or missing value earns an annotation.
    """
    m = mark(value)
    if not m.inferred and m.recorded:
        return text
    tag = f"{m.symbol} {m.label}" if symbol else m.label
    return f"{text} ({tag})"


# ── Language (F8) ─────────────────────────────────────────────────────────────
#
# The audit behind F8 found the app's prose mostly honest already — `phenology`
# says "we predict", `plant_impact` says "no *documented* wildlife", `docent`
# says "*documented* wildlife species". The failure was narrower and worse than
# loose wording: `design_critic` asserted **absences** as facts ("Nothing
# provides bird food"), and an absence is the one claim incomplete data cannot
# support. See `data_quality.validate_use_tags_against_edges`, which measures
# the specific case where the app's own cited edges contradict the tag the
# absence was read off.


def no_record_of(what: str) -> str:
    """Phrase an absence as what it actually is: a gap in the catalogue.

    "Nothing provides bird food" is a claim about the yard. "Nothing in this
    design is recorded as providing bird food" is a claim about the record, and
    only the second one is true — the app knows what it has been told, and its
    own data audit puts documented plant-fauna coverage near half the catalogue.
    """
    return f"Nothing in this design is recorded as {what}"


def hedge_count(n: int, noun: str, *, plural: Optional[str] = None) -> str:
    """``"12 documented bee species"`` — a count that says what it counts.

    Every wildlife count in this app is a count of *records*, not of animals.
    It is a floor, and phrasing it as a total is the commonest way this codebase
    over-claims.

    A noun already ending in ``s`` is left alone unless ``plural`` says
    otherwise: every noun this is called with is some flavour of "species", and
    "speciess" is the kind of error that makes the honest phrasing look careless.
    """
    if n == 1:
        word = noun
    elif plural:
        word = plural
    else:
        word = noun if noun.endswith("s") else f"{noun}s"
    return f"{n} documented {word}"
