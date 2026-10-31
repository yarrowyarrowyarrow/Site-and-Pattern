"""
plan_notes.py — what a plan says about itself in the simple app (PY-8, V3.29;
docs/homeowner/07-plan-my-yard.md §4.5).

Design principle P9 — see docs/DESIGN_PHILOSOPHY.md.

The generator leaves its notes in two lists on the project's properties:
``generation_warnings``, the English the advanced Design notes and the command
line show, and ``generation_notes``, a code for each with what it needs
(``{"code": "vine_alone", "names": [...]}``). This module is the one table from
code to the simple app's words: a code in :data:`COULD_NOT` becomes a *What I
could not do* line, a code in :data:`ADVANCED_ONLY` stays in the Design notes.
A test reads every code the generator can leave and fails on one this table
does not know.

:func:`summary` is *About this plan*: at most six lines and two *could not*
lines, in the Overview's voice, its numbers computed by the functions the
Overview uses (``yard_overview_items``), never restated. No "community",
"boundary", "species" or "existing feature".

Qt-free.
"""

from __future__ import annotations

from typing import Callable, Optional

#: Codes whose note becomes a *What I could not do* line: ``code: words``, the
#: words formatted with the note's fields.
COULD_NOT = {
    "no_pond": "Plants that grow in standing water were left out: there is "
               "no pond.",
    "pond_full": "The pond had no room for every water plant.",
    "vine_alone": "Nothing in the plan is tall enough for {names} to climb "
                  "yet, so it lies on the ground.",
    "hard_to_find": "{names} is rarely sold. Ask a nursery before you count "
                    "on it.",
    "cover_short": "It covers about {cover}% of the ground once grown, not "
                   "{target}%: {reason}.",
    "over_budget": "It is over your budget: plants about {cost}.",
    "no_goal_plant": "No plant does everything you asked at once, so it may "
                     "not do all of it.",
}

#: Codes that stay in the advanced Design notes, with why.
ADVANCED_ONLY = {
    "revised": "a second round only the command line runs",
    "repair": "the design review's additions, said on each plant's page",
    "communities_skipped": "a count of plant communities, an advanced word",
    "companion": "companion spacing, an advanced tool",
    "pond_planted": "said on each pond plant's page",
    "for_animal": "the wildlife picker is an advanced tool",
    "water_only": "the wildlife picker is an advanced tool",
    "unbacked": "a goal no data backs is not offered",
    "caveat": "said beside the box in the dialog",
    "goal_added": "said on the plant's page",
    "goal_pond": "said on the plant's page",
    "goal_water_only": "the advanced goals only",
    "budget": "the cost line says it",
}

#: Words the simple summary never uses (§4.5).
BANNED = ("community", "communities", "boundary", "species",
          "existing feature")

MAX_LINES = 6

#: A structure in a sentence.
STRUCTURE_WORDS = {"brush_pile": "a brush pile", "bee_hotel": "a bee hotel"}
MAX_COULD_NOT = 2


def known_codes() -> set:
    return set(COULD_NOT) | set(ADVANCED_ONLY)


def _names(names) -> str:
    names = list(dict.fromkeys(n for n in (names or []) if n))
    if len(names) <= 1:
        return "".join(names)
    return ", ".join(names[:-1]) + " and " + names[-1]


def could_not(notes: list) -> list:
    """The *What I could not do* lines for ``notes``, at most two, each once."""
    out = []
    for note in notes or []:
        words = COULD_NOT.get(note.get("code"))
        if not words:
            continue
        fields = {k: v for k, v in note.items() if k != "code"}
        if "names" in fields:
            fields["names"] = _names(fields["names"])
            if len(set(note.get("names") or [])) > 1:
                words = words.replace("so it lies", "so they lie")
            if "{names} is" in words and len(set(note.get("names") or [])) > 1:
                words = words.replace("is rarely sold", "are rarely sold") \
                    .replace("on it", "on them")
        try:
            line = words.format(**fields)
        except (KeyError, IndexError):
            continue
        if line not in out:
            out.append(line)
    return out[:MAX_COULD_NOT]


def plan_features(project: dict, plan_run: str = "") -> list:
    """The features a plan placed: those stamped ``plan_run`` (the last plan
    when none is named), or every plant when nothing is stamped."""
    feats = list((project or {}).get("features") or [])
    runs = [(f.get("properties") or {}).get("plan_run") for f in feats]
    run = plan_run or next((r for r in reversed(runs) if r), "")
    if not run:
        return feats
    return [f for f in feats
            if (f.get("properties") or {}).get("plan_run") == run]


def summary(project: dict, notes: list, *, where: str = "",
            setting: str = "", plan_run: str = "",
            get_plant: Optional[Callable] = None) -> dict:
    """*About this plan*: ``{"heading", "lines", "could_not"}``.

    ``where`` is "beds" or "yard"; ``setting`` "front", "back" or "". The
    numbers are the plan's own plants', by the Overview's functions."""
    from src import yard_overview_items as items
    sub = dict(project or {})
    sub["features"] = plan_features(project, plan_run)
    d = items._gather(sub, get_plant)
    n, kinds = len(d.placed), len(d.ids)
    heading = (f"Your plan: {n} plant{'s' if n != 1 else ''} of "
               f"{kinds} kind{'s' if kinds != 1 else ''}")
    lines = []
    parts = [{"beds": "In your beds", "yard": "In your yard outline"}.get(
        where, "")]
    if setting == "front":
        parts.append("with shorter plants along the street")
    elif setting == "back":
        made = [STRUCTURE_WORDS.get(s.get("id"), "")
                or "a " + (s.get("name") or "").lower()
                for s in d.structures if s.get("id") or s.get("name")]
        if made:
            parts.append(f"with {_names(made)}")
    first = ", ".join(p for p in parts if p)
    if first:
        lines.append(first[0].upper() + first[1:] + ".")
    if n:
        lines.append(items.item_flowers(d).lines[0])
        lines.append(items.item_food(d).lines[0])
        lines.append(_cost_line(d))
    return {"heading": heading, "lines": lines[:MAX_LINES],
            "could_not": could_not(notes)}


def _cost_line(d) -> str:
    from src import region, sourcing
    pack = region.for_site(d.site) or region.default()
    note = ((pack.overview or {}).get("price_note") or "").strip()
    lo, hi = sourcing.estimate_cost(d.placed, get_plant=d.get_plant)
    return f"About {items_dollars(lo, hi)}" + (f" {note}." if note else ".")


def items_dollars(lo: float, hi: float) -> str:
    from src.yard_overview_items import _dollars
    return _dollars(lo, hi)


def as_text(s: dict) -> str:
    out = [s["heading"], ""] + list(s["lines"])
    if s["could_not"]:
        out += ["", "What I could not do"] + [f"• {c}" for c in s["could_not"]]
    return "\n".join(out)
