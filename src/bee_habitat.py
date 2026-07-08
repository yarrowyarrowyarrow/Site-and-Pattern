"""
bee_habitat.py — "Design for a bee": turn the native-bee data spine into
actionable habitat advice for a chosen target species or genus (F37, the
"see what a bee sees" family of features).

Given a bee, this module answers three questions from what the user already
has and what the plant/fauna database knows:

  1. Floral hosts — which plants (ideally the ones already in the design) feed
     this bee, and how well the flower's shape fits the bee's tongue.
  2. Nesting — what this bee needs to nest, mapped onto the app's real habitat
     structures (bee hotel, drilled log, brush pile, unmown lawn patch) and
     plain-language practices.
  3. Forage across the flight season — are there blooms in the design for every
     month the bee is on the wing, or are there gaps to fill?

Qt-free by design: it reads through ``src.db.fauna`` and returns plain
dataclasses so the analysis panel (and, later, the 3D fly-through and the map
recolour lens) can share one "chosen bee → relevant flowers" selection.

Design principle P3 (relationships matter more than components) and P10 (design
for relationships, not objects) — the bee↔plant and bee↔host-bee edges are the
product here — and P8 (repair is first-class: this is habitat you build *for* a
species). Uncertainty is handled honestly per P9: tongue-fit and forage
coverage degrade to "unknown" / "skipped" rather than inventing a signal.
See docs/DESIGN_PHILOSOPHY.md.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

from src.db import fauna as _fauna
from src.db import structures as _structures
from src.habitat_score import parse_month_range


# ── Result types ──────────────────────────────────────────────────────────────

@dataclass
class FloralMatch:
    plant_id: int
    common_name: str
    scientific_name: str
    bloom_period: str
    flower_form: str
    in_users_list: bool           # True if the plant is already in the design
    match_basis: str              # 'edge' | 'genus' | 'both'
    tongue_form_fit: str          # 'good' | 'plausible' | 'unknown' (never 'perfect')
    confidence: str               # 'documented' | 'inferred'


@dataclass
class NestingGuidance:
    nesting_habit: str            # the raw enum ('ground', 'cavity', …, 'unknown')
    headline: str
    structure_ids: list[str]      # ids from src.db.structures (may be empty)
    structures: list[dict]        # resolved structure defs for those ids
    actions: list[str]            # plain-language, non-structure practices


@dataclass
class ForageCoverage:
    flight_months: list[int]      # 1-12, from the bee's flight_season
    covered_months: list[int]     # flight months with ≥1 matched bloom in the design
    gap_months: list[int]         # flight months with no bloom in the design
    note: str                     # honesty line when data is thin / nothing matched
    suggestions: list[FloralMatch] = field(default_factory=list)  # gap-filling hosts


@dataclass
class BeeHabitatPlan:
    fauna_id: int
    bee: dict                     # the fauna row (names, image_url, description…)
    attrs: dict                   # the bee_attributes row (may be sparse / {})
    floral_matches: list[FloralMatch]
    nesting: NestingGuidance
    forage: ForageCoverage
    data_confidence: str          # 'documented' | 'partial' | 'thin'


# ── Selector ──────────────────────────────────────────────────────────────────

def list_target_bees() -> list[dict]:
    """Return every bee the user can target, ordered genus-first so the UI can
    group them. Each dict carries the fauna id + names, the (possibly NULL) bee
    attributes, and an ``is_group`` flag for the genus-level ``… spp.`` rows
    (which act as the "any species in this genus" option)."""
    out: list[dict] = []
    for row in _fauna.list_bees_with_attributes():
        genus = row.get("bee_genus") or _genus_of(row.get("scientific_name", ""))
        out.append({
            "id": row["id"],
            "scientific_name": row.get("scientific_name", ""),
            "common_name": row.get("common_name", ""),
            "genus": genus,
            "is_group": str(row.get("scientific_name", "")).endswith("spp."),
            "nesting_habit": row.get("nesting_habit"),
            "tongue_length": row.get("tongue_length"),
            "flight_season": row.get("flight_season"),
            "conservation_status": row.get("conservation_status"),
            "image_url": row.get("image_url", ""),
        })
    # Genus groups sort above their species; then by common name.
    out.sort(key=lambda b: (b["genus"].lower(), not b["is_group"],
                            b["common_name"].lower()))
    return out


# ── Floral-host matching ──────────────────────────────────────────────────────

_DEEP_FORMS = {"bell", "spike"}          # tubular / deep corolla
_OPEN_FORMS = {"daisy", "umbel", "cluster"}


def tongue_form_fit(tongue_length: Optional[str],
                    flower_form: Optional[str]) -> str:
    """How well a flower's shape suits a bee's tongue. A *Bombus*-only signal:
    returns ``'unknown'`` whenever tongue length is absent (all non-*Bombus*
    bees) or the flower form is unknown — we never claim a fit without data,
    and there is deliberately no ``'perfect'``.

    Long tongues reach deep tubular flowers well; short tongues suit open,
    shallow flowers; medium tongues are versatile.
    """
    if tongue_length in (None, "", "unknown"):
        return "unknown"
    form = (flower_form or "").strip().lower()
    if not form or form == "none":
        return "unknown"
    if tongue_length == "long":
        return "good" if form in _DEEP_FORMS else "plausible"
    if tongue_length == "short":
        return "good" if form in _OPEN_FORMS else "plausible"
    # medium
    return "good" if form in _OPEN_FORMS else "plausible"


def floral_matches_for_bee(fauna_id: int,
                           plant_ids: Optional[list[int]] = None) -> list[FloralMatch]:
    """Plants that feed ``fauna_id``, from two sources:

      * documented ``plant_fauna`` nectar/pollen edges (``confidence='documented'``);
      * a genus-level fallback from ``bee_attributes.floral_host_genera`` — plants
        whose genus is a listed floral host (``confidence='inferred'``).

    If ``plant_ids`` (the design's plant ids) is given, plants already in the
    design are flagged ``in_users_list`` and sorted first — start from what the
    user already has (P5).
    """
    user_ids = {int(p) for p in plant_ids} if plant_ids else set()

    # (1) documented edges
    edge_ids: set[int] = set()
    rows_by_id: dict[int, dict] = {}
    for rel in ("nectar", "pollen"):
        for p in _fauna.plants_for_fauna(fauna_id, relationship=rel):
            pid = p["id"]
            edge_ids.add(pid)
            rows_by_id.setdefault(pid, p)

    # (2) genus fallback
    genus_ids: set[int] = set()
    attrs = _fauna.bee_attributes_for(fauna_id)
    hosts = (attrs.get("floral_host_genera") or "").strip()
    if hosts:
        genera = [g.strip() for g in hosts.split(",") if g.strip()]
        for p in _fauna.plants_in_genera(genera):
            pid = p["id"]
            genus_ids.add(pid)
            rows_by_id.setdefault(pid, p)

    tongue = attrs.get("tongue_length")
    matches: list[FloralMatch] = []
    for pid, p in rows_by_id.items():
        is_edge = pid in edge_ids
        is_genus = pid in genus_ids
        basis = "both" if (is_edge and is_genus) else ("edge" if is_edge else "genus")
        matches.append(FloralMatch(
            plant_id=pid,
            common_name=p.get("common_name", ""),
            scientific_name=p.get("scientific_name", ""),
            bloom_period=p.get("bloom_period") or "",
            flower_form=p.get("flower_form") or "",
            in_users_list=pid in user_ids,
            match_basis=basis,
            tongue_form_fit=tongue_form_fit(tongue, p.get("flower_form")),
            confidence="documented" if is_edge else "inferred",
        ))

    _order = {"good": 0, "plausible": 1, "unknown": 2}
    matches.sort(key=lambda m: (
        not m.in_users_list,                       # design plants first
        m.confidence != "documented",              # documented before inferred
        _order.get(m.tongue_form_fit, 3),          # better fit first
        m.common_name.lower(),
    ))
    return matches


# ── Nesting guidance ──────────────────────────────────────────────────────────

def nesting_guidance(fauna_id: int) -> NestingGuidance:
    """Map the bee's ``nesting_habit`` onto the app's real habitat structures
    plus plain-language practices. Cleptoparasites get no structure — the honest
    advice is to support their host bee (P3/P10)."""
    attrs = _fauna.bee_attributes_for(fauna_id)
    habit = attrs.get("nesting_habit") or "unknown"
    host = attrs.get("host_genus") or "its host bee"

    if habit == "ground":
        headline = "Ground-nesting — leave bare, sunny soil"
        struct_ids = ["native_lawn_patch"]
        actions = [
            "Leave a patch of bare, well-drained soil in a sunny, undisturbed "
            "spot — no mulch or landscape fabric over it.",
            "Avoid tilling or heavy digging where they nest.",
        ]
    elif habit == "cavity":
        headline = "Cavity-nesting — stems, holes & bee hotels"
        struct_ids = ["bee_hotel", "native_bee_log"]
        actions = [
            "Put up a bee hotel or a drilled hardwood log, facing south/east and "
            "sheltered from rain and wind.",
            "Leave hollow and pithy stems standing over winter.",
        ]
    elif habit == "pithy_stem":
        headline = "Pithy-stem nesting — leave standing stems"
        struct_ids = []
        actions = [
            "Leave standing dead stems (raspberry, elderberry, sunflower) over "
            "winter; cut back to 20–40 cm in spring so bees can excavate the pith.",
            "Skip the autumn tidy-up in at least part of the yard.",
        ]
    elif habit == "social_ground":
        headline = "Social colony — undisturbed rough ground"
        struct_ids = ["brush_pile", "native_lawn_patch"]
        actions = [
            "Leave an area of unmown rough grass, tussocks, or an old rodent "
            "burrow undisturbed — that is where founding queens start colonies.",
            "A brush pile or an unmown lawn patch gives sheltered nest sites.",
        ]
    elif habit == "cleptoparasite":
        headline = "Cuckoo bee — support its host"
        struct_ids = []
        actions = [
            f"This is a cuckoo bee: it builds no nest and depends on {host} bees. "
            f"Build habitat for {host} and this bee can follow.",
            "A healthy host-bee population is the only way to support it — its "
            "presence is a sign of a working bee community.",
        ]
    else:  # unknown
        headline = "Nesting needs not characterised"
        struct_ids = []
        actions = [
            "We don't have documented nesting data for this bee yet. General "
            "native-bee habitat — bare soil, standing stems, and unmown patches "
            "— helps most species.",
        ]

    resolved = [s for s in (_structures.get_structure(i) for i in struct_ids) if s]
    return NestingGuidance(
        nesting_habit=habit,
        headline=headline,
        structure_ids=struct_ids,
        structures=resolved,
        actions=actions,
    )


# ── Forage coverage across the flight season ──────────────────────────────────

def forage_coverage(fauna_id: int,
                    considered: list[FloralMatch]) -> ForageCoverage:
    """Do the ``considered`` plants bloom across every month the bee flies?

    ``considered`` is normally the matched plants already in the design. Returns
    covered vs gap months plus, when there are gaps, suggested host plants (not
    already considered) that bloom in a gap month. Skipped honestly when the
    bee's flight season is undocumented (P9).
    """
    attrs = _fauna.bee_attributes_for(fauna_id)
    flight_months = parse_month_range(attrs.get("flight_season") or "")
    if not flight_months:
        return ForageCoverage(
            [], [], [],
            note="Flight season isn't documented for this bee — the seasonal "
                 "coverage check is skipped rather than guessed.",
        )

    bloom: set[int] = set()
    for m in considered:
        bloom.update(parse_month_range(m.bloom_period))

    covered = [mo for mo in flight_months if mo in bloom]
    gap = [mo for mo in flight_months if mo not in bloom]

    if not considered:
        note = ("No matching floral hosts are in your design yet — add some of "
                "the plants above to feed this bee across its flight season.")
    elif gap:
        note = ("Gaps are months the bee is flying but nothing in your design "
                "is in bloom for it.")
    else:
        note = "Your design has a bloom for this bee in every month it flies."

    # Gap-filling suggestions: matched hosts NOT already considered that bloom in
    # a gap month (surface a few so the UI can offer "add these").
    suggestions: list[FloralMatch] = []
    if gap:
        considered_ids = {m.plant_id for m in considered}
        gap_set = set(gap)
        for m in floral_matches_for_bee(fauna_id):
            if m.plant_id in considered_ids:
                continue
            if gap_set & set(parse_month_range(m.bloom_period)):
                suggestions.append(m)
    return ForageCoverage(flight_months, covered, gap, note, suggestions[:12])


# ── Orchestration ─────────────────────────────────────────────────────────────

def build_bee_habitat_plan(fauna_id: int,
                           plant_ids: Optional[list[int]] = None) -> Optional[BeeHabitatPlan]:
    """Single entry point: assemble floral matches, nesting guidance, and forage
    coverage for ``fauna_id`` against the design's ``plant_ids``. Returns None if
    the fauna id isn't a known bee.

    This is the shared "chosen bee → relevant flowers" selection the later 3D
    fly-through and map-recolour lenses reuse.
    """
    bee = _fauna.get_fauna(fauna_id)
    if not bee or bee.get("taxon") != "bee":
        return None
    attrs = _fauna.bee_attributes_for(fauna_id)

    matches = floral_matches_for_bee(fauna_id, plant_ids)
    nesting = nesting_guidance(fauna_id)

    # Coverage is judged against the design when we have one, else against all
    # candidate hosts (so the check still means something with no plants placed).
    if plant_ids:
        considered = [m for m in matches if m.in_users_list]
    else:
        considered = matches
    forage = forage_coverage(fauna_id, considered)

    data_confidence = _confidence(attrs, matches)
    return BeeHabitatPlan(
        fauna_id=fauna_id, bee=bee, attrs=attrs,
        floral_matches=matches, nesting=nesting, forage=forage,
        data_confidence=data_confidence,
    )


def target_plant_ids_for_bee(fauna_id: int) -> list[int]:
    """The DB plant ids that feed ``fauna_id`` (documented edges + genus hosts).

    The shared selection the 3D fly-through (increment 2) and the map-recolour
    lens (increment 3) consume to know which plants to highlight for a chosen bee.
    """
    return [m.plant_id for m in floral_matches_for_bee(fauna_id)]


def flight_months_for_bee(fauna_id: int) -> list[int]:
    """The months (1-12) the bee is on the wing, from ``flight_season``. Empty
    when undocumented — the fly-through's seasonal tour then spans the whole year
    rather than guessing a window (P9). Shared with the lepidoptera fly-through."""
    attrs = _fauna.bee_attributes_for(fauna_id)
    return parse_month_range(attrs.get("flight_season") or "")


# ── Helpers ───────────────────────────────────────────────────────────────────

def _genus_of(scientific_name: str) -> str:
    return (scientific_name or "").split(" ", 1)[0]


def _confidence(attrs: dict, matches: list[FloralMatch]) -> str:
    """Roll up how much of this bee's picture is documented vs inferred."""
    has_nesting = bool(attrs.get("nesting_habit")) and attrs.get("nesting_habit") != "unknown"
    has_season = bool(attrs.get("flight_season"))
    has_documented = any(m.confidence == "documented" for m in matches)
    score = sum((has_nesting, has_season, has_documented or bool(matches)))
    if score >= 3:
        return "documented"
    if score >= 1:
        return "partial"
    return "thin"
