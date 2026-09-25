"""
name_variants.py — spellings people type that the catalogue does not use (V2.86).

The common name is this catalogue's foreign key and its public URL, so a
spelling cannot be changed to suit a search box: renaming *Bur Oak* would move
every edge keyed on it and a page people may have linked to. But "Burr Oak" is
how a good share of gardeners and nurseries write it, and the desktop search and
the website's filter box both returned **nothing** for it. The plant was there;
the reader was told it was not.

So the variants live here, once, and both searches read them:

* :func:`query_forms` -- the query as typed, plus the query with each variant
  word replaced by the catalogue's spelling. ``search_plants`` matches any form.
* :func:`searchable` -- a name plus every variant spelling of it, for the
  website's client-side index, which matches by substring and cannot be taught
  a rule.

Whole words only: "burr" is replaced, "burrowing" is not.

Only real, attested spellings belong here, each on a species in the catalogue.
This is not a synonym table: a different *name* for a plant (Box Elder for
Manitoba Maple) is carried in the row's own parenthetical, where a reader sees
it too.
"""

from __future__ import annotations

import re

#: ``{variant: catalogue spelling}``, lower case, one word each.
SPELLINGS: dict[str, str] = {
    # Bur Oak, *Quercus macrocarpa*. "Burr" is common in Canadian nursery
    # listings and in older floras; the catalogue follows VASCAN's "bur".
    "burr": "bur",
}

_WORD = re.compile(r"[a-z]+")


def _swap(text: str, table: dict) -> str:
    return _WORD.sub(lambda m: table.get(m.group(0), m.group(0)), text)


def query_forms(query: str) -> list[str]:
    """``query`` lower-cased, and again in the catalogue's spelling when that
    differs. Always at least one form; never a duplicate."""
    q = (query or "").lower()
    fixed = _swap(q, SPELLINGS)
    return [q] if fixed == q else [q, fixed]


def searchable(name: str) -> str:
    """``name`` lower-cased, followed by each variant spelling of it, so a
    substring match on the result finds the plant under either spelling."""
    base = (name or "").lower()
    reverse = {canon: variant for variant, canon in SPELLINGS.items()}
    variant = _swap(base, reverse)
    return base if variant == base else f"{base} {variant}"
