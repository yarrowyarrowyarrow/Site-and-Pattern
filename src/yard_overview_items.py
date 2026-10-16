"""
yard_overview_items.py — how your yard is doing, in six plain items (OV-1,
V3.27; docs/homeowner/06-yard-overview.md §4–§6).

Design principle P6 — see docs/DESIGN_PHILOSOPHY.md.

The Design tab had six pages and two thousand words, two habitat scores for one
design and no line saying how much of the bed would be planted. The overview
answers the questions a homeowner brings, always in this order (O7): who it
feeds, when it flowers, whether the plants belong here, how full it will be,
how it will look from the street, and what it will take. Each item has a status
word, a few lines and one action.

**One number, one source** (§4 rule 5): every figure is computed by the function
the advanced page and the PDF use (``what_it_feeds``, ``design_native``,
``cues_to_care``, ``sourcing``, ``maintenance_calendar``, ``water_budget``,
``yard_overview``), never restated here. **No score** (O1): the 0–100 number
stays on the advanced pages. **Records, not claims** (O4, P9): "recorded as
food for", with the fixed caveat, and an animal is named only by an English
name (WD-7). No bylaw sentence (O5): a pack may carry ``overview.street_rule``
and Edmonton's does not.

Qt-free. ``overview(project)`` returns :class:`Item` rows; the page, the PDF and
the API draw them.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable, Optional

GOOD, LOOK, PLAN = "good", "look", "plan"
#: The status words (§4 rule 7): never a symbol alone.
STATUS_WORDS = {GOOD: "Looks good", LOOK: "Worth a look", PLAN: "To plan for"}

TITLE = "How your yard is doing"
EMPTY = ("Add some plants, or use Plan my yard, to see how your yard is "
         "doing.")
CAVEAT = ("Records from across Alberta and Saskatchewan: what visits depends "
          "on what lives nearby.")
FILL_LINE = ("Weeds move into bare ground: fill the gaps, or keep them "
             "mulched while the plants spread.")
#: How many birds that eat a design's seed or fruit is enough (§5 item 1).
FEW_BIRDS = 3

MONTHS = ("January", "February", "March", "April", "May", "June", "July",
          "August", "September", "October", "November", "December")
#: The flowering strip's months, April to October.
STRIP = tuple(range(4, 11))

#: The street cues: (what is there, the next step, the action, its target).
#: Only a drawn shape has an action; the order is ``cues_to_care``'s.
_CUES = {
    "mown_edge": ("a mown strip", "a mown strip about a metre wide along the "
                  "street", "Draw a mown strip", "shape:Lawn Area"),
    "crisp_border": ("a clear edge", "a clear edge around the bed",
                     "Draw the bed's edge", "shape:Garden Bed"),
    "height_graded": ("tall plants at the back", "the tallest plants toward "
                      "the back", "", ""),
    "visible_path": ("a path", "a path or a way in", "Draw a path",
                     "shape:Pathway"),
    "showy_repeat": ("a repeated showy flower", "one showy flower repeated "
                     "three or more times", "", ""),
}


@dataclass
class Item:
    """One card: its title, status, lines and one action (``target`` is what
    ``yard_overview_flow.run_action`` does). ``more`` is MD-4's link to the
    advanced page that explains it; ``strip`` the flowering months' counts."""
    key: str
    title: str
    status: str
    lines: list
    action: str = ""
    target: str = ""
    more: tuple = ()
    strip: list = field(default_factory=list)

    @property
    def status_word(self) -> str:
        return STATUS_WORDS.get(self.status, "")


@dataclass
class Design:
    """What the items read, gathered once."""
    project: dict
    placed: list
    ids: list
    rows: dict
    site: dict
    structures: list
    get_plant: Callable


def _gather(project: dict, get_plant: Optional[Callable]) -> Design:
    from src.project_store import ProjectStore
    if get_plant is None:
        from src.db.plants import get_plant                   # noqa: PLC0415
    placed = list(ProjectStore(project).placed_plants)
    rows: dict = {}
    for p in placed:
        pid = p.get("plant_id")
        if pid not in rows:
            rows[pid] = get_plant(pid) or {}
    site = ((project or {}).get("properties") or {}).get("site_config") or {}
    structures = [(f.get("properties") or {}).get("struct_def") or {}
                  for f in (project or {}).get("features", []) or []
                  if (f.get("properties") or {}).get("element_type")
                  == "structure"]
    return Design(project, placed, list(rows), rows, site, structures,
                  get_plant)


