"""
member_colors.py — the one colour table for plants.

A plant is drawn in its type's colour everywhere: the plant list's dot, the map
marker (``html/map/10-plant-key.js`` mirrors this table, and the map legend is
built from it), the community builder's layout and the 3D scene contract. The
colour a person gives a species (its ``marker_color``) wins over its type's.

Until V3.03 community members on the map were coloured by vegetation layer, in
seven greens several of which were nearly the same, and only until the design
was reopened, when the loader drew them by type; the builder had a third table
of its own. One scheme, which the legend can say. The module keeps its name so
its importers do not churn.

Qt-free and import-light on purpose: placement code paths (map event router,
area-fill controller) need a colour without dragging in the whole ``src.app``
module (whose import requires QtWebEngine to be set up first).
"""

from __future__ import annotations

# Canonical per-plant-type marker colours. Shared by the plant browser
# (src/plant_list_view re-exports it as _TYPE_COLORS), the map markers
# (html/map/10-plant-key.js mirrors it, guarded by tests/test_plant_key.py),
# the community builder and the 3D scene contract (src/scene_contract).
TYPE_COLORS: dict[str, str] = {
    "tree":        "#2e7d32",   # dark green
    "shrub":       "#558b2f",   # olive green
    "wildflower":  "#ab47bc",   # purple — flowering forbs (V1.87)
    "herb":        "#9ccc65",   # light green — foliage / medicinal herbs
    "groundcover": "#c6a817",   # gold
    "grass":       "#cddc39",   # lime — true grasses
    "sedge":       "#8d6e63",   # taupe — sedges
    "rush":        "#5d4037",   # brown — rushes
    "vine":        "#00838f",   # teal
    "fern":        "#33691e",   # deep olive
    "aquatic":     "#29b6f6",   # blue — aquatic / wetland
    "root":        "#6d4c41",   # legacy (no plants currently tagged 'root')
}

#: A plant with no type the table knows.
DEFAULT_COLOR = "#66bb6a"


def plant_color(plant: dict) -> str:
    """The colour a plant is drawn in: the one given to its species, else its
    type's."""
    plant = plant or {}
    return (plant.get("marker_color")
            or TYPE_COLORS.get(plant.get("plant_type") or "", DEFAULT_COLOR))
