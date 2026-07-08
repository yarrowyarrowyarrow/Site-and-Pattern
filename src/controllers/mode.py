"""
src/controllers/mode.py — Drawing-mode controller.

Owns the small, self-contained ``_enter_*_mode`` methods that just flip
``MainWindow._current_mode``, push the corresponding mode call into
``MapWidget``, and update the status-bar label.

Extracted from ``src/app.py:MainWindow`` in Chunk 5 of the strengthening
roadmap. The complex mode helpers — ``_enter_plant_mode`` (plant DB
lookup + polyculture-mix recipe handling), ``_enter_polyculture_mode``
+ ``_enter_polyculture_pattern_mode`` (MapBridge signal-connect
handshake), ``_cancel_draw`` (site-pin signal disconnect), and
``_enter_site_pin_mode`` — stay on MainWindow until a follow-up PR
tackles them with the same shim pattern.

The smoke test in tests/test_app_smoke.py keeps pinning all the
``_enter_*_mode`` method names on MainWindow; the extracted ones get
shims, the others stay native.
"""

from __future__ import annotations


class ModeController:
    """Status-bar label + simple drawing-mode toggles.

    Holds a MainWindow reference so it can read ``map_widget``,
    ``toolbar``, and the ``_sb_mode`` QLabel + mutate the
    ``_current_mode`` flag.
    """

    def __init__(self, main_window):
        self._main = main_window

    def _set_mode_label(self, text: str):
        self._main._sb_mode.setText(f"Mode: {text}")

    def _enter_boundary_mode(self):
        self._main._current_mode = 'boundary'
        self._main.map_widget.set_mode('boundary')
        self._set_mode_label(
            "Drawing boundary — click to add points, double-click or click first point to close"
        )

    def _enter_measure_mode(self):
        self._main._current_mode = 'measure'
        self._main.map_widget.set_mode('measure')
        self._set_mode_label("Measure — click two points to see distance")

    def _enter_annotate_mode(self):
        self._main._current_mode = 'annotate'
        self._main.map_widget.set_mode('annotate')
        self._set_mode_label("Annotate — click map to place a note")

    def _enter_select_mode(self):
        self._main._current_mode = 'select'
        self._main.map_widget.set_mode('select')
        self._set_mode_label(
            "Select — drag a box to select; drag the selection to move it, "
            "or press Delete"
        )

    def _enter_fill_mode(self):
        self._main._current_mode = 'fill'
        self._main.map_widget.set_mode('fill')
        self._main.toolbar.reset_draw_buttons()
        self._set_mode_label(
            "Fill area — click to draw a polygon, double-click to finish; "
            "the plants scatter inside it"
        )

    def _enter_structure_mode(self, struct_def: dict):
        self._main._current_mode = 'structure'
        # Stash height for existing tree/building marks (V1.49) — the JS
        # placement callback only echoes (id, name, lat, lng, size), so the
        # shade-relevant height is remembered here and read back in
        # map_events._on_existing_feature_placed. Tree foliage rides the same
        # stash for the leaf-off winter-shade model (V2.13).
        self._main._existing_feature_height_m = struct_def.get("height_m")
        self._main._existing_feature_foliage = struct_def.get("tree_foliage")
        self._main.map_widget.set_structure_mode(struct_def)
        self._main.toolbar.reset_draw_buttons()
        self._set_mode_label(
            f"Placing: {struct_def.get('icon', '')} {struct_def.get('name', 'Structure')} — click map, Esc to cancel"
        )

    def _enter_hedgerow_mode(self, hedge_config: dict):
        self._main._current_mode = 'hedgerow'
        self._main.map_widget.set_hedgerow_mode(hedge_config)
        self._main.toolbar.reset_draw_buttons()
        self._set_mode_label(
            "Drawing hedgerow — click to add points, double-click to finish"
        )

    def _enter_shape_mode(self, shape_config: dict):
        self._main._current_mode = 'shape'
        # Foliage stash for drawn tree canopies — the shape-complete callback
        # doesn't echo custom config fields (V2.13, mirrors the height stash
        # in _enter_structure_mode).
        self._main._tree_canopy_foliage = shape_config.get("tree_foliage")
        self._main.map_widget.set_shape_mode(shape_config)
        self._main.toolbar.reset_draw_buttons()
        self._set_mode_label(
            "Drawing shape — click points, double-click or click first point to close"
        )
