"""
map3d_js.py — Python→JS builders for the embedded map3d 3D view (V1.56).

Mirrors ``src/map_js.py``: every Python→JS call is built here with ``json.dumps``
so callers (a ``Map3DWidget``/``QWebEngineView`` hosting the map3d fork under
``web3d/``) never format JavaScript by hand.

The 3D scene exposes ``window.permaSetSun(azimuthDeg, altitudeDeg)`` (added to
the map3d fork's ``src/state/sunStore.ts``), which points a shadow-casting
``THREE.DirectionalLight`` — so the 3D shadows track the *same* sun path as the
2D shade engine when we drive them from ``src/solar.py``. Angles follow the
project convention: azimuth degrees clockwise from north (0 = N, 90 = E,
180 = S, 270 = W); altitude degrees above the horizon.
"""

from __future__ import annotations

import json
from datetime import datetime, timedelta
from typing import Optional


def set_sun(azimuth_deg: float, altitude_deg: float) -> str:
    """JS to point the 3D scene's sun — and the shadows it casts — at a given
    azimuth (deg clockwise from north) and altitude (deg above the horizon).
    Guarded with ``&&`` so it is a no-op until the scene has registered the hook."""
    return ("window.permaSetSun && window.permaSetSun("
            f"{json.dumps(float(azimuth_deg))}, {json.dumps(float(altitude_deg))});")


def set_sun_for(lat: float, lng: float, when: datetime) -> Optional[str]:
    """Convenience: compute the sun position for ``lat``/``lng`` at local solar
    time ``when`` (reusing ``src/solar.sun_position``) and return the JS to apply
    it, or ``None`` when the sun is at/below the horizon (no meaningful shadow).

    ``when`` is a naive *local* solar datetime, matching ``shade.shade_grid_at`` —
    ``solar.sun_position`` expects UTC and re-derives local solar time from the
    longitude, so we shift by ``-lng/15`` here for consistency with the 2D engine."""
    from src.solar import sun_position
    sun = sun_position(lat, lng, when + timedelta(hours=-lng / 15.0))
    if sun.altitude <= 0:
        return None
    return set_sun(sun.azimuth, sun.altitude)


def set_scene(scene: dict) -> str:
    """JS to (re)build the whole 3D scene from a Scene JSON dict
    (``src.scene_contract.build_scene`` output: terrain, buildings, plants,
    boundary, structures, sun — all in local metres). Guarded with ``&&``
    so it's a no-op until the viewer registers ``window.permaSetScene``."""
    return ("window.permaSetScene && window.permaSetScene("
            f"{json.dumps(scene or {})});")


def capture_ortho(rect: dict, width: int = 2048) -> str:
    """JS to bake a top-down orthographic render of the loaded Gaussian-splat
    backdrop into a PNG, for the 2D map's "yard photo" overlay (V1.65).

    ``rect`` frames the camera to an exact scene-metre rectangle
    ``{min_x, max_x, min_y, max_y}`` (east/north) so the PNG maps 1:1 onto the
    splat's lat/lng bbox; ``width`` is the longest output edge in pixels. The
    result returns asynchronously via the widget's ``onOrthoBaked`` bridge
    slot (the splat may still be streaming when this fires). Guarded with
    ``&&`` so it's a no-op until the viewer registers ``permaCaptureOrtho``."""
    opts = {
        "min_x": float(rect["min_x"]), "max_x": float(rect["max_x"]),
        "min_y": float(rect["min_y"]), "max_y": float(rect["max_y"]),
        "width": int(width),
    }
    return ("window.permaCaptureOrtho && window.permaCaptureOrtho("
            f"{json.dumps(opts)});")


def clear_splat() -> str:
    """JS to remove the Gaussian-splat backdrop from the scene. Guarded with
    ``&&`` so it's a no-op until the viewer registers ``permaClearSplat``."""
    return "window.permaClearSplat && window.permaClearSplat();"


