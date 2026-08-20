"""
src/glossary.py — what the Site Info numbers actually mean (F122, V2.55).

Design principle P5 (perception is constructed, not received) — see
docs/DESIGN_PHILOSOPHY.md.

    Author's report: *"Site Info is overwhelming to most beginner users and even
    long time landscape designers."*

Twenty metrics were on that panel and **fifteen of them explained themselves
nowhere** — no tooltip, no caption note, nothing. Meanwhile
:func:`src.climate.zone_description` had been returning exactly the right
sentence about a hardiness zone since V1.x and was **called by nothing**, and
the best plain-English account of GDD₅ in the repository was a developer comment
in ``climate.py`` that no user could ever reach. The information existed; it was
just pointed at the wrong audience.

**Qt-free on purpose.** The companion (F85) is meant to read these out, the
same way the docent reads its beats. A glossary locked inside a widget can be
shown in exactly one place; this one can be shown anywhere, printed, or spoken.

**Two rules the entries follow**, both learned from the five tooltips that
already existed and were good:

* Say what it *is*, then say what it *decides*. "Growing-degree days" is a
  definition; "the single best predictor of whether a plant has enough heat to
  flower" is why anyone should look at it.
* **Say when a number is weaker than it looks** (P9). A regional soil figure is
  a provincial average and the entry says so, because a number that is presented
  identically to a measurement will be read as one.

**Scope, deliberately (P12).** This glossary is about *site physics* — cold,
warmth, water, wind, ground. It carries no plant-use content of any kind and
must not grow any. The ethnobotanical-vocabulary scans that guard the public
surfaces live in the plant-directory and site-facet tests; a glossary that ever
gains plant-use terms has to be added to them first.
"""

from __future__ import annotations

from typing import NamedTuple, Optional


class Entry(NamedTuple):
    """One metric: its key, the term as a reader would say it, the explanation."""
    key: str
    term: str
    text: str


# Metric keys. Named constants rather than bare strings so a typo at a call
# site is an AttributeError here rather than a silently missing tooltip there —
# which is the exact failure this module exists to end.
ZONE = "zone"
HARDINESS_SOURCE = "hardiness_source"
GDD = "gdd"
FROST_WINDOW = "frost_window"
ECOREGION = "ecoregion"
ELEVATION = "elevation"
ASPECT = "aspect"
PREVAILING_WIND = "prevailing_wind"
RAIN_ANNUAL = "rain_annual"
RAIN_MONTHLY = "rain_monthly"
RAIN_GROWING = "rain_growing"
RAIN_SNOW = "rain_snow"
RAIN_SOURCE = "rain_source"
SNOW_COVER = "snow_cover"
THAW_STRESS = "thaw_stress"
SOIL_PH = "soil_ph"
SOIL_TEXTURE = "soil_texture"
SOIL_MIX = "soil_mix"
SOIL_DEPTH = "soil_depth"
SOIL_SOURCE = "soil_source"


