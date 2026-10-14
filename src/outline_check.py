"""
src/outline_check.py — a yard outline that crosses itself is not kept
(V3.19, QF-14, R29).

The outside review drew a bow-tie and the app took it without a word: the
outline was stored, its area worked out by the shoelace formula (which, for a
figure that crosses itself, subtracts one loop from the other and means
nothing), and the planner, the plan's area and every "inside the yard" test
then read that figure as the yard. Nothing a person can draw on a real lot
crosses itself, so a crossing is a slip of the mouse, and the honest answer is
to say so and keep nothing.

:func:`crosses_itself` is the test, Qt-free, by shapely's ``is_simple`` on the
outline's ring (a ring that crosses or touches itself is not simple). The map
sends corners as ``[[lat, lng], ...]``; a repeated corner, which a design read
back from a file carries at its end, is not a crossing. Without shapely (it is
an optional dependency) nothing is refused, as the rest of the app's geometry
degrades without it.

The words follow docs/homeowner/09-words.md: what happened, and what to do.
The map handler (``controllers/map_events.py``) takes a refused outline off the
map, so the map never shows a yard the design does not hold, and a corner
dragged across another side is put back where it was.
"""

from __future__ import annotations

from src.log import get_logger

log = get_logger(__name__)

try:
    from shapely.geometry import LinearRing
    _HAVE_SHAPELY = True
except Exception:                                          # noqa: BLE001
    _HAVE_SHAPELY = False

#: Drawn and closed: nothing was kept, and the way to get an outline is to
#: draw it again (there is no undo for a corner while drawing).
DRAWN_TEXT = ("The outline crosses itself, so it was not kept. Draw it again, "
              "clicking the corners in order around the edge.")

#: A corner dragged across another side: the outline is put back as it was.
EDITED_TEXT = ("That move would make the outline cross itself, so the corner "
               "went back where it was. Drag it to a spot where the sides do "
               "not cross.")


def corners(points) -> list:
    """The distinct corners of ``points`` in order: a corner repeated straight
    after itself, and the first repeated at the end, are dropped."""
    out = []
    for p in points or []:
        q = (float(p[0]), float(p[1]))
        if not out or q != out[-1]:
            out.append(q)
    if len(out) > 1 and out[0] == out[-1]:
        out.pop()
    return out


def crosses_itself(points) -> bool:
    """True when the outline through ``points`` ([[lat, lng], ...]) crosses
    or touches itself. Fewer than three corners is not a crossing (and is not
    an outline either; the map does not close one)."""
    pts = corners(points)
    if len(pts) < 3 or not _HAVE_SHAPELY:
        return False
    try:
        return not LinearRing([(lng, lat) for lat, lng in pts]).is_simple
    except Exception:                                      # noqa: BLE001
        log.exception("could not check an outline of %d corners", len(pts))
        return False


def closed_ring(points) -> list:
    """The GeoJSON ring ([[lng, lat], ...], closed once) for ``points``.
    A design read back from a file sends its corners with the first repeated
    at the end, and until V3.19 every edit closed the ring again, so each one
    added another copy of the first corner to the saved file."""
    pts = corners(points)
    ring = [[lng, lat] for lat, lng in pts]
    return ring + ring[:1]


def tell_refused(parent, *, edited: bool = False) -> None:
    """Say why the outline was not kept, in a box (through
    ``plain_messages``, whose ``_run`` the tests replace)."""
    from src import plain_messages
    log.info("an outline that crosses itself was refused (%s)",
             "edited" if edited else "drawn")
    plain_messages._run(plain_messages._box(
        parent, "Corner put back" if edited else "Outline not kept",
        EDITED_TEXT if edited else DRAWN_TEXT))
