"""
tests/test_shade_features.py — Sun & Shade › Existing features (V3.37).

The owner: the existing features "should be accessible within Sun & Shade. As
a collapsible (initially collapsed) drop down that allows you to pick the
features that the sun path shade will then reflect." The rows and the switch
are Qt-free (``sun_shade``), the one rule that leaves a switched-off feature
out is ``shade.casters_from_project``, and the section and its flow are tested
with a stand-in window; the real window's version is in ``test_app_smoke``.
"""

import os
import sys
import unittest
from contextlib import contextmanager

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from src import shade, sun_shade  # noqa: E402

try:
    from PyQt6.QtWidgets import QApplication
    _HAVE_QT = True
except ImportError:                                        # pragma: no cover
    _HAVE_QT = False

# A yard 40 m square around (53.5, -113.5): its middle is the row's reference.
_D = 0.00018
_BOUNDARY = {"type": "Feature",
             "geometry": {"type": "Polygon", "coordinates": [[
                 [-113.5 - _D, 53.5 - _D], [-113.5 + _D, 53.5 - _D],
                 [-113.5 + _D, 53.5 + _D], [-113.5 - _D, 53.5 + _D],
                 [-113.5 - _D, 53.5 - _D]]]},
             "properties": {"element_type": "property_boundary"}}


def _tree(lat, lng, **props):
    return {"type": "Feature",
            "geometry": {"type": "Point", "coordinates": [lng, lat]},
            "properties": {"element_type": "existing_tree", "height_m": 11.0,
                           "canopy_radius_m": 3.0, "label": "Tree (detected)",
                           **props}}


def _building(lat, lng, **props):
    d = 0.00005
    ring = [[lng - d, lat - d], [lng + d, lat - d], [lng + d, lat + d],
            [lng - d, lat + d], [lng - d, lat - d]]
    return {"type": "Feature",
            "geometry": {"type": "Polygon", "coordinates": [ring]},
            "properties": {"element_type": "canopy_footprint", "height_m": 6.0,
                           "cast_shade": True, "canopy_radius_m": 7.0,
                           "label": "Building (OSM)", "source": "osm",
                           **props}}


def _project(*feats):
    return {"type": "FeatureCollection", "properties": {"site_config": {}},
            "features": [_BOUNDARY, *feats]}


# 23 m east and 11 m north-west of the middle; a plant in the middle.
_EAST = (53.5, -113.5 + 0.00034)
_NW = (53.5 + 0.00007, -113.5 - 0.00012)
_PLANT = {"type": "Feature",
          "geometry": {"type": "Point", "coordinates": [-113.5, 53.5]},
          "properties": {"element_type": "plant", "plant_id": 1}}


class TheRows(unittest.TestCase):

    def test_buildings_first_then_trees_nearest_first(self):
        project = _project(_tree(*_EAST), _PLANT, _building(*_EAST),
                           _tree(*_NW))
        rows = sun_shade.caster_rows(project)
        self.assertEqual([r["index"] for r in rows], [3, 4, 1])
        self.assertTrue(rows[0]["text"].startswith("Building (OSM) · 6 m tall"))
        self.assertEqual(rows[0]["where"], "23 m east")
        self.assertEqual(rows[1]["where"], "11 m north-west")
        self.assertTrue(all(r["on"] for r in rows))

    def test_where_from(self):
        middle = (53.5, -113.5)
        self.assertEqual(sun_shade.where_from(middle, middle), "in the middle")
        self.assertEqual(sun_shade.where_from((53.5 - 0.0002, -113.5), middle),
                         "22 m south")
        self.assertEqual(sun_shade.where_from(None, middle), "")
        self.assertEqual(sun_shade.where_from(middle, None), "")

    def test_with_no_boundary_the_pin_is_the_middle(self):
        project = {"features": [_tree(*_EAST)],
                   "properties": {"site_config": {}}}
        self.assertEqual(sun_shade.caster_rows(project)[0]["where"], "")
        sc = {"latitude": 53.5, "longitude": -113.5}
        self.assertEqual(sun_shade.caster_rows(project, sc)[0]["where"],
                         "23 m east")

    def test_a_drawn_tree_reads_as_a_tree(self):
        canopy = _building(*_EAST, caster_kind="tree", label="Tree")
        self.assertIn("crown", sun_shade.describe_feature(canopy))
        self.assertEqual(sun_shade.caster_counts(_project(canopy)), (0, 1))


