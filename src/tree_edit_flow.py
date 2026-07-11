"""
tree_edit_flow.py — persist drag / scroll-resize of existing tree & building
marks (V2.26).

Free functions taking ``main`` (kept off MainWindow/the map controller, both at
their guard ceilings; wired from ``app.py`` via lambdas). Existing on-site
features — detected trees, and anything placed with Mark tree / Mark building —
are ``existing_tree`` / ``existing_building`` Point features (shade casters, not
design plants). The map now lets the user drag them to the real spot and
scroll-resize the crown to match the photo; these handlers write the new
position / canopy radius back onto the feature so it survives save, reload,
shade and the 3D view.

Each edit is one undo step (a persistence checkpoint). The marker has already
moved/resized on the map, so there's nothing to redraw — we only persist.
"""

from __future__ import annotations

from contextlib import nullcontext

_EXISTING = ("existing_tree", "existing_building")


def _checkpoint(main, label: str):
    persistence = getattr(main, "_persistence", None)
    return (persistence.checkpoint(label) if persistence is not None
            else nullcontext())


def _find(main, struct_id: str, lat: float, lng: float):
    """The existing-feature Point matching ``struct_id`` at ≈(lat, lng), or
    ``None``. Position is the identity (struct_id is shared by every tree)."""
    for f in main._project.get("features", []):
        props = f.get("properties") or {}
        if props.get("element_type") not in _EXISTING:
            continue
        if props.get("struct_id") != struct_id:
            continue
        coords = (f.get("geometry") or {}).get("coordinates") or []
        if len(coords) >= 2 and abs(coords[1] - lat) < 1e-6 \
                and abs(coords[0] - lng) < 1e-6:
            return f
    return None


def on_existing_feature_moved(main, marker_id: str, struct_id: str,
                              old_lat: float, old_lng: float,
                              new_lat: float, new_lng: float) -> None:
    """Write a dragged existing tree/building's new position onto its feature."""
    feat = _find(main, struct_id, old_lat, old_lng)
    if feat is None:
        return
    with _checkpoint(main, "move existing feature"):
        feat["geometry"]["coordinates"] = [new_lng, new_lat]
    main._mark_modified()


def on_existing_feature_foliage(main, marker_id: str, struct_id: str,
                                lat: float, lng: float, foliage: str) -> None:
    """Set a tree's foliage (conifer/deciduous) from the map's right-click
    switch — drives the 2D crown colour, 3D shape, and winter-shade weighting.
    Only trees carry foliage; a building mark is ignored."""
    if foliage not in ("evergreen", "deciduous"):
        return
    feat = _find(main, struct_id, lat, lng)
    if feat is None or feat["properties"].get("element_type") != "existing_tree":
        return
    with _checkpoint(main, "set tree foliage"):
        feat["properties"]["tree_foliage"] = foliage
    main._mark_modified()


def on_existing_feature_resized(main, marker_id: str, struct_id: str,
                                lat: float, lng: float,
                                new_diameter_m: float) -> None:
    """Write a scroll-resized existing feature's new crown size (diameter →
    ``canopy_radius_m``, the value shade + keep-out read) onto its feature."""
    feat = _find(main, struct_id, lat, lng)
    if feat is None:
        return
    radius = max(0.5, float(new_diameter_m) / 2.0)
    with _checkpoint(main, "resize existing feature"):
        props = feat["properties"]
        props["canopy_radius_m"] = radius
        props["size_m"] = float(new_diameter_m)
    main._mark_modified()
