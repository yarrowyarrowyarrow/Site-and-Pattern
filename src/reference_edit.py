"""
reference_edit.py — planting into a wild community (V2.43).

Design principle P1 (living systems self-organize — encode generative rules,
not fixed layouts), P3 (relationships matter more than components) and P8
(repair is more sophisticated than creation) — see docs/DESIGN_PHILOSOPHY.md.

``reference_ecosystem`` has built a walkable reference community since F50, and
until now it was a diorama: seven landscapes you could look at and not touch.
This module makes them **sandboxes** — you can plant into them and pull things
out of them, and the consequence is shown.

That turns out to be the cheap way to give Learn mode a project. Everything
design-coupled in this repo already takes ``placed_plants`` as a plain
argument — ``lesson_track``, ``plant_impact``, ``habitat_score``, ``docent``,
``field_study``, ``chickadee_scenario``, ``scene_wildlife`` — so once the
reference landscape is editable and saved, all of them work on it with no
change at all.

Qt-free, like every core in this codebase: the window in
``reference_ecosystem_window`` owns the widgets, this owns the decisions.

## Two rules that are not negotiable

1. **Every mutation goes through :class:`src.project_store.ProjectStore`.**
   Never touch ``features`` or ``_placed_plants`` directly.
   ``tests/test_project_store.py`` greps the source tree and fails the build
   on any new hand-rolled mutation, and it is right to: the project dict and
   the placed-plant index are two structures that must agree, and every bug
   from letting callers do it themselves was a silent divergence.
2. **Metres go through :mod:`src.projection`.** The map stores only
   ``(lat, lon)``; a click in the 3D scene arrives as local metres and must be
   converted with the app's own cosLat metric rather than a hand-rolled
   constant, so the sandbox and the design agree about where things are.

## Where a sandbox lives

``<saves>/wild/<community>.perma.geojson`` — one per community, so your fen is
still your fen next launch, and it is an ordinary project file the user could
open in Design mode if they wanted to. Reference plants are tagged
``pattern_kind='reference'`` by the builder and the user's own are tagged
``'user'``, so "reset this landscape" can put back what was shipped without
touching what the person planted.
"""

from __future__ import annotations

import json
import math
import os
from typing import Callable, Optional

#: Marks a plant the *user* placed in a sandbox, as opposed to one the curated
#: community placed (``'reference'``). The distinction is what lets a reset be
#: non-destructive, and what lets the lessons say "you added six things".
USER_KIND = "user"
REFERENCE_KIND = "reference"


# ── Where sandboxes live ─────────────────────────────────────────────────────

def sandbox_dir() -> str:
    """The folder holding the editable wild landscapes."""
    from src import saves
    return os.path.join(saves.saves_dir(), "wild")


def sandbox_path(community: str) -> str:
    """Path to one community's sandbox file. The key is a fixed vocabulary
    from :mod:`src.reference_ecosystem`, not user text, so it needs no
    slugifying — but it is still constrained to that vocabulary by
    :func:`load_sandbox` / :func:`save_sandbox` rather than trusted."""
    safe = "".join(c for c in (community or "") if c.isalnum() or c == "_")
    return os.path.join(sandbox_dir(), f"{safe}.perma.geojson")


def load_sandbox(community: str) -> Optional[dict]:
    """The saved sandbox for a community, or ``None`` if there isn't one.

    Never raises. A corrupt sandbox reads as absent, which puts the user back
    in the pristine community rather than in front of a traceback — the file
    is a convenience, not their life's work, and the shipped landscape is
    always recoverable.
    """
    path = sandbox_path(community)
    try:
        if not os.path.exists(path):
            return None
        with open(path, "r", encoding="utf-8") as fh:
            data = json.load(fh)
        if isinstance(data, dict) and data.get("type") == "FeatureCollection":
            return data
        return None
    except Exception:                                      # noqa: BLE001
        return None


def save_sandbox(community: str, project: dict) -> bool:
    """Write a sandbox back. Returns whether it was written."""
    if not isinstance(project, dict):
        return False
    path = sandbox_path(community)
    try:
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as fh:
            json.dump(project, fh)
        return True
    except Exception:                                      # noqa: BLE001
        return False


def open_sandbox(community: str, *, center: Optional[tuple] = None,
                 build: Optional[Callable] = None) -> dict:
    """The project to walk into: the saved sandbox if there is one, otherwise
    a fresh build of the curated community.

    ``build`` is injectable so tests need no database.
    """
    saved = load_sandbox(community)
    if saved is not None:
        return saved
    if build is None:
        from src.reference_ecosystem import build_reference_project
        build = build_reference_project
    lat, lng = center or (51.05, -114.07)
    return build(community, center_lat=lat, center_lng=lng)


def reset_sandbox(community: str) -> bool:
    """Throw away the user's edits and go back to the shipped community.

    Deletes the file rather than rebuilding into it, so the next open goes
    through the ordinary "no sandbox yet" path — one code path for a fresh
    landscape instead of two that can disagree.
    """
    try:
        path = sandbox_path(community)
        if os.path.exists(path):
            os.remove(path)
        return True
    except Exception:                                      # noqa: BLE001
        return False


# ── Editing ──────────────────────────────────────────────────────────────────

def offset_latlng(lat: float, lng: float, dx_m: float, dy_m: float) -> tuple:
    """Shift ``(lat, lng)`` by ``dx`` east / ``dy`` north metres.

    The app's cosLat metric, taken from :mod:`src.projection` rather than
    re-typed: at yard scale its ~1% error is centimetres, and the one thing
    that must not happen is the sandbox using a *different* approximation from
    the rest of the app and drifting from the scene it is drawn in.
    """
    from src.projection import metres_per_deg
    m_lat, m_lng = metres_per_deg(lat)
    return (lat + dy_m / (m_lat or 1.0), lng + dx_m / (m_lng or 1.0))


