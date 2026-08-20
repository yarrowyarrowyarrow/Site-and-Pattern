"""
tests/test_planting_document.py

The take-it-outside document: site prep (F43), the numbered planting map (F41)
and the maintenance calendar (F42), plus the module that assembles all five
sections in the order the work happens.

The properties that matter here are about honesty and usability rather than
formatting:

  * prep advice keys off the soil texture, and the sheet always states how much
    the soil figure can be trusted — a regional estimate is not a measurement;
  * map numbers key EXACTLY to the F40 buy list, or the two documents send the
    user to the wrong hole;
  * maintenance hours FALL across the bands — the whole P4 story — and the
    spring-cut-back rule names the user's own species;
  * a section that raises never costs the user the rest of the document.
"""

import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

_TMP_DIR = tempfile.mkdtemp(prefix="permadesign_plandoc_test_")
try:
    import src.db.plants as _plants_mod
    _plants_mod._DATA_DIR = _TMP_DIR
    _plants_mod._DB_PATH = os.path.join(_TMP_DIR, "permadesign_test.db")
except Exception:                                    # pragma: no cover
    pass

from src import maintenance_calendar as mc  # noqa: E402
from src import planting_map as pmap_mod  # noqa: E402
from src import planting_plan_export as export  # noqa: E402
from src import site_prep as sp  # noqa: E402


def _placed(pid, name, lat, lng, **extra):
    d = {"plant_id": pid, "common_name": name, "lat": lat, "lng": lng}
    d.update(extra)
    return d


def _project_with_boundary():
    return {"type": "FeatureCollection",
            "properties": {"site_config": {}},
            "features": [{
                "type": "Feature",
                "geometry": {"type": "Polygon", "coordinates": [[
                    [-113.5000, 53.5000], [-113.4998, 53.5000],
                    [-113.4998, 53.5001], [-113.5000, 53.5001],
                    [-113.5000, 53.5000]]]},
                "properties": {"element_type": "property_boundary"}}]}


# ── F43 · Site prep ──────────────────────────────────────────────────────────

class TestSitePrep(unittest.TestCase):

    def _regional(self, texture="Clay", ph=7.6):
        return {"soil_texture": texture, "soil_ph": ph,
                "soil": {"fallback": True,
                         "summary": {"ph_top": ph, "texture_class": texture}}}

    def _measured(self, texture="Loam", ph=6.8):
        return {"soil_texture": texture, "soil_ph": ph,
                "soil": {"summary": {"ph_top": ph, "texture_class": texture},
                         "source": "Gridded Soil Landscapes of Canada"}}

    def test_advice_keys_off_the_texture(self):
        clay = sp.build_site_prep(self._regional("Clay"), [],
                                  bed_area_m2=50, get_plant=lambda _p: {})
        sand = sp.build_site_prep(self._regional("Sand"), [],
                                  bed_area_m2=50, get_plant=lambda _p: {})
        clay_text = sp.render_prep_text(clay)
        sand_text = sp.render_prep_text(sand)
        self.assertIn("clay", clay_text.lower())
        self.assertIn("Never work heavy clay wet", clay_text)
        self.assertNotIn("Never work heavy clay wet", sand_text)
        self.assertIn("drought-tolerant", sand_text)

    def test_it_says_do_not_enrich(self):
        # The contrarian core: enriching a native bed feeds the weeds. If this
        # ever quietly becomes generic "dig in compost" advice, fail loudly.
        prep = sp.build_site_prep(self._regional(), [], bed_area_m2=50,
                                  get_plant=lambda _p: {})
        text = sp.render_prep_text(prep)
        self.assertIn("do NOT enrich", text)
        self.assertIn("STRUCTURE, not fertility", text)

    def test_regional_soil_is_flagged_as_an_estimate(self):
        prep = sp.build_site_prep(self._regional(), [], bed_area_m2=50,
                                  get_plant=lambda _p: {})
        self.assertEqual(prep.soil_basis, "regional")
        joined = " ".join(prep.caveats)
        self.assertIn("REGIONAL approximation", joined)
        self.assertIn("jar test", joined)

    def test_measured_soil_is_not_called_regional(self):
        prep = sp.build_site_prep(self._measured(), [], bed_area_m2=50,
                                  get_plant=lambda _p: {})
        self.assertEqual(prep.soil_basis, "measured")
        self.assertNotIn("REGIONAL approximation", " ".join(prep.caveats))

    def test_no_soil_data_says_so_rather_than_guessing(self):
        prep = sp.build_site_prep({}, [], bed_area_m2=0,
                                  get_plant=lambda _p: {})
        self.assertEqual(prep.soil_basis, "unknown")
        self.assertIn("No soil data", " ".join(prep.caveats))

    def test_mulch_volume_is_a_range_from_the_area(self):
        prep = sp.build_site_prep(self._regional(), [], bed_area_m2=100,
                                  get_plant=lambda _p: {})
        # 5–8 cm over 100 m².
        self.assertAlmostEqual(prep.mulch_m3_low, 5.0, delta=0.2)
        self.assertAlmostEqual(prep.mulch_m3_high, 8.0, delta=0.2)
        self.assertLess(prep.mulch_m3_low, prep.mulch_m3_high)

    def test_ph_mismatch_flags_only_species_with_a_recorded_bracket(self):
        plants = {1: {"common_name": "Acid Lover", "soil_ph_min": 4.0,
                      "soil_ph_max": 5.5},
                  2: {"common_name": "Happy Anywhere", "soil_ph_min": 5.0,
                      "soil_ph_max": 8.0},
                  3: {"common_name": "Unrecorded"}}
        got = sp.ph_mismatches(
            [_placed(i, plants[i].get("common_name", ""), 0, 0)
             for i in (1, 2, 3)],
            ph=7.6, get_plant=plants.get)
        self.assertEqual(len(got), 1)
        self.assertIn("Acid Lover", got[0])

    def test_ph_mismatch_uses_the_same_slack_as_plant_search(self):
        # 0.5 of a pH unit, because a regional estimate is coarse; flagging on
        # 0.1 would be noise dressed as advice.
        plants = {1: {"common_name": "Edge Case", "soil_ph_min": 5.0,
                      "soil_ph_max": 7.0}}
        self.assertEqual(
            sp.ph_mismatches([_placed(1, "Edge Case", 0, 0)], ph=7.4,
                             get_plant=plants.get), [])
        self.assertEqual(
            len(sp.ph_mismatches([_placed(1, "Edge Case", 0, 0)], ph=7.9,
                                 get_plant=plants.get)), 1)

    def test_bare_ground_for_ground_nesting_bees_is_always_included(self):
        prep = sp.build_site_prep(self._regional(), [], bed_area_m2=50,
                                  get_plant=lambda _p: {})
        self.assertIn("Leave some ground bare",
                      [s.title for s in prep.steps])

    def test_steps_are_numbered_in_order(self):
        prep = sp.build_site_prep(self._regional(), [], bed_area_m2=50,
                                  get_plant=lambda _p: {})
        self.assertEqual([s.order for s in prep.steps],
                         list(range(1, len(prep.steps) + 1)))


