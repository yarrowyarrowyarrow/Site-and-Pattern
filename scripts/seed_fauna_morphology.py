#!/usr/bin/env python3
"""
scripts/seed_fauna_morphology.py — what the animals look like, as data (V2.36).

    python scripts/seed_fauna_morphology.py            # write
    python scripts/seed_fauna_morphology.py --check    # report, write nothing

WHY THIS EXISTS
---------------
Every creature's appearance used to be computed in `src/scene_wildlife.py` from
SUBSTRINGS OF ITS COMMON NAME — a twelve-genus bee table and seventeen
`if "azure" in name` tests. It worked, in the sense that something got drawn,
and it collapsed the catalogue:

    69 bees        -> 12 distinct appearances   (29 Bombus pixel-identical,
                                                 all 20 cuckoo bees identical)
    31 lepidoptera -> 16 distinct appearances   (Polyphemus, Cecropia and
                                                 Isabella Tiger Moth were one moth)

and none of it was in the database, so none of it could be sourced, checked or
corrected without editing code. Schema v58 gives those columns a home; this
file fills them.

WHAT THESE VALUES ARE, HONESTLY
-------------------------------
**Everything written here is `estimated`** — genus-level and field-mark-level
judgement, in the same standing as `seed_flower_morphology.py`'s floral
formulae. A bumblebee band pattern below is what that species is *generally
described as*; it is not read off a keyed page, and Bombus are notoriously
variable across their range (`rufocinctus` alone runs through half a dozen
colour forms). So every record gets `morph_data_source: "estimated"` and a
BLANK citation, and `scripts/tune_fauna.py` is where they get raised to
`flora`/`photo`/`measured` as somebody actually checks them.

Writing the patterns out rather than leaving them blank is deliberate: it makes
the 29 bumblebees 29 different animals in the preview today, and — more useful —
it gives the person at the bench something to CHECK rather than something to
invent. Wrong-and-visible beats absent.

Wingspans are the mm ranges these species are normally given in the guides,
kept as ranges because that is what is published and inventing a midpoint is
the false precision P9 forbids. They are the first real measurement the fauna
data has ever carried: `size` was a hand-tuned 0.5–1.25 multiplier in Python.

P12: nothing here touches Indigenous knowledge — these are physical
descriptions of insects. See docs/DATA_SOURCES.md.
"""

from __future__ import annotations

import argparse
import json
import os
import sys

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

from src.data_quality import (                              # noqa: E402
    BAND_COLOURS, BEE_BUILDS, FLIGHT_STYLES, RESTING_POSTURES,
    SCOPA_POSITIONS, WING_PATTERNS, WING_SHAPES, WING_TINTS,
    band_pattern_tokens)

_FAUNA = os.path.join(_ROOT, "data", "fauna_master.json")
_BEES = os.path.join(_ROOT, "data", "bee_attributes_master.json")
_LEPS = os.path.join(_ROOT, "data", "lepidoptera_attributes_master.json")

