"""
placement_score.py — Ecological cell-scoring for design generation (V1.51).

Replaces the four-bucket zone system with continuous per-cell scoring:
each placement cell gets a 0–1 fitness score for a given plant, combining
shade match, moisture (elevation + aspect), slope suitability, and
edge/interior preference.  Scores are fast to compute (no DB or network
calls at score time) — all environmental data is pre-computed in
build_cell_env_map and reused across all plant queries in a design pass.

Also provides companion-proximity checking: after placement, warns when
friend pairs land too far apart or enemy pairs too close.

Qt-free; no circular imports (depends only on src.db.plants and stdlib).
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Optional

_SPACING_M = 6.0  # matches llm_design._SPACING_M


# ── Environmental snapshot for one placement cell ─────────────────────────────

@dataclass(frozen=True)
class CellEnv:
    shade_fraction: float   # 0.0–1.0, seasonal average from shade grid
    elevation_pct: float    # 0.0–1.0, normalised across the full grid
    slope_pct: float        # raw % slope from compute_slope_grid
    aspect_deg: float       # 0–360 compass degrees, or -1.0 for flat cells
    is_edge: bool           # True if within 1 grid step of the boundary edge


# ── Cell-set topology helpers ─────────────────────────────────────────────────

def classify_edge_cells(all_cells: list, spacing_m: float = _SPACING_M) -> set:
    """Return the subset of cells on the interior edge of the placement pool.

    A cell is an edge cell if at least one of its 8 cardinal/diagonal
    neighbours (at spacing_m offsets) is absent from the pool.  Works on
    the regular grid produced by grid_cells_in_boundary — cells outside the
    polygon are simply not in all_cells, so boundary-adjacent cells are
    reliably detected.  O(n) via integer grid normalisation."""
    if not all_cells:
        return set()
    ref_lat = sum(c[0] for c in all_cells) / len(all_cells)
    cos_lat = math.cos(ref_lat * math.pi / 180) or 1e-9
    dlat = spacing_m / 111320.0
    dlng = spacing_m / (111320.0 * cos_lat)

    min_lat = min(c[0] for c in all_cells)
    min_lng = min(c[1] for c in all_cells)

    def _idx(lat: float, lng: float):
        return (round((lat - min_lat) / dlat),
                round((lng - min_lng) / dlng))

    idx_set = {_idx(lat, lng) for lat, lng in all_cells}
    idx_to_latlng = {_idx(lat, lng): (lat, lng) for lat, lng in all_cells}

    edge: set = set()
    for (i, j), cell in idx_to_latlng.items():
        for di in (-1, 0, 1):
            for dj in (-1, 0, 1):
                if di == 0 and dj == 0:
                    continue
                if (i + di, j + dj) not in idx_set:
                    edge.add(cell)
                    break
            else:
                continue
            break
    return edge


def _latlng_to_rc(lat: float, lng: float, elev: dict) -> tuple:
    """Nearest elevation grid (r, c) for a (lat, lng) position.
    Clamped so out-of-bbox positions don't index-error."""
    bbox = elev["bbox"]
    grid = elev.get("grid") or [[]]
    rows = elev.get("rows", len(grid))
    cols = elev.get("cols", len(grid[0]) if rows else 0)
    if rows <= 0 or cols <= 0:
        return (0, 0)
    span_lat = bbox["north"] - bbox["south"]
    span_lng = bbox["east"] - bbox["west"]
    t = (bbox["north"] - lat) / span_lat if span_lat else 0.5
    u = (lng - bbox["west"]) / span_lng if span_lng else 0.5
    r = max(0, min(rows - 1, int(round(t * (rows - 1)))))
    c = max(0, min(cols - 1, int(round(u * (cols - 1)))))
    return (r, c)


# ── Pre-compute all cell environments ─────────────────────────────────────────

