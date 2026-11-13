"""
scene3d_stops.py — the 3D preview's named moments and viewpoints (V3.44, F261).

Design principle P4 (time is the most undervalued design variable) and P5
(perception is constructed) — see docs/DESIGN_PHILOSOPHY.md.

The V3.43 review's finding 13: sixteen controls in three rows, three of them
sliders with no words on them, and a window that opened on a yard *fully grown*
at one in the afternoon in June, a picture no yard is ever in. A homeowner
brings three questions to it (how will it look in a few years, in which season,
from where) and each has a short list of answers worth looking at.

This is that list, as data, for the toolbar (``scene3d_toolbar``), the window
(``scene3d_window``), the picture's own line (``html/scene3d/27-views.js``,
held equal by a test) and the contact sheets (``scripts/render_yard.py``).
Qt-free.

**A stop is a name for a value, never a rounding of one.** With the fine
sliders (Advanced tools) on year 7 the list reads "Seventh summer", which is
where the picture is, and not "Fifth summer", which is the nearest name.
"""

from __future__ import annotations

#: How far the growth timeline runs (``scene3d_toolbar.MAX_YEAR``).
_MAX_YEAR = 25

_ORDINALS = (
    "First", "Second", "Third", "Fourth", "Fifth", "Sixth", "Seventh",
    "Eighth", "Ninth", "Tenth", "Eleventh", "Twelfth", "Thirteenth",
    "Fourteenth", "Fifteenth", "Sixteenth", "Seventeenth", "Eighteenth",
    "Nineteenth", "Twentieth", "Twenty-first", "Twenty-second",
    "Twenty-third", "Twenty-fourth", "Twenty-fifth",
)

_MONTHS = ("", "January", "February", "March", "April", "May", "June", "July",
           "August", "September", "October", "November", "December")

#: Year 0 is the design fully grown (``scene3d.effective_age``, on purpose):
#: every plant at its grown size, none lost. Said in those words everywhere.
FULLY_GROWN = "Fully grown"

#: The months a yard is not in its summer: the line over the picture says
#: "Fifth year · January", not "Fifth summer · January".
_COLD_MONTHS = (11, 12, 1, 2, 3)

#: ``(year, words)``: the years worth stopping at. Fully grown comes last
#: because it is where the design is headed, and it is year 0 in the model.
WHEN_STOPS = ((1, "First summer"), (3, "Third summer"), (5, "Fifth summer"),
              (10, "Tenth summer"), (20, "Twentieth summer"),
              (0, FULLY_GROWN))

#: ``(month, words)``: one month that shows each season on the prairies.
SEASON_STOPS = ((5, "Spring"), (7, "Summer"), (9, "Fall"), (1, "Winter"))

#: ``(hour, words)``, local solar time, as the sun and its shadows are placed.
DAY_STOPS = ((9, "Morning"), (12, "Midday"), (15, "Afternoon"),
             (19, "Evening"), (23, "Night"))

#: ``(key, words, what it shows)``: where to look from. The key is what
#: ``window.permaShowView`` takes.
VIEWS = (
    ("street", "From the street",
     "Stand where a neighbour would, on the street side, and look in."),
    ("house", "From the house",
     "Stand at the house wall nearest the planting and look out at it."),
    ("above", "From above",
     "Look straight down on the whole yard, north at the top."),
)

#: Said on *From the house* when the scene has no house: no building stands
#: inside the yard's outline or, with nothing outlined, under the yard's pin.
NO_HOUSE = ("No house is recorded in this yard. Scan this area, on the Site "
            "tab's Features page, finds buildings; the house is the one "
            "inside your yard outline, or under your yard's pin.")

#: What the window opens on (decision D5 of the V3.43 plan): the fifth summer,
#: July, mid-afternoon, from the street.
OPENING = {"year": 5, "month": 7, "hour": 15, "view": "street"}


def when_words(year: int, month: int = 7) -> str:
    """"Fully grown", "Fifth summer", or "Fifth year" in a cold month."""
    year = int(year or 0)
    if year <= 0:
        return FULLY_GROWN
    unit = "year" if int(month or 7) in _COLD_MONTHS else "summer"
    if year <= len(_ORDINALS):
        return f"{_ORDINALS[year - 1]} {unit}"
    return f"Year {year}"


def month_words(month: int) -> str:
    """The season's name at a stop, the month's name anywhere else."""
    month = int(month or 0)
    for value, words in SEASON_STOPS:
        if value == month:
            return words
    return _MONTHS[month] if 1 <= month <= 12 else ""


def hour_words(hour: int) -> str:
    """"Afternoon" at a stop, "17:00" anywhere else."""
    hour = int(hour or 0)
    for value, words in DAY_STOPS:
        if value == hour:
            return words
    return f"{hour}:00"


def entries(stops: tuple, value: int, off_stop) -> list:
    """What a list shows for ``value``: ``[(value, words), ...]``, the stops in
    order, plus ``value`` itself in its own words when it is not one of them
    (so the list never names a stop the picture is not at)."""
    rows = [(int(v), words) for v, words in stops]
    if int(value) not in [v for v, _w in rows]:
        rows.append((int(value), off_stop(int(value))))
    return rows


def when_entries(year: int) -> list:
    return entries(WHEN_STOPS, year, when_words)


def season_entries(month: int) -> list:
    return entries(SEASON_STOPS, month, month_words)


def day_entries(hour: int) -> list:
    return entries(DAY_STOPS, hour, hour_words)


def every_word(key: str) -> list:
    """Everything the ``"year"``, ``"month"`` or ``"hour"`` list can come to
    say, stops and the values between them, for sizing it."""
    if key == "year":
        return [when_words(y) for y in range(0, _MAX_YEAR + 1)]
    if key == "month":
        return [month_words(m) for m in range(1, 13)]
    return [hour_words(h) for h in range(0, 24)]


def ordinals() -> tuple:
    """The year words, for the test that holds the page's copy to them."""
    return _ORDINALS


def flyover_storyboard() -> list:
    """The Flyover's ~60 s, three acts, as ``(year, month, hour, big, sub)``
    keyframes: the design grows at peak-summer midday, the seasons turn at
    maturity, and night falls (V2.13; here since V3.44, with the other named
    moments).

    No frame is year 0 (V3.43). It opened on "Year 0: the lawn, today", and
    year 0 is the design fully grown, so the tour began on the finished yard
    and then shrank it. It starts in the first summer; and it does not end on
    year 0 either, which would stand every plant the timeline has lost back
    up."""
    frames = []
    # Act 1 — growth (the first summer → year 25), July midday.
    for y in (1, 2, 3, 5, 7, 9, 12, 15, 18, 22, 25):
        sub = ("the first summer" if y == 1 else
               "settling in" if y <= 2 else
               "filling in" if y <= 9 else
               "a young habitat" if y <= 18 else "grown, not designed")
        frames.append((y, 7, 13, f"Year {y}", sub))
    # Act 2 — the seasons turn, at maturity.
    season = {3: "spring green", 5: "first blooms", 7: "high summer",
              9: "autumn seed & fruit", 11: "bare stems, standing seed"}
    for m in (3, 5, 7, 9, 11):
        frames.append((25, m, 13, _MONTHS[m], season[m]))
    # Act 3 — into the night (moths, bats, glowing blooms).
    frames.append((25, 7, 18, "Evening", "the day shift clocks off"))
    frames.append((25, 7, 21, "Dusk", "hawkmoths on the wing"))
    frames.append((25, 7, 23, "Night", "moths, bats & moonlit blooms"))
    return frames
