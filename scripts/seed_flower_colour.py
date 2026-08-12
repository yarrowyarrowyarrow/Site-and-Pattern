#!/usr/bin/env python3
"""Author FLOWER COLOUR per species in data/plants_master.json
(V2.48, schema v64). Idempotent, so this file is both the tool and the
provenance record.

    python scripts/seed_flower_colour.py [--check]

WHY THIS EXISTS
-------------------------------------------------------------------------------
V2.47 made ``flower_color`` filterable and the filter immediately exposed that
the column was **seeded at genus level**. Reported by the author:

    "You have blue and yellow columbine as red."

They were, and so was everything else in the genus: all four *Aquilegia* carried
``#d6453a``, correct for *A. canadensis* and *A. formosa* and wrong for
*A. brevistyla* (blue) and *A. flavescens* (yellow). Measured across the
catalogue, **32 genera have three or more species sharing one hex** and 44 rows
disagree with a colour word in their own common name. Every row said
``flower_data_source = 'estimated'``, which was true and invisible.

THE TWO SIGNALS USED HERE
-------------------------------------------------------------------------------
No flora could be fetched in the session that wrote this (egress policy), so the
corrections rest on two pieces of evidence that travel *with the species* and
that any reader can check without trusting the author:

  ``name``     The accepted common name states the flower colour.
               "Yellow Columbine" is not an opinion about *A. flavescens*.
  ``epithet``  The Latin epithet states it: flavescens, lutescens, aureum,
               flavum, candida, ochroleucus, rosea, purpurea, caerulea.

Both are recorded in ``flower_colour_source`` so a later pass against a real
flora can tell a *checkable* value from the genus default it replaced. Rows this
script does not touch keep ``estimated`` and are now **visibly** estimated: the
directory and the website mark them.

WHAT A COLOUR WORD IN A NAME DOES *NOT* SETTLE
-------------------------------------------------------------------------------
The trap that makes this hand-curated rather than a regex. A colour in a name
often describes the fruit, the foliage, the bark or the seed head:

  Red Baneberry (*Actaea rubra*)          red BERRIES, white flowers  -> unchanged
  Common Snowberry (*S. albus*)           white BERRY, pink bells     -> unchanged
  Golden Sedge (*Carex aurea*)            golden PERIGYNIA, a sedge   -> unchanged
  Purple Oat Grass (*S. purpurascens*)    purplish SEED HEAD, a grass -> unchanged
  White-grained Mountain Rice Grass       the GRAIN                   -> unchanged

Those five are listed in KEEP below with their reason, so the next person to run
the audit does not "fix" them back.

The wind-pollinated families are never given a bloom colour here at all: see
``src/flower_colour.py`` for why a grass, sedge or rush is filed under straw
whatever its hex says.
"""

from __future__ import annotations

import argparse
import json
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))

_JSON = pathlib.Path(__file__).resolve().parent.parent / "data" / "plants_master.json"

#: The palette. Reuses hexes already in the catalogue so the 3D viewer's florets
#: keep rendering from a known-good set rather than gaining twenty new tints.
HEX = {
    "white": "#f2f2ea", "cream": "#ece6c8", "yellow": "#f2c11e",
    "orange": "#e07020", "red": "#d6453a", "pink": "#e58fb0",
    "purple": "#8e6fc4", "blue": "#6f8fd6", "green": "#8aa05a",
}

