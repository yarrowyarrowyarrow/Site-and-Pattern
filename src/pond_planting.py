"""Where the generator plants what grows in water (F185, V2.95).

Design principle P2 — see docs/DESIGN_PHILOSOPHY.md

Until V2.95 a water plant the design asked for was positioned like any other
plant, and the pond was placed after them all, so every pond-lily stood on dry
ground: 0 of 6 in a measured design, 9 to 28 m from the pond it was meant for.

**A plant that needs standing water goes in a pond, or is not placed.** Which
plants those are is ``zoning.needs_standing_water``'s answer (V2.91), and each
has a role from the body the 3D scene draws it with (``pond_habit.body_for``):

* **open water** — floating and submerged plants, seated inside the pond's water
  at most ``OPEN_REACH`` of the way from its centre to its edge, so a pad does not
  lie half on the bank. Floating leaves shade at most ``FLOATING_SHARE`` of the
  water; the rest stays open for the submerged plants' light.
* **margin** — the emergents, standing in the shallows ``MARGIN_REACH`` of the way
  out, along the north two-thirds of the shore: at these latitudes a tall plant
  on the north bank shades the bank and not the water, and the south third stays
  open as the shallow shore the pond's own catalogue entry asks for.

The water is ``pond_habit``'s ellipse, so a plant seated in the open water is one
the 3D preview draws on the water. Seats fill from the middle outward and from due
north along the shore; a seat is free when every plant already there is at least
half the two spacings away, the room rule the main pass and ``open_ground`` use.

Every number here is a drawing or design choice, said in its own comment.
"""

from __future__ import annotations

import math
from typing import Callable, Iterable, Optional

from src import pond_habit
from src.projection import Projector
from src.zoning import needs_standing_water

OPEN, MARGIN = "open", "margin"

#: How far out each role sits, as a fraction of the way from the pond's centre
#: to the water's edge.
OPEN_REACH = 0.70
MARGIN_REACH = 0.85
#: The planted shore reaches this many degrees either side of due north; the
#: south third of the shore is left open.
SHORE_ARC_DEG = 120.0
#: Floating leaves may shade at most this share of the water.
FLOATING_SHARE = 0.5
#: A pond plant's spacing: its recorded one, never tighter than this (duckweed is
#: recorded at 0.1 m, which as a seat is a single frond).
MIN_SPACING_M = 0.25
DEFAULT_SPACING_M = 0.5
#: A community goes in a pond when at least this share of its members does.
POND_COMMUNITY_SHARE = 0.5

#: The review's planting for a pond the design left bare: (bodies, species,
#: plants of each). Seven plants on a 6 m pond, a design choice.
BARE_POND_PLANTING = (
    (("floating",), 1, 1),
    (("submerged",), 1, 2),
    (None, 2, 2),                       # None: the margin's emergents
)

#: Never chosen by the generator on its own. The AI may still ask for them by
#: name; this only keeps the generator from putting the name on a list itself.
NOT_CHOSEN_AUTOMATICALLY = {
    "Myriophyllum sibiricum": (
        "catalogued as 'Spiked Water-milfoil', the usual name of the Eurasian "
        "M. spicatum, a prohibited aquatic invasive in Alberta (F172)"),
}

_OPEN_BODIES = ("floating", "submerged")
_GOLDEN = math.pi * (3.0 - math.sqrt(5.0))
_OPEN_CANDIDATES = 240
_SHORE_STEP_DEG = 3.0


def role_of(plant: dict) -> Optional[str]:
    """``OPEN`` or ``MARGIN`` for a plant that needs standing water, else None."""
    if not needs_standing_water(plant or {}):
        return None
    return OPEN if pond_habit.body_for(plant) in _OPEN_BODIES else MARGIN


def spacing_m(plant: dict) -> float:
    """Centre-to-centre spacing of one pond plant: its mature spread, the fields
    the main pass reads and in its order (a catalogue row's ``mature_canopy_m``,
    then ``spacing_meters``; ``spacing_m`` is the seed file's name for it)."""
    for key in ("mature_canopy_m", "spacing_meters", "spacing_m"):
        try:
            s = float(plant.get(key) or 0.0)
        except (TypeError, ValueError):
            s = 0.0
        if s > 0:
            return max(MIN_SPACING_M, s)
    return DEFAULT_SPACING_M


def is_pond_community(member_rows: Iterable[dict]) -> bool:
    """True when at least half of a community's members need standing water:
    the seeded pond assemblages, not a bed with one wet-footed member."""
    rows = [r for r in member_rows if r]
    if not rows:
        return False
    wet = sum(1 for r in rows if needs_standing_water(r))
    return wet / len(rows) >= POND_COMMUNITY_SHARE