def _and(names: list) -> str:
    names = [n for n in names if n]
    if len(names) <= 1:
        return "".join(names)
    return ", ".join(names[:-1]) + " and " + names[-1]


def _kinds(n: int, one: str, many: str) -> str:
    return f"{n} {one if n == 1 else many}"


# ── 1. Food for wildlife ────────────────────────────────────────────────────

def english_name(animal: dict) -> str:
    """The animal's English name, or ``""`` when the catalogue has only its
    Latin name or a generic one ("A Leafcutter Bee") (WD-7)."""
    name = (animal.get("name") or animal.get("common_name") or "").strip()
    if (not name or name == (animal.get("scientific_name") or "").strip()
            or name.split(" ", 1)[0] in ("A", "An")):
        return ""
    return name


def example_animal(animals: list, familiar: tuple = ()) -> str:
    """The one animal the item names (§5.2): from the pack's familiar list
    when it has one (O4), else a bird that eats the seed or fruit, else a
    butterfly or moth, else a bumble bee; most of the design's plants first."""
    named = [a for a in animals if a["food"] and english_name(a)]
    if familiar:
        known = [a for a in named if english_name(a) in familiar]
        if known:
            return english_name(known[0])

    def eats_fruit(a):
        return any(k in ("fruit_food", "seed_food")
                   for ks in a["plants"].values() for k in ks)
    for test in (lambda a: a["taxon"] == "bird" and eats_fruit(a),
                 lambda a: a["taxon"] == "lepidoptera",
                 lambda a: (a.get("scientific_name") or "").startswith(
                     "Bombus")):
        pick = [a for a in named if test(a)]
        if pick:                     # animals_fed sorts most plants first
            return english_name(pick[0])
    return ""


def item_food(d: Design) -> Item:
    from src import what_it_feeds as w
    animals = w.animals_fed(d.ids)
    counts = w.food_counts(d.ids)
    bees, leps, birds = (counts.get(t, 0) for t in ("bee", "lepidoptera",
                                                    "bird"))
    fruit_birds = sum(
        1 for a in animals if a["taxon"] == "bird" and any(
            k in ("fruit_food", "seed_food")
            for ks in a["plants"].values() for k in ks))
    groups = [g for g in (
        _kinds(bees, "kind of bee", "kinds of bee") if bees else "",
        f"{leps} of butterfly and moth" if leps else "",
        f"{birds} of bird" if birds else "") if g]
    from src import region
    pack = region.for_site(d.site) or region.default()
    name = example_animal(animals, tuple(
        (pack.overview or {}).get("familiar_animals") or ()))
    if groups:
        line = f"Recorded as food for {_and(groups)}"
        line += f", such as the {name}." if name else "."
    else:
        line = "No animal is recorded eating these plants yet."
    lines = [line]
    look = fruit_birds < FEW_BIRDS
    if look and groups:
        lines.append(f"Few birds: only {_kinds(fruit_birds, 'kind eats', 'kinds eat')}"
                     " its seeds or berries.")
    lines.append(CAVEAT)
    if look:
        return Item("food", "Food for wildlife", LOOK, lines,
                    "Add a berry shrub", "plants:berry_shrub",
                    ("See who it feeds", "advanced:food"))
    return Item("food", "Food for wildlife", GOOD, lines,
                "See who it feeds ▸", "advanced:food")


# ── 2. Flowers through the season ───────────────────────────────────────────

def item_flowers(d: Design) -> Item:
    from src.what_it_feeds import month_by_month
    months = month_by_month(d.ids)["months"]
    counts = {m["month"]: len(m["pollinators"]) for m in months}
    flowering = [m for m in range(1, 13) if counts[m]]
    strip = [(MONTHS[m - 1][:3], counts[m]) for m in STRIP]
    if not flowering:
        return Item("flowers", "Flowers through the season", LOOK,
                    ["None of these plants has a recorded flowering time "
                     "for pollinators."],
                    "Find a flower", "plants:blooms_in=6", strip=strip)
    gaps = [m for m in STRIP if not counts[m]]
    ones = [m for m in STRIP if counts[m] == 1]
    first, last = MONTHS[flowering[0] - 1], MONTHS[flowering[-1] - 1]
    line = (f"In flower from {first} to {last}." if first != last
            else f"In flower in {first}.")
    notes = []
    if gaps:
        notes.append(f"Nothing in {_and([MONTHS[m - 1] for m in gaps])}")
    if ones:
        notes.append(f"only one kind in {_and([MONTHS[m - 1] for m in ones])}")
    if notes:
        text = ", and ".join(notes) if len(notes) == 2 else notes[0]
        line += " " + text[0].upper() + text[1:] + "."
    if gaps:
        month = MONTHS[gaps[0] - 1]
        article = "an" if month[0] in "AEIOU" else "a"
        return Item("flowers", "Flowers through the season", LOOK, [line],
                    f"Find {article} {month} flower",
                    f"plants:blooms_in={gaps[0]}",
                    ("See what flowers when", "advanced:food"), strip)
    return Item("flowers", "Flowers through the season", GOOD, [line],
                "See what flowers when ▸", "advanced:food", strip=strip)


