"""
pdf_export.py — Export the current design as a presentation-quality PDF.

Uses QPrinter/QPainter to render the map view, legend, plant list, and
title block into a PDF document. No external PDF libraries required.
"""

from __future__ import annotations

import os
from datetime import datetime
from collections import Counter

from PyQt6.QtCore import Qt, QMarginsF, QRectF, QSizeF
from PyQt6.QtGui import (
    QPainter, QColor, QFont, QPen, QPageLayout, QPageSize,
)
from PyQt6.QtPrintSupport import QPrinter

from src.branding import APP_NAME


def _font(px, bold: bool = False, family: str = "Arial") -> QFont:
    """A font sized in DEVICE PIXELS, not points.

    Every layout figure in this module is ``N * dpi_scale`` — a device-pixel
    measurement, because the page is designed at 96 DPI and scaled up to the
    printer's. Feeding that same number to ``QFont(family, pointSize)`` was a
    category error: a point size is *physical*, so Qt scaled it by the device
    DPI a second time. On a 1200-DPI PDF printer (``dpi_scale`` = 12.5) a
    "9 pt" body font became 112 pt — about 2,100 device pixels tall, drawn into
    a rect 175 pixels high. Qt clipped it, and every text page of the export
    came out blank while the boxes and rules around it drew correctly.

    ``setPixelSize`` takes device pixels, which is exactly what the call sites
    already compute, so the intended 96-DPI design renders at any resolution.
    """
    f = QFont(family)
    f.setPixelSize(max(1, int(px)))
    f.setBold(bold)
    return f


