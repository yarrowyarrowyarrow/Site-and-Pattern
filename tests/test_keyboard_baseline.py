"""
tests/test_keyboard_baseline.py — keyboard and screen reader (F195, V3.02).

The first half of the V2.98 review's accessibility baseline: focus that can be
seen on any control, single-key shortcuts that wait for the map, names a screen
reader can read, and the lists and builder a keyboard could not reach. The map
itself is in ``test_map_keyboard``; the walk over the real window's names and
keys is in ``test_app_smoke``, which builds the window once.
"""

import os
import shutil
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

_TMP = tempfile.mkdtemp(prefix="sp_keyboard_")
import src.db.plants as _plants  # noqa: E402
_plants._DATA_DIR = _TMP
_plants._DB_PATH = os.path.join(_TMP, "permadesign_test.db")

try:
    from PyQt6.QtCore import QEvent, QPoint, QPointF, Qt
    from PyQt6.QtGui import QKeyEvent, QMouseEvent
    from PyQt6.QtWidgets import (
        QApplication, QLabel, QPushButton, QTabWidget, QVBoxLayout, QWidget,
    )
    _HAVE_QT = True
except Exception:                                          # noqa: BLE001
    _HAVE_QT = False


def tearDownModule():
    shutil.rmtree(_TMP, ignore_errors=True)


def _app():
    return QApplication.instance() or QApplication(["permadesign-tests"])


def _key(widget, key, modifiers=None):
    from PyQt6.QtCore import Qt as _Qt
    mods = modifiers if modifiers is not None else _Qt.KeyboardModifier.NoModifier
    ev = QKeyEvent(QEvent.Type.KeyPress, key, mods)
    QApplication.sendEvent(widget, ev)
    return ev


