"""
src/design_critic.py — evaluate-and-repair intelligence for Generate Design
(V1.62).

Design principle P8 (repair is more sophisticated than creation) and P9
(uncertainty is a feature — evaluate, critique, revise rather than assert a
single perfect answer) — see docs/DESIGN_PHILOSOPHY.md.

The generator's first pass produces a valid design; this module is what
makes the result *good*. It closes the loop the pipeline already had all
the parts for:

  1. :func:`evaluate_design` — score a generated project with the same
     Habitat Value Score the Analysis panel shows (species diversity,
     keystone/host/bird support, vertical layers, structures, bloom
     continuity).
  2. :func:`critique_lines` — turn the score breakdown into the concrete,
     human-readable issues ("no bloom in August", "no keystone species").
     The GUI can show them; :meth:`LLMClient.revise_spec` feeds them back
     to the model for a revision round.
  3. :func:`apply_repairs` — a deterministic critic that fixes the most
     impactful gaps directly from the catalogue (no LLM needed), so even
     fully-offline designs improve: missing keystone → add one, missing
     host plant → add one, bloom-gap months → add natives flowering then.

Pure Python; the plant catalogue is reached through an injected
``query_plants`` and placement spots through an injected ``position_for``
callable, so there are no import cycles with :mod:`src.llm_design` and
tests can drive it synthetically.
"""

from __future__ import annotations

from typing import Callable, Optional

# The shared uncertainty vocabulary (F8). Imported rather than restated so the
# critic, the panels and the static site all hedge the same way — the whole
# reason the confidence block was built as one increment.
from src.confidence import hedge_count as _hedge_count, no_record_of as _no_record_of

_MONTH_NAMES = ["", "January", "February", "March", "April", "May", "June",
                "July", "August", "September", "October", "November",
                "December"]

# Most repairs to attempt per design — the critic should mend gaps, not
# take over the plant list.
_MAX_REPAIRS = 3


def evaluate_design(project) -> Optional[dict]:
    """Habitat-score breakdown for a :class:`~src.permadesign_api.Project`
    (the ``HabitatScore.as_dict()`` shape), or ``None`` when nothing is
    placed / the score can't be computed."""
    try:
        from src.habitat_score import compute_habitat_score
        hs = compute_habitat_score(project.placed_plants, project.structures)
    except Exception:  # noqa: BLE001 — evaluation is best-effort
        return None
    return hs.as_dict() if hs is not None else None


def critique_lines(habitat: dict) -> list[str]:
    """Concrete issues in a habitat-score breakdown, most impactful first.
    Empty list = nothing worth flagging.

    **Absences are phrased as absences of RECORD (F8, V2.53).** Three of these
    lines used to state a fact about the yard — *"Nothing provides bird food"* —
    from a zero in a score component that reads **use tags**. Two things make
    that a claim the data cannot carry. The catalogue's tags are an editorial
    judgement rather than an observation; and the app holds a *second, cited*
    source for the same question, the ``plant_fauna`` edges, which disagrees for
    48 species (``data_quality.validate_use_tags_against_edges`` counts them —
    37 with a documented ``larval_host`` edge and no ``host_plant`` tag,
    Chokecherry and Balsam Poplar among them).

    So where ``food_web`` contradicts the tag-derived component, this says what
    is actually true rather than picking the gloomier of the two numbers sitting
    in the same dictionary.

    **Correction (V2.58).** This paragraph used to call ``food_web``
    "edge-derived". It was not: ``has_birds`` fell back to the ``bird_food``
    tag, so the dict could report ``birds: True`` beside ``n_birds: 0`` and call
    the web complete. The lines below were already written defensively — each
    checks the bool *and* the count — so the prose escaped, but the premise was
    wrong and the status field was not so lucky. ``food_web`` now carries
    ``birds_evidence`` / ``caterpillars_evidence``, and ``complete`` means
    documented.
    """
    out: list[str] = []
    comp = (habitat or {}).get("components", {}) or {}
    food_web = (habitat or {}).get("food_web") or {}

    # Coverage first, because it reframes everything under it: a design whose
    # species are simply unrecorded should not read as a design that supports
    # nothing (V2.58).
    _scored = int(food_web.get("species_scored") or 0)
    _known = int(food_web.get("species_with_records") or 0)
    if _scored and _known == 0:
        out.append(
            f"No wildlife records exist for any of these {_scored} species. "
            f"That is a gap in the catalogue, not a verdict on the planting — "
            f"the app holds relationship data for 99 of 437 plants, and these "
            f"are among the rest.")
    elif _scored and _known < _scored:
        out.append(
            f"Wildlife records exist for {_known} of these {_scored} species. "
            f"The other {_scored - _known} are not recorded as supporting "
            f"nothing — they are simply not recorded yet, so anything below "
            f"counts only what is known.")

    bloom = comp.get("bloom", {})
    gaps = bloom.get("gap_months") or []
    if gaps:
        names = ", ".join(_MONTH_NAMES[m] for m in gaps if 0 < m < 13)
        out.append(
            f"No bloom recorded in {names} — pollinators face a nectar gap; "
            f"add native species flowering then.")

    if (comp.get("keystone", {}).get("score") or 0) == 0:
        out.append(
            "Nothing here is tagged as a keystone species — keystones "
            "(willows, goldenrods, asters…) support far more caterpillars and "
            "wildlife than average plants.")

    if (comp.get("host", {}).get("score") or 0) == 0:
        n_cat = int(food_web.get("n_caterpillars") or 0)
        if food_web.get("caterpillars") and n_cat:
            # The tag says no host plants; the cited edges name the caterpillars.
            # Report the stronger source, and name the weaker one as the gap.
            out.append(
                f"No plant here is tagged as a caterpillar host, yet "
                f"{_hedge_count(n_cat, 'butterfly or moth species')} are "
                f"recorded laying eggs on these plants — the host tags are "
                f"behind the relationship data, so the score reads lower than "
                f"the evidence supports.")
        else:
            out.append(
                "No butterfly/moth host plants recorded — without host plants "
                "there are no caterpillars, and without caterpillars few baby "
                "birds.")

    if (comp.get("bird_food", {}).get("score") or 0) == 0:
        if food_web.get("birds") and int(food_web.get("n_birds") or 0):
            out.append(
                f"No plant here is tagged as bird food, yet "
                f"{_hedge_count(int(food_web['n_birds']), 'bird species')} are "
                f"recorded feeding on these plants.")
        else:
            out.append(_no_record_of("providing bird food (berries/seeds)")
                       + ".")

    # Food-web completeness (F3): flag a *broken* Tallamy chain — one link
    # present without the other. (When both links are missing the separate
    # host / bird-food lines above already say so, so stay quiet there.)
    if food_web.get("status") == "no_birds":
        out.append(
            "Host plants feed caterpillars here, but nothing in the design is "
            "recorded as supporting the birds that should eat them; add "
            "berry/seed producers or bird habitat.")
    elif food_web.get("status") == "no_hosts":
        out.append(
            "You're feeding birds, but no caterpillar host plants are recorded "
            "here — and caterpillars are the protein nestlings need; add host "
            "plants.")

    layers = comp.get("layers", {}).get("present") or []
    if len(layers) <= 2:
        out.append(
            "Little vertical structure (layers: "
            + (", ".join(layers) if layers else "none")
            + ") — mix canopy, shrub, and ground layers for nesting and "
              "shelter niches.")

    if (comp.get("structures", {}).get("score") or 0) == 0:
        out.append(
            "No habitat structures — a bee hotel, brush pile, or snag "
            "adds nesting and overwintering habitat plants alone can't.")

    native = comp.get("native", {})
    ratio = native.get("ratio")
    if ratio is not None and ratio < 0.8:
        out.append(f"Only {ratio:.0%} of species are Alberta natives — "
                   f"favour natives.")
    return out


