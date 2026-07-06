"""
habitat_score.py — Qt-free Habitat Value Score computation.

Design principle P6 (conventional value metrics miss ecological value) and P10
(design for relationships, not objects) — see docs/DESIGN_PHILOSOPHY.md.

Extracted from ``src/analysis_panel.py:AnalysisPanel._calc_habitat_score``
in Chunk 6 of the strengthening roadmap (the "domain logic trapped in a
widget" case of E1). The scoring is pure arithmetic over the placed-plant
and placed-structure lists plus read-only plant DB lookups — none of it
needs Qt — so it now lives here where both the GUI (AnalysisPanel) and
the headless scripting API (``src.permadesign_api.run_analysis``) can
share one implementation.

The number-crunching is byte-for-byte the same as the pre-extraction
panel code; ``AnalysisPanel`` keeps the label / breakdown-text / tips
rendering and simply calls :func:`compute_habitat_score` for the maths.

Score components (100 pts total):
  1. Native ratio          20 pts   native_species / n_species
  2. Keystone species      15 pts   full at 5 distinct species
  3. Host plants           10 pts   full at 10
  4. Bird-food species     10 pts   full at 10
  5. Vegetation layers     15 pts   3 pts per canonical layer, max 5
  6. Habitat structures    10 pts   2 pts per distinct type, max 5
  7. Bloom continuity      20 pts   bloom-months in Apr–Oct / 7 * 20

Lepidoptera-supported is reported alongside the score (informational),
not summed into the headline — so existing scores don't drift as the
fauna data grows. Food-web completeness (F3) — whether the design closes
the Tallamy chain (host plants → caterpillars → the birds that eat them)
— is reported the same way: informational, never summed.

Design principle P3 (relationships matter more than components — the chain
has to connect) — see docs/DESIGN_PHILOSOPHY.md.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional


# Canonical layer names paired with the plant_types that fulfil them.
PLANT_TYPE_TO_LAYER: dict[str, str] = {
    "tree":        "overstory",
    "shrub":       "shrub",
    "herb":        "herbaceous",
    "groundcover": "groundcover",
    "vine":        "vine",
    "root":        "herbaceous",
}

CANONICAL_LAYERS: frozenset[str] = frozenset(
    {"overstory", "shrub", "herbaceous", "groundcover", "vine"}
)

# Structure ids that contribute to habitat value (Water + Habitat
# categories from src/db/structures.py).
HABITAT_STRUCTURE_IDS: frozenset[str] = frozenset({
    "pond", "swale", "rain_garden", "rain_barrel",
    "native_bee_log", "bee_hotel", "brush_pile", "snag",
    "rock_xeriscape", "native_lawn_patch",
})

# Growing-season months Apr(4)..Oct(10) used for bloom continuity.
GROWING_SEASON_MONTHS: frozenset[int] = frozenset(range(4, 11))

_MONTH_MAP = {
    "jan": 1, "january": 1, "feb": 2, "february": 2,
    "mar": 3, "march": 3, "apr": 4, "april": 4,
    "may": 5, "jun": 6, "june": 6,
    "jul": 7, "july": 7, "aug": 8, "august": 8,
    "sep": 9, "september": 9, "oct": 10, "october": 10,
    "nov": 11, "november": 11, "dec": 12, "december": 12,
}


def parse_month_range(text: str) -> list[int]:
    """Parse 'June-August' / 'May' style strings to month numbers (1-12).

    A two-token range that wraps the year end (e.g. 'Nov-Feb') expands
    across the boundary. Single tokens return a one-element list.
    """
    text = (text or "").lower().strip()
    parts = text.replace("–", "-").replace("—", "-").split("-")
    months: list[int] = []
    for part in parts:
        part = part.strip()
        for key, num in _MONTH_MAP.items():
            if part.startswith(key):
                months.append(num)
                break
    if len(months) == 2:
        start, end = months
        if start <= end:
            return list(range(start, end + 1))
        return list(range(start, 13)) + list(range(1, end + 1))
    return months


class HabitatScoreError(RuntimeError):
    """Raised when the plant database can't be read to compute a score.

    The GUI catches this to render a '?' placeholder; the scripting API
    surfaces it as a :class:`src.errors.AnalysisError`.
    """


@dataclass
class HabitatScore:
    """Structured result of :func:`compute_habitat_score`.

    ``total`` is the rounded 0–100 headline. The per-component scores and
    raw counts let callers render their own breakdown (the GUI) or emit a
    JSON-friendly dict (the scripting API)."""

    total: int
    grade: str

    n_species: int
    n_total_plants: int

    # plant_ids that resolved to a real DB row (drives the tips'
    # already-placed exclusion in the GUI).
    scored_plant_ids: list[int]

    native_species: int
    native_ratio: float
    score_native: float

    keystone_species: list[str]
    score_keystone: float

    host_species: list[str]
    score_host: float

    bird_species: list[str]
    score_bird: float

    layers_present: list[str]   # sorted, intersected with CANONICAL_LAYERS
    score_layers: float

    habitat_struct_types: list[str]   # sorted
    score_structs: float

    bloom_months: list[int]     # sorted, within the growing season
    gap_months: list[int]       # sorted growing-season months with no bloom
    score_bloom: float

    n_lepidoptera_supported: int

    # Informational, per-taxon count of distinct native fauna the placed
    # plants support (schema v20 fauna expansion). Like n_lepidoptera_supported
    # this is reported alongside the score but NOT summed into the headline, so
    # existing designs' scores stay stable as the fauna dataset grows.
    fauna_by_taxon: dict = field(default_factory=dict)

    # Food-web completeness (F3) — does the design close the Tallamy chain
    # (host plants → caterpillars → the birds that eat them)? Informational
    # and un-summed, exactly like the fauna lines above, so it never moves the
    # headline. Shape:
    #   {"caterpillars": bool, "n_caterpillars": int,
    #    "birds": bool, "n_birds": int, "complete": bool, "status": str}
    # status ∈ {"complete", "no_birds", "no_hosts", "empty"}.
    food_web: dict = field(default_factory=dict)

    def as_dict(self) -> dict:
        """JSON-serialisable view, used by the scripting API."""
        return {
            "total": self.total,
            "grade": self.grade,
            "n_species": self.n_species,
            "n_total_plants": self.n_total_plants,
            "components": {
                "native":     {"ratio": self.native_ratio,
                               "native_species": self.native_species,
                               "score": round(self.score_native, 1), "max": 20},
                "keystone":   {"species": self.keystone_species,
                               "score": round(self.score_keystone, 1), "max": 15},
                "host":       {"species": self.host_species,
                               "score": round(self.score_host, 1), "max": 10},
                "bird_food":  {"species": self.bird_species,
                               "score": round(self.score_bird, 1), "max": 10},
                "layers":     {"present": self.layers_present,
                               "score": round(self.score_layers, 1), "max": 15},
                "structures": {"types": self.habitat_struct_types,
                               "score": round(self.score_structs, 1), "max": 10},
                "bloom":      {"months": self.bloom_months,
                               "gap_months": self.gap_months,
                               "score": round(self.score_bloom, 1), "max": 20},
            },
            "lepidoptera_supported": self.n_lepidoptera_supported,
            "fauna_by_taxon": dict(self.fauna_by_taxon),
            "food_web": dict(self.food_web),
        }


def _grade_for(total_int: int) -> str:
    if total_int >= 75:
        return "Excellent habitat"
    if total_int >= 50:
        return "Solid habitat"
    if total_int >= 25:
        return "Foundation laid"
    return "Just getting started"


_MONTH_ABBR = ["", "Jan", "Feb", "Mar", "Apr", "May", "Jun",
               "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]


def _gap_phrase(gap_months: list[int]) -> str:
    """Human month list for a bloom gap: 'May', 'May & Jun', 'May, Jun & Jul'."""
    names = [_MONTH_ABBR[m] for m in gap_months if 1 <= m <= 12]
    if not names:
        return ""
    if len(names) == 1:
        return names[0]
    return ", ".join(names[:-1]) + " & " + names[-1]


def habitat_nudges(score: "HabitatScore", *, limit: int = 3) -> list[dict]:
    """The 'what would help most' half of the habitat readout (P6, P9).

    Turns a :class:`HabitatScore` into up to ``limit`` actionable suggestions,
    ranked by how many points each still has on the table — so the design's
    biggest ecological gaps surface first. Each nudge is
    ``{"headroom": float, "text": str}`` where ``text`` is soft, ranged
    language ("up to +N pts"), never a false-precision promise. Returns an
    empty list for a full or absent score.

    Pure data — no Qt; the On This Design panel renders the strings.
    """
    if not score:
        return []
    nudges: list[dict] = []

    def add(headroom: float, text: str):
        if headroom > 0.5:
            nudges.append({"headroom": round(headroom, 1), "text": text})

    # Bloom is usually the biggest lever and the most concrete ask — lead with
    # the specific gap months when there are any.
    gap = _gap_phrase(getattr(score, "gap_months", []) or [])
    if gap:
        head = 20.0 - (getattr(score, "score_bloom", 0.0) or 0.0)
        add(head, f"No bloom in {gap} — add forage for those weeks "
                  f"(up to +{int(round(head))} pts, and it feeds pollinators "
                  "through the gap).")

    # Native ratio.
    n = getattr(score, "n_species", 0)
    nat = getattr(score, "native_species", 0)
    if n:
        head = 20.0 - (getattr(score, "score_native", 0.0) or 0.0)
        if head > 0.5 and (n - nat) > 0:
            add(head, f"{n - nat} of {n} species aren't Alberta-native — "
                      f"swapping some for natives adds up to +{int(round(head))} "
                      "pts and more wildlife value.")

    # Keystone genera (full at 5). Kept generic — no specific taxa named.
    n_key = len(getattr(score, "keystone_species", []) or [])
    if n_key < 5:
        head = 15.0 - (getattr(score, "score_keystone", 0.0) or 0.0)
        add(head, f"Only {n_key} keystone species so far — these carry the most "
                  "of the food web; a few more add up to "
                  f"+{int(round(head))} pts (filter Plants → Use → Keystone).")

    # Larval-host plants (full at 10).
    n_host = len(getattr(score, "host_species", []) or [])
    if n_host < 10:
        head = 10.0 - (getattr(score, "score_host", 0.0) or 0.0)
        add(head, f"{n_host} caterpillar-host plant"
                  f"{'s' if n_host != 1 else ''} — hosts make the caterpillars "
                  "most songbirds feed their young; more add up to "
                  f"+{int(round(head))} pts (Plants → Use → Host Plant).")

    # Bird-food plants (full at 10).
    n_bird = len(getattr(score, "bird_species", []) or [])
    if n_bird < 10:
        head = 10.0 - (getattr(score, "score_bird", 0.0) or 0.0)
        add(head, f"{n_bird} bird-food plant{'s' if n_bird != 1 else ''} — "
                  "seed and fruit producers extend the design into fall/winter "
                  f"(up to +{int(round(head))} pts, Plants → Use → Bird Food).")

    # Vegetation layers (3 pts each, up to 5).
    present = set(getattr(score, "layers_present", []) or [])
    missing = [l for l in ("overstory", "shrub", "herbaceous",
                           "groundcover", "vine") if l not in present]
    if missing and len(present) < 5:
        head = 15.0 - (getattr(score, "score_layers", 0.0) or 0.0)
        pretty = ", ".join(m.replace("_", " ") for m in missing[:3])
        add(head, f"Missing layers: {pretty} — stacking more vegetation layers "
                  f"adds up to +{int(round(head))} pts and niches for wildlife.")

    # Habitat structures (2 pts each, up to 5).
    n_struct = len(getattr(score, "habitat_struct_types", []) or [])
    if n_struct < 5:
        head = 10.0 - (getattr(score, "score_structs", 0.0) or 0.0)
        add(head, f"{n_struct} habitat structure type"
                  f"{'s' if n_struct != 1 else ''} — a bee hotel, brush pile or "
                  f"small pond adds up to +{int(round(head))} pts "
                  "(Structures tab).")

    nudges.sort(key=lambda d: -d["headroom"])
    return nudges[:limit]


def compute_habitat_score(
    placed_plants: list[dict],
    structures: list[dict],
    *,
    connection=None,
) -> Optional[HabitatScore]:
    """Compute the Habitat Value Score for a design.

    Args:
        placed_plants: list of placed-plant dicts; each needs a
            ``plant_id``. Duplicate plant_ids count once toward species
            metrics but all count toward ``n_total_plants``.
        structures: list of placed-structure dicts; each is matched to a
            habitat structure id via ``id`` / ``type`` / slugified
            ``name``.
        connection: optional open sqlite3 connection (for tests / reuse).
            When ``None``, a fresh ``src.db.plants.get_connection()`` is
            opened and closed internally.

    Returns:
        A :class:`HabitatScore`, or ``None`` when nothing is placed (no
        plants and no structures) — the caller renders its own
        "place something first" placeholder.

    Raises:
        HabitatScoreError: when the plant database can't be read.
    """
    if not placed_plants and not structures:
        return None

    owns_connection = connection is None
    try:
        from src.db.plants import plant_uses_for_ids
        from src.db.fauna import (
            lepidoptera_supported_by_plants, fauna_supported_by_plants,
        )
        if owns_connection:
            from src.db.plants import get_connection
            connection = get_connection()
    except Exception as exc:  # pragma: no cover - import guard
        raise HabitatScoreError(str(exc)) from exc

    try:
        plant_rows: dict[int, dict] = {}
        plant_ids = list({p["plant_id"] for p in placed_plants})
        for pid in plant_ids:
            row = connection.execute(
                "SELECT id, common_name, plant_type, "
                "       native_to_alberta, bloom_period "
                "FROM plants WHERE id = ?",
                (pid,)
            ).fetchone()
            if row:
                plant_rows[pid] = dict(row)
        # Schema v13: tag membership from the plant_uses junction.
        plant_uses_map = plant_uses_for_ids(list(plant_rows.keys()))
        # Schema v13: distinct lepidoptera species larval-hosted.
        scored_ids = list(plant_rows.keys())
        n_lepidoptera_supported = len(
            lepidoptera_supported_by_plants(scored_ids)
        )
        # Schema v20: distinct native fauna supported per taxon (informational).
        fauna_by_taxon: dict[str, int] = {}
        for _taxon in ("lepidoptera", "bird", "bee", "other_insect", "mammal"):
            _n = len(fauna_supported_by_plants(scored_ids, taxon=_taxon))
            if _n:
                fauna_by_taxon[_taxon] = _n
    except Exception as exc:
        raise HabitatScoreError(str(exc)) from exc
    finally:
        if owns_connection and connection is not None:
            connection.close()

    n_species = len(plant_rows)
    n_total_plants = len(placed_plants)

    def _has_use(pid: int, key: str) -> bool:
        return key in plant_uses_map.get(pid, set())

    # ── 1. % natives (20 pts) ─────────────────────────────────────────
    native_species = sum(
        1 for r in plant_rows.values() if r.get("native_to_alberta")
    )
    native_ratio = native_species / n_species if n_species else 0.0
    score_native = native_ratio * 20

    # ── 2. Keystone species (15 pts, full at 5 distinct species) ──────
    keystone_species = [
        r["common_name"] for pid, r in plant_rows.items()
        if _has_use(pid, "keystone_species")
    ]
    score_keystone = min(len(keystone_species) / 5.0, 1.0) * 15

    # ── 3. Host plant species (10 pts, full at 10) ────────────────────
    host_species = [
        r["common_name"] for pid, r in plant_rows.items()
        if _has_use(pid, "host_plant")
    ]
    score_host = min(len(host_species) / 10.0, 1.0) * 10

    # ── 4. Bird food species (10 pts, full at 10) ─────────────────────
    bird_species = [
        r["common_name"] for pid, r in plant_rows.items()
        if _has_use(pid, "bird_food")
    ]
    score_bird = min(len(bird_species) / 10.0, 1.0) * 10

    # ── 5. Vegetation layer diversity (15 pts, 3 pts per layer) ───────
    layers_present: set[str] = set()
    for r in plant_rows.values():
        layer = PLANT_TYPE_TO_LAYER.get(r.get("plant_type", ""))
        if layer:
            layers_present.add(layer)
    layers_canonical = layers_present & CANONICAL_LAYERS
    score_layers = min(len(layers_canonical), 5) * 3

    # ── 6. Structural diversity (10 pts, 2 pts per distinct type) ─────
    habitat_struct_types: set[str] = set()
    for s in structures:
        sid = s.get("id") or s.get("type") or s.get("name", "").lower().replace(" ", "_")
        if sid in HABITAT_STRUCTURE_IDS:
            habitat_struct_types.add(sid)
    score_structs = min(len(habitat_struct_types), 5) * 2

    # ── 7. Bloom continuity across growing season Apr–Oct (20 pts) ────
    growing = set(GROWING_SEASON_MONTHS)
    bloom_months: set[int] = set()
    for r in plant_rows.values():
        if r.get("bloom_period"):
            for m in parse_month_range(r["bloom_period"]):
                if m in growing:
                    bloom_months.add(m)
    score_bloom = (len(bloom_months) / len(growing)) * 20

    total = (score_native + score_keystone + score_host + score_bird
             + score_layers + score_structs + score_bloom)
    total_int = int(round(total))

    # ── Food-web completeness (informational, un-summed; F3) ──────────
    # The Tallamy chain: host plants make caterpillars, and ~96% of land
    # birds feed those caterpillars to their nestlings. Presence of species
    # isn't enough — the *links* have to connect. Reuse the counts already
    # gathered: caterpillars come from larval-host lepidoptera (relationship
    # data) or the host_plant tag; birds from the bird fauna they support or
    # the bird_food tag. Reported beside the score, never added to it.
    n_birds = fauna_by_taxon.get("bird", 0)
    has_caterpillars = n_lepidoptera_supported > 0 or bool(host_species)
    has_birds = n_birds > 0 or bool(bird_species)
    if has_caterpillars and has_birds:
        food_web_status = "complete"
    elif has_caterpillars:
        food_web_status = "no_birds"
    elif has_birds:
        food_web_status = "no_hosts"
    else:
        food_web_status = "empty"
    food_web = {
        "caterpillars": has_caterpillars,
        "n_caterpillars": n_lepidoptera_supported,
        "birds": has_birds,
        "n_birds": n_birds,
        "complete": has_caterpillars and has_birds,
        "status": food_web_status,
    }

    return HabitatScore(
        total=total_int,
        grade=_grade_for(total_int),
        n_species=n_species,
        n_total_plants=n_total_plants,
        scored_plant_ids=sorted(plant_rows.keys()),
        native_species=native_species,
        native_ratio=native_ratio,
        score_native=score_native,
        keystone_species=keystone_species,
        score_keystone=score_keystone,
        host_species=host_species,
        score_host=score_host,
        bird_species=bird_species,
        score_bird=score_bird,
        layers_present=sorted(layers_canonical),
        score_layers=score_layers,
        habitat_struct_types=sorted(habitat_struct_types),
        score_structs=score_structs,
        bloom_months=sorted(bloom_months),
        gap_months=sorted(growing - bloom_months),
        score_bloom=score_bloom,
        n_lepidoptera_supported=n_lepidoptera_supported,
        fauna_by_taxon=fauna_by_taxon,
        food_web=food_web,
    )
