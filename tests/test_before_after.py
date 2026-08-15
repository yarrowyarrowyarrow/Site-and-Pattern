"""
tests/test_before_after.py — before / after / in five years (F76, V2.56).

The one image that makes people act: the user's yard now, the design at year 1,
the design at year 5, on one page. Every ingredient existed for three releases
and had never been assembled.

Three layers here, and the third is the interesting one:

* the **spec builder**, Qt-free, like ``presentation_still``;
* the **page geometry**, split out of the painter so it can be checked without
  rendering anything;
* the **capture chain**, driven against a stub viewer. Real rendering needs a
  GPU this container does not have — but the *sequencing* is where the bugs
  live (a stale run interleaving, a photo panel sent to the renderer, panels
  arriving out of order), and none of that needs a GPU to catch.
"""

import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

_TMP = tempfile.mkdtemp(prefix="permadesign_before_after_")
try:
    import src.db.plants as _plants_mod
    _plants_mod._DATA_DIR = _TMP
    _plants_mod._DB_PATH = os.path.join(_TMP, "t.db")
except Exception:  # pragma: no cover
    pass

from src import before_after as ba  # noqa: E402
from src.project_store import ProjectStore  # noqa: E402

_GP = lambda _pid: {"years_to_maturity": 8}          # noqa: E731


def _qt_available():
    try:
        from PyQt6.QtWidgets import QApplication  # noqa: F401
        return True
    except Exception:
        return False


def _project(n=3):
    p = {"type": "FeatureCollection", "features": [], "properties": {}}
    store = ProjectStore(p)
    for i in range(n):
        store.add_plant(i + 1, f"Plant {i}", 51.05 + i * 1e-5, -114.07)
    return p


#: A real 1x1 PNG as a data URL — QPixmap.loadFromData must actually succeed on
#: it, or the tests below would be exercising the decode-failure path by
#: accident and reporting it as success.
_PNG = ("data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAf"
        "FcSJAAAADUlEQVR42mP8z8BQDwAEhQGAhKmMIQAAAABJRU5ErkJggg==")


def _with_photo(project, image=_PNG):
    from src import site_photo
    site_photo.set_feature(project, site_photo.build_feature(
        image=image,
        center={"lat": 51.05, "lng": -114.07}, width_m=20.0, aspect=0.66))
    return project


class TestPanelSpecs(unittest.TestCase):
    def test_three_panels_in_reading_order(self):
        panels = ba.panel_specs(_project(), get_plant=_GP)
        self.assertEqual([p["id"] for p in panels],
                         [ba.BEFORE, ba.NEAR, ba.FAR])

    def test_years_come_from_the_timeline_vocabulary(self):
        """Read off snapshot_years rather than hard-coded, so the timeline and
        this page cannot disagree about which years are worth showing."""
        from src.snapshot_timeline import placed_records, snapshot_years
        project = _project()
        expected = snapshot_years(placed_records(project), get_plant=_GP)[:2]
        self.assertEqual(list(ba.panel_years(project, get_plant=_GP)),
                         list(expected))

    def test_every_rendered_panel_shares_one_camera(self):
        """A viewpoint change between two panels reads as a change in the
        design. The only thing allowed to vary across this page is time."""
        panels = ba.panel_specs(_project(), get_plant=_GP)
        cams = {p["camera"] for p in panels if p["kind"] == ba.KIND_RENDER}
        self.assertEqual(len(cams), 1, f"panels disagree on camera: {cams}")
        months = {p["month"] for p in panels if p["kind"] == ba.KIND_RENDER}
        self.assertEqual(len(months), 1, f"panels disagree on month: {months}")

    def test_an_unknown_camera_falls_back_rather_than_breaking(self):
        panels = ba.panel_specs(_project(), camera="nonsense", get_plant=_GP)
        from src.presentation_still import CAMERA_PRESETS
        for p in panels:
            if p["kind"] == ba.KIND_RENDER:
                self.assertIn(p["camera"], CAMERA_PRESETS)


