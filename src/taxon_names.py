"""How a scientific name is read, so two of them can be compared (V2.82).

One function, and it exists because the comparison was done by eye and got four
of V2.80's eight renames wrong.

A checklist records a name **with its authority** — ``Stachys pilosa Nuttall``,
``Primula pauciflora (Greene) A.R. Mast & Reveal var. pauciflora`` — and the
authority is not part of the name. Reading the epithet off the wrong end of one
produced *Stachys pilosa* var. *pilosa* and *Urtica gracilis* subsp. *gracilis*,
two taxa VASCAN does not carry, one of which collided with a row already in the
catalogue and shipped the same plant twice.

The rule an authority follows is not a grammar and cannot be parsed as one, but
it has one reliable signal: **a capital letter or an open bracket, after the
epithet, starts the authority.** Rank markers (``var.``, ``subsp.``) are
lower-case and are part of the name, so they survive; ``(Greene)`` does not, and
neither does anything after it — which is why the trailing ``var. pauciflora``
above is dropped rather than mistaken for a rank on a name it is no longer
attached to.

This module is deliberately *not* in ``scripts/``: both the rename tool and the
data-quality gate need the same reading of a name, and a gate importing its
definition of correctness from a dev script has the dependency backwards.
"""

from __future__ import annotations

#: Rank markers that belong to the name rather than starting an authority.
RANK_MARKERS = ("var.", "subsp.", "ssp.", "f.")


def binomial(authored: str) -> str:
    """The name in ``authored``, without its authority.

    >>> binomial("Campanula rotundifolia Linnaeus")
    'Campanula rotundifolia'
    >>> binomial("Spiraea splendens var. rosea (A. Gray) Kartesz & Gandhi")
    'Spiraea splendens var. rosea'
    >>> binomial("")
    ''
    """
    out: list = []
    for token in (authored or "").split():
        if out and (token[0].isupper() or token[0] == "("):
            break
        if token in RANK_MARKERS:
            out.append(token)
            continue
        if len(out) >= 2 and out[-1] not in RANK_MARKERS:
            break
        out.append(token)
    return " ".join(out)


def is_infraspecific(name: str) -> bool:
    """Does this name claim a rank below species?

    Useful on its own: a row at a rank the checklist answered about at
    *species* rank is the V2.80 failure, and it is visible in the name.
    """
    return any(f" {marker} " in f" {name} " for marker in RANK_MARKERS)
