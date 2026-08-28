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
    found_as: str             #: how it was matched: "name" or "common name"
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
    """Does this line start a new species, or a new family?

    Two shapes, and the second was missing at first. A species heading is
    Genus then epithet, with the genus not a word a flora opens a sentence
    with. A **family** heading is the family name in capitals --
    ``ELEAEAGNACEAE - oleaster family`` -- and because it is not
    Genus-then-epithet it did not end a block, so *Opuntia polyacantha* ran
    968 characters into the Elaeagnaceae and picked up their flowers too. It
    happened to take the right sentence; the next species would not have.
    """
    text = line.strip()
    if re.match(r"[A-Z]{4,}(ACEAE|AE)\b", text):
        return True
    m = re.match(r"([A-Z][a-z]{2,})\s+([a-z]{3,})", text)
    return bool(m) and m.group(1).lower() not in DESCRIPTIVE_STARTS


def _fold(name: str) -> str:
    """A common name reduced to something two books can agree on.

    Budd's is from 1979 and hyphenates differently than this catalogue does:
    *giant-hyssop* against *Giant Hyssop*, *prickly-pear* against *Prickly
    Pear*. Folding case, hyphens and spaces away makes those the same string.
    """
    return re.sub(r"[^a-z]", "", (name or "").lower())


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
        found = _colours_in_words(words)
        if found:
            return tuple(found), sentence.strip()
    return (), ""


def _colours_in_words(words: list) -> list:
    """Colour buckets in order, with compounds collapsed.

    **"Pinkish white" is one colour, not two.** A flora writes both a range and
    a compound and they look alike to a word scanner:

        Flowers white to pinkish      -> two colours, a real range
        Flowers pinkish white         -> ONE colour, a white tinged pink
        Flowers greenish purple       -> ONE colour, a purple

    Reading the second kind as a range would have the site claim bearberry
    blooms "pink to white" where the book says "pinkish white", which is an
    overstatement of exactly the sort this whole line of work exists to remove.

    The signal is adjacency. Two colour words with nothing between them but a
    hedge are a compound, and English puts the head last -- *pinkish white* is
    a white -- so the later word wins and the earlier is dropped. Anything
    separated by a connector ("to", "or", a comma) is a genuine range.
    """
    out: list = []
    prev_colour_at = -99
    for i, word in enumerate(words):
        if word in _HEDGES:
            continue
        bucket = COLOUR_TERMS.get(word)
        if not bucket:
            prev_colour_at = -99
            continue
        # Adjacent to the previous colour, ignoring hedges between them.
        if out and i - prev_colour_at <= 2 and not _connector_between(words,
                                                                     prev_colour_at, i):
            out[-1] = bucket                      # the head noun wins
        elif bucket not in out:
            out.append(bucket)
        prev_colour_at = i
    return out


def _connector_between(words: list, a: int, b: int) -> bool:
    """Is there a range word between two colour words?"""
    return any(w in ("to", "or", "and", "through", "sometimes", "rarely",
                     "varying", "from", "occasionally")
               for w in words[a + 1:b])


def blocks(text: str, wanted: Iterable[str], common: dict = None) -> dict:
    """``{our name: (block, how it was matched)}`` for each species asked about.

    A block runs from the line naming the species to the next heading line,
    capped, because a name whose block never ends would swallow the rest of
    the book. Working in lines rather than one flat string is what stops a
    sentence beginning "Leaves ..." from reading as the next species.

    **The binomial is tried first and the common name second**, because a 1979
    flora does not use 2026 nomenclature. *Cornus sericea* is simply absent
    from Budd's, which files red osier dogwood under *Cornus stolonifera* --
    and no amount of parsing finds a name the book does not contain. The
    common name crosses that gap, and the review file records which key
    matched so a reader can weigh it.
    """
    lines = normalise(text).split("\n")
    lowered = [ln.lower() for ln in lines]
    heads = [i for i, ln in enumerate(lines) if _is_heading(ln)]
    folded = [_fold(ln) for ln in lines]
    common = common or {}

    def _block(start):
        end = next((h for h in heads if h > start), len(lines))
        return " ".join(lines[start:end])[:2400]

    out: dict = {}
    for name in wanted:
        canon = _canonical(name)
        if canon:
            start = next((i for i, ln in enumerate(lowered) if canon in ln),
                         None)
            if start is not None:
                out[name] = (_block(start), "name")
                continue
        # A common name is a weaker key, so it is only reached when the
        # binomial is not in the book at all. Short ones are refused: "rose"
        # or "sage" would match half a flora.
        cname = _fold(common.get(name, ""))
        if len(cname) >= 8:
            start = next((i for i, ln in enumerate(folded) if cname in ln),
                         None)
            if start is not None:
                out[name] = (_block(start), "common name")
    return out


def read(text: str, wanted: Iterable[str], common: dict = None) -> list:
    """Findings for every species the text actually describes."""
    found = []
    for name, (block, how) in blocks(text, wanted, common).items():
        buckets, quote = colour_in(block)
        if not buckets:
            continue
        found.append(Finding(
            scientific_name=name,
            found_as=how,
            buckets=buckets,
            quote=quote[:300],
            confident=len(buckets) == 1 and how == "name",
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
