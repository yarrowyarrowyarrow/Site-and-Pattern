#!/usr/bin/env python3
"""
scripts/rank_availability.py — where a plant can actually be bought (V3.14).

The owner, V3.14: "most can only be gotten at a native plant specialist and
even then many are too rare to be found there."

Until V3.14 ``availability_class`` came from name keywords in
``scripts/apply_sourcing_data.py``: any name containing "aster", "goldenrod",
"cinquefoil", "currant" or "columbine" was "usually stocked by garden centres",
which put Alpine Aster, Skunk Currant, Marsh Cinquefoil and Alaska Harebell
among 66 such species. Only orchids, gentians, the wood lily and the sundew
were "rare". The species pages, the website's "Where to buy" facet, the order
file, the *Easy to find* toggle and the *Budget-friendly* design goal all read
that field.

This script owns the field now, and it is the provenance record (the pattern of
``seed_flower_colour.py``). Each list below names its species on purpose; the
rules after them are checkable against the shipped occurrence ranges. The tiers,
easiest first:

    big_box            big-box garden sections, usually as a cultivar
    garden_centre      general garden centres, often as a cultivar
    native_specialist  native-plant nurseries: the default for a native
    seed_or_plug       seed or plugs: the grasses, sedges and rushes, and a few
    rare               rarely sold at all

**It is a judgment, and labelled one.** The trade lists are the author's
(Claude's, V3.14) reading of what Alberta garden centres and big-box stores
carried in 2024-26, made without the catalogues (the session could not reach any
nursery's site). Where unsure, the lower tier was chosen, which is the owner's
direction. ``OWNER`` holds the owner's corrections and wins over everything.
Every page that shows a tier already says it is an estimate; ``sourcing_notes``
now also says why a plant is rare.

Run from the project root:

    python scripts/rank_availability.py          # what would change, nothing written
    python scripts/rank_availability.py --apply  # write data/plants_master.json
"""

from __future__ import annotations

import argparse
import collections
import json
import os
import sys

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, _ROOT)

_FILES = [os.path.join(_ROOT, "data", "plants_master.json"),
          os.path.join(_ROOT, "data", "garden_plants.json")]
_RANGES = os.path.join(_ROOT, "data", "plant_ecoregions.json")

#: The owner's corrections, ``{scientific name: tier}``. Empty until a review.
OWNER: dict = {}

#: Sold in big-box garden sections, as the species or a cultivar of it.
BIG_BOX = {
    "Amelanchier alnifolia",      # Saskatoon ('Thiessen', 'Smoky')
    "Prunus virginiana",          # chokecherry ('Schubert')
    "Cornus sericea",             # red osier dogwood
    "Dasiphora fruticosa",        # potentilla, in dozens of cultivars
    "Juniperus horizontalis",     # creeping juniper ('Blue Chip')
    "Picea glauca",               # white spruce, and 'Conica'
    "Viburnum opulus",            # highbush cranberry ('Bailey Compact')
    "Rubus idaeus",               # raspberry cultivars
    "Allium schoenoprasum",       # chives, in the herb rack
}

#: Sold by general garden centres, not only native nurseries.
GARDEN_CENTRE = {
    # trees
    "Populus tremuloides", "Betula papyrifera", "Pinus contorta",
    "Larix laricina", "Abies balsamea", "Pseudotsuga menziesii",
    "Juniperus scopulorum", "Quercus macrocarpa", "Acer negundo",
    "Ulmus americana",
    # shrubs
    "Juniperus communis", "Arctostaphylos uva-ursi", "Symphoricarpos albus",
    "Elaeagnus commutata", "Shepherdia argentea", "Ribes aureum",
    "Yucca glauca",
    # perennials, ferns and a grass, often as cultivars
    "Gaillardia aristata", "Campanula rotundifolia", "Pulsatilla nuttalliana",
    "Geum triflorum", "Linum lewisii", "Monarda fistulosa", "Aster alpinus",
    "Symphyotrichum laeve", "Achillea borealis", "Agastache foeniculum",
    "Echinacea angustifolia", "Aquilegia canadensis", "Ratibida columnifera",
    "Eutrochium maculatum", "Helianthus tuberosus", "Fragaria vesca",
    "Matteuccia struthiopteris", "Panicum virgatum",
}

#: Sold as seed or plugs, beyond the grasses, sedges and rushes.
SEED_OR_PLUG = {"Typha latifolia", "Schoenoplectus acutus", "Carex utriculata",
                "Rhinanthus minor"}

