"""
side_panel_layout.py — the side panel's tabs, by the question a person brings
(F94, V3.07).

The V3.05 surface audit counted 26 pages under six tabs and found seven ideas
each split across two to five of them. The owner answered it page by page
(docs/SURFACE_AUDIT.md, the Decision column), and this is the shape that
follows, the first half of it:

    Site       Site Info · Slope · Sun & Shade · Wind · Features · Field Notes
    Placement  Plants · Communities · Structures
    Design     Report card · Planted · Habitat · This Month · Bees
    Planning   Effort · Wildlife · Harvest · Water · Notes · Timeline
    Learn      Field Study · Lessons · Present

Sun & Shade and Wind describe the site, not the design. *Placement* is the
owner's name, for the three kinds of thing that go in. *Design* begins a release
early because On This Design had to leave the Plants tab: its Stats page is the
**Report card**, and Species and Communities are **Planted**. V3.08 merges
Planning into Design and moves Present to a Share place.

Every panel still builds its own pages and owns what they do; this module only
moves pages between tab widgets after they are built, so nothing about how a
page works moves with it. **Address a page by its widget**
(``keyboard_help.show_panel``), never by its index in a strip: an index is
exactly what this module changes, and three lookups that used one would have
broken.
"""

from __future__ import annotations

from PyQt6.QtWidgets import QStackedWidget, QTabWidget, QWidget

#: The top-level tabs, in order.
TOP_TABS = ("Site", "Placement", "Design", "Planning", "Learn")


def tab_owner(page: QWidget):
    """The tab widget ``page`` is a page of, or ``None``."""
    stack = page.parentWidget()
    tabs = stack.parentWidget() if stack is not None else None
    if isinstance(stack, QStackedWidget) and isinstance(tabs, QTabWidget):
        return tabs
    return None


def move_page(page: QWidget, to: QTabWidget, index: int,
              label: str = "") -> None:
    """Take ``page`` out of the tab widget it is in and put it in ``to`` at
    ``index``, under its own label unless ``label`` is given."""
    source = tab_owner(page)
    if source is not None:
        i = source.indexOf(page)
        label = label or source.tabText(i)
        source.removeTab(i)
    to.insertTab(index, page, label)


def placement_tab(main) -> QWidget:
    """Placement: Plants, Communities, Structures."""
    from src.fill_tab_widget import FillTabWidget
    from src.ui_style import inner_tab_stylesheet
    inner = FillTabWidget()
    inner.setDocumentMode(True)
    inner.tabBar().setUsesScrollButtons(False)
    inner.tabBar().setExpanding(True)
    inner.setStyleSheet(inner_tab_stylesheet())
    # "Plants" here is the owner's word: until V3.07 this page was "Browse",
    # because Plants was also the tab it sat under.
    inner.addTab(main.plant_panel, "Plants")
    inner.addTab(main.polyculture_panel, "Communities")
    inner.addTab(main.structure_panel, "Structures")
    main._placement_tabs = inner
    return inner


def arrange(main) -> list:
    """Move the pages into place and return ``[(widget, label)]`` for the top
    level, in :data:`TOP_TABS` order. Called once, after every panel is
    built."""
    site, design = main.site_panel, main.analysis_panel

    # Site: the two pages that describe the site, after Slope.
    at = site._tabs.indexOf(site.slope_page) + 1
    move_page(design._sun_page, site._tabs, at)
    move_page(design._wind_page, site._tabs, at + 1)
    site._tabs.setCurrentWidget(site.info_page)

    # Design: the report card first, then what is planted.
    otd = main.on_this_design
    move_page(otd._stats_page, design._tabs, 0, "Report card")
    design._tabs.insertTab(1, otd, "Planted")
    design._tabs.setCurrentIndex(0)

    return [(site, "Site"), (placement_tab(main), "Placement"),
            (design, "Design"), (main.planning_panel, "Planning"),
            (main.learn_panel, "Learn")]
