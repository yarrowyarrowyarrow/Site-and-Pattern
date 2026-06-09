"""
src/lawn_zones.py — lawn-to-habitat conversion zones (N2).

A conversion zone is just a drawn ``custom_shape`` whose ``shape_type`` is one of
the zone labels below — so zones reuse the whole existing shape-drawing pipeline
(draw, colour, area, save/load) with no new map JS. This module is the single,
Qt-free source of truth for:

  * the zone catalogue (key → label / fill / stroke / opacity / stage), shared by
    the Structures → Shapes drawer presets and the tally here, so the drawer and
    the readout never drift;
  * ``conversion_summary`` — tallies m² per zone from the project features and
    derives "lawn remaining", "converted so far" and a stage-by-stage breakdown;
  * ``format_conversion_summary`` — a compact human-readable readout.

Zone keys match the brainstorm enum: lawn_remaining, restoration_year_1,
restoration_year_3, established_native, existing_remnant.
"""

from __future__ import annotations

from collections import OrderedDict

# key → display label (also the stored shape_type) + render style + which
# conversion stage it counts toward.
ZONE_TYPES: "OrderedDict[str, dict]" = OrderedDict([
    ("lawn_remaining", {
        "label": "Lawn — to convert",
        "fill": "#cddc39", "stroke": "#9e9d24", "opacity": 0.20,
        "stage": "lawn",
    }),
    ("restoration_year_1", {
        "label": "Restoration — Year 1",
        "fill": "#d7a86e", "stroke": "#8d6e63", "opacity": 0.30,
        "stage": "converted",
    }),
    ("restoration_year_3", {
        "label": "Restoration — Year 3",
        "fill": "#9ccc65", "stroke": "#558b2f", "opacity": 0.30,
        "stage": "converted",
    }),
    ("established_native", {
        "label": "Established native",
        "fill": "#2e7d32", "stroke": "#1b5e20", "opacity": 0.35,
        "stage": "converted",
    }),
    ("existing_remnant", {
        "label": "Existing remnant",
        "fill": "#00695c", "stroke": "#004d40", "opacity": 0.35,
        "stage": "remnant",
    }),
])

# Reverse lookup: stored shape_type label → zone key.
LABEL_TO_KEY = {spec["label"]: key for key, spec in ZONE_TYPES.items()}


def is_zone_label(shape_type: str) -> bool:
    """True if a drawn shape's ``shape_type`` is one of the conversion zones."""
    return shape_type in LABEL_TO_KEY


def zone_key_for(shape_type: str) -> str | None:
    """Zone key for a stored ``shape_type`` label, or None if it isn't a zone."""
    return LABEL_TO_KEY.get(shape_type)


def conversion_summary(features) -> dict:
    """Tally lawn-conversion zones from a project's GeoJSON ``features``.

    Returns a dict with per-zone m² (``by_zone``), the stage breakdown
    (``by_stage`` → lawn / converted / remnant), the headline numbers
    (``lawn_remaining_m2``, ``converted_m2``, ``remnant_m2``,
    ``total_zone_m2``) and ``pct_converted`` (converted ÷ lawn+converted).
    All-zero when no zones are drawn."""
    by_zone = {k: 0.0 for k in ZONE_TYPES}
    for f in features or []:
        props = f.get("properties", {}) if isinstance(f, dict) else {}
        if props.get("element_type") not in ("custom_shape", "canopy_footprint"):
            continue
        key = LABEL_TO_KEY.get(props.get("shape_type"))
        if key is None:
            continue
        by_zone[key] += float(props.get("area_m2") or 0.0)

    lawn = by_zone["lawn_remaining"]
    converted = (by_zone["restoration_year_1"]
                 + by_zone["restoration_year_3"]
                 + by_zone["established_native"])
    remnant = by_zone["existing_remnant"]
    base = lawn + converted
    return {
        "by_zone": by_zone,
        "by_stage": {"lawn": lawn, "converted": converted, "remnant": remnant},
        "lawn_remaining_m2": round(lawn, 1),
        "converted_m2": round(converted, 1),
        "remnant_m2": round(remnant, 1),
        "total_zone_m2": round(lawn + converted + remnant, 1),
        "pct_converted": round(100.0 * converted / base, 1) if base > 0 else 0.0,
    }


def _area_str(m2: float) -> str:
    return f"{m2:,.0f} m²" if m2 < 10000 else f"{m2 / 10000:.2f} ha"


def format_conversion_summary(summary: dict) -> str:
    """Compact multi-line readout, or '' when nothing is drawn."""
    if not summary or summary.get("total_zone_m2", 0) <= 0:
        return ""
    by = summary["by_zone"]
    lines = [
        f"Converted: {_area_str(summary['converted_m2'])} "
        f"({summary['pct_converted']:.0f}% of lawn+restoration); "
        f"lawn left: {_area_str(summary['lawn_remaining_m2'])}."
    ]
    # Stage-by-stage breakdown, only the zones actually present.
    parts = []
    for key, spec in ZONE_TYPES.items():
        if by.get(key, 0) > 0:
            parts.append(f"{spec['label']}: {_area_str(by[key])}")
    if parts:
        lines.append(" · ".join(parts))
    return "\n".join(lines)
