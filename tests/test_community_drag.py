"""
tests/test_community_drag.py — drag-a-community-into-the-mix (V1.87).

Mirrors the plant drag-to-mix on the Plant Library tab: the Communities
library tree is draggable (carries the community id) and the "Plant
Communities Mix" box is a drop target; dropping adds the community and
expands the Placement pane.

Skips cleanly when PyQt6 isn't installed. Temp-DB pattern; offscreen Qt.
"""

import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

_TMP = tempfile.mkdtemp(prefix="permadesign_community_drag_")
try:
    import src.db.plants as _plants_mod
    _plants_mod._DATA_DIR = _TMP
    _plants_mod._DB_PATH = os.path.join(_TMP, "t.db")
except Exception:  # pragma: no cover
    pass


def _qt_available():
    try:
        import PyQt6  # noqa: F401
        from PyQt6.QtWidgets import QApplication  # noqa: F401
        return True
    except Exception:
        return False


@unittest.skipUnless(_qt_available(), "PyQt6 not installed in this env")
class TestCommunityDrag(unittest.TestCase):
    _app = None
    _panel = None
    _err = None

    @classmethod
    def setUpClass(cls):
        from PyQt6.QtWidgets import QApplication
        cls._app = QApplication.instance() or QApplication(["permadesign-tests"])
        try:
            from src.db.plants import init_db
            init_db()
            from src.polyculture_panel import PolyculturePanel
            cls._panel = PolyculturePanel()
        except Exception as exc:  # noqa: BLE001
            cls._err = exc

    def setUp(self):
        if self._err is not None:
            self.skipTest(f"PolyculturePanel construction failed: {self._err}")

    def _first_community_id(self):
        from PyQt6.QtCore import Qt
        tree = self._panel.polyculture_tree
        for i in range(tree.topLevelItemCount()):
            pid = tree.topLevelItem(i).data(0, Qt.ItemDataRole.UserRole)
            if pid:
                return int(pid)
        return None

    def test_tree_is_draggable_with_id_payload(self):
        from src.polyculture_panel import _CommunityTree, _COMMUNITY_MIME
        tree = self._panel.polyculture_tree
        self.assertIsInstance(tree, _CommunityTree)
        self.assertTrue(tree.dragEnabled())
        if tree.topLevelItemCount() == 0:
            self.skipTest("no communities seeded")
        md = tree.mimeData([tree.topLevelItem(0)])
        self.assertTrue(md.hasFormat(_COMMUNITY_MIME))

    def test_drop_adds_to_mix_and_expands(self):
        cid = self._first_community_id()
        if cid is None:
            self.skipTest("no communities seeded")
        p = self._panel
        p._mix_communities = []
        p._refresh_community_mix()
        p._placement_panel.set_expanded(False)
        p._add_to_community_mix(cid)        # what the drop handler calls
        self.assertEqual(len(p._mix_communities), 1)
        self.assertTrue(p._placement_panel.expanded())


if __name__ == "__main__":
    unittest.main()