def export_pdf(
    path: str,
    project: dict,
    placed_plants: list[dict],
    structures: list[dict],
    notes: str = "",
    map_pixmap=None,
    still_pixmap=None,
    still_caption: str = "",
) -> None:
    """
    Export the current design to a PDF file.

    Parameters
    ----------
    path : str
        Output file path.
    project : dict
        The full project dict (GeoJSON FeatureCollection).
    placed_plants : list[dict]
        List of placed plant dicts with plant_id, common_name.
    structures : list[dict]
        List of placed structure dicts.
    notes : str
        Design notes text.
    map_pixmap : QPixmap or None
        Screenshot of the current map view (if available).
    still_pixmap : QPixmap or None
        A presentation still rendered by the 3D window (F69), or None. Optional
        because export is synchronous while the viewer's capture is a callback,
        so a caller that has no still simply omits the page.
    still_caption : str
        Caption for that still.
    """
    printer = QPrinter(QPrinter.PrinterMode.HighResolution)
    printer.setOutputFormat(QPrinter.OutputFormat.PdfFormat)
    printer.setOutputFileName(path)
    printer.setPageSize(QPageSize(QPageSize.PageSizeId.Letter))
    printer.setPageMargins(QMarginsF(20, 20, 20, 20), QPageLayout.Unit.Millimeter)

    painter = QPainter()
    if not painter.begin(printer):
        raise RuntimeError(f"Could not open {path} for writing")

    try:
        page_rect = printer.pageRect(QPrinter.Unit.DevicePixel)
        w = page_rect.width()
        h = page_rect.height()
        dpi_scale = printer.resolution() / 96.0

        project_name = project.get("properties", {}).get("project_name", "Untitled Design")
        zone = project.get("properties", {}).get("hardiness_zone")
        created = project.get("properties", {}).get("created", "")

        # ── Page 1: Title + Map ───────────────────────────────────────────
        y = _draw_title_block(painter, w, project_name, zone, created, dpi_scale)

        # Map screenshot
        if map_pixmap and not map_pixmap.isNull():
            map_h = h * 0.55
            scaled = map_pixmap.scaled(
                int(w - 40 * dpi_scale), int(map_h),
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation
            )
            x_offset = (w - scaled.width()) / 2
            painter.drawPixmap(int(x_offset), int(y + 10 * dpi_scale), scaled)
            y += scaled.height() + 20 * dpi_scale
        else:
            # Placeholder
            painter.setPen(QPen(QColor("#546e7a")))
            painter.setFont(_font(10 * dpi_scale))
            painter.drawText(
                QRectF(0, y, w, 30 * dpi_scale),
                Qt.AlignmentFlag.AlignCenter,
                "(Map screenshot not available)"
            )
            y += 40 * dpi_scale

        # Habitat Value Score + whole-design cost for the summary block.
        try:
            from src.habitat_score import compute_habitat_score
            score = compute_habitat_score(placed_plants, structures)
        except Exception:
            score = None
        try:
            from src.sourcing import design_cost
            bed_area = sum(
                float(f.get("properties", {}).get("area_m2") or 0.0)
                for f in project.get("features", [])
                if f.get("properties", {}).get("element_type") == "custom_shape"
            )
            cost = design_cost(placed_plants, structures=structures,
                               mulch_area_m2=bed_area)
        except Exception:
            cost = None

        # Quick summary on page 1
        y = _draw_summary(painter, w, y, placed_plants, structures, dpi_scale,
                          score, cost)

        # ── Presentation still (F69) ──────────────────────────────────────
        # The design as a picture, at the year it has become itself. A map
        # screenshot says where things go; this says what it will look like,
        # and it is the page a client, a spouse or a board actually reads
        # (P13 — a native planting has to be loved to survive). Rendered by
        # the 3D window and passed in, because export is synchronous and the
        # viewer's capture is a callback.
        if still_pixmap is not None and not still_pixmap.isNull():
            printer.newPage()
            _draw_presentation_still(painter, w, h, dpi_scale, still_pixmap,
                                     still_caption)

        # ── Page 2: Site prep (F43) ───────────────────────────────────────
        # Ahead of the buy list on purpose: this is the work that happens
        # first, and a document ordered by module history rather than by the
        # order of the job is a document people read out of order.
        try:
            from src.lawn_zones import conversion_summary
            from src.site_prep import build_site_prep
            prep_bed_area = sum(
                float(f.get("properties", {}).get("area_m2") or 0.0)
                for f in project.get("features", [])
                if f.get("properties", {}).get("element_type") == "custom_shape"
            )
            prep = build_site_prep(
                project.get("properties", {}).get("site_config") or {},
                placed_plants, bed_area_m2=prep_bed_area,
                lawn_summary=conversion_summary(project.get("features", [])))
        except Exception:
            prep = None
        if prep is not None and prep.steps:
            printer.newPage()
            _draw_site_prep(painter, w, h, prep, dpi_scale)

        # ── Page 3: Planting Plan ─────────────────────────────────────────
        # The buy-it / plant-it plan (F40) — quantities, form, spacing, when, and
        # cost, plus a phased schedule. Falls back to the bare plant list if the
        # plan can't be built for any reason.
        printer.newPage()
        try:
            from src.planting_plan import build_planting_plan
            structs = [
                f["properties"]["struct_def"]
                for f in project.get("features", [])
                if f.get("properties", {}).get("element_type") == "structure"
                and f.get("properties", {}).get("struct_def")
            ]
            plan_bed_area = sum(
                float(f.get("properties", {}).get("area_m2") or 0.0)
                for f in project.get("features", [])
                if f.get("properties", {}).get("element_type") == "custom_shape"
            )
            plan = build_planting_plan(placed_plants, structures=structs,
                                       bed_area_m2=plan_bed_area)
        except Exception:
            plan = None
        if plan is not None:
            _draw_planting_plan(painter, w, h, plan, dpi_scale)
        else:
            _draw_plant_list(painter, w, h, placed_plants, dpi_scale)

        # ── Page 4: The numbered planting map (F41) ───────────────────────
        # A scale drawing, not the satellite capture on page 1: this is the
        # page that goes outside with a tape measure.
        try:
            from src.planting_map import build_planting_map
            pmap = build_planting_map(placed_plants, project, plan=plan)
        except Exception:
            pmap = None
        if pmap is not None and pmap.placements:
            printer.newPage()
            _draw_planting_map(painter, w, h, pmap, dpi_scale)
        elif placed_plants:
            # Silently dropping the page taught the user nothing: they asked for
            # a planting map, got a PDF without one, and had no way to tell
            # whether the feature existed. Say why (V2.37).
            printer.newPage()
            _draw_missing_map_note(painter, w, h, dpi_scale, project)

        # ── Page 5: Phased conversion schedule (F17) ──────────────────────
        # Year-by-year "remove this / plant that, when" — only when there is a
        # design (or drawn lawn zones) to schedule.
        try:
            from src.conversion_plan import build_conversion_schedule
            from src.lawn_zones import conversion_summary
            schedule = build_conversion_schedule(
                placed_plants, summary=conversion_summary(project.get("features", [])))
        except Exception:
            schedule = None
        if schedule is not None and (placed_plants or schedule.has_zones):
            printer.newPage()
            _draw_conversion_schedule(painter, w, h, schedule, dpi_scale)

        # ── Page 6: Maintenance calendar (F42) ────────────────────────────
        try:
            from src.maintenance_calendar import build_maintenance_calendar
            structs_for_cal = [
                f["properties"]["struct_def"]
                for f in project.get("features", [])
                if f.get("properties", {}).get("element_type") == "structure"
                and f.get("properties", {}).get("struct_def")
            ]
            cal = build_maintenance_calendar(placed_plants, structs_for_cal)
        except Exception:
            cal = None
        if cal is not None and placed_plants:
            printer.newPage()
            _draw_maintenance(painter, w, h, cal, dpi_scale)

        # ── Page 7: Notes (if any) ────────────────────────────────────────
        if notes.strip():
            printer.newPage()
            _draw_notes_page(painter, w, h, notes, dpi_scale)

    finally:
        painter.end()


