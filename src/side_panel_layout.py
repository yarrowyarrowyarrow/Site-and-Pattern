"""
side_panel_layout.py — the side panel's tabs, by the question a person brings
(F94, V3.07; completed V3.08).

The V3.05 surface audit counted 26 pages under six tabs and found seven ideas
each split across two to five of them. The owner answered it page by page
(docs/SURFACE_AUDIT.md, the Decision column), and this is the shape that
follows:

    Site       Site Info · Slope · Sun & Shade · Wind · Features · Notes
    Placement  Plants · Communities · Structures
    Design     Report card · Planted · Habitat · Food · Over time · Water
    Share      Present · Export
    Learn      Field Study · Lessons

Sun & Shade and Wind describe the site, not the design. *Placement* is the
owner's name, for the three kinds of thing that go in. *Design* is what the
design is and does: On This Design's Stats as the **Report card**, its Species
and Communities as **Planted**, **Food** (``src/food_page.py``, the Bees,
Wildlife and Harvest pages as one), **Over time** (This Month, the Timeline and
Effort, in that order) and Water. Planning's other page, the design journal,
went to Site's **Notes**, under the site walk's questions. **Share** holds what
leaves the app: Learn's Present, and the exports (``src/share_panel.py``) with
Where to buy from Site Info beside them.

Every panel still builds its own pages and owns what they do; this module only
moves pages between tab widgets after they are built, so nothing about how a
page works moves with it. **Address a page by its widget**
(``keyboard_help.show_panel``), never by its index in a strip: an index is
exactly what this module changes, and three lookups that used one would have
broken.
"""

from __future__ import annotations

from PyQt6.QtWidgets import (
    QFrame, QLabel, QScrollArea, QStackedWidget, QTabWidget, QVBoxLayout,
    QWidget,
)

#: The top-level tabs, in order.
TOP_TABS = ("Site", "Placement", "Design", "Share", "Learn")

#: Over time's sections, in reading order: the near question first.
OVER_TIME = ("This month", "Year by year", "Hours of work")

_SECTION_STYLE = ("color: #a5d6a7; font-size: 13px; font-weight: bold; "
                  "padding: 10px 6px 0 6px;")


def tab_owner(page: QWidget):
    """The tab widget ``page`` is a page of, or ``None``."""
    stack = page.parentWidget()
    tabs = stack.parentWidget() if stack is not None else None
    if isinstance(stack, QStackedWidget) and isinstance(tabs, QTabWidget):
        return tabs
    return None


def take_page(page: QWidget) -> str:
    """Take ``page`` out of the tab widget it is in; return its label. The
    strip hides the page as it lets it go: one put in a layout rather than in
    another strip must be shown again, or its heading sits over nothing (the
    first V3.08 build did that to Over time and Notes)."""
    source = tab_owner(page)
    if source is None:
        return ""
    i = source.indexOf(page)
    label = source.tabText(i)
    source.removeTab(i)
    return label


def _discard(widget: QWidget) -> None:
    """Out of its tab widget and out of the window now, deleted later: a
    removed page stays its old stack's child until it is deleted, and the
    window's walks (``accessible_names``, the guards) would still find it."""
    take_page(widget)
    widget.setParent(None)
    widget.deleteLater()


def move_page(page: QWidget, to: QTabWidget, index: int,
              label: str = "") -> None:
    """Take ``page`` out of the tab widget it is in and put it in ``to`` at
    ``index``, under its own label unless ``label`` is given."""
    taken = take_page(page)
    to.insertTab(index, page, label or taken)


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


def over_time_page(main) -> QScrollArea:
    """Design › Over time: what the design is doing this month, how it grows
    year by year, and the work each year takes, as one page in that order.
    The three were Design › This Month and Planning's Timeline and Effort; the
    owner merged them ("Through the years")."""
    design, planning = main.analysis_panel, main.planning_panel
    month = design._phenology_page.takeWidget()     # the scroll page goes
    _discard(design._phenology_page)
    design._phenology_page = None
    take_page(planning._timeline_page)
    take_page(planning._maint_page)

    page = QScrollArea()
    page.setWidgetResizable(True)
    page.setFrameShape(QFrame.Shape.NoFrame)
    page.setAccessibleName("Over time")
    body = QWidget()
    page.setWidget(body)
    lay = QVBoxLayout(body)
    lay.setContentsMargins(0, 0, 0, 0)
    lay.setSpacing(0)
    page.sections = {}
    for heading, part in zip(OVER_TIME, (month, planning._timeline_page,
                                         planning._maint_page)):
        head = QLabel(heading)
        head.setStyleSheet(_SECTION_STYLE)
        head.setAccessibleName(heading)
        lay.addWidget(head)
        lay.addWidget(part)
        part.show()             # a strip hides the page it gives up
        page.sections[heading] = part
    lay.addStretch()
    return page


def arrange(main) -> list:
    """Move the pages into place and return ``[(widget, label)]`` for the top
    level, in :data:`TOP_TABS` order. Called once, after every panel is
    built."""
    from src.share_panel import SharePanel
    site, design = main.site_panel, main.analysis_panel
    planning, learn = main.planning_panel, main.learn_panel

    # Site: the two pages that describe the site, after Slope; the design
    # journal and the map's notes under the site walk, on Notes.
    at = site._tabs.indexOf(site.slope_page) + 1
    move_page(design._sun_page, site._tabs, at)
    move_page(design._wind_page, site._tabs, at + 1)
    take_page(planning._notes_page)
    site._journal_slot.layout().addWidget(planning._notes_page)
    planning._notes_page.show()
    site._tabs.setCurrentWidget(site.info_page)

    # Design: the report card first, then what is planted, then what the
    # design does: Habitat and Food are its own, Over time and Water came
    # from Planning.
    otd = main.on_this_design
    move_page(otd._stats_page, design._tabs, 0, "Report card")
    design._tabs.insertTab(1, otd, "Planted")
    over_time = over_time_page(main)
    design._tabs.addTab(over_time, "Over time")
    move_page(planning._water_page, design._tabs, design._tabs.count())
    design._over_time_page = over_time
    design._tabs.setCurrentIndex(0)
    # Effort and Water fill themselves when on screen (src/live_refresh.py);
    # they are on screen in Design now.
    planning._live.move_to(design, design._tabs, {
        over_time: planning._calc_maintenance,
        planning._water_page: planning._calc_water,
    })
    # Every page of Planning has gone: the panel stays, unseen, as the owner
    # of their state and signals. Its empty strip goes, or it lingers in the
    # window as a container with nothing in it and no name.
    _discard(planning._tabs)
    planning._tabs = None
    planning.hide()

    # Share: the narrated tour, then the exports and where to buy.
    share = SharePanel(main)
    move_page(learn._present_page, share._tabs, 0)
    share.add_to_export(site._nursery_box)
    share._tabs.setCurrentIndex(0)
    main.share_panel = share

    return [(site, "Site"), (placement_tab(main), "Placement"),
            (design, "Design"), (share, "Share"), (learn, "Learn")]
