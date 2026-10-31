"""
tests/test_osm_features.py

V1.51 — parsing OpenStreetMap (Overpass) responses into existing trees /
buildings and importing them into a project. Fixture-only (no live API; the
sandbox blocks egress and the live path degrades gracefully by design).
"""

import math
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import src.osm_features as osm  # noqa: E402
from src.project import new_project  # noqa: E402

# A representative Overpass response: a 2-storey building way, two trees
# (one with a crown diameter, one with a height tag), and a non-building way
# that must be ignored.
_FIXTURE = {"elements": [
    {"type": "way", "tags": {"building": "house", "building:levels": "2"},
     "geometry": [{"lat": 53.5000, "lon": -113.5000},
                  {"lat": 53.5000, "lon": -113.4998},
                  {"lat": 53.5002, "lon": -113.4998},
                  {"lat": 53.5002, "lon": -113.5000},
                  {"lat": 53.5000, "lon": -113.5000}]},
    {"type": "node", "tags": {"natural": "tree", "diameter_crown": "8"},
     "lat": 53.5005, "lon": -113.4995},
    {"type": "node", "tags": {"natural": "tree", "height": "15 m"},
     "lat": 53.5006, "lon": -113.4994},
    {"type": "way", "tags": {"highway": "residential"},
     "geometry": [{"lat": 53.5, "lon": -113.5}]},
]}


class TestParse(unittest.TestCase):
    def test_counts(self):
        feats = osm.parse_elements(_FIXTURE)
        self.assertEqual(sum(1 for f in feats if f["kind"] == "building"), 1)
        self.assertEqual(sum(1 for f in feats if f["kind"] == "tree"), 2)

    def test_building_height_from_levels(self):
        b = next(f for f in osm.parse_elements(_FIXTURE)
                 if f["kind"] == "building")
        self.assertEqual(b["height_m"], 6.0)        # 2 levels × 3 m
        self.assertGreater(b["radius_m"], 0)
        self.assertGreaterEqual(len(b["footprint"]), 4)   # keeps the true ring

    def test_tree_crown_to_radius(self):
        trees = [f for f in osm.parse_elements(_FIXTURE) if f["kind"] == "tree"]
        crowned = next(t for t in trees if abs(t["radius_m"] - 4.0) < 1e-6)
        self.assertEqual(crowned["radius_m"], 4.0)  # crown 8 → radius 4

    def test_tree_explicit_height(self):
        trees = [f for f in osm.parse_elements(_FIXTURE) if f["kind"] == "tree"]
        self.assertTrue(any(abs(t["height_m"] - 15.0) < 1e-6 for t in trees))

    def test_graceful_on_none_and_empty(self):
        self.assertEqual(osm.parse_elements(None), [])
        self.assertEqual(osm.parse_elements({}), [])
        self.assertEqual(osm.parse_elements({"elements": []}), [])

    def test_degenerate_building_skipped(self):
        bad = {"elements": [{"type": "way", "tags": {"building": "yes"},
                             "geometry": [{"lat": 1, "lon": 2}]}]}  # <3 pts
        self.assertEqual(osm.parse_elements(bad), [])

    def test_relation_building_outer_rings_parse(self):
        """Multipolygon buildings (V2.13): each closed outer member becomes a
        footprint; unclosed fragments and inner (courtyard) rings are skipped."""
        closed = [{"lat": 53.5000, "lon": -113.5000},
                  {"lat": 53.5000, "lon": -113.4996},
                  {"lat": 53.5003, "lon": -113.4996},
                  {"lat": 53.5003, "lon": -113.5000},
                  {"lat": 53.5000, "lon": -113.5000}]
        inner = [{"lat": 53.5001, "lon": -113.4999},
                 {"lat": 53.5001, "lon": -113.4998},
                 {"lat": 53.5002, "lon": -113.4998},
                 {"lat": 53.5001, "lon": -113.4999}]
        fragment = [{"lat": 53.5004, "lon": -113.5000},
                    {"lat": 53.5004, "lon": -113.4996},
                    {"lat": 53.5006, "lon": -113.4996}]   # not closed
        rel = {"elements": [{
            "type": "relation",
            "tags": {"building": "apartments", "building:levels": "4"},
            "members": [
                {"type": "way", "role": "outer", "geometry": closed},
                {"type": "way", "role": "inner", "geometry": inner},
                {"type": "way", "role": "outer", "geometry": fragment},
            ],
        }]}
        feats = osm.parse_elements(rel)
        self.assertEqual(len(feats), 1)
        b = feats[0]
        self.assertEqual(b["kind"], "building")
        self.assertEqual(b["height_m"], 12.0)          # 4 levels × 3 m
        self.assertGreaterEqual(len(b["footprint"]), 4)

    def test_relation_without_building_tag_ignored(self):
        rel = {"elements": [{
            "type": "relation", "tags": {"landuse": "residential"},
            "members": [{"type": "way", "role": "outer",
                         "geometry": [{"lat": 1, "lon": 1}, {"lat": 1, "lon": 2},
                                      {"lat": 2, "lon": 2}, {"lat": 1, "lon": 1}]}],
        }]}
        self.assertEqual(osm.parse_elements(rel), [])


