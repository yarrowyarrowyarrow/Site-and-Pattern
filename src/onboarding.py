"""
onboarding.py — the cold-start path: first run → first design (F44 / F45).

Design principle P1 (living systems self-organize from generative rules — the
example yard is a *rule set resolved against the live catalogue*, not a frozen
layout) and P9 (uncertainty is a feature — a generated or example design is
stated as a starting point, never as an answer) — see docs/DESIGN_PHILOSOPHY.md.

The app opens on a silent blank map. Everything else this project has built —
the food web, the succession engine, the relationship web, the whole teaching
layer — is worth exactly nothing to somebody who never reaches a first design,
and the roadmap's funnel review named this the binding constraint. This module
is the Qt-free core of the fix:

  * :func:`steps_progress` / :func:`first_step` — where the user actually is on
    the three-step path (pin → boundary → plants), computed from the project
    itself so the welcome, the step bar and the Site panel can never disagree
    about what to do next.
  * :data:`FIRST_RUN_GOALS` — the Generate defaults a first-timer should get.
  * :func:`build_example_project` — a real worked design to open and pull apart.

**The example is a spec, not a file.** Shipping a `.perma.geojson` would bake in
plant ids, and ids are NOT stable across reseeds (see `CLAUDE.md` and
`_remap_user_polyculture_plants`) — a shipped example would silently rot into
pointing at the wrong species on some future schema bump. Instead the layout is
authored as species *names* plus positions in metres, resolved against the live
catalogue at open time, exactly as `src/reference_ecosystem.py` resolves its
reference communities. It therefore can never name a plant the app doesn't have,
and it improves as the seed data does. Anything unresolvable is reported to the
caller rather than silently dropped (P9).

Qt-free, DB-injectable, no I/O.
"""

from __future__ import annotations

from typing import Callable, Optional

from src.projection import metres_per_deg

# ── The Generate defaults a first-timer should land on ───────────────────────
# Not "everything ticked": a beginner's first design should be native, feed
# something, stay inside its bed, and be buyable at an actual Alberta nursery.
# Keys are from src/design_goals.py:GOALS.
FIRST_RUN_GOALS: tuple[str, ...] = (
    "native_only", "pollinator", "well_behaved", "low_cost",
)

# ── The three-step path ──────────────────────────────────────────────────────
# Three, because that is what it actually takes to reach a design — not a tour
# of the app. Each step's `done` is read from the project, so the guidance is
# always about the state in front of the user.

STEPS: tuple[dict, ...] = (
    {
        "key": "pin",
        # `short` is what fits on a chip in the strip above the map; `title`
        # is the sentence-shaped version the welcome and the Site panel use.
        # One source, two widths — so they can't drift into saying different
        # things about the same step.
        "short": "Drop a pin",
        "title": "Drop a property pin",
        "detail": "Search your address in the Site tab, or click "
                  "“Use Pin Drop…” and click your yard on the "
                  "map. This is what fetches your climate, soil and frost "
                  "dates.",
    },
    {
        "key": "boundary",
        "short": "Draw the boundary",
        "title": "Draw your boundary",
        "detail": "Draw → ⬡ Boundary, then click around the area "
                  "you want to plant. Click the first point again to close it.",
    },
    {
        "key": "plants",
        "short": "Add plants",
        # V2.41: the two halves swapped. The manual path leads because that is
        # what the app is for; Generate is a shortcut offered second, not the
        # headline. Same change of emphasis as taking Generate off the start
        # screen — `short` has always said "Add plants", so this is the title
        # catching up with the label beside it.
        "title": "Add your plants — or let the app draft it",
        "detail": "Pick plants from the Plants tab and click to place them. "
                  "Or use ✨ Generate Design to fill the boundary from your "
                  "goals and edit from there.",
    },
)


def _has_pin(project: dict) -> bool:
    sc = ((project or {}).get("properties") or {}).get("site_config") or {}
    return sc.get("latitude") is not None and sc.get("longitude") is not None


def _has_boundary(project: dict) -> bool:
    for f in (project or {}).get("features") or []:
        if (f.get("properties") or {}).get("element_type") == "property_boundary":
            return True
    return False


def _has_plants(project: dict) -> bool:
    for f in (project or {}).get("features") or []:
        if (f.get("properties") or {}).get("element_type") == "plant":
            return True
    return False


_DONE_CHECKS = {"pin": _has_pin, "boundary": _has_boundary,
                "plants": _has_plants}


def steps_progress(project: dict) -> list[dict]:
    """The three steps with a live ``done`` flag each.

    Steps are reported independently, not as a strict sequence: someone who
    draws a boundary before dropping a pin has genuinely done step 2, and
    telling them otherwise would be wrong about their own screen.
    """
    return [dict(step, done=_DONE_CHECKS[step["key"]](project))
            for step in STEPS]


