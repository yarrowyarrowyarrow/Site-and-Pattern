"""
tests/test_outline_crosses_itself.py — an outline that crosses itself is not
kept (V3.19, QF-14, R29).

The review drew a bow-tie and the app stored it, with an area from the
shoelace formula, which for a figure that crosses itself means nothing. Now
``src/outline_check.py`` (shapely's ``is_simple``) decides, and the map
handler (``MapEventRouter``) refuses: a drawn outline is not stored and comes
off the map; a corner dragged across another side is put back, on the map and
in the design. Both say why in a box.

The handlers run against a fake main, as tests/test_map_events_drag.py runs
them, so no window is built. The JS that puts an edited outline back
(``restoreBoundary``) is run in the real page by tests/test_offline_map.py.
"""

import os
import sys
import unittest
from unittest import mock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from src import map_js, outline_check  # noqa: E402
from src.controllers.map_events import MapEventRouter  # noqa: E402

_LAT, _LNG, _D = 53.5461, -113.4938, 0.0002
SQUARE = [[_LAT - _D, _LNG - _D], [_LAT - _D, _LNG + _D],
          [_LAT + _D, _LNG + _D], [_LAT + _D, _LNG - _D]]
# The same four corners clicked out of order: the second and fourth sides cross.
BOW_TIE = [SQUARE[0], SQUARE[2], SQUARE[1], SQUARE[3]]


@unittest.skipUnless(outline_check._HAVE_SHAPELY, "shapely not installed")
class TestWhatCrossesItself(unittest.TestCase):

    def test_a_bow_tie_crosses_and_a_square_does_not(self):
        self.assertTrue(outline_check.crosses_itself(BOW_TIE))
        self.assertFalse(outline_check.crosses_itself(SQUARE))

    def test_a_repeated_corner_is_not_a_crossing(self):
        """An outline read back from a file repeats its first corner at the
        end; a double-click can put two corners on one spot."""
        self.assertFalse(outline_check.crosses_itself(SQUARE + [SQUARE[0]]))
        self.assertFalse(outline_check.crosses_itself(
            SQUARE[:2] + [SQUARE[1]] + SQUARE[2:]))

    def test_a_corner_that_touches_another_side(self):
        """Two loops joined at a point are not one yard either."""
        mid_south = [_LAT - _D, _LNG]
        pinched = [SQUARE[0], SQUARE[1], [_LAT + _D, _LNG], mid_south,
                   [_LAT + _D, _LNG - _D * 0.5]]
        self.assertTrue(outline_check.crosses_itself(pinched))

    def test_too_few_corners_is_not_a_crossing(self):
        self.assertFalse(outline_check.crosses_itself(SQUARE[:2]))
        self.assertFalse(outline_check.crosses_itself([]))


class TestTheRing(unittest.TestCase):

    def test_closed_once(self):
        ring = outline_check.closed_ring(SQUARE)
        self.assertEqual(len(ring), 5)
        self.assertEqual(ring[0], ring[-1])
        self.assertEqual(ring[0], [SQUARE[0][1], SQUARE[0][0]])    # lng, lat

    def test_an_edit_does_not_add_another_closing_corner(self):
        """A design read back sends its first corner again at the end; until
        V3.19 each edit closed the ring once more."""
        self.assertEqual(outline_check.closed_ring(SQUARE + [SQUARE[0]]),
                         outline_check.closed_ring(SQUARE))


class _Recorder:
    def __init__(self):
        self.calls = []

    def __getattr__(self, name):
        return lambda *a, **k: self.calls.append((name,) + a)


class _FakeMain:
    def __init__(self, features=None):
        self._project = {"features": list(features or [])}
        self.map_widget = _Recorder()
        self.toolbar = _Recorder()
        self.undo_entries, self.modified, self.labels = [], 0, []
        self._current_zone = "3a"

    def _push_undo(self, entry):
        self.undo_entries.append(entry)

    def _mark_modified(self):
        self.modified += 1

    def _set_mode_label(self, text):
        self.labels.append(text)

    def _set_zone_display(self, zone):
        self._current_zone = zone


def _boundary(bid, points):
    return {"type": "Feature",
            "geometry": {"type": "Polygon",
                         "coordinates": [outline_check.closed_ring(points)]},
            "properties": {"element_type": "property_boundary",
                           "boundary_id": bid, "color": "green"}}


