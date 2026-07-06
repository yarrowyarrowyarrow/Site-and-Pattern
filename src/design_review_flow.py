"""
design_review_flow.py — On This Design ↔ map/tab cross-link glue (V2.13).

Free functions taking ``main`` (the MainWindow), mirroring wind_shadow_flow /
site_photo_flow: MainWindow is at its method ceiling
(tests/test_architecture_guard.py), so the review-tab behaviours live here
and app.py wires panel signals through thin lambdas.

Everything routes through existing pipelines: species selection uses the map's
unified selection model, removal goes selection → deleteSelected() so the JS
bridge's batch-removal path (store update + undo) runs exactly as it does for
a marquee + Delete.
"""

from __future__ import annotations

from typing import Optional

# Fallback half-size (degrees, ~5 m) so a single-plant "zoom to" still frames
# something sensible instead of a zero-area box.
_MIN_PAD_DEG = 0.00005


def _bounds(records) -> Optional[tuple]:
    """(south, west, north, east) over record lat/lng, padded to non-zero."""
    lats = [r["lat"] for r in records if r.get("lat") is not None]
    lngs = [r["lng"] for r in records if r.get("lng") is not None]
    if not lats or not lngs:
        return None
    south, north = min(lats), max(lats)
    west, east = min(lngs), max(lngs)
    if north - south < _MIN_PAD_DEG:
        south -= _MIN_PAD_DEG
        north += _MIN_PAD_DEG
    if east - west < _MIN_PAD_DEG:
        west -= _MIN_PAD_DEG
        east += _MIN_PAD_DEG
    return south, west, north, east


def _species_records(main, plant_id: int) -> list:
    return [r for r in (main._placed_plants or [])
            if r.get("plant_id") == plant_id]


def focus_species(main, plant_id: int) -> None:
    """Click a species row: light its markers up and frame them on the map."""
    recs = _species_records(main, plant_id)
    if not recs:
        return
    main.map_widget.select_plants_by_species(plant_id)
    b = _bounds(recs)
    if b:
        main.map_widget.fit_bounds(*b)
    name = recs[0].get("common_name") or f"plant #{plant_id}"
    main.statusBar().showMessage(
        f"{name}: {len(recs)} on the map — selected (Delete removes them; "
        "Esc / map click clears)", 4000)


def select_species(main, plant_id: int) -> None:
    """Context-menu 'Select on map' — selection only, no zoom."""
    main.map_widget.select_plants_by_species(plant_id)


def remove_species(main, plant_id: int) -> None:
    """Context-menu 'Remove all …' with confirmation. Deletion runs through
    the map's normal selection→delete pipeline so the store and undo stack
    see exactly the same events as a manual marquee + Delete."""
    from PyQt6.QtWidgets import QMessageBox
    recs = _species_records(main, plant_id)
    if not recs:
        return
    name = recs[0].get("common_name") or f"plant #{plant_id}"
    n = len(recs)
    resp = QMessageBox.question(
        main, "Remove plants",
        f"Remove all {n} placed {name}{'s' if n != 1 else ''} from the "
        "design? (Undo restores them.)",
        QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        QMessageBox.StandardButton.No)
    if resp != QMessageBox.StandardButton.Yes:
        return
    main.map_widget.select_plants_by_species(plant_id)
    main.map_widget.delete_selected()


def show_in_library(main, plant_id: int) -> None:
    """Context-menu 'Show in Plant Library' — jump to the Plants tab with the
    species name in the search box."""
    try:
        from src.db.plants import get_plant
        plant = get_plant(plant_id) or {}
    except Exception:  # noqa: BLE001
        plant = {}
    name = plant.get("common_name") or ""
    main._side_tabs.setCurrentWidget(main._plant_poly_tab)
    main._plants_inner_tabs.setCurrentWidget(main.plant_panel)
    if name:
        main.plant_panel._search_box.setText(name)


def focus_community(main, name: str) -> None:
    """Click a community row: frame every placed member of that community."""
    recs = [r for r in (main._placed_plants or [])
            if (r.get("polyculture_name") or "").strip() == name]
    b = _bounds(recs)
    if b:
        main.map_widget.fit_bounds(*b)
        main.statusBar().showMessage(
            f"{name}: {len(recs)} plants framed on the map", 3000)


def browse_communities(main, eco_key: str) -> None:
    """Site tab's ecoregion cross-link → open the Plant Community Library
    pre-filtered to communities of that ecoregion."""
    main._side_tabs.setCurrentWidget(main._plant_poly_tab)
    main._plants_inner_tabs.setCurrentWidget(main.polyculture_panel)
    main.polyculture_panel.set_habitat_filter([eco_key])
