"""
src/map_js.py — Typed builders for every JS entry point in html/map.html.

Each public function in this module returns a JavaScript snippet that
``MapWidget.run_js()`` can hand to the embedded Chromium page. The
builders are the single canonical surface for crossing the Python ↔
Leaflet boundary; calling code never assembles JS strings inline.

Why this exists:
  • Before Chunk 3 of the strengthening plan, every JS entry point's
    name was duplicated as a hard-coded string in f-string literals
    scattered across ``src/map_widget.py`` (≈50 sites) and
    ``src/app.py`` (≈19 sites that bypassed MapWidget entirely). A JS
    rename silently broke Python callers.
  • These builders are pure (no Qt, no I/O, no side effects), so the
    full bridge is unit-testable in plain Python.
  • String / dict args go through ``json.dumps`` rather than f-string
    interpolation, so a plant name containing a quote can no longer
    inject syntax.

If you add a new JS function in ``html/map.html``, add a matching
builder here and a unit test in ``tests/test_map_js.py``.
"""

from __future__ import annotations

import json
from typing import Any, Optional

# ── Low-level escape helpers ─────────────────────────────────────────────────

def _jsbool(b: bool) -> str:
    """Python ``True`` / ``False`` → JS ``true`` / ``false``."""
    return "true" if b else "false"


def _jsstr(s: str) -> str:
    """Embed a Python string as a JS string literal, properly escaped."""
    return json.dumps(s)


def _jslit(v: Any) -> str:
    """Embed any JSON-serialisable Python value as a JS literal."""
    return json.dumps(v)


def _jsobj(obj: Any) -> str:
    """Embed a Python dict/list as a JS object/array via ``JSON.parse``.

    The double-encoding ensures the JS source contains a single string
    literal that JS then parses at runtime — robust against any embedded
    quotes or control characters in the data.
    """
    return f"JSON.parse({json.dumps(json.dumps(obj))})"


# ── Modes ────────────────────────────────────────────────────────────────────

def set_mode(mode: str) -> str:
    """Enter a simple named mode (e.g. ``'sun_anchor'``, ``'terrain_rect'``)."""
    return f"setMode({_jsstr(mode)});"


def set_mode_with_payload(mode: str, payload: dict) -> str:
    """Enter a mode that carries a config dict (plant, structure, hedgerow,
    shape, contour)."""
    return f"setMode({_jsstr(mode)}, {_jsobj(payload)});"


def cancel_draw() -> str:
    return "cancelDraw();"


# ── Layer visibility toggles ────────────────────────────────────────────────

def set_satellite_visible(visible: bool) -> str:
    return f"setSatelliteVisible({_jsbool(visible)});"


def init_mapbox_layer(token: str) -> str:
    return f"initMapboxLayer({json.dumps(token)});"


def set_boundary_visible(visible: bool) -> str:
    return f"setBoundaryVisible({_jsbool(visible)});"


def set_measure_visible(visible: bool) -> str:
    return f"setMeasureVisible({_jsbool(visible)});"


def set_plants_visible(visible: bool) -> str:
    return f"setPlantsVisible({_jsbool(visible)});"


def set_labels_visible(visible: bool) -> str:
    return f"setLabelsVisible({_jsbool(visible)});"


def set_canopy_visible(visible: bool) -> str:
    return f"setCanopyVisible({_jsbool(visible)});"


def set_satellite_offset(east_m: float, north_m: float) -> str:
    """Nudge the satellite basemap by (east, north) metres — cosmetic alignment
    only; never moves project data."""
    return f"setSatelliteOffset({float(east_m)}, {float(north_m)});"


def set_structures_visible(visible: bool) -> str:
    """Toggle the *combined* layer group for structures + hedgerows +
    shapes. No JS function exists for this — the call inlines the loop
    over the three global marker dicts."""
    v = _jsbool(visible)
    return (
        "Object.values(structureMarkers).forEach(function(g) {"
        f"  if ({v}) g.addTo(map); else map.removeLayer(g);"
        "});"
        "Object.values(hedgerowLayers).forEach(function(g) {"
        f"  if ({v}) g.addTo(map); else map.removeLayer(g);"
        "});"
        "Object.values(shapeLayers).forEach(function(g) {"
        f"  if ({v}) g.addTo(map); else map.removeLayer(g);"
        "});"
    )


# ── Selection / global clears ───────────────────────────────────────────────

def clear_measure() -> str:
    return "clearMeasure();"