def first_step(project: dict) -> dict:
    """The next thing to do — ``{index, total, key, title, detail, complete}``.

    ``complete`` is True once every step is done, at which point the caller
    should stop nagging: the step bar has served its purpose and hides itself.
    """
    progress = steps_progress(project)
    for i, step in enumerate(progress):
        if not step["done"]:
            return {"index": i + 1, "total": len(progress), "complete": False,
                    "key": step["key"], "title": step["title"],
                    "detail": step["detail"]}
    return {"index": len(progress), "total": len(progress), "complete": True,
            "key": "done", "title": "Your design is under way",
            "detail": "Analysis → Habitat scores what it provides; "
                      "Planning → Planting Plan tells you what to buy "
                      "and when to plant it."}


def first_step_line(project: dict) -> str:
    """One-line version for a panel header. Plain text, no markup."""
    step = first_step(project)
    if step["complete"]:
        return step["title"] + "."
    return (f"Step {step['index']} of {step['total']}: {step['title']} "
            f"— {step['detail']}")


# ── The worked example ───────────────────────────────────────────────────────
# A front-yard lawn conversion at the scale most people actually have: one
# 11 x 8 m bed. Offsets are metres east (x) / north (y) from the plot's
# south-west corner, so the layout is real geometry rather than an accident of
# whatever latitude it lands at.

EXAMPLE_NAME = "Example — Front Yard Lawn Conversion"
EXAMPLE_WIDTH_M = 11.0
EXAMPLE_DEPTH_M = 8.0

#: Where the example lands when the user has no pin of their own: central
#: Edmonton, zone 3b/4a — the middle of this app's actual range.
EXAMPLE_DEFAULT_LATLNG = (53.5461, -113.4938)

#: ``(preferred name, fallback names…)`` → the builder takes the first that the
#: live catalogue actually has. Fallbacks exist because seed data changes;
#: a species that resolves to nothing is reported, never silently skipped.
EXAMPLE_PLANTING: tuple[tuple[tuple[str, ...], tuple[float, float]], ...] = (
    # Backbone — two shrubs at the back, offset so the bed never reads as a row.
    (("Saskatoon Berry",), (2.6, 6.2)),
    (("Chokecherry",), (7.9, 6.6)),
    (("Red Osier Dogwood",), (5.2, 6.9)),
    # Mid layer — the nectar relay: spring, midsummer, late summer.
    (("Golden Bean", "Purple Prairie Clover"), (1.4, 4.4)),
    (("Wild Bergamot",), (3.5, 4.7)),
    (("Wild Bergamot",), (4.4, 3.9)),
    (("Showy Milkweed",), (6.4, 4.5)),
    (("Showy Milkweed",), (7.2, 5.1)),
    (("Canada Goldenrod",), (9.3, 4.8)),
    (("Blanketflower", "Prairie Coneflower"), (8.5, 3.6)),
    (("Purple Prairie Clover", "Wild Blue Flax"), (2.2, 3.1)),
    (("Wild Blue Flax", "Harebell"), (6.0, 3.2)),
    # Front edge — short things you can see over, plus the grass matrix.
    (("Prairie Crocus", "Harebell"), (1.2, 1.5)),
    (("Blue Grama Grass", "Rough Fescue"), (3.0, 1.7)),
    (("Blue Grama Grass", "Rough Fescue"), (5.6, 1.3)),
    (("Blue Grama Grass", "Rough Fescue"), (8.2, 1.6)),
    (("Wild Strawberry",), (4.2, 0.9)),
    (("Wild Strawberry",), (7.0, 0.8)),
    (("Yarrow",), (9.6, 2.0)),
)

EXAMPLE_NOTES = (
    "This is a worked example, not a recommendation for your yard.\n\n"
    "It converts about 88 m² of front lawn into one bed: three "
    "fruiting/host shrubs for structure, a nectar relay that carries from "
    "spring (Golden Bean, Prairie Crocus) through midsummer (Wild Bergamot, "
    "Showy Milkweed) into fall (Canada Goldenrod), and a short grass matrix "
    "along the street edge so it still reads as tended.\n\n"
    "Things worth doing to it:\n"
    "  • Analysis → Habitat: score it, then tick “Show the "
    "relationship web” to see which animals each plant feeds.\n"
    "  • Analysis → Habitat → Pull-a-plant: remove the "
    "milkweed and watch what it costs.\n"
    "  • View → 3D Preview: drag the year slider and watch the "
    "shrubs close over the forbs.\n"
    "  • Planning → Planting Plan: what to buy, and when to plant it."
)


