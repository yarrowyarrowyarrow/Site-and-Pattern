#!/usr/bin/env python3
"""
scripts/curate_introduced.py — the 24 species GBIF called introduced, read.

**Dev-time, offline, no network.** Run it to see the table; the ingest gate
imports :func:`verdicts`.

    python3 scripts/curate_introduced.py

Why a hand-reviewed list and not a filter
-----------------------------------------
V2.61 asked GBIF whether each of 3,064 animals is introduced to Canada. Two
attempts, both wrong in instructive ways:

1. **The occurrence facet** (``facet=establishmentMeans``) returns **nothing at
   all**, on any species — including a starling with 267,995 Alberta records.
2. **The checklist distributions** (``/species/{key}/distributions``) do return
   values, and the aggregate **disagrees with itself**. Filtering strictly to
   rows that name Canada fixed the Summer Tanager and the Ruffed Grouse, made
   the Alder Flycatcher and Red-eyed Vireo *worse* — from `conflicted` to a
   flat `introduced` — and lost *Apis mellifera* entirely, which is the single
   most obviously introduced insect in the country.

GBIF's backbone distributions aggregate many checklists, some of which stamp
their own `establishmentMeans` across a species' whole range. No filter fixes
a source that contradicts itself.

**But the shortlist is 24 species out of 3,064**, and 24 is a number a person
can simply read. So GBIF's `origin` becomes a *candidate list* rather than a
verdict, and the verdict lives here — the same move `curate_birds.py` makes,
for the same reason, and the reason that worked.

What the list turned out to be
------------------------------
Nineteen of the twenty-four are genuinely introduced to Canada and were caught
correctly: the adelgids, Cabbage White, Seven-spotted Lady Beetle, Asian Lady
Beetle, European Corn Borer, Cinnabar Moth, Large Yellow Underwing, Brown
Marmorated Stink Bug, European Skipper.

**Every clear false positive is a bird** — Snow Goose, Alder Flycatcher,
Red-eyed Vireo, Scarlet Tanager — plus one wasp. Birds already have a human
verdict in `curate_birds.py`, which is why none of this reached the seed data.

Every call below is mine, unsourced, exactly like the 142 fauna rows already
shipped. It is a diffable table with a reason on every line so an Albertan can
disagree with a specific one.
"""

from __future__ import annotations

import json
import os
import sys

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, _ROOT)
_NATIVITY = os.path.join(_ROOT, "data", "fetched", "fauna_nativity.json")

