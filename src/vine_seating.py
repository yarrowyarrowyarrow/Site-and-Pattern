"""Where the design generator plants a vine: at the foot of a tree or shrub.

Design principle P10 — see docs/DESIGN_PHILOSOPHY.md

Since V2.89 a vine climbs the tree or shrub whose footprint touches its own, and
with none it lies on the ground (:mod:`src.vine_habit`). The generator never
connected the two: a vine group took the best free cell like any other group and
was laid out in a row, so a generated vine touched a host only by chance (F181,
V2.90).

Trees and shrubs are placed before vines (``llm_design._LAYER_ORDER``), so when a
vine comes up its possible hosts are already in the ground, and
:class:`VineSeats` seats it at the foot of one:

* **At the base.** 0.25-0.6 m from the host's centre (half its crown radius),
  inside the crown: where a clematis is planted to climb a shrub, and the one
  distance that keeps a vine touching its host at every age the growth timeline
  draws. Seated at the mature drip line it would be a metre from a young shrub.
* **The sunny side first:** south, then west, east and round to north. In
  Alberta a vine on the north side of its host climbs into shade.
* **Not smothering the host.** One vine per shrub under 2 m across, two on a
  bigger shrub or a tree, three on a tree over 6 m across.
* **The least-used host first**, then the earliest placed, so one design always
  seats the same way.

When nothing can hold a vine the generator places it as before, and
:func:`vines_with_nothing_to_climb` names it for the design notes: the owner's
option (c). It asks the 3D scene at maturity rather than repeating the rule, so
the note and the picture cannot disagree.
"""

from __future__ import annotations

import math
from collections import Counter
from typing import Callable, Iterable, Optional

from src.projection import Projector

#: A seat is half the host's crown radius from its centre, within these bounds.
SEAT_MIN_M = 0.25
SEAT_MAX_M = 0.60
#: How close a seat may come to any placed plant but its host.
CLEAR_M = 0.30
#: Degrees clockwise from north, in the order a seat is tried: sunny side first.
BEARINGS = (180, 270, 90, 225, 135, 315, 45, 0)
#: Two vines on one host keep at least this far apart around it.
MIN_SEPARATION_DEG = 60

#: Crown widths (metres) at which a host takes one more vine.
SHRUB_TWO_VINES_M = 2.0
TREE_THREE_VINES_M = 6.0


def seat_distance_m(crown_m: float) -> float:
    """How far from the host's centre its vine is planted: half its radius."""
    return min(SEAT_MAX_M, max(SEAT_MIN_M, float(crown_m or 0.0) / 4.0))


def capacity(plant_type: str, crown_m: float) -> int:
    """How many vines one host carries. Zero for anything but a tree or shrub:
    the owner's rule (V2.89) is that nothing else holds a vine up."""
    crown = float(crown_m or 0.0)
    if plant_type == "tree":
        return 3 if crown > TREE_THREE_VINES_M else 2
    if plant_type == "shrub":
        return 2 if crown >= SHRUB_TWO_VINES_M else 1
    return 0


def crown_m_of(plant: dict) -> float:
    """A catalogue row's crown width at maturity, exactly as the 3D scene draws
    it (``scene3d.plant_3d_state`` at year 0), defaults and all."""
    from src.scene3d import plant_3d_state
    return float(plant_3d_state(plant or {}, 0.0, 0.0, 0)["canopy_m"])


def _bearing_gap(a: float, b: float) -> float:
    d = abs(a - b) % 360.0
    return min(d, 360.0 - d)


