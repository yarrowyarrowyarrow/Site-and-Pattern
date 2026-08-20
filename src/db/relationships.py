"""
relationships.py — the unified edges layer (F7, schema v51).

Design principle P3 (relationships matter more than components — the edge
between species is the unit of value) and P10 (design for relationships, not
objects — plants are nodes in a network) — see docs/DESIGN_PHILOSOPHY.md.

The ecology in this app has always been edges, stored in four unrelated shapes:

  * ``plant_fauna``       — who eats, hosts, nests in or shelters at a plant
  * ``companion_friends`` — horticultural affinity
  * ``companion_enemies`` — horticultural antagonism
  * ``polyculture_members`` — plants an author put in the same community

Every consumer that wanted the whole picture had to know all four and join them
by hand: ``habitat_score`` reads one, ``placement_score.build_companion_graph``
reads two, ``scene_dossier`` reads a third. This module is the single query API
over all of them — the roadmap's "show me everything connected to this plant".

The union itself is the ``relationship_edges`` SQL view in ``schema.sql``; the
per-relationship tables stay the source of truth, so there is no second copy to
drift out of date and nothing new for the reseed to wipe.

Honesty rules (P9):

  * Every edge carries ``evidence``, in three states since V2.42:

      ``documented`` — a seeded record that carries a citable ``source``
      ``recorded``   — a seeded record with no citation. An authored fact about
                       this catalogue, not a sourced one. Companion pairings and
                       community co-membership live here.
      ``derived``    — computed rather than read: this module's ``shared_fauna``
                       edges, and the genus-level expansions in
                       ``src.db.derived_edges``.

    Before V2.42 there were two states and ``documented`` was *hardcoded* for
    everything the SQL view produced, so an uncited companion pairing made
    exactly the same provenance claim as a cited larval-host record. The view
    computes it now, per source table.
  * ``strength`` is a coarse 0–1 weight for drawing and ranking, never a claim
    of measured interaction rate. The kind's own semantics dominate: a
    specialist's larval host outranks a generalist's nectar stop because the
    specialist has nowhere else to go, and that is a fact about the record.
    Derived edges are discounted by confidence band so they can never out-rank
    a documented edge of the same kind.
  * **Nothing is inferred from taxonomy** — no "plants like this usually…".
    V2.42 did not relax this. Expanding a published *genus-level* host record
    onto that genus's members restates a claim at the resolution its source
    made it; inventing genus-level scope for a record about a single species
    would be the thing this rule forbids, and is why congeneric transfer is
    measured but not implemented (see ``src/db/derived_edges.py``).

Qt-free, connection-injectable, JSON-serialisable.
"""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass, asdict
from typing import Callable, Iterable, Optional

# ── The edge vocabulary ───────────────────────────────────────────────────────
# One registry so a legend, a filter checkbox, a tooltip and a graph edge all
# read the same words. `weight` is the default strength for the kind; `phrase`
# reads from a → b (the plant's side, matching src/scene_dossier.py).


@dataclass(frozen=True)
class EdgeKind:
    kind: str
    label: str          # short UI label ("Caterpillar host")
    phrase: str         # how the edge reads a → b ("caterpillar host for")
    group: str          # 'trophic' | 'shelter' | 'companion' | 'community'
    b_type: str         # what sits on the far end
    weight: float       # default strength 0–1
    color: str          # legend / overlay colour


