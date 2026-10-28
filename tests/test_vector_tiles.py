"""
tests/test_vector_tiles.py — buildings off OpenStreetMap's map tiles (V3.37).

When no Overpass server answers, the import reads the buildings off
OpenFreeMap's tiles (``src/vector_tiles.py``). The suite has no network, and
the app's decoder is its own, so it is checked against a tile written by a
reference encoder, ``mapbox-vector-tile`` 2.2.0, with ``y_coord_down`` (tile
units as the format stores them); the library is not a dependency. The tile:

  building      1 a house, 100 × 80 units at (1000, 1000), render_height 8 (int)
                2 a courtyard building, 12.5 (double), with a hole
                3 an outline with hide_3d (its part is drawn too)
                4 that part, 20
                5 a building of the next tile, in this one's buffer (x 4100)
                6 one with no height recorded
                7 one building in two pieces, 6
  transportation, water   other layers, to be passed over
"""

import base64
import gzip
import json
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src import osm_features as osm  # noqa: E402
from src import vector_tiles as vt  # noqa: E402

TILE = base64.b64decode(
    "Gj0KDnRyYW5zcG9ydGF0aW9uEhASAgAAGAIiCAkAAAqAQIBAGgVjbGFzcyINCgtyZXNpZGVu"
    "dGlhbCiAIHgCGrsCCghidWlsZGluZxIaEgQAAAEBGAMiEAnQD9APGsgBAACgAccBAA8SKBIC"
    "AAIYAyIgCaAfoB8a2AQAANgE1wQADwnIAY8DGgDIAcgBAADHAQ8SGhIEAAMCBBgDIhAJ8C7o"
    "BxrIAQAAyAHHAQAPEhYSAgADGAMiDgnwLugHGmQAAMgBYwAPEhUSAgAFGAMiDQmIQMgBGmQA"
    "AGRjAA8SFRICAwYYAyINCegH8C4aeAAAeHcADxIhEgIABxgDIhkJkAOQAxpkAABkYwAPCcgB"
    "ZBpkAABkYwAPGg1yZW5kZXJfaGVpZ2h0GhFyZW5kZXJfbWluX2hlaWdodBoHaGlkZV8zZBoG"
    "Y29sb3VyIgIgCCICIAAiCRkAAAAAAAApQCICIBQiAjgBIgIgByIJCgcjZDlkMGM5IgIgBiiA"
    "IHgCGjMKBXdhdGVyEhYSAgAAGAMiDgkUFBqgAQAAoAGfAQAPGgVjbGFzcyIGCgRsYWtlKIAg"
    "eAI=")
# The zoom-14 tile holding (53.5, -113.5), Edmonton's south side.
Z, X, Y = 14, 3026, 5299


def box(x0, y0, x1, y1):
    return [(x0, y0), (x1, y0), (x1, y1), (x0, y1)]


class TheDecoder(unittest.TestCase):

    def test_it_reads_what_the_reference_encoder_wrote(self):
        extent, polygons = vt.layer_polygons(TILE)
        self.assertEqual(extent, 4096)
        self.assertEqual(polygons, [
            ({"render_height": 8, "render_min_height": 0},
             [box(1000, 1000, 1100, 1080)]),
            # The courtyard is a hole, and holes are left out.
            ({"render_height": 12.5}, [box(2000, 2000, 2300, 2300)]),
            ({"render_height": 20, "hide_3d": True},
             [box(3000, 500, 3100, 600)]),
            ({"render_height": 20}, [box(3000, 500, 3050, 600)]),
            ({"render_height": 7}, [box(4100, 100, 4150, 150)]),
            ({"colour": "#d9d0c9"}, [box(500, 3000, 560, 3060)]),
            ({"render_height": 6},
             [box(200, 200, 250, 250), box(300, 300, 350, 350)]),
        ])

    def test_other_layers_are_passed_over_or_read_by_name(self):
        self.assertEqual(vt.layer_polygons(TILE, "water"),
                         (4096, [({"class": "lake"}, [box(10, 10, 90, 90)])]))
        self.assertIsNone(vt.layer_polygons(TILE, "poi"))
        # A line is not a polygon.
        self.assertEqual(vt.layer_polygons(TILE, "transportation"), (4096, []))

    def test_the_buildings_of_a_tile(self):
        found = vt.tile_buildings(TILE, Z, X, Y)
        # The outline with parts and the neighbour's building are not here.
        self.assertEqual([b["height_m"] for b in found],
                         [8.0, 12.5, 20.0, 5.0, 6.0, 6.0])
        house = found[0]
        self.assertEqual(house["kind"], "building")
        self.assertEqual(house["footprint"][0], house["footprint"][-1])
        lng, lat = vt.to_lnglat(Z, X, Y, 1000, 1000)
        self.assertAlmostEqual(house["footprint"][0][0], lng, places=9)
        self.assertAlmostEqual(house["footprint"][0][1], lat, places=9)
        # 100 × 80 units at zoom 14 and 53.5 degrees are about 35.5 × 28.4 m,
        # so the circle round it is half the diagonal, 22.7 m.
        self.assertAlmostEqual(house["radius_m"], 22.7, delta=0.3)
        # What the Overpass import expects of a building.
        self.assertTrue(osm.add_features_to_project(
            found, {"features": []}))

    def test_a_building_counts_where_its_middle_is_unless_that_is_not_asked(self):
        # Building 5 sits in the strip this tile repeats of the next one.
        homes = []
        found = vt.tile_buildings(TILE, Z, X, Y, keep=lambda tx, ty: (
            homes.append((tx, ty)) or True))
        self.assertIn((X + 1, Y), homes)
        self.assertIn(7.0, [b["height_m"] for b in found])
        # By default only this tile's own.
        self.assertNotIn(7.0, [b["height_m"]
                               for b in vt.tile_buildings(TILE, Z, X, Y)])

    def test_a_tile_sent_compressed(self):
        self.assertEqual(vt.tile_buildings(gzip.compress(TILE), Z, X, Y),
                         vt.tile_buildings(TILE, Z, X, Y))

    def test_a_broken_tile_raises_and_is_not_read_as_empty(self):
        with self.assertRaises((ValueError, IndexError)):
            vt.tile_buildings(TILE[:200], Z, X, Y)