# ── F41 · The numbered planting map ──────────────────────────────────────────

class _FakeItem:
    def __init__(self, plant_id, common_name, qty=1):
        self.plant_id = plant_id
        self.common_name = common_name
        self.scientific_name = ""
        self.plant_type = "shrub"
        self.qty = qty
        self.spacing_m = 1.5


class _FakePlan:
    def __init__(self, items):
        self.items = items


class TestPlantingMap(unittest.TestCase):

    def _plants(self):
        return [_placed(1, "Saskatoon Berry", 53.50005, -113.49995),
                _placed(1, "Saskatoon Berry", 53.50007, -113.49990),
                _placed(2, "Wild Bergamot", 53.50003, -113.49985)]

    def test_numbers_follow_the_buy_list_exactly(self):
        # Deliberately NOT alphabetical, to prove the map follows the plan
        # rather than re-deriving its own order.
        plan = _FakePlan([_FakeItem(2, "Wild Bergamot", 1),
                          _FakeItem(1, "Saskatoon Berry", 2)])
        pm = pmap_mod.build_planting_map(
            self._plants(), _project_with_boundary(), plan=plan)
        by_id = {mp.plant_id: mp.number for mp in pm.placements}
        self.assertEqual(by_id[2], 1)
        self.assertEqual(by_id[1], 2)
        self.assertEqual([k.number for k in pm.key], [1, 2])

    def test_every_plant_of_one_species_shares_its_number(self):
        plan = _FakePlan([_FakeItem(1, "Saskatoon Berry", 2),
                          _FakeItem(2, "Wild Bergamot", 1)])
        pm = pmap_mod.build_planting_map(
            self._plants(), _project_with_boundary(), plan=plan)
        sask = [mp.number for mp in pm.placements if mp.plant_id == 1]
        self.assertEqual(len(sask), 2)
        self.assertEqual(len(set(sask)), 1)

    def test_positions_are_positive_metres_from_the_sw_corner(self):
        pm = pmap_mod.build_planting_map(self._plants(),
                                         _project_with_boundary(),
                                         get_plant=lambda _p: {})
        self.assertTrue(pm.placements)
        for mp in pm.placements:
            self.assertGreater(mp.x_m, 0)
            self.assertGreater(mp.y_m, 0)
            self.assertLess(mp.x_m, pm.width_m)
            self.assertLess(mp.y_m, pm.height_m)

    def test_boundary_is_closed_and_in_the_same_frame(self):
        pm = pmap_mod.build_planting_map(self._plants(),
                                         _project_with_boundary(),
                                         get_plant=lambda _p: {})
        self.assertGreaterEqual(len(pm.boundary), 4)
        self.assertEqual(pm.boundary[0], pm.boundary[-1])

    def test_no_boundary_still_produces_a_usable_plan(self):
        pm = pmap_mod.build_planting_map(self._plants(), {"features": []},
                                         get_plant=lambda _p: {})
        self.assertTrue(pm.placements)
        self.assertEqual(pm.boundary, [])
        self.assertIn("No property boundary",
                      " ".join(pm.caveats))

    def test_empty_design_is_well_formed(self):
        pm = pmap_mod.build_planting_map([], _project_with_boundary(),
                                         get_plant=lambda _p: {})
        self.assertEqual(pm.placements, [])
        self.assertIn("No plants placed", " ".join(pm.caveats))

    def test_scale_bar_is_a_round_number_that_fits(self):
        for width, expected_max in ((14.0, 14.0), (40.0, 40.0), (3.0, 3.0)):
            pm = pmap_mod.PlantingMap(width_m=width)
            bar = pm.scale_bar_m()
            self.assertIn(bar, pmap_mod._SCALE_STEPS)
            self.assertLess(bar, expected_max)

    def test_key_text_carries_positions_for_a_tape_measure(self):
        # The text export has no drawing, so it must still be layout-able.
        pm = pmap_mod.build_planting_map(self._plants(),
                                         _project_with_boundary(),
                                         get_plant=lambda _p: {})
        text = pmap_mod.render_map_key_text(pm)
        self.assertIn("POSITIONS", text)
        self.assertIn(" E ", text)
        self.assertIn(" N ", text)

    def test_spacing_is_not_quoted_to_the_millimetre(self):
        self.assertEqual(pmap_mod._spacing_str(0.878), "0.9 m")
        self.assertEqual(pmap_mod._spacing_str(0.585), "0.6 m")


