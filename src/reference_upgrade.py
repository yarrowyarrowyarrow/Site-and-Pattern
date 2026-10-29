"""
reference_upgrade.py — a saved walk built from an older community (V3.39).

Design principle P8 (repair is more sophisticated than creation) — see
docs/DESIGN_PHILOSOPHY.md: what the person planted is kept.

A walk you have planted in is a saved file (``src.reference_edit``), and a
saved walk was never built again: the Aspen Parkland walks saved before V3.39
would have kept their alphabetical trees, with no aspen, for good. Every walk
now records the version of the community it was built from
(``reference_ecosystem.COMMUNITY_VERSION``); an older one is built afresh where
it stood, and every plant the person planted is put back where they put it.
"""

from __future__ import annotations

from typing import Callable, Optional

from src import reference_edit


def _plants(project: dict, kind: str = "") -> list:
    """``(record, feature)`` for each plant, of one ``pattern_kind`` if given.
    The kind is read off the feature: the placed-plant record does not carry
    it."""
    from src.project_store import plant_record_from_feature
    out = []
    for f in project.get("features", []):
        rec = plant_record_from_feature(f)
        if rec is None:
            continue
        if kind and (f.get("properties") or {}).get("pattern_kind") != kind:
            continue
        out.append((rec, f))
    return out


def _shipped_centre(project: dict) -> Optional[tuple]:
    """Where an older sandbox was built: the middle of its shipped plants'
    extent. Those were scattered evenly over a square round the centre, so the
    middle of their extent is the centre to well under a metre; a mean would
    be pulled toward wherever the scatter happened to be thick."""
    pts = [(r["lat"], r["lng"]) for r, _f in
           _plants(project, reference_edit.REFERENCE_KIND)]
    pts = pts or [(r["lat"], r["lng"]) for r, _f in _plants(project)]
    if not pts:
        return None
    lats, lngs = [p[0] for p in pts], [p[1] for p in pts]
    return ((min(lats) + max(lats)) / 2.0, (min(lngs) + max(lngs)) / 2.0)


def upgrade_sandbox(community: str, saved: dict, *,
                    build: Optional[Callable] = None) -> dict:
    """``saved`` as it is when it was built from the current version of the
    community; otherwise the community built afresh where the old one stood,
    with every plant the person planted kept where they put it, with its
    planting year and its identity (V3.39).

    Only the shipped plants are replaced. Anything else in the file, a
    feature that is not a plant, comes across unchanged."""
    from src.project_store import ProjectStore, plant_record_from_feature
    from src.reference_ecosystem import COMMUNITY_VERSION
    props = saved.get("properties") or {}
    if props.get("reference_version") == COMMUNITY_VERSION:
        return saved
    centre = props.get("reference_center") or _shipped_centre(saved)
    if not centre:
        return saved
    if build is None:
        from src.reference_ecosystem import build_reference_project
        build = build_reference_project
    fresh = build(community, center_lat=float(centre[0]),
                  center_lng=float(centre[1]))
    store = ProjectStore(fresh)
    for rec, _f in _plants(saved, reference_edit.USER_KIND):
        store.add_plant(int(rec["plant_id"]), rec.get("common_name") or "plant",
                        float(rec["lat"]), float(rec["lng"]),
                        pattern_kind=reference_edit.USER_KIND,
                        feature_id=rec.get("feature_id") or "",
                        planted_year=rec.get("planted_year"))
    fresh.setdefault("features", []).extend(
        f for f in saved.get("features", [])
        if plant_record_from_feature(f) is None)
    return fresh