# ── bees, by genus ──────────────────────────────────────────────────────────
# (build, hair, integument, metallic, scopa, wing_tint, body_mm, band_pattern)
# `hair` is the pile colour, `integument` the cuticle under it. Lengths are
# mid-range female/worker. The band pattern here is a GENUS default; Bombus
# overrides it per species below, which is the whole point.
_BEE_GENUS = {
    "bombus":      ("round",      "#f2c12e", "#26211c", 0, "hind_leg", "smoky", 15.0,
                    "yellow,yellow,black,yellow,black,black,black"),
    "anthophora":  ("stout",      "#c9a06a", "#3a2c1e", 0, "hind_leg", "clear", 13.0,
                    "buff,buff,black,buff,black,black,black"),
    "andrena":     ("slender",    "#8a7a63", "#2a2520", 0, "hind_leg", "clear", 10.0,
                    "brown,black,buff,black,buff,black,black"),
    "osmia":       ("stout",      "#3a6b63", "#1d2b33", 1, "abdomen",  "smoky",  9.0,
                    "black,black,black,black,black,black,black"),
    "megachile":   ("leafcutter", "#d8cbb0", "#2a2620", 0, "abdomen",  "smoky", 11.0,
                    "buff,white,white,white,black,black,black"),
    "halictus":    ("slender",    "#9a8f7a", "#2a2622", 0, "hind_leg", "clear",  8.0,
                    "grey,black,white,black,white,black,black"),
    "lasioglossum":("slender",    "#7d7568", "#26231e", 0, "hind_leg", "clear",  6.0,
                    "grey,black,white,black,white,black,black"),
    "agapostemon": ("slender",    "#3fae5a", "#2c6b3a", 1, "hind_leg", "clear",  9.0,
                    "black,yellow,black,yellow,black,yellow,black"),
    "melissodes":  ("round",      "#c2a274", "#3a2c1e", 0, "hind_leg", "clear", 12.0,
                    "buff,white,buff,white,buff,black,black"),
    "eucera":      ("round",      "#c2a274", "#3a2c1e", 0, "hind_leg", "clear", 12.0,
                    "buff,white,buff,white,buff,black,black"),
    "colletes":    ("stout",      "#caa878", "#3a2c20", 0, "hind_leg", "clear", 11.0,
                    "buff,white,white,white,white,black,black"),
    "diadasia":    ("stout",      "#c9a877", "#3a2c1e", 0, "hind_leg", "clear", 11.0,
                    "buff,buff,white,buff,white,black,black"),
}
# Cuckoo bees: nearly hairless and wasp-like, which is itself the field mark —
# no pollen-carrying brush at all, because they do not provision a nest.
_BEE_CUCKOO_GENERA = {"nomada", "triepeolus", "epeolus", "melecta",
                      "xeromelecta", "zacosmia"}
_BEE_CUCKOO = ("slender", "#b5462e", "#241a16", 0, "none", "smoky", 9.0,
               "red,black,white,black,white,black,black")
_BEE_DEFAULT = ("round", "#e0a92a", "#2a231c", 0, "hind_leg", "clear", 10.0,
                "buff,black,buff,black,buff,black,black")

# Bumblebee colour banding: thorax, then T1..T6. THE bumblebee character — every
# key works by naming these in turn, and the catalogue's common names already
# encode most of it ("Tricoloured", "Red-belted", "Yellow-banded", "Half-black").
# Workers, dorsal view, and the commonly-figured form where a species is
# variable. Every one is `estimated`; Williams et al. is where they get checked.
_BOMBUS_BANDS = {
    "Bombus huntii":        "yellow,yellow,orange,orange,yellow,black,black",
    "Bombus ternarius":     "yellow,yellow,orange,orange,yellow,black,black",
    "Bombus rufocinctus":   "yellow,yellow,orange,black,black,black,black",
    "Bombus borealis":      "yellow,yellow,yellow,yellow,buff,buff,black",
    "Bombus appositus":     "yellow,yellow,yellow,black,black,black,black",
    "Bombus balteatus":     "yellow,yellow,orange,orange,black,black,black",
    "Bombus bifarius":      "yellow,yellow,orange,orange,black,black,black",
    "Bombus bohemicus":     "yellow,black,black,yellow,white,white,black",
    "Bombus centralis":     "yellow,yellow,orange,orange,yellow,black,black",
    "Bombus cryptarum":     "yellow,black,yellow,black,white,white,black",
    "Bombus fervidus":      "yellow,yellow,yellow,yellow,yellow,black,black",
    "Bombus flavidus":      "yellow,black,yellow,yellow,black,black,black",
    "Bombus flavifrons":    "yellow,yellow,yellow,orange,orange,black,black",
    "Bombus frigidus":      "yellow,yellow,yellow,orange,orange,black,black",
    "Bombus griseocollis":  "yellow,yellow,brown,black,black,black,black",
    "Bombus insularis":     "yellow,black,black,yellow,yellow,black,black",
    "Bombus melanopygus":   "yellow,yellow,orange,orange,black,black,black",
    "Bombus mixtus":        "yellow,yellow,yellow,black,orange,orange,orange",
    "Bombus nevadensis":    "yellow,yellow,yellow,black,black,black,black",
    "Bombus occidentalis":  "yellow,black,black,yellow,white,white,white",
    "Bombus pensylvanicus": "black,yellow,yellow,yellow,black,black,black",
    "Bombus perplexus":     "yellow,yellow,yellow,black,black,black,black",
    "Bombus polaris":       "yellow,yellow,orange,orange,black,black,black",
    "Bombus sitkensis":     "yellow,yellow,yellow,orange,orange,black,black",
    "Bombus suckleyi":      "yellow,black,black,yellow,orange,black,black",
    "Bombus sylvicola":     "yellow,yellow,yellow,orange,orange,black,black",
    "Bombus terricola":     "yellow,black,yellow,yellow,black,black,black",
    "Bombus vagans":        "yellow,yellow,yellow,black,black,black,black",
}
# The four Bombus cuckoos are socially parasitic: sparser hair, no scopa.
_BOMBUS_CUCKOOS = {"Bombus bohemicus", "Bombus flavidus", "Bombus insularis",
                   "Bombus suckleyi"}

