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

import json
import os
from contextlib import contextmanager

from PyQt6.QtCore import QTimer
from PyQt6.QtWidgets import QFileDialog, QMessageBox

import src.project as project_io
from src.branding import APP_NAME
from src.log import get_logger

_log = get_logger(__name__)


def autosave_path() -> str:
    """The single crash-recovery autosave file. Fixed path (not per-project)
    so the startup recovery check knows where to look; the design's real
    path is stamped inside (``properties._autosave_source_path``)."""
    return os.path.join(os.path.expanduser("~"),
                        ".site-and-pattern_autosave.perma.geojson")


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
        # Shade overlay turns on via a worker callback (async), so its
        # turn-on undo step is opened here (begin_shade_undo) and pushed from
        # the ready callback (commit_shade_undo) — see Part 3.
        self._shade_pending_before = None

    # ── Modified flag + window title ─────────────────────────────────────────

    def _mark_modified(self):
        self._main._modified = True
        if not self._main.windowTitle().endswith(' *'):
            self._main.setWindowTitle(self._main.windowTitle() + ' *')
        # Shade-tab caster inventory (V2.13): every feature mutation lands
        # here, so the "Casting shade: …" line stays live after imports,
        # marks, draws, removals and undo. Cheap pure feature scan.
        try:
            self._main.site_panel.update_caster_summary(self._main._project)
        except Exception:  # noqa: BLE001 — a status line must never block a save flag
            pass

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
            # The design is now durably on disk — a crash-recovery copy from
            # before this save would only offer to roll the user back.
            self.clear_autosave()
        except Exception as exc:
            _log.exception("save failed: %s", path)
            QMessageBox.critical(self._main, "Save failed", str(exc))

    # ── Autosave + crash recovery ─────────────────────────────────────────────
    # The timer writes a recovery copy (with the design's real path stamped
    # inside) whenever there are unsaved changes; a clean save or clean exit
    # deletes it. If it's still there at the next launch, the previous
    # session died with unsaved work — maybe_offer_autosave_recovery (wired
    # to the map bridge's map_ready in app.py, so the restore can render)
    # offers it back exactly once.

    def _start_autosave(self):
        self._main._autosave_timer = QTimer(self._main)
        self._main._autosave_timer.setInterval(self._main.AUTOSAVE_INTERVAL_MS)
        self._main._autosave_timer.timeout.connect(self._autosave)
        self._main._autosave_timer.start()

    def _autosave(self):
        if not self._main._modified:
            return
        # Stamp the source path on shallow copies so the live project (and
        # therefore real saves) never carry the recovery-only key.
        data = dict(self._main._project)
        props = dict(data.get("properties") or {})
        props["_autosave_source_path"] = self._main._project_path or ""
        data["properties"] = props
        try:
            project_io.save_project(data, autosave_path())
        except Exception:
            _log.warning("autosave failed", exc_info=True)

    def clear_autosave(self):
        try:
            os.unlink(autosave_path())
        except FileNotFoundError:
            pass
        except OSError:
            _log.warning("could not remove autosave file", exc_info=True)

    def maybe_offer_autosave_recovery(self):
        """If the last session left an autosave behind, offer to restore it.
        One-shot per launch; the file is consumed (deleted) either way —
        declining means the user chose the on-disk version."""
        if getattr(self, "_recovery_checked", False):
            return
        self._recovery_checked = True
        path = autosave_path()
        if not os.path.exists(path):
            return
        try:
            data = project_io.load_project(path)
            props = data.get("properties") or {}
            source = props.pop("_autosave_source_path", "") or ""
            name = props.get("project_name", "Untitled Design")
        except Exception:
            _log.warning("unreadable autosave file — discarding", exc_info=True)
            self.clear_autosave()
            return
        r = QMessageBox.question(
            self._main, "Restore autosaved design?",
            f"Site & Pattern closed without saving last time.\n\n"
            f"An autosaved copy of “{name}” was recovered"
            + (f" (last saved to:\n{source})" if source else "")
            + ".\n\nRestore it now?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
        if r == QMessageBox.StandardButton.Yes:
            m = self._main
            m._project = data          # → ProjectStore.set_project
            m._project_path = source if source and os.path.exists(source) else None
            m._modified = True         # recovered work is unsaved by definition
            self.render_project_to_map(fit_view=True)
            m.setWindowTitle(f"{APP_NAME} — {name} *")
            m.statusBar().showMessage("Recovered autosaved design", 5000)
            _log.info("restored autosave (source=%s)", source or "unsaved")
        self.clear_autosave()

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
        self._sync_undo_actions()

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
        self._sync_undo_actions()
        self._mark_modified()

    def _sync_undo_actions(self):
        """Reflect the undo/redo stacks on both the Edit-menu actions and the
        toolbar buttons, so each greys out when its stack is empty."""
        m = self._main
        has_undo, has_redo = bool(m._undo_stack), bool(m._redo_stack)
        m._act_undo.setEnabled(has_undo)
        m._act_redo.setEnabled(has_redo)
        tb = getattr(m, "toolbar", None)
        if tb is not None:
            tb.set_undo_redo_enabled(has_undo, has_redo)

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
        """Record a snapshot undo step around a block that mutates the
        project's features and/or an analysis-overlay toggle. Re-entrant: only
        the outermost checkpoint snapshots and pushes, so a decorated helper
        called from a decorated entry point yields a single undo entry. Records
        nothing when the block raises or leaves the captured state unchanged."""
        outer = self._cp_depth == 0
        if outer:
            self._cp_before = self._capture_state()
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
                    after = self._capture_state()
                    if before != after:
                        self._push_undo({"action": "snapshot",
                                         "label": label,
                                         "before": before, "after": after})

    # ── captured state = features + a compact analysis-overlay view-state ─────
    # Features are snapshotted as ONE canonical JSON string, not a deepcopy
    # tree (V2.22). Same information (features are JSON by definition — they
    # ARE the saved file), but: ~several× less memory per entry than a
    # Python object graph, immune to aliasing by construction (strings are
    # immutable), before/after comparison is a string compare, and identical
    # consecutive snapshots share one string object (the interning below) —
    # so a 50-deep stack over a large imported project no longer holds up to
    # 100 full deep copies of every feature.

    def _capture_state(self) -> dict:
        feats_json = json.dumps(
            self._main._project.get("features", []),
            separators=(",", ":"), sort_keys=True, default=str)
        # Chain-share: consecutive captures of unchanged features reuse the
        # previous string object instead of holding a duplicate.
        if feats_json == getattr(self, "_last_feats_json", None):
            feats_json = self._last_feats_json
        else:
            self._last_feats_json = feats_json
        return {
            "features_json": feats_json,
            "view": self._capture_view_state(),
        }

    def _capture_view_state(self) -> dict:
        """The transient analysis overlays that aren't part of project features
        (shade, live wind-shadow, sun path, sun sectors, site pin). Scalars are
        read fresh; the shade payload is held by reference (never mutated in
        place), so this is cheap to call on every checkpoint."""
        m = self._main
        sc = (m._project.get("properties", {}) or {}).get("site_config", {}) or {}
        return {
            "shade": {
                "active": bool(getattr(m, "_shade_overlay_active", False)),
                "payload": getattr(m, "_last_shade_payload", None),
                "opacity": getattr(m, "_shade_opacity", 0.5),
            },
            "wind": {
                "on": bool(getattr(m, "_wind_shadow_on", False)),
                "angle": getattr(m, "_wind_shadow_angle", None),
            },
            "sun": getattr(m, "_active_sun_state", None),
            "sectors": getattr(m, "_active_sector_state", None),
            "pin": {"lat": sc.get("latitude"), "lng": sc.get("longitude"),
                    "label": sc.get("pin_label")},
        }

    # ── shade turn-on bridges the async worker callback ──────────────────────

    def begin_shade_undo(self):
        """Stash pre-toggle state when a shade request starts; the matching
        commit (from the worker's ready callback) pushes the undo step iff the
        overlay actually turned ON (so recomputes / time-scrubs don't spam)."""
        self._shade_pending_before = self._capture_state()

    def commit_shade_undo(self):
        before, self._shade_pending_before = self._shade_pending_before, None
        if before is None:
            return
        was_on = before["view"]["shade"]["active"]
        now_on = bool(getattr(self._main, "_shade_overlay_active", False))
        if not was_on and now_on:                 # off → on only
            after = self._capture_state()
            if before != after:
                self._push_undo({"action": "snapshot", "label": "show shade",
                                 "before": before, "after": after})

    def _undo_snapshot(self, entry: dict):
        self._apply_snapshot(entry["before"])
        self._main.statusBar().showMessage(
            f"Undo: {entry.get('label') or 'change'}", 2000)

    def _redo_snapshot(self, entry: dict):
        self._apply_snapshot(entry["after"])
        self._main.statusBar().showMessage(
            f"Redo: {entry.get('label') or 'change'}", 2000)

    def _apply_snapshot(self, side: dict):
        """Restore one side of a snapshot: features + the site pin (via
        site_config, re-placed by the re-render) + the transient overlays."""
        m = self._main
        view = side.get("view") or {}
        pin = view.get("pin") or {}
        sc = m._project.setdefault("properties", {}).setdefault("site_config", {})
        for state_key, sc_key in (("lat", "latitude"), ("lng", "longitude"),
                                  ("label", "pin_label")):
            val = pin.get(state_key)
            if val is None:
                sc.pop(sc_key, None)
            else:
                sc[sc_key] = val
        # Decode a fresh feature tree (the JSON string in the entry stays
        # pristine no matter what later gestures do to the live objects).
        m._project["features"] = json.loads(side["features_json"])
        self._last_feats_json = side["features_json"]
        m._store.rebuild_index()
        self.render_project_to_map(fit_view=False)
        self._apply_view_state(view)

    def _apply_view_state(self, target: dict):
        """Re-apply the transient overlays to ``target``. Called right after
        render_project_to_map, which (via clear_all) has just wiped most JS
        overlays — so each overlay is set unconditionally (draw or clear)
        rather than diffed against now-stale Python flags."""
        m = self._main

        tw = target.get("wind") or {}
        import src.wind_shadow_flow as wind_shadow_flow
        if tw.get("angle") is not None:            # None → keep the flow default
            m._wind_shadow_angle = tw.get("angle")
        wind_shadow_flow.enable(m, bool(tw.get("on")))

        ts = target.get("shade") or {}
        m._shade_overlay_active = bool(ts.get("active"))
        m._shade_opacity = ts.get("opacity", getattr(m, "_shade_opacity", 0.5))
        m._last_shade_payload = ts.get("payload")
        if ts.get("active"):
            self._redraw_shade(ts.get("payload"), m._shade_opacity)
        else:
            m.map_widget.clear_shade_overlay()
            m.map_widget.clear_shadow_polygons()

        tsun = target.get("sun")
        if tsun:
            m._render_sun_path(tsun[0], tsun[1], tsun[2])
        else:
            m.map_widget.clear_sun_path()
            m._active_sun_state = None

        tsec = target.get("sectors")
        if tsec:
            m.map_widget.draw_sectors(tsec[0], tsec[1], tsec[2])
            m._active_sector_state = tsec
        else:
            m.map_widget.clear_sectors()
            m._active_sector_state = None

    def _redraw_shade(self, payload, opacity):
        """Redraw a cached shade overlay synchronously (no worker) — raster or
        true-shape vector, matching how it was first drawn."""
        m = self._main
        if not payload:
            m.map_widget.clear_shade_overlay()
            m.map_widget.clear_shadow_polygons()
            return
        if payload.get("kind") == "vector":
            m.map_widget.clear_shade_overlay()
            m.map_widget.draw_shadow_polygons(
                payload["polygons"], payload.get("bbox"), opacity)
        else:
            m.map_widget.clear_shadow_polygons()
            m.map_widget.draw_shade_overlay(
                payload["data_url"], payload.get("bbox"), opacity)

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
        if data.get("slope_overlay") or data.get("water_overlay"):
            layers = []
            if data.get("slope_overlay"):
                layers.append("Slope ramp")
            if data.get("water_overlay"):
                layers.append("water overlay")
            m.site_panel.set_auto_terrain_status(
                " and ".join(layers)
                + " not loaded — click Generate to recompute.")

        # Site pin (clearAll wiped it) + photoreal splat backdrop, both read
        # from the project so undo of an import that removed them clears them.
        sc = proj.get("properties", {}).get("site_config") or {}
        plat, plng = sc.get("latitude"), sc.get("longitude")
        if plat is not None and plng is not None:
            m.map_widget.place_site_pin(plat, plng, sc.get("pin_label", ""))
        from src import splat_flow
        splat_flow.restore_splat_overlay(m)
        # Site photo underlay (F24) — same story: redraw from the project so
        # undo of an import that added/removed it stays in sync.
        from src import site_photo_flow
        site_photo_flow.restore_site_photo(m)

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
