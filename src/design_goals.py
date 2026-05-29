"""
design_goals.py — Registry mapping user-facing "design goals" to the
machinery that honours them.

A *goal* is a checkbox the user ticks in the Generate-Design dialog (or a
``--goal`` flag on the CLI): "Food producing", "Pet friendly", etc. Each goal
maps to three things, used by the hybrid generation path in
:mod:`src.llm_design`:

  * ``filters``        — hard ``search_plants`` keyword filters applied when the
                         data exists to back the goal (e.g. ``edible_only`` for
                         "Food producing"). These are *guaranteed* — the
                         generator binds them even if the model forgets.
  * ``prompt_hint``    — a sentence appended to the LLM brief. Used for goals
                         with no data backing yet (pet/kid safety, all-season
                         bloom) *and* alongside filters, since hints also help
                         the model choose well.
  * ``community_hints``— substrings matched against the names of seeded plant
                         communities (polycultures) so the deterministic
                         fallback can pull in a fitting community.

``backed=False`` marks a goal we can only *hint* this release because the
supporting plant data does not exist yet (see ``docs/data_gaps_v1.44.md``).
When that data lands in a later chunk, flip ``backed`` to ``True`` and add the
``filters`` here — every caller (GUI, CLI, LLM path, fallback) picks it up at
once, because this module is the single source of truth.

Nothing here imports Qt or touches the database; it is a pure, declarative
table so it can be unit-tested in isolation and imported headlessly.
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class Goal:
    """One selectable design goal. ``key`` is the stable identifier stored in
    ``site_config["priorities"]`` and accepted by the CLI; ``label`` is the UI
    text."""

    key: str
    label: str
    filters: dict = field(default_factory=dict)
    prompt_hint: str = ""
    community_hints: tuple[str, ...] = ()
    backed: bool = True


# Order here is the order checkboxes appear in the dialog. The two fully-backed
# ecological goals first, then food (backed via edible_parts), then the
# hint-only goals awaiting data work.
GOALS: list[Goal] = [
    Goal(
        key="native_only",
        label="Native only",
        filters={"native_only": True},
        prompt_hint="Use only species native to Alberta.",
    ),
    Goal(
        key="pollinator",
        label="Pollinator habitat",
        filters={"pollinator_only": True},
        prompt_hint="Maximise nectar and pollen for native bees and butterflies.",
        community_hints=("Pollinator", "Bloom"),
    ),
    Goal(
        key="food_producing",
        label="Food producing",
        filters={"edible_only": True},
        prompt_hint="Favour plants with edible fruit, nuts, leaves, or roots.",
        community_hints=("Edible", "Berry"),
    ),
    Goal(
        key="flowers_all_season",
        label="Flowers all season",
        # No bloom-month data to filter on yet (bloom_period is free text);
        # handled as a hint until month-coded bloom data lands (data gap #2).
        prompt_hint=(
            "Stagger bloom so something is flowering from April through "
            "October; avoid clustering all bloom into a single month."
        ),
        community_hints=("Continuous Bloom", "Pollinator"),
        backed=False,
    ),
    Goal(
        key="pet_friendly",
        label="Pet friendly",
        # No toxicity data yet (data gap #1) — hint only.
        prompt_hint="Avoid plants toxic to dogs and cats.",
        backed=False,
    ),
    Goal(
        key="kid_friendly",
        label="Kid friendly",
        # No toxicity / thorn data yet (data gap #1) — hint only.
        prompt_hint=(
            "Avoid plants with toxic berries or sharp thorns near areas where "
            "children play."
        ),
        backed=False,
    ),
    Goal(
        key="year_round_interest",
        label="Visually interesting all year",
        # deciduous_evergreen / fruit_period exist but aren't filterable yet
        # (data gap #3) — hint only, with a berry/winter-fruit community nudge.
        prompt_hint=(
            "Include evergreens and plants with winter-persistent fruit, bark, "
            "or seed heads so the design has structure through winter."
        ),
        community_hints=("Berry",),
        backed=False,
    ),
]

_BY_KEY: dict[str, Goal] = {g.key: g for g in GOALS}


def goal_keys() -> list[str]:
    """All valid goal keys, in dialog order. Used for CLI ``choices=``."""
    return [g.key for g in GOALS]


def get_goal(key: str) -> Goal | None:
    """Return the :class:`Goal` for ``key``, or ``None`` if unknown."""
    return _BY_KEY.get(key)


def filters_for_goals(keys) -> dict:
    """Merge the hard ``search_plants`` filters for ``keys``.

    Filters are additive (they narrow the query with AND), so on the rare key
    collision a truthy value wins. Unknown keys are skipped silently — the
    caller may pass arbitrary stored priorities.
    """
    merged: dict = {}
    for key in keys or ():
        goal = _BY_KEY.get(key)
        if goal is None:
            continue
        for fk, fv in goal.filters.items():
            if fv:
                merged[fk] = fv
    return merged


def hints_for_goals(keys) -> list[str]:
    """Ordered, de-duplicated ``prompt_hint`` strings for ``keys`` (both backed
    and hint-only goals contribute — hints help the model even when a hard
    filter also applies). Unknown keys are skipped."""
    out: list[str] = []
    seen: set[str] = set()
    for key in keys or ():
        goal = _BY_KEY.get(key)
        if goal is None or not goal.prompt_hint:
            continue
        if goal.prompt_hint not in seen:
            seen.add(goal.prompt_hint)
            out.append(goal.prompt_hint)
    return out


def community_name_hints(keys) -> list[str]:
    """Ordered, de-duplicated community-name substrings to match against seeded
    plant communities for ``keys``. Unknown keys are skipped."""
    out: list[str] = []
    seen: set[str] = set()
    for key in keys or ():
        goal = _BY_KEY.get(key)
        if goal is None:
            continue
        for hint in goal.community_hints:
            if hint not in seen:
                seen.add(hint)
                out.append(hint)
    return out


def unbacked_goals(keys) -> list[str]:
    """Goal keys among ``keys`` that have no hard filter this release (so the
    generator can warn that they were applied as guidance only). Unknown keys
    are skipped."""
    return [
        key for key in (keys or ())
        if (g := _BY_KEY.get(key)) is not None and not g.backed
    ]
