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
        "short": "Find your yard",
        "title": "Find your yard",
        # V3.30 (WD-2): the words of 09-words.md §3.1.
        "detail": "Type your address, or click your yard on the map.",
    },
    {
        # V3.28 (PY-10): a bed is enough. The whole yard, or just the beds.
        "key": "boundary",
        "short": "Outline where to plant",
        "title": "Outline where to plant",
        "detail": "Click around your yard, or around one bed. Click the "
                  "first point again to finish.",
    },
    {
        "key": "plants",
        "short": "Plan it, or pick plants yourself",
        # V2.41 put the manual path first; V3.28 (PY-10) names both, the plan
        # first, because the strip's button is the plan.
        "title": "Plan it, or pick plants yourself",
        "detail": "Plan my yard suggests a planting you can change.",
    },
)


def _has_pin(project: dict) -> bool:
    sc = ((project or {}).get("properties") or {}).get("site_config") or {}
    return sc.get("latitude") is not None and sc.get("longitude") is not None


def _has_boundary(project: dict) -> bool:
    """An outline, or a bed (V3.28, PY-10): either is somewhere to plant."""
    from src.yard_overview import BED_SHAPES                 # noqa: PLC0415
    for f in (project or {}).get("features") or []:
        props = f.get("properties") or {}
        if props.get("element_type") == "property_boundary":
            return True
        if (props.get("element_type") == "custom_shape"
                and props.get("shape_type") in BED_SHAPES):
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
            "detail": "Design → Planted says what each plant feeds; "
                      "File → Export Planting Plan… says what to buy "
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

def _example() -> dict:
    """The default region pack's worked example (V3.24, ED-1:
    ``data/regions/<key>/region.json``, ``example``)."""
    from src import region                                   # noqa: PLC0415
    return region.default().example


def _example_place() -> str:
    from src import region                                   # noqa: PLC0415
    return region.default().short


EXAMPLE_NAME = _example()["name"]
EXAMPLE_WIDTH_M = float(_example()["width_m"])
EXAMPLE_DEPTH_M = float(_example()["depth_m"])

#: Where the example lands when the user has no pin of their own: the pack's
#: centre (central Edmonton, zone 3b/4a, the middle of this app's range).
EXAMPLE_DEFAULT_LATLNG = tuple(_example()["centre"])

#: An example made from a real lot (F254, V3.38, ``scripts/make_example.py``)
#: opens on that lot whatever the person's pin: its house and front walk are
#: that lot's, and drawn at someone else's pin they would sit on top of their
#: real house. The generic example, a bare rectangle, still follows the pin.
EXAMPLE_OWN_PLACE = bool(_example().get("own_place"))

#: ``(preferred name, fallback names…)`` → the builder takes the first that the
#: live catalogue actually has. Fallbacks exist because seed data changes;
#: a species that resolves to nothing is reported, never silently skipped.
#: Every species it can resolve to is native around the pack's place, where
#: the example lands (V3.18; ``tests/test_onboarding.py`` and
#: ``tests/test_region_packs.py`` hold it there): it had Canada Goldenrod and
#: Showy Milkweed, which the Edmonton list leaves off. Read from the pack since
#: V3.24: backbone shrubs at the back, the nectar relay in the middle, short
#: plants and the grass matrix at the front.
EXAMPLE_PLANTING: tuple[tuple[tuple[str, ...], tuple[float, float]], ...] = tuple(
    (tuple(names), (float(off[0]), float(off[1])))
    for names, off in _example()["planting"])