# ── F42 · Maintenance calendar ───────────────────────────────────────────────

class TestMaintenanceCalendar(unittest.TestCase):

    def _design(self, n=6, native=True):
        return [_placed(i, f"Plant {i}", 0, 0, plant_type="shrub",
                        native_to_alberta=native) for i in range(1, n + 1)]

    def _cal(self, **kw):
        kw.setdefault("get_plant", lambda _p: {})
        kw.setdefault("fauna_edges", lambda _ids: [])
        return mc.build_maintenance_calendar(self._design(), **kw)

    def test_the_work_falls_across_the_bands(self):
        # This IS the feature (P4). If the curve ever flattens or inverts, the
        # design's central promise stops being true on paper.
        cal = self._cal()
        highs = [b.hours_high for b in cal.bands]
        self.assertEqual(highs, sorted(highs, reverse=True))
        self.assertLess(cal.bands[-1].hours_high, cal.bands[0].hours_high / 2)

    def test_cultivated_plants_do_not_ramp_down_as_far(self):
        native = mc.build_maintenance_calendar(
            self._design(native=True), get_plant=lambda _p: {},
            fauna_edges=lambda _i: [])
        cultivated = mc.build_maintenance_calendar(
            self._design(native=False), get_plant=lambda _p: {},
            fauna_edges=lambda _i: [])
        self.assertLess(native.bands[-1].hours_high,
                        cultivated.bands[-1].hours_high)

    def test_hours_are_ranges_not_figures(self):
        cal = self._cal()
        for band in cal.bands:
            self.assertLess(band.hours_low, band.hours_high)

    def test_year_one_leads_with_water(self):
        cal = self._cal()
        first = cal.bands[0]
        self.assertIn("Water DEEPLY", first.tasks[0])

    def test_spring_cutback_note_is_present_and_explained(self):
        cal = self._cal()
        self.assertIn("spring, not fall", cal.overwintering_note)
        text = mc.render_maintenance_text(cal)
        self.assertIn("WHY SPRING AND NOT FALL", text)

    def test_overwintering_species_come_from_documented_edges_only(self):
        rows = [{"plant_id": 1, "relationship": "nesting"},
                {"plant_id": 2, "relationship": "nectar"},
                {"plant_id": 3, "relationship": "cover"}]
        got = mc.overwintering_species(
            [_placed(1, "Stemmy", 0, 0), _placed(2, "Nectar Only", 0, 0),
             _placed(3, "Shelter", 0, 0)],
            get_plant=lambda _p: {}, fauna_edges=lambda _ids: rows)
        self.assertEqual(got, ["Shelter", "Stemmy"])

    def test_bands_line_up_with_the_succession_stages(self):
        from src import succession
        cal = self._cal()
        for band in cal.bands:
            self.assertIn(succession.restoration_stage(band.year_from),
                          band.stage)

    def test_band_for_year_covers_every_year(self):
        cal = self._cal()
        for year in (1, 2, 4, 5, 9, 10, 40):
            self.assertIsNotNone(cal.band_for_year(year), year)

    def test_structures_add_their_own_upkeep(self):
        without = self._cal()
        with_struct = mc.build_maintenance_calendar(
            self._design(), structures=[{"id": "pond"}],
            get_plant=lambda _p: {}, fauna_edges=lambda _i: [],
            get_structure=lambda _sid: {"name": "Pond",
                                        "maintenance_hours_year": 8})
        self.assertGreater(with_struct.bands[-1].hours_high,
                           without.bands[-1].hours_high)
        self.assertEqual(with_struct.structure_hours, 8.0)

    def test_effort_constants_are_shared_with_the_planning_panel(self):
        # One set of numbers, two surfaces — the panel imports them from here.
        panel_src = _read("src/planning_panel.py")
        self.assertIn("from src.maintenance_calendar import "
                      "PLANT_MAINTENANCE_HOURS", panel_src)
        self.assertNotIn('"tree":        3.0,   # pruning', panel_src)