def _draw_title_block(painter: QPainter, w: float, name: str,
                      zone, created: str, s: float) -> float:
    """Draw the title block at the top. Returns the Y position after."""
    # Background bar
    painter.fillRect(QRectF(0, 0, w, 60 * s), QColor("#1b3a1b"))

    # Title
    painter.setPen(QColor("#a5d6a7"))
    painter.setFont(_font(18 * s, bold=True))
    painter.drawText(QRectF(15 * s, 8 * s, w - 30 * s, 30 * s),
                     Qt.AlignmentFlag.AlignLeft, f"{APP_NAME} — {name}")

    # Subtitle
    painter.setFont(_font(9 * s))
    painter.setPen(QColor("#78909c"))
    zone_str = f"Zone {zone}" if zone else "Zone: —"
    date_str = datetime.now().strftime("%Y-%m-%d")
    painter.drawText(
        QRectF(15 * s, 38 * s, w - 30 * s, 20 * s),
        Qt.AlignmentFlag.AlignLeft,
        f"{zone_str}  |  Exported: {date_str}  |  Edmonton, Alberta"
    )

    return 65 * s


def _draw_summary(painter: QPainter, w: float, y: float,
                  plants: list[dict], structures: list[dict], s: float,
                  score=None, cost=None) -> float:
    """Draw a quick design summary (counts + habitat score + cost)."""
    painter.setPen(QColor("#a5d6a7"))
    painter.setFont(_font(12 * s, bold=True))
    painter.drawText(QRectF(15 * s, y, w, 20 * s),
                     Qt.AlignmentFlag.AlignLeft, "Design Summary")
    y += 22 * s

    painter.setFont(_font(9 * s))
    painter.setPen(QColor("#c8e6c9"))

    # Count by type
    type_counts: Counter = Counter()
    species = set()
    for p in plants:
        type_counts[p.get("plant_type", "herb")] += 1
        species.add(p.get("common_name", "?"))

    lines = [
        f"Total plants: {len(plants)} ({len(species)} species)",
    ]
    type_parts = []
    for t in ["tree", "shrub", "herb", "groundcover", "vine", "root"]:
        if type_counts.get(t, 0) > 0:
            type_parts.append(f"{type_counts[t]} {t}s")
    if type_parts:
        lines.append("  " + ", ".join(type_parts))
    if structures:
        lines.append(f"Structures: {len(structures)}")
    if score is not None:
        lines.append(
            f"Habitat Value Score: {score.total}/100  (grade {score.grade})"
        )
        lines.append(
            f"  {int(round(score.native_ratio * 100))}% native · "
            f"{len(score.keystone_species)} keystone · "
            f"{len(score.layers_present)} vegetation layers"
        )
    if cost is not None:
        try:
            from src.sourcing import format_cost
            lines.append(
                f"Estimated cost: {format_cost(*cost['total'])}  (AB estimate)"
            )
        except Exception:
            pass
    if score is not None and cost is not None:
        # Value vs. price framing (F11, P6): the price doesn't capture the value.
        lines.append(
            "Value vs. price: a one-time cost that creates lasting ecological value."
        )

    for line in lines:
        painter.drawText(QRectF(20 * s, y, w - 40 * s, 14 * s),
                         Qt.AlignmentFlag.AlignLeft, line)
        y += 14 * s

    return y + 5 * s


def _draw_plant_list(painter: QPainter, w: float, h: float,
                     plants: list[dict], s: float) -> float:
    """Draw a detailed plant list table. Returns final Y."""
    # Title
    painter.fillRect(QRectF(0, 0, w, 35 * s), QColor("#1b3a1b"))
    painter.setPen(QColor("#a5d6a7"))
    painter.setFont(_font(14 * s, bold=True))
    painter.drawText(QRectF(15 * s, 8 * s, w, 25 * s),
                     Qt.AlignmentFlag.AlignLeft, "Plant List")

    y = 45 * s

    # Count plants
    counts: Counter = Counter()
    names: dict[int, str] = {}
    types: dict[int, str] = {}
    for p in plants:
        pid = p.get("plant_id", 0)
        counts[pid] += 1
        names[pid] = p.get("common_name", "?")
        types[pid] = p.get("plant_type", "herb")

    # Enrich with DB data
    try:
        from src.db.plants import get_plant
    except Exception:
        get_plant = lambda pid: None

    # Table header
    painter.setFont(_font(8 * s, bold=True))
    painter.setPen(QColor("#a5d6a7"))
    col_x = [15 * s, 200 * s, 350 * s, 430 * s, 510 * s]
    headers = ["Plant", "Scientific Name", "Type", "Qty", "Water"]
    for i, header in enumerate(headers):
        if i < len(col_x):
            painter.drawText(QRectF(col_x[i], y, 180 * s, 14 * s),
                             Qt.AlignmentFlag.AlignLeft, header)
    y += 16 * s

    # Divider
    painter.setPen(QPen(QColor("#2e4a2e"), 1))
    painter.drawLine(int(15 * s), int(y), int(w - 15 * s), int(y))
    y += 4 * s

    # Rows
    painter.setFont(_font(8 * s))
    painter.setPen(QColor("#c8e6c9"))

    sorted_pids = sorted(counts.keys(), key=lambda pid: names.get(pid, ""))
    for pid in sorted_pids:
        if y > h - 40 * s:
            break  # Don't overflow page

        plant = get_plant(pid) if pid else None
        name = names.get(pid, "?")
        sci = (plant or {}).get("scientific_name", "") or ""
        ptype = (plant or {}).get("plant_type", types.get(pid, "")) or ""
        # water_needs may be comma-delimited (V1.84); render each value titled.
        from src.plant_conditions import condition_tokens
        water = ", ".join(t.replace("_", " ").title()
                          for t in condition_tokens((plant or {}).get("water_needs")))
        qty = str(counts[pid])

        values = [name, sci, ptype.title(), qty, water]
        for i, val in enumerate(values):
            if i < len(col_x):
                painter.drawText(QRectF(col_x[i], y, 180 * s, 14 * s),
                                 Qt.AlignmentFlag.AlignLeft, val)
        y += 14 * s

    # Alberta native sourcing footer (mirrors the plant-order export).
    if y < h - 50 * s:
        y += 14 * s
        painter.setFont(_font(7 * s, bold=True))
        painter.setPen(QColor("#a5d6a7"))
        painter.drawText(QRectF(15 * s, y, w - 30 * s, 12 * s),
                         Qt.AlignmentFlag.AlignLeft,
                         "Alberta native plant / seed sources")
        y += 13 * s
        painter.setFont(_font(7 * s))
        painter.setPen(QColor("#78909c"))
        for src_line in (
            "ALCLA Native Plants · Bow Valley Habitat Development",
            "Wild About Flowers · Bedrock Seed Bank",
        ):
            painter.drawText(QRectF(15 * s, y, w - 30 * s, 12 * s),
                             Qt.AlignmentFlag.AlignLeft, src_line)
            y += 12 * s

    return y