class TheSwitch(unittest.TestCase):

    def test_off_writes_the_key_and_on_takes_it_away(self):
        project = _project(_building(*_EAST), _tree(*_NW), _PLANT)
        self.assertEqual(sun_shade.set_shade(project, [1, 2], False), 2)
        self.assertTrue(project["features"][1]["properties"][shade.SHADE_OFF])
        self.assertEqual(sun_shade.set_shade(project, [1, 2], False), 0)
        self.assertEqual(sun_shade.set_shade(project, [1], True), 1)
        # On is the default: written by removing the key, so a design that
        # never switched anything off is the file it always was.
        self.assertNotIn(shade.SHADE_OFF, project["features"][1]["properties"])
        # Not an existing feature, or not there at all: left alone.
        self.assertEqual(sun_shade.set_shade(project, [0, 3, 99], False), 0)
        self.assertNotIn(shade.SHADE_OFF, project["features"][3]["properties"])

    def test_the_counts_leave_it_out_and_say_so(self):
        project = _project(_building(*_EAST), _tree(*_NW))
        sun_shade.set_shade(project, [1], False)
        self.assertEqual(sun_shade.caster_counts(project), (0, 1))
        self.assertEqual(sun_shade.switched_off(project), 1)
        line, have = sun_shade.caster_summary(0, 1, off=1)
        self.assertTrue(have)
        self.assertIn("1 switched off in Sun & Shade.", line)
        line, _ = sun_shade.caster_summary(0, 1, off=1, off_where="below")
        self.assertTrue(line.endswith("1 switched off below."))
        line, have = sun_shade.caster_summary(0, 0, off=2)
        self.assertFalse(have)
        self.assertIn("Nothing is casting shade", line)

    def test_the_shade_leaves_it_out_and_keeps_the_plants(self):
        project = _project(_building(*_EAST), _tree(*_NW))
        self.assertEqual(len(shade.casters_from_project(project)), 2)
        sun_shade.set_shade(project, [1, 2], False)
        self.assertEqual(shade.casters_from_project(project), [])
        # A placed plant is never in the list, and a stray key on one does
        # not take its shade away.
        plant = dict(_PLANT, properties=dict(_PLANT["properties"],
                                             shade_off=True))
        project["features"].append(plant)
        from unittest import mock
        with mock.patch("src.db.plants.get_plant",
                        return_value={"mature_height_meters": 8,
                                      "mature_canopy_m": 4}):
            self.assertEqual(len(shade.casters_from_project(project)), 1)

    @unittest.skipUnless(shade._HAVE_SHAPELY, "shapely not installed")
    def test_the_shade_map_is_drawn_without_it(self):
        from datetime import datetime
        project = _project(_building(*_EAST))
        noon = datetime(2025, 6, 21, 15, 0)
        self.assertIsNotNone(shade.shadow_polygons_payload(
            project, None, {}, when=noon))
        sun_shade.set_shade(project, [1], False)
        self.assertIsNone(shade.shadow_polygons_payload(
            project, None, {}, when=noon))


class _Main:
    """What the flow touches of the window."""

    def __init__(self, project):
        from src.shade_features import ShadeFeatures
        self._project = project
        self.checkpoints, self.framed = [], []
        self.modified = self.shade_refreshed = 0
        main = self

        class _Persistence:
            @contextmanager
            def checkpoint(self, label):
                main.checkpoints.append(label)
                yield

        class _Events:
            def _refresh_shade_if_active(self):
                main.shade_refreshed += 1

        class _Analysis:
            shade_features = ShadeFeatures()

        class _Map:
            def fit_bounds(self, *box):
                main.framed.append(box)

        self._persistence = _Persistence()
        self._map_events = _Events()
        self.analysis_panel = _Analysis()
        self.map_widget = _Map()
        self.analysis_panel.shade_features.refresh(project)

    def _mark_modified(self):
        # As the window does: every change refreshes the list.
        self.modified += 1
        self.analysis_panel.shade_features.refresh(self._project)


