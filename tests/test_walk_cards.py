"""
tests/test_walk_cards.py — the walk's cards and its zoom (F255, V3.38).

The owner, in Learn › Walk a wild landscape: *"I'd like to be able to click a
plant and read its drop down"* and *"use the scroll wheel to zoom out or in"*.
The hint on screen already said "left-click a plant to learn about it"; the
click did nothing, because only the design's 3D preview ever sent the viewer
the cards (``scene_dossier.build_dossier``). And walk mode turns the orbit
camera off, which is what owned the wheel.
"""

import json
import os
import pathlib
import re
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

_TMP_DIR = tempfile.mkdtemp(prefix="permadesign_walk_cards_test_")
import src.db.plants as _plants_mod  # noqa: E402
_plants_mod._DATA_DIR = _TMP_DIR
_plants_mod._DB_PATH = os.path.join(_TMP_DIR, "permadesign_test.db")

from src import walk_cards  # noqa: E402

_ROOT = pathlib.Path(__file__).resolve().parent.parent
_MODES = _ROOT / "html" / "scene3d" / "08-modes.js"


class _Viewer:
    def __init__(self):
        self.dossiers = []

    def set_dossier(self, dossier):
        self.dossiers.append(dossier)


class _Win:
    def __init__(self):
        self.viewer = _Viewer()


