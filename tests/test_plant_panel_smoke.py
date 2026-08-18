"""
tests/test_plant_panel_smoke.py

Headless-Qt smoke test for src/plant_panel.py:PlantPanel. Safety net for
the upcoming plant_panel split (Chunk 4 of the strengthening roadmap)
into PlantListModel + PlantRowDelegate, the mix logic, and the placed-
plants strip.

Same skip-gracefully pattern as tests/test_app_smoke.py — when PyQt6 is
missing or the panel can't construct in this env, the tests skip
cleanly. Run locally with::

    QT_QPA_PLATFORM=offscreen python -m unittest tests.test_plant_panel_smoke -v

The mix logic (`_add_to_mix`, `_remove_from_mix`, `_clear_mix`) is the
piece most likely to move during the Chunk 4 split, so it gets the most
behavioural coverage here.
"""

import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Force offscreen platform BEFORE importing anything Qt-touching.
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

# Sandbox DB so the test never touches the real user DB.
_TMP_DIR = tempfile.mkdtemp(prefix="permadesign_plant_smoke_")
try:
    import src.db.plants as _plants_mod
    _plants_mod._DATA_DIR = _TMP_DIR
    _plants_mod._DB_PATH = os.path.join(_TMP_DIR, "permadesign_test.db")
except Exception:  # pragma: no cover
    pass


def _qt_available():
    try:
        import PyQt6  # noqa: F401
        from PyQt6.QtWidgets import QApplication  # noqa: F401
        return True
    except Exception:
        return False


