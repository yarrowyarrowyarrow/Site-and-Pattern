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
supporting plant data does not exist yet (see ``docs/DATA_GAPS.md``).
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
    # An advisory shown when the goal is honoured by a DENYLIST (exclude
    # known-bad) rather than a positive guarantee — e.g. the safety goals.
    caveat: str = ""


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
    # The region's own list (F220; from the pack since V3.24, ED-3): placed
    # here by _with_local_goal below, so the dialog keeps its order.
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
        # Backed by a denylist (schema v18): excludes plants classified toxic
        # to pets. Unassessed plants pass — hence the caveat.
        filters={"pet_safe_only": True},
        prompt_hint="Avoid plants toxic to dogs and cats.",
        caveat=("Pet friendly excludes plants known to be toxic to pets, but "
                "the absence of a flag is not a guarantee of safety — confirm "
                "before planting where it matters."),
    ),
    Goal(
        key="kid_friendly",
        label="Kid friendly",
        # Denylist: excludes plants toxic to people AND thorny ones.
        filters={"kid_safe_only": True},
        prompt_hint=(
            "Avoid plants with toxic berries or sharp thorns near areas where "
            "children play."
        ),
        caveat=("Kid friendly excludes plants known to be toxic to people and "
                "those with thorns, but is not a guarantee of safety — confirm "
                "before planting where children play."),
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
    Goal(
        key="well_behaved",
        label="Won't take over the yard",
        # Denylist: excludes aggressive rhizomatous spreaders + heavy self-seeders.
        filters={"well_behaved_only": True},
        prompt_hint=(
            "Prefer clumping, well-behaved plants; avoid aggressive "
            "rhizomatous spreaders and heavy self-seeders."
        ),
        caveat=("Won't-take-over excludes plants known to spread aggressively; "
                "unassessed plants are still shown."),
    ),
    Goal(
        key="low_cost",
        label="Budget-friendly / easy to find",
        # Denylist (schema v19): drop only plants that are hard to source
        # (seed/plug-only or rare). Pair with the dialog's Budget field, which
        # caps the design's estimated total.
        filters={"common_only": True},
        prompt_hint=(
            "Prefer affordable, readily available native plants; avoid rare or "
            "seed-only specialties and large specimen trees."
        ),
        # The communities built from plants people can buy (V3.14).
        community_hints=("Easy",),
        caveat=("Budget-friendly uses estimated Alberta retail prices (ranges, "
                "not quotes) and excludes only hard-to-source plants."),
    ),
]

#: The goal that keeps plants native around the region's place (F220). Its
#: key was ``edmonton_native`` until V3.24 (ED-3): a saved design's priorities
#: still say that, and are read as this.
LOCAL_KEY = "local_native"
_OLD_KEYS = {"edmonton_native": LOCAL_KEY}


def local_goal(r) -> Goal:
    """The local goal for a region pack: "Edmonton natives only" for the
    Edmonton pack, "Calgary natives only" for a Calgary one, with no code."""
    from src.native_here import PROVINCE_NAMES               # noqa: PLC0415
    prov = PROVINCE_NAMES.get(r.province, r.province)
    km = f"{r.radius_km:g}"
    return Goal(
        key=LOCAL_KEY,
        label=f"{r.short} natives only",
        filters={"native_near": r.key},
        prompt_hint=(f"Use only species native around {r.short}, which leaves "
                     f"out the plants native elsewhere in {prov} but not "
                     "here."),
        # The pack's seeded communities lead the offline pick.
        community_hints=tuple(h for h in [(r.communities or {}).get("hint")]
                              if h),
        caveat=(f"{r.short} natives only keeps plants collected at least "
                f"{r.min_collections} times within {km} km of "
                f"{r.short}, or confirmed on review. A species the herbarium "
                "record is too thin to settle is left out until it is "
                "reviewed, not because it is known to be foreign here."),
    )


def _region_for(site_config):
    """The pack a design's goals are read against: the pin's, the default
    with no pin, ``None`` for a pin outside every pack (the local goal is
    then not offered)."""
    from src import region                                   # noqa: PLC0415
    sc = site_config or {}
    if sc.get("latitude") is None or sc.get("longitude") is None:
        return region.default()
    return region.at(sc["latitude"], sc["longitude"])


