"""
placement_arming.py — what the map is armed with, said in words (V2.37, V2.98).

Design principle P5 — see docs/DESIGN_PHILOSOPHY.md

Two panels arm the same map: the plant browser and the community library. From
V2.37 *selecting* was the arming gesture (a tester kept planting "the last thing"
because arming was a separate act the map gave no sign of), which meant looking
armed the map too. Since V2.99 a Place action arms it and selecting only looks;
once placing, choosing another plant switches to it, which is what that tester
needed (``src/place_action.py``).

Until V2.98 the answer to "what am I about to place?" was a chip on each panel's
Place button, "● Placing: Wild Bergamot · Row", in a section that was usually
collapsed. It is now the first line of the placement bar over the map
(``src/placement_bar.py``), where the click will land, and it says what the click
will *do*: "Placing Wild Bergamot in a row. Click the start point, then the end
point."

The wording lives here, Qt-free, so both panels read the same and a test can
check every case without a display. *When* to arm stays with each panel (a plant
row vs a community tree node); the debounce that re-arms after a setting moves
is shared, below, so the two panels cannot feel different.

Qt is imported lazily inside :func:`rearm_timer`, so the module stays importable
headless.
"""

from __future__ import annotations

# How long to wait after a placement parameter moves before re-arming the map.
# Every re-arm is a round trip to the map, and these are spinners: holding an
# arrow emits per tick. Long enough to coalesce a drag, short enough that
# letting go feels immediate.
REARM_DELAY_MS = 150

# What each pattern does with the subject, and what the next clicks must be.
_HOW = {
    "row": ("Placing {subject} in a row",
            "Click the start point, then the end point."),
    "grid": ("Placing {subject} in a grid",
             "Click one corner, then the opposite corner."),
    "circle": ("Placing {subject} in a circle",
               "Click the centre, then a point on the edge."),
    "fill": ("Filling an area with {subject}",
             "Click around the area, then double-click to finish."),
}


def describe(source: str, kind: str, what: str = "", *, qty: int = 1,
             mix: int = 0) -> tuple[str, str]:
    """``(headline, instruction)`` for the placement bar.

    ``source`` is ``"plants"`` or ``"communities"``; ``what`` names the plant or
    community armed; ``mix`` is the number of species (or communities) in the
    mix being placed, 0 when none. A mix is only placed by the multi-cell
    patterns and Fill: in Single the map places ``what`` itself, and says so,
    where the V2.37 chip said "the mix" while the map planted the selected
    plant.
    """
    what = (what or "").strip() or "the selection"
    kind = kind if kind in _HOW or kind == "single" else "single"
    noun = "plant" if source == "plants" else "community"
    subject = what
    if mix >= 2 and kind != "single":
        subject = f"your {mix}-{noun} mix"
    if kind == "single":
        # The map stays armed after a click, which the review found nothing
        # said (finding 8); the bar says so now, for the modes that repeat
        # one click at a time.
        if source == "communities":
            return (f"Placing {what}",
                    "Click the map where its centre should go. "
                    "Each click places another.")
        if qty > 1:
            return (f"Placing {what}, {qty} at a time",
                    f"Click the map to place a cluster of {qty}. "
                    f"Each click places another.")
        return (f"Placing {what}",
                "Click the map to place it. Each click places another.")
    headline, instruction = _HOW[kind]
    return headline.format(subject=subject), instruction


def rearm_timer(owner, on_timeout):
    """A single-shot debounce timer for re-arming, owned by ``owner``.

    Here rather than in each panel so both wait the same amount — two panels
    arming the same map at different rates would be a difference the user can
    feel and nobody chose.

    The timer only *starts* while the panel is armed (:func:`request_rearm`),
    ``set_armed(False)`` stops it, and ``on_timeout`` must check ``_armed``
    again, because a stand-down and the timeout can land in the same turn of
    the event loop. Until V2.98 nothing checked at all, so a Count changed just
    before Esc re-armed the map 150 ms after you had stopped placing.

    ``on_timeout`` is connected as given, and should be a bound method: PyQt
    ties that connection to the object's life. A closure here holds the panel
    alive through its own timer, which is how a first draft of this check left
    dead tests' panels firing into later ones.
    """
    from PyQt6.QtCore import QTimer          # noqa: PLC0415 — keep Qt lazy
    timer = QTimer(owner)
    timer.setSingleShot(True)
    timer.setInterval(REARM_DELAY_MS)
    timer.timeout.connect(on_timeout)
    return timer


def request_rearm(panel) -> None:
    """A placement parameter moved: re-arm, once the user stops moving it.

    Does nothing while the map is not armed — fiddling with the controls before
    choosing a plant must not seize the map.
    """
    if not getattr(panel, "_armed", False):
        return
    panel._rearm_timer.start()
