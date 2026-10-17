"""
advanced_tools.py — simple by default, the advanced tools one switch away
(V3.21, MD-1 and RM-4; docs/homeowner/02-two-ways-to-use-it.md).

Design principle P13 — see docs/DESIGN_PHILOSOPHY.md.

The owner: *"the advanced features not muddying the waters of what a novice
sees so possibly 2 ways to interact with the app."* Everyone starts with the
homeowner's path; View → Advanced tools shows everything else. The switch is
remembered, and it **hides tools, never work**: what a design already holds
(contours, measurements, notes, shapes) still draws, prints and undoes with it
off, and turning it on or off changes nothing in the file or the undo stack.

This is not the mode split V2.42 argued against (``app_mode.py`` quotes it):
nobody is asked to choose, and nothing is a second app.

Qt-free apart from QSettings, which the switch is stored in. The **registry**
below is the one table of what the switch hides: ``advanced_tools_flow`` reads
it to hide and show, and the tests read it to check both. Each entry is an
attribute path from the main window (``"site_panel.slope_page"``) or, for a
menu action, its object name. Add a surface here, never in the flow.
"""

from __future__ import annotations

from PyQt6.QtCore import QSettings

#: The QSettings key; off unless a person turned it on (decision M1).
SETTINGS_KEY = "ui/advanced_tools"

#: The switch's name on the View menu (decision M3).
NAME = "Advanced tools"

# ── The registry (part 03 §5, as the owner amended it) ──────────────────────

#: Pages in a tab strip, hidden with their tab. An emptied strip goes too.
ADVANCED_PAGES: tuple = (
    "site_panel.slope_page",          # §5 rank 2: contours, slope, water flow
    "analysis_panel._wind_page",      # rank 3: wind, shelter, snow catch
    "on_this_design._stats_page",     # the Report card: Overview instead
    "analysis_panel._habitat_page",   # rank 1: the Design tab in depth
    "analysis_panel._food",
    "analysis_panel._over_time_page",
    "planning_panel._water_page",
    "learn_panel._present_page",      # rank 7: Share's narrated tour
    "learn_panel",                    # rank 8: the Learn tab (S2, G2)
)

#: Menu actions, by object name (set where each is made).
ADVANCED_ACTIONS: tuple = (
    "view_split",                     # rank 6: the View menu's windows
    "view_3d_preview",
    "view_wild_landscape",
    "view_growth_snapshots",
    "view_scale_units",               # rank 9: map settings and units
    "view_map_settings",
)

#: The Draw and View rows' items: actions, or a widget the row holds.
ADVANCED_TOOLBAR_ITEMS: tuple = (
    "toolbar._act_measure",           # rank 9: Measure, notes on the map
    "toolbar._act_annotate",
    "toolbar._act_boundary_layer",    # the View row's layer switches
    "toolbar._act_measurements_layer",
    "toolbar._grid_btn",
    "toolbar._act_canopy",
    "toolbar._act_structures_layer",
)

#: Controls inside a page that stays: each a container made for the purpose,
#: so nothing else that shows or hides the controls inside it is overruled.
ADVANCED_CONTROLS: tuple = (
    "analysis_panel._sun_arc_box",    # Sun & Shade's arc and shadow arrows
    "site_panel._features_more",      # Features beyond Scan this area (rank 4)
    "site_panel._existing_box",
    "site_panel._sat_align_box",
    "site_panel._browse_box",         # Site Info's communities link and the
    "site_panel._soil_dl_box",        # soil download (V3.30, WD-2)
    "plant_panel._mix_box",           # rank 5: Placement's builders
    "polyculture_panel._builder_rows",
    "polyculture_panel._mix_community_box",
    "share_panel.pictures",           # rank 7: Share's presentation pictures
)

#: Objects told the switch's state, for what is not a widget to hide: the
#: placing patterns beyond Single and Fill (rank 5), the plant page's Add to
#: mix, the community page's pattern card (RM-8). Each has
#: ``set_advanced_tools(on)``.
ADVANCED_HOOKS: tuple = (
    "plant_panel._placement",
    "plant_panel.picker",             # the rows' band chip (PR-3)
    "polyculture_panel.placement_widget",
    "species_flyout.page",            # the plant page's Add to mix
    "species_flyout.community",       # the community page's pattern card
    "toolbar.shape_tool",             # Draw › Shape's lines and Custom
    "site_panel",                     # Site Info opens on its details (WD-2)
)


def is_on(settings: QSettings = None) -> bool:
    """Whether the advanced tools are shown. Off on a first run."""
    s = settings if settings is not None else QSettings()
    return bool(s.value(SETTINGS_KEY, False, type=bool))


def set_on(on: bool, settings: QSettings = None) -> None:
    """Remember the switch."""
    s = settings if settings is not None else QSettings()
    s.setValue(SETTINGS_KEY, bool(on))


def every_entry() -> tuple:
    """Every name in the registry, for the tests and the flow's checks."""
    return (ADVANCED_PAGES + ADVANCED_ACTIONS + ADVANCED_TOOLBAR_ITEMS
            + ADVANCED_CONTROLS + ADVANCED_HOOKS)


# ── A design that uses them says so (MD-3) ──────────────────────────────────

#: ``(words, test(feature properties))``, in the order the bar names them.
#: A site photo is not here: it sits on Site › Notes, which part 03 §6 keeps
#: in the simple app. Wind overlays are not saved in a design.
_ADVANCED_IN_DESIGN = (
    ("contours or a slope map", lambda p: p.get("element_type") in (
        "contour_line", "auto_contour", "slope_overlay", "water_overlay")),
    ("measurements", lambda p: p.get("element_type") == "measurement"),
    ("notes on the map", lambda p: p.get("element_type") == "annotation"),
    ("hedges, fences or windbreaks",
     lambda p: p.get("element_type") == "hedgerow"),
    ("custom shapes", lambda p: p.get("element_type") == "custom_shape"
     and p.get("shape_type") == "Custom"),
)

#: What the bar says (decision W1's plain words).
BAR_TEXT = "This design uses advanced tools."


def uses_advanced(project) -> list:
    """What in ``project`` was made with the advanced tools, in words, each
    once: ``["contours or a slope map", "measurements"]``. Empty for a design
    the simple app made."""
    found = set()
    for f in (project or {}).get("features", []) or []:
        props = f.get("properties") or {}
        for words, test in _ADVANCED_IN_DESIGN:
            if test(props):
                found.add(words)
    return [words for words, _t in _ADVANCED_IN_DESIGN if words in found]