class TestQuery(unittest.TestCase):
    _BBOX = {"south": 53.5, "west": -113.51, "north": 53.51, "east": -113.5}

    def test_building_query_includes_ways_and_relations(self):
        q = osm._query(self._BBOX, include_trees=False, include_buildings=True)
        self.assertIn('way["building"](53.5,-113.51,53.51,-113.5);', q)
        self.assertIn('relation["building"](53.5,-113.51,53.51,-113.5);', q)
        self.assertIn("out geom;", q)

    def test_tree_query_unchanged(self):
        q = osm._query(self._BBOX, include_trees=True, include_buildings=False)
        self.assertIn('node["natural"="tree"]', q)
        self.assertNotIn("building", q)


class TestBboxHelpers(unittest.TestCase):
    _TRI = [(53.5000, -113.5000), (53.5000, -113.4990), (53.5009, -113.4995)]

    def test_boundary_bbox_is_padded(self):
        """The search box grows ~30 m past the boundary so buildings whose
        corner nodes hug the drawn edge still match (V2.13 fix)."""
        bbox, note = osm.bbox_with_area_note(self._TRI, {})
        self.assertLess(bbox["south"], 53.5000)
        self.assertGreater(bbox["north"], 53.5009)
        self.assertLess(bbox["west"], -113.5000)
        self.assertGreater(bbox["east"], -113.4990)
        # ~30 m in degrees latitude.
        self.assertAlmostEqual(53.5000 - bbox["south"], 30.0 / 111320.0,
                               places=6)
        self.assertIn("boundary", note)
        self.assertIn("30 m", note)

    def test_pin_fallback_note_and_size(self):
        bbox, note = osm.bbox_with_area_note(
            None, {"latitude": 53.5, "longitude": -113.5})
        self.assertAlmostEqual(bbox["north"] - bbox["south"],
                               2 * 60.0 / 111320.0, places=6)
        self.assertIn("around the pin", note)
        self.assertIn("boundary", note)      # tells the user how to control it

    def test_no_boundary_no_pin(self):
        bbox, note = osm.bbox_with_area_note(None, {})
        self.assertIsNone(bbox)
        self.assertEqual(note, "")

    def test_back_compat_wrapper_matches(self):
        bbox = osm.bbox_from_boundary_or_pin(self._TRI, {})
        bbox2, _ = osm.bbox_with_area_note(self._TRI, {})
        self.assertEqual(bbox, bbox2)