_KINDS: tuple[EdgeKind, ...] = (
    # Trophic — the food web. Larval host leads: it is the link Tallamy's
    # whole argument turns on, and the one a design most often misses.
    # Base weights leave room below 1.0 for the specialist bonus — a specialist
    # larval-host edge is the strongest thing this data can say, so it must be
    # able to outrank a generalist one on the same kind.
    EdgeKind("larval_host", "Caterpillar host", "caterpillar host for",
             "trophic", "fauna", 0.85, "#8bc34a"),
    EdgeKind("nectar", "Nectar", "nectar for",
             "trophic", "fauna", 0.70, "#ffb300"),
    EdgeKind("pollen", "Pollen", "pollen for",
             "trophic", "fauna", 0.70, "#ffd54f"),
    EdgeKind("fruit_food", "Fruit", "fruit for",
             "trophic", "fauna", 0.75, "#ef5350"),
    EdgeKind("seed_food", "Seed", "seed for",
             "trophic", "fauna", 0.65, "#bcaaa4"),
    # Shelter — the half of habitat that is not food.
    EdgeKind("nesting", "Nest site", "nest site for",
             "shelter", "fauna", 0.80, "#4dd0e1"),
    EdgeKind("cover", "Cover", "cover for",
             "shelter", "fauna", 0.55, "#4db6ac"),
    # Plant ↔ plant.
    EdgeKind("companion_friend", "Good together", "grows well with",
             "companion", "plant", 0.50, "#66bb6a"),
    EdgeKind("companion_enemy", "Keep apart", "does poorly beside",
             "companion", "plant", 0.50, "#e57373"),
    EdgeKind("co_planted", "Same community", "shares a community with",
             "community", "plant", 0.35, "#9575cd"),
    # Derived (computed here, never stored) — the second-order edge that only
    # a unified layer can see: two plants tied together by an animal they both
    # support. This is the food web's actual topology, and it is what makes a
    # design a network rather than a list.
    EdgeKind("shared_fauna", "Feeds the same wildlife", "shares wildlife with",
             "derived", "plant", 0.30, "#4fc3f7"),
)

EDGE_KINDS: dict[str, EdgeKind] = {k.kind: k for k in _KINDS}

#: Kinds sourced from seeded records (the SQL view).
DOCUMENTED_KINDS: tuple[str, ...] = tuple(
    k.kind for k in _KINDS if k.kind != "shared_fauna")
#: Kinds this module computes rather than reads.
DERIVED_KINDS: tuple[str, ...] = ("shared_fauna",)


def edge_kinds(group: str = "") -> list[dict]:
    """The edge vocabulary as plain dicts — for legends, filter rows and the
    scripting API. Optionally narrowed to one ``group``."""
    return [asdict(k) for k in _KINDS if not group or k.group == group]


# ── The edge record ───────────────────────────────────────────────────────────

@dataclass(frozen=True)
class Edge:
    """One relationship. ``a`` is always a plant; ``b`` is a plant or a fauna
    row depending on the kind."""
    kind: str
    a_id: int
    b_type: str            # 'plant' | 'fauna'
    b_id: int
    directed: bool         # True for plant → fauna ("nectar for")
    strength: float        # 0–1, coarse weight for drawing/ranking
    evidence: str          # 'documented' | 'recorded' | 'derived'
    detail: str = ""       # 'specialist' / a community name / a shared species
    source: str = ""       # citation for documented edges
    confidence: str = ""   # derived edges only: 'high' | 'moderate' | 'low'

    @property
    def a_type(self) -> str:
        return "plant"

    def as_dict(self) -> dict:
        d = asdict(self)
        d["a_type"] = "plant"
        return d

    def other(self, plant_id: int) -> tuple[str, int]:
        """The far end of the edge as seen from ``plant_id``."""
        if self.b_type == "plant" and self.b_id == plant_id:
            return ("plant", self.a_id)
        return (self.b_type, self.b_id)


# ── Connection plumbing ───────────────────────────────────────────────────────

def _default_connect() -> sqlite3.Connection:
    from src.db.plants import get_connection      # noqa: PLC0415
    return get_connection()


def _rows(connect: Optional[Callable], sql: str, params: Iterable) -> list[dict]:
    conn = (connect or _default_connect)()
    try:
        return [dict(r) for r in conn.execute(sql, list(params)).fetchall()]
    finally:
        conn.close()


def _specialist_strength(kind: str, detail: str) -> float:
    """A specialist edge is the strongest thing the data can say: the animal has
    nowhere else to go, so losing the plant loses the animal."""
    base = EDGE_KINDS[kind].weight if kind in EDGE_KINDS else 0.5
    if detail == "specialist":
        return min(1.0, base + 0.25)
    return base


#: How far a derived edge is discounted against a documented one of the same
#: kind. A derived edge restates a genus-level record at the resolution it was
#: published (see src/db/derived_edges.py); it is real, but it is not a record
#: about *this species*, and it must never out-draw or out-rank one that is.
_DERIVED_DISCOUNT: dict[str, float] = {
    "high": 0.60,
    "moderate": 0.45,
    "low": 0.30,
}


