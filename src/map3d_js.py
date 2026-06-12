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


def set_plants(records: list) -> str:
    """JS to (re)populate the 3D scene with placed plants. ``records`` are the
    per-plant 3D-state dicts from ``src.scene3d.placed_plants_3d_state`` (lat /
    lng / height_m / canopy_m / scale_factor / presence_opacity / plant_type /
    plant_id). Guarded with ``&&`` so it's a no-op until the scene registers the
    ``window.permaSetPlants`` hook."""
    return ("window.permaSetPlants && window.permaSetPlants("
            f"{json.dumps(records or [])});")
