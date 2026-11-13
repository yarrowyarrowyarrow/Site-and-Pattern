#!/usr/bin/env python3
"""
scripts/render_yard.py — a whole yard through the real 3D viewer, as pictures
(V3.43).

    python scripts/render_yard.py --out /tmp/yard
    python scripts/render_yard.py --out /tmp/yard --design my-yard.perma.geojson

Writes two contact sheets, ``yard.jpg`` (the yard and its setting: as the
window opens, from the house, from above, the whole yard, from inside) and
``time.jpg`` (the same street view through the years, the seasons and the
day), each tile drawn by the app's own viewer from the scene the app's own
``build_scene`` makes. Since V3.44 the views are the window's own named ones
(``src/scene3d_stops.py``), so a sheet shows what its buttons show.

**Why it exists.** Six audits rendered one plant at a time, and the V3.37 use
test could not open 3D at all, so for years nobody looked at a yard. The V3.43
review did, by hand, and found the house a see-through green box, the camera
framing a 50 m stage with the yard about 1% of it, Walk starting inside the
house, and a third of a plan dead by year 5 with nothing saying so. Every later
3D increment ends by running this and putting its sheets beside the last ones.

Without ``--design`` it plans the review's lot: 15.2 x 36.6 m in south
Edmonton, street to the south, with what Scan this area and a few minutes of
Draw › Shape leave on the map (a house, a garage, a neighbour either side, a
boulevard tree and a spruce, three beds, a path, a driveway, a patio, a lawn),
planned twice by Plan My Yard's generator with the first-run goals, front then
back. It also renders the shipped example yard.

It uses a throwaway database and never touches your designs or catalogue. It
does not reach the internet (``--online`` lets it, for terrain and wind). It
needs a Chromium or Chrome binary (``CHROME=`` to name one) and takes a few
minutes: the pictures are drawn in software, which changes light and edges and
not shapes or sizes. Dev tool: nothing in ``src/`` imports it, and the
installer leaves it and ``html/yard_probe.html`` out.
"""

from __future__ import annotations

import argparse
import base64
import json
import math
import os
import re
import shutil
import subprocess
import sys
import tempfile
import threading
from datetime import datetime
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)
HTML = os.path.join(ROOT, "html")

#: The pages this checkout always serves itself, whichever viewer is under test.
_OWN_PAGES = ("/yard_probe.html", "/probe_watch.js")

# ── the browser ──────────────────────────────────────────────────────────────


def find_chromium():
    """A Chromium or Chrome binary, or ``None``: ``CHROME``, then Playwright's
    browser folder, then PATH (as ``tests/test_scene3d_render.py`` looks)."""
    env = os.environ.get("CHROME")
    if env and os.path.isfile(env):
        return env
    pw = os.environ.get("PLAYWRIGHT_BROWSERS_PATH", "/opt/pw-browsers")
    if os.path.isdir(pw):
        for entry in sorted(os.listdir(pw)):
            for folder in ("chrome-linux", "chrome-linux64"):
                cand = os.path.join(pw, entry, folder, "chrome")
                if os.path.isfile(cand):
                    return cand
    for name in ("chromium", "chromium-browser", "google-chrome", "chrome"):
        found = shutil.which(name)
        if found:
            return found
    return None


class _Handler(SimpleHTTPRequestHandler):
    routes: dict = {}

    def log_message(self, *args):
        pass

    def do_GET(self):                                        # noqa: N802
        path = self.path.split("?")[0]
        body = self.routes.get(path)
        if body is None and path in _OWN_PAGES:
            with open(os.path.join(HTML, path.lstrip("/")), "rb") as fh:
                body = fh.read()
        if body is None:
            return super().do_GET()
        kind = ("application/json" if path.endswith(".json")
                else "text/javascript" if path.endswith(".js") else "text/html")
        self.send_response(200)
        self.send_header("Content-Type", kind)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


class Server:
    """``html/`` on a loopback port, with ``routes`` (``{"/__yard/x.json":
    obj}``) served from memory. ``viewer_root`` serves another checkout's
    ``html/`` instead, which is how the gate is shown to fail on an older
    viewer; the probe page itself always comes from this checkout."""

    def __init__(self, routes: dict | None = None, viewer_root: str = HTML):
        handler = type("YardHandler", (_Handler,), {"routes": {
            path: (body if isinstance(body, bytes)
                   else json.dumps(body).encode("utf-8"))
            for path, body in (routes or {}).items()}})
        self.httpd = ThreadingHTTPServer(
            ("127.0.0.1", 0), partial(handler, directory=viewer_root))
        self.port = self.httpd.server_address[1]
        threading.Thread(target=self.httpd.serve_forever, daemon=True).start()

    def url(self, page: str) -> str:
        return f"http://127.0.0.1:{self.port}/{page.lstrip('/')}"

    def stop(self):
        self.httpd.shutdown()
        self.httpd.server_close()