def _derived_strength(base: float, confidence: str) -> float:
    """Discount a derived edge by its confidence band.

    Deliberately multiplicative rather than a flat subtraction: the kind's own
    semantics still dominate (a derived pollen edge should still outweigh a
    derived cover edge), while the whole derived population sits below the
    documented one. P9 — the ordering is the claim, the number is not.
    """
    return round(base * _DERIVED_DISCOUNT.get(confidence, 0.30), 4)


def _edge_from_row(row: dict) -> Optional[Edge]:
    kind = row.get("kind") or ""
    if kind not in EDGE_KINDS:
        return None                     # unknown vocabulary — never guess
    detail = row.get("detail") or ""
    # V2.42: `evidence` is computed by the `relationship_edges` view, not assumed
    # here. It used to be hardcoded to 'documented' for every row this function
    # saw, which meant a cited plant_fauna record and an uncited companion
    # pairing made the same provenance claim — on the app's most folklore-prone
    # data. The view now distinguishes documented / recorded / derived; the
    # fallback below only applies to a caller passing a hand-built row.
    # A row from the view carries `evidence`. A hand-built row (tests, callers
    # constructing edges directly) does not, so fall back to the SAME rule the
    # view applies rather than a blind default: a citation makes it documented.
    evidence = row.get("evidence") or (
        "documented" if (row.get("source") or "").strip() else "recorded")
    confidence = row.get("confidence") or ""
    strength = _specialist_strength(kind, detail)
    if evidence == "derived":
        strength = _derived_strength(strength, confidence)
    return Edge(
        kind=kind,
        a_id=int(row["a_id"]),
        b_type=row.get("b_type") or "plant",
        b_id=int(row["b_id"]),
        directed=bool(row.get("directed")),
        strength=strength,
        evidence=evidence,
        detail=detail,
        source=row.get("source") or "",
        confidence=confidence,
    )


# ── Queries ───────────────────────────────────────────────────────────────────

def edges_among(plant_ids: Iterable[int], *,
                kinds: Optional[Iterable[str]] = None,
                include_derived: bool = True,
                connect: Optional[Callable] = None) -> list[Edge]:
    """Every relationship *inside* a set of plants — the design's own network.

    Plant↔plant edges are kept only when BOTH ends are in ``plant_ids``: a
    companion pairing with a plant you did not place is not part of this design.
    Plant→fauna edges are kept whenever their plant is present; the animal is
    the far end by definition.

    One query for the documented kinds regardless of design size, plus one
    grouping pass for the derived ones.
    """
    pids = sorted({int(p) for p in plant_ids})
    if not pids:
        return []
    wanted = set(kinds) if kinds is not None else set(EDGE_KINDS)
    doc_wanted = sorted(wanted & set(DOCUMENTED_KINDS))

    edges: list[Edge] = []
    if doc_wanted:
        ph = ",".join("?" * len(pids))
        kph = ",".join("?" * len(doc_wanted))
        try:
            rows = _rows(
                connect,
                f"""SELECT kind, a_id, b_type, b_id, directed, detail, source,
                       evidence, confidence
                      FROM relationship_edges
                     WHERE kind IN ({kph})
                       AND (a_id IN ({ph}) OR (b_type = 'plant'
                                               AND b_id IN ({ph})))""",
                doc_wanted + pids + pids,
            )
        except Exception:                       # noqa: BLE001 — best-effort
            rows = []
        present = set(pids)
        for row in rows:
            edge = _edge_from_row(row)
            if edge is None:
                continue
            if edge.b_type == "plant":
                if edge.a_id not in present or edge.b_id not in present:
                    continue
                if edge.a_id == edge.b_id:
                    continue
            elif edge.a_id not in present:
                continue
            edges.append(edge)
        edges = _dedupe(edges)
        if "co_planted" in wanted:
            _name_communities(edges, connect)

    if include_derived and "shared_fauna" in wanted:
        edges.extend(shared_fauna_edges(pids, connect=connect))
    return edges


