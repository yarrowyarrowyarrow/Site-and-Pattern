"""
phenology_bar.py — when this plant flowers, drawn.

Design principle P5 — see docs/DESIGN_PHILOSOPHY.md.

Why this exists
---------------
The catalogue has known each species' bloom window since the first seed file
(``bloom_period`` on 424 of 430 species) and has shown it three ways, all of
them text: the words "Jun–Sep" in a table, twelve month chips linking to the
blooming-in hubs, and a sentence in the directory. None of those let you answer
the question a person actually has in front of a plant list, which is *what is
flowering in July, and does anything carry August* — because comparing two
species means reading two strings and holding a calendar in your head.

Every regional flora draws this as a bar. It is the second half of the atlas
page whose first half is the dot map: where it grows, and when it does the
thing you are planting it for. Twelve cells and no prose.

**Fruit sits on the same axis on purpose.** 285 species carry ``fruit_period``,
and the gap between the two is the information — a shrub that flowers in May
and fruits in September is doing eleven months of work in a design, and no
arrangement of two separate strings shows that.

What it will not do
-------------------
**Nothing recorded draws nothing** (P9). A bar of twelve empty cells is not the
absence of a claim, it is the claim that we checked and this plant never
flowers, which for the six species with no ``bloom_period`` would be false. An
empty string is the honest output and the caller omits the row.

**The window is a stated range, not an observation series.** It came from
horticultural references, not from phenology records, so it is one solid band
per plant and cannot show that bloom peaks mid-window or that it runs three
weeks later in the north. The caption says so rather than leaving a reader to
assume a resolution the data does not have.

Output is a self-contained ``<svg>`` string: no script, no external reference,
no dependency, same contract as :mod:`src.ecoregion_map`. Callers embed it
directly.
"""

from __future__ import annotations

import html

#: Month initials, as a flora prints them. Twelve characters, because a bar
#: that needs three-letter labels stops fitting beside a map on a phone.
MONTH_INITIALS = ("J", "F", "M", "A", "M", "J",
                  "J", "A", "S", "O", "N", "D")

MONTH_NAMES = ("January", "February", "March", "April", "May", "June",
               "July", "August", "September", "October", "November",
               "December")

#: Bloom and fruit fills. Deliberately not the flower's own colour: 
#: `bloom_colour_note` reads "a genus-level estimate" on a large share of the
#: catalogue, and painting the bar with an estimate would launder it into
#: something that looks measured. The flower's colour has its own labelled row
#: on the page, where the estimate travels with it.
BLOOM_FILL = "#c2762c"
FRUIT_FILL = "#7a4a5e"
EMPTY_FILL = "#e8e4dc"
GRID = "#c9c2b6"

#: Growing season, for the faint band behind the cells. Alberta and
#: Saskatchewan, not a general truth -- which is the point: a bar that shows a
#: bloom in April reads differently once you can see the ground is frozen.
SEASON = (5, 6, 7, 8, 9)


def parse_period(text: str) -> list[int]:
    """``"June–August"`` -> ``[6, 7, 8]``. Wraps the year end.

    A thin pass-through to :func:`src.habitat_score.parse_month_range`, which
    has parsed these strings since V1.x and handles the en dash, the em dash
    and both the short and long month names -- 37 distinct spellings across the
    catalogue and it reads all of them. Restating that here would be a second
    parser to disagree with the first.
    """
    from src.habitat_score import parse_month_range
    return parse_month_range(text or "")