def clear_all() -> str:
    return "clearAll();"


def clear_selection() -> str:
    return "clearSelection();"


def delete_selected() -> str:
    return "deleteSelected();"


def toggle_legend() -> str:
    return "toggleLegend();"


# ── Map view ────────────────────────────────────────────────────────────────

def set_view(lat: float, lng: float, zoom: int = 14) -> str:
    return f"setView({lat}, {lng}, {zoom});"


def set_zoom_sensitivity(level: str) -> str:
    """level ∈ {'fine', 'normal', 'fast', 'coarse'}."""
    return f"setZoomSensitivity({_jsstr(level)});"


def set_grid_style(color: str, opacity: float) -> str:
    return f"setGridStyle({_jsstr(color)}, {float(opacity)});"


def set_snap_enabled(enabled: bool, grid_size: float = 1.0) -> str:
    return f"setSnapEnabled({_jsbool(enabled)}, {float(grid_size)});"


def set_crosshair_cursor() -> str:
    """Force a crosshair cursor on the map container — used while the
    user is arming a 'click to place' gesture for plant communities."""
    return "map.getContainer().style.cursor = 'crosshair';"


# ── Boundaries ──────────────────────────────────────────────────────────────

def load_boundary(boundary_data: dict, fit: bool = True) -> str:
    """The JS side expects a JSON string (not an object) for this entry
    point, hence the single-encoded payload. ``fit`` controls whether the
    map recenters on the boundary — File → Open fits, undo/redo re-renders
    pass ``fit=False`` so the camera stays put."""
    fit_lit = "true" if fit else "false"
    return f"loadBoundary({_jslit(json.dumps(boundary_data))}, {fit_lit});"


def undo_boundary(boundary_id: str) -> str:
    """Remove a boundary from the map by id. Wrapped in a typeof guard
    because ``_removeBoundaryEntry`` is an internal helper that may not
    exist on older map.html versions."""
    return (
        "(function() {"
        f"  if (typeof _removeBoundaryEntry === 'function') {{"
        f"    _removeBoundaryEntry({_jsstr(boundary_id)});"
        f"  }}"
        "})()"
    )


# ── Plant markers ───────────────────────────────────────────────────────────

def load_plant_marker(
    plant_id: int,
    common_name: str,
    lat: float,
    lng: float,
    spacing_m: float = 1.0,
    plant_type: str = "herb",
    custom_color: Optional[str] = None,
    group_id: Optional[str] = None,
    community_id: Optional[str] = None,
) -> str:
    """Restore a plant marker from a loaded project (no undo entry)."""
    color = _jsstr(custom_color) if custom_color else "null"
    group = _jsstr(group_id) if group_id else "null"
    community = _jsstr(community_id) if community_id else "null"
    return (
        f"loadPlantMarker({int(plant_id)}, {_jsstr(common_name)}, "
        f"{lat}, {lng}, {float(spacing_m)}, {_jsstr(plant_type)}, "
        f"{color}, {group}, {community});"
    )


def place_plant_marker(
    plant_id: int,
    common_name: str,
    lat: float,
    lng: float,
    spacing_m: float = 1.0,
    plant_type: str = "herb",
    color: Optional[str] = None,
    group_id: Optional[str] = None,
    community_id: Optional[str] = None,
) -> str:
    """Place a plant marker as a fresh user action (drives the standard
    placePlantMarker code path on the JS side, including the post-place
    sync)."""
    color_arg = _jsstr(color) if color else "null"
    group_arg = _jsstr(group_id) if group_id else "null"
    community_arg = _jsstr(community_id) if community_id else "null"
    return (
        f"placePlantMarker({int(plant_id)}, {_jsstr(common_name)}, "
        f"{lat}, {lng}, {float(spacing_m)}, {_jsstr(plant_type)}, "
        f"{color_arg}, {group_arg}, {community_arg});"
    )


def set_plant_group_for_latest(plant_id: int, lat: float, lng: float,
                                group_id: str) -> str:
    return (
        f"setPlantGroupForLatest({int(plant_id)}, {lat}, {lng}, "
        f"{_jsstr(group_id)});"
    )


def update_marker_color(plant_id: int, color: str) -> str:
    return f"updateMarkerColor({int(plant_id)}, {_jsstr(color)});"


def place_annotation(ann_id: str, lat: float, lng: float, text: str) -> str:
    return (
        f"placeAnnotation({_jsstr(ann_id)}, {lat}, {lng}, {_jsstr(text)});"
    )


