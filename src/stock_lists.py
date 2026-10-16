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
    # Arnica Wildflowers' 2026 lists (V3.26). The rhombic-leaved sunflower is
    # H. pauciflorus subsp. subrhomboideus; Alberta's alpine hedysarum is
    # H. alpinum var. americanum, the catalogue's H. americanum.
    "helianthus subrhomboideus": "Helianthus pauciflorus",
    "hedysarum alpinum": "Hedysarum americanum",
    # Local names on the Edmonton Native Plant Society's 2026 sale lists, which
    # give no binomials. Arnica's lists pair the first five with theirs.
    "common tall sunflower": "Helianthus nuttallii",
    "low goldenrod": "Solidago missouriensis",
    "purple stemmed aster": "Symphyotrichum puniceum",
    "richardson s alumroot": "Heuchera richardsonii",
    "veiny meadowrue": "Thalictrum venulosum",
    "heart leaved alexander": "Zizia aptera",
    "large northern aster": "Canadanthus modestus",
    "great northern aster": "Canadanthus modestus",
    "long headed anemone": "Anemone cylindrica",
    "low milkweed": "Asclepias ovalifolia",
    "pasture sage": "Artemisia frigida",
    # The catalogue's one violet of that name; Alberta's Canada violet is
    # V. canadensis var. rugulosa.
    "canada violet": "Viola rugulosa",
}


def norm(text: str) -> str:
    """Lower case, letters only, single spaces: "Yarrow, Common –" ->
    "yarrow common"."""
    return re.sub(r"[^a-z]+", " ", (text or "").lower()).strip()


def name_table(rows: Iterable[Mapping]) -> dict:
    """``{normalised name: scientific name}`` for every catalogue row: its
    binomial, its common name, the names it was renamed from, and
    :data:`ALIASES`. A binomial (or old binomial) is marked by
    :data:`BINOMIALS` so a line naming one is read by it alone."""
    table: dict = {}
    sci_names: set = set()
    for r in rows:
        sci = (r.get("scientific_name") or "").strip()
        if not sci:
            continue
        # "Stiff Sunflower (Rhombic-leaved Sunflower)" is known by either.
        commons = [c for c in re.split(r"[(),]", r.get("common_name") or "")
                   if c.strip()]
        for name, is_sci in ((sci, True), (" ".join(sci.split()[:2]), True),
                             (r.get("common_name"), False),
                             *((c, False) for c in commons),
                             (r.get("renamed_from"), True),
                             (r.get("common_renamed_from"), False)):
            n = norm(name or "")
            if n and n not in table:
                table[n] = sci
                if is_sci:
                    sci_names.add(n)
    genera = {n.split()[0] for n in sci_names}
    for alias, sci in ALIASES.items():
        n = norm(alias)
        table.setdefault(n, sci)
        if n.split()[0] in genera:          # an old binomial, not a common name
            sci_names.add(n)
    table[BINOMIALS] = frozenset(sci_names)
    return table


#: The key under which :func:`name_table` keeps which names are binomials.
BINOMIALS = "\x00binomials"


def match(text: str, table: Mapping) -> tuple:
    """``(found, unread)``: the scientific names named in ``text``, in order
    of first mention, and the non-empty lines that named none.

    A longer name wins over a shorter one inside it, so "Wild Blue Flax" is
    not also read as some "Flax", and a bare common name of one word
    ("Yarrow") counts only when nothing longer on its line matched."""
    binomials = table.get(BINOMIALS) or frozenset()
    names = sorted((n for n in table if n != BINOMIALS), key=lambda n: -len(n))
    found: list = []
    unread: list = []
    for line in (text or "").splitlines():
        if line.lstrip().startswith("#"):
            continue                       # a note, not a plant
        line_n = f" {norm(line)} "
        if not line_n.strip():
            continue
        hits = []
        for n in names:
            needle = f" {n} "
            if needle in line_n:
                hits.append(n)
                line_n = line_n.replace(needle, " | ")
        # A line naming a binomial is read by it: "Artemisia ludoviciana -
        # Prairie Sagewort" is A. ludoviciana, though the catalogue's Prairie
        # Sagewort is A. frigida (V3.26, Arnica's lists).
        if any(n in binomials for n in hits):
            hits = [n for n in hits if n in binomials]
        for n in hits:
            if table[n] not in found:
                found.append(table[n])
        if not hits:
            unread.append(line.strip())
    return found, unread