def build_cell_env_map(
    cells: list,
    shade_grid: Optional[list] = None,
    elev_grid: Optional[dict] = None,
    slope_grid: Optional[list] = None,
    aspect_grid: Optional[list] = None,
    spacing_m: float = _SPACING_M,
) -> dict:
    """Pre-compute a CellEnv for every placement cell.

    All grid lookups are guarded — missing or out-of-bounds data falls back
    to neutral defaults (shade=0.5, elev=0.5, slope=0, aspect=-1) so the
    function never raises even when all grids are None."""
    if not cells:
        return {}

    edge_cells = classify_edge_cells(cells, spacing_m)

    # Elevation normalisation range computed across the full grid (not just
    # boundary cells) so the relative signal is consistent.
    e_min = e_max = None
    if elev_grid and elev_grid.get("grid"):
        flat_elev = [v for row in elev_grid["grid"] for v in row]
        if flat_elev:
            e_min, e_max = min(flat_elev), max(flat_elev)
    e_span = (e_max - e_min) if (e_min is not None and e_max != e_min) else 1.0

    rows = cols = 0
    if elev_grid and elev_grid.get("grid"):
        rows = elev_grid.get("rows", len(elev_grid["grid"]))
        cols = elev_grid.get("cols",
                             len(elev_grid["grid"][0]) if rows else 0)

    result: dict = {}
    for (lat, lng) in cells:
        shade = 0.5
        elev_pct = 0.5
        slope = 0.0
        aspect = -1.0

        if rows > 0 and cols > 0:
            r, c = _latlng_to_rc(lat, lng, elev_grid)
            if e_min is not None:
                raw_e = elev_grid["grid"][r][c]
                elev_pct = max(0.0, min(1.0, (raw_e - e_min) / e_span))
            if (shade_grid is not None
                    and r < len(shade_grid)
                    and c < len(shade_grid[r])):
                shade = float(shade_grid[r][c])
            if (slope_grid is not None
                    and r < len(slope_grid)
                    and c < len(slope_grid[r])):
                slope = float(slope_grid[r][c])
            if (aspect_grid is not None
                    and r < len(aspect_grid)
                    and c < len(aspect_grid[r])):
                aspect = float(aspect_grid[r][c])

        result[(lat, lng)] = CellEnv(
            shade_fraction=max(0.0, min(1.0, shade)),
            elevation_pct=max(0.0, min(1.0, elev_pct)),
            slope_pct=max(0.0, slope),
            aspect_deg=aspect,
            is_edge=(lat, lng) in edge_cells,
        )
    return result


# ── Per-plant scoring sub-functions ───────────────────────────────────────────

def _shade_match(sun_req: str, shade: float) -> float:
    """0–1 fitness of a cell's shade level for a plant's sun requirement."""
    if sun_req == "full_sun":
        return max(0.0, 1.0 - shade / 0.35)
    if sun_req == "partial_shade":
        if shade < 0.2:
            return shade / 0.2
        if shade <= 0.55:
            return 1.0
        return max(0.0, 1.0 - (shade - 0.55) / 0.45)
    if sun_req == "full_shade":
        return min(1.0, shade / 0.4)
    return 0.5


def _moisture_match(water_needs: str, cell: CellEnv) -> float:
    """0–1 fitness based on cell moisture: low elevation = wetter, high slope
    and S-facing aspect = drier."""
    base = 1.0 - cell.elevation_pct
    aspect_adj = 0.0
    if cell.aspect_deg >= 0:
        a = cell.aspect_deg
        if 135.0 <= a <= 225.0:      # S-facing: warmer, drier
            aspect_adj = -0.15
        elif a >= 315.0 or a <= 45.0:  # N-facing: cooler, wetter
            aspect_adj = 0.15
    slope_adj = -min(0.15, cell.slope_pct / 100.0)   # steep = drains fast
    cell_moisture = max(0.0, min(1.0, base + aspect_adj + slope_adj))

    if water_needs == "high":
        return cell_moisture
    if water_needs == "low":
        return 1.0 - cell_moisture
    if water_needs in ("medium", "moderate"):
        return max(0.0, 1.0 - abs(cell_moisture - 0.5) * 2.0)
    return 0.5


def _slope_suitability(plant_type: str, slope: float) -> float:
    """0–1 fitness based on slope steepness vs plant type."""
    if plant_type in ("groundcover", "herb", "grass", "sedge"):
        return 1.0
    if plant_type == "aquatic":
        return max(0.0, 1.0 - slope / 2.0)
    if plant_type == "tree":
        if slope <= 15.0:
            return 1.0
        if slope <= 30.0:
            return 1.0 - (slope - 15.0) / 15.0
        return 0.0
    # shrub, vine, root, and anything else
    return max(0.0, 1.0 - slope / 35.0)


