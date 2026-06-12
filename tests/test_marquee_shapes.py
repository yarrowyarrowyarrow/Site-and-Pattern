"""
tests/test_marquee_shapes.py

V1.64 — drag-select (marquee) covers shapes: OSM buildings, shade-casting
footprints and custom area shapes are selectable, highlightable and
deletable alongside plants/structures/boundaries. Two layers of coverage:

  • Source-level tripwires on the split map JS (same approach as
    tests/test_bridge_contract.py): the marquee hit-test, selection
    identity, selection visuals and delete dispatch must all handle the
    'shape' kind, and a modifier-click on a shape polygon must toggle
    selection.
  • Behaviour tests for MapEventRouter._on_shape_removed — feature
    removal by shape_id, and the shade refresh that must follow when the
    removed shape was a shade caster (its shadow has to disappear with it).
"""

import os
import re
import sys
import unittest
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.controllers.map_events import MapEventRouter  # noqa: E402

_MAP_DIR = Path(__file__).resolve().parent.parent / "html" / "map"


def _js(name: str) -> str:
    return (_MAP_DIR / name).read_text(encoding="utf-8")


def _function_body(source: str, name: str) -> str:
    """Slice from a function's declaration to the next top-level function.
    The split map JS declares its functions at a fixed 4-space indent, so
    this is a reliable, parser-free way to scope assertions."""
    m = re.search(r"function " + re.escape(name) + r"\b.*?\n    function ",
                  source, re.S)
    assert m is not None, f"{name} not found in map JS"
    return m.group(0)


class TestMarqueeShapeJsContract(unittest.TestCase):
    """Source tripwires: the selection model must keep handling 'shape'."""

    def test_same_selectable_knows_shapes(self):
        self.assertIn("a.shapeId === b.shapeId", _js("01-core.js"))

    def test_marquee_hit_test_covers_shape_layers(self):
        body = _function_body(_js("01-core.js"), "_marqueeHitTest")
        self.assertIn("shapeLayers", body)
        self.assertIn("kind: 'shape'", body)

    def test_selection_visuals_style_shapes(self):
        body = _function_body(_js("01-core.js"), "_refreshSelectionVisuals")
        self.assertIn("shapeLayers", body)

    def test_delete_selected_dispatches_shapes(self):
        body = _function_body(_js("01-core.js"), "deleteSelected")
        self.assertIn("item.kind === 'shape'", body)
        self.assertIn("bridge.onShapeRemoved", body)

    def test_modifier_click_toggles_shape_selection(self):
        self.assertIn("toggleSelection({ kind: 'shape', shapeId: id })",
                      _js("05-features.js"))


class _FakeStatusBar:
    def showMessage(self, *_a, **_k):
        pass


class _FakeMain:
    """Minimal stand-in for MainWindow exposing only what the handler uses."""

    def __init__(self, project):
        self._project = project
        self.modified = 0

    def _mark_modified(self):
        self.modified += 1

    def statusBar(self):
        return _FakeStatusBar()


def _shape_feature(shape_id, *, cast_shade):
    props = {
        "element_type": "canopy_footprint" if cast_shade else "custom_shape",
        "shape_id": shape_id,
    }
    if cast_shade:
        props["cast_shade"] = True
        props["height_m"] = 5.0
    return {
        "type": "Feature",
        "geometry": {"type": "Polygon",
                     "coordinates": [[[-113.0, 53.0], [-113.0, 53.0001],
                                      [-113.0001, 53.0001], [-113.0, 53.0]]]},
        "properties": props,
    }


class TestShapeRemoved(unittest.TestCase):

    def _router(self, features):
        main = _FakeMain({"features": features})
        router = MapEventRouter(main)
        refreshes = []
        router._refresh_shade_if_active = lambda: refreshes.append(1)
        return main, router, refreshes

    def test_removes_feature_by_shape_id(self):
        main, router, _ = self._router([
            _shape_feature("s1", cast_shade=False),
            _shape_feature("s2", cast_shade=False),
        ])
        router._on_shape_removed("s1")
        ids = [f["properties"]["shape_id"] for f in main._project["features"]]
        self.assertEqual(ids, ["s2"])
        self.assertEqual(main.modified, 1)

    def test_caster_removal_refreshes_shade(self):
        main, router, refreshes = self._router(
            [_shape_feature("b1", cast_shade=True)])
        router._on_shape_removed("b1")
        self.assertEqual(main._project["features"], [])
        self.assertEqual(len(refreshes), 1)

    def test_plain_shape_removal_skips_shade_refresh(self):
        main, router, refreshes = self._router(
            [_shape_feature("s1", cast_shade=False)])
        router._on_shape_removed("s1")
        self.assertEqual(main._project["features"], [])
        self.assertEqual(len(refreshes), 0)


if __name__ == "__main__":
    unittest.main()
