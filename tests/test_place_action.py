"""
tests/test_place_action.py — looking at a list is not placing from it (F191, V2.99).

Measured on V2.98: a click on a plant's name, a click on ▶ to read its card, an
arrow key, and keyboard focus arriving in the list each armed the map, so the
next click on it planted what you had only looked at. Now a list reports two
things (``src/place_action.py``), and these tests drive them with real input:

* **place**: Enter or Return, or a double-click. Never ``activated``, which Qt
  also emits on a *single* click where the style says so (KDE's default).
* **choose**: a click that ends where it began, or an arrow key. Not focus
  arriving, not a press released elsewhere, not a click the row's delegate took
  (the plant list's ▶, which Qt 6 still reports as ``clicked``).

And the map's side: the footprint drawn under the cursor while placing
(``html/map/08-footprint.js``), run in node against the arithmetic Python uses
to put the plants down, so the ghost is where they land.

Offscreen Qt; the Qt parts skip where PyQt6 isn't importable, the JS parts where
there is no node.
"""

import json
import math
import os
import pathlib
import re
import shutil
import subprocess
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

try:
    from PyQt6.QtCore import QPoint, QStringListModel, Qt
    from PyQt6.QtTest import QTest
    from PyQt6.QtWidgets import (QApplication, QListView, QProxyStyle,
                                 QStyle, QStyledItemDelegate)
    _HAVE_QT = True
except ImportError:                                  # pragma: no cover
    _HAVE_QT = False

_ROOT = pathlib.Path(__file__).resolve().parent.parent
_MAP = _ROOT / "html" / "map"


def _node():
    return shutil.which("node") or shutil.which("nodejs")


# ── What a list reports ──────────────────────────────────────────────────────

if _HAVE_QT:
    class _TakesClicks(QStyledItemDelegate):
        """Stands in for the plant row's ▶: takes every release, says so."""
        take = False

        def editorEvent(self, event, model, option, index):
            if self.take and event.type() == event.Type.MouseButtonRelease:
                self._took = True
                return True
            return super().editorEvent(event, model, option, index)

        def took_click(self):
            took, self._took = getattr(self, "_took", False), False
            return took

    class _ClickActivates(QProxyStyle):
        """A style that activates items on one click, as KDE's does."""

        def styleHint(self, hint, option=None, widget=None, data=None):
            if hint == QStyle.StyleHint.SH_ItemView_ActivateItemOnSingleClick:
                return 1
            return super().styleHint(hint, option, widget, data)


