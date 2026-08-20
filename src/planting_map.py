"""
planting_map.py — the plan you take outside and dig from (F41).

Design principle P11 (the body and the site know things the screen does not —
this is the artifact that gets the design off the screen and into the ground)
and P5 (perception is constructed — a keyed plan reads a yard in a way a
photograph cannot) — see docs/DESIGN_PHILOSOPHY.md.

F40 answered *what to buy*. It never answered **where each one goes**, which is
the question standing between a nursery receipt and a planted bed. This module
computes the keyed, numbered planting plan that closes that gap.

Three decisions worth stating, because each went against the obvious route.

**It is a drawing, not a screenshot.** The card proposed numbering a captured
map image. A satellite capture is the worst possible background for a document
you use outdoors with a tape measure: it is dark, it is busy, it prints badly,
and it has no scale. A clean scale drawing of the boundary with numbered
positions, a scale bar and a north arrow is what a planting plan has looked like
for a century, and it costs no capture plumbing, no coordinate round-trip
through the browser, and no map-JS at all.

**Numbers are per SPECIES, not per hole.** "Dig holes 7, 8, 9" sounds right and
is unusable at 119 plants; a key of 119 entries is not a key. Every Saskatoon is
a **7**, and the key line reads *7 — Saskatoon Berry — 3 plants, 2.5 m apart*.
That is how planting plans are actually drawn, and it keys straight back to the
F40 buy list, because the numbering follows exactly that list's order.

**Positions come out in metres, not pixels.** The core returns a local
east/north frame in metres so the renderer only has to pick a scale — which
means the same numbers drive the PDF, a future on-screen view, and the tests,
and the geometry stays in Python where it can be checked.

Qt-free, dependency-injectable, JSON-serialisable.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Callable, Optional

from src.projection import metres_per_deg

#: Padding around the drawn extent, in metres, so nothing touches the frame.
_MARGIN_M = 1.5
#: Scale-bar candidates in metres — the drawer picks the largest that fits.
_SCALE_STEPS = (1, 2, 5, 10, 20, 25, 50, 100)


@dataclass
class MapPlacement:
    """One planted position, in metres east/north of the plan's origin."""
    number: int
    plant_id: int
    common_name: str
    x_m: float
    y_m: float


@dataclass
class MapKeyEntry:
    """One line of the key — and one line of the F40 buy list."""
    number: int
    plant_id: int
    common_name: str
    scientific_name: str
    plant_type: str
    qty: int
    spacing_m: float


@dataclass
class PlantingMap:
    placements: list = field(default_factory=list)   # list[MapPlacement]
    key: list = field(default_factory=list)          # list[MapKeyEntry]
    boundary: list = field(default_factory=list)     # [(x_m, y_m), …] closed
    width_m: float = 0.0
    height_m: float = 0.0
    #: True north is up in this frame; the note says so rather than assuming
    #: the reader knows.
    north_note: str = "North is up. Distances are in metres."
    caveats: list = field(default_factory=list)

    def as_dict(self) -> dict:
        return asdict(self)

    def scale_bar_m(self, drawable_width_m: Optional[float] = None) -> int:
        """A round scale-bar length that fits comfortably in the frame.

        Aimed at roughly a third of the width: long enough to be useful for
        pacing a distance off the drawing, short enough not to dominate it.
        """
        span = drawable_width_m or self.width_m or 1.0
        target = span / 2.5
        best = _SCALE_STEPS[0]
        for step in _SCALE_STEPS:
            if step <= target:
                best = step
        return best


def _boundary_rings(project: dict) -> list:
    """Every property-boundary ring as [(lat, lng), …]."""
    rings = []
    for f in (project or {}).get("features") or []:
        props = f.get("properties") or {}
        if props.get("element_type") != "property_boundary":
            continue
        coords = ((f.get("geometry") or {}).get("coordinates") or [])
        if not coords:
            continue
        ring = [(pt[1], pt[0]) for pt in coords[0] if len(pt) >= 2]
        if len(ring) >= 3:
            rings.append(ring)
    return rings


