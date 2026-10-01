"""
tests/test_plant_picker.py — one picker for three screens (F192, V3.00).

The picker drives the real query against a temp catalogue: a filter that is
drawn but not wired is the dead-control shape this app has shipped before, and
only pressing the control catches it. Also here: what each part of a row says
about itself (finding 5 of the V2.98 review), and the community builder, which
had a picker of its own until V3.00.
"""

import os
import shutil
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

_TMP = tempfile.mkdtemp(prefix="sp_picker_")
import src.db.plants as _plants  # noqa: E402
_plants._DATA_DIR = _TMP
_plants._DB_PATH = os.path.join(_TMP, "permadesign_test.db")

try:
    from PyQt6.QtCore import QRect, Qt
    from PyQt6.QtWidgets import QApplication, QWidget
    _HAVE_QT = True
except Exception:                                          # noqa: BLE001
    _HAVE_QT = False


def tearDownModule():
    shutil.rmtree(_TMP, ignore_errors=True)


def _app():
    return QApplication.instance() or QApplication(["permadesign-tests"])


@unittest.skipUnless(_HAVE_QT, "PyQt6 not installed in this env")
class TestThePicker(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls._app = _app()
        _plants.init_db()

    def setUp(self):
        from src.plant_picker import PlantPicker
        self.holder = QWidget()
        self.addCleanup(self.holder.deleteLater)
        self.picker = PlantPicker(self.holder)
        self.picker.refresh()

    def test_a_side_panel_starts_folded_and_says_nothing_is_on(self):
        self.assertFalse(self.picker.filters_open())
        self.assertEqual(self.picker.chip_texts(), [])
        self.assertEqual(self.picker.none_label.text(), "None on")
        self.assertFalse(self.picker.none_label.isHidden())
        self.assertTrue(self.picker.clear_button.isHidden())

    def test_the_folded_line_names_what_is_on_and_clear_clears_it(self):
        self.picker.chips["native_only"].setChecked(True)
        self.picker.set_facet("type", ["shrub"])
        self.assertEqual(self.picker.chip_texts(), ["Type: Shrub", "Native"])
        self.assertTrue(self.picker.none_label.isHidden())
        self.assertFalse(self.picker.clear_button.isHidden())
        before = len(self.picker.rows())
        self.picker.clear_button.click()
        self.assertEqual(self.picker.chip_texts(), [])
        self.assertFalse(self.picker.chips["native_only"].isChecked())
        self.assertEqual(self.picker.combos["type"].checked_keys(), [])
        self.assertGreater(len(self.picker.rows()), before)

    def test_clear_keeps_what_was_typed(self):
        self.picker.search_box.setText("aster")
        self.picker.chips["edible_only"].setChecked(True)
        self.picker.clear_filters()
        self.assertEqual(self.picker.search_box.text(), "aster")
        self.assertTrue(all("aster" in (r["common_name"] + r["scientific_name"]
                                        + (r.get("permaculture_uses") or "")
                                        ).lower() for r in self.picker.rows()))

    def test_the_filters_button_folds_and_unfolds(self):
        self.picker.filters_button.click()
        self.assertTrue(self.picker.filters_open())
        self.assertIn("▾", self.picker.filters_button.text())
        self.picker.filters_button.click()
        self.assertFalse(self.picker.filters_open())

    def test_every_control_has_a_name_a_screen_reader_can_read(self):
        """The review found one filter of nine with a name."""
        for key, combo in self.picker.combos.items():
            self.assertTrue(combo.accessibleName().endswith(" filter"), key)
            self.assertEqual(combo.lineEdit().accessibleName(),
                             combo.accessibleName())
        for key, chip in self.picker.chips.items():
            self.assertTrue(chip.text(), key)
            self.assertTrue(chip.accessibleDescription(), key)
        self.assertEqual(self.picker.search_box.accessibleName(),
                         "Search plants")
        self.assertEqual(self.picker.order_combo.accessibleName(),
                         "Order plants by")

    def test_every_quality_reaches_the_query(self):
        """Each one narrows the shipped catalogue (the least, Native, by
        nine), so a quality that comes back with every plant is not wired."""
        every = len(self.picker.rows())
        for key, chip in self.picker.chips.items():
            chip.setChecked(True)
            narrowed = len(self.picker.rows())
            chip.setChecked(False)
            self.assertLess(narrowed, every, key)
            self.assertGreater(narrowed, 0, key)

    def test_set_criteria_replaces_rather_than_merges(self):
        self.picker.chips["edible_only"].setChecked(True)
        self.picker.set_criteria({"type": ["tree"]})
        self.assertFalse(self.picker.chips["edible_only"].isChecked())
        self.assertEqual({r["plant_type"] for r in self.picker.rows()}, {"tree"})

    def test_no_site_means_name_order_and_no_suits_choice(self):
        self.assertEqual(self.picker.order(), "name")
        combo = self.picker.order_combo
        suits = combo.findData("suits")
        self.assertFalse(combo.model().item(suits).isEnabled())

    def test_a_site_makes_suits_the_order_until_the_reader_picks(self):
        self.picker.set_site((53.55, -113.49), zone=3)
        self.assertEqual(self.picker.order(), "suits")
        names = [r["common_name"] for r in self.picker.rows()]
        from src.zoning import needs_standing_water
        wet = [needs_standing_water(r) for r in self.picker.rows()]
        self.assertEqual(wet, sorted(wet), "pond plants are not last")
        self.assertEqual(len(names), len(set(names)))
        # The reader's own choice survives a new site.
        self.picker.set_order("type")
        self.picker.set_site((50.0, -110.0), zone=4)
        self.assertEqual(self.picker.order(), "type")

    def test_losing_the_site_leaves_suits(self):
        self.picker.set_site((53.55, -113.49))
        self.picker.set_site(None)
        self.assertEqual(self.picker.order(), "name")

    def test_the_selection_survives_a_reorder(self):
        self.picker.view.setCurrentIndex(self.picker.model.index(5, 0))
        chosen = self.picker.current_plant()["id"]
        self.picker.set_order("height")
        self.assertEqual(self.picker.current_plant()["id"], chosen)

    def test_an_app_set_restriction_is_applied(self):
        """The site's soil pH: set by the app, not ticked by the reader."""
        every = len(self.picker.rows())
        self.picker.set_soil_ph(8.6)
        self.assertLess(len(self.picker.rows()), every)
        self.picker.set_soil_ph(None)
        self.assertEqual(len(self.picker.rows()), every)

    def test_the_count_says_when_nothing_matches(self):
        self.picker.search_box.setText("zzzz no such plant")
        self.picker.refresh()
        self.assertEqual(self.picker.count_label.text(), "No plants match")

    def test_a_window_picker_shows_its_filters(self):
        from src.plant_picker import PlantPicker
        wide = PlantPicker(self.holder, wide=True)
        self.assertTrue(wide.filters_open())

    def test_list_apart_leaves_the_list_to_its_owner(self):
        from src.plant_picker import PlantPicker
        apart = PlantPicker(self.holder, list_apart=True)
        self.assertIsNot(apart.view.parentWidget(), apart)


@unittest.skipUnless(_HAVE_QT, "PyQt6 not installed in this env")
class TestFiltersPeopleCanRead(unittest.TestCase):
    """F194, V3.01: a chosen filter keeps its name and says how it combines,
    each one can be removed alone, and an empty list says what emptied it."""

    @classmethod
    def setUpClass(cls):
        cls._app = _app()
        _plants.init_db()

    def setUp(self):
        from src.plant_picker import PlantPicker
        self.holder = QWidget()
        self.holder.resize(437, 800)
        self.addCleanup(self.holder.deleteLater)
        self.picker = PlantPicker(self.holder)
        self.picker.resize(437, 800)
        self.picker.refresh()

    def _search(self, **kwargs):
        from src.db.plants import search_plants
        return search_plants(**kwargs)

    def test_every_dropdown_names_its_dimension_and_its_rule(self):
        from src import plant_filters as pf
        for f in pf.FACETS:
            combo = self.picker.combos[f.key]
            self.assertEqual(combo.rule_text(), pf.rule(f), f.key)
        self.picker.set_facet("use", ["bird_food", "host_plant"])
        self.assertEqual(self.picker.combos["use"].lineEdit().text(),
                         "Role: Larval Host and Bird Food")
        self.assertEqual(self.picker.chip_texts(),
                         ["Role: Larval Host and Bird Food"])

    def test_a_chip_removes_its_own_filter_and_nothing_else(self):
        self.picker.set_facet("type", ["shrub", "tree"])
        self.picker.chips["edible_only"].setChecked(True)
        chips = self.picker.filter_line.chips()
        self.assertEqual(chips[0].accessibleName(),
                         "Remove Type: Tree or Shrub")
        chips[0].click()
        self.assertEqual(self.picker.combos["type"].checked_keys(), [])
        self.assertTrue(self.picker.chips["edible_only"].isChecked())
        self.assertEqual(self.picker.chip_texts(), ["Edible"])
        self.picker.filter_line.chips()[0].click()
        self.assertFalse(self.picker.chips["edible_only"].isChecked())
        self.assertEqual(self.picker.chip_texts(), [])

    def test_a_removed_chip_hands_the_keyboard_on(self):
        # Shown and settled first: a window activating later hands focus to
        # the first control in its chain, whatever was asked for before.
        self.holder.show()
        self._app.processEvents()
        self.picker.set_facet("type", ["shrub"])
        self.picker.chips["edible_only"].setChecked(True)
        self._app.processEvents()
        first = self.picker.filter_line.chips()[0]
        first.setFocus()
        self._app.processEvents()
        first.click()
        self._app.processEvents()
        now = self.picker.filter_line.chips()
        self.assertEqual(len(now), 1)
        self.assertIs(self.holder.focusWidget(), now[0], "focus was dropped")
        now[0].click()
        self._app.processEvents()
        self.assertIs(self.holder.focusWidget(), self.picker.filters_button)

    def test_taking_an_offer_hands_the_keyboard_to_the_plants(self):
        """The offer goes with the empty state; Qt would have handed the
        keyboard to the map's toolbar (measured live: "# Grid")."""
        self.holder.show()
        self._app.processEvents()
        self.picker.set_facet("type", ["fern"])
        self.picker.set_facet("bloom_months", ["1"])
        self._app.processEvents()
        offer = self.picker.why_empty.buttons()[0]
        offer.setFocus()
        self._app.processEvents()
        offer.click()
        self._app.processEvents()
        self.assertTrue(self.picker.rows())
        self.assertIs(self.holder.focusWidget(), self.picker.view)

    def test_clear_all_hands_the_keyboard_to_filters(self):
        """Clear all hides itself once nothing is on."""
        self.holder.show()
        self._app.processEvents()
        self.picker.chips["edible_only"].setChecked(True)
        self._app.processEvents()
        self.picker.clear_button.setFocus()
        self._app.processEvents()
        self.picker.clear_button.click()
        self._app.processEvents()
        self.assertIs(self.holder.focusWidget(), self.picker.filters_button)

    def _chain(self, start, wanted, steps=400):
        """The widgets of ``wanted`` in the order Tab reaches them from
        ``start``."""
        out, w = [], start
        for _ in range(steps):
            w = w.nextInFocusChain()
            if w is start:
                break
            if any(w is x for x in wanted) and not any(w is o for o in out):
                out.append(w)
        return out

    def test_tab_follows_the_line_and_the_offers(self):
        """Chips and offers are made after the window, which put them at the
        end of the tab chain, after the plant list (measured live)."""
        self.picker.set_facet("type", ["fern"])
        self.picker.set_facet("bloom_months", ["1"])
        line = self.picker.filter_line
        wanted = (line.chips() + [self.picker.clear_button,
                                  self.picker.order_combo]
                  + self.picker.why_empty.buttons() + [self.picker.view])
        self.assertEqual(self._chain(self.picker.filters_button, wanted),
                         wanted)

    def test_typing_does_not_rebuild_the_chips(self):
        """Rebuilding on every keystroke would pull a focused chip out from
        under the keyboard."""
        self.picker.set_facet("type", ["shrub"])
        before = self.picker.filter_line.chips()
        self.picker.search_box.setText("rose")
        self.picker.refresh()
        self.assertEqual(self.picker.filter_line.chips(), before)

    def test_the_count_says_how_much_the_filters_took(self):
        every = len(self._search())
        self.assertEqual(self.picker.count_label.text(), f"{every} plants")
        self.picker.set_facet("type", ["tree"])
        trees = len(self._search(plant_type=["tree"]))
        self.assertEqual(self.picker.count_label.text(),
                         f"{trees} of {every} plants")

    def test_an_empty_list_names_the_filter_that_emptied_it(self):
        """Ferns have no bloom window, so Blooms in empties a list of ferns."""
        self.picker.set_facet("type", ["fern"])
        self.picker.set_facet("bloom_months", ["1"])
        self.assertEqual(self.picker.rows(), [])
        ferns = len(self._search(plant_type=["fern"]))
        self.assertGreater(ferns, 0)
        offers = self.picker.why_empty.offers()
        self.assertIn(f"Remove \u201cBlooms in: January\u201d "
                      f"({ferns} plant{'s' if ferns != 1 else ''})", offers)
        self.assertFalse(self.picker.why_empty.isHidden())
        # Taking it off is the offer's own button.
        button = next(b for b in self.picker.why_empty._offers
                      if "Blooms in" in b.text())
        button.click()
        self.assertEqual(len(self.picker.rows()), ferns)
        self.assertTrue(self.picker.why_empty.isHidden())

    def test_only_offers_that_bring_plants_back_are_made(self):
        self.picker.set_facet("type", ["fern"])
        self.picker.search_box.setText("zzzz no such plant")
        self.picker.refresh()
        offers = self.picker.why_empty.offers()
        self.assertEqual(len(offers), 1, offers)
        self.assertTrue(offers[0].startswith(
            "Clear the search \u201czzzz no such plant\u201d"))

    def test_a_search_alone_says_what_was_searched_for(self):
        self.picker.search_box.setText("zzzz")
        self.picker.refresh()
        self.assertEqual(self.picker.why_empty.label.text(),
                         "No plant\u2019s name or role contains \u201czzzz\u201d.")

    def test_when_no_single_filter_is_to_blame_it_says_so(self):
        self.picker.set_facet("type", ["fern"])
        self.picker.set_facet("bloom_months", ["1"])
        self.picker.search_box.setText("zzzz")
        self.picker.refresh()
        self.assertIn("it is the combination",
                      self.picker.why_empty.label.text())
        self.assertEqual(self.picker.why_empty.offers(), ["Clear all filters"])

    def test_the_soil_ph_is_a_chip_and_a_toggle(self):
        self.assertTrue(self.picker.soil_toggle.isHidden(),
                        "a toggle for a pH nobody has")
        every = len(self.picker.rows())
        self.picker.set_soil_ph(8.0)
        shown = len(self._search(soil_ph=8.0))
        self.assertEqual(len(self.picker.rows()), shown)
        self.assertEqual(self.picker.chip_texts(), ["Your soil: pH 8.0"])
        self.assertFalse(self.picker.soil_toggle.isHidden())
        self.assertTrue(self.picker.soil_toggle.isChecked())
        self.assertEqual(self.picker.count_label.text(),
                         f"{shown} of {every} plants")
        chip = self.picker.filter_line.chips()[0]
        self.assertIn(f"hiding {every - shown} plants", chip.toolTip())
        # Rich text, so Qt wraps it (plain, it ran 1,340 px across a 1,366 px
        # screen); a screen reader is handed the words, not the markup.
        self.assertTrue(chip.toolTip().startswith("<p>"))
        self.assertIn(f"hiding {every - shown} plants",
                      chip.accessibleDescription())
        self.assertNotIn("<", chip.accessibleDescription())

    def test_removing_the_soil_ph_holds_through_a_refetch(self):
        every = len(self.picker.rows())
        self.picker.set_soil_ph(8.0)
        self.picker.filter_line.chips()[0].click()
        self.assertEqual(len(self.picker.rows()), every)
        self.assertFalse(self.picker.soil_toggle.isChecked())
        self.picker.set_soil_ph(7.9)            # a re-fetch, a new pin
        self.assertEqual(len(self.picker.rows()), every)
        self.assertEqual(self.picker.chip_texts(), [])
        self.picker.soil_toggle.setChecked(True)
        self.assertLess(len(self.picker.rows()), every)
        self.assertEqual(self.picker.chip_texts(), ["Your soil: pH 7.9"])

    def test_clear_all_clears_the_soil_ph_too(self):
        every = len(self.picker.rows())
        self.picker.set_soil_ph(8.0)
        self.picker.chips["native_only"].setChecked(True)
        self.picker.clear_button.click()
        self.assertEqual(len(self.picker.rows()), every)
        self.assertFalse(self.picker.soil_applies())
        self.assertEqual(self.picker.chip_texts(), [])

    def test_the_soil_ph_can_be_what_empties_the_list(self):
        self.picker.set_soil_ph(8.0)
        self.picker.set_facet("type", ["fern"])
        if self.picker.rows():
            self.skipTest("a fern now tolerates pH 8.0 in the catalogue")
        offers = self.picker.why_empty.offers()
        self.assertTrue(any("Your soil: pH 8.0" in o for o in offers), offers)


@unittest.skipUnless(_HAVE_QT, "PyQt6 not installed in this env")
class TestWhatARowSays(unittest.TestCase):
    """Until V3.00 every part of a row showed one tooltip, the plant's name,
    and a screen reader was given the common name alone (finding 5)."""

    _PLANT = {"id": 7, "common_name": "Saskatoon Berry",
              "scientific_name": "Amelanchier alnifolia", "plant_type": "shrub",
              "native_to_alberta": 1, "hardiness_zone_min": 2,
              "hardiness_zone_max": 7}

    @classmethod
    def setUpClass(cls):
        cls._app = _app()

    def setUp(self):
        from src.plant_list_view import PlantRowDelegate
        self.delegate = PlantRowDelegate()
        self.rect = QRect(0, 0, 420, 26)

    def _at(self, part, placed=0):
        lay = self.delegate._layout(self._PLANT, self.rect, placed)
        return self.delegate.tooltip_at(self._PLANT, self.rect, placed,
                                        lay[part].center())

    def test_each_badge_says_what_it_is(self):
        self.assertEqual(self._at("dot"), "Shrub")
        self.assertEqual(self._at("zone"), "Hardy in zones 2 to 7")
        self.assertEqual(self._at("native"), "Native to Alberta")
        self.assertEqual(self._at("name"),
                         "Saskatoon Berry (Amelanchier alnifolia)")

    def test_the_count_says_it_is_this_design(self):
        self.assertIn("2 in this design", self._at("name", placed=2))

    def test_a_non_native_says_so(self):
        from src.plant_list_view import native_words
        self.assertEqual(native_words({"native_to_alberta": 0}),
                         "Not native to Alberta")

    def test_the_row_is_read_with_its_facts(self):
        from src.plant_list_view import row_description
        self.assertEqual(
            row_description(self._PLANT, 2),
            "Saskatoon Berry, Amelanchier alnifolia. Shrub. Native to Alberta. "
            "Hardy in zones 2 to 7. 2 in this design.")

    def test_the_model_hands_the_reader_that_text(self):
        from src.plant_list_view import PlantListModel
        model = PlantListModel()
        model.set_plants([self._PLANT])
        model.set_placed_counts({7: 1})
        text = model.data(model.index(0), Qt.ItemDataRole.AccessibleTextRole)
        self.assertIn("Native to Alberta", text)
        self.assertIn("1 in this design", text)

    def test_the_card_is_gone(self):
        """No ▶, no expansion, no painted detail block: the page is beside
        the list now (src/species_page.py)."""
        import src.plant_list_view as plv
        from src.plant_list_view import PlantListModel, PlantRowDelegate
        self.assertFalse(hasattr(plv, "_PLANT_EXPANDED_ROLE"))
        self.assertFalse(hasattr(PlantListModel, "toggle_expanded"))
        self.assertFalse(hasattr(PlantRowDelegate, "_paint_calendar"))
        self.assertFalse(hasattr(PlantRowDelegate, "took_click"))

    def test_a_long_name_wraps_rather_than_hiding_its_badges(self):
        long = dict(self._PLANT, common_name="White-grained Mountain Rice Grass")
        lay = self.delegate._layout(long, QRect(0, 0, 220, 44), 0)
        self.assertTrue(lay["wrapped"])
        self.assertFalse(lay["name"].intersects(lay["native"]))


@unittest.skipUnless(_HAVE_QT, "PyQt6 not installed in this env")
class TestTheBuilderUsesThePicker(unittest.TestCase):
    """The community builder had a checkbox, four single-choice dropdowns and
    a list of plain strings filtered in Python. It is the shared picker now."""

    @classmethod
    def setUpClass(cls):
        cls._app = _app()
        _plants.init_db()

    def setUp(self):
        from src.polyculture_panel import PolycultureBuilderDialog
        self.dialog = PolycultureBuilderDialog(None)
        self.addCleanup(self.dialog.deleteLater)

    def test_it_starts_on_natives_by_the_flora(self):
        from src.db.plants import search_plants
        picker = self.dialog.picker
        self.assertTrue(picker.chips["native_only"].isChecked())
        self.assertEqual(len(picker.rows()),
                         len(search_plants(native_province="AB")))

    def test_a_layer_lifts_its_plants_and_hides_none(self):
        picker = self.dialog.picker
        every = len(picker.rows())
        self.dialog.layer_combo.setCurrentIndex(
            self.dialog.layer_combo.findData("shrub_layer"))
        rows = picker.rows()
        self.assertEqual(len(rows), every)
        types = [r["plant_type"] for r in rows]
        first_other = next(i for i, t in enumerate(types) if t != "shrub")
        self.assertTrue(all(t != "shrub" for t in types[first_other:]))
        self.assertGreater(first_other, 0)

    def test_a_function_lifts_its_plants(self):
        self.dialog.function_checks["nitrogen_fixer"].setChecked(True)
        first = self.dialog.picker.rows()[0]
        self.assertIn("nitrogen", (first.get("permaculture_uses") or "").lower())

    def test_the_grid_places_what_the_picker_has_selected(self):
        picker = self.dialog.picker
        picker.view.setCurrentIndex(picker.model.index(0, 0))
        self.assertEqual(self.dialog._selected_plant()["id"],
                         picker.rows()[0]["id"])
        self.dialog._on_canvas_add(0.5, -0.5)
        members = self.dialog.canvas.get_members()
        self.assertEqual(members[-1]["plant_id"], picker.rows()[0]["id"])

    def test_the_dead_one_at_a_time_dialog_is_gone(self):
        import src.polyculture_panel as pp
        self.assertFalse(hasattr(pp, "AddMemberDialog"))
        self.assertFalse(hasattr(pp, "OffsetCanvas"))


if __name__ == "__main__":
    unittest.main()
