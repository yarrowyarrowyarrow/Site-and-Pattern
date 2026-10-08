#!/usr/bin/env python3
"""
scripts/apply_sourcing_data.py — populate the sourcing + cost fields added in
schema v19 (V1.45). Re-runnable and idempotent (recomputes from plant_type +
name keywords each run), mirroring scripts/apply_safety_tags.py.

PRICING MODEL: a **range** per single nursery plant, defaulted by `plant_type`
(the canonical defaults live in src/sourcing.py:TYPE_PRICE_DEFAULTS so seed data
and the runtime fallback never drift), with a curated override list for large
specimen trees and rare specialists. Everything is an ESTIMATE — Alberta retail,
region/year-dependent — stamped with an as-of year in `sourcing_notes`.

Sources (CAD, 2025–26): Arnica Wildflowers (Edmonton, herbaceous only: 1-yr
$10–13, 2-yr+ $13–15); small native sellers / ENPS (plug $4, 4" $7, 1-gal $15);
woody-stock nurseries (Bow Point) + garden centres (Blue Grass / Salisbury /
Greengate): shrubs ~$25–60, trees ~$60–200+; TreeTime.ca reforestation
plugs/bare-root ~$2–6 (the seed_or_plug tier).

AVAILABILITY (`availability_class`) is no longer set here (V3.14). It was set
from name keywords, which called Alpine Aster and Skunk Currant garden-centre
stock; `scripts/rank_availability.py` owns it now, with its reasons. This
script leaves the field as it finds it: run that one after it.

Run from the project root:  python scripts/apply_sourcing_data.py
"""

from __future__ import annotations

import json
import os
import sys

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, _ROOT)
from src.sourcing import TYPE_PRICE_DEFAULTS  # noqa: E402  single source of truth

_FILES = [
    os.path.join(_ROOT, "data", "plants_master.json"),
    os.path.join(_ROOT, "data", "garden_plants.json"),
]

AS_OF_YEAR = 2026

# ── Price overrides (CAD) — win over the plant_type default ───────────────────
# Large / slow specimen trees command more than the generic tree default.
_LARGE_TREE_KEYWORDS = (
    "oak", "spruce", "pine", "fir", "cottonwood", "balsam poplar",
    "white poplar", "larch", "tamarack", "maple", "elm", "ash", "birch",
)
_LARGE_TREE_RANGE = (60.0, 150.0)

# Genuinely hard-to-source specialists (mostly native orchids / rare forbs).
_RARE_KEYWORDS = (
    "orchid", "lady's slipper", "ladys slipper", "lady's-slipper",
    "cypripedium", "platanthera", "coralroot", "calypso", "gentian",
    "wood lily", "western red lily", "venus", "twayblade",
)
_RARE_RANGE = (18.0, 40.0)  # forb specialists: more than a common forb


def _has(text: str, keywords) -> bool:
    t = (text or "").lower()
    return any(k in t for k in keywords)


def _classify(record: dict) -> dict:
    ptype = (record.get("plant_type") or "herb").strip().lower()
    name = record.get("common_name", "")
    sci = record.get("scientific_name", "")
    hay = f"{name} {sci}"

    # ── price ── (availability is scripts/rank_availability.py's, V3.14)
    low, high = TYPE_PRICE_DEFAULTS.get(ptype, (8.0, 16.0))
    tier = f"{ptype} default"
    if ptype == "tree" and _has(hay, _LARGE_TREE_KEYWORDS):
        low, high = _LARGE_TREE_RANGE
        tier = "large specimen tree"
    elif _has(hay, _RARE_KEYWORDS):
        low, high = _RARE_RANGE
        tier = "specialist / rare"

    return {
        "price_low_cad": int(low) if low == int(low) else low,
        "price_high_cad": int(high) if high == int(high) else high,
        "sourcing_notes": f"Estimate ({tier}); AB retail as of {AS_OF_YEAR}",
    }


def apply_to_file(path: str) -> int:
    with open(path, "r", encoding="utf-8") as f:
        records = json.load(f)
    for r in records:
        r.update(_classify(r))
    with open(path, "w", encoding="utf-8") as f:
        json.dump(records, f, indent=2, ensure_ascii=False)
        f.write("\n")
    return len(records)


def main() -> int:
    total = 0
    for path in _FILES:
        if not os.path.exists(path):
            print(f"  (skipped, not found: {path})")
            continue
        n = apply_to_file(path)
        total += n
        print(f"  {os.path.basename(path)}: priced {n} records")
    print(f"Done — {total} records given a price range. Now run "
          "scripts/rank_availability.py --apply, which adds its sentence "
          "back to each note.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