def build_planting_map(placed_plants: list, project: Optional[dict] = None, *,
                       plan=None, get_plant: Optional[Callable] = None
                       ) -> PlantingMap:
    """Build the numbered planting plan.

    ``plan`` is an optional :class:`src.planting_plan.PlantingPlan`; when given,
    the numbering follows its item order exactly, so a number on the drawing and
    a number on the buy list are the same number. Without one, the same ordering
    (by common name) is reproduced locally.
    """
    pm = PlantingMap()
    points = [(float(p["lat"]), float(p["lng"]))
              for p in (placed_plants or [])
              if p.get("lat") is not None and p.get("lng") is not None]
    if not points:
        pm.caveats.append("No plants placed yet — nothing to draw.")
        return pm

    rings = _boundary_rings(project or {})
    frame_points = list(points) + [pt for ring in rings for pt in ring]

    # Local east/north frame with its origin at the SW corner of everything
    # being drawn, so x and y are both positive and read like a site plan.
    min_lat = min(p[0] for p in frame_points)
    min_lng = min(p[1] for p in frame_points)
    max_lat = max(p[0] for p in frame_points)
    max_lng = max(p[1] for p in frame_points)
    m_lat, m_lng = metres_per_deg((min_lat + max_lat) / 2.0)

    def to_xy(lat, lng):
        return (round((lng - min_lng) * m_lng + _MARGIN_M, 3),
                round((lat - min_lat) * m_lat + _MARGIN_M, 3))

    pm.width_m = round((max_lng - min_lng) * m_lng + 2 * _MARGIN_M, 2)
    pm.height_m = round((max_lat - min_lat) * m_lat + 2 * _MARGIN_M, 2)
    if rings:
        # Only the first ring is drawn — a plan with several overlapping
        # boundaries is a different drawing, and guessing which is "the" plot
        # would be worse than showing the one the user drew first.
        pm.boundary = [to_xy(lat, lng) for lat, lng in rings[0]]
        if pm.boundary and pm.boundary[0] != pm.boundary[-1]:
            pm.boundary.append(pm.boundary[0])
        if len(rings) > 1:
            pm.caveats.append(
                f"{len(rings)} boundaries are drawn; the plan shows the first. "
                f"Plant positions are all shown regardless.")
    else:
        pm.caveats.append(
            "No property boundary drawn, so the plan has no outline — only the "
            "planted positions and the scale.")

    numbers = _numbering(placed_plants, plan, get_plant)
    for p in placed_plants or []:
        pid = p.get("plant_id")
        if pid is None or p.get("lat") is None or p.get("lng") is None:
            continue
        x, y = to_xy(float(p["lat"]), float(p["lng"]))
        pm.placements.append(MapPlacement(
            number=numbers.get(pid, 0), plant_id=int(pid),
            common_name=p.get("common_name") or "", x_m=x, y_m=y))
    pm.placements.sort(key=lambda mp: (mp.number, mp.y_m, mp.x_m))
    pm.key = _key_entries(placed_plants, numbers, plan, get_plant)
    pm.caveats.append(
        "Positions are where the plants sit on the map, to about a "
        "centimetre — but the map is only as right as your boundary. Measure "
        "from a fixed edge (a fence, a wall, the sidewalk), not from the "
        "drawing's corner.")
    return pm


def _numbering(placed_plants, plan, get_plant) -> dict:
    """``{plant_id: number}`` in the F40 buy list's order."""
    if plan is not None and getattr(plan, "items", None):
        return {item.plant_id: i for i, item in enumerate(plan.items, 1)}
    # No plan handed in — reproduce its ordering (by common name) so the two
    # never disagree about which species is #7.
    names: dict = {}
    for p in placed_plants or []:
        pid = p.get("plant_id")
        if pid is not None and pid not in names:
            names[pid] = (p.get("common_name") or "").lower()
    ordered = sorted(names, key=lambda pid: (names[pid], pid))
    return {pid: i for i, pid in enumerate(ordered, 1)}