def clear_annotations() -> str:
    """Remove every annotation marker. clearAll() leaves annotations alone,
    so the whole-project re-render clears them explicitly before redrawing."""
    return "clearAnnotations();"


def undo_place_plant(plant_id: int, lat: float, lng: float) -> str:
    """Remove the most-recent plant marker matching (plant_id, lat, lng).

    No named JS function exists for this; the search loop iterates the
    global ``plantMarkers`` dict from newest to oldest. Inline because
    promoting it to a named JS helper is out of scope for Chunk 3.
    """
    return (
        "(function() {"
        "  var keys = Object.keys(plantMarkers);"
        "  for (var i = keys.length - 1; i >= 0; i--) {"
        "    var m = plantMarkers[keys[i]];"
        f"    if (m._pd && m._pd.plantId === {int(plant_id)}"
        f"        && Math.abs(m._pd.lat - {lat}) < 1e-7"
        f"        && Math.abs(m._pd.lng - {lng}) < 1e-7) {{"
        "      map.removeLayer(m);"
        "      if (plantLabels[keys[i]]) { map.removeLayer(plantLabels[keys[i]]); delete plantLabels[keys[i]]; }"
        "      delete plantMarkers[keys[i]];"
        "      break;"
        "    }"
        "  }"
        "})()"
    )


def revert_plant_position(
    plant_id: int,
    from_lat: float, from_lng: float,
    to_lat: float, to_lng: float,
) -> str:
    """Move a plant marker from (from_lat, from_lng) back to
    (to_lat, to_lng). Used by undo/redo on a plant drag."""
    return (
        "(function() {"
        "  var keys = Object.keys(plantMarkers);"
        "  for (var i = keys.length - 1; i >= 0; i--) {"
        "    var m = plantMarkers[keys[i]];"
        f"    if (m._pd && m._pd.plantId === {int(plant_id)}"
        f"        && Math.abs(m._pd.lat - {from_lat}) < 1e-7"
        f"        && Math.abs(m._pd.lng - {from_lng}) < 1e-7) {{"
        f"      m.setLatLng([{to_lat}, {to_lng}]);"
        f"      m._pd.lat = {to_lat}; m._pd.lng = {to_lng};"
        "      var lbl = plantLabels[keys[i]];"
        f"      if (lbl) lbl.setLatLng([{to_lat}, {to_lng}]);"
        "      break;"
        "    }"
        "  }"
        "})()"
    )


# ── Site pin ────────────────────────────────────────────────────────────────

def place_site_pin(lat: float, lng: float, label: str = "") -> str:
    return f"placeSitePin({lat}, {lng}, {_jsstr(label)});"


def clear_site_pin() -> str:
    return "clearSitePin(false);"


def set_site_pin_drop_mode(active: bool) -> str:
    return f"setSitePinDropMode({_jsbool(active)});"


# ── Structures / hedgerows / shapes ─────────────────────────────────────────

def load_structure(struct_def: dict, lat: float, lng: float) -> str:
    return f"loadStructure({_jsobj(struct_def)}, {lat}, {lng});"


def undo_structure_at(struct_id: str, lat: float, lng: float) -> str:
    return f"undoStructureAt({_jsstr(struct_id)}, {lat}, {lng});"


def load_hedgerow(hedge_def: dict) -> str:
    return f"loadHedgerow({_jsobj(hedge_def)});"


def undo_hedgerow_by_id(hedge_id: str) -> str:
    return f"undoHedgerowById({_jsstr(hedge_id)});"


def load_shape(shape_def: dict) -> str:
    return f"loadShape({_jsobj(shape_def)});"


def undo_custom_shape_by_id(shape_id: str) -> str:
    return f"undoCustomShapeById({_jsstr(shape_id)});"


# ── Sun / sector / wind / season overlays ───────────────────────────────────

def draw_sun_path(data: dict, lat: Optional[float] = None,
                   lng: Optional[float] = None) -> str:
    if lat is not None and lng is not None:
        return f"drawSunPath({_jsobj(data)}, {lat}, {lng});"
    return f"drawSunPath({_jsobj(data)});"


def clear_sun_path() -> str:
    return "clearSunPath();"


def draw_sectors(data: dict, lat: Optional[float] = None,
                  lng: Optional[float] = None) -> str:
    if lat is not None and lng is not None:
        return f"drawSectors({_jsobj(data)}, {lat}, {lng});"
    return f"drawSectors({_jsobj(data)});"


