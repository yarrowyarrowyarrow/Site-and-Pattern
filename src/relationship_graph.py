"""
relationship_graph.py — the design drawn as a living network (F5).

Design principle P3 (relationships matter more than components), P10 (plants are
nodes in a network) and P5 (perception is constructed — make the invisible
ecology *visible*) — see docs/DESIGN_PHILOSOPHY.md.

The map shows a design as dots on grass. What the design actually *is* — the
thing the Habitat Value Score is a single number for — is a web: this shrub
hosts those caterpillars, which those birds eat; these two forbs feed the same
solitary bee; that pair shares a community. This module turns the unified edges
layer (:mod:`src.db.relationships`, F7) into a drawable graph laid over the real
map, so the relationships appear *where the plants are*.

Two deliberate choices about what a node is:

  * **One node per species, not per placement.** Forty bergamots and one bee
    would draw forty identical lines to the same animal — a hairball that hides
    the very structure it is meant to reveal. The species node sits at the
    centroid of its placements and carries its count, so the picture stays the
    graph and the map underneath stays the planting.
  * **Animals ring the design.** Fauna have no coordinates — inventing a spot in
    the yard for a bumble bee would be false precision (P9). Each animal is
    placed on a ring just outside the planting, on the bearing of the plants
    that support it, so its lines converge naturally on its own hosts. The ring
    is a diagram, and the legend says so.

All geometry is computed here in metres and converted once to lat/lng, keeping
the map JS a thin renderer (the map-JS line ceiling is real — see
tests/test_architecture_guard.py).

Qt-free, dependency-injectable, JSON-serialisable.
"""

from __future__ import annotations

import math
from typing import Callable, Iterable, Optional

from src.projection import metres_per_deg

#: Kinds shown when the caller does not narrow the view. Companion and
#: co-planted edges are off by default: they are horticultural bookkeeping and
#: they dominate the picture by sheer count, drowning the food web that is the
#: point of the overlay. The filter row turns them on.
DEFAULT_KINDS: tuple[str, ...] = (
    "larval_host", "nectar", "pollen", "fruit_food", "seed_food",
    "nesting", "cover",
)

#: How many animal nodes to draw before the picture stops being readable. The
#: overlay reports what it dropped rather than silently thinning (P9).
MAX_FAUNA_NODES = 60

#: Ring geometry, in metres.
_RING_MARGIN_M = 8.0        # clearance between the planting and the ring
_RING_MIN_RADIUS_M = 12.0   # so a two-plant design still has a legible ring

