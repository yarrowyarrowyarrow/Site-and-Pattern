"""
yard_overview_flow.py — the Overview page in the window, and what its buttons
do (OV-2, MD-4; V3.27; docs/homeowner/06-yard-overview.md §8, part 02).

Design principle P6 — see docs/DESIGN_PHILOSOPHY.md.

:func:`install` puts the page first in the Design tab and makes it current; it
refills when it is on screen and after edits (``src/live_refresh.py``, poked by
``follow_design.request_sync``, which every edit, open and undo reaches). In
the simple app it replaces the Report card, which the Advanced tools switch
holds (``advanced_tools.ADVANCED_PAGES``).

:func:`run_action` turns a card's target into what its words say: a filter set
on the plant list, Draw › Shape opened on the right type, the fill and swap
dialogs (``src/yard_overview_dialogs.py``), Export PDF, Plan My Yard. A *More
detail* link (MD-4) turns the Advanced tools on and shows the page that
explains the item, and says once a session how to turn them off.
"""

from __future__ import annotations

ADVANCED_ON = ("Advanced tools are on. View → Advanced tools turns them off.")

_said_advanced = False


def install(main) -> None:
    """Build the page, put it first in Design and keep it filled."""
    from src.live_refresh import LiveRefresh
    from src.yard_overview_page import OverviewPage
    design = main.analysis_panel
    page = OverviewPage()
    design._tabs.insertTab(0, page, "Overview")
    design._tabs.setCurrentIndex(0)
    page.action_requested.connect(lambda target: run_action(main, target))
    main.overview_page = page
    main._overview_live = LiveRefresh(design, design._tabs,
                                      {page: lambda: fill(main)})


def fill(main) -> None:
    """Refill the page from the open design."""
    from src import yard_overview_items as yi
    page = getattr(main, "overview_page", None)
    project = getattr(main, "_project", None)
    if page is None or project is None:
        return
    try:
        items = yi.overview(project)
    except Exception:                                      # noqa: BLE001
        import logging
        logging.getLogger(__name__).exception("overview")
        items = []
    page.show_items(yi.heading(project), items)


def poke(main) -> None:
    live = getattr(main, "_overview_live", None)
    if live is not None:
        live.poke()


def run_action(main, target: str) -> None:
    """Do what a card's button or link says."""
    kind, _, arg = (target or "").partition(":")
    handler = _HANDLERS.get(kind)
    if handler is not None:
        handler(main, arg)


def _advanced(main, which: str) -> None:
    """MD-4: the page that explains the item, with the switch on."""
    global _said_advanced
    from src import advanced_tools, advanced_tools_flow
    from src.keyboard_help import show_panel
    if not advanced_tools.is_on():
        advanced_tools_flow.set_and_apply(main, True)
        act = getattr(main, "_act_advanced", None)
        if act is not None:
            act.setChecked(True)
        if not _said_advanced:
            _said_advanced = True
            main.statusBar().showMessage(ADVANCED_ON, 10000)
    design = main.analysis_panel
    page = {"food": getattr(design, "_food", None),
            "over_time": getattr(design, "_over_time_page", None)}.get(which)
    if page is not None:
        show_panel(page)


def _page(main, which: str) -> None:
    from src.keyboard_help import show_panel
    if which == "planted":
        show_panel(main.on_this_design)


def _plants(main, arg: str) -> None:
    """Placement › Plants with the filters the button names."""
    from src.keyboard_help import show_panel
    panel = main.plant_panel
    show_panel(panel)
    picker = panel.picker
    if arg == "berry_shrub":
        picker.set_facet("type", ["shrub"])
        picker.set_facet("use", ["bird_food"])
    elif arg.startswith("blooms_in="):
        picker.set_facet("bloom_months", [arg.split("=", 1)[1]])


def _shape(main, kind: str) -> None:
    """Draw › Shape, opened with ``kind`` chosen: a popup, so nothing waits."""
    from PyQt6.QtCore import QPoint
    bar = main.toolbar
    bar.shape_tool.set_type(kind)
    button = bar._shape_btn
    button.menu().popup(button.mapToGlobal(QPoint(0, button.height())))


def _export(main, _arg: str) -> None:
    main._on_export_pdf()


def _site(main, _arg: str) -> None:
    main.site_panel.focus_address_search()


def _draw(main, _arg: str) -> None:
    main._enter_boundary_mode()


def _plan(main, _arg: str) -> None:
    main._on_generate_design()


def _swap(main, arg: str) -> None:
    from src import yard_overview_dialogs
    yard_overview_dialogs.swap(main, int(arg))


def _fill(main, _arg: str) -> None:
    from src import yard_overview_dialogs
    yard_overview_dialogs.fill_gaps(main)


_HANDLERS = {"advanced": _advanced, "page": _page, "plants": _plants,
             "shape": _shape, "export": _export, "site": _site,
             "draw": _draw, "plan": _plan, "swap": _swap,
             "fill_gaps": _fill}
