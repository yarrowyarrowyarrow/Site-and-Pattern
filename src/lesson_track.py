"""
lesson_track.py — the guided lesson track (F53).

The app is full of teaching moments — the ecological-role labels, the food-web
score, the succession timeline, the honest ranges — but they're scattered across
tabs. This module stitches four of them into a short **course narrated against
the user's OWN project**, in the order a native-plant gardener actually learns:

  1. Keystone plants do most of the work.
  2. Closing the food web (host plants → caterpillars → birds).
  3. Succession over time (design the trajectory, not the install day).
  4. Ranges, not certainties (ship confidence, never false precision).

Each step pairs a one-paragraph lesson with a **"your design" readout** computed
live from the same surfaces the rest of the app uses, and a status
(good / attention / empty) so the stepper can show progress.

Design principle P5 (perception is constructed — a guided sequence builds the
model the tool assumes) and P7 (generalist knowledge — the course crosses
ecology, design and time). See docs/DESIGN_PHILOSOPHY.md.

Qt-free and dependency-injectable: the stepper panel renders it, the scripting
layer and the tests share one definition.
"""

from __future__ import annotations

from typing import Callable, Optional

# A plant is a meaningful caterpillar "keystone" when it hosts at least this many
# lepidoptera species (Tallamy's keystone genera host far more; this is the floor
# for calling a plant a real caterpillar factory in this data set).
_KEYSTONE_FLOOR = 3


def _distinct_rows(placed_plants: list[dict],
                   get_plant: Optional[Callable]) -> list[dict]:
    """Full plant rows for each distinct placed species (for role + traits)."""
    if get_plant is None:
        from src.db.plants import get_plant as _gp
        get_plant = _gp
    rows: dict = {}
    for p in placed_plants or []:
        pid = p.get("plant_id")
        if pid is None or pid in rows:
            continue
        row = get_plant(pid) or dict(p)
        row.setdefault("common_name", p.get("common_name") or f"plant {pid}")
        rows[pid] = row
    return list(rows.values())


def build_lesson_track(placed_plants: Optional[list[dict]],
                       structures: Optional[list[dict]] = None, *,
                       score=None,
                       get_plant: Optional[Callable] = None,
                       get_keystone: Optional[Callable] = None) -> dict:
    """Return the four-step guided lesson track for the live design.

    ``score`` is an optional precomputed ``HabitatScore`` (else it is computed).
    ``get_plant`` / ``get_keystone`` are injectable for tests. See the module
    docstring for the result shape.
    """
    rows = _distinct_rows(placed_plants or [], get_plant)
    steps = [
        _step_keystone(rows, get_keystone),
        _step_food_web(placed_plants or [], structures or [], score),
        _step_succession(rows),
        _step_ranges(rows),
    ]
    return {"steps": steps, "n_steps": len(steps)}


def _step_keystone(rows: list[dict], get_keystone: Optional[Callable]) -> dict:
    if get_keystone is None:
        from src.db.fauna import keystone_rank_lepidoptera as get_keystone
    ranked = []
    for r in rows:
        try:
            k = int(get_keystone(r.get("id") or r.get("plant_id")) or 0)
        except Exception:      # noqa: BLE001
            k = 0
        if k > 0:
            ranked.append((k, r.get("common_name") or "a plant"))
    ranked.sort(reverse=True)
    strong = [n for k, n in ranked if k >= _KEYSTONE_FLOOR]
    lesson = (
        "A handful of native plant genera support the overwhelming majority of "
        "caterpillar species — Doug Tallamy calls them keystone plants. Willows, "
        "poplars/aspen, native cherries, asters and goldenrods each host dozens "
        "to hundreds of species, while most ornamentals host almost none. Getting "
        "a few keystones right matters more than adding many minor players.")
    if not rows:
        return _mk("keystone", "Keystone plants do most of the work", lesson,
                   "No plants placed yet — start with one keystone host.", "empty")
    if strong:
        top = ", ".join(strong[:3])
        readout = (f"Your design has {len(strong)} keystone host "
                   f"plant{'s' if len(strong) != 1 else ''} "
                   f"(≥{_KEYSTONE_FLOOR} caterpillar species each): {top}. "
                   f"These are doing the heavy lifting.")
        status = "good"
    elif ranked:
        top = ranked[0][1]
        readout = (f"You have host plants ({top} and others), but none is a heavy "
                   f"keystone yet. Adding a willow, aspen, native cherry, aster or "
                   f"goldenrod would multiply the caterpillars.")
        status = "attention"
    else:
        readout = ("None of your placed plants is a documented caterpillar host. "
                   "A single keystone would change that at once.")
        status = "attention"
    return _mk("keystone", "Keystone plants do most of the work", lesson,
               readout, status)