# ── lepidoptera, by species ─────────────────────────────────────────────────
# (wingspan_min, wingspan_max, fore, hind, margin, shape, pattern, eyespots,
#  posture, flight_style)
_LEP = {
    "Danaus plexippus":       (93, 105, "#e2711d", "#e2711d", "#1c140e", "broad",   "veined",    0, "wings_up",   "gliding"),
    "Papilio canadensis":     (67,  90, "#f2d64b", "#f2d64b", "#1c140e", "tailed",  "banded",    0, "wings_up",   "gliding"),
    "Papilio rutulus":        (70,  95, "#f2d64b", "#f2d64b", "#1c140e", "tailed",  "banded",    0, "wings_up",   "gliding"),
    "Papilio machaon":        (65,  86, "#f0d75a", "#f0d75a", "#1c140e", "tailed",  "banded",    1, "wings_up",   "gliding"),
    "Nymphalis antiopa":      (60,  85, "#5a3420", "#5a3420", "#e8d18a", "angular", "banded",    0, "wings_flat", "gliding"),
    "Aglais milberti":        (42,  55, "#c9531f", "#3a2414", "#e0b25a", "angular", "banded",    0, "wings_flat", "erratic"),
    "Nymphalis l-album":      (55,  70, "#b5763a", "#5a3a22", "#e0b25a", "angular", "mottled",   0, "wings_flat", "gliding"),
    "Vanessa cardui":         (50,  65, "#d98a3d", "#caa06a", "#2a1c12", "angular", "mottled",   4, "wings_flat", "erratic"),
    "Vanessa atalanta":       (45,  60, "#2a1c14", "#2a1c14", "#c8352a", "angular", "banded",    0, "wings_flat", "darting"),
    "Limenitis arthemis":     (55,  75, "#20242a", "#20242a", "#eef2f5", "broad",   "banded",    0, "wings_flat", "gliding"),
    "Speyeria aphrodite":     (55,  75, "#d07b2c", "#b06a28", "#2a1c10", "rounded", "spotted",   0, "wings_up",   "bobbing"),
    "Speyeria mormonia":      (38,  50, "#d07b2c", "#b06a28", "#2a1c10", "rounded", "spotted",   0, "wings_up",   "bobbing"),
    "Cercyonis pegala":       (45,  73, "#6a5638", "#6a5638", "#c9a45a", "rounded", "eyespots",  2, "wings_up",   "bobbing"),
    "Celastrina ladon":       (19,  29, "#7fa6e0", "#9fc0ea", "#2a2c34", "rounded", "plain",     0, "wings_up",   "erratic"),
    "Glaucopsyche lygdamus":  (22,  32, "#7fa6e0", "#9fc0ea", "#2a2c34", "rounded", "spotted",   0, "wings_up",   "erratic"),
    "Cupido amyntula":        (19,  26, "#8fb2e6", "#a8c6ee", "#2a2c34", "tailed",  "spotted",   0, "wings_up",   "erratic"),
    "Hesperia comma":         (25,  32, "#c08a3a", "#7a5228", "#2a1c10", "narrow",  "spotted",   0, "swept",      "darting"),
    "Antheraea polyphemus":  (100, 150, "#b98a4a", "#b98a4a", "#6a4a2a", "broad",   "eyespots",  1, "tent",       "bobbing"),
    "Hyalophora cecropia":   (110, 150, "#8a4a3a", "#8a4a3a", "#e0d2c0", "broad",   "banded",    1, "tent",       "bobbing"),
    "Hemaris thysbe":         (38,  55, "#5a7a3a", "#8a5a3a", "#2a1c12", "narrow",  "plain",     0, "swept",      "hovering"),
    "Hemaris diffinis":       (32,  48, "#4a6a3a", "#3a2a20", "#2a1c12", "narrow",  "plain",     0, "swept",      "hovering"),
    "Hyles lineata":          (60,  90, "#7a6a4a", "#b06a4a", "#2a1c12", "narrow",  "veined",    0, "swept",      "hovering"),
    "Pachysphinx modesta":    (95, 135, "#8a7a62", "#9a5a4a", "#3a2c20", "angular", "banded",    0, "swept",      "bobbing"),
    "Smerinthus jamaicensis": (55,  85, "#8a7458", "#b5462e", "#3a2c20", "angular", "eyespots",  1, "swept",      "bobbing"),
    "Pyrrharctia isabella":   (45,  65, "#d8a83a", "#d8a83a", "#8a6a2a", "broad",   "spotted",   0, "tent",       "fluttery"),
    "Lophocampa maculata":    (32,  45, "#e0c060", "#c8a850", "#3a3020", "broad",   "checkered", 0, "tent",       "fluttery"),
    "Epargyreus clarus":      (43,  60, "#5a4028", "#4a3520", "#e8e0c0", "angular", "banded",    0, "swept",      "darting"),
    "Coenonympha tullia":     (25,  38, "#c8a86a", "#b09858", "#8a7448", "rounded", "eyespots",  1, "wings_up",   "bobbing"),
    "Colias philodice":       (32,  54, "#eddc4b", "#e6d24a", "#3a3a1e", "rounded", "plain",     0, "wings_up",   "fluttery"),
    "Plebejus melissa":       (22,  32, "#7f9ee0", "#9fc0ea", "#e0a03a", "rounded", "spotted",   0, "wings_up",   "erratic"),
    "Phyciodes cocyta":       (25,  38, "#d0782c", "#a85f24", "#2a1c10", "rounded", "checkered", 0, "wings_flat", "erratic"),
}
# Anything not named above, by kind. Never silently a butterfly.
_LEP_FALLBACK = {
    "butterfly": (30, 50, "#c88a3a", "#a8702c", "#2a1c10", "rounded", "plain", 0, "wings_up", "fluttery"),
    "skipper":   (25, 35, "#c08a3a", "#7a5228", "#2a1c10", "narrow",  "spotted", 0, "swept",  "darting"),
    "moth":      (35, 60, "#8a7a5a", "#6a5a44", "#3a3020", "broad",   "mottled", 0, "tent",   "fluttery"),
}

