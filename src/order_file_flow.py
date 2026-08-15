"""
order_file_flow.py — exporting the order file (F92, V2.57).

The Qt glue for :mod:`src.order_file`, which is Qt-free and does the work. Same
core-plus-``_flow`` split as ``wind.py``/``wind_flow.py`` — and here it also
answers the architecture guard's actual instruction rather than just its number:
*"New behaviour should go in a controller/flow module, not as a fat method"* on
MainWindow.
"""

from __future__ import annotations


def on_export_order_file(main) -> None:
    """Ask where to put it, build the lines, write the CSV."""
    from PyQt6.QtWidgets import QFileDialog, QMessageBox

    from src import order_file

    placed = list(getattr(main, "_placed_plants", []) or [])
    if not placed:
        QMessageBox.information(
            main, "Nothing to order",
            "Place some plants first — an order file of nothing is not much "
            "use to a nursery.")
        return

    path, _ = QFileDialog.getSaveFileName(
        main, "Export order file", "plant-order.csv",
        "CSV for spreadsheets and nurseries (*.csv);;All Files (*)")
    if not path:
        return
    if not path.lower().endswith(".csv"):
        path += ".csv"

    try:
        lines = order_file.build_order_lines(placed, main._project)
        order_file.write_order_file(path, lines, main._project)
    except Exception as exc:                               # noqa: BLE001
        QMessageBox.critical(main, "Order File Failed", str(exc))
        return

    qty, low, high = order_file.order_totals(lines)
    groups = len(order_file.group_by_channel(lines))
    # Say what is in the file, not just that a file happened: the counts are
    # what tell a designer whether it is the design they meant to price.
    main.statusBar().showMessage(
        f"Order file exported: {len(lines)} species, {qty} plants, "
        f"{groups} sourcing channels, ${low:,.0f}–${high:,.0f} — {path}",
        8000)