def _read(rel):
    from pathlib import Path
    return (Path(__file__).resolve().parent.parent / rel
            ).read_text(encoding="utf-8")


# ── The assembled document ───────────────────────────────────────────────────

class TestDocumentAssembly(unittest.TestCase):
    """The assembler has no injection seams — it is the wiring layer — so
    these run against the real (temp) catalogue."""

    @classmethod
    def setUpClass(cls):
        from src.db.plants import init_db
        init_db()

    def test_sections_appear_in_the_order_the_work_happens(self):
        text = export.assemble(
            _project_with_boundary(),
            [_placed(1, "Saskatoon Berry", 53.50005, -113.49995,
                     plant_type="shrub", native_to_alberta=True)],
            [], _FakePlan([_FakeItem(1, "Saskatoon Berry")]),
            bed_area_m2=40.0, plan_text="WHAT TO BUY")
        order = [text.index(marker) for marker in
                 ("SITE PREP", "WHAT TO BUY", "PLANTING MAP", "MAINTENANCE")]
        self.assertEqual(order, sorted(order))

    def test_a_failing_section_does_not_cost_the_document(self):
        # A planting plan that fails to export because the soil lookup hiccuped
        # would be a worse failure than one missing its soil page.
        broken = lambda: (_ for _ in ()).throw(RuntimeError("boom"))  # noqa: E731
        self.assertEqual(export._section(broken), "")
        text = export.assemble(
            {"features": None},        # makes the prep/map sections throw
            [_placed(1, "X", 53.5, -113.5)], [],
            _FakePlan([_FakeItem(1, "X")]), plan_text="WHAT TO BUY")
        self.assertIn("WHAT TO BUY", text)

    def test_empty_design_still_returns_a_string(self):
        text = export.assemble({"features": []}, [], [],
                               _FakePlan([]), plan_text="WHAT TO BUY")
        self.assertIsInstance(text, str)
        self.assertIn("WHAT TO BUY", text)


class TestPdfFontSizing(unittest.TestCase):
    """The PDF export sized fonts in POINTS from a device-pixel figure.

    On a 1200-DPI PDF printer that made a "9 pt" body font 112 pt — about
    2,100 device pixels tall, drawn into a rect 175 pixels high — so Qt clipped
    it and every text page came out blank while the rules and boxes around it
    drew fine. Guarded as source structure because reproducing it needs a real
    QPrinter.
    """

    def test_no_point_sized_fonts_survive(self):
        src = _read("src/pdf_export.py")
        self.assertNotIn("_safe_size", src,
                         "the point-size clamp is the bug's fingerprint")
        self.assertNotIn('QFont("Arial",', src,
                         "fonts must go through _font(), which sets a PIXEL "
                         "size")

    def test_font_helper_uses_pixel_size(self):
        src = _read("src/pdf_export.py")
        self.assertIn("setPixelSize", src)


if __name__ == "__main__":
    unittest.main()
