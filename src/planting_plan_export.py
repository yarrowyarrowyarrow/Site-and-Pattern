"""
planting_plan_export.py — the whole take-it-outside document, in order (V2.31).

F40 shipped the buy-it/plant-it sheet; F43, F41 and F42 fill in the three things
it left out. This module is the one place that decides what the finished document
contains and in what order, so the text export and the PDF cannot drift into
being different documents:

  1. **Site prep** (F43) — what to do to the ground first.
  2. **What to buy** (F40) — species, quantities, forms, prices, by source.
  3. **The planting map key** (F41) — which number is which species, and where
     each one goes, in metres.
  4. **Phased conversion schedule** (F17) — the year-by-year remove/plant order.
  5. **Maintenance** (F42) — the cadence, and how the work falls over time.

Ordered the way the work happens, not the way the modules were written.

Every section is **best-effort**: a section that raises is left out and the rest
of the document still reaches the user. A planting plan that fails to export
because the soil lookup hiccuped would be a worse failure than a plan missing
its soil page.

Qt-free — the PDF exporter draws its own pages from the same builders, and this
module is what the text export writes.
"""

from __future__ import annotations

from typing import Optional


def _section(build) -> str:
    """Run one section builder, swallowing anything it throws."""
    try:
        return build() or ""
    except Exception:                    # noqa: BLE001 — see the module docstring
        return ""


def site_prep_section(project: dict, placed_plants: list,
                      bed_area_m2: float = 0.0) -> str:
    from src.lawn_zones import conversion_summary
    from src.site_prep import build_site_prep, render_prep_text
    site_config = ((project or {}).get("properties") or {}).get(
        "site_config") or {}
    prep = build_site_prep(
        site_config, placed_plants, bed_area_m2=bed_area_m2,
        lawn_summary=conversion_summary((project or {}).get("features", [])))
    return render_prep_text(prep)


def planting_map_section(project: dict, placed_plants: list, plan) -> str:
    from src.planting_map import build_planting_map, render_map_key_text
    return render_map_key_text(
        build_planting_map(placed_plants, project, plan=plan))


def conversion_section(project: dict, placed_plants: list) -> str:
    from src.conversion_plan import (build_conversion_schedule,
                                     render_schedule_text)
    from src.lawn_zones import conversion_summary
    return render_schedule_text(build_conversion_schedule(
        placed_plants,
        summary=conversion_summary((project or {}).get("features", []))))


def maintenance_section(placed_plants: list, structures: list) -> str:
    from src.maintenance_calendar import (build_maintenance_calendar,
                                          render_maintenance_text)
    return render_maintenance_text(
        build_maintenance_calendar(placed_plants, structures))


def assemble(project: dict, placed_plants: list, structures: list, plan,
             *, bed_area_m2: float = 0.0,
             plan_text: Optional[str] = None) -> str:
    """The full document as plain text.

    ``plan`` is a :class:`src.planting_plan.PlantingPlan`; ``plan_text`` lets a
    caller substitute an already-rendered F40 section.
    """
    if plan_text is None:
        from src.planting_plan import render_plan_text
        plan_text = render_plan_text(plan)

    sections = [
        _section(lambda: site_prep_section(project, placed_plants,
                                           bed_area_m2)),
        plan_text,
        _section(lambda: planting_map_section(project, placed_plants, plan)),
        _section(lambda: conversion_section(project, placed_plants)),
        _section(lambda: maintenance_section(placed_plants, structures)),
    ]
    return "\n\n".join(s.rstrip() for s in sections if s.strip()) + "\n"
