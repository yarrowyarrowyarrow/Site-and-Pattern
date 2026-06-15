"""
tests/test_user_paths.py — the shared per-user data directory and the one-time
PermaDesign → Site & Pattern folder migration (V1.69).

Uses a temp base dir (never the real ~/.local/share) and patches
``user_paths._platform_base`` so all three platform branches are irrelevant to
the test outcome — we only care about the migrate/create behaviour.
"""

import shutil
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from src import user_paths
from src.branding import DATA_DIR_NAME, LEGACY_DATA_DIR_NAME


class TestMigration(unittest.TestCase):
    def setUp(self):
        self.base = Path(tempfile.mkdtemp(prefix="sp_userpaths_"))
        self.addCleanup(shutil.rmtree, self.base, ignore_errors=True)
        self._patch = mock.patch.object(
            user_paths, "_platform_base", return_value=self.base)
        self._patch.start()
        self.addCleanup(self._patch.stop)

    def test_fresh_install_creates_new_dir(self):
        d = Path(user_paths.user_data_dir())   # returns a str; compare as Path
        self.assertEqual(d, self.base / DATA_DIR_NAME)
        self.assertTrue(d.is_dir())
        self.assertFalse((self.base / LEGACY_DATA_DIR_NAME).exists())

    def test_legacy_only_is_migrated(self):
        legacy = self.base / LEGACY_DATA_DIR_NAME
        legacy.mkdir()
        (legacy / "permadesign.db").write_text("db", encoding="utf-8")

        d = Path(user_paths.user_data_dir())

        self.assertEqual(d, self.base / DATA_DIR_NAME)
        # The user's data came along…
        self.assertTrue((d / "permadesign.db").is_file())
        # …and the old folder is gone (renamed, not copied).
        self.assertFalse(legacy.exists())

    def test_both_present_keeps_new_and_leaves_legacy(self):
        legacy = self.base / LEGACY_DATA_DIR_NAME
        legacy.mkdir()
        (legacy / "old.db").write_text("old", encoding="utf-8")
        new = self.base / DATA_DIR_NAME
        new.mkdir()
        (new / "new.db").write_text("new", encoding="utf-8")

        d = Path(user_paths.user_data_dir())

        self.assertEqual(d, new)
        self.assertTrue((new / "new.db").is_file())
        self.assertFalse((new / "old.db").exists())   # never clobbered
        self.assertTrue(legacy.exists())              # left untouched

    def test_migration_failure_falls_back_gracefully(self):
        legacy = self.base / LEGACY_DATA_DIR_NAME
        legacy.mkdir()
        (legacy / "permadesign.db").write_text("db", encoding="utf-8")

        with mock.patch.object(user_paths.shutil, "move",
                               side_effect=OSError("cross-device")):
            d = Path(user_paths.user_data_dir())

        # The move failed and was swallowed: the legacy data stays reachable
        # where it is, and a usable directory is still returned (created).
        self.assertTrue(d.is_dir())
        self.assertTrue(legacy.exists())


class TestDataDirPathIsPure(unittest.TestCase):
    def test_no_side_effects(self):
        base = Path(tempfile.mkdtemp(prefix="sp_pure_"))
        self.addCleanup(shutil.rmtree, base, ignore_errors=True)
        with mock.patch.object(user_paths, "_platform_base", return_value=base):
            p = user_paths.data_dir_path()
        self.assertEqual(p, base / DATA_DIR_NAME)
        # Pure: computing the path must not create the folder (so module-level
        # constants can be built at import time without side effects).
        self.assertFalse(p.exists())


if __name__ == "__main__":
    unittest.main()
