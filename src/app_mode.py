"""
app_mode.py — which door the user came through (V2.43).

Design principle P13 — see docs/DESIGN_PHILOSOPHY.md. A native planting has to
be loved to survive, and nobody loves a tool that opens onto six tabs of
somebody else's profession.

User feedback: *"having someone start with all of the features of the site and
then have a design it and then getting into the 3D view is just a little bit
too complicated at the moment"*, and *"I'd love the design side to be sort of
professional, and that's where you go once you understand the basics and you
wanna design a landscape."*

So some of the start screen's doors open standalone windows: no map, no side
tabs, no site analysis. A landscape you can walk into and plant, the lessons,
and the quizzes. The design app (``MainWindow``) is built behind the start
screen and simply never shown for them.

**Since V3.42 these doors are on the start screen itself**, in its Learn
column beside *Look at an example yard* (the owner: the example, the walk and
the lessons "grouped together in a simple fashion that leads to these
options", with Lessons and Quizzes as separate items). The second screen they
sat behind from V2.43, ``LearnMenu``, is gone, and with it Back. The window
the lessons and quizzes open in is :mod:`src.learn_window`.

Qt-free on purpose: this module decides *routing*, and routing is exactly the
part that must be testable without a display. The screen that shows these
choices (``start_screen``) stays presentation-only.

## Why this is not the toggle V2.42 argued against

``docs/plans/V2.42-first-user-on-the-relationship-web.md`` says plainly:

    **What I would not do:** ship a top-level Design/Learn toggle that hides
    half the app. … A mode split that makes a beginner choose "am I designing
    or learning?" before they have a yard drawn asks a question they cannot
    answer yet.

That objection is about a **mid-session toggle**, and it is still right. This
is a door at boot, re-openable at any time from Help → Start Screen, and the
question it asks is *"do you want to learn about this, or design your yard?"* —
which somebody on day one can answer. The distinction is worth keeping in mind
if a later increment is ever tempted to add a mode switch to the toolbar: that
would be the thing V2.42 refused, and this is not.

## The move that makes Learn cheap

The Learn windows carry a **real project** — the reference landscape from
:mod:`src.reference_ecosystem`, made editable in V2.43. It is a genuine
FeatureCollection of ``plant_feature()`` records, so every design-coupled
teaching tool in the repo binds to it with no rewrite at all, because each one
already takes ``placed_plants`` as a plain argument: ``lesson_track``,
``plant_impact``, ``habitat_score``, ``docent``, ``field_study``,
``chickadee_scenario``, ``scene_wildlife``.

That is also why the walk's key is the one the start screen already used for
that surface (``REFERENCE``): ``onboarding_flow._dispatch`` needed no second
way to say the same thing. The Plant Directory door (``DIRECTORY``) went in
V3.22 (RM-10, the owner's S4): the same plant pages are in Placement › Plants.
"""

from __future__ import annotations

#: What a dismissed or turned-off start screen opens: the design app.
DESIGN = "design"

#: The start screen's Learn doors that open a window of their own. ``WALK`` is
#: deliberately the *same* key the start screen used for this surface before
#: the Learn menu existed (``start_screen.REFERENCE``).
WALK = "reference"        # the walkable, editable reference landscape
LESSONS = "lessons"       # the lessons, over the walk you planted in
QUIZZES = "quizzes"       # Field Study's quizzes, by topic (F208)

#: Choices that live entirely in their own windows and must NOT bring up the
#: MainWindow. This set is the whole mechanical content of the split: the
#: simplification the feedback asked for is precisely "the beginner does not
#: meet the map". *Look at an example yard* sits beside them on the screen
#: and is not one of them: the example is a design, on the map.
_LEARN_ONLY = frozenset({WALK, LESSONS, QUIZZES})


def is_learn_choice(choice: str) -> bool:
    """Whether this choice is handled by a standalone Learn window."""
    return choice in _LEARN_ONLY


def opens_main_window(choice: str) -> bool:
    """Whether acting on ``choice`` should show the MainWindow.

    ``""`` — the start screen dismissed, or turned off — is *not* a Learn
    choice: it has always meant "start me on the blank map", and quietly
    turning it into "show nothing" would leave the user with no app.
    """
    return not is_learn_choice(choice)