def _wrap(text: str, width: int) -> list[str]:
    """Greedy word-wrap to ``width`` characters (for the phased summary)."""
    out: list[str] = []
    cur = ""
    for word in text.split(" "):
        if cur and len(cur) + 1 + len(word) > width:
            out.append(cur)
            cur = word
        else:
            cur = word if not cur else f"{cur} {word}"
    if cur:
        out.append(cur)
    return out


def _draw_planting_plan(painter: QPainter, w: float, h: float, plan, s: float) -> float:
    """Draw the buy-it / plant-it Planting Plan page (F40): species grouped by
    nursery source with form / qty / spacing / when / price, then a phased
    planting schedule and the nursery footer. Returns final Y."""
    from src.sourcing import format_cost
    from src.planting_plan import PHASES, NURSERIES

    # Title bar
    painter.fillRect(QRectF(0, 0, w, 35 * s), QColor("#1b3a1b"))
    painter.setPen(QColor("#a5d6a7"))
    painter.setFont(_font(14 * s, bold=True))
    painter.drawText(QRectF(15 * s, 8 * s, w, 25 * s),
                     Qt.AlignmentFlag.AlignLeft, "Planting Plan")

    y = 45 * s
    # 'When' carries a phrase ('Late spring, after the last frost'), so it
    # gets the slack the narrow Price column was hoarding.
    col_x = [15 * s, 195 * s, 275 * s, 315 * s, 375 * s, 570 * s]
    headers = ["Species", "Form", "Qty", "Space", "When", "Price"]
    sections = [
        ("native_woody", "Native trees & shrubs"),
        ("native_herb", "Native herbaceous & groundcover"),
        ("cultivated", "Cultivated / non-native"),
    ]

    for bucket, label in sections:
        items = plan.items_by_source(bucket)
        if not items or y > h - 60 * s:
            continue
        painter.setFont(_font(9 * s, bold=True))
        painter.setPen(QColor("#a5d6a7"))
        painter.drawText(QRectF(15 * s, y, w - 30 * s, 14 * s),
                         Qt.AlignmentFlag.AlignLeft, label)
        y += 15 * s

        painter.setFont(_font(7 * s, bold=True))
        painter.setPen(QColor("#78909c"))
        for i, head in enumerate(headers):
            painter.drawText(QRectF(col_x[i], y, 120 * s, 12 * s),
                             Qt.AlignmentFlag.AlignLeft, head)
        y += 11 * s
        painter.setPen(QPen(QColor("#2e4a2e"), 1))
        painter.drawLine(int(15 * s), int(y), int(w - 15 * s), int(y))
        y += 4 * s

        painter.setFont(_font(7 * s))
        painter.setPen(QColor("#c8e6c9"))
        for it in items:
            if y > h - 40 * s:
                break
            vals = [
                it.common_name,
                it.form,
                str(it.qty),
                f"{it.spacing_m:g} m",
                it.planting_window,
                format_cost(it.ext_low, it.ext_high),
            ]
            for i, val in enumerate(vals):
                cw = (col_x[i + 1] - col_x[i] - 4 * s) if i + 1 < len(col_x) else 120 * s
                painter.drawText(QRectF(col_x[i], y, max(40 * s, cw), 12 * s),
                                 Qt.AlignmentFlag.AlignLeft, val)
            y += 11 * s
        y += 8 * s

    # Phased planting schedule
    if y < h - 90 * s:
        painter.setFont(_font(9 * s, bold=True))
        painter.setPen(QColor("#a5d6a7"))
        painter.drawText(QRectF(15 * s, y, w - 30 * s, 14 * s),
                         Qt.AlignmentFlag.AlignLeft,
                         "Phased planting (work top to bottom)")
        y += 15 * s
        for phase, season in PHASES:
            pit = plan.items_by_phase(phase)
            if not pit or y > h - 40 * s:
                continue
            painter.setFont(_font(7 * s, bold=True))
            painter.setPen(QColor("#a5d6a7"))
            painter.drawText(QRectF(15 * s, y, w - 30 * s, 12 * s),
                             Qt.AlignmentFlag.AlignLeft, f"{phase}  ·  {season}")
            y += 11 * s
            painter.setFont(_font(7 * s))
            painter.setPen(QColor("#c8e6c9"))
            names = ", ".join(f"{it.common_name} ×{it.qty}" for it in pit)
            for line in _wrap(names, 95):
                if y > h - 30 * s:
                    break
                painter.drawText(QRectF(25 * s, y, w - 45 * s, 12 * s),
                                 Qt.AlignmentFlag.AlignLeft, line)
                y += 11 * s
            y += 3 * s

    # Alberta native sourcing footer
    if y < h - 45 * s:
        y += 6 * s
        painter.setFont(_font(7 * s, bold=True))
        painter.setPen(QColor("#a5d6a7"))
        painter.drawText(QRectF(15 * s, y, w - 30 * s, 12 * s),
                         Qt.AlignmentFlag.AlignLeft,
                         "Alberta native plant / seed sources")
        y += 12 * s
        painter.setFont(_font(7 * s))
        painter.setPen(QColor("#78909c"))
        for nm, url in NURSERIES:
            if y > h - 20 * s:
                break
            painter.drawText(QRectF(15 * s, y, w - 30 * s, 12 * s),
                             Qt.AlignmentFlag.AlignLeft, f"{nm} · {url}")
            y += 11 * s

    return y


