"""
tests/test_region_packs.py — every region pack is whole, and the pin chooses
it (V3.24, ED-1; docs/homeowner/08-edmonton-edition.md §4.9).

A pack is data, so what a test can hold is that its parts agree: the manifest
validates and carries no field the module does not name (P12), its centre is in
its own province, every nursery it names is in the directory, every species of
its worked example is in the catalogue and native around it (which would have
caught R14), its climate block is complete, its rulings carry no reason.
"""

import json
import os
import re
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src import region  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _manifest(key):
    with open(os.path.join(ROOT, "data", "regions", key, "region.json"),
              encoding="utf-8") as fh:
        return json.load(fh)


class EveryPackIsWhole(unittest.TestCase):

    def setUp(self):
        self.packs = region.regions()
        self.assertTrue(self.packs, "no region pack shipped")

    def test_each_manifest_validates(self):
        for key in self.packs:
            self.assertEqual(region.validate(_manifest(key), key), [], key)

    def test_unknown_fields_are_refused(self):
        """P12: no field for plant uses or cultural knowledge can be added in
        passing."""
        doc = dict(_manifest("edmonton"))
        doc["plant_uses"] = {}
        self.assertTrue(any("unknown fields" in e
                            for e in region.validate(doc, "edmonton")))

    def test_the_centre_is_in_the_packs_province(self):
        from src.site_fit import province_at
        for key, r in self.packs.items():
            self.assertEqual(province_at(*r.centre), r.province, key)

    def test_every_nursery_is_in_the_directory(self):
        with open(os.path.join(ROOT, "data", "nurseries_master.json"),
                  encoding="utf-8") as fh:
            doc = json.load(fh)
        rows = doc.get("nurseries", doc) if isinstance(doc, dict) else doc
        names = {r.get("name") for r in rows}
        for key, r in self.packs.items():
            self.assertTrue(r.nurseries, key)
            for name in r.nurseries:
                self.assertIn(name, names, key)

    def test_the_example_resolves_and_is_native_around_the_pack(self):
        """R14 would have failed here: Canada Goldenrod and Showy Milkweed."""
        from src import native_here
        with open(os.path.join(ROOT, "data", "plants_master.json"),
                  encoding="utf-8") as fh:
            sci = {p["common_name"]: p["scientific_name"]
                   for p in json.load(fh)}
        for key, r in self.packs.items():
            for names, _off in r.example["planting"]:
                first = next((n for n in names if n in sci), None)
                self.assertIsNotNone(first, f"{key}: none of {names} in the "
                                            "catalogue")
                for n in names:
                    if n in sci:
                        self.assertTrue(native_here.native_around(sci[n], key),
                                        f"{key}: {n} is not native around it")

    def test_the_climate_block_is_complete(self):
        for key, r in self.packs.items():
            self.assertEqual(len(r.climate["monthly_precip_mm"]), 12, key)
            for k in ("last_spring_frost", "first_fall_frost"):
                month, day = map(int, r.climate[k].split("-"))
                self.assertTrue(1 <= month <= 12 and 1 <= day <= 31, key)
            for k in ("station", "period", "source"):
                self.assertTrue(r.climate[k], (key, k))

    def test_no_ruling_carries_a_reason(self):
        for key in self.packs:
            with open(region.rulings_path(key), encoding="utf-8") as fh:
                rows = (json.load(fh).get("places") or {}).get(key) or {}
            for name, ruling in rows.items():
                self.assertNotIn("reason", ruling, (key, name))

    def test_each_pack_has_its_list(self):
        from src import native_here
        for key in self.packs:
            self.assertGreater(len(native_here.native_names(key)), 0, key)

    def test_the_map_page_cold_load_matches_the_default_pack(self):
        """``html/map/01-core.js`` keeps a literal for the moment before
        Python speaks; it must be the default pack's map centre."""
        with open(os.path.join(ROOT, "html", "map", "01-core.js"),
                  encoding="utf-8") as fh:
            js = fh.read()
        m = re.search(r"center:\s*\[\s*(-?[\d.]+)\s*,\s*(-?[\d.]+)\s*\]", js)
        self.assertIsNotNone(m)
        self.assertEqual((float(m.group(1)), float(m.group(2))),
                         tuple(region.default().map["centre"]))

    def test_the_edition_names_a_shipped_pack(self):
        with open(os.path.join(ROOT, "data", "edition.json"),
                  encoding="utf-8") as fh:
            edition = json.load(fh)
        self.assertIn(edition["default_region"], self.packs)
        self.assertEqual(region.default().key, edition["default_region"])


