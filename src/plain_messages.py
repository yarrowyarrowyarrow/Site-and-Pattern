"""
src/plain_messages.py — what a failed open, save or plan says, and the two
questions asked before work is thrown away (V3.18, WD-4).

The rule, from docs/homeowner/09-words.md §3.7: every message says what
happened, whether work is safe, and what to do. The technical detail goes to
the app's log (``src.log``), never into the message. Until V3.18 a damaged
design file showed a JSON parser's complaint about "line 1 column 1", a failed
plan showed the generator's internal wording, and closing with unsaved work
offered *Exit anyway?* with no way to save.

The words are Qt-free and tested without a display. The ``tell_`` and
``ask_`` helpers build the boxes; each goes through :func:`_run`, which a test
replaces so a box never waits for an answer nobody will give.
"""

from __future__ import annotations

import os

from src.log import get_logger, log_file_path

log = get_logger(__name__)


# ── The words ───────────────────────────────────────────────────────────────

def open_failed_text(path: str) -> str:
    name = os.path.basename(path or "") or "the design"
    return (f"Couldn't open \"{name}\". The file may be damaged or from a "
            "newer version. Your other designs are fine.")


def save_failed_text(name: str) -> str:
    return (f"Couldn't save \"{name or 'this design'}\". Your work is still "
            "open; try Save As… to a different folder.")


def plan_failed_text(detail: str = "") -> str:
    """The plan's failure in words, by its cause. The generator's own
    message goes to the log; these are the two failures a person can act on,
    and the plan's general advice for the rest."""
    d = (detail or "").lower()
    if "no plants or communities" in d:
        return ("Couldn't make a plan: no plants matched everything you "
                "asked for. Untick a goal or raise the budget, then try "
                "again.")
    if "no site location" in d:
        return ("Couldn't make a plan: the design has no yard outline or "
                "address yet. Draw your yard or find its address, then try "
                "again.")
    return ("Couldn't make a plan. Check that your yard outline or bed is "
            "closed, then try again.")


def save_before_closing_text(name: str) -> str:
    return f"Save changes to \"{name or 'this design'}\" before closing?"


def discard_for_new_text(name: str) -> str:
    return (f"Discard unsaved changes to \"{name or 'this design'}\" and "
            "start a new yard?")


def details_text() -> str:
    """What *Show Details* reveals: where the full record is."""
    try:
        where = log_file_path()
    except Exception:                                      # noqa: BLE001
        where = ""
    return ("A full record is in the log:\n" + where if where
            else "A full record is in the app's log.")


# ── The boxes ───────────────────────────────────────────────────────────────

def _run(box):
    """Show ``box`` and wait for its answer. Tests replace this."""
    return box.exec()


def _box(parent, title: str, text: str, *, warning: bool = True,
         details: str = ""):
    from PyQt6.QtWidgets import QMessageBox
    box = QMessageBox(parent)
    box.setIcon(QMessageBox.Icon.Warning if warning
                else QMessageBox.Icon.Question)
    box.setWindowTitle(title)
    box.setText(text)
    if details:
        box.setDetailedText(details)
    return box


def tell_open_failed(parent, path: str) -> None:
    """Call from the ``except`` block of a failed open: logs the exception
    with its traceback, then says so in words."""
    log.exception("could not open %s", path)
    _run(_box(parent, "Couldn't open", open_failed_text(path),
              details=details_text()))


def tell_save_failed(parent, name: str) -> None:
    """Call from the ``except`` block of a failed save."""
    log.exception("could not save %s", name)
    _run(_box(parent, "Couldn't save", save_failed_text(name),
              details=details_text()))


def tell_plan_failed(parent, detail: str) -> None:
    log.warning("the plan failed: %s", detail)
    _run(_box(parent, "Couldn't make a plan", plan_failed_text(detail),
              details=details_text()))


def ask_save_before_closing(parent, name: str) -> str:
    """``"save"``, ``"discard"`` or ``"cancel"``."""
    from PyQt6.QtWidgets import QMessageBox
    B = QMessageBox.StandardButton
    box = _box(parent, "Unsaved changes", save_before_closing_text(name),
               warning=False)
    box.setStandardButtons(B.Save | B.Discard | B.Cancel)
    box.button(B.Discard).setText("Don't save")
    box.setDefaultButton(B.Save)
    answer = _run(box)
    if answer == B.Save:
        return "save"
    if answer == B.Discard:
        return "discard"
    return "cancel"


def ask_discard_for_new(parent, name: str) -> bool:
    from PyQt6.QtWidgets import QMessageBox
    B = QMessageBox.StandardButton
    box = _box(parent, "New yard", discard_for_new_text(name), warning=False)
    box.setStandardButtons(B.Discard | B.Cancel)
    box.setDefaultButton(B.Cancel)
    return _run(box) == B.Discard


def ask_design_name(parent, *, title: str = "Save design",
                    label: str = "Name this design:",
                    suggested: str = "My yard") -> str:
    """A name for a design, or ``""`` if the person cancelled or gave none
    (V3.23: asked at the first save only when the address has not named the
    design, ST-5, and by File › Rename Design…, ST-7)."""
    from PyQt6.QtWidgets import QInputDialog
    box = QInputDialog(parent)
    box.setWindowTitle(title)
    box.setLabelText(label)
    box.setTextValue(suggested)
    if not _run(box):
        return ""
    return " ".join((box.textValue() or "").split())
