"""
stock_lists.py — reading a nursery's plant list into scientific names (V3.25).

A nursery's availability list is whatever its website or flyer says: "Wild
Bergamot (Monarda fistulosa) 1 gal $12", "Yarrow, Common – Achillea
millefolium", a table pasted from a PDF. :func:`match` finds the catalogue's
plants in any such text by their common name or binomial, and by the old names
a nursery may still use, and returns what it found and the lines it could not
read, so a person can see what was missed rather than trust a silent count.

Used by ``scripts/merge_stock.py`` (authoritative) and by the stock review
page's preview (``tools/stock_review``), which embeds :func:`name_table`.
Qt-free.
"""

from __future__ import annotations

import re
from typing import Iterable, Mapping

#: Names nurseries use for a catalogue plant that the catalogue does not carry
#: as a rename. Each is a lump or an older treatment of the same plant around
#: Edmonton, never a different species.
ALIASES = {
    "achillea millefolium": "Achillea borealis",   # the lump; ours is native
    "common yarrow": "Achillea borealis",
    "yarrow": "Achillea borealis",
    "anemone patens": "Pulsatilla nuttalliana",
    "pulsatilla patens": "Pulsatilla nuttalliana",
    "pasque flower": "Pulsatilla nuttalliana",
    "pasqueflower": "Pulsatilla nuttalliana",
    "anise hyssop": "Agastache foeniculum",
    "potentilla fruticosa": "Dasiphora fruticosa",
    "bee balm": "Monarda fistulosa",
    "white sage": "Artemisia ludoviciana",
}


def norm(text: str) -> str:
    """Lower case, letters only, single spaces: "Yarrow, Common –" ->
    "yarrow common"."""
    return re.sub(r"[^a-z]+", " ", (text or "").lower()).strip()


def name_table(rows: Iterable[Mapping]) -> dict:
    """``{normalised name: scientific name}`` for every catalogue row: its
    binomial, its common name, the names it was renamed from, and
    :data:`ALIASES`."""
    table: dict = {}
    for r in rows:
        sci = (r.get("scientific_name") or "").strip()
        if not sci:
            continue
        for name in (sci, " ".join(sci.split()[:2]), r.get("common_name"),
                     r.get("renamed_from"), r.get("common_renamed_from")):
            n = norm(name or "")
            if n and len(n.split()) >= 1 and n not in table:
                table[n] = sci
    for alias, sci in ALIASES.items():
        table.setdefault(norm(alias), sci)
    return table


def match(text: str, table: Mapping) -> tuple:
    """``(found, unread)``: the scientific names named in ``text``, in order
    of first mention, and the non-empty lines that named none.

    A longer name wins over a shorter one inside it, so "Wild Blue Flax" is
    not also read as some "Flax", and a bare common name of one word
    ("Yarrow") counts only when nothing longer on its line matched."""
    names = sorted(table, key=lambda n: -len(n))
    found: list = []
    unread: list = []
    for line in (text or "").splitlines():
        line_n = f" {norm(line)} "
        if not line_n.strip():
            continue
        hit = False
        for n in names:
            needle = f" {n} "
            if needle in line_n:
                sci = table[n]
                if sci not in found:
                    found.append(sci)
                hit = True
                line_n = line_n.replace(needle, " | ")
        if not hit:
            unread.append(line.strip())
    return found, unread