def clear_sectors() -> str:
    return "clearSectors();"


def draw_wind_overlay(data: dict) -> str:
    return f"drawWindOverlay({_jsobj(data)});"


def clear_wind_overlay() -> str:
    return "clearWindOverlay();"


def set_season_view(season: str, pid_visibility: dict) -> str:
    """Highlight plants in/out of season for a given month name."""
    return f"setSeasonView({_jsstr(season)}, {_jslit(pid_visibility)});"


def set_timeline_year_by_plant_id(year: int, pid_factors: dict,
                                  pid_presence: dict | None = None,
                                  pid_spread: dict | None = None) -> str:
    """Drive the growth-timeline animation: each entry in ``pid_factors`` is
    plant_id → maturity-factor (0..1) for size. Optional ``pid_presence`` maps
    plant_id → presence-opacity (0..1) so pioneers fade out and climax species
    fade in along the succession timeline (N5); omitted ⇒ all fully present.
    Optional ``pid_spread`` maps plant_id → footprint-expansion (≥1.0) so self-
    spreaders widen their canopy as the colony fills in (F35)."""
    pres = pid_presence or {}
    spread = pid_spread or {}
    if spread:
        return (f"setTimelineYearByPlantId({int(year)}, {_jslit(pid_factors)}, "
                f"{_jslit(pres)}, {_jslit(spread)});")
    if pid_presence:
        return (f"setTimelineYearByPlantId({int(year)}, {_jslit(pid_factors)}, "
                f"{_jslit(pid_presence)});")
    return f"setTimelineYearByPlantId({int(year)}, {_jslit(pid_factors)});"


# ── Contours / auto-terrain ─────────────────────────────────────────────────

def clear_contours() -> str:
    return "clearContours();"


def undo_last_contour(elevation_m: float) -> str:
    return f"undoLastContour({float(elevation_m)});"


def restore_contour(contour: dict) -> str:
    """Re-finish a previously-drawn contour from a saved project. The
    JS-side ``finishContour`` reuses the in-progress drawing globals
    (``contourPoints`` / ``currentContour``), so this IIFE temporarily
    primes them and then clears them."""
    return (
        "(function() {"
        f"  var d = {_jsobj(contour)};"
        "  contourPoints = d.points;"
        "  currentContour = d;"
        "  finishContour();"
        "  contourPoints = [];"
        "})()"
    )


def request_terrain_viewport() -> str:
    return "emitTerrainBboxFromViewport();"


def request_terrain_boundary_bbox() -> str:
    return "emitTerrainBboxFromBoundary();"


def draw_auto_contours(contours: list[dict], color: str,
                        show_labels: bool) -> str:
    payload = {
        "contours": contours,
        "color": color,
        "show_labels": bool(show_labels),
    }
    return f"drawAutoContours({_jsobj(payload)});"


def draw_slope_overlay(png_data_url: str, bbox: dict, opacity: float) -> str:
    payload = {
        "image": png_data_url,
        "bbox": bbox,
        "opacity": float(opacity),
    }
    return f"drawSlopeOverlay({_jsobj(payload)});"


def set_slope_overlay_opacity(opacity: float) -> str:
    return f"setSlopeOverlayOpacity({float(opacity)});"


def draw_shade_overlay(png_data_url: str, bbox: dict, opacity: float) -> str:
    """Render the shade-fraction PNG as a separate image overlay (V1.51)."""
    payload = {"image": png_data_url, "bbox": bbox, "opacity": float(opacity)}
    return f"drawShadeOverlay({_jsobj(payload)});"


def set_shade_overlay_opacity(opacity: float) -> str:
    return f"setShadeOverlayOpacity({float(opacity)});"


def clear_shade_overlay() -> str:
    return "clearShadeOverlay();"


# ── Dynamic wind shadow (V1.68) ──────────────────────────────────────────────

def set_wind_casters(casters: list) -> str:
    """Push the per-plant shelter casters (lat/lng/height/half_width/porosity) to
    the JS live layer so it can redraw ghost wedges instantly as the dial turns
    or a plant drags — no Python round-trip per frame."""
    return f"setWindCasters({_jsobj(casters or [])});"


def set_wind_angle_live(deg: float) -> str:
    """Update only the wind angle and re-orient the live ghost wedges in JS."""
    return f"setWindAngleLive({float(deg)});"