@unittest.skipUnless(outline_check._HAVE_SHAPELY, "shapely not installed")
class TestTheMapHandler(unittest.TestCase):

    def setUp(self):
        self.told = []
        patcher = mock.patch.object(
            outline_check, "tell_refused",
            lambda parent, edited=False: self.told.append(edited))
        patcher.start()
        self.addCleanup(patcher.stop)

    def test_a_drawn_bow_tie_is_not_stored_and_leaves_the_map(self):
        main = _FakeMain()
        MapEventRouter(main)._on_boundary_complete("b1", BOW_TIE, "green")
        self.assertEqual(main._project["features"], [])
        self.assertEqual(main.undo_entries, [])
        self.assertEqual(main.modified, 0)
        self.assertIn(("undo_boundary", "b1"), main.map_widget.calls)
        self.assertIn(("reset_draw_buttons",), main.toolbar.calls)
        self.assertEqual(self.told, [False])

    def test_a_drawn_square_is_stored_as_before(self):
        main = _FakeMain()
        MapEventRouter(main)._on_boundary_complete("b1", SQUARE, "green")
        (f,) = main._project["features"]
        self.assertEqual(f["geometry"]["coordinates"],
                         [outline_check.closed_ring(SQUARE)])
        self.assertEqual(main.undo_entries[0]["action"], "place_boundary")
        self.assertEqual(main.map_widget.calls, [])
        self.assertEqual(self.told, [])

    def test_a_corner_dragged_across_a_side_is_put_back(self):
        kept = _boundary("b1", SQUARE)
        before = [list(p) for p in kept["geometry"]["coordinates"][0]]
        main = _FakeMain([kept])
        MapEventRouter(main)._on_boundary_geom_changed("b1", BOW_TIE)
        self.assertEqual(kept["geometry"]["coordinates"][0], before)
        self.assertEqual(main.modified, 0)
        (call,) = main.map_widget.calls
        self.assertEqual(call[0:2], ("restore_boundary", "b1"))
        self.assertEqual([list(p) for p in call[2]], SQUARE)
        self.assertEqual(self.told, [True])

    def test_an_outline_saved_crossing_itself_can_still_be_mended(self):
        """A design saved before V3.19 may hold a bow-tie. Refusing every edit
        of it would leave it unmendable, so an edit of one is kept."""
        kept = _boundary("b1", BOW_TIE)
        nudged = [[p[0] + _D * 0.1, p[1]] for p in BOW_TIE]
        main = _FakeMain([kept])
        MapEventRouter(main)._on_boundary_geom_changed("b1", nudged)
        self.assertEqual(kept["geometry"]["coordinates"],
                         [outline_check.closed_ring(nudged)])
        self.assertEqual(self.told, [])
        MapEventRouter(main)._on_boundary_geom_changed("b1", SQUARE)
        self.assertEqual(kept["geometry"]["coordinates"],
                         [outline_check.closed_ring(SQUARE)])

    def test_a_corner_moved_within_the_outline_is_kept(self):
        kept = _boundary("b1", SQUARE)
        moved = [[_LAT - _D * 1.5, _LNG - _D]] + SQUARE[1:]
        main = _FakeMain([kept])
        MapEventRouter(main)._on_boundary_geom_changed("b1", moved + [moved[0]])
        self.assertEqual(kept["geometry"]["coordinates"],
                         [outline_check.closed_ring(moved)])
        self.assertEqual(main.modified, 1)
        self.assertEqual(self.told, [])


class TestThePageIsTold(unittest.TestCase):

    def test_the_builder_and_the_page_agree(self):
        js = map_js.restore_boundary("b1", [(53.5, -113.4), (53.6, -113.5)])
        self.assertTrue(js.startswith('restoreBoundary("b1", JSON.parse('))
        self.assertIn("[[53.5, -113.4], [53.6, -113.5]]", js)
        page = (os.path.join(os.path.dirname(os.path.dirname(
            os.path.abspath(__file__))), "html", "map", "02-boundary.js"))
        with open(page, encoding="utf-8") as fh:
            self.assertIn("function restoreBoundary(id, points)", fh.read())


try:
    from PyQt6.QtWidgets import QApplication
    _HAVE_QT = True
except Exception:                                          # noqa: BLE001
    _HAVE_QT = False


@unittest.skipUnless(_HAVE_QT, "PyQt6 not installed in this env")
class TestTheWords(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls._app = QApplication.instance() or QApplication(["sp-tests"])

    def test_the_box_says_what_happened_and_what_to_do(self):
        from src import plain_messages
        shown = []
        with mock.patch.object(plain_messages, "_run",
                               lambda box: shown.append(box.text())):
            outline_check.tell_refused(None)
            outline_check.tell_refused(None, edited=True)
        self.assertEqual(shown, [outline_check.DRAWN_TEXT,
                                 outline_check.EDITED_TEXT])
        self.assertIn("crosses itself", shown[0])
        for text in shown:                       # two sentences at most (09 §1)
            self.assertLessEqual(text.count(". "), 1, text)
            self.assertNotIn("boundary", text.lower())


if __name__ == "__main__":
    unittest.main()