@unittest.skipUnless(_HAVE_QT, "PyQt6 not installed in this env")
class TestTheFocusRing(unittest.TestCase):
    """One frame that follows keyboard focus, drawn outside the control's own
    stylesheet, which is what had removed Qt's focus drawing everywhere."""

    @classmethod
    def setUpClass(cls):
        cls._app = _app()
        from src.focus_ring import FocusRing
        cls.ring = FocusRing(cls._app)

    def setUp(self):
        self.window = QWidget()
        self.addCleanup(self.window.deleteLater)
        self.addCleanup(self.window.close)
        lay = QVBoxLayout(self.window)
        self.a = QPushButton("First")
        self.b = QPushButton("Second")
        # A stylesheet that sets its own border: the case that hid focus.
        for w in (self.a, self.b):
            w.setStyleSheet("QPushButton { border: 1px solid #2e4a2e; }")
            lay.addWidget(w)
        self.window.show()
        self._app.processEvents()
        self.window.activateWindow()
        self._app.processEvents()

    def _press_mouse(self, widget):
        ev = QMouseEvent(QEvent.Type.MouseButtonPress, QPointF(2, 2),
                         QPointF(widget.mapToGlobal(QPoint(2, 2))),
                         Qt.MouseButton.LeftButton, Qt.MouseButton.LeftButton,
                         Qt.KeyboardModifier.NoModifier)
        QApplication.sendEvent(widget, ev)

    def test_it_rings_what_the_keyboard_reaches(self):
        self.a.setFocus()
        _key(self.a, Qt.Key.Key_Tab)
        self.b.setFocus()
        self._app.processEvents()
        self.assertIs(self.ring.ringed(), self.b)

    def test_a_mouse_press_puts_it_away(self):
        _key(self.a, Qt.Key.Key_Tab)
        self.a.setFocus()
        self._app.processEvents()
        self._press_mouse(self.a)
        self._app.processEvents()
        self.assertIsNone(self.ring.ringed())
        self.assertFalse(self.ring.keyboard_in_use())

    def test_the_mouse_does_not_bring_it_back_by_moving_focus(self):
        self._press_mouse(self.a)
        self.b.setFocus()
        self._app.processEvents()
        self.assertIsNone(self.ring.ringed())

    def test_install_gives_one_ring_per_application(self):
        from src import focus_ring
        self.assertIs(focus_ring.install(self._app), focus_ring.install(self._app))

    def test_a_control_packed_against_its_parents_edges_shows_all_four(self):
        """The first build used Qt's frame, which sits in a margin outside the
        control: a search field laid edge to edge showed only its bottom, and
        a scroll area nothing. The ring is drawn over the control instead."""
        from PyQt6.QtWidgets import QLineEdit, QScrollArea
        from src.focus_ring import RING_COLOUR, RING_EDGE
        window = QWidget()
        self.addCleanup(window.deleteLater)
        self.addCleanup(window.close)
        window.resize(320, 160)
        outer = QVBoxLayout(window)
        outer.setContentsMargins(0, 0, 0, 0)
        area = QScrollArea()
        area.setWidgetResizable(True)
        outer.addWidget(area)
        content = QWidget()
        inner = QVBoxLayout(content)
        inner.setContentsMargins(0, 0, 0, 0)
        field = QLineEdit("yarrow")
        inner.addWidget(field)
        inner.addStretch(1)
        area.setWidget(content)
        window.show()
        self._app.processEvents()
        field.setFocus()
        _key(field, Qt.Key.Key_Tab)
        self.ring._ring(field)
        self._app.processEvents()
        self.assertIs(self.ring.ringed(), field)

        image = window.grab().toImage()
        top_left = field.mapTo(window, QPoint(0, 0))
        x0, y0 = top_left.x(), top_left.y()
        x1, y1 = x0 + field.width() - 1, y0 + field.height() - 1
        mid_x, mid_y = (x0 + x1) // 2, (y0 + y1) // 2
        edges = {"left": (x0, mid_y), "right": (x1, mid_y),
                 "top": (mid_x, y0), "bottom": (mid_x, y1)}
        for side, (x, y) in edges.items():
            with self.subTest(side=side):
                self.assertEqual(image.pixelColor(x, y).name(), RING_COLOUR)
        # The dark line inside it, which carries the ring on a light field.
        self.assertEqual(image.pixelColor(x0 + 2, mid_y).name(), RING_EDGE)

    def test_the_map_is_left_to_its_page(self):
        """Focus inside the web view moves between the page's own controls,
        which Qt cannot see; html/map/09-keyboard.js draws that ring."""
        from src.focus_ring import _wants_ring

        class QWebEngineView(QWidget):    # the class name is what is read
            pass
        view = QWebEngineView()
        self.addCleanup(view.deleteLater)
        inside = QWidget(view)
        self.assertFalse(_wants_ring(inside))
        self.assertTrue(_wants_ring(self.a))


