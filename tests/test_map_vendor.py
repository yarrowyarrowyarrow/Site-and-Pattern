"""
tests/test_map_vendor.py

Guards the V2.83 fix: the 2D design map (html/map.html) loads Leaflet and
Leaflet.draw from VENDORED, LOCAL files -- never from a CDN.

Until V2.83 both came from unpkg.com. With no internet, or with unpkg down or
blocked, the page loaded with no `L`, `01-core.js` and `04-tools.js` threw
`ReferenceError: L is not defined`, and the window opened on an empty panel:
no boundary, no placement, no overlays. The 3D viewer had been vendored since
V1.77 with its own guard (tests/test_scene3d_assets.py); the map the whole
design workflow runs on had not, and was documented as a gotcha rather than
fixed.

Map TILES still come from the network, and are allowed to: they are data, and
the map starts and draws without them. What this pins is that the code does
not.

Pure file reads -- no Qt, no DB.
"""

import os
import re
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_HTML = os.path.join(_ROOT, "html")
_MAP = os.path.join(_HTML, "map.html")
_MAP_JS = os.path.join(_HTML, "map")
_VENDOR = os.path.join(_HTML, "vendor")

# Hosts that serve code. A tile server is not on this list on purpose.
_CDN_HOSTS = ("unpkg.com", "cdn.jsdelivr.net", "cdnjs.cloudflare.com",
              "ajax.googleapis.com", "code.jquery.com")


def _read(path):
    with open(path, "r", encoding="utf-8") as fh:
        return fh.read()


class TestMapLoadsNothingFromACdn(unittest.TestCase):

    def test_map_html_names_no_cdn(self):
        # Strict on purpose: not even in a comment, so a commented-out CDN tag
        # cannot be uncommented back into service without this noticing.
        src = _read(_MAP)
        for host in _CDN_HOSTS:
            self.assertFalse(host in src, f"html/map.html names {host}")

    def test_no_map_script_names_a_cdn(self):
        # The site pin's icon URLs lived in 06-overlays.js, not in map.html,
        # which is why checking the page alone was not enough.
        for name in sorted(os.listdir(_MAP_JS)):
            if name.endswith(".js"):
                src = _read(os.path.join(_MAP_JS, name))
                for host in _CDN_HOSTS:
                    self.assertFalse(host in src,
                                     f"html/map/{name} names {host}")

    def test_every_script_and_stylesheet_is_local_and_exists(self):
        src = _read(_MAP)
        refs = (re.findall(r'<script[^>]+src="([^"]+)"', src)
                + re.findall(r'<link[^>]+rel="stylesheet"[^>]+href="([^"]+)"',
                             src))
        self.assertTrue(refs, "found no scripts or stylesheets in map.html")
        for ref in refs:
            if ref.startswith("qrc:"):
                continue      # Qt's own qwebchannel.js, compiled into Qt
            self.assertFalse(re.match(r"^[a-z]+://", ref),
                             f"map.html loads {ref} from outside the app")
            self.assertTrue(os.path.isfile(os.path.join(_HTML, ref)),
                            f"map.html names {ref}, which does not exist")

    def test_leaflet_loads_before_the_map_scripts(self):
        # The split map scripts are classic scripts sharing globals (V1.64);
        # every one of them assumes `L` already exists.
        src = _read(_MAP)
        leaflet = src.index('src="vendor/leaflet/leaflet.js"')
        draw = src.index('src="vendor/leaflet-draw/leaflet.draw.js"')
        first_map_script = src.index('src="map/01-core.js"')
        self.assertLess(leaflet, draw)
        self.assertLess(draw, first_map_script)


class TestVendoredLeaflet(unittest.TestCase):

    def test_the_versions_are_the_ones_recorded(self):
        # html/vendor/README.md records these; a refresh must update both.
        self.assertIn("Leaflet 1.9.4",
                      _read(os.path.join(_VENDOR, "leaflet", "leaflet.js"))[:300])
        self.assertIn("Leaflet.draw 1.0.4",
                      _read(os.path.join(_VENDOR, "leaflet-draw",
                                         "leaflet.draw.js"))[:300])
        readme = _read(os.path.join(_VENDOR, "README.md"))
        self.assertIn("1.9.4", readme)
        self.assertIn("1.0.4", readme)

    def test_every_image_the_stylesheets_name_is_vendored(self):
        # Both stylesheets reference images relative to themselves; a missing
        # one is a blank toolbar button or an invisible marker, not an error.
        for sub, css in (("leaflet", "leaflet.css"),
                         ("leaflet-draw", "leaflet.draw.css")):
            text = _read(os.path.join(_VENDOR, sub, css))
            for ref in re.findall(r"url\(['\"]?([^'\")]+)['\"]?\)", text):
                if ref.startswith("#"):
                    continue      # url(#default#VML), an old IE behaviour
                self.assertTrue(os.path.isfile(os.path.join(_VENDOR, sub, ref)),
                                f"{sub}/{css} names {ref}, not vendored")

    def test_the_licences_travel_with_the_code(self):
        for sub in ("leaflet", "leaflet-draw"):
            self.assertTrue(os.path.isfile(os.path.join(_VENDOR, sub, "LICENSE")),
                            f"html/vendor/{sub}/LICENSE is missing")


if __name__ == "__main__":
    unittest.main()
