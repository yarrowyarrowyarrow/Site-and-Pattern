"""
water_flow.py — map-side glue for the water flow & accumulation overlay (V2.13).

Free functions taking ``main`` (the MainWindow), in the wind_flow /
building_flow mould: the terrain controller is at its line ceiling
(tests/test_architecture_guard.py), so the water-overlay rendering +
project persistence live here. The actual hydrology (D8 routing,
accumulation, raster/arrows) is in the Qt-free src/hydrology.py; the
compute runs inside terrain.generate_terrain on the terrain worker thread.
"""

from __future__ import annotations

import base64


def render_water_overlay(main, result: dict) -> bool:
    """Draw the water overlay from a terrain-worker result and persist its
    marker feature (PNG regenerated on demand, like the slope overlay).
    Returns True when an overlay was drawn."""
    water_png = result.get("water_png_bytes")
    water_bbox = result.get("water_bbox")
    if not water_png or not water_bbox:
        return False
    data_url = ("data:image/png;base64,"
                + base64.b64encode(water_png).decode("ascii"))
    main.map_widget.draw_water_overlay({
        "image":   data_url,
        "bbox":    water_bbox,
        "opacity": 0.65,
        "arrows":  result.get("water_arrows") or [],
    })
    ring = [
        [water_bbox["west"], water_bbox["south"]],
        [water_bbox["east"], water_bbox["south"]],
        [water_bbox["east"], water_bbox["north"]],
        [water_bbox["west"], water_bbox["north"]],
        [water_bbox["west"], water_bbox["south"]],
    ]
    main._project["features"].append({
        "type": "Feature",
        "geometry": {"type": "Polygon", "coordinates": [ring]},
        "properties": {
            "element_type": "water_overlay",
            "bbox":         water_bbox,
            "resolution_m": result.get("resolution_m"),
            "source":       result.get("source", ""),
        },
    })
    return True


def water_status_bits(stats: dict) -> list[str]:
    """Status-line fragments for the terrain readout: ponding count plus the
    coarse-DEM honesty caveat (P9)."""
    bits = []
    n_pond = stats.get("n_ponding", 0)
    bits.append(f"Water: {n_pond} ponding cell(s)"
                if n_pond else "Water: no ponding found")
    if stats.get("water_dem_coarse"):
        bits.append("⚠ 30 m DEM — broad drainage patterns only, "
                    "not yard-scale flow")
    return bits
