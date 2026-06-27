"""
src/scene_contract.py — the versioned Scene JSON contract (V1.62).

Design principle P4 (time is the most undervalued design variable — the scene is
built for a chosen growth-timeline year) — see docs/DESIGN_PHILOSOPHY.md.

One pure function, :func:`build_scene`, turns a project dict into a
renderer-agnostic scene description in **local metres** (+x east, +y north,
origin at the design centroid). The embedded 3D viewer consumes it via
``window.permaSetScene``; anything else that needs a geometric picture of
the design (a future exporter, the PDF isometric view, tests) reads the
same dict — so the map, the 3D view, and the analysis can't drift apart.

Scene schema (``SCENE_VERSION`` = 1)::

    {
      "version": 1,
      "year": int,                     # growth-timeline year (0 = mature)
      "month": int,                    # 1–12, drives 3D seasonal foliage colour
      "origin": {"lat": .., "lng": ..},# projection origin (WGS-84)
      "bounds": {"min_x","min_y","max_x","max_y"},   # metres, scene extent
      "boundary": [[x, y], ...] | None,              # property outline
      "plants": [{plant_id, x, y, height_m, canopy_m, plant_type,
                  foliage_type, scale_factor, spread_factor, spread_rate,
                  growth_curve, color, opacity, common_name, existing?}, ...],
                                       # foliage_type: deciduous|evergreen|
                                       #   herbaceous|semi-evergreen (3D crown
                                       #   shape + seasonal colour)
                                       # scale_factor: 0.1–1.0 growth maturity
                                       #   (3D branch-complexity tier)
                                       # spread_factor: ≥1.0 colony widening
                                       # spread_rate: 0–1 aggressiveness (3D
                                       #   continuous year-by-year spread)
      "buildings": [{ring: [[x, y], ...], height_m, kind}, ...],
                                       # kind: "building" | "canopy"
      "structures": [{x, y, struct_id, name, size_m, height_m}, ...],
      "terrain": {rows, cols, min_x, min_y, max_x, max_y, base_m,
                  heights: [[m above base_m, row 0 = north], ...]} | None,
      "scan_points": [[x, y, z], ...] | None,   # imported yard scan (V1.63)
      "splat": {path, matrix, opacity} | None,  # Gaussian-splat backdrop (V1.65)
      "sun": {"azimuth_deg": .., "altitude_deg": ..} | None,
    }

Everything is plain JSON-serialisable data. Qt-free, DB-free (``get_plant``
is injectable), network-free (``elevation`` is passed in when available).
Plant sizing/presence comes from :mod:`src.scene3d` so the 3D scene matches
the 2D growth timeline exactly; colours come from the shared
``_TYPE_COLORS`` so the 3D plants match the map's markers.

Not yet in the scene (future versions): hedgerow lines, annotation labels.
"""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Callable, Optional

from src.member_colors import TYPE_COLORS as _TYPE_COLORS
from src.projection import Projector
from src.project_store import plant_record_from_feature
from src.scene3d import plant_3d_state

SCENE_VERSION = 1

# Default scene moment: summer solstice, 13:00 local solar — high sun, the
# reference most landscape shadow studies use.
_DEFAULT_WHEN = datetime(2025, 6, 21, 13, 0)

_FALLBACK_PLANT_COLOR = "#66bb6a"   # map.html's marker fallback

# Existing trees marked on the map get a muted colour so proposed plants
# stand out against what's already there.
_EXISTING_TREE_COLOR = "#4e6e52"

# ── Natural foliage + bloom (V1.90) ──────────────────────────────────────────
# The 3D viewer used to colour plants by their map-marker (plant-type) colour —
# which since the V1.87 taxonomy turned wildflowers purple. Instead send a
# natural foliage green per type (with a silver set for sages etc.), and pass
# the curated flower_color / flower_form + bloom window so the viewer can render
# real-coloured flowers when a plant is in bloom for the scene's month.
_FOLIAGE_BY_TYPE = {
    "tree":        "#4a7a3e",
    "shrub":       "#4f7a3a",
    "wildflower":  "#6a9a4a",
    "herb":        "#6a9a4a",
    "groundcover": "#5b8a4a",
    "grass":       "#8aa256",
    "sedge":       "#7e9a55",
    "rush":        "#6f9a5a",
    "fern":        "#3f6b46",
    "vine":        "#5a8a3c",
    "aquatic":     "#4a8a64",
}
_SILVER_FOLIAGE_GENERA = {
    "artemisia", "antennaria", "anaphalis", "elaeagnus", "shepherdia",
    "krascheninnikovia", "eurotia",
}
_DEFAULT_FOLIAGE = "#5b8a4a"

