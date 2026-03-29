"""
structures.py — Structure definitions for placeable landscape elements.

Each structure has an id, name, category, icon (emoji/unicode), default size,
color, description, and optional maintenance hours/year estimate.
"""

from __future__ import annotations

STRUCTURE_CATEGORIES = [
    "Water",
    "Growing",
    "Animal",
    "Storage",
    "Infrastructure",
]

# Each structure definition
# size_m: approximate footprint diameter in metres
# maintenance_hours_year: estimated annual labour hours
STRUCTURES: list[dict] = [
    # ── Water ─────────────────────────────────────────────────────────
    {
        "id": "pond",
        "name": "Pond",
        "category": "Water",
        "icon": "\U0001F4A7",      # 💧
        "shape": "ellipse",
        "size_m": 6.0,
        "color": "#1565c0",
        "fill_color": "#42a5f5",
        "fill_opacity": 0.35,
        "description": "Wildlife pond or irrigation reservoir. Place at low point of property for natural water collection.",
        "maintenance_hours_year": 8,
    },
    {
        "id": "swale",
        "name": "Swale",
        "category": "Water",
        "icon": "\U0001F30A",      # 🌊
        "shape": "rectangle",
        "size_m": 10.0,
        "width_m": 1.5,
        "color": "#0277bd",
        "fill_color": "#4fc3f7",
        "fill_opacity": 0.25,
        "description": "Contour swale for water harvesting and infiltration. Align along contour lines.",
        "maintenance_hours_year": 4,
    },
    {
        "id": "rain_garden",
        "name": "Rain Garden",
        "category": "Water",
        "icon": "\U0001F327\uFE0F",  # 🌧️
        "shape": "ellipse",
        "size_m": 4.0,
        "color": "#00838f",
        "fill_color": "#4dd0e1",
        "fill_opacity": 0.30,
        "description": "Depressed garden bed that captures runoff. Plant with native water-tolerant species.",
        "maintenance_hours_year": 6,
    },
    {
        "id": "rain_barrel",
        "name": "Rain Barrel",
        "category": "Water",
        "icon": "\U0001FAA3",      # 🪣
        "shape": "circle",
        "size_m": 0.8,
        "color": "#37474f",
        "fill_color": "#546e7a",
        "fill_opacity": 0.6,
        "description": "Rainwater collection barrel (200-300L). Place under downspouts.",
        "maintenance_hours_year": 2,
    },

    # ── Growing ───────────────────────────────────────────────────────
    {
        "id": "raised_bed",
        "name": "Raised Bed",
        "category": "Growing",
        "icon": "\U0001F331",      # 🌱
        "shape": "rectangle",
        "size_m": 3.0,
        "width_m": 1.2,
        "color": "#6d4c41",
        "fill_color": "#8d6e63",
        "fill_opacity": 0.35,
        "description": "Standard raised garden bed (3m × 1.2m). Good for annuals and intensive planting.",
        "maintenance_hours_year": 20,
    },
    {
        "id": "keyhole_bed",
        "name": "Keyhole Bed",
        "category": "Growing",
        "icon": "\U0001F511",      # 🔑
        "shape": "keyhole",
        "size_m": 3.0,
        "color": "#795548",
        "fill_color": "#a1887f",
        "fill_opacity": 0.35,
        "description": "Keyhole garden with central compost basket. Maximizes growing area with easy access.",
        "maintenance_hours_year": 15,
    },
    {
        "id": "herb_spiral",
        "name": "Herb Spiral",
        "category": "Growing",
        "icon": "\U0001F300",      # 🌀
        "shape": "spiral",
        "size_m": 2.0,
        "color": "#7cb342",
        "fill_color": "#aed581",
        "fill_opacity": 0.35,
        "description": "Vertical herb garden spiral creating micro-climates. Dry at top, moist at base.",
        "maintenance_hours_year": 8,
    },
    {
        "id": "hugelkultur",
        "name": "Hügelkultur Bed",
        "category": "Growing",
        "icon": "\U000026F0\uFE0F",  # ⛰️
        "shape": "rectangle",
        "size_m": 5.0,
        "width_m": 2.0,
        "color": "#5d4037",
        "fill_color": "#8d6e63",
        "fill_opacity": 0.40,
        "description": "Mounded bed built over buried logs. Self-watering and nutrient-rich for years.",
        "maintenance_hours_year": 6,
    },
    {
        "id": "greenhouse",
        "name": "Greenhouse",
        "category": "Growing",
        "icon": "\U0001F3E1",      # 🏡
        "shape": "rectangle",
        "size_m": 6.0,
        "width_m": 3.0,
        "color": "#66bb6a",
        "fill_color": "#a5d6a7",
        "fill_opacity": 0.20,
        "description": "Season-extending greenhouse. Orient long axis E-W in Edmonton for maximum sun.",
        "maintenance_hours_year": 25,
    },
    {
        "id": "cold_frame",
        "name": "Cold Frame",
        "category": "Growing",
        "icon": "\u2744\uFE0F",    # ❄️
        "shape": "rectangle",
        "size_m": 1.5,
        "width_m": 1.0,
        "color": "#81d4fa",
        "fill_color": "#b3e5fc",
        "fill_opacity": 0.25,
        "description": "Low-profile cold frame for hardening off and early starts. Extends season 4-6 weeks.",
        "maintenance_hours_year": 4,
    },

    # ── Animal ────────────────────────────────────────────────────────
    {
        "id": "chicken_coop",
        "name": "Chicken Coop",
        "category": "Animal",
        "icon": "\U0001F414",      # 🐔
        "shape": "rectangle",
        "size_m": 3.0,
        "width_m": 2.0,
        "color": "#ff8f00",
        "fill_color": "#ffca28",
        "fill_opacity": 0.30,
        "description": "Chicken coop with attached run. Place in Zone 1-2 for daily access.",
        "maintenance_hours_year": 50,
    },
    {
        "id": "beehive",
        "name": "Beehive",
        "category": "Animal",
        "icon": "\U0001F41D",      # 🐝
        "shape": "circle",
        "size_m": 1.0,
        "color": "#fbc02d",
        "fill_color": "#fff176",
        "fill_opacity": 0.45,
        "description": "Beehive for pollination and honey. Face entrance south/southeast, away from paths.",
        "maintenance_hours_year": 20,
    },

    # ── Storage & Compost ─────────────────────────────────────────────
    {
        "id": "compost_bin",
        "name": "Compost Bin",
        "category": "Storage",
        "icon": "\u267B\uFE0F",    # ♻️
        "shape": "circle",
        "size_m": 1.5,
        "color": "#4e342e",
        "fill_color": "#6d4c41",
        "fill_opacity": 0.45,
        "description": "3-bin compost system. Place in Zone 2 near kitchen garden for convenience.",
        "maintenance_hours_year": 12,
    },
    {
        "id": "shed",
        "name": "Tool Shed",
        "category": "Storage",
        "icon": "\U0001F3E0",      # 🏠
        "shape": "rectangle",
        "size_m": 3.0,
        "width_m": 2.5,
        "color": "#5d4037",
        "fill_color": "#795548",
        "fill_opacity": 0.45,
        "description": "Tool and equipment storage. Place in Zone 2 for easy access.",
        "maintenance_hours_year": 3,
    },

    # ── Infrastructure ────────────────────────────────────────────────
    {
        "id": "fence",
        "name": "Fence / Wall",
        "category": "Infrastructure",
        "icon": "\U0001F9F1",      # 🧱
        "shape": "rectangle",
        "size_m": 5.0,
        "width_m": 0.3,
        "color": "#78909c",
        "fill_color": "#90a4ae",
        "fill_opacity": 0.40,
        "description": "Fence, wall, or windbreak structure. Can support espaliered fruit trees.",
        "maintenance_hours_year": 4,
    },
    {
        "id": "fire_pit",
        "name": "Fire Pit",
        "category": "Infrastructure",
        "icon": "\U0001F525",      # 🔥
        "shape": "circle",
        "size_m": 2.0,
        "color": "#e64a19",
        "fill_color": "#ff7043",
        "fill_opacity": 0.35,
        "description": "Fire pit or outdoor cooking area. Place in Zone 1-2 for social gathering.",
        "maintenance_hours_year": 3,
    },
]

# Quick lookup by id
_BY_ID: dict[str, dict] = {s["id"]: s for s in STRUCTURES}


def get_structure(structure_id: str) -> dict | None:
    """Return structure definition by id, or None."""
    return _BY_ID.get(structure_id)


def get_structures_by_category(category: str) -> list[dict]:
    """Return all structures in a given category."""
    return [s for s in STRUCTURES if s["category"] == category]


def get_all_structures() -> list[dict]:
    """Return all structure definitions."""
    return STRUCTURES.copy()
