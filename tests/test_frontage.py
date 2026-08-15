"""
tests/test_frontage.py — which edge faces the street (V2.58).

``cues_to_care`` needs to know which side the public sees, and until now the app
held no road data at all, so it reused the ``sidewalk`` camera's documented
south-edge assumption and said so. The author asked for the real thing.

Roads now come from the same Overpass source that already supplies trees and
buildings. Everything here is network-free — roads go in as data.
"""

import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

_TMP = tempfile.mkdtemp(prefix="permadesign_frontage_")
try:
    import src.db.plants as _plants_mod
    _plants_mod._DATA_DIR = _TMP
    _plants_mod._DB_PATH = os.path.join(_TMP, "t.db")
except Exception:  # pragma: no cover
    pass

from src import frontage as fr  # noqa: E402

#: A ~65 m square lot centred near (53.5005, -113.4995).
_RING = [[-113.500, 53.500], [-113.499, 53.500], [-113.499, 53.501],
         [-113.500, 53.501], [-113.500, 53.500]]


def _road(line, name="Test St", highway="residential"):
    return {"line": line, "name": name, "highway": highway}


def _project(roads=None):
    p = {"type": "FeatureCollection", "properties": {}, "features": [
        {"type": "Feature",
         "properties": {"element_type": "property_boundary"},
         "geometry": {"type": "Polygon", "coordinates": [_RING]}}]}
    if roads:
        fr.store_roads(p, roads)
    return p


class TestItFindsTheRightEdge(unittest.TestCase):
    """A street on each side, from a road line that runs well past the lot —
    which is the case that broke the first implementation."""

    _CASES = {
        "east":  [[-113.4988, 53.4990], [-113.4988, 53.5020]],
        "west":  [[-113.5002, 53.4990], [-113.5002, 53.5020]],
        "south": [[-113.5010, 53.5002], [-113.4980, 53.5002]],
        "north": [[-113.5010, 53.5008], [-113.4980, 53.5008]],
    }

    def test_each_direction(self):
        for side, line in self._CASES.items():
            with self.subTest(side=side):
                f = fr.frontage_from_roads(_RING, [_road(line)])
                self.assertTrue(f.measured, f"{side} road was not measured")
                self.assertEqual(f.side, side)

    def test_it_uses_the_closest_point_not_the_nearest_endpoint(self):
        """The bug the four-direction test caught: a road running north–south
        well past the lot has both endpoints diagonally away, so taking an
        endpoint reported a due-east street as 'south-east'. The frontage would
        have named the wrong edge on most real lots."""
        f = fr.frontage_from_roads(_RING, [_road(self._CASES["east"])])
        self.assertEqual(f.side, "east")
        self.assertAlmostEqual(f.bearing, 90.0, delta=5.0)

    def test_the_nearest_road_wins(self):
        far = _road([[-113.4900, 53.4990], [-113.4900, 53.5020]], name="Far")
        near = _road(self._CASES["south"], name="Near")
        f = fr.frontage_from_roads(_RING, [far, near])
        self.assertEqual(f.road_name, "Near")


class TestItAdmitsWhenItIsGuessing(unittest.TestCase):
    """A measurement that cannot say when it is a guess is worse than a guess
    that admits it."""

    def test_no_roads_falls_back_and_says_so(self):
        f = fr.frontage_from_roads(_RING, [])
        self.assertFalse(f.measured)
        self.assertEqual(f.side, "south")
        self.assertIn("assuming", f.note)

    def test_a_distant_road_is_not_this_property_s_frontage(self):
        far = _road([[-113.4900, 53.4990], [-113.4900, 53.5020]])
        self.assertFalse(fr.frontage_from_roads(_RING, [far]).measured)

    def test_no_boundary_falls_back(self):
        self.assertFalse(
            fr.frontage_from_roads([], [_road([[0, 0], [0, 1]])]).measured)

    def test_a_measured_note_names_the_road(self):
        f = fr.frontage_from_roads(
            _RING, [_road([[-113.4988, 53.4990], [-113.4988, 53.5020]],
                          name="Maple Street")])
        self.assertIn("Maple Street", f.note)
        self.assertIn("mapped road data", f.note)
        self.assertNotIn("assuming", f.note)


