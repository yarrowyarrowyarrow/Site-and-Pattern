"""
site_summary.py — Site Info in four plain lines (WD-2, V3.30;
docs/homeowner/09-words.md §3.2, decision W5).

Design principle P9 — see docs/DESIGN_PHILOSOPHY.md.

    Where: 10423 81 Avenue NW, Edmonton, in the Edmonton region.
    Cold:  Plants hardy to zone 3b grow here. Frost-free from about May 12
           to September 20.
    Rain:  About 470 mm a year, most of it in June and July.
    Soil:  Loam, slightly alkaline (pH 7.4), as mapped near your yard.

Each line says where its figure came from when it is not this yard's own
(*typical for the Edmonton region*), and **no line is shown for a value the
app does not have** (P9): a blank is the app knowing it does not know. The
growing-degree days, the snow, the soil percentages and every source wait
under *Details*, which is the page as it was.

Qt-free: the panel hands over what its fetches returned.
"""

from __future__ import annotations

from typing import Optional

MONTHS = ("January", "February", "March", "April", "May", "June", "July",
          "August", "September", "October", "November", "December")

#: ``(key, label)`` in the order the page shows them.
LINES = (("where", "Where"), ("cold", "Cold"), ("rain", "Rain"),
         ("soil", "Soil"))


def _pack(lat, lng):
    from src import region_climate
    if lat is None or lng is None:
        return None
    return region_climate.pack_for({"latitude": lat, "longitude": lng})


def _typical(lat, lng) -> str:
    """"typical for the Edmonton region": what a fallback figure is."""
    pack = _pack(lat, lng)
    return f"typical for the {pack.name}" if pack is not None else ""


def where_line(label: str, lat, lng) -> str:
    """The pin's place and the region it is in, or ``""`` with no pin."""
    if lat is None or lng is None:
        return ""
    from src import region
    from src.site_fit import province_at
    parts = [p.strip() for p in (label or "").split(",") if p.strip()]
    place = ", ".join(parts[:2]) or "Your yard"
    pack = region.at(lat, lng)
    if pack is not None:
        return f"{place}, in the {pack.name}."
    prov = {"AB": "Alberta", "SK": "Saskatchewan"}.get(
        province_at(lat, lng), "")
    return f"{place}, in {prov}." if prov else f"{place}."


def _date(doy: int) -> str:
    import datetime as dt
    d = dt.date(2025, 1, 1) + dt.timedelta(days=int(doy) - 1)
    return f"{MONTHS[d.month - 1]} {d.day}"


def cold_line(zone, frost: Optional[tuple], lat, lng) -> str:
    """The zone, then the frost-free window: the yard's own (``frost``,
    ``(last spring, first fall)`` as days of the year), else the region's
    station normal, said as typical."""
    out = []
    if zone not in (None, ""):
        out.append(f"Plants hardy to zone {zone} grow here.")
    if frost and None not in frost:
        out.append(f"Frost-free from about {_date(frost[0])} to "
                   f"{_date(frost[1])}.")
    else:
        from src import region_climate
        f = region_climate.frost_dates({"latitude": lat, "longitude": lng})
        if f:
            last = f"{MONTHS[f['last'][0] - 1]} {f['last'][1]}"
            first = f"{MONTHS[f['first'][0] - 1]} {f['first'][1]}"
            out.append(f"Frost-free from about {last} to {first} "
                       f"({_typical(lat, lng)}).")
    return " ".join(out)


def _wettest(monthly) -> str:
    """"June and July": the two wettest months, in calendar order."""
    top = sorted(sorted(range(12), key=lambda i: -monthly[i])[:2])
    return " and ".join(MONTHS[i] for i in top)


def rain_line(rain: Optional[dict], lat, lng) -> str:
    """The year's rain and when most of it falls. A station's normal is
    typical for the region, not this yard's own; no fetch reads the pack's."""
    typical = ""
    monthly = list((rain or {}).get("monthly_mm") or [])
    annual = (rain or {}).get("annual_mm")
    if not monthly or annual is None:
        from src import region_climate
        monthly, _label = region_climate.rainfall(
            {"latitude": lat, "longitude": lng})
        monthly = list(monthly)
        annual = sum(monthly) if monthly else None
        typical = _typical(lat, lng)
    elif "normal" in ((rain or {}).get("source") or "").lower():
        typical = _typical(lat, lng)
    if annual is None or len(monthly) != 12:
        return ""
    text = (f"About {int(round(annual / 10.0) * 10)} mm a year, most of it in "
            f"{_wettest(monthly)}")
    return text + (f" ({typical})." if typical else ".")


def ph_words(ph: float) -> str:
    if ph < 5.5:
        return "acidic"
    if ph < 6.5:
        return "slightly acidic"
    if ph <= 7.3:
        return "neutral"
    if ph <= 7.8:
        return "slightly alkaline"
    return "alkaline"


def soil_line(soil: Optional[dict], lat, lng) -> str:
    """The texture and pH, as mapped near the yard or typical for the
    region; ``""`` with neither."""
    if not soil:
        return ""
    from src.site_prep import texture_class
    s = soil.get("summary") or {}
    texture = texture_class(s.get("texture_class"))
    ph = s.get("ph_top")
    parts = [texture] if texture else []
    if ph is not None:
        parts.append(f"{ph_words(float(ph))} (pH {float(ph):.1f})")
    if not parts:
        return ""
    where = (_typical(lat, lng) if soil.get("fallback")
             else "as mapped near your yard")
    text = ", ".join(parts)
    return text[0].upper() + text[1:] + (f", {where}." if where else ".")


def lines(facts: dict) -> list:
    """``[(label, text)]``, only the lines the app has something for.

    ``facts``: ``label``, ``lat``, ``lng``, ``zone``, ``frost``
    (``(last, first)`` days of the year), ``rain`` and ``soil`` (the
    fetches' dicts)."""
    lat, lng = facts.get("lat"), facts.get("lng")
    if lat is None or lng is None:
        return []
    texts = {
        "where": where_line(facts.get("label", ""), lat, lng),
        "cold": cold_line(facts.get("zone"), facts.get("frost"), lat, lng),
        "rain": rain_line(facts.get("rain"), lat, lng),
        "soil": soil_line(facts.get("soil"), lat, lng),
    }
    return [(label, texts[key]) for key, label in LINES if texts[key]]