#: ``scientific_name -> (colour, source, why)``.
#:
#: ``source`` is ``name`` when the accepted common name states the colour and
#: ``epithet`` when the Latin does. Where both agree, ``epithet`` wins: it is
#: the more stable of the two.
CORRECTIONS: dict = {
    # ── Latin says it outright ──────────────────────────────────────────────
    "Aquilegia flavescens":   ("yellow", "epithet", "flavescens = yellowish"),
    "Castilleja lutescens":   ("yellow", "epithet", "lutescens = yellowish"),
    "Ribes aureum":           ("yellow", "epithet", "aureum = golden"),
    "Eriogonum flavum":       ("yellow", "epithet", "flavum = yellow"),
    "Dalea candida":          ("white",  "epithet", "candida = white"),
    "Lathyrus ochroleucus":   ("cream",  "epithet", "ochroleucus = yellowish-white"),
    "Antennaria rosea":       ("pink",   "epithet", "rosea = rose"),

    # ── The common name says it, and it is the flower it is describing ──────
    "Aquilegia brevistyla":   ("blue",   "name", "Blue Columbine"),
    "Aquilegia canadensis":   ("red",    "name",
                               "Eastern Red Columbine; already red, but "
                               "now for a reason rather than by genus "
                               "default"),
    "Aquilegia formosa":      ("red",    "name", "Red Columbine, likewise"),
    "Oxytropis campestris":   ("yellow", "name", "Yellow-flowered Locoweed"),
    "Viola orbiculata":       ("yellow", "name", "Round-leaved Yellow Violet"),
    "Dryas drummondii":       ("yellow", "name",
                               "Yellow Mountain Avens; the white Dryas is "
                               "octopetala, which is a different species"),
    "Geum aleppicum":         ("yellow", "name",
                               "Yellow Avens; the genus default was Geum "
                               "rivale's pink"),
    "Angelica dawsonii":      ("yellow", "name", "Yellow Angelica"),
    "Penstemon confertus":    ("yellow", "name",
                               "Yellow Beardtongue; the only non-purple "
                               "Penstemon in the catalogue"),
    "Linum rigidum":          ("yellow", "name",
                               "Yellow Flax; the blue one is Linum lewisii"),
    "Penstemon procerus":     ("blue",   "name", "Slender Blue Beardtongue"),
    "Penstemon nitidus":      ("blue",   "name", "Smooth Blue Beardtongue"),
    "Clematis occidentalis":  ("blue",   "name", "Blue Clematis"),
    "Iris missouriensis":     ("blue",   "name", "Western Blue Iris"),
    "Viola adunca":           ("blue",   "name", "Early Blue Violet"),
    "Anticlea elegans":       ("white",  "name", "White Camas"),
    "Oenothera nuttallii":    ("white",  "name", "White Evening Primrose"),
    "Geranium richardsonii":  ("white",  "name", "White Geranium"),
    "Symphyotrichum ericoides": ("white", "name",
                                 "Tufted White Prairie Aster; white rays, not "
                                 "the genus purple"),
    "Asclepias ovalifolia":   ("green",  "name",
                               "Green Milkweed; greenish-white umbels, not the "
                               "pink of A. speciosa"),
    "Geranium viscosissimum": ("purple", "name", "Sticky Purple Geranium"),
    "Echinacea angustifolia": ("purple", "name", "Purple Coneflower"),
    "Geum rivale":            ("purple", "name", "Purple Avens / Water Avens"),
    "Capnoides sempervirens": ("pink",   "name", "Pink Corydalis"),
    "Erythranthe lewisii":    ("pink",   "name", "Pink Monkey Flower"),
    "Pyrola asarifolia":      ("pink",   "name", "Pink Pyrola"),
    "Spiraea douglasii":      ("pink",   "name", "Pink Spirea"),
    "Oenothera suffrutescens": ("pink",  "name",
                                "Scarlet Butterfly Plant; white aging to pink "
                                "and red, nearer pink than the genus yellow"),
    "Ribes triste":           ("red",    "name", "Wild Red Currant"),
}

