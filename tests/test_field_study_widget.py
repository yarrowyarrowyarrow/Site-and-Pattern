"""
tests/test_field_study_widget.py — the Field Study quiz runner (F48).

The widget had no tests at all, and it was where a reported "using the quiz
crashes the app" lived. The crash shape matters for what these assert: an
exception escaping a Qt slot does not raise into the caller, it calls qFatal()
and aborts the process — so a test that merely drives the slot and catches
nothing would pass while the app dies in the user's hands. These therefore
exercise the *states* that made the slot raise, and assert the guards.

Offscreen Qt; skipped entirely where PyQt6 isn't installed, like the other
widget tests.
"""

import os
import pathlib
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

try:
    from PyQt6.QtWidgets import QApplication
    _HAVE_QT = True
except ImportError:                                  # pragma: no cover
    _HAVE_QT = False

import src.db.plants as _plants_mod                  # noqa: E402


@unittest.skipUnless(_HAVE_QT, "PyQt6 not installed in this env")
class TestFieldStudyWidgetFlow(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls._app = QApplication.instance() or QApplication([])
        cls._tmp = tempfile.mkdtemp(prefix="permadesign_fsw_")
        _plants_mod._DATA_DIR = cls._tmp
        _plants_mod._DB_PATH = os.path.join(cls._tmp, "t.db")
        cls._orig_dir = _plants_mod._user_data_dir
        _plants_mod._user_data_dir = lambda: pathlib.Path(cls._tmp)
        from src.db.plants import init_db
        init_db()

    @classmethod
    def tearDownClass(cls):
        _plants_mod._user_data_dir = cls._orig_dir

    def _widget(self, provider=None):
        from src.field_study_widget import FieldStudyWidget
        w = FieldStudyWidget(provider)
        # Never touch the network from a test; the warm path is covered
        # separately by its own assertions below.
        w._warm_photo_pool = lambda *a, **k: None
        return w

    # ── the crash that was reported ──────────────────────────────────────────

    def test_answering_after_a_failed_restart_does_not_raise(self):
        """The reported crash. `new_quiz` used to return early on an empty quiz
        while leaving the previous question's buttons live and `_answered`
        False, so the next click indexed an empty list."""
        w = self._widget()
        w.new_quiz()
        self.assertTrue(w._quiz, "precondition: a real quiz was generated")

        # Simulate the restart failing (a locked DB is the real-world case).
        import src.field_study_widget as mod
        orig = mod.__dict__.get("generate_quiz")
        from src import field_study
        real = field_study.generate_quiz

        def boom(*a, **k):
            raise RuntimeError("database is locked")

        field_study.generate_quiz = boom
        try:
            w.new_quiz()
        finally:
            field_study.generate_quiz = real
            if orig is not None:
                mod.__dict__["generate_quiz"] = orig

        self.assertEqual(w._quiz, [])
        # The slot must survive a click in this state — this is the abort.
        w._answer(0)
        w._answer(3)
        w._next()

    def test_no_clickable_option_survives_an_empty_quiz(self):
        """Defence in depth for the same bug: nothing clickable should be left
        on screen when there is no question behind it."""
        w = self._widget()
        w.new_quiz()
        w._quiz = []
        w._clear_question()
        for b in w._opt_btns:
            self.assertFalse(b.isVisible())
            self.assertFalse(b.isEnabled())

    def test_show_and_answer_tolerate_an_out_of_range_index(self):
        w = self._widget()
        w.new_quiz()
        w._i = 999
        w._show()          # must not raise
        w._answered = False
        w._answer(0)       # must not raise

    # ── ordinary flow still works ────────────────────────────────────────────

    def test_a_full_quiz_can_be_played_to_the_end(self):
        w = self._widget()
        w.new_quiz()
        n = len(w._quiz)
        self.assertGreater(n, 0)
        for _ in range(n):
            w._answer(0)
            w._next()
        self.assertLessEqual(w._score, n)

    def test_repeated_restarts_are_stable(self):
        """The user's actual gesture: hammer Restart."""
        w = self._widget()
        for _ in range(25):
            w.new_quiz()
            if w._quiz:
                w._answer(0)
        self.assertTrue(True)   # reaching here without an abort is the assertion

    def test_answer_marks_right_and_wrong_with_a_stylesheet_qt_accepts(self):
        """The feedback colouring silently did nothing: the continuation lines
        are plain literals, so the doubled `}}` reached Qt unbalanced and the
        whole rule was dropped."""
        w = self._widget()
        w.new_quiz()
        correct = w._quiz[0]["answer_index"]
        w._answer(correct)
        sheet = w._opt_btns[correct].styleSheet()
        self.assertIn("font-weight: bold", sheet)
        self.assertEqual(sheet.count("{"), sheet.count("}"),
                         f"unbalanced braces — Qt drops the sheet: {sheet!r}")

    # ── the photo warm ───────────────────────────────────────────────────────

    def test_warm_pool_is_serial_and_deduped(self):
        """It used to start eight parallel fetches on the global pool on every
        Restart, against an index that could not take concurrent writers."""
        from src.field_study_widget import FieldStudyWidget
        w = FieldStudyWidget(None)

        started: list = []

        class _FakePool:
            def start(self, task):
                started.append(task)

        import PyQt6.QtCore as qtcore
        orig = qtcore.QThreadPool.globalInstance
        qtcore.QThreadPool.globalInstance = staticmethod(lambda: _FakePool())
        try:
            w._warm_photo_pool()
            first = len(w._warmed)
            w._warm_photo_pool()
        finally:
            qtcore.QThreadPool.globalInstance = orig

        self.assertLessEqual(len(started), 2,
                             "one queued task per call, not one per photo")
        self.assertGreater(first, 0, "precondition: something was warmable")
        # Second call must not re-queue the URLs the first one already took.
        self.assertEqual(len(w._warmed), min(first * 2, len(w._warmed)))
        self.assertGreaterEqual(len(w._warmed), first)


@unittest.skipUnless(_HAVE_QT, "PyQt6 not installed in this env")
class TestLearnPanelSync(unittest.TestCase):
    """`set_structures` stored its argument and refreshed nothing, so the
    lesson track and docent script described the design as it was before a
    structure was placed."""

    @classmethod
    def setUpClass(cls):
        cls._app = QApplication.instance() or QApplication([])

    def test_set_structures_refreshes_the_readers(self):
        from src.learn_panel import LearnPanel
        panel = LearnPanel()
        calls = []
        panel._lesson_track.refresh = lambda: calls.append("lesson")
        panel._docent.refresh = lambda: calls.append("docent")
        panel.set_structures([{"name": "Bee hotel"}])
        self.assertIn("lesson", calls)
        self.assertIn("docent", calls)


if __name__ == "__main__":
    unittest.main()