class TheGround(unittest.TestCase):

    def test_tiles_and_points_agree(self):
        self.assertEqual(vt.tile_xy(53.5, -113.5, Z), (X, Y))
        west, north = vt.to_lnglat(Z, X, Y, 0, 0)
        east, south = vt.to_lnglat(Z, X, Y, 4096, 4096)
        self.assertTrue(west <= -113.5 <= east and south <= 53.5 <= north)
        # About 1.45 km across, here.
        self.assertAlmostEqual((east - west) * 111320 * 0.595, 1455, delta=10)

    def test_a_yard_is_one_tile_and_a_seam_two(self):
        yard = {"south": 53.4995, "north": 53.5005, "west": -113.5005,
                "east": -113.4995}
        self.assertEqual(vt.tiles_for_bbox(yard, Z), [(X, Y)])
        east_edge, _ = vt.to_lnglat(Z, X, Y, 4096, 0)
        seam = dict(yard, west=east_edge - 0.0005, east=east_edge + 0.0005)
        self.assertEqual(vt.tiles_for_bbox(seam, Z), [(X, Y), (X + 1, Y)])


class TheFetch(unittest.TestCase):
    """``_get`` stands in for the network: the TileJSON, then the tile."""

    TEMPLATE = "https://tiles.openfreemap.org/planet/2026_x/{z}/{x}/{y}.pbf"

    def _bbox_round_the_house(self):
        (w, n), (e, s) = (vt.to_lnglat(Z, X, Y, 990, 990),
                          vt.to_lnglat(Z, X, Y, 1110, 1090))
        return {"south": s, "north": n, "west": w, "east": e}

    def _get(self, answers):
        asked = []

        def get(url):
            asked.append(url)
            return answers.get(url, osm.Unanswered(
                osm._host(url), osm.UNREACHABLE, "not in the test"))
        return get, asked

    def test_the_buildings_in_the_box(self):
        tile_url = self.TEMPLATE.format(z=Z, x=X, y=Y)
        get, asked = self._get({
            vt.TILEJSON_URL: json.dumps(
                {"tiles": [self.TEMPLATE], "maxzoom": 14}).encode(),
            tile_url: TILE})
        found = vt.fetch_buildings(self._bbox_round_the_house(), _get=get)
        self.assertEqual(asked, [vt.TILEJSON_URL, tile_url])
        self.assertEqual([b["height_m"] for b in found], [8.0])

    def test_each_failure_is_said(self):
        bbox = self._bbox_round_the_house()
        why = []
        get, _ = self._get({})
        self.assertIsNone(vt.fetch_buildings(bbox, why=why, _get=get))
        self.assertEqual(why[0].host, "tiles.openfreemap.org")
        self.assertEqual(why[0].kind, osm.UNREACHABLE)

        why = []
        get, _ = self._get({vt.TILEJSON_URL: b"<html>no</html>"})
        self.assertIsNone(vt.fetch_buildings(bbox, why=why, _get=get))
        self.assertEqual(why[0].kind, osm.GARBLED)

        why = []
        get, _ = self._get({
            vt.TILEJSON_URL: json.dumps({"tiles": [self.TEMPLATE]}).encode(),
            self.TEMPLATE.format(z=Z, x=X, y=Y): TILE[:200]})
        self.assertIsNone(vt.fetch_buildings(bbox, why=why, _get=get))
        self.assertEqual(why[0].kind, osm.GARBLED)

    def test_a_city_is_not_asked_for(self):
        city = {"south": 53.3, "north": 53.7, "west": -113.8, "east": -113.2}
        get, asked = self._get({vt.TILEJSON_URL: json.dumps(
            {"tiles": [self.TEMPLATE]}).encode()})
        self.assertIsNone(vt.fetch_buildings(city, _get=get))
        self.assertEqual(asked, [vt.TILEJSON_URL])


