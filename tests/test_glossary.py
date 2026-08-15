"""
tests/test_glossary.py — every Site Info number explains itself (F122, V2.55).

Twenty metrics sit on the Site Info tab and fifteen of them explained themselves
nowhere before this. The point of the guard here is not that the twenty strings
exist — it is that **a twenty-first row cannot be added bare**, which is how the
fifteen accumulated in the first place: each was added by someone who knew what
it meant.

Two layers, deliberately:

* a **source scan** that runs everywhere, with no Qt, pairing the panel's
  ``_explain`` calls against the glossary's keys in both directions;
* a **real-widget test** that builds the actual panel offscreen and reads the
  tooltips back off the actual caption widgets. The V2.37 dead-control bug —
  a control wired to a parameter nothing read — is the reason this repo does not
  trust a source scan on its own.
"""

import os
import re
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

_TMP = tempfile.mkdtemp(prefix="permadesign_glossary_")
try:
    import src.db.plants as _plants_mod
    _plants_mod._DATA_DIR = _TMP
    _plants_mod._DB_PATH = os.path.join(_TMP, "t.db")
except Exception:  # pragma: no cover
    pass

from src import glossary  # noqa: E402

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_PANEL = os.path.join(_ROOT, "src", "site_panel.py")


def _panel_source():
    with open(_PANEL, "r", encoding="utf-8") as fh:
        return fh.read()


def _qt_available():
    try:
        from PyQt6.QtWidgets import QApplication  # noqa: F401
        return True
    except Exception:
        return False


class TestGlossaryTable(unittest.TestCase):
    """The table itself, with no UI in the picture."""

    def test_every_entry_is_populated(self):
        self.assertEqual(len(glossary.METRIC_KEYS), 20,
                         "the Site Info tab has 20 metric rows")
        for key in sorted(glossary.METRIC_KEYS):
            with self.subTest(metric=key):
                self.assertTrue(glossary.term(key).strip(),
                                f"{key} has no human-readable term")
                text = glossary.explain(key)
                self.assertTrue(text.strip(), f"{key} has no explanation")
                self.assertGreater(
                    len(text), 60,
                    f"{key}'s explanation is a label, not an explanation — the "
                    f"point is to say what the number decides, not restate it")

    def test_an_unknown_key_is_empty_not_an_exception(self):
        """A missing tooltip is a gap; a traceback while building the panel is
        an outage. The tests are where a bad key gets caught."""
        self.assertEqual(glossary.explain("no_such_metric"), "")
        self.assertEqual(glossary.term("no_such_metric"), "")

    def test_the_zone_entry_uses_the_function_that_had_no_caller(self):
        """climate.zone_description() returned exactly the right sentence and
        was called by nothing at all until this feature. If the glossary stops
        composing it in, it goes back to being dead code."""
        from src.climate import zone_description
        generic = glossary.explain(glossary.ZONE)
        for zone in (2, 3, 4, 8):
            with self.subTest(zone=zone):
                specific = glossary.explain(glossary.ZONE, zone=zone)
                self.assertIn(zone_description(zone), specific)
                self.assertNotEqual(
                    specific, generic,
                    "explain(ZONE, zone=…) returned the generic text — the "
                    "measured zone is not reaching the reader")

    def test_no_plant_use_vocabulary(self):
        """P12. This glossary is about site physics — cold, warmth, water, wind,
        ground. If it ever grows plant-use content it has to go through the
        ethnobotanical scans that guard the public surfaces first, and this
        test is the tripwire that says so."""
        banned = ("medicinal", "edible", "traditional use", "ceremonial",
                  "ethnobotan", "remedy", "tea from", "poultice")
        for key in sorted(glossary.METRIC_KEYS):
            blob = (glossary.term(key) + " " + glossary.explain(key)).lower()
            for word in banned:
                with self.subTest(metric=key, word=word):
                    self.assertNotIn(
                        word, blob,
                        f"{key} mentions '{word}'. This glossary is site "
                        f"physics only (P12) — see the module docstring")