@unittest.skipUnless(_HAVE_QT, "PyQt6 not installed in this env")
class TheSection(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls._app = QApplication.instance() or QApplication(["sp-shade"])

    def _main(self):
        main = _Main(_project(_building(*_EAST), _tree(*_NW)))
        from src import shade_features_flow
        section = main.analysis_panel.shade_features
        section.shade_switched.connect(
            lambda idx, on: shade_features_flow.switch(main, idx, on))
        section.casting_changed.connect(
            main._map_events._refresh_shade_if_active)
        section.frame_requested.connect(
            lambda lat, lng: shade_features_flow.frame(main, lat, lng))
        return main, section

    def test_it_opens_closed_and_says_how_many(self):
        from src.shade_features import ShadeFeatures
        section = ShadeFeatures()
        self.assertFalse(section.toggle.isChecked())
        self.assertTrue(section.body.isHidden())
        self.assertEqual(section.toggle.text(), "Existing features ▸")
        self.assertFalse(section.empty.isHidden())        # what to do instead
        main, section = self._main()
        self.assertEqual(section.toggle.text(), "Existing features (2) ▸")
        section.toggle.setChecked(True)
        self.assertFalse(section.body.isHidden())
        self.assertTrue(section.toggle.text().endswith("▾"))
        self.assertEqual(section.list.count(), 2)

    def test_unticking_one_is_one_undo_step_and_redraws_the_shade(self):
        from PyQt6.QtCore import Qt
        main, section = self._main()
        section.list.item(0).setCheckState(Qt.CheckState.Unchecked)
        building = main._project["features"][1]["properties"]
        self.assertTrue(building[shade.SHADE_OFF])
        self.assertEqual(main.checkpoints, ["stop casting shade"])
        # Asked for once: the list held the tick, so its own refresh found
        # nothing moved.
        self.assertEqual(main.shade_refreshed, 1)
        self.assertEqual(section.toggle.text(),
                         "Existing features (1 of 2 cast shade) ▸")
        self.assertTrue(section.all_on.isEnabled())

    def test_an_undo_moves_the_tick_and_the_shade_follows(self):
        from PyQt6.QtCore import Qt
        main, section = self._main()
        # As an undo would leave it: the project changed under the list.
        main._project["features"][2]["properties"][shade.SHADE_OFF] = True
        main._mark_modified()
        self.assertEqual(section.list.item(1).checkState(),
                         Qt.CheckState.Unchecked)
        self.assertEqual(main.shade_refreshed, 1)
        self.assertEqual(main.checkpoints, [])

    def test_untick_all_and_tick_all_are_one_step_each(self):
        main, section = self._main()
        section.all_off.click()
        self.assertEqual(sun_shade.switched_off(main._project), 2)
        section.all_on.click()
        self.assertEqual(sun_shade.switched_off(main._project), 0)
        self.assertEqual(main.checkpoints,
                         ["stop casting shade", "cast shade"])
        self.assertFalse(section.all_on.isEnabled())

    def test_a_row_shows_where_it_is(self):
        main, section = self._main()
        section.list.setCurrentRow(1)
        (south, west, north, east), = main.framed
        self.assertAlmostEqual((south + north) / 2, _NW[0], places=6)
        self.assertAlmostEqual((west + east) / 2, _NW[1], places=6)

    def test_a_list_rebuilt_keeps_the_ticks_and_the_place(self):
        from PyQt6.QtCore import Qt
        main, section = self._main()
        section.list.setCurrentRow(1)
        # A tree in the middle comes before the north-west one, which stays
        # the row picked.
        main._project["features"].append(_tree(53.5, -113.5))
        main._mark_modified()
        self.assertEqual(section.list.count(), 3)
        self.assertEqual(section.list.currentRow(), 2)
        self.assertIn("north-west", section.list.currentItem().text())
        self.assertEqual(len(main.framed), 1)          # not framed again
        self.assertTrue(all(section.list.item(i).checkState()
                            == Qt.CheckState.Checked for i in range(3)))


if __name__ == "__main__":
    unittest.main()