def run_probe(url: str, *, budget_ms: int = 120000, timeout: int = 900) -> str:
    """The page's DOM once its scripts have had ``budget_ms`` of page time
    (headless Chromium, software WebGL, as the other render gates run)."""
    chrome = find_chromium()
    if chrome is None:
        raise RuntimeError("no Chromium or Chrome binary: set CHROME= to one")
    proc = subprocess.run(
        [chrome, "--headless", "--no-sandbox", "--disable-gpu-sandbox",
         "--enable-unsafe-swiftshader", "--use-angle=swiftshader",
         f"--virtual-time-budget={int(budget_ms)}", "--dump-dom", url],
        capture_output=True, text=True, timeout=timeout, encoding="utf-8")
    return proc.stdout


# ── the yard ─────────────────────────────────────────────────────────────────

LAT0, LNG0 = 53.5232, -113.5263
KX = 111320 * math.cos(math.radians(LAT0))
KY = 111320.0
W, D = 15.2, 36.6


def _ll(east, north):
    return [LNG0 + east / KX, LAT0 + north / KY]


def _rect(x0, y0, x1, y1):
    ring = [_ll(e, n) for e, n in ((x0, y0), (x1, y0), (x1, y1), (x0, y1))]
    return ring + [ring[0]]


def _shape(kind, ring, label=""):
    return {"type": "Feature",
            "geometry": {"type": "Polygon", "coordinates": [ring]},
            "properties": {"element_type": "custom_shape", "shape_type": kind,
                           "label": label or kind}}


def _building(ring, height, label):
    xs = [c[0] for c in ring[:-1]]
    ys = [c[1] for c in ring[:-1]]
    return {"type": "Feature",
            "geometry": {"type": "Polygon", "coordinates": [ring]},
            "properties": {
                "element_type": "canopy_footprint",
                "shape_id": "shape_osm_" + label.lower().replace(" ", "_"),
                "label": label, "shape_type": "Building (OSM)",
                "height_m": height, "cast_shade": True, "canopy_radius_m": 6.0,
                "lat": sum(ys) / len(ys), "lng": sum(xs) / len(xs),
                "source": "osm"}}


def _tree(east, north, height, radius, foliage):
    lng, lat = _ll(east, north)
    return {"type": "Feature",
            "geometry": {"type": "Point", "coordinates": [lng, lat]},
            "properties": {"element_type": "existing_tree", "height_m": height,
                           "canopy_radius_m": radius,
                           "label": "Tree (canopy map)",
                           "struct_id": "existing_tree", "source": "canopy",
                           "tree_foliage": foliage}}


BOUNDARY = [[LAT0 + n / KY, LNG0 + e / KX]
            for e, n in ((0, 0), (W, 0), (W, D), (0, D))]
SITE = {"latitude": LAT0 + 18 / KY, "longitude": LNG0 + 7.6 / KX}
SCANNED = [
    _building(_rect(2.2, 9.0, 13.0, 21.0), 6.5, "House"),
    _building(_rect(8.2, 29.6, 14.6, 36.0), 3.4, "Garage"),
    _building(_rect(-13.0, 8.5, -2.0, 21.5), 6.5, "Neighbour west"),
    _building(_rect(17.2, 9.5, 28.0, 20.5), 5.5, "Neighbour east"),
    _tree(4.0, -2.5, 14.0, 5.5, "deciduous"),
    _tree(2.5, 33.0, 13.0, 3.0, "evergreen"),
]
FRONT = [_shape("Garden Bed", _rect(0.6, 0.8, 9.2, 7.6)),
         _shape("Pathway", _rect(9.6, 0.0, 10.8, 9.0)),
         _shape("Patio / Deck", _rect(11.2, 0.0, 14.8, 9.0), "Driveway")]
BACK = [_shape("Patio / Deck", _rect(3.0, 21.2, 9.0, 25.0)),
        _shape("Lawn Area", _rect(0.6, 25.4, 7.8, 31.0)),
        _shape("Garden Bed", _rect(0.6, 31.4, 7.8, 36.0)),
        _shape("Garden Bed", _rect(9.4, 21.4, 14.6, 29.2))]


def use_throwaway_database() -> str:
    import src.db.plants as plants
    tmp = tempfile.mkdtemp(prefix="render_yard_")
    plants._DATA_DIR = tmp
    plants._DB_PATH = os.path.join(tmp, "render_yard.db")
    plants.init_db()
    return tmp


