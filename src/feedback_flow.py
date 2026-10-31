"""
feedback_flow.py — wire the feedback dialog to the app (V2.37).

Free functions taking ``main``, per the project's flow-module convention, so
``Help → Send Feedback…`` costs MainWindow no new method (the architecture guard
caps the class at 140 and the discipline is the point, not the number).

Qt is imported lazily so the module stays importable headless.
"""

from __future__ import annotations

def open_guide(main) -> None:
    """Help › How to Plan Your Yard: the guide, in a window of its own (F253,
    V3.38). Until V3.38 it opened the README on GitHub's default branch,
    which had no guide; :mod:`src.guide` says why it moved."""
    try:
        from src.guide_window import open_guide as show
        show(main)
    except Exception:                               # noqa: BLE001
        from src import slot_errors
        slot_errors.report("The guide")


def _app_version(main) -> str:
    """Whatever the build knows about itself — baked version, else the branch."""
    try:
        from src.app_version import build_version
        version = build_version()
        if version:
            return version
    except Exception:                               # noqa: BLE001
        pass
    try:
        return main._current_branch_name() or ""
    except Exception:                               # noqa: BLE001
        return ""


def _schema_version():
    try:
        from src.db.plants import _SCHEMA_VERSION
        return _SCHEMA_VERSION
    except Exception:                               # noqa: BLE001
        return None


def send_feedback(main) -> None:
    """Collect a report and hand it to the browser, prefilled.

    Wrapped so a failure here can never take down the app — the one surface
    whose whole job is to hear about failures should not become one.
    """
    try:
        from PyQt6.QtCore import QUrl
        from PyQt6.QtGui import QDesktopServices
        from PyQt6.QtWidgets import QMessageBox
        from src.feedback import diagnostics, issue_url, mailto_url
        from src.feedback_dialog import EMAIL, FeedbackDialog

        diag = diagnostics(_app_version(main), _schema_version())
        dialog = FeedbackDialog(diag, main)
        if dialog.exec() != dialog.DialogCode.Accepted:
            return

        attached = diag if dialog.wants_diagnostics() else None
        if dialog.way() == EMAIL:
            url = mailto_url(dialog.address(), dialog.category_key(),
                             dialog.message(), attached)
        else:
            url = issue_url(dialog.category_key(), dialog.message(), attached)
        if not url:
            QMessageBox.information(
                main, "Send Feedback",
                "Couldn't work out where to send this. Please open an issue on "
                "the project's GitHub page.")
            return
        QDesktopServices.openUrl(QUrl(url))
        try:
            main.statusBar().showMessage(
                "Opened your email with the message filled in."
                if dialog.way() == EMAIL else
                "Opened a prefilled report in your browser.", 4000)
        except Exception:                           # noqa: BLE001
            pass
    except Exception as exc:                        # noqa: BLE001
        try:
            from PyQt6.QtWidgets import QMessageBox
            QMessageBox.warning(main, "Send Feedback",
                                f"Couldn't open the feedback form: {exc}")
        except Exception:                           # noqa: BLE001
            pass
