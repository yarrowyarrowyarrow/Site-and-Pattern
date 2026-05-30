"""
structures.py — Structure definitions for placeable landscape elements.

Each structure has an id, name, category, icon (emoji/unicode), default size,
color, description, and optional maintenance hours/year estimate.

The library is curated for native-habitat / lawn-to-habitat design: water
features, wildlife shelters, and lightweight built elements. Several
permaculture-era structures (herb spiral, hugelkultur, keyhole bed,
chicken coop, beehive, greenhouse, cold frame) were removed in the
"Native Habitat Designer" reframe — see the brush pile, snag, native
bee log, rock xeriscape, and bee hotel entries below for the native
habitat equivalents.
"""

from __future__ import annotations

STRUCTURE_CATEGORIES = [
    "Water",
    "Habitat",
    "Growing",
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
        "description": "Wildlife pond. Place at a low point so it collects runoff naturally. Stock with native plants only; provide a shallow shoreline for amphibians and birds.",
        "maintenance_hours_year": 8,
    },
    {
        "id": "swale",
        "name": "Bioswale",
        "category": "Water",
        "icon": "\U0001F30A",      # 🌊
        "shape": "rectangle",
        "size_m": 10.0,
        "width_m": 1.5,
        "color": "#0277bd",
        "fill_color": "#4fc3f7",
        "fill_opacity": 0.25,
        "description": "Shallow vegetated channel that captures runoff and lets it infiltrate. Align along contour; plant with sedges, rushes, and water-tolerant natives.",
        "maintenance_hours_year": 4,
    },
    {
        "id": "rain_garden",
        "name": "Rain Garden",
        "category": "Water",
        "icon": "\U0001F327️",  # 🌧️
        "shape": "ellipse",
        "size_m": 4.0,
        "color": "#00838f",
        "fill_color": "#4dd0e1",
        "fill_opacity": 0.30,
        "description": "Depressed bed that captures roof or driveway runoff. Plant with water-tolerant natives like blue flag iris, swamp milkweed, and sedges.",
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
        "description": "Rainwater collection barrel (200-300L). Place under downspouts; use to water new plantings during establishment.",
        "maintenance_hours_year": 2,
    },

    # ── Habitat (native wildlife shelter & nesting structures) ────────
    {
        "id": "native_bee_log",
        "name": "Native Bee Habitat Log",
        "category": "Habitat",
        "icon": "\U0001FAB5",      # 🪵
        "shape": "rectangle",
        "size_m": 1.2,
        "width_m": 0.4,
        "color": "#6d4c41",
        "fill_color": "#8d6e63",
        "fill_opacity": 0.55,
        "description": "Drilled hardwood log or stumpery providing cavity nesting for native solitary bees (mason, leafcutter). Place sun-facing in a dry spot.",
        "maintenance_hours_year": 1,
    },
    {
        "id": "bee_hotel",
        "name": "Bee Hotel / Nest Box",
        "category": "Habitat",
        "icon": "\U0001F41D",      # 🐝
        "shape": "rectangle",
        "size_m": 0.6,
        "width_m": 0.3,
        "color": "#8d6e63",
        "fill_color": "#a1887f",
        "fill_opacity": 0.55,
        "description": "Purpose-built nesting structure with hollow stems / reed tubes for native solitary bees. South-facing, sheltered from wind and rain.",
        "maintenance_hours_year": 2,
    },
    {
        "id": "brush_pile",
        "name": "Brush Pile",
        "category": "Habitat",
        "icon": "\U0001F343",      # 🍃
        "shape": "circle",
        "size_m": 2.5,
        "color": "#5d4037",
        "fill_color": "#795548",
        "fill_opacity": 0.45,
        "description": "Loose stack of branches and prunings. Shelters chickadees, juncos, sparrows, native bees, and small mammals through winter.",
        "maintenance_hours_year": 1,
    },
    {
        "id": "snag",
        "name": "Snag (Standing Deadwood)",
        "category": "Habitat",
        "icon": "\U0001F332",      # 🌲
        "shape": "circle",
        "size_m": 1.0,
        "color": "#4e342e",
        "fill_color": "#6d4c41",
        "fill_opacity": 0.6,
        "description": "Standing dead or dying tree retained for woodpeckers, cavity nesters, fungi, and saproxylic insects. Leave 3–6 m where safe.",
        "maintenance_hours_year": 0,
    },
    {
        "id": "rock_xeriscape",
        "name": "Rock Xeriscape",
        "category": "Habitat",
        "icon": "\U0001FAA8",      # 🪨
        "shape": "ellipse",
        "size_m": 3.0,
        "color": "#6d6d6d",
        "fill_color": "#9e9e9e",
        "fill_opacity": 0.45,
        "description": "Dry-stacked rock garden / cairn for xeric natives (pasqueflower, harebell, prairie crocus), basking reptiles, and overwintering insects.",
        "maintenance_hours_year": 2,
    },
    {
        "id": "native_lawn_patch",
        "name": "Native Lawn Patch",
        "category": "Habitat",
        "icon": "\U0001F33F",      # 🌿
        "shape": "rectangle",
        "size_m": 6.0,
        "width_m": 4.0,
        "color": "#7cb342",
        "fill_color": "#aed581",
        "fill_opacity": 0.30,
        "description": "Low-mow native turf alternative — sedge meadow, blue grama, sheep fescue. Mow once or twice a year; supports ground-nesting bees.",
        "maintenance_hours_year": 4,
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
        "description": "Standard raised garden bed (3 m × 1.2 m). Useful for vegetable annuals or starting native seedlings before transplanting out.",
        "maintenance_hours_year": 20,
    },

    # ── Storage & Compost ─────────────────────────────────────────────
    {
        "id": "compost_bin",
        "name": "Compost Bin",
        "category": "Storage",
        "icon": "♻️",    # ♻️
        "shape": "circle",
        "size_m": 1.5,
        "color": "#4e342e",
        "fill_color": "#6d4c41",
        "fill_opacity": 0.45,
        "description": "3-bin compost system. Returns yard waste to soil instead of sending it to landfill.",
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
        "description": "Tool and equipment storage. Position near working beds for convenience.",
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
        "description": "Fence, wall, or windbreak. A native hedgerow is usually a better choice for habitat — see the Hedgerow tab.",
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
        "description": "Fire pit or outdoor cooking area. Keep clear of dry vegetation; treat as a gathering anchor for the human-use zone.",
        "maintenance_hours_year": 3,
    },
]

