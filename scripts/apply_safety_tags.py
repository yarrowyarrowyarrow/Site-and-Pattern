#!/usr/bin/env python3
"""
scripts/apply_safety_tags.py — one-time, idempotent curation of the safety +
spread fields added in schema v18 (V1.44 chunk 2).

WHY A SCRIPT: the toxicity classification is safety-critical and must be
auditable. Rather than hand-edit hundreds of JSON records, the curated denylist
lives here with its reasoning, and the script stamps it onto the seed JSON. It
is idempotent — re-running reproduces the same result — and only writes the
safety keys onto records it actually classifies, so the diff stays small and
unassessed plants keep their existing shape.

CLASSIFICATION POLICY (matches the user-chosen "denylist" model):
  * We tag only plants we are confident are toxic / thorny / aggressive.
  * Everything else is left UNASSESSED (key absent ⇒ '' at seed time). The
    pet/kid-safe filters exclude only the *known*-toxic, so unassessed plants
    still appear — surfaced with a "no known toxicity, not a guarantee" caveat.
  * Severity: 'high' = serious / potentially fatal; 'low' = mild (GI upset,
    irritation). Both are excluded by the safety filters; the split is for
    future UI nuance.
  * Sources: ASPCA toxic-plant database (pets) + standard human poison-control
    references (e.g. Canadian Biodiversity / provincial poison info). Noted per
    record in `safety_source`.

FOOD vs SAFETY OVERLAP is intentional and preserved: e.g. the Prunus cherries
(chokecherry, pin cherry, Nanking, Evans) keep their edible fruit (food
producing) but are flagged toxic to pets — their foliage/twigs/pits are
cyanogenic. Such a plant is correctly *excluded* from pet/kid-friendly while
remaining in the food list.

Run from the project root:  python scripts/apply_safety_tags.py
"""

from __future__ import annotations

import json
import os

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_FILES = [
    os.path.join(_ROOT, "data", "plants_master.json"),
    os.path.join(_ROOT, "data", "garden_plants.json"),
]

# ── Toxicity by genus: genus → (toxicity_pets, toxicity_humans, source) ───────
# Genus-level is the safe default for these (the toxin is shared across the
# genus); species overrides below refine where needed.
_TOXIC_BY_GENUS = {
    # ── Serious / potentially fatal (humans + pets) ──
    "Actaea":      ("high", "high", "Baneberry: cardiogenic glycosides + protoanemonin (ASPCA; poison-control)"),
    "Aconitum":    ("high", "high", "Monkshood: aconitine, highly toxic (ASPCA; poison-control)"),
    "Delphinium":  ("high", "high", "Larkspur: diterpenoid alkaloids (ASPCA; poison-control)"),
    "Lupinus":     ("high", "high", "Lupine: quinolizidine alkaloids, esp. seeds (ASPCA)"),
    "Thermopsis":  ("high", "high", "Golden bean: quinolizidine alkaloids; pea-like pods attract children (poison-control)"),
    "Asclepias":   ("high", "high", "Milkweed: cardenolides (ASPCA toxic to dogs/cats/horses)"),
    "Apocynum":    ("high", "high", "Dogbane: cardiac glycosides (poison-control)"),
    "Solanum":     ("high", "high", "Nightshade: solanine in foliage/unripe fruit (ASPCA)"),
    "Anticlea":    ("high", "high", "Death camas (Anticlea, formerly Zigadenus): zygacine alkaloids, often fatal (poison-control)"),
    "Zigadenus":   ("high", "high", "Death camas: zygacine alkaloids, often fatal (poison-control)"),
    "Toxicoscordion": ("high", "high", "Death camas: zygacine alkaloids, often fatal (poison-control)"),
    "Veratrum":    ("high", "high", "False hellebore: steroidal alkaloids, severe (poison-control)"),
    "Convallaria": ("high", "high", "Lily-of-the-valley: cardiac glycosides (ASPCA)"),
    "Cicuta":      ("high", "high", "Water hemlock: cicutoxin, often fatal (poison-control)"),
    "Conium":      ("high", "high", "Poison hemlock: coniine, often fatal (poison-control)"),
    "Taxus":       ("high", "high", "Yew: taxine alkaloids, often fatal (ASPCA)"),
    "Digitalis":   ("high", "high", "Foxglove: cardiac glycosides (ASPCA)"),
    # ── Mild / irritant (humans + pets) ──
    "Aquilegia":   ("low",  "low",  "Columbine: mild cardiogenic toxins in seeds/roots"),
    "Iris":        ("low",  "low",  "Iris: irritant resins in rhizomes (ASPCA, GI upset)"),
    "Maianthemum": ("low",  "low",  "Wild lily-of-the-valley (NOT Convallaria): berries mildly toxic in quantity"),
    "Symphoricarpos": ("low", "low", "Snowberry: saponins in berries, mildly toxic"),
    "Ranunculus":  ("low",  "low",  "Buttercup: protoanemonin, irritant (poison-control)"),
    "Anemone":     ("low",  "low",  "Anemone: protoanemonin, irritant to skin/GI (poison-control)"),
    "Pulsatilla":  ("low",  "low",  "Prairie crocus: protoanemonin, irritant (poison-control)"),
    "Caltha":      ("low",  "low",  "Marsh marigold: protoanemonin, toxic raw (poison-control)"),
    "Lathyrus":    ("low",  "low",  "Peavine: lathyrogens in seeds, toxic in quantity (poison-control)"),
    "Vicia":       ("low",  "low",  "Vetch: toxins in seeds (poison-control)"),
    # ── Toxic to pets/livestock, but fine / edible for people (humans left unset) ──
    "Achillea":    ("low",  "",     "Yarrow: ASPCA toxic to dogs/cats/horses (mild GI); culinary/medicinal for people"),
    "Allium":      ("low",  "",     "Wild onion/chives: ASPCA toxic to pets (hemolytic anemia); edible for people"),
    "Oxytropis":   ("low",  "",     "Locoweed: swainsonine, toxic to livestock/pets"),
    "Astragalus":  ("low",  "",     "Milkvetch/locoweed: many species toxic to livestock/pets"),
    "Prunus":      ("high", "low",  "Cherry/chokecherry: cyanogenic foliage/twigs/pits (toxic to pets/livestock); fruit flesh edible, pits hazardous"),
    "Sambucus":    ("low",  "low",  "Elderberry: raw berries/stems/leaves cyanogenic; cooked fruit edible"),
}

