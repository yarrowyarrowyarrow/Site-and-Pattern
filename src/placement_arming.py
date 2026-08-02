"""
placement_arming.py — the shared "the map is armed with X" chip (V2.37).

Design principle P5 — see docs/DESIGN_PHILOSOPHY.md

Two panels arm the same map: the plant browser and the community library. Since
V2.37 *selecting* is the arming gesture rather than pressing a button — a tester
kept planting "the last thing" because arming was a separate act the map gave no
sign of — which leaves the Place button as the only thing on screen answering
"what am I about to place?".

That answer has to look identical wherever it appears, so the styling and the
wording live here rather than in each panel. Both panels keep their own
``_auto_arm``: *when* to arm is panel-specific (a plant row vs a community tree
node), but *how the armed state reads* is not.

Qt is imported lazily inside :func:`apply_chip` so the module stays importable
headless, like the other shared UI helpers.
"""

from __future__ import annotations

# Amber, not green: green is this app's "do the thing" colour, and an armed map
# is a *state*, not an action waiting to be taken. Left-aligned because the text
# is a readout that changes length, and centred text that jumps around reads as
# a different control each time.
ARMED_STYLE = """
QPushButton {
    background: #4a3a12;
    color: #ffe082;
    border: 1px solid #ffb300;
    border-radius: 4px;
    padding: 7px 12px;
    font-weight: bold;
    font-size: 13px;
    text-align: left;
}
QPushButton:hover    { background: #5a4718; border-color: #ffca28; }
QPushButton:pressed  { background: #3a2e0e; }
"""

# Pattern kind → the word shown in the chip.
PATTERN_WORDS = {"single": "Single", "row": "Row", "grid": "Grid",
                 "circle": "Circle", "fill": "Fill Area"}

ARMED_TOOLTIP = ("The map is armed — click it to place.\n"
                 "Click here (or press Esc) to stop placing.")


# How long to wait after a placement parameter moves before re-arming the map.
# Every re-arm is a round trip to the map, and these are spinners and a slider:
# holding an arrow emits per tick. Long enough to coalesce a drag, short enough
# that letting go feels immediate.
REARM_DELAY_MS = 150


def rearm_timer(owner, on_timeout):
    """A single-shot debounce timer for re-arming, owned by ``owner``.

    Here rather than in each panel so both wait the same amount — two panels
    arming the same map at different rates would be a difference the user can
    feel and nobody chose.
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


def chip_text(what: str, kind: str = "") -> str:
    """"● Placing: Wild Bergamot · Row" — what is armed, and how it will land."""
    word = PATTERN_WORDS.get(kind, "")
    return f"● Placing: {what or 'selection'}" + (f" · {word}" if word else "")


def apply_chip(button, *, armed: bool, what: str = "", kind: str = "",
               idle_text: str = "Place on Map", idle_style: str = "",
               idle_tooltip: str = "") -> None:
    """Render ``button`` as the armed status chip, or back to its idle state.

    Never raises: a mis-rendered button must not be able to take down the panel
    that arms placement.
    """
    try:
        if armed:
            button.setText(chip_text(what, kind))
            button.setStyleSheet(ARMED_STYLE)
            button.setToolTip(ARMED_TOOLTIP)
        else:
            button.setText(idle_text)
            button.setStyleSheet(idle_style)
            button.setToolTip(idle_tooltip)
    except RuntimeError:
        pass        # the widget went away underneath us
