"""
src/conversion_plan.py — the year-by-year lawn → habitat conversion schedule (F17).

Design principle P8 (repair is more sophisticated than creation — restoration as a
staged plan, not a single install day) and P4 (time is the most undervalued design
variable) — see docs/DESIGN_PHILOSOPHY.md.

Pure / Qt-free and dependency-injectable so the planning panel, the Planting Plan
text export, the PDF and the tests share one definition. It crosses three things
the app already knows:

  * the drawn conversion zones (``lawn_zones.conversion_summary`` → how much lawn
    is being converted, and how much is already underway);
  * the restoration-stage timeline (``succession.restoration_stage`` → what each
    year looks like ecologically: pioneer forbs → matrix → shrubs → climax);
  * the design's own plants, grouped by successional role (woody structure /
    pioneers / matrix / self-spreaders / climax),

into an ordered "remove this / plant that, when" task list. The cadence is
deliberately given as honest year *ranges*, never false day-precision (P9).
"""

from __future__ import annotations

from dataclasses import dataclass

from src import succession


# Spread habits that mark a self-spreader (kept in step with planting_plan).
_SPREADERS = ("self_seeding", "slow_spreader", "aggressive_rhizomatous")

# Milestone years the schedule is anchored on — one per restoration_stage band
# (see succession.restoration_stage thresholds): planting, pioneer forbs,
# forb–grass matrix, shrubs establishing, climax/canopy.
_MILESTONES = [
    (0, "Year 0"),
    (1, "Years 1–2"),
    (3, "Years 3–4"),
    (5, "Years 5–9"),
    (10, "Year 10+"),
]

_NAME_CAP = 4


@dataclass
class ConversionStage:
    """One band of the schedule: a year range, its restoration stage, and the
    ordered tasks for that band."""
    year_label: str
    stage: str
    tasks: list   # list[str]


@dataclass
class ConversionSchedule:
    """A whole lawn → habitat conversion as an ordered, staged task list."""
    stages: list           # list[ConversionStage]
    target_m2: float       # lawn ground being converted (lawn + restoration zones)
    converted_m2: float    # of that, the area already underway
    species_count: int
    total_plants: int

    @property
    def has_zones(self) -> bool:
        return self.target_m2 > 0


def _names(names: list[str], cap: int = _NAME_CAP) -> str:
    """Compact a name list to ``a, b, c +N more``."""
    names = [n for n in names if n]
    if not names:
        return ""
    if len(names) <= cap:
        return ", ".join(names)
    return ", ".join(names[:cap]) + f" +{len(names) - cap} more"


def _area_str(m2: float) -> str:
    return f"{m2:,.0f} m²" if m2 < 10000 else f"{m2 / 10000:.2f} ha"


def _classify(placed_plants, get_plant) -> dict:
    """Group the design's distinct species by the role they play in the
    conversion: woody structure, pioneers, matrix, self-spreading fill, climax.
    A species can appear in more than one group (a slow climax tree is both
    'woody' — planted first — and 'climax' — defining the canopy later)."""
    woody: list[str] = []
    pioneer: list[str] = []
    matrix: list[str] = []
    fill: list[str] = []
    climax: list[str] = []
    seen: set = set()
    for p in placed_plants or []:
        pid = p.get("plant_id") if isinstance(p, dict) else p
        if pid is None or pid in seen:
            continue
        seen.add(pid)
        plant = get_plant(pid) or {}
        name = plant.get("common_name") or (
            p.get("common_name") if isinstance(p, dict) else None) or "?"
        ptype = (plant.get("plant_type") or "").strip().lower()
        role = succession.successional_role(plant)
        spreader = (plant.get("spread_habit") or "").strip().lower() in _SPREADERS
        if ptype in ("tree", "shrub", "vine"):
            woody.append(name)
        if role == "pioneer":
            pioneer.append(name)
        elif role == "climax":
            climax.append(name)
        if spreader:
            fill.append(name)
        elif ptype in ("herb", "groundcover", "root") and role != "pioneer":
            matrix.append(name)
    return {"woody": woody, "pioneer": pioneer, "matrix": matrix,
            "fill": fill, "climax": climax}


