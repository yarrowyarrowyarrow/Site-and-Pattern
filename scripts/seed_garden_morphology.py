"""Author the botanical-morphology fields for data/garden_plants.json (V2.30).
Idempotent — re-running rewrites the same values, so this file is both the tool
and the provenance record for them.

    python scripts/seed_garden_morphology.py [--check]

WHY THIS EXISTS
`scripts/seed_woody_morphology.py` and `scripts/seed_non_woody_morphology.py`
between them cover all 434 rows of `data/plants_master.json`. Neither touches
`data/garden_plants.json`, whose five rows were therefore the ONLY species in the
whole catalogue with no `leaf_shape`, no `leaf_size_cm` and no `bark_color`.

That was visible. Since V2.29 a plant's recorded leaf characters select its baked
archetype variant and put its blade outline into a tree crown's silhouette, so
five species with no record fell back to neutral defaults — and three of them are
trees standing next to each other in the catalogue. A user reviewing the sprite
contact sheet picked them out unprompted: "Evans Cherry, Goodland Apple and
Norland Apple are three near-identical green blobs."

These are cultivated fruit trees rather than native flora, which is why they live
in a separate file (the app's subject is native-plant landscaping; these are the
edible-yard additions). They still have to be drawn.

SOURCING (P9)
Standard descriptive characters for very well-described cultivated species — the
kind of thing any pomology text or extension guide agrees on. Recorded as TYPICAL
values for the species, not measurements of any individual. Cultivar names
('Goodland', 'Norland', 'Evans') are prairie-hardy selections; their leaf and
bark characters are those of the species, so the values here are the species'.
Colours are representative renderings chosen for the 3D palette, an
interpretation rather than a measurement, exactly as in the woody script.

This encodes no traditional, cultural or Indigenous knowledge of these plants —
only the botanical description of leaf and bark (P12).
"""

from __future__ import annotations

import argparse
import json
import os
import sys

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_GARDEN = os.path.join(_ROOT, "data", "garden_plants.json")

FIELDS = ("leaf_shape", "leaf_size_cm", "leaf_arrangement",
          "bark_color", "fall_color", "branching", "growth_form")

# scientific_name -> the FIELDS above, in order. None = leave empty (an honest
# empty rather than a guess — the V2.29 precedent).
MORPHOLOGY = {
    # Apples: broad elliptic-to-ovate leaves, grey-brown scaly bark, a low
    # spreading open-centre crown (orchard trees are pruned to it, and these
    # two are sold as such).
    "Malus domestica 'Goodland'": (
        "elliptic", 8.0, "alternate", "#6a5238", "#c8a83e", "decurrent", ""),
    "Malus domestica 'Norland'": (
        "elliptic", 7.5, "alternate", "#6a5238", "#c4a444", "decurrent", ""),
    # Sour cherry: narrower, glossier, more sharply toothed than an apple's,
    # on the smooth banded reddish-brown bark typical of Prunus.
    "Prunus cerasus 'Evans'": (
        "ovate", 7.0, "alternate", "#7a5140", "#d4762e", "decurrent", ""),
    # Nanking cherry: a multi-stemmed shrub with small, distinctly wrinkled,
    # densely hairy obovate leaves — nothing like the tree cherries above.
    "Prunus tomentosa": (
        "obovate", 5.0, "alternate", "#8a5a3e", "#d98a3a", "multi_stem", ""),
    # Bee balm duplicates Monarda fistulosa in plants_master, which already
    # carries morphology; repeated here so the two rows cannot disagree.
    "Monarda fistulosa": (
        "lanceolate", 8.0, "opposite", "", "", "", "clump"),
}


def apply(records, check=False):
    applied, seen = 0, set()
    for rec in records:
        sci = (rec.get("scientific_name") or "").strip()
        row = MORPHOLOGY.get(sci)
        if not row:
            continue
        seen.add(sci)
        if not check:
            for field, value in zip(FIELDS, row):
                if value == "" or value is None:
                    rec.setdefault(field, "")
                else:
                    rec[field] = value
        applied += 1
    return applied, sorted(set(MORPHOLOGY) - seen)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true",
                    help="report coverage without writing")
    args = ap.parse_args()

    with open(_GARDEN, encoding="utf-8") as fh:
        records = json.load(fh)
    applied, missing = apply(records, check=args.check)

    if missing:
        print("morphology rows with no matching species (renamed?):")
        for name in missing:
            print("   ", name)
    uncovered = [r.get("common_name") for r in records
                 if (r.get("scientific_name") or "").strip() not in MORPHOLOGY]
    if uncovered:
        print(f"garden species still without morphology ({len(uncovered)}):")
        for name in uncovered:
            print("   ", name)

    if args.check:
        print(f"check: {applied}/{len(records)} garden species covered")
        return 1 if (missing or uncovered) else 0

    with open(_GARDEN, "w", encoding="utf-8") as fh:
        json.dump(records, fh, indent=2, ensure_ascii=False)
        fh.write("\n")
    print(f"wrote {_GARDEN}: {applied}/{len(records)} garden species")
    return 0


if __name__ == "__main__":
    sys.exit(main())
