"""
tests/test_pin_zoom.py — setting the pin brings the yard into view (V3.19, QF-2).

R7 of the first review: after Pin Drop the map stayed at city scale (zoom 12, a
2 km scale bar), so drawing the boundary, the next step, started seven zoom
levels from the yard. A chosen address went to zoom 17 whatever the view, which
zoomed a person already closer back out.

Now a Pin Drop click and a chosen address ask the page for zoom 19, and the page
decides (``zoomToSitePin``, html/map/06-overlays.js), because only it knows the
zoom it is at now: never out, and when already closer, a pan only if the pin is
off screen. ``placeSitePin`` itself never moves the map, so a design opened, an
undo or a dragged pin, which all come back through it, leave the view alone.
The page's decision runs in node against a stubbed map, as
tests/test_fit_when_shown.py runs 02-boundary.js.
"""

import json
import os
import pathlib
import shutil
import subprocess
import sys
import unittest
from types import SimpleNamespace
from unittest import mock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src import map_js  # noqa: E402
from src.controllers.map_events import PIN_ZOOM, MapEventRouter  # noqa: E402

_OVERLAYS = (pathlib.Path(__file__).resolve().parent.parent
             / "html" / "map" / "06-overlays.js")


def _function(name: str) -> str:
    """One top-level function of 06-overlays.js, by the file's indentation."""
    src = _OVERLAYS.read_text(encoding="utf-8")
    start = src.index(f"function {name}(")
    return src[start:src.index("\n    }\n", start) + 6]


def _node():
    return shutil.which("node") or shutil.which("nodejs")


_STUBS = r"""
var calls = [];
var zoom = 12, inView = true;
var map = {
  getZoom: function () { return zoom; },
  getBounds: function () { return {contains: function () { return inView; }}; },
  setView: function (c, z) { calls.push(['setView', c, z]); },
  panTo: function (c) { calls.push(['panTo', c]); }
};
"""


def _zoom_from(current: float, pin_in_view: bool):
    """zoomToSitePin(53.52, -113.49, PIN_ZOOM) on a map at ``current``."""
    script = "\n".join([
        _STUBS,
        _function("sitePinView"),
        _function("zoomToSitePin"),
        f"zoom = {json.dumps(current)}; inView = {json.dumps(pin_in_view)};",
        f"zoomToSitePin(53.52, -113.49, {PIN_ZOOM});",
        "console.log(JSON.stringify(calls));",
    ])
    proc = subprocess.run([_node(), "-"], input=script, capture_output=True,
                          text=True, timeout=60, encoding="utf-8")
    if proc.returncode != 0:
        raise AssertionError(f"node failed: {proc.stderr}")
    return json.loads(proc.stdout)


class TestTheZoom(unittest.TestCase):

    def test_is_about_yard_scale(self):
        """The accepted bar: a pin leaves the map at 18 or closer."""
        self.assertGreaterEqual(PIN_ZOOM, 18)
        self.assertLessEqual(PIN_ZOOM, 19)   # the street map's deepest tiles

    def test_the_builder_names_the_page_function(self):
        self.assertEqual(map_js.zoom_to_site_pin(53.5, -113.5, 19),
                         "zoomToSitePin(53.5, -113.5, 19);")
        self.assertIn("function zoomToSitePin(",
                      _OVERLAYS.read_text(encoding="utf-8"))

    def test_placing_the_pin_never_moves_the_map(self):
        """An open and an undo redraw the pin through placeSitePin: if it
        moved the map, every undo would throw the view back to the pin."""
        body = _function("placeSitePin")
        for move in ("setView", "zoomToSitePin", "panTo", "fitBounds", "flyTo"):
            self.assertNotIn(move, body)


@unittest.skipIf(_node() is None, "no node binary")
class TestThePageDecides(unittest.TestCase):

    def test_from_city_scale_it_zooms_to_the_yard(self):
        self.assertEqual(_zoom_from(12, True),
                         [["setView", [53.52, -113.49], PIN_ZOOM]])

    def test_a_fraction_short_still_zooms(self):
        """The map's zoom snaps to tenths (01-core.js), so 18.9 is a real zoom."""
        self.assertEqual(_zoom_from(18.9, True),
                         [["setView", [53.52, -113.49], PIN_ZOOM]])

    def test_never_zooms_out(self):
        self.assertEqual(_zoom_from(21.5, True), [])
        self.assertEqual(_zoom_from(PIN_ZOOM, True), [])

    def test_closer_with_the_pin_off_screen_pans_at_the_same_zoom(self):
        self.assertEqual(_zoom_from(21.5, False),
                         [["panTo", [53.52, -113.49]]])


class _Main(SimpleNamespace):
    """What the pin handlers touch on the window, and nothing more."""

    def __init__(self):
        super().__init__(
            _project={"properties": {"site_config": {}}},
            _site_pin_mode=True,
            map_widget=mock.MagicMock(),
            # A page in no tab: show_panel climbs parentWidget() until None,
            # which a MagicMock never returns.
            site_panel=SimpleNamespace(
                set_pin=mock.MagicMock(),
                info_page=SimpleNamespace(parentWidget=lambda: None)),
            _mark_modified=mock.MagicMock(),
            _set_mode_label=mock.MagicMock(),
            _start_pin_reverse_geocode=mock.MagicMock(),
            _on_site_pin_click=mock.MagicMock(),
        )

    def zooms(self):
        return self.map_widget.zoom_to_site_pin.call_args_list


class TestWhoAsksForIt(unittest.TestCase):

    def test_a_pin_drop_click(self):
        main = _Main()
        MapEventRouter(main)._on_site_pin_click(53.52, -113.49)
        main.map_widget.place_site_pin.assert_called_once_with(53.52, -113.49, "")
        self.assertEqual(main.zooms(), [mock.call(53.52, -113.49, PIN_ZOOM)])

    def test_a_chosen_address(self):
        main = _Main()
        MapEventRouter(main)._on_address_resolved(53.52, -113.49, "Somewhere")
        self.assertEqual(main.zooms(), [mock.call(53.52, -113.49, PIN_ZOOM)])
        # zoom 17 whatever the view zoomed a closer person out
        main.map_widget.set_view.assert_not_called()

    def test_a_click_when_not_dropping_a_pin_does_nothing(self):
        main = _Main()
        main._site_pin_mode = False
        MapEventRouter(main)._on_site_pin_click(53.52, -113.49)
        self.assertEqual(main.zooms(), [])

    def test_not_the_pin_coming_back_from_the_page(self):
        """The page reports every pin it draws: a drag, an open, an undo and
        the reverse lookup's label all arrive here, and none of them is a
        person asking to go to the yard."""
        main = _Main()
        router = MapEventRouter(main)
        router._on_site_pin_placed(53.52, -113.49, "")
        router._on_pin_reverse_geocode_done(53.52, -113.49, "An address")
        self.assertEqual(main.zooms(), [])


if __name__ == "__main__":
    unittest.main()
