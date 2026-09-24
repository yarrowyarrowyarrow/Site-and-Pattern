"""
site_fit.py — has this plant been recorded near this yard? (F154, V2.85)

Design principle P9 — see docs/DESIGN_PHILOSOPHY.md.

The question a recommendation has to answer
-------------------------------------------
Until V2.85 the design generator answered *"does this plant fit the site?"* at
the scale of an ecoregion: at least three occurrence records anywhere in the
region, and Aspen Parkland runs from Calgary to Winnipeg. An Edmonton yard was
offered Bur Oak on the strength of Saskatchewan parkland records, Broomweed
from the dry south, and Alpine Aster from the foothills edge -- each honestly
"recorded in Aspen Parkland", none of them a plant of this yard.

The catalogue already knew better. V2.79 built a 0.25-degree occupancy grid of
the same records (``data/plant_ranges.json``, drawn on every species page of
the website), and nothing on the design side read it. This module is the one
place that does, so the generator, its critic and anything later ask one
question in one way.

Two answers, both deliberately modest
-------------------------------------
* :func:`province_at` -- which province the pin is in, because nativity is
  recorded per province (VASCAN, since V2.80) and the generator was filtering
  on the Alberta flag wherever the yard was. The Alberta-Saskatchewan border
  is the 110th meridian from the 49th parallel to the 60th, which the survey
  fixed exactly; outside the two provinces the answer is ``""``.
* :func:`locality` -- how near the nearest records are: ``"here"`` (the yard's
  own grid square or one of the eight around it, roughly 80 by 50 km at
  Edmonton's latitude), ``"near"`` (the next ring out), ``"elsewhere"`` (only
  further away) or ``"unrecorded"`` (no grid entry at all).

**A ranking signal, never a filter.** Records follow collectors, and an empty
square is unsurveyed as often as it is unoccupied (the website's `/method/`
page says the same in plain words). So a plant recorded near the yard is
*preferred* over one recorded only elsewhere, and nothing is removed for
lacking records: ``"unrecorded"`` ranks level with ``"elsewhere"``, not below
it, because under-collected and absent look identical at this resolution.
"""

from __future__ import annotations

import functools
import json
import math

from src.species_range import CELL_DEG, parse_document

#: The Alberta-Saskatchewan border, west of which is Alberta (degrees east).
AB_SK_BORDER_LNG = -110.0

#: Rings of grid squares around the yard's own. Ring 1 is the 3x3 block (the
#: yard's square and the eight touching it); ring 2 is the 5x5 block.
HERE_RING = 1
NEAR_RING = 2

#: How strongly each answer is preferred when ranking candidates. "unrecorded"
#: sits level with "elsewhere" on purpose -- see the module docstring.
LOCALITY_RANK = {"here": 2, "near": 1, "elsewhere": 0, "unrecorded": 0}


def province_at(lat: float, lng: float) -> str:
    """``"AB"``, ``"SK"`` or ``""`` for a coordinate.

    Inside the catalogue's subject area the 110th meridian decides; anywhere
    else there is no province this catalogue can speak for, and a caller should
    fall back to what it did before rather than guess.
    """
    try:
        lat, lng = float(lat), float(lng)
    except (TypeError, ValueError):
        return ""
    from src.subject_area import in_subject_provinces        # noqa: PLC0415
    if not in_subject_provinces(lat, lng):
        return ""
    return "AB" if lng < AB_SK_BORDER_LNG else "SK"


def _index(value: float) -> int:
    """A grid coordinate as an integer square index, so neighbours are found by
    arithmetic rather than by comparing floats."""
    return math.floor(value / CELL_DEG + 1e-9)


@functools.lru_cache(maxsize=1)
def _grid() -> dict:
    """``{scientific name: {(lat index, lng index): records}}``, loaded once."""
    from src.resources import resource_path                  # noqa: PLC0415
    try:
        with open(resource_path("data", "plant_ranges.json"),
                  encoding="utf-8") as fh:
            doc = parse_document(json.load(fh))
    except (OSError, ValueError):
        return {}
    return {name: {(_index(la), _index(ln)): n for la, ln, n in cells}
            for name, cells in doc.items()}


def records_near(scientific_name: str, lat: float, lng: float,
                 ring: int = HERE_RING) -> int:
    """Records in the square holding ``(lat, lng)`` and ``ring`` squares around
    it. ``0`` when the species has no grid entry or none fall that close."""
    cells = _grid().get((scientific_name or "").strip())
    if not cells:
        return 0
    i, j = _index(lat), _index(lng)
    return sum(cells.get((i + di, j + dj), 0)
               for di in range(-ring, ring + 1)
               for dj in range(-ring, ring + 1))


def locality(scientific_name: str, lat: float, lng: float) -> str:
    """``"here"``, ``"near"``, ``"elsewhere"`` or ``"unrecorded"``."""
    if not _grid().get((scientific_name or "").strip()):
        return "unrecorded"
    if records_near(scientific_name, lat, lng, HERE_RING):
        return "here"
    if records_near(scientific_name, lat, lng, NEAR_RING):
        return "near"
    return "elsewhere"


def locality_rank(scientific_name: str, lat, lng) -> int:
    """:data:`LOCALITY_RANK` for a species at a site, or ``0`` with no site."""
    if lat is None or lng is None:
        return 0
    return LOCALITY_RANK[locality(scientific_name, lat, lng)]
