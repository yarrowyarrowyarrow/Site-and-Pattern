"""
src/graduation.py — take the landscape you built into Design (F104, V2.55).

Design principle P13 (a native planting has to be loved to survive) and P8
(repair is more sophisticated than creation) — see docs/DESIGN_PHILOSOPHY.md.

Learn mode was a side room. You could walk a wild community, plant into it, pull
things out of it and net the insects — and then there was nowhere for any of
that to go. The landscape you built was a sandbox in both senses.

This is the door out: **the fen you assembled, moved to your own address, saved
as an ordinary design.** After it, Learn *leads* somewhere.

**It crosses the mode split on purpose.** ``app_mode._LEARN_ONLY`` exists so the
beginner does not meet the map — its docstring calls that "the whole mechanical
content of the mode split". Graduation is the one sanctioned crossing, and so it
must always be an explicit act by the user, never something the app does on
their behalf. The Qt side of that lives in ``reference_edit_flow``; this module
is the part that can be reasoned about and tested without a display.

**Where it lands, and why the centroid.** The saved sandbox records its
``name`` and its ``reference_ecoregion`` and *not* the centre it was built
around, so there is no original origin to read back. The centroid of what you
planted is used instead — which is also the better promise to make: the middle
of the landscape you built arrives on your pin.

**With no property pin it still graduates.** In Learn mode there often is no
pin, and refusing to proceed would put a wall exactly where this feature is
trying to open a door. The landscape comes across at its own coordinates and the
existing first-step machinery asks for an address, which is the app's normal way
of saying "this needs a location" — see :func:`src.onboarding.first_step_line`.
"""

from __future__ import annotations

from typing import Optional

#: What the graduated design is called before the user renames it.
NAME_PREFIX = "From Learn"


def plant_records(project: dict) -> list:
    """The placed plants, read through the store rather than off the features."""
    from src.project_store import ProjectStore
    return list(ProjectStore(project).placed_plants)


def plant_centroid(project: dict) -> Optional[tuple]:
    """``(lat, lng)`` at the middle of the placed plants, or ``None`` if empty.

    A plain mean rather than a bounding-box centre: a landscape with one
    outlying shrub should not have its whole middle dragged toward that shrub's
    corner, which is what a bbox centre would do.
    """
    lats, lngs = [], []
    for rec in plant_records(project):
        try:
            lats.append(float(rec["lat"]))
            lngs.append(float(rec["lng"]))
        except (KeyError, TypeError, ValueError):
            continue
    if not lats:
        return None
    return (sum(lats) / len(lats), sum(lngs) / len(lngs))


def recentre(project: dict, target: tuple) -> int:
    """Move every placed plant so the centroid sits on ``target``.

    Returns how many plants moved. Each move goes through
    ``ProjectStore.move_plant`` — the single write path for placed-plant state
    (``tests/test_project_store.py`` greps the tree for anything else), which
    also keeps the feature list and the record index in step.

    Relative geometry is preserved by construction: every plant is converted to
    metres east/north of the old centroid and rebuilt at the same offsets from
    the new one, using the app's shared ``projection`` metric via
    ``reference_edit``'s helpers so the sandbox cannot drift from the scene it
    was drawn in.
    """
    from src.project_store import ProjectStore
    from src.reference_edit import local_offset, offset_latlng

    origin = plant_centroid(project)
    if origin is None or not target:
        return 0
    tgt_lat, tgt_lng = float(target[0]), float(target[1])
    store = ProjectStore(project)
    moved = 0
    # Snapshot the records first: move_plant rewrites the index as it goes, and
    # iterating a list that is being rebuilt underneath is how you move half a
    # landscape and silently leave the rest behind.
    for rec in list(store.placed_plants):
        try:
            pid = int(rec["plant_id"])
            old_lat, old_lng = float(rec["lat"]), float(rec["lng"])
        except (KeyError, TypeError, ValueError):
            continue
        dx, dy = local_offset(old_lat, old_lng, origin[0], origin[1])
        new_lat, new_lng = offset_latlng(tgt_lat, tgt_lng, dx, dy)
        if store.move_plant(pid, old_lat, old_lng, new_lat, new_lng,
                            feature_id=rec.get("feature_id", "") or ""):
            moved += 1
    return moved


def graduated_name(project: dict) -> str:
    """A name for the new design, from the community it came out of."""
    props = (project or {}).get("properties") or {}
    base = str(props.get("name") or "").strip()
    # The sandbox names itself "Reference — Aspen Parkland"; keep the half that
    # says where you were, drop the word that says it was a demo.
    if "—" in base:
        base = base.split("—", 1)[1].strip()
    return f"{NAME_PREFIX}: {base}" if base else NAME_PREFIX


def graduate(project: dict, target: Optional[tuple] = None, *,
             site_config: Optional[dict] = None) -> dict:
    """A design-shaped copy of the sandbox, re-centred on ``target``.

    ``target`` is the property pin. ``None`` — no pin yet — leaves the plants
    where they are rather than refusing; see the module docstring.

    ``site_config`` is the **design's** cached site data — pin, zone, soil,
    rainfall, frost. It has to come across or graduating would be a downgrade:
    ``MainWindow._load_from_path`` replays this block to restore the pin and
    every Site Info reading, so a graduated project without it would open at
    your address with the whole site panel blank, and would overwrite the
    site data the user already had.

    The sandbox itself is not touched: a user who graduates a landscape and then
    keeps playing should find the sandbox exactly as they left it.
    """
    import copy

    out = copy.deepcopy(project or {})
    out.setdefault("type", "FeatureCollection")
    out.setdefault("features", [])
    props = out.setdefault("properties", {})
    props["name"] = graduated_name(project)
    # Where it came from, kept on the project so the provenance is not folded
    # into a display string that someone later reformats.
    src_props = (project or {}).get("properties") or {}
    if src_props.get("reference_ecoregion"):
        props["graduated_from"] = src_props["reference_ecoregion"]
    if site_config:
        props["site_config"] = copy.deepcopy(site_config)
    if target:
        recentre(out, target)
    return out


def save_as_design(project: dict, directory: Optional[str] = None) -> str:
    """Write a graduated project into the saves folder. Returns the path.

    Lands in the ordinary saves directory under an ordinary unique name, so it
    shows up in File → Open beside everything else — the point being that a
    graduated landscape is a design, not a special kind of object.
    """
    import json

    from src import saves

    name = ((project or {}).get("properties") or {}).get("name") or NAME_PREFIX
    path = saves.unique_save_path(name, directory)
    import os
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(project, fh)
    saves.clear_cache()
    return path
