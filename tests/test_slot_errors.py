"""
tests/test_slot_errors.py — a button that raises is a message, not the end of
the session (V3.05).

The V3.05 surface audit clicked every button in the window and one of them
(*Download Edmonton Data*) aborted the whole app on every press: PyQt6 calls
``qFatal`` on an exception escaping a slot unless ``sys.excepthook`` has been
replaced. ``src/slot_errors.py`` replaces it. The text and the throttle are
checked here without a display; the behaviour that matters, the process living
through a raising slot, is checked in a child process both ways, because the
hook is process-wide and a test must not install it into the suite's own.
"""

import os
import subprocess
import sys
import textwrap
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src import slot_errors  # noqa: E402

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _raise_here():
    raise ValueError("cannot import the thing")


class TestTheWords(unittest.TestCase):

    def setUp(self):
        slot_errors.reset()

    def _info(self):
        try:
            _raise_here()
        except ValueError:
            return sys.exc_info()

    def test_summary_names_the_fault(self):
        summary, details = slot_errors.describe(*self._info())
        self.assertEqual(summary, "ValueError: cannot import the thing")
        self.assertIn("Traceback", details)
        self.assertIn("_raise_here", details)

    def test_a_long_message_is_cut(self):
        try:
            raise RuntimeError("x" * 500)
        except RuntimeError:
            summary, _ = slot_errors.describe(*sys.exc_info())
        self.assertLessEqual(len(summary), 160)

    def test_the_message_says_what_to_do_and_where_the_record_is(self):
        text = slot_errors.message_text("ValueError: boom", "/data/logs/app.log")
        self.assertIn("still open", text)
        self.assertIn("save", text)
        self.assertIn("/data/logs/app.log", text)
        self.assertIn("Send Feedback", text)
        self.assertIn("ValueError: boom", text)

    def test_one_fault_is_reported_once(self):
        key = slot_errors.fault_key(*self._info()[0::2])
        self.assertTrue(slot_errors.should_show(key, now=0.0))
        self.assertFalse(slot_errors.should_show(key, now=1.0))

    def test_the_same_line_is_the_same_fault_whatever_the_message(self):
        a = slot_errors.fault_key(*self._info()[0::2])
        b = slot_errors.fault_key(*self._info()[0::2])
        self.assertEqual(a, b)

    def test_at_most_a_few_a_minute(self):
        shown = [slot_errors.should_show(("E", "f.py", n), now=float(n))
                 for n in range(10)]
        self.assertEqual(sum(shown), slot_errors.MAX_PER_MINUTE)
        # A minute later there is room again.
        self.assertTrue(slot_errors.should_show(("E", "f.py", 99), now=100.0))


def _qt_available() -> bool:
    try:
        import PyQt6.QtWidgets  # noqa: F401
        return True
    except Exception:                                      # noqa: BLE001
        return False


_CHILD = textwrap.dedent("""
    import os, sys
    sys.path.insert(0, {root!r})
    os.environ["QT_QPA_PLATFORM"] = "offscreen"
    from PyQt6.QtWidgets import QApplication, QPushButton
    app = QApplication(["slot-errors-test"])
    if {install}:
        from src import slot_errors
        slot_errors._show = lambda summary, details: print("REPORTED", summary)
        slot_errors.install()
    def broken():
        raise ImportError("cannot import name '_USER_AGENT'")
    button = QPushButton("Download")
    button.clicked.connect(broken)
    button.click()
    app.processEvents()
    print("STILL RUNNING")
""")


@unittest.skipUnless(_qt_available(), "PyQt6 not installed in this env")
class TestTheAppLivesThroughIt(unittest.TestCase):

    def _run(self, install: bool):
        env = dict(os.environ, QT_QPA_PLATFORM="offscreen",
                   SITEANDPATTERN_ALLOW_NETWORK="")
        return subprocess.run(
            [sys.executable, "-c", _CHILD.format(root=_ROOT, install=install)],
            capture_output=True, text=True, timeout=120, env=env)

    def test_without_the_hook_a_raising_button_ends_the_process(self):
        # The premise: if this ever stops being true, the module is moot.
        r = self._run(install=False)
        self.assertNotIn("STILL RUNNING", r.stdout)
        self.assertNotEqual(r.returncode, 0)

    def test_with_the_hook_it_is_reported_and_the_process_goes_on(self):
        r = self._run(install=True)
        self.assertEqual(r.returncode, 0, r.stderr[-2000:])
        self.assertIn("REPORTED ImportError", r.stdout)
        self.assertIn("STILL RUNNING", r.stdout)

    def test_main_installs_it(self):
        with open(os.path.join(_ROOT, "main.py"), encoding="utf-8") as fh:
            self.assertIn("slot_errors.install()", fh.read())


if __name__ == "__main__":
    unittest.main()