_BEE_KEYS = ("body_length_mm", "build", "hair_colour", "integument_colour",
             "metallic", "scopa_position", "wing_tint", "band_pattern")
_LEP_KEYS = ("wingspan_min_mm", "wingspan_max_mm", "forewing_colour",
             "hindwing_colour", "margin_colour", "wing_shape", "wing_pattern",
             "eyespot_count", "resting_posture", "flight_style")


def _load(path):
    with open(path, encoding="utf-8") as fh:
        return json.load(fh)


def _save(path, data):
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(data, fh, indent=2, ensure_ascii=False)
        fh.write("\n")


def bee_morphology(sci: str) -> dict:
    genus = (sci or "").split(" ")[0].lower()
    if genus in _BEE_CUCKOO_GENERA:
        vals = _BEE_CUCKOO
    else:
        vals = _BEE_GENUS.get(genus, _BEE_DEFAULT)
    out = dict(zip(_BEE_KEYS, (vals[6], vals[0], vals[1], vals[2], vals[3],
                               vals[4], vals[5], vals[7])))
    band = _BOMBUS_BANDS.get(sci)
    if band:
        out["band_pattern"] = band
    if sci in _BOMBUS_CUCKOOS:
        out["scopa_position"] = "none"     # socially parasitic: no pollen load
    return out


def lep_morphology(sci: str, kind: str) -> dict:
    vals = _LEP.get(sci) or _LEP_FALLBACK.get(kind or "butterfly",
                                              _LEP_FALLBACK["butterfly"])
    return dict(zip(_LEP_KEYS, vals))