def review_lot() -> dict:
    """The review's lot, planned as the app plans it: front, then back."""
    from src.llm_design import generate_design_offline
    from src.onboarding import FIRST_RUN_GOALS
    from src.project import new_project

    def plan(setting, mine, others):
        made = generate_design_offline(
            site_config=dict(SITE, yard_setting=setting), boundary=BOUNDARY,
            goals=list(FIRST_RUN_GOALS), density="balanced", cover=0.70,
            existing_features=SCANNED + mine + others, setting=setting,
            street_side="south" if setting == "front" else "").as_dict()
        return [f for f in made["features"]
                if (f.get("properties") or {}).get("plant_id")
                or (f.get("properties") or {}).get("element_type") == "structure"]

    ring = [[p[1], p[0]] for p in BOUNDARY]
    project = new_project("Review lot")
    project.setdefault("properties", {})["site_config"] = dict(SITE)
    project["features"] = (
        [{"type": "Feature",
          "geometry": {"type": "Polygon", "coordinates": [ring + [ring[0]]]},
          "properties": {"element_type": "property_boundary",
                         "boundary_id": "b1"}}]
        + SCANNED + FRONT + BACK + plan("front", FRONT, BACK)
        + plan("back", BACK, FRONT))
    return project


def scene(project: dict, year: int, month: int, hour: int) -> dict:
    from src.scene_contract import build_scene
    return build_scene(project, year=year,
                       when=datetime(2025, month, 21, hour, 0))


# ── the sheets ───────────────────────────────────────────────────────────────

def _opening() -> tuple:
    """What the window opens on (``scene3d_stops.OPENING``, the owner's D5)."""
    from src.scene3d_stops import OPENING
    return (OPENING["year"], OPENING["month"], OPENING["hour"])


#: tag: (year, month, hour). Year 0 is the design fully grown. ``open`` was
#: (0, 6, 13) until V3.44; the others are unchanged, so a time sheet can be
#: laid beside an older one.
MOMENTS = {
    "open": _opening(), "y1_jun": (1, 6, 13), "y3_jul": (3, 7, 13),
    "y5_jul": (5, 7, 13), "y25_jul": (25, 7, 13), "y5_apr": (5, 4, 13),
    "y5_oct": (5, 10, 13), "y5_jan": (5, 1, 13), "y5_aug_18h": (5, 8, 18),
    "y5_jul_23h": (5, 7, 23),
}


def job(label: str, lot_name: str, with_example: bool, width: int,
        height: int) -> dict:
    lot = lambda tag: f"/__yard/lot_{tag}.json"              # noqa: E731
    shots = [
        {"name": "lot_open", "scene": lot("open"), "view": "open"},
        {"name": "house", "scene": lot("open"), "view": "house"},
        {"name": "above", "scene": lot("open"), "view": "above"},
        {"name": "whole", "scene": lot("open"), "view": "whole"},
        {"name": "yard", "scene": lot("open"), "view": "yard"},
        {"name": "street", "scene": lot("y5_jul"), "view": "street"},
        {"name": "y1", "scene": lot("y1_jun"), "view": "street"},
        {"name": "y3", "scene": lot("y3_jul"), "view": "street"},
        {"name": "y25", "scene": lot("y25_jul"), "view": "street"},
        {"name": "apr", "scene": lot("y5_apr"), "view": "street"},
        {"name": "oct", "scene": lot("y5_oct"), "view": "street"},
        {"name": "jan", "scene": lot("y5_jan"), "view": "street"},
        {"name": "eve", "scene": lot("y5_aug_18h"), "view": "street"},
        {"name": "night", "scene": lot("y5_jul_23h"), "view": "street"},
    ]
    from src.scene3d_stops import when_words
    year, month, hour = MOMENTS["open"]
    moment = (f"{when_words(year, month).lower()}, "
              f"{datetime(2025, month, 1):%B}, {hour}:00")
    yard = [
        {"shot": "lot_open", "caption": f"{lot_name}, as the window opens: "
                                        f"{moment}, from the street."},
        {"shot": "house", "caption": "From the house (where there is one; "
                                     "else the whole yard)."},
        {"shot": "above", "caption": "From above, north at the top."},
        {"shot": "whole", "caption": "Reset view: the whole yard."},
        {"shot": "yard", "caption": "A few steps into the yard."},
    ]
    if with_example:
        shots.insert(0, {"name": "example_open",
                         "scene": "/__yard/example_open.json", "view": "open"})
        yard.insert(0, {"shot": "example_open",
                        "caption": "The example yard, as the window opens: "
                                   f"{moment}, from the street."})
    time = [
        {"shot": "y1", "caption": "Year 1, June, from the street."},
        {"shot": "y3", "caption": "Year 3, July."},
        {"shot": "street", "caption": "Year 5, July."},
        {"shot": "y25", "caption": "Year 25, July."},
        {"shot": "apr", "caption": "Year 5, 21 April."},
        {"shot": "oct", "caption": "Year 5, 21 October."},
        {"shot": "jan", "caption": "Year 5, 21 January."},
        {"shot": "eve", "caption": "Year 5, August, 6 pm."},
    ]
    return {
        "width": width, "height": height, "tile_width": 760,
        "shots": shots,
        "sheets": [
            {"name": "yard", "tiles": yard,
             "title": f"3D Preview at {label}: the yard and its setting",
             "sub": "The app's viewer, fed the scenes the app builds. "
                    "Drawn in software: light and edges differ on a "
                    "graphics card, shapes and sizes do not."},
            {"name": "time", "tiles": time,
             "title": f"3D Preview at {label}: the years and the seasons",
             "sub": "One view, as the Year, Time of year and Time of day "
                    "sliders move."},
        ],
    }


