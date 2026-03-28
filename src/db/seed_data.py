"""Populate the plant database from data/plants.json."""
import json
import os
import sys

from .plants import get_connection, init_db, DB_PATH

DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "data")


def seed_plants():
    plants_file = os.path.join(DATA_DIR, "plants.json")
    if not os.path.exists(plants_file):
        print(f"Error: {plants_file} not found")
        return

    with open(plants_file, encoding="utf-8") as f:
        plants = json.load(f)

    conn = get_connection()

    # Check if already seeded
    count = conn.execute("SELECT COUNT(*) FROM plants").fetchone()[0]
    if count > 0:
        print(f"Database already contains {count} plants. Skipping seed.")
        conn.close()
        return

    for p in plants:
        conn.execute(
            """INSERT INTO plants (
                common_name, scientific_name, plant_type,
                hardiness_zone_min, hardiness_zone_max,
                sun_requirement, water_needs, native_region,
                permaculture_uses, spacing_meters, mature_height_meters,
                bloom_period, fruit_period, edible_parts,
                deciduous_evergreen, soil_ph_min, soil_ph_max,
                perennial_annual, notes
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                p.get("common_name"),
                p.get("scientific_name"),
                p.get("plant_type"),
                int(p["hardiness_zone_min"]) if p.get("hardiness_zone_min") else None,
                int(p["hardiness_zone_max"]) if p.get("hardiness_zone_max") else None,
                p.get("sun_requirement"),
                p.get("water_needs"),
                p.get("native_region"),
                p.get("permaculture_uses"),
                float(p["spacing_m"]) if p.get("spacing_m") else None,
                float(p["mature_height_m"]) if p.get("mature_height_m") else None,
                p.get("bloom_period"),
                p.get("fruit_period"),
                p.get("edible_parts"),
                p.get("deciduous_evergreen"),
                float(p["soil_ph_min"]) if p.get("soil_ph_min") else None,
                float(p["soil_ph_max"]) if p.get("soil_ph_max") else None,
                p.get("perennial_annual"),
                p.get("notes"),
            ),
        )

    conn.commit()
    print(f"Seeded {len(plants)} plants into {DB_PATH}")
    conn.close()


def main():
    init_db()
    seed_plants()


if __name__ == "__main__":
    main()
