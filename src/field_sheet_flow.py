"""
src/field_sheet_flow.py — print the site-walk sheet (F32, V3.05).

Design principle P11 — see docs/DESIGN_PHILOSOPHY.md: the body and the site
know things the screen does not.

Site › Notes (Field Notes until V3.08) asks ten questions only the ground can
answer, and until V3.05 the only way to answer them was to stand in the yard
holding a laptop.
*Print this sheet* saves them as a page for a clipboard (``pdf_export.
export_field_sheet``), with anything already noted printed under its question;
the full design PDF carries the same page first, before Site prep, because
walking the site is the first job.

Free function taking ``main``, wired from ``app.py`` by a lambda (MainWindow's
method budget is guarded).
"""

from __future__ import annotations


def export(main) -> str:
    """Ask where, save the sheet, say so. Returns the path, or ``""``."""
    from PyQt6.QtWidgets import QFileDialog, QMessageBox
    path, _ = QFileDialog.getSaveFileName(
        main, "Save the site-walk sheet", "site-walk.pdf",
        "PDF Files (*.pdf);;All Files (*)")
    if not path:
        return ""
    if not path.lower().endswith(".pdf"):
        path += ".pdf"
    try:
        from src.pdf_export import export_field_sheet
        export_field_sheet(path, main._project)
    except Exception as exc:                               # noqa: BLE001
        QMessageBox.critical(main, "Could not save the sheet", str(exc))
        return ""
    main.statusBar().showMessage(f"Site-walk sheet saved to {path}", 6000)
    return path