#: Rarely sold, each group for its own reason.
RARE = {
    "an orchid": {"Cypripedium parviflorum", "Spiranthes romanzoffiana"},
    "slow and difficult from seed": {
        "Gentiana calycosa", "Gentiana affinis", "Gentianella amarella",
        "Lilium philadelphicum", "Fritillaria pudica", "Erythronium grandiflorum",
        "Linnaea borealis", "Cornus canadensis"},
    "a hemiparasite, which needs a host plant": {
        "Castilleja miniata", "Castilleja lutescens", "Pedicularis bracteosa",
        "Comandra umbellata", "Orthocarpus luteus"},
    "a bog plant": {
        "Drosera rotundifolia", "Ledum groenlandicum", "Vaccinium oxycoccos",
        "Vaccinium uliginosum"},
    "a wintergreen, which depends on its soil fungi": {"Pyrola asarifolia"},
    "a floating or submerged water plant": {
        "Elodea canadensis", "Lemna trisulca", "Stuckenia pectinata",
        "Myriophyllum sibiricum", "Utricularia vulgaris", "Hippuris vulgaris",
        "Caltha natans", "Nuphar variegata", "Persicaria amphibia"},
}

#: Grown by native nurseries although the rules below would call them rare.
#: Calgary-area nurseries grow from the foothills, which the rule counts as
#: mountains.
NURSERY_GROWN = {
    "Acer glabrum",               # Douglas maple, grown for Calgary yards
    "Dryas drummondii",           # yellow mountain avens, a reclamation staple
    "Aquilegia flavescens",       # yellow columbine
    "Anaphalis margaritacea",     # pearly everlasting
    "Mahonia repens",             # creeping Oregon grape, a dry-shade staple
}

#: Where native nurseries sell: prairie, parkland and the boreal transition.
SETTLED = {"aspen_parkland", "fescue_grassland", "mixed_grassland",
           "moist_mixed_grassland", "cypress_upland", "boreal_transition"}
#: Below this share of its records in SETTLED, a plant is of the mountains or
#: the far north, and few nurseries grow it.
SETTLED_SHARE = 0.10
#: Below this many records in the two provinces, seed is scarce.
FEW_RECORDS = 25

_NOTES = {
    "big_box": "Usually sold as a cultivar.",
    "garden_centre": "Often sold as a cultivar.",
}


def _records() -> dict:
    """``{scientific name: (all records, records in SETTLED)}``."""
    with open(_RANGES, encoding="utf-8") as fh:
        species = json.load(fh).get("species") or {}
    return {name: (sum(r["occurrences"] for r in rows),
                   sum(r["occurrences"] for r in rows
                       if r["ecoregion"] in SETTLED))
            for name, rows in species.items()}


def rank(plant: dict, records: dict) -> tuple:
    """``(tier, why)`` for one catalogue row; ``why`` is "" when the tier needs
    no explaining."""
    name = (plant.get("scientific_name") or "").strip()
    if name in OWNER:
        return OWNER[name], "Confirmed on review."
    if name in BIG_BOX:
        return "big_box", _NOTES["big_box"]
    if name in GARDEN_CENTRE:
        return "garden_centre", _NOTES["garden_centre"]
    if (plant.get("plant_type") in ("grass", "sedge", "rush")
            or name in SEED_OR_PLUG):
        return "seed_or_plug", ""
    for reason, names in RARE.items():
        if name in names:
            return "rare", f"Rarely sold: {reason}."
    if name not in NURSERY_GROWN:
        total, settled = records.get(name, (0, 0))
        if total and settled < SETTLED_SHARE * total:
            return "rare", ("Rarely sold: a plant of the mountains or the far "
                            "north.")
        if total < FEW_RECORDS:
            return "rare", "Rarely sold: few records in Alberta and Saskatchewan."
    return "native_specialist", ""


#: How this script's sentence begins, after the price note and ". ".
_OURS = ("Rarely sold:", "Usually sold as a cultivar.",
         "Often sold as a cultivar.", "Confirmed on review.")


def _note(old: str, why: str) -> str:
    """The price estimate's note, then this script's sentence. One an earlier
    run wrote is replaced, never stacked; no note ended in a full stop before
    this script, so ". " is always the joiner it wrote."""
    base = old or ""
    for start in _OURS:
        cut = base.find(". " + start)
        if cut >= 0:
            base = base[:cut]
    if not why:
        return base
    return f"{base}. {why}" if base else why


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--apply", action="store_true",
                        help="write the tiers (default: report only)")
    args = parser.parse_args()
    records = _records()
    moves = collections.Counter()
    tiers = collections.Counter()
    for path in _FILES:
        if not os.path.exists(path):
            continue
        with open(path, encoding="utf-8") as fh:
            rows = json.load(fh)
        for plant in rows:
            tier, why = rank(plant, records)
            old = plant.get("availability_class") or ""
            tiers[tier] += 1
            if old != tier:
                moves[(old, tier)] += 1
                if not args.apply:
                    print(f"  {plant['common_name']}: {old} -> {tier}"
                          + (f"  ({why})" if why else ""))
            plant["availability_class"] = tier
            plant["sourcing_notes"] = _note(plant.get("sourcing_notes"), why)
        if args.apply:
            with open(path, "w", encoding="utf-8") as fh:
                json.dump(rows, fh, indent=2, ensure_ascii=False)
                fh.write("\n")
    print("\nTiers:", dict(tiers))
    print("Moves:", {f"{a or '-'} -> {b}": n for (a, b), n in moves.items()})
    print("Written." if args.apply else "Nothing written (pass --apply).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