def _bloom_months_of(row: dict) -> set:
    try:
        from src.habitat_score import parse_month_range
        return set(parse_month_range(row.get("bloom_period") or ""))
    except Exception:  # noqa: BLE001
        return set()


def apply_repairs(project, query_plants: Callable,
                  position_for: Callable, *,
                  habitat: Optional[dict] = None,
                  max_additions: int = _MAX_REPAIRS) -> list[str]:
    """Deterministically mend the most impactful gaps in a generated
    design. Adds at most ``max_additions`` plants (one per gap, bloom
    gaps covered greedily) through ``project.place_plant`` at spots from
    ``position_for()``. Returns the warning messages describing what was
    added (empty when the design needed nothing)."""
    habitat = habitat if habitat is not None else evaluate_design(project)
    if not habitat:
        return []
    comp = habitat.get("components", {}) or {}
    placed_ids = {p.get("plant_id") for p in project.placed_plants}
    msgs: list[str] = []

    def _add(row, why) -> bool:
        if row["id"] in placed_ids:
            return False
        try:
            lat, lng = position_for()
            project.place_plant(row["id"], lat, lng, quantity=1)
        except Exception:  # noqa: BLE001 — a failed repair is not fatal
            return False
        placed_ids.add(row["id"])
        msgs.append(f"Added {row.get('common_name', 'a plant')} — {why}")
        return True

    def _candidates(**filters):
        try:
            return query_plants(native_only=True, **filters) or []
        except Exception:  # noqa: BLE001
            return []

    budget = max(0, int(max_additions))

    if budget and (comp.get("keystone", {}).get("score") or 0) == 0:
        for row in _candidates(keystone_only=True):
            if _add(row, "a keystone species anchors the food web "
                         "(habitat score had none)"):
                budget -= 1
                break

    if budget and (comp.get("host", {}).get("score") or 0) == 0:
        for row in _candidates(host_plant_only=True):
            if _add(row, "a host plant so butterflies and moths can "
                         "actually breed here"):
                budget -= 1
                break

    gaps = list((comp.get("bloom", {}) or {}).get("gap_months") or [])
    if budget and gaps:
        # Greedy cover: prefer the pollinator plant whose bloom span fills
        # the most of the remaining gap months.
        pool = _candidates(pollinator_only=True)
        remaining = set(gaps)
        while budget and remaining and pool:
            best, best_cover = None, set()
            for row in pool:
                cover = _bloom_months_of(row) & remaining
                if len(cover) > len(best_cover):
                    best, best_cover = row, cover
            if best is None or not best_cover:
                break
            months = ", ".join(_MONTH_NAMES[m] for m in sorted(best_cover))
            if _add(best, f"covers the {months} bloom gap for pollinators"):
                budget -= 1
            remaining -= best_cover
            pool.remove(best)

    return msgs