class TestFetchFailureHonesty(unittest.TestCase):
    """A failed Overpass request must surface as None (failure), never as an
    empty result — 'Found 0 buildings' on a rate-limit was a lie (V2.13)."""

    _BBOX = {"south": 53.5, "west": -113.51, "north": 53.51, "east": -113.5}

    def test_every_server_once_then_none(self):
        calls, why = [], []

        def post(query, url):
            calls.append(url)
            return None

        # The log says which server said what (V3.37: it said nothing).
        with self.assertLogs(osm.log, "INFO") as logged:
            out = osm._fetch_overpass("q", _post=post, _sleep=lambda s: None,
                                      why=why)
        self.assertIsNone(out)
        self.assertIn("no server answered", logged.output[-1])
        self.assertIn("overpass-api.de", logged.output[0])
        # V3.37: the others before the main one again, which is asked again
        # only when it said it was busy (it did not say anything here).
        self.assertEqual(calls, osm._OVERPASS_URLS)
        self.assertEqual([m.host for m in why],
                         [osm._host(u) for u in osm._OVERPASS_URLS])

    def test_each_miss_is_said_as_it_happens(self):
        heard = []
        with self.assertLogs(osm.log, "INFO"):
            osm._fetch_overpass(
                "q", _post=lambda q, url: None, _sleep=lambda s: None,
                on_miss=lambda m: heard.append(osm.trying_words(m)))
        self.assertEqual(len(heard), len(osm._OVERPASS_URLS))
        self.assertIn("overpass-api.de could not be reached", heard[0])
        self.assertIn("another server", heard[0])

    def test_a_busy_main_server_is_asked_again_after_a_pause(self):
        calls, pauses = [], []

        def post(query, url):
            calls.append(url)
            if url == osm._OVERPASS_URL:
                return osm.Unanswered("overpass-api.de", osm.BUSY, "HTTP 429")
            return osm.Unanswered(osm._host(url), osm.UNREACHABLE, "refused")

        with self.assertLogs(osm.log, "INFO"):
            osm._fetch_overpass("q", _post=post, _sleep=pauses.append)
        self.assertEqual(calls, osm._OVERPASS_URLS + [osm._OVERPASS_URL])
        self.assertEqual(pauses, [osm._BUSY_PAUSE_S])

    def test_mirror_success_after_primary_failure(self):
        for name in ("private.coffee", "kumi"):
            def post(query, url, name=name):
                return {"elements": []} if name in url else None

            out = osm._fetch_overpass("q", _post=post, _sleep=lambda s: None)
            self.assertEqual(out, {"elements": []})

    def test_fetch_existing_features_none_on_failure(self):
        orig = osm._fetch_overpass
        osm._fetch_overpass = lambda q, **kw: None
        try:
            self.assertIsNone(osm.fetch_existing_features(self._BBOX))
        finally:
            osm._fetch_overpass = orig

    def test_fetch_buildings_keeps_empty_list_contract(self):
        orig = osm._fetch_overpass
        osm._fetch_overpass = lambda q, **kw: None
        try:
            self.assertEqual(osm.fetch_buildings(self._BBOX), [])
            self.assertIsNone(osm.fetch_buildings_or_none(self._BBOX))
        finally:
            osm._fetch_overpass = orig

    def test_buildings_alone_do_not_ask_for_streets(self):
        # V3.37: every part of a bulk download fetched every street in it.
        asked = []
        orig = osm._fetch_overpass
        osm._fetch_overpass = lambda q, **kw: asked.append(q) or {
            "elements": []}
        try:
            osm.fetch_buildings(self._BBOX)
            osm.fetch_trees(self._BBOX)
        finally:
            osm._fetch_overpass = orig
        self.assertEqual(len(asked), 2)
        self.assertTrue(all("highway" not in q for q in asked))

    def test_a_yard_declares_little_memory_and_a_city_the_default(self):
        yard = {"south": 53.5, "west": -113.501, "north": 53.501,
                "east": -113.5}
        self.assertIn("[maxsize:", osm._query(yard, True, True, True))
        self.assertNotIn("[maxsize:", osm._query(self._BBOX | {
            "north": 53.53}, False, True))


