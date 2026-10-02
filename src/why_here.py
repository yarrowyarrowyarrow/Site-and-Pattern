"""
why_here.py — why a generated plant is where it is, written onto the plant
(F19, V3.05).

Design principle P5 — see docs/DESIGN_PHILOSOPHY.md.

The generator scores every open cell for each plant and, until V3.05, kept none
of it: a generated design could not say why its milkweed was by the fence. Every
rule that places a plant now leaves its reason on the plant's feature
(``why_here``, a list of short sentences, which ``project_store`` carries), and
the plant's page shows them first when the plant is clicked on the map.

Most plants go on the cell scored best for them and say why in that score's
terms (``placement_score.explain_cell_for_plant``; with no terrain or shade for
the site, ``placement_score.NO_SITE_DATA_WHY``). The rest are placed by a rule
and name it, in the words below. A plant placed by hand has no reason written,
and the page then shows none: absent is not "for no reason".

Measured on one generated design with a tree, a vine, a mixed stand and a
community: 71 of 102 plants carried a reason when only scored cells wrote one,
108 of 108 once the rules below did, the design review's addition included.
"""

from __future__ import annotations

#: A vine seated at the foot of a host the generator planted (F181).
VINE_SEAT = "At the foot of a tree or shrub planted for it to climb"
#: A plant mix: one stand, its ground scored for its first member.
MIX = "Part of a mixed stand"
MIX_OTHER = "Part of a mixed stand, on ground chosen for {first}"
#: A community placed whole, where its footprint fits inside the boundary.
COMMUNITY = "Part of the {name} community, set where all of it fits"
COMMUNITY_MEMBER = "Part of the {name} community"
#: What the design review added after the main pass (``design_critic``).
REVIEW = "Added when the design was reviewed: {why}"
#: Added so a chosen animal has a plant, or a chosen goal is met.
FOR_ANIMAL = "Added so the design has a plant for the {name}"
FOR_GOAL = "Added so the design meets the goals you chose"
#: A plant that needs standing water, seated in a pond (F185).
POND = "In the pond: it grows in standing water"
BARE_POND = "Planted so the pond was not left bare"


def stamp(project, n: int, why) -> None:
    """Write ``why`` onto the last ``n`` plant features placed. Empty
    reasons write nothing."""
    stamp_each(project, [why] * max(0, int(n)))


def stamp_each(project, whys: list) -> None:
    """``whys[i]`` onto the i-th of the last ``len(whys)`` features placed."""
    if not whys:
        return
    try:
        features = project.as_dict()["features"]
    except (AttributeError, KeyError, TypeError):
        return
    for f, why in zip(features[-len(whys):], whys):
        props = f.get("properties", {})
        if why and props.get("element_type") == "plant":
            props["why_here"] = list(why)


def feature_count(project) -> int:
    """How many features ``project`` holds, to stamp what a call added."""
    try:
        return len(project.as_dict()["features"])
    except (AttributeError, KeyError, TypeError):
        return 0