def _edge_preference(uses: set, is_edge: bool) -> float:
    """0–1 fitness based on boundary-edge vs interior preference."""
    if is_edge:
        if "windbreak" in uses or "hedge" in uses:
            return 1.0
        if "groundcover" in uses:
            return 0.3
        return 0.5
    else:
        if "groundcover" in uses:
            return 0.8
        if "windbreak" in uses or "hedge" in uses:
            return 0.2
        return 0.5


def score_cell_for_plant(plant: dict, cell: CellEnv) -> float:
    """Ecological fitness score (0–1) for placing plant at this cell.

    Weights: shade 35%, moisture 35%, slope 15%, edge preference 15%.
    Any missing plant field defaults to a neutral 0.5 sub-score so the
    function never raises on incomplete plant dicts.

    The caller should pre-fetch use tags and embed them as ``plant["_uses"]``
    (a set of use-key strings, e.g. ``{"windbreak", "nitrogen_fixer"}``)
    before calling.  If absent, edge preference is neutral."""
    sun_req = (plant.get("sun_requirement") or "").lower()
    water_needs = (plant.get("water_needs") or "").lower()
    plant_type = (plant.get("plant_type") or "").lower()
    uses = plant.get("_uses") or set()

    shade_s = _shade_match(sun_req, cell.shade_fraction)
    moist_s = _moisture_match(water_needs, cell)
    slope_s = _slope_suitability(plant_type, cell.slope_pct)
    edge_s = _edge_preference(uses, cell.is_edge)

    return max(0.0, min(1.0,
        0.35 * shade_s + 0.35 * moist_s + 0.15 * slope_s + 0.15 * edge_s))


# ── Shade-tag matching against the cached zone tags ───────────────────────────

# Which cached zone tags are an acceptable home for each plant sun requirement.
# A full-sun plant tolerates partial shade but not full shade; a full-shade
# plant wants shade and is stressed in full sun; partial-shade plants are the
# generalists. Tags come from src/db/shade_zones.tag_for_fraction.
_SUN_REQ_OK_TAGS = {
    "full_sun":      {"full_sun", "partial_shade"},
    "partial_shade": {"full_sun", "partial_shade", "full_shade"},
    "full_shade":    {"partial_shade", "full_shade"},
}

_TAG_LABEL = {
    "full_sun":      "full sun",
    "partial_shade": "partial shade",
    "full_shade":    "full shade",
}


def shade_tag_matches_plant(sun_req: str, tag: str) -> bool:
    """True when a plant's ``sun_requirement`` is compatible with a spot's
    cached shade ``tag``. Unknown requirements are treated as tolerant (True)
    so we never warn on incomplete catalogue data."""
    sun_req = (sun_req or "").lower()
    if sun_req not in _SUN_REQ_OK_TAGS:
        return True
    return tag in _SUN_REQ_OK_TAGS[sun_req]


def check_shade_matches(placed_plants: list, project_key: str) -> list:
    """Warn when a placed plant sits in a spot whose cached shade tag clashes
    with its sun requirement (e.g. a full-sun plant under full shade).

    Reads the derived shade-tag cache (``src/db/shade_zones.py``) — the live
    grid stays authoritative during generation; this is fast GUI feedback after
    the user has run 'Classify planting zones'. Returns [] when nothing is
    cached, so it is silent until classification has happened.

    ``placed_plants``: dicts with ``plant_id``/``lat``/``lng`` and optionally
    ``common_name`` and ``sun_requirement`` (looked up from the catalogue when
    absent). One warning per plant species (deduped)."""
    if not placed_plants:
        return []
    try:
        from src.db import shade_zones
        if not shade_zones.has_tags(project_key):
            return []
    except Exception:  # noqa: BLE001 — matching is best-effort
        return []

    # Resolve sun requirement + display name per plant_id, catalogue-backed.
    def _plant_meta(p):
        sun = p.get("sun_requirement")
        name = p.get("common_name")
        if sun is None or name is None:
            try:
                from src.db.plants import get_plant
                row = get_plant(p.get("plant_id")) or {}
                sun = sun if sun is not None else row.get("sun_requirement")
                name = name if name is not None else row.get("common_name")
            except Exception:  # noqa: BLE001
                pass
        return (sun or ""), (name or str(p.get("plant_id")))

    warnings: list = []
    seen: set = set()
    for p in placed_plants:
        try:
            lat, lng = float(p["lat"]), float(p["lng"])
        except (KeyError, TypeError, ValueError):
            continue
        sun_req, name = _plant_meta(p)
        tag = shade_zones.tag_at(project_key, lat, lng)
        if not tag or shade_tag_matches_plant(sun_req, tag):
            continue
        key = (p.get("plant_id"), tag)
        if key in seen:
            continue
        seen.add(key)
        want = _TAG_LABEL.get(sun_req, sun_req or "different light")
        got = _TAG_LABEL.get(tag, tag)
        warnings.append(
            f"{name} wants {want} but is placed in a {got} spot — "
            "consider moving it or choosing a shade-matched plant."
        )
    return warnings


