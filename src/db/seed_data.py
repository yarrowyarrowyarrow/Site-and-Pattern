"""
seed_data.py — Plant catalogue seeding for PermaDesign.

Plants are loaded exclusively from data/plants_master.json (433 plants).
The hardcoded SEED_PLANTS tuple list has been removed in v6.

Can be run directly to reset the database:
    python -m src.db.seed_data
"""

import json
import os

_HERE        = os.path.dirname(os.path.abspath(__file__))
_PROJECT_ROOT = os.path.dirname(os.path.dirname(_HERE))
_MASTER_JSON  = os.path.join(_PROJECT_ROOT, "data", "plants_master.json")


def load_plants_from_master() -> list[dict]:
    """Load all plant records from data/plants_master.json."""
    with open(_MASTER_JSON, "r", encoding="utf-8") as f:
        return json.load(f)


# ── Companion planting relationships ──────────────────────────────────────────
# Each tuple: (common_name_a, common_name_b, 'friend' | 'enemy')
# Relationships are bidirectional — only list each pair once.

SEED_COMPANIONS: list[tuple] = [
    # Wild Chives (native allium) repels aphids near roses and fruit trees
    ("Wild Chives", "Prickly Wild Rose", "friend"),
    ("Wild Chives", "Saskatoon Berry",   "friend"),
    ("Wild Chives", "Goodland Apple",    "friend"),
    ("Wild Chives", "Norland Apple",     "friend"),
    ("Wild Chives", "Evans Cherry",      "friend"),

    # Yarrow improves soil and attracts beneficials near most plants
    ("Yarrow", "Goodland Apple",    "friend"),
    ("Yarrow", "Norland Apple",     "friend"),
    ("Yarrow", "Evans Cherry",      "friend"),
    ("Yarrow", "Saskatoon Berry",   "friend"),

    # Native nitrogen-fixers benefit neighbours
    ("Purple Prairie Clover", "Goodland Apple",  "friend"),
    ("Purple Prairie Clover", "Bur Oak",         "friend"),
    ("Silvery Lupine",        "Saskatoon Berry", "friend"),
    ("Canada Milk Vetch",     "Bur Oak",         "friend"),

    # Wild Bergamot deters pests and attracts pollinators
    ("Wild Bergamot", "Saskatoon Berry", "friend"),
    ("Wild Bergamot", "Bur Oak",         "friend"),

    # Stinging Nettle improves soil and fruit quality nearby
    ("Stinging Nettle", "Goodland Apple",  "friend"),
    ("Stinging Nettle", "Norland Apple",   "friend"),
    ("Stinging Nettle", "Evans Cherry",    "friend"),
    ("Stinging Nettle", "Bur Oak",         "friend"),

    # Jerusalem Artichoke is allelopathic — suppresses many plants
    ("Jerusalem Artichoke", "Goodland Apple",  "enemy"),
    ("Jerusalem Artichoke", "Norland Apple",   "enemy"),
    ("Jerusalem Artichoke", "Saskatoon Berry", "enemy"),
]


# ── Planting calendar data (imported from separate module for readability) ─────
from src.db.calendar_data import SEED_CALENDAR  # noqa: E402


# ── CLI entry point ────────────────────────────────────────────────────────────

def reseed() -> None:
    """Drop all plants and re-insert from plants_master.json. Resets the catalogue."""
    from src.db.plants import get_connection, _insert_companions, _seed_from_master_json, _DATA_DIR, _DB_PATH
    import os

    os.makedirs(_DATA_DIR, exist_ok=True)
    conn = get_connection()
    try:
        conn.execute("DELETE FROM companion_friends")
        conn.execute("DELETE FROM companion_enemies")
        conn.execute("DELETE FROM plants")
        conn.commit()
        count = _seed_from_master_json(conn)
        _insert_companions(conn, SEED_COMPANIONS)
        print(f"Seeded {count} plants + companions into {_DB_PATH}")
    finally:
        conn.close()


if __name__ == "__main__":
    # python -m src.db.seed_data
    import sys, os
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
    from src.db.plants import init_db
    init_db()
    reseed()