class ThePinChoosesThePack(unittest.TestCase):
    """§4.5: four kinds of pin, and what each is told."""

    def test_downtown_red_deer_toronto_and_no_pin(self):
        self.assertEqual(region.coverage(53.52, -113.52).kind, region.REGION)
        red_deer = region.coverage(52.27, -113.81)
        self.assertEqual(red_deer.kind, region.PROVINCE)
        self.assertAlmostEqual(red_deer.distance_km, 150, delta=15)
        self.assertEqual(region.coverage(43.65, -79.38).kind, region.OUTSIDE)
        self.assertEqual(region.coverage().kind, region.NO_PIN)

    def test_what_each_is_told(self):
        self.assertEqual(region.message(region.coverage(53.52, -113.52)),
                         "Edmonton region.")
        far = region.message(region.coverage(52.27, -113.81))
        self.assertTrue(far.startswith("This pin is 144 km from Edmonton, "
                                       "outside the area Site & Pattern is "
                                       "set up for."), far)
        self.assertIn("everything native to Alberta", far)
        self.assertEqual(
            region.message(region.coverage(43.65, -79.38)),
            "This pin is outside Alberta and Saskatchewan. Site & Pattern "
            "knows the plants, climate and nurseries of the Edmonton region "
            "only, so it can't suggest plants for this yard.")
        self.assertEqual(region.message(region.coverage()), "")

    def test_a_design_takes_its_pins_pack_else_the_default(self):
        inside = {"latitude": 53.6, "longitude": -113.4}
        self.assertEqual(region.for_site(inside).key, "edmonton")
        self.assertEqual(region.for_site({}).key, region.default().key)

    def test_the_place_line(self):
        """ED-5 (EDF-2): every PDF said "Edmonton, Alberta" whatever the pin."""
        self.assertEqual(region.place_line(53.52, -113.52),
                         "Edmonton region, Alberta")
        self.assertEqual(region.place_line(50.45, -104.6), "50.4500, -104.6000")
        self.assertEqual(region.place_line(), "")


class TheLocalGoalFollowsThePin(unittest.TestCase):
    """ED-3 and EDF-3: "Edmonton natives only" had restricted a Regina or
    Calgary design to the Edmonton list (0 off-list species in both runs)."""

    def test_a_pin_outside_every_pack_gets_no_local_list(self):
        from src import design_goals
        regina = {"latitude": 50.45, "longitude": -104.6}
        self.assertEqual(design_goals.filters_for_goals(["local_native"],
                                                        regina), {})
        self.assertNotIn("local_native",
                         [g.key for g in design_goals.goals_for_site(regina)])

    def test_a_saved_design_with_the_old_key_keeps_the_goal(self):
        from src import design_goals
        self.assertEqual(design_goals.normalize(["edmonton_native", "pollinator"]),
                         ["local_native", "pollinator"])
        self.assertEqual(design_goals.filters_for_goals(["edmonton_native"]),
                         {"native_near": "edmonton"})

    def test_the_picker_and_the_switch_say_the_regions_name(self):
        import pathlib
        from src import plant_filters as pf
        q = next(q for q in pf.QUALITIES if q.key == "local_native")
        self.assertEqual(q.label, f"Native around {region.default().short}")
        self.assertEqual(q.value, region.default().key)
        self.assertEqual(pf.criteria_to_kwargs({"edmonton_native": True}),
                         {"native_near": region.default().key})
        panel = (pathlib.Path(ROOT) / "src" / "polyculture_panel.py").read_text(
            encoding="utf-8")
        self.assertIn('f"{self._home.short} natives only"', panel)


class ASecondPackNeedsNoCode(unittest.TestCase):
    """A synthetic pack is found, chosen by its pin and named in messages."""

    def setUp(self):
        doc = dict(_manifest("edmonton"))
        doc.update(key="testville", name="Testville region", short="Testville",
                   area={"centre": [51.05, -114.07], "radius_km": 40},
                   map={"centre": [51.05, -114.07], "zoom": 12})
        packs = dict(region.regions())
        packs["testville"] = region.from_doc(doc)
        region.set_regions(packs)
        self.addCleanup(region.set_regions, None)

    def test_its_pin_chooses_it(self):
        self.assertEqual(region.at(51.06, -114.05).key, "testville")
        self.assertEqual(region.message(region.coverage(51.06, -114.05)),
                         "Testville region.")
        self.assertEqual(region.at(53.52, -113.52).key, "edmonton")

    def test_its_goal_is_named_and_keyed_by_it(self):
        """ED-3: "Testville natives only", filtering to its own list, with no
        code; a design pinned there gets it, an Edmonton one keeps its own."""
        from src import design_goals
        tv = region.regions()["testville"]
        g = design_goals.local_goal(tv)
        self.assertEqual(g.label, "Testville natives only")
        self.assertEqual(g.filters, {"native_near": "testville"})
        here = {"latitude": 51.06, "longitude": -114.05}
        self.assertEqual(design_goals.filters_for_goals(["local_native"], here),
                         {"native_near": "testville"})
        edm = {"latitude": 53.52, "longitude": -113.52}
        self.assertEqual(design_goals.filters_for_goals(["local_native"], edm),
                         {"native_near": "edmonton"})

    def test_the_local_flora_places_grow_with_it(self):
        from src import local_flora
        self.assertIn("testville", local_flora.places())


if __name__ == "__main__":
    unittest.main()
