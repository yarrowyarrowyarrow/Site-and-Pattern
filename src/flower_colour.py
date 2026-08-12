"""
flower_colour.py — what colour a plant flowers, as something you can filter on.

Design principle P13 — see docs/DESIGN_PHILOSOPHY.md.

``plants.flower_color`` has held a hex since schema v31 (V1.90), where it drives
the 3D viewer's florets. Thirty search parameters later, **none of them was
colour** — the one axis every ornamental catalogue on the web leads with, and
the one a person uses when they are choosing a plant because they want to look
at it. P13 says beauty is the mechanism the ecology survives contact with people
by; a catalogue that cannot answer "show me the white ones" is not serving it.

This module is the parser that makes the column filterable. It is used by
``db.plants.search_plants`` (the ``flower_colours`` filter), by the directory's
facet strip, and by the static site's colour pages — one classifier, so those
three can never disagree about what colour a plant is.

**The largest bucket is not a bloom colour, and says so.** All 79 species
carrying ``#cbbd80`` are grasses, sedges and rushes, every one of them recorded
with ``flower_form = 'plume'``. Poaceae, Cyperaceae and Juncaceae are
wind-pollinated: they do not advertise, and that hex is the *default for a plant
with no showy flower*, not an observation of one. Filed as "yellow" beside a
black-eyed susan it would be a claim the data does not make (P9). It gets its
own bucket instead, named for what it is — and stays selectable, because
designing for winter texture means wanting exactly that set.

**A plant with no recorded colour matches no colour**, the same rule
``_month_filter`` applies to bloom windows: "we don't know" is not "white".
"""

from __future__ import annotations

import colorsys
from typing import Optional

#: Families that do not advertise. The taxonomic rule is checked *before* the
#: hex, because it is the reason the straw bucket exists — the HSV band that
#: also happens to catch `#cbbd80` is only a heuristic, and a grass that one day
#: gets a brighter hex should still classify honestly.
WIND_POLLINATED_TYPES = frozenset({"grass", "sedge", "rush"})

#: ``(key, label, swatch, note)`` — the filter vocabulary, in the order a colour
#: wheel runs so the facet list reads as a spectrum rather than a frequency
#: table. ``swatch`` is a representative hex for a UI chip; ``note`` is the
#: tooltip. Buckets with no species today (green) are kept: the vocabulary
#: describes the colour space, not this month's seed data.
COLOURS: tuple = (
    ("white",  "White",            "#f2f2ea",
     "Clean white — the moon-garden palette."),
    ("cream",  "Cream",            "#ece6c8",
     "Greenish- or yellowish-white."),
    ("yellow", "Yellow",           "#f2c11e",
     "The prairie's most common bloom colour by a wide margin."),
    ("orange", "Orange",           "#e07020",
     "Rare here — three species."),
    ("red",    "Red",              "#d6453a",
     "Includes the deep wine reds."),
    ("pink",   "Pink",             "#e58fb0",
     "Pale pink through magenta."),
    ("purple", "Purple",           "#8e6fc4",
     "Violet, lilac and mauve."),
    ("blue",   "Blue",             "#6f8fd6",
     "True blues are uncommon in any flora."),
    ("green",  "Green",            "#7f9a52",
     "Greenish flowers that are still showy."),
    ("brown",  "Brown",            "#7a5230",
     "Dark browns and bronzes."),
    ("straw",  "Straw / green (grasses & sedges)", "#cbbd80",
     "Grasses, sedges and rushes. Wind-pollinated, so this is the colour of "
     "the seed head, not of a flower — the texture you design with, not a "
     "bloom you notice."),
)

#: ``{key: label}``, for the facet table.
COLOUR_LABELS: dict = {key: label for key, label, _swatch, _note in COLOURS}

#: ``{key: hex}``, for swatches.
COLOUR_SWATCHES: dict = {key: swatch for key, _label, swatch, _note in COLOURS}

#: The keys, in wheel order.
COLOUR_KEYS: tuple = tuple(key for key, _l, _s, _n in COLOURS)


def _hsv(value: str) -> Optional[tuple]:
    """``#rrggbb`` → ``(hue 0–360, sat 0–1, val 0–1)``, or ``None``.

    Returns ``None`` rather than raising on anything unparseable: a malformed
    hex in one row must not take down a search over the whole catalogue.
    """
    text = (value or "").strip().lstrip("#")
    if len(text) != 6:
        return None
    try:
        r, g, b = (int(text[i:i + 2], 16) / 255 for i in (0, 2, 4))
    except ValueError:
        return None
    hue, sat, val = colorsys.rgb_to_hsv(r, g, b)
    return hue * 360.0, sat, val


def classify_hex(value: str) -> str:
    """The colour bucket for a hex, or ``""`` if there isn't one.

    Thresholds are set against the 23 hexes actually in the catalogue (the table
    in ``docs/plans/V2.47-colour-and-a-public-catalogue.md``) and chosen at the
    gaps between them, not at round numbers. Two are load-bearing:

    * **White is saturation ≤ 0.12**, not the more obvious 0.2. `#c9b8e0` is a
      pale lilac at 0.18 and a looser rule files it as white.
    * **Yellow needs saturation ≥ 0.55.** Below that, in the same hue band, sits
      the wind-pollinated straw — see the module docstring.
    """
    got = _hsv(value)
    if got is None:
        return ""
    hue, sat, val = got

    if val < 0.18:                                   # near-black reads as brown
        return "brown"
    if sat <= 0.12 and val >= 0.80:
        return "white"

    if 30.0 <= hue < 70.0:                           # the warm-neutral band
        if sat <= 0.30 and val >= 0.85:
            return "cream"
        if sat < 0.55 and val < 0.90:
            return "straw"
        if val < 0.62:
            return "brown"
        return "yellow"
    if 15.0 <= hue < 30.0:
        return "brown" if val < 0.62 else "orange"
    if hue >= 345.0 or hue < 15.0:
        return "pink" if sat < 0.45 else "red"
    if 70.0 <= hue < 170.0:
        return "green"
    if 170.0 <= hue < 248.0:                         # 248 splits `#7e7fc4`
        return "blue"                                # (periwinkle) from violet
    if 248.0 <= hue < 300.0:
        return "purple"
    return "pink"                                    # 300–345, the magentas


def classify(plant: dict) -> str:
    """The colour bucket for a plant row, or ``""`` if it records no colour.

    Reads ``plant_type`` before ``flower_color`` on purpose — see the module
    docstring on why the wind-pollinated rule is the primary one.
    """
    colour = (plant.get("flower_color") or "").strip()
    if not colour:
        return ""
    if (plant.get("plant_type") or "") in WIND_POLLINATED_TYPES:
        return "straw"
    return classify_hex(colour)


def matches(plant: dict, wanted) -> bool:
    """Does ``plant`` fall in any of the ``wanted`` colour keys?

    An empty ``wanted`` means no restriction, matching how every other
    ``search_plants`` filter reads an empty value.
    """
    keys = {str(k) for k in (wanted or []) if str(k).strip()}
    if not keys:
        return True
    return classify(plant) in keys


def bucket_counts(plants) -> dict:
    """``{colour_key: n}`` over ``plants``, for the pages that show how big each
    colour is before you click it. Uncoloured rows are counted under ``""`` so a
    caller can report the gap rather than having it vanish."""
    counts: dict = {}
    for plant in plants or []:
        key = classify(plant)
        counts[key] = counts.get(key, 0) + 1
    return counts