class TheFallback(unittest.TestCase):
    """Overpass first; the tiles only when no Overpass server answered."""

    def setUp(self):
        self._overpass, self._tiles = osm._fetch_overpass, vt.fetch_buildings
        self.addCleanup(setattr, osm, "_fetch_overpass", self._overpass)
        self.addCleanup(setattr, vt, "fetch_buildings", self._tiles)

    def _overpass_fails(self, query, why=None, on_miss=None, **_kw):
        why.append(osm.Unanswered("overpass-api.de", osm.BUSY, "HTTP 429"))
        return None

    def test_overpass_answers_and_the_tiles_are_not_asked(self):
        osm._fetch_overpass = lambda q, **kw: {"elements": []}
        vt.fetch_buildings = lambda *a, **k: self.fail("tiles asked")
        res = osm.fetch_with_fallback({"south": 53.5, "north": 53.501,
                                       "west": -113.5, "east": -113.499})
        self.assertNotIn("from_tiles", res)

    def test_the_tiles_answer_when_overpass_does_not(self):
        osm._fetch_overpass = self._overpass_fails
        building = vt.tile_buildings(TILE, Z, X, Y)[0]
        vt.fetch_buildings = lambda bbox, why=None: [building]
        told, why = [], []
        res = osm.fetch_with_fallback({"south": 53.5, "north": 53.501,
                                       "west": -113.5, "east": -113.499},
                                      why=why, on_tiles=lambda: told.append(1))
        self.assertEqual(told, [1])
        self.assertEqual(res, {"buildings": [building], "trees": [],
                               "roads": [], "from_tiles": True})
        self.assertEqual(why[0].kind, osm.BUSY)
        # The import says where they came from, and keeps the streets an
        # earlier import stored (the tiles bring none).
        project = {"features": [], "properties": {}}
        from src.frontage import store_roads
        store_roads(project, [{"kind": "road", "line": [[-113.5, 53.5],
                                                        [-113.49, 53.5]],
                               "name": "81 Ave", "highway": "residential"}])
        before = json.dumps(project["properties"], sort_keys=True)
        out = osm.import_osm_result(res, project)
        self.assertTrue(out["from_tiles"])
        self.assertIn(osm.TILES_NOTE, out["message"])
        self.assertEqual(out["added"], 1)
        self.assertEqual(json.dumps(project["properties"], sort_keys=True),
                         before)

    def test_neither_answers(self):
        osm._fetch_overpass = self._overpass_fails

        def no_tiles(bbox, why=None):
            why.append(osm.Unanswered("tiles.openfreemap.org",
                                      osm.UNREACHABLE, "refused"))
        vt.fetch_buildings = no_tiles
        why = []
        self.assertIsNone(osm.fetch_with_fallback(
            {"south": 53.5, "north": 53.501, "west": -113.5,
             "east": -113.499}, why=why))
        words = osm.failure_words(why)
        self.assertIn("busy", words)
        self.assertIn("overpass-api.de HTTP 429", words)
        self.assertIn("tiles.openfreemap.org not reached", words)


class TheServersSay(unittest.TestCase):
    """V3.37: the failure line ends with each server's answer, so a
    screenshot of it says what the log would."""

    def test_each_server_in_a_word_or_two(self):
        u = osm.Unanswered
        words = osm.server_words([
            u("overpass-api.de", osm.BUSY, "HTTP 429"),
            u("overpass.private.coffee", osm.BUSY,
              "runtime error: Query timed out in \"query\""),
            u("overpass.kumi.systems", osm.SLOW, "no answer in 30 s"),
            u("overpass-api.de", osm.BUSY,
              "runtime error: Query run out of memory using about 70 MB"),
            u("tiles.openfreemap.org", osm.CERTIFICATE, "self-signed")])
        self.assertEqual(words, (
            "overpass-api.de HTTP 429 · overpass.private.coffee cut its "
            "answer short · overpass.kumi.systems too slow · overpass-api.de "
            "out of memory · tiles.openfreemap.org certificate not checked"))

    def test_a_query_that_ran_out_of_memory_is_asked_again_without_maxsize(self):
        asked = []

        def send(url, body=None, context=None):
            asked.append(body)
            if b"maxsize" in body:
                return (b'{"elements": [], "remark": "runtime error: Query run '
                        b'out of memory in \\"query\\" using about 70 MB"}')
            return b'{"elements": [{"type": "node", "id": 1}]}'

        orig = osm._send
        osm._send = send
        self.addCleanup(setattr, osm, "_send", orig)
        yard = {"south": 53.5, "north": 53.501, "west": -113.5,
                "east": -113.499}
        with self.assertLogs(osm.log, "WARNING"):
            got = osm._post_overpass(osm._query(yard, True, True), "https://x")
        self.assertEqual(got["elements"], [{"type": "node", "id": 1}])
        self.assertEqual(len(asked), 2)


if __name__ == "__main__":
    unittest.main()
