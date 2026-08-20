"""
tests/test_log.py — the logging foundation (V2.22).

Covers the properties the rest of the codebase relies on:
  * get_logger namespaces under one app root (so init_logging governs all),
  * init_logging is idempotent, never raises, and writes under the user
    data dir (redirected to a tempdir here),
  * an uninitialized logger stays silent below WARNING (headless/test
    callers create no files and spam nothing).
"""

import importlib
import logging
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


class TestGetLogger(unittest.TestCase):
    def test_namespaced_under_app_root(self):
        from src.log import get_logger
        lg = get_logger("src.some_module")
        self.assertEqual(lg.name, "sitepattern.src.some_module")
        # Configuring the app root must govern this logger (dot-hierarchy).
        self.assertTrue(lg.name.startswith("sitepattern."))

    def test_root_logger_returned_for_empty_name(self):
        from src.log import get_logger
        self.assertEqual(get_logger().name, "sitepattern")
        self.assertEqual(get_logger("sitepattern").name, "sitepattern")

    def test_uninitialized_module_logger_has_no_handlers(self):
        # Headless callers (tests, agent API) never call init_logging —
        # module loggers must carry no handlers of their own.
        from src.log import get_logger
        self.assertFalse(get_logger("src.fresh_module_xyz").handlers)


class TestInitLogging(unittest.TestCase):
    def setUp(self):
        # Fresh module state + isolated data dir per test.
        import src.log as log_mod
        self._tmp = tempfile.mkdtemp(prefix="sp-logtest-")
        import src.user_paths as user_paths
        self._orig_dds = user_paths._data_dir_str
        user_paths._data_dir_str = lambda: self._tmp
        self._log_mod = importlib.reload(log_mod)

    def tearDown(self):
        import src.user_paths as user_paths
        user_paths._data_dir_str = self._orig_dds
        root = logging.getLogger("sitepattern")
        for h in list(root.handlers):
            h.close()
            root.removeHandler(h)
        importlib.reload(self._log_mod)

    def test_init_creates_log_file_and_is_idempotent(self):
        root1 = self._log_mod.init_logging()
        n_handlers = len(root1.handlers)
        root2 = self._log_mod.init_logging()
        self.assertIs(root1, root2)
        self.assertEqual(len(root2.handlers), n_handlers,
                         "second init_logging must not stack handlers")
        path = self._log_mod.log_file_path()
        self.assertTrue(path.startswith(self._tmp))
        self.assertTrue(os.path.exists(path), "log file not created")
        root1.info("hello from the test")
        for h in root1.handlers:
            h.flush()
        with open(path, encoding="utf-8") as f:
            self.assertIn("hello from the test", f.read())

    def test_init_survives_unwritable_dir(self):
        # A bad data dir must not raise — stderr-only fallback.
        import src.user_paths as user_paths
        user_paths._data_dir_str = lambda: os.path.join(
            self._tmp, "gone", "\0bad" if os.name != "nt" else "aux")
        try:
            self._log_mod.init_logging()  # must not raise
        finally:
            user_paths._data_dir_str = lambda: self._tmp


if __name__ == "__main__":
    unittest.main()