# Quick lookup by id
_BY_ID: dict[str, dict] = {s["id"]: s for s in STRUCTURES}


def get_structure(structure_id: str) -> dict | None:
    """Return structure definition by id, or None.

    Returns None for legacy structure ids (herb_spiral, hugelkultur,
    keyhole_bed, chicken_coop, beehive, greenhouse, cold_frame) that
    were removed in the Native Habitat Designer pivot. Callers loading
    older project files should handle the None case by rendering a
    placeholder marker rather than crashing.
    """
    return _BY_ID.get(structure_id)


def get_structures_by_category(category: str) -> list[dict]:
    """Return all structures in a given category."""
    return [s for s in STRUCTURES if s["category"] == category]


def get_all_structures() -> list[dict]:
    """Return all structure definitions."""
    return STRUCTURES.copy()


# ── Existing on-site features (V1.49) ────────────────────────────────────────
#
# Trees and buildings that already exist on the property. These are NOT part of
# the placeable structure catalogue (they don't belong in the structure browser
# and don't count toward the Habitat Value Score) — they're context the user
# marks so the design generator's shade model honours their cast shade
# (src/shade.py reads element_type existing_tree / existing_building). They ride
# the existing structure placement pipeline via these reserved ids, which
# src/controllers/map_events.py:_on_structure_placed recognises and writes as
# the existing_* feature types instead of a structure.

EXISTING_TREE_ID = "existing_tree"
EXISTING_BUILDING_ID = "existing_building"
EXISTING_FEATURE_IDS = frozenset({EXISTING_TREE_ID, EXISTING_BUILDING_ID})


def existing_feature_def(feature_id: str, *, size_m: float,
                         height_m: float) -> dict:
    """Build a structure-style placement payload for an existing tree/building
    so it flows through the normal click-to-place machinery (the map renders it
    like any structure). ``size_m`` is the canopy/footprint diameter; height is
    carried through for the shade model."""
    if feature_id == EXISTING_TREE_ID:
        return {"id": EXISTING_TREE_ID, "name": "Existing tree", "icon": "🌳",
                "shape": "circle", "size_m": float(size_m),
                "color": "#33691e", "fill_color": "#7cb342",
                "fill_opacity": 0.25, "height_m": float(height_m),
                "category": "Existing"}
    return {"id": EXISTING_BUILDING_ID, "name": "Existing building",
            "icon": "🏠", "shape": "rectangle", "size_m": float(size_m),
            "width_m": float(size_m), "color": "#5d4037",
            "fill_color": "#8d6e63", "fill_opacity": 0.3,
            "height_m": float(height_m), "category": "Existing"}