class TestStorage(unittest.TestCase):
    def test_roads_round_trip_through_the_project(self):
        p = _project([_road([[-113.4988, 53.4990], [-113.4988, 53.5020]])])
        self.assertEqual(len(fr.roads_in_project(p)), 1)
        self.assertTrue(fr.frontage_for_project(p).measured)

    def test_re_storing_replaces_rather_than_accumulates(self):
        """Move the pin, re-fetch — the old street must not linger."""
        p = _project([_road([[-113.4988, 53.4990], [-113.4988, 53.5020]])])
        fr.store_roads(p, [_road([[-113.5002, 53.4990], [-113.5002, 53.5020]])])
        self.assertEqual(len(fr.roads_in_project(p)), 1)
        self.assertEqual(fr.frontage_for_project(p).side, "west")

    def test_storing_roads_leaves_other_features_alone(self):
        p = _project([_road([[-113.4988, 53.4990], [-113.4988, 53.5020]])])
        kinds = [(f.get("properties") or {}).get("element_type")
                 for f in p["features"]]
        self.assertIn("property_boundary", kinds)


class TestTheOsmSide(unittest.TestCase):
    def test_the_parser_reads_an_open_two_node_way(self):
        """_ring_lnglat demands three vertices and closes the ring — both wrong
        for a street. A two-node way is a real road segment."""
        from src.osm_features import parse_elements
        data = {"elements": [{
            "type": "way",
            "tags": {"highway": "residential", "name": "Maple St"},
            "geometry": [{"lat": 53.499, "lon": -113.4988},
                         {"lat": 53.502, "lon": -113.4988}]}]}
        roads = [f for f in parse_elements(data) if f["kind"] == "road"]
        self.assertEqual(len(roads), 1)
        self.assertEqual(len(roads[0]["line"]), 2)
        self.assertNotEqual(roads[0]["line"][0], roads[0]["line"][-1],
                            "the road line was closed like a ring")

    def test_footpaths_are_not_streets(self):
        """The question is which edge the public sees from the road; a back-lane
        cycle path is not that."""
        from src.osm_features import parse_elements
        data = {"elements": [{
            "type": "way", "tags": {"highway": "footway"},
            "geometry": [{"lat": 53.499, "lon": -113.4988},
                         {"lat": 53.502, "lon": -113.4988}]}]}
        self.assertEqual(
            [f for f in parse_elements(data) if f["kind"] == "road"], [])

    def test_roads_do_not_inflate_the_import_count(self):
        """A road is useful precisely because it is outside the property.
        Counting it as an imported feature would pad 'found 12 buildings' with
        things the user never asked to place."""
        from src.osm_features import import_osm_result
        p = _project()
        out = import_osm_result(
            {"buildings": [], "trees": [],
             "roads": [_road([[-113.4988, 53.4990], [-113.4988, 53.5020]])]},
            p, boundary=None)
        self.assertEqual(out["added"], 0)
        self.assertEqual(len(fr.roads_in_project(p)), 1)

    def test_a_failed_fetch_still_reports_failure(self):
        from src.osm_features import import_osm_result
        out = import_osm_result(None, _project())
        self.assertEqual(out["added"], 0)
        self.assertIn("didn't answer", out["message"])


class TestCuesToCareUsesIt(unittest.TestCase):
    def test_the_line_reports_a_measurement_when_there_is_one(self):
        from src import cues_to_care as cc
        p = _project([_road([[-113.4988, 53.4990], [-113.4988, 53.5020]],
                            name="Maple Street")])
        line = [c for c in cc.assess(p, get_plant=lambda _i: {})
                if c.key == cc.MOWN_EDGE][0].line
        self.assertIn("east edge", line)
        self.assertIn("Maple Street", line)
        self.assertNotIn("assuming", line)

    def test_it_still_says_assuming_with_no_road_data(self):
        from src import cues_to_care as cc
        line = [c for c in cc.assess(_project(), get_plant=lambda _i: {})
                if c.key == cc.MOWN_EDGE][0].line
        self.assertIn("assuming", line)

    def test_only_the_mown_edge_mentions_the_frontage(self):
        """Unchanged from V2.56: a wrong frontage still costs one line."""
        from src import cues_to_care as cc
        p = _project([_road([[-113.4988, 53.4990], [-113.4988, 53.5020]])])
        for cue in cc.assess(p, get_plant=lambda _i: {}):
            if cue.key == cc.MOWN_EDGE:
                continue
            with self.subTest(cue=cue.key):
                self.assertNotIn("edge, from mapped", cue.line or "")


if __name__ == "__main__":
    unittest.main()
