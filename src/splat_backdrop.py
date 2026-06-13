"""
src/splat_backdrop.py — georeferenced 3D Gaussian-splat backdrop (V1.65).

A phone capture app (Scaniverse / Polycam / Luma) can export a *photoreal*
3D Gaussian splat of a yard as a ``.ply``. The splat's vertices are the
gaussian centres, so the existing scan-import georeference flow
(:func:`src.scan_import.align_scan`) aligns them like any point cloud — and
the same rotation/scale/translation then places the **whole splat** in the
3D preview as a true-to-life backdrop, with the proposed planting drawn on
top. A top-down render of that splat is also baked to a PNG and shown on the
2D map as a personal, fresher "satellite" layer (see
``html/map/06-overlays.js`` ``drawSplatOrthoOverlay`` and the slope/shade
overlays it mirrors).

This module is the **Qt-free, DB-free** core: the world-matrix math that
turns a 2D georeference into the splat's 3D placement, the splat's lat/lng
footprint, and the ``splat_backdrop`` GeoJSON feature that persists it in the
single-file project. The renderer ingredients (Spark in ``html/scene3d.html``,
the ``Map3DWidget``) and the dialog wiring live elsewhere; everything here is
plain data so it is unit-testable without a display.

Coordinate frames (all metres unless noted)::

    F_file    raw splat-file vertices (Spark loads these unchanged)
    F_zup     z-up, after read_points' up-axis swap
    F_proj    projector-local (georeferenced); origin = control-point centroid
    F_scene   scene-local; origin = the design centroid build_scene picks
    F_three   three.js: x_east→+x, y_north→−z, up→+y

:func:`world_matrix` composes F_file → F_three as a single 4×4 (returned
column-major, ready for three.js ``Matrix4.fromArray``).
"""

from __future__ import annotations

import math
from typing import Optional

ELEMENT_TYPE = "splat_backdrop"
_DEFAULT_OPACITY = 1.0


# ── world matrix (F_file → F_three) ──────────────────────────────────────────

def _mat4(rows) -> list:
    """3×3 linear ``rows`` (+ optional 4th translation column folded in by the
    caller) → 4×4 row-major list. Helper kept tiny so the composition below
    reads as the maths."""
    return [
        [rows[0][0], rows[0][1], rows[0][2], 0.0],
        [rows[1][0], rows[1][1], rows[1][2], 0.0],
        [rows[2][0], rows[2][1], rows[2][2], 0.0],
        [0.0, 0.0, 0.0, 1.0],
    ]


def _matmul(a: list, b: list) -> list:
    return [[sum(a[i][k] * b[k][j] for k in range(4)) for j in range(4)]
            for i in range(4)]


def _translate(dx: float, dy: float, dz: float) -> list:
    return [[1.0, 0.0, 0.0, dx],
            [0.0, 1.0, 0.0, dy],
            [0.0, 0.0, 1.0, dz],
            [0.0, 0.0, 0.0, 1.0]]


def world_matrix(transform, *, up: str = "z",
                 origin_offset=(0.0, 0.0)) -> list:
    """4×4 matrix (flat 16-list, **column-major** for three.js) mapping a raw
    splat-file vertex into the scene's three.js coordinates.

    ``transform`` is a :func:`src.scan_import.similarity_transform_2d` result
    ``(scale, theta_rad, tx, ty)`` — the georeference. ``up`` is the file's
    vertical axis (``"z"`` or ``"y"``), matching ``read_points``.
    ``origin_offset`` is ``(dx, dy)`` in projector metres to shift the
    projector origin onto the scene origin (see :func:`origin_offset`).

    The composition is ``M_axis · M_off · M_sim · M_up`` — file→z-up, the 2D
    similarity (uniform scale + rotation about vertical + xy translation, z
    scaled), projector→scene offset, then scene→three.js axis remap. All
    factors are rotations + positive uniform scale + translation, so the
    result is reflection-free and three.js can ``decompose`` it cleanly.
    """
    scale, theta, tx, ty = (float(transform[0]), float(transform[1]),
                            float(transform[2]), float(transform[3]))
    dx, dy = float(origin_offset[0]), float(origin_offset[1])

    if up.lower() == "y":
        # file (x, y_up, z_fwd) → z-up (x, -z_fwd, y_up)
        m_up = _mat4([[1, 0, 0], [0, 0, -1], [0, 1, 0]])
    else:
        m_up = _mat4([[1, 0, 0], [0, 1, 0], [0, 0, 1]])

    c, s = math.cos(theta), math.sin(theta)
    m_sim = [[scale * c, -scale * s, 0.0, tx],
             [scale * s,  scale * c, 0.0, ty],
             [0.0,        0.0,       scale, 0.0],
             [0.0,        0.0,       0.0, 1.0]]

    m_off = _translate(dx, dy, 0.0)

    # scene (x_e, y_n, z_up) → three (x_e, z_up, -y_n)
    m_axis = _mat4([[1, 0, 0], [0, 0, 1], [0, -1, 0]])

    m = _matmul(m_axis, _matmul(m_off, _matmul(m_sim, m_up)))
    # three.js Matrix4.elements is column-major: index = col * 4 + row.
    return [m[row][col] for col in range(4) for row in range(4)]


# ── geographic footprint ─────────────────────────────────────────────────────

