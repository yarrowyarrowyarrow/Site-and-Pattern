"""
tests/test_make_example.py — a design becomes the worked example (F254, V3.38).

The owner: *"Either choose a better location for this layout or let me make a
design that will be the example design."* ``scripts/make_example.py`` turns a
saved design into the pack's ``example``; ``src.onboarding`` builds the
example back from it. These tests hold the round trip (what the owner drew is
what opens, to the centimetre), what is refused (no outline, no plants, a
plant not native here, notes carrying plant-use words), what is never
carried (the address, the design's name), and where the example opens.
"""

import copy
import json
import os
import pathlib
import shutil
import sys
import tempfile
import unittest
from types import SimpleNamespace
from unittest import mock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

_ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_ROOT / "scripts"))

import make_example  # noqa: E402
from src import native_here, onboarding, region  # noqa: E402
from src.projection import metres_per_deg  # noqa: E402

_LAT, _LNG = 53.5600, -113.4100
_CATALOGUE = make_example._catalogue()


def _local_natives(n: int) -> list:
    """``n`` catalogue plants on the default pack's native list."""
    key = region.default().key
    names = sorted(c for c, row in _CATALOGUE.items()
                   if native_here.native_around(row["scientific_name"], key))
    return names[:n]


def _ll(east: float, north: float) -> list:
    """``[lng, lat]`` of a point ``east``/``north`` metres from the corner."""
    m_lat, m_lng = metres_per_deg(_LAT)
    return [round(_LNG + east / m_lng, 8), round(_LAT + north / m_lat, 8)]


def _poly(kind, corners, **props):
    ring = [_ll(*c) for c in corners] + [_ll(*corners[0])]
    return {"type": "Feature",
            "geometry": {"type": "Polygon", "coordinates": [ring]},
            "properties": dict(props, element_type=kind)}


def _pt(kind, east, north, **props):
    return {"type": "Feature",
            "geometry": {"type": "Point", "coordinates": _ll(east, north)},
            "properties": dict(props, element_type=kind)}


def _design(plants=None, notes="Two drifts along the walk.") -> dict:
    """A 15 × 9 m front yard: a house, a walk, a bed, a tree, a brush pile
    and a planting, with the address in the places a real design keeps it."""
    plants = plants if plants is not None else [     # all inside the bed
        (name, 2.0 + 0.7 * i, 2.0 + 0.6 * (i % 3))
        for i, name in enumerate(_local_natives(6) * 2)]
    return {
        "type": "FeatureCollection",
        "properties": {
            "project_name": "8103 95A Street NW",
            "notes": notes,
            "site_config": {"latitude": _LAT, "longitude": _LNG,
                            "pin_label": "8103, 95A Street NW, Edmonton"},
        },
        "features": [
            _poly("property_boundary", [(0, 0), (15, 0), (15, 9), (0, 9)],
                  boundary_id="b1", color="#66bb6a"),
            _poly("custom_shape", [(1, 1), (10, 1), (10, 4), (1, 4)],
                  shape_type="Garden Bed", label="Front bed",
                  fill_color="#6d8a3a", shape_id="shape_x", area_m2=27.0),
            _poly("custom_shape", [(11, 0), (12.2, 0), (12.2, 6), (11, 6)],
                  shape_type="Pathway", label="Walk"),
            _poly("canopy_footprint", [(2, 6), (13, 6), (13, 9), (2, 9)],
                  shape_type="Building (OSM)", label="Building (OSM)",
                  height_m=7.0, cast_shade=True, source="osm",
                  lat=_LAT, lng=_LNG),
            _pt("existing_tree", 14.0, 1.0, height_m=9.0,
                canopy_radius_m=3.0, label="Boulevard elm", source="osm"),
            _pt("structure", 9.0, 5.0, struct_id="brush_pile",
                name="Brush Pile", size_m=1.5),
        ] + [_pt("plant", e, n, plant_id=1000 + i, common_name=name)
             for i, (name, e, n) in enumerate(plants)],
    }


def _lookup(name):
    return ({"id": sorted(_CATALOGUE).index(name) + 1, "common_name": name}
            if name in _CATALOGUE else None)