_MONTHS = {
    "jan": 1, "feb": 2, "mar": 3, "apr": 4, "may": 5, "jun": 6, "jul": 7,
    "aug": 8, "sep": 9, "oct": 10, "nov": 11, "dec": 12,
}


def _foliage_color(plant: dict) -> str:
    """Natural foliage colour for the 3D body — a green by plant type, silvery
    for sage-type genera, or the user's explicit marker colour if they set one."""
    marker = plant.get("marker_color")
    if marker:
        return marker
    genus = (plant.get("scientific_name") or "").split(" ")[0].lower()
    if genus in _SILVER_FOLIAGE_GENERA:
        return "#9aa890"
    if (plant.get("plant_type") == "tree"
            and plant.get("deciduous_evergreen") == "evergreen"):
        return "#355e3b"   # conifers — darker
    return _FOLIAGE_BY_TYPE.get(plant.get("plant_type"), _DEFAULT_FOLIAGE)


def _bloom_months(bloom_period: str):
    """Parse a ``bloom_period`` like 'May-Jul', 'June-August', or 'Aug' into
    ``(start_month, end_month)`` (1–12), or ``(0, 0)`` when unknown. The 3D
    viewer shows flowers only when the scene's month falls in this window."""
    s = (bloom_period or "").strip().lower()
    if not s:
        return 0, 0
    parts = [p.strip()[:3] for p in s.replace("–", "-").split("-")]
    nums = [_MONTHS[p] for p in parts if p in _MONTHS]
    if not nums:
        return 0, 0
    return nums[0], nums[-1]


def _boundary_ring(project: dict) -> Optional[list]:
    """First property_boundary ring as ``[[lat, lng], ...]`` (open)."""
    for f in project.get("features", []):
        props = f.get("properties", {}) or {}
        geom = f.get("geometry", {}) or {}
        if (props.get("element_type") == "property_boundary"
                and geom.get("type") == "Polygon"
                and geom.get("coordinates")):
            ring = [[pt[1], pt[0]] for pt in geom["coordinates"][0]]
            if len(ring) > 1 and ring[0] == ring[-1]:
                ring = ring[:-1]
            return ring if len(ring) >= 3 else None
    return None


def _scene_origin(project: dict, boundary: Optional[list]) -> tuple:
    """Scene origin (lat, lng): boundary centroid → plant centroid →
    site-config pin → (0, 0)."""
    if boundary:
        return (sum(p[0] for p in boundary) / len(boundary),
                sum(p[1] for p in boundary) / len(boundary))
    pts = []
    for f in project.get("features", []):
        rec = plant_record_from_feature(f)
        if rec is not None:
            pts.append((rec["lat"], rec["lng"]))
    if pts:
        return (sum(p[0] for p in pts) / len(pts),
                sum(p[1] for p in pts) / len(pts))
    sc = (project.get("properties", {}) or {}).get("site_config", {}) or {}
    if sc.get("latitude") is not None and sc.get("longitude") is not None:
        return float(sc["latitude"]), float(sc["longitude"])
    return 0.0, 0.0


def _square_ring(x: float, y: float, size_m: float) -> list:
    """Axis-aligned square ring (open) of side ``size_m`` centred on x, y."""
    h = max(0.25, float(size_m or 1.0)) / 2.0
    return [[x - h, y - h], [x + h, y - h], [x + h, y + h], [x - h, y + h]]


def _sun_for(lat: float, lng: float, when: datetime) -> Optional[dict]:
    """Sun azimuth/altitude at local solar ``when`` — same convention and
    longitude shift as ``map3d_js.set_sun_for`` / the 2D shade engine."""
    from src.solar import sun_position
    sun = sun_position(lat, lng, when + timedelta(hours=-lng / 15.0))
    if sun.altitude <= 0:
        return None
    return {"azimuth_deg": round(sun.azimuth, 2),
            "altitude_deg": round(sun.altitude, 2)}