class Pond:
    """One pond: where it is, how big, and the water ``pond_habit`` draws."""

    def __init__(self, lat: float, lng: float, size_m: float):
        self.lat, self.lng = float(lat), float(lng)
        self.size_m = float(size_m)
        self.rx = pond_habit.POND_WATER_RX * self.size_m      # east-west
        self.ry = pond_habit.POND_WATER_RY * self.size_m      # north-south
        self._proj = Projector(self.lat, self.lng)

    @property
    def water_m2(self) -> float:
        return math.pi * self.rx * self.ry

    def at(self, u: float, v: float) -> tuple[float, float]:
        """``(lat, lng)`` at ``(u, v)``, fractions of the way to the water's edge
        east and north."""
        return self._proj.to_latlng(u * self.rx, v * self.ry)

    def uv(self, lat: float, lng: float) -> tuple[float, float]:
        x, y = self._proj.to_xy(lat, lng)
        return (x / self.rx if self.rx else 0.0, y / self.ry if self.ry else 0.0)

    def xy(self, lat: float, lng: float) -> tuple[float, float]:
        return self._proj.to_xy(lat, lng)

    def holds(self, lat: float, lng: float) -> bool:
        """Inside the pond's footprint (its keep-out circle)."""
        x, y = self._proj.to_xy(lat, lng)
        return math.hypot(x, y) <= self.size_m / 2.0


def ponds_in(features: Iterable[dict]) -> list:
    """The ponds among a project's features, in their order."""
    out = []
    for f in features or []:
        props = f.get("properties", {}) or {}
        if props.get("element_type") != "structure":
            continue
        sd = props.get("struct_def") or {}
        if (props.get("struct_id") or sd.get("id")) != "pond":
            continue
        geom = f.get("geometry", {}) or {}
        coords = geom.get("coordinates") or []
        if geom.get("type") != "Point" or len(coords) < 2:
            continue
        size = props.get("size_m") or sd.get("size_m") or 6.0
        try:
            out.append(Pond(coords[1], coords[0], float(size)))
        except (TypeError, ValueError):
            continue
    return out


class PondSeats:
    """The ponds in a design, asked for one water plant at a time.

    ``project`` is read on every call, so each seat sees the plants seated before
    it. ``row_of(plant_id)`` is a catalogue lookup (``get_plant`` by default).
    """

    def __init__(self, project, ponds, row_of: Optional[Callable] = None):
        self._project = project
        self.ponds = list(ponds or [])
        self._row_of = row_of or _catalogue_row
        self._rows: dict = {}

    def __bool__(self) -> bool:
        return bool(self.ponds)

    def seat(self, row: dict, role: Optional[str] = None
             ) -> Optional[tuple[float, float]]:
        """Where one of ``row`` goes in the first pond with room, or None. A plant
        that does not need standing water (a pond community's water smartweed)
        takes the shore."""
        role = role or role_of(row) or MARGIN
        own = spacing_m(row)
        floating = pond_habit.body_for(row) == "floating"
        for pond in self.ponds:
            here = self._in(pond)
            if floating and not self._floating_fits(pond, here, own):
                continue
            for la, ln in _candidates(pond, role):
                if self._free(pond, la, ln, own, here):
                    return la, ln
        return None

    # ── what is already there ───────────────────────────────────────────────

    def _row(self, plant_id) -> dict:
        if plant_id not in self._rows:
            try:
                self._rows[plant_id] = self._row_of(plant_id) or {}
            except Exception:  # noqa: BLE001
                self._rows[plant_id] = {}
        return self._rows[plant_id]

    def _in(self, pond: Pond) -> list:
        """``(x, y, spacing, row)`` for each plant already in ``pond``."""
        out = []
        for p in self._project.placed_plants:
            la, ln = p.get("lat"), p.get("lng")
            if la is None or ln is None or not pond.holds(la, ln):
                continue
            row = self._row(p.get("plant_id"))
            x, y = pond.xy(la, ln)
            out.append((x, y, spacing_m(row), row))
        return out

    def _free(self, pond: Pond, la: float, ln: float, own: float,
              here: list) -> bool:
        x, y = pond.xy(la, ln)
        return all(math.hypot(x - ox, y - oy) >= (own + sp) / 2.0
                   for ox, oy, sp, _ in here)

    def _floating_fits(self, pond: Pond, here: list, own: float) -> bool:
        shaded = sum(math.pi * (sp / 2.0) ** 2 for _, _, sp, row in here
                     if pond_habit.body_for(row) == "floating")
        return shaded + math.pi * (own / 2.0) ** 2 <= FLOATING_SHARE * pond.water_m2


