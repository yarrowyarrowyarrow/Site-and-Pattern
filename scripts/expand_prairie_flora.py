#!/usr/bin/env python3
"""
scripts/expand_prairie_flora.py — add curated Saskatchewan Mixed / Moist Mixed
Grassland forbs that are genuinely absent from the Alberta-built catalogue
(V2.16). Re-runnable and idempotent (dedup by scientific_name), mirroring
scripts/expand_fauna.py.

Most of Saskatchewan's grassland flora already lives in data/plants_master.json
because the Aspen Parkland / Mixed Grassland ecoregions are shared with Alberta —
those shared species are handled by scripts/tag_prairie_provenance.py, not here.
This script only adds the small set of well-documented species the AB catalogue
lacked. Each record is hand-curated to pass src/data_quality.py.

Sources: Budd's Flora of the Canadian Prairie Provinces (Agriculture Canada);
Saskatchewan Native Plant Society; USDA PLANTS distribution. No Indigenous
knowledge is encoded (Design principle P12 — relationship, not extraction).

Run from the project root:  python scripts/expand_prairie_flora.py
"""

from __future__ import annotations

import json
import os

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_FILE = os.path.join(_ROOT, "data", "plants_master.json")

_MONTHS = ["jan", "feb", "mar", "apr", "may", "jun",
           "jul", "aug", "sep", "oct", "nov", "dec"]


def _cal(growing=(), harvest=()):
    """Build cal_jan..cal_dec: dormant by default, with growing/harvest months
    (1-indexed) overridden."""
    cal = {f"cal_{m}": "dormant" for m in _MONTHS}
    for i in growing:
        cal[f"cal_{_MONTHS[i - 1]}"] = "growing"
    for i in harvest:
        cal[f"cal_{_MONTHS[i - 1]}"] = "harvest"
    return cal


def F(**kw):
    """Assemble a full plant record from the curated fields + sensible defaults,
    so each dict carries every column the seeder and data_quality expect."""
    rec = {
        "common_name": "", "scientific_name": "", "plant_type": "wildflower",
        "hardiness_zone_min": "3", "hardiness_zone_max": "8",
        "sun_requirement": "full_sun", "water_needs": "low",
        "spacing_m": "0.3", "mature_height_m": "0.3",
        "native_region": "", "permaculture_uses": "pollinator",
        "bloom_period": "", "fruit_period": "",
        "edible_parts": "", "deciduous_evergreen": "herbaceous",
        "soil_ph_min": "6.5", "soil_ph_max": "8.5",
        "perennial_annual": "perennial", "notes": "",
        "native_to_alberta": 1, "growth_rate": "moderate",
        "years_to_maturity": 2, "growth_curve": "steady",
        "ab_ecoregion": "mixedgrass_prairie", "native_provinces": "AB,SK",
        "price_low_cad": 8, "price_high_cad": 16,
        "availability_class": "native_specialist",
        "sourcing_notes": "Estimate (herb default); SK/AB retail as of 2026",
        "flower_color": "", "flower_form": "daisy",
    }
    cal = kw.pop("cal", _cal(growing=(5, 6), harvest=(7, 8)))
    rec.update(kw)
    rec.update(cal)
    return rec


