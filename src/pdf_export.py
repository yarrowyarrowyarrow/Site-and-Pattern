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


def _safe_size(n) -> int:
    """Clamp a computed font size to a minimum of 1.

    Qt prints ``QFont::setPointSize: Point size <= 0 (-1), must be
    greater than 0`` (and ignores the call) whenever a non-positive
    size lands in QFont. With a low ``dpi_scale`` the ``int(N * scale)``
    expressions below can collapse to 0; clamping to 1 keeps Qt quiet
    without hiding genuine bugs (there are no callers that *want* a
    sub-1 pt font).
    """
    return max(1, int(n))


def export_pdf(
    path: str,
    project: dict,
    placed_plants: list[dict],
    structures: list[dict],
    notes: str = "",
    map_pixmap=None,
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
            painter.setFont(QFont("Arial", _safe_size(10 * dpi_scale)))
            painter.drawText(
                QRectF(0, y, w, 30 * dpi_scale),
                Qt.AlignmentFlag.AlignCenter,
                "(Map screenshot not available)"
            )
            y += 40 * dpi_scale

        # Quick summary on page 1
        y = _draw_summary(painter, w, y, placed_plants, structures, dpi_scale)

        # ── Page 2: Plant List ────────────────────────────────────────────
        printer.newPage()
        y = _draw_plant_list(painter, w, h, placed_plants, dpi_scale)

        # ── Page 3: Notes (if any) ────────────────────────────────────────
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
    painter.setFont(QFont("Arial", _safe_size(18 * s), QFont.Weight.Bold))
    painter.drawText(QRectF(15 * s, 8 * s, w - 30 * s, 30 * s),
                     Qt.AlignmentFlag.AlignLeft, f"PermaDesign — {name}")

    # Subtitle
    painter.setFont(QFont("Arial", _safe_size(9 * s)))
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
                  plants: list[dict], structures: list[dict], s: float) -> float:
    """Draw a quick design summary."""
    painter.setPen(QColor("#a5d6a7"))
    painter.setFont(QFont("Arial", _safe_size(12 * s), QFont.Weight.Bold))
    painter.drawText(QRectF(15 * s, y, w, 20 * s),
                     Qt.AlignmentFlag.AlignLeft, "Design Summary")
    y += 22 * s

    painter.setFont(QFont("Arial", _safe_size(9 * s)))
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
    painter.setFont(QFont("Arial", _safe_size(14 * s), QFont.Weight.Bold))
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
    painter.setFont(QFont("Arial", _safe_size(8 * s), QFont.Weight.Bold))
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
    painter.setFont(QFont("Arial", _safe_size(8 * s)))
    painter.setPen(QColor("#c8e6c9"))

    sorted_pids = sorted(counts.keys(), key=lambda pid: names.get(pid, ""))
    for pid in sorted_pids:
        if y > h - 40 * s:
            break  # Don't overflow page

        plant = get_plant(pid) if pid else None
        name = names.get(pid, "?")
        sci = (plant or {}).get("scientific_name", "") or ""
        ptype = (plant or {}).get("plant_type", types.get(pid, "")) or ""
        water = (plant or {}).get("water_needs", "") or ""
        qty = str(counts[pid])

        values = [name, sci, ptype.title(), qty, water.title()]
        for i, val in enumerate(values):
            if i < len(col_x):
                painter.drawText(QRectF(col_x[i], y, 180 * s, 14 * s),
                                 Qt.AlignmentFlag.AlignLeft, val)
        y += 14 * s

    return y


def _draw_notes_page(painter: QPainter, w: float, h: float,
                     notes: str, s: float):
    """Draw the design notes page."""
    painter.fillRect(QRectF(0, 0, w, 35 * s), QColor("#1b3a1b"))
    painter.setPen(QColor("#a5d6a7"))
    painter.setFont(QFont("Arial", _safe_size(14 * s), QFont.Weight.Bold))
    painter.drawText(QRectF(15 * s, 8 * s, w, 25 * s),
                     Qt.AlignmentFlag.AlignLeft, "Design Notes")

    y = 45 * s
    painter.setFont(QFont("Consolas", _safe_size(8 * s)))
    painter.setPen(QColor("#c8e6c9"))

    for line in notes.split("\n"):
        if y > h - 30 * s:
            break
        painter.drawText(QRectF(15 * s, y, w - 30 * s, 14 * s),
                         Qt.AlignmentFlag.AlignLeft, line)
        y += 12 * s
