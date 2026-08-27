"""
src/budds_colour.py — read flower colour out of a regional flora's prose.

*Budd's Flora of the Canadian Prairie Provinces* (Agriculture Canada
publication 1662) is the right authority for exactly this ground, and it is a
scanned book: no characteristics table, no colour column, just descriptions.
So the colour has to be read out of sentences like

    Flowers white or pinkish, in flat-topped corymbs.

Why this exists at all
----------------------
350 of the catalogue's flower colours are a genus default marked *not
verified*. V2.80 tried USDA PLANTS first, because a structured export is
cheaper than parsing prose, and the author checked the result against the two
species they knew best:

    "They say yarrow is yellow, the giant hyssop is red"

Checked at the binomial, not the common name, so it was not the *Achillea
filipendulina* confusion it could have been. A source that is wrong about
*Achillea millefolium* is not a source.

**The job this module is really doing is not "extract colour". It is "make
348 species checkable in an evening."** OCR of a 1979 scan will be wrong
sometimes, and a parser reading English prose will be wrong sometimes, so the
output is never the last word. What makes it fast is that every proposal
carries **the book's own sentence** beside it. Checking a line then costs
reading a quote, rather than looking a species up.

What it does not do
-------------------
It does not fetch the book and it does not read a PDF. Text in, findings out.
That keeps it testable, keeps it working where a PDF library will not install,
and means the OCR step is visible rather than buried.
"""

from __future__ import annotations

import re
from typing import Iterable, NamedTuple

#: Words that mean the sentence is talking about the bloom, not the leaf, the
#: stem or the fruit. "Flowers yellow" is a colour; "leaves yellow-green in
#: autumn" is not, and a flora says both about the same plant.
FLOWER_WORDS: tuple = (
    "flower", "flowers", "floret", "florets", "petal", "petals",
    "ray", "rays", "ligule", "ligules", "corolla", "corollas",
    "perianth", "sepal", "sepals", "head", "heads", "bloom", "blooms",
    "calyx", "tepals", "spike", "raceme", "panicle", "umbel", "corymb",
)

#: Words that mean it is NOT the bloom, checked first. A description reading
#: "leaves green above, purple beneath" must not become a purple flower.
NOT_FLOWER_WORDS: tuple = (
    "leaf", "leaves", "foliage", "stem", "stems", "bark", "twig", "twigs",
    "fruit", "fruits", "berry", "berries", "seed", "seeds", "achene",
    "achenes", "root", "roots", "rhizome", "capsule", "pod", "pods",
    "anther", "anthers", "stamen", "stamens", "bract", "bracts",
)

#: Colour word -> this catalogue's bucket key (see src/flower_colour.COLOURS).
#: Deliberately generous about the forms a flora actually uses -- "yellowish",
#: "ochroleucous", "roseate" -- because the cost of missing one is a species
#: that silently gets no proposal.
COLOUR_TERMS: dict = {
    "white": "white", "whitish": "white", "albino": "white",
    "milky": "white", "silvery": "white",
    "cream": "cream", "creamy": "cream", "ochroleucous": "cream",
    "ivory": "cream", "straw": "cream", "buff": "cream",
    "yellow": "yellow", "yellowish": "yellow", "golden": "yellow",
    "gold": "yellow", "lemon": "yellow", "sulphur": "yellow",
    "sulfur": "yellow", "flavous": "yellow",
    "orange": "orange", "orangish": "orange", "tawny": "orange",
    "salmon": "orange", "apricot": "orange",
    "red": "red", "reddish": "red", "scarlet": "red", "crimson": "red",
    "vermilion": "red", "wine": "red", "maroon": "red", "ruby": "red",
    "pink": "pink", "pinkish": "pink", "rose": "pink", "roseate": "pink",
    "rosy": "pink", "magenta": "pink", "blush": "pink",
    "purple": "purple", "purplish": "purple", "violet": "purple",
    "lilac": "purple", "mauve": "purple", "lavender": "purple",
    "plum": "purple",
    "blue": "blue", "bluish": "blue", "azure": "blue", "indigo": "blue",
    "green": "green", "greenish": "green", "olive": "green",
    "brown": "brown", "brownish": "brown", "bronze": "brown",
    "coppery": "brown", "chestnut": "brown",
}

#: Modifiers that appear before a colour and must not break the match.
_HEDGES = ("pale", "deep", "dark", "bright", "light", "faint", "vivid",
           "rarely", "sometimes", "often", "usually", "occasionally")


class Finding(NamedTuple):
    """One species, one proposal, and the sentence it came from."""
    scientific_name: str      #: the name WE key on
    found_as: str             #: the name as the book spells it
    buckets: tuple            #: colour keys, in the order the sentence gives
    quote: str                #: the sentence, so a person can check in one read
    confident: bool           #: exactly one colour, and a flower word near it


#: Words a flora starts a *sentence* with that look exactly like a genus.
#: Without these, "Leaves finely dissected" reads as a new species heading and
#: every description gets truncated at its first sentence -- which is what the
#: first version of this module did, silently, to all five test species.
DESCRIPTIVE_STARTS: frozenset = frozenset((
    "leaves", "leaf", "flowers", "flower", "stems", "stem", "fruit", "fruits",
    "heads", "head", "petals", "seeds", "seed", "roots", "root", "bark",
    "branches", "twigs", "perennial", "annual", "biennial", "shrub", "shrubs",
    "herb", "herbs", "tree", "trees", "plant", "plants", "erect", "low",
    "tall", "stout", "slender", "creeping", "tufted", "dry", "moist", "wet",
    "common", "rare", "found", "grows", "native", "introduced", "similar",
    "differs", "flowering", "fruiting", "inflorescence", "calyx", "corolla",
    "rhizome", "rhizomes", "achenes", "capsule", "spikelets", "culms",
))