def latlng_bbox(aligned_points, projector) -> dict:
    """Lat/lng bounding box of a georeferenced (projector-frame) cloud:
    ``{"south", "north", "west", "east"}``. ``aligned_points`` is the
    ``align_scan`` output; ``projector`` its returned frame."""
    xs = aligned_points[:, 0]
    ys = aligned_points[:, 1]
    min_x, max_x = float(xs.min()), float(xs.max())
    min_y, max_y = float(ys.min()), float(ys.max())
    # Project the four corners; cosLat frame is axis-aligned to N/E so the
    # extreme lat/lng sit at the corners.
    corners = [projector.to_latlng(x, y)
               for x in (min_x, max_x) for y in (min_y, max_y)]
    lats = [la for (la, _ln) in corners]
    lngs = [ln for (_la, ln) in corners]
    return {"south": min(lats), "north": max(lats),
            "west": min(lngs), "east": max(lngs)}


def origin_offset(feature_origin: dict, scene_lat: float,
                  scene_lng: float) -> tuple:
    """``(dx, dy)`` projector-metre offset moving the splat's stored origin
    onto the live scene origin — same convention scene_contract uses to
    re-frame scan points (constant shift between two cosLat frames)."""
    from src.projection import metres_per_deg
    m_lat, m_lng = metres_per_deg(scene_lat)
    dx = (float(feature_origin.get("lng", scene_lng)) - scene_lng) * m_lng
    dy = (float(feature_origin.get("lat", scene_lat)) - scene_lat) * m_lat
    return dx, dy


# ── persistence: the splat_backdrop GeoJSON feature ──────────────────────────

def _bbox_ring(bbox: dict) -> list:
    """Closed lng/lat ring (GeoJSON order) for a lat/lng bbox."""
    s, n = bbox["south"], bbox["north"]
    w, e = bbox["west"], bbox["east"]
    return [[w, s], [e, s], [e, n], [w, n], [w, s]]


def build_feature(*, file_path: str, origin: dict, transform, up: str,
                  bbox: dict, ortho_png: Optional[str] = None,
                  opacity: float = _DEFAULT_OPACITY,
                  name: str = "Yard scan") -> dict:
    """A ``splat_backdrop`` GeoJSON Feature persisting one georeferenced splat.

    The big ``.ply`` is referenced by absolute ``file_path`` (50–200 MB — never
    embedded); the baked top-down ``ortho_png`` data URL **is** embedded so the
    2D map layer reloads instantly without re-loading the splat. The geometry
    is the lat/lng footprint ring so the splat still shows an extent on the map
    even if the file later goes missing.
    """
    scale, theta, tx, ty = transform
    props = {
        "element_type": ELEMENT_TYPE,
        "name": name,
        "file_path": file_path,
        "origin": {"lat": float(origin["lat"]), "lng": float(origin["lng"])},
        "transform": {"scale": float(scale), "theta_rad": float(theta),
                      "tx": float(tx), "ty": float(ty)},
        "up_axis": up,
        "bbox": {k: float(bbox[k]) for k in ("south", "north", "west", "east")},
        "ortho_opacity": float(opacity),
    }
    if ortho_png:
        props["ortho_png"] = ortho_png
    return {
        "type": "Feature",
        "geometry": {"type": "Polygon", "coordinates": [_bbox_ring(bbox)]},
        "properties": props,
    }


def feature_from_project(project: dict) -> Optional[dict]:
    """The project's splat_backdrop feature (the latest wins), or ``None``."""
    found = None
    for f in project.get("features", []):
        if (f.get("properties", {}) or {}).get("element_type") == ELEMENT_TYPE:
            found = f
    return found


def transform_tuple(feature: dict) -> tuple:
    """``(scale, theta_rad, tx, ty)`` from a splat_backdrop feature."""
    t = (feature.get("properties", {}) or {}).get("transform", {}) or {}
    return (float(t.get("scale", 1.0)), float(t.get("theta_rad", 0.0)),
            float(t.get("tx", 0.0)), float(t.get("ty", 0.0)))


def scene_field(feature: dict, scene_lat: float, scene_lng: float) -> dict:
    """Placement spec for the Scene JSON ``splat`` field (consumed by the 3D
    viewer's splat loader).

    Returns ``{"path", "matrix", "opacity"}`` — ``path`` the absolute splat
    file (the ``Map3DWidget`` turns it into a ``file://`` URL for Spark and
    skips loading if it's missing), ``matrix`` the 16-element column-major
    world matrix placing the splat into a scene at the given origin, and the
    splat render opacity. No filesystem check here so the contract stays pure
    and unit-testable; file presence is the widget's concern.
    """
    props = feature.get("properties", {}) or {}
    off = origin_offset(props.get("origin", {}) or {}, scene_lat, scene_lng)
    return {
        "path": props.get("file_path", ""),
        "matrix": world_matrix(transform_tuple(feature),
                               up=props.get("up_axis", "z"),
                               origin_offset=off),
        "opacity": float(props.get("ortho_opacity", _DEFAULT_OPACITY)),
    }


def ortho_overlay_payload(feature: dict) -> Optional[dict]:
    """``{"image", "bbox", "opacity"}`` for the 2D map overlay, or ``None``
    when no baked PNG is stored yet."""
    props = feature.get("properties", {}) or {}
    png = props.get("ortho_png")
    if not png:
        return None
    return {"image": png, "bbox": props.get("bbox", {}),
            "opacity": float(props.get("ortho_opacity", _DEFAULT_OPACITY))}
