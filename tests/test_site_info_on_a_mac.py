"""
tests/test_site_info_on_a_mac.py — Site Info's values draw whole under a style
that holds a form's fields to their size hint (V3.19, QF-5 review).

QF-5 made every value on Site Info wrap, so the page stopped scrolling sideways
with a pin. Under macOS's own style that broke three lines that read correctly
before: the Mac's default field growth policy is ``FieldsStayAtSizeHint``, a
wrapped label's size hint is a quarter of 80 characters, and the form gave
"May 12 → Sep 18  (128 days)" a box 127 px wide and one line tall, so it drew
as two lines cut through the middle. Linux, Windows and CI draw in styles that
grow the fields, so nothing else in the suite could see it.

A form asks its parent widget's style for the policy, so the test gives each
form's parent a style that answers as the Mac's does, leaving the application's
style alone for every other test in the process.
"""

import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

# The ecoregion row counts communities from the catalogue: a database of the
# test's own.
_TMP = tempfile.mkdtemp(prefix="sp_site_info_mac_")
import src.db.plants as _plants_mod  # noqa: E402
_plants_mod._DATA_DIR = _TMP
_plants_mod._DB_PATH = os.path.join(_TMP, "site_info_mac.db")

try:
    from PyQt6.QtWidgets import (
        QApplication, QFormLayout, QLabel, QProxyStyle, QStyle, QStyleFactory,
        QVBoxLayout, QWidget)
    _HAVE_QT = True
except Exception:                                          # noqa: BLE001
    _HAVE_QT = False

if _HAVE_QT:
    class _HeldToHint(QProxyStyle):
        """Fusion, answering for form fields as QMacStyle does."""

        def styleHint(self, hint, option=None, widget=None, data=None):  # noqa: N802
            if hint == QStyle.StyleHint.SH_FormLayoutFieldGrowthPolicy:
                return QFormLayout.FieldGrowthPolicy.FieldsStayAtSizeHint.value
            return super().styleHint(hint, option, widget, data)


@unittest.skipUnless(_HAVE_QT, "PyQt6 not installed in this env")
class TestSiteInfoValuesDrawWhole(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls._app = QApplication.instance() or QApplication(["sp-tests"])
        # Lives as long as the process: a widget keeps only a guarded pointer
        # to the style it is given, and must never outlive it unguarded.
        cls._mac = _HeldToHint(QStyleFactory.create("Fusion"))

    def test_every_value_is_as_tall_as_its_words_need(self):
        from src.site_panel import SitePanel
        host = QWidget()
        self.addCleanup(host.deleteLater)
        QVBoxLayout(host).setContentsMargins(0, 0, 0, 0)
        panel = SitePanel()
        host.layout().addWidget(panel)
        page = panel.info_page.widget()
        forms = page.findChildren(QFormLayout)
        self.assertGreaterEqual(len(forms), 5)
        for form in forms:
            form.parentWidget().setStyle(self._mac)
        # The emulation took: each form's parent now speaks for the Mac.
        hint = QStyle.StyleHint.SH_FormLayoutFieldGrowthPolicy
        self.assertEqual(
            {f.parentWidget().style().styleHint(hint) for f in forms},
            {QFormLayout.FieldGrowthPolicy.FieldsStayAtSizeHint.value})

        # What an online pin in Edmonton fills in, through the real handlers.
        panel._lbl_label.setText(
            "10423 Saskatchewan Drive Northwest, Strathcona, Edmonton, "
            "Alberta, T6E 4R7, Canada")
        panel._on_hardiness({"zone": "3b", "avg_extreme_min_c": -36.4,
                             "source": "Natural Resources Canada plant "
                                       "hardiness zones (2014)"})
        panel._on_climate({"gdd5_mean": 1452.0, "years_used": 10,
                           "last_spring_frost_doy": 132,
                           "first_fall_frost_doy": 261,
                           "frost_free_days": 128, "cached": True})
        panel._on_ecoregion({"key": "aspen_parkland",
                             "label": "Aspen Parkland (central AB / SK)"})
        panel.show_wind({"annual": {"prevailing_label": "WNW",
                                    "mean_speed": 17.0}, "cached": True})

        host.resize(424, 768)            # the side panel's width at 1366 × 768
        host.show()
        for _ in range(3):
            self._app.processEvents()

        cut = []
        for form in forms:
            for row in range(form.rowCount()):
                item = form.itemAt(row, QFormLayout.ItemRole.FieldRole)
                value = item.widget() if item is not None else None
                if (isinstance(value, QLabel) and value.wordWrap()
                        and value.text() and value.isVisibleTo(page)):
                    need = value.heightForWidth(value.width())
                    if need > value.height():
                        cut.append(f"{value.text()!r}: {value.width()} px wide, "
                                   f"{value.height()} tall, needs {need}")
        self.assertEqual(cut, [])
        self.assertIn("→", panel._lbl_frost.text())       # the row was filled


if __name__ == "__main__":
    unittest.main()
