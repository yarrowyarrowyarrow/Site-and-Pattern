"""
src/planting_plan.py — the design → buy-it-and-plant-it handoff (F40).

Turns a placed design into the artifact a homeowner actually carries to the
nursery and out to the yard. It answers the three questions that otherwise stall
a design on the screen:

  * **What do I buy?** — species, quantity, nursery *form* (container / plug /
    seed / bulb), per-species price range, grouped by nursery source.
  * **When do I plant it?** — a per-species planting window (from the Edmonton
    calendar) and a phased order (structure → matrix → fill) to work top-to-bottom.
  * **How far apart?** — centre-to-centre spacing per species.

It consolidates and supersedes the plant-order text that used to live inside
``MainWindow`` and feeds both the text export and the PDF. Qt-free and
dependency-injectable so the CLI, the exporters and the tests share one
definition, reusing the existing costing (:mod:`src.sourcing`), spacing
(:mod:`src.planting_spacing`), succession roles (:mod:`src.succession`) and the
Edmonton planting calendar (:mod:`src.db.calendar_data`).

Design principle P8 (repair is more sophisticated than creation — the conversion
*plan* is first-class) and P11 (the body and the site know things the screen does
not — drive the user outside with a real field plan) — see docs/DESIGN_PHILOSOPHY.md.
"""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass

from src.branding import APP_NAME
from src import sourcing
from src import planting_spacing
from src import succession


# Form (seed / plug / container) inferred from plant_type — native nurseries
# commonly stock woody plants as containers, herbaceous as plugs/seed, roots as
# bulbs/tubers. (Lifted from the former app.py order-list builder.)
_FORM_BY_TYPE = {
    "tree": "container",
    "shrub": "container",
    "vine": "container",
    "herb": "plug or seed",
    "groundcover": "plug or seed",
    "root": "bulb / tuber",
}
_FORM_FALLBACK = "plug or seed"

# Alberta native plant / seed sources (display name + buy link).
NURSERIES = [
    ("ALCLA Native Plants", "https://alclanativeplants.com/"),
    ("Bow Valley Habitat Development", "https://bowvalleyhabitat.com/"),
    ("Wild About Flowers", "https://wildaboutflowers.ca/"),
    ("Bedrock Seed Bank", "https://bedrockseedbank.ca/"),
]

# Nursery-source buckets, in display order, with their section headings.
SOURCE_SECTIONS = [
    ("native_woody", "NATIVE TREES & SHRUBS  (sources: ALCLA, Bow Valley Habitat)"),
    ("native_herb",  "NATIVE HERBACEOUS & GROUNDCOVER  "
                     "(sources: ALCLA, Wild About Flowers, Bedrock Seed Bank)"),
    ("cultivated",   "CULTIVATED / NON-NATIVE  (sources: local garden centres)"),
]

# Phases: the order a conversion actually goes into the ground — woody structure
# first, then the herbaceous matrix, then the gap-filling self-spreaders. (P8/P4)
PHASE_STRUCTURE = "Phase 1 — Structure (trees & shrubs)"
PHASE_MATRIX = "Phase 2 — Matrix (perennials & groundcover)"
PHASE_FILL = "Phase 3 — Fill (self-spreaders & gaps)"
PHASES = [
    (PHASE_STRUCTURE, "spring after soil thaws, or early fall"),
    (PHASE_MATRIX, "late spring, after the last frost"),
    (PHASE_FILL, "spring or fall — they fill in over time"),
]