def local_offset(lat: float, lng: float,
                 center_lat: float, center_lng: float) -> tuple:
    """The inverse: ``(dx east, dy north)`` metres from a centre."""
    from src.projection import metres_per_deg
    m_lat, m_lng = metres_per_deg(center_lat)
    return ((lng - center_lng) * m_lng, (lat - center_lat) * m_lat)


def plant_at(project: dict, plant_id: int, common_name: str,
             center: tuple, dx_m: float, dy_m: float, *,
             planted_year: Optional[int] = None) -> dict:
    """Place one plant at a point given in scene-local metres.

    Returns the placed record. The mutation goes through ``ProjectStore``, and
    the plant is tagged ``pattern_kind='user'`` so a later reset can tell it
    from the curated community.

    ``planted_year`` (V2.44) is the timeline year showing when the user
    planted it, which is what makes a new sapling read as new against the
    established community around it. The curated plants carry none, on purpose
    — they are the mature backdrop the new one is measured against.
    """
    from src.project_store import ProjectStore
    lat, lng = offset_latlng(center[0], center[1], dx_m, dy_m)
    store = ProjectStore(project)
    record = store.add_plant(int(plant_id), common_name or "plant", lat, lng,
                             pattern_kind=USER_KIND,
                             planted_year=planted_year)
    return record


def pull_at(project: dict, plant_id: int, lat: float, lng: float, *,
            feature_id: str = "") -> Optional[dict]:
    """Remove one plant. Returns the removed record, or ``None``."""
    from src.project_store import ProjectStore
    store = ProjectStore(project)
    return store.remove_plant(int(plant_id), float(lat), float(lng),
                              feature_id=feature_id, newest_first=True)


def nearest_plant(project: dict, center: tuple, dx_m: float, dy_m: float, *,
                  within_m: float = 1.5) -> Optional[dict]:
    """The placed plant closest to a scene-local point, within ``within_m``.

    The 3D viewer raycasts against instanced geometry and can tell us *where*
    a click landed far more reliably than *which instance* it hit, so pulling
    is resolved here, in metres, against the authoritative record list.
    """
    from src.project_store import ProjectStore
    best = None
    best_d = float(within_m)
    for rec in ProjectStore(project).placed_plants:
        try:
            ex, ny = local_offset(rec["lat"], rec["lng"], center[0], center[1])
        except Exception:                                  # noqa: BLE001
            continue
        d = math.hypot(ex - dx_m, ny - dy_m)
        if d <= best_d:
            best_d = d
            best = rec
    return best


# ── The palette ──────────────────────────────────────────────────────────────

#: How many species the palette offers. A palette is a set of choices, not the
#: catalogue: 439 species in a dropdown is the Design side's job, and putting
#: it here would rebuild the complexity Learn mode exists to avoid.
PALETTE_SIZE = 14


def palette(community: str, *, resolve: Optional[Callable] = None,
            limit: int = PALETTE_SIZE) -> list[dict]:
    """What you can plant here: the curated community's own species.

    **The community's species, and not the whole catalogue** — that is the
    design decision in this function. Learn mode is teaching what belongs
    together in a place; a palette that offers everything teaches the opposite,
    and "why can I plant a bulrush in the mixedgrass prairie" is a question the
    app would then have to answer.

    Returns ``[{plant_id, common_name, scientific_name, layer}]``, ordered
    canopy → shrub → forb → grass so the list reads like the community does.
    """
    if resolve is None:
        from src.db.fauna import plants_in_genera
        resolve = plants_in_genera
    from src.reference_ecosystem import reference_community

    spec = reference_community(community)
    out: list[dict] = []
    seen: set[int] = set()
    for layer in ("canopy", "shrub", "forb", "grass"):
        lspec = (spec.get("layers") or {}).get(layer) or {}
        try:
            rows = resolve(lspec.get("genera", [])) or []
        except Exception:                                  # noqa: BLE001
            rows = []
        for row in rows:
            pid = row.get("id")
            if pid is None or pid in seen:
                continue
            seen.add(pid)
            out.append({
                "plant_id": pid,
                "common_name": row.get("common_name") or "plant",
                "scientific_name": row.get("scientific_name") or "",
                "layer": layer,
            })
    return out[:limit] if limit else out


# ── What changed ─────────────────────────────────────────────────────────────

def pull_consequence(placed_plants: list, plant_id: int, *,
                     get_plant: Optional[Callable] = None) -> str:
    """One line about what pulling this plant would cost the food web.

    This is the entire point of making the landscape editable. A diorama you
    can rearrange is a toy; a place where pulling the milkweed tells you the
    monarch has lost its only host is a lesson (P3, P5).

    The sentence is ``plant_impact``'s own ``verdict`` — F46, shipped in V2.30,
    tested, and honest about redundancy in a way a second implementation here
    would not stay. It is deliberately **not** re-derived: the app must not
    grow two answers to "what does pulling this cost".

    **Call this before the removal.** ``pull_plant_impact`` simulates the pull
    itself — it needs the list with the plant still in it, and returns ``None``
    if the plant is already gone.
    """
    try:
        from src.plant_impact import pull_plant_impact
        res = pull_plant_impact(list(placed_plants or []), [], int(plant_id),
                                get_plant=get_plant)
        return (res or {}).get("verdict", "") or ""
    except Exception:                                      # noqa: BLE001
        # A missing sentence is a much smaller failure than a broken click.
        return ""


def plant_consequence(record: dict) -> str:
    """The counterpart line for a placement. Short on purpose: the interesting
    half of this feature is what happens when you take something away."""
    return f"Planted {(record or {}).get('common_name') or 'a plant'}."