def _dedupe(edges: list[Edge]) -> list[Edge]:
    """Collapse the mirror rows the symmetric tables store (companion_friends
    holds (a,b); a design may match it from either end) to one edge per
    (kind, unordered pair)."""
    seen: dict[tuple, Edge] = {}
    for e in edges:
        if e.directed:
            key = (e.kind, e.a_id, e.b_type, e.b_id)
        else:
            lo, hi = sorted((e.a_id, e.b_id))
            key = (e.kind, lo, e.b_type, hi)
        if key not in seen or e.strength > seen[key].strength:
            seen[key] = e
    return list(seen.values())


def _name_communities(edges: list[Edge], connect: Optional[Callable]) -> None:
    """Fill in which community a ``co_planted`` pair shares — the view collapses
    duplicate pairs, so the names are gathered here in one extra query."""
    pairs = {(min(e.a_id, e.b_id), max(e.a_id, e.b_id))
             for e in edges if e.kind == "co_planted"}
    if not pairs:
        return
    ids = sorted({pid for pair in pairs for pid in pair})
    ph = ",".join("?" * len(ids))
    try:
        rows = _rows(
            connect,
            f"""SELECT m.polyculture_id AS gid, m.plant_id AS pid,
                       COALESCE(p.name, '') AS name
                  FROM polyculture_members m
                  JOIN polycultures p ON p.id = m.polyculture_id
                 WHERE m.plant_id IN ({ph})""",
            ids,
        )
    except Exception:                           # noqa: BLE001
        return
    by_group: dict = {}
    names: dict = {}
    for r in rows:
        by_group.setdefault(r["gid"], set()).add(r["pid"])
        names[r["gid"]] = r["name"]
    shared: dict = {}
    for gid, members in by_group.items():
        for pair in pairs:
            if pair[0] in members and pair[1] in members:
                shared.setdefault(pair, []).append(names.get(gid, ""))
    for i, e in enumerate(edges):
        if e.kind != "co_planted":
            continue
        got = shared.get((min(e.a_id, e.b_id), max(e.a_id, e.b_id)))
        if got:
            edges[i] = _with_detail(e, ", ".join(sorted(n for n in got if n)))


def _with_detail(edge: Edge, detail: str) -> Edge:
    return Edge(kind=edge.kind, a_id=edge.a_id, b_type=edge.b_type,
                b_id=edge.b_id, directed=edge.directed,
                strength=edge.strength, evidence=edge.evidence,
                detail=detail or edge.detail, source=edge.source)


def shared_fauna_edges(plant_ids: Iterable[int], *,
                       min_shared: int = 1,
                       connect: Optional[Callable] = None) -> list[Edge]:
    """Plant↔plant edges *derived* from a shared animal.

    Two plants that both support the same species are related whether or not
    anyone recorded a companion pairing — that is the food web's real topology,
    and it is exactly the structure no single table can see. Strength grows with
    the number of animals shared, capped; the detail names them (up to three).

    Marked ``evidence='derived'`` so a caller can always separate this from a
    seeded record (P9).
    """
    pids = sorted({int(p) for p in plant_ids})
    if len(pids) < 2:
        return []
    ph = ",".join("?" * len(pids))
    try:
        rows = _rows(
            connect,
            f"""SELECT e.a_id AS pid, e.b_id AS fid,
                       COALESCE(f.common_name, '') AS name
                  FROM relationship_edges e
                  LEFT JOIN fauna f ON f.id = e.b_id
                 WHERE e.b_type = 'fauna' AND e.a_id IN ({ph})""",
            pids,
        )
    except Exception:                           # noqa: BLE001
        return []
    by_fauna: dict = {}
    fauna_names: dict = {}
    for r in rows:
        by_fauna.setdefault(r["fid"], set()).add(r["pid"])
        fauna_names[r["fid"]] = r["name"]

    pair_species: dict = {}
    for fid, users in by_fauna.items():
        members = sorted(users)
        if len(members) < 2:
            continue
        for i, a in enumerate(members):
            for b in members[i + 1:]:
                pair_species.setdefault((a, b), set()).add(fid)

    base = EDGE_KINDS["shared_fauna"].weight
    out = []
    for (a, b), fids in sorted(pair_species.items()):
        if len(fids) < min_shared:
            continue
        names = sorted(n for n in (fauna_names.get(f, "") for f in fids) if n)
        out.append(Edge(
            kind="shared_fauna", a_id=a, b_type="plant", b_id=b,
            directed=False,
            strength=min(1.0, base + 0.10 * (len(fids) - 1)),
            evidence="derived",
            detail=", ".join(names[:3]) + ("…" if len(names) > 3 else ""),
            source=f"{len(fids)} shared species",
        ))
    return out