class TestWhyAServerDidNotAnswer(unittest.TestCase):
    """V3.37: each failure is kept with its kind, so the status line can say
    busy from offline from a certificate the computer could not check."""

    _URL = osm._OVERPASS_URL

    def setUp(self):
        self._send = osm._send
        osm._mozilla["context"] = None
        self.addCleanup(self._restore)

    def _restore(self):
        osm._send = self._send
        osm._mozilla["context"] = None

    def _failing(self, exc):
        def send(url, body, context=None):
            raise exc
        osm._send = send
        return osm._post_overpass("q", self._URL)

    def test_http_statuses(self):
        import urllib.error
        for code, kind in ((429, osm.BUSY), (504, osm.BUSY), (503, osm.BUSY),
                           (403, osm.REFUSED), (400, osm.REFUSED)):
            got = self._failing(urllib.error.HTTPError(
                self._URL, code, "x", {}, None))
            self.assertEqual((got.kind, got.detail), (kind, f"HTTP {code}"))
            self.assertEqual(got.host, "overpass-api.de")

    def test_timeouts_and_no_connection(self):
        import socket
        import urllib.error
        self.assertEqual(self._failing(TimeoutError()).kind, osm.SLOW)
        self.assertEqual(self._failing(urllib.error.URLError(
            socket.timeout("timed out"))).kind, osm.SLOW)
        self.assertEqual(self._failing(urllib.error.URLError(
            ConnectionRefusedError())).kind, osm.UNREACHABLE)
        self.assertEqual(self._failing(urllib.error.URLError(
            "[Errno -2] Name or service not known")).kind, osm.UNREACHABLE)

    def test_a_certificate_the_computer_cannot_check_is_asked_of_certifi(self):
        import ssl
        import urllib.error
        try:
            import certifi  # noqa: F401
        except ImportError:
            self.skipTest("certifi not installed")
        contexts = []

        def send(url, body, context=None):
            contexts.append(context)
            if context is None:
                raise urllib.error.URLError(ssl.SSLCertVerificationError(
                    "unable to get local issuer certificate"))
            return b'{"elements": []}'

        osm._send = send
        with self.assertLogs(osm.log, "WARNING") as logged:
            self.assertEqual(osm._post_overpass("q", self._URL),
                             {"elements": []})
        self.assertIn("certifi", logged.output[0])
        self.assertIsNone(contexts[0])
        self.assertIsInstance(contexts[1], ssl.SSLContext)
        # And from then on, straight to the list that worked.
        osm._post_overpass("q", self._URL)
        self.assertIs(contexts[2], contexts[1])

    def test_a_certificate_neither_list_can_check(self):
        import ssl
        import urllib.error
        got = self._failing(urllib.error.URLError(
            ssl.SSLCertVerificationError("certificate has expired")))
        self.assertEqual(got.kind, osm.CERTIFICATE)

    def test_answers_that_are_not_answers(self):
        def answering(raw):
            osm._send = lambda url, body, context=None: raw
            return osm._post_overpass("q", self._URL)

        self.assertEqual(answering(b"<html>Too busy</html>").kind,
                         osm.GARBLED)
        self.assertEqual(answering(b'{"remark": "x"}').kind, osm.GARBLED)
        # A query the server cut short is part of an answer, not an answer.
        cut = answering(b'{"elements": [], "remark": "runtime error: Query '
                        b'timed out in \\"query\\" at line 1 after 26 s."}')
        self.assertEqual(cut.kind, osm.BUSY)
        self.assertEqual(answering(b'{"elements": []}'), {"elements": []})


