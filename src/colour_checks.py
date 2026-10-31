"""
colour_checks.py — flower colours checked against photographs (V3.33; F172).

Design principle P9 — see docs/DESIGN_PHILOSOPHY.md.

123 of the catalogue's flower colours are a genus default, 34 were read from a
name, and some read from Budd's flora are what a flora describes rather than
what a person sees (Common Paintbrush's corolla is green; its bracts are red).
The question asked here is the homeowner's: **what colour does it look in
flower?** The owner answers it by looking at photographs of the plant in flower
(``scripts/fetch_colour_evidence.py`` fetches them and writes the review page),
and the answer is recorded as ``photo``, the mark ``src.confidence`` defines as
"read off a photograph".

This module is the rule both sides share:

- :func:`worklist` says which plants to look at, in which order;
- :func:`validate` refuses an answer about a plant not on the list, or a colour
  that is not one of the buckets;
- :func:`apply` writes the answers into ``data/plants_master.json``'s rows, and
  :func:`load_checks` / :func:`agrees` keep ``data/flower_colour_checks.json``
  (the record of every answer, with the observations shown) and the catalogue
  equal, which a test asserts.

Qt-free, and free of the database: it reads the seed rows, so the owner's PC
needs no app data to run the fetch.
"""

from __future__ import annotations

import collections
import json
from pathlib import Path
from typing import Iterable, Optional

from src.flower_colour import (COLOUR_LABELS, COLOUR_SWATCHES,
                               WIND_POLLINATED_TYPES)

ROOT = Path(__file__).resolve().parent.parent
MASTER = ROOT / "data" / "plants_master.json"
CHECKS = ROOT / "data" / "flower_colour_checks.json"

#: The answers that are not colours.
LOOKS_RIGHT = "looks_right"
NO_SHOWY_FLOWER = "no_showy_flower"
CANT_TELL = "cant_tell"
VERDICTS = (LOOKS_RIGHT, NO_SHOWY_FLOWER, CANT_TELL)

#: The source a checked colour carries (``src.confidence``: "read off a
#: photograph").
SOURCE = "photo"

#: The bucket hex, so ``flower_colour.classify_hex`` reads it back to the same
#: bucket. Straw is the grasses' and is never an answer.
HEX = {key: hexval for key, hexval in COLOUR_SWATCHES.items()
       if key != "straw"}
LABELS = {key: COLOUR_LABELS[key] for key in HEX}
ANSWER_COLOURS = tuple(HEX)

#: F172 (the V2.87 3D audit): judged from renders, so first in line to be
#: looked at in photographs. ``scientific_name -> what the audit saw``.
FLAGGED = {
    "Ratibida columnifera": "recorded purple; the rays are usually yellow",
    "Penstemon eriantherus": "recorded red and purple",
    "Castilleja miniata": "recorded green and red: the flora's corolla, not "
                          "the red bracts a person sees",
    "Oxytropis monticola": "Late Yellow Oxytropis, recorded purple",
    "Rubus arcticus": "Dwarf Raspberry, recorded white",
    "Silene acaulis": "Moss Campion, recorded white",
    "Rhodiola integrifolia": "Roseroot, recorded purple and yellow",
}

#: Why a plant is on the list, in the order the list takes them.
REASONS = (
    ("flagged", "flagged by the 3D audit"),
    ("estimated", "a guess from its genus"),
    ("name", "read from its name"),
    ("blank", "no colour recorded"),
    ("flora", "read from Budd's flora"),
)
REASON_WORDS = dict(REASONS)


def load_master(path: Path = MASTER) -> list:
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def load_checks(path: Path = CHECKS) -> dict:
    """``{scientific_name: check}``; ``{}`` before any answers."""
    try:
        with open(path, encoding="utf-8") as f:
            return dict(json.load(f).get("checks") or {})
    except FileNotFoundError:
        return {}


def _source(row: dict) -> str:
    src = (row.get("flower_colour_source") or "").strip()
    if src:
        return src
    return "estimated" if (row.get("flower_color") or "").strip() else ""