def phenology_svg(bloom=(), fruit=(), *, width: int = 240,
                  height: int = 34, labels: bool = True,
                  season: bool = True) -> str:
    """The bar. ``""`` when there is nothing to say.

    ``bloom`` and ``fruit`` are month numbers 1-12 in any order. Both empty
    returns the empty string -- see the module docstring on why an empty bar is
    a different and false statement.
    """
    bloom = {int(m) for m in bloom if 1 <= int(m) <= 12}
    fruit = {int(m) for m in fruit if 1 <= int(m) <= 12}
    if not bloom and not fruit:
        return ""

    label_h = 11 if labels else 0
    rows = [("bloom", bloom, BLOOM_FILL)] if bloom else []
    if fruit:
        rows.append(("fruit", fruit, FRUIT_FILL))
    band = (height - label_h) / max(1, len(rows))
    cell = width / 12.0

    parts = [f'<svg class="phenobar" viewBox="0 0 {width} {height}" '
             f'width="100%" height="auto" role="img" '
             f'xmlns="http://www.w3.org/2000/svg" '
             f'aria-label="{html.escape(alt_text(bloom, fruit))}">']

    if season:
        # One rectangle, not five: the growing season is contiguous here, and
        # five abutting rects leave hairline seams at some zoom levels.
        x0 = (SEASON[0] - 1) * cell
        parts.append(f'<rect x="{x0:.1f}" y="0" '
                     f'width="{len(SEASON) * cell:.1f}" '
                     f'height="{height - label_h:.1f}" fill="#f3efe6"/>')

    for row, (_kind, months, fill) in enumerate(rows):
        y = row * band
        for m in range(1, 13):
            x = (m - 1) * cell
            on = m in months
            parts.append(
                f'<rect x="{x:.1f}" y="{y:.1f}" width="{cell:.1f}" '
                f'height="{band:.1f}" fill="{fill if on else EMPTY_FILL}" '
                f'fill-opacity="{"0.95" if on else "0.45"}" '
                f'stroke="{GRID}" stroke-width="0.5"/>')

    if labels:
        for m in range(1, 13):
            parts.append(
                f'<text x="{(m - 0.5) * cell:.1f}" y="{height - 2:.1f}" '
                f'text-anchor="middle" font-size="8" fill="#6b6357">'
                f'{MONTH_INITIALS[m - 1]}</text>')

    parts.append(f"<title>{html.escape(alt_text(bloom, fruit))}</title>")
    parts.append("</svg>")
    return "".join(parts)


def alt_text(bloom, fruit=()) -> str:
    """What the bar says, in words. The accessible name and the tooltip.

    A picture of a calendar is unreadable to a screen reader and to anybody
    printing in greyscale, and this catalogue has an outside review's worth of
    evidence that the second group exists.
    """
    bloom = sorted({int(m) for m in bloom if 1 <= int(m) <= 12})
    fruit = sorted({int(m) for m in fruit if 1 <= int(m) <= 12})
    bits = []
    if bloom:
        bits.append(f"Flowers {_span(bloom)}")
    if fruit:
        bits.append(f"fruits {_span(fruit)}")
    return "; ".join(bits) if bits else ""


def _span(months: list) -> str:
    """``[6, 7, 8]`` -> ``"June to August"``; ``[6]`` -> ``"in June"``.

    Handles the wrap the parser produces for a range like Nov-Feb, which
    arrives as ``[11, 12, 1, 2]`` sorted into ``[1, 2, 11, 12]`` and is one
    window, not two.
    """
    if len(months) == 1:
        return f"in {MONTH_NAMES[months[0] - 1]}"
    if len(months) == 12:
        return "all year"
    wrapped = 1 in months and 12 in months and len(months) < 12
    if wrapped:
        start = max(m for m in months if m > 6 and m - 1 not in months) \
            if any(m > 6 and m - 1 not in months for m in months) else 12
        end = max(m for m in months if m < 7 and m + 1 not in months)
        return f"{MONTH_NAMES[start - 1]} to {MONTH_NAMES[end - 1]}"
    return f"{MONTH_NAMES[months[0] - 1]} to {MONTH_NAMES[months[-1] - 1]}"


#: What the bar is and is not, for a caption beside it. One sentence, because
#: the alternative is a reader assuming a resolution the data does not have.
CAVEAT = ("Flowering and fruiting windows as recorded in the catalogue, from "
          "horticultural references rather than phenology records: one stated "
          "range per species, so the bar cannot show a peak inside the window "
          "or that bloom runs later in the north.")