def _draw_conversion_schedule(painter: QPainter, w: float, h: float,
                              schedule, s: float) -> float:
    """Draw the year-by-year phased conversion schedule page (F17): each
    restoration band as a heading with its tasks. Returns final Y."""
    # Title bar
    painter.fillRect(QRectF(0, 0, w, 35 * s), QColor("#1b3a1b"))
    painter.setPen(QColor("#a5d6a7"))
    painter.setFont(_font(14 * s, bold=True))
    painter.drawText(QRectF(15 * s, 8 * s, w, 25 * s),
                     Qt.AlignmentFlag.AlignLeft, "Phased Conversion")

    y = 45 * s
    if schedule.has_zones:
        from src.conversion_plan import _area_str
        sub = f"Converting ~{_area_str(schedule.target_m2)} of lawn to habitat"
        if schedule.converted_m2 > 0:
            sub += f" ({_area_str(schedule.converted_m2)} already underway)"
        painter.setFont(_font(8 * s))
        painter.setPen(QColor("#90a4ae"))
        painter.drawText(QRectF(15 * s, y, w - 30 * s, 12 * s),
                         Qt.AlignmentFlag.AlignLeft, sub + ".")
        y += 16 * s

    for st in schedule.stages:
        if y > h - 50 * s:
            break
        painter.setFont(_font(9 * s, bold=True))
        painter.setPen(QColor("#a5d6a7"))
        painter.drawText(QRectF(15 * s, y, w - 30 * s, 14 * s),
                         Qt.AlignmentFlag.AlignLeft, f"{st.year_label} · {st.stage}")
        y += 14 * s
        painter.setFont(_font(7 * s))
        painter.setPen(QColor("#c8e6c9"))
        for task in st.tasks:
            for i, line in enumerate(_wrap(task, 95)):
                if y > h - 30 * s:
                    break
                prefix = "•  " if i == 0 else "   "
                painter.drawText(QRectF(25 * s, y, w - 45 * s, 12 * s),
                                 Qt.AlignmentFlag.AlignLeft, prefix + line)
                y += 10 * s
        y += 6 * s

    return y


def _draw_notes_page(painter: QPainter, w: float, h: float,
                     notes: str, s: float):
    """Draw the design notes page."""
    painter.fillRect(QRectF(0, 0, w, 35 * s), QColor("#1b3a1b"))
    painter.setPen(QColor("#a5d6a7"))
    painter.setFont(_font(14 * s, bold=True))
    painter.drawText(QRectF(15 * s, 8 * s, w, 25 * s),
                     Qt.AlignmentFlag.AlignLeft, "Design Notes")

    y = 45 * s
    painter.setFont(_font(8 * s, family="Consolas"))
    painter.setPen(QColor("#c8e6c9"))

    for line in notes.split("\n"):
        if y > h - 30 * s:
            break
        painter.drawText(QRectF(15 * s, y, w - 30 * s, 14 * s),
                         Qt.AlignmentFlag.AlignLeft, line)
        y += 12 * s