class TestPanelWiring(unittest.TestCase):
    """Source-level pairing, so this runs even with no Qt in the environment."""

    def test_every_glossary_key_is_used_by_the_panel(self):
        used = set(re.findall(r"glossary\.([A-Z_]+)\b", _panel_source()))
        wired = {getattr(glossary, name) for name in used
                 if isinstance(getattr(glossary, name, None), str)}
        missing = sorted(glossary.METRIC_KEYS - wired)
        self.assertFalse(
            missing,
            f"these metrics have an explanation nobody shows: {missing}. "
            f"Either wire them with _explain() or drop them from the glossary")

    def test_the_panel_uses_no_key_the_glossary_lacks(self):
        used = set(re.findall(r"glossary\.([A-Z_]+)\b", _panel_source()))
        unknown = sorted(n for n in used
                         if not isinstance(getattr(glossary, n, None), str))
        self.assertFalse(
            unknown,
            f"site_panel references glossary constants that do not exist: "
            f"{unknown} — those rows would silently get no tooltip")

    def test_the_inline_tooltips_were_not_left_behind(self):
        """The three that existed before V2.55 moved into the glossary. If an
        inline copy comes back, the panel and the glossary can disagree about
        what a number means, which is worse than only one of them saying it."""
        src = _panel_source()
        for stale in ("_lbl_gdd.setToolTip(", "_lbl_frost.setToolTip(",
                      "_lbl_ecoregion.setToolTip(",
                      "_lbl_info_aspect.setToolTip(",
                      "_lbl_info_wind.setToolTip("):
            with self.subTest(call=stale):
                self.assertNotIn(
                    stale, src,
                    f"{stale} is back in site_panel.py — the glossary is meant "
                    f"to be the single source for these strings")


@unittest.skipUnless(_qt_available(), "PyQt6 not installed in this env")
class TestTheTooltipsReallyLand(unittest.TestCase):
    """Build the real panel and read the tooltips back off the real widgets.

    A source scan proves the call was written. This proves it arrived — and in
    particular that it arrived on the **caption**, which is the half that was
    missing for every tooltip this panel had before V2.55.
    """

    _app = None
    _panel = None

    @classmethod
    def setUpClass(cls):
        from PyQt6.QtWidgets import QApplication
        # A name, not []: the first QApplication built in a process wins for the
        # whole run, and an empty argv aborts the next QWebEngineView anywhere
        # in the suite (see CLAUDE.md and the architecture guard).
        cls._app = QApplication.instance() or QApplication(["test_glossary"])
        from src.site_panel import SitePanel
        cls._panel = SitePanel()

    @classmethod
    def tearDownClass(cls):
        if cls._panel is not None:
            cls._panel.close()
            cls._panel.deleteLater()

    #: (value-label attribute, its form layout attribute, glossary key)
    _ROWS = (
        ("_lbl_zone", "_hard_form", glossary.ZONE),
        ("_lbl_gdd", "_hard_form", glossary.GDD),
        ("_lbl_frost", "_hard_form", glossary.FROST_WINDOW),
        ("_lbl_ecoregion", "_hard_form", glossary.ECOREGION),
    )

    def test_the_value_label_carries_the_explanation(self):
        for attr, _form, key in self._ROWS:
            with self.subTest(row=attr):
                widget = getattr(self._panel, attr)
                self.assertEqual(widget.toolTip(), glossary.explain(key))

    def test_the_caption_carries_it_too(self):
        """The whole point of F122. Hovering the word you do not understand is
        what a beginner actually does; before this it showed nothing."""
        for attr, form_attr, key in self._ROWS:
            with self.subTest(row=attr):
                form = getattr(self._panel, form_attr)
                caption = form.labelForField(getattr(self._panel, attr))
                self.assertIsNotNone(
                    caption, f"{attr} has no caption widget — labelForField "
                             f"returned None, so the row was never added")
                self.assertEqual(
                    caption.toolTip(), glossary.explain(key),
                    f"the caption beside {attr} explains nothing")

    def test_the_zone_tooltip_updates_with_the_measured_zone(self):
        """Set once at build time it would go stale — reading as working while
        describing a winter that is not yours."""
        from src.climate import zone_description
        before = self._panel._lbl_zone.toolTip()
        self._panel._on_hardiness({"zone": 4, "source": "test"})
        after = self._panel._lbl_zone.toolTip()
        self.assertNotEqual(before, after, "the zone tooltip did not refresh")
        self.assertIn(zone_description(4), after)
        caption = self._panel._hard_form.labelForField(self._panel._lbl_zone)
        self.assertIn(zone_description(4), caption.toolTip(),
                      "the value refreshed but the caption went stale")


if __name__ == "__main__":
    unittest.main()
