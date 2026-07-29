"""
tests/test_feedback.py — the in-app feedback channel (V2.37).

User feedback: "There needs to be a very easy straightforward way for
users/test-users to send me feedback directly via the app." There was none at
all — a tester who hit the Learn-tab crash had to already know the maintainer.

The assertions that matter here are the privacy ones. This is the one feature
that transmits anything about the user, so what it does NOT include is as much
part of the contract as what it does.
"""

import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from src import feedback  # noqa: E402


class TestFeedbackCore(unittest.TestCase):
    """Qt-free: importable and testable with no display."""

    def test_categories_are_broader_than_bug_reports(self):
        """A form that only accepts defects collects only defects, which is the
        feedback a design tool least needs."""
        keys = set(feedback.category_keys())
        self.assertIn("broken", keys)
        self.assertIn("idea", keys)
        self.assertIn("stuck", keys)
        self.assertIn("liked", keys)

    def test_every_category_has_a_prompt_and_an_issue_label(self):
        for key, label, issue_label, prompt in feedback.CATEGORIES:
            self.assertTrue(label.strip(), key)
            self.assertTrue(issue_label.strip(), key)
            self.assertTrue(prompt.strip().endswith(("?", ")")), key)

    def test_title_summarises_the_first_line(self):
        title = feedback.build_title("broken", "The quiz crashes\nevery time")
        self.assertIn("The quiz crashes", title)
        self.assertNotIn("every time", title)

    def test_long_titles_are_truncated_not_dropped(self):
        title = feedback.build_title("idea", "x" * 300)
        self.assertLessEqual(len(title), 80)
        self.assertTrue(title.endswith("…"))

    def test_an_empty_message_still_produces_a_usable_report(self):
        self.assertIn("no summary", feedback.build_title("idea", ""))
        self.assertIn("no description", feedback.build_body(""))

    # ── privacy ──────────────────────────────────────────────────────────────

    def test_diagnostics_carry_only_setup_facts(self):
        """Deliberately excludes anything about the user's design: where they
        live is in their project, and a bug report is not a reason to collect
        it."""
        diag = feedback.diagnostics("V2.37", 58)
        self.assertEqual(set(diag), {"App version", "OS", "Python", "DB schema"})
        blob = feedback.format_diagnostics(diag).lower()
        for leak in ("lat", "lng", "longitude", "address", "/home/", "project"):
            self.assertNotIn(leak, blob, f"diagnostics leaked {leak!r}")

    def test_diagnostics_are_omitted_when_not_wanted(self):
        body = feedback.build_body("something broke", None)
        self.assertNotIn("App version", body)
        self.assertIn("something broke", body)

    def test_diagnostics_shown_are_exactly_what_is_attached(self):
        """The dialog shows format_diagnostics() above the opt-in checkbox, so
        the two must not be able to diverge — an app that reports something it
        did not display has spent trust it cannot get back."""
        diag = feedback.diagnostics("V2.37", 58)
        shown = feedback.format_diagnostics(diag)
        body = feedback.build_body("hello", diag)
        self.assertTrue(body.endswith(shown))

    # ── the submission ───────────────────────────────────────────────────────

    def test_issue_url_prefills_title_body_and_label(self):
        url = feedback.issue_url("broken", "The quiz crashes",
                                 repo="owner/repo")
        self.assertTrue(url.startswith("https://github.com/owner/repo/issues/new?"))
        from urllib.parse import parse_qs, urlparse
        q = parse_qs(urlparse(url).query)
        self.assertIn("The quiz crashes", q["title"][0])
        self.assertIn("The quiz crashes", q["body"][0])
        self.assertEqual(q["labels"][0], "bug")

    def test_issue_url_defaults_to_the_projects_own_repo(self):
        from src.github_releases import DEFAULT_REPO
        self.assertIn(DEFAULT_REPO, feedback.issue_url("idea", "hi"))

    def test_special_characters_survive_the_url(self):
        msg = "It said “100 % done” & then crashed — at 53.5°N?"
        from urllib.parse import parse_qs, urlparse
        q = parse_qs(urlparse(feedback.issue_url("broken", msg, repo="a/b")).query)
        self.assertIn("100 % done", q["body"][0])
        self.assertIn("crashed", q["body"][0])


def _qt_available():
    try:
        from PyQt6.QtWidgets import QApplication  # noqa: F401
        return True
    except Exception:                               # noqa: BLE001
        return False


@unittest.skipUnless(_qt_available(), "PyQt6 not installed in this env")
class TestFeedbackDialog(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from PyQt6.QtWidgets import QApplication
        cls._app = QApplication.instance() or QApplication([])

    def _dialog(self):
        from src.feedback_dialog import FeedbackDialog
        return FeedbackDialog(feedback.diagnostics("V2.37", 58))

    def test_send_is_disabled_until_there_is_something_to_say(self):
        d = self._dialog()
        self.assertFalse(d._ok.isEnabled())
        d._text.setPlainText("it broke")
        self.assertTrue(d._ok.isEnabled())

    def test_choosing_a_category_changes_the_prompt(self):
        d = self._dialog()
        d._choose("liked")
        liked = d._prompt.text()
        d._choose("broken")
        self.assertNotEqual(liked, d._prompt.text())
        self.assertEqual(d.category_key(), "broken")

    def test_the_attached_details_are_on_screen_before_they_are_attached(self):
        d = self._dialog()
        self.assertTrue(d._attach.isChecked())
        self.assertIn("V2.37", d._diag_box.text())


@unittest.skipUnless(_qt_available(), "PyQt6 not installed in this env")
class TestHelpMenuWiring(unittest.TestCase):
    def test_help_menu_offers_feedback(self):
        import pathlib
        src = (pathlib.Path(__file__).resolve().parent.parent
               / "src" / "app.py").read_text(encoding="utf-8")
        self.assertIn("Send &Feedback…", src)
        self.assertIn("feedback_flow.send_feedback", src)

    def test_it_costs_no_new_mainwindow_method(self):
        """The flow-module discipline, which tests/test_onboarding.py also
        guards: wire via lambda → flow function, not a new method."""
        import ast
        import pathlib
        src = (pathlib.Path(__file__).resolve().parent.parent
               / "src" / "app.py").read_text(encoding="utf-8")
        tree = ast.parse(src)
        cls = next(n for n in ast.walk(tree)
                   if isinstance(n, ast.ClassDef) and n.name == "MainWindow")
        names = {n.name for n in cls.body if isinstance(n, ast.FunctionDef)}
        self.assertNotIn("_on_send_feedback", names)
        self.assertLessEqual(len(names), 140)


if __name__ == "__main__":
    unittest.main()
