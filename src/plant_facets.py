"""
plant_facets.py — the browser's facet vocabularies (V2.46).

Qt-free, on purpose and for the second time: ``src/ecoregion.py`` was pulled
out of this same file in V2.38 so the data validator and the range-derivation
script could read the ecoregion list without importing PyQt6, and these labels
have exactly the same problem — ``polyculture_panel`` and two test modules read
them, and importing a 1,600-line widget to get a dict of eleven strings is a
dependency nobody chose.

Extracted when the architecture guard fired on ``plant_panel.py`` at 1,609 of
its 1,600 lines. The rule that table states is *"the fix when one trips is
extraction, never a bigger number"*, and this is the most obviously extractable
thing in the file: pure data, no widget, no behaviour. ``plant_panel`` re-exports
every name, so nothing that imported them from there has to change.

Each ``plant_type`` key matches a colour swatch on the map, so the dropdown
doubles as the map legend — do not add a key here without one there.
"""

from __future__ import annotations

from src.ecoregion import ECOREGIONS as _ECOREGIONS

# ── Plant type / habit / lifecycle ───────────────────────────────────────────
# V1.87: full botanical split. "herb" was a 231-plant catch-all; it's now split
# into Wildflower (flowering forbs) and Herb / Foliage (foliage / medicinal),
# grasses/sedges/rushes/ferns/aquatics get their own colours + filter entries,
# and the dead "Root / Bulb" (0 plants) is retired. Order: woody → forbs →
# graminoids → ground/fern/water. Each key matches a plant_type colour swatch
# (the dropdown doubles as the map legend).
_TYPE_LABELS: dict[str, str] = {
    "tree":        "Tree",
    "shrub":       "Shrub",
    "vine":        "Vine",
    "wildflower":  "Wildflower",
    "herb":        "Herb / Foliage",
    "groundcover": "Groundcover",
    "grass":       "Grass",
    "sedge":       "Sedge",
    "rush":        "Rush",
    "fern":        "Fern",
    "aquatic":     "Aquatic / Wetland",
}

_DECIDUOUS_LABELS: dict[str, str] = {
    "deciduous":  "Deciduous",
    "evergreen":  "Evergreen",
    "herbaceous": "Herbaceous (dies back)",
}

_LIFECYCLE_LABELS: dict[str, str] = {
    "perennial": "Perennial",
    "annual":    "Annual",
    "biennial":  "Biennial",
}


# ── Alberta ecoregion choices (Reference Ecosystem picker, N1) ────────────────
# Order matches the dropdown; the empty-string id is "any ecoregion" (no
# filter).  Keep the ids in sync with the comma-separated tags stored in
# plants.ab_ecoregion (see data/plants_master.json + src/db/plants.py
# heuristic tagging pass).
#
# Ecoregion keys are shared across the prairie provinces where the ecoregion is
# the same (Design principle P1/P2 — nature does not respect borders); the SK
# Regina/Saskatoon belt adds the moist_mixedgrass key (V2.14). The constant
# keeps its historical _AB_ name for back-compat; the province-neutral rename
# lands in the Phase B schema refactor.
# Month facets (V2.37). Keys are the 1–12 month numbers `parse_month_range`
# returns, as strings because CheckableComboBox keys travel as strings; the
# search layer coerces them back with int().
_MONTH_LABELS: dict[str, str] = {
    "1": "January", "2": "February", "3": "March", "4": "April",
    "5": "May", "6": "June", "7": "July", "8": "August",
    "9": "September", "10": "October", "11": "November", "12": "December",
}

# The vocabulary itself now lives in the Qt-free src/ecoregion.py (V2.38), so
# the data validator and the range-derivation script can read it without
# importing PyQt6. These keep the historical shape for existing callers.
_ECOREGION_CHOICES: list[tuple[str, str]] = (
    [("Any ecoregion", "")]
    + [(f"{name} ({where})", key) for key, name, where in _ECOREGIONS])
_ECOREGION_DISPLAY: dict[str, tuple[str, str]] = {
    key: (name, where) for key, name, where in _ECOREGIONS}

# Back-compat alias — the constant was province-scoped (_AB_ECOREGION_CHOICES)
# before the V2.15 province-neutral rename. Kept so external imports and the
# data_quality key loader's fallback keep resolving.
_AB_ECOREGION_CHOICES = _ECOREGION_CHOICES
