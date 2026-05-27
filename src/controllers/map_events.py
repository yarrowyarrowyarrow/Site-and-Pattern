"""
src/controllers/map_events.py — MapBridge → MainWindow event router.

Owns the ``_on_*`` slot handlers wired to MapBridge signals in
``_connect_signals``. These handlers translate user gestures on the
Leaflet map (boundary draws, plant moves, structure placements, …)
into mutations on ``MainWindow._project["features"]`` plus undo-stack
entries, modified-flag updates, and status-bar / mode-label feedback.

Extracted from ``src/app.py:MainWindow`` in Chunk 5d of the
strengthening roadmap. This pilot covers the *boundary* handler family
only — the rest of the ~50 ``_on_*`` handlers (structure, hedgerow,
shape, contour, terrain, sun/sector/wind, plant move/group-move,
polyculture, sun/sector anchor) move in follow-up commits that group
them by feature domain.

Why one-domain-at-a-time:

- The Chunk 4 fallout taught us that touching scattered, deeply-coupled
  code in one big move risks runtime regressions that no static check
  catches. Boundary handlers are the smallest, most self-contained
  domain, so they're the right pilot.
- The shim pattern (``MainWindow._on_X`` → ``self._map_events._on_X``)
  preserves the QSignal.connect() wiring in ``_connect_signals``
  unchanged, so a domain extraction can't accidentally break the
  signal hookup.
"""

from __future__ import annotations

from src.climate import get_zone, zone_label


class MapEventRouter:
    """MapBridge slot handlers. Holds a MainWindow reference so handlers
    can mutate ``_project["features"]`` and call back into the other
    controllers (``_push_undo`` → PersistenceController,
    ``_mark_modified`` → PersistenceController, ``_set_mode_label`` →
    ModeController, ``_set_zone_display`` → MainWindow native).
    """

    def __init__(self, main_window):
        self._main = main_window

    # ── Boundary handlers ────────────────────────────────────────────────────

    def _on_boundary_complete(self, bid: str, coords: list, color: str):
        """Multi-boundary: add a new boundary to the project."""
        ring = [[pt[1], pt[0]] for pt in coords] + [[coords[0][1], coords[0][0]]]
        self._main._project["features"].append({
            "type": "Feature",
            "geometry": {"type": "Polygon", "coordinates": [ring]},
            "properties": {
                "element_type": "property_boundary",
                "boundary_id": bid,
                "color": color,
                "show_lengths": True,
                "show_area": True,
            }
        })

        lats = [pt[0] for pt in coords]
        lngs = [pt[1] for pt in coords]
        self._main._set_zone_display(get_zone(sum(lats)/len(lats), sum(lngs)/len(lngs)))

        self._main._push_undo({
            "action": "place_boundary",
            "boundary_id": bid,
            "coords": list(coords),
            "color": color,
        })

        self._main._mark_modified()
        self._main.toolbar.reset_draw_buttons()
        self._main._set_mode_label(
            f"Boundary added ({color}) — " + zone_label(self._main._current_zone)
        )

    def _on_boundary_geom_changed(self, bid: str, coords: list):
        """Update geometry of an existing boundary after vertex/move/scale drag."""
        ring = [[pt[1], pt[0]] for pt in coords] + [[coords[0][1], coords[0][0]]]
        for f in self._main._project.get("features", []):
            if (f.get("properties", {}).get("element_type") == "property_boundary"
                    and f["properties"].get("boundary_id") == bid):
                f["geometry"]["coordinates"] = [ring]
                break
        self._main._mark_modified()

    def _on_boundary_props_changed(self, bid: str, color: str,
                                    show_lengths: bool, show_area: bool):
        """Update color/label toggles for an existing boundary."""
        for f in self._main._project.get("features", []):
            if (f.get("properties", {}).get("element_type") == "property_boundary"
                    and f["properties"].get("boundary_id") == bid):
                f["properties"]["color"] = color
                f["properties"]["show_lengths"] = show_lengths
                f["properties"]["show_area"] = show_area
                break
        self._main._mark_modified()

    def _on_boundary_removed(self, bid: str):
        """Remove a boundary from the project."""
        self._main._project["features"] = [
            f for f in self._main._project["features"]
            if not (f.get("properties", {}).get("element_type") == "property_boundary"
                    and f["properties"].get("boundary_id") == bid)
        ]
        self._main._mark_modified()