class TheWalkSendsItsCards(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        _plants_mod.init_db()
        from src.reference_ecosystem import build_reference_project
        from src.scene_contract import build_scene
        project = build_reference_project("aspen_parkland",
                                          center_lat=53.55,
                                          center_lng=-113.49)
        cls.scene = build_scene(project, year=12)

    def test_every_plant_in_the_scene_has_a_card(self):
        win = _Win()
        walk_cards.push(win, self.scene)
        dossier = win.viewer.dossiers[-1]
        in_scene = {str(p["plant_id"]) for p in self.scene["plants"]
                    if p.get("plant_id")}
        self.assertTrue(in_scene)
        self.assertEqual(set(dossier["plants"]), in_scene)
        self.assertTrue(dossier["fauna"], "a creature's card too")
        json.dumps(dossier)                  # it goes to the page as JSON

    def test_the_window_sends_them_with_every_scene(self):
        """Pushed from ``_render``, which every edit, undo, community switch
        and time change goes through, so a card left open stays current."""
        src = (_ROOT / "src" / "reference_ecosystem_window.py").read_text(
            encoding="utf-8")
        render = src[src.index("    def _render"):
                     src.index("    def _on_time_changed")]
        self.assertIn("walk_cards.push(self, scene)", render)

    def test_a_failure_sends_no_cards_rather_than_breaking_the_walk(self):
        win = _Win()
        with mock.patch("src.scene_dossier.build_dossier",
                        side_effect=RuntimeError("no database")):
            walk_cards.push(win, self.scene)
        self.assertEqual(win.viewer.dossiers[-1], {})


class PlantOnePutsItOnTheTrowel(unittest.TestCase):
    """V3.39: *Plant one* on an animal's card, for a plant the walk offers."""

    def _win(self):
        class Combo:
            def __init__(self):
                self.items = [{"plant_id": 3, "common_name": "June Grass"},
                              {"plant_id": 7, "common_name": "Wild Bergamot"}]
                self.current = 0

            def count(self):
                return len(self.items)

            def itemData(self, i):                          # noqa: N802
                return self.items[i]

            def setCurrentIndex(self, i):                   # noqa: N802
                self.current = i

        class Button:
            checked = False

            def setChecked(self, on):                       # noqa: N802
                self.checked = on

        class Say:
            text = ""

            def setText(self, text):                        # noqa: N802
                self.text = text

        win = _Win()
        win._species, win._plant_btn, win._say = Combo(), Button(), Say()
        win.modes = []
        win._set_mode = win.modes.append
        return win

    def test_it_chooses_the_plant_and_holds_out_the_trowel(self):
        win = self._win()
        walk_cards.on_plant_chosen(win, 7)
        self.assertEqual(win._species.current, 1)
        self.assertTrue(win._plant_btn.checked)
        self.assertEqual(win.modes, ["plant"])
        self.assertIn("Wild Bergamot", win._say.text)

    def test_a_plant_the_walk_does_not_offer_changes_nothing(self):
        win = self._win()
        walk_cards.on_plant_chosen(win, 99)
        self.assertEqual((win._species.current, win.modes), (0, []))

    def test_the_page_the_bridge_and_the_window_agree(self):
        widget = (_ROOT / "src" / "map3d_widget.py").read_text(encoding="utf-8")
        self.assertIn("plant_chosen = pyqtSignal(int)", widget)
        self.assertIn("def choosePlant(", widget)
        window = (_ROOT / "src" / "reference_ecosystem_window.py").read_text(
            encoding="utf-8")
        self.assertIn("bridge.plant_chosen.connect(", window)
        self.assertIn("walk_cards.on_plant_chosen(self, pid)", window)
        cards = (_ROOT / "html" / "scene3d" / "25-cards.js").read_text(
            encoding="utf-8")
        self.assertIn("_bridge.choosePlant(", cards)


def _walk_probe_data() -> bytes:
    """What the walk window pushes for the shipped Aspen Parkland, built by
    the functions the window calls (``ReferenceEcosystemWindow._render``)."""
    from datetime import datetime
    from src.reference_ecosystem import build_reference_project
    from src.reference_edit import palette
    from src.scene_contract import build_scene
    from src.scene_wildlife import support_by_taxon, wildlife_for_scene
    _plants_mod.init_db()
    project = build_reference_project("aspen_parkland", center_lat=53.55,
                                      center_lng=-113.49)
    scene = build_scene(project, year=12, when=datetime(2025, 6, 21, 13, 0))
    pids = [p["plant_id"] for p in scene["plants"] if p.get("plant_id")]
    plantable = [p["plant_id"] for p in palette("aspen_parkland")]
    return json.dumps({"scene": scene, "wildlife": wildlife_for_scene(scene),
                       "support": support_by_taxon(pids),
                       "dossier": walk_cards.build(
                           scene, plantable=plantable,
                           province=walk_cards.WALK_PROVINCE)}).encode("utf-8")


def _run_walk_probe():
    """``html/walk_probe.html`` in headless Chromium: the walk's real scene in
    walk mode, a click where the viewer's own picker finds a plant, and the
    card that opened, read back from the page's title."""
    from functools import partial
    from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
    import threading
    from tests.test_scene3d_render import _find_chromium, fail_on_viewer_errors

    payload = _walk_probe_data()

    class Handler(SimpleHTTPRequestHandler):
        def do_GET(self):                                   # noqa: N802
            if self.path.split("?")[0] == "/walk_probe_data.json":
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(payload)))
                self.end_headers()
                self.wfile.write(payload)
                return
            super().do_GET()

        def log_message(self, *args):
            pass

    try:
        httpd = ThreadingHTTPServer(
            ("127.0.0.1", 0),
            partial(Handler, directory=str(_ROOT / "html")))
    except OSError as exc:
        raise unittest.SkipTest(f"cannot bind a local port: {exc}")
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    try:
        url = f"http://127.0.0.1:{httpd.server_address[1]}/walk_probe.html"
        proc = subprocess.run(
            [_find_chromium(), "--headless", "--no-sandbox",
             "--disable-gpu-sandbox", "--enable-unsafe-swiftshader",
             "--use-angle=swiftshader", "--virtual-time-budget=45000",
             "--dump-dom", url],
            capture_output=True, text=True, timeout=240, encoding="utf-8")
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise unittest.SkipTest(f"Chromium would not run headlessly: {exc}")
    finally:
        httpd.shutdown()
        httpd.server_close()
    fail_on_viewer_errors(proc.stdout)
    miss = re.search(r"WALK_NO_CARD (\{.*?\})</title>", proc.stdout, re.S)
    if miss:
        raise AssertionError("the walk opened no card for any plant it "
                             f"picked: {miss.group(1)}")
    match = re.search(r"WALK_CARD (\{.*?\})</title>", proc.stdout, re.S)
    if not match:
        raise unittest.SkipTest(
            "the probe never reported — no WebGL in this environment "
            f"(chromium exit {proc.returncode})")
    return json.loads(match.group(1)), json.loads(payload)["dossier"]


def _chromium():
    try:
        from tests.test_scene3d_render import _find_chromium
        return _find_chromium()
    except Exception:                                      # noqa: BLE001
        return None