@unittest.skipUnless(_HAVE_QT, "PyQt6 not installed in this env")
class TestTheShortcutTable(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls._app = _app()

    def test_each_letter_is_read_unmodified_only(self):
        from src import keyboard_help as kh
        for key, action, _words in kh.MAP_LETTERS:
            code = getattr(Qt.Key, f"Key_{key}")
            ev = QKeyEvent(QEvent.Type.KeyPress, code,
                           Qt.KeyboardModifier.NoModifier)
            self.assertEqual(kh.letter_action(ev), action, key)
            ev = QKeyEvent(QEvent.Type.KeyPress, code,
                           Qt.KeyboardModifier.ControlModifier)
            self.assertEqual(kh.letter_action(ev), "", key)

    def test_the_letters_are_distinct(self):
        from src import keyboard_help as kh
        keys = [k for k, _a, _w in kh.MAP_LETTERS]
        self.assertEqual(len(keys), len(set(keys)))

    def test_the_help_page_lists_every_key(self):
        from src import keyboard_help as kh
        page = kh.help_html()
        for key, _action, words in kh.MAP_LETTERS:
            self.assertIn(f"<b>{key}</b>", page)
            self.assertIn(words.split(":")[0], page)
        for key, _words in kh.MAP_KEYS + kh.LIST_KEYS:
            self.assertIn(key.replace("&", "&amp;").replace("<", "&lt;")
                          .split(",")[0], page)

    def test_the_map_has_focus_only_when_it_or_a_child_does(self):
        from src import keyboard_help as kh
        window = QWidget()
        self.addCleanup(window.deleteLater)
        lay = QVBoxLayout(window)
        fake_map = QWidget()
        inner = QPushButton("inside the map")
        QVBoxLayout(fake_map).addWidget(inner)
        panel_button = QPushButton("in a panel")
        lay.addWidget(fake_map)
        lay.addWidget(panel_button)
        window.show()
        self._app.processEvents()
        window.activateWindow()
        inner.setFocus()
        self._app.processEvents()
        if QApplication.focusWidget() is not inner:
            self.skipTest("this platform does not give the window focus")
        self.assertTrue(kh.map_has_focus(fake_map))
        panel_button.setFocus()
        self._app.processEvents()
        self.assertFalse(kh.map_has_focus(fake_map))

    def test_show_panel_opens_every_tab_level(self):
        """P and G did nothing: the panels sit inside the Plants tab, and
        setCurrentWidget on the outer tabs ignores them."""
        from src import keyboard_help as kh
        outer = QTabWidget()
        self.addCleanup(outer.deleteLater)
        outer.addTab(QLabel("site"), "Site")
        inner = QTabWidget()
        outer.addTab(inner, "Plants")
        inner.addTab(QLabel("browse"), "Browse")
        communities = QLabel("communities")
        inner.addTab(communities, "Plant Communities")
        kh.show_panel(communities)
        self.assertIs(outer.currentWidget(), inner)
        self.assertIs(inner.currentWidget(), communities)

    def test_f6_goes_to_the_map_and_back_to_where_you_were(self):
        """18 presses of Tab from the plant list to the map, measured live;
        F6 is two presses for list, map, list."""
        from src.keyboard_help import PaneSwitch

        class _Map(QWidget):
            arrived = 0

            def focus_by_keyboard(self):
                _Map.arrived += 1
                self.setFocus()

        window = QWidget()
        self.addCleanup(window.deleteLater)
        self.addCleanup(window.close)
        lay = QVBoxLayout(window)
        the_map = _Map()
        the_map.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        panel = QTabWidget()
        page = QWidget()
        page_lay = QVBoxLayout(page)
        first, chosen = QPushButton("first"), QPushButton("chosen")
        page_lay.addWidget(first)
        page_lay.addWidget(chosen)
        panel.addTab(page, "Plants")
        toolbar_button = QPushButton("Boundary")
        for w in (toolbar_button, the_map, panel):
            lay.addWidget(w)
        switch = PaneSwitch(window, the_map, panel)
        window.show()
        window.activateWindow()
        self._app.processEvents()
        chosen.setFocus()
        self._app.processEvents()
        if QApplication.focusWidget() is not chosen:
            self.skipTest("this platform does not give the window focus")

        switch.switch()
        self._app.processEvents()
        self.assertIs(QApplication.focusWidget(), the_map)
        self.assertEqual(_Map.arrived, 1)
        switch.switch()
        self._app.processEvents()
        self.assertIs(QApplication.focusWidget(), chosen)     # not `first`
        toolbar_button.setFocus()
        self._app.processEvents()
        switch.switch()                                       # from elsewhere
        self._app.processEvents()
        self.assertIs(QApplication.focusWidget(), the_map)

    def test_containers_are_named_after_the_tab_they_sit_in(self):
        from PyQt6.QtWidgets import QScrollArea
        from src.accessible_names import name_containers
        window = QWidget()
        self.addCleanup(window.deleteLater)
        lay = QVBoxLayout(window)
        outer = QTabWidget()
        lay.addWidget(outer)
        page = QWidget()
        page_lay = QVBoxLayout(page)
        inner = QTabWidget()
        page_lay.addWidget(inner)
        scroll = QScrollArea()
        inner.addTab(scroll, "On This Design")
        outer.addTab(page, "Plants")
        self.assertEqual(name_containers(window), 2)
        self.assertEqual(inner.accessibleName(), "Plants")
        # The nearer tab names it, not the outer one that also contains it.
        self.assertEqual(scroll.accessibleName(), "On This Design")
        self.assertEqual(outer.accessibleName(), "")     # named by its owner

    def test_menu_shortcuts_are_read_from_the_window(self):
        from PyQt6.QtGui import QAction, QKeySequence
        from src import keyboard_help as kh
        window = QWidget()
        self.addCleanup(window.deleteLater)
        act = QAction("&Save", window)
        act.setShortcut(QKeySequence("Ctrl+S"))
        window.addAction(act)
        rows = kh.menu_shortcuts(window)
        self.assertIn("Save", [w for _k, w in rows])

    def test_a_key_bound_twice_is_listed_once(self):
        """Redo carries the platform's Redo keys and Ctrl+Shift+Z by name; on
        Linux the first already holds the second, and the page said it twice."""
        from PyQt6.QtGui import QAction, QKeySequence
        from src import keyboard_help as kh
        window = QWidget()
        self.addCleanup(window.deleteLater)
        act = QAction("&Redo", window)
        act.setShortcuts([QKeySequence("Ctrl+Shift+Z"), QKeySequence("Ctrl+Y"),
                          QKeySequence("Ctrl+Shift+Z")])
        window.addAction(act)
        keys = dict((w, k) for k, w in kh.menu_shortcuts(window))["Redo"]
        self.assertEqual(keys.count("Ctrl+Shift+Z"), 1)
        self.assertIn("Ctrl+Y", keys)

    def test_the_page_scrolls_rather_than_running_off_a_short_screen(self):
        from PyQt6.QtWidgets import QScrollArea
        from src import keyboard_help as kh
        window = QWidget()
        self.addCleanup(window.deleteLater)
        dialog = kh.show_shortcuts(window)
        self.addCleanup(dialog.deleteLater)
        self.addCleanup(dialog.close)
        area = dialog.findChild(QScrollArea)
        self.assertIsNotNone(area)
        self.assertIn("Shift+Enter", area.widget().text())
        room = window.screen().availableGeometry()
        self.assertLessEqual(dialog.height(), room.height())


@unittest.skipUnless(_HAVE_QT, "PyQt6 not installed in this env")
class TestTheBuilderByKeyboard(unittest.TestCase):
    """The builder's grid was mouse-only: a keyboard could not add a plant."""

    @classmethod
    def setUpClass(cls):
        cls._app = _app()
        _plants.init_db()

    def setUp(self):
        from src.polyculture_panel import PolycultureBuilderDialog
        self.dialog = PolycultureBuilderDialog(None)
        self.addCleanup(self.dialog.deleteLater)

    def test_the_next_spot_is_clear_of_every_member_and_inside(self):
        from src.polyculture_panel import next_free_offset
        members = []
        for _ in range(12):
            x, y = next_free_offset(members, 6.0)
            self.assertLessEqual((x * x + y * y) ** 0.5, 6.0)
            for m in members:
                d = ((x - m["offset_x"]) ** 2 + (y - m["offset_y"]) ** 2) ** 0.5
                self.assertGreaterEqual(d, 0.8 - 1e-9)
            members.append({"offset_x": x, "offset_y": y})
        self.assertEqual(next_free_offset([], 6.0), (0.0, 0.0))

    def test_enter_in_the_plant_list_adds_the_plant(self):
        picker = self.dialog.picker
        picker.view.setCurrentIndex(picker.model.index(0, 0))
        _key(picker.view, Qt.Key.Key_Return)
        members = self.dialog.canvas.get_members()
        self.assertEqual(len(members), 1)
        self.assertEqual(members[0]["plant_id"], picker.rows()[0]["id"])
        picker.view.setCurrentIndex(picker.model.index(1, 0))
        _key(picker.view, Qt.Key.Key_Return)
        self.assertEqual(len(self.dialog.canvas.get_members()), 2)

    def test_delete_in_members_removes_the_selected_one(self):
        picker = self.dialog.picker
        for row in (0, 1, 2):
            picker.view.setCurrentIndex(picker.model.index(row, 0))
            self.dialog._add_at_next_spot()
        self.dialog.show()
        self._app.processEvents()
        members = self.dialog.member_list
        members.setFocus()
        members.setCurrentRow(1)
        second = self.dialog.canvas.get_members()[1]["plant_id"]
        self._app.processEvents()
        if QApplication.focusWidget() is not members:
            self.dialog._remove_current_member()   # no window focus offscreen
        else:
            _key(members, Qt.Key.Key_Delete)
        left = [m["plant_id"] for m in self.dialog.canvas.get_members()]
        self.assertEqual(len(left), 2)
        self.assertNotIn(second, left)

    def test_the_grid_and_its_controls_have_names(self):
        d = self.dialog
        self.assertEqual(d.canvas.accessibleName(), "Community layout")
        self.assertIn("Enter", d.canvas.accessibleDescription())
        self.assertEqual(d.member_list.accessibleName(), "Members")
        self.assertEqual(d.layer_combo.accessibleName(), "Layer")


@unittest.skipUnless(_HAVE_QT, "PyQt6 not installed in this env")
class TestOnThisDesignTakesTheKeyboard(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls._app = _app()

    def test_its_lists_take_focus_and_are_named(self):
        from src.on_this_design_panel import OnThisDesignPanel
        panel = OnThisDesignPanel()
        self.addCleanup(panel.deleteLater)
        for lst in (panel._plants_list, panel._communities_list):
            self.assertNotEqual(lst.focusPolicy(), Qt.FocusPolicy.NoFocus)
            self.assertTrue(lst.accessibleName())

    def test_enter_on_a_row_does_what_a_click_does(self):
        from PyQt6.QtWidgets import QListWidgetItem
        from src.on_this_design_panel import OnThisDesignPanel
        panel = OnThisDesignPanel()
        self.addCleanup(panel.deleteLater)
        got = []
        panel.species_focus_requested.connect(got.append)
        item = QListWidgetItem("Wild Bergamot")
        item.setData(Qt.ItemDataRole.UserRole, 42)
        panel._plants_list.addItem(item)
        panel._plants_list.setCurrentItem(item)
        panel.show()
        self._app.processEvents()
        panel._plants_list.setFocus()
        self._app.processEvents()
        from PyQt6.QtGui import QShortcut
        shortcuts = [s for s in panel._plants_list.findChildren(QShortcut)]
        self.assertTrue(shortcuts, "no key does what a click does")
        shortcuts[0].activated.emit()
        self.assertEqual(got, [42])


@unittest.skipUnless(_HAVE_QT, "PyQt6 not installed in this env")
class TestNamesOutsideTheWindow(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls._app = _app()

    def test_the_start_screens_choices_are_named(self):
        """Each read as "button": the words are child labels."""
        from src.start_screen import StartScreen, _Row
        screen = StartScreen(None, last_design="My Yard", saves_count=2)
        self.addCleanup(screen.deleteLater)
        rows = screen.findChildren(_Row)
        self.assertGreaterEqual(len(rows), 4)
        for row in rows:
            self.assertTrue(row.accessibleName(), row)
            self.assertTrue(row.accessibleDescription(), row)
        self.assertIn("Continue", [r.accessibleName() for r in rows])

    def test_the_side_panel_strip_takes_focus_and_says_what_it_does(self):
        from src.collapsible_panel import CollapsibleSidebar
        strip = CollapsibleSidebar("Panels", expanded=True)
        self.addCleanup(strip.deleteLater)
        self.assertNotEqual(strip._chev.focusPolicy(), Qt.FocusPolicy.NoFocus)
        self.assertEqual(strip._chev.accessibleName(), "Collapse Panels")
        strip.set_expanded(False, persist=False)
        self.assertEqual(strip._chev.accessibleName(), "Expand Panels")

    def test_the_unfocusable_section_header_is_gone(self):
        import src.collapsible_panel as cp
        self.assertFalse(hasattr(cp, "CollapsiblePanel"))


if __name__ == "__main__":
    unittest.main()