#: Chips carry a species name, so they need real angular room. A single ring
#: therefore holds only so many before the labels overlap — past that the
#: animals spill onto further rings ("lanes") outward. Round-robin assignment
#: puts neighbouring bearings in *different* lanes, which is what actually
#: separates them; a second ring alone would just re-create the pile-up.
_MIN_ANGULAR_GAP_DEG = 13.0
_LANE_CAPACITY = max(1, int(360.0 // _MIN_ANGULAR_GAP_DEG))
_LANE_STEP_M = 9.0          # radial spacing between lanes
_MAX_LANES = 4              # beyond this the web is unreadable at any spacing

_TAXON_MARK = {
    "bee": "🐝", "lepidoptera": "🦋", "bird": "🐦",
    "other_insect": "🪲", "mammal": "🐿",
}


# ── Geometry helpers ──────────────────────────────────────────────────────────

def _centroid(points: list) -> tuple[float, float]:
    return (sum(p[0] for p in points) / len(points),
            sum(p[1] for p in points) / len(points))


def _offset(lat: float, lng: float, bearing_deg: float,
            distance_m: float) -> tuple[float, float]:
    """A point ``distance_m`` from ``(lat, lng)`` on a compass bearing.

    Local-tangent maths via :func:`src.projection.metres_per_deg` — the app's
    one sanctioned lat/lng↔metres path (see docs / the geo-projection skill).
    At ring scale (tens of metres) this is exact to centimetres.
    """
    m_lat, m_lng = metres_per_deg(lat)
    rad = math.radians(bearing_deg)
    return (lat + (distance_m * math.cos(rad)) / m_lat,
            lng + (distance_m * math.sin(rad)) / m_lng)


def _bearing(from_lat: float, from_lng: float,
             to_lat: float, to_lng: float) -> float:
    """Compass bearing (0–360, 0 = north) on the same local tangent plane."""
    m_lat, m_lng = metres_per_deg(from_lat)
    north = (to_lat - from_lat) * m_lat
    east = (to_lng - from_lng) * m_lng
    if abs(north) < 1e-9 and abs(east) < 1e-9:
        return 0.0
    return math.degrees(math.atan2(east, north)) % 360.0


def _mean_bearing(bearings: list) -> float:
    """Circular mean — the average of 350° and 10° is 0°, not 180°."""
    if not bearings:
        return 0.0
    x = sum(math.cos(math.radians(b)) for b in bearings)
    y = sum(math.sin(math.radians(b)) for b in bearings)
    if abs(x) < 1e-12 and abs(y) < 1e-12:
        return 0.0
    return math.degrees(math.atan2(y, x)) % 360.0


def _assign_lanes(bearing_pairs: list,
                  capacity: int = _LANE_CAPACITY,
                  max_lanes: int = _MAX_LANES) -> list:
    """Lay ``[(id, bearing), …]`` out as ``[(id, angle, lane), …]``.

    One ring holds ``capacity`` labelled chips before they collide. Past that,
    animals spill onto further rings — and they are dealt **round-robin by
    bearing order**, so two animals with nearly the same bearing land on
    *different* rings. Dealing them in contiguous blocks instead would just
    rebuild the same pile-up one ring further out.

    Within each lane the angles are spread to the minimum gap, so a lane that
    happens to be lightly loaded still reads cleanly.
    """
    if not bearing_pairs:
        return []
    lanes = min(max_lanes,
                max(1, -(-len(bearing_pairs) // max(1, capacity))))
    buckets: list = [[] for _ in range(lanes)]
    for i, pair in enumerate(bearing_pairs):
        buckets[i % lanes].append(pair)

    out = []
    for lane, bucket in enumerate(buckets):
        bucket.sort(key=lambda pair: pair[1])   # _spread_angles sorts too
        spread = _spread_angles([b for _, b in bucket])
        for (fid, _), angle in zip(bucket, spread):
            out.append((fid, angle, lane))
    return out


def _spread_angles(angles: list, min_gap: float = _MIN_ANGULAR_GAP_DEG) -> list:
    """Push near-coincident ring angles apart, preserving order.

    Animals that share the same hosts land on the same bearing; without this
    their labels stack into an unreadable pile. One forward pass around the
    circle, then a wrap check so the last entry cannot collide with the first.
    """
    n = len(angles)
    if n < 2:
        return list(angles)
    if min_gap * n >= 360.0:                    # ring is full — spread evenly
        start = angles[0]
        return [(start + i * (360.0 / n)) % 360.0 for i in range(n)]
    out = sorted(angles)
    for i in range(1, n):
        if out[i] - out[i - 1] < min_gap:
            out[i] = out[i - 1] + min_gap
    overflow = (out[0] + 360.0) - out[-1]
    if overflow < min_gap:
        shift = (min_gap - overflow) / 2.0
        out = [a - shift for a in out]
    return [a % 360.0 for a in out]


# ── The graph ─────────────────────────────────────────────────────────────────

def build_relationship_graph(placed_plants: list, *,
                             kinds: Optional[Iterable[str]] = None,
                             max_fauna: int = MAX_FAUNA_NODES,
                             edges_provider: Optional[Callable] = None,
                             fauna_lookup: Optional[Callable] = None) -> dict:
    """Build the drawable relationship web for a design.

    ``placed_plants`` are the app's placed-plant records (``plant_id``, ``lat``,
    ``lng``, ``common_name``). Returns a JSON-serialisable payload::

        {"nodes": [...], "edges": [...], "legend": [...], "stats": {...},
         "ring": {"lat":…, "lng":…, "radius_m":…, "lanes": n,
                  "lane_step_m": …}}

    Plant nodes carry their real position; fauna nodes carry a ring position and
    ``on_ring: True`` so the renderer (and the legend) can say plainly that the
    animal's spot is a diagram, not a location.
    """
    if edges_provider is None:
        from src.db.relationships import edges_among as edges_provider  # noqa: PLC0415
    from src.db.relationships import EDGE_KINDS                          # noqa: PLC0415

    wanted = tuple(kinds) if kinds is not None else DEFAULT_KINDS
    wanted = tuple(k for k in wanted if k in EDGE_KINDS)

    # ── Species nodes at the centroid of their placements ────────────────────
    by_species: dict = {}
    for p in placed_plants or []:
        try:
            pid = int(p.get("plant_id"))
            lat, lng = float(p.get("lat")), float(p.get("lng"))
        except (TypeError, ValueError):
            continue
        rec = by_species.setdefault(
            pid, {"points": [], "name": p.get("common_name") or "",
                  "plant_type": p.get("plant_type") or ""})
        rec["points"].append((lat, lng))
        if not rec["name"]:
            rec["name"] = p.get("common_name") or ""

    if not by_species or not wanted:
        return _empty(wanted)

    plant_nodes: dict = {}
    for pid, rec in by_species.items():
        lat, lng = _centroid(rec["points"])
        plant_nodes[pid] = {
            "id": f"p{pid}", "type": "plant", "plant_id": pid,
            "label": rec["name"], "plant_type": rec["plant_type"],
            "lat": round(lat, 7), "lng": round(lng, 7),
            "count": len(rec["points"]), "degree": 0, "on_ring": False,
        }

    edges = list(edges_provider(sorted(plant_nodes), kinds=wanted))

    # ── Fauna nodes, ranked by how much of THIS design they touch ────────────
    fauna_ids = sorted({e.b_id for e in edges if e.b_type == "fauna"})
    fauna_rows = (fauna_lookup or _default_fauna)(fauna_ids) if fauna_ids else {}

    supporters: dict = {}
    specialist_for: dict = {}
    for e in edges:
        if e.b_type != "fauna":
            continue
        supporters.setdefault(e.b_id, set()).add(e.a_id)
        if e.detail == "specialist":
            specialist_for[e.b_id] = True

    # A specialist supported by one plant is the most important thing on the
    # map — rank it above a generalist with many hosts, and never let the cap
    # drop it (that is precisely the edge the overlay exists to reveal).
    def _rank(fid: int) -> tuple:
        return (0 if specialist_for.get(fid) else 1,
                -len(supporters.get(fid, ())),
                fauna_rows.get(fid, {}).get("common_name", ""))

    ranked = sorted(supporters, key=_rank)
    kept = set(ranked[:max(0, int(max_fauna))])
    dropped = len(ranked) - len(kept)

    # ── Place the kept animals on a ring outside the planting ────────────────
    pts = [(n["lat"], n["lng"]) for n in plant_nodes.values()]
    c_lat, c_lng = _centroid(pts)
    m_lat, m_lng = metres_per_deg(c_lat)
    extent = max(
        (math.hypot((lat - c_lat) * m_lat, (lng - c_lng) * m_lng)
         for lat, lng in pts),
        default=0.0)
    radius = max(_RING_MIN_RADIUS_M, extent + _RING_MARGIN_M)

    raw = []
    for fid in ranked:
        if fid not in kept:
            continue
        bearings = [_bearing(c_lat, c_lng,
                             plant_nodes[pid]["lat"], plant_nodes[pid]["lng"])
                    for pid in sorted(supporters[fid]) if pid in plant_nodes]
        raw.append((fid, _mean_bearing(bearings)))
    raw.sort(key=lambda pair: pair[1])
    placements = _assign_lanes(raw)

    fauna_nodes: dict = {}
    for fid, angle, lane in placements:
        row = fauna_rows.get(fid, {})
        lat, lng = _offset(c_lat, c_lng, angle, radius + lane * _LANE_STEP_M)
        taxon = row.get("taxon") or ""
        fauna_nodes[fid] = {
            "id": f"f{fid}", "type": "fauna", "fauna_id": fid,
            "label": row.get("common_name") or f"species {fid}",
            "scientific_name": row.get("scientific_name") or "",
            "taxon": taxon, "mark": _TAXON_MARK.get(taxon, "•"),
            "lat": round(lat, 7), "lng": round(lng, 7),
            # Which side of the ring the chip hangs off, so the label reads
            # outward instead of straddling the lines converging on it.
            "anchor": "left" if 180.0 < angle < 360.0 else "right",
            "lane": lane,
            "count": len(supporters.get(fid, ())),
            "degree": 0, "on_ring": True,
            "specialist": bool(specialist_for.get(fid)),
            # V2.42: the plants in THIS design that support this animal, by
            # name. The overlay could previously only be read by tracing lines
            # by eye — there was no way to click a chip and ask "supported by
            # what?", which is the first question the picture provokes.
            "supported_by": sorted(
                plant_nodes[pid]["label"]
                for pid in supporters.get(fid, ()) if pid in plant_nodes),
            # The single fact that makes an edge urgent: pull this plant and
            # this animal loses everything it has here (P3, and the same
            # reading src/plant_impact.py gives the user in words).
            "only_source": len(supporters.get(fid, ())) == 1,
            # Sixty named chips is not a picture, it is a wall of text — so
            # only the animals whose story the overlay exists to tell wear
            # their name unprompted. The rest are marks that name themselves
            # on hover: nothing is hidden, but the eye is given somewhere to
            # land.
            "named": bool(specialist_for.get(fid)),
        }

    # ── Edges, resolved to node ids ──────────────────────────────────────────
    out_edges = []
    for e in edges:
        a = plant_nodes.get(e.a_id)
        if a is None:
            continue
        if e.b_type == "fauna":
            b = fauna_nodes.get(e.b_id)
        else:
            b = plant_nodes.get(e.b_id)
        if b is None:
            continue
        meta = EDGE_KINDS[e.kind]
        a["degree"] += 1
        b["degree"] += 1
        # V2.42: what a plant does, in words, for the click-through panel —
        # "nectar for Painted Lady" rather than a line the reader has to trace.
        if e.b_type == "fauna":
            a.setdefault("supports", []).append(
                {"name": b["label"], "how": meta.phrase, "mark": b.get("mark", "•"),
                 "specialist": e.detail == "specialist",
                 "evidence": e.evidence})
        out_edges.append({
            "a": a["id"], "b": b["id"], "kind": e.kind,
            "label": meta.label, "phrase": meta.phrase,
            "color": meta.color, "group": meta.group,
            "strength": round(e.strength, 3),
            "evidence": e.evidence,
            "detail": e.detail,
            "specialist": e.detail == "specialist",
            "a_lat": a["lat"], "a_lng": a["lng"],
            "b_lat": b["lat"], "b_lng": b["lng"],
        })

    nodes = list(plant_nodes.values()) + list(fauna_nodes.values())
    lanes = 1 + max((p[2] for p in placements), default=0)
    return {
        "nodes": nodes,
        "edges": out_edges,
        "legend": _legend(out_edges, EDGE_KINDS),
        "taxon_key": _taxon_key(fauna_nodes),
        "ring": {"lat": round(c_lat, 7), "lng": round(c_lng, 7),
                 "radius_m": round(radius, 2),
                 "lanes": lanes, "lane_step_m": _LANE_STEP_M},
        "stats": _stats(plant_nodes, fauna_nodes, out_edges, dropped, wanted),
    }


#: What each ring mark means, in words. The overlay draws animals as emoji and
#: names only the specialists, so most of the ring is unlabelled marks — which
#: is fine as a density decision and useless without a key. There wasn't one:
#: the legend explained the *line* colours and left the reader to guess whether
#: 🪲 meant a beetle or "other". Reported by the first user to open the overlay.
_TAXON_LABEL = {
    "bee": "bees", "lepidoptera": "butterflies & moths", "bird": "birds",
    "other_insect": "other insects", "mammal": "mammals",
}


def _taxon_key(fauna_nodes: dict) -> list:
    """The mark → meaning key, for the taxa this design actually draws.

    Same rule as :func:`_legend`: only what is on screen. A key naming mammals
    when no mammal is drawn sends the reader hunting for one.
    """
    counts: dict = {}
    for n in fauna_nodes.values():
        counts.setdefault((n.get("mark") or "•", n.get("taxon") or ""),
                          []).append(n)
    out = []
    for (mark, taxon), group in counts.items():
        out.append({
            "mark": mark,
            "taxon": taxon,
            "label": _TAXON_LABEL.get(taxon, taxon or "other"),
            "count": len(group),
        })
    return sorted(out, key=lambda r: (-r["count"], r["label"]))


def _legend(edges: list, kind_meta: dict) -> list:
    """Only the kinds actually drawn — a legend naming relationships this design
    does not have teaches the wrong lesson."""
    counts: dict = {}
    for e in edges:
        counts[e["kind"]] = counts.get(e["kind"], 0) + 1
    return [{"kind": k, "label": kind_meta[k].label,
             "color": kind_meta[k].color, "count": counts[k]}
            for k in sorted(counts, key=lambda k: -kind_meta[k].weight)]


def _stats(plant_nodes: dict, fauna_nodes: dict, edges: list,
           dropped: int, kinds: tuple) -> dict:
    """Headline numbers, plus the honest note about what was left out."""
    specialists = sum(1 for n in fauna_nodes.values() if n["specialist"])
    only = sum(1 for n in fauna_nodes.values() if n["only_source"])
    isolated = sorted(n["label"] for n in plant_nodes.values()
                      if n["degree"] == 0 and n["label"])
    return {
        "species": len(plant_nodes),
        "wildlife": len(fauna_nodes),
        "edges": len(edges),
        "specialists": specialists,
        "single_support": only,
        "isolated": isolated,
        "dropped_fauna": dropped,
        "kinds": list(kinds),
        "derived_edges": sum(1 for e in edges if e["evidence"] == "derived"),
        # V2.42: `evidence` gained a third state, so "not derived" stopped
        # meaning "documented". These are counted rather than subtracted.
        "documented_edges": sum(
            1 for e in edges if e["evidence"] == "documented"),
        "recorded_edges": sum(1 for e in edges if e["evidence"] == "recorded"),
    }


def _empty(kinds: tuple) -> dict:
    return {"nodes": [], "edges": [], "legend": [],
            "ring": {"lat": 0.0, "lng": 0.0, "radius_m": 0.0,
                     "lanes": 0, "lane_step_m": _LANE_STEP_M},
            "stats": {"species": 0, "wildlife": 0, "edges": 0,
                      "specialists": 0, "single_support": 0, "isolated": [],
                      "dropped_fauna": 0, "kinds": list(kinds),
                      "derived_edges": 0}}


def _default_fauna(fauna_ids: list) -> dict:
    """``{fauna_id: row}`` for the animals on the graph — one query."""
    if not fauna_ids:
        return {}
    try:
        from src.db.plants import get_connection          # noqa: PLC0415
        conn = get_connection()
        try:
            ph = ",".join("?" * len(fauna_ids))
            return {r["id"]: dict(r) for r in conn.execute(
                f"SELECT id, common_name, scientific_name, taxon FROM fauna "
                f"WHERE id IN ({ph})", list(fauna_ids))}
        finally:
            conn.close()
    except Exception:                                     # noqa: BLE001
        return {}


def summary_lines(graph: dict) -> list[str]:
    """Plain-language read-out of a graph, for the panel and the scripting API.

    Says what the picture says, including what it is *not* showing — a graph
    that quietly dropped forty animals is a lie told by omission (P9).
    """
    s = graph.get("stats") or {}
    if not s.get("species"):
        return ["Place some plants to see the design's relationship web."]
    # V2.42: this used to be `edges - derived_edges`, which was right while
    # `evidence` had two states and became an overstatement the moment it had
    # three — companion pairings ship uncited and would have been counted as
    # documented records. Count the state, don't infer it by subtraction.
    documented = s.get("documented_edges",
                       s["edges"] - s.get("derived_edges", 0))
    lines = [
        f"{s['species']} species · {s['wildlife']} wildlife species · "
        f"{documented} documented relationship"
        f"{'' if documented == 1 else 's'}"
    ]
    if s.get("recorded_edges"):
        lines.append(
            f"{s['recorded_edges']} further link"
            f"{'' if s['recorded_edges'] == 1 else 's'} are recorded in the "
            f"catalogue but carry no citation — mostly companion pairings")
    if s.get("specialists"):
        lines.append(
            f"{s['specialists']} specialist"
            f"{'s' if s['specialists'] != 1 else ''} — animals with nowhere "
            f"else to go if their host leaves")
    if s.get("single_support"):
        one = s["single_support"] == 1
        lines.append(
            f"{s['single_support']} wildlife species {'is' if one else 'are'} "
            f"held up by a single plant in this design")
    if s.get("derived_edges"):
        # Was "plant-to-plant links (two plants feeding the same animal)", which
        # described shared_fauna — the only derived kind until V2.42. Derived
        # now also covers genus-level host records expanded onto this species,
        # so the wording can no longer name one mechanism.
        lines.append(
            f"{s['derived_edges']} inferred link"
            f"{'' if s['derived_edges'] == 1 else 's'} — shown dashed. Either "
            f"two plants feeding the same animal, or a host record published "
            f"for the genus rather than this species. Not documented records.")
    if s.get("isolated"):
        shown = ", ".join(s["isolated"][:4])
        more = f" +{len(s['isolated']) - 4} more" if len(s["isolated"]) > 4 else ""
        lines.append(f"No recorded relationships yet: {shown}{more}")
    if s.get("dropped_fauna"):
        one = s["dropped_fauna"] == 1
        lines.append(
            f"{s['dropped_fauna']} further wildlife species "
            f"{'is' if one else 'are'} supported but not drawn — the web "
            f"would stop being readable")
    return lines
