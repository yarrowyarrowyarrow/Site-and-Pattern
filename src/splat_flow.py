"""
src/splat_flow.py — map-side wiring for the Gaussian-splat backdrop (V1.65).

The Qt-free maths and persistence live in :mod:`src.splat_backdrop`; this
module is the thin glue that moves a baked top-down render onto the 2D map and
keeps the "Yard photo" View toggle in sync with the project. Kept as free
functions taking ``main`` (never new MainWindow methods), mirroring
:func:`src.scan_import_dialog.start_scan_import`, so the architecture guard's
method ceiling stays meaningful.
"""

from __future__ import annotations

from src import splat_backdrop


def restore_splat_overlay(main) -> None:
    """On project open (and after an import): redraw the 2D "yard photo"
    overlay from the splat feature's embedded PNG and enable the View toggle —
    or clear it and disable the toggle when the project has no splat."""
    feature = splat_backdrop.feature_from_project(main._project)
    payload = splat_backdrop.ortho_overlay_payload(feature) if feature else None
    if payload:
        main.map_widget.draw_splat_ortho_overlay(
            payload["image"], payload["bbox"], payload["opacity"])
        main.toolbar.set_yard_photo_available(True, checked=True)
    else:
        main.map_widget.clear_splat_ortho()
        # A splat with no baked PNG yet still enables the toggle (the user can
        # bake it from the 3D preview); no splat at all disables it.
        main.toolbar.set_yard_photo_available(bool(feature), checked=False)


def apply_baked_ortho(main, feature: dict, data_url) -> bool:
    """Store a freshly baked top-down PNG on the splat ``feature``, draw it on
    the map, and switch the toggle on. Returns ``False`` (with no side effects)
    when the bake produced no image — splat still streaming, or no WebGL."""
    if (not data_url or not isinstance(data_url, str)
            or not data_url.startswith("data:image")):
        return False
    feature.setdefault("properties", {})["ortho_png"] = data_url
    payload = splat_backdrop.ortho_overlay_payload(feature)
    main.map_widget.draw_splat_ortho_overlay(
        payload["image"], payload["bbox"], payload["opacity"])
    main.toolbar.set_yard_photo_available(True, checked=True)
    main._mark_modified()
    return True
