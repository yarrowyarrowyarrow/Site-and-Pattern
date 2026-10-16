"""
region_climate.py — the climate a design is planned with, from the pin's
region pack (V3.25, ED-6; docs/homeowner/08-edmonton-edition.md §4).

Design principle P9 — see docs/DESIGN_PHILOSOPHY.md.

Until V3.25 the climate a page fell back on was typed into each page: the
Water page's "Edmonton normal" rainfall (a hand-rounded copy of the normals),
the sun path's "Last Frost (~May 7)" and "First Frost (~Sep 23)", the planting
calendar's "~May 20". Three frost dates in one app, and every pin got
Edmonton's rain, Toronto's included (R4, R32). The pack holds one set,
Environment and Climate Change Canada's normals for its station, and this
module is how a page asks for it:

* a pin in a pack, or no pin: that pack's normals;
* a pin in Alberta or Saskatchewan outside every pack: the nearest pack's,
  as §4.5 tells that person ("the nurseries and planting dates are
  Edmonton's");
* a pin outside both provinces: nothing. A page says it has no figure rather
  than borrowing one from 2,700 km away.

A site's own fetched figures always come first; these are what a page shows
before, or instead of, them. Qt-free.
"""

from __future__ import annotations

import datetime as _dt
from typing import Mapping, Optional

_MONTHS = ("Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep",
           "Oct", "Nov", "Dec")


def pack_for(site_config: Optional[Mapping] = None):
    """The pack whose climate a design uses, or ``None`` for a pin outside
    Alberta and Saskatchewan."""
    from src import region                                   # noqa: PLC0415
    sc = site_config or {}
    cov = region.coverage(sc.get("latitude"), sc.get("longitude"))
    if cov.kind == region.OUTSIDE:
        return None
    if cov.kind == region.REGION and cov.region is not None:
        return cov.region
    if cov.kind == region.PROVINCE:
        return cov.nearest
    return region.default()


def normal_label(pack) -> str:
    """"Edmonton City Centre A normal, 1981–2010": where the figure is from."""
    c = pack.climate
    return f"{c['station']} normal, {c['period']}"


def rainfall(site_config: Optional[Mapping] = None) -> tuple:
    """``(12 monthly mm, label)`` from the pack, or ``((), reason)`` for a pin
    outside every province a pack covers."""
    pack = pack_for(site_config)
    if pack is None:
        return (), "no rainfall known for this pin"
    return (tuple(float(m) for m in pack.climate["monthly_precip_mm"]),
            normal_label(pack))


def _month_day(text: str) -> tuple:
    month, day = (int(x) for x in str(text).split("-"))
    return month, day


def frost_dates(site_config: Optional[Mapping] = None) -> Optional[dict]:
    """``{"last": (5, 15), "first": (9, 16), "words": "May 15 → Sep 16",
    "label": …}`` from the pack, or ``None`` outside the provinces."""
    pack = pack_for(site_config)
    if pack is None:
        return None
    last = _month_day(pack.climate["last_spring_frost"])
    first = _month_day(pack.climate["first_fall_frost"])
    return {"last": last, "first": first,
            "words": f"{date_words(last)} → {date_words(first)}",
            "free_days": (_dt.date(2025, *first) - _dt.date(2025, *last)).days,
            "label": normal_label(pack)}


def date_words(month_day: tuple) -> str:
    """``(5, 15)`` -> "May 15"."""
    month, day = month_day
    return f"{_MONTHS[month - 1]} {day}"
