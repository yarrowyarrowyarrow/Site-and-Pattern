"""Author the ``fruit_form`` field for every fleshy-fruited species in
data/plants_master.json (V2.29). Idempotent — re-running rewrites the same
values, so this file is both the tool and the provenance record for them.

    python scripts/seed_fruit_morphology.py [--check]

WHY THIS FIELD EXISTS
The 3D viewer drew every fruit in the catalogue as the same sprite: one
radial-gradient disc, tinted by the species' ``fruit_color``. That is a
defensible primitive for a currant and simply false for most of the rest. A
strawberry is a conic red receptacle studded with pips and shouldered by a green
calyx; a rose hip is an urn with a persistent dark crown; a chokecherry hangs in
a drooping raceme; a raspberry is a thimble of druplets; a mountain-ash carries a
flat-topped bunch of dozens. Drawn as spheres they are all "red dot", which is
both wrong and — worse for this app — makes species that are easy to tell apart
in the hand indistinguishable on screen (P5: make the invisible visible; P9: no
false precision, but no false SAMENESS either).

``fruit_color`` already existed (v35). ``fruit_form`` is its shape half, and it
is a data field rather than a genus table in the viewer for the same reason
``flower_form`` is: the renderer should read the catalogue, not re-encode
botany in JavaScript.

THE FORMS
  berry        A round, single fleshy fruit. Currant-type gooseberries,
               blueberries, snowberries, honeysuckle pairs, bearberry,
               buffaloberry, Oregon-grape, baneberry, Solomon's-seal.
  strig        A hanging string of small round berries — the currant signature
               (Ribes), and the reason a currant reads differently from a
               gooseberry on the same bush architecture.
  raceme       A longer, looser drooping cluster of round drupes: chokecherry.
  cherry       A round drupe on a long visible pedicel, in loose umbel-like
               bunches: pin cherry. Distinct from `raceme` precisely because
               pin cherry and chokecherry are the pair people confuse.
  pome         Round with a five-point calyx eye at the far end: saskatoon,
               hawthorn. The eye is the field mark that says "not a berry".
  hip          An urn/ovoid with a persistent dark calyx crown: rose.
  strawberry   A conic accessory fruit, pip-studded, green calyx at the
               shoulder: Fragaria.
  aggregate    A thimble/dome of many small druplets: Rubus.
  flat_cluster A flat-topped bunch of many small fruits: mountain ash,
               highbush cranberry, red-osier dogwood, bunchberry, sumac.

SOURCING (P9)
These are standard descriptive characters for well-described regional species —
fruit type is one of the least contested things in a flora. Values are TYPICAL
for the species, not measurements of an individual, and the reference frame is
the general botanical literature for the prairie provinces and boreal Canada
catalogued in docs/REFERENCES.md. Where a species could arguably take two forms
(Ribes aureum's short strigs, say) the choice is the one that reads correctly at
garden viewing distance, which is the only thing the field is used for.

This encodes no traditional, cultural or Indigenous knowledge of these plants —
only the botanical description of the fruit's shape (P12).
"""

from __future__ import annotations

import argparse
import json
import os
import sys

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_MASTER = os.path.join(_ROOT, "data", "plants_master.json")

FIELD = "fruit_form"