def reason(row: dict) -> str:
    """The key in :data:`REASONS` for a row on the list, or ``""``."""
    if (row.get("plant_type") or "") in WIND_POLLINATED_TYPES:
        return ""
    src = _source(row)
    if src in ("photo", "checked"):
        return ""                   # already looked at, flagged or not
    sci = (row.get("scientific_name") or "").strip()
    if sci in FLAGGED:
        return "flagged"
    if src == "estimated":
        return "estimated"
    if src in ("name", "epithet"):
        return "name"
    if not src:
        return "blank"
    if src == "flora":
        return "flora"
    return ""


def share_groups(rows: Iterable[dict]) -> list:
    """``[(siblings, genus, hex, [row, ...]), ...]``, most-shared first:
    how many species in a genus carry one identical hex. One shared value is
    one decision made once and applied many times, which is the shape of every
    colour bug found so far. ``scripts/colour_worklist.py`` ranks by it too."""
    groups: dict = collections.defaultdict(list)
    for row in rows:
        genus = ((row.get("scientific_name") or "").split() or [""])[0]
        groups[(genus, (row.get("flower_color") or "").strip().lower())
               ].append(row)
    out = [(len(v), g, h, sorted(v, key=lambda r: r.get("common_name") or ""))
           for (g, h), v in groups.items()]
    out.sort(key=lambda t: (-t[0], t[1]))
    return out


def worklist(rows: Iterable[dict], checks: Optional[dict] = None,
             include_flora: bool = True) -> list:
    """The plants to look at, in order: ``[{scientific_name, common_name,
    plant_type, reason, colours, hex, why}]``. A plant already answered
    (``checks``) is left off unless it was *can't tell*."""
    checks = checks or {}
    by_reason: dict = collections.defaultdict(list)
    for row in rows:
        key = reason(row)
        if not key or (key == "flora" and not include_flora):
            continue
        sci = (row.get("scientific_name") or "").strip()
        done = checks.get(sci)
        if done and done.get("verdict") != CANT_TELL:
            continue
        by_reason[key].append(row)
    ordered = []
    for key, _words in REASONS:
        group = by_reason.get(key, [])
        if key == "estimated":
            group = [r for _n, _g, _h, members in share_groups(group)
                     for r in members]
        else:
            group = sorted(group, key=lambda r: r.get("common_name") or "")
        for row in group:
            sci = (row.get("scientific_name") or "").strip()
            ordered.append({
                "scientific_name": sci,
                "common_name": row.get("common_name") or sci,
                "plant_type": row.get("plant_type") or "",
                "reason": key,
                "why": FLAGGED.get(sci, ""),
                "hex": (row.get("flower_color") or "").strip(),
                "colours": list(_colours(row)),
            })
    return ordered


def _colours(row: dict) -> tuple:
    from src.flower_colour import colours
    return colours(row)


def validate(answers: dict, listed: Iterable[str]) -> list:
    """Every problem with ``answers`` (``{scientific_name: answer}``), as
    sentences; ``[]`` when all of them can be folded in. An answer is
    ``{"colours": [...]}`` or ``{"verdict": ...}``, with optional
    ``"observations"`` (the iNaturalist ids shown)."""
    listed = set(listed)
    problems = []
    for sci, answer in sorted((answers or {}).items()):
        if sci not in listed:
            problems.append(f"{sci}: not on the list of plants to check")
            continue
        if not isinstance(answer, dict):
            problems.append(f"{sci}: not an answer")
            continue
        colours = answer.get("colours") or []
        verdict = answer.get("verdict") or ""
        if bool(colours) == bool(verdict):
            problems.append(f"{sci}: give colours or a verdict, not both")
            continue
        if verdict and verdict not in VERDICTS:
            problems.append(f"{sci}: unknown verdict {verdict!r}")
        bad = [c for c in colours if c not in ANSWER_COLOURS]
        if bad:
            problems.append(f"{sci}: not a colour: {', '.join(map(str, bad))}")
        if len(set(colours)) != len(colours):
            problems.append(f"{sci}: a colour given twice")
        if len(colours) > 3:
            problems.append(f"{sci}: more than three colours")
    return problems