def _offset_latlng(lat: float, lng: float,
                   east_m: float, north_m: float) -> tuple[float, float]:
    """Local-tangent offset — the app's one sanctioned metres↔lat/lng path."""
    m_lat, m_lng = metres_per_deg(lat)
    return (lat + north_m / m_lat, lng + east_m / m_lng)


def example_boundary_ring(lat: float, lng: float) -> list:
    """The example plot as a closed GeoJSON ring ([lng, lat] order), with
    ``(lat, lng)`` as its south-west corner."""
    corners = [(0.0, 0.0), (EXAMPLE_WIDTH_M, 0.0),
               (EXAMPLE_WIDTH_M, EXAMPLE_DEPTH_M), (0.0, EXAMPLE_DEPTH_M)]
    ring = []
    for east, north in corners:
        plat, plng = _offset_latlng(lat, lng, east, north)
        ring.append([round(plng, 7), round(plat, 7)])
    ring.append(list(ring[0]))
    return ring


def _default_lookup(name: str) -> Optional[dict]:
    """``{"id", "common_name"}`` for an exact common-name match, or None."""
    try:
        from src.db.plants import get_connection            # noqa: PLC0415
        conn = get_connection()
        try:
            row = conn.execute(
                "SELECT id, common_name FROM plants WHERE common_name = ?",
                (name,)).fetchone()
            return {"id": row["id"], "common_name": row["common_name"]} \
                if row else None
        finally:
            conn.close()
    except Exception:                                       # noqa: BLE001
        return None


def resolve_example_planting(lookup: Optional[Callable] = None
                             ) -> tuple[list, list[str]]:
    """Resolve the authored species names against the live catalogue.

    Returns ``(placements, missing)`` where each placement is
    ``{"plant_id", "common_name", "east_m", "north_m"}`` and ``missing`` names
    the entries no candidate satisfied — surfaced to the user rather than
    quietly producing a thinner design than the one described (P9).
    """
    lookup = lookup or _default_lookup
    placements, missing = [], []
    for candidates, (east, north) in EXAMPLE_PLANTING:
        for name in candidates:
            hit = lookup(name)
            if hit:
                placements.append({"plant_id": int(hit["id"]),
                                   "common_name": hit["common_name"],
                                   "east_m": east, "north_m": north})
                break
        else:
            missing.append(candidates[0])
    return placements, missing


def build_example_project(lat: Optional[float] = None,
                          lng: Optional[float] = None, *,
                          lookup: Optional[Callable] = None,
                          new_project: Optional[Callable] = None,
                          ) -> tuple[dict, list[str]]:
    """Build the worked example as a project dict, centred near ``(lat, lng)``.

    Returns ``(project, missing)``. Placed plants are written through
    :class:`src.project_store.ProjectStore` — the single write path — so the
    feature list and the placed index agree exactly as they would if the user
    had clicked each plant onto the map themselves.
    """
    from src.project_store import ProjectStore              # noqa: PLC0415
    if new_project is None:
        from src.project import new_project                 # noqa: PLC0415

    if lat is None or lng is None:
        lat, lng = EXAMPLE_DEFAULT_LATLNG
    # The given point is the centre of the plot; shift to its SW corner so the
    # example straddles the user's pin instead of hanging off it.
    sw_lat, sw_lng = _offset_latlng(lat, lng,
                                    -EXAMPLE_WIDTH_M / 2.0,
                                    -EXAMPLE_DEPTH_M / 2.0)

    project = new_project(EXAMPLE_NAME)
    props = project.setdefault("properties", {})
    props["notes"] = EXAMPLE_NOTES
    site_config = props.setdefault("site_config", {})
    site_config["latitude"] = round(lat, 7)
    site_config["longitude"] = round(lng, 7)
    site_config["pin_label"] = "Example site"
    site_config["priorities"] = list(FIRST_RUN_GOALS)

    project["features"].append({
        "type": "Feature",
        "geometry": {"type": "Polygon",
                     "coordinates": [example_boundary_ring(sw_lat, sw_lng)]},
        "properties": {"element_type": "property_boundary",
                       "boundary_id": "example_boundary",
                       "color": "#66bb6a",
                       "show_lengths": True, "show_area": True},
    })

    store = ProjectStore(project)
    placements, missing = resolve_example_planting(lookup)
    for p in placements:
        plat, plng = _offset_latlng(sw_lat, sw_lng, p["east_m"], p["north_m"])
        store.add_plant(p["plant_id"], p["common_name"],
                        round(plat, 7), round(plng, 7))
    return store.project, missing


def example_filename() -> str:
    """Filename the example is written under, so re-opening it overwrites the
    same file rather than accumulating copies."""
    return "example-front-yard-conversion.perma.geojson"