def edges_for_plant(plant_id: int, *,
                    kinds: Optional[Iterable[str]] = None,
                    connect: Optional[Callable] = None) -> list[Edge]:
    """Everything connected to one plant, across the whole catalogue — the
    question F7 exists to answer. Unlike :func:`edges_among` this is not scoped
    to a design: it is the species' full documented neighbourhood."""
    pid = int(plant_id)
    wanted = sorted((set(kinds) if kinds is not None else set(DOCUMENTED_KINDS))
                    & set(DOCUMENTED_KINDS))
    if not wanted:
        return []
    kph = ",".join("?" * len(wanted))
    try:
        rows = _rows(
            connect,
            f"""SELECT kind, a_id, b_type, b_id, directed, detail, source,
                       evidence, confidence
                  FROM relationship_edges
                 WHERE kind IN ({kph})
                   AND (a_id = ? OR (b_type = 'plant' AND b_id = ?))""",
            wanted + [pid, pid],
        )
    except Exception:                           # noqa: BLE001
        return []
    edges = [e for e in (_edge_from_row(r) for r in rows) if e is not None]
    return _dedupe(edges)


def neighbourhood(plant_id: int, *,
                  connect: Optional[Callable] = None,
                  name_lookup: Optional[Callable] = None) -> dict:
    """A plain-dict summary of one plant's neighbourhood, grouped by edge kind
    and resolved to names — what a "show me everything connected to this plant"
    panel or the scripting API wants in one call.

    ``{"plant_id": id, "total": n, "groups": [{kind, label, phrase, group,
    color, items: [{id, name, detail, strength, evidence}]}]}``
    """
    edges = edges_for_plant(plant_id, connect=connect)
    if not edges:
        return {"plant_id": int(plant_id), "total": 0, "groups": []}

    plant_ids = sorted({e.other(plant_id)[1] for e in edges
                        if e.other(plant_id)[0] == "plant"})
    fauna_ids = sorted({e.b_id for e in edges if e.b_type == "fauna"})
    if name_lookup is None:
        names = _default_names(plant_ids, fauna_ids, connect=connect)
    else:
        names = name_lookup(plant_ids, fauna_ids)

    grouped: dict = {}
    for e in edges:
        far_type, far_id = e.other(plant_id)
        grouped.setdefault(e.kind, []).append({
            "id": far_id,
            "type": far_type,
            "name": names.get((far_type, far_id), ""),
            "detail": e.detail,
            "strength": round(e.strength, 2),
            "evidence": e.evidence,
            # V2.42: `source` reached the DB, the view and the Edge, and was
            # dropped right here — which is why no screen in the app has ever
            # shown a citation for its ecology. Carrying it costs one line.
            "source": e.source,
            "confidence": e.confidence,
        })

    groups = []
    for kind in sorted(grouped, key=lambda k: -EDGE_KINDS[k].weight):
        meta = EDGE_KINDS[kind]
        groups.append({
            "kind": kind, "label": meta.label, "phrase": meta.phrase,
            "group": meta.group, "color": meta.color,
            "items": sorted(grouped[kind], key=lambda it: it["name"]),
        })
    return {"plant_id": int(plant_id), "total": len(edges), "groups": groups}


def _default_names(plant_ids: list, fauna_ids: list, *,
                   connect: Optional[Callable] = None) -> dict:
    """``{(type, id): common_name}`` for the ids a neighbourhood touches."""
    out: dict = {}
    if not plant_ids and not fauna_ids:
        return out
    conn = (connect or _default_connect)()
    try:
        for table, kind, ids in (("plants", "plant", plant_ids),
                                 ("fauna", "fauna", fauna_ids)):
            if not ids:
                continue
            ph = ",".join("?" * len(ids))
            for row in conn.execute(
                    f"SELECT id, common_name FROM {table} WHERE id IN ({ph})",
                    list(ids)):
                out[(kind, row["id"])] = row["common_name"] or ""
    except Exception:                           # noqa: BLE001
        pass
    finally:
        conn.close()
    return out
