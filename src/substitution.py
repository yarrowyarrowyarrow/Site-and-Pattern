"""
src/substitution.py — "the nursery is out" (F91, V2.57).

Design principle P3 (relationships matter more than components) and P10 (design
for relationships, not objects) — see docs/DESIGN_PHILOSOPHY.md.

Every plant tool has a "similar plants" feature and every one of them means
*similar height and similar flower colour* — a similarity between objects, which
is exactly the frame P10 exists to reject. This app holds the relationships, so
it can mean something different and much more useful: **ecologically
equivalent**. Same vegetation layer, an overlapping site envelope, and — the
part nothing else can do — an overlapping set of animals actually supported.

And then it **reports the trade rather than hiding it**. A substitution is a
loss as well as a gain, and a tool that returns "here are 5 similar plants"
without saying what changes is asking the user to trust a judgement it has not
shown them (P9). So:

    Chokecherry for Saskatoon — keeps 9 of 12 supported species.
    You lose 3, including Cedar Waxwing. Blooms a month earlier.

**Triggered by the real moment**, which is not "browse alternatives": it is the
nursery being out of stock, or the plant being out of budget. Both are reasons a
designer is holding a plant they cannot have, which is why
:func:`substitutes` takes the plant you are losing rather than a search.

Qt-free, with the catalogue and the fauna queries injectable, so it is testable
without a database.
"""

from __future__ import annotations

from typing import Callable, NamedTuple, Optional

#: Taxa the fauna comparison runs over — the same tuple ``plant_impact`` uses,
#: so "supported species" means the same thing in both places.
TAXA = ("lepidoptera", "bird", "bee", "other_insect", "mammal")

#: How many alternatives to offer. A list of twenty is a search result; a list
#: of five is a recommendation, which is what somebody on the phone to a nursery
#: actually needs.
DEFAULT_LIMIT = 5

#: Below this share of the original's supported fauna, a candidate is not
#: offered at all. A "substitution" that keeps a fifth of the relationships is
#: a different plant, and calling it equivalent would be the exact false
#: reassurance this module exists to avoid.
MIN_FAUNA_KEPT = 0.25

#: …but only once the original has enough recorded relationships for that ratio
#: to mean anything. With one recorded species, "keep 25%" collapses into "keep
#: that exact species", so a thinly-recorded plant would return no substitutes
#: at all — punishing the user for a gap in the *data* rather than telling them
#: something about the *plants*. Below this, candidates are ranked rather than
#: excluded, and the sentence says the comparison is thin.
MIN_FAUNA_TO_FILTER = 4


class Swap(NamedTuple):
    """One candidate substitution, with the trade already computed."""
    plant_id: int
    common_name: str
    scientific_name: str
    kept: int                 # supported species the swap keeps
    original_total: int       # supported species the original had
    lost: list                # names of species lost (sorted)
    gained: int               # species the candidate adds
    price_low: float
    price_high: float
    availability: str
    bloom_shift: int          # months earlier (−) / later (+); 0 = same start

    @property
    def kept_fraction(self) -> float:
        return (self.kept / self.original_total) if self.original_total else 0.0


# ── Reading a plant ──────────────────────────────────────────────────────────

#: plant_type → the group a substitution may draw from.
#:
#: **Deliberately not** ``habitat_score.PLANT_TYPE_TO_LAYER``, for two separate
#: reasons.
#:
#: The first is that the canonical map does not cover this catalogue. It knows
#: six types; the plants table holds eleven, and the five it misses account for
#: **311 of 437 species** — every ``wildflower`` (210 of them, the largest group
#: by far), plus grass, sedge, rush, aquatic and fern. Using it here would leave
#: substitution silently dead for most of the app. That gap is not fixed by this
#: module: widening the canonical map moves the vegetation-layer component of
#: every affected design's Habitat Value Score, which the score-stability rule
#: makes the author's decision, not a side effect of building this. Measured and
#: reported as backlog row F124.
#:
#: The second is that even a corrected layer map would be the wrong grain here.
#: Grasses and forbs are both "herbaceous", and swapping a wind-pollinated grass
#: for an insect-pollinated forb is a bad recommendation however equal their
#: layer. Substitution wants graminoids kept apart from forbs, which is finer
#: than the layer question and specific to this feature.
SUBSTITUTION_GROUPS: dict = {
    "tree": "overstory",
    "shrub": "shrub",
    "wildflower": "forb",
    "herb": "forb",
    "root": "forb",
    "grass": "graminoid",
    "sedge": "graminoid",
    "rush": "graminoid",
    "groundcover": "groundcover",
    "vine": "vine",
    "fern": "fern",
    "aquatic": "aquatic",
}


