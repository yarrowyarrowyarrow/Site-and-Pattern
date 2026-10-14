"""
tests/test_address_search.py — no connection is not "no results" (V3.19, QF-3).

R6 of the first review: offline, a correct Edmonton address got *"No Alberta
results. Try a nearby intersection or town name"*, which blames the address.
``geocode_address`` returned ``[]`` both when nothing matched and when it could
not ask, so the Site panel could not tell them apart. It now returns ``None``
for a search that could not be made, and the panel says which happened.

The suite is offline (tests/__init__.py raises ``URLError`` for anything past
the machine), so the real offline path is the one a test takes by default.
"""

import os
import sys
import tempfile
import time
import unittest
from unittest import mock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

# The panel reads the catalogue: a database of the test's own.
_TMP = tempfile.mkdtemp(prefix="sp_address_search_")
import src.db.plants as _plants_mod  # noqa: E402
_plants_mod._DATA_DIR = _TMP
_plants_mod._DB_PATH = os.path.join(_TMP, "address_search.db")

from src import property_data  # noqa: E402

try:
    from PyQt6.QtWidgets import QApplication
    _HAVE_QT = True
except Exception:                                          # noqa: BLE001
    _HAVE_QT = False

_ADDRESS = "10423 Saskatchewan Drive NW, Edmonton"

_PLACE = {"lat": "53.5232", "lon": "-113.4935", "importance": 0.4,
          "display_name": "10423, Saskatchewan Drive NW, Edmonton, Alberta",
          "address": {"state": "Alberta", "house_number": "10423"}}


class TestTheTwoAnswers(unittest.TestCase):
    """``geocode_address``: ``None`` when it could not ask, ``[]`` when it
    asked and nothing matched."""

    def test_offline_is_none(self):
        """The real path: the suite's guard is a machine with no network."""
        self.assertIsNone(property_data.geocode_address(_ADDRESS))

    def test_a_failed_request_is_none(self):
        # http_get_json answers None for an HTTP error, a timeout and an
        # unreachable host alike, and logs which.
        with mock.patch.object(property_data, "_http_get_json", return_value=None):
            self.assertIsNone(property_data.geocode_address(_ADDRESS))

    def test_a_reply_that_is_not_a_list_of_places_is_none(self):
        with mock.patch.object(property_data, "_http_get_json",
                               return_value={"error": "Unable to geocode"}):
            self.assertIsNone(property_data.geocode_address(_ADDRESS))

    def test_no_match_is_an_empty_list(self):
        with mock.patch.object(property_data, "_http_get_json", return_value=[]):
            self.assertEqual(property_data.geocode_address(_ADDRESS), [])

    def test_matches_only_outside_the_prairies_are_no_match(self):
        elsewhere = dict(_PLACE, address={"state": "Ontario"})
        with mock.patch.object(property_data, "_http_get_json",
                               return_value=[elsewhere]):
            self.assertEqual(property_data.geocode_address(_ADDRESS), [])

    def test_a_match(self):
        with mock.patch.object(property_data, "_http_get_json",
                               return_value=[_PLACE]):
            hits = property_data.geocode_address(_ADDRESS)
        self.assertEqual(len(hits), 1)
        self.assertAlmostEqual(hits[0]["lat"], 53.5232)

    def test_what_needs_no_network_still_answers(self):
        """Typed coordinates and an empty box never ask Nominatim."""
        self.assertEqual(property_data.geocode_address("53.5, -113.5")[0]["lat"], 53.5)
        self.assertEqual(property_data.geocode_address("   "), [])

    def test_the_old_name_is_the_same_function(self):
        self.assertIs(property_data.geocode_alberta, property_data.geocode_address)


@unittest.skipUnless(_HAVE_QT, "PyQt6 not installed in this env")
class TestThePanelSaysWhich(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls._app = QApplication.instance() or QApplication(["sp-tests"])

    def _panel(self):
        from src.site_panel import SitePanel
        panel = SitePanel()
        self.addCleanup(panel.deleteLater)
        return panel

    def _search(self, panel, query=_ADDRESS, timeout=20.0):
        """Press Find as a person does, then wait for the answer: the search
        runs on its own thread and answers through the event loop."""
        panel._addr_input.blockSignals(True)       # no typeahead timer
        panel._addr_input.setText(query)
        panel._addr_input.blockSignals(False)
        panel._on_address_search()
        self.assertEqual(panel._lbl_status.text(), "Searching…")
        end = time.monotonic() + timeout
        while panel._lbl_status.text() == "Searching…" and time.monotonic() < end:
            self._app.processEvents()
            time.sleep(0.01)
        self._settle(panel, end)
        return panel._lbl_status.text()

    def _settle(self, panel, end):
        """Let the search's thread stop before the panel goes: a QThread
        destroyed while running ends the process (CLAUDE.md, V2.40)."""
        from src.site_panel import _safe_is_running
        while _safe_is_running(panel._geo_thread) and time.monotonic() < end:
            self._app.processEvents()
            time.sleep(0.01)

    def test_offline_it_says_it_needs_a_connection(self):
        from src.site_panel import SitePanel
        panel = self._panel()
        said = self._search(panel)
        self.assertEqual(said, SitePanel.OFFLINE_TEXT)
        self.assertIn("internet connection", said)
        self.assertNotIn("No address found", said)
        self.assertFalse(panel._addr_results.isVisibleTo(panel))

    def test_no_match_says_so(self):
        from src.site_panel import SitePanel
        panel = self._panel()
        with mock.patch.object(property_data, "_http_get_json", return_value=[]):
            said = self._search(panel)
        self.assertEqual(said, SitePanel.NO_MATCH_TEXT)
        self.assertNotIn("internet", said)

    def test_a_match_is_listed(self):
        panel = self._panel()
        with mock.patch.object(property_data, "_http_get_json",
                               return_value=[_PLACE]):
            said = self._search(panel)
        self.assertEqual(said, "")
        self.assertEqual(panel._addr_results.count(), 1)

    def test_a_failure_clears_the_last_search_s_matches(self):
        panel = self._panel()
        panel._on_geocode_results([{"label": "Old match", "lat": 53.5, "lng": -113.5}])
        self.assertEqual(panel._addr_results.count(), 1)
        panel._on_geocode_failed("unreachable")
        self.assertEqual(panel._addr_results.count(), 0)

    def test_the_words_are_plain(self):
        """What happened and what to do, no error text (09-words.md §1)."""
        from src.site_panel import SitePanel
        for text in (SitePanel.OFFLINE_TEXT, SitePanel.NO_MATCH_TEXT):
            self.assertLessEqual(text.count(". "), 1, text)     # two sentences
            for word in ("failed", "error", "Nominatim", "URLError", "("):
                self.assertNotIn(word, text)

    def test_an_exception_in_the_search_is_a_failure_not_a_crash(self):
        from src.site_panel import _GeocodeWorker
        worker = _GeocodeWorker(_ADDRESS)
        failed, results = [], []
        worker.failed.connect(failed.append)
        worker.results.connect(results.append)
        with mock.patch("src.property_data.geocode_address",
                        side_effect=RuntimeError("boom")):
            worker.run()
        self.assertEqual((len(failed), results), (1, []))


if __name__ == "__main__":
    unittest.main()