@unittest.skipUnless(_qt_available(), "PyQt6 not installed in this env")
class TestPlantPanelSmoke(unittest.TestCase):

    _app = None
    _panel = None
    _construct_error: Exception | None = None

    @classmethod
    def setUpClass(cls):
        from PyQt6.QtWidgets import QApplication
        cls._app = QApplication.instance() or QApplication(["permadesign-tests"])
        try:
            from src.db.plants import init_db
            init_db()  # seeds the temp DB so PlantPanel queries succeed
            from src.plant_panel import PlantPanel
            cls._panel = PlantPanel()
        except Exception as exc:  # noqa: BLE001
            cls._construct_error = exc

    @classmethod
    def tearDownClass(cls):
        if cls._panel is not None:
            cls._panel.close()
            cls._panel.deleteLater()
            cls._panel = None

    def setUp(self):
        if self._construct_error is not None:
            self.skipTest(
                f"PlantPanel construction failed in this env: "
                f"{type(self._construct_error).__name__}: {self._construct_error}"
            )
        # The panel is constructed once for the class (setUpClass), so its
        # mutable transient state leaks between test methods in alphabetical
        # run order — e.g. test_add_to_mix_* would dirty _mix_species before
        # test_constructed checks it's empty. Reset to construction defaults
        # before each test so assertions are order-independent.
        if self._panel is not None:
            self._panel._mix_species = []
            self._panel._selected_plant = None
            self._panel._current_zone = None
            self._panel._placed_counts = {}

    # ── Basic class shape ────────────────────────────────────────────────────

    def test_constructed(self):
        self.assertIsNotNone(self._panel)
        # Initial mix should be empty.
        self.assertEqual(self._panel._mix_species, [])
        self.assertIsNone(self._panel._selected_plant)
        self.assertIsNone(self._panel._current_zone)

    def test_no_legacy_api_setter(self):
        # Chunk 1 cleanup removed the set_api_keys no-op; verify it stays
        # gone so the upcoming Chunk 4 split doesn't accidentally
        # resurrect it.
        self.assertFalse(hasattr(self._panel, "set_api_keys"))

    # ── Mix add/remove/clear semantics ───────────────────────────────────────

    def _reset_mix(self):
        self._panel._mix_species = []

    def test_add_to_mix_appends_entry(self):
        self._reset_mix()
        self._panel._add_to_mix({"id": 1, "common_name": "Yarrow"})
        self.assertEqual(len(self._panel._mix_species), 1)
        self.assertEqual(self._panel._mix_species[0]["id"], 1)
        self.assertEqual(self._panel._mix_species[0]["_weight"], 1)

    def test_add_to_mix_rejects_duplicates(self):
        self._reset_mix()
        self._panel._add_to_mix({"id": 1, "common_name": "Yarrow"})
        self._panel._add_to_mix({"id": 1, "common_name": "Yarrow"})
        self.assertEqual(len(self._panel._mix_species), 1)

    def test_add_to_mix_rejects_db_less_rows(self):
        self._reset_mix()
        self._panel._add_to_mix({"id": None, "common_name": "Ghost"})
        self._panel._add_to_mix({"common_name": "Also Ghost"})
        self.assertEqual(self._panel._mix_species, [])

    def test_add_to_mix_caps_at_MIX_MAX(self):
        self._reset_mix()
        cap = self._panel._MIX_MAX
        for i in range(cap + 3):
            self._panel._add_to_mix({"id": i + 1, "common_name": f"P{i}"})
        self.assertEqual(len(self._panel._mix_species), cap)

    def test_add_to_mix_does_not_mutate_caller_dict(self):
        self._reset_mix()
        plant = {"id": 1, "common_name": "Yarrow"}
        self._panel._add_to_mix(plant)
        self.assertNotIn("_weight", plant)
        self.assertIn("_weight", self._panel._mix_species[0])

    def test_remove_from_mix_drops_matching_id(self):
        self._reset_mix()
        self._panel._add_to_mix({"id": 1, "common_name": "Yarrow"})
        self._panel._add_to_mix({"id": 2, "common_name": "Bergamot"})
        self._panel._remove_from_mix(1)
        ids = [s["id"] for s in self._panel._mix_species]
        self.assertEqual(ids, [2])

    def test_remove_from_mix_ignores_unknown_id(self):
        self._reset_mix()
        self._panel._add_to_mix({"id": 1, "common_name": "Yarrow"})
        self._panel._remove_from_mix(999)
        self.assertEqual(len(self._panel._mix_species), 1)

    # ── Zone tracking ────────────────────────────────────────────────────────

    def test_set_zone_persists(self):
        self._panel.set_zone(3)
        self.assertEqual(self._panel._current_zone, 3)
        self._panel.set_zone(None)
        self.assertIsNone(self._panel._current_zone)

    # ── Placed-plants round-trip ─────────────────────────────────────────────
    # `clear_placed` / `load_placed` are what app.py calls after every map
    # mutation. Pin the dict-shape contract so the Chunk 4 split can't
    # silently change it.

    def test_clear_placed_resets_counts(self):
        self._panel._placed_counts = {1: 5, 2: 3}
        self._panel.clear_placed()
        self.assertEqual(self._panel._placed_counts, {})

    def test_load_placed_recomputes_counts(self):
        self._panel.load_placed([
            {"plant_id": 1, "common_name": "A"},
            {"plant_id": 1, "common_name": "A"},
            {"plant_id": 2, "common_name": "B"},
        ])
        self.assertEqual(self._panel._placed_counts.get(1), 2)
        self.assertEqual(self._panel._placed_counts.get(2), 1)

    # ── V1.85: unified multi-select filter dropdowns ─────────────────────────

    def test_use_based_toggle_buttons_removed(self):
        # The six use-overlapping toggles folded into the Use dropdown.
        for attr in ("_medicinal_btn", "_nfixer_btn", "_pollinator_btn",
                     "_keystone_btn", "_host_btn", "_birdfood_btn"):
            self.assertFalse(hasattr(self._panel, attr), attr)
        # The non-use extras stay as buttons.
        for attr in ("_native_filter_btn", "_edible_btn", "_perennial_btn",
                     "_has_image_btn"):
            self.assertTrue(hasattr(self._panel, attr), attr)

    def test_facet_combos_are_multiselect(self):
        from src.plant_panel import CheckableComboBox
        # All facet dropdowns — including ecoregion (V1.85 follow-up) — are
        # multi-select.
        for attr in ("_type_combo", "_sun_combo", "_water_combo",
                     "_use_combo", "_rarity_combo", "_ecoregion_combo"):
            self.assertIsInstance(getattr(self._panel, attr), CheckableComboBox)
        # The ecoregion combo drops the "Any ecoregion" sentinel — its
        # placeholder covers "any". Since V2.67 it is a three-level tree rather
        # than a flat list, so it carries a row per ecozone, per ecoregion and
        # per Alberta subregion; the flat count it used to assert would now be
        # asserting that the tree had not been built.
        from src.ecoregion import MOISTURE_NICHES, geographic_keys
        from src.ecoregion_tree import ecozones, regions_in, subregions_in
        expected = (len(ecozones()) + len(geographic_keys())
                    + sum(len(subregions_in(region))
                          for zone, _n in ecozones()
                          for region, _rn in regions_in(zone))
                    + len(MOISTURE_NICHES))
        self.assertEqual(self._panel._ecoregion_combo.model().rowCount(),
                         expected)

    def _set_checked(self, combo, keys):
        """Check exactly ``keys`` in ``combo`` (clearing others) — order-safe."""
        from PyQt6.QtCore import Qt
        for i in range(combo.model().rowCount()):
            it = combo.model().item(i)
            want = it.data(Qt.ItemDataRole.UserRole) in keys
            it.setCheckState(Qt.CheckState.Checked if want
                             else Qt.CheckState.Unchecked)

    def test_type_combo_has_colour_icons(self):
        # The Type dropdown items carry the plant-type colour swatch (legend).
        tc = self._panel._type_combo
        self.assertTrue(tc.model().rowCount() > 0)
        for i in range(tc.model().rowCount()):
            self.assertFalse(tc.model().item(i).icon().isNull())

    def test_browser_pane_not_collapsible(self):
        # V1.86: the Plant Browser pane is no longer wrapped in a CollapsiblePanel.
        self.assertFalse(hasattr(self._panel, "_browser_panel"))

    def test_ecoregion_default_is_empty(self):
        # With no auto-detected pin, the ecoregion picker starts unselected and
        # shows its placeholder (V1.86).
        self.assertEqual(self._panel._ecoregion_combo.checked_keys(), [])
        self.assertEqual(
            self._panel._ecoregion_combo.lineEdit().placeholderText(),
            "Restoring toward…")

    def test_live_pin_sets_and_clears_ecoregion(self):
        # A dropped pin's region drives the picker live; clearing removes it.
        p = self._panel
        p.set_autodetected_ecoregion("aspen_parkland")
        self.assertEqual(p._ecoregion_combo.checked_keys(), ["aspen_parkland"])
        p.set_autodetected_ecoregion("")
        self.assertEqual(p._ecoregion_combo.checked_keys(), [])

    def test_type_filter_has_full_taxonomy(self):
        # V1.87: full botanical types, dead "root" retired, all colourable.
        from src.plant_panel import _TYPE_LABELS
        from src.member_colors import TYPE_COLORS
        self.assertNotIn("root", _TYPE_LABELS)
        for key in ("wildflower", "grass", "sedge", "rush", "fern", "aquatic"):
            self.assertIn(key, _TYPE_LABELS)
        for key in _TYPE_LABELS:
            self.assertIn(key, TYPE_COLORS)

    def test_results_list_is_draggable(self):
        from src.plant_list_view import _PLANT_MIME
        from PyQt6.QtCore import Qt
        p = self._panel
        self.assertTrue(p._results_list.dragEnabled())
        m = p._results_model
        if m.rowCount() == 0:
            self.skipTest("no plants seeded")
        idx = m.index(0)
        self.assertTrue(bool(m.flags(idx) & Qt.ItemFlag.ItemIsDragEnabled))
        md = m.mimeData([idx])
        self.assertTrue(md.hasFormat(_PLANT_MIME))

    def test_drop_adds_to_mix_and_expands(self):
        from src.plant_list_view import _PLANT_OBJ_ROLE
        p = self._panel
        p._mix_species = []
        p._placement_panel.set_expanded(False)
        m = p._results_model
        if m.rowCount() == 0:
            self.skipTest("no plants seeded")
        pid = m.data(m.index(0), _PLANT_OBJ_ROLE)["id"]
        p._add_to_mix_by_id(pid)             # what the drop handler calls
        self.assertEqual(len(p._mix_species), 1)
        self.assertTrue(p._placement_panel.expanded())

    def test_multiselect_filter_matches_query(self):
        from src.db.plants import search_plants
        p = self._panel
        self._set_checked(p._type_combo, {"tree", "shrub"})
        self._set_checked(p._use_combo, {"pollinator", "host_plant"})
        p._run_search()
        expected = len(search_plants(plant_type=["tree", "shrub"],
                                     perm_use=["pollinator", "host_plant"]))
        self.assertEqual(p._result_count.text(), f"Results: {expected}")
        # AND semantics on uses → strictly fewer than pollinator alone
        self.assertLess(expected, len(search_plants(perm_use="pollinator")))

    def test_the_flower_colour_filter_narrows_and_restores(self):
        """V2.48. The directory got a colour filter in V2.47 and the picker
        beside the map did not, which is backwards: choosing a plant because of
        how it will look is a placement decision, and this is the panel you
        place from (P13).

        Reported by the author, and the reason this test drives the real widget
        rather than the query layer: a facet wired to a parameter nobody reads
        is the exact shape of the V2.37 dead-control bugs, and only pressing the
        control catches it.
        """
        from src.db.plants import search_plants
        p = self._panel
        # The class shares one panel and `setUp` resets only the mix, so an
        # earlier test's type/use selections are still checked here. Clear every
        # facet first or this measures the intersection instead of the colour.
        for combo in (p._type_combo, p._sun_combo, p._water_combo, p._use_combo,
                      p._rarity_combo, p._bloom_combo, p._fruit_combo,
                      p._colour_combo):
            self._set_checked(combo, set())
        p._run_search()
        every = p._results_model.rowCount()

        self._set_checked(p._colour_combo, {"purple"})
        p._run_search()
        purple = p._results_model.rowCount()
        self.assertEqual(purple, len(search_plants(flower_colours=["purple"])))
        self.assertGreater(purple, 0)
        self.assertLess(purple, every)

        self._set_checked(p._colour_combo, {"purple", "yellow"})
        p._run_search()
        both = p._results_model.rowCount()
        self.assertEqual(both,
                         purple + len(search_plants(flower_colours=["yellow"])))

        self._set_checked(p._colour_combo, set())
        p._run_search()
        self.assertEqual(p._results_model.rowCount(), every)

    def test_the_colour_menu_offers_the_shared_vocabulary(self):
        """Restating the colour list in the panel is how the panel, the
        directory and the website come to disagree about what colour a plant
        is."""
        from src.flower_colour import COLOUR_LABELS
        self.assertEqual(self._panel._colour_combo.count(), len(COLOUR_LABELS))