def images(dom: str, attr: str) -> dict:
    """``{name: bytes}`` for every ``<img data-<attr>="name" src="data:…">``
    in a dumped DOM, whichever order the browser wrote the attributes in."""
    found = {}
    for tag in re.findall(r"<img\b[^>]*>", dom):
        name = re.search(r'data-%s="([^"]+)"' % attr, tag)
        data = re.search(r'src="data:image/\w+;base64,([^"]+)"', tag)
        if name and data:
            found[name.group(1)] = base64.b64decode(data.group(1))
    return found


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--out", required=True, help="folder for the sheets")
    ap.add_argument("--design", help="a saved design (.perma.geojson) to "
                                     "render instead of the review lot")
    ap.add_argument("--label", default="", help="the version in the sheets' "
                                                "titles (default: this branch)")
    ap.add_argument("--viewer-root", default=HTML,
                    help="another checkout's html/ folder, to draw the same "
                         "scenes with an older viewer")
    ap.add_argument("--online", action="store_true",
                    help="let the planner fetch terrain and wind")
    ap.add_argument("--tiles", action="store_true",
                    help="also save every tile on its own")
    ap.add_argument("--size", default="1280x760", help="a tile, WxH")
    args = ap.parse_args(argv)

    if find_chromium() is None:
        print("No Chromium or Chrome binary found. Set CHROME= to one.")
        return 2
    if not args.online:
        import tests  # noqa: F401  (its __init__ blocks the internet)
    use_throwaway_database()
    width, height = (int(v) for v in args.size.lower().split("x"))

    if args.design:
        with open(args.design, encoding="utf-8") as fh:
            lot = json.load(fh)
        name = os.path.basename(args.design).split(".")[0]
    else:
        print("planning the review lot…")
        lot, name = review_lot(), "The review lot"
    routes = {}
    for tag, (year, month, hour) in MOMENTS.items():
        routes[f"/__yard/lot_{tag}.json"] = scene(lot, year, month, hour)
    with_example = not args.design
    if with_example:
        from src.onboarding import build_example_project
        routes["/__yard/example_open.json"] = scene(
            build_example_project()[0], *MOMENTS["open"])
    label = args.label
    if not label:
        from src.app_version import running_version
        label = running_version() or "this checkout"
    spec = job(label, name, with_example, width, height)
    spec["keep_shots"] = bool(args.tiles)
    routes["/__yard/shots.json"] = spec

    print(f"rendering {len(spec['shots'])} pictures (a few minutes)…")
    server = Server(routes, viewer_root=args.viewer_root)
    try:
        dom = run_probe(server.url("yard_probe.html?shots=/__yard/shots.json"),
                        budget_ms=600000, timeout=1800)
    finally:
        server.stop()
    errors = re.search(r'<pre id="probe-errors"[^>]*>(.*?)</pre>', dom, re.S)
    if errors and errors.group(1).strip():
        print("the viewer threw:\n" + errors.group(1).strip())
    sheets = images(dom, "sheet")
    if not sheets:
        print("No pictures came back: the viewer did not start (no WebGL "
              "here?) or threw before it finished.")
        return 1
    os.makedirs(args.out, exist_ok=True)
    for kind, extra in (("sheet", sheets),
                        ("shot", images(dom, "shot") if args.tiles else {})):
        for key, data in extra.items():
            path = os.path.join(args.out, f"{key}.jpg")
            with open(path, "wb") as fh:
                fh.write(data)
            if kind == "sheet":
                print("wrote", path)
    return 0


if __name__ == "__main__":
    sys.exit(main())
