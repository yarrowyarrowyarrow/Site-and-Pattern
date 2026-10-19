"""
tests/test_fetch_animals_near.py — counting each animal near a region pack's
centre (V3.36, F190/F249), with GBIF replaced.
"""

import io
import json
import os
import shutil
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from unittest import mock
from urllib.parse import parse_qs, urlparse

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "scripts"))

import fetch_animals_near as near  # noqa: E402

EDMONTON = (53.5461, -113.4938)


class _Failed(Exception):
    pass


class _Throttle:
    sleep = 0.0

    def wait(self):
        pass


def _fake(answers):
    """A stand-in for the seeder's GBIF machinery: ``answers`` maps a
    scientific name to a count, or to an exception to raise."""
    asked = []

    def get_json(url, timeout, throttle):
        q = parse_qs(urlparse(url).query)
        asked.append(q)
        got = answers[q["scientificName"][0]]
        if isinstance(got, Exception):
            raise got
        return {"count": got, "results": []}

    return mock.Mock(_get_json=get_json, _Throttle=_Throttle,
                     FetchFailed=_Failed,
                     GBIF_SEARCH="https://api.gbif.org/v1/occurrence/search"), asked


class TheQuery(unittest.TestCase):

    def test_the_circle_and_the_box(self):
        q = parse_qs(urlparse(near.query("Poecile atricapillus", EDMONTON, 50))
                     .query)
        self.assertEqual(q["geoDistance"], ["53.5461,-113.4938,50km"])
        self.assertEqual(q["limit"], ["0"])
        self.assertNotIn("LIVING_SPECIMEN", q["basisOfRecord"])
        self.assertNotIn("FOSSIL_SPECIMEN", q["basisOfRecord"])
        self.assertIn("HUMAN_OBSERVATION", q["basisOfRecord"])
        lat_min, lat_max, lng_min, lng_max = near.box(EDMONTON, 50)
        self.assertAlmostEqual(lat_max - lat_min, 100 / 111.32, places=3)
        self.assertGreater(lng_max - lng_min, lat_max - lat_min,
                           "a degree of longitude is shorter this far north")
        qb = parse_qs(urlparse(near.query("x", EDMONTON, 50, by_box=True)).query)
        self.assertNotIn("geoDistance", qb)
        self.assertIn("decimalLatitude", qb)

    def test_the_packs_come_from_the_region_files(self):
        keys = [k for k, _c, _r in near.packs()]
        self.assertIn("edmonton", keys)


class TheRun(unittest.TestCase):

    def setUp(self):
        self.dir = tempfile.mkdtemp(prefix="animals_near_")
        self.addCleanup(shutil.rmtree, self.dir, True)
        self.out = os.path.join(self.dir, "animals_near.json")
        self.animals = [("Poecile atricapillus", "Black-capped Chickadee", "bird"),
                        ("Lagopus leucura", "White-tailed Ptarmigan", "bird"),
                        ("Bombus ternarius", "Tri-coloured Bumble Bee", "bee")]

    def _run(self, answers, argv=()):
        mod, asked = _fake(answers)
        with mock.patch.object(near, "gbif", return_value=mod), \
                mock.patch.object(near, "OUT", self.out), \
                mock.patch.object(near, "animals", return_value=self.animals), \
                mock.patch.object(near, "packs",
                                  return_value=[("edmonton", EDMONTON, 50.0)]), \
                redirect_stdout(io.StringIO()):
            near.main(list(argv))
        return asked

    def test_counts_are_kept_and_a_failure_is_not_a_zero(self):
        self._run({"Poecile atricapillus": 41234, "Lagopus leucura": 0,
                   "Bombus ternarius": _Failed("HTTP 503")})
        with open(self.out, encoding="utf-8") as fh:
            blob = json.load(fh)
        pack = blob["packs"]["edmonton"]
        self.assertEqual(pack["animals"], {"Poecile atricapillus": 41234,
                                           "Lagopus leucura": 0})
        self.assertEqual(pack["radius_km"], 50.0)
        asked = self._run({"Bombus ternarius": 377})
        self.assertEqual([q["scientificName"] for q in asked],
                         [["Bombus ternarius"]], "only what was not answered")
        with open(self.out, encoding="utf-8") as fh:
            self.assertEqual(json.load(fh)["packs"]["edmonton"]["animals"]
                             ["Bombus ternarius"], 377)

    def test_the_probe_writes_nothing(self):
        mod, _asked = _fake({name: 5 for name, _e in near.PROBE})
        with mock.patch.object(near, "gbif", return_value=mod), \
                mock.patch.object(near, "OUT", self.out), \
                mock.patch.object(near, "packs",
                                  return_value=[("edmonton", EDMONTON, 50.0)]), \
                redirect_stdout(io.StringIO()) as out:
            self.assertEqual(near.main(["--probe"]), 0)
        self.assertFalse(os.path.exists(self.out))
        self.assertIn("circle", out.getvalue())


if __name__ == "__main__":
    unittest.main()