if __name__ == "__main__":
    unittest.main()


class TestTheEcoregionFilterIsATree(unittest.TestCase):
    """Three levels, collapsed to six (V2.67).

    The surveyed vocabulary is 24 ecoregions and 21 Alberta subregions. In one
    flat list that is the menu the author asked not to have: *"tabs, subtabs and
    subsubtabs to account for the 3 levels. This way we don't have one
    overwhelming menu with 24 items."*
    """

    @classmethod
    def setUpClass(cls):
        try:
            from PyQt6.QtWidgets import QApplication
        except ImportError as exc:                                # pragma: no cover
            raise unittest.SkipTest(f"PyQt6 not installed: {exc}")
        # A NAME, not an empty list: the first QApplication built in a process
        # wins for the whole process, and one built as QApplication([]) makes
        # the next QWebEngineView abort. See CLAUDE.md.
        cls.app = QApplication.instance() or QApplication(["tests"])

    def _combo(self):
        from src.filter_widgets import (CheckableComboBox,
                                        build_ecoregion_tree)
        combo = CheckableComboBox(placeholder="Restoring toward…")
        build_ecoregion_tree(combo)
        return combo

    def _visible(self, combo):
        model = combo.model()
        return [model.item(i) for i in range(model.rowCount())
                if not combo.view().isRowHidden(i)]

    def _item(self, combo, key):
        from PyQt6.QtCore import Qt
        model = combo.model()
        for i in range(model.rowCount()):
            if model.item(i).data(Qt.ItemDataRole.UserRole) == key:
                return model.item(i)
        raise AssertionError(f"no row for {key}")

    def test_it_opens_showing_six_systems_and_the_two_niches(self):
        combo = self._combo()
        self.assertEqual(len(self._visible(combo)), 8)

    def test_every_level_is_present_in_the_model(self):
        """Collapsed is not absent: the rows exist and are only hidden, so a
        filter the user set and then collapsed is still set."""
        combo = self._combo()
        self.assertGreater(combo.model().rowCount(), 100)

    def test_opening_a_system_reveals_its_regions(self):
        combo = self._combo()
        before = len(self._visible(combo))
        combo._set_expanded(self._item(combo, "zone_boreal_plains"), True)
        after = self._visible(combo)
        self.assertGreater(len(after), before)
        self.assertIn("mid_boreal_uplands",
                      [i.data(0x0100) for i in after])

    def test_closing_a_system_hides_the_whole_subtree(self):
        """Not one level. Re-opening a branch must not surface grandchildren
        the user had already collapsed."""
        combo = self._combo()
        zone = self._item(combo, "zone_boreal_plains")
        combo._set_expanded(zone, True)
        combo._set_expanded(self._item(combo, "mid_boreal_uplands"), True)
        combo._set_expanded(zone, False)
        self.assertEqual(len(self._visible(combo)), 8)
        combo._set_expanded(zone, True)
        keys = [i.data(0x0100) for i in self._visible(combo)]
        self.assertNotIn("sub_central_mixedwood", keys)

    def test_a_parent_row_shows_a_disclosure_marker(self):
        combo = self._combo()
        zone = self._item(combo, "zone_boreal_plains")
        self.assertTrue(zone.text().lstrip().startswith("▸"))
        combo._set_expanded(zone, True)
        self.assertTrue(zone.text().lstrip().startswith("▾"))

    def test_a_moisture_niche_is_flat(self):
        """`riparian` is a condition, not a place. It sits inside every
        ecozone, so nesting it under one would say something false."""
        from src.filter_widgets import DEPTH_ROLE
        self.assertEqual(self._item(self._combo(), "riparian").data(DEPTH_ROLE), 0)

    def test_the_summary_shows_the_bare_label_not_the_indented_one(self):
        combo = self._combo()
        combo.set_checked_keys(["mid_boreal_uplands"])
        self.assertEqual(combo.lineEdit().text(), "Mid-Boreal Uplands")

    def test_checking_a_system_is_one_key_that_expands_at_query_time(self):
        """Checking an ecozone stays one checked row — the search expands it.
        Auto-checking 27 descendants would make the summary read "27 selected"
        for one click and lose which choice the user actually made."""
        from src.ecoregion_tree import expand_for_filter
        combo = self._combo()
        combo.set_checked_keys(["zone_boreal_plains"])
        self.assertEqual(combo.checked_keys(), ["zone_boreal_plains"])
        self.assertIn("mid_boreal_uplands",
                      expand_for_filter(combo.checked_keys()))