def _layer_of(row: dict) -> str:
    return SUBSTITUTION_GROUPS.get((row.get("plant_type") or "").lower(), "")


def _bloom_start(row: dict) -> Optional[int]:
    from src.habitat_score import parse_month_range
    months = parse_month_range(row.get("bloom_period") or "")
    return min(months) if months else None


def _tokens(value) -> set:
    """A multi-value catalogue field as a set.

    ``sun_requirement`` is **comma-separated** — ``"full_sun,partial_shade"`` is
    one plant that tolerates both, not a typo. Comparing these as whole strings
    treats a full-sun plant and a full-sun-or-part-shade plant as incompatible,
    which rejected 76 of 80 candidate grasses before this was noticed.
    """
    return {t.strip().lower() for t in str(value or "").split(",") if t.strip()}


def _zone(value) -> Optional[int]:
    """A hardiness zone as an int, or ``None`` when it cannot be read.

    The column is not reliably numeric: the catalogue records uncertainty in
    place, so ``'4?'`` is a real stored value. ``int()`` on it raises, which
    crashed this function on the first shrub it was given. An unreadable zone
    reads as "not recorded" and stops constraining the match, rather than
    taking the whole feature down.
    """
    if value is None:
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        digits = "".join(c for c in str(value) if c.isdigit())
        return int(digits) if digits else None


def _envelope_ok(a: dict, b: dict) -> bool:
    """Whether ``b`` can grow where ``a`` was going to.

    Sun and water must *overlap* where both are recorded — not match exactly,
    because these are tolerance sets and a plant that takes sun or part shade
    can stand in for one that takes sun. A blank on either side is not treated
    as a mismatch: the catalogue's blanks mean "not recorded", and excluding on
    them would quietly hide good candidates (the absent-is-not-a-value rule the
    confidence work set in V2.53).

    The hardiness ranges must overlap — that one is not negotiable, since a
    plant that cannot survive the winter is not a substitution at any price.
    """
    for field in ("sun_requirement", "water_needs"):
        av, bv = _tokens(a.get(field)), _tokens(b.get(field))
        if av and bv and not (av & bv):
            return False
    a_lo, a_hi = _zone(a.get("hardiness_zone_min")), _zone(a.get("hardiness_zone_max"))
    b_lo, b_hi = _zone(b.get("hardiness_zone_min")), _zone(b.get("hardiness_zone_max"))
    if None in (a_lo, a_hi, b_lo, b_hi):
        return True
    return not (b_lo > a_hi or b_hi < a_lo)


def _fauna_for(plant_id: int, supported_by=None) -> set:
    if supported_by is None:
        from src.db.fauna import fauna_supported_by_plants as supported_by
    out: set = set()
    for taxon in TAXA:
        try:
            out |= set(supported_by([int(plant_id)], taxon=taxon) or ())
        except Exception:                                  # noqa: BLE001
            continue
    return out


def _fauna_names(ids: set, get_fauna=None) -> list:
    if not ids:
        return []
    if get_fauna is None:
        from src.db.fauna import get_fauna
    names = []
    for fid in ids:
        try:
            row = get_fauna(fid) or {}
        except Exception:                                  # noqa: BLE001
            continue
        if row.get("common_name"):
            names.append(row["common_name"])
    return sorted(names, key=str.lower)


# ── The recommendation ───────────────────────────────────────────────────────

