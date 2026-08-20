"""
before_after_flow.py — capturing the three panels (F76, V2.56).

Design principle P13 (a native planting has to be loved to survive) — see
docs/DESIGN_PHILOSOPHY.md.

The Qt-free half is :mod:`src.before_after`: which panels, which years, which
camera, what to caption them. This is the half that needs the viewer — set the
scene to each panel's moment, wait for a frame, capture it, move on — and it
lives outside ``scene3d_window`` because that file is at 914 lines against a
950-line ceiling and this is ~90 lines of asynchronous chaining.

**Why it is a chain rather than three calls.** ``Scene3DWindow._render_still``
already documents the reason for one still: *"the sliders have to re-push the
scene and the camera preset has to land in the viewer before the renderer is
asked for a frame, and the bridge is one-directional so there is nothing to
await."* Three panels is that, three times, each waiting on the last.

Two safeguards, both taken from ``sprite_gallery_window``, which solved this
first for its contact sheet:

* **A run token.** A second export started while the first is in flight would
  otherwise interleave — two runs pushing scenes at one viewer and filling one
  result list. Every callback checks the token and a stale run returns.
* **Waiting for the models.** Baked GLB archetypes load asynchronously and
  rebuild the scene when they arrive. Capture before that and you get the
  procedural fallback — *which looks like a finished answer and is not the one
  the app draws.* Bounded retries, then go with what is there, because a
  slightly wrong picture beats a export that silently never finishes.
"""

from __future__ import annotations

from typing import Callable, Optional

#: Milliseconds between setting a panel's moment and asking for its frame. The
#: same 450 ms ``_render_still`` uses — the scene push and the camera preset
#: both have to land, and there is nothing to await on a one-way bridge.
SETTLE_MS = 450

#: How long to wait for the baked models, in 100 ms ticks, before giving up and
#: rendering whatever geometry is loaded.
MODEL_TRIES = 60


def on_before_after(win) -> None:
    """Render the three panels and hand them to the main window.

    Stored on the main window rather than written to a file: the page belongs in
    the PDF beside the planting plan and the buy list, and ``export_pdf`` is
    synchronous while this capture is a chain of callbacks — the same reason the
    presentation still is passed in rather than rendered during export.
    """
    from src import before_after as ba

    panels = ba.panel_specs(win._main._project)
    win._ba_btn.setEnabled(False)
    win._main.statusBar().showMessage("Rendering before / after…", 0)

    def _done(captured):
        win._ba_btn.setEnabled(True)
        # Fewer than two panels is not a comparison, so it is a failure rather
        # than a thinner page.
        if len(captured) < 2:
            win._main.statusBar().showMessage(
                "Could not render the panels — let the 3D view finish loading "
                "and try again.", 6000)
            return
        win._main._before_after = (captured, ba.page_caption(panels))
        win._main.statusBar().showMessage(
            f"{len(captured)} panels ready — included in your next PDF export "
            f"(File → Export PDF).", 8000)

    capture_panels(win, panels, _done)


def _later(ms: int, fn) -> None:
    """Run ``fn`` after ``ms`` milliseconds.

    Indirected through one function so a test can drive the whole chain
    synchronously by replacing it. That is not a convenience: driving this chain
    with a real Qt event loop means calling ``processEvents`` mid-suite, and
    with the full test suite's modules imported that **segfaults** — verified
    with ``-X faulthandler``, which put the abort inside the test's own pump.
    The sequencing is what has bugs in it; the one-line ``QTimer.singleShot``
    below is not, and it is not worth crashing the suite to assert.
    """
    from PyQt6.QtCore import QTimer
    QTimer.singleShot(ms, fn)


def pixmap_from_data_url(url):
    """``QPixmap`` from a ``data:image/...;base64,...`` URL, or ``None``.

    An unloaded viewer returns ``''``, so this has to degrade to None rather
    than raise in the middle of a three-panel chain.
    """
    import base64

    from PyQt6.QtGui import QPixmap

    if not url or "," not in url:
        return None
    try:
        raw = base64.b64decode(url.split(",", 1)[1])
    except Exception:                                      # noqa: BLE001
        return None
    pix = QPixmap()
    return pix if pix.loadFromData(raw) else None