# scientific_name -> fruit_form
FRUIT_FORM = {
    # ── round single berries ────────────────────────────────────────────
    "Actaea rubra":                "berry",   # glossy red, stalked cluster
    "Arctostaphylos uva-ursi":     "berry",   # dull red mealy drupe
    "Lonicera dioica":             "berry",   # paired orange-red
    "Lonicera involucrata":        "berry",   # paired black in red bracts
    "Mahonia repens":              "berry",   # blue, glaucous
    "Maianthemum canadense":       "berry",
    "Maianthemum racemosum":       "berry",
    "Maianthemum stellatum":       "berry",
    "Ribes oxyacanthoides":        "berry",   # gooseberry: single, not a strig
    "Shepherdia argentea":         "berry",
    "Shepherdia canadensis":       "berry",
    "Symphoricarpos albus":        "berry",   # waxy white
    "Symphoricarpos occidentalis": "berry",
    "Vaccinium myrtilloides":      "berry",
    "Vaccinium myrtillus":         "berry",
    "Vaccinium oxycoccos":         "berry",
    "Vaccinium uliginosum":        "berry",
    # ── hanging strings (Ribes) ─────────────────────────────────────────
    "Ribes americanum":            "strig",
    "Ribes aureum":                "strig",
    "Ribes glandulosum":           "strig",
    "Ribes hudsonianum":           "strig",
    "Ribes lacustre":              "strig",
    "Ribes triste":                "strig",
    # ── the confusable cherries ─────────────────────────────────────────
    "Prunus virginiana":           "raceme",  # chokecherry: drooping raceme
    "Prunus pensylvanica":         "cherry",  # pin cherry: long-stalked bunches
    # ── pomes with a calyx eye ──────────────────────────────────────────
    "Amelanchier alnifolia":       "pome",
    "Crataegus douglasii":         "pome",
    # ── rose hips ───────────────────────────────────────────────────────
    "Rosa acicularis":             "hip",
    "Rosa arkansana":              "hip",
    "Rosa woodsii":                "hip",
    # ── strawberries ────────────────────────────────────────────────────
    "Fragaria vesca":              "strawberry",
    "Fragaria virginiana":         "strawberry",
    # ── aggregates of druplets (Rubus) ──────────────────────────────────
    "Rubus arcticus":              "aggregate",
    "Rubus idaeus":                "aggregate",
    "Rubus parviflorus":           "aggregate",
    "Rubus pedatus":               "aggregate",
    "Rubus pubescens":             "aggregate",
    # ── flat-topped bunches ─────────────────────────────────────────────
    "Cornus canadensis":           "flat_cluster",
    "Cornus sericea":              "flat_cluster",
    "Rhus aromatica":              "flat_cluster",
    "Sorbus scopulina":            "flat_cluster",
    "Viburnum edule":              "flat_cluster",
    "Viburnum opulus":             "flat_cluster",
}

# Fruit colours corrected while authoring the shapes. Pin cherry is the reason
# this dict exists: it shared chokecherry's near-black #3a1426, so a 7 m pin
# cherry and a 4 m saskatoon in the same bed were the same silhouette wearing
# the same dark dots. Pin cherry fruit is bright translucent red, and saying so
# separates the two species at a glance — which was the reported complaint.
FRUIT_COLOR_FIX = {
    "Prunus pensylvanica": "#d8322b",   # bright translucent red, not near-black
}


def apply(records, check=False):
    applied, seen, recoloured = 0, set(), 0
    for rec in records:
        sci = (rec.get("scientific_name") or "").strip()
        form = FRUIT_FORM.get(sci)
        if form:
            seen.add(sci)
            if not check:
                rec[FIELD] = form
            applied += 1
        fix = FRUIT_COLOR_FIX.get(sci)
        if fix and (rec.get("fruit_color") or "") != fix:
            if not check:
                rec["fruit_color"] = fix
            recoloured += 1
    missing = sorted(set(FRUIT_FORM) - seen)
    return applied, missing, recoloured


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true",
                    help="report coverage without writing")
    args = ap.parse_args()

    with open(_MASTER, encoding="utf-8") as fh:
        records = json.load(fh)
    # Every species with a curated fruit_color needs a shape; a species without
    # one is dry-fruited and draws nothing, so it needs no form.
    fleshy = [r for r in records
              if (r.get("fruit_color") or "").strip().startswith("#")]
    applied, missing, recoloured = apply(records, check=args.check)

    if missing:
        print("fruit_form rows with no matching species (renamed?):")
        for name in missing:
            print("   ", name)
    uncovered = [r["common_name"] for r in fleshy
                 if (r.get("scientific_name") or "").strip() not in FRUIT_FORM]
    if uncovered:
        print(f"fleshy-fruited species still without a fruit_form ({len(uncovered)}):")
        for name in uncovered:
            print("   ", name)

    if args.check:
        print(f"check: {applied}/{len(fleshy)} fleshy-fruited species covered"
              f"; {recoloured} colour correction(s) pending")
        return 1 if (missing or uncovered) else 0

    with open(_MASTER, "w", encoding="utf-8") as fh:
        json.dump(records, fh, indent=2, ensure_ascii=False)
        fh.write("\n")
    print(f"wrote {_MASTER}: {applied}/{len(fleshy)} fleshy-fruited species"
          f", {recoloured} fruit colour(s) corrected")
    return 0


if __name__ == "__main__":
    sys.exit(main())