class TestTheBeforePanelIsHonest(unittest.TestCase):
    """The two 'before' cases are different arguments. 'Your lawn as it is now'
    is what converts somebody; 'the design on install day' is weaker but true.
    Letting one silently stand in for the other is the failure being avoided."""

    def test_with_a_photo_it_is_the_photo(self):
        panels = ba.panel_specs(_with_photo(_project()), get_plant=_GP)
        before = panels[0]
        self.assertEqual(before["kind"], ba.KIND_PHOTO)
        self.assertTrue(before["image"])
        self.assertIn("today", before["caption"].lower())

    def test_without_a_photo_it_is_a_year_zero_render_that_says_so(self):
        before = ba.panel_specs(_project(), get_plant=_GP)[0]
        self.assertEqual(before["kind"], ba.KIND_RENDER)
        self.assertEqual(before["year"], ba.INSTALL_YEAR)
        cap = before["caption"].lower()
        self.assertIn("no photograph", cap,
                      "the fallback before-panel does not say it is not a "
                      "photo of the user's yard — that is the one thing it "
                      "must not imply")

    def test_the_two_captions_are_not_the_same(self):
        a = ba.panel_specs(_project(), get_plant=_GP)[0]["caption"]
        b = ba.panel_specs(_with_photo(_project()), get_plant=_GP)[0]["caption"]
        self.assertNotEqual(a, b)

    def test_a_photo_panel_is_never_sent_to_the_renderer(self):
        panels = ba.panel_specs(_with_photo(_project()), get_plant=_GP)
        ids = [pid for pid, _req in ba.render_requests(panels)]
        self.assertNotIn(ba.BEFORE, ids)
        self.assertEqual(len(ids), 2)

    def test_without_a_photo_all_three_render(self):
        panels = ba.panel_specs(_project(), get_plant=_GP)
        self.assertEqual(len(ba.render_requests(panels)), 3)


class TestRenderRequests(unittest.TestCase):
    def test_sizing_is_not_restated(self):
        """It comes from presentation_still.render_request, so a print-
        resolution change lands on both features at once."""
        from src.presentation_still import PRINT_WIDTH_PX
        panels = ba.panel_specs(_project(), get_plant=_GP)
        for _pid, req in ba.render_requests(panels):
            self.assertEqual(req["width"], PRINT_WIDTH_PX)
            self.assertGreater(req["height"], 0)
            self.assertGreaterEqual(req["pixel_ratio"], 1)

    def test_each_request_carries_its_own_year(self):
        panels = ba.panel_specs(_project(), get_plant=_GP)
        years = [req["year"] for _pid, req in ba.render_requests(panels)]
        self.assertEqual(len(set(years)), len(years),
                         "two panels would render the same year — the page "
                         "would show the same picture twice")


@unittest.skipUnless(_qt_available(), "PyQt6 not installed in this env")
class TestPageGeometry(unittest.TestCase):
    """Split out of the painter because the failure it prevents — panels off
    the bottom of the page, or a caption running under the next panel — is
    invisible until somebody prints it."""

    def test_panels_fit_the_page(self):
        from src.pdf_export import before_after_layout
        w, h, s = 2550.0, 3300.0, 3.0
        for n in (2, 3):
            with self.subTest(panels=n):
                lay = before_after_layout(w, h, s, n)
                self.assertEqual(len(lay["xs"]), n)
                right = lay["xs"][-1] + lay["col_w"]
                self.assertLessEqual(round(right, 3), w,
                                     "the last panel runs off the page")
                bottom = (lay["top"] + lay["img_h"] + lay["caption_h"]
                          + lay["footer_h"])
                self.assertLessEqual(round(bottom, 3), h,
                                     "the row runs off the bottom")

    def test_columns_do_not_overlap(self):
        from src.pdf_export import before_after_layout
        lay = before_after_layout(2550.0, 3300.0, 3.0, 3)
        for a, b in zip(lay["xs"], lay["xs"][1:]):
            self.assertGreaterEqual(b - a, lay["col_w"],
                                    "columns overlap — captions would collide")