def draw_merged_wind_shelter(payload: dict) -> str:
    """Draw the authoritative merged, porosity-banded shelter (Python-computed,
    on commit). ``payload`` = ``{bands:[{strength,rings}], wind_from_deg}``."""
    return f"drawMergedWindShelter({_jsobj(payload or {})});"


def set_wind_shadow_visible(visible: bool) -> str:
    return f"setWindShadowVisible({_jsbool(visible)});"


def clear_wind_shadow() -> str:
    return "clearWindShadow();"


def draw_splat_ortho_overlay(png_data_url: str, bbox: dict,
                             opacity: float) -> str:
    """Render the baked top-down splat photo as its own image overlay (V1.65)
    — a personal, fresher "satellite" layer of the user's yard. Separate from
    the slope/shade overlays so all can show at once; mirrors
    ``draw_shade_overlay``."""
    payload = {"image": png_data_url, "bbox": bbox, "opacity": float(opacity)}
    return f"drawSplatOrthoOverlay({_jsobj(payload)});"


def set_splat_ortho_visible(visible: bool) -> str:
    return f"setSplatOrthoVisible({_jsbool(visible)});"


def set_splat_ortho_opacity(opacity: float) -> str:
    return f"setSplatOrthoOpacity({float(opacity)});"


def clear_splat_ortho() -> str:
    return "clearSplatOrtho();"


def draw_site_photo_overlay(image_data_url: str, bbox: dict,
                            opacity: float) -> str:
    """Render a user yard/drone photo as a georeferenced map underlay (F24) —
    its own image layer (like the splat ortho / shade overlays) so it composes
    with everything else."""
    payload = {"image": image_data_url, "bbox": bbox, "opacity": float(opacity)}
    return f"drawSitePhotoOverlay({_jsobj(payload)});"


def set_site_photo_visible(visible: bool) -> str:
    return f"setSitePhotoVisible({_jsbool(visible)});"


def set_site_photo_opacity(opacity: float) -> str:
    return f"setSitePhotoOpacity({float(opacity)});"


def clear_site_photo() -> str:
    return "clearSitePhoto();"


def draw_shade_zones(cells: list, d_lat: float, d_lng: float,
                     opacity: float = 0.45) -> str:
    """Draw the classified planting zones as a coloured grid (V1.60). ``cells``
    is a list of ``{lat, lng, tag}`` dicts; ``d_lat``/``d_lng`` are the grid
    cell size in degrees so each cell renders as a filled rectangle."""
    payload = {"cells": cells, "dLat": float(d_lat), "dLng": float(d_lng),
               "opacity": float(opacity)}
    return f"drawShadeZones({_jsobj(payload)});"


def set_shade_zones_visible(visible: bool) -> str:
    return f"setShadeZonesVisible({_jsbool(visible)});"


def clear_shade_zones() -> str:
    return "clearShadeZones();"


def draw_shadow_polygons(polygons: list, bbox: dict, opacity: float) -> str:
    """Render true-shape shadows as vector polygons (V1.54). ``polygons`` is a
    list of rings-lists of ``[lat, lng]`` pairs (exterior first, then holes)."""
    payload = {"polygons": polygons, "bbox": bbox, "opacity": float(opacity)}
    return f"drawShadowPolygons({_jsobj(payload)});"


def set_shadow_polygon_opacity(opacity: float) -> str:
    return f"setShadowPolygonOpacity({float(opacity)});"


def clear_shadow_polygons() -> str:
    return "clearShadowPolygons();"


def clear_auto_terrain() -> str:
    return "clearAutoTerrain();"


# ── Resize / invalidate (load-bearing — see map_widget.py block comment) ────

def invalidate_size() -> str:
    """The two ``console.log`` calls and the ``clientWidth`` reads are
    NOT debug noise — each one forces a Chromium layout reflow, which is
    what keeps the Windows maximise-with-LiDAR-contours code path from
    freezing. See the block comment above ``MapWidget.invalidate_size``
    in ``src/map_widget.py`` before editing this string."""
    return (
        "if (typeof map !== 'undefined' && map && map.invalidateSize) {"
        "  console.log('[dbg] invalidateSize start, container=' + "
        "    map.getContainer().clientWidth + 'x' + map.getContainer().clientHeight);"
        "  var _t0 = performance.now();"
        "  map.invalidateSize(false);"
        "  console.log('[dbg] invalidateSize end, elapsed=' + "
        "    (performance.now() - _t0).toFixed(1) + 'ms');"
        "}"
    )