#: scientific_name → (verdict, reason)
#:
#: ``introduced`` — not native to Canada; refuse it whatever its record count.
#: ``native``     — GBIF is wrong; this species belongs here.
#: ``unsure``     — I cannot call it; treated as `introduced` because a
#:                  catalogue of native plantings should fail closed.
INTRODUCED: dict[str, tuple] = {
    # ── Genuinely introduced. GBIF got these right. ──────────────────────
    "Sturnus vulgaris": (
        "introduced",
        "European Starling. Released in New York in 1890 and now continental. "
        "The textbook case, and the one that proved occurrence counts cannot "
        "answer this question."),
    "Pieris rapae": (
        "introduced",
        "Cabbage White. Arrived in Quebec around 1860; now the commonest "
        "white butterfly in the country."),
    "Thymelicus lineola": (
        "introduced",
        "European Skipper. Escaped from a shipment of timothy hay in Ontario "
        "in 1910 and spread west with the forage trade."),
    "Coccinella septempunctata": (
        "introduced",
        "Seven-spotted Lady Beetle. Deliberately released for aphid control "
        "and now displacing native coccinellids."),
    "Harmonia axyridis": (
        "introduced",
        "Asian Lady Beetle. Biocontrol release turned household nuisance and "
        "a documented competitor of native lady beetles."),
    "Halyomorpha halys": (
        "introduced",
        "Brown Marmorated Stink Bug. Recent arrival, a major agricultural "
        "pest, and moving north."),
    "Ostrinia nubilalis": (
        "introduced",
        "European Corn Borer. Arrived with broom corn around 1917."),
    "Noctua pronuba": (
        "introduced",
        "Large Yellow Underwing. First recorded in Nova Scotia in 1979 and "
        "across the continent within twenty years."),
    "Tyria jacobaeae": (
        "introduced",
        "Cinnabar Moth. Released as biocontrol for tansy ragwort. Its host is "
        "a weed we would not plant, so nothing is lost by refusing it."),
    "Calophasia lunula": (
        "introduced",
        "Toadflax Brocade. Released as biocontrol for invasive toadflax — "
        "same reasoning as the Cinnabar Moth."),
    "Adelges abietis": (
        "introduced",
        "Eastern Spruce Gall Adelgid. European, long established, a pest of "
        "the spruces this catalogue recommends."),
    "Adelges piceae": (
        "introduced",
        "Balsam Woolly Adelgid. European, and a serious killer of true firs."),
    "Fenusa dohrnii": (
        "introduced",
        "European Alder Leafminer. Palaearctic; a pest of the alders in this "
        "catalogue."),
    "Metallus lanceolatus": (
        "introduced",
        "A European sawfly whose larvae mine the leaves of Rubus — the "
        "raspberries and thimbleberry this catalogue recommends."),
    "Coleophora deauratella": (
        "introduced",
        "Red Clover Casebearer. European, and a clover-seed pest."),
    "Lateroligia ophiogramma": (
        "introduced",
        "Double Lobed. European noctuid, established in eastern Canada."),
    "Dysdera crocata": (
        "introduced",
        "Woodlouse Spider. Mediterranean, cosmopolitan with human settlement."),
    "Enoplognatha ovata": (
        "introduced",
        "Candy-striped Spider. European, now widespread in North America."),

    # ── GBIF is wrong. Every one of these is native here. ────────────────
    "Anser caerulescens": (
        "native",
        "Snow Goose. Breeds in the Canadian Arctic in millions and stages on "
        "the prairies twice a year. The INTRODUCED rows are European feral "
        "populations, stamped onto a Canada row by a checklist that should "
        "not have."),
    "Empidonax alnorum": (
        "native",
        "Alder Flycatcher. Breeds across the boreal forest, winters in South "
        "America. Nothing about it is introduced anywhere."),
    "Vireo olivaceus": (
        "native",
        "Red-eyed Vireo. One of the commonest breeding birds of the Canadian "
        "deciduous canopy. The Belgian record is a vagrant, not a colony."),
    "Piranga olivacea": (
        "native",
        "Scarlet Tanager. Native to eastern North America — marginal in "
        "Alberta, which is a range question and not an origin one. Held by "
        "curate_birds for range; not introduced."),
    "Isodontia elegans": (
        "native",
        "Elegant Grass-carrying Wasp. Native to western North America. Its "
        "only checklist row is Canada, which suggests the row records "
        "presence and the establishment value is noise."),

    # ── Cannot call it. Fails closed. ────────────────────────────────────
    "Nemorimyza posticata": (
        "unsure",
        "An agromyzid leafminer of asters, recorded on both sides of the "
        "Atlantic, and I cannot tell which way it travelled. Refused, because "
        "a catalogue of native plantings should fail closed — but this is my "
        "uncertainty, not a finding."),
}


def verdicts() -> dict:
    """``scientific_name → True`` for every species the gate must refuse.

    `unsure` counts as refused. A catalogue whose whole claim is that its
    species belong here should fail closed on a species nobody can place.
    """
    return {name: True for name, (v, _) in INTRODUCED.items()
            if v in ("introduced", "unsure")}


def overrides() -> dict:
    """``scientific_name → True`` for species GBIF wrongly called introduced.

    These are *not* waved through the rest of the gate — they still need
    occurrence records in AB or SK like anything else. This only says the
    origin signal was wrong about them.
    """
    return {name: True for name, (v, _) in INTRODUCED.items()
            if v == "native"}


def main() -> int:
    flagged = {}
    if os.path.exists(_NATIVITY):
        with open(_NATIVITY, encoding="utf-8") as fh:
            flagged = {k: v for k, v in json.load(fh).items()
                       if v.get("origin") == "introduced"}
    missing = sorted(set(flagged) - set(INTRODUCED))
    stale = sorted(set(INTRODUCED) - set(flagged))

    for verdict in ("introduced", "unsure", "native"):
        rows = [(k, r) for k, (v, r) in sorted(INTRODUCED.items())
                if v == verdict]
        print(f"\n{verdict.upper()}  ({len(rows)})")
        for name, reason in rows:
            n = flagged.get(name, {}).get("ab_records", "—")
            print(f"  {name:30s} AB={n}")
            print(f"      {reason[:100]}")

    print("\n" + "=" * 64)
    print(f"  {len(verdicts())} species the gate will refuse")
    print(f"  {len(overrides())} GBIF false positives corrected")
    if missing:
        print(f"\n  !! {len(missing)} newly flagged and unreviewed:")
        for m in missing:
            print(f"       {m}")
    if stale:
        print(f"\n  {len(stale)} in this table are no longer flagged by GBIF "
              f"(harmless — the verdict still stands):")
        for s in stale[:10]:
            print(f"       {s}")
    print("=" * 64)
    return 0


if __name__ == "__main__":
    sys.exit(main())