# ── 3. Right plants for here ────────────────────────────────────────────────

def item_native(d: Design) -> Item:
    from src import design_native
    title = "Right plants for here"
    if d.site.get("latitude") is None or d.site.get("longitude") is None:
        return Item("native", title, LOOK,
                    ["Put a pin on your address to check the plants against "
                     "the ones native where you are."],
                    "Find my address", "site:pin")
    is_native = design_native.rule(d.site)
    where = design_native.words(d.site)
    names = {pid: (r.get("common_name") or "") for pid, r in d.rows.items()}
    away = sorted((pid for pid, r in d.rows.items() if not is_native(r)),
                  key=lambda pid: names[pid].lower())
    total = len(d.rows)
    kinds = _kinds(total, "kind of plant", "kinds of plant")
    if not away:
        line = (f"The one kind of plant is {where}." if total == 1
                else f"All {kinds} are {where}.")
        return Item("native", title, GOOD, [line],
                    "See the plant list", "page:planted")
    shown = [names[p] for p in away[:3]]
    more = len(away) - len(shown)
    tail = _and(shown + ([f"{more} more"] if more else []))
    line = (f"{total - len(away)} of {kinds} are {where}. {tail} "
            f"{'is' if len(away) == 1 else 'are'} not.")
    return Item("native", title, LOOK, [line], f"Swap {names[away[0]]}",
                f"swap:{away[0]}")


# ── 4. How full it will be ──────────────────────────────────────────────────

def item_cover(d: Design) -> Item:
    from src import yard_overview as yo
    title = "How full it will be"
    try:
        c = yo.cover(d.project, get_plant=d.get_plant)
    except ImportError:                       # no shapely: say nothing wrong
        c = None
    if c is None:
        return Item("cover", title, LOOK,
                    ["Outline your yard, or the beds you are planting, to see "
                     "how much of it the plants will cover."],
                    "Outline my yard", "draw:boundary")
    words = yo.share_words(c["share"])
    line = (f"Once grown, the plants will cover {words} of the area you "
            f"outlined ({c['covered_m2']:.0f} of {c['area_m2']:.0f} m²).")
    lines = [line]
    parts = yo.parts_words(yo.yard_parts(d.project))
    if parts:
        lines.append(parts)
    if c["share"] >= yo.WELL_FILLED:
        return Item("cover", title, GOOD, lines)
    lines.append(FILL_LINE)
    return Item("cover", title, LOOK, lines, "Ways to fill the gaps",
                "fill_gaps")


# ── 5. How it will look from the street ─────────────────────────────────────

def item_street(d: Design) -> Item:
    from src import cues_to_care, region
    title = "How it will look from the street"
    cues = [c for c in cues_to_care.assess(d.project, get_plant=d.get_plant)
            if c.key in _CUES and c.present is not None]
    have = [_CUES[c.key][0] for c in cues if c.present]
    lacking = [c for c in cues if c.present is False]
    lines = []
    if cues:
        verb = "is" if len(have) == 1 else "are"
        first = f"{len(have)} of {len(cues)} signs of care {verb} in place"
        lines.append(first + (f": {_and(have)}." if have else "."))
    pack = region.for_site(d.site) or region.default()
    rule = ((pack.overview or {}).get("street_rule") or "").strip()
    if not lacking:
        if rule:
            lines.append(rule)
        return Item("street", title, GOOD, lines or [
            "Signs of care are in place."])
    nxt = lacking[0]
    _have, step, action, target = _CUES[nxt.key]
    text = f"Most useful next: {step}"
    if nxt.key == "mown_edge":
        side = cues_to_care.frontage_for(d.project)
        if not side.measured:
            text += f" (taken to be the {side.side} side)"
    lines.append(text + ".")
    if rule:
        lines.append(rule)
    return Item("street", title, LOOK, lines, action, target)


