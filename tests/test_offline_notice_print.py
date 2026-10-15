"""
tests/test_offline_notice_print.py — Export PDF's map picture leaves out the
line that says the map needs an internet connection (V3.19, QF-6, from the
review of the build).

Offline, the map page says *The map needs an internet connection to load.
Your design is safe.* (html/map/11-map-furniture.js). Export PDF's map page is
a grab of that page, so the line was printed over the plan: words for the
screen, in a document. ``holdOfflineNotice`` keeps it off while the export asks
where to save and grabs the map, and puts it back after if it still applies;
``map_furniture_flow.offline_notice_held`` is the Python side. The real window
is checked in tests/test_app_smoke.py (the order of the hold, the save box and
the grab).
"""

import shutil
import unittest

from src import map_js

try:
    from src import map_furniture_flow
    _HAVE_QT = True
except Exception:                                          # noqa: BLE001
    _HAVE_QT = False


def _node():
    return shutil.which("node") or shutil.which("nodejs")


class TestTheBuilder(unittest.TestCase):

    def test_what_the_page_is_told(self):
        self.assertEqual(map_js.hold_offline_notice(True),
                         "holdOfflineNotice(true);")
        self.assertEqual(map_js.hold_offline_notice(False),
                         "holdOfflineNotice(false);")


@unittest.skipIf(_node() is None, "no node binary")
class TestTheHold(unittest.TestCase):
    """11-map-furniture.js in node, with test_offline_map's stubs."""

    def _run(self, steps):
        from tests.test_offline_map import _run
        return _run(steps)

    def test_a_line_shown_is_held_off_and_comes_back(self):
        out = self._run("""
            var layer = stubLayer();
            watchBaseTiles(layer, null);
            layer.fire('tileerror'); layer.fire('load');
            var before = !!shown();
            holdOfflineNotice(true);
            var held = !!shown();
            holdOfflineNotice(false);
            console.log(JSON.stringify({before: before, held: held,
                                        after: !!shown()}));""")
        self.assertEqual(out, {"before": True, "held": False, "after": True})

    def test_a_line_that_went_while_held_stays_gone(self):
        """A tile that drew during the export: the line no longer applies."""
        out = self._run("""
            var layer = stubLayer();
            watchBaseTiles(layer, null);
            layer.fire('tileerror'); layer.fire('load');
            holdOfflineNotice(true);
            layer.draw(1); layer.fire('tileload');
            holdOfflineNotice(false);
            console.log(JSON.stringify({after: !!shown()}));""")
        self.assertEqual(out, {"after": False})

    def test_a_line_that_came_while_held_shows_after(self):
        out = self._run("""
            var layer = stubLayer();
            watchBaseTiles(layer, null);
            holdOfflineNotice(true);
            layer.fire('tileerror'); layer.fire('load');
            var held = !!shown();
            holdOfflineNotice(false);
            console.log(JSON.stringify({held: held, after: !!shown()}));""")
        self.assertEqual(out, {"held": False, "after": True})


@unittest.skipUnless(_HAVE_QT, "PyQt6 not installed in this env")
class TestTheFlow(unittest.TestCase):

    def _main(self, ready):
        calls = []

        class _Map:
            is_ready = ready

            def hold_offline_notice(self, held):
                calls.append(held)

        class _Main:
            map_widget = _Map()

        return _Main(), calls

    def test_held_for_the_block_and_let_go_after(self):
        main, calls = self._main(True)
        with map_furniture_flow.offline_notice_held(main):
            self.assertEqual(calls, [True])
        self.assertEqual(calls, [True, False])

    def test_let_go_when_the_export_fails(self):
        main, calls = self._main(True)
        with self.assertRaises(RuntimeError):
            with map_furniture_flow.offline_notice_held(main):
                raise RuntimeError("the save box failed")
        self.assertEqual(calls, [True, False])

    def test_a_page_not_loaded_is_told_nothing(self):
        main, calls = self._main(False)
        with map_furniture_flow.offline_notice_held(main):
            pass
        self.assertEqual(calls, [])


if __name__ == "__main__":
    unittest.main()