def _candidates(pond: Pond, role: str):
    """Seats in the order they fill: the open water from the middle outward on a
    sunflower spiral, the shore from due north outward, east and west in turn."""
    if role == OPEN:
        for k in range(_OPEN_CANDIDATES):
            r = OPEN_REACH * math.sqrt((k + 0.5) / _OPEN_CANDIDATES)
            t = k * _GOLDEN
            yield pond.at(r * math.cos(t), r * math.sin(t))
        return
    steps = int(SHORE_ARC_DEG // _SHORE_STEP_DEG)
    for i in range(0, steps + 1):
        for sign in ((1,) if i == 0 else (1, -1)):
            b = math.radians(sign * i * _SHORE_STEP_DEG)   # bearing from north
            yield pond.at(MARGIN_REACH * math.sin(b), MARGIN_REACH * math.cos(b))


def _catalogue_row(plant_id) -> dict:
    from src.db.plants import get_plant
    return get_plant(plant_id) or {}


def _community(cid) -> tuple[str, list]:
    """A seeded or saved community's name and member rows, in order."""
    from src.db.polycultures import get_polyculture_by_id
    c = get_polyculture_by_id(int(cid)) or {}
    return (c.get("name") or "",
            [_catalogue_row(m.get("plant_id")) for m in c.get("members") or []])


# ── the main pass: the spec's water plants ──────────────────────────────────

def split_water(p_items, p_mixes, c_groups, c_mixes, *,
                row_of: Optional[Callable] = None,
                community_of: Optional[Callable] = None):
    """Take a resolved spec's water plants and pond communities out of it, to be
    seated after the rest is placed (the pond is placed last). Returns
    ``(p_items, p_mixes, c_groups, c_mixes, water, pond_communities)`` where
    ``water`` is ``[(plant_id, quantity)]`` and ``pond_communities`` is
    ``[(community_id, count)]``. A spec with no water in it comes back as it
    went in, so a dry design is placed exactly as before."""
    row_of = row_of or _catalogue_row
    community_of = community_of or _community
    water: list = []
    dry_items = []
    for it in p_items or []:
        if needs_standing_water(row_of(it[0]) or {}):
            water.append((it[0], int(it[1])))
        else:
            dry_items.append(it)
    dry_mixes = []
    for mix in p_mixes or []:
        members = mix.get("members") or []
        wet = [(pid, w) for pid, w in members
               if needs_standing_water(row_of(pid) or {})]
        if not wet:
            dry_mixes.append(mix)
            continue
        total = sum(w for _, w in members) or 1.0
        qty = int(mix.get("quantity") or 0)
        for pid, w in wet:
            share = int(round(qty * w / total))
            if share:
                water.append((pid, share))
        wet_ids = {pid for pid, _ in wet}
        dry = [(pid, w) for pid, w in members if pid not in wet_ids]
        if dry:
            left = qty - int(round(qty * sum(w for _, w in wet) / total))
            dry_mixes.append(dict(mix, members=dry, quantity=max(1, left)))
    ponds: list = []

    def is_pond(cid) -> bool:
        try:
            return is_pond_community(community_of(cid)[1])
        except Exception:  # noqa: BLE001
            return False

    dry_groups = []
    for g in c_groups or []:
        cid = g["id"] if isinstance(g, dict) else g
        count = int(g.get("count") or 1) if isinstance(g, dict) else 1
        if is_pond(cid):
            ponds.append((cid, count))
        else:
            dry_groups.append(g)
    dry_cmixes = []
    for mix in c_mixes or []:
        members = mix.get("members") or []
        wet = [(cid, w) for cid, w in members if is_pond(cid)]
        if not wet:
            dry_cmixes.append(mix)
            continue
        total = sum(w for _, w in members) or 1.0
        count = int(mix.get("count") or len(members))
        for cid, w in wet:
            share = int(round(count * w / total))
            if share:
                ponds.append((cid, share))
        wet_ids = {cid for cid, _ in wet}
        dry = [(cid, w) for cid, w in members if cid not in wet_ids]
        if dry:
            left = count - int(round(count * sum(w for _, w in wet) / total))
            dry_cmixes.append(dict(mix, members=dry, count=max(1, left)))
    return dry_items, dry_mixes, dry_groups, dry_cmixes, water, ponds


def seat_water(project, water, pond_communities, seats: PondSeats, *,
               row_of: Optional[Callable] = None,
               community_of: Optional[Callable] = None) -> list:
    """Seat the spec's water plants and pond communities in the design's ponds
    (``seats``). Returns the design notes: what was left out, and why."""
    row_of = row_of or _catalogue_row
    community_of = community_of or _community
    if not water and not pond_communities:
        return []
    if not seats:
        return [_no_pond_note(water, pond_communities, row_of, community_of)]
    short: list = []                          # (name, placed, asked)
    for pid, qty in water:
        row = row_of(pid) or {}
        placed = 0
        for _ in range(max(0, int(qty))):
            spot = seats.seat(row)
            if spot is None:
                break
            project.place_plant(pid, spot[0], spot[1], quantity=1)
            placed += 1
        if placed < qty:
            short.append((row.get("common_name") or "plant", placed, qty))
    for cid, count in pond_communities:
        name, members = community_of(cid)
        for _ in range(max(0, int(count))):
            for row in members:
                spot = seats.seat(row)
                if spot is None:
                    short.append((row.get("common_name") or "plant", 0, 1))
                    continue
                project.place_plant(row["id"], spot[0], spot[1],
                                    polyculture_name=name, quantity=1)
    return [_short_note(short)] if short else []


def _names(names: list) -> str:
    names = [n for n in names if n]
    if len(names) <= 1:
        return "".join(names)
    return ", ".join(names[:-1]) + " and " + names[-1]


def _no_pond_note(water, pond_communities, row_of, community_of) -> str:
    plants = []
    for pid, _ in water:
        n = (row_of(pid) or {}).get("common_name")
        if n and n not in plants:
            plants.append(n)
    comms = []
    for cid, _ in pond_communities:
        n = community_of(cid)[0]
        if n and n not in comms:
            comms.append(f'the "{n}" community')
    what = _names(plants + comms)
    return (f"Left out {what}: they grow in standing water, and this design "
            "has no pond. Add a pond, or plant them in one you have.")


def _short_note(short: list) -> str:
    merged: dict = {}
    for name, placed, asked in short:
        p, a = merged.get(name, (0, 0))
        merged[name] = (p + placed, a + asked)
    parts = [f"{p} of the {a} {n}" for n, (p, a) in merged.items()]
    return f"The pond had room for {_names(parts)}."


# ── the review: a pond the design left bare ─────────────────────────────────

def plant_bare_ponds(project, ponds, pool: Iterable[dict], site=None, *,
                     row_of: Optional[Callable] = None) -> list:
    """Plant each of ``ponds`` that has no water plant in it with
    :func:`bare_pond_choices` from ``pool``. Returns the design notes."""
    row_of = row_of or _catalogue_row
    pool = list(pool or [])
    notes = []
    for pond in ponds or []:
        seats = PondSeats(project, [pond], row_of=row_of)
        here = [row for _, _, _, row in seats._in(pond)]
        if any(role_of(r) for r in here):
            continue
        planted = []
        for row, count in bare_pond_choices(pool, site):
            n = 0
            for _ in range(count):
                spot = seats.seat(row)
                if spot is None:
                    break
                project.place_plant(row["id"], spot[0], spot[1], quantity=1)
                n += 1
            if n:
                planted.append(row.get("common_name") or "plant")
        if planted:
            notes.append(f"Planted the pond with {_names(planted)}: a pond needs "
                         "plants in its water and along its shore.")
    return notes


# ── the review's planting for a bare pond ───────────────────────────────────

def bare_pond_choices(rows: Iterable[dict], site=None) -> list:
    """``(row, count)`` for a pond the design left bare, per
    ``BARE_POND_PLANTING``, from ``rows`` (the site-scoped pool): recorded near
    the site first, then by ecological value, then catalogue order."""
    pool = [r for r in rows or [] if role_of(r) is not None
            and (r.get("scientific_name") or "") not in NOT_CHOSEN_AUTOMATICALLY]

    def near(r):
        if not site:
            return 0
        from src.site_fit import locality_rank
        return locality_rank(r.get("scientific_name") or "", site[0], site[1])

    pool = sorted(pool, key=lambda r: (near(r), _value(r)), reverse=True)
    chosen, seen = [], set()
    for bodies, n_species, each in BARE_POND_PLANTING:
        taken = 0
        for r in pool:
            if taken >= n_species:
                break
            if r.get("id") in seen:
                continue
            body = pond_habit.body_for(r)
            fits = (body in bodies) if bodies else (role_of(r) == MARGIN)
            if fits:
                chosen.append((r, each))
                seen.add(r.get("id"))
                taken += 1
    return chosen


def _value(row: dict) -> int:
    """The offline generator's ecological value, less its water penalty (every
    plant here is a water plant)."""
    uses = row.get("permaculture_uses") or ""
    return ((3 if "keystone_species" in uses else 0)
            + (2 if "host_plant" in uses else 0)
            + (1 if "pollinator" in uses else 0)
            + (1 if "bird_food" in uses else 0))