EXAMPLE_NOTES = (
    "This is a worked example, not a recommendation for your yard.\n\n"
    "It converts about 88 m² of front lawn into one bed: three "
    "fruiting/host shrubs for structure, a nectar relay that carries from "
    "spring (Golden Bean, Prairie Crocus) through midsummer (Wild Bergamot, "
    "Oval-leaf Milkweed) into fall (Stiff Goldenrod), and a short grass "
    "matrix along the street edge so it still reads as tended. Every plant "
    f"in it is native around {_example_place()}.\n\n"
    "Things worth doing to it, with View → Advanced tools on:\n"
    "  • Design → Habitat: see its score, then tick “Show the "
    "relationship web” to see which animals each plant feeds.\n"
    "  • Design → Habitat → Pull-a-plant: remove the "
    "milkweed and watch what it costs.\n"
    "  • View → 3D Preview: drag the year slider and watch the "
    "shrubs close over the forbs.\n"
    "  • File → Export Planting Plan…: what to buy, and when to plant it."
)


def example_notes(example: Optional[dict] = None) -> str:
    """Site › Notes for the example: the pack's own words when it has them
    (an example made from a design carries its design's notes, V3.38), else
    :data:`EXAMPLE_NOTES`, which describes the generic example's plants."""
    ex = example if example is not None else _example()
    return str(ex.get("notes") or "") or EXAMPLE_NOTES


def _offset_latlng(lat: float, lng: float,
                   east_m: float, north_m: float) -> tuple[float, float]:
    """Local-tangent offset — the app's one sanctioned metres↔lat/lng path."""
    m_lat, m_lng = metres_per_deg(lat)
    return (lat + north_m / m_lat, lng + east_m / m_lng)


def _ring_at(lat: float, lng: float, points) -> list:
    """Metre offsets from ``(lat, lng)`` as a closed GeoJSON ring."""
    ring = []
    for east, north in points:
        plat, plng = _offset_latlng(lat, lng, float(east), float(north))
        ring.append([round(plng, 7), round(plat, 7)])
    if ring and ring[0] != ring[-1]:
        ring.append(list(ring[0]))
    return ring


def example_boundary_ring(lat: float, lng: float, *,
                          outline=None, width_m: Optional[float] = None,
                          depth_m: Optional[float] = None) -> list:
    """The example plot as a closed GeoJSON ring ([lng, lat] order), with
    ``(lat, lng)`` as its south-west corner: the pack's ``outline`` when it
    has one (V3.38), else the width × depth rectangle."""
    if outline:
        return _ring_at(lat, lng, outline)
    w = EXAMPLE_WIDTH_M if width_m is None else float(width_m)
    d = EXAMPLE_DEPTH_M if depth_m is None else float(depth_m)
    return _ring_at(lat, lng, [(0.0, 0.0), (w, 0.0), (w, d), (0.0, d)])


def _shoelace_m2(points) -> float:
    pts = [(float(x), float(y)) for x, y in points]
    return abs(sum(x1 * y2 - x2 * y1 for (x1, y1), (x2, y2)
                   in zip(pts, pts[1:] + pts[:1]))) / 2.0


def example_features(sw_lat: float, sw_lng: float,
                     example: Optional[dict] = None) -> list:
    """The example's beds, paths, house, trees and structures (V3.38, F254)
    as design features, from the pack's metre offsets. Ids are made fresh, as
    a drawing would make them; nothing here is a plant."""
    from src import region                                   # noqa: PLC0415
    from src.db.structures import get_structure              # noqa: PLC0415
    ex = example if example is not None else _example()
    out = []
    for i, f in enumerate(ex.get("features") or []):
        kind = f["kind"]
        props = dict(f.get("props") or {})
        props["element_type"] = kind
        if kind in region.EXAMPLE_POLYGONS:
            ring = _ring_at(sw_lat, sw_lng, f["ring"])
            props["shape_id"] = f"shape_example_{i}"
            props["area_m2"] = round(_shoelace_m2(f["ring"]), 1)
            if kind == "canopy_footprint":
                from src.osm_features import ring_radius_m   # noqa: PLC0415
                props["canopy_radius_m"] = max(0.5, ring_radius_m(ring))
            geometry = {"type": "Polygon", "coordinates": [ring]}
        else:
            plat, plng = _offset_latlng(sw_lat, sw_lng, *map(float, f["at"]))
            geometry = {"type": "Point",
                        "coordinates": [round(plng, 7), round(plat, 7)]}
            if kind == "structure":
                sd = dict(get_structure(props.get("struct_id", "")) or
                          {"id": props.get("struct_id", ""),
                           "name": props.get("name", "")})
                if props.get("size_m"):
                    sd["size_m"] = props["size_m"]
                props["struct_def"] = sd
            else:
                props["struct_id"] = kind
                props["source"] = "example"
        out.append({"type": "Feature", "geometry": geometry,
                    "properties": props})
    return out


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