class ADesignBecomesTheExample(unittest.TestCase):

    def setUp(self):
        self.pack = region.default()
        self.design = _design()
        self.example = make_example.example_from_design(self.design,
                                                        self.pack)

    def test_it_is_a_valid_example(self):
        self.assertEqual(region.example_errors(self.example), [])
        self.assertTrue(self.example["own_place"])
        self.assertEqual(len(self.example["outline"]), 4)
        self.assertEqual(
            sorted(f["kind"] for f in self.example["features"]),
            ["canopy_footprint", "custom_shape", "custom_shape",
             "existing_tree", "structure"])

    def test_it_never_carries_the_address_or_the_designs_name(self):
        text = json.dumps(self.example)
        self.assertNotIn("95A", text)
        self.assertNotIn("pin_label", text)
        self.assertEqual(self.example["name"], make_example.DEFAULT_NAME)

    def test_plants_are_names_and_metres(self):
        planted = [names[0] for names, _ in self.example["planting"]]
        self.assertEqual(len(planted), 12)
        for names, (east, north) in self.example["planting"]:
            self.assertIn(names[0], _CATALOGUE)
            self.assertTrue(0 <= east <= 15.01 and 0 <= north <= 9.01)
        self.assertNotIn("plant_id", json.dumps(self.example["planting"]))

    def test_only_the_named_properties_travel(self):
        building = next(f for f in self.example["features"]
                        if f["kind"] == "canopy_footprint")
        self.assertEqual(building["props"]["height_m"], 7.0)
        for gone in ("lat", "lng", "source", "shape_id"):
            self.assertNotIn(gone, building["props"])
        bed = next(f for f in self.example["features"]
                   if f["props"].get("shape_type") == "Garden Bed")
        self.assertNotIn("area_m2", bed["props"])

    def test_the_designs_notes_travel(self):
        self.assertEqual(self.example["notes"], "Two drifts along the walk.")
        self.assertEqual(onboarding.example_notes(self.example),
                         "Two drifts along the walk.")

    def test_no_notes_gives_a_plain_line_with_no_species_named(self):
        ex = make_example.example_from_design(_design(notes=""), self.pack)
        self.assertIn("12 plants of 6 kinds", ex["notes"])
        self.assertIn("native around", ex["notes"])
        for name in _local_natives(6):
            self.assertNotIn(name, ex["notes"])


class TheRoundTrip(unittest.TestCase):
    """What the owner drew is what opens: corners, shapes and plants back
    within 5 cm, on the same lot."""

    def setUp(self):
        self.design = _design()
        self.example = make_example.example_from_design(self.design,
                                                        region.default())
        self.project, self.missing = onboarding.build_example_project(
            lookup=_lookup, example=self.example)

    def _features(self, project, kind):
        return [f for f in project["features"]
                if f["properties"]["element_type"] == kind]

    @staticmethod
    def _close(a, b, metres=0.05):
        m_lat, m_lng = metres_per_deg(_LAT)
        return (abs(a[0] - b[0]) * m_lng <= metres
                and abs(a[1] - b[1]) * m_lat <= metres)

    def test_it_opens_on_the_same_lot(self):
        sc = self.project["properties"]["site_config"]
        self.assertEqual(sc["pin_label"], "Example site")
        mine = self._features(self.design, "property_boundary")[0]
        back = self._features(self.project, "property_boundary")[0]
        for a, b in zip(mine["geometry"]["coordinates"][0],
                        back["geometry"]["coordinates"][0]):
            self.assertTrue(self._close(a, b), (a, b))

    def test_every_plant_comes_back_where_it_was(self):
        self.assertEqual(self.missing, [])
        mine = self._features(self.design, "plant")
        back = self._features(self.project, "plant")
        self.assertEqual(len(back), len(mine))
        for a, b in zip(mine, back):
            self.assertEqual(a["properties"]["common_name"],
                             b["properties"]["common_name"])
            self.assertTrue(self._close(a["geometry"]["coordinates"],
                                        b["geometry"]["coordinates"]))

    def test_the_shapes_house_tree_and_brush_pile_come_back(self):
        shapes = self._features(self.project, "custom_shape")
        self.assertEqual(sorted(f["properties"]["shape_type"] for f in shapes),
                         ["Garden Bed", "Pathway"])
        bed = next(f for f in shapes
                   if f["properties"]["shape_type"] == "Garden Bed")
        self.assertAlmostEqual(bed["properties"]["area_m2"], 27.0, delta=0.2)
        house = self._features(self.project, "canopy_footprint")[0]
        self.assertEqual(house["properties"]["height_m"], 7.0)
        self.assertGreater(house["properties"]["canopy_radius_m"], 2)
        tree = self._features(self.project, "existing_tree")[0]
        self.assertEqual(tree["properties"]["struct_id"], "existing_tree")
        pile = self._features(self.project, "structure")[0]
        self.assertEqual(pile["properties"]["struct_def"]["id"], "brush_pile")
        self.assertEqual(pile["properties"]["struct_def"]["size_m"], 1.5)

    def test_ids_are_fresh_and_distinct(self):
        ids = [f["properties"]["shape_id"] for f in self.project["features"]
               if "shape_id" in f["properties"]]
        self.assertEqual(len(ids), len(set(ids)))
        self.assertNotIn("shape_x", ids)

    def test_the_planting_is_measured(self):
        lines = make_example.report(self.example)
        text = "\n".join(lines)
        self.assertIn("12 plants of 6 kinds", text)
        self.assertIn("% once grown", text)


