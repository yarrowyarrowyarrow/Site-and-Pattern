"""plant_conditions.py — helpers for multi-value plant condition fields (V1.84).

Some plant fields — currently ``sun_requirement`` and ``water_needs`` — may hold
a comma-delimited list of values when a species genuinely tolerates a range of
conditions (e.g. ``"full_sun,partial_shade"``). Storing them as a comma-delimited
TEXT column mirrors the existing ``ab_ecoregion`` / ``edible_parts`` pattern and
needs no schema change.

This module centralises splitting and "any-of" membership so every reader treats
the fields consistently: a plant *fits* a target condition when ANY of its tokens
matches. Pure stdlib, no PyQt6 and no heavy deps — safe to import from the data
layer, scoring, zoning, the planning panel, and the data-quality validator.
"""

from __future__ import annotations

from typing import Iterable


def condition_tokens(value) -> list[str]:
    """Split a (possibly comma-delimited) condition field into clean tokens.

    Accepts a legacy single value (``"full_sun"``), a multi-value string
    (``"full_sun,partial_shade"``), ``None``/``""``, or an already-split
    list/tuple/set. Tokens are stripped and lower-cased; empties are dropped.
    Order is preserved for string/list inputs so the first token can serve as
    the "primary" value where a single answer is required.
    """
    if value is None:
        return []
    if isinstance(value, (list, tuple, set)):
        items: Iterable = value
    else:
        items = str(value).split(",")
    return [t.strip().lower() for t in (str(i) for i in items) if t.strip()]


def condition_matches(value, target: str) -> bool:
    """True when ``target`` is one of the plant's condition tokens.

    ``target`` empty/None means "no restriction" → always True.
    """
    if not target:
        return True
    return target.strip().lower() in condition_tokens(value)