_ENTRIES = (
    Entry(
        ZONE, "Hardiness zone",
        "How cold this site gets in an average winter, on Canada's 0–9 scale. "
        "It is the first filter on what can survive here at all: a plant rated "
        "for zone 4 will usually die in a zone 3 winter, however well it is "
        "watered and fed."),
    Entry(
        HARDINESS_SOURCE, "Where the zone came from",
        "Which dataset this zone was read from. It matters because a zone taken "
        "from a weather station a few kilometres away is worth a great deal "
        "more than one interpolated across half a province."),
    Entry(
        GDD, "Growing-degree days",
        "Cumulative summer warmth across the growing season, counted in degrees "
        "above 5 °C. The single best predictor of whether a plant has enough "
        "heat to flower, set fruit and reach maturity here.\n\n"
        "Worth knowing: this is not the same information as the hardiness zone. "
        "Lethbridge accumulates around 1700 and Fort McMurray around 1300, and "
        "both are nominally zone 3 — same winter, very different summer."),
    Entry(
        FROST_WINDOW, "Frost window",
        "The average last frost of spring and first frost of autumn, computed "
        "from recent daily temperatures. The gap between them is your "
        "frost-free season, which is what most planting calendars are really "
        "counting."),
    Entry(
        ECOREGION, "Ecoregion",
        "The natural region this property sits in, detected from its latitude "
        "and longitude. The plant filter pre-populates from it, so the species "
        "suggested to you are the ones documented growing wild in your area. "
        "You can always override the filter by hand."),
    Entry(
        ELEVATION, "Elevation",
        "Height above sea level at the property pin. It feeds the slope and "
        "shade calculations, and it is a climate fact in its own right — air "
        "cools roughly 0.6 °C for every 100 m you go up."),
    Entry(
        ASPECT, "Aspect",
        "Which way the ground faces. South-facing slopes run warmer and drier "
        "and thaw first; north-facing ones stay cooler and hold their snow "
        "longer. On a small property this can be a bigger difference than a "
        "whole hardiness zone."),
    Entry(
        PREVAILING_WIND, "Prevailing wind",
        "The direction the wind most often comes from across the year, from "
        "hourly ERA5 history and cached for offline use. Wind dries plants out "
        "and strips winter snow cover, so it decides where a windbreak earns "
        "its place. The full seasonal rose is in Analysis → Wind."),
    Entry(
        RAIN_ANNUAL, "Annual mean rainfall",
        "Total precipitation in an average year, as liquid water. Useful for "
        "comparing against a plant's water needs — but the annual total hides "
        "*when* the water arrives, which is what the rows below are for."),
    Entry(
        RAIN_MONTHLY, "Monthly rainfall",
        "The same yearly total broken out month by month, so you can see "
        "whether the water comes while plants are actively growing or arrives "
        "in one spring pulse and then stops."),
    Entry(
        RAIN_GROWING, "Growing-season rain",
        "The share of the year's water that falls while roots can actually use "
        "it. This, rather than the annual total, is the number that decides "
        "whether a planting will need watering to establish."),
    Entry(
        RAIN_SNOW, "Snow, as melt water",
        "Winter precipitation expressed as the liquid water it becomes when it "
        "melts. It is shown separately because it waters differently: it "
        "arrives as one pulse at spring melt rather than spread through the "
        "season."),
    Entry(
        RAIN_SOURCE, "Where the rainfall came from",
        "Which dataset these climate normals were read from, and over what "
        "period they were averaged."),
    Entry(
        SNOW_COVER, "Snow cover",
        "How reliably snow lies here, and how deep. Snow is insulation, not "
        "just cold: under about 30 cm of it the ground stays near 0 °C however "
        "far the air temperature falls. It is why a plant rated a zone too "
        "tender often survives where snow lies dependably — and why it dies in "
        "the winter the snow fails."),
    Entry(
        THAW_STRESS, "Thaw stress",
        "How often winter here thaws and refreezes. Repeated freeze–thaw is "
        "harder on roots and crowns than steady cold is, which is why a mild "
        "winter can kill plants that a colder one would not have touched."),
    Entry(
        SOIL_PH, "Soil pH",
        "How acid or alkaline the soil is, measured in water. Most prairie "
        "soils are alkaline, around 7.5–8.5. pH decides which nutrients a plant "
        "can physically take up, so an acid-loving plant will starve in "
        "alkaline ground no matter how well fed it is."),
    Entry(
        SOIL_TEXTURE, "Texture class",
        "The soil's class — sand, silt, clay and the loams between them. "
        "Texture governs how fast water drains away and how well the soil holds "
        "on to nutrients, and it usually predicts what will grow better than "
        "fertility does."),
    Entry(
        SOIL_MIX, "Sand / silt / clay",
        "The measured percentages behind the texture class. Worth reading when "
        "the class sits near a boundary: a loam that is 45% sand behaves quite "
        "differently from one that is 20% sand, though both are called loam."),
    Entry(
        SOIL_DEPTH, "Reported depth",
        "The depth of soil this measurement describes. Figures are for the top "
        "few centimetres unless stated otherwise, and deeper roots may reach "
        "quite different material."),
    Entry(
        SOIL_SOURCE, "Where the soil came from",
        "Which dataset this soil reading came from — the downloaded soil pack, "
        "SoilGrids, or a regional approximation. The distinction is not "
        "cosmetic: a regional figure is an average over a large area, not a "
        "measurement of your yard, and should be treated as a starting guess "
        "until a soil test says otherwise."),
)

#: Every metric, keyed. The panel looks entries up by key.
GLOSSARY: dict[str, Entry] = {e.key: e for e in _ENTRIES}

#: The full key set — what ``tests/test_glossary.py`` checks the panel against,
#: so a Site Info row cannot be added without an explanation.
METRIC_KEYS = frozenset(GLOSSARY)


def term(key: str) -> str:
    """The metric's name as a reader would say it, or ``""`` if unknown."""
    entry = GLOSSARY.get(key)
    return entry.term if entry else ""


#: Characters per line in a tooltip. A tooltip is read in one glance, and a
#: 180-character single line makes the eye travel the whole screen and lose the
#: line it was on — the V2.58 report. Roughly 58 characters is a comfortable
#: measure, and it keeps the box narrow enough to sit beside what it describes.
WRAP_COLS = 58


def tooltip_html(key: str, *, zone: Optional[int] = None) -> str:
    """The explanation as a narrow, titled, readable tooltip.

    Rich text on purpose, for two reasons that are both bugs otherwise:

    * **Width.** Plain text with no newlines renders as one enormous line.
      Wrapping is done here rather than left to Qt because Qt's own tooltip
      wrapping only kicks in past a width that is already too wide to scan.
    * **Colour.** The value labels on the Site panel set ``color:`` in their
      stylesheet, and that cascades into the tooltip — which is why hovering a
      *value* produced pale green text on a pale background while hovering the
      *caption* was perfectly legible. Stating the colours explicitly here stops
      the cascade reaching the text.
    """
    import textwrap

    entry = GLOSSARY.get(key)
    if entry is None:
        return ""
    body = explain(key, zone=zone)
    paras = [p.strip() for p in body.split("\n\n") if p.strip()]
    wrapped = "<br><br>".join(
        "<br>".join(textwrap.wrap(p, WRAP_COLS)) for p in paras)
    return (
        f"<div style='color:#10200f;'>"
        f"<b style='color:#10200f;'>{entry.term}</b><br>{wrapped}</div>")


def explain(key: str, *, zone: Optional[int] = None) -> str:
    """The explanation for ``key``, or ``""`` for an unknown key.

    ``zone`` is the one piece of *measured* context the glossary takes. The
    hardiness entry is the only one whose useful second half depends on the
    value on screen, and :func:`src.climate.zone_description` has been returning
    exactly that sentence — with the temperature band and the nearest familiar
    city — since long before anything called it.

    Returning ``""`` rather than raising is deliberate: a missing tooltip is a
    gap, and a traceback while building a panel is an outage. The test suite is
    where an unknown key is supposed to be caught, not the user's screen.
    """
    entry = GLOSSARY.get(key)
    if entry is None:
        return ""
    if key == ZONE and zone is not None:
        from src.climate import zone_description
        return f"{entry.text}\n\n{zone_description(zone)}"
    return entry.text
