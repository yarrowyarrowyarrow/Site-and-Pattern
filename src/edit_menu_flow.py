"""
edit_menu_flow.py — the Edit menu: Undo, Redo, Delete, Select all (V3.19, QF-15).

The menu bar was File, View and Help from V2.25, when an Edit menu that only
repeated the toolbar's Undo and Redo was dropped. The first review found a
stranger looking for Undo where every other program keeps it (R33), so it is
back, with the two things a selection on the map can have done to it.

Each item is its toolbar or map twin, never a second way of doing it:

  * **Undo** and **Redo** are the window's own actions (``_act_undo``,
    ``_act_redo``, built in ``MainWindow._build_menu``), the ones that carry
    the keys and that ``PersistenceController._sync_undo_actions`` greys out
    with the toolbar's buttons. A second action bound to Ctrl+Z would make Qt
    call the pair ambiguous and fire neither (V3.02).
  * **Delete** runs what the Delete key runs on the map
    (``MapWidget.delete_selected``, one ``onSelectionDeleted``, one undo step)
    and is offered while something is selected, which the page reports
    (``onSelectionCount``; a redraw clears the selection, 05-features.js).
    It binds no key: Delete belongs to the map while the map has focus
    (V3.02), and pressed in a side panel's list or box it must not remove
    what is selected on the map.
  * **Select all** (Ctrl+A) selects what the selection box would catch drawn
    round the whole map, less what a View switch hides (``selectAll``,
    html/map/04-tools.js). In a text box Ctrl+A still selects the text: a
    focused text box takes its own editing keys first.

Wired from ``MainWindow._build_menu`` (MainWindow is at its method ceiling).
"""

from __future__ import annotations

from PyQt6.QtGui import QAction, QKeySequence


def install(main) -> None:
    """Add the Edit menu to ``main``'s menu bar, after File. Call it between
    the File and View menus in ``_build_menu``, so the order is File, Edit,
    View, Help."""
    menu = main.menuBar().addMenu("&Edit")
    menu.addAction(main._act_undo)
    menu.addAction(main._act_redo)
    menu.addSeparator()

    delete = QAction("&Delete", main)
    delete.setStatusTip("Remove what is selected on the map. With the map in "
                        "use, the Delete key does the same.")
    delete.setEnabled(False)
    delete.triggered.connect(lambda: main.map_widget.delete_selected())
    menu.addAction(delete)

    select_all = QAction("Select &All", main)
    select_all.setShortcut(QKeySequence.StandardKey.SelectAll)
    select_all.setStatusTip("Select everything shown on the map, ready to "
                            "move or delete.")
    select_all.triggered.connect(lambda: main.map_widget.select_all())
    menu.addAction(select_all)

    # The page says how many things are selected whenever that changes; a
    # page loading again (a restarted renderer) starts with none.
    main.map_widget.bridge.selection_count_changed.connect(
        lambda n: delete.setEnabled(n > 0))
    main.map_widget.loadStarted.connect(lambda: delete.setEnabled(False))
    main._edit_menu = menu
    main._act_delete = delete
    main._act_select_all = select_all
