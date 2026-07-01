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

Design principle P6 (conventional value metrics miss ecological value) and P8
(repair is more sophisticated than creation — conversion is first-class) — see
docs/DESIGN_PHILOSOPHY.md. The lawn-equivalent counterfactual (F10) lives here too.
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


# A conventional turf-grass lawn supports essentially none of the specialist
# insects and the birds that depend on them (Tallamy, Nature's Best Hope): its
# Habitat Value is ~0 on the same 0–100 scale the design is scored on.
LAWN_HABITAT_SCORE = 0


def lawn_counterfactual(design_score, summary=None) -> dict:
    """The Tallamy contrast (F10): this design's habitat value vs. the ≈0 a
    conventional lawn of the same ground provides.

    ``design_score`` is the design's 0–100 Habitat Value total (a HabitatScore,
    a number, or ``None``). ``summary`` is an optional
    :func:`conversion_summary` result; when it carries a converted/under-
    conversion area, the contrast is grounded in that many m² reclaimed from
    lawn. Returns a dict the GUI / PDF render:

      ``design_score`` (int), ``lawn_score`` (0), ``delta`` (design − lawn),
      ``area_m2`` (lawn ground the contrast is about; 0 when no zones drawn).
    """
    total = getattr(design_score, "total", design_score)
    try:
        total = int(round(total)) if total is not None else 0
    except (TypeError, ValueError):
        total = 0
    area = 0.0
    if summary:
        # The ground this contrast is about: lawn still to convert plus the
        # restoration zones already underway (both were lawn).
        by_stage = summary.get("by_stage") or {}
        area = float(by_stage.get("lawn", 0.0)) + float(by_stage.get("converted", 0.0))
    return {
        "design_score": total,
        "lawn_score": LAWN_HABITAT_SCORE,
        "delta": total - LAWN_HABITAT_SCORE,
        "area_m2": round(area, 1),
    }


def format_lawn_counterfactual(cf: dict) -> list[str]:
    """Render :func:`lawn_counterfactual` as a short side-by-side readout.

    Two-plus lines: the design's score beside the lawn baseline, then the
    Tallamy "why" — and, when an area is known, the ground reclaimed. Returns
    ``[]`` only when handed nothing."""
    if not cf:
        return []
    lines = [
        f"This design: {cf['design_score']} / 100   ·   "
        f"the same area as lawn: ~{cf['lawn_score']} / 100",
        "Conventional turf supports almost none of the specialist insects — "
        "and the birds that feed on them — that native plants do.",
    ]
    if cf.get("area_m2", 0) > 0:
        lines.append(f"You're reclaiming ~{_area_str(cf['area_m2'])} from lawn.")
    return lines


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