def apply(rows: list, checks: dict) -> dict:
    """Write ``checks`` into the seed ``rows`` in place. Returns counts by
    what was done. *Looks right* turns what is there into a checked answer
    (its colours, now ``photo``); *no showy flower* clears a colour that was
    a guess; *can't tell* changes nothing."""
    by_sci = {}
    for row in rows:
        by_sci.setdefault((row.get("scientific_name") or "").strip(),
                          []).append(row)
    done = collections.Counter()
    for sci, check in checks.items():
        for row in by_sci.get(sci, []):
            colours = list(check.get("colours") or [])
            verdict = check.get("verdict") or ""
            if verdict == CANT_TELL:
                done["unchanged"] += 1
                continue
            if verdict == NO_SHOWY_FLOWER:
                row["flower_color"] = ""
                row["flower_colours"] = ""
                row["flower_colour_source"] = SOURCE
                done["no showy flower"] += 1
                continue
            if verdict == LOOKS_RIGHT:
                colours = [c for c in _colours(row) if c in HEX]
            if not colours:
                done["unchanged"] += 1
                continue
            row["flower_color"] = HEX[colours[0]]
            row["flower_colours"] = ",".join(colours) if len(colours) > 1 else ""
            row["flower_colour_source"] = SOURCE
            done["confirmed" if verdict == LOOKS_RIGHT else "set"] += 1
    return dict(done)


def agrees(rows: list, checks: dict) -> list:
    """The checked plants whose catalogue row says something else, as
    sentences: what a hand edit of either file would leave behind."""
    by_sci = {(r.get("scientific_name") or "").strip(): r for r in rows}
    out = []
    for sci, check in sorted(checks.items()):
        row = by_sci.get(sci)
        if row is None:
            out.append(f"{sci}: checked but not in the catalogue")
            continue
        verdict = check.get("verdict") or ""
        if verdict == CANT_TELL:
            continue
        if (row.get("flower_colour_source") or "") != SOURCE:
            out.append(f"{sci}: checked, but its source is "
                       f"{row.get('flower_colour_source')!r}")
            continue
        if verdict == NO_SHOWY_FLOWER:
            if (row.get("flower_color") or "").strip():
                out.append(f"{sci}: no showy flower, but a colour is recorded")
            continue
        want = list(check.get("colours") or [])
        if want and list(_colours(row)) != want:
            out.append(f"{sci}: checked {want}, catalogue says "
                       f"{list(_colours(row))}")
    return out


def record(answers: dict, *, made: str, existing: Optional[dict] = None,
           rows: Optional[list] = None) -> dict:
    """The checks file's ``checks``: ``existing`` with ``answers`` laid over
    it. *Looks right* is stored as the colours it confirmed, so the record
    says what the plant is, not what was pressed."""
    out = dict(existing or {})
    by_sci = {(r.get("scientific_name") or "").strip(): r for r in rows or []}
    for sci, answer in answers.items():
        entry = {"made": made,
                 "observations": [int(o) for o in answer.get("observations")
                                  or [] if str(o).isdigit()]}
        verdict = answer.get("verdict") or ""
        if verdict == LOOKS_RIGHT and sci in by_sci:
            kept = [c for c in _colours(by_sci[sci]) if c in HEX]
            if kept:
                entry["colours"] = kept
            else:
                # "Looks right" on a plant with no colour recorded: it has no
                # showy flower, which is what the page shows it as.
                entry["verdict"] = NO_SHOWY_FLOWER
        elif verdict:
            entry["verdict"] = verdict
        else:
            entry["colours"] = list(answer.get("colours") or [])
        if sci in by_sci and "was" not in entry:
            entry["was"] = _source(by_sci[sci]) or "blank"
        out[sci] = entry
    return out
