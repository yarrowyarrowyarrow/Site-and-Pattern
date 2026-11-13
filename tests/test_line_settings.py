"""
tests/test_line_settings.py — a drawn line keeps what the person set (V3.45).

Draw › Shape asks a hedge's or a fence's width, plant spacing and colour, and
the map draws the line with them. But the map's callback when the line is
finished carries only its points, species, style and length, and the handler
wrote ``width_m: 1.5``, ``spacing_m: 1.0`` and ``color: "#4caf50"`` whatever
had been set: a 3 m windbreak came back 1.5 m wide and green the next time the
design was opened. Found in V3.45, when the 3D preview began to draw a line as
wide as the design says it is.

The settings are stashed when the tool is armed (as a drawn tree canopy's
foliage has been since V2.13) and read when the line is finished. No Qt: the
two controllers are plain objects over a main window.
"""

import json
import os
import sys
import unittest
from unittest import mock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.controllers.map_events import MapEventRouter        # noqa: E402
from src.controllers.mode import ModeController              # noqa: E402

_POINTS = json.dumps([[53.5, -113.5], [53.5001, -113.5]])


def _main():
    main = mock.MagicMock()
    main._project = {"type": "FeatureCollection", "features": []}
    del main._hedge_config                  # a window that never armed the tool
    return main


def _finish(main, style="windbreak"):
    MapEventRouter(main)._on_hedgerow_complete(
        "h1", _POINTS, "Caragana", style, 11.1, 11)
    return main._project["features"][-1]["properties"]


class ALineKeepsItsSettings(unittest.TestCase):

    def test_the_width_spacing_and_colour_are_saved(self):
        main = _main()
        ModeController(main)._enter_hedgerow_mode(
            {"style": "windbreak", "width_m": 3.0, "spacing_m": 2.5,
             "species": "Caragana", "color": "#8d6e63"})
        props = _finish(main)
        self.assertEqual((props["width_m"], props["spacing_m"],
                          props["color"]), (3.0, 2.5, "#8d6e63"))
        self.assertEqual((props["style"], props["species"]),
                         ("windbreak", "Caragana"))

    def test_the_map_is_still_told_the_same_settings(self):
        main = _main()
        cfg = {"style": "hedge", "width_m": 2.0, "spacing_m": 0.5,
               "color": "#4caf50"}
        ModeController(main)._enter_hedgerow_mode(cfg)
        main.map_widget.set_hedgerow_mode.assert_called_once_with(cfg)

    def test_the_next_line_does_not_inherit_the_last_ones(self):
        main = _main()
        mode = ModeController(main)
        mode._enter_hedgerow_mode({"style": "windbreak", "width_m": 3.0,
                                   "spacing_m": 2.5, "color": "#8d6e63"})
        _finish(main)
        mode._enter_hedgerow_mode({"style": "fence", "width_m": 1.0,
                                   "spacing_m": 1.0, "color": "#795548"})
        props = _finish(main, "fence")
        self.assertEqual((props["width_m"], props["color"]),
                         (1.0, "#795548"))

    def test_a_line_finished_with_nothing_stashed_gets_the_old_defaults(self):
        """A callback that arrives with no tool armed (a replayed map event):
        nothing fails, and the line is as it always was."""
        props = _finish(_main(), "hedge")
        self.assertEqual((props["width_m"], props["spacing_m"],
                          props["color"]), (1.5, 1.0, "#4caf50"))
        main = _main()
        main._hedge_config = {"style": "hedge"}          # a config with gaps
        props = _finish(main, "hedge")
        self.assertEqual((props["width_m"], props["spacing_m"],
                          props["color"]), (1.5, 1.0, "#4caf50"))

    def test_the_3d_scene_draws_the_width_that_was_set(self):
        from src.scene_contract import build_scene
        main = _main()
        ModeController(main)._enter_hedgerow_mode(
            {"style": "windbreak", "width_m": 3.0, "spacing_m": 2.5,
             "color": "#8d6e63"})
        _finish(main)
        scene = build_scene(main._project, get_plant=lambda _i: {}, wind=False)
        self.assertEqual(scene["lines"][0]["width_m"], 3.0)


if __name__ == "__main__":
    unittest.main()