def apply(check: bool = False) -> tuple:
    fauna = {r["scientific_name"]: r for r in _load(_FAUNA)}
    bees, leps = _load(_BEES), _load(_LEPS)

    n_bee = n_lep = 0
    for rec in bees:
        sci = rec.get("scientific_name")
        if not sci or sci not in fauna:
            continue
        rec.update(bee_morphology(sci))
        rec.setdefault("morph_data_source", "estimated")
        rec.setdefault("morph_data_citation", "")
        n_bee += 1
    for rec in leps:
        sci = rec.get("scientific_name")
        if not sci or sci not in fauna:
            continue
        rec.update(lep_morphology(sci, rec.get("kind")))
        rec.setdefault("morph_data_source", "estimated")
        rec.setdefault("morph_data_citation", "")
        n_lep += 1

    if not check:
        _save(_BEES, bees)
        _save(_LEPS, leps)
    return n_bee, n_lep, bees, leps


def _validate(bees, leps) -> list:
    """Everything written must be inside the vocabularies the gate enforces —
    caught here, where the table above is in front of you, rather than at the
    next `python -m src.data_quality` run."""
    bad = []
    # Both master files carry a leading metadata record (`_comment`/`_sources`)
    # with no species; the seeders skip it and so must this.
    bees = [r for r in bees if r.get("scientific_name")]
    leps = [r for r in leps if r.get("scientific_name")]
    for r in bees:
        s = r.get("scientific_name", "?")
        if r.get("build") not in BEE_BUILDS:
            bad.append((s, "build", r.get("build")))
        if r.get("scopa_position") not in SCOPA_POSITIONS:
            bad.append((s, "scopa_position", r.get("scopa_position")))
        if r.get("wing_tint") not in WING_TINTS:
            bad.append((s, "wing_tint", r.get("wing_tint")))
        toks = band_pattern_tokens(r.get("band_pattern"))
        if not 1 <= len(toks) <= 7:
            bad.append((s, "band_pattern length", len(toks)))
        for t in toks:
            if t not in BAND_COLOURS:
                bad.append((s, "band colour", t))
    for r in leps:
        s = r.get("scientific_name", "?")
        if r.get("wing_shape") not in WING_SHAPES:
            bad.append((s, "wing_shape", r.get("wing_shape")))
        if r.get("wing_pattern") not in WING_PATTERNS:
            bad.append((s, "wing_pattern", r.get("wing_pattern")))
        if r.get("resting_posture") not in RESTING_POSTURES:
            bad.append((s, "resting_posture", r.get("resting_posture")))
        if r.get("flight_style") not in FLIGHT_STYLES:
            bad.append((s, "flight_style", r.get("flight_style")))
        lo, hi = r.get("wingspan_min_mm"), r.get("wingspan_max_mm")
        if lo is None or hi is None or lo <= 0 or hi < lo:
            bad.append((s, "wingspan range", (lo, hi)))
    return bad


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true",
                    help="report coverage and validity without writing")
    args = ap.parse_args()

    n_bee, n_lep, bees, leps = apply(check=args.check)
    bad = _validate(bees, leps)
    if bad:
        print("values outside the vocabulary:")
        for row in bad[:25]:
            print("   ", row)
        return 1

    # The number that matters: how many DISTINCT animals this produces. The
    # whole complaint was that 100 species shared 28 appearances.
    bee_looks = len({json.dumps({k: r.get(k) for k in _BEE_KEYS}, sort_keys=True)
                     for r in bees if r.get("scientific_name")})
    lep_looks = len({json.dumps({k: r.get(k) for k in _LEP_KEYS}, sort_keys=True)
                     for r in leps if r.get("scientific_name")})
    verb = "would describe" if args.check else "described"
    print(f"{verb} {n_bee} bees -> {bee_looks} distinct appearances "
          f"(was 12 in src/scene_wildlife.py)")
    print(f"{verb} {n_lep} lepidoptera -> {lep_looks} distinct appearances "
          f"(was 16)")
    print("all `estimated` with a blank citation — raise them in "
          "scripts/tune_fauna.py as they are checked")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