class TestFailureWords(unittest.TestCase):

    @staticmethod
    def _miss(kind, detail="", host="overpass-api.de"):
        return osm.Unanswered(host, kind, detail)

    def test_the_worst_news_is_said(self):
        words = osm.failure_words([
            self._miss(osm.BUSY, "HTTP 429"),
            self._miss(osm.UNREACHABLE, host="overpass.private.coffee")])
        self.assertIn("busy", words)
        self.assertIn("Try again in a minute", words)

    def test_each_kind_reads_differently(self):
        said = {k: osm.failure_words([self._miss(k, "HTTP 403")])
                for k in osm._KINDS}
        self.assertEqual(len(set(said.values())), len(osm._KINDS))
        self.assertIn("HTTP 403", said[osm.REFUSED])
        self.assertIn("online", said[osm.UNREACHABLE])
        self.assertIn("certificate", said[osm.CERTIFICATE].replace(
            "secure connection", "certificate"))
        for words in said.values():
            # How a person tells a failure from an empty answer.
            self.assertTrue(words.startswith("OpenStreetMap didn't answer"))
            self.assertNotIn("Found 0", words)

    def test_what_was_lost_is_the_callers(self):
        words = osm.failure_words([self._miss(osm.SLOW)],
                                  lost="no buildings came")
        self.assertIn("so no buildings came.", words)
        self.assertIn("didn't answer", osm.failure_words([]))


class TestBoundaryFilter(unittest.TestCase):
    # ~100 m square boundary around (53.5005, -113.4995).
    _POLY = [(53.5000, -113.5002), (53.5000, -113.4988),
             (53.5009, -113.4988), (53.5009, -113.5002)]

    @staticmethod
    def _bldg(lat, lng):
        return {"kind": "building", "lat": lat, "lng": lng,
                "height_m": 5.0, "radius_m": 4.0}

    def test_point_in_polygon(self):
        self.assertTrue(osm._point_in_polygon(53.5005, -113.4995, self._POLY))
        self.assertFalse(osm._point_in_polygon(53.5020, -113.4995, self._POLY))

    def test_dist_to_polygon(self):
        # ~22 m north of the north edge (53.5009).
        d = osm._dist_to_polygon_m(53.5011, -113.4995, self._POLY)
        self.assertAlmostEqual(d, 0.0002 * 111320.0, delta=2.0)

    def test_filter_keeps_inside_and_near_drops_far(self):
        inside = self._bldg(53.5005, -113.4995)
        near = self._bldg(53.50105, -113.4995)     # ~17 m past the edge
        far = self._bldg(53.5030, -113.4995)       # ~230 m away
        kept, n_in, n_nb = osm.filter_to_boundary(
            [inside, near, far], self._POLY, margin_m=30.0)
        self.assertEqual((n_in, n_nb), (1, 1))
        self.assertEqual(len(kept), 2)
        self.assertNotIn(far, kept)

    def test_margin_zero_keeps_only_inside(self):
        inside = self._bldg(53.5005, -113.4995)
        near = self._bldg(53.50105, -113.4995)
        kept, n_in, n_nb = osm.filter_to_boundary(
            [inside, near], self._POLY, margin_m=0.0)
        self.assertEqual((len(kept), n_in, n_nb), (1, 1, 0))

    def test_footprint_vertex_counts_as_near(self):
        # Centroid far outside, but one footprint corner within the margin.
        b = self._bldg(53.5013, -113.4995)
        b["footprint"] = [[-113.4995, 53.50095], [-113.4994, 53.5013],
                          [-113.4996, 53.5013], [-113.4995, 53.50095]]
        kept, n_in, n_nb = osm.filter_to_boundary([b], self._POLY,
                                                  margin_m=30.0)
        self.assertEqual(len(kept), 1)
        self.assertEqual(n_nb, 1)

    def test_no_boundary_keeps_everything(self):
        feats = [self._bldg(53.6, -113.6)]
        kept, n_in, n_nb = osm.filter_to_boundary(feats, None, 30.0)
        self.assertEqual(kept, feats)


