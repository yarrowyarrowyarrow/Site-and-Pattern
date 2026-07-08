#!/usr/bin/env python3
"""
scripts/expand_fauna_sk.py — link the curated Saskatchewan grassland forbs
(scripts/expand_prairie_flora.py) to the existing fauna registry so they are not
ecological orphans (V2.16). Re-runnable and idempotent (dedup by
(plant, fauna, relationship)), mirroring scripts/expand_fauna.py.

No NEW fauna are added — the registry's prairie bees, butterflies and moths are
shared with Saskatchewan. This only adds plant ↔ fauna edges from the new plants
to generalist pollinators already in data/fauna_master.json (every `fauna`
reference below is an existing scientific_name; unmatched links are silently
dropped at seed time). Relationships are well-documented, genus-level generalist
associations — no over-specific claims (P9). No Indigenous knowledge is encoded
(P12 — relationship, not extraction).

Sources: Acorn & Sheldon, Butterflies of Alberta; Packer et al., native bee
compilations; general prairie-composite pollination literature.

Run from the project root:  python scripts/expand_fauna_sk.py
"""

from __future__ import annotations

import json
import os

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_LINKS_FILE = os.path.join(_ROOT, "data", "plant_fauna_master.json")


def L(plant, fauna, relationship, specificity="generalist", source="", notes=""):
    return {"plant": plant, "fauna": fauna, "relationship": relationship,
            "specificity": specificity, "source": source, "notes": notes}


_SRC = "Prairie-composite pollination literature; Acorn & Sheldon 2006"

NEW_LINKS = [
    # Scarlet Globemallow — mallow pollen/nectar for long- and short-tongued bees.
    L("Scarlet Globemallow", "Bombus spp.", "pollen", source=_SRC,
      notes="Bumble bees work the orange saucer flowers for pollen."),
    L("Scarlet Globemallow", "Megachile spp.", "pollen", source=_SRC,
      notes="Leafcutter bees collect globemallow pollen."),
    L("Scarlet Globemallow", "Halictus spp.", "nectar", source=_SRC),

    # Bastard Toadflax — shallow white umbels favour small short-tongued bees.
    L("Bastard Toadflax", "Lasioglossum spp.", "nectar", source=_SRC,
      notes="Small sweat bees at the open umbels."),
    L("Bastard Toadflax", "Halictus spp.", "nectar", source=_SRC),

    # Stiff Goldenrod — a keystone late-season nectar source (Solidago).
    L("Stiff Goldenrod", "Danaus plexippus", "nectar", source=_SRC,
      notes="Fall goldenrod fuels migrating monarchs."),
    L("Stiff Goldenrod", "Bombus spp.", "nectar", source=_SRC),
    L("Stiff Goldenrod", "Colias philodice", "nectar", source=_SRC),
    L("Stiff Goldenrod", "Agapostemon virescens", "pollen", source=_SRC),

    # White Prairie Aster — keystone late nectar (Symphyotrichum).
    L("White Prairie Aster", "Bombus spp.", "nectar", source=_SRC),
    L("White Prairie Aster", "Vanessa cardui", "nectar", source=_SRC,
      notes="Late-season nectar for migrating painted ladies."),
    L("White Prairie Aster", "Lasioglossum spp.", "pollen", source=_SRC),

    # Woolly Groundsel — early-summer yellow composite.
    L("Woolly Groundsel", "Halictus spp.", "nectar", source=_SRC),
    L("Woolly Groundsel", "Bombus spp.", "nectar", source=_SRC),

    # Tufted Fleabane — small early nectar for tiny bees.
    L("Tufted Fleabane", "Lasioglossum spp.", "nectar", source=_SRC),
    L("Tufted Fleabane", "Halictus spp.", "nectar", source=_SRC),
]


def _key(link: dict):
    return (link["plant"], link["fauna"], link["relationship"])


def main() -> int:
    with open(_LINKS_FILE, "r", encoding="utf-8") as f:
        links = json.load(f)

    existing = {_key(el) for el in links if isinstance(el, dict) and "plant" in el}
    added = 0
    for link in NEW_LINKS:
        if _key(link) in existing:
            continue
        links.append(link)
        existing.add(_key(link))
        added += 1

    with open(_LINKS_FILE, "w", encoding="utf-8") as f:
        json.dump(links, f, indent=2, ensure_ascii=False)
        f.write("\n")

    print(f"expand_fauna_sk: {added} plant↔fauna links added "
          f"({len(links)} elements total).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
