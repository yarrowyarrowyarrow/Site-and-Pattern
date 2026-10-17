"""
tests/test_services.py — every outside service is credited, and the app says
who it is (FN-5, FN-6; V3.31; docs/homeowner/10-finishing.md §4).
"""

import os
import re
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from src import services  # noqa: E402

_HOST = re.compile(r"https?://([A-Za-z0-9.-]+)")


def _code_hosts() -> dict:
    """``{host: [file]}`` for every URL in ``src/`` and the map's scripts."""
    out: dict = {}
    roots = [os.path.join(ROOT, "src"), os.path.join(ROOT, "html", "map")]
    for root in roots:
        for dirpath, _dirs, files in os.walk(root):
            if "__pycache__" in dirpath:
                continue
            for name in files:
                if not name.endswith((".py", ".js")):
                    continue
                path = os.path.join(dirpath, name)
                with open(path, encoding="utf-8") as fh:
                    for host in _HOST.findall(fh.read()):
                        out.setdefault(host.rstrip("."), []).append(
                            os.path.relpath(path, ROOT))
    html_map = os.path.join(ROOT, "html", "map.html")
    with open(html_map, encoding="utf-8") as fh:
        for host in _HOST.findall(fh.read()):
            out.setdefault(host, []).append("html/map.html")
    return out


class EveryServiceIsCredited(unittest.TestCase):

    def test_every_host_in_the_code_is_a_service_or_said_why_not(self):
        known = services.hosts() | set(services.NOT_ASKED)
        missing = {h: f for h, f in _code_hosts().items()
                   if h not in known
                   and not any(h.startswith(k) for k in known)}
        self.assertEqual(missing, {}, "credit it in src/services.py, or say "
                                      "in NOT_ASKED why the app never asks it")

    def test_each_service_says_what_it_is_sent(self):
        for s in services.SERVICES:
            self.assertTrue(s.used_for and s.sent, s.name)

    def test_the_credits_providers_ask_for(self):
        text = " ".join(services.credit_lines())
        for words in ("Weather data by Open-Meteo.com",
                      "© OpenStreetMap contributors", "SoilGrids by ISRIC"):
            self.assertIn(words, text)

    def test_the_privacy_paragraph(self):
        for words in ("address you type", "no analytics", "location removed"):
            self.assertIn(words, services.PRIVACY)


class TheAppSaysWhoItIs(unittest.TestCase):
    """FN-6: one identity, with the version, on every request."""

    def test_one_user_agent(self):
        from src import http_utils
        ua = http_utils.user_agent()
        self.assertTrue(ua.startswith("SiteAndPattern/"), ua)
        self.assertIn(http_utils.APP_URL, ua)
        for name in ("osm_features", "tree_detect", "tree_detect_chm",
                     "soil_downloader", "llm_design", "terrain_downloader"):
            mod = __import__(f"src.{name}", fromlist=["_USER_AGENT"])
            self.assertEqual(mod._USER_AGENT, http_utils._USER_AGENT, name)

    def test_no_old_identity_left(self):
        for dirpath, _dirs, files in os.walk(os.path.join(ROOT, "src")):
            if "__pycache__" in dirpath:
                continue
            for name in files:
                if name.endswith(".py") and name != "http_utils.py":
                    with open(os.path.join(dirpath, name),
                              encoding="utf-8") as fh:
                        self.assertNotIn("PermaDesign/1.0", fh.read(), name)

    def test_the_address_search_is_asked_once_per_query(self):
        from unittest import mock
        from src import property_data
        property_data.clear_geocode_cache()
        reply = [{"display_name": "10423 81 Ave NW, Edmonton, Alberta",
                  "lat": "53.52", "lon": "-113.50",
                  "address": {"state": "Alberta"}}]
        with mock.patch.object(property_data, "_http_get_json",
                               return_value=reply) as get:
            property_data.geocode_address("10423 81 Ave")
            property_data.geocode_address("10423 81 Ave")
        self.assertEqual(get.call_count, 1)
        property_data.clear_geocode_cache()


if __name__ == "__main__":
    unittest.main()