# ── Site prep (F43) ─────────────────────────────────────────────────────────

def _page_title(painter: QPainter, w: float, s: float, title: str,
                subtitle: str = "") -> float:
    """Shared page header. Returns the Y to start the body at."""
    painter.fillRect(QRectF(0, 0, w, 35 * s), QColor("#1b3a1b"))
    painter.setPen(QColor("#a5d6a7"))
    painter.setFont(_font(14 * s, bold=True))
    painter.drawText(QRectF(15 * s, 8 * s, w, 25 * s),
                     Qt.AlignmentFlag.AlignLeft, title)
    if subtitle:
        painter.setFont(_font(8 * s))
        painter.drawText(QRectF(15 * s, 8 * s, w - 30 * s, 25 * s),
                         Qt.AlignmentFlag.AlignRight, subtitle)
    return 48 * s


def _draw_presentation_still(painter, w, h, s, pixmap, caption):
    """A full-page render of the design, with its caption underneath."""
    y = _page_title(painter, w, s, "What it will look like",
                    caption.split(".")[0][:90] if caption else "")
    avail_h = h - y - 70 * s
    scaled = pixmap.scaled(
        int(w), int(avail_h),
        Qt.AspectRatioMode.KeepAspectRatio,
        Qt.TransformationMode.SmoothTransformation)
    painter.drawPixmap(int((w - scaled.width()) / 2), int(y), scaled)
    y += scaled.height() + 14 * s
    if caption:
        painter.setPen(QPen(QColor("#37474f")))
        painter.setFont(_font(9 * s))
        for line in _wrap(caption, 105)[:4]:
            painter.drawText(QRectF(0, y, w, 14 * s),
                             Qt.AlignmentFlag.AlignLeft, line)
            y += 13 * s


def _draw_missing_map_note(painter, w, h, s, project) -> None:
    """Say why the planting map is absent instead of dropping the page.

    The map is a scale drawing, so it needs a property boundary to be drawn to
    scale *within*. Without one there is nothing to measure from — but that is a
    thing the user can fix in about thirty seconds, and they can only fix it if
    someone tells them.
    """
    y = _page_title(painter, w, s, "Planting map — not drawn")
    has_boundary = any(
        (f.get("properties") or {}).get("element_type") == "property_boundary"
        for f in (project.get("features") or []))
    reason = ("This design has plants but no property boundary, and the "
              "planting map is a scale drawing — it needs the property outline "
              "to measure from."
              if not has_boundary else
              "The planting map could not be built for this design.")
    painter.setPen(QColor("#333333"))
    painter.setFont(_font(9.5 * s))
    for line in _wrap(reason, 95):
        painter.drawText(QRectF(15 * s, y, w - 30 * s, 15 * s),
                         Qt.AlignmentFlag.AlignLeft, line)
        y += 15 * s
    if not has_boundary:
        y += 8 * s
        painter.setFont(_font(9 * s))
        painter.setPen(QColor("#2e7d32"))
        painter.drawText(
            QRectF(15 * s, y, w - 30 * s, 15 * s), Qt.AlignmentFlag.AlignLeft,
            "To get it: draw your property boundary on the map, then export "
            "again.")