def build_conversion_schedule(placed_plants, summary=None,
                              get_plant=None) -> ConversionSchedule:
    """Build the year-by-year conversion schedule.

    ``placed_plants`` are placed-plant dicts (carrying ``plant_id``); ``summary``
    is an optional ``lawn_zones.conversion_summary`` result (its ``by_stage``
    gives the lawn area being converted). ``get_plant`` is injectable for tests.
    The schedule is always built — even with no drawn zones the plant-driven
    cadence is useful — but the lawn-removal step only appears when there is lawn
    ground to convert."""
    if get_plant is None:
        from src.db.plants import get_plant as _gp
        get_plant = _gp

    by_stage = (summary or {}).get("by_stage") or {}
    lawn = float(by_stage.get("lawn", 0.0))
    converted = float(by_stage.get("converted", 0.0))
    target = lawn + converted

    groups = _classify(placed_plants, get_plant)
    woody, pioneer = groups["woody"], groups["pioneer"]
    matrix, fill, climax = groups["matrix"], groups["fill"], groups["climax"]

    distinct = {p.get("plant_id") for p in (placed_plants or [])
                if (p.get("plant_id") if isinstance(p, dict) else p) is not None}
    total_plants = sum(1 for p in (placed_plants or [])
                       if (p.get("plant_id") if isinstance(p, dict) else p) is not None)

    def stage_for(year: int) -> str:
        return succession.restoration_stage(year)

    stages: list[ConversionStage] = []

    # ── Year 0 — site prep & planting ─────────────────────────────────────
    y0: list[str] = []
    if target > 0:
        y0.append(
            f"Remove or smother the turf over ~{_area_str(target)} "
            f"(sheet-mulch in fall, or strip / solarize in spring)."
        )
    if woody:
        y0.append(f"Plant the woody structure first: {_names(woody)}.")
    if pioneer:
        y0.append(f"Plant pioneer species to hold the soil: {_names(pioneer)}.")
    if total_plants and not woody and not pioneer:
        y0.append("Plant the design, working outward from the largest plants.")
    y0.append("Mulch the new beds and water everything in.")
    stages.append(ConversionStage(_MILESTONES[0][1], stage_for(0), y0))

    # ── Years 1–2 — pioneer forbs ─────────────────────────────────────────
    y1 = [
        "Water through the first season or two to establish roots.",
        "Spot-weed as the planting knits together.",
    ]
    if pioneer:
        y1.append(
            f"Pioneers ({_names(pioneer)}) peak now, then ease off as the "
            f"later layers close in."
        )
    stages.append(ConversionStage(_MILESTONES[1][1], stage_for(1), y1))

    # ── Years 3–4 — forb–grass matrix ─────────────────────────────────────
    y3: list[str] = []
    if matrix:
        y3.append(f"Fill the matrix layer: {_names(matrix)}.")
    y3.append("Taper watering as the planting deepens its roots.")
    if fill:
        y3.append(f"Let self-spreaders ({_names(fill)}) seed into the gaps.")
    stages.append(ConversionStage(_MILESTONES[2][1], stage_for(3), y3))

    # ── Years 5–9 — shrubs establishing ───────────────────────────────────
    y5 = [
        "Stop routine irrigation — the planting should now carry itself.",
        "Thin or divide only where plants crowd each other.",
    ]
    if woody:
        y5.append(f"Shrubs and young trees ({_names(woody)}) close in.")
    stages.append(ConversionStage(_MILESTONES[3][1], stage_for(5), y5))

    # ── Year 10+ — climax / canopy ────────────────────────────────────────
    y10: list[str] = []
    if climax:
        y10.append(f"Climax species ({_names(climax)}) define the canopy.")
    y10.append("Annual late-winter cut-back of perennials; no irrigation needed.")
    stages.append(ConversionStage(_MILESTONES[4][1], stage_for(10), y10))

    return ConversionSchedule(
        stages=stages,
        target_m2=round(target, 1),
        converted_m2=round(converted, 1),
        species_count=len(distinct),
        total_plants=total_plants,
    )


def render_schedule_text(schedule: ConversionSchedule) -> str:
    """Render the schedule as the plain-text block used by the Planting Plan
    export and the planning panel."""
    lines = ["PHASED CONVERSION  (year by year)", ""]
    if schedule.has_zones:
        head = f"Converting ~{_area_str(schedule.target_m2)} of lawn to habitat"
        if schedule.converted_m2 > 0:
            head += f" ({_area_str(schedule.converted_m2)} already underway)"
        lines.append(head + ".")
        lines.append("")
    for st in schedule.stages:
        lines.append(f"{st.year_label} · {st.stage}")
        for task in st.tasks:
            lines.append(f"  • {task}")
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"