def set_plants(records: list) -> str:
    """JS to (re)populate the 3D scene with placed plants. ``records`` are the
    per-plant 3D-state dicts from ``src.scene3d.placed_plants_3d_state`` (lat /
    lng / height_m / canopy_m / scale_factor / presence_opacity / plant_type /
    plant_id). Guarded with ``&&`` so it's a no-op until the scene registers the
    ``window.permaSetPlants`` hook."""
    return ("window.permaSetPlants && window.permaSetPlants("
            f"{json.dumps(records or [])});")


def set_bee_mode(on: bool) -> str:
    """JS to enter/leave the "fly as a bee" first-person mode in the built-in
    viewer (F37 increment 2). When on, OrbitControls is disabled and a low fly
    camera + bee-vision overlay take over; when off, the orbit view is restored.
    Guarded with ``&&`` so it's a no-op until the viewer registers the hook."""
    return ("window.permaSetBeeMode && window.permaSetBeeMode("
            f"{json.dumps(bool(on))});")


def set_bee_targets(plant_ids: list, bee_label: str = "",
                    kind: str = "bee", host_ids: list = None,
                    appearance: dict = None) -> str:
    """JS to mark the plants a chosen pollinator uses, so the fly-through floats
    a glowing nectar beacon over each one (F37 increment 2; lepidoptera V2.12).

    ``plant_ids`` are the ADULT nectar plants (DB ids from
    ``bee_habitat.target_plant_ids_for_bee`` / ``lep_habitat.nectar_plant_ids_for_lep``);
    the viewer shows a beacon only for those present AND in bloom for the scene
    month. ``bee_label`` is the creature's display name for the HUD. ``kind`` is
    ``'bee'`` | ``'butterfly'`` | ``'moth'`` and selects the flying avatar.
    ``host_ids`` are larval-host plant ids (butterflies/moths) shown as
    "caterpillar nursery" markers — present-gated, not bloom-gated, and never
    collectable. ``appearance`` is the flown creature's look spec (from
    ``scene_wildlife.appearance_for_fauna``) so the avatar matches the species —
    a green sweat bee ≠ a bumble bee. Guarded with ``&&``."""
    ids = [int(p) for p in (plant_ids or [])]
    hosts = [int(p) for p in (host_ids or [])]
    return ("window.permaSetBeeTargets && window.permaSetBeeTargets("
            f"{json.dumps(ids)}, {json.dumps(str(bee_label or ''))}, "
            f"{json.dumps(str(kind or 'bee'))}, {json.dumps(hosts)}, "
            f"{json.dumps(appearance or None)});")


def set_wildlife(creatures: list) -> str:
    """JS to populate the scene with ambient wildlife — the animals the design's
    plants support, each on/near a plant it uses, with a per-species appearance
    spec (V2.12). ``creatures`` is ``src.scene_wildlife.wildlife_for_scene``
    output. Shown in the orbit + walk views (hidden while flying as one creature).
    Guarded with ``&&`` so it's a no-op until the viewer registers the hook."""
    return ("window.permaSetWildlife && window.permaSetWildlife("
            f"{json.dumps(creatures or [])});")


def set_walk_mode(on: bool) -> str:
    """JS to enter/leave the third-person "walk the garden" mode (V2.12): a
    walking human avatar with a follow camera, strolling among the ambient
    wildlife. Guarded with ``&&`` so it's a no-op until the viewer registers
    ``window.permaSetWalkMode``."""
    return ("window.permaSetWalkMode && window.permaSetWalkMode("
            f"{json.dumps(bool(on))});")


def set_bee_tour(on: bool) -> str:
    """JS to toggle the seasonal nectar tour in the fly-through (V2.12): the
    flyer auto-hops flower to flower, and the host advances the scene month
    underneath it so blooms come and go across the year. Guarded with ``&&`` so
    it's a no-op until the viewer registers ``window.permaSetBeeTour``."""
    return ("window.permaSetBeeTour && window.permaSetBeeTour("
            f"{json.dumps(bool(on))});")


def set_quality(level: int) -> str:
    """JS to set the viewer's geometry detail (0 Low · 1 Medium · 2 High). The
    viewer drops its archetype caches and re-renders the current scene at the new
    density (build-time only). Guarded with ``&&`` so it's a no-op until the scene
    registers ``window.permaSetQuality``."""
    return ("window.permaSetQuality && window.permaSetQuality("
            f"{int(level)});")