def _draw_site_prep(painter: QPainter, w: float, h: float, prep, s: float) -> float:
    """Do-this-first page (F43): the soil reading, the numbered prep steps, and
    an explicit statement of how much the soil figures can be trusted."""
    y = _page_title(painter, w, s, "Site Prep — do this first")

    painter.setPen(QColor("#333333"))
    painter.setFont(_font(9 * s))
    head = f"Soil: {prep.soil_line}"
    if prep.ph_line:
        head += f"   ·   {prep.ph_line}"
    if prep.lawn_line:
        head += f"   ·   {prep.lawn_line}"
    painter.drawText(QRectF(15 * s, y, w - 30 * s, 14 * s),
                     Qt.AlignmentFlag.AlignLeft, head)
    y += 18 * s
    if prep.mulch_m3_low:
        painter.drawText(
            QRectF(15 * s, y, w - 30 * s, 14 * s), Qt.AlignmentFlag.AlignLeft,
            f"Mulch to buy: {prep.mulch_m3_low:.1f}–{prep.mulch_m3_high:.1f} m³ "
            f"of wood chip")
        y += 18 * s
    y += 4 * s

    for step in prep.steps:
        if y > h - 70 * s:
            break
        painter.setPen(QColor("#1b5e20"))
        painter.setFont(_font(10 * s, bold=True))
        painter.drawText(QRectF(15 * s, y, w - 30 * s, 14 * s),
                         Qt.AlignmentFlag.AlignLeft,
                         f"{step.order}.  {step.title}")
        y += 14 * s
        painter.setPen(QColor("#333333"))
        painter.setFont(_font(8.5 * s))
        for line in _wrap(step.detail, 96):
            if y > h - 60 * s:
                break
            painter.drawText(QRectF(28 * s, y, w - 45 * s, 12 * s),
                             Qt.AlignmentFlag.AlignLeft, line)
            y += 11 * s
        if step.when:
            painter.setPen(QColor("#666666"))
            painter.drawText(QRectF(28 * s, y, w - 45 * s, 12 * s),
                             Qt.AlignmentFlag.AlignLeft, f"When: {step.when}")
            y += 11 * s
        y += 6 * s

    # The honesty block gets its own tinted box — it is the part a user is most
    # likely to skip and most likely to need (P9).
    if prep.caveats and y < h - 40 * s:
        box_top = y
        painter.setPen(QColor("#333333"))
        painter.setFont(_font(8 * s))
        lines = []
        for caveat in prep.caveats:
            lines.extend(_wrap(caveat, 104))
            lines.append("")
        box_h = min((len(lines) + 2) * 10 * s, h - box_top - 15 * s)
        painter.fillRect(QRectF(15 * s, box_top, w - 30 * s, box_h),
                         QColor("#fff8e1"))
        yy = box_top + 8 * s
        painter.setPen(QColor("#5d4037"))
        painter.setFont(_font(8.5 * s, bold=True))
        painter.drawText(QRectF(22 * s, yy, w - 44 * s, 12 * s),
                         Qt.AlignmentFlag.AlignLeft, "How sure is this?")
        yy += 12 * s
        painter.setFont(_font(8 * s))
        for line in lines:
            if yy > box_top + box_h - 8 * s:
                break
            painter.drawText(QRectF(22 * s, yy, w - 44 * s, 11 * s),
                             Qt.AlignmentFlag.AlignLeft, line)
            yy += 10 * s
        y = box_top + box_h + 10 * s
    return y


# ── The numbered planting map (F41) ─────────────────────────────────────────

def _draw_planting_map(painter: QPainter, w: float, h: float, pmap,
                       s: float) -> float:
    """A scale plan drawing with numbered positions and a key.

    Deliberately a drawing rather than the page-1 satellite capture: this is the
    page that goes outside. Numbers key straight to the buy list on the Planting
    Plan page — every plant of one species carries the same number.
    """
    y = _page_title(painter, w, s, "Planting Map",
                    pmap.north_note)

    # Frame: fit the plot into the upper ~55% of the page, preserving aspect.
    frame_x, frame_y = 20 * s, y
    frame_w = w - 40 * s
    frame_h = h * 0.52
    plot_w = max(pmap.width_m, 0.001)
    plot_h = max(pmap.height_m, 0.001)
    scale = min(frame_w / plot_w, frame_h / plot_h)     # page units per metre
    draw_w, draw_h = plot_w * scale, plot_h * scale
    ox = frame_x + (frame_w - draw_w) / 2.0
    oy = frame_y + draw_h                                # y grows downward

    def to_page(x_m, y_m):
        return (ox + x_m * scale, oy - y_m * scale)

    painter.fillRect(QRectF(ox, frame_y, draw_w, draw_h), QColor("#fbfdf9"))

    # Boundary.
    if len(pmap.boundary) >= 3:
        painter.setPen(QPen(QColor("#2e7d32"), max(1.0, 1.5 * s)))
        prev = None
        for pt in pmap.boundary:
            cur = to_page(*pt)
            if prev is not None:
                painter.drawLine(int(prev[0]), int(prev[1]),
                                 int(cur[0]), int(cur[1]))
            prev = cur

    # Numbered positions. Radius is fixed on the page, not scaled with the
    # plot — a legible marker matters more than a true-to-scale dot.
    r = max(4.0, 7 * s)
    painter.setFont(_font(7 * s, bold=True))
    for mp in pmap.placements:
        cx, cy = to_page(mp.x_m, mp.y_m)
        painter.setPen(QPen(QColor("#33691e"), max(1.0, 1.0 * s)))
        painter.setBrush(QColor("#dcedc8"))
        painter.drawEllipse(QRectF(cx - r, cy - r, r * 2, r * 2))
        painter.setPen(QColor("#1b5e20"))
        painter.drawText(QRectF(cx - r, cy - r, r * 2, r * 2),
                         Qt.AlignmentFlag.AlignCenter, str(mp.number))
    painter.setBrush(Qt.BrushStyle.NoBrush)

    # Scale bar + north arrow — what makes this usable with a tape measure.
    bar_m = pmap.scale_bar_m()
    bar_px = bar_m * scale
    bar_y = frame_y + draw_h + 12 * s
    painter.setPen(QPen(QColor("#333333"), max(1.0, 1.2 * s)))
    painter.drawLine(int(ox), int(bar_y), int(ox + bar_px), int(bar_y))
    painter.drawLine(int(ox), int(bar_y - 4 * s), int(ox), int(bar_y + 4 * s))
    painter.drawLine(int(ox + bar_px), int(bar_y - 4 * s),
                     int(ox + bar_px), int(bar_y + 4 * s))
    painter.setFont(_font(8 * s))
    painter.drawText(QRectF(ox, bar_y + 5 * s, bar_px, 12 * s),
                     Qt.AlignmentFlag.AlignCenter, f"{bar_m} m")

    nx = ox + draw_w - 14 * s
    painter.drawLine(int(nx), int(bar_y + 2 * s), int(nx), int(bar_y - 12 * s))
    painter.drawLine(int(nx), int(bar_y - 12 * s),
                     int(nx - 3 * s), int(bar_y - 7 * s))
    painter.drawLine(int(nx), int(bar_y - 12 * s),
                     int(nx + 3 * s), int(bar_y - 7 * s))
    painter.drawText(QRectF(nx - 10 * s, bar_y + 5 * s, 20 * s, 12 * s),
                     Qt.AlignmentFlag.AlignCenter, "N")

    # Key — two columns so a 20-species design still fits one page.
    y = bar_y + 24 * s
    painter.setPen(QColor("#1b5e20"))
    painter.setFont(_font(10 * s, bold=True))
    painter.drawText(QRectF(15 * s, y, w - 30 * s, 14 * s),
                     Qt.AlignmentFlag.AlignLeft, "Key")
    y += 16 * s
    painter.setPen(QColor("#333333"))
    painter.setFont(_font(8 * s))
    col_w = (w - 30 * s) / 2.0
    rows_per_col = max(1, int((h - y - 20 * s) / (11 * s)))
    for i, entry in enumerate(pmap.key):
        col, row = divmod(i, rows_per_col)
        if col > 1:
            break
        ky = y + row * 11 * s
        text = (f"{entry.number}.  {entry.common_name}  "
                f"×{entry.qty}"
                + (f"  ·  {entry.spacing_m:.1f} m apart"
                   if entry.spacing_m else ""))
        painter.drawText(QRectF(15 * s + col * col_w, ky, col_w - 10 * s,
                                11 * s),
                         Qt.AlignmentFlag.AlignLeft, text)
    return h


