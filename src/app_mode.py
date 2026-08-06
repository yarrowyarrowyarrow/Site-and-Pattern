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

So the app has two front doors:

  **Learn** — standalone windows, no map, no side tabs, no site analysis. A
  landscape you can walk into and plant, the catalogue as a reference work, and
  the lessons. This is where a beginner lands.
  **Design** — today's MainWindow, entirely unchanged, for when you know what
  you are doing.

Qt-free on purpose: this module decides *routing*, and routing is exactly the
part that must be testable without a display. The screens that show these
choices (``start_screen``, ``learn_menu``) stay presentation-only, the way
``start_screen`` has been since V2.41.

## Why this is not the toggle V2.42 argued against

``docs/plans/V2.42-first-user-on-the-relationship-web.md`` says plainly:

    **What I would not do:** ship a top-level Design/Learn toggle that hides
    half the app. … A mode split that makes a beginner choose "am I designing
    or learning?" before they have a yard drawn asks a question they cannot
    answer yet.

That objection is about a **mid-session toggle**, and it is still right. This
is a door at boot, re-openable at any time from Help → Welcome, and the
question it asks is *"do you want to learn about this, or design your yard?"* —
which somebody on day one can answer. The distinction is worth keeping in mind
if a later increment is ever tempted to add a mode switch to the toolbar: that
would be the thing V2.42 refused, and this is not.

## The move that makes Learn cheap

Learn mode carries a **real project** — the reference landscape from
:mod:`src.reference_ecosystem`, made editable in V2.43. It is a genuine
FeatureCollection of ``plant_feature()`` records, so every design-coupled
teaching tool in the repo binds to it with no rewrite at all, because each one
already takes ``placed_plants`` as a plain argument: ``lesson_track``,
``plant_impact``, ``habitat_score``, ``docent``, ``field_study``,
``chickadee_scenario``, ``scene_wildlife``.

That is also why the Learn doors mostly return the choice keys the start screen
already used (``REFERENCE``, ``DIRECTORY``): they open surfaces that existed,
and ``onboarding_flow._dispatch`` needed no new branch for them.
"""

from __future__ import annotations

#: The two front doors, as returned by the start screen.
LEARN = "learn"
DESIGN = "design"

#: Rows on the Learn menu. ``WALK`` and ``GUIDE`` are deliberately the *same*
#: keys the start screen used for these surfaces before they moved in here, so
#: the dispatch table did not have to grow a second way to say the same thing.
WALK = "reference"        # the walkable, editable reference landscape
GUIDE = "directory"       # the catalogue as a reference work (F90)
STUDIO = "studio"         # lessons + field study, over the sandbox
BACK = "back"             # return to the start screen

#: ``(key, icon, title)`` — the Learn menu, in the order a person needs it: go
#: somewhere and look at it, look something up, then be taught about it. The
#: note beside each row is computed (see :func:`learn_notes`), because a fact
#: about your own situation beats a description of the button — the V2.41
#: start-screen lesson, applied to its second screen.
LEARN_DOORS = (
    (WALK, "🌲", "Walk a wild landscape"),
    (GUIDE, "🔎", "Field Guide"),
    (STUDIO, "📚", "Lessons & Field Study"),
)

#: Choices that live entirely in Learn mode and must NOT bring up the
#: MainWindow. This set is the whole mechanical content of the mode split: the
#: simplification the feedback asked for is precisely "the beginner does not
#: meet the map".
_LEARN_ONLY = frozenset({WALK, GUIDE, STUDIO})


def is_learn_choice(choice: str) -> bool:
    """Whether this choice is handled by a standalone Learn-mode window."""
    return choice in _LEARN_ONLY


def opens_main_window(choice: str) -> bool:
    """Whether acting on ``choice`` should show the MainWindow.

    ``""`` — the start screen dismissed, or turned off — is *not* a Learn
    choice: it has always meant "start me on the blank map", and quietly
    turning it into "show nothing" would leave the user with no app.
    """
    return not is_learn_choice(choice)


def learn_notes(discovery_line: str = "", communities: int = 0,
                sandbox: str = "") -> dict:
    """The note column for each Learn door — one short fact per row.

    Kept here rather than in the widget so the wording is testable without a
    display, and so the five-word ceiling the start-screen tests enforce is
    checkable in one place. Every string must survive its inputs being empty:
    this runs before any project exists.
    """
    if communities:
        walk = f"{communities} communities"
    else:
        walk = "plant and pull, live"
    if sandbox:
        walk = f"continue in {sandbox}"
    return {
        WALK: walk,
        GUIDE: discovery_line or "look up any native species",
        STUDIO: "about the landscape you're in",
    }
