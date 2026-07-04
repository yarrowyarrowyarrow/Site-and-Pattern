"""
phenology.py — the "what's happening now" phenology dashboard (F51).

The app is good at the install-day snapshot; this module answers the question a
gardener actually asks all season: *what is happening in my design right now, and
what should I go outside and look for?* For the placed plants it derives, month
by month, what is **blooming**, **fruiting**, **waking** (breaking dormancy in
spring), **going dormant** (fall senescence), and which hands-on **tasks** the
planting calendar calls for — then turns the current month into a short "go
check" prompt that sends the user out to verify the prediction against the real
site.

Design principle P4 (time is the most undervalued design variable — the design
is a trajectory, not a single day) and P11 (the body and the site know things the
screen does not — every prediction becomes a thing to go confirm outside). See
docs/DESIGN_PHILOSOPHY.md.

Qt-free and deterministic: the panel renders it, the scripting layer and the
tests exercise it directly. Bloom/fruit windows are parsed with the same
``parse_month_range`` the Habitat Score and forage calendar use, so nothing can
disagree. Per-plant data (fruit window, planting calendar) is injectable; by
default it reads the DB.
"""

from __future__ import annotations

from typing import Callable, Optional

from src.habitat_score import parse_month_range

_MONTH_ABBR = ["", "Jan", "Feb", "Mar", "Apr", "May", "Jun",
               "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
_MONTH_FULL = ["", "January", "February", "March", "April", "May", "June",
               "July", "August", "September", "October", "November", "December"]

# Planting-calendar statuses that are a hands-on task worth a reminder (the
# 'dormant'/'growing' base states are not actionable).
_TASK_STATUSES = {"start_indoors", "direct_sow", "transplant", "harvest", "pruning"}
_TASK_VERB = {
    "start_indoors": "start seeds indoors", "direct_sow": "direct-sow",
    "transplant": "transplant out", "harvest": "harvest", "pruning": "prune",
}


def _distinct_plants(placed_plants: list[dict],
                     get_plant: Optional[Callable]) -> list[dict]:
    """One record per distinct placed species, carrying the fields we need.
    Uses the placed dict's own fields when present, else looks the plant up."""
    seen: dict = {}
    for p in placed_plants or []:
        pid = p.get("plant_id")
        if pid is None or pid in seen:
            continue
        rec = {
            "plant_id": pid,
            "common_name": p.get("common_name") or "",
            "bloom_period": p.get("bloom_period"),
            "fruit_period": p.get("fruit_period"),
        }
        # Fill any missing piece from the DB (fruit_period is rarely on the
        # placed feature; bloom_period usually is).
        if rec["bloom_period"] is None or rec["fruit_period"] is None \
                or not rec["common_name"]:
            if get_plant is None:
                from src.db.plants import get_plant as _gp
                get_plant = _gp
            row = get_plant(pid) or {}
            rec["common_name"] = rec["common_name"] or row.get("common_name") or f"plant {pid}"
            if rec["bloom_period"] is None:
                rec["bloom_period"] = row.get("bloom_period")
            if rec["fruit_period"] is None:
                rec["fruit_period"] = row.get("fruit_period")
        seen[pid] = rec
    return list(seen.values())


def _active_flags(calendar: Optional[list]) -> Optional[list]:
    """12 booleans: is the plant out of dormancy that month? ``None`` if we have
    no calendar to reason from."""
    if not calendar:
        return None
    flags = [False] * 12
    for entry in calendar:
        m = entry.get("month")
        if isinstance(m, int) and 1 <= m <= 12:
            flags[m - 1] = (entry.get("status") != "dormant")
    return flags


def _transitions(flags: Optional[list]) -> tuple[set, set]:
    """(waking_months, dormant_months) from the active-flag ring — a wake is
    inactive→active, a senescence is active→inactive (Dec wraps to Jan)."""
    if not flags or all(flags) or not any(flags):
        return set(), set()
    waking, going = set(), set()
    for m in range(12):
        prev = flags[m - 1]        # m==0 → flags[-1] == December, the wrap
        if flags[m] and not prev:
            waking.add(m + 1)
        elif not flags[m] and prev:
            going.add(m + 1)
    return waking, going


def build_phenology(placed_plants: Optional[list[dict]], *,
                    month: Optional[int] = None,
                    get_plant: Optional[Callable] = None,
                    get_calendar: Optional[Callable] = None) -> dict:
    """Return the month-by-month phenology of ``placed_plants``.

    ``month`` sets the "now" slice (defaults to the current calendar month).
    ``get_plant`` / ``get_calendar`` are injectable for tests; by default they
    read the DB. See the module docstring for the result shape.
    """
    if month is None:
        from datetime import datetime
        month = datetime.now().month
    month = max(1, min(12, int(month)))

    plants = _distinct_plants(placed_plants or [], get_plant)

    months = [{"month": m, "name": _MONTH_FULL[m], "abbr": _MONTH_ABBR[m],
               "blooming": [], "fruiting": [], "waking": [], "dormant": [],
               "tasks": []} for m in range(1, 13)]

    for rec in plants:
        name = rec["common_name"]
        for m in parse_month_range(rec.get("bloom_period") or ""):
            if 1 <= m <= 12:
                months[m - 1]["blooming"].append(name)
        for m in parse_month_range(rec.get("fruit_period") or ""):
            if 1 <= m <= 12:
                months[m - 1]["fruiting"].append(name)
        # Waking / dormancy / tasks need the planting calendar.
        if get_calendar is None:
            from src.db.plants import get_calendar as _gc
            get_calendar = _gc
        try:
            cal = get_calendar(rec["plant_id"])
        except Exception:      # noqa: BLE001
            cal = None
        waking, going = _transitions(_active_flags(cal))
        for m in waking:
            months[m - 1]["waking"].append(name)
        for m in going:
            months[m - 1]["dormant"].append(name)
        for entry in (cal or []):
            st = entry.get("status")
            mm = entry.get("month")
            if st in _TASK_STATUSES and isinstance(mm, int) and 1 <= mm <= 12:
                months[mm - 1]["tasks"].append({"name": name, "status": st,
                                                "verb": _TASK_VERB.get(st, st)})

    for slot in months:
        slot["n_active"] = (len(slot["blooming"]) + len(slot["fruiting"])
                            + len(slot["waking"]) + len(slot["dormant"])
                            + len(slot["tasks"]))

    now = _now_slice(months[month - 1], len(plants))
    return {
        "current_month": month,
        "current_name": _MONTH_FULL[month],
        "months": months,
        "now": now,
        "n_plants": len(plants),
        "note": now["headline"],
    }


def _now_slice(slot: dict, n_plants: int) -> dict:
    """The current month plus a plain-language headline and a 'go verify' prompt."""
    name = slot["name"]
    if n_plants == 0:
        headline = "No plants placed yet — add some to see the season unfold."
        go_check = ""
    else:
        bits = []
        if slot["blooming"]:
            bits.append(f"{len(slot['blooming'])} in bloom")
        if slot["fruiting"]:
            bits.append(f"{len(slot['fruiting'])} fruiting")
        if slot["waking"]:
            bits.append(f"{len(slot['waking'])} breaking dormancy")
        if slot["dormant"]:
            bits.append(f"{len(slot['dormant'])} going dormant")
        if slot["tasks"]:
            bits.append(f"{len(slot['tasks'])} task"
                        f"{'s' if len(slot['tasks']) != 1 else ''}")
        headline = (f"{name}: " + ", ".join(bits) + "."
                    if bits else
                    f"{name}: a quiet month — nothing predicted to change.")
        go_check = _go_check(slot)
    return {
        "month": slot["month"], "name": name,
        "blooming": slot["blooming"], "fruiting": slot["fruiting"],
        "waking": slot["waking"], "dormant": slot["dormant"],
        "tasks": slot["tasks"], "headline": headline, "go_check": go_check,
    }


def _go_check(slot: dict) -> str:
    """A prediction to walk outside and confirm (P11)."""
    if slot["blooming"]:
        who = slot["blooming"][0]
        extra = (f" and {len(slot['blooming']) - 1} more"
                 if len(slot["blooming"]) > 1 else "")
        return (f"We predict {who}{extra} in bloom around now — go outside and "
                f"check. Is it early, late, or on time? Note what you actually see.")
    if slot["fruiting"]:
        who = slot["fruiting"][0]
        return (f"We predict {who} setting fruit around now — go see whether the "
                f"birds have found it yet.")
    if slot["waking"]:
        who = slot["waking"][0]
        return (f"We predict {who} breaking dormancy — go look for the first "
                f"green and mark the date.")
    if slot["tasks"]:
        t = slot["tasks"][0]
        return f"Time to {t['verb']} {t['name']} — and see how the ground looks."
    return ("Nothing dramatic predicted — a good week to just walk the site and "
            "notice what the model can't see.")