class TestImportOsmResult(unittest.TestCase):
    _POLY = [(53.5000, -113.5002), (53.5000, -113.4988),
             (53.5009, -113.4988), (53.5009, -113.5002)]

    def test_failure_message(self):
        proj = new_project("t")
        out = osm.import_osm_result(None, proj, boundary=self._POLY)
        self.assertEqual(out["added"], 0)
        self.assertIn("didn't answer", out["message"])
        self.assertNotIn("Found 0", out["message"])

    def test_failure_says_why(self):
        # The worker's failure (V3.37) carries what each server said.
        proj = new_project("t")
        out = osm.import_osm_result(
            {"failed": [osm.Unanswered("overpass-api.de", osm.BUSY,
                                       "HTTP 429")]},
            proj, boundary=self._POLY)
        self.assertEqual(out["added"], 0)
        self.assertEqual(len(out["failed"]), 1)
        self.assertIn("busy", out["message"])
        self.assertEqual(proj["features"], [])

    def test_counts_and_message(self):
        proj = new_project("t")
        res = {"buildings": [
            {"kind": "building", "lat": 53.5005, "lng": -113.4995,
             "height_m": 5.0, "radius_m": 4.0},
            {"kind": "building", "lat": 53.5030, "lng": -113.4995,
             "height_m": 5.0, "radius_m": 4.0},        # far — filtered out
        ], "trees": []}
        out = osm.import_osm_result(res, proj, boundary=self._POLY,
                                    margin_m=30.0)
        self.assertEqual(out["found"], 2)
        self.assertEqual(out["kept"], 1)
        self.assertEqual(out["added"], 1)
        self.assertIn("1 inside your boundary", out["message"])
        self.assertIn("Delete", out["message"])

    def test_genuinely_empty_result(self):
        proj = new_project("t")
        out = osm.import_osm_result({"buildings": [], "trees": []}, proj,
                                    boundary=self._POLY)
        self.assertEqual(out["added"], 0)
        self.assertIn("knows no buildings", out["message"])


