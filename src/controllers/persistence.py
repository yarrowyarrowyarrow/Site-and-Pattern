"""
src/controllers/persistence.py — Save / autosave / undo-stack controller.

Owns the small, low-coupling persistence helpers: marking the project
dirty (and reflecting that in the window title), saving to disk +
choosing a path, the autosave timer, and pushing entries onto the
undo stack.

Extracted from ``src/app.py:MainWindow`` in Chunk 5c of the
strengthening roadmap. The much larger ``_do_undo`` / ``_do_redo``
methods (200+ lines each, action-type branches that mutate project
state and drive the map via typed bridges from Chunk 3) stay on
MainWindow for a separate follow-up — they're high-risk and deserve
their own characterisation tests first.

The controller still talks to Qt via the bound MainWindow: file dialog
parent, status bar messages, the undo/redo QAction widgets created in
``_build_menu``. Making it Qt-free is Chunk 6 (E1).
"""

from __future__ import annotations

import copy
import os
from contextlib import contextmanager

from PyQt6.QtCore import QTimer
from PyQt6.QtWidgets import QFileDialog, QMessageBox

import src.project as project_io
from src.branding import APP_NAME


class PersistenceController:
    """Save / autosave / push_undo. Holds a MainWindow reference for the
    project state (``_project``, ``_project_path``, ``_modified``), the
    undo stack (``_undo_stack``, ``_redo_stack``, ``_max_undo``), the
    undo/redo QActions (``_act_undo``, ``_act_redo``), the autosave
    timer slot (``_autosave_timer``), and the Qt host (file dialog
    parent, status bar, window title).
    """

    def __init__(self, main_window):
        self._main = main_window
        # Snapshot-checkpoint re-entrancy state (V1.81). A depth counter so
        # nested checkpoints (e.g. a community fill that calls a placement
        # helper that is itself decorated) push exactly one undo entry.
        self._cp_depth = 0
        self._cp_before = None

    # ── Modified flag + window title ─────────────────────────────────────────

    def _mark_modified(self):
        self._main._modified = True
        if not self._main.windowTitle().endswith(' *'):
            self._main.setWindowTitle(self._main.windowTitle() + ' *')

    # ── Save / Save As ────────────────────────────────────────────────────────

    def _on_save(self):
        if self._main._project_path:
            self._save_to_path(self._main._project_path)
        else:
            self._on_save_as()

    def _on_save_as(self):
        path, _ = QFileDialog.getSaveFileName(
            self._main, "Save Design", "",
            "Site & Pattern Files (*.perma.geojson);;GeoJSON (*.geojson)"
        )
        if path:
            if not path.endswith('.perma.geojson') and not path.endswith('.geojson'):
                path += '.perma.geojson'
            self._save_to_path(path)

    def _save_to_path(self, path: str):
        try:
            project_io.save_project(self._main._project, path)
            self._main._project_path = path
            self._main._modified     = False
            name = self._main._project["properties"].get("project_name", "Design")
            self._main.setWindowTitle(f"{APP_NAME} — {name}")
            self._main.statusBar().showMessage(f"Saved: {path}", 3000)
        except Exception as exc:
            QMessageBox.critical(self._main, "Save failed", str(exc))

    # ── Autosave timer ────────────────────────────────────────────────────────

    def _start_autosave(self):
        self._main._autosave_timer = QTimer(self._main)
        self._main._autosave_timer.setInterval(self._main.AUTOSAVE_INTERVAL_MS)
        self._main._autosave_timer.timeout.connect(self._autosave)
        self._main._autosave_timer.start()

    def _autosave(self):
        if not self._main._modified:
            return
        tmp = os.path.join(os.path.expanduser("~"), ".permadesign_autosave.perma.geojson")
        try:
            project_io.save_project(self._main._project, tmp)
        except Exception:
            pass

    # ── Undo / redo ───────────────────────────────────────────────────────────
    # V1.63: the full undo/redo engine lives here (the Chunk 5c docstring
    # deferred it pending characterisation tests — tests/test_undo_redo.py
    # is that suite). Design: one (undo, redo) handler pair per action
    # type in _HANDLERS. Undo handlers stash whatever features they remove
    # into the entry ("_removed_features"), so redo is generic where it
    # can be: re-append the stashed features and re-render them through
    # the same map-widget loaders File → Open uses.

    def _push_undo(self, entry: dict):
        self._main._undo_stack.append(entry)
        if len(self._main._undo_stack) > self._main._max_undo:
            self._main._undo_stack.pop(0)
        self._main._redo_stack.clear()
        self._main._act_undo.setEnabled(True)
        self._main._act_redo.setEnabled(False)

    def _do_undo(self):
        m = self._main
        if not m._undo_stack:
            return
        entry = m._undo_stack.pop()
        pair = self._HANDLERS.get(entry["action"])
        if pair is not None:
            pair[0](self, entry)
            m._redo_stack.append(entry)
        self._refresh_actions()

    def _do_redo(self):
        m = self._main
        if not m._redo_stack:
            return
        entry = m._redo_stack.pop()
        pair = self._HANDLERS.get(entry["action"])
        if pair is not None:
            pair[1](self, entry)
            m._undo_stack.append(entry)
        self._refresh_actions()

    def _refresh_actions(self):
        m = self._main
        m._act_undo.setEnabled(bool(m._undo_stack))
        m._act_redo.setEnabled(bool(m._redo_stack))
        self._mark_modified()

    # ── feature stash helpers ────────────────────────────────────────────────

    def _stash_removed(self, entry: dict, predicate, *,
                       single: bool = True, newest_first: bool = True):
        """Remove the feature(s) matching ``predicate`` from the project
        (newest-first when ``single``) and stash them on the entry for
        redo. Returns the removed features."""
        m = self._main
        feats = m._project["features"]
        removed: list = []
        if single:
            order = range(len(feats) - 1, -1, -1) if newest_first \
                else range(len(feats))
            for i in order:
                if predicate(feats[i]):
                    removed.append(feats.pop(i))
                    break
        else:
            kept = []
            for f in feats:
                (removed if predicate(f) else kept).append(f)
            m._project["features"] = kept
        entry["_removed_features"] = removed
        return removed

    def _restore_stashed(self, entry: dict) -> list:
        """Re-append the features an undo stashed; returns them."""
        feats = entry.get("_removed_features") or []
        self._main._project["features"].extend(feats)
        return feats

    # ── snapshot checkpoint (V1.81 — the exhaustive catch-all) ───────────────
    # The surgical handlers above cover the high-frequency single-item
    # gestures (place/move one plant, one boundary, …). Everything else —
    # bulk placements (pattern, generate, area fill, community), every
    # removal, every geometry/property edit, and every import (OSM, footprint,
    # scan, terrain) — is wrapped in a checkpoint instead. A checkpoint
    # deep-copies project["features"] before the action and, if it changed,
    # pushes one "snapshot" entry carrying the before/after lists. Undo/redo
    # swap the whole list back in and re-render the map. This makes undo
    # exhaustive by construction: any feature change is reversible, and new
    # feature types need no bespoke handler pair.

    @contextmanager
    def checkpoint(self, label: str = ""):
        """Record a snapshot undo step around a block that mutates
        ``project["features"]``. Re-entrant: only the outermost checkpoint
        snapshots and pushes, so a decorated helper called from a decorated
        entry point yields a single undo entry. Records nothing when the
        block raises or leaves the features unchanged."""
        m = self._main
        outer = self._cp_depth == 0
        if outer:
            self._cp_before = copy.deepcopy(m._project.get("features", []))
        self._cp_depth += 1
        ok = False
        try:
            yield
            ok = True
        finally:
            self._cp_depth -= 1
            if outer:
                before, self._cp_before = self._cp_before, None
                if ok:
                    after = m._project.get("features", [])
                    if before != after:
                        self._push_undo({
                            "action": "snapshot",
                            "label": label,
                            "before": before,
                            "after": copy.deepcopy(after),
                        })

    def _undo_snapshot(self, entry: dict):
        self._apply_features_snapshot(entry["before"])
        self._main.statusBar().showMessage(
            f"Undo: {entry.get('label') or 'change'}", 2000)

    def _redo_snapshot(self, entry: dict):
        self._apply_features_snapshot(entry["after"])
        self._main.statusBar().showMessage(
            f"Redo: {entry.get('label') or 'change'}", 2000)

    def _apply_features_snapshot(self, features: list):
        """Swap the project's whole feature list to a stored snapshot, rebuild
        the placed-plants index from it, and redraw the map from scratch."""
        m = self._main
        m._project["features"] = copy.deepcopy(features)
        m._store.rebuild_index()
        self.render_project_to_map(fit_view=False)

    # ── whole-project map re-render (shared by File→Open and undo/redo) ───────

    def render_project_to_map(self, *, fit_view: bool = False):
        """Clear the map and redraw every feature-derived layer from the
        current project. File → Open passes ``fit_view=True`` (recenter on the
        site); snapshot undo/redo pass ``False`` so the camera stays put.

        Lives on the controller (not as a fat MainWindow method) so the
        architecture-guard method ceiling stays meaningful; ``_load_from_path``
        and the snapshot handlers both call it."""
        from src.climate import get_zone
        m = self._main
        proj = m._project

        m.map_widget.clear_all()
        # clearAll() leaves these alone, so wipe them explicitly before redraw.
        m.map_widget.clear_annotations()
        m.map_widget.clear_shade_overlay()

        data = project_io.project_to_map_data(proj)

        for bd in data.get("boundaries", []):
            m.map_widget.load_boundary(bd, fit=fit_view)
        if data.get("boundaries"):
            first = data["boundaries"][0]
            lats = [p[0] for p in first["points"]]
            lngs = [p[1] for p in first["points"]]
            m._set_zone_display(
                get_zone(sum(lats) / len(lats), sum(lngs) / len(lngs)))

        # Backfill placement_group_id onto legacy plant features so a later
        # save persists the singleton groups project_to_map_data minted.
        plant_idx = 0
        for f in proj.get("features", []):
            if f.get("properties", {}).get("element_type") == "plant":
                if (not f["properties"].get("placement_group_id")
                        and plant_idx < len(data["plants"])):
                    f["properties"]["placement_group_id"] = (
                        data["plants"][plant_idx]["placement_group_id"])
                plant_idx += 1

        for p in data["plants"]:
            spacing_m, plant_type, custom_color = m._plant_info(p["plant_id"])
            community_id = project_io.community_id_for(
                p.get("polyculture_center_lat"),
                p.get("polyculture_center_lng"))
            m.map_widget.load_plant_marker(
                p["plant_id"], p["common_name"], p["lat"], p["lng"],
                spacing_m, plant_type, custom_color,
                p.get("placement_group_id", ""), community_id or "")
        m._store.replace_placed_plants(data["plants"])
        m.plant_panel.load_placed(data["plants"])

        for s in data.get("structures", []):
            m.map_widget.load_structure(s["struct_def"], s["lat"], s["lng"])
        for h in data.get("hedgerows", []):
            m.map_widget.load_hedgerow(h)
        for sh in data.get("shapes", []):
            m.map_widget.load_shape(sh)
        for ctr in data.get("contours", []):
            m.map_widget.apply_loaded_contour(ctr)
        for ann in data.get("annotations", []):
            m.map_widget.place_annotation(
                ann["annotation_id"], ann["lat"], ann["lng"], ann["text"])

        auto_contours = data.get("auto_contours") or []
        if auto_contours:
            m.map_widget.draw_auto_contours(
                [{"elevation_m": c["elevation_m"], "segments": c["segments"]}
                 for c in auto_contours],
                color=auto_contours[0].get("color", "#44cc00"),
                show_labels=True)
        if data.get("slope_overlay"):
            m.site_panel.set_auto_terrain_status(
                "Slope ramp not loaded — click Generate to recompute.")

        # Site pin (clearAll wiped it) + photoreal splat backdrop, both read
        # from the project so undo of an import that removed them clears them.
        sc = proj.get("properties", {}).get("site_config") or {}
        plat, plng = sc.get("latitude"), sc.get("longitude")
        if plat is not None and plng is not None:
            m.map_widget.place_site_pin(plat, plng, sc.get("pin_label", ""))
        from src import splat_flow
        splat_flow.restore_splat_overlay(m)

    # ── per-action handlers ──────────────────────────────────────────────────

    def _undo_place_plant(self, entry):
        m = self._main
        pid, lat, lng = entry["plant_id"], entry["lat"], entry["lng"]
        m.map_widget.undo_place_plant(pid, lat, lng)
        m._store.remove_plant(pid, lat, lng, newest_first=True)
        m.plant_panel.on_plant_removed(pid)
        m.statusBar().showMessage("Undo: removed plant", 2000)

    def _redo_place_plant(self, entry):
        m = self._main
        pid, name = entry["plant_id"], entry["common_name"]
        lat, lng = entry["lat"], entry["lng"]
        group_id = entry.get("placement_group_id") or ""
        spacing_m, plant_type, custom_color = m._plant_info(pid)
        m.map_widget.load_plant_marker(
            pid, name, lat, lng, spacing_m, plant_type, custom_color,
            group_id)
        m._store.add_plant(pid, name, lat, lng,
                           placement_group_id=group_id)
        m.plant_panel.on_plant_placed(pid, name)
        m.statusBar().showMessage("Redo: placed plant", 2000)

    def _undo_place_structure(self, entry):
        m = self._main
        sid, lat, lng = entry["struct_id"], entry["lat"], entry["lng"]
        m.map_widget.undo_structure_at(sid, lat, lng)
        # Existing tree/building marks (V1.49) also undo through here.
        _undoable = {"structure", "existing_tree", "existing_building"}

        def _match(f):
            props = f.get("properties", {})
            coords = f.get("geometry", {}).get("coordinates", [])
            return (props.get("element_type") in _undoable
                    and props.get("struct_id") == sid
                    and coords
                    and abs(coords[1] - lat) < 1e-7
                    and abs(coords[0] - lng) < 1e-7)
        self._stash_removed(entry, _match)
        m.statusBar().showMessage(
            f"Undo: removed {entry.get('name', 'structure')}", 2000)
        m._sync_planning_panel()

    def _redo_place_structure(self, entry):
        m = self._main
        for f in self._restore_stashed(entry):
            props = f.get("properties", {})
            coords = f.get("geometry", {}).get("coordinates", [])
            sd = props.get("struct_def") or entry.get("struct_def") or {}
            if len(coords) >= 2 and sd:
                m.map_widget.load_structure(sd, coords[1], coords[0])
        m.statusBar().showMessage(
            f"Redo: placed {entry.get('name', 'structure')}", 2000)
        m._sync_planning_panel()

    def _undo_place_boundary(self, entry):
        m = self._main
        bid = entry["boundary_id"]
        m.map_widget.undo_boundary(bid)
        self._stash_removed(
            entry,
            lambda f: (f.get("properties", {}).get("element_type")
                       == "property_boundary"
                       and f["properties"].get("boundary_id") == bid),
            single=False)
        m.statusBar().showMessage("Undo: removed boundary", 2000)

    def _redo_place_boundary(self, entry):
        m = self._main
        for f in self._restore_stashed(entry):
            geom = f.get("geometry", {})
            props = f.get("properties", {})
            if geom.get("type") != "Polygon" or not geom.get("coordinates"):
                continue
            m.map_widget.load_boundary({
                "id": props.get("boundary_id"),
                "points": [[pt[1], pt[0]] for pt in geom["coordinates"][0]],
                "color": props.get("color", "green"),
                "showLengths": props.get("show_lengths", True),
                "showArea": props.get("show_area", True),
            })
        m.statusBar().showMessage("Redo: placed boundary", 2000)

    def _undo_place_contour(self, entry):
        m = self._main
        elev = float(entry.get("elevation_m") or 0.0)
        m.map_widget.undo_last_contour(elev)
        self._stash_removed(
            entry,
            lambda f: (f.get("properties", {}).get("element_type")
                       == "contour_line"
                       and abs(float(f["properties"].get("elevation_m")
                                     or 0.0) - elev) < 1e-3))
        m.statusBar().showMessage(
            f"Undo: removed contour at {elev:.1f}m", 2000)

    def _redo_place_contour(self, entry):
        m = self._main
        for f in self._restore_stashed(entry):
            geom = f.get("geometry", {})
            props = f.get("properties", {})
            if geom.get("type") != "LineString":
                continue
            m.map_widget.apply_loaded_contour({
                "points": [[pt[1], pt[0]] for pt in geom["coordinates"]],
                "elevation_m": props.get("elevation_m", 0),
                "color": props.get("color", "#795548"),
            })
        m.statusBar().showMessage(
            f"Redo: placed contour at "
            f"{float(entry.get('elevation_m') or 0.0):.1f}m", 2000)

    def _undo_place_hedgerow(self, entry):
        m = self._main
        hid = entry["hedge_id"]
        m.map_widget.undo_hedgerow_by_id(hid)
        self._stash_removed(
            entry,
            lambda f: f.get("properties", {}).get("hedge_id") == hid,
            single=False)
        m.statusBar().showMessage("Undo: removed hedgerow", 2000)

    def _redo_place_hedgerow(self, entry):
        m = self._main
        for f in self._restore_stashed(entry):
            geom = f.get("geometry", {})
            props = f.get("properties", {})
            if geom.get("type") != "LineString":
                continue
            m.map_widget.load_hedgerow({
                "points": [[pt[1], pt[0]] for pt in geom["coordinates"]],
                "style": props.get("style", "hedge"),
                "color": props.get("color", "#4caf50"),
                "width_m": props.get("width_m", 1.5),
                "spacing_m": props.get("spacing_m", 1.0),
                "species": props.get("species", ""),
            })
        m.statusBar().showMessage("Redo: placed hedgerow", 2000)

    def _undo_place_custom_shape(self, entry):
        m = self._main
        sid = entry["shape_id"]
        m.map_widget.undo_custom_shape_by_id(sid)
        self._stash_removed(
            entry,
            lambda f: f.get("properties", {}).get("shape_id") == sid,
            single=False)
        label = entry.get("label") or entry.get("shape_type") or "shape"
        m.statusBar().showMessage(f"Undo: removed {label}", 2000)

    def _redo_place_custom_shape(self, entry):
        m = self._main
        for f in self._restore_stashed(entry):
            sh = project_io.feature_to_shape(f)
            if sh:
                m.map_widget.load_shape(sh)
        label = entry.get("label") or entry.get("shape_type") or "shape"
        m.statusBar().showMessage(f"Redo: placed {label}", 2000)

    # ── move handlers (entries carry both endpoints — no stash needed) ──────

    def _move_one(self, pid, from_lat, from_lng, to_lat, to_lng):
        m = self._main
        m.map_widget.revert_plant_position(pid, from_lat, from_lng,
                                           to_lat, to_lng)
        m._store.move_plant(pid, from_lat, from_lng, to_lat, to_lng)

    def _undo_move_plant(self, entry):
        self._move_one(entry["plant_id"],
                       float(entry["new_lat"]), float(entry["new_lng"]),
                       float(entry["old_lat"]), float(entry["old_lng"]))
        self._main.statusBar().showMessage("Undo: plant move", 2000)

    def _redo_move_plant(self, entry):
        self._move_one(entry["plant_id"],
                       float(entry["old_lat"]), float(entry["old_lng"]),
                       float(entry["new_lat"]), float(entry["new_lng"]))
        self._main.statusBar().showMessage("Redo: plant move", 2000)

    def _move_group(self, entry, *, forward: bool):
        originals = entry.get("originals") or []
        moved = entry.get("moved") or []
        moved_by_id = {mv.get("markerId"): mv for mv in moved}
        n = 0
        for orig in originals:
            new = moved_by_id.get(orig.get("markerId"))
            if not new:
                continue
            pid = int(orig.get("plantId") or 0)
            ol, og = float(orig.get("lat") or 0.0), float(orig.get("lng") or 0.0)
            nl, ng = float(new.get("lat") or 0.0), float(new.get("lng") or 0.0)
            if forward:
                self._move_one(pid, ol, og, nl, ng)
            else:
                self._move_one(pid, nl, ng, ol, og)
            n += 1
        return n

    def _undo_move_plant_group(self, entry):
        n = self._move_group(entry, forward=False)
        self._main.statusBar().showMessage(
            f"Undo: polyculture move ({n} plants)", 2000)

    def _redo_move_plant_group(self, entry):
        n = self._move_group(entry, forward=True)
        self._main.statusBar().showMessage(
            f"Redo: polyculture move ({n} plants)", 2000)

    def _undo_move_selection(self, entry):
        n = self._move_group(entry, forward=False)
        self._main.statusBar().showMessage(
            f"Undo: selection move ({n} plants)", 2000)

    def _redo_move_selection(self, entry):
        n = self._move_group(entry, forward=True)
        self._main.statusBar().showMessage(
            f"Redo: selection move ({n} plants)", 2000)

    _HANDLERS = {
        "place_plant": (_undo_place_plant, _redo_place_plant),
        "place_structure": (_undo_place_structure, _redo_place_structure),
        "place_boundary": (_undo_place_boundary, _redo_place_boundary),
        "place_contour": (_undo_place_contour, _redo_place_contour),
        "place_hedgerow": (_undo_place_hedgerow, _redo_place_hedgerow),
        "place_custom_shape": (_undo_place_custom_shape,
                               _redo_place_custom_shape),
        "move_plant": (_undo_move_plant, _redo_move_plant),
        "move_plant_group": (_undo_move_plant_group, _redo_move_plant_group),
        "move_selection": (_undo_move_selection, _redo_move_selection),
        "snapshot": (_undo_snapshot, _redo_snapshot),
    }