@unittest.skipUnless(_HAVE_QT, "PyQt6 not installed in this env")
class TestListGestures(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls._app = QApplication.instance() or QApplication(["permadesign-tests"])

    def _list(self, **options):
        from src.place_action import ListGestures
        view = QListView()
        # Parented to the view: a model only Python holds dies with the view's
        # wrapper, which can go before the view does (see CLAUDE.md's table of
        # whole-run aborts, V2.98).
        view.setModel(QStringListModel([f"plant {n}" for n in range(6)], view))
        view.setItemDelegate(_TakesClicks(view))
        view.resize(240, 200)
        gestures = ListGestures(view, **options)
        self.placed, self.chosen, self.read = [], [], []
        gestures.place.connect(lambda i: self.placed.append(i.row()))
        gestures.choose.connect(lambda i: self.chosen.append(i.row()))
        gestures.read.connect(lambda i: self.read.append(i.row()))
        view.show()
        self._app.processEvents()
        self.addCleanup(view.deleteLater)
        self.addCleanup(view.close)
        return view

    def _at(self, view, row):
        return view.visualRect(view.model().index(row, 0)).center()

    def test_right_arrow_reads_only_where_the_list_asked_for_it(self):
        """V3.00: → opens the plant list's page. A tree uses → to open a
        group (the community list), so it is opt-in."""
        view = self._list(read_key=True)
        view.setCurrentIndex(view.model().index(2, 0))
        QTest.keyClick(view, Qt.Key.Key_Right)
        self.assertEqual(self.read, [2])
        self.assertEqual(self.placed, [])
        plain = self._list()
        plain.setCurrentIndex(plain.model().index(1, 0))
        QTest.keyClick(plain, Qt.Key.Key_Right)
        self.assertEqual(self.read, [])

    def test_enter_and_return_place_the_current_row(self):
        view = self._list()
        view.setCurrentIndex(view.model().index(2, 0))
        QTest.keyClick(view, Qt.Key.Key_Return)
        QTest.keyClick(view, Qt.Key.Key_Enter)
        self.assertEqual(self.placed, [2, 2])

    def test_a_double_click_places_the_row(self):
        view = self._list()
        QTest.mouseClick(view.viewport(), Qt.MouseButton.LeftButton,
                         pos=self._at(view, 3))
        QTest.mouseDClick(view.viewport(), Qt.MouseButton.LeftButton,
                          pos=self._at(view, 3))
        self.assertEqual(self.placed, [3])

    def test_a_click_and_an_arrow_key_choose(self):
        view = self._list()
        QTest.mouseClick(view.viewport(), Qt.MouseButton.LeftButton,
                         pos=self._at(view, 1))
        QTest.keyClick(view, Qt.Key.Key_Down)
        self.assertEqual(self.chosen, [1, 2])
        self.assertEqual(self.placed, [], "choosing is not placing")

    def test_focus_arriving_chooses_nothing(self):
        """Tabbing into the list makes its first row current; on V2.98 that
        armed the map with it."""
        view = self._list()
        view.setFocus(Qt.FocusReason.TabFocusReason)
        self._app.processEvents()
        self.assertTrue(view.currentIndex().isValid(),
                        "focus did not make a row current; the case is not tested")
        self.assertEqual((self.chosen, self.placed), ([], []))

    def test_a_press_released_on_another_row_chooses_nothing(self):
        view = self._list()
        QTest.mousePress(view.viewport(), Qt.MouseButton.LeftButton,
                         pos=self._at(view, 1))
        QTest.mouseRelease(view.viewport(), Qt.MouseButton.LeftButton,
                           pos=self._at(view, 4))
        self.assertEqual(self.chosen, [])

    def test_a_click_the_row_took_chooses_nothing(self):
        """The plant list's ▶ reads the card. Qt 6 still emits ``clicked`` for
        a release its delegate took, so the delegate has to say so."""
        view = self._list()
        view.itemDelegate().take = True
        QTest.mouseClick(view.viewport(), Qt.MouseButton.LeftButton,
                         pos=self._at(view, 2))
        self.assertEqual(self.chosen, [])

    def test_a_single_click_never_places_even_where_clicks_activate(self):
        """On a style that activates on one click, ``activated`` fires on every
        click. Arming from it would come back on those machines alone."""
        view = self._list()
        self._style = _ClickActivates()       # outlives the view's use of it
        view.setStyle(self._style)
        self.addCleanup(lambda: view.setStyle(None))
        activated = []
        view.activated.connect(lambda i: activated.append(i.row()))
        QTest.mouseClick(view.viewport(), Qt.MouseButton.LeftButton,
                         pos=self._at(view, 2))
        self.assertEqual(activated, [2], "the stand-in style did not take")
        self.assertEqual(self.placed, [])


@unittest.skipUnless(_HAVE_QT, "PyQt6 not installed in this env")
class TestPlaceButton(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls._app = QApplication.instance() or QApplication(["permadesign-tests"])

    def _button(self, **kw):
        from src.place_action import PlaceButton
        btn = PlaceButton("plant", **kw)
        btn.resize(300, 30)
        self.addCleanup(btn.deleteLater)
        return btn

    def test_names_what_it_places(self):
        btn = self._button()
        btn.set_subject("Wild Bergamot")
        self.assertEqual(btn.text(), "Place Wild Bergamot on the map")
        self.assertEqual(btn.accessibleName(), "Place Wild Bergamot on the map")
        self.assertTrue(btn.isEnabled())
        self.assertFalse(btn.isCheckable(), "V2.37's Place button toggled")

    def test_says_why_it_cannot(self):
        btn = self._button()
        btn.set_subject("")
        self.assertFalse(btn.isEnabled())
        self.assertEqual(btn.text(), "Select a plant to place it")

    def test_a_long_name_is_elided_and_kept_whole_for_a_screen_reader(self):
        """The catalogue's longest is 56 characters."""
        name = "Three Flowered Avens (Prairie Smoke, Old Man's Whiskers)"
        btn = self._button()
        btn.set_subject(name)
        self.assertIn("…", btn.text())
        self.assertLessEqual(btn.fontMetrics().horizontalAdvance(btn.text()),
                             btn.width())
        self.assertEqual(btn.accessibleName(), f"Place {name} on the map")
        self.assertIn(name, btn.toolTip())

    def test_the_compact_one_carries_the_name_for_a_screen_reader(self):
        btn = self._button(compact=True)
        btn.set_subject("Aromatic Herb Circle")
        self.assertEqual(btn.text(), "Place on map")
        self.assertEqual(btn.accessibleName(),
                         "Place Aromatic Herb Circle on the map")


# ── What the map draws under the cursor ──────────────────────────────────────

_ROWS = {
    1: {"spacing_meters": 0.6, "mature_canopy_m": 0.9},
    2: {"spacing_meters": 1.5, "mature_canopy_m": 2.4},
}
_COMMUNITY = {"name": "Test Circle", "members": [
    {"plant_id": 1, "offset_x": 0.0, "offset_y": 0.0},
    {"plant_id": 2, "offset_x": 1.2, "offset_y": -0.8},
    {"plant_id": 99, "offset_x": -1.0, "offset_y": 1.5},   # not in the catalogue
]}


class TestCommunityFootprint(unittest.TestCase):
    """Qt-free: the payload src/placement_footprint.py hands the map."""

    def _fp(self):
        from src.placement_footprint import community_footprint
        return community_footprint(_COMMUNITY, _ROWS.get)

    def test_members_keep_their_offsets_and_sizes(self):
        fp = self._fp()
        self.assertEqual(fp["name"], "Test Circle")
        self.assertEqual(fp["members"][1], [1.2, -0.8, 1.5, 2.4])

    def test_a_member_the_catalogue_lacks_keeps_its_place(self):
        self.assertEqual(self._fp()["members"][2], [-1.0, 1.5, 1.0, 1.5])

    def test_the_outline_reaches_the_far_edge_of_the_farthest_canopy(self):
        want = max(math.hypot(1.2, -0.8) + 2.4 / 2, math.hypot(-1.0, 1.5) + 1.5 / 2)
        self.assertAlmostEqual(self._fp()["radius_m"], want, places=3)

    def test_an_empty_community_draws_nothing(self):
        from src.placement_footprint import community_footprint
        self.assertEqual(community_footprint({"members": []}, _ROWS.get)["members"], [])


def _run_footprint(setup_js: str, also: str = "null"):
    """Run 08-footprint.js's spec for a stubbed map state. Returns the spec
    as JSON, or ``(spec, also)`` when ``also`` names a JS expression to report
    beside it."""
    plants = (_MAP / "03-plants.js").read_text(encoding="utf-8")
    burst = re.search(r"function _hexBurstPositions\(.*?\n    \}\n", plants, re.S)
    if not burst:
        raise AssertionError("03-plants.js: _hexBurstPositions() is gone; the "
                             "footprint draws a cluster with it")
    script = "\n".join([
        "var currentMode = 'none', currentPlant = null, currentCommunity = null,"
        " _patternStage = 0;",
        burst.group(0),
        (_MAP / "08-footprint.js").read_text(encoding="utf-8"),
        setup_js,
        "var spec = _footprintSpec();",
        "console.log(JSON.stringify({also: " + also + ", spec: spec && {"
        "sizes: spec.sizes, at: spec.at(53.5, -113.5), outline: spec.outline,"
        " badge: spec.badge}}));",
    ])
    proc = subprocess.run([_node(), "-e", script], capture_output=True,
                          text=True, timeout=60, encoding="utf-8")
    if proc.returncode != 0:
        raise AssertionError(f"node failed: {proc.stderr}")
    out = json.loads(proc.stdout)
    return out["spec"] if also == "null" else (out["spec"], out["also"])


@unittest.skipIf(_node() is None, "no node binary")
class TestTheFootprintOnTheMap(unittest.TestCase):
    """The viewer's own footprint code, run against Python's placement."""

    def test_a_community_ghost_is_where_its_plants_land(self):
        from src.placement_footprint import community_footprint
        fp = community_footprint(_COMMUNITY, _ROWS.get)
        out = _run_footprint("currentMode = 'polyculture'; currentCommunity = "
                             + json.dumps(fp) + ";")
        lat, lng = 53.5, -113.5
        cos_lat = math.cos(lat * math.pi / 180) or 1e-9
        for m, (glat, glng) in zip(_COMMUNITY["members"], out["at"]):
            with self.subTest(member=m["plant_id"]):
                # MapEventRouter._on_polyculture_click, verbatim.
                self.assertAlmostEqual(glat, lat + m["offset_y"] / 111320, places=9)
                self.assertAlmostEqual(
                    glng, lng + m["offset_x"] / (111320 * cos_lat), places=9)
        self.assertAlmostEqual(out["outline"], fp["radius_m"])
        self.assertEqual(out["sizes"][1], [1.5, 2.4])

    def test_one_plant_is_one_pair_of_rings(self):
        out = _run_footprint("currentMode = 'plant'; currentPlant = {id: 7,"
                             " spacing_m: 2.5, mature_canopy_m: 3.0,"
                             " pattern: {kind: 'single'}};")
        self.assertEqual(out["sizes"], [[2.5, 3.0]])
        self.assertEqual(out["at"], [[53.5, -113.5]])
        self.assertEqual(out["badge"], "")

    def test_a_cluster_is_drawn_as_it_will_be_laid(self):
        # The click (01-core.js onMapClick) lays a Qty cluster with
        # _hexBurstPositions(lat, lng, spacing_m, qty); the ghost must match.
        out, laid = _run_footprint(
            "currentMode = 'plant'; currentPlant = {id: 7, spacing_m: 0.5,"
            " quantity: 5, pattern: {kind: 'single'}};",
            also="_hexBurstPositions(53.5, -113.5, 0.5, 5)")
        self.assertEqual(out["at"], laid)
        self.assertEqual(len(laid), 5)
        self.assertEqual(out["badge"], "5 plants")

    def test_a_pattern_shows_its_first_plant_until_its_own_preview_takes_over(self):
        setup = ("currentMode = 'plant'; currentPlant = {id: 7, spacing_m: 1.0,"
                 " pattern: {kind: 'row', params: {}}};")
        self.assertEqual(len(_run_footprint(setup)["at"]), 1)
        self.assertIsNone(_run_footprint(setup + "_patternStage = 1;"))

    def test_a_community_pattern_is_one_ring_its_size(self):
        out = _run_footprint("currentMode = 'plant'; currentPlant = {id: 7,"
                             " spacing_m: 3.5, mature_canopy_m: 0.4,"
                             " pattern: {kind: 'grid', params: {community:"
                             " {spacing_m: 3.5}}}};")
        self.assertEqual(out["sizes"], [[3.5, 3.5]])

    def test_nothing_when_not_placing_or_filling(self):
        self.assertIsNone(_run_footprint("currentMode = 'none';"))
        self.assertIsNone(_run_footprint("currentMode = 'fill';"))


class TestTheFootprintIsWired(unittest.TestCase):
    """Static: the hooks that make the footprint appear, move and go."""

    @classmethod
    def setUpClass(cls):
        cls.core = (_MAP / "01-core.js").read_text(encoding="utf-8")
        cls.features = (_MAP / "05-features.js").read_text(encoding="utf-8")
        cls.footprint = (_MAP / "08-footprint.js").read_text(encoding="utf-8")
        cls.html = (_ROOT / "html" / "map.html").read_text(encoding="utf-8")

    def test_map_html_loads_it_last(self):
        self.assertLess(self.html.index("map/07-network.js"),
                        self.html.index("map/08-footprint.js"))

    def test_it_follows_the_pointer_and_leaves_with_it(self):
        move = self.core[self.core.index("function onMapMouseMove(e)"):]
        move = move[:move.index("\n    }\n")]
        self.assertIn("updateCursorFootprint(e.latlng)", move)
        self.assertRegex(self.core, r"map\.on\('mouseout'[^;]*\n[^;]*hideCursorFootprint")

    def test_every_mode_change_resets_it_and_a_community_brings_its_shape(self):
        body = self.features[self.features.index("function setMode(mode, data)"):]
        body = body[:body.index("\n    }\n")]
        self.assertIn("resetCursorFootprint()", body)
        case = body[body.index("case 'polyculture':"):]
        self.assertIn("currentCommunity = data", case[:case.index("break;")])

    def test_it_never_takes_the_click(self):
        """It sits exactly under the pointer; a ghost that took pointer events
        would swallow the click it previews."""
        self.assertIn("pointerEvents = 'none'", self.footprint)
        self.assertNotIn("interactive: true", self.footprint)
        self.assertEqual(self.footprint.count("L.circle("),
                         self.footprint.count("interactive: false"))

    def test_the_app_sends_a_community_its_footprint(self):
        app = (_ROOT / "src" / "app.py").read_text(encoding="utf-8")
        fn = app[app.index("def _enter_polyculture_mode"):]
        fn = fn[:fn.index("\n    def ")]
        self.assertIn("set_polyculture_mode(community_footprint(", fn)


if __name__ == "__main__":
    unittest.main()
