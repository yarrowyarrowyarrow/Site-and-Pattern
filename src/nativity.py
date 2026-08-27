"""
nativity.py — what "Native to Alberta and Saskatchewan" is actually resting on.

Design principle P9 — see docs/DESIGN_PHILOSOPHY.md.

The claim, and where it came from
---------------------------------
354 of 430 species in this catalogue carry ``native_provinces = "AB,SK"``, 75
carry ``"AB"``, and grownativeplants.ca prints that under **Native to**. Unlike
flower colour, unlike safety, unlike leaf shape, the field has **no source
column** — there is no ``native_provinces_source`` to read, because nothing
ever read one to write it.

What produced it was ``scripts/tag_prairie_provenance.py``, retired in V2.75,
and its own docstring is the plainest statement of the problem::

    The heuristic was published as a fact. An outside botanical review read the
    site and said, correctly, that many species listed as native to AB and SK
    are native to only one. They are reading the output of this file.

The heuristic was **ecoregion continuity**: the Aspen Parkland, the grasslands
and the boreal plain run unbroken across the 110th meridian, so a species
documented from one of them in Alberta was written down as native to the same
ecoregion in Saskatchewan. That is a reasonable inference and it is *not* a
range map, and it was rendered as a claim by a page that never asked how it was
made. Alberta itself rests on ``native_to_alberta``, an editorial flag from the
first seed file, which is a different provenance and no better sourced.

What this module does, and what it is waiting for
-------------------------------------------------
It puts the mark back on. Nothing here decides *whether* a species is native;
it says what the existing claim is standing on, in the same shape the flower
colour's note has had since V2.48, so a reader can weigh it.

**The real fix is F137/F144 and needs the network.** VASCAN
(``scripts/fetch_flora_nativity.py``) returns ``establishmentMeans`` per
province per species, which is the sourced answer, and
``scripts/ingest_flora_nativity.py`` is written and tested and has never run
because the project's cloud sessions cannot reach ``data.canadensys.net``. When
it does run, each species gains a real per-species source and
:func:`provenance` should read that column instead of inferring the note from
the shape of the value. Until then, a derived note is honest and a stored one
would be 430 copies of the same sentence, which is inventing a data shape ahead
of the data.
"""

from __future__ import annotations

#: Set by the VASCAN ingest when it lands (F144). Until a species carries one,
#: :func:`provenance` reasons from the shape of the claim instead.
SOURCE_FIELD = "native_provinces_source"

#: How the two halves of the claim were produced. Two different provenances
#: wearing one string, which is exactly why one note for both would be wrong.
_SK_INFERRED = ("Saskatchewan is inferred from ecoregions that continue across "
                "the provincial border, not from a range map for this species")
_AB_EDITORIAL = ("from the catalogue's own Alberta flag, not checked against "
                 "a published flora")


#: What a page says instead of an unsourced province list (V2.80).
#:
#: The author's instruction, after seeing the marked-but-published claims:
#: *"I do not want any inference being made... only facts backed by data."*
#: V2.78 printed the inference with its heuristic named beside it, which was a
#: real improvement on printing it bare and is still an inference published as
#: this site's answer to the question it is named after.
#:
#: Deliberately vague about WHY, because the species this covers differ and a
#: single specific sentence would be false for some of them. The V2.80 pass
#: over the original ~16 found four distinct reasons, which is the point:
#: *Achillea millefolium* was introduced here and the native race was already
#: carried as *A. borealis*; *Urtica dioica* and seven others were filed under
#: a name VASCAN does not accept and are sourced the moment they are renamed;
#: *Solidago nemoralis* and *Spiraea douglasii* are recorded by VASCAN but not
#: for these two provinces; and the fruit cultivars will never have a flora
#: entry at all. "Not established" is true of every one of them; "no flora
#: records it" is true of almost none.
WITHHELD_NOTE = ("Not established. No source we have read settles which "
                 "provinces this species is native to, and this catalogue "
                 "does not guess.")


def publishable(plant: dict) -> bool:
    """May the province list be shown as this catalogue's claim?

    True only when the value carries a source somebody checked. Everything else
    -- a genus default, an ecoregion inference, an editorial flag -- is
    withheld and :data:`WITHHELD_NOTE` is shown instead.

    Separate from :func:`provenance` because they answer different questions:
    that one asks *how sure are we*, this one asks *may we say it at all*, and
    collapsing them would make a page's honesty depend on a note's wording.
    """
    return not provenance(plant)["inferred"] and bool(
        provinces(plant.get("native_provinces") or plant.get("native")))


def provinces(value) -> list:
    """``"AB,SK"`` -> ``["AB", "SK"]``. Blank in, empty out."""
    if isinstance(value, (list, tuple)):
        parts = list(value)
    else:
        parts = (value or "").split(",")
    return [p.strip().upper() for p in parts if str(p).strip()]


def provenance(plant: dict) -> dict:
    """``{"note": str, "inferred": bool}`` for a plant's nativity claim.

    Accepts either a raw catalogue row or a
    :func:`src.plant_directory.species_entry` dict.

    ``note`` is empty when there is nothing to say — no claim at all, or (once
    VASCAN has run) a claim somebody checked. A verified value carries no mark:
    marking everything trains the eye to skip the mark, which loses the one
    case that matters. That rule is :func:`src.confidence.annotate`'s and is
    borrowed rather than restated.
    """
    from src.confidence import mark
    source = (plant.get(SOURCE_FIELD) or "").strip()
    if source:
        m = mark(source)
        return {"note": "" if not m.inferred else m.label,
                "inferred": bool(m.inferred)}

    # Both shapes on purpose. `native_provinces` is the raw catalogue row;
    # `native` is what `plant_directory.species_entry` renames it to, and the
    # website reads the entry, not the row. A function that knew only one of
    # them would work in a test and return nothing on every published page,
    # which is how the first version of this shipped a note nobody saw.
    codes = provinces(plant.get("native_provinces")
                      or plant.get("native")
                      or plant.get("native_region") or "")
    if not codes:
        return {"note": "", "inferred": False}

    if "SK" in codes and "AB" in codes:
        note = _SK_INFERRED
    elif codes == ["AB"]:
        note = _AB_EDITORIAL
    else:
        # A hand-set code the generator preserved rather than produced (one
        # row reads "SK,MB"). It is not the heuristic's output and saying it
        # was would be its own false claim, so this says only what is true of
        # every row: nobody has checked it against a flora.
        note = "not checked against a published flora"
    return {"note": note, "inferred": True}


def annotate(text: str, plant: dict) -> str:
    """``text`` with the nativity note appended in parentheses, or unchanged."""
    note = provenance(plant)["note"]
    return f"{text} ({note})" if (text and note) else text
