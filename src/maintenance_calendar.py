"""
maintenance_calendar.py — what this design asks of you, year by year (F42).

Design principle P4 (time is the most undervalued design variable — the whole
point of a native planting is that the work *falls*, and a calendar that hides
that curve sells the design short) and P9 (ranges, never false precision — hours
here are estimates with a stated spread, not a quote) — see
docs/DESIGN_PHILOSOPHY.md.

Two things this says that a generic garden calendar does not.

**Year one is the one that kills plantings, and it is about water.** Not
fertiliser, not pruning — deep weekly watering through the first summer while
roots go down. Native plantings fail overwhelmingly in their first season, to
owners who were told natives need no water and took that to mean *never*, rather
than *not once established*.

**Cut back in spring, not fall.** The tidy-up-in-October reflex removes exactly
the overwintering habitat the rest of this app spends its time modelling: stem-
nesting bees inside hollow and pithy stems, lepidoptera eggs and pupae on and
under standing growth, seed heads for winter birds. The calendar says why, and
names the species in *your* design it applies to.

The hour figures share their constants with the Planning → Effort tab
(:data:`PLANT_MAINTENANCE_HOURS` lives here now and is imported there), so the
two surfaces cannot drift into quoting different numbers for the same design.

Qt-free, dependency-injectable, JSON-serialisable.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Callable, Optional

from src import succession

# ── The shared effort model ──────────────────────────────────────────────────
# Annual hours per plant, by type, at a mature steady state. Moved here from
# src/planning_panel.py (which now imports them) so the Effort tab and this
# calendar quote one set of numbers.
PLANT_MAINTENANCE_HOURS: dict[str, float] = {
    "tree":        3.0,   # pruning, watering establishment
    "shrub":       2.5,   # pruning, mulching
    "herb":        1.5,   # dividing, weeding
    "wildflower":  1.5,
    "grass":       1.0,
    "groundcover": 0.5,   # minimal once established
    "vine":        3.0,   # training, pruning
    "root":        1.0,   # harvest, replant
}
_HOURS_FALLBACK = 1.5

#: Per-band multipliers on the steady-state hours. Natives ramp down hard once
#: established; cultivated plants stay near a steady annual cost. Same values
#: the Effort tab has always used for years 1 and 3+, extended across the bands.
_BAND_MULT_NATIVE = {"establish": 2.0, "fill": 1.0, "close": 0.5, "mature": 0.3}
_BAND_MULT_CULTIVATED = {"establish": 1.5, "fill": 1.3, "close": 1.1,
                         "mature": 1.0}

#: An estimate is a spread, not a figure. ±35% is wide enough to be honest about
#: how much this varies with the weather, the weeds and the gardener.
_HOURS_SPREAD = 0.35

# ── The bands ────────────────────────────────────────────────────────────────
# Year ranges chosen to line up with succession.restoration_stage, so the
# calendar and the 3D year slider tell the same story about the same years.

_BANDS = (
    {
        "key": "establish", "years": (1, 1), "label": "Year 1",
        "headline": "Establishment — the year that decides it",
        "tasks": (
            "Water DEEPLY once a week through the first summer — about 15–20 mm "
            "at a time, at the base, not a daily sprinkle. This is the single "
            "thing that decides whether a native planting survives; \"natives "
            "don't need water\" is true of an established planting and false of "
            "a new one.",
            "Weed hard and often. Young natives are slower than the weed seed "
            "bank you just exposed; the first two seasons are when you win or "
            "lose that race.",
            "Top the mulch up if it has thinned, keeping it off the stems.",
            "Do not fertilise. It feeds the weeds and makes the natives leggy.",
            "Walk it monthly and write down what you see — Planning → Notes. "
            "Year-one observations are the most useful ones you will ever take.",
        ),
    },
    {
        "key": "fill", "years": (2, 4), "label": "Years 2–4",
        "headline": "Filling in — taper the water, keep weeding",
        "tasks": (
            "Water only in a genuine drought, and deeply when you do. By the "
            "end of year 3 most of this should be on its own.",
            "Keep weeding, but less: as the matrix closes, gaps for weeds close "
            "with it.",
            "Top up mulch every 2–3 years, or let leaf litter take over the job.",
            "Cut back in SPRING, not fall — see the note below.",
            "Expect gaps and losses. Replace from the same species list rather "
            "than substituting; a hole that fills itself is the design working.",
        ),
    },
    {
        "key": "close", "years": (5, 9), "label": "Years 5–9",
        "headline": "Editing, not maintaining",
        "tasks": (
            "No irrigation in a normal year.",
            "Cut back the herbaceous layer in spring, in patches rather than "
            "all at once, so something is always standing.",
            "Thin or prune woody plants only where they crowd a path or a "
            "window — the crowding between plants is the design.",
            "Edit the self-seeders: this is when the plants start deciding the "
            "layout, and your job becomes choosing which volunteers to keep.",
        ),
    },
    {
        "key": "mature", "years": (10, None), "label": "Year 10+",
        "headline": "Climax — mostly watching",
        "tasks": (
            "An annual spring cut-back and a walk-through is close to the whole "
            "job.",
            "No water, no fertiliser, no mulch except where you disturb the "
            "ground.",
            "Keep taking notes. By now the planting knows things about your "
            "site that the app doesn't.",
        ),
    },
)

#: The first season, month by month, for the app's Alberta / prairie range.
#: Deliberately coarse — a frost date is not a calendar entry (P9).
_FIRST_YEAR_MONTHS = (
    (5, "Plant after your last frost date; water each plant in as you go."),
    (6, "Weekly deep watering begins. Weed weekly — small weeds pull easy."),
    (7, "Keep watering weekly through the heat. Check mulch depth."),
    (8, "Keep watering. Note what is flowering and what isn't."),
    (9, "Taper watering as nights cool. Last good month for planting woody "
        "stock."),
    (10, "Water everything deeply once before freeze-up, then stop."),
    (11, "LEAVE THE STEMS STANDING. Do not tidy. See the overwintering note."),
)

OVERWINTERING_NOTE = (
    "Cut back in spring, not fall. Hollow and pithy stems are where stem-nesting "
    "native bees spend the winter; lepidoptera overwinter as eggs and pupae on "
    "and under standing growth; seed heads feed birds through the cold. Leave "
    "the growth standing until things are reliably moving in spring, then cut "
    "to 20–40 cm and leave the stubble — the previous year's residents are "
    "still in there. Fall tidying removes most of the winter habitat this "
    "design exists to provide."
)


@dataclass
class MaintenanceBand:
    key: str
    label: str
    headline: str
    year_from: int
    year_to: Optional[int]
    stage: str                 # succession.restoration_stage for the band
    tasks: list = field(default_factory=list)
    hours_low: float = 0.0
    hours_high: float = 0.0


@dataclass
class MaintenanceCalendar:
    bands: list = field(default_factory=list)
    first_year_months: list = field(default_factory=list)
    structure_hours: float = 0.0
    structure_detail: list = field(default_factory=list)
    overwintering_note: str = OVERWINTERING_NOTE
    #: Species in THIS design whose stems shelter something over winter — the
    #: reason the spring-cut-back rule is not generic advice.
    overwintering_species: list = field(default_factory=list)
    caveats: list = field(default_factory=list)

    def as_dict(self) -> dict:
        return asdict(self)

    def band_for_year(self, year: int) -> Optional[MaintenanceBand]:
        for band in self.bands:
            if year >= band.year_from and (band.year_to is None
                                           or year <= band.year_to):
                return band
        return None


def _stage_span(year_from: int, year_to) -> str:
    """The restoration stage(s) a band covers.

    A band can straddle two stages (years 2–4 spans pioneer forbs and the
    forb–grass matrix); naming only the first would quietly disagree with the
    3D year slider halfway through the band.
    """
    start = succession.restoration_stage(year_from)
    end = succession.restoration_stage(year_to if year_to is not None
                                       else year_from)
    return start if start == end else f"{start} → {end}"


def _hours_range(low: float, high: float) -> tuple[float, float]:
    return (round(max(0.0, low * (1 - _HOURS_SPREAD)), 1),
            round(high * (1 + _HOURS_SPREAD), 1))


def _structure_hours(structures, get_structure=None) -> tuple[float, list]:
    """Annual structure upkeep, from the hard-coded structure catalogue."""
    total, detail = 0.0, []
    if not structures:
        return 0.0, []
    if get_structure is None:
        try:
            from src.db.structures import get_structure as _gs   # noqa: PLC0415
            get_structure = _gs
        except Exception:                                        # noqa: BLE001
            get_structure = None
    counts: dict = {}
    for s in structures:
        sid = (s or {}).get("id") or (s or {}).get("struct_id")
        rec = s
        if get_structure is not None and sid:
            rec = get_structure(sid) or s
        name = (rec or {}).get("name") or str(sid or "structure")
        hours = float((rec or {}).get("maintenance_hours_year") or 0.0)
        slot = counts.setdefault(name, {"qty": 0, "hours": hours})
        slot["qty"] += 1
        total += hours
    for name, slot in sorted(counts.items()):
        detail.append({"name": name, "qty": slot["qty"],
                       "hours_each": slot["hours"],
                       "hours_total": round(slot["hours"] * slot["qty"], 1)})
    return round(total, 1), detail


def overwintering_species(placed_plants, get_plant=None,
                          fauna_edges=None) -> list[str]:
    """Species in the design that documented fauna use for nesting or cover.

    This is what turns "cut back in spring" from received wisdom into a fact
    about the user's own bed. Documented edges only — nothing inferred (P9).
    """
    pids = sorted({int(p["plant_id"]) for p in (placed_plants or [])
                   if p.get("plant_id") is not None})
    if not pids:
        return []
    if fauna_edges is None:
        try:
            from src.db.fauna import fauna_for_plants as fauna_edges  # noqa: PLC0415
        except Exception:                                        # noqa: BLE001
            return []
    try:
        rows = list(fauna_edges(pids))
    except Exception:                                            # noqa: BLE001
        return []
    names: dict = {p["plant_id"]: p.get("common_name", "")
                   for p in (placed_plants or []) if p.get("plant_id")}
    out = set()
    for r in rows:
        if (r.get("relationship") or "") in ("nesting", "cover"):
            pid = r.get("plant_id")
            if pid in names and names[pid]:
                out.add(names[pid])
    return sorted(out)


def build_maintenance_calendar(placed_plants, structures=None, *,
                               get_plant: Optional[Callable] = None,
                               get_structure: Optional[Callable] = None,
                               fauna_edges: Optional[Callable] = None,
                               ) -> MaintenanceCalendar:
    """Assemble the year-by-year cadence for a placed design."""
    if get_plant is None:
        from src.db.plants import get_plant as _gp                # noqa: PLC0415
        get_plant = _gp

    # Steady-state hours, split native / cultivated so the ramp-down is honest
    # about which plants actually ramp down.
    native_base = cultivated_base = 0.0
    for p in placed_plants or []:
        pid = p.get("plant_id")
        plant = (get_plant(pid) or {}) if pid is not None else {}
        ptype = (p.get("plant_type") or plant.get("plant_type")
                 or "herb").strip().lower()
        base = PLANT_MAINTENANCE_HOURS.get(ptype, _HOURS_FALLBACK)
        native = p.get("native_to_alberta")
        if native is None:
            native = plant.get("native_to_alberta")
        if native:
            native_base += base
        else:
            cultivated_base += base

    struct_hours, struct_detail = _structure_hours(structures, get_structure)

    bands = []
    for spec in _BANDS:
        y_from, y_to = spec["years"]
        hours = (native_base * _BAND_MULT_NATIVE[spec["key"]]
                 + cultivated_base * _BAND_MULT_CULTIVATED[spec["key"]]
                 + struct_hours)
        lo, hi = _hours_range(hours, hours)
        bands.append(MaintenanceBand(
            key=spec["key"], label=spec["label"], headline=spec["headline"],
            year_from=y_from, year_to=y_to,
            stage=_stage_span(y_from, y_to),
            tasks=list(spec["tasks"]),
            hours_low=lo, hours_high=hi))

    cal = MaintenanceCalendar(
        bands=bands,
        first_year_months=[{"month": m, "task": t}
                           for m, t in _FIRST_YEAR_MONTHS],
        structure_hours=struct_hours,
        structure_detail=struct_detail,
        overwintering_species=overwintering_species(
            placed_plants, get_plant, fauna_edges),
    )
    cal.caveats.append(
        "Hours are estimates with a wide spread — how weedy the ground was, "
        "how the summer goes and how fussy you are all move them more than the "
        "plant list does. The shape matters more than the numbers: the work "
        "falls by roughly two thirds as the natives establish."
    )
    if not any(b.hours_low for b in bands):
        cal.caveats.append("No plants placed yet, so there is nothing to cost.")
    return cal


_MONTH_NAME = ["", "January", "February", "March", "April", "May", "June",
               "July", "August", "September", "October", "November", "December"]


def render_maintenance_text(cal: MaintenanceCalendar) -> str:
    """Plain-text section for the Planting Plan export."""
    lines = ["MAINTENANCE — YEAR BY YEAR", "=" * 44, ""]
    for band in cal.bands:
        span = (f"{band.label}" if band.year_to is not None
                else f"{band.label}")
        lines.append(f"{span}  ·  {band.stage}")
        lines.append(f"  {band.headline}")
        lines.append(f"  About {band.hours_low:.0f}–{band.hours_high:.0f} "
                     f"hours/year")
        for task in band.tasks:
            for i, chunk in enumerate(_wrap(task, 66)):
                lines.append(("    • " if i == 0 else "      ") + chunk)
        lines.append("")

    lines.append("FIRST SEASON, MONTH BY MONTH")
    lines.append("-" * 44)
    for entry in cal.first_year_months:
        name = _MONTH_NAME[entry["month"]]
        chunks = _wrap(entry["task"], 58)
        lines.append(f"  {name:<10} {chunks[0]}")
        for chunk in chunks[1:]:
            lines.append(f"  {'':<10} {chunk}")
    lines.append("")

    lines.append("WHY SPRING AND NOT FALL")
    lines.append("-" * 44)
    for chunk in _wrap(cal.overwintering_note, 68):
        lines.append(f"  {chunk}")
    if cal.overwintering_species:
        shown = ", ".join(cal.overwintering_species[:8])
        more = (f" +{len(cal.overwintering_species) - 8} more"
                if len(cal.overwintering_species) > 8 else "")
        lines.append("")
        for chunk in _wrap(
                f"In this design, documented nesting or cover for wildlife: "
                f"{shown}{more}.", 68):
            lines.append(f"  {chunk}")
    lines.append("")

    if cal.structure_detail:
        lines.append("STRUCTURE UPKEEP")
        lines.append("-" * 44)
        for s in cal.structure_detail:
            lines.append(f"  {s['name']} ×{s['qty']}  —  "
                         f"{s['hours_total']:.1f} h/year")
        lines.append("")

    if cal.caveats:
        lines.append("HOW SURE IS THIS?")
        lines.append("-" * 44)
        for caveat in cal.caveats:
            for chunk in _wrap(caveat, 68):
                lines.append(f"  {chunk}")
            lines.append("")
    return "\n".join(lines).rstrip() + "\n"


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
