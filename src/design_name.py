"""
design_name.py — a design takes its name from its address (V3.23, ST-5;
docs/homeowner/04-start-screen.md §6, the owner's S9).

Every design started as "Untitled Design" unless File › New's prompt was
filled in, so the saves list and the window title said the same two words for
every yard. Now the address search names it: Nominatim's
``"10234, 82 Avenue NW, Strathcona, Edmonton, Alberta, T6E 1Z8, Canada"``
becomes ``"10234 82 Avenue NW"``. Only a placeholder name is replaced: a name
the person gave is never touched.

Qt-free. The glue that renames the open design is
:func:`src.start_flow.name_from_pin`.
"""

from __future__ import annotations

import re

PLACEHOLDER = "Untitled Design"
#: Names other code has used for a design nobody named. "My yard" is not one:
#: it is what the save prompt offers, and saving under it is a choice.
_PLACEHOLDERS = {PLACEHOLDER.lower(), "", "untitled"}
MAX_CHARS = 60

_HOUSE_NUMBER = re.compile(r"^\d+[A-Za-z]?(?:[-/]\d+[A-Za-z]?)?$")
_COORDINATES = re.compile(r"^\s*-?\d+(?:\.\d+)?\s*,\s*-?\d+(?:\.\d+)?\s*$")


def is_placeholder(name) -> bool:
    """Whether ``name`` is one nobody chose."""
    return (name or "").strip().lower() in _PLACEHOLDERS


def from_address(label) -> str:
    """A short name for a design from an address search's label, or ``""``.

    A house number is joined to its street ("10234 82 Avenue NW"); otherwise
    the first part ("Ritchie"). A label that is only coordinates names
    nothing. At most :data:`MAX_CHARS`. Never raises."""
    try:
        text = (label or "").strip()
        if not text or _COORDINATES.match(text):
            return ""
        parts = [p.strip() for p in text.split(",") if p.strip()]
        if not parts:
            return ""
        name = parts[0]
        if _HOUSE_NUMBER.match(name) and len(parts) > 1:
            name = f"{name} {parts[1]}"
        name = " ".join(name.split())
        return name[:MAX_CHARS].rstrip()
    except Exception:                                      # noqa: BLE001
        return ""


def renamed(current, label, previous="") -> str:
    """The name a design should take when its pin arrives with ``label``:
    the address's name when ``current`` is a placeholder and the label names
    somewhere, else ``""`` (no change).

    A name the last address gave (``previous`` is that pin's label) is a
    placeholder too, so it follows the pin when the pin moves (V3.37): the
    owner's list held a design called "8103 95A Street NW" pinned at 10173
    144 Street NW. Once the person changes the name it is theirs."""
    taken = from_address(previous) if previous else ""
    if not is_placeholder(current) and not (
            taken and (current or "").strip() == taken):
        return ""
    name = from_address(label)
    return "" if name == (current or "").strip() else name