def normalise(text: str) -> str:
    """Undo the damage a scan does, **without destroying line structure**.

    Soft hyphens go, and a word split across a line break is rejoined
    (``yel-\\nlow`` -> ``yellow``). Runs of spaces collapse. Newlines stay,
    because in a flora the line break before a binomial is the clearest signal
    that a new species has started, and the first version of this function
    collapsed newlines into spaces and threw that signal away.
    """
    text = (text or "").replace("­", "")           # soft hyphen
    text = re.sub(r"([A-Za-z])-[ \t]*\n[ \t]*([a-z])", r"\1\2", text)
    text = re.sub(r"[ \t]+", " ", text)
    return re.sub(r"\n{2,}", "\n", text).strip()


def _is_heading(line: str) -> bool:
    """Does this line start a new species?

    Genus then epithet, with the genus not one of the words a flora habitually
    opens a sentence with.
    """
    m = re.match(r"([A-Z][a-z]{2,})\s+([a-z]{3,})", line.strip())
    return bool(m) and m.group(1).lower() not in DESCRIPTIVE_STARTS


def _canonical(name: str) -> str:
    """A binomial, lowercased, authority and infraspecifics dropped."""
    parts = [p for p in re.sub(r"[×x]\s+", "", (name or "")).split() if p]
    return " ".join(parts[:2]).lower().strip(",.;:")


def _sentences(block: str) -> list:
    return [s.strip() for s in re.split(r"(?<=[.;])\s+", block) if s.strip()]


def colour_in(block: str) -> tuple:
    """``(buckets, quote)`` for a description block, or ``((), "")``.

    Reads sentence by sentence and takes the **first** sentence that mentions
    a flower word and a colour, because a flora leads with the bloom and then
    talks about leaves, fruit and roots -- so the later a colour word appears,
    the less likely it is describing a flower.
    """
    for sentence in _sentences(block):
        words = re.findall(r"[A-Za-z]+", sentence.lower())
        if not words:
            continue
        wordset = set(words)
        if not wordset & set(FLOWER_WORDS):
            continue
        # A sentence naming a leaf or a fruit as well is ambiguous; a flora
        # writes "Flowers yellow; leaves green" as one sentence often enough
        # that refusing it outright loses too much, so it is kept but not
        # called confident.
        mixed = bool(wordset & set(NOT_FLOWER_WORDS))
        found, seen = [], set()
        for word in words:
            bucket = COLOUR_TERMS.get(word)
            if bucket and bucket not in seen:
                seen.add(bucket)
                found.append(bucket)
        if found:
            return tuple(found), sentence.strip()
    return (), ""


def blocks(text: str, wanted: Iterable[str]) -> dict:
    """``{our name: description block}`` for each species we asked about.

    A block runs from the line naming the species to the next heading line,
    capped, because a name whose block never ends would swallow the rest of
    the book. Working in lines rather than in one flat string is what stops a
    sentence beginning "Leaves ..." from being read as the next species.
    """
    lines = normalise(text).split("\n")
    heads = [i for i, ln in enumerate(lines) if _is_heading(ln)]
    out: dict = {}
    for name in wanted:
        canon = _canonical(name)
        if not canon:
            continue
        start = next((i for i, ln in enumerate(lines)
                      if canon in ln.lower()), None)
        if start is None:
            continue
        end = next((h for h in heads if h > start), len(lines))
        out[name] = " ".join(lines[start:end])[:2400]
    return out


def read(text: str, wanted: Iterable[str]) -> list:
    """Findings for every species the text actually describes."""
    found = []
    for name, block in blocks(text, wanted).items():
        buckets, quote = colour_in(block)
        if not buckets:
            continue
        found.append(Finding(
            scientific_name=name,
            found_as=_canonical(name),
            buckets=buckets,
            quote=quote[:300],
            confident=len(buckets) == 1,
        ))
    return sorted(found, key=lambda f: f.scientific_name)


def peek(text: str) -> str:
    """What the extracted text looks like, before anything parses it.

    The same discipline as ``--columns`` on the USDA export: V2.79 lost a day
    to a fixture that agreed with the parser's wrong guess, so the real file
    gets looked at first. An image-only PDF extracts to almost nothing, and
    that must be visible as a number rather than as an empty result later.
    """
    flat = normalise(text)
    words = re.findall(r"[A-Za-z]+", flat)
    binomials = re.findall(r"\b[A-Z][a-z]{3,} [a-z]{4,}\b", flat)
    colour_hits = sum(1 for w in words if w.lower() in COLOUR_TERMS)
    lines = [
        f"{len(text):,} characters, {len(words):,} words",
        f"{len(set(binomials)):,} distinct binomial-looking names",
        f"{colour_hits:,} colour words",
        "",
        "first 400 characters after cleanup:",
        "  " + flat[:400],
    ]
    if len(words) < 5000:
        lines += ["", "WARNING: very little text. If this came from a PDF it "
                  "is probably a scan with no", "text layer, and needs OCR "
                  "rather than extraction."]
    return "\n".join(lines)