def _terrain_block(elevation: Optional[dict], proj: Projector) -> Optional[dict]:
    """Convert a ``terrain.fetch_openmeteo_grid``-shaped elevation dict
    (grid row 0 = north edge) into the scene's local-metre terrain block."""
    if not elevation or not elevation.get("grid"):
        return None
    grid = elevation["grid"]
    bbox = elevation.get("bbox") or {}
    if not all(k in bbox for k in ("north", "south", "east", "west")):
        return None
    flat = [v for row in grid for v in row if v is not None]
    if not flat:
        return None
    base = min(flat)
    # Project the bbox corners; the grid is regular in degrees, which over a
    # property-sized span is regular in metres to well under the DEM error.
    x0, y0 = proj.to_xy(bbox["south"], bbox["west"])
    x1, y1 = proj.to_xy(bbox["north"], bbox["east"])
    return {
        "rows": len(grid),
        "cols": len(grid[0]) if grid else 0,
        "min_x": round(min(x0, x1), 2), "min_y": round(min(y0, y1), 2),
        "max_x": round(max(x0, x1), 2), "max_y": round(max(y0, y1), 2),
        "base_m": round(base, 2),
        "heights": [[round((v - base), 2) if v is not None else 0.0
                     for v in row] for row in grid],
    }


def build_scene(project: dict, *, year: int = 0,
                get_plant: Optional[Callable] = None,
                elevation: Optional[dict] = None,
                when: Optional[datetime] = None,
                scan: Optional[dict] = None,
                splat: Optional[dict] = None) -> dict:
    """Build the Scene JSON for ``project`` at growth-timeline ``year``.

    ``get_plant`` is injectable for tests (defaults to the DB);
    ``elevation`` is an optional ``fetch_openmeteo_grid`` result;
    ``when`` is the local-solar moment for the sun (default summer noon);
    ``scan`` is an optional ``scan_import.sample_for_scene`` result —
    its points are re-framed from the scan's projection origin into this
    scene's and exposed as ``scene["scan_points"]``.
    ``splat`` optionally overrides the project's ``splat_backdrop`` feature
    (a Gaussian-splat photoreal backdrop); when omitted it is auto-detected
    from ``project`` and exposed as ``scene["splat"]`` ({path, matrix,
    opacity}) so the 3D viewer can place it behind the design.
    """
    if get_plant is None:
        from src.db.plants import get_plant as _gp
        get_plant = _gp

    boundary = _boundary_ring(project)
    lat0, lng0 = _scene_origin(project, boundary)
    proj = Projector(lat0, lng0)

    plants: list = []
    buildings: list = []
    structures: list = []
    cache: dict = {}

    def _plant_rec(pid):
        if pid not in cache:
            cache[pid] = get_plant(pid) or {}
        return cache[pid]

    for f in project.get("features", []):
        props = f.get("properties", {}) or {}
        geom = f.get("geometry", {}) or {}
        etype = props.get("element_type")

        rec = plant_record_from_feature(f)
        if rec is not None:
            plant = _plant_rec(rec["plant_id"])
            st = plant_3d_state(plant, rec["lat"], rec["lng"], year)
            x, y = proj.to_xy(rec["lat"], rec["lng"])
            plants.append({
                "plant_id": rec["plant_id"],
                "common_name": rec.get("common_name", ""),
                "x": round(x, 2), "y": round(y, 2),
                "height_m": st["height_m"], "canopy_m": st["canopy_m"],
                "plant_type": st["plant_type"] or "herb",
                "foliage_type": st.get("foliage_type", "herbaceous"),
                # Growth maturity (0.1–1.0) drives the 3D viewer's structural
                # tier (sapling/young/mature branch complexity); spread_factor
                # (≥1.0) widens the footprint; spread_rate (0–1) drives the
                # continuous, year-by-year colony scatter for self-spreaders.
                "scale_factor": st["scale_factor"],
                "spread_factor": st["spread_factor"],
                "spread_rate": st["spread_rate"],
                "growth_curve": plant.get("growth_curve") or "steady",
                # 3D body = natural foliage colour (V1.90); flowers carry their
                # own real colour + form, shown when in bloom for the month.
                "color": _foliage_color(plant),
                "flower_color": plant.get("flower_color") or "",
                "flower_form": plant.get("flower_form") or "none",
                "bloom_start": _bloom_months(plant.get("bloom_period"))[0],
                "bloom_end": _bloom_months(plant.get("bloom_period"))[1],
                "opacity": st["presence_opacity"],
            })
            continue

        if etype == "existing_tree" and geom.get("type") == "Point":
            lng, lat = geom["coordinates"]
            x, y = proj.to_xy(lat, lng)
            canopy = float(props.get("canopy_radius_m")
                           or (props.get("size_m") or 6.0) / 2.0) * 2.0
            plants.append({
                "plant_id": None,
                "common_name": props.get("label", "Existing tree"),
                "x": round(x, 2), "y": round(y, 2),
                "height_m": float(props.get("height_m") or 6.0),
                "canopy_m": canopy,
                "plant_type": "tree",
                # Existing trees are mature with no modelled colony spread.
                "scale_factor": 1.0,
                "spread_factor": 1.0,
                "spread_rate": 0.0,
                "growth_curve": "steady",
                "color": _EXISTING_TREE_COLOR,
                "flower_color": "",
                "flower_form": "none",
                "bloom_start": 0,
                "bloom_end": 0,
                "opacity": 1.0,
                "existing": True,
            })

        elif etype == "existing_building" and geom.get("type") == "Point":
            lng, lat = geom["coordinates"]
            x, y = proj.to_xy(lat, lng)
            buildings.append({
                "ring": [[round(px, 2), round(py, 2)] for px, py in
                         _square_ring(x, y, props.get("size_m") or 8.0)],
                "height_m": float(props.get("height_m") or 6.0),
                "kind": "building",
            })

        elif (etype in ("custom_shape", "canopy_footprint")
              and geom.get("type") == "Polygon"
              and float(props.get("height_m") or 0.0) > 0.0):
            ring_ll = geom.get("coordinates", [[]])[0]
            ring = []
            for pt in ring_ll:
                x, y = proj.to_xy(pt[1], pt[0])
                ring.append([round(x, 2), round(y, 2)])
            if len(ring) > 1 and ring[0] == ring[-1]:
                ring = ring[:-1]
            if len(ring) >= 3:
                buildings.append({
                    "ring": ring,
                    "height_m": float(props.get("height_m")),
                    "kind": ("canopy" if etype == "canopy_footprint"
                             else "building"),
                })

        elif etype == "structure" and geom.get("type") == "Point":
            lng, lat = geom["coordinates"]
            x, y = proj.to_xy(lat, lng)
            sd = props.get("struct_def", {}) or {}
            structures.append({
                "x": round(x, 2), "y": round(y, 2),
                "struct_id": sd.get("id", ""),
                "name": sd.get("name", ""),
                "size_m": float(sd.get("size_m") or 1.0),
                "height_m": float(sd.get("height_m") or 1.0),
            })

    boundary_xy = None
    if boundary:
        boundary_xy = [[round(x, 2), round(y, 2)]
                       for x, y in (proj.to_xy(la, ln) for la, ln in boundary)]

    # Scene extent: everything placed, padded; floor of ±25 m so an
    # empty/near-empty design still gets a sensible stage.
    xs, ys = [0.0], [0.0]
    for p in plants:
        xs.append(p["x"]); ys.append(p["y"])
    for b in buildings:
        xs.extend(pt[0] for pt in b["ring"])
        ys.extend(pt[1] for pt in b["ring"])
    for s in structures:
        xs.append(s["x"]); ys.append(s["y"])
    if boundary_xy:
        xs.extend(pt[0] for pt in boundary_xy)
        ys.extend(pt[1] for pt in boundary_xy)
    pad = 5.0
    bounds = {
        "min_x": round(min(min(xs) - pad, -25.0), 2),
        "min_y": round(min(min(ys) - pad, -25.0), 2),
        "max_x": round(max(max(xs) + pad, 25.0), 2),
        "max_y": round(max(max(ys) + pad, 25.0), 2),
    }

    scan_points = None
    if scan and scan.get("points"):
        # Re-frame from the scan's projection origin into this scene's:
        # both are local cosLat frames, so the shift is a constant offset.
        from src.projection import metres_per_deg
        so = scan.get("origin") or {}
        m_lat, m_lng = metres_per_deg(lat0)
        dx = ((so.get("lng") or lng0) - lng0) * m_lng
        dy = ((so.get("lat") or lat0) - lat0) * m_lat
        scan_points = [[round(p[0] + dx, 2), round(p[1] + dy, 2), p[2]]
                       for p in scan["points"]]

    splat_feature = splat
    if splat_feature is None:
        from src.splat_backdrop import feature_from_project
        splat_feature = feature_from_project(project)
    splat_field = None
    if splat_feature:
        from src.splat_backdrop import scene_field
        splat_field = scene_field(splat_feature, lat0, lng0)

    return {
        "version": SCENE_VERSION,
        "year": int(year),
        "month": (when or _DEFAULT_WHEN).month,
        "origin": {"lat": lat0, "lng": lng0},
        "bounds": bounds,
        "boundary": boundary_xy,
        "plants": plants,
        "buildings": buildings,
        "structures": structures,
        "terrain": _terrain_block(elevation, proj),
        "scan_points": scan_points,
        "splat": splat_field,
        "sun": _sun_for(lat0, lng0, when or _DEFAULT_WHEN),
    }