#: ``scientific_name -> why the obvious 'correction' is wrong``. These all trip
#: a naive name-versus-hex audit and all of them are already right.
KEEP: dict = {
    "Actaea rubra": "rubra is the BERRY; the flowers are white",
    "Symphoricarpos albus": "albus is the BERRY; the flowers are pink bells",
    "Carex aurea": "aurea is the perigynium, and a sedge has no showy flower",
    "Schizachne purpurascens": "purplish SEED HEAD on a wind-pollinated grass",
    "Calamagrostis purpurascens": "as above",
    "Oryzopsis asperifolia": "'white-grained' is the GRAIN, on a grass",
    "Spiraea alba var. latifolia": (
        "common name says pink, epithet says white, and the plant is white to "
        "palest pink; the epithet is the more reliable of the two"),
    "Sphaeralcea coccinea": (
        "coccinea = scarlet, and the flowers really are orange-red; the "
        "existing orange is nearer than red"),
    "Oxytropis sericea": (
        "'Early Yellow Locoweed' is a regional name for a white-to-cream "
        "flower; left alone rather than made yellow on the strength of it"),
    "Oxytropis monticola": "as above, and the two are frequently confused",
    "Nassella viridula": (
        "'Green Needle Grass' is the FOLIAGE, and viridula says the same; it "
        "is a bunchgrass, so it has no bloom colour at all. Its plant_type was "
        "also wrong (groundcover), which is what let it be given one"),
    "Oenothera suffrutescens": (
        "'Scarlet Butterfly Plant' overstates it: the flowers open white and "
        "age through pink to red, so pink is the closest single answer and "
        "scarlet is the end of the range, not the flower"),
}

#: ``scientific_name -> (correct plant_type, why)``. Found by the same audit:
#: a mistyped graminoid escapes the wind-pollinated rule in
#: ``src.flower_colour`` and gets given a bloom colour it cannot have.
TYPE_FIXES: dict = {
    "Nassella viridula": ("grass", "a bunchgrass, typed groundcover"),
    "Koeleria macrantha": ("grass", "a bunchgrass, typed groundcover"),
}


def apply(rows: list) -> tuple:
    """Rewrite ``rows`` in place. Returns ``(colours, types, missing)``."""
    by_sci = {}
    for row in rows:
        by_sci.setdefault((row.get("scientific_name") or "").strip(), []).append(row)

    colours = types = 0
    missing = []

    for sci, (colour, source, _why) in CORRECTIONS.items():
        targets = by_sci.get(sci)
        if not targets:
            missing.append(sci)
            continue
        for row in targets:
            row["flower_color"] = HEX[colour]
            row["flower_colour_source"] = source
            colours += 1

    for sci, (ptype, _why) in TYPE_FIXES.items():
        targets = by_sci.get(sci)
        if not targets:
            missing.append(sci)
            continue
        for row in targets:
            row["plant_type"] = ptype
            types += 1

    # Everything untouched is explicitly an estimate rather than silently one.
    for row in rows:
        row.setdefault("flower_colour_source", "")
        if not row["flower_colour_source"]:
            row["flower_colour_source"] = (
                "estimated" if (row.get("flower_color") or "").strip() else "")

    return colours, types, missing


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--check", action="store_true",
                    help="report what would change; write nothing")
    args = ap.parse_args()

    rows = json.loads(_JSON.read_text(encoding="utf-8"))
    before = {(r.get("scientific_name") or ""): r.get("flower_color") for r in rows}
    colours, types, missing = apply(rows)

    changed = [(r["scientific_name"], before.get(r["scientific_name"]),
                r["flower_color"])
               for r in rows
               if before.get(r["scientific_name"]) != r.get("flower_color")]

    print(f"{len(rows)} rows")
    print(f"  {colours} colour corrections across "
          f"{len(CORRECTIONS)} named species")
    print(f"  {types} plant_type corrections")
    print(f"  {len(KEEP)} audit trips deliberately left alone")
    if missing:
        print(f"  !! {len(missing)} names not found in the catalogue: {missing}")
    for sci, old, new in changed:
        print(f"     {sci:34s} {old} -> {new}")

    if args.check:
        print("\n--check: nothing written")
        return 1 if missing else 0

    _JSON.write_text(json.dumps(rows, indent=2, ensure_ascii=False) + "\n",
                     encoding="utf-8")
    print(f"\nwrote {_JSON}")
    print("Remember to bump _SCHEMA_VERSION in src/db/plants.py.")
    return 1 if missing else 0


if __name__ == "__main__":
    raise SystemExit(main())