@unittest.skipIf(_chromium() is None,
                 "no Chromium binary (set CHROME= to run this gate)")
class AClickInTheWalkOpensTheCard(unittest.TestCase):
    """The end-to-end form of TheWalkSendsItsCards: in the real viewer, in
    walk mode, a left click on a plant opens that plant's card."""

    @classmethod
    def setUpClass(cls):
        cls.card, cls.dossier = _run_walk_probe()

    def test_the_card_that_opens_is_the_plant_clicked(self):
        card, dossier = self.card, self.dossier
        entry = dossier["plants"][card["key"]]
        self.assertEqual(card["name"], entry["name"])
        self.assertFalse(card["notes"], "no free-text notes on the card")

    def test_it_leads_with_what_the_plant_is_food_for(self):
        """V3.39: sentences first, eight animals, the rest folded, and
        everything else the card had under More about this plant."""
        entry = self.dossier["plants"][self.card["key"]]
        self.assertEqual(self.card["does"], len(entry["does"]))
        self.assertLessEqual(self.card["shown"], 8)
        self.assertEqual(self.card["folded"], len(entry["users"]) > 8)
        self.assertTrue(self.card["more"])

    def test_an_animal_on_the_card_opens_its_card_and_leads_back(self):
        card = self.card
        self.assertTrue(card.get("animal_link"), "no animal on the card")
        self.assertEqual(card["animal"], card["animal_link"])
        self.assertGreaterEqual(card["here"], 1,
                                "an animal's card links its plants here")
        self.assertIn(card["name"], card["back"])
        self.assertEqual(card["back_to"], card["name"])
        # No Plant one without the walk's bridge (this page has none).
        self.assertEqual(card["plant_one"], 0)

    def test_the_roster_is_one_line_and_a_fold(self):
        self.assertIn("recorded as food for", self.card["roster_head"])
        self.assertTrue(self.card["roster_folded"])


def _node():
    return shutil.which("node") or shutil.which("nodejs")


def _walk_zoom(cases):
    """``walkZoom(dist, deltaY)`` over ``cases``, run in node from the page's
    own source: the constants line and the function, cut out of 08-modes.js
    (the rest of the file needs three.js and a page)."""
    text = _MODES.read_text(encoding="utf-8")
    consts = re.search(r"^const _WALK_DIST_MIN = .*;$", text, re.M).group(0)
    start = text.index("function walkZoom(")
    end = text.index("\n}\n", start) + 3
    script = "\n".join([
        consts, text[start:end],
        "var cases = %s;" % json.dumps(cases),
        "console.log(JSON.stringify(cases.map(function (c) {"
        " return walkZoom(c[0], c[1]); })));",
    ])
    proc = subprocess.run([_node(), "-"], input=script, capture_output=True,
                          text=True, timeout=60, encoding="utf-8")
    if proc.returncode != 0:
        raise AssertionError(f"node failed: {proc.stderr}")
    return json.loads(proc.stdout)


@unittest.skipIf(_node() is None, "no node binary")
class TheWheelZoomsTheWalk(unittest.TestCase):

    def test_a_notch_moves_the_camera_about_a_sixth(self):
        out, back, still = _walk_zoom([[6.5, 100], [6.5, -100], [6.5, 0]])
        self.assertAlmostEqual(out / 6.5, 1.16, places=2)
        self.assertAlmostEqual(back / 6.5, 1 / 1.16, places=2)
        self.assertEqual(still, 6.5)

    def test_it_stops_at_two_and_thirty_metres(self):
        near, far = _walk_zoom([[2.1, -5000], [29.0, 5000]])
        self.assertEqual((near, far), (2, 30))

    def test_the_follow_camera_reads_it(self):
        text = _MODES.read_text(encoding="utf-8")
        self.assertIn("addScaledVector(cam, _walkDist)", text)
        self.assertNotIn("_WALK_DIST)", text, "the old constant is gone")
        listener = text[text.index("addEventListener('wheel'"):]
        listener = listener[:listener.index("});")]
        self.assertIn("if (!walkMode) return;", listener,
                      "out of walk mode the orbit camera keeps the wheel")
        self.assertIn("preventDefault", listener)

    def test_the_hint_says_so(self):
        self.assertIn("scroll to zoom", _MODES.read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