_SPREADERS = ("self_seeding", "slow_spreader", "aggressive_rhizomatous")
_MON_ABBR = ["", "Jan", "Feb", "Mar", "Apr", "May", "Jun",
             "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
_PLANTING_STATUSES = ("transplant", "direct_sow")

_CAL_INDEX: dict | None = None


@dataclass
class PlantingItem:
    """One species in the plan, with everything needed to buy and plant it."""
    plant_id: int
    common_name: str
    scientific_name: str
    plant_type: str
    qty: int
    form: str
    unit_low: float
    unit_high: float
    spacing_m: float
    planting_window: str
    source_bucket: str   # native_woody | native_herb | cultivated
    role: str            # pioneer | mid | climax
    phase: str

    @property
    def ext_low(self) -> float:
        return round(self.unit_low * self.qty, 2)

    @property
    def ext_high(self) -> float:
        return round(self.unit_high * self.qty, 2)


@dataclass
class PlantingPlan:
    """A whole design as a buy-it / plant-it sheet."""
    items: list            # list[PlantingItem], sorted by common name
    total_plants: int
    species_count: int
    native_count: int
    cultivated_count: int
    plants_low: float
    plants_high: float
    struct_low: float
    struct_high: float
    mulch_low: float
    mulch_high: float
    bed_area_m2: float
    structures_detail: list  # [(name, qty, low, high), …]

    @property
    def grand_low(self) -> float:
        return round(self.plants_low + self.struct_low + self.mulch_low, 2)

    @property
    def grand_high(self) -> float:
        return round(self.plants_high + self.struct_high + self.mulch_high, 2)

    def items_by_source(self, bucket: str) -> list:
        return [i for i in self.items if i.source_bucket == bucket]

    def items_by_phase(self, phase: str) -> list:
        return [i for i in self.items if i.phase == phase]


def _source_bucket(native: bool, ptype: str) -> str:
    if native and ptype in ("tree", "shrub", "vine"):
        return "native_woody"
    if native:
        return "native_herb"
    return "cultivated"


def _spacing_for(plant: dict) -> float:
    """Centre-to-centre spacing (m): the plant's own ``spacing_m`` when present,
    else the naturalistic layer/spread-aware estimate."""
    explicit = plant.get("spacing_m")
    if explicit:
        try:
            return round(float(explicit), 2)
        except (TypeError, ValueError):
            pass
    return planting_spacing.plant_spacing(plant, base_m=0.45)


def _phase_for(plant: dict) -> str:
    layer = planting_spacing.layer_of(plant.get("plant_type"))
    if layer in ("canopy", "shrub"):
        return PHASE_STRUCTURE
    if (plant.get("spread_habit") or "").strip().lower() in _SPREADERS:
        return PHASE_FILL
    return PHASE_MATRIX


def _calendar_index() -> dict:
    """Lazy ``common_name(lower) -> sorted planting months`` from the Edmonton
    calendar — the months a species is actually transplanted / direct-sown."""
    global _CAL_INDEX
    if _CAL_INDEX is None:
        try:
            from src.db.calendar_data import SEED_CALENDAR
        except Exception:
            SEED_CALENDAR = []
        idx: dict = {}
        for name, month, status, _notes in SEED_CALENDAR:
            if status in _PLANTING_STATUSES:
                idx.setdefault(str(name).strip().lower(), set()).add(int(month))
        _CAL_INDEX = idx
    return _CAL_INDEX


def _format_months(months) -> str:
    """Compact consecutive months as abbreviated ranges, e.g. ``Apr–May, Sep``."""
    months = sorted(set(months))
    if not months:
        return ""
    groups: list = []
    start = prev = months[0]
    for m in months[1:]:
        if m == prev + 1:
            prev = m
        else:
            groups.append((start, prev))
            start = prev = m
    groups.append((start, prev))
    return ", ".join(_MON_ABBR[a] if a == b else f"{_MON_ABBR[a]}–{_MON_ABBR[b]}"
                     for a, b in groups)


def planting_window(plant: dict) -> str:
    """When to plant this species outdoors: the calendar's transplant/direct-sow
    months when known, else a sensible default by type. Never empty (P9 — honest
    guidance, not false precision)."""
    name = (plant.get("common_name") or "").strip().lower()
    months = _calendar_index().get(name)
    if months:
        return _format_months(months)
    ptype = (plant.get("plant_type") or "").strip().lower()
    if ptype in ("tree", "shrub", "vine"):
        return "Spring after soil thaws (≈May), or early fall"
    if ptype == "root":
        return "Spring (≈May), or fall dormancy"
    return "Late spring, after the last frost (late May–Jun)"


def _structures_detail(structures, get_structure) -> list:
    """``[(name, qty, low, high), …]`` install cost per structure type."""
    if get_structure is None:
        try:
            from src.db.structures import get_structure as _gs
            get_structure = _gs
        except Exception:
            get_structure = lambda _sid: None
    counts: Counter = Counter()
    sdef_by_id: dict = {}
    for s in structures or []:
        sid = s.get("id") if isinstance(s, dict) else s
        counts[sid] += 1
        if isinstance(s, dict):
            sdef_by_id.setdefault(sid, s)
    out: list = []
    for sid, n in sorted(counts.items(), key=lambda kv: str(kv[0])):
        sdef = sdef_by_id.get(sid, {})
        catalogue = get_structure(sid) or {}
        nm = sdef.get("name") or catalogue.get("name") or (sid or "structure")
        ic = catalogue.get("install_cost_cad") or sdef.get("install_cost_cad") or (0.0, 0.0)
        out.append((nm, n, round(ic[0] * n, 2), round(ic[1] * n, 2)))
    return out


def build_planting_plan(placed_plants, structures=None, bed_area_m2: float = 0.0,
                        get_plant=None, get_structure=None) -> PlantingPlan:
    """Aggregate a placed design into a :class:`PlantingPlan`.

    ``placed_plants`` are placed-plant dicts (``plant_id`` / ``common_name``);
    ``structures`` are structure-definition dicts (as stored on a placed feature's
    ``struct_def``); ``bed_area_m2`` is the drawn bed area to mulch. ``get_plant``
    / ``get_structure`` are injectable for tests."""
    if get_plant is None:
        from src.db.plants import get_plant as _gp
        get_plant = _gp

    counts: Counter = Counter()
    names: dict = {}
    for p in placed_plants or []:
        pid = p.get("plant_id")
        if pid is None:
            continue
        counts[pid] += 1
        names[pid] = p.get("common_name", "?")

    items: list = []
    plants_low = plants_high = 0.0
    native_count = cultivated_count = 0
    for pid, qty in counts.items():
        plant = get_plant(pid) or {}
        ptype = (plant.get("plant_type") or "other").strip().lower()
        native = bool(plant.get("native_to_alberta"))
        lo, hi = sourcing.plant_price_range(plant)
        item = PlantingItem(
            plant_id=pid,
            common_name=names.get(pid) or plant.get("common_name", "?"),
            scientific_name=plant.get("scientific_name", "") or "",
            plant_type=ptype,
            qty=qty,
            form=_FORM_BY_TYPE.get(ptype, _FORM_FALLBACK),
            unit_low=lo,
            unit_high=hi,
            spacing_m=_spacing_for(plant),
            planting_window=planting_window(plant),
            source_bucket=_source_bucket(native, ptype),
            role=succession.successional_role(plant),
            phase=_phase_for(plant),
        )
        items.append(item)
        plants_low += item.ext_low
        plants_high += item.ext_high
        if native:
            native_count += qty
        else:
            cultivated_count += qty

    items.sort(key=lambda i: i.common_name.lower())

    struct_low, struct_high = sourcing.structure_cost(
        structures or [], get_structure=get_structure)
    mulch_low, mulch_high = sourcing.mulch_cost(bed_area_m2)

    return PlantingPlan(
        items=items,
        total_plants=sum(counts.values()),
        species_count=len(counts),
        native_count=native_count,
        cultivated_count=cultivated_count,
        plants_low=round(plants_low, 2),
        plants_high=round(plants_high, 2),
        struct_low=struct_low,
        struct_high=struct_high,
        mulch_low=mulch_low,
        mulch_high=mulch_high,
        bed_area_m2=float(bed_area_m2 or 0.0),
        structures_detail=_structures_detail(structures or [], get_structure),
    )


def render_plan_text(plan: PlantingPlan) -> str:
    """Render a :class:`PlantingPlan` as the plain-text export (nursery list +
    phased planting schedule)."""
    fc = sourcing.format_cost
    lines = [
        f"{APP_NAME} — Planting Plan",
        "=" * 44,
        "",
        "WHAT TO BUY  (by nursery source)",
        "",
    ]
    for bucket, title in SOURCE_SECTIONS:
        bucket_items = plan.items_by_source(bucket)
        if not bucket_items:
            continue
        lines.append(title)
        lines.append("-" * len(title))
        sub_lo = sub_hi = 0.0
        for it in bucket_items:
            line = f"  {it.common_name}"
            if it.scientific_name:
                line += f"  ({it.scientific_name})"
            line += (f"  ×{it.qty}  [{it.form}]  space ~{it.spacing_m:g} m  "
                     f"~{fc(it.ext_low, it.ext_high)}")
            lines.append(line)
            sub_lo += it.ext_low
            sub_hi += it.ext_high
        lines.append(f"  Subtotal: {fc(sub_lo, sub_hi)}")
        lines.append("")

    if plan.structures_detail or plan.bed_area_m2 > 0:
        title = "SITE PREP & STRUCTURES  (estimated install / materials)"
        lines.append(title)
        lines.append("-" * len(title))
        for nm, n, lo, hi in plan.structures_detail:
            lines.append(f"  {nm}  ×{n}  ~{fc(lo, hi)}")
        if plan.bed_area_m2 > 0:
            lines.append(f"  Mulch — {plan.bed_area_m2:,.0f} m² @ 7.5 cm  "
                         f"~{fc(plan.mulch_low, plan.mulch_high)}")
        lines.append("")

    lines.append("=" * 44)
    lines.append(
        f"Total: {plan.total_plants} plants ({plan.species_count} species)  "
        f"— {plan.native_count} native, {plan.cultivated_count} cultivated"
    )
    lines.append(f"Plants:           {fc(plan.plants_low, plan.plants_high)}")
    if plan.structures_detail:
        lines.append(f"Structures:       {fc(plan.struct_low, plan.struct_high)}")
    if plan.bed_area_m2 > 0:
        lines.append(f"Mulch:            {fc(plan.mulch_low, plan.mulch_high)}")
    lines.append(
        f"ESTIMATED TOTAL:  {fc(plan.grand_low, plan.grand_high)}  "
        f"(AB retail/install estimate — varies by nursery, year, site)"
    )
    lines.append("")

    lines.append("WHEN TO PLANT  (phased — work top to bottom)")
    lines.append("")
    for phase, season in PHASES:
        phase_items = plan.items_by_phase(phase)
        if not phase_items:
            continue
        lines.append(f"{phase}  ·  {season}")
        for it in phase_items:
            lines.append(f"  {it.common_name} ×{it.qty} — {it.planting_window}")
        lines.append("")

    lines.append("Alberta native plant nurseries / seed sources:")
    for nm, url in NURSERIES:
        lines.append(f"  • {nm:<32} {url}")

    return "\n".join(lines)