def capture_panels(win, panels: list, on_done: Callable,
                   *, on_progress: Optional[Callable] = None) -> int:
    """Render every render-panel in ``panels``, then call ``on_done``.

    ``on_done`` receives ``[(title, pixmap, caption), …]`` in panel order, with
    any panel that failed to render dropped — so a caller gets a short list
    rather than a list with holes in it. Returns the run token.

    Photo panels need no viewer and are decoded up front.
    """
    win._ba_run = getattr(win, "_ba_run", 0) + 1
    run = win._ba_run
    results: dict = {}

    from src.before_after import (
        KIND_PHOTO, install_day_panel, render_requests,
    )

    # Photo panels need no viewer — decode them up front. A photo that will not
    # decode falls back to the year-0 render **in place**, rather than being
    # dropped: losing the before-panel would leave a two-panel page with no
    # before, which is the whole argument gone, and silently.
    for i, p in enumerate(list(panels)):
        if p.get("kind") != KIND_PHOTO:
            continue
        pix = pixmap_from_data_url(p.get("image"))
        if pix is not None:
            results[p.get("id")] = pix
        else:
            # Match the camera the rest of the page uses, or the fallback
            # renders from a different viewpoint and stops being a comparison.
            cam = next((q.get("camera") for q in panels
                        if q.get("kind") != KIND_PHOTO and q.get("camera")),
                       None)
            panels[i] = (install_day_panel(cam) if cam
                         else install_day_panel())

    queue = list(render_requests(panels))
    if not queue:
        _finish(win, run, panels, results, on_done)
        return run
    _wait_for_models(win, run, 0, queue, panels, results, on_done, on_progress)
    return run


def _stale(win, run: int) -> bool:
    return getattr(win, "_ba_run", 0) != run


def _wait_for_models(win, run, tries, queue, panels, results, on_done,
                     on_progress):
    if _stale(win, run):
        return
    if tries > MODEL_TRIES:
        _render_next(win, run, queue, panels, results, on_done, on_progress)
        return

    def got(ready):
        if _stale(win, run):
            return
        if ready:
            _render_next(win, run, queue, panels, results, on_done, on_progress)
        else:
            _later(100, lambda: _wait_for_models(
                win, run, tries + 1, queue, panels, results, on_done,
                on_progress))

    try:
        win.viewer.models_ready(got)
    except Exception:                                      # noqa: BLE001
        _render_next(win, run, queue, panels, results, on_done, on_progress)


def _render_next(win, run, queue, panels, results, on_done, on_progress):
    """Set the next panel's moment, let it land, capture it, recurse."""
    if _stale(win, run):
        return
    if not queue:
        _finish(win, run, panels, results, on_done)
        return

    panel_id, req = queue.pop(0)
    if on_progress is not None:
        on_progress(panel_id, len(results), len(panels))

    for widget, value in ((win._year, req["year"]),
                          (win._month, req.get("month", 7))):
        widget.blockSignals(True)
        widget.setValue(value)
        widget.blockSignals(False)
    win._update_labels()
    win._push_scene()
    win.viewer.set_camera_preset(req["camera"])

    def _capture():
        if _stale(win, run):
            return

        def _done(url):
            if _stale(win, run):
                return
            pix = pixmap_from_data_url(url)
            if pix is not None:
                results[panel_id] = pix
            _later(0, lambda: _render_next(
                win, run, queue, panels, results, on_done, on_progress))

        win.viewer.snapshot(_done, px=req["width"], height=req["height"],
                            pixel_ratio=req["pixel_ratio"],
                            mime="image/png", quality=1.0)

    _later(SETTLE_MS, _capture)


def _finish(win, run, panels, results, on_done):
    if _stale(win, run):
        return
    out = [(p.get("title", ""), results[p["id"]], p.get("caption", ""))
           for p in panels if p.get("id") in results]
    on_done(out)
