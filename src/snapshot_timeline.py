"""
src/snapshot_timeline.py — the Year 1 / 5 / 15 / 30 growth snapshots (F2).

Design principle P4 (time is the most undervalued design variable — show the
trajectory, not the install-day moment) — see docs/DESIGN_PHILOSOPHY.md.

The philosophy's literal "most important feature": let the user *watch the yard
mature* instead of judging it on planting day. The engine already renders any
year — :func:`src.scene_contract.build_scene` scales each plant via
:func:`src.scene3d.plant_3d_state` (growth + colony spread) and fades it via
:func:`src.succession.presence_factor`. This module just picks the four headline
years and asks the existing contract for a scene at each.

Pure Python: Qt-free, ``get_plant`` injectable, no rendering. The 2×2 of canopy
panels is painted by :mod:`src.snapshot_window`, which consumes these scenes.
"""

from __future__ import annotations

from typing import Callable, Optional

# The four headline years the comparison shows: establishment, fill-in, a young
# habitat, and a mature one.
SNAPSHOT_YEARS: tuple[int, ...] = (1, 5, 15, 30)


def placed_records(project: dict) -> list[dict]:
    """Placed-plant records (each carrying ``plant_id``) in ``project`` —
    the same inverse-index entries :mod:`src.project_store` builds."""
    from src.project_store import plant_record_from_feature
    out: list[dict] = []
    for f in project.get("features", []):
        rec = plant_record_from_feature(f)
        if rec is not None:
            out.append(rec)
    return out


def snapshot_years(plants, get_plant: Optional[Callable] = None) -> list[int]:
    """The timeline years to render, clamped to the design's own horizon.

    Each of :data:`SNAPSHOT_YEARS` is capped at
    :func:`src.succession.timeline_max_years` (so a design of fast perennials
    doesn't pretend to keep changing at year 30 when it matures at 20), then
    de-duplicated and sorted. ``plants`` are placed-plant dicts or bare ids,
    exactly as :func:`timeline_max_years` accepts.
    """
    from src.succession import timeline_max_years
    cap = timeline_max_years(plants, get_plant=get_plant)
    return sorted({min(y, cap) for y in SNAPSHOT_YEARS})


def build_snapshots(project: dict, *, get_plant: Optional[Callable] = None,
                    when=None) -> list[dict]:
    """Scene JSON for ``project`` at each snapshot year.

    Returns ``[{"year": y, "scene": <build_scene result>}, ...]`` ordered by
    year. ``get_plant`` is injectable for tests; ``when`` is passed through to
    :func:`build_scene` for seasonal foliage (irrelevant to the top-down canopy
    render, honoured for parity with the 3D view).
    """
    from src.scene_contract import build_scene
    years = snapshot_years(placed_records(project), get_plant=get_plant)
    return [
        {"year": y,
         "scene": build_scene(project, year=y, get_plant=get_plant, when=when)}
        for y in years
    ]