class WhatIsRefused(unittest.TestCase):

    def _refused(self, design, words):
        with self.assertRaises(make_example.Refused) as ctx:
            make_example.example_from_design(design, region.default())
        self.assertIn(words, str(ctx.exception))

    def test_no_outline(self):
        design = _design()
        design["features"] = [f for f in design["features"]
                              if f["properties"]["element_type"]
                              != "property_boundary"]
        self._refused(design, "no yard outline")

    def test_no_plants(self):
        self._refused(_design(plants=[]), "no plants")

    def test_a_plant_not_native_here(self):
        key = region.default().key
        off = next(c for c, row in sorted(_CATALOGUE.items())
                   if not native_here.native_around(row["scientific_name"],
                                                    key))
        self._refused(_design(plants=[(off, 2, 2)]), off)

    def test_notes_carrying_plant_use_words(self):
        """P12: the example's notes ship in every copy and open in Site ›
        Notes; they do not carry plant-use knowledge."""
        self._refused(_design(notes="A traditional use of these roots is…"),
                      "P12")


class TheFormatIsChecked(unittest.TestCase):

    def setUp(self):
        self.example = make_example.example_from_design(_design(),
                                                        region.default())

    def test_the_shipped_example_is_valid(self):
        self.assertEqual(region.example_errors(region.default().example), [])

    def test_an_unknown_field_is_refused(self):
        ex = dict(self.example, address="8103 95A Street NW")
        self.assertTrue(any("unknown fields address" in e
                            for e in region.example_errors(ex)))

    def test_an_unknown_kind_or_property_is_refused(self):
        ex = copy.deepcopy(self.example)
        ex["features"].append({"kind": "hot_tub", "at": [1, 1], "props": {}})
        ex["features"][0]["props"]["uses"] = "tea"
        errs = " ".join(region.example_errors(ex))
        self.assertIn("'hot_tub'", errs)
        self.assertIn("unknown properties uses", errs)

    def test_a_polygon_needs_a_ring(self):
        ex = copy.deepcopy(self.example)
        poly = next(f for f in ex["features"] if "ring" in f)
        del poly["ring"]
        self.assertTrue(any("needs 'ring'" in e
                            for e in region.example_errors(ex)))


class WritingIt(unittest.TestCase):
    """``--write`` replaces the example and leaves the rest of the pack's file
    byte for byte as it was formatted."""

    def test_only_the_example_changes(self):
        tmp = pathlib.Path(tempfile.mkdtemp(prefix="make_example_"))
        self.addCleanup(shutil.rmtree, tmp)
        key = region.default().key
        src = _ROOT / "data" / "regions" / key / "region.json"
        dest = tmp / "data" / "regions" / key
        dest.mkdir(parents=True)
        shutil.copy(src, dest / "region.json")
        before = json.loads(src.read_text(encoding="utf-8"))
        example = make_example.example_from_design(_design(),
                                                   region.default())
        with mock.patch.object(make_example, "PROJECT_ROOT", tmp):
            path = make_example.write(example, key)
        text = path.read_text(encoding="utf-8")
        after = json.loads(text)
        self.assertEqual(after["example"], example)
        self.assertEqual({k: v for k, v in after.items() if k != "example"},
                         {k: v for k, v in before.items() if k != "example"})
        self.assertEqual(text, json.dumps(after, indent=2,
                                          ensure_ascii=False) + "\n")
        self.assertEqual(region.validate(after, key), [])

    def test_the_shipped_file_is_in_the_form_write_writes(self):
        key = region.default().key
        text = (_ROOT / "data" / "regions" / key / "region.json").read_text(
            encoding="utf-8")
        self.assertEqual(text, json.dumps(json.loads(text), indent=2,
                                          ensure_ascii=False) + "\n")


class WhereItOpens(unittest.TestCase):

    def _main(self, coords):
        panel = SimpleNamespace(current_coords=lambda: coords)
        return SimpleNamespace(site_panel=panel)

    def test_the_generic_example_follows_a_pin_inside_the_pack(self):
        from src import onboarding_flow
        inside = tuple(region.default().centre)
        with mock.patch.object(onboarding, "EXAMPLE_OWN_PLACE", False):
            self.assertEqual(onboarding_flow.example_position(
                self._main(inside)), inside)
            self.assertEqual(onboarding_flow.example_position(
                self._main((43.65, -79.38))), (None, None), "not Toronto")
            self.assertEqual(onboarding_flow.example_position(
                self._main(None)), (None, None))

    def test_an_example_made_from_a_lot_opens_on_that_lot(self):
        from src import onboarding_flow
        inside = tuple(region.default().centre)
        with mock.patch.object(onboarding, "EXAMPLE_OWN_PLACE", True):
            self.assertEqual(onboarding_flow.example_position(
                self._main(inside)), (None, None))


if __name__ == "__main__":
    unittest.main()