def substitutes(plant_id: int, *, limit: int = DEFAULT_LIMIT,
                get_plant: Optional[Callable] = None,
                all_plants: Optional[Callable] = None,
                supported_by: Optional[Callable] = None,
                get_fauna: Optional[Callable] = None) -> list:
    """Ecologically equivalent alternatives to ``plant_id``, best first.

    Ranked by how much of the original's supported fauna the candidate keeps,
    then by how many species it adds. Native plants are preferred over
    non-natives at equal standing, because a native-habitat app substituting
    away from a native would be working against itself.
    """
    if get_plant is None:
        from src.db.plants import get_plant as get_plant
    if all_plants is None:
        from src.db.plants import get_all_plants as all_plants

    original = get_plant(int(plant_id)) or {}
    if not original:
        return []
    layer = _layer_of(original)
    origin_fauna = _fauna_for(plant_id, supported_by)
    origin_bloom = _bloom_start(original)

    scored = []
    for cand in all_plants() or []:
        cid = cand.get("id")
        if cid is None or int(cid) == int(plant_id):
            continue
        if _layer_of(cand) != layer or not layer:
            continue
        if not _envelope_ok(original, cand):
            continue
        cand_fauna = _fauna_for(cid, supported_by)
        kept_ids = origin_fauna & cand_fauna
        # Filter on retention only when the original is well enough recorded for
        # the ratio to be about the plants rather than about the data.
        if (len(origin_fauna) >= MIN_FAUNA_TO_FILTER
                and (len(kept_ids) / len(origin_fauna)) < MIN_FAUNA_KEPT):
            continue
        from src.sourcing import plant_price_range
        lo, hi = plant_price_range(cand)
        cb = _bloom_start(cand)
        scored.append((
            len(kept_ids),
            len(cand_fauna - origin_fauna),
            1 if cand.get("native_to_alberta") else 0,
            Swap(
                plant_id=int(cid),
                common_name=cand.get("common_name") or "",
                scientific_name=cand.get("scientific_name") or "",
                kept=len(kept_ids),
                original_total=len(origin_fauna),
                lost=_fauna_names(origin_fauna - cand_fauna, get_fauna),
                gained=len(cand_fauna - origin_fauna),
                price_low=float(lo), price_high=float(hi),
                availability=(cand.get("availability_class") or "").strip(),
                bloom_shift=((cb - origin_bloom)
                             if (cb is not None and origin_bloom is not None)
                             else 0),
            ),
        ))
    scored.sort(key=lambda t: (t[0], t[1], t[2]), reverse=True)
    return [t[3] for t in scored[:max(1, int(limit))]]


# ── Saying it out loud ───────────────────────────────────────────────────────

def _bloom_phrase(shift: int) -> str:
    if not shift:
        return ""
    months = abs(int(shift))
    unit = "a month" if months == 1 else f"{months} months"
    return f"Blooms {unit} {'later' if shift > 0 else 'earlier'}."


def swap_line(original_name: str, swap: Swap) -> str:
    """One sentence a designer can read on the phone to a nursery.

    Leads with what is kept and then names what is lost. Both halves are
    required: the gain alone is a sales pitch, and the loss alone would stop
    somebody making a substitution that is, on balance, fine.
    """
    parts = [f"{swap.common_name} for {original_name} "]
    if swap.original_total:
        parts.append(f"— keeps {swap.kept} of {swap.original_total} "
                     f"supported species")
        if swap.lost:
            shown = ", ".join(swap.lost[:2])
            more = f" and {len(swap.lost) - 2} more" if len(swap.lost) > 2 else ""
            parts.append(f". You lose {len(swap.lost)}, including {shown}{more}")
    else:
        # Honest about the reason there is no comparison to report, rather than
        # printing "keeps 0 of 0" as though that were a finding.
        parts.append("— no wildlife relationships are recorded for "
                     f"{original_name}, so there is nothing to compare")
    if swap.gained:
        parts.append(f". Adds {swap.gained}")
    line = "".join(parts) + "."
    # A ratio out of one or two species is arithmetic, not evidence. Say so,
    # rather than letting "keeps 1 of 2" read with the same authority as
    # "keeps 6 of 8" (P9).
    if 0 < swap.original_total < MIN_FAUNA_TO_FILTER:
        line += (f" Only {swap.original_total} "
                 f"{'relationship is' if swap.original_total == 1 else 'relationships are'} "
                 f"recorded for it, so this comparison is thin.")
    bloom = _bloom_phrase(swap.bloom_shift)
    return f"{line} {bloom}".strip()


def swap_lines(plant_id: int, *, limit: int = DEFAULT_LIMIT, **kwargs) -> list:
    """``swap_line`` for each alternative — the whole card, ready to show."""
    get_plant = kwargs.get("get_plant")
    if get_plant is None:
        from src.db.plants import get_plant
    original = get_plant(int(plant_id)) or {}
    name = original.get("common_name") or "it"
    return [swap_line(name, s)
            for s in substitutes(plant_id, limit=limit, **kwargs)]