def _planting(example: dict) -> tuple:
    return tuple((tuple(names), (float(off[0]), float(off[1])))
                 for names, off in example["planting"])


def resolve_example_planting(lookup: Optional[Callable] = None, *,
                             planting=None) -> tuple[list, list[str]]:
    """Resolve the authored species names against the live catalogue.

    Returns ``(placements, missing)`` where each placement is
    ``{"plant_id", "common_name", "east_m", "north_m"}`` and ``missing`` names
    the entries no candidate satisfied — surfaced to the user rather than
    quietly producing a thinner design than the one described (P9).
    ``planting`` defaults to the pack's (:data:`EXAMPLE_PLANTING`).
    """
    lookup = lookup or _default_lookup
    placements, missing = [], []
    for candidates, (east, north) in (EXAMPLE_PLANTING if planting is None
                                      else planting):
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
                          example: Optional[dict] = None,
                          ) -> tuple[dict, list[str]]:
    """Build the worked example as a project dict, centred near ``(lat, lng)``.

    Returns ``(project, missing)``. Placed plants are written through
    :class:`src.project_store.ProjectStore` — the single write path — so the
    feature list and the placed index agree exactly as they would if the user
    had clicked each plant onto the map themselves. ``example`` is a pack's
    ``example`` block (the default pack's when omitted; tests and
    ``scripts/make_example.py`` pass their own).
    """
    from src.project_store import ProjectStore              # noqa: PLC0415
    if new_project is None:
        from src.project import new_project                 # noqa: PLC0415
    ex = example if example is not None else _example()
    width, depth = float(ex["width_m"]), float(ex["depth_m"])

    if lat is None or lng is None:
        lat, lng = (float(c) for c in ex["centre"])
    # The given point is the centre of the plot; shift to its SW corner so the
    # example straddles the user's pin instead of hanging off it.
    sw_lat, sw_lng = _offset_latlng(lat, lng, -width / 2.0, -depth / 2.0)

    project = new_project(ex["name"])
    props = project.setdefault("properties", {})
    props["notes"] = example_notes(ex)
    site_config = props.setdefault("site_config", {})
    site_config["latitude"] = round(lat, 7)
    site_config["longitude"] = round(lng, 7)
    site_config["pin_label"] = "Example site"
    site_config["priorities"] = list(FIRST_RUN_GOALS)

    ring = example_boundary_ring(sw_lat, sw_lng, outline=ex.get("outline"),
                                 width_m=width, depth_m=depth)
    project["features"].append({
        "type": "Feature",
        "geometry": {"type": "Polygon", "coordinates": [ring]},
        "properties": {"element_type": "property_boundary",
                       "boundary_id": "example_boundary",
                       "color": "#66bb6a",
                       "show_lengths": True, "show_area": True},
    })
    project["features"].extend(example_features(sw_lat, sw_lng, ex))

    store = ProjectStore(project)
    placements, missing = resolve_example_planting(
        lookup, planting=_planting(ex))
    for p in placements:
        plat, plng = _offset_latlng(sw_lat, sw_lng, p["east_m"], p["north_m"])
        store.add_plant(p["plant_id"], p["common_name"],
                        round(plat, 7), round(plng, 7))
    return store.project, missing


def example_filename() -> str:
    """Filename the example is written under, so re-opening it overwrites the
    same file rather than accumulating copies."""
    return "example-front-yard-conversion.perma.geojson"
