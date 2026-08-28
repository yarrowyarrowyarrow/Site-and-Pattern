"""
src/budds_genus.py — the colour a flora states once, at the genus.

Budd's describes **140 of this catalogue's species without naming a flower
colour for them**, and that is not an omission. A flora states the colour once
in the genus description and then notes only departures from it:

    SOLIDAGO  goldenrod
    Heads small and numerous, rays yellow ...

      Solidago rigida  stiff goldenrod
      An erect stout-stemmed species, with a densely fine-hairy rough stem ...

*Solidago rigida* has no colour sentence because it is yellow like the rest of
them. A botanist reads the genus description as part of every species entry
beneath it, so recovering that is reading the book rather than guessing.

Where this stops being safe
---------------------------
*Solidago* is yellow throughout. **Viola is not**: blue, white and yellow
violets all sit in it, and handing every unstated *Viola* the genus colour
would fabricate. The author put it exactly this way -- *"this would hold for
goldenrods but I'm unsure about others"* -- and asked for a list of the ones
that need checking.

**That list is measured, not judged.** Within the book, some species in a
genus do state their own colour. If all of them agree, the genus is uniform
and inheritance is sound. If they disagree, every unstated species in that
genus is flagged. Where no species states a colour there is nothing to test
against, so it is flagged too: an untestable inheritance is not a safe one.

What it is worth
----------------
A genus reading is weaker than a species one and says so. It writes
``flower_colour_source = "flora_genus"``, a mark of its own beside ``flora``,
so a page reads *"from the genus description in a flora"* rather than passing
as a species-level reading. That is a different claim from ``estimated``,
which is this project's own genus default and the thing all of this exists to
remove: the difference is that a published flora asserts this one.
"""

from __future__ import annotations

import re
from typing import Iterable

from src.budds_colour import Finding, _is_heading, colour_in, normalise


def genus_of(name: str) -> str:
    """The genus of a binomial."""
    parts = (name or "").replace("×", "").split()
    return parts[0].strip(",.;:") if parts else ""


def genus_blocks(text: str, genera: Iterable[str]) -> dict:
    """``{genus: description block}`` for each genus asked about.

    A genus heading is the genus name and an English common name alone on a
    line -- ``Viola violet``, ``Solidago goldenrod`` -- which is what
    ``--peek-genus`` found in the real scan. Some floras set it in capitals
    instead, so both are tried.

    **The candidate is validated rather than trusted.** A two-token line is
    also what a species heading stripped of its authority looks like, and the
    book's identification key pairs species names with colours on single lines
    all through the front matter. So a candidate only counts if the text under
    it actually reads like a genus description: a flower word and a colour,
    before the first species heading.
    """
    lines = normalise(text).split("\n")
    heads = [i for i, ln in enumerate(lines) if _is_heading(ln)]
    out: dict = {}
    for genus in genera:
        if not genus:
            continue
        pattern = re.compile(rf"^{re.escape(genus)}\s+[a-z][a-z-]{{2,}}\s*$", re.I)
        caps = re.compile(rf"^{re.escape(genus.upper())}\b")
        for i, line in enumerate(lines):
            text_i = line.strip()
            if not (pattern.match(text_i) or caps.match(text_i)):
                continue
            end = next((h for h in heads if h > i), len(lines))
            block = " ".join(lines[i:end])[:2000]
            if colour_in(block)[0]:
                out[genus] = block
                break
    return out


def uniformity(findings: Iterable) -> dict:
    """``{genus: "uniform" | "variable" | "untested"}`` from species readings.

    Measured from the book: among the species of a genus that state their own
    colour, do they agree? *Solidago* comes back uniform and *Viola* variable
    without anybody deciding that in advance.
    """
    seen: dict = {}
    for f in findings:
        g = genus_of(f.scientific_name)
        if g:
            seen.setdefault(g, set()).add(f.buckets[0])
    return {g: ("uniform" if len(c) == 1 else "variable")
            for g, c in seen.items()}


def inherit(text: str, wanted: Iterable[str], common: dict,
            species_findings: Iterable, measured_from: Iterable = None) -> list:
    """Findings for species the book describes but states no colour for.

    ``species_findings`` says which species still need a colour.
    ``measured_from`` is what the genus is *tested* against, and it has to be
    a different set.

    **They were the same set at first, and it silently disabled the test.**
    The species that state their own colour had already been applied in an
    earlier pass, so they no longer appeared in "needs a colour" -- leaving
    nothing to measure uniformity against, and all 23 inheritances came back
    ``untested`` when *Solidago* alone should have been uniform. A test with
    an empty sample does not fail loudly; it just stops testing.

    So the caller passes readings over the **whole catalogue**, sourced or
    not, and the genus is judged on every species of it the book describes.
    """
    from src.budds_colour import blocks

    done = {f.scientific_name for f in species_findings}
    uni = uniformity(measured_from if measured_from is not None
                     else species_findings)
    todo = [n for n in wanted if n not in done]
    described = blocks(text, todo, common)

    genera = sorted({genus_of(n) for n in described} - {""})
    gblocks = genus_blocks(text, genera)

    out = []
    for name in described:
        g = genus_of(name)
        block = gblocks.get(g)
        if not block:
            continue
        buckets, quote = colour_in(block)
        if not buckets:
            continue
        state = uni.get(g, "untested")
        out.append(Finding(
            scientific_name=name,
            found_as=f"genus ({state})",
            buckets=buckets,
            quote=f"[{g}] {quote}"[:300],
            # Never confident. A uniform genus is the safest case and is still
            # a colour the book states about the genus rather than about this
            # plant, so every one of these is a row a person may want to see.
            confident=False,
        ))
    return sorted(out, key=lambda f: f.scientific_name)


def needs_checking(findings: Iterable) -> list:
    """The genus inheritances a person should look at, worst first.

    ``variable`` first because the book itself disagrees inside that genus;
    then ``untested``, where no species stated a colour so there was nothing
    to check against. A ``uniform`` genus is the sound case and sorts last.
    """
    rank = {"variable": 0, "untested": 1, "uniform": 2}
    return sorted(
        [f for f in findings if f.found_as.startswith("genus")],
        key=lambda f: (rank.get(f.found_as[7:-1], 3), f.scientific_name))