NEW_FLORA = [
    F(common_name="Scarlet Globemallow", scientific_name="Sphaeralcea coccinea",
      hardiness_zone_min="3", hardiness_zone_max="9",
      spacing_m="0.3", mature_height_m="0.25",
      native_region="Northern Great Plains — dry mixed grassland (AB, SK)",
      permaculture_uses="pollinator,groundcover,erosion_control,ornamental",
      bloom_period="June–August",
      notes="Low, drought-hardy forb of dry mixed grassland; grey-hairy leaves "
            "and brick-orange saucer flowers. Deep taproot thrives on eroded, "
            "calcareous, sandy-clay soils. Nectar and pollen for native bees.",
      ab_ecoregion="mixedgrass_prairie", native_provinces="AB,SK",
      growth_rate="moderate", growth_curve="steady",
      flower_color="#e2571e", flower_form="cluster",
      cal=_cal(growing=(5, 6), harvest=(7, 8))),

    F(common_name="Bastard Toadflax", scientific_name="Comandra umbellata",
      hardiness_zone_min="2", hardiness_zone_max="7",
      sun_requirement="full_sun,partial_shade",
      spacing_m="0.25", mature_height_m="0.2",
      native_region="Widespread native grassland and open parkland (AB, SK)",
      permaculture_uses="pollinator,groundcover,wildlife_habitat",
      bloom_period="May–June", fruit_period="July–August",
      notes="Low rhizomatous forb with waxy blue-green leaves and starry white "
            "umbels; a root hemiparasite that taps neighbouring prairie plants. "
            "Ubiquitous in native grassland and open parkland.",
      ab_ecoregion="mixedgrass_prairie,aspen_parkland", native_provinces="AB,SK",
      growth_rate="slow", growth_curve="slow_start",
      flower_color="#f4f0e6", flower_form="umbel",
      cal=_cal(growing=(5,), harvest=(6, 7, 8))),

    F(common_name="Stiff Goldenrod", scientific_name="Oligoneuron rigidum",
      hardiness_zone_min="3", hardiness_zone_max="9",
      water_needs="medium", spacing_m="0.4", mature_height_m="0.9",
      native_region="Eastern prairies and Moist Mixed Grassland (SK, MB); "
                     "barely reaches the Alberta border",
      permaculture_uses="pollinator,keystone_species,bird_food,wildlife_habitat",
      bloom_period="August–September", fruit_period="September–October",
      notes="Flat-topped clusters of golden flowers on stiff stems with thick "
            "basal leaves; a late-season nectar powerhouse for migrating "
            "monarchs and native bees. Characteristic of SK Moist Mixed "
            "Grassland and parkland; barely reaches Alberta.",
      native_to_alberta=0,
      ab_ecoregion="moist_mixedgrass,aspen_parkland", native_provinces="SK,MB",
      growth_rate="moderate", growth_curve="steady",
      flower_color="#f2c53d", flower_form="cluster",
      cal=_cal(growing=(5, 6, 7), harvest=(8, 9))),

    F(common_name="White Prairie Aster", scientific_name="Symphyotrichum falcatum",
      hardiness_zone_min="3", hardiness_zone_max="8",
      spacing_m="0.3", mature_height_m="0.35",
      native_region="Dry mixed grassland across the prairies (AB, SK)",
      permaculture_uses="pollinator,keystone_species,wildlife_habitat",
      bloom_period="August–September", fruit_period="September–October",
      notes="Small white daisies on wiry, grey-hairy stems; a tough late-bloomer "
            "of dry prairie and eroded slopes. Late nectar for bees and "
            "migrating butterflies (asters are a keystone genus, Tallamy).",
      ab_ecoregion="mixedgrass_prairie", native_provinces="AB,SK",
      flower_color="#f5f5f0", flower_form="daisy",
      cal=_cal(growing=(5, 6, 7), harvest=(8, 9))),

    F(common_name="Woolly Groundsel", scientific_name="Packera cana",
      hardiness_zone_min="2", hardiness_zone_max="7",
      spacing_m="0.25", mature_height_m="0.3",
      native_region="Dry mixed grassland and eroded slopes (AB, SK)",
      permaculture_uses="pollinator,groundcover,erosion_control",
      bloom_period="May–June", fruit_period="June–July",
      notes="Silvery white-woolly rosettes topped by yellow daisy clusters in "
            "early summer; a drought-hardy pioneer of dry, gravelly and eroded "
            "prairie soils. Early-season nectar.",
      ab_ecoregion="mixedgrass_prairie", native_provinces="AB,SK",
      growth_rate="slow", growth_curve="slow_start",
      flower_color="#f2c200", flower_form="daisy",
      cal=_cal(growing=(4, 5), harvest=(6,))),

    F(common_name="Tufted Fleabane", scientific_name="Erigeron caespitosus",
      hardiness_zone_min="2", hardiness_zone_max="7",
      spacing_m="0.2", mature_height_m="0.15",
      native_region="Dry grassland, gravelly slopes and badlands (AB, SK)",
      permaculture_uses="pollinator,groundcover,erosion_control",
      bloom_period="June–July", fruit_period="July–August",
      notes="Low cushion-forming fleabane with pale lavender-white ray flowers; "
            "hugs dry, gravelly and eroded ground. Good early-summer nectar and "
            "a tidy front-of-bed native.",
      ab_ecoregion="mixedgrass_prairie", native_provinces="AB,SK",
      growth_rate="slow", growth_curve="slow_start",
      flower_color="#c9b8e0", flower_form="daisy",
      cal=_cal(growing=(5, 6), harvest=(6, 7))),
]


def main() -> int:
    with open(_FILE, "r", encoding="utf-8") as f:
        records = json.load(f)
    existing = {r.get("scientific_name", "").lower() for r in records}

    added = 0
    for rec in NEW_FLORA:
        if rec["scientific_name"].lower() in existing:
            continue
        records.append(rec)
        existing.add(rec["scientific_name"].lower())
        added += 1

    with open(_FILE, "w", encoding="utf-8") as f:
        json.dump(records, f, indent=2, ensure_ascii=False)
        f.write("\n")

    print(f"expand_prairie_flora: {added} SK grassland species added "
          f"({len(records)} total).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