class VineSeats:
    """The trees and shrubs placed so far, and the vines seated on them.

    ``fits(lat, lng)`` says whether a spot may be planted at all: inside the
    boundary and clear of keep-out. The caller owns those rules.
    """

    def __init__(self, fits: Callable[[float, float], bool]):
        self._fits = fits
        self._hosts: list[dict] = []

    @property
    def hosts(self) -> int:
        return len(self._hosts)

    def add_host(self, lat: float, lng: float, plant_type: str,
                 crown_m: float) -> None:
        cap = capacity(plant_type, crown_m)
        if cap:
            self._hosts.append({"lat": lat, "lng": lng, "crown_m": crown_m,
                                "cap": cap, "used": []})

    def seat(self, others: Iterable[tuple]) -> Optional[tuple[float, float]]:
        """A spot for one vine, or None when no host has room. ``others`` are
        the ``(lat, lng)`` of every plant already placed, seated vines included."""
        others = list(others)
        order = sorted(range(len(self._hosts)),
                       key=lambda i: (len(self._hosts[i]["used"]), i))
        for i in order:
            h = self._hosts[i]
            if len(h["used"]) >= h["cap"]:
                continue
            proj = Projector(h["lat"], h["lng"])
            d = seat_distance_m(h["crown_m"])
            for b in BEARINGS:
                if any(_bearing_gap(b, u) < MIN_SEPARATION_DEG
                       for u in h["used"]):
                    continue
                rad = math.radians(b)
                lat, lng = proj.to_latlng(d * math.sin(rad), d * math.cos(rad))
                if not self._fits(lat, lng):
                    continue
                if any(_crowds(proj, lat, lng, o) for o in others):
                    continue
                h["used"].append(b)
                return lat, lng
        return None


def _crowds(proj: Projector, lat: float, lng: float, other: tuple) -> bool:
    """True when ``other`` is a plant other than the host (which sits at the
    projector's origin) closer than CLEAR_M to the seat."""
    ox, oy = proj.to_xy(other[0], other[1])
    if math.hypot(ox, oy) < 1e-3:
        return False
    x, y = proj.to_xy(lat, lng)
    return math.hypot(x - ox, y - oy) < CLEAR_M


# ── Option (c): say which vines have nothing to climb ───────────────────────

#: How far apart (metres) a generated vine and a scene record may be and still
#: be the same plant: the scene rounds positions to the centimetre.
_MATCH_M = 0.05


def vines_with_nothing_to_climb(generated: dict,
                                existing_features: Iterable[dict] = ()
                                ) -> list[str]:
    """Common names, one per vine in ``generated`` that the 3D scene draws on
    the ground at maturity.

    ``existing_features`` is the rest of the user's project: the generated
    plants join it, so its trees, shrubs and existing trees can hold a
    generated vine too, but only generated vines are reported.
    """
    from src.project_store import plant_record_from_feature
    from src.scene_contract import build_scene

    feats = list(generated.get("features") or [])
    combined = dict(generated)
    combined["features"] = feats + list(existing_features or [])
    scene = build_scene(combined, year=0, wind=False)
    flat = [p for p in scene.get("plants") or []
            if p.get("plant_type") == "vine"
            and (p.get("drawn") or {}).get("habit") != "climbing"]
    if not flat:
        return []
    origin = scene.get("origin") or {}
    proj = Projector(origin["lat"], origin["lng"])
    names = []
    for f in feats:
        rec = plant_record_from_feature(f)
        if rec is None:
            continue
        x, y = proj.to_xy(rec["lat"], rec["lng"])
        for p in flat:
            if (p.get("plant_id") == rec["plant_id"]
                    and abs(p["x"] - x) <= _MATCH_M
                    and abs(p["y"] - y) <= _MATCH_M):
                names.append(p.get("common_name") or rec.get("common_name")
                             or "a vine")
                flat.remove(p)
                break
    return names


def climb_note(names: list[str]) -> str:
    """The design note for vines with nothing to climb (the owner's option c)."""
    counts = Counter(names)
    parts = [f"{n} (×{c})" if c > 1 else n
             for n, c in sorted(counts.items())]
    listed = (parts[0] if len(parts) == 1
              else ", ".join(parts[:-1]) + " and " + parts[-1])
    if len(names) == 1:
        return (f"Nothing here for {listed} to climb: no tree or shrub stands "
                f"beside it, so it grows along the ground. Plant it at the foot "
                f"of a shrub or tree and it will climb.")
    return (f"Nothing here for {listed} to climb: no tree or shrub stands "
            f"beside them, so they grow along the ground. Plant each at the "
            f"foot of a shrub or tree and it will climb.")
