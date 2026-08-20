"""
data_sources_flow.py — the "where this data came from" screen (V2.42).

Design principle P9 (uncertainty is a feature — ship ranges and confidence,
never false precision) — see docs/DESIGN_PHILOSOPHY.md.

The app's licensing and sourcing position is careful and, in the case of the
photographs, mechanically enforced — and it was written down only in
``docs/DATA_SOURCES.md``, a file referenced from code comments and reachable by
a user exactly never. The About dialog showed a version and a commit hash.

So a user had no way to answer either of the two questions they are entitled to
ask about an app that tells them what to plant: *is this real*, and *is this
yours to give me*. This dialog answers both from inside the app.

Called as a lambda from the Help menu (``src/app.py``), so it costs MainWindow
no method — the same pattern as ``feedback_flow`` and ``onboarding_flow``.
"""

from __future__ import annotations

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QDialog, QDialogButtonBox, QLabel, QScrollArea, QVBoxLayout, QWidget,
)

from src.branding import APP_NAME


def _counts() -> dict:
    """Live coverage numbers, read from the database rather than hardcoded.

    A page about data honesty that quotes stale numbers would be its own
    counter-example. Degrades to an empty dict if the DB is unavailable.
    """
    try:
        from src.db.plants import get_connection            # noqa: PLC0415
        conn = get_connection()
        try:
            q = lambda sql: conn.execute(sql).fetchone()[0]  # noqa: E731
            return {
                "plants": q("SELECT COUNT(*) FROM plants"),
                "fauna": q("SELECT COUNT(*) FROM fauna"),
                "documented": q("SELECT COUNT(*) FROM plant_fauna"),
                "derived": q("SELECT COUNT(*) FROM plant_fauna_derived"),
                "photos": q("SELECT COUNT(*) FROM plants "
                            "WHERE COALESCE(image_url,'') <> ''"),
            }
        finally:
            conn.close()
    except Exception:                                        # noqa: BLE001
        return {}


def _body_html() -> str:
    from src.citations import all_sources, format_citation, disclaimer

    c = _counts()
    parts = [
        f"<h3>Where {APP_NAME}'s data comes from</h3>",
        "<p>Two different questions, answered separately below: whether the "
        "ecological claims are real, and whether the material is ours to give "
        "you.</p>",
    ]

    if c:
        parts.append(
            "<h4>What is in the catalogue</h4><ul>"
            f"<li>{c['plants']} plants, {c['fauna']} animals</li>"
            f"<li><b>{c['documented']}</b> plant↔animal relationships from "
            "published records, each citing a work listed below</li>"
            f"<li><b>{c['derived']}</b> further relationships <i>derived</i> "
            "from host records published at genus level — real claims, shown "
            "as inferred rather than recorded, and never counted in the "
            "Habitat Value Score</li>"
            f"<li>{c['photos']} plant photographs, every one carrying its "
            "photographer's credit and licence</li></ul>")

    parts.append(
        "<h4>How confident each claim is</h4>"
        "<p>Every relationship carries one of three labels, and the app never "
        "blurs them:</p><ul>"
        "<li><b>Documented</b> — a record in the literature, with a citation.</li>"
        "<li><b>Recorded</b> — in our catalogue, but no one cited a source. "
        "Most companion-planting pairings are here. Treat them as folklore "
        "worth trying, not evidence.</li>"
        "<li><b>Derived</b> — computed by this app from a broader published "
        "record, shown dashed on the relationship web, and carrying a "
        "confidence band rather than a number we cannot justify.</li></ul>")

    parts.append("<h4>Photographs</h4>"
                 "<p>Every photograph is Creative Commons licensed (CC0, "
                 "CC&nbsp;BY or CC&nbsp;BY-SA), shown with its photographer's "
                 "credit. A photo without a credit fails our build — it is a "
                 "hard error, not a reminder.</p>")

    parts.append("<h4>The works the ecological data cites</h4>")
    grouped: dict = {}
    for rec in all_sources():
        if (rec.get("kind") or "") == "NOT_A_WORK":
            continue
        grouped.setdefault((rec.get("covers") or "other"), []).append(rec)
    label = {"lepidoptera": "Butterflies &amp; moths", "bees": "Bees",
             "birds": "Birds", "mammals": "Mammals",
             "insects_general": "Insects", "pollination": "Pollination",
             "other": "Other"}
    for covers in sorted(grouped):
        parts.append(f"<p><b>{label.get(covers, covers.title())}</b></p><ul>")
        for rec in grouped[covers]:
            parts.append(f"<li>{format_citation(rec['key'])}</li>")
        parts.append("</ul>")

    parts.append(f"<p><i>{disclaimer()}</i></p>")

    placeholders = [r for r in all_sources()
                    if (r.get("kind") or "") == "NOT_A_WORK"]
    if placeholders:
        parts.append(
            "<h4>What we cannot yet attribute</h4>"
            "<p>A small number of relationships were seeded without naming a "
            "specific work. Rather than quietly attach them to a nearby "
            "citation, they are held separately and shown as unattributed "
            "wherever they appear. Re-sourcing them is open work.</p>")

    parts.append(
        "<h4>What this does not claim</h4>"
        "<p>Nothing here has been verified against a herbarium specimen or a "
        "field survey of your site, and no plant list is a substitute for "
        "local advice — especially for anything you intend to eat, or plant "
        "near livestock or children. Toxicity ratings carry their own sources "
        "and should be checked against them.</p>"
        "<p>The full written position, including the copyright reasoning "
        "behind reading facts out of a flora, is in "
        "<code>docs/DATA_SOURCES.md</code>, with coverage and gap numbers in "
        "<code>docs/DATA_AUDIT.md</code>.</p>")
    return "".join(parts)


def show_data_sources(parent=None):
    """Open the data-provenance dialog."""
    dlg = QDialog(parent)
    dlg.setWindowTitle(f"Where {APP_NAME}'s data comes from")
    dlg.resize(680, 620)

    body = QLabel(_body_html())
    body.setWordWrap(True)
    body.setTextFormat(Qt.TextFormat.RichText)
    body.setTextInteractionFlags(
        Qt.TextInteractionFlag.TextBrowserInteraction)
    body.setOpenExternalLinks(True)
    body.setAlignment(Qt.AlignmentFlag.AlignTop)
    body.setContentsMargins(4, 4, 12, 4)

    holder = QWidget()
    inner = QVBoxLayout(holder)
    inner.setContentsMargins(0, 0, 0, 0)
    inner.addWidget(body)
    inner.addStretch(1)

    scroll = QScrollArea()
    scroll.setWidgetResizable(True)
    scroll.setWidget(holder)

    buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
    buttons.rejected.connect(dlg.reject)
    buttons.accepted.connect(dlg.accept)

    col = QVBoxLayout(dlg)
    col.addWidget(scroll)
    col.addWidget(buttons)
    dlg.exec()