# ── Companion relationship graph ──────────────────────────────────────────────

def build_companion_graph(plant_ids: list) -> dict:
    """Batch-fetch companion relationships for all plants in the design.

    Returns ``{plant_id: {"friends": [id,...], "enemies": [id,...]}}``
    where each list contains only ids also present in ``plant_ids``.
    One DB connection, two queries total regardless of design size."""
    if not plant_ids:
        return {}
    id_set = set(plant_ids)
    result: dict = {pid: {"friends": [], "enemies": []}
                    for pid in plant_ids}
    try:
        from src.db.plants import get_connection
        conn = get_connection()
        try:
            ph = ",".join("?" * len(plant_ids))
            params = list(plant_ids) + list(plant_ids)
            for table, key in (("companion_friends", "friends"),
                                ("companion_enemies", "enemies")):
                rows = conn.execute(
                    f"SELECT plant_id_a, plant_id_b FROM {table} "
                    f"WHERE plant_id_a IN ({ph}) OR plant_id_b IN ({ph})",
                    params,
                ).fetchall()
                for a, b in rows:
                    if a in id_set and b in id_set:
                        if b not in result[a][key]:
                            result[a][key].append(b)
                        if a not in result[b][key]:
                            result[b][key].append(a)
        finally:
            conn.close()
    except Exception:  # noqa: BLE001 — companion checking is best-effort
        pass
    return result


def check_companion_spacing(placed_plants: list,
                             companion_graph: dict) -> list:
    """Return warning strings for companion pairs that are poorly spaced.

    Friends placed > 3× combined spacing apart get a "consider moving
    closer" note; enemies < combined spacing apart get a "consider
    separating" note.  Only warns once per pair (no duplicates).

    ``placed_plants``: list of dicts with ``plant_id``, ``lat``, ``lng``,
    and optionally ``common_name``."""
    if not placed_plants or not companion_graph:
        return []

    from collections import defaultdict
    coords: dict = defaultdict(list)
    names: dict = {}
    for p in placed_plants:
        pid = p.get("plant_id")
        if pid is None:
            continue
        coords[pid].append((float(p["lat"]), float(p["lng"])))
        if pid not in names:
            names[pid] = p.get("common_name") or str(pid)

    def _centroid(pts):
        return (sum(x[0] for x in pts) / len(pts),
                sum(x[1] for x in pts) / len(pts))

    def _dist_m(a, b):
        cos_lat = math.cos(a[0] * math.pi / 180) or 1e-9
        dx = (b[1] - a[1]) * 111320.0 * cos_lat
        dy = (b[0] - a[0]) * 111320.0
        return math.hypot(dx, dy)

    try:
        from src.db.plants import get_plant as _gp
        def _spacing(pid):
            row = _gp(pid) or {}
            s = (row.get("mature_canopy_m") or row.get("spacing_meters") or 2.0)
            return max(0.5, float(s))
    except Exception:  # noqa: BLE001
        def _spacing(_):  # type: ignore[misc]
            return 2.0

    warnings: list = []
    checked: set = set()

    for pid, rels in companion_graph.items():
        if pid not in coords:
            continue
        for rel_type, partner_ids in rels.items():
            for other_id in partner_ids:
                pair_key = (rel_type, frozenset((pid, other_id)))
                if pair_key in checked or other_id not in coords:
                    continue
                checked.add(pair_key)
                ca = _centroid(coords[pid])
                cb = _centroid(coords[other_id])
                dist = _dist_m(ca, cb)
                combined = _spacing(pid) + _spacing(other_id)
                na = names.get(pid, "?")
                nb = names.get(other_id, "?")
                if rel_type == "friends" and dist > combined * 3:
                    warnings.append(
                        f"{na} and {nb} are companion plants — consider "
                        "moving them closer together."
                    )
                elif rel_type == "enemies" and dist < combined:
                    warnings.append(
                        f"{na} and {nb} inhibit each other — consider "
                        "separating them further."
                    )
    return warnings