def _with_local_goal(goals: list, r) -> list:
    """``goals`` with the local goal second, after "Native only"."""
    out = [g for g in goals if g.key != LOCAL_KEY]
    if r is not None:
        out.insert(1, local_goal(r))
    return out


def _default_region():
    from src import region                                   # noqa: PLC0415
    return region.default()


GOALS[:] = _with_local_goal(GOALS, _default_region())

_BY_KEY: dict[str, Goal] = {g.key: g for g in GOALS}


def normalize(keys) -> list:
    """Stored goal keys read as today's: ``edmonton_native`` is the local goal."""
    out = []
    for k in keys or ():
        k = _OLD_KEYS.get(k, k)
        if k not in out:
            out.append(k)
    return out


def goals_for_site(site_config=None) -> list:
    """The goals a design can choose from: the local goal is its pin's pack's,
    and is left out for a pin outside every pack (§4.4)."""
    return _with_local_goal(GOALS, _region_for(site_config))


def _lookup(key, site_config=None):
    key = _OLD_KEYS.get(key, key)
    if key == LOCAL_KEY:
        r = _region_for(site_config)
        return local_goal(r) if r is not None else None
    return _BY_KEY.get(key)


def goal_keys() -> list[str]:
    """All valid goal keys, in dialog order. Used for CLI ``choices=``."""
    return [g.key for g in GOALS]


def get_goal(key: str, site_config=None) -> Goal | None:
    """Return the :class:`Goal` for ``key``, or ``None`` if unknown."""
    return _lookup(key, site_config)


def filters_for_goals(keys, site_config=None) -> dict:
    """Merge the hard ``search_plants`` filters for ``keys``.

    Filters are additive (they narrow the query with AND), so on the rare key
    collision a truthy value wins. Unknown keys are skipped silently — the
    caller may pass arbitrary stored priorities.
    """
    merged: dict = {}
    for key in keys or ():
        goal = _lookup(key, site_config)
        if goal is None:
            continue
        for fk, fv in goal.filters.items():
            if fv:
                merged[fk] = fv
    return merged


def hints_for_goals(keys, site_config=None) -> list[str]:
    """Ordered, de-duplicated ``prompt_hint`` strings for ``keys`` (both backed
    and hint-only goals contribute — hints help the model even when a hard
    filter also applies). Unknown keys are skipped."""
    out: list[str] = []
    seen: set[str] = set()
    for key in keys or ():
        goal = _lookup(key, site_config)
        if goal is None or not goal.prompt_hint:
            continue
        if goal.prompt_hint not in seen:
            seen.add(goal.prompt_hint)
            out.append(goal.prompt_hint)
    return out


def community_name_hints(keys, site_config=None) -> list[str]:
    """Ordered, de-duplicated community-name substrings to match against seeded
    plant communities for ``keys``. Unknown keys are skipped."""
    out: list[str] = []
    seen: set[str] = set()
    for key in keys or ():
        goal = _lookup(key, site_config)
        if goal is None:
            continue
        for hint in goal.community_hints:
            if hint not in seen:
                seen.add(hint)
                out.append(hint)
    return out


def caveats_for_goals(keys, site_config=None) -> list[str]:
    """Ordered, de-duplicated caveat strings for ``keys`` — advisories for
    goals honoured by a denylist (e.g. the safety goals) rather than a positive
    guarantee. Unknown keys are skipped."""
    out: list[str] = []
    seen: set[str] = set()
    for key in keys or ():
        goal = _lookup(key, site_config)
        if goal is None or not goal.caveat:
            continue
        if goal.caveat not in seen:
            seen.add(goal.caveat)
            out.append(goal.caveat)
    return out


def unbacked_goals(keys, site_config=None) -> list[str]:
    """Goal keys among ``keys`` that have no hard filter this release (so the
    generator can warn that they were applied as guidance only). Unknown keys
    are skipped."""
    return [
        key for key in (keys or ())
        if (g := _lookup(key, site_config)) is not None and not g.backed
    ]
