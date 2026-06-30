"""
src/site_photo_flow.py — map-side wiring for the site photo overlay (F24).

The Qt-free maths and persistence live in :mod:`src.site_photo`; this module is
the thin glue that loads an image file, embeds it on the project's ``site_photo``
feature, and keeps the 2D map overlay + the Site panel's controls in sync. Kept
as free functions taking ``main`` (never new MainWindow methods — it is at the
architecture-guard method ceiling), mirroring :mod:`src.splat_flow`.

Design principle P11 (the body and the site know things the screen does not) —
see docs/DESIGN_PHILOSOPHY.md.
"""

from __future__ import annotations

import base64
from typing import Optional

from src import site_photo


# Scaled-down embed bound: keeps the project file reasonable while staying sharp
# enough as a yard underlay (the original file is never stored).
_MAX_EMBED_DIM = 1600


def _image_to_data_url(path: str) -> tuple[Optional[str], float]:
    """Load ``path``, scale it under ``_MAX_EMBED_DIM``, and return
    ``(data_url, aspect)`` where ``aspect`` is the original height/width ratio.
    Returns ``(None, 1.0)`` if the image can't be read."""
    from PyQt6.QtGui import QImage
    from PyQt6.QtCore import QByteArray, QBuffer, QIODevice, Qt
    img = QImage(path)
    if img.isNull():
        return None, 1.0
    w, h = img.width(), img.height()
    aspect = (h / w) if w else 1.0
    if max(w, h) > _MAX_EMBED_DIM:
        img = img.scaled(_MAX_EMBED_DIM, _MAX_EMBED_DIM,
                         Qt.AspectRatioMode.KeepAspectRatio,
                         Qt.TransformationMode.SmoothTransformation)
    ba = QByteArray()
    buf = QBuffer(ba)
    buf.open(QIODevice.OpenModeFlag.WriteOnly)
    img.save(buf, "JPEG", 82)
    buf.close()
    b64 = base64.b64encode(bytes(ba)).decode("ascii")
    return f"data:image/jpeg;base64,{b64}", aspect


def _placement_center(main) -> Optional[dict]:
    """Where to centre a freshly imported photo: the property pin if one is set,
    else the current map centre. ``None`` when neither is known."""
    lat = getattr(main.site_panel, "_lat", None)
    lng = getattr(main.site_panel, "_lng", None)
    if lat is not None and lng is not None:
        return {"lat": float(lat), "lng": float(lng)}
    center = main.map_widget.last_center()
    if center:
        return {"lat": float(center[0]), "lng": float(center[1])}
    return None


def _push_panel_state(main, feature: Optional[dict], *, visible: bool = True):
    """Reflect the current site-photo feature into the Site panel's controls."""
    if feature is None:
        main.site_panel.set_site_photo_state(False)
        return
    props = feature.get("properties", {}) or {}
    main.site_panel.set_site_photo_state(
        True,
        width_m=float(props.get("width_m", 30.0)),
        opacity=float(props.get("opacity", 0.7)),
        visible=visible,
        name=str(props.get("name", "Site photo")),
    )


def import_site_photo(main, path: str) -> bool:
    """Load an image file, place it centred on the pin / map centre, embed it on
    the project, draw it, and update the panel. Returns False (with a status
    message) when the image can't be read or there's nowhere to place it."""
    if not path:
        return False
    data_url, aspect = _image_to_data_url(path)
    if not data_url:
        main.statusBar().showMessage("Couldn't read that image.", 4000)
        return False
    center = _placement_center(main)
    if center is None:
        main.statusBar().showMessage(
            "Drop a property pin or pan the map first, then add a site photo.",
            5000)
        return False
    import os
    feature = site_photo.build_feature(
        image=data_url, center=center, width_m=site_photo._DEFAULT_WIDTH_M,
        aspect=aspect, name=os.path.basename(path) or "Site photo")
    site_photo.set_feature(main._project, feature)
    payload = site_photo.overlay_payload(feature)
    main.map_widget.draw_site_photo_overlay(
        payload["image"], payload["bbox"], payload["opacity"])
    _push_panel_state(main, feature, visible=True)
    main._mark_modified()
    main.statusBar().showMessage(
        "Site photo added — set its width and opacity on the Field Notes tab.",
        4000)
    return True


def restore_site_photo(main) -> None:
    """On project open / new: redraw the site photo overlay from the project (or
    clear it) and sync the panel controls."""
    feature = site_photo.feature_from_project(main._project)
    payload = site_photo.overlay_payload(feature) if feature else None
    if payload:
        main.map_widget.draw_site_photo_overlay(
            payload["image"], payload["bbox"], payload["opacity"])
    else:
        main.map_widget.clear_site_photo()
    _push_panel_state(main, feature, visible=True)


def set_width(main, width_m: float) -> None:
    """Resize the on-map photo to a new real-world width and redraw."""
    feature = site_photo.feature_from_project(main._project)
    if feature is None:
        return
    site_photo.set_width(feature, width_m)
    payload = site_photo.overlay_payload(feature)
    if payload:
        main.map_widget.draw_site_photo_overlay(
            payload["image"], payload["bbox"], payload["opacity"])
    main._mark_modified()


def set_opacity(main, opacity: float) -> None:
    """Update the photo overlay's opacity (live on the map)."""
    feature = site_photo.feature_from_project(main._project)
    if feature is None:
        return
    site_photo.set_opacity(feature, opacity)
    main.map_widget.set_site_photo_opacity(
        float(feature["properties"]["opacity"]))
    main._mark_modified()


def clear_site_photo(main) -> None:
    """Remove the site photo from the project and the map."""
    removed = site_photo.clear_from_project(main._project)
    main.map_widget.clear_site_photo()
    _push_panel_state(main, None)
    if removed:
        main._mark_modified()