# ── Maintenance calendar (F42) ──────────────────────────────────────────────

def _draw_maintenance(painter: QPainter, w: float, h: float, cal,
                      s: float) -> float:
    """Year-by-year cadence, with the hours falling as the natives establish."""
    y = _page_title(painter, w, s, "Maintenance — year by year")

    for band in cal.bands:
        if y > h - 70 * s:
            break
        painter.setPen(QColor("#1b5e20"))
        painter.setFont(_font(10 * s, bold=True))
        painter.drawText(QRectF(15 * s, y, w - 30 * s, 14 * s),
                         Qt.AlignmentFlag.AlignLeft,
                         f"{band.label} — {band.headline}")
        painter.setPen(QColor("#666666"))
        painter.setFont(_font(8 * s))
        painter.drawText(
            QRectF(15 * s, y, w - 30 * s, 14 * s),
            Qt.AlignmentFlag.AlignRight,
            f"{band.hours_low:.0f}–{band.hours_high:.0f} h/yr  ·  {band.stage}")
        y += 15 * s
        painter.setPen(QColor("#333333"))
        painter.setFont(_font(8.5 * s))
        for task in band.tasks:
            for i, line in enumerate(_wrap(task, 100)):
                if y > h - 60 * s:
                    break
                painter.drawText(
                    QRectF(24 * s, y, w - 40 * s, 12 * s),
                    Qt.AlignmentFlag.AlignLeft,
                    ("•  " if i == 0 else "    ") + line)
                y += 10.5 * s
        y += 6 * s

    # The spring-cut-back note, boxed, because it is the instruction most often
    # got backwards and the one that costs the most habitat when it is.
    if y < h - 50 * s:
        lines = _wrap(cal.overwintering_note, 104)
        if cal.overwintering_species:
            shown = ", ".join(cal.overwintering_species[:8])
            lines.append("")
            lines.extend(_wrap(
                f"In this design, documented nesting or cover: {shown}.", 104))
        box_h = min((len(lines) + 2) * 10.5 * s, h - y - 15 * s)
        painter.fillRect(QRectF(15 * s, y, w - 30 * s, box_h),
                         QColor("#e8f5e9"))
        yy = y + 8 * s
        painter.setPen(QColor("#1b5e20"))
        painter.setFont(_font(9 * s, bold=True))
        painter.drawText(QRectF(22 * s, yy, w - 44 * s, 12 * s),
                         Qt.AlignmentFlag.AlignLeft,
                         "Cut back in spring, not fall")
        yy += 13 * s
        painter.setPen(QColor("#333333"))
        painter.setFont(_font(8 * s))
        for line in lines:
            if yy > y + box_h - 8 * s:
                break
            painter.drawText(QRectF(22 * s, yy, w - 44 * s, 11 * s),
                             Qt.AlignmentFlag.AlignLeft, line)
            yy += 10 * s
        y += box_h + 8 * s
    return y