def _step_food_web(placed_plants: list[dict], structures: list[dict],
                   score) -> dict:
    if score is None:
        try:
            from src.habitat_score import compute_habitat_score
            score = compute_habitat_score(placed_plants, structures)
        except Exception:      # noqa: BLE001
            score = None
    fw = (score.food_web if score else {}) or {}
    status_code = fw.get("status", "empty")
    lesson = (
        "A yard becomes habitat when it feeds a whole chain, not one link. Native "
        "host plants grow caterpillars; caterpillars feed nesting birds; berries "
        "and seeds carry wildlife through the rest of the year. A design that "
        "grows caterpillars but offers birds nothing to eat — or draws birds with "
        "no caterpillars to raise their young on — has a broken chain.")
    n_cat = fw.get("n_caterpillars", 0)
    n_bird = fw.get("n_birds", 0)
    if status_code == "complete":
        readout = (f"Your food web is closed: {n_cat} caterpillar species with "
                   f"{n_bird} bird species to eat them. This is the whole point — "
                   f"host plants feeding the birds that feed on them.")
        status = "good"
    elif status_code == "no_birds":
        readout = (f"You grow {n_cat} caterpillar species, but nothing draws the "
                   f"birds that eat them. Add a berry- or seed-bearing native to "
                   f"close the chain.")
        status = "attention"
    elif status_code == "no_hosts":
        readout = ("You have bird food, but no caterpillar host plants — so the "
                   "birds have nothing to raise their young on. Add a keystone host.")
        status = "attention"
    else:
        readout = ("No food web yet. Place native host plants and a berry/seed "
                   "source and watch the chain form.")
        status = "empty"
    return _mk("food_web", "Closing the food web", lesson, readout, status)


def _step_succession(rows: list[dict]) -> dict:
    from src.succession import successional_role
    roles = {"pioneer": [], "mid": [], "climax": []}
    for r in rows:
        try:
            role = successional_role(r)
        except Exception:      # noqa: BLE001
            role = "mid"
        roles.get(role, roles["mid"]).append(r.get("common_name") or "a plant")
    lesson = (
        "A landscape is a process, not a product. Pioneers — fast, sun-loving, "
        "short-lived — stabilise bare ground and then give way to the longer-lived "
        "climax species that rise up through them. Designing for a single moment is "
        "why so many plantings look right on install day and wrong five years on. "
        "Design the trajectory: some plants for now, some for the canopy to come.")
    np, nm, nc = len(roles["pioneer"]), len(roles["mid"]), len(roles["climax"])
    if not rows:
        return _mk("succession", "Succession over time", lesson,
                   "No plants placed yet — plan for both now and later.", "empty")
    if np and nc:
        readout = (f"Good spread across time: {np} pioneer, {nm} mid, {nc} climax "
                   f"species. Pioneers cover the ground now; the climax layer takes "
                   f"over as they fade.")
        status = "good"
    else:
        have = ("all pioneers/early species" if np and not nc else
                "all climax/long-lived species" if nc and not np else
                "all mid-succession species")
        readout = (f"Your design is {have}. A trajectory needs both — add "
                   f"{'a long-lived climax anchor' if not nc else 'fast pioneers to cover the ground now'} "
                   f"so year 1 and year 15 both read well.")
        status = "attention"
    return _mk("succession", "Succession over time", lesson, readout, status)


def _step_ranges(rows: list[dict]) -> dict:
    lesson = (
        "Ecology runs on ranges, not point values. A brood needs roughly "
        "6,000–9,000 caterpillars; a plant blooms 'around' a window that shifts "
        "with the year; a score is an estimate, not a measurement. This tool ships "
        "ranges and confidence on purpose — false precision would be a lie, and it "
        "would stop you from going outside to see what actually happens. Treat "
        "every number here as a hypothesis to test on the ground.")
    if not rows:
        readout = ("Nothing to estimate yet — but when you place plants, every "
                   "figure the app shows you will be a range to verify, not a fact.")
        status = "empty"
    else:
        readout = ("Notice where the app hedges — the caterpillar tally is a band, "
                   "bloom windows say 'around', the habitat score is an estimate. "
                   "That honesty is the point: go check the real site against it.")
        status = "good"
    return _mk("ranges", "Ranges, not certainties", lesson, readout, status)


def _mk(step_id: str, title: str, lesson: str, your_design: str,
        status: str) -> dict:
    return {"id": step_id, "title": title, "lesson": lesson,
            "your_design": your_design, "status": status}