def _key_entries(placed_plants, numbers, plan, get_plant) -> list:
    """The key table, one row per species, in number order."""
    if plan is not None and getattr(plan, "items", None):
        return [MapKeyEntry(
            number=numbers.get(item.plant_id, 0), plant_id=item.plant_id,
            common_name=item.common_name,
            scientific_name=item.scientific_name,
            plant_type=item.plant_type, qty=item.qty,
            spacing_m=item.spacing_m) for item in plan.items]

    if get_plant is None:
        from src.db.plants import get_plant as _gp                # noqa: PLC0415
        get_plant = _gp
    counts: dict = {}
    labels: dict = {}
    for p in placed_plants or []:
        pid = p.get("plant_id")
        if pid is None:
            continue
        counts[pid] = counts.get(pid, 0) + 1
        labels.setdefault(pid, p.get("common_name") or "")
    out = []
    for pid, number in sorted(numbers.items(), key=lambda kv: kv[1]):
        plant = get_plant(pid) or {}
        try:
            # Same helper the F40 plan uses, so a key row and a buy-list row
            # never quote different spacings for one species.
            from src.planting_plan import _spacing_for           # noqa: PLC0415
            spacing = float(_spacing_for(plant))
        except Exception:                                        # noqa: BLE001
            spacing = 0.0
        out.append(MapKeyEntry(
            number=number, plant_id=pid,
            common_name=labels.get(pid) or plant.get("common_name", "?"),
            scientific_name=plant.get("scientific_name", "") or "",
            plant_type=(plant.get("plant_type") or "").lower(),
            qty=counts.get(pid, 0), spacing_m=round(spacing, 2)))
    return out


def render_map_key_text(pm: PlantingMap) -> str:
    """Plain-text key for the Planting Plan export.

    The drawing itself is a PDF page; the text export carries the key plus each
    plant's offset, which is enough to lay the bed out with a tape measure and
    no printer.
    """
    lines = ["PLANTING MAP — KEY", "=" * 44, ""]
    if not pm.placements:
        lines.append("No plants placed yet.")
        return "\n".join(lines) + "\n"
    lines.append(f"Plot: {pm.width_m:.1f} m east–west × "
                 f"{pm.height_m:.1f} m north–south. {pm.north_note}")
    lines.append("")
    for entry in pm.key:
        lines.append(
            f"  {entry.number:>3}.  {entry.common_name}"
            + (f" ({entry.scientific_name})" if entry.scientific_name else "")
            + f" — {entry.qty} plant{'s' if entry.qty != 1 else ''}"
            + (f", {_spacing_str(entry.spacing_m)} apart"
               if entry.spacing_m else ""))
    lines.append("")
    lines.append("POSITIONS  (metres east / north of the plan's SW corner)")
    lines.append("-" * 44)
    for mp in pm.placements:
        lines.append(f"  {mp.number:>3}.  {mp.x_m:>6.1f} E   "
                     f"{mp.y_m:>6.1f} N   {mp.common_name}")
    if pm.caveats:
        lines.append("")
        lines.append("NOTES")
        lines.append("-" * 44)
        for caveat in pm.caveats:
            for chunk in _wrap(caveat, 68):
                lines.append(f"  {chunk}")
            lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def _spacing_str(metres: float) -> str:
    """Spacing to the nearest 5 cm.

    ``plant_spacing`` returns an unrounded estimate off canopy and spread
    habit; printing "0.878 m apart" on a sheet somebody plants from claims a
    precision the model does not have (P9).
    """
    rounded = round(float(metres) * 20.0) / 20.0
    return f"{rounded:g} m"


def _wrap(text: str, width: int) -> list[str]:
    words, lines, cur = (text or "").split(), [], ""
    for word in words:
        if cur and len(cur) + len(word) + 1 > width:
            lines.append(cur)
            cur = word
        else:
            cur = f"{cur} {word}".strip()
    if cur:
        lines.append(cur)
    return lines or [""]