# ── 6. What it will take ────────────────────────────────────────────────────

def _range(lo: float, hi: float, unit: str = "") -> str:
    lo_s, hi_s = f"{lo:,.0f}", f"{hi:,.0f}"
    return f"{lo_s}{unit}" if lo_s == hi_s else f"{lo_s}–{hi_s}{unit}"


def _dollars(lo: float, hi: float) -> str:
    from src.sourcing import format_cost
    return format_cost(lo, hi) if round(lo) != round(hi) else f"${lo:,.0f}"


def item_cost(d: Design) -> Item:
    from src import sourcing, water_budget, region
    from src.maintenance_calendar import build_maintenance_calendar
    from src.site_prep import MULCH_DEPTH_CM
    from src.yard_overview import bed_area_m2
    pack = region.for_site(d.site) or region.default()
    note = ((pack.overview or {}).get("price_note") or "").strip()
    lo, hi = sourcing.estimate_cost(d.placed, get_plant=d.get_plant)
    n = len(d.placed)
    line = (f"Plants: about {_dollars(lo, hi)} for "
            f"{_kinds(n, 'plant', 'plants')}" + (f" {note}." if note else "."))
    area = bed_area_m2(d.project)
    if area > 0:
        m_lo, m_hi = sourcing.mulch_cost(area)
        v_lo = area * MULCH_DEPTH_CM[0] / 100.0
        v_hi = area * MULCH_DEPTH_CM[1] / 100.0
        line += (f" Mulch: {_range(max(1, v_lo), max(1, v_hi))} m³ of wood "
                 f"chips (often free; {_dollars(m_lo, m_hi)} bought).")
    s_lo, s_hi = sourcing.structure_cost(d.structures)
    if s_hi > 0:
        line += f" Structures: {_dollars(s_lo, s_hi)}."
    enriched = [dict(p, **{k: d.rows.get(p.get("plant_id"), {}).get(k)
                           for k in ("plant_type", "water_needs")},
                     native=bool(d.rows.get(p.get("plant_id"), {})
                                 .get("native_to_alberta")))
                for p in d.placed]
    cal = build_maintenance_calendar(d.placed, d.structures,
                                     get_plant=d.get_plant)
    first, last = cal.bands[0], cal.bands[-1]
    work = (f"First year: {_range(first.hours_low, first.hours_high)} hours "
            "of work, mostly weeding")
    litres = water_budget.first_summer_weekly_litres(enriched)
    if litres > 0:
        work += (", and a deep soak once a week in any week without a good "
                 f"rain (about {water_budget._round_litres(litres)} L)")
    lines = [line, work + ".",
             f"Once it has filled in: {_range(last.hours_low, last.hours_high)}"
             " hours a year."]
    return Item("cost", "What it will take", PLAN, lines,
                "Print the shopping list and care plan", "export:pdf",
                ("See the hours", "advanced:over_time"))


BUILDERS = (item_food, item_flowers, item_native, item_cover, item_street,
            item_cost)


def overview(project: dict, *, get_plant: Optional[Callable] = None) -> list:
    """The six items in their fixed order (O7), or one empty-state item."""
    d = _gather(project, get_plant)
    if not d.placed:
        return [Item("empty", TITLE, LOOK, [EMPTY], "Plan my yard", "plan")]
    return [build(d) for build in BUILDERS]


def heading(project: dict) -> str:
    """"Example — Front Yard · 19 plants, 14 kinds"."""
    from src.project_store import ProjectStore
    placed = list(ProjectStore(project).placed_plants)
    props = (project or {}).get("properties") or {}
    name = (props.get("project_name") or "").strip()
    kinds = len({p.get("plant_id") for p in placed})
    count = (f"{_kinds(len(placed), 'plant', 'plants')}, "
             f"{_kinds(kinds, 'kind', 'kinds')}") if placed else ""
    return " · ".join(p for p in (name, count) if p)


def as_text(items: list) -> str:
    """The items as plain text, for the PDF and the API."""
    out = []
    for it in items:
        out.append(f"{it.title}: {it.status_word}" if it.key != "empty"
                   else it.title)
        out.extend(it.lines)
        if it.strip:
            out.append(" · ".join(f"{m} {n}" for m, n in it.strip))
        out.append("")
    return "\n".join(out).strip()


def word_count(items: list) -> int:
    words = 0
    for it in items:
        words += len(f"{it.title} {it.status_word} {it.action}".split())
        words += sum(len(line.split()) for line in it.lines)
    return words