class TestImport(unittest.TestCase):
    def test_adds_to_project(self):
        proj = new_project("t")
        feats = osm.parse_elements(_FIXTURE)
        n = osm.add_features_to_project(feats, proj)
        self.assertEqual(n, 3)
        ets = [f["properties"]["element_type"] for f in proj["features"]]
        self.assertEqual(ets.count("existing_tree"), 2)
        # V1.58: a building with a footprint imports as a true-outline
        # canopy_footprint Polygon, not a Point existing_building.
        self.assertEqual(ets.count("canopy_footprint"), 1)
        self.assertEqual(ets.count("existing_building"), 0)

    def test_building_imports_as_true_polygon(self):
        proj = new_project("t")
        osm.add_features_to_project(osm.parse_elements(_FIXTURE), proj)
        b = next(f for f in proj["features"]
                 if f["properties"]["element_type"] == "canopy_footprint")
        self.assertEqual(b["geometry"]["type"], "Polygon")
        ring = b["geometry"]["coordinates"][0]
        self.assertEqual(ring[0], ring[-1])            # closed ring
        self.assertGreaterEqual(len(ring), 5)          # 4 corners + close
        props = b["properties"]
        self.assertTrue(props["cast_shade"])
        self.assertEqual(props["source"], "osm")
        self.assertGreater(props["height_m"], 0)
        self.assertGreater(props["canopy_radius_m"], 0)
        self.assertIn("lat", props)                    # centroid for keep-out
        self.assertIn("lng", props)

    def test_building_caster_carries_footprint(self):
        proj = new_project("t")
        osm.add_features_to_project(osm.parse_elements(_FIXTURE), proj)
        from src.shade import casters_from_project
        casters = casters_from_project(proj)
        self.assertTrue(any(c.get("footprint") for c in casters))

    def test_building_without_footprint_falls_back_to_point(self):
        proj = new_project("t")
        # A building dict lacking a usable footprint (legacy/degenerate) must
        # still import as a Point existing_building so nothing is lost.
        item = {"kind": "building", "lat": 53.5, "lng": -113.5,
                "height_m": 5.0, "radius_m": 4.0}
        n = osm.add_features_to_project([item], proj)
        self.assertEqual(n, 1)
        f = proj["features"][-1]
        self.assertEqual(f["geometry"]["type"], "Point")
        self.assertEqual(f["properties"]["element_type"], "existing_building")

    def test_reimport_dedupes_building(self):
        proj = new_project("t")
        osm.add_features_to_project(osm.parse_elements(_FIXTURE), proj)
        # Re-importing the same area adds nothing (trees + building deduped).
        n2 = osm.add_features_to_project(osm.parse_elements(_FIXTURE), proj)
        self.assertEqual(n2, 0)

    def test_building_shape_ids_unique(self):
        # Two buildings must get distinct shape_ids — a count-based scheme could
        # collide after a delete; uuids never do.
        two = {"elements": [
            {"type": "way", "tags": {"building": "yes"},
             "geometry": [{"lat": 53.5000, "lon": -113.5000},
                          {"lat": 53.5000, "lon": -113.4998},
                          {"lat": 53.5002, "lon": -113.4998},
                          {"lat": 53.5000, "lon": -113.5000}]},
            {"type": "way", "tags": {"building": "yes"},
             "geometry": [{"lat": 53.5010, "lon": -113.5010},
                          {"lat": 53.5010, "lon": -113.5008},
                          {"lat": 53.5012, "lon": -113.5008},
                          {"lat": 53.5010, "lon": -113.5010}]},
        ]}
        proj = new_project("t")
        osm.add_features_to_project(osm.parse_elements(two), proj)
        ids = [f["properties"]["shape_id"] for f in proj["features"]
               if f["properties"].get("element_type") == "canopy_footprint"]
        self.assertEqual(len(ids), 2)
        self.assertEqual(len(set(ids)), 2)          # all unique

    def test_dedupes_against_existing(self):
        proj = new_project("t")
        # Pre-mark a tree at the same spot as one OSM tree.
        proj["features"].append({
            "type": "Feature",
            "geometry": {"type": "Point", "coordinates": [-113.4995, 53.5005]},
            "properties": {"element_type": "existing_tree"}})
        n = osm.add_features_to_project(osm.parse_elements(_FIXTURE), proj)
        self.assertEqual(n, 2)     # the duplicate tree is skipped

    def test_imported_features_feed_shade_and_keepout(self):
        proj = new_project("t")
        osm.add_features_to_project(osm.parse_elements(_FIXTURE), proj)
        from src.shade import casters_from_project
        from src.exclusion import keepout_circles
        self.assertEqual(len(casters_from_project(proj)), 3)
        self.assertEqual(len(keepout_circles(proj)), 3)


class TestRingHelpers(unittest.TestCase):
    """V1.58 — shared footprint-sizing helpers (OSM import, drawn shapes, and
    the footprint-edit handler all size canopy_radius_m through these)."""

    def _square(self, half_m=5.0, clat=53.5, clng=-113.5):
        dlat = half_m / 111320.0
        dlng = half_m / (111320.0 * math.cos(math.radians(clat)))
        return [[clng - dlng, clat - dlat], [clng + dlng, clat - dlat],
                [clng + dlng, clat + dlat], [clng - dlng, clat + dlat],
                [clng - dlng, clat - dlat]]

    def test_centroid_of_square(self):
        c = osm.ring_centroid(self._square())
        self.assertIsNotNone(c)
        self.assertAlmostEqual(c[0], 53.5, places=4)
        self.assertAlmostEqual(c[1], -113.5, places=4)

    def test_radius_of_square(self):
        # Half-extent 5 m → corner distance ≈ 5·√2 ≈ 7.07 m.
        r = osm.ring_radius_m(self._square(5.0))
        self.assertAlmostEqual(r, 5.0 * math.sqrt(2), delta=0.2)

    def test_radius_empty_ring(self):
        self.assertEqual(osm.ring_radius_m([]), 0.0)

    def test_centroid_degenerate_none(self):
        self.assertIsNone(osm.ring_centroid([[0, 0], [1, 1]]))


if __name__ == "__main__":
    unittest.main()