@unittest.skipUnless(_qt_available(), "PyQt6 not installed in this env")
class TestTheCaptureChain(unittest.TestCase):
    """Drive the chain against a stub viewer.

    Real rendering needs a GPU, but the sequencing is where the bugs are: a
    second run interleaving with the first, a photo panel sent to the renderer,
    results arriving in the wrong order.
    """

    _app = None

    @classmethod
    def setUpClass(cls):
        from PyQt6.QtWidgets import QApplication
        cls._app = QApplication.instance() or QApplication(["test_before_after"])

    def _win(self):
        """A stand-in Scene3DWindow: the six attributes the flow touches."""
        from PyQt6.QtWidgets import QSpinBox

        # A 1x1 PNG as a data URL — enough for QPixmap.loadFromData to succeed.
        png = ("data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAf"
               "FcSJAAAADUlEQVR42mP8z8BQDwAEhQGAhKmMIQAAAABJRU5ErkJggg==")

        class Viewer:
            def __init__(self):
                self.snapshots = 0
                self.presets = []

            def models_ready(self, cb):
                cb(True)

            def set_camera_preset(self, name):
                self.presets.append(name)

            def snapshot(self, cb, **kw):
                self.snapshots += 1
                cb(png)

        class Win:
            def __init__(self):
                self.viewer = Viewer()
                self._year = QSpinBox(); self._year.setRange(0, 100)
                self._month = QSpinBox(); self._month.setRange(1, 12)
                self.pushes = 0

            def _update_labels(self):
                pass

            def _push_scene(self):
                self.pushes += 1

        return Win(), png

    def setUp(self):
        """Replace the chain's one scheduling hop with a queue we control.

        The obvious way to test this — pump a Qt event loop until the callback
        lands — **segfaults the suite**. Alone it passes; with the whole suite's
        modules imported it aborts inside ``processEvents``, located with
        ``python -X faulthandler`` pointing straight at the test's own pump.

        A queue is also strictly better than running each hop immediately:
        immediate execution finishes the whole chain before ``capture_panels``
        returns, so a second run could never overlap the first and the run-token
        guard would be untestable. Holding the hops lets a run be caught
        genuinely mid-flight.

        What this gives up is proof that ``QTimer.singleShot`` is wired — one
        line, in ``_later``, which is not where sequencing bugs live.
        """
        from src import before_after_flow as flow
        self._pending: list = []
        real = flow._later
        flow._later = lambda _ms, fn: self._pending.append(fn)
        self.addCleanup(setattr, flow, "_later", real)

    def _drain(self, *_args, **_kwargs):
        """Run every queued hop, and anything they queue in turn."""
        for _ in range(200):
            if not self._pending:
                return
            self._pending.pop(0)()
        raise AssertionError("the capture chain did not terminate")

    def test_it_captures_every_panel_in_order(self):
        from src import before_after_flow as flow
        win, _png = self._win()
        panels = ba.panel_specs(_project(), get_plant=_GP)
        out = {}
        flow.capture_panels(win, panels, lambda r: out.setdefault("r", r))
        self._drain(out)
        self.assertIn("r", out, "the chain never called back")
        self.assertEqual(len(out["r"]), 3)
        self.assertEqual([t for t, _p, _c in out["r"]],
                         [p["title"] for p in panels],
                         "panels came back out of order")
        self.assertEqual(win.viewer.snapshots, 3)

    def test_a_photo_panel_is_decoded_not_rendered(self):
        from src import before_after_flow as flow
        win, _png = self._win()
        panels = ba.panel_specs(_with_photo(_project()), get_plant=_GP)
        out = {}
        flow.capture_panels(win, panels, lambda r: out.setdefault("r", r))
        self._drain(out)
        self.assertEqual(len(out["r"]), 3, "the photo panel was dropped")
        self.assertEqual(win.viewer.snapshots, 2,
                         "the photo panel was sent to the renderer")

    def test_every_panel_gets_its_own_year_pushed(self):
        from src import before_after_flow as flow
        win, _png = self._win()
        panels = ba.panel_specs(_project(), get_plant=_GP)
        out = {}
        flow.capture_panels(win, panels, lambda r: out.setdefault("r", r))
        self._drain(out)
        self.assertEqual(win.pushes, 3,
                         "the scene was not re-pushed per panel — the page "
                         "would show the same year three times")

    def test_an_undecodable_photo_falls_back_instead_of_vanishing(self):
        """Found by this suite. A stored photo that will not decode used to be
        dropped, leaving a two-panel page with no 'before' at all — the whole
        argument gone, and silently. It now renders install day in its place."""
        from src import before_after_flow as flow
        win, _png = self._win()
        project = _with_photo(_project(), image="data:image/png;base64,AAAA")
        panels = ba.panel_specs(project, get_plant=_GP)
        self.assertEqual(panels[0]["kind"], ba.KIND_PHOTO)   # before the fix-up
        out = {}
        flow.capture_panels(win, panels, lambda r: out.setdefault("r", r))
        self._drain(out)
        self.assertEqual(len(out["r"]), 3, "the before-panel vanished")
        self.assertIn("no photograph", out["r"][0][2].lower(),
                      "the fallback panel does not admit it is not a photo")
        self.assertEqual(win.viewer.snapshots, 3,
                         "the fallback was not rendered")

    def test_the_fallback_keeps_the_pages_camera(self):
        """Left to render_request's own default it would come out 'overview'
        beside two 'sidewalk' panels, and the page would stop comparing like
        with like."""
        from src import before_after_flow as flow
        win, _png = self._win()
        project = _with_photo(_project(), image="data:image/png;base64,AAAA")
        panels = ba.panel_specs(project, get_plant=_GP)
        out = {}
        flow.capture_panels(win, panels, lambda r: out.setdefault("r", r))
        self._drain(out)
        self.assertEqual(len(set(win.viewer.presets)), 1,
                         f"panels rendered from different cameras: "
                         f"{win.viewer.presets}")

    def test_a_second_run_cancels_the_first(self):
        """Without the run token two exports interleave: two chains pushing
        scenes at one viewer and filling one result list."""
        from src import before_after_flow as flow
        win, _png = self._win()
        panels = ba.panel_specs(_project(), get_plant=_GP)
        first = []
        flow.capture_panels(win, panels, lambda r: first.append(r))
        second = {}
        flow.capture_panels(win, panels, lambda r: second.setdefault("r", r))
        self._drain(second)
        self.assertIn("r", second, "the second run never completed")
        self.assertEqual(first, [],
                         "the superseded run still called back — two exports "
                         "would both write into the PDF")


if __name__ == "__main__":
    unittest.main()