# Exact scientific-name overrides win over the genus rule. (Reserved for
# species that buck their genus; none needed yet.)
_TOXIC_BY_SPECIES: dict[str, tuple[str, str, str]] = {}

# ── Thorns (kid-proximity hazard) ─────────────────────────────────────────────
_THORNY_GENERA = {
    "Rosa", "Crataegus", "Berberis", "Rubus", "Shepherdia",
    "Elaeagnus", "Hippophae", "Oplopanax", "Cirsium", "Carduus",
}
# Ribes is mixed: gooseberries are spiny, currants are not — tag by species.
_THORNY_SPECIES = {
    "Ribes oxyacanthoides", "Ribes lacustre", "Ribes hirtellum",
}

# ── Spread habit ──────────────────────────────────────────────────────────────
# Only the well-documented aggressive spreaders are flagged; the "well-behaved"
# filter excludes aggressive_rhizomatous + self_seeding.
_SPREAD_BY_GENUS = {
    "Equisetum": "aggressive_rhizomatous",
    "Mentha":    "aggressive_rhizomatous",
    "Petasites": "aggressive_rhizomatous",
    "Urtica":    "aggressive_rhizomatous",
    "Fragaria":  "slow_spreader",
}
_SPREAD_BY_SPECIES = {
    "Anemone canadensis":    "aggressive_rhizomatous",
    "Solidago canadensis":   "aggressive_rhizomatous",
    "Glycyrrhiza lepidota":  "aggressive_rhizomatous",
    "Maianthemum canadense": "aggressive_rhizomatous",
    "Tanacetum vulgare":     "aggressive_rhizomatous",
    "Achillea millefolium":  "self_seeding",
    "Gaillardia aristata":   "self_seeding",
    "Rudbeckia hirta":       "self_seeding",
    "Cornus sericea":        "slow_spreader",
    "Monarda fistulosa":     "slow_spreader",
}


def _genus(sci: str) -> str:
    return (sci or "").strip().split(" ")[0]


def _species_key(sci: str) -> str:
    # First two tokens, dropping cultivar quotes — "Prunus cerasus 'Evans'" → "Prunus cerasus".
    parts = (sci or "").strip().split(" ")
    return " ".join(parts[:2])


def _classify(record: dict) -> dict:
    """Return the safety/spread fields to set on this record (may be empty)."""
    sci = record.get("scientific_name", "")
    genus = _genus(sci)
    species = _species_key(sci)
    out: dict = {}

    tox = _TOXIC_BY_SPECIES.get(species) or _TOXIC_BY_GENUS.get(genus)
    if tox:
        pets, humans, source = tox
        out["toxicity_pets"] = pets
        out["toxicity_humans"] = humans
        out["safety_source"] = source

    if genus in _THORNY_GENERA or species in _THORNY_SPECIES:
        out["has_thorns"] = 1

    spread = _SPREAD_BY_SPECIES.get(species) or _SPREAD_BY_GENUS.get(genus)
    if spread:
        out["spread_habit"] = spread

    return out


def apply_to_file(path: str) -> tuple[int, int]:
    with open(path, "r", encoding="utf-8") as f:
        records = json.load(f)
    classified = 0
    for r in records:
        fields = _classify(r)
        if fields:
            classified += 1
            r.update(fields)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(records, f, indent=2, ensure_ascii=False)
        f.write("\n")
    return classified, len(records)


def main() -> int:
    grand = 0
    for path in _FILES:
        if not os.path.exists(path):
            print(f"  (skipped, not found: {path})")
            continue
        n, total = apply_to_file(path)
        grand += n
        print(f"  {os.path.basename(path)}: tagged {n}/{total} records")
    print(f"Done — {grand} records classified for safety/spread.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
